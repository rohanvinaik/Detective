"""Receiver factories for `detective converge --receiver-factory` on METHOD targets whose class
cannot be constructed without arguments (the 2026-09-06 dogfood sweep).

A method's receiver is a fixture the tool cannot synthesize: `converge` says so
("needs-receiver — <Class>() could not be constructed without arguments") and asks for
`MODULE:CALLABLE`. Each factory here builds the smallest receiver on which every branch of the
target method is REACHABLE — that is the whole design criterion, stated per factory — so the
authored `--input`s can drive the method through its lines and the mutants can be killed.
Not a test module (no `test_` prefix): pytest never collects it; converge imports it.
"""

from __future__ import annotations

import ast

from Detective.purity import _SideEffectVisitor


def make_side_effect_visitor() -> _SideEffectVisitor:
    """A `_SideEffectVisitor` over a METHOD with parameters, so `visit_Call` can reach both arms of
    every branch: `self` is a local name (`is_method=True` seeds it), every parameter is external
    (parameters are aliases the caller owns — the visitor's own doctrine), and nothing has been
    flagged yet, so each authored call's reason is the only one appended."""
    func = ast.parse("def method(self, items, path, x):\n    return x\n").body[0]
    assert isinstance(func, ast.FunctionDef)
    return _SideEffectVisitor(func, True)
