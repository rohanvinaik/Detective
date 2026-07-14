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


def _collect_reads(node: ast.AST) -> set[str]:
    return {c.id for c in ast.walk(node) if isinstance(c, ast.Name) and isinstance(c.ctx, ast.Load)}


def _collect_writes(node: ast.AST) -> set[str]:
    return {
        c.id for c in ast.walk(node) if isinstance(c, ast.Name) and isinstance(c.ctx, (ast.Store, ast.Del))
    }


def _has_exit_statement(node: ast.AST) -> bool:
    """True if return/break/continue exists at THIS scope level — a jump that would
    change meaning if the block moved into a helper. Nested function/class scopes
    are not descended into (their returns are their own)."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return False
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.Return, ast.Break, ast.Continue)):
            return True
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if _has_exit_statement(child):
            return True
    return False


def _analyze_statement(index: int, stmt: ast.stmt) -> _StmtInfo:
    return _StmtInfo(
        index=index,
        stmt=stmt,
        reads=frozenset(_collect_reads(stmt)),
        writes=frozenset(_collect_writes(stmt)),
        has_exit=_has_exit_statement(stmt),
    )


def _get_param_names(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    args = func_node.args
    names = {a.arg for a in args.posonlyargs + args.args + args.kwonlyargs}
    if args.vararg:
        names.add(args.vararg.arg)
    if args.kwarg:
        names.add(args.kwarg.arg)
    return names


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
    the block is not single-exit. inputs = reads-from-outside; outputs = writes read
    after the block."""
    block = infos[start:end]
    if any(s.has_exit for s in block):
        return None
    block_reads: set[str] = set()
    block_writes: set[str] = set()
    for s in block:
        block_reads |= s.reads
        block_writes |= s.writes
    pre_defined: set[str] = set(param_names)
    for s in infos[:start]:
        pre_defined |= s.writes
    inputs = (block_reads & pre_defined) - block_writes
    post_reads: set[str] = set()
    for s in infos[end:]:
        post_reads |= s.reads
    outputs = block_writes & post_reads
    return inputs, outputs


def _suggest_name(block: list[_StmtInfo], parent_name: str) -> str:
    all_writes: set[str] = set()
    for s in block:
        all_writes |= s.writes
    named = sorted(w for w in all_writes if not w.startswith("_"))
    return f"_compute_{named[0]}" if named else f"_{parent_name}_helper"


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


def _evaluate_block(
    infos: list[_StmtInfo],
    start: int,
    end: int,
    param_names: set[str],
    parent_name: str,
    max_params: int,
    max_outputs: int,
) -> ExtractionCandidate | None:
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
    name = _suggest_name(block, parent_name)
    return ExtractionCandidate(
        start_line=line_start,
        end_line=line_end,
        proposed_name=name,
        inputs=tuple(sorted(inputs)),
        outputs=tuple(sorted(outputs)),
        cc_reduction=block_cc,
        confidence=_confidence(block, inputs, outputs, block_cc),
        reason=f"lines {line_start}-{line_end} → {name}({', '.join(sorted(inputs))}) "
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
    min_statements: int = 3,
    max_params: int = 4,
    max_outputs: int = 2,
) -> tuple[ExtractionCandidate, ...]:
    """Every contiguous statement block that is a clean, complexity-reducing
    extraction — the deterministic responsibility seams of the function."""
    body = func_node.body
    if len(body) <= min_statements:
        return ()
    infos = [_analyze_statement(i, stmt) for i, stmt in enumerate(body)]
    param_names = _get_param_names(func_node)
    n = len(infos)
    found: list[ExtractionCandidate] = []
    for start in range(n):
        for end in range(start + min_statements, min(n + 1, start + _MAX_BLOCK_STMTS)):
            candidate = _evaluate_block(
                infos, start, end, param_names, func_node.name, max_params, max_outputs
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
    return DecompositionPlan(
        function=function,
        is_decomposable=decomposable,
        candidates=candidates,
        rationale=_rationale(decomposable, candidates, surviving_categories),
    )


def _rationale(
    decomposable: bool, candidates: tuple[ExtractionCandidate, ...], surviving: tuple[str, ...]
) -> str:
    if not decomposable:
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
