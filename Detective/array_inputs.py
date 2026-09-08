"""Bounded NumPy witnesses for ledger Step 3; candidates, never reachability proofs.

Only an existing NumPy binding establishes the type. No tuple-index heuristic or
user expression evaluation is involved. The literal --input grammar is unchanged.
"""

from __future__ import annotations

import ast
import sys
from types import ModuleType
from typing import Any

from .equivalence import SourceExpr


def array_source_disposition(rank: int, size: int, kind: str, finite: bool, exact: bool) -> str:
    """Choose the bounded serializable array domain (ledger Step 3, pure — pinned)."""
    if not exact:
        return "unsupported_type"
    if rank not in (1, 2) or not 0 <= size <= 16:
        return "outside_bound"
    if kind not in ("b", "i", "u", "f"):
        return "unsupported_dtype"
    if not finite:
        return "nonfinite"
    return "render"


def array_source(value: Any) -> SourceExpr | None:
    """Render an exact small numeric ndarray, preserving its shape and dtype."""
    numpy = sys.modules.get("numpy")
    if not isinstance(numpy, ModuleType) or type(value) is not vars(numpy).get("ndarray"):
        return None
    status = array_source_disposition(value.ndim, value.size, value.dtype.kind, True, True)
    if status != "render":
        return None
    if not bool(numpy.isfinite(value).all()):
        return None
    # Restrict floats to at most float64: tolist() for wider floats need not yield literals.
    if value.dtype.kind == "f" and value.dtype.itemsize > 8:
        return None
    expr = f"numpy.array({value.tolist()!r}, dtype={value.dtype.str!r}).reshape({value.shape!r})"
    return SourceExpr(value.copy(), expr, ("import numpy",), copy_on_use=True)


def array_grid(annotation: ast.AST | None, namespace: dict) -> list[SourceExpr] | None:
    """Finite seeds only for an annotation resolving to the loaded numpy.ndarray."""
    numpy = sys.modules.get("numpy")
    if not isinstance(numpy, ModuleType):
        return None
    node = annotation
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        try:
            node = ast.parse(node.value, mode="eval").body
        except SyntaxError:
            return None
    if isinstance(node, ast.Name):
        resolved = namespace.get(node.id)
    elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        base = namespace.get(node.value.id)
        resolved = vars(base).get(node.attr) if isinstance(base, ModuleType) else None
    else:
        return None
    if resolved is not vars(numpy).get("ndarray"):
        return None
    values = ([], [0], [1, 2], [[0]], [[0, 1], [2, 3]], [[3, 2], [1, 0]])
    return [source for data in values if (source := array_source(numpy.array(data, dtype="int64")))]
