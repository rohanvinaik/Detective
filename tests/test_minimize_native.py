"""Tests for Detective.minimize — greedy set-cover over a kill matrix.

Pure functions, mutation-driven to value-assertion ceilings. Plain helpers, no
fixtures (Wesker runs test callables by direct call, so fixtures carry no kill
power).
"""

from __future__ import annotations

from Detective.minimize import coverage_by_test, minimal_cover, redundant_tests


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
