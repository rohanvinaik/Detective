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
apart; the callers hold that line (`Detective.audit.kill_relation_of` reads the full relation the
engine measured in the profile it already ran, and names the states in which there is none; no
redundant set is claimed in those).

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


def known_killers(credit: dict[str, list[str]], relation: dict[str, list[str]]) -> dict[str, list[str]]:
    """Every test known to kill each mutant, from the engine's two records of one run (#145, pure — pinned).

    ``credit`` is the first-killer matrix, ``relation`` the per-test relation (empty when none was
    measured). A test in either kills the mutant, so the union is a set of tests that provably do; each
    killer list is sorted, so it is a function of the two records and not of the order the tests ran.
    Where the relation is whole the credit is inside it and the union IS the relation; where there is
    none the result is the credit, which is one test per mutant and follows execution order, so it is a
    LOWER BOUND on the killers. For the proof basis a certificate rests on that is enough to be sound
    (every test in it kills), and the relation makes it deterministic; it is never enough to name a
    cover or a redundant set, which read `kill_relation_of` and refuse without the relation.
    """
    mutants = sorted(set(credit) | set(relation))
    return {m: sorted(set(credit.get(m, ())) | set(relation.get(m, ()))) for m in mutants}


def display_test_id(test_id: str) -> str:
    """A test id as a page names it (#145, pure — pinned): Wesker's internal ``legacy:`` routing
    namespace stripped, nothing else changed.

    The engine spells a test it could not collect live as ``legacy:<origin>::<name>`` and one it
    collected as the bare nodeid; the two are the same test to a reader, and the prefix is bookkeeping.
    Converge printed ``detected by … ← legacy:tests/detective/…`` while ``flag``'s refusal named
    ``tests/test_m.py::test_interval`` for the same kind of mutant.
    """
    return test_id.removeprefix("legacy:")


def detecting_test_name(killers: list[str]) -> str:
    """The ONE test a page names as detecting a mutant, from every test known to kill it (#145, pure —
    pinned): the smallest displayed id, ``""`` for none.

    Any killer detects it, so which is named is only a matter of being stable: the smallest id AS
    DISPLAYED (``display_test_id``), over all killers rather than the one the run order credited, so the
    name is a function of the suite and two pages cannot name two tests for one mutant.
    """
    shown = sorted({display_test_id(t) for t in killers if t})
    return shown[0] if shown else ""


def kill_relation_disagreement(first_killer_mutants: list[str], full_relation_mutants: list[str]) -> int:
    """How many mutants the first-killer matrix and the full relation disagree on being killed at all
    (#145, pure — pinned).

    Both are read off the ONE measurement, so the SET of killed mutants must be identical; only who is
    credited differs. A mutant in one and not the other means the engine's two records of the same run
    disagree, and no cover is claimed from a relation that does not reproduce the run it explains.
    """
    return len(set(first_killer_mutants) ^ set(full_relation_mutants))


def cover_standing(main_admits: bool, engine_standing: str, disagreeing_mutants: int) -> str:
    """Whether a redundant set / cover may be claimed, and if not, why (#145, pure — pinned).

    The cover and the redundant set are functions of the FULL kill relation over one function's own
    tests, never of the first-killer credit (an artifact of execution order). The relation is measured
    by the engine in the profile it already ran (`profile(full_matrix=True)`); ``engine_standing`` is
    what the engine said of it (``kill_relation_standing``), or ``"absent"`` when the engine's result
    has no such field at all. Where the relation is unavailable the state is NAMED and nothing is
    claimed; it never falls back to first-killer.

      "full_matrix"       the engine measured the relation, whole, for every killed mutant (or nothing
                          was killed, so it is empty by construction): the cover is claimed.
      "main_unresolved"   the measurement admits no certificate (a cut, an unscored mutant, an
                          unresolved basis): the relation is not read off a measurement that cannot
                          stand.
      "test_unmeasured"   the engine's scan was not whole: the run was cut, a mutant's scan did not
                          reach every test or left a cell unresolved (a loop budget, a wall bound, a
                          refused measurement), or a killed mutant has no killer in its row.
      "relation_disagrees" the relation and the first-killer matrix killed different mutants.
      "not_requested"     the profile was not asked for the relation: there is none, and an empty one
                          would read as "no test kills anything".
      "engine_lacks_relation" the installed engine cannot measure it (an older Wesker).
    """
    if not main_admits:
        return "main_unresolved"
    if engine_standing == "absent":
        return "engine_lacks_relation"
    if engine_standing == "not_requested":
        return "not_requested"
    if engine_standing != "complete":
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
    pool = {t: obligations for t, obligations in by_test.items() if t in candidates}
    # At most one pick per candidate, so the loop is bounded by construction. Everything still uncovered
    # is something only a candidate discharges (the staying tests' share was removed above), so each pick
    # has a positive gain until nothing is left.
    for _ in range(len(pool)):
        if not uncovered:
            break
        best = _largest_gain(pool, uncovered)
        needed.add(best)
        uncovered -= pool[best]
    return needed


def _largest_gain(pool: dict[str, set], uncovered: set) -> str:
    """The test of ``pool`` discharging the most of ``uncovered``; ties to the smallest id (pure)."""
    return min(pool, key=lambda t: (-len(pool[t] & uncovered), t))


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
