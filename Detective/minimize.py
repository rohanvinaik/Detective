"""Minimal complete test suites — greedy set-cover over a kill matrix.

A suite is *functionally-complete* when it kills every killable mutant, and
*minimal* when no test can be dropped without losing a kill. Detective computes
the minimal covering subset from a ``kill_matrix`` (mutant -> the tests that
killed it); tests outside that subset kill nothing the kept set does not
already kill.

THE MATRIX MUST BE THE FULL RELATION (#145). "Which tests kill which mutants" is a relation over
(test, mutant) — KNOWABILITY Def. 2.3 / Prop. 7.1 define killing per test — and a cover or a
redundant set is a function of that relation alone. Wesker's default ``kill_matrix`` credits each
mutant to its FIRST killer, which is an artifact of execution order (and the order follows the
trace cache's warmth), so a cover read off it moves with the cache. Nothing here can tell the two
apart; the callers hold that line (`Detective.audit.measure_kill_relation` builds the full relation
and names the states in which it cannot, and no redundant set is claimed in those).

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
    """Greedy set-cover: a small set of tests that kills every killed mutant.

    Each step takes the test killing the most still-uncovered mutants; TIES BREAK TO THE
    LEXICOGRAPHICALLY SMALLEST TEST ID (#145). The choice is therefore a function of the relation and
    the test ids alone, never of the order the tests ran or the order the matrix lists them: when
    several covers are equally good, the one kept is the one whose ids sort first, and of two tests
    with identical kill sets the smaller id is kept. A mutant killed by exactly one test forces that
    test in (it is the only cover) — which holds of a FULL matrix only; under first-killer credit
    every killed mutant looks singly killed.
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


def merge_kill_relations(per_test: dict[str, dict[str, list[str]]]) -> dict[str, list[str]]:
    """The full kill relation from one measurement PER TEST (#145, pure — pinned).

    ``per_test`` maps a test id to the kill matrix measured with that test alone in the suite
    (mutant -> the tests that killed it, here at most that one). The union is the relation
    ``mutant -> every test that kills it``: one pair per (test, mutant) the measurements witnessed,
    with no order anywhere in it — keys and killer lists are sorted, and a test only ever appears under
    its own measurement, so a measurement cannot credit a kill to a test it did not run. Split from the
    impure measurement, which holds live tests and a profile per test.
    """
    merged: dict[str, set[str]] = {}
    for test, matrix in per_test.items():
        for mutant, killers in matrix.items():
            if test in killers:
                merged.setdefault(mutant, set()).add(test)
    return {mutant: sorted(merged[mutant]) for mutant in sorted(merged)}


def kill_relation_disagreement(first_killer_mutants: list[str], full_relation_mutants: list[str]) -> int:
    """How many mutants the whole-suite run and the per-test runs disagree on being killed at all
    (#145, pure — pinned).

    The first-killer matrix and the full relation are two measurements of the same suite, so the SET of
    killed mutants must be identical; only who is credited differs. A mutant in one and not the other
    is a kill that depends on more than one test (state a test leaves behind) or on an unstable
    run — and no cover is claimed from a relation that does not reproduce the run it explains.
    """
    return len(set(first_killer_mutants) ^ set(full_relation_mutants))


def cover_standing(
    main_admits: bool,
    killed_mutants: int,
    tests_expected: int,
    tests_measured: int,
    tests_unsound: int,
    disagreeing_mutants: int,
) -> str:
    """Whether a redundant set / cover may be claimed, and if not, why (#145, pure — pinned).

    The cover and the redundant set are functions of the FULL kill relation over one function's own
    tests, never of the first-killer credit (an artifact of execution order). Where that relation is
    unavailable the state is NAMED and nothing is claimed; it never falls back to first-killer.

      "full_matrix"       the relation was measured for every candidate test (or there is nothing killed
                          to attribute, so it is empty by construction): the cover is claimed.
      "main_unresolved"   the whole-suite measurement admits no certificate (a cut, an unscored mutant,
                          an unresolved basis): the relation is not built over a measurement that
                          cannot stand.
      "test_unmeasured"   a candidate test could not be run alone (not collected live) or its own run was
                          cut or left a mutant unscored.
      "relation_disagrees" the per-test runs and the whole-suite run killed different mutants.
    """
    if not main_admits:
        return "main_unresolved"
    if killed_mutants == 0:
        return "full_matrix"
    if tests_measured < tests_expected or tests_unsound > 0:
        return "test_unmeasured"
    if disagreeing_mutants > 0:
        return "relation_disagrees"
    return "full_matrix"


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


def minimal_cover_2axis(kill_matrix: dict[str, list[str]], line_coverage: dict[str, list[int]]) -> set[str]:
    """Greedy set-cover over BOTH axes: a test set that kills every killed mutant AND
    covers every covered line, built by repeatedly taking the test with the largest
    remaining gain (ties to the lexicographically smallest test id, so the result is a
    function of the relation and the ids alone — #145; the matrix must be the FULL one).

    It is NOT the smallest such set, which this function used to claim (#103, the
    addendum to #54): greedy set cover only approximates the minimum, and it need not be
    inclusion-minimal either, since a test taken early can be covered by later picks.
    Every sole killer of a mutant and sole coverer of a line is always taken. What it
    guarantees is what deletion relies on: each observed kill and covered line keeps a
    test in this set, so trimming to it preserves mutant- and line-completeness
    together."""
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


def redundant_2axis(kill_matrix: dict[str, list[str]], line_coverage: dict[str, list[int]]) -> set[str]:
    """Tests outside the two-axis minimal cover — redundant for BOTH kills and
    lines. This is the set to PROPOSE for deletion (never auto-delete): every test
    here kills no mutant and covers no line that the kept set does not already."""
    return set(_obligations_by_test(kill_matrix, line_coverage)) - minimal_cover_2axis(
        kill_matrix, line_coverage
    )


def needed_candidates(
    kill_matrix: dict[str, list[str]], line_coverage: dict[str, list[int]], candidates: set[str]
) -> set[str]:
    """The deletion candidates the tests that STAY cannot replace (#145, pure — pinned).

    ``candidates`` are the tests proposed for deletion, spelled as the relation and the coverage name
    them. Every other test stays, so what it kills and covers is already discharged; the candidates are
    then added greedily — largest remaining gain, ties to the lexicographically smallest id — for exactly
    what is still undischarged, and those are the ones a removal would un-pin. A candidate not returned
    is replaceable by the tests that stay, and by nothing that is itself being deleted, so deleting every
    candidate not returned together keeps every killed mutant killed and every covered line covered.

    This replaces reading the whole-suite cover for need. The cover prefers whichever test sorts first
    among equals, so a candidate that merely sorted before a staying twin (`legacy:` before a nodeid) was
    kept for a function the twin already served, and which function a test was "kept for" followed spelling.
    The matrix must be the FULL relation (see the module docstring).
    """
    by_test = _obligations_by_test(kill_matrix, line_coverage)
    stay = set(by_test) - candidates
    covered: set = set().union(*(by_test[t] for t in stay)) if stay else set()
    uncovered: set = set().union(*by_test.values()) - covered if by_test else set()
    needed: set[str] = set()
    pool = {t: by_test[t] for t in by_test if t in candidates}
    # At most one pick per candidate, so the loop is bounded by construction. Everything still uncovered
    # is something only a candidate discharges (the staying tests' share was removed above), so each pick
    # has a positive gain until nothing is left.
    for _ in range(len(pool)):
        if not uncovered:
            break
        best = min(pool, key=lambda t: (-len(pool[t] & uncovered), t))
        needed.add(best)
        uncovered -= pool[best]
    return needed


def strip_foreign_evidence(
    kill_matrix: dict[str, list[str]],
    line_coverage: dict[str, list[int]],
    foreign: set[str],
) -> tuple[dict[str, list[str]], dict[str, list[int]]]:
    """Remove ``foreign`` tests from both evidence axes before a redundancy decision
    (issue #7). A sibling target's GENERATED test may genuinely kill this target's
    mutants today, but its file is rewritten wholesale on that target's next
    converge — support that can evaporate must not justify dropping a witness this
    target owns. Parametrized rows carry bracket suffixes (``test_x[args0]``); a row
    is foreign when its base name is.
    """

    def is_foreign(test: str) -> bool:
        # Resolve the identifier before comparing (#13/#54). `foreign` holds BARE function names
        # read out of a sibling's AST, while the evidence axes are keyed by pytest nodeid
        # (Wesker #16) or Wesker's `legacy:<origin>::<base>` fallback. Comparing the two
        # vocabularies directly made this ALWAYS False — so #7's guard never stripped anything,
        # and was inert for as long as the minimization it protects was also inert. Fixing only
        # the minimization would have switched a latent regression on.
        from .suite_edit import nodeid_function_name

        return nodeid_function_name(test) in foreign

    kept_matrix = {mutant: [t for t in tests if not is_foreign(t)] for mutant, tests in kill_matrix.items()}
    kept_lines = {t: lines for t, lines in line_coverage.items() if not is_foreign(t)}
    return kept_matrix, kept_lines


def missing_lines(executable_lines: list[int], line_coverage: dict[str, list[int]]) -> list[int]:
    """Executable target lines no test covers — the line-completeness gap. Empty
    means line-complete. Sorted for stable reporting."""
    covered: set[int] = set()
    for lines in line_coverage.values():
        covered.update(lines)
    return sorted(set(executable_lines) - covered)
