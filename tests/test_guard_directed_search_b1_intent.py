"""B1 (#15 F0): guard-directed active search — turn a reachability-identified unreached survivor into a KILL.

B0 closed the deep_structural worklist case with a fixed adjacency-topology library. B1 generalizes it to
the SIMPLE comparison guard a candidate-equivalent sits behind: a survivor on a line gated by ``len(x) > 5``
or ``x == 42`` is unreached because the scalar grid never entered that branch, and the branch's OWN guard
names the reaching condition — so we synthesize an input that satisfies it (read off the AST) and retry.

Positive-only, exactly like B0: an input can only PROVE a kill, never erase one, so this can never
manufacture a false COMPLETE. The differential / domain-object reach (serialize_rule's differential
``Relation``) stays the open frontier — a fixture caveat, NOT claimed here.

INTENT tests: the two pure decisions are hand-pinned truth tables (converge inflates on wholesale-imported
``engine.py`` — the documented hazard, same as ``structural_retry_gate``); the generator and the end-to-end
assert the behaviour the feature exists for — a survivor the default pool leaves unreached becomes a kill
under B1, and not otherwise.
"""

from __future__ import annotations

import ast

import Detective.engine as engine
from Detective.engine import (
    _guard_directed_inputs,
    classify_survivors,
    guard_comparison_target,
    guard_retry_gate,
)

_PICK = (
    "def pick(items: list) -> int:\n"
    "    if len(items) > 5:\n"
    "        return items[5] * 100  # unreached by the length grid (len 0..2) → a value-mutant survives\n"
    "    return 0\n"
)


# ── the pure decision: comparison → satisfying value (truth table) ────────────────
def test_guard_comparison_target_is_the_adjacent_satisfying_integer():
    assert guard_comparison_target(">", 5) == 6
    assert guard_comparison_target("<", 5) == 4
    assert guard_comparison_target(">=", 5) == 5
    assert guard_comparison_target("<=", 5) == 5
    assert guard_comparison_target("==", 5) == 5
    assert guard_comparison_target("!=", 5) == 6


def test_an_unsatisfiable_or_unknown_operator_is_none_not_a_guess():
    # The honest bound: an operator a single adjacent integer cannot satisfy leaves the survivor a
    # caveat, never a fabricated kill.
    assert guard_comparison_target("in", 5) is None
    assert guard_comparison_target("is", 5) is None
    assert guard_comparison_target("", 5) is None


# ── the retry gate (truth table, all 8 rows) ─────────────────────────────────────
def test_guard_retry_gate_runs_iff_a_candidate_remains_and_the_search_is_safe():
    import itertools

    for cand, effects, exhausted in itertools.product([False, True], repeat=3):
        expected = "run" if (cand and not effects and not exhausted) else "skip"
        assert guard_retry_gate(cand, effects, exhausted) == expected, (cand, effects, exhausted)


# ── the generator ────────────────────────────────────────────────────────────────
def test_generator_builds_a_length_satisfying_list_for_a_len_guard():
    node = ast.parse(_PICK).body[0]
    # line 3 (`return items[5] * 100`) is gated by `len(items) > 5` → a non-trivial list of length 6,
    # distinct non-zero so a value-mutant on the indexed element is distinguishable, not zeroed out.
    inputs = _guard_directed_inputs(node, {}, frozenset({3}))
    assert inputs == [([1, 2, 3, 4, 5, 6],)], inputs


def test_generator_builds_the_satisfying_value_for_a_scalar_equality_guard():
    src = "def scale(x: int) -> int:\n    if x == 42:\n        return x * 7\n    return x + 1\n"
    node = ast.parse(src).body[0]
    assert _guard_directed_inputs(node, {}, frozenset({3})) == [(42,)]
    # an unconditional line (the else return) has no guard — nothing to synthesize.
    assert _guard_directed_inputs(node, {}, frozenset({4})) == []


# ── end-to-end: the unreached survivor becomes a kill under B1 ───────────────────
def _write(tmp_path) -> str:
    (tmp_path / "pick.py").write_text(_PICK)
    tdir = tmp_path / "tests"
    tdir.mkdir()
    (tdir / "test_pick.py").write_text(
        "from pick import pick\n\n\n"
        "def test_pick():\n"
        "    assert pick([]) == 0\n"
        "    assert pick([1, 2]) == 0\n"
    )
    return str(tmp_path)


def test_b1_kills_an_unreached_survivor_the_default_pool_leaves(tmp_path, monkeypatch):
    root = _write(tmp_path)

    # B1 forced OFF: the survivor behind `len(items) > 5` is unreached by the length grid and survives
    # as a candidate-equivalent (reached=False — the reachability signal's own residual).
    monkeypatch.setattr(engine, "guard_retry_gate", lambda *a, **k: "skip")
    without = classify_survivors("pick.py", "pick", root, deadline_s=None)
    kills_without = len(without.killable)
    assert any(not v.reached for v in without.candidate_equivalent), "expected an unreached residual off B1"

    # B1 ON: the guard-directed input `[1..6]` reaches the branch and proves the kill.
    monkeypatch.undo()
    with_b1 = classify_survivors("pick.py", "pick", root, deadline_s=None)
    assert len(with_b1.killable) > kills_without, (kills_without, len(with_b1.killable))
    # positive-only: every remaining candidate-equivalent is one B1 could not reach/propagate, never a
    # new false survivor — and any that remain are reached-but-not-propagated (the irreducible residual).
    assert all(v.reached for v in with_b1.candidate_equivalent)
