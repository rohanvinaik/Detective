"""The witness search must be able to REACH the regions its own analysis names.

`quantity >= 50` mutated to `quantity == 50` differs only strictly above the edge — and the
built-in integer grid (±3) can never land there, so the mutant read "candidate-equivalent"
while `quantity == 51` kills it. Two seedings close that: the ordering EDGES the body draws
(bracketed by their integer neighbors) join the per-parameter grids, and a SUPPLIED input's
numeric coordinates are perturbed ±1 — the region a human just said matters, stepped one
past its edges.
"""

from __future__ import annotations

import ast

from Detective.engine import _input_grids, _neighbor_inputs, _ordering_edge_values
from Detective.equivalence import bounded_product, find_witness


def _fn_node(src: str) -> ast.FunctionDef:
    return ast.parse(src).body[0]


def test_ordering_edges_bracket_every_integer_boundary():
    node = _fn_node(
        "def f(q):\n    if q >= 50:\n        return 2\n    elif q >= 10:\n        return 1\n    return 0\n"
    )
    edges = _ordering_edge_values(node)
    assert edges == {"q": [49, 50, 51, 9, 10, 11]}


def test_ordering_edges_float_contributes_itself_and_bool_is_excluded():
    node = _fn_node(
        "def f(x, flag):\n"
        "    if x > 2.5:\n"
        "        return 1\n"
        "    if flag > True:\n"
        "        return 2\n"
        "    return 0\n"
    )
    edges = _ordering_edge_values(node)
    assert edges["x"] == [2.5]
    assert "flag" not in edges or all(not isinstance(v, bool) for v in edges["flag"])


def test_neighbor_inputs_step_each_numeric_coordinate_one_past():
    out = _neighbor_inputs([(50, 2.0, False)])
    assert (49, 2.0, False) in out
    assert (51, 2.0, False) in out
    assert (50, 1.0, False) in out
    assert (50, 3.0, False) in out
    # bools are ints to isinstance — but flipping one is not a boundary step; leave it alone
    assert all(args[2] is False for args in out)
    assert len(out) == len(set(out))  # no duplicates


def test_gte_collapsed_to_eq_is_killable_from_the_enriched_grid():
    # The regression itself, end to end at the search layer: with the edges in the grid, the
    # `>= 50` → `== 50` mutant has a value-witness (any input strictly above the edge).
    node = _fn_node("def f(q):\n    if q >= 50:\n        return 2\n    return 0\n")

    def original(q):
        return 2 if q >= 50 else 0

    def mutant(q):
        return 2 if q == 50 else 0

    inputs = bounded_product(_input_grids(node, {}))
    assert (51,) in inputs
    assert find_witness(original, mutant, inputs) is not None
