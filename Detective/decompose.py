"""Decomposition — propose extraction candidates for an entangled function.

A regime-B function (≥2 mutation categories with survivors) has interleaved
responsibilities; testing it whole is specification-inefficient. This proposes a
first-cut split: each top-level compound block (if/for/while/with/try) with
enough body is a separable concern worth extracting into a helper.

First-principles (not a port of LintGate's convergence subsystem). Structural
heuristic; a def-use-aware refinement is a follow-on.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

_COMPOUND_KIND: dict[type, str] = {
    ast.If: "if",
    ast.For: "for",
    ast.While: "while",
    ast.With: "with",
    ast.Try: "try",
}

# A block worth extracting has at least this many body statements.
_MIN_BODY = 2

# A function is decomposable when it has at least this many separable concerns.
_MIN_CANDIDATES = 2


@dataclass(frozen=True)
class ExtractionCandidate:
    """A top-level block proposed for extraction into a helper."""

    kind: str
    lineno: int
    statement_count: int
    suggested_name: str
    reason: str


@dataclass(frozen=True)
class DecompositionPlan:
    """The proposed decomposition of a function."""

    function: str
    is_decomposable: bool
    candidates: tuple[ExtractionCandidate, ...]
    rationale: str


def decompose(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    function: str = "",
    surviving_categories: tuple[str, ...] = (),
) -> DecompositionPlan:
    """Propose extraction candidates for ``func_node``."""
    candidates = tuple(
        _candidate(stmt) for stmt in func_node.body if _is_extractable(stmt)
    )
    decomposable = len(candidates) >= _MIN_CANDIDATES
    return DecompositionPlan(
        function=function,
        is_decomposable=decomposable,
        candidates=candidates,
        rationale=_rationale(decomposable, candidates, surviving_categories),
    )


def _is_extractable(stmt: ast.stmt) -> bool:
    return type(stmt) in _COMPOUND_KIND and _body_size(stmt) >= _MIN_BODY


def _candidate(stmt: ast.stmt) -> ExtractionCandidate:
    kind = _COMPOUND_KIND[type(stmt)]
    size = _body_size(stmt)
    return ExtractionCandidate(
        kind=kind,
        lineno=stmt.lineno,
        statement_count=size,
        suggested_name=_suggested_name(kind, stmt),
        reason=f"{kind} block with {size} statements — a separable concern",
    )


def _body_size(stmt: ast.stmt) -> int:
    """Total statements the block contains, recursively — its weight. A block that
    wraps a substantial nested block (a ``for`` around an ``if/else``) is weighed
    by everything it owns, not just its direct children."""
    return sum(1 for node in ast.walk(stmt) if isinstance(node, ast.stmt)) - 1


def _suggested_name(kind: str, stmt: ast.stmt) -> str:
    """A helper-name suggestion derived from the block."""
    if kind == "for" and isinstance(stmt, ast.For):
        target = stmt.target.id if isinstance(stmt.target, ast.Name) else "items"
        return f"process_{target}"
    if kind == "if":
        return f"handle_case_line_{stmt.lineno}"
    return f"extract_{kind}_line_{stmt.lineno}"


def _rationale(
    decomposable: bool, candidates: tuple[ExtractionCandidate, ...], surviving: tuple[str, ...]
) -> str:
    if not decomposable:
        return "fewer than 2 separable blocks — decomposition is unlikely to help"
    entangled = f" ({len(surviving)} entangled categories: {', '.join(surviving)})" if surviving else ""
    return f"{len(candidates)} separable concerns{entangled} — extract each into a helper, then re-profile"
