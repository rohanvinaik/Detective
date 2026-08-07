"""Deterministic dependency-clustering decomposition — find the responsibility
seams in a function and propose contiguous-block extractions.

Ported from LintGate's ``structure_checks/dependency_clustering`` (the deterministic
partition it has validated across hundreds of functions). The two systems complete
one loop: **LintGate finds the seam deterministically here; Detective proves the
extraction behavior-preserving** (via the mutation profile) before it is applied.

The algorithm (V1 — contiguous groups only): enumerate every contiguous run of
top-level statements; for each, compute its interface by def-use —
  * inputs  = names it reads that were defined before it (become parameters)
  * outputs = names it writes that are read after it (become return values)
— and keep the block only when it is *single-exit* (no return/break/continue
crossing the boundary), has a *small interface* (≤ max_params inputs, ≤ max_outputs
outputs), and is *worth it* (cognitive complexity ≥ a floor). Overlapping candidates
are resolved greedily by complexity reduction. The whole thing is deterministic.

Detective adds one gate LintGate's structural linter does not: the function must be
behaviorally ENTANGLED — 2+ surviving mutation categories — before we decompose,
because that is the signal that it is doing more than one thing.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from .cognitive_complexity import compute_cognitive_complexity

_MAX_BLOCK_STMTS = 20  # cap block width to avoid quadratic blowup
_MIN_BLOCK_CC = 3  # a block below this complexity is not worth extracting
_MAX_CANDIDATES = 3  # base cap on suggestions per function (scales with CC)


@dataclass(frozen=True)
class ExtractionCandidate:
    """A contiguous statement block proposed for extraction, with its def-use
    interface and the line span (straight from the AST) it occupies."""

    start_line: int
    end_line: int
    proposed_name: str
    inputs: tuple[str, ...]  # → parameters
    outputs: tuple[str, ...]  # → return values
    cc_reduction: int  # cognitive complexity removed from the parent
    confidence: float
    reason: str


@dataclass(frozen=True)
class DecompositionPlan:
    """The proposed decomposition of a function."""

    function: str
    is_decomposable: bool
    candidates: tuple[ExtractionCandidate, ...]
    rationale: str


# ── Statement-level def-use analysis ────────────────────────────────────


@dataclass(frozen=True)
class _StmtInfo:
    index: int
    stmt: ast.stmt
    reads: frozenset[str]
    writes: frozenset[str]
    has_exit: bool
    flow: _Flow


def _collect_reads(node: ast.AST) -> set[str]:
    return {c.id for c in ast.walk(node) if isinstance(c, ast.Name) and isinstance(c.ctx, ast.Load)}


def _collect_writes(node: ast.AST) -> set[str]:
    return {
        c.id for c in ast.walk(node) if isinstance(c, ast.Name) and isinstance(c.ctx, (ast.Store, ast.Del))
    }


def _target_names(node: ast.expr) -> set[str]:
    """Plain names BOUND by an assignment target (descends tuple/list/starred).
    A Subscript/Attribute target mutates an existing object and binds nothing."""
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, ast.Starred):
        return _target_names(node.value)
    if isinstance(node, (ast.Tuple, ast.List)):
        names: set[str] = set()
        for elt in node.elts:
            names |= _target_names(elt)
        return names
    return set()


def _target_uses(node: ast.expr) -> set[str]:
    """Names an assignment target READS to locate its store site (``d[k] = v``
    reads ``d`` and ``k``; a plain ``x = v`` reads nothing)."""
    if isinstance(node, ast.Name):
        return set()
    if isinstance(node, ast.Starred):
        return _target_uses(node.value)
    if isinstance(node, (ast.Tuple, ast.List)):
        names: set[str] = set()
        for elt in node.elts:
            names |= _target_uses(elt)
        return names
    return _expr_uses(node)


def _expr_uses(node: ast.AST, bound: frozenset[str] = frozenset()) -> set[str]:
    """Names ``node`` reads from the enclosing function scope. Comprehension
    targets and lambda bodies are their own scopes and do not leak; a
    comprehension's iterables/conditions evaluate in sequence, each seeing the
    targets bound so far."""
    if isinstance(node, ast.Name):
        return {node.id} - bound if isinstance(node.ctx, ast.Load) else set()
    if isinstance(node, ast.Lambda):
        uses: set[str] = set()
        for default in node.args.defaults:
            uses |= _expr_uses(default, bound)
        for default in node.args.kw_defaults:
            if default is not None:
                uses |= _expr_uses(default, bound)
        # Review finding 2: the lambda body's free variables are read from the
        # enclosing scope at call time — live-ins, not private to the lambda.
        uses |= _scope_free_uses(node) - set(bound)
        return uses
    if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
        uses = set()
        inner = set(bound)
        for gen in node.generators:
            uses |= _expr_uses(gen.iter, frozenset(inner))
            inner |= _target_names(gen.target)
            for cond in gen.ifs:
                uses |= _expr_uses(cond, frozenset(inner))
        if isinstance(node, ast.DictComp):
            uses |= _expr_uses(node.key, frozenset(inner))
            uses |= _expr_uses(node.value, frozenset(inner))
        else:
            uses |= _expr_uses(node.elt, frozenset(inner))
        return uses
    if isinstance(node, ast.NamedExpr):
        return _expr_uses(node.value, bound)
    uses = set()
    for child in ast.iter_child_nodes(node):
        uses |= _expr_uses(child, bound)
    return uses


def _walrus_defs(node: ast.AST) -> set[str]:
    """NamedExpr targets bind in the enclosing function scope (PEP 572) — even
    from inside a comprehension. Nested function/class/lambda scopes bind their
    own and are not descended."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
        return set()
    defs: set[str] = set()
    if isinstance(node, ast.NamedExpr) and isinstance(node.target, ast.Name):
        defs.add(node.target.id)
    for child in ast.iter_child_nodes(node):
        defs |= _walrus_defs(child)
    return defs


def _pattern_names(pattern: ast.pattern) -> set[str]:
    """Names a match pattern CAPTURES (MatchAs/MatchStar/MatchMapping rest)."""
    names: set[str] = set()
    if isinstance(pattern, ast.MatchAs) and pattern.name:
        names.add(pattern.name)
    elif isinstance(pattern, ast.MatchStar) and pattern.name:
        names.add(pattern.name)
    elif isinstance(pattern, ast.MatchMapping) and pattern.rest:
        names.add(pattern.rest)
    for child in ast.iter_child_nodes(pattern):
        if isinstance(child, ast.pattern):
            names |= _pattern_names(child)
    return names


def _pattern_uses(pattern: ast.pattern) -> set[str]:
    """Names a match pattern READS (MatchValue constants, MatchClass classes,
    MatchMapping keys)."""
    uses: set[str] = set()
    if isinstance(pattern, ast.MatchValue):
        uses |= _expr_uses(pattern.value)
    elif isinstance(pattern, ast.MatchClass):
        uses |= _expr_uses(pattern.cls)
    elif isinstance(pattern, ast.MatchMapping):
        for key in pattern.keys:
            uses |= _expr_uses(key)
    for child in ast.iter_child_nodes(pattern):
        if isinstance(child, ast.pattern):
            uses |= _pattern_uses(child)
    return uses


@dataclass(frozen=True)
class _Flow:
    """Ordered def-use summary of one statement (issue #6). ``uses`` are
    upward-exposed reads — consumed before any DEFINITE local definition, so the
    pre-statement value is what they see. ``must`` are names defined on every
    non-raising path; ``may`` on at least one. Order matters and sets alone
    cannot carry it: ``x += 1`` both reads and writes ``x``, and the read wins."""

    uses: frozenset[str]
    must: frozenset[str]
    may: frozenset[str]


def _flow_stmts(stmts: list[ast.stmt]) -> _Flow:
    """Sequential composition: a later read is upward-exposed unless an earlier
    statement MUST-defines the name (a may-def is not enough — the defining path
    may not have run)."""
    uses: set[str] = set()
    must: set[str] = set()
    may: set[str] = set()
    for stmt in stmts:
        flow = _flow_stmt(stmt)
        uses |= set(flow.uses) - must
        must |= flow.must
        may |= flow.may
    return _Flow(frozenset(uses), frozenset(must), frozenset(may))


# The four node kinds that OPEN a scope and carry a body. Named because the recursion below
# feeds itself from `nested`, so the parameter and that list must agree or one of them lies.
_Scope = ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | ast.Lambda


def _scope_free_uses(scope: _Scope) -> set[str]:
    """Approximate FREE VARIABLES of a nested scope — the outer names its body reads.

    Review finding 2: a class body executes at definition time, and a nested function
    or lambda closes over outer locals at call time — either way, a block containing
    the definition needs those names to exist, so they are live-ins of the extracted
    helper. Ignoring the bodies (the original rule 6 reading) produced extractions
    that raised ``NameError`` on names like ``hidden`` that only the nested body read.

    Free = reads − names bound in this scope (params, assignments, imports, nested
    def/class names), with deeper nested scopes contributing THEIR free variables.
    Approximate on purpose — comprehension/class-scope subtleties can over-subtract a
    shadowed name — and it errs toward extra inputs, which the interface-size gate and
    the proof gate both tolerate; a missing live-in is the direction that ships a
    broken helper.
    """
    bound: set[str] = set()
    reads: set[str] = set()
    nested: list[_Scope] = []

    def visit(n: ast.AST) -> None:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(n.name)
            nested.append(n)
            # decorators and defaults evaluate in THIS scope, not the nested one
            for dec in n.decorator_list:
                visit(dec)
            if not isinstance(n, ast.ClassDef):
                for default in n.args.defaults:
                    visit(default)
                for default in n.args.kw_defaults:
                    if default is not None:
                        visit(default)
            return
        if isinstance(n, ast.Lambda):
            nested.append(n)
            for default in n.args.defaults:
                visit(default)
            for default in n.args.kw_defaults:
                if default is not None:
                    visit(default)
            return
        if isinstance(n, ast.Name):
            if isinstance(n.ctx, ast.Load):
                reads.add(n.id)
            else:
                bound.add(n.id)
            return
        if isinstance(n, (ast.Global, ast.Nonlocal)):
            reads.update(n.names)  # resolve OUTSIDE this scope: free by declaration
            return
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            bound.update(alias.asname or alias.name.split(".")[0] for alias in n.names)
            return
        for child in ast.iter_child_nodes(n):
            visit(child)

    if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        a = scope.args
        bound |= {x.arg for x in a.posonlyargs + a.args + a.kwonlyargs}
        if a.vararg:
            bound.add(a.vararg.arg)
        if a.kwarg:
            bound.add(a.kwarg.arg)
    body = [scope.body] if isinstance(scope, ast.Lambda) else list(scope.body)
    for item in body:
        visit(item)
    free = set(reads)
    for sub in nested:
        free |= _scope_free_uses(sub)
    return free - bound


def _flow_stmt(stmt: ast.stmt) -> _Flow:  # noqa: C901 — a total dispatch over stmt kinds
    """One statement's ordered def-use flow. Composition rules (issue #6):
    RHS before targets; AugAssign target is load-then-store; branch must-defs
    intersect; loop bodies contribute only may-defs (zero iterations); nested
    function/class scopes are never descended."""
    walrus = frozenset(_walrus_defs(stmt))

    def flow(uses: set[str], must: set[str], may: set[str]) -> _Flow:
        return _Flow(frozenset(uses), frozenset(must), frozenset(may | must | walrus))

    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
        uses: set[str] = set()
        for dec in stmt.decorator_list:
            uses |= _expr_uses(dec)
        for default in stmt.args.defaults:
            uses |= _expr_uses(default)
        for default in stmt.args.kw_defaults:
            if default is not None:
                uses |= _expr_uses(default)
        # Review finding 2: the body's FREE variables are live-ins of any block that
        # carries the definition — the closure reads them from the enclosing scope.
        uses |= _scope_free_uses(stmt)
        return flow(uses, {stmt.name}, set())
    if isinstance(stmt, ast.ClassDef):
        uses = set()
        for node in [*stmt.decorator_list, *stmt.bases, *(k.value for k in stmt.keywords)]:
            uses |= _expr_uses(node)
        # A class body executes AT DEFINITION TIME: its free reads happen right here.
        uses |= _scope_free_uses(stmt)
        return flow(uses, {stmt.name}, set())
    if isinstance(stmt, ast.Assign):
        uses = _expr_uses(stmt.value)
        defs: set[str] = set()
        for target in stmt.targets:
            uses |= _target_uses(target)
            defs |= _target_names(target)
        return flow(uses, defs, set())
    if isinstance(stmt, ast.AnnAssign):
        # A function-local annotation is never evaluated; a bare ``x: int`` binds nothing.
        if stmt.value is None:
            return flow(set(), set(), set())
        uses = _expr_uses(stmt.value) | _target_uses(stmt.target)
        return flow(uses, _target_names(stmt.target), set())
    if isinstance(stmt, ast.AugAssign):
        # ``x += 1`` loads x, then stores it: the pre-statement value is consumed.
        uses = _expr_uses(stmt.value)
        if isinstance(stmt.target, ast.Name):
            uses.add(stmt.target.id)
            return flow(uses, {stmt.target.id}, set())
        uses |= _expr_uses(stmt.target)
        return flow(uses, set(), set())
    if isinstance(stmt, ast.If):
        body = _flow_stmts(stmt.body)
        orelse = _flow_stmts(stmt.orelse)
        uses = _expr_uses(stmt.test) | set(body.uses) | set(orelse.uses)
        # a missing else is an empty branch: its must-defs are {}, so the intersection is {}
        return flow(uses, set(body.must & orelse.must), set(body.may | orelse.may))
    if isinstance(stmt, (ast.For, ast.AsyncFor)):
        targets = _target_names(stmt.target)
        body = _flow_stmts(stmt.body)
        orelse = _flow_stmts(stmt.orelse)
        uses = _expr_uses(stmt.iter) | (set(body.uses) - targets) | set(orelse.uses)
        # zero iterations bind nothing: everything here is a may-def, never a must-def
        return flow(uses, set(), targets | set(body.may) | set(orelse.may))
    if isinstance(stmt, ast.While):
        body = _flow_stmts(stmt.body)
        orelse = _flow_stmts(stmt.orelse)
        uses = _expr_uses(stmt.test) | set(body.uses) | set(orelse.uses)
        return flow(uses, set(), set(body.may | orelse.may))
    if isinstance(stmt, (ast.With, ast.AsyncWith)):
        uses = set()
        bound: set[str] = set()
        for item in stmt.items:
            uses |= _expr_uses(item.context_expr, frozenset(bound))
            if item.optional_vars is not None:
                bound |= _target_names(item.optional_vars)
        body = _flow_stmts(stmt.body)
        uses |= set(body.uses) - bound
        return flow(uses, bound | set(body.must), set(body.may))
    if isinstance(stmt, ast.Try) or (hasattr(ast, "TryStar") and isinstance(stmt, ast.TryStar)):
        body = _flow_stmts(stmt.body)
        orelse = _flow_stmts(stmt.orelse)
        final = _flow_stmts(stmt.finalbody)
        uses = set(body.uses)
        may = set(body.may)
        handler_musts: list[frozenset[str]] = []
        for handler in stmt.handlers:
            if handler.type is not None:
                uses |= _expr_uses(handler.type)
            hflow = _flow_stmts(handler.body)
            huses = set(hflow.uses)
            hmay = set(hflow.may)
            if handler.name:
                # the exception name is bound before the handler body and DELETED after it
                huses -= {handler.name}
                hmay -= {handler.name}
            # the body may have raised at any point, so none of its defs are definite here
            uses |= huses
            may |= hmay
            handler_musts.append(hflow.must - ({handler.name} if handler.name else set()))
        uses |= set(orelse.uses) - set(body.must)
        may |= set(orelse.may)
        # finally runs whether or not the body completed: nothing before it is definite
        uses |= set(final.uses)
        may |= set(final.may)
        if stmt.handlers:
            # reached either via success (body ∪ else) or via some handler
            success = set(body.must) | set(orelse.must)
            via_handler: set[str] = set.intersection(*map(set, handler_musts)) if handler_musts else set()
            must = set(final.must) | (success & via_handler)
        else:
            # no handlers: an exception propagates, so reaching here means the body completed
            must = set(final.must) | set(body.must) | set(orelse.must)
        return flow(uses, must, may)
    if isinstance(stmt, ast.Match):
        uses = _expr_uses(stmt.subject)
        may = set()
        for case in stmt.cases:
            captures = _pattern_names(case.pattern)
            uses |= _pattern_uses(case.pattern)
            cuses = _expr_uses(case.guard) if case.guard is not None else set()
            cflow = _flow_stmts(case.body)
            uses |= (cuses | set(cflow.uses)) - captures
            may |= captures | set(cflow.may)
        # no case is guaranteed to match: may-defs only
        return flow(uses, set(), may)
    if isinstance(stmt, (ast.Import, ast.ImportFrom)):
        names = {alias.asname or alias.name.split(".")[0] for alias in stmt.names}
        return flow(set(), names, set())
    if isinstance(stmt, ast.Delete):
        uses = set()
        for target in stmt.targets:
            if isinstance(target, ast.Name):
                uses.add(target.id)  # ``del x`` needs x bound; the unbinding is ignored
            else:
                uses |= _expr_uses(target)
        return flow(uses, set(), set())
    if isinstance(stmt, (ast.Global, ast.Nonlocal, ast.Pass, ast.Break, ast.Continue)):
        return flow(set(), set(), set())
    if isinstance(stmt, (ast.Expr, ast.Return, ast.Raise, ast.Assert)):
        return flow(_expr_uses(stmt), set(), set())
    # unhandled statement kind: fall back to the flat walk — over-approximates uses
    # (safe: an extra input) and claims no must-defs (safe: more upward exposure upstream)
    return flow(set(_collect_reads(stmt)), set(), set(_collect_writes(stmt)))


def _has_exit_statement(node: ast.AST) -> bool:
    """True if ``node`` IS, or contains at THIS scope level, a return/break/continue — a
    jump that would change meaning if the block moved into a helper. Nested function/class
    scopes are not descended into (their returns are their own).

    The node ITSELF must be tested, not only its children. A bare ``return x`` standing as a
    block's own statement has no ``Return`` among its children — its child is the value
    expression — so a children-only check called it exit-free. A block could then swallow
    the function's own exit: the helper took the ``return``, and the caller, whose outputs
    are ``block_writes & post_reads`` with nothing after the block to read anything, got an
    empty interface and silently returned None. Only a return NESTED in an ``if`` was caught.
    """
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return False
    if isinstance(node, (ast.Return, ast.Break, ast.Continue)):
        return True
    return any(_has_exit_statement(child) for child in ast.iter_child_nodes(node))


def _analyze_statement(index: int, stmt: ast.stmt) -> _StmtInfo:
    return _StmtInfo(
        index=index,
        stmt=stmt,
        reads=frozenset(_collect_reads(stmt)),
        writes=frozenset(_collect_writes(stmt)),
        has_exit=_has_exit_statement(stmt),
        flow=_flow_stmt(stmt),
    )


def _get_param_names(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    args = func_node.args
    names = {a.arg for a in args.posonlyargs + args.args + args.kwonlyargs}
    if args.vararg:
        names.add(args.vararg.arg)
    if args.kwarg:
        names.add(args.kwarg.arg)
    return names


def _get_param_order(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[str, ...]:
    """The same names as :func:`_get_param_names`, in the order the signature declares
    them. The set is what membership tests want; this is what RENDERING wants — see
    :func:`_human_order`."""
    args = func_node.args
    ordered = [a.arg for a in args.posonlyargs + args.args]
    if args.vararg:
        ordered.append(args.vararg.arg)
    ordered += [a.arg for a in args.kwonlyargs]
    if args.kwarg:
        ordered.append(args.kwarg.arg)
    return tuple(ordered)


def _human_order(
    names: Iterable[str], param_order: Sequence[str], infos: Sequence[_StmtInfo]
) -> tuple[str, ...]:
    """Order an extracted interface the way a person would write the parameter list.

    Parameters of the ENCLOSING function come first, in signature order — a reader
    checking the helper's call against the caller's header should not have to re-sort it.
    Alphabetical (the previous rule) scrambles that reliably: the seam extracted from
    ``shipping_cost(weight_kg, distance_km, express, member)`` came back as
    ``(distance_km, express, member, weight_kg)``, which no one would have typed. Names
    bound inside the body follow, in the order the reader first meets them.

    Both keys are positional, so this is exactly as deterministic as sorting was — the
    trailing name key only breaks ties among names absent from the signature and from
    every statement, which cannot happen for a real interface but keeps the key total.
    """
    position = {name: i for i, name in enumerate(param_order)}
    first_seen: dict[str, int] = {}
    for info in infos:
        for name in info.writes | info.reads:
            first_seen.setdefault(name, info.index)
    unlisted = len(position)
    return tuple(sorted(names, key=lambda n: (position.get(n, unlisted), first_seen.get(n, len(infos)), n)))


def _compute_block_cc(stmts: list[ast.stmt]) -> int:
    dummy = ast.FunctionDef(
        name="_dummy",
        args=ast.arguments(
            posonlyargs=[], args=[], vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]
        ),
        body=stmts,
        decorator_list=[],
        returns=None,
        lineno=0,
        col_offset=0,
    )
    return compute_cognitive_complexity(dummy)


def _compute_block_variables(
    infos: list[_StmtInfo], start: int, end: int, param_names: set[str]
) -> tuple[set[str], set[str]] | None:
    """(inputs, outputs) for the contiguous block ``infos[start:end]``, or None when
    the block is not single-exit.

    Ordered composition of per-statement flows (issue #6). Inputs are the block's
    upward-exposed uses — reads no earlier block statement DEFINITELY defines —
    restricted to names that can exist before the block. The old set arithmetic
    ``(reads & pre) - writes`` erased exactly the read-before-write live-ins
    (``x += 1``, ``x = x + 1``), producing helpers with unbound locals. Outputs are
    the block's may-defs some later statement reads before redefining.
    """
    block = infos[start:end]
    if any(s.has_exit for s in block):
        return None
    uses: set[str] = set()
    must: set[str] = set()
    may: set[str] = set()
    for s in block:
        uses |= set(s.flow.uses) - must
        must |= s.flow.must
        may |= s.flow.may
    pre_defined: set[str] = set(param_names)
    for s in infos[:start]:
        pre_defined |= s.flow.may
    inputs = uses & pre_defined
    post_uses: set[str] = set()
    post_must: set[str] = set()
    for s in infos[end:]:
        post_uses |= set(s.flow.uses) - post_must
        post_must |= s.flow.must
    outputs = may & post_uses
    return inputs, outputs


def _assigns_only_boolean(var: str, block_stmts: Sequence[ast.stmt]) -> bool:
    """True when every assignment to ``var`` in the block is boolean-shaped.

    Boolean-shaped: a ``bool`` literal, a comparison, or a boolean operation over
    boolean-shaped operands (``a and b < c``). One non-boolean assignment anywhere
    disqualifies — a name must never promise a predicate the code does not keep.
    Requires at least one sighting: a var the block never assigns is not "all
    assignments boolean" vacuously, it is unknown.
    """

    def _boolish(expr: ast.expr) -> bool:
        if isinstance(expr, ast.Constant):
            return isinstance(expr.value, bool)
        if isinstance(expr, ast.Compare):
            return True
        if isinstance(expr, ast.BoolOp):
            return all(_boolish(v) for v in expr.values)
        if isinstance(expr, ast.UnaryOp):
            return isinstance(expr.op, ast.Not)
        return False

    seen = False
    for stmt in block_stmts:
        for node in ast.walk(stmt):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == var:
                    seen = True
                    if not _boolish(node.value):
                        return False
    return seen


# Return names that carry no naming signal — a helper called `_compute_out` / `_compute_result`
# is no better than `_helper`. When the single output is one of these, fall through to the honest
# parent-derived form rather than dress a throwaway up as a purpose.
_GENERIC_OUTPUT_NAMES = frozenset(
    {"out", "output", "result", "res", "ret", "val", "value", "tmp", "temp", "data", "r", "v", "x"}
)


def _suggest_name(outputs: set[str], parent_name: str, block_stmts: Sequence[ast.stmt] = ()) -> str:
    """Name the helper for what it OBSERVABLY DOES, selected by behavioral signature.

    Returns a value -> name it for what it RETURNS (issue #3), never for an arbitrary
    local assigned somewhere inside the block — that named helpers ``_compute_name``
    after a loop-local and ``_compute_b`` after a comprehension variable, neither of
    which the helper returned. A single output the block only ever assigns from
    boolean-shaped expressions gets the predicate form (``_is_valid``, and a var
    already carrying an ``is_``/``has_`` prefix keeps it rather than doubling up).

    Returns nothing and raises -> a guard clause, and ``_<parent>_helper`` said none
    of that (measured on a validation seam that earned ``_process_order_helper``
    while its three sibling extractions all got real names). ``_validate_<object>``
    with the object read off the parent by dropping its leading verb token is
    deterministic — same trace + AST, same name, every run — which is what lets
    decompose be applied repeatedly across a codebase with stable diffs.

    A void block that does not raise keeps the honest fallback: bland-but-true.
    """
    named = sorted(o for o in outputs if not o.startswith("_"))
    if named:
        if len(named) == 1 and _assigns_only_boolean(named[0], block_stmts):
            var = named[0]
            return f"_{var}" if var.startswith(("is_", "has_")) else f"_is_{var}"
        if len(named) == 1 and named[0] not in _GENERIC_OUTPUT_NAMES:
            return f"_compute_{named[0]}"
        # 2+ outputs, or a single throwaway name: do NOT concatenate return names into
        # `_compute_a_b_c` — a mechanical string that helps no reader (issue #26). A deterministic
        # engine cannot infer the block's PURPOSE (that is the model layer's job), so use the honest
        # bland form that says only what is true — an extraction from this parent — for the human to
        # rename, rather than dress the return tuple up as one.
        return f"_{parent_name.lstrip('_')}_helper"
    if any(isinstance(n, ast.Raise) for s in block_stmts for n in ast.walk(s)):
        tokens = parent_name.strip("_").split("_")
        obj = "_".join(tokens[1:]) if len(tokens) > 1 else ""
        return f"_validate_{obj}_inputs" if obj else "_validate_inputs"
    return f"_{parent_name}_helper"


def _confidence(block: list[_StmtInfo], inputs: set[str], outputs: set[str], block_cc: int) -> float:
    conf = 0.50
    if len(inputs) <= 2:
        conf += 0.10
    if len(outputs) == 0:
        conf += 0.10  # void helper — cleanest
    if len(block) >= 5:
        conf += 0.05
    if block_cc >= 8:
        conf += 0.10
    return min(conf, 0.85)


def _has_cell_crossing_closure(stmts: list[ast.stmt]) -> bool:
    """True when any nested function among ``stmts`` contains a ``nonlocal`` (issue #11).

    Relocating such a def into a helper changes WHICH lexical cell the closure reads
    and writes: inside the helper it closes over the helper frame's cell, the caller
    receives only a copied-out value, and later invocations mutate state nobody sees —
    or the relocation fails outright (``SyntaxError: no binding for nonlocal``). A
    parameter cannot fix it: a parameter supplies a value and creates a NEW cell.
    Certified abstention is the only sound V1 answer; closures that merely READ free
    variables stay eligible (their value dependency is exactly what the free-variable
    live-ins carry).
    """

    def nested_defs(node: ast.AST):
        for child in ast.walk(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                yield child

    return any(
        isinstance(inner, ast.Nonlocal)
        for stmt in stmts
        for fn in nested_defs(stmt)
        for inner in ast.walk(fn)
    )


def _is_empty_initializer(stmt: ast.stmt) -> bool:
    """``x = []`` / ``{}`` / ``()`` / ``set()`` / ``""`` / ``0`` — an initializer for
    the code that FOLLOWS it, never the tail of a real seam (issue #2). A block that
    ends on one hands back a freshly-constructed empty value it never filled."""
    if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
        return False
    if not isinstance(stmt.targets[0], ast.Name):
        return False
    value = stmt.value
    if isinstance(value, ast.Dict):
        return not value.keys
    if isinstance(value, (ast.List, ast.Set, ast.Tuple)):
        return not value.elts
    if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
        empty_builders = {"set", "frozenset", "list", "dict", "tuple"}
        return value.func.id in empty_builders and not value.args and not value.keywords
    if isinstance(value, ast.Constant):
        v = value.value
        if isinstance(v, bool):
            return False
        return v in ("", b"") or (isinstance(v, (int, float)) and v == 0)
    return False


def _evaluate_block(
    infos: list[_StmtInfo],
    start: int,
    end: int,
    param_names: set[str],
    param_order: Sequence[str],
    parent_name: str,
    max_params: int,
    max_outputs: int,
) -> ExtractionCandidate | None:
    # Issue #2: a trailing empty-literal initializer (``out = []``) belongs to the code
    # that CONSUMES it. A boundary landing past it makes the helper return an empty
    # container it just built. Retract the end — below the enumeration's min width if
    # need be, since the retracted seam still has to earn its place through the CC and
    # interface gates like any other — and let overlap removal drop any duplicate range.
    while end - start > 1 and _is_empty_initializer(infos[end - 1].stmt):
        end -= 1
    if end - start < 2:
        return None
    # Issue #11: a nested def carrying `nonlocal` pins its cell to THIS frame; a block
    # relocating it cannot preserve cell identity, so the candidate is structurally
    # false before any proof is attempted.
    if _has_cell_crossing_closure([s.stmt for s in infos[start:end]]):
        return None
    result = _compute_block_variables(infos, start, end, param_names)
    if result is None:
        return None
    inputs, outputs = result
    if len(inputs) > max_params or len(outputs) > max_outputs:
        return None
    block = infos[start:end]
    block_cc = _compute_block_cc([s.stmt for s in block])
    if block_cc < _MIN_BLOCK_CC:
        return None
    line_start = block[0].stmt.lineno
    line_end = block[-1].stmt.end_lineno or block[-1].stmt.lineno
    name = _suggest_name(outputs, parent_name, [s.stmt for s in block])
    ordered_inputs = _human_order(inputs, param_order, infos)
    ordered_outputs = _human_order(outputs, param_order, infos)
    return ExtractionCandidate(
        start_line=line_start,
        end_line=line_end,
        proposed_name=name,
        inputs=ordered_inputs,
        outputs=ordered_outputs,
        cc_reduction=block_cc,
        confidence=_confidence(block, inputs, outputs, block_cc),
        reason=f"lines {line_start}-{line_end} → {name}({', '.join(ordered_inputs)}) "
        f"(complexity -{block_cc}, single-exit, {len(inputs)} in / {len(outputs)} out)",
    )


def _remove_overlapping(
    candidates: list[ExtractionCandidate], max_count: int
) -> tuple[ExtractionCandidate, ...]:
    """Greedily keep the highest-benefit non-overlapping candidates (by line span)."""
    kept: list[ExtractionCandidate] = []
    used: set[int] = set()
    for c in candidates:
        span = set(range(c.start_line, c.end_line + 1))
        if span & used:
            continue
        kept.append(c)
        used |= span
    return tuple(kept[:max_count])


def _max_candidates(cc: int) -> int:
    if cc > 50:
        return 10
    if cc > 30:
        return 6
    return _MAX_CANDIDATES


def find_extraction_candidates(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    # 2, not 3 (review finding 5): a real seam can be exactly two statements — an
    # accumulator loop and its initializer — and enumeration never saw it; only the
    # retraction path could reach width 2. The CC and interface gates still decide
    # whether a narrow block is WORTH extracting.
    min_statements: int = 2,
    max_params: int = 4,
    max_outputs: int = 2,
) -> tuple[ExtractionCandidate, ...]:
    """Every contiguous statement block that is a clean, complexity-reducing
    extraction — the deterministic responsibility seams of the function."""
    body = func_node.body
    # A leading docstring belongs to the FUNCTION, not to any extracted block: sweeping it
    # into a helper both mis-describes the helper (it would inherit the parent's whole-
    # function docstring) and strips the parent of its own docstring. Skip it so blocks start
    # at the first real statement — line numbers still come from each stmt's own lineno.
    if ast.get_docstring(func_node) is not None:
        body = body[1:]
    if len(body) <= min_statements:
        return ()
    infos = [_analyze_statement(i, stmt) for i, stmt in enumerate(body)]
    param_names = _get_param_names(func_node)
    param_order = _get_param_order(func_node)
    n = len(infos)
    found: list[ExtractionCandidate] = []
    for start in range(n):
        for end in range(start + min_statements, min(n + 1, start + _MAX_BLOCK_STMTS)):
            candidate = _evaluate_block(
                infos, start, end, param_names, param_order, func_node.name, max_params, max_outputs
            )
            if candidate is not None:
                found.append(candidate)
    found.sort(key=lambda c: c.cc_reduction, reverse=True)
    return _remove_overlapping(found, _max_candidates(compute_cognitive_complexity(func_node)))


def decompose(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    function: str = "",
    surviving_categories: tuple[str, ...] = (),
) -> DecompositionPlan:
    """Structure-gated, deterministic decomposition plan.

    A function is decomposable when the deterministic dependency clustering finds at least
    one clean extraction — a single-exit block with a small interface (few reads-from-before,
    one/two writes-read-after) and enough cognitive complexity to be worth pulling out. That
    separability is a STRUCTURAL property of the code, independent of test coverage: a block
    that cleanly detaches IS a distinct responsibility, whereas a cohesive algorithm's
    internals share too large an interface to pass the clustering. Test survivors are a
    coverage signal and do NOT gate this — the converge PROOF (the suite stays green after a
    trial extraction) is the sole safety gate for actually applying one. ``surviving_categories``
    is retained for context in the rationale only.
    """
    candidates = find_extraction_candidates(func_node)
    decomposable = len(candidates) >= 1
    cell_obstructed = not decomposable and _has_cell_crossing_closure(list(func_node.body))
    return DecompositionPlan(
        function=function,
        is_decomposable=decomposable,
        candidates=candidates,
        rationale=_rationale(decomposable, candidates, surviving_categories, cell_obstructed),
    )


def _rationale(
    decomposable: bool,
    candidates: tuple[ExtractionCandidate, ...],
    surviving: tuple[str, ...],
    cell_obstructed: bool = False,
) -> str:
    if not decomposable:
        if cell_obstructed:
            # Issue #11: name the obstruction — "no seam" without explanation reads as
            # a structural verdict when the real reason is lexical-state safety.
            return (
                "no cell-safe extraction — a nested closure declares `nonlocal`, and "
                "relocating it would change which lexical cell it reads and writes; "
                "V1 abstains rather than propose a helper that cannot preserve state"
            )
        return (
            "no clean extraction — no single-exit block with a small interface and enough "
            "cognitive complexity to be worth pulling out; structurally one piece"
        )
    cats = sorted(set(surviving))
    ctx = f"; still unspecified across {', '.join(cats)}" if cats else ""
    return (
        f"{len(candidates)} responsibility seam(s) — each a single-exit, small-interface "
        f"block worth extracting{ctx}; extract, then re-profile"
    )
