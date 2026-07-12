"""Tests for Detective.equivalence — killable vs equivalent-candidate by execution.

Pure functions (they only call the callables handed to them), mutation-driven to
value-assertion ceilings. Plain module-level helper callables, no fixtures.
"""

from __future__ import annotations

from Detective.equivalence import (
    Witness,
    _outcome,
    classify_survivor,
    find_witness,
)


def _double(x):
    return x * 2


def _plus_two(x):
    return x + 2


def _gt0(x):
    return x > 0


def _ge0(x):
    return x >= 0


def _boom():
    raise ValueError("nope")


# ── _outcome ──────────────────────────────────────────────────────
def test_outcome_reprs_the_value():
    assert _outcome(lambda: 42, ()) == "42"


def test_outcome_marks_a_raise_as_an_observable_outcome():
    assert _outcome(_boom, ()) == "<raised ValueError>"


# ── find_witness ──────────────────────────────────────────────────
def test_find_witness_returns_first_distinguishing_input():
    w = find_witness(_double, _plus_two, [(3,)])
    assert w == Witness((3,), "6", "5")


def test_find_witness_none_when_indistinguishable():
    # x*1 vs x agree everywhere tried -> no witness (NOT a proof of equivalence)
    assert find_witness(lambda x: x * 1, lambda x: x, [(3,), (0,), (-4,)]) is None


def test_find_witness_needs_the_boundary_input():
    # differ only at x==0: without (0,) no witness; with it, the boundary is caught
    assert find_witness(_gt0, _ge0, [(1,), (5,)]) is None
    assert find_witness(_gt0, _ge0, [(1,), (0,)]) == Witness((0,), "False", "True")


def test_find_witness_empty_inputs_is_none():
    assert find_witness(_double, _plus_two, []) is None


# ── classify_survivor ─────────────────────────────────────────────
def test_classify_killable_carries_witness_and_label():
    v = classify_survivor("M0", "ARITHMETIC", "- a*2\n+ a+2", _double, _plus_two, [(3,)])
    assert v.killable is True
    assert v.witness == Witness((3,), "6", "5")
    assert v.label == "killable"
    assert v.searched == 1


def test_classify_equivalent_candidate_has_no_witness():
    v = classify_survivor(
        "M1", "VALUE", "- x*1\n+ x", lambda x: x * 1, lambda x: x, [(3,), (0,)]
    )
    assert v.killable is False
    assert v.witness is None
    assert v.label == "equivalent-candidate"
    assert v.searched == 2
