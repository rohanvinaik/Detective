"""Audit an EXISTING test suite for one function — surface what is pointless,
what is missing, and how small the suite could be, without changing anything.

Detective's converge builds a complete suite from scratch; audit turns the same
lenses on a suite that already exists. It reuses the two completeness axes:
Wesker's kill matrix (which test kills which mutant) and its baseline line-coverage
matrix (which test covers which line). From those it reports, read-only:

  * ``redundant_tests`` — tests that kill no mutant AND cover no line the rest of
    the suite does not already: pointless. These are DELETION PROPOSALS, never
    auto-removed (a test carries intent a mutation matrix cannot see).
  * ``killable_gaps`` — surviving mutants a better test would kill: the suite's
    specification holes.
  * ``missing_lines`` — executable lines no test reaches.
  * ``minimal_test_count`` — the size of the two-axis minimal cover, so the bloat
    (``test_count - minimal_test_count``) is explicit.

Writing (augmenting the suite with generated tests, applying confirmed deletions)
is a separate, explicit step — audit only observes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .engine import classify_survivors, profile
from .minimize import minimal_cover_2axis, missing_lines, redundant_2axis


@dataclass(frozen=True)
class SuiteAudit:
    """Read-only assessment of an existing suite for one function."""

    function: str
    test_count: int
    kill_pct: float
    mutant_complete: bool  # kills every KILLABLE mutant (equivalents may survive)
    line_complete: bool  # covers every executable line
    redundant_tests: tuple[str, ...]  # pointless for BOTH axes -> deletion PROPOSALS
    failing_tests: tuple[str, ...]  # assert-fail on current code -> WARN, never delete
    killable_gaps: tuple[str, ...]  # killable mutants the suite fails to kill
    missing_lines: tuple[int, ...]  # executable lines no test covers
    minimal_test_count: int  # size of the two-axis minimal cover
    manual_equivalent: int = 0  # survivors manually flagged equivalent (oracle)
    candidate_equivalent: int = 0  # survivors with no distinguishing input found (UNPROVEN — flag to confirm)
    unclassified: int = 0  # survivors the search could not classify (may be killable OR equivalent)

    @property
    def complete(self) -> bool:
        """Mutant-complete AND line-complete — the suite needs no new tests."""
        return self.mutant_complete and self.line_complete

    @property
    def complete_modulo_equivalent(self) -> bool:
        """Complete except for UNPROVEN candidate-equivalent survivors — every killable
        mutant is killed and every line covered, but some survivors have no distinguishing
        input found (automated search never proves equivalence; only `flag` or a killing
        input resolves them). A distinct tier from both '✓ complete' and '✗ incomplete'."""
        return self.complete and self.candidate_equivalent > 0

    @property
    def bloat(self) -> int:
        """How many tests exceed the minimal cover (candidates to prune)."""
        return max(0, self.test_count - self.minimal_test_count)


def audit_suite(
    file: str,
    function: str,
    project_root: str = ".",
    *,
    progress: Callable[[int, int, float], None] | None = None,
    use_parallel: bool | None = None,
) -> SuiteAudit:
    """Assess the function's existing suite on both completeness axes.

    Runs one profile of the CURRENT suite (kill matrix + baseline line coverage),
    then classifies the survivors so a *killable* gap (a specification hole) is not
    conflated with an *equivalent* survivor (nothing to fix). Never writes.
    ``use_parallel=True`` fans that profile across worker processes (mutually exclusive
    with ``progress`` — the caller passes one or the other).
    """
    result = profile(file, function, project_root, progress=progress, use_parallel=use_parallel)
    # A test belongs to THIS function's suite only if it discharges an obligation for
    # it — kills one of its mutants OR covers one of its lines. The baseline pass runs
    # every discovered test against the original, so tests for OTHER functions appear
    # in line_coverage with an EMPTY covered-line list; counting those would inflate
    # test_count and bloat. Require a non-empty contribution.
    test_names = sorted(
        set(t for tests in result.kill_matrix.values() for t in tests)
        | {t for t, lines in result.line_coverage.items() if lines}
    )
    redundant = redundant_2axis(result.kill_matrix, result.line_coverage)
    missing = missing_lines(result.executable_lines, result.line_coverage)
    minimal = minimal_cover_2axis(result.kill_matrix, result.line_coverage)

    # Distinguish killable survivors (real gaps) from equivalent ones (nothing a
    # test can do). Advisory: if classification cannot run, fall back to "any
    # survivor is a gap" so the audit never understates the work.
    killable_gaps: tuple[str, ...]
    manual_equivalent = 0
    candidate_equivalent = 0
    unclassified = 0
    try:
        report = classify_survivors(file, function, project_root)
        killable_gaps = tuple(
            f"{v.category} [{v.mutant_id}]" + (f" — kill with {v.witness.args}" if v.witness else "")
            for v in report.killable
        )
        manual_equivalent = len(report.manual_equivalent)
        candidate_equivalent = len(report.equivalent)
        unclassified = len(report.unclassified)
        mutant_complete = not report.killable and not report.unclassified
    except Exception:  # noqa: BLE001 — classification is advisory, never fails the audit
        killable_gaps = tuple(
            f"{r.get('category', '?')} [{r.get('mutant_id', '?')}]" for r in result.value_survivor_records
        )
        mutant_complete = result.value_survived == 0

    total = result.total_mutants
    return SuiteAudit(
        function=result.function_key,
        test_count=len(test_names),
        kill_pct=round(100 * result.total_killed / total, 1) if total else 100.0,
        mutant_complete=mutant_complete,
        line_complete=not missing,
        redundant_tests=tuple(sorted(redundant)),
        failing_tests=tuple(result.failing_tests),
        killable_gaps=killable_gaps,
        missing_lines=tuple(missing),
        minimal_test_count=len(minimal),
        manual_equivalent=manual_equivalent,
        candidate_equivalent=candidate_equivalent,
        unclassified=unclassified,
    )
