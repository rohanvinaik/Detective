"""B0 (#15 F0): active structural search — turn a deep_structural candidate-equivalent into a KILL.

TEST_BASIS §17 F0 ("route the un-killed residual to synthesis"), the tractable half. A
worklist/fixpoint target over a nested-int container (``deep_structural`` per #67's detector) has
distinguishing inputs the scalar and length-variant grids cannot construct: CROSS-REFERENTIAL
adjacency topologies whose inner integers index back into the outer list. Before B0 those survivors
filed as candidate-equivalent (a claim about the input pool wearing the costume of a claim about the
code); B0 retries the classification over a fixed topology library and, positive-only, upgrades the
ones a topology distinguishes to proven kills.

These are INTENT tests authored from the design, not a characterization: the truth-table pins the
retry gate completely (a total function over four booleans), and the end-to-end asserts the behaviour
the feature exists for — a residual the default pool leaves becomes a kill under B0, and not
otherwise. General worklist synthesis (arbitrary depth / cross-reference) is deliberately NOT claimed
here; it stays the open frontier (B1).
"""

from __future__ import annotations

import ast
import itertools

import Detective.engine as engine
from Detective.engine import (
    _ADJACENCY_TOPOLOGIES,
    _is_nested_int_container,
    _nested_int_container_positions,
    _structural_topology_inputs,
    classify_survivors,
    structural_input_difficulty,
    structural_retry_gate,
    structural_shape,
)

WORKLIST_SRC = '''
def sum_reachable(adj: list[list[int]], start: int) -> int:
    """Sum of the indices reachable from ``start`` in an adjacency list (a worklist traversal)."""
    total = 0
    seen: set[int] = set()
    stack = [start]
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        total += node
        for nbr in adj[node]:
            stack.append(nbr)
    return total
'''


# ── the retry gate — the pinned pure decision (truth table, all 16 rows) ──────────
def test_structural_retry_gate_runs_iff_worklist_residual_and_search_is_safe():
    # "run" is the ONE conjunction: a deep_structural target that STILL has a candidate-equivalent
    # residual to upgrade, on a non-effectful target (a fabricated adjacency list would be damage),
    # with budget left. Any single failure of those four ⇒ "skip". Enumerated completely.
    for deep, persisting, effects, exhausted in itertools.product([False, True], repeat=4):
        expected = "run" if (deep and persisting and not effects and not exhausted) else "skip"
        assert structural_retry_gate(deep, persisting, effects, exhausted) == expected, (
            deep,
            persisting,
            effects,
            exhausted,
        )


def test_gate_never_runs_on_an_effectful_target():
    # The world-effects gate is not advisory: a fabricated topology CALLS the target, so on an
    # effectful function it is damage, never a guess — the same line the fabricated grid pool draws.
    assert structural_retry_gate(True, True, True, False) == "skip"


def test_gate_never_runs_once_the_wall_is_exhausted():
    # #31: a cut run keeps its first-pass verdicts rather than starting a second search it cannot
    # finish.
    assert structural_retry_gate(True, True, False, True) == "skip"


# ── the nested-int-container detector ─────────────────────────────────────────────
def _ann(annotation: str) -> ast.AST:
    return ast.parse(f"def f(x: {annotation}): ...").body[0].args.args[0].annotation


def test_detector_fires_on_list_of_list_of_int():
    assert _is_nested_int_container(_ann("list[list[int]]")) is True


def test_detector_fires_on_list_of_tuple_of_int():
    # tuple[int, ...] carries an ast.Tuple slice; the element type is its first entry.
    assert _is_nested_int_container(_ann("list[tuple[int, ...]]")) is True


def test_detector_rejects_a_flat_int_list():
    # A flat list is within the scalar/length grid's reach — not the topology's job.
    assert _is_nested_int_container(_ann("list[int]")) is False


def test_detector_rejects_a_nested_str_container():
    # The topology trick is that inner values are valid INDICES; a non-int leaf is not indexable.
    assert _is_nested_int_container(_ann("list[list[str]]")) is False


def test_detector_rejects_an_unannotated_parameter():
    assert _is_nested_int_container(None) is False


def test_positions_are_in_the_self_cls_skipped_grid_order():
    # _input_grids skips self/cls and appends one grid per remaining positional; the positions must
    # index into THAT reduced space so the caller can swap topologies in slot-for-slot.
    node = (
        ast.parse("class C:\n    def m(self, name: str, adj: list[list[int]], k: int): ...").body[0].body[0]
    )
    # reduced params: name(0), adj(1), k(2) — adj is the only nested container.
    assert _nested_int_container_positions(node) == [1]


# ── the topology generator ────────────────────────────────────────────────────────
def test_generator_places_topologies_in_the_nested_slot_as_full_tuples():
    node = ast.parse(WORKLIST_SRC).body[0]
    tuples = _structural_topology_inputs(node, {})
    assert tuples, "a deep_structural target with a nested-int param must yield topology inputs"
    # every tuple is (adj, start) — full arity — and each adjacency slot is a library topology.
    assert all(len(t) == 2 for t in tuples)
    assert all(list(t[0]) in _ADJACENCY_TOPOLOGIES for t in tuples)
    # the cross-referential structures the length-variant grid cannot build are present.
    adjs = {tuple(map(tuple, t[0])) for t in tuples}
    assert ((1,), (0,)) in adjs  # a two-node cycle


def test_generator_is_empty_without_a_nested_container_param():
    node = ast.parse("def f(x: int, y: list[int]): ...").body[0]
    assert _structural_topology_inputs(node, {}) == []


# ── end-to-end: the residual the default pool leaves becomes a kill under B0 ────────
def _write_target(tmp_path):
    (tmp_path / "graph.py").write_text(WORKLIST_SRC)
    return str(tmp_path)


def test_the_target_is_deep_structural():
    # The premise of the whole feature: this shape is the one #67 flags as beyond scalar synthesis.
    node = ast.parse(WORKLIST_SRC).body[0]
    assert structural_input_difficulty(**structural_shape(node)) == "deep_structural"


def test_b0_kills_a_residual_the_default_pool_leaves_candidate_equivalent(tmp_path, monkeypatch):
    root = _write_target(tmp_path)

    # With B0 forced OFF, the deep_structural target has at least one survivor no synthesized input
    # discriminates — the candidate-equivalent residual the feature exists to close.
    monkeypatch.setattr(engine, "structural_retry_gate", lambda *a, **k: "skip")
    without = classify_survivors("graph.py", "sum_reachable", root)
    kills_without = sum(1 for v in without.killable if v.killable)
    assert without.unclassified, "expected an un-discriminated residual before B0 (the F0 gap)"

    # With B0 (the real gate), the topology library proves strictly more kills, and at least one
    # winning witness IS a library topology — the cross-referential input the grid could not build.
    monkeypatch.undo()
    with_b0 = classify_survivors("graph.py", "sum_reachable", root)
    kills_with = sum(1 for v in with_b0.killable if v.killable)
    assert kills_with > kills_without, (kills_without, kills_with)

    topo_witnesses = [
        v
        for v in with_b0.killable
        if v.killable and v.witness is not None and list(v.witness.args[0]) in _ADJACENCY_TOPOLOGIES
    ]
    assert topo_witnesses, "at least one kill must be witnessed by a library topology"
    # a stale 'no input discriminates' note must not survive a new kill.
    assert with_b0.note is None
