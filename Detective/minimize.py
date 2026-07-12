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


def _obligations_by_test(
    kill_matrix: dict[str, list[str]], line_coverage: dict[str, list[int]]
) -> dict[str, set]:
    """Invert both matrices into ``test -> {obligations it discharges}``, where an
    obligation is a killed mutant (``('m', desc)``) or a covered line (``('l', n)``).
    Namespacing keeps a mutant description and a line number from ever colliding, so
    the two completeness axes share one set-cover."""
    by_test: dict[str, set] = {}
    for mutant, tests in kill_matrix.items():
        for test in tests:
            by_test.setdefault(test, set()).add(("m", mutant))
    for test, lines in line_coverage.items():
        for line in lines:
            by_test.setdefault(test, set()).add(("l", line))
    return by_test


def minimal_cover_2axis(
    kill_matrix: dict[str, list[str]], line_coverage: dict[str, list[int]]
) -> set[str]:
    """Greedy set-cover over BOTH axes: the smallest test set that kills every
    killed mutant AND covers every covered line. A test survives minimization when
    it is the sole killer of a mutant OR the sole coverer of a line — so trimming to
    this set preserves mutant-completeness and line-completeness together."""
    by_test = _obligations_by_test(kill_matrix, line_coverage)
    uncovered: set = set().union(*by_test.values()) if by_test else set()
    chosen: set[str] = set()
    while uncovered:
        best = min(by_test, key=lambda t: (-len(by_test[t] & uncovered), t))
        gain = by_test[best] & uncovered
        if not gain:
            break
        chosen.add(best)
        uncovered -= gain
    return chosen


def redundant_2axis(
    kill_matrix: dict[str, list[str]], line_coverage: dict[str, list[int]]
) -> set[str]:
    """Tests outside the two-axis minimal cover — redundant for BOTH kills and
    lines. This is the set to PROPOSE for deletion (never auto-delete): every test
    here kills no mutant and covers no line that the kept set does not already."""
    return set(_obligations_by_test(kill_matrix, line_coverage)) - minimal_cover_2axis(
        kill_matrix, line_coverage
    )


def missing_lines(executable_lines: list[int], line_coverage: dict[str, list[int]]) -> list[int]:
    """Executable target lines no test covers — the line-completeness gap. Empty
    means line-complete. Sorted for stable reporting."""
    covered: set[int] = set()
    for lines in line_coverage.values():
        covered.update(lines)
    return sorted(set(executable_lines) - covered)
