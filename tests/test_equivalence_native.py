"""Tests for Detective.equivalence — killable vs equivalent-candidate by execution.

Pure functions (they only call the callables handed to them), mutation-driven to
value-assertion ceilings. Plain module-level helper callables, no fixtures.
"""

from __future__ import annotations

from Detective.equivalence import (
    MutantVerdict,
    SurvivorReport,
    Witness,
    _grid_for,
    _outcome,
    candidate_inputs,
    classify_survivor,
    find_witness,
    typed_inputs,
)


# ── _grid_for / typed_inputs ──────────────────────────────────────
def test_grid_for_known_types():
    assert _grid_for("str") == ["", "a", "abc"]
    assert _grid_for("bool") == [False, True]


def test_grid_for_unknown_or_none_falls_back_to_ints():
    assert _grid_for(None) == [-1, 0, 1, 2, 3]
    assert _grid_for("SomeClass") == [-1, 0, 1, 2, 3]


def test_typed_inputs_empty_is_single_empty_tuple():
    assert typed_inputs([]) == [()]


def test_typed_inputs_str_param_yields_strings():
    assert typed_inputs(["str"]) == [("",), ("a",), ("abc",)]


def test_typed_inputs_small_signature_is_full_product():
    assert typed_inputs(["bool", "bool"]) == [
        (False, False),
        (False, True),
        (True, False),
        (True, True),
    ]


def test_typed_inputs_large_signature_is_zipped_rows():
    # 5^3 = 125 > cap -> positionally-zipped diagonals (5 rows)
    assert typed_inputs(["int", "int", "int"]) == [
        (-1, -1, -1),
        (0, 0, 0),
        (1, 1, 1),
        (2, 2, 2),
        (3, 3, 3),
    ]


def _verdict(killable: bool) -> MutantVerdict:
    w = Witness((1,), "1", "2") if killable else None
    return MutantVerdict("M", "VALUE", "", killable, w, 3)


# ── SurvivorReport ────────────────────────────────────────────────
def test_survivor_report_splits_killable_from_equivalent():
    rep = SurvivorReport((_verdict(True), _verdict(False), _verdict(False)), (), None)
    assert len(rep.killable) == 1
    assert len(rep.equivalent) == 2


def test_survivor_report_carries_unclassified_and_note():
    rep = SurvivorReport((), ("- a\n+ b",), note="inputs don't exercise this function")
    assert rep.killable == () and rep.equivalent == ()
    assert rep.unclassified == ("- a\n+ b",)
    assert rep.note == "inputs don't exercise this function"


# ── candidate_inputs ──────────────────────────────────────────────
def test_candidate_inputs_arity_zero_is_single_empty_tuple():
    assert candidate_inputs(0) == [()]


def test_candidate_inputs_arity_one_is_the_base_grid():
    assert candidate_inputs(1) == [(-1,), (0,), (1,), (2,), (3,)]


def test_candidate_inputs_arity_two_is_full_product_including_boundaries():
    got = candidate_inputs(2)
    assert len(got) == 25
    assert (0, 0) in got and (-1, 2) in got


def test_candidate_inputs_wide_signature_stays_bounded():
    got = candidate_inputs(3)
    assert len(got) == 8  # 5 diagonals + 3 varied
    assert (1, 2, 3) in got and (3, 2, 1) in got


def test_candidate_inputs_arity_three_is_pinned_verbatim():
    # pin the exact grid so the range/modulo arithmetic in the varied tuples is
    # specified, not just counted
    assert candidate_inputs(3) == [
        (-1, -1, -1),
        (0, 0, 0),
        (1, 1, 1),
        (2, 2, 2),
        (3, 3, 3),
        (1, 2, 3),
        (3, 2, 1),
        (0, 1, 2),
    ]


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
    v = classify_survivor("M1", "VALUE", "- x*1\n+ x", lambda x: x * 1, lambda x: x, [(3,), (0,)])
    assert v.killable is False
    assert v.witness is None
    assert v.label == "equivalent-candidate"
    assert v.searched == 2
