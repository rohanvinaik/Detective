"""Preservation is compared by obligation SET, not by count (issue #62).

The cold-start guard kept the suite already on disk when a run's kill TOTAL dropped. Equal
totals passed, and they should not:

    before: {mutant_A, mutant_B}   count = 2
    after:  {mutant_B, mutant_C}   count = 2

`mutant_A` regressed and the guard saw nothing, because a scalar cannot express WHICH
behaviours are pinned — only how many. Shipping that suite trades one obligation for another
and reports convergence.

The invariant is containment: for an unchanged target, policy, capability set and pytest
manifest, `old admissible obligations ⊆ new`. That is strictly stronger than the count rule and
subsumes it, since containment forbids a drop in size.

`mutant_id` is what makes the comparison meaningful across two profiles: `_content_mutant_id`
hashes the mutated AST dump, so it is invocation-stable and survives regeneration. An ordinal or
a rendered description would compare positions, not behaviours.
"""

from __future__ import annotations

from Detective.converge import regressed_obligations


def test_a_swap_at_equal_count_is_caught():
    """THE defect, in one line. This is precisely what the count comparison could not see."""
    assert regressed_obligations(["A", "B"], ["B", "C"]) == ["A"]


def test_a_strict_superset_is_not_a_regression():
    """Convergence ADDS obligations. A guard that fired here would refuse every successful run,
    which is worse than the bug it replaces."""
    assert regressed_obligations(["A", "B"], ["A", "B", "C"]) == []


def test_an_identical_set_is_not_a_regression():
    assert regressed_obligations(["A", "B"], ["B", "A"]) == []


def test_a_dropped_obligation_is_caught_even_when_the_count_grows():
    """The case that most embarrasses a count rule: the total went UP and evidence was still
    destroyed. No magnitude comparison in any direction detects this."""
    assert regressed_obligations(["A", "B"], ["B", "C", "D", "E"]) == ["A"]


def test_every_lost_obligation_is_named():
    """Returning a bool would send the reader to diff two suites by hand. Sorted, so two
    identical runs cannot report differently."""
    assert regressed_obligations(["z", "a", "m"], []) == ["a", "m", "z"]


def test_an_empty_baseline_cannot_regress():
    """A cold start with nothing pinned has nothing to lose — the guard must not block the
    first run that ever writes a suite."""
    assert regressed_obligations([], ["A", "B"]) == []


def test_duplicate_ids_do_not_manufacture_a_regression():
    """Records are per kill EVENT, so one obligation can appear more than once. Comparing
    multisets would report a phantom loss when a mutant was simply killed by fewer tests."""
    assert regressed_obligations(["A", "A", "B"], ["A", "B"]) == []
