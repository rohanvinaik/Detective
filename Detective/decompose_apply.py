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
import textwrap
from dataclasses import dataclass


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
        a.target.id
        for a in ast.walk(node)
        if isinstance(a, ast.AugAssign) and isinstance(a.target, ast.Name)
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


def block_interface(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef, index: int
) -> BlockInterface:
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


@dataclass(frozen=True)
class Extraction:
    """A generated (not-yet-validated) extraction: the helper's interface and the
    full rewritten source with the helper spliced in and the block replaced by a
    call."""

    helper_name: str
    params: tuple[str, ...]
    returns: tuple[str, ...]
    new_source: str


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


def _build(source: str, function: str):
    """Exec ``source`` in a fresh namespace and return the top-level ``function``,
    or None if it does not build (a syntax error in a generated rewrite is a failed
    extraction, never a crash)."""
    target = function.split(".")[-1]
    namespace: dict = {}
    try:
        exec(compile(source, "<decompose>", "exec"), namespace)  # noqa: S102 — our own generated source
    except Exception:  # noqa: BLE001
        return None
    return namespace.get(target)


def preserves_behavior(
    original_source: str,
    new_source: str,
    function: str,
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    """True iff the decomposed source computes the SAME result as the original on
    every synthesized input — the deterministic gate for auto-applying.

    Both versions are built and run over the input grid the witness search uses
    (types honored). Any observable difference fails preservation; so does a rewrite
    that no input exercises (nothing was actually compared — never claim safety on
    zero evidence)."""
    from .engine import _input_grids
    from .equivalence import _outcome, bounded_product

    original = _build(original_source, function)
    decomposed = _build(new_source, function)
    if original is None or decomposed is None:
        return False
    inputs = bounded_product(_input_grids(func_node, getattr(original, "__globals__", {}) or {}))
    exercised = False
    for args in inputs:
        original_outcome = _outcome(original, args)
        if not original_outcome.startswith("<raised"):
            exercised = True
        if original_outcome != _outcome(decomposed, args):
            return False
    return exercised


@dataclass(frozen=True)
class Decomposition:
    """One candidate's outcome: the generated extraction and whether execution
    proved it behavior-preserving (hence auto-appliable)."""

    extraction: Extraction
    validated: bool  # True -> safe to auto-apply; False -> propose only


@dataclass(frozen=True)
class DecompositionApply:
    """Result of decomposing a function: what was applied (validated + written) and
    what is only proposed (generated but unvalidated, or written=False)."""

    function: str
    applied: tuple[Extraction, ...]
    proposed: tuple[Decomposition, ...]
    unsafe_blocks: tuple[str, ...]  # blocks skipped as non-extractable (control escape)


def apply_decomposition(
    file: str, function: str, project_root: str = ".", *, write: bool = False, max_extractions: int = 8
) -> DecompositionApply:
    """Extract every safely-decomposable block, validating each by execution.

    Iterative: after each APPLIED extraction the file is re-read and re-planned, so
    line numbers stay correct and the function decomposes fully. A validated
    extraction is written only when ``write`` is True (the ``--apply`` confirmation);
    otherwise it is reported as proposed. Unvalidated extractions and control-flow-
    escaping blocks are always proposed / skipped, never written."""
    import os

    from .decompose import decompose

    root = os.path.abspath(project_root)
    full = file if os.path.isabs(file) else os.path.join(root, file)

    applied: list[Extraction] = []
    proposed: list[Decomposition] = []
    unsafe: list[str] = []
    for _ in range(max_extractions):
        with open(full, encoding="utf-8") as fh:
            source = fh.read()
        tree = ast.parse(source)
        func = _resolve(tree, function)
        if func is None:
            break
        body_index = {id(stmt): i for i, stmt in enumerate(func.body)}
        plan = decompose(func, function)
        progressed = False
        for candidate in plan.candidates:
            index = next(
                (i for stmt, i in ((s, body_index[id(s)]) for s in func.body) if stmt.lineno == candidate.lineno),
                None,
            )
            if index is None:
                continue
            extraction = extract_block(source, function, index)
            if extraction is None:
                unsafe.append(f"{candidate.kind} block @ line {candidate.lineno} (control-flow escape)")
                continue
            if preserves_behavior(source, extraction.new_source, function, func):
                if write:
                    with open(full, "w", encoding="utf-8") as fh:
                        fh.write(extraction.new_source)
                    applied.append(extraction)
                    progressed = True
                    break  # re-read and re-plan against the rewritten file
                proposed.append(Decomposition(extraction, validated=True))
            else:
                proposed.append(Decomposition(extraction, validated=False))
        if not (write and progressed):
            break
    return DecompositionApply(
        function=function,
        applied=tuple(applied),
        proposed=tuple(proposed),
        unsafe_blocks=tuple(dict.fromkeys(unsafe)),
    )
