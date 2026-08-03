"""Tests for Detective.minimize — greedy set-cover over a kill matrix.

Pure functions, mutation-driven to value-assertion ceilings. Plain helpers, no
fixtures (Wesker runs test callables by direct call, so fixtures carry no kill
power).
"""

from __future__ import annotations

from Detective.minimize import (
    coverage_by_test,
    minimal_cover,
    redundant_2axis,
    redundant_tests,
    strip_foreign_evidence,
)


# ── coverage_by_test ──────────────────────────────────────────────
def test_coverage_by_test_inverts_matrix():
    km = {"m1": ["ta", "tb"], "m2": ["ta"]}
    assert coverage_by_test(km) == {"ta": {"m1", "m2"}, "tb": {"m1"}}


def test_coverage_by_test_empty():
    assert coverage_by_test({}) == {}


# ── minimal_cover ─────────────────────────────────────────────────
def test_minimal_cover_keeps_both_unique_killers():
    # each mutant killed by exactly one distinct test -> both are forced in
    assert minimal_cover({"m1": ["ta"], "m2": ["tb"]}) == {"ta", "tb"}


def test_minimal_cover_drops_the_redundant_test():
    # ta kills both mutants; tb kills only m1 -> tb is redundant
    assert minimal_cover({"m1": ["ta", "tb"], "m2": ["ta"]}) == {"ta"}


def test_minimal_cover_tie_break_is_deterministic_by_name():
    # both cover exactly one mutant of equal size -> lexicographically-smaller name wins
    assert minimal_cover({"m1": ["tb", "ta"]}) == {"ta"}


def test_minimal_cover_empty_matrix_is_empty():
    assert minimal_cover({}) == set()


# ── redundant_tests ───────────────────────────────────────────────
def test_redundant_tests_names_only_the_droppable():
    assert redundant_tests({"m1": ["ta", "tb"], "m2": ["ta"]}) == {"tb"}


def test_redundant_tests_empty_when_all_load_bearing():
    assert redundant_tests({"m1": ["ta"], "m2": ["tb"]}) == set()


# ── issue #7: foreign generated evidence must not justify deletions ─────────────


def test_sibling_generated_test_cannot_make_owned_witness_removable():
    # T (owned) and S (foreign synth) kill the same mutant; unfiltered redundancy
    # flags T, filtered redundancy keeps it — S's file evaporates on its next converge
    km = {"m1": ["test_own_value_0", "test_sibling_value_0"]}
    lc = {"test_own_value_0": [3], "test_sibling_value_0": [3]}
    unfiltered = redundant_2axis(km, lc)
    assert unfiltered  # one of the two is redundant today
    own_km, own_lc = strip_foreign_evidence(km, lc, {"test_sibling_value_0"})
    assert redundant_2axis(own_km, own_lc) == set()
    assert own_km == {"m1": ["test_own_value_0"]}
    assert "test_sibling_value_0" not in own_lc


def test_user_written_tests_still_make_generated_witness_redundant():
    # a user test is stable base evidence: it CAN render an owned witness redundant
    km = {"m1": ["test_own_value_0", "test_user_pins_m1"]}
    lc = {"test_own_value_0": [], "test_user_pins_m1": [3]}
    own_km, own_lc = strip_foreign_evidence(km, lc, set())
    assert "test_own_value_0" in redundant_2axis(own_km, own_lc)


def test_parametrized_rows_are_foreign_by_base_name():
    km = {"m1": ["test_sibling_golden[args0-1]", "test_own_value_0"]}
    lc = {"test_sibling_golden[args0-1]": [3]}
    own_km, own_lc = strip_foreign_evidence(km, lc, {"test_sibling_golden"})
    assert own_km == {"m1": ["test_own_value_0"]}
    assert own_lc == {}
