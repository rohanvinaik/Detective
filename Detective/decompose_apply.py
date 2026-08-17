"""Apply a decomposition — extract a compound block into a helper function.

:mod:`Detective.decompose` proposes which blocks are separable; this module turns
a proposal into real code and, when it can PROVE the rewrite is behavior-preserving,
applies it. Proof is by EXECUTION, not by trusting the transform: the decomposed
function is run against the original over witness inputs, and only an exact match on
every input earns an auto-apply (Detective's stochastic-proposer / deterministic-
checker model). Anything unvalidated is proposed — shown, never written.

The extraction itself is scope-based: a block's PARAMS are the names it reads that
were defined before it, its RETURNS are the names it writes that are read after it,
and a block that escapes its own control flow (return / yield / a free break) is not
extractable at all.
"""

from __future__ import annotations

import ast
import hashlib
import json
import textwrap
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from ._contain import budget_is_exhausted, contained_stdout, remaining_budget_ms
from .decompose import (
    InterfaceContract,
    contract_apply_disposition,
    interface_obligations,
    trial_verdict,
)
from .verdict_cache import wesker_policy_id

if TYPE_CHECKING:
    from .converge import ConvergeResult


def _kill_matrix(file: str, function: str, project_root: str) -> dict[str, list[str]]:
    """The target's ``mutant -> tests that killed it`` map. Served from the content-hashed
    verdict cache whenever the function and its tests are unchanged, so this costs ~nothing
    right after converge profiled the same target."""
    from .engine import profile

    try:
        return profile(file, function, project_root).kill_matrix
    except Exception:  # noqa: BLE001 — no profile -> no proof suite -> propose, never apply
        return {}


def _wanted_test_names(kill_matrix: dict[str, list[str]]) -> set[str]:
    """The test names that killed a mutant OF THIS TARGET, as the names their ``def``s
    carry: a parametrize id is stripped, since ``t[case-a]`` is defined by ``def t``.

    ``kill_matrix`` maps mutant -> the tests that killed it, so every name here provably
    exercises the target. That is what "covers the target specifically" means, and it is
    why the whole discovered suite must NOT be used instead — ``discover_test_callables``
    returns every test in the project, which would let an unrelated passing test stand in
    for the proof.
    """
    from .suite_edit import nodeid_function_name

    # Resolve, don't just strip the row suffix (#13/#54). These names are compared against the
    # `def`s a test module DEFINES, which are bare; the matrix keys tests by pytest nodeid
    # (Wesker #16) or Wesker's `legacy:` fallback, so `path::t[case] -> path::t` still matched
    # nothing and this returned no covering files at all. It went unnoticed because the proof
    # basis normally also carries `written_path`; it surfaces the moment the generated file is
    # legitimately absent — which is exactly when the pre-existing suite IS the whole proof.
    return {nodeid_function_name(t) for tests in kill_matrix.values() for t in tests}


def _test_names_in_source(source: str) -> set[str]:
    """The function names a test module's source DEFINES. Source that does not parse
    defines nothing — a malformed file specifies no behavior, so it is not proof."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    return {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)}


def _covering_test_files(
    root: str, kill_matrix: dict[str, list[str]], line_owner_ids: tuple[str, ...] = ()
) -> tuple[str, ...]:
    """The PRE-EXISTING test files that provably specify this target — the proof suite
    when converge wrote nothing because the hand-written suite was already complete.

    The walk is deliberately thin; the decisions live in the two pure helpers above.
    Names resolve to files by reading the source, never ``inspect.getfile``: Wesker binds
    parametrized cases through a wrapper, so a callable's file is its wrapper's file.

    ``line_owner_ids`` are the admissible LINE-coverage owners (#59) — tests that cover a target
    line but kill no mutant, so ``_wanted_test_names`` (kill matrix only) omits them and their file
    never enters the proof basis. The caller supplies the ALREADY-GATED owners (``admissible`` basis
    only); resolving them to ``def`` names the same way keeps a line-only owner's file in the suite.
    """
    import os

    from .suite_edit import nodeid_function_name

    wanted = _wanted_test_names(kill_matrix) | {nodeid_function_name(t) for t in line_owner_ids}
    if not wanted:
        return ()

    files: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith((".", "__")) and d != "node_modules"]
        for name in filenames:
            if not (name.startswith("test_") and name.endswith(".py")):
                continue
            full = os.path.join(dirpath, name)
            try:
                with open(full, encoding="utf-8") as fh:
                    source = fh.read()
            except OSError:
                continue
            if _test_names_in_source(source) & wanted:
                files.add(os.path.relpath(full, root))
    return tuple(sorted(files))


def _names(node: ast.AST, ctx: type | tuple[type, ...]) -> set[str]:
    """The ``Name`` ids used with the given context (Load / Store) anywhere in
    ``node``, not descending into nested function scopes (their locals are theirs)."""
    found: set[str] = set()
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.Name) and isinstance(child.ctx, ctx):
            found.add(child.id)
        if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            found |= _names(child, ctx)
    return found


def _aug_targets(node: ast.AST) -> set[str]:
    """Names that are augmented-assignment targets (``x += 1``): read AND written,
    so they must be passed IN as well as returned OUT."""
    return {
        a.target.id for a in ast.walk(node) if isinstance(a, ast.AugAssign) and isinstance(a.target, ast.Name)
    }


def _target_names(target: ast.AST) -> set[str]:
    """The Name ids bound by an assignment/loop target (handles tuple unpacking)."""
    return {n.id for n in ast.walk(target) if isinstance(n, ast.Name)}


def structural_bindings(node: ast.AST) -> set[str]:
    """Names a block binds structurally BEFORE any use — loop variables, ``with … as``
    targets, ``except … as`` names, comprehension targets. Such a name is the block's
    own local (its read is of the value the block itself just bound), so it is NOT an
    external read and must never become a parameter — the loop-variable leak that a
    plain reads∩defined-before test gets wrong when an earlier loop left the same
    name bound in the enclosing scope."""
    bound: set[str] = set()
    for n in ast.walk(node):
        if isinstance(n, (ast.For, ast.AsyncFor)):
            bound |= _target_names(n.target)
        elif isinstance(n, ast.comprehension):
            bound |= _target_names(n.target)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            bound.add(n.name)
        elif isinstance(n, ast.withitem) and n.optional_vars is not None:
            bound |= _target_names(n.optional_vars)
    return bound


def _has_free_break(node: ast.AST, in_loop: bool) -> bool:
    """True if ``node`` contains a ``break``/``continue`` NOT enclosed by a loop
    within ``node`` — such a jump targets an OUTER loop and cannot move into a
    helper. Nested function scopes are ignored (they cannot break the outer loop)."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.Break, ast.Continue)) and not in_loop:
            return True
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        child_in_loop = in_loop or isinstance(child, (ast.For, ast.While, ast.AsyncFor))
        if _has_free_break(child, child_in_loop):
            return True
    return False


def control_escapes(stmt: ast.stmt) -> bool:
    """True if extracting ``stmt`` into a helper would change control flow: it
    contains a ``return``/``yield``, a ``nonlocal``/``global`` declaration, or a
    ``break``/``continue`` that targets a loop outside the block."""
    for node in ast.walk(stmt):
        if isinstance(node, (ast.Return, ast.Yield, ast.YieldFrom, ast.Nonlocal, ast.Global)):
            return True
    started_in_loop = isinstance(stmt, (ast.For, ast.While, ast.AsyncFor))
    return _has_free_break(stmt, in_loop=started_in_loop)


@dataclass(frozen=True)
class BlockInterface:
    """The data-flow interface of an extractable block: what it needs in and hands
    out. ``params`` come in as arguments, ``returns`` go out as the helper's return."""

    params: tuple[str, ...]
    returns: tuple[str, ...]


def block_interface(func_node: ast.FunctionDef | ast.AsyncFunctionDef, index: int) -> BlockInterface:
    """Params and returns for extracting ``func_node.body[index]``.

    A param is a name the block READS that was defined before it (a function
    parameter, or something assigned in an earlier statement) — a loop variable or
    other block-local read is NOT a param. A return is a name the block WRITES that
    is READ by a later statement — anything written only for the block's own use
    stays inside the helper. Both are sorted for a deterministic signature.
    """
    block = func_node.body[index]
    arg_names = {a.arg for a in func_node.args.args}
    arg_names |= {a.arg for a in getattr(func_node.args, "posonlyargs", [])}
    arg_names |= {a.arg for a in func_node.args.kwonlyargs}
    if func_node.args.vararg:
        arg_names.add(func_node.args.vararg.arg)
    if func_node.args.kwarg:
        arg_names.add(func_node.args.kwarg.arg)

    defined_before = set(arg_names)
    for earlier in func_node.body[:index]:
        defined_before |= _names(earlier, ast.Store)

    reads = _names(block, ast.Load) | _aug_targets(block)
    # Exclude names the block binds for itself (loop vars etc.): their read is of the
    # block's own binding, not an external value, even if an earlier statement left
    # the same name in scope.
    params = (reads & defined_before) - structural_bindings(block)

    writes = _names(block, ast.Store) | _aug_targets(block)
    read_after: set[str] = set()
    for later in func_node.body[index + 1 :]:
        read_after |= _names(later, ast.Load)
    returns = writes & read_after

    return BlockInterface(tuple(sorted(params)), tuple(sorted(returns)))


def _resolve(tree: ast.Module, function: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    """The FunctionDef named ``function`` (last path segment for a method)."""
    target = function.split(".")[-1]
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == target:
            return node
    return None


# ── The versioned transformation class (issue #14) ─────────────────────
#
# A `PROVEN` decomposition is a claim with TWO parameters: the mutation policy
# the proof suite is complete under (Wesker's, carried as `policy_id`), and
# the rewrite model the trial exercised — THIS. The id changes when the
# transformer's semantics change (a new interface algorithm, a loosened
# refusal), so a receipt minted under one rewrite model can never silently
# stand for another. Bump discipline is enforced the same way as Wesker's
# POLICY_VERSION: a golden test pins the id and its failure message names the
# two legal moves.

TRANSFORM_CLASS_VERSION = 1

_TRANSFORM_SURFACE: dict[str, object] = {
    "transform_class_version": TRANSFORM_CLASS_VERSION,
    "shape": "contiguous single-exit statement block extracted to a module-level helper",
    "interface": (
        "params = names read before written inside the block, in first-use order; "
        "returns = block-assigned names live after the block, in assignment order"
    ),
    "refusals": [
        "blocks with break/continue/return escaping the block",
        "nonlocal/closure-cell relocation (cell identity is not preserved)",
        "a leading docstring never moves into the helper",
        "candidates below cognitive-complexity 3 or above 4-in/2-out interface",
    ],
    "placement": "helper inserted before the parent; call site replaces the block",
    "supported": "sync functions; generators/async are structural refusals",
}


def transform_class_id() -> str:
    """The versioned identifier of the supported rewrite model — the Τ in the
    proof claim "τ ∈ Τ preserved every obligation under policy μ"."""
    canonical = json.dumps(_TRANSFORM_SURFACE, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
    return f"{TRANSFORM_CLASS_VERSION}.{digest}"


@dataclass(frozen=True)
class Extraction:
    """A generated (not-yet-validated) extraction: the helper's interface and the
    full rewritten source with the helper spliced in and the block replaced by a
    call."""

    helper_name: str
    params: tuple[str, ...]
    returns: tuple[str, ...]
    new_source: str
    # The explicit interface obligations this extraction must preserve (#16). Default-empty so
    # the older ``extract_block`` path (and any hand-built Extraction) stays constructible; the
    # live ``extract_candidate`` path always fills it from the block's def-use + effect analysis.
    contract: InterfaceContract = InterfaceContract(())


def extract_block(source: str, function: str, index: int) -> Extraction | None:
    """Rewrite ``source`` extracting ``function``'s ``index``-th body statement into
    a helper, or None if that statement is not safely extractable (it escapes its
    control flow) or cannot be located.

    Surgical, not a full reparse: only the block's lines become a call and the
    helper is spliced in above the function, so every comment and the formatting of
    the rest of the file survive. Behavior preservation is NOT asserted here — the
    caller validates by execution before applying."""
    tree = ast.parse(source)
    func = _resolve(tree, function)
    if func is None or index < 0 or index >= len(func.body):
        return None
    block = func.body[index]
    if control_escapes(block):
        return None
    iface = block_interface(func, index)

    lines = source.splitlines(keepends=True)
    end = block.end_lineno or block.lineno
    block_text = "".join(lines[block.lineno - 1 : end])
    first = lines[block.lineno - 1]
    base_indent = first[: len(first) - len(first.lstrip())]

    helper_name = f"_{function.split('.')[-1]}_{type(block).__name__.lower()}_{block.lineno}"
    body = textwrap.indent(textwrap.dedent(block_text), "    ")
    if not body.endswith("\n"):
        body += "\n"
    helper = f"def {helper_name}({', '.join(iface.params)}):\n{body}"
    if iface.returns:
        helper += f"    return {', '.join(iface.returns)}\n"
    helper += "\n\n"

    call = base_indent + (f"{', '.join(iface.returns)} = " if iface.returns else "")
    call += f"{helper_name}({', '.join(iface.params)})\n"

    func_start = min([func.lineno, *(d.lineno for d in func.decorator_list)]) - 1
    rewritten = lines[: block.lineno - 1] + [call] + lines[end:]
    new_source = "".join(rewritten[:func_start]) + helper + "".join(rewritten[func_start:])
    return Extraction(helper_name, iface.params, iface.returns, new_source)


def _annotated_params(inputs, annotations) -> str:
    """Pure: the extracted helper's parameter list. Each input name carries the parent's
    declared type where it is one of the parent's params (``annotations`` maps name→type
    source), and is left bare where it is a local computed before the block — which has no
    declared type. Threading these keeps an applied split from redding strict ANN lint (#28)."""
    return ", ".join(f"{n}: {annotations[n]}" if n in annotations else n for n in inputs)


def _leaves_pure_wrapper(func, start_line, end_line) -> bool:
    """Does extracting the statements in ``[start_line, end_line]`` leave the parent a PURE
    delegating wrapper — nothing but a single ``return`` besides the call the block becomes?
    Excludes a leading docstring. True means the split turns the parent into
    ``<outputs> = helper(<inputs>); return <outputs>`` — a call hop and a test-indirection layer
    for zero readability gain, not a real seam. False when meaningful residual logic stays behind
    (another statement besides the return), which is a legitimate split (its only fault may be the
    helper's NAME, a separate concern)."""
    body = func.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    outside = [s for s in body if not (start_line <= s.lineno <= end_line)]
    return len(outside) == 1 and isinstance(outside[0], ast.Return)


def _worth_extracting(block_lines, parent_lines, is_wrapper, *, max_body_fraction=0.95) -> bool:
    """Pure: is a PROVEN-preserving extraction worth APPLYING? Detective only trials safe splits,
    but safe is not the same as worth it. Reject a pure delegating wrapper (``is_wrapper``), and —
    as a loose structural backstop, not a fitted threshold — a near-total extraction whose block is
    over ``max_body_fraction`` of the parent body (a wrapper in all but a trivial residual). Keep
    everything else: a large split that leaves real residual logic is a legitimate seam."""
    if is_wrapper or parent_lines <= 0:
        return False
    return (block_lines / parent_lines) <= max_body_fraction


def _candidate_worth(node, candidate) -> bool:
    """The value gate one extraction candidate must pass to be APPLIED — the SINGLE predicate shared
    by diagnose's seam count and apply's trial loop (issue #33). Before this was single-sourced,
    diagnose counted a delegating-wrapper candidate as a 'clean seam' and routed to
    `decompose --apply`, which then rejected it as low-value and printed 'no seam to split'.
    """
    parent_lines = (node.end_lineno or node.lineno) - node.body[0].lineno + 1
    is_wrapper = _leaves_pure_wrapper(node, candidate.start_line, candidate.end_line)
    block_lines = candidate.end_line - candidate.start_line + 1
    return _worth_extracting(block_lines, parent_lines, is_wrapper)


def actionable_seam_count(node) -> int:
    """Extraction candidates that would actually be APPLIED — the count passing the same value gate
    apply trials, not the raw structural count (issue #33). This is the number diagnose must report
    as 'clean seams' and route on, so its next action terminates usefully. Best-effort: 0 on any
    failure, so a structural read never breaks a diagnose."""
    try:
        from .decompose import find_extraction_candidates

        return sum(1 for c in find_extraction_candidates(node) if _candidate_worth(node, c))
    except Exception:  # noqa: BLE001 — a structural read must never fail a diagnose
        return 0


def _block_span_with_comments(lines, start, end):
    """Grow a statement span ``[start, end]`` (1-based, inclusive) to absorb TRAILING comment
    lines that sit DEEPER than the block's base indent — i.e. inside the last compound statement
    being moved (a loop / if body) but after the AST's final statement, which does not count them
    in its ``end_lineno``. Without this they are left in the parent at the moved code's original
    (now-broken) indentation, documenting code that is no longer there (#29). Stops at the first
    line that is blank, not a comment, or at/shallower than the base indent: a comment at the
    block's OWN indent is ambiguous (it may lead the NEXT statement), so it is left where it is —
    validly indented — rather than mis-attributed to the helper."""
    base = lines[start - 1]
    base_indent = len(base) - len(base.lstrip())
    e = end
    while e < len(lines):
        nxt = lines[e]  # 0-based index e is line number e+1
        stripped = nxt.strip()
        indent = len(nxt) - len(nxt.lstrip())
        if stripped.startswith("#") and indent > base_indent:
            e += 1
        else:
            break
    return start, e


def helper_generic_clause(type_params, referenced) -> str:
    """Pure (#28 follow-on — pinned): the PEP 695 generic clause the extracted helper
    must declare so a threaded annotation that names a parent type-param stays defined.

    ``#28`` threads the parent's parameter annotations onto the helper (``x: list[E]``)
    but the helper is spliced at MODULE scope, where a type-param ``E`` scoped to the
    parent ``def f[E, R](...)`` is an undefined name — ruff F821 / a ty unresolved-
    reference on every applied split over a generic function. The helper must therefore
    redeclare the subset of the parent's type-params its threaded annotations actually
    use.

    ``type_params`` is the parent's params in declaration order, each a
    ``[name, source, deps]`` triple: ``source`` is the text to re-emit verbatim (so a
    bound/default/``*``/``**`` rides along) and ``deps`` the type-param names that source
    itself references. ``referenced`` is the type-param names the helper's threaded
    annotations mention.

    Returns the bracketed subset in PARENT ORDER, transitively closed over ``deps`` (a
    bound ``R: list[E]`` drags in ``E``), and the empty string when nothing applies — so
    the caller concatenates it unconditionally. Parent order preserves PEP 695's
    'defaults last' invariant the valid parent already satisfies; emitting only the used
    subset keeps the helper from declaring a type-param it never mentions.
    """
    by_name = {tp[0]: tp for tp in type_params}
    need = {name for name in referenced if name in by_name}
    frontier = list(need)
    while frontier:
        for dep in by_name[frontier.pop()][2]:
            if dep in by_name and dep not in need:
                need.add(dep)
                frontier.append(dep)
    used = [tp[1] for tp in type_params if tp[0] in need]
    return f"[{', '.join(used)}]" if used else ""


def extract_candidate(source: str, function: str, candidate) -> Extraction | None:
    """Extract the finder's contiguous block (``candidate.start_line..end_line``)
    into ``candidate.proposed_name``, using the def-use interface the deterministic
    finder already computed (``inputs``/``outputs``). Surgical: only those lines
    become a call and the helper is spliced above the function, so the rest of the
    file is untouched."""
    tree = ast.parse(source)
    func = _resolve(tree, function)
    if func is None:
        return None
    lines = source.splitlines(keepends=True)
    start, end = candidate.start_line, candidate.end_line
    if start < 1 or end > len(lines) or start > end:
        return None
    # Carry trailing comments that live inside the moved construct along with it, so a design
    # comment does not strand in the parent at broken indentation, pointing at code that left (#29).
    start, end = _block_span_with_comments(lines, start, end)
    # Review finding 5: the proposed name must not collide with a symbol the module
    # already defines — an existing `_compute_out` and a new one silently merge into
    # whichever definition comes last. Reserve by suffixing until free.
    taken = {
        n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }
    taken |= {
        t.id for n in tree.body if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)
    }
    helper_name = candidate.proposed_name
    suffix = 2
    while helper_name in taken:
        helper_name = f"{candidate.proposed_name}_{suffix}"
        suffix += 1
    block_text = "".join(lines[start - 1 : end])
    first = lines[start - 1]
    base_indent = first[: len(first) - len(first.lstrip())]
    body = textwrap.indent(textwrap.dedent(block_text), "    ")
    if not body.endswith("\n"):
        body += "\n"
    # Thread the enclosing def's parameter annotations onto the extracted helper (issue #28):
    # an input that is one of the parent's params carries its declared type; an input that is a
    # local computed before the block has none. Dropping them all reds strict annotation lint
    # (ruff ANN001 / a mypy call-site) and broke a target repo's CI on every applied split — a
    # split that is behaviour-preserving must also stay mergeable.
    annotation_nodes = {
        a.arg: a.annotation
        for a in [*func.args.posonlyargs, *func.args.args, *func.args.kwonlyargs]
        if a.annotation is not None
    }
    annotations = {name: ast.unparse(node) for name, node in annotation_nodes.items()}
    params = _annotated_params(candidate.inputs, annotations)
    # PEP 695: a threaded annotation (#28) that names one of the parent's type-params
    # (``def f[E](x: list[E])``) would land ``E`` on the MODULE-level helper, where it is an
    # undefined name (ruff F821 / ty unresolved-reference) — so the helper must redeclare the
    # subset of the parent's type-params its threaded annotations actually use. ``referenced``
    # is drawn only from the annotations that are emitted (the parent-param inputs); each
    # type-param carries its own source and the names its bound/default reference, for
    # helper_generic_clause to close over.
    referenced = {
        node.id
        for name in candidate.inputs
        if name in annotation_nodes
        for node in ast.walk(annotation_nodes[name])
        if isinstance(node, ast.Name)
    }
    type_params = [
        [
            tp.name,
            ast.unparse(tp),
            [
                m.id
                for child in (getattr(tp, "bound", None), getattr(tp, "default_value", None))
                if child is not None
                for m in ast.walk(child)
                if isinstance(m, ast.Name)
            ],
        ]
        for tp in getattr(func, "type_params", [])
    ]
    generic = helper_generic_clause(type_params, referenced)
    returns = ", ".join(candidate.outputs)
    helper = f"def {helper_name}{generic}({params}):\n{body}"
    if candidate.outputs:
        helper += f"    return {returns}\n"
    helper += "\n\n"
    call = base_indent + (f"{returns} = " if candidate.outputs else "")
    # The DEFINITION carries annotated params (#28); the CALL passes bare argument names.
    call += f"{helper_name}({', '.join(candidate.inputs)})\n"
    func_start = min([func.lineno, *(d.lineno for d in func.decorator_list)]) - 1
    rewritten = lines[: start - 1] + [call] + lines[end:]
    new_source = "".join(rewritten[:func_start]) + helper + "".join(rewritten[func_start:])
    # The interface obligations this extraction must preserve (#16): value flow (structural),
    # plus any in-place mutation of an input or ordered side effect the block carries (witnessed).
    # The top-level statements in the candidate's own span ARE the moved block. Its serialization
    # rides on the returned Extraction, so a PROVEN claim can be audited obligation by obligation.
    block_stmts = [s for s in func.body if candidate.start_line <= s.lineno <= candidate.end_line]
    contract = interface_obligations(block_stmts, candidate.inputs, candidate.outputs)
    return Extraction(helper_name, candidate.inputs, candidate.outputs, new_source, contract)


@dataclass(frozen=True)
class Decomposition:
    """One candidate's outcome: the generated extraction and whether execution
    proved it behavior-preserving (hence auto-appliable)."""

    extraction: Extraction
    validated: bool
    # The `trial_verdict` code this candidate earned (proven / witnessed / rejected / unproven),
    # carried so the CLI reads the ACTUAL trial outcome instead of re-deriving it from
    # `functionally_complete` — the two disagree exactly when a mutation-complete suite still
    # retains candidate-equivalent survivors, where the trial was `unproven` (the suite was
    # withheld), NOT `rejected`. Default "" for directly-built results (tests, older callers).
    trial: str = ""  # True -> safe to auto-apply; False -> propose only


@dataclass(frozen=True)
class DecompositionApply:
    """Result of decomposing a function: what was applied (validated + written) and
    what is only proposed (generated but unvalidated, or written=False)."""

    function: str
    applied: tuple[Extraction, ...]
    proposed: tuple[Decomposition, ...]
    unsafe_blocks: tuple[str, ...]
    # The converge run used as the proof attempt. When it is not ``functionally_complete``
    # (a KILLABLE mutant synthesis could not reach), the extraction cannot be proven — and
    # this carries the exact residual (signature, param shape, killable survivors) so the CLI
    # can hand the user the ``--input`` to supply, instead of a dead-end "review it yourself".
    proof: ConvergeResult | None = None
    # The claim's two parameters (issue #14): a PROVEN result means "the trial
    # rewrite, drawn from transformation class `transform_class_id`, preserved
    # every obligation in a suite complete under Wesker policy `policy_id`" —
    # reconstructable, and invalidated by a change to either. None policy_id =
    # the installed engine predates policy versioning.
    policy_id: str | None = None
    transform_class_id: str | None = None
    # The aggregate command deadline (issue #31) was exhausted during the proof converge or
    # the trial loop. A cut proof is already blocked from applying — a cut converge is not
    # ``functionally_complete``, so ``proof_suite`` stays None and nothing is written — but
    # this stamps the cause explicitly so the CLI says "CUT during <phase>", exits non-zero,
    # and never reads the run as "nothing to decompose".
    budget_exhausted: bool = False
    cut_phase: str = ""
    # Bytes the target emitted to stdout during the whole decompose, contained off the
    # report/JSON channel — nonzero names an integration target (the wrap_trace regression).
    stdout_bytes: int = 0


def preservation_admissible(functionally_complete: bool, stale: bool, candidate_equivalents: int) -> bool:
    """Whether a converge proof may authorize ``decompose --apply`` (issue #41).

    A green before/after trial proves the rewrite preserved the behaviours the proof suite PINNED —
    and says nothing about the ones it did not. A candidate-equivalent survivor is exactly a
    behaviour finite-input search could not pin (no distinguishing witness FOUND — not equivalence
    PROVEN), so applying across it is unproven preservation: the 3-of-31 case where a suite pinning a
    tenth of the operator universe auto-rewrote, green before and after because the trial was silent
    on the other 28 dimensions. Admissible only when the proof is mutation-complete, not stale, AND
    carries ZERO candidate-equivalents — zero survivors, or a residual every one of which a human
    flagged equivalent (the recorded oracle, which lands in ``manual_equivalent``, never in the
    candidate ``equivalent`` population). Any candidate-equivalent makes the extraction proposal-only.
    """
    return functionally_complete and not stale and candidate_equivalents == 0


def apply_decomposition(
    file: str,
    function: str,
    project_root: str = ".",
    *,
    write: bool = False,
    max_extractions: int = 8,
    supplied_inputs: list[tuple] | None = None,
    deadline_s: float | None = 300.0,
    notify: Callable[[str], None] | None = None,
) -> DecompositionApply:
    """Decompose, with the consumer target's stdout contained off the report channel.

    A thin shell over :func:`_apply_decomposition_impl`. Decompose's proof step converges the
    target and its trial loop re-runs the suite, so the same integration-target flood converge
    guards against applies here (the original ``wrap_trace`` regression). One command-level
    ``sys.stdout`` redirect for the whole run keeps it off the human/JSON channel; the byte
    count is stamped on the result. ``deadline_s`` is the one aggregate wall, threaded into the
    proof converge and drawn down across the trial loop (issue #31).
    """
    with contained_stdout() as _sink:
        result = _apply_decomposition_impl(
            file,
            function,
            project_root,
            write=write,
            max_extractions=max_extractions,
            supplied_inputs=supplied_inputs,
            deadline_s=deadline_s,
            notify=notify,
        )
    return replace(result, stdout_bytes=_sink.bytes_written) if _sink.bytes_written else result


def _apply_decomposition_impl(
    file: str,
    function: str,
    project_root: str = ".",
    *,
    write: bool = False,
    max_extractions: int = 8,
    supplied_inputs: list[tuple] | None = None,
    deadline_s: float | None = 300.0,
    notify: Callable[[str], None] | None = None,
) -> DecompositionApply:
    """The full decomposition loop — a decomposition is applied only when PROVED
    behavior-preserving by a mutant-complete test suite.

        1. converge → generate a functional, mutant-complete test suite (the
           behavioral spec: it kills every killable mutant, so passing it means every
           behavioral degree of freedom is preserved).
        2. decompose (deterministic dependency clustering, gated on entanglement) →
           propose contiguous-block extractions.
        3. PROVE: trial-apply each extraction and re-run the suite. Green → proven
           behavior-preserving; red → reject and revert.

    A validated extraction is kept only when ``write`` is True; otherwise the trial
    is reverted and the extraction reported as (validated) proposed."""
    import os

    from .certify import verify_under_pytest
    from .converge import converge
    from .decompose import decompose

    root = os.path.abspath(project_root)
    full = file if os.path.isabs(file) else os.path.join(root, file)
    # decompose's cost IS the converge below (mutating + running the suite), so without this
    # the slowest command is also the only silent one — it looks hung while doing the most.
    say = notify or (lambda _m: None)
    # The ONE aggregate wall (issue #31), shared across the proof converge AND the trial loop.
    # ``_budget_s`` hands converge whatever seconds remain as ITS deadline (converge draws down
    # from there), and the trial loop below checks the same wall before each extraction.
    _deadline_ms = deadline_s * 1000.0 if deadline_s and deadline_s > 0 else None
    _t0 = time.monotonic()

    def _budget_ms() -> float | None:
        return remaining_budget_ms(_deadline_ms, (time.monotonic() - _t0) * 1000.0)

    def _budget_s() -> float | None:
        _ms = _budget_ms()
        return None if _ms is None else _ms / 1000.0

    budget_cut = False
    cut_phase = ""

    # STEP 1 — the mutant-complete suite is both the spec and the proof.
    surviving_categories: tuple[str, ...] = ()
    try:
        # ``supplied_inputs`` are the Zone-2 residual filled through the CLI (`decompose
        # --input`): the exact inputs deterministic synthesis could not exercise. They flow
        # into the proof suite so a function whose line-/mutant-completeness needs a human
        # sample can still reach the `line_complete` gate below — otherwise it could never
        # be proven decomposable from the CLI.
        say("proving: converging the target to a mutation-complete suite (the proof)…")
        conv = converge(
            file,
            function,
            project_root,
            # Canonical home is tests/detective/ (issue #21); this call still passed the old
            # tests/ root, so decompose's proof suite and any new-helper test landed at root while
            # every other converge wrote to tests/detective/ (issue #27). Aligning it also lets
            # `_write` retire the legacy root-level sibling on the way past.
            write_dir="tests/detective",
            supplied_inputs=supplied_inputs,
            # The proof converge draws from the shared wall — its own containment nests
            # harmlessly inside ours (idempotent stdout redirect).
            deadline_s=_budget_s(),
            notify=notify,
        )
        report = conv.survivor_report
        if report is not None:
            surviving_categories = tuple(sorted({v.category for v in report.verdicts}))
        if conv.budget_exhausted and not budget_cut:
            budget_cut, cut_phase = True, conv.cut_phase or "proof converge"
    except Exception:  # noqa: BLE001 — no suite -> no proof possible
        conv = None
    if not surviving_categories:
        from .engine import profile

        try:
            _prof = profile(file, function, project_root, budget_ms=_budget_ms())
            surviving_categories = tuple(
                sorted({r.get("category", "") for r in _prof.value_survivor_records})
            )
            if _prof.budget_exhausted and not budget_cut:
                budget_cut, cut_phase = True, "mutant profiling"
        except Exception:  # noqa: BLE001
            surviving_categories = ()

    # The proof suite is the TARGET's own MUTATION-complete suite. The behavior-preservation
    # proof is mutation-completeness (every KILLABLE mutant killed → every pin-able behavioral
    # degree of freedom is pinned, so a decomposition that changes any of them fails a test).
    # LINE-completeness is orthogonal and NOT required: a line whose mutants are all killed is
    # fully specified whether or not a test "covers" it in the coverage sense, and a covered
    # line whose mutants survive proves nothing. Gating on ``functionally_complete`` (not
    # ``line_complete``) is what lets a branchy function be proven+auto-applied without the
    # user hand-feeding boundary ``--input``s just to satisfy a coverage metric that does not
    # bear on preservation. (A genuine residual — a KILLABLE mutant synthesis could not reach —
    # correctly leaves ``functionally_complete`` False, and THAT is the real case to surface an
    # ``--input`` for.) The suite must still exist and cover the target specifically, so an
    # unrelated passing test can never stand in for the proof.
    # The suite that proves preservation is whichever one is mutation-complete — Detective
    # does not have to be its author. When converge wrote nothing BECAUSE the pre-existing
    # hand-written suite already killed every killable mutant (``written_path`` None with
    # ``functionally_complete`` True — the BEST case, a function already fully specified),
    # the proof is those hand-written files. Gating on ``written_path`` alone rejected
    # exactly that case, and misreported the cause as "not mutation-complete".
    proof_suite: str | tuple[str, ...] | None = None
    # Candidate-equivalents are finite-search "no witness found", NOT proven equivalence — they
    # are the behaviours the proof suite did not pin, so they cannot authorize an auto-rewrite
    # (issue #41). Counted here so both the gate and the refusal message name them.
    _cand_equiv = len(conv.survivor_report.equivalent) if (conv and conv.survivor_report) else 0
    # A stale converge (target edited under the run, issue #17) is not a proof of anything, and a
    # proof carrying candidate-equivalents proves preservation only of the pinned behaviours (#41).
    if conv is not None and preservation_admissible(
        conv.functionally_complete, conv.stale_target, _cand_equiv
    ):
        if conv.written_path:
            proof_suite = conv.written_path
        else:
            proof_suite = (
                _covering_test_files(root, _kill_matrix(file, function, project_root), conv.line_owner_ids)
                or None
            )

    def _suite_green() -> bool:
        if proof_suite is None:
            return False
        ok, count = verify_under_pytest(root, proof_suite)
        return ok and count > 0

    if proof_suite is None:
        # Distinct causes, distinct sentences: a stale converge HAD a suite (it pinned a function
        # that no longer exists); candidate-equivalents mean the suite is complete but proves only
        # the pinned behaviours (#41); "no proof suite" would send a user to build one they have.
        if conv is not None and conv.stale_target:
            say(
                "proof suite is STALE — the target changed during the converge; "
                "re-run to prove; extractions will be proposed only"
            )
        elif _cand_equiv:
            # The GATE is right to count the union — a crash-only survivor is not value-pinned
            # either, so the proof suite did not pin that behaviour and preservation is not proven
            # for it. But the MESSAGE must not call them all "unproven" (#36): an input DOES
            # distinguish a crash-only mutant, and `detective flag` is the wrong advice for one.
            # `conv is not None` is implied by `_cand_equiv` being non-zero — but only via an
            # invariant established forty lines up, which a reader has to reconstruct and a later
            # edit can silently break. State it here (ty: unresolved-attribute).
            _crash = len(conv.survivor_report.crash_only) if conv and conv.survivor_report else 0
            _unpinned = _cand_equiv - _crash
            _named = " and ".join(
                bit
                for bit in (
                    f"{_unpinned} candidate-equivalent" if _unpinned else "",
                    f"{_crash} crash-only" if _crash else "",
                )
                if bit
            )
            say(
                f"{_named} survivor(s) block automatic application — "
                "a green trial would prove only the pinned behaviours, not these. "
                "`detective flag` each that is truly equivalent, or supply a stronger proof; "
                "extractions will be proposed only"
            )
        else:
            say("no proof suite — nothing can be proven; extractions will be proposed only")
    else:
        say("baseline: running the proof suite against the UNCHANGED function…")
    baseline_green = _suite_green()

    applied: list[Extraction] = []
    proposed: list[Decomposition] = []
    unsafe: list[str] = []
    from .engine import _purge_stale_bytecode

    for _ in range(max_extractions):
        # The trial loop draws from the same wall (issue #31): each extraction re-runs the
        # proof suite (pytest), so an unbounded loop over many candidates could outlive the
        # deadline the proof converge respected. Stop starting new trials once it is gone.
        if budget_is_exhausted(_budget_ms()):
            budget_cut, cut_phase = True, cut_phase or "decompose trial"
            say("⚠ aggregate deadline exhausted — stopping decompose trials")
            break
        with open(full, encoding="utf-8") as fh:
            source = fh.read()
        tree = ast.parse(source)
        func = _resolve(tree, function)
        if func is None:
            break
        plan = decompose(func, function, surviving_categories)
        progressed = False
        for candidate in plan.candidates:
            # Value gate (#3): reject a non-seam BEFORE trialling it. A split that leaves the parent
            # a pure delegating wrapper (or extracts all but a trivial residual) adds a call hop and
            # a test-indirection layer for zero readability gain — proven-preserving, but not worth
            # applying. Skip to the next candidate; the outer loop ends if none is worth it.
            block_lines = candidate.end_line - candidate.start_line + 1
            parent_lines = (func.end_lineno or func.lineno) - func.body[0].lineno + 1
            is_wrapper = _leaves_pure_wrapper(func, candidate.start_line, candidate.end_line)
            # The SAME predicate diagnose counts on (issue #33), so the two never disagree.
            if not _candidate_worth(func, candidate):
                say(
                    f"skipping low-value extraction {candidate.proposed_name}: "
                    + (
                        "leaves a pure delegating wrapper"
                        if is_wrapper
                        else f"near-total, {block_lines}/{parent_lines} lines"
                    )
                    + " — not a seam"
                )
                continue
            extraction = extract_candidate(source, function, candidate)
            if extraction is None:
                unsafe.append(f"block lines {candidate.start_line}-{candidate.end_line}")
                continue
            # Trial-apply on disk, PROVE against the mutant-complete suite, then either
            # keep (write mode) or revert (dry run / rejected).
            say(
                f"trialling: {extraction.helper_name}"
                f"({', '.join(extraction.params)}) -> {', '.join(extraction.returns) or 'None'} "
                "— re-running the proof suite against the rewrite…"
            )
            with open(full, "w", encoding="utf-8") as fh:
                fh.write(extraction.new_source)
            # The proof run must import THIS trial, not bytecode cached from the
            # pre-trial file (same-second, same-size writes fool the .pyc check).
            _purge_stale_bytecode(full)
            proven = baseline_green and _suite_green()
            # A green trial is necessary but not sufficient (#16): it proves the suite pinned every
            # dimension it PINS, but an interface obligation nothing can establish (`unsupported`)
            # must not ride a green rerun into an auto-apply. `trial_verdict` is the ONE decision the
            # loop consumes — proven / witnessed / rejected / unproven — so the message and the
            # apply gate can never re-derive it differently. For the current model no real candidate
            # carries an unsupported obligation, so the disposition only ever WITHHOLDS and a clean
            # run applies exactly as before; #15's calibration is what can start producing `witnessed`.
            _code = trial_verdict(
                proven, proof_suite is not None, contract_apply_disposition(extraction.contract)
            )
            apply_ok = _code == "proven"
            if _code == "unproven":
                verdict = "unproven — no suite to prove against; proposed, not applied"
            elif _code == "rejected":
                verdict = "rejected — the suite says behavior changed"
            elif _code == "witnessed":
                _unsup = ", ".join(
                    sorted({o.kind for o in extraction.contract.obligations if o.evidence == "unsupported"})
                )
                verdict = (
                    f"witnessed only — green, but interface obligation(s) [{_unsup}] are "
                    "unsupported; proposed, not applied"
                )
            else:
                verdict = "PROVEN — behavior preserved"
            say(f"{verdict}: {extraction.helper_name}")
            if apply_ok and write:
                applied.append(extraction)
                progressed = True
                break  # keep it; re-read and re-plan against the rewritten file
            with open(full, "w", encoding="utf-8") as fh:
                fh.write(source)  # revert the trial
            # Never leave the USER's next import running trial bytecode: the revert
            # restores the pre-trial content, so retire the trial's cache with it.
            _purge_stale_bytecode(full)
            # Carry the ACTUAL trial code, not just `validated`: `_code` distinguishes a rewrite
            # the suite disproved (`rejected`) from one that was never tested (`unproven` — the
            # suite was withheld because candidate-equivalents block it). The CLI banner needs that
            # difference; `validated=apply_ok` collapses it to a single False.
            proposed.append(Decomposition(extraction, validated=apply_ok, trial=_code))
        if not (write and progressed):
            break
    return DecompositionApply(
        function=function,
        applied=tuple(applied),
        proposed=tuple(proposed),
        unsafe_blocks=tuple(dict.fromkeys(unsafe)),
        proof=conv,
        policy_id=conv.policy_id if conv is not None else wesker_policy_id(),
        transform_class_id=transform_class_id(),
        budget_exhausted=budget_cut,
        cut_phase=cut_phase,
        # stdout_bytes is stamped by the ``apply_decomposition`` containment shell.
    )
