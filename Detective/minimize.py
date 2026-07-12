"""Minimal complete test suites — greedy set-cover over a kill matrix.

A suite is *functionally-complete* when it kills every killable mutant, and
*minimal* when no test can be dropped without losing a kill. Detective computes
the minimal covering subset from Wesker's ``kill_matrix`` (mutant -> the tests
that killed it); tests outside that subset kill nothing the kept set does not
already kill.

Dropping such a test is NOT unconditionally safe — it may still cover a *line* no
mutant exercises — so minimization here SURFACES the redundant set as a proposal;
deletion is confirmed elsewhere, never automatic. (Line coverage is the second
axis of completeness, folded in by the caller.)
"""

from __future__ import annotations


def coverage_by_test(kill_matrix: dict[str, list[str]]) -> dict[str, set[str]]:
    """Invert ``mutant -> [killing tests]`` into ``test -> {mutants it kills}``."""
    by_test: dict[str, set[str]] = {}
    for mutant, tests in kill_matrix.items():
        for test in tests:
            by_test.setdefault(test, set()).add(mutant)
    return by_test


def minimal_cover(kill_matrix: dict[str, list[str]]) -> set[str]:
    """Greedy set-cover: the smallest set of tests that kills every killed mutant.

    Each step takes the test killing the most still-uncovered mutants, breaking
    ties by test name so the result is deterministic. A mutant killed by exactly
    one test forces that test in (it is the only cover), so every unique killer is
    always retained.
    """
    by_test = coverage_by_test(kill_matrix)
    uncovered = set(kill_matrix.keys())
    chosen: set[str] = set()
    while uncovered:
        best = min(by_test, key=lambda t: (-len(by_test[t] & uncovered), t))
        gain = by_test[best] & uncovered
        if not gain:
            break  # no remaining test covers anything left (shouldn't happen)
        chosen.add(best)
        uncovered -= gain
    return chosen


def redundant_tests(kill_matrix: dict[str, list[str]]) -> set[str]:
    """Tests that kill nothing the minimal cover does not — redundant for kills.

    Note: redundant *for kills* only. A test here may still cover a unique line,
    so this is the candidate set to PROPOSE for removal, not to delete outright.
    """
    return set(coverage_by_test(kill_matrix)) - minimal_cover(kill_matrix)
