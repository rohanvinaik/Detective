"""Intent tests for the AST-input synthesizers in ``Detective.equivalence`` (2026-09-06).

The contract these functions document — "the value is produced by eval-ing the very expression that
will be rendered, so the live input and its emitted source cannot disagree" — had no test that
reached the eval: every existing caller asked for a non-AST type and took the early ``None``. So
the promise that a generated test reads ``ast.parse('def _f(x): ...').body[0]`` and rebuilds the
SAME node was pinned by nothing.

Written from intent: for a representative sample and for every grid entry, the rendered ``expr``
must re-evaluate (with the imports the carrier names, and nothing else) to a node whose dump equals
the live value's dump; the grid must offer more than one input per type, because one input can
never separate a mutant from its original unless it reaches the mutated line.
"""

from __future__ import annotations

import ast

import pytest

from Detective.equivalence import SourceExpr, ast_grid, synth_ast_input


def _rebuild(carrier: SourceExpr):
    ns: dict = {}
    for imp in carrier.imports:
        # S102: the carrier's own `import ast`, nothing else
        exec(imp, ns)  # noqa: S102
    # S307: Detective-synthesized expr rather than user input
    return eval(carrier.expr, ns)  # noqa: S307


@pytest.mark.parametrize(
    ("type_name", "node_type"),
    [
        ("ast.FunctionDef", ast.FunctionDef),
        ("ast.AsyncFunctionDef", ast.AsyncFunctionDef),
        ("ast.Module", ast.Module),
        ("ast.stmt", ast.stmt),
        ("ast.expr", ast.expr),
        ("ast.AST", ast.AST),
    ],
)
def test_the_sample_is_a_node_of_the_asked_type_whose_source_rebuilds_it(type_name, node_type):
    carrier = synth_ast_input(type_name)
    assert isinstance(carrier, SourceExpr)
    assert isinstance(carrier.value, node_type)
    assert carrier.imports == ("import ast",)
    assert ast.dump(_rebuild(carrier)) == ast.dump(carrier.value)


def test_an_unknown_ast_type_degrades_to_the_generic_node_not_to_nothing():
    carrier = synth_ast_input("ast.Whatever")
    assert carrier is not None
    assert isinstance(carrier.value, ast.AST)


@pytest.mark.parametrize("type_name", ["int", "", None, "str"])
def test_a_non_ast_type_is_not_this_synthesizers_business(type_name):
    assert synth_ast_input(type_name) is None
    assert ast_grid(type_name) == []


@pytest.mark.parametrize(
    "type_name", ["ast.FunctionDef", "ast.AsyncFunctionDef", "ast.Module", "ast.stmt", "ast.expr"]
)
def test_the_grid_offers_several_distinguishing_inputs_each_of_which_rebuilds(type_name):
    grid = ast_grid(type_name)
    assert len(grid) >= 2, "one input can never separate a mutant that it does not reach"
    for carrier in grid:
        assert isinstance(carrier, SourceExpr)
        assert ast.dump(_rebuild(carrier)) == ast.dump(carrier.value)


def test_an_ast_type_without_its_own_grid_falls_back_to_real_nodes_not_the_integer_grid():
    grid = ast_grid("ast.Whatever")
    assert grid, "a new node type degrades to a few real nodes"
    assert all(isinstance(c.value, ast.AST) for c in grid)
