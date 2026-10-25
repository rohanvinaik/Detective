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

References:
    §2.3, §9, §15.4, D5, G6, X4  docs/TEST_BASIS.md
    Q8                           docs/theory/NEGATIVE_SPECIFICATION.md §18
    Finding E                    docs/dogfood/revalidation_2026-09-06.md
"""

from __future__ import annotations

import ast
import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from Wesker.ci import walk_functions
from Wesker.monitoring import MonitoringUnavailable

from .engine import FunctionBasis, classify_survivors, function_basis, profile
from .line_flags import classify_missing_lines, load_line_flags
from .minimize import (
    _obligations_by_test,
    minimal_cover_2axis,
    missing_lines,
    redundant_2axis,
    strip_foreign_evidence,
)
from .synthesis.writer import foreign_generated_test_names

# The marker a candidate id carries when it names a pre-existing (non-generated) test. One
# spelling, because the code both TESTS for it and STRIPS it — two literals that must agree, and
# a drifted one would strip the wrong number of characters rather than fail loudly.
_LEGACY_PREFIX = "legacy:"


def _target_node(file: str, function: str, root_abs: str) -> ast.AST | None:
    """The target's AST node, or None when the file cannot be read or parsed.

    A file that will not open or parse yields None rather than raising: the line-flag oracle below
    is ADVISORY, and losing it must not take the whole audit with it."""
    full_path = file if os.path.isabs(file) else os.path.join(root_abs, file)
    try:
        with open(full_path, encoding="utf-8") as fh:
            return next((n for qn, n in walk_functions(ast.parse(fh.read())) if qn == function), None)
    except (OSError, SyntaxError):
        return None


def _origin_census(root_abs: str, test_names: list[str]) -> dict[str, int]:
    """ℋ ⊎ 𝒢 origin census (§2.3, D5): how many obligation-discharging tests came from each half.

    Attributed from the RECORDED authorship fact each test's file carries, never a path glob.
    `witness_origin_of_nodeid` owns the nodeid→file resolution (a live `file.py::name` or a
    `legacy:/abs/...::name`), so this census and the FunctionBasis witnesses agree file-for-file.
    A test whose file cannot be read is `unattributed` — "we did not measure this", kept apart from
    both halves rather than folded into either.
    """
    from .certify import witness_origin_of_nodeid

    origins = {"intent": 0, "characterization": 0, "unattributed": 0}
    for tid in test_names:
        origins[witness_origin_of_nodeid(root_abs, tid)] += 1
    return origins


class AuditAccountingError(Exception):
    """The audit's value partition did not reconcile with its classification (#55/#65).

    A genuine internal accounting inconsistency, not a fact about the user's suite. Raised as a typed
    exception so the CLI can render a clean 'please report' refusal rather than leaking a raw
    traceback — and named distinctly from a bare ``AssertionError`` so a caller can catch exactly
    this. With the single-profile reuse (#65) it should be unreachable; it remains a last resort."""


@dataclass(frozen=True)
class SuiteAudit:
    """Read-only assessment of an existing suite for one function."""

    function: str
    test_count: int
    # `kill_pct` is a DETECTION rate: total_killed / universe, where total_killed counts BOTH value
    # kills (a test pins the value) AND crash kills (a test crashes on the mutant). It is NOT the
    # value-completeness — a crash-killed mutant is "killed" here but is a value-survivor in the
    # classification below, which is why the two views legitimately differ (issue #55). `value_killed`
    # (a defaulted field below) is the value-pinned count, so the value partition is derivable.
    kill_pct: float
    # `mutant_complete` = every KILLABLE mutant killed AND no survivor left UNCLASSIFIED, i.e.
    # `not killable and not unclassified`. False when unclassified > 0 even with no killable gap,
    # because an unclassified survivor MAY be killable (honest uncertainty); the measurement is not
    # complete. (Whether that should gate CI is #50 — it does not, by default.)
    mutant_complete: bool
    line_complete: bool  # covers every executable line
    redundant_tests: tuple[str, ...]  # pointless for BOTH axes -> deletion PROPOSALS
    # fail on current code: typed `failed`, asserted or raised (#124), or named by an engine with no
    # ledger row (Wesker#17) -> WARN, never delete. An errored test is `errored_tests`, never here.
    failing_tests: tuple[str, ...]
    killable_gaps: tuple[str, ...]  # killable mutants the suite fails to kill
    missing_lines: tuple[int, ...]  # executable lines no test covers (after the line oracle)
    minimal_test_count: int  # size of the two-axis minimal cover
    manually_unreachable: int = 0  # lines closed by a manual unreachability flag (issue #9)
    contradicted_line_flags: tuple[str, ...] = ()  # flags overridden by observed execution
    manual_equivalent: int = 0  # survivors manually flagged equivalent (oracle)
    # Survivors manually flagged a FENCE (Q8) — an authored MUST-NOT the suite does not enforce. A GAP
    # (it blocks `mutant_complete`), never an equivalent; exposed so `audit --json` explains an
    # incompleteness a fence, not a killable/unclassified survivor, caused.
    authored_fence: int = 0
    candidate_equivalent: int = 0  # survivors with no distinguishing input found (UNPROVEN — flag to confirm)
    unclassified: int = 0  # survivors the search could not classify (may be killable OR equivalent)
    # How many of `unclassified` the search could not run because the function writes files AND nothing
    # in the suite detects (#105): the residual a test written under tmp_path closes, and the count
    # audit's ladder routes on. A crash-detected one is named in `write_refused_survivors`, never here.
    write_refused: int = 0
    # Every write-refused survivor as `(mutant_id, change, standing, killer)` (`write_refused_survivors`):
    # the page names the open ones to pin and the crash-detected ones with the test that detects them.
    write_refused_survivors: tuple[tuple[str, str, str, str], ...] = ()
    step_budget_divergent: int = 0  # survivors whose loop execution deterministically diverged (#80/#126)
    # Mutants that reached NO verdict in the profile — `(mutant_id, disposition)`, the same derivation
    # converge carries (`validity.unresolved_mutant_records`), so the two verbs name them alike (#126).
    unresolved_mutants: tuple[tuple[str, str], ...] = ()
    # The candidate-equivalents' actual ids. `flag` takes an id, so a count alone cannot
    # produce a runnable command: the report said "`flag <mutant_id>`" and left the reader to
    # go find one. The classifier already has them; keeping only `len()` is what made the
    # next action a placeholder instead of something to paste.
    candidate_equivalent_ids: tuple[str, ...] = ()
    # How many of `candidate_equivalent` are crash-only-distinguishable — an input DOES
    # distinguish them (the mutant raises where the original returns); what no input can do is
    # pin them with a VALUE. A breakdown, NOT a separate population: `candidate_equivalent`
    # still counts every equivalent, so the verdict string it feeds keeps its meaning. Split
    # out only so a renderer stops saying "no input distinguishes them" about a class where
    # that is false — which is what sent readers hunting for an input that cannot exist.
    crash_only_equivalent: int = 0
    # WHICH of `candidate_equivalent_ids` are crash-only (#71): an input distinguishes them, so the
    # closing action never offers `flag` (an equivalence claim) for one. Defaulted — additive.
    crash_only_ids: tuple[str, ...] = ()
    # Whether the classifier's boundary-probe pass ran over the residual (#71) — the
    # `engine.boundary_probe_gate` code the report carried, "" when it never reached the gate. The
    # closing action names an unprobed residual as possible search budget instead of a frontier.
    boundary_probe: str = ""
    # Mutants a test pins by VALUE (assertion kills). Exposed so the whole universe partitions,
    # derivably and provably: `total_mutants = value_killed + len(killable_gaps) + candidate_equivalent
    # + manual_equivalent + authored_fence + unclassified` (asserted in `audit_suite` via
    # `audit_partition_sums`).
    # `crash_only_equivalent` is a SUB-COUNT of `candidate_equivalent`, not a separate term — a JSON
    # consumer must not add the two. `kill_pct` counts value AND crash kills, so it is `>= value_killed
    # / total` and reconciles with this partition only once the crash overlap is named (issue #55).
    value_killed: int = 0
    total_mutants: int = 0
    # Which evidence the line ledger rested on (#59), the same four-state basis converge reports:
    # `admissible` (baseline-green view), `observed` (an engine too old to filter — named, not
    # silently reverted, per #60), `none_admissible` (the engine filtered and nothing qualified),
    # `malformed` (a broken engine view). `line_complete` on an `observed` basis is the weaker
    # claim, and a certificate must say so rather than imply the admissible one.
    line_basis: str = "observed"
    # The ℋ ⊎ 𝒢 origin census over the tests that discharge an obligation (§2.3, D5). Each is
    # attributed from a RECORDED authorship fact (the file's Detective header), never a path glob:
    #   intent_tests         ℋ — hand-written, or a generated file a human edited: INTENT evidence
    #   characterized_tests  𝒢 — Detective-generated and unedited: CHARACTERIZATION (may pin a bug)
    #   unattributed_tests   no recorded fact (unreadable) — counted as neither, never silently either
    # These sum to `test_count`. A suite that is 30/30 pinned but 0 intent-grounded is fully
    # characterized and un-reviewed — the doctrine "generated tests are a characterization, not a
    # review" made visible instead of true only in prose.
    intent_tests: int = 0
    characterized_tests: int = 0
    unattributed_tests: int = 0
    # The FunctionBasis this audit earned (#X4 tail, §9) — the ONE object diagnose/audit both carry.
    # Attached with the REAL candidate-equivalent count from THIS audit's classification, so its
    # `action` (complete | gap | unresolved) is accurate where the profile-time basis (which cannot
    # classify, so reads 0 equivalents) would wrongly say `gap` for an all-equivalent survivor set.
    # None only on an older result or a direct construction. `asdict` carries it to `audit --json`.
    function_basis: FunctionBasis | None = None
    # Why the survivor search could not RUN over the target (Finding E), carried from the classify
    # report so audit's next action names the SAME escape converge does — the module would not import
    # (`load_failed` + the exception in `note`), or no synthesized input reached the function
    # (`inputs_expressible`: False = a param with no literal form; None = unknown, every candidate
    # raised -> a real sample is needed). Defaulted, so a direct construction / older result is
    # unchanged and `asdict` carries them to `audit --json`.
    load_failed: bool = False
    inputs_expressible: bool | None = None
    note: str = ""
    # Preserve the engine's refusal through the report and its closing action.
    cut_reasons: tuple[str, ...] = ()
    # Per not-entered cause, its mutants and what still holds the original (`validity.not_entered`,
    # #77) — the cause code alone cannot say where a captured or aliased reference lives.
    not_entered: tuple[dict, ...] = ()
    # Tests whose baseline is typed `error` — setup or teardown failed, so they never ran to a verdict
    # of their own (Wesker#17). Named apart from `failing_tests`: not a wrong expectation, never gated.
    errored_tests: tuple[str, ...] = ()
    # Each of `missing_lines` with WHY it has no admissible coverage (`missing_line_standing`, #139):
    # `(line, standing)`. A line only a failing test runs is unproven, never "uncovered".
    missing_line_standings: tuple[tuple[int, str], ...] = ()

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


def audit_check_failed(killable_gaps: int, missing_lines: int, failing_tests: int, fence: int = 0) -> bool:
    """Whether ``detective audit --check`` should FAIL the CI ratchet on a SPECIFICATION gap (#35, #50, Q8).

    True ONLY for a real, actionable claim about the USER's code or suite: a KILLABLE mutant it does
    not kill (a spec hole), a reachable line no test covers, a currently-FAILING test, or an authored
    ``fence`` — a MUST-NOT the human declared that no test enforces (Q8). The fence is a spec gap for
    exactly the reason the others are: a definite, actionable claim about the suite ("you said this
    output is forbidden and nothing catches it"), resolved by writing the test, not by the tool
    measuring longer. This is the default gate; it must fail only when the code/contract got WORSE,
    never when Detective's own measurement got shorter. An UNCLASSIFIED survivor is a MEASUREMENT limit
    — the equivalence search could not run on it, the tool's uncertainty, not the developer's
    regression — so it is EXCLUDED here (issue #50, the over-gating direction; #35 fixed the
    under-gating one) and handled by :func:`audit_measurement_incomplete`, fatal only under
    ``--check-strict``. Candidate-equivalent and crash-only survivors are likewise excluded:
    unproven-equivalent, resolved by ``flag`` or a killing input, never a spec hole a green-field edit
    introduced. A ratchet that reddens on tool-internal conditions gets deleted from the pipeline,
    taking the real gate with it.
    """
    return bool(killable_gaps) or bool(missing_lines) or bool(failing_tests) or bool(fence)


def audit_measurement_incomplete(unclassified: int, errored: int = 0, unresolved: int = 0) -> bool:
    """Whether the audit's MEASUREMENT was incomplete — honest tool-side uncertainty, not a code gap.

    An UNCLASSIFIED survivor (issue #50) is one the equivalence search could not evaluate — it may be
    killable OR equivalent; Detective simply could not decide. That is the same class as a budget CUT:
    a limit on the measurement, not a finding about the suite. It is surfaced ALWAYS (visible), but is
    fatal only under ``--check-strict`` — so the default ``--check`` stays a claim about the code alone,
    and a green suite that has not changed can never be reddened because a search got shorter.

    An ERRORED test (Wesker#17, `function_errored_tests`) is the same class from the other side: it
    reaches this function, but its setup or teardown failed, so it never ran to a verdict and its
    evidence is absent rather than clean. Not a code gap, so never a ``1``. But "could not measure"
    must not pass the strict gate as "measured no gap" (COMMUNICATING_DETERMINISM §3.1).

    An UNRESOLVED mutant (#80) is the third: one that reached no verdict for a cause the reader CAN
    repair. ``unresolved`` counts only those (`unresolved_gate_standing`); a step-budget divergence or a
    wall bound is named in the gate's payload but never fails it. The three causes share the strict
    gate's ``2``; the gate's ``--json`` payload names which (``unmeasured``)."""
    return unclassified > 0 or errored > 0 or unresolved > 0


def unresolved_gate_standing(reason: str) -> str:
    """Whether a mutant that reached no verdict fails ``--check-strict`` (#80, pure — pinned).

    The founder's ruling (2026-10-25): the strict gate fails only on a cause the reader can fix. A
    measurement that withheld a verdict is never silently clean. The gate's ``--json`` lists every
    unresolved mutant with this standing, so a pipeline can choose. But a ratchet that reddens for
    good, on a condition no edit can change, gets deleted from the pipeline and takes the real gate
    with it (`audit_check_failed`). Measured: nearly every ``while`` loop has a mutant like
    ``while n > 0 -> while True``, which the step budget stops deterministically.

      "repairable"    ``write_outside_authority``: the test's write was prevented. The page names the
                      repair (keep the test's writes inside its temporary directory). Fails the gate.
      "budget_floor"  ``diverged``: the step budget stopped it, deterministically and for good. "No input
                      or flag applies". Named, never gating.
      "machine_bound" ``undetermined``: a wall-clock bound fired, so whether it does depends on the
                      runner's speed until Wesker#27's calibrated liveness bound lands. Named, never gating.
      "unknown"       a reason this version does not know: it cannot be called a floor, so it fails the
                      gate as could-not-measure.
    """
    if reason == "write_outside_authority":
        return "repairable"
    if reason == "diverged":
        return "budget_floor"
    if reason == "undetermined":
        return "machine_bound"
    return "unknown"


def audit_gate_exit(spec_gap: bool, measurement_incomplete: bool, strict: bool) -> int:
    """The ``detective audit --check`` exit code from the two partitioned signals (issue #50, pinned).

    A SPECIFICATION gap always fails the ratchet with ``1`` — the code got worse. A MEASUREMENT-incomplete
    run fails only under ``--check-strict``, and with a DISTINCT ``2`` so CI can branch a shorter search
    from a real regression without parsing text. Otherwise ``0``. Spec gaps OUTRANK measurement limits: a
    run with both is a ``1`` (the actionable one — fix the code), never masked as a mere measurement note."""
    if spec_gap:
        return 1
    if measurement_incomplete and strict:
        return 2
    return 0


def mutation_estimate_seconds(mutant_count: int, per_mutant_ms: float | None) -> float | None:
    """The tier-2 mutation-cost estimate for ``audit --plan`` (issue #52, pure — pinned): the mutant
    universe size times this machine's OWN recent per-mutant time (from telemetry), in seconds — or
    None when there is no prior rate to ground it (a first-ever run, honestly "no estimate" rather than
    a fabricated number). A MEASURED schedule, never a promise; a negative count is treated as no
    estimate rather than a nonsensical negative time."""
    if per_mutant_ms is None or mutant_count < 0:
        return None
    return mutant_count * per_mutant_ms / 1000.0


def audit_partition_sums(
    total: int,
    value_killed: int,
    killable: int,
    candidate_equivalent: int,
    manual: int,
    fence: int,
    unclassified: int,
    diverged: int = 0,
) -> bool:
    """Whether every mutant lands in EXACTLY one terminal value-bucket (issue #55, pure — pinned).

    The universe partitions by VALUE specification, mutually exclusive and exhaustive:
    ``total == value_killed + killable + candidate_equivalent + manual + fence + unclassified + diverged``.
    Each mutant is value-pinned, a killable-unkilled gap, value-equivalent (candidate), manually-flagged
    equivalent, an authored FENCE (a must-not the suite does not enforce — Q8), unclassifiable, or
    step-budget-divergent (#80/#126). When this is False the headline % cannot be reconstructed from
    the classification beneath it — a Detective ACCOUNTING bug, not a fact about the suite — so
    :func:`audit_suite` raises rather than print a number that does not reconcile.
    ``crash_only_equivalent`` is a sub-count of ``candidate_equivalent`` and never a term here;
    ``kill_pct`` counts crash kills too and is a different (detection) lens that does not enter this
    partition."""
    return total == value_killed + killable + candidate_equivalent + manual + fence + unclassified + diverged


def _gap_desc(verdict: Any, expressible: bool) -> str:
    """One killable gap: the mutant, and the input to kill it with ONLY if that input can be
    written down.

    `witness.args` is repr'd. For a domain object that renders
    `<billing.Account object at 0x105fe6ad0>` — a memory address, presented as the input to
    kill with. It cannot be typed, it changes every run, and an LLM reading it does not skip
    it: it passes the string, or invents a constructor from it, or treats the address as
    meaningful. Handing a caller a pointer and calling it an input is worse than saying
    nothing, because nothing is at least not actionable.

    When the witness came from CAPTURE (a real object out of the user's own tests) the honest
    rendering is the mutant alone. The input already exists in the suite; the way to reach the
    rest is another test, which is what the next action says.
    """
    if verdict.witness and expressible:
        # `literal_source`, not the tuple's repr: a NaN in the witness prints `float('nan')`, a
        # spelling `--input` accepts and a test can run (#78).
        from .equivalence import literal_source

        kill_with = literal_source(tuple(verdict.witness.args))
        return f"{verdict.category} [{verdict.mutant_id}] — kill with {kill_with}"
    return f"{verdict.category} [{verdict.mutant_id}]"


def function_test_suite(kill_matrix: dict[str, list[str]], line_coverage: dict[str, list[int]]) -> set[str]:
    """The tests that are THIS function's business (#114, pure — pinned): each killed one of its
    mutants or executed one of its lines.

    The baseline runs every discovered test against the original, so tests for OTHER functions appear
    in ``line_coverage`` with an EMPTY covered-line list; counting those would inflate a one-function
    report with the whole collection. A non-empty contribution is required. ``line_coverage`` is the
    RAW observed view, never the admissible one: a test that fails on current code is excluded from
    the admissible ledger, and the scoping below exists precisely to find it.

    Shared by `audit_suite` and `converge`, so the two verbs cannot scope one report differently.
    """
    return {t for tests in kill_matrix.values() for t in tests} | {
        t for t, lines in line_coverage.items() if lines
    }


def baseline_failure_disposition(named_failing: bool, outcome: str) -> str:
    """What ONE test's baseline says about this function's floor: failing, errored, or neither
    (#124, Wesker#17, pure — pinned).

    The engine's `failing_tests` is decided from a run code that cannot see pytest's PHASE, and it
    lists only ASSERTION failures. Two readings were wrong with it alone. A fixture whose setup
    asserts (pytest's ERROR, typed ``error`` in the very same result's ledger) was named and printed
    as a failing test, and asked "is the TEST's expectation wrong?" when it never reached one
    (Wesker#17). A test whose call RAISED, which pytest itself reports ``failed``, was never named, so
    audit asked for a sample over three failing tests and converge certified over them (#124). The
    typed outcome is the finer reading, and this one table consumes it for both verbs:

      "failing"      typed ``failed``, asserted or raised, named or not (#124); or ``unrecorded`` and
                     named, an engine with no ledger row, where its word is all there is
      "errored"      typed ``error``: setup or teardown failed, so the test never ran to a verdict of its
                     own. Never a wrong expectation: the repair is the fixture, and it is named apart
      "not_failing"  a pass, a skip or an expected failure, whatever the engine named; and a test with
                     no typed outcome that the engine did not name
    """
    if outcome == "error":
        return "errored"
    if outcome == "failed" or (named_failing and outcome == "unrecorded"):
        return "failing"
    return "not_failing"


def function_failing_tests(
    failing_tests: list[str],
    kill_matrix: dict[str, list[str]],
    line_coverage: dict[str, list[int]],
    typed_outcomes: dict[str, str] | None = None,
) -> tuple[str, ...]:
    """The tests that fail on current code AND are this function's business (#114, pure — pinned).

    ``failing_tests`` is the baseline's REPO-WIDE list, in the engine's order. A test that fails
    BECAUSE of this function executed its lines (or killed one of its mutants), so it is in
    `function_test_suite`; one that fails elsewhere — an unrelated test, or a routed test that fails
    before it ever reaches the function — touched none of them and is not this function's floor.
    Order is preserved, so the first name is the one a report shows first: the engine's names, then
    the typed failures it did not name.

    Each candidate is read by `baseline_failure_disposition` over ``typed_outcomes`` (the engine's typed
    baseline outcome per test, `baseline_typed_outcomes`); a test the ledger does not carry reads
    ``unrecorded``. An engine with no ledger yields ``{}``, so its own names stand, as before.

    One derivation, two consumers: audit's ``FAILING NOW`` and converge's floor gate. Converge printed
    ✓ COMPLETE over a function whose only routed test failed (#114) because it never consulted this.
    """
    suite = function_test_suite(kill_matrix, line_coverage)
    typed = typed_outcomes or {}
    named = set(failing_tests)
    raised = [t for t, outcome in typed.items() if outcome == "failed"]
    return tuple(
        t
        for t in dict.fromkeys([*failing_tests, *raised])
        if t in suite and baseline_failure_disposition(t in named, typed.get(t, "unrecorded")) == "failing"
    )


def function_errored_tests(
    kill_matrix: dict[str, list[str]],
    line_coverage: dict[str, list[int]],
    typed_outcomes: dict[str, str] | None = None,
) -> tuple[str, ...]:
    """The tests that are this function's business and ERRORED on current code (Wesker#17, pure — pinned).

    The sibling of `function_failing_tests`, over the same suite and the same typed reading
    (`baseline_failure_disposition`): setup or teardown failed, so the test never ran to a verdict.
    It is no wrong expectation, and no evidence either way. Its tests are absent from the measurement
    rather than measured clean, so a renderer names them apart, and the strict gate counts them as an
    incomplete measurement (`audit_measurement_incomplete`). Sorted, because no engine order exists
    for a test it did not name.
    """
    suite = function_test_suite(kill_matrix, line_coverage)
    return tuple(
        sorted(
            t
            for t, outcome in (typed_outcomes or {}).items()
            if t in suite and baseline_failure_disposition(False, outcome) == "errored"
        )
    )


def missing_line_standing(
    line: int,
    line_coverage: dict[str, list[int]],
    failing_tests: list[str],
    errored_tests: list[str],
) -> str:
    """Why an executable line has no admissible coverage, read off what its observations show (#139,
    pure — pinned).

    `missing_lines` is computed over the ADMISSIBLE view (#59): only a baseline-green, contained,
    non-truncated observation may discharge a line. A line in it may therefore still have RUN, and
    "uncovered" / "no test covers" is a claim about EXECUTION, false for every such line. #114's
    `scale(2) == 4` executes line 2: the page printed `✗ uncovered 1 line(s): 2`, and the report offered
    an `--input` to reach it. Four states, four remedies (COMMUNICATING_DETERMINISM §3):

      "run_by_failing"    a test that fails on current code executes it. Fixing that test or the code
                          covers it; no input applies, and converge writes nothing over the floor.
      "run_by_errored"    only a test whose setup or teardown errored executes it (Wesker#17). Repairing
                          the fixture covers it, and so does a test converge writes from an input.
      "run_inadmissibly"  a test executes it, but only in an observation the ledger may not rest on (a
                          cut, uncontained or replayed trace): a fresh observation can cover it.
      "unexecuted"        no observed test executes it: the remedy is an input, or a test that reaches it.

    ``line_coverage`` is the OBSERVED union per test (`result.line_coverage`); ``failing_tests`` and
    ``errored_tests`` are `function_failing_tests` and `function_errored_tests`. A failing runner
    outranks an errored one, as the floor outranks a fixture in both ladders.
    """
    runners = {test for test, lines in line_coverage.items() if line in lines}
    if runners.intersection(failing_tests):
        return "run_by_failing"
    if runners.intersection(errored_tests):
        return "run_by_errored"
    if runners:
        return "run_inadmissibly"
    return "unexecuted"


def write_refused_standing(killed_by: str) -> str:
    """Whether the suite already detects a survivor whose search was refused because the function writes
    files (#105, pure — pinned).

    The search that would sort such a survivor into crash-only, killable or equivalent is exactly the one
    refused for a writer, so #105's first route handed EVERY one back as "write a test". That loops:
    measured on #105's own fixture (2026-10-25), a test written to the letter of that advice closed none
    of the six, was then called redundant and `--remove`d, and the advice returned. The suite's own kill
    is evidence that needs no speculative run:

      "crash_detected"  the suite kills it, by a crash: detected, though no value assertion pins it, and
                        whether one could was not searched. Named, never a hand-back that keeps returning.
      "open"            no test in the suite fails under it (a timeout reads `undetermined` in Wesker's own
                        disposition, never a detection): a test written to fail under its change closes it.
    """
    return "crash_detected" if killed_by == "crash" else "open"


def write_refused_survivors(
    records: list[list[str]],
    kill_matrix: dict[str, list[str]],
) -> tuple[tuple[str, str, str, str], ...]:
    """Each write-refused survivor as ``(mutant_id, change, standing, killer)`` (#105, pure — pinned).

    ``records`` are `SurvivorReport.write_refused_records` (``mutant_id, mutant, change, killed_by``),
    and ``kill_matrix`` the profile's map from a mutant's description to the tests that kill it.
    ``standing`` is `write_refused_standing`; ``killer`` names a test that kills a ``crash_detected``
    one ("" for an open one), so the page can say WHICH test detects it: the first in sorted order where
    the profile recorded several. A profile in first-killer mode records one, the first to kill in its
    own run order, so audit and converge may name different tests; each detects it. One derivation,
    read by audit's page, converge's page and both ladders: only an ``open`` one is a residual a
    written test can close.
    """
    out: list[tuple[str, str, str, str]] = []
    for mutant_id, mutant, change, killed_by in records:
        standing = write_refused_standing(killed_by)
        killers = sorted(kill_matrix.get(mutant, [])) if standing == "crash_detected" else []
        out.append((mutant_id, change, standing, killers[0] if killers else ""))
    return tuple(out)


def baseline_typed_outcomes(result: Any) -> dict[str, str]:
    """The engine's typed baseline outcome per test id (#124), read off its trace ledger.

    Each `trace_evidence` row carries pytest's own verdict for one traced test on the unmutated code
    (``passed`` / ``failed`` / ``skipped`` / ``xfailed`` / ``error``). A row with no id names nothing,
    and one the engine did not type (``unrecorded``: hand-built, or cached before outcomes were typed)
    is left out rather than guessed. A REPLAYED row is kept: it may never prove (#20), but the floor is
    a refusal, and the engine's assertion list reaches `function_failing_tests` through the same cache —
    dropping replayed outcomes would restore the raise/assert asymmetry on every warm run. An engine
    with no ledger yields ``{}``: the assertion-only derivation, as before.
    """
    outcomes: dict[str, str] = {}
    for row in getattr(result, "trace_evidence", None) or ():
        test_id = str(getattr(row, "test_id", "") or "")
        outcome = str(getattr(row, "baseline_outcome", "") or "")
        if test_id and outcome and outcome != "unrecorded":
            outcomes[test_id] = outcome
    return outcomes


def audit_suite(
    file: str,
    function: str,
    project_root: str = ".",
    *,
    progress: Callable[[int, int, float], None] | None = None,
    trace_progress: Callable[[int, int, float], None] | None = None,
    two_sign: bool = False,
) -> SuiteAudit:
    """Assess the function's existing suite on both completeness axes.

    Runs one profile of the CURRENT suite (kill matrix + baseline line coverage),
    then classifies the survivors so a *killable* gap (a specification hole) is not
    conflated with an *equivalent* survivor (nothing to fix). Never writes.

    ``trace_progress`` reports the BASELINE-TRACE phase, which dominates a large suite's wall clock
    and, unreported, made audit look hung for minutes before the first byte (issue #53).
    """
    # two_sign (§16 CI-gate view of the negative sign): under the two-sign policy the profile adds the
    # μ⁻ OUTPUT perturbations, so a surviving negative DOF surfaces in killable_gaps and — via the
    # unchanged audit_check_failed — makes `audit --two-sign --check` fail on an ENGINE-found unpinned
    # output invariant, extending Q8's authored-fence gate to the perturbations the engine finds.
    result = profile(
        file,
        function,
        project_root,
        progress=progress,
        trace_progress=trace_progress,
        two_sign=two_sign,
        isolated=True,
        use_cache=False,
    )
    # A test belongs to THIS function's suite only if it discharges an obligation for
    # it — kills one of its mutants OR covers one of its lines (`function_test_suite`, the one
    # derivation converge's floor gate shares).
    suite = function_test_suite(result.kill_matrix, result.line_coverage)
    test_names = sorted(suite)
    # ℋ ⊎ 𝒢 origin census (§2.3, D5): attribute each obligation-discharging test to its half from the
    # RECORDED authorship fact its file carries, never a path glob. The nodeid's path segment resolves
    # the file; `witness_origin_of` reads its Detective header. A test whose file cannot be read is
    # unattributed — "we did not measure this", kept apart from both halves.
    _origins = _origin_census(os.path.abspath(project_root), test_names)
    # Issue #7: deletion proposals and the minimal cover count only DURABLE evidence —
    # user tests plus this target's own generated file. A sibling target's generated
    # tests may kill this function's mutants today, but that file is rewritten wholesale
    # on the sibling's next converge; proposing a deletion on its support would let this
    # function's certificate silently regress. (``suite``/``test_names`` above stay
    # whole-evidence: they describe what exercises the function right now.)
    # The line ledger rests on the ADMISSIBLE view, never the raw observed union (#59): audit judged
    # line completeness from `result.line_coverage`, so a baseline-FAILING test's coverage closed the
    # ledger and audit read line-complete on evidence that proves nothing. The SAME helper converge
    # uses, so the two verdicts cannot diverge.
    from .converge import admissible_proof_coverage

    proof_coverage, line_basis = admissible_proof_coverage(result)
    # The minimize basis is admissible AND foreign-stripped (the G6 fix, §15.4): strip foreign tests
    # from the ADMISSIBLE ledger, NOT the raw union. Before, `redundant`/`minimal` rested on the raw
    # observed coverage while converge minimized on the admissible one — the two proposed different
    # "delete this test" sets for the same suite, the #59 drift one axis over. Now audit minimizes on
    # exactly the coverage a certificate may rest on (admissible, like converge), with foreign tests
    # removed (#7, so it never proposes deleting a sibling's rewritten-wholesale generated file).
    own_matrix, own_lines = strip_foreign_evidence(
        result.kill_matrix,
        proof_coverage,
        foreign_generated_test_names(os.path.abspath(project_root), result.function_key),
    )
    redundant = redundant_2axis(own_matrix, own_lines)
    missing = missing_lines(result.executable_lines, proof_coverage)
    minimal = minimal_cover_2axis(own_matrix, own_lines)
    # Issue #9: the line-unreachability oracle. A missing line whose statement a user
    # flagged unreachable closes on the LINE ledger only — reported as "modulo", never
    # silently as covered — and a flag contradicted by observed execution is surfaced
    # as overridden, since execution is proof of reachability. Mutation-completeness
    # never reads this store.
    manually_unreachable: list[int] = []
    contradicted_flags: tuple[str, ...] = ()
    node: ast.AST | None = None  # bound for the FunctionBasis below even when the flag oracle skips
    if missing or load_line_flags(os.path.abspath(project_root)):
        root_abs = os.path.abspath(project_root)
        node = _target_node(file, function, root_abs)
        if node is not None:
            # The admissible view, for the SAME reason as the gap above: a flag "contradicted by
            # observed execution" must be contradicted by execution that COUNTS, or a
            # baseline-failing test could override a human's unreachability judgement (#59).
            covered = {ln for lines in proof_coverage.values() for ln in lines}
            missing, manually_unreachable, contradicted = classify_missing_lines(
                root_abs, result.function_key, node, missing, covered
            )
            contradicted_flags = tuple(f"{f.source} (line {f.line})" for f in contradicted)

    # Distinguish killable survivors (real gaps) from equivalent ones (nothing a
    # test can do). Advisory: if classification cannot run, fall back to "any
    # survivor is a gap" so the audit never understates the work.
    killable_gaps: tuple[str, ...]
    manual_equivalent = 0
    fence = 0  # authored must-nots the suite does not enforce (Q8) — a gap, not an equivalent
    candidate_equivalent = 0
    candidate_equivalent_ids: tuple[str, ...] = ()
    crash_only_equivalent = 0
    crash_only_ids: tuple[str, ...] = ()
    boundary_probe = ""
    unclassified = 0
    write_refused = 0
    write_refused_named: tuple[tuple[str, str, str, str], ...] = ()
    classified = False
    # The measurement-block signals (Finding E), carried onto the audit so its next action names the
    # SAME escape converge does via `measurement_block_route`. Defaulted here so the advisory
    # except-fallback below leaves them at "measurement ran, nothing blocked".
    _load_failed = False
    # The capture harvest's routing failure (#91) — classification's fact, like `_load_failed`.
    _harvest_routing_failed = False
    _report_expressible: bool | None = None
    _report_note = ""
    try:
        # Reuse THIS profile (#65): classify the survivors of the exact measurement whose counts the
        # partition below checks, so the two can never come from two divergent profiles and crash the
        # assertion. `classify_survivors` re-profiles only when no compatible result is handed to it.
        # Under the SAME policy the profile used (#92): classification regenerates the content-addressed
        # mutants it witness-searches, and a one-sign regeneration has no OUTPUT (μ⁻) ids — so under
        # `--two-sign` every surviving negative DOF read "un-buildable" and fell to `unclassified`
        # instead of surfacing in killable_gaps, which is what the two-sign audit exists to gate on.
        report = classify_survivors(file, function, project_root, profile_result=result, two_sign=two_sign)
        # Defensive reads (#60): a report without the Finding-E fields (an older SurvivorReport, a test
        # stub) must not crash the classification into the advisory except-fallback below — which would
        # silently zero candidate_equivalent and mis-read a fully-classified suite as a gap.
        _load_failed = bool(getattr(report, "load_failed", False))
        _harvest_routing_failed = bool(getattr(report, "routing_error", ""))
        _report_expressible = getattr(report, "inputs_expressible", None)
        _report_note = getattr(report, "note", "") or ""
        # Whether a killable gap may name the input to kill it with — see `_gap_desc`.
        expressible = bool(report.inputs_expressible)
        killable_gaps = tuple(_gap_desc(v, expressible) for v in report.killable)
        manual_equivalent = len(report.manual_equivalent)
        fence = len(report.authored_fence)
        candidate_equivalent = len(report.equivalent)
        candidate_equivalent_ids = tuple(v.mutant_id for v in report.equivalent)
        crash_only_equivalent = sum(1 for v in report.equivalent if v.crash_only)
        crash_only_ids = tuple(v.mutant_id for v in report.equivalent if v.crash_only)
        boundary_probe = str(getattr(report, "boundary_probe", "") or "")
        unclassified = len(report.unclassified)
        write_refused_named = write_refused_survivors(
            [list(r) for r in getattr(report, "write_refused_records", ())], result.kill_matrix
        )
        write_refused = sum(1 for s in write_refused_named if s[2] == "open")
        step_budget_divergent = len(getattr(report, "step_budget_divergent", ()))
        # An authored fence is an UNENFORCED must-not (Q8) — a gap like killable/unclassified, so it
        # blocks mutant-completeness exactly as they do; never treated as a discharged equivalent.
        # Deterministic step budget divergence likewise blocks completeness (#80).
        mutant_complete = (
            not report.killable
            and not report.unclassified
            and not report.authored_fence
            and not step_budget_divergent
        )
        classified = True
    except MonitoringUnavailable:
        # An unobservable execution cannot authorize completeness or a removal proposal.
        raise
    # BLE001: ordinary classification failures retain the conservative survivor fallback
    except Exception:  # noqa: BLE001
        killable_gaps = tuple(
            f"{r.get('category', '?')} [{r.get('mutant_id', '?')}]" for r in result.value_survivor_records
        )
        mutant_complete = result.value_survived == 0
        step_budget_divergent = 0

    total = result.total_mutants
    # REFUSE rather than report a headline that cannot be reconstructed from the classification (#55).
    # The value partition must be exact; a mismatch is a Detective accounting bug, surfaced loudly here
    # instead of shipped as a wrong percentage. Only when classification actually ran (the advisory
    # fallback above does not produce the terminal buckets).
    if classified and not audit_partition_sums(
        total,
        result.value_killed,
        len(killable_gaps),
        candidate_equivalent,
        manual_equivalent,
        fence,
        unclassified,
        step_budget_divergent,
    ):
        # With the single-profile reuse above this cannot arise from two divergent measurements — it
        # is now a genuine defensive last resort for an internal accounting inconsistency. Typed (not a
        # bare AssertionError) so the CLI renders a clean "please report" refusal instead of leaking a
        # raw Python traceback to a user (#65).
        raise AuditAccountingError(
            f"audit partition does not sum for {result.function_key}: total={total} "
            f"value_killed={result.value_killed} killable={len(killable_gaps)} "
            f"candidate_equivalent={candidate_equivalent} manual={manual_equivalent} "
            f"fence={fence} unclassified={unclassified} diverged={step_budget_divergent}"
        )
    # The FunctionBasis this audit earned (#X4 tail, review-reconciled): the undischargeable residue
    # U_t is every VALUE-undischargeable survivor — candidate-equivalent, crash-only, AND manual-
    # equivalent — so the basis reads complete-modulo exactly where converge's `functionally_complete`
    # does (open = killable + unclassified). `candidate_equivalent` here is the UNION (true-equivalent
    # + crash-only, audit.py:341); adding `manual_equivalent` completes the modulo set. The earlier
    # crash-only SUBTRACTION made a crash-only-only run read `gap` where converge reads complete-modulo
    # — the review's crash-only inconsistency, ruled to modulo. Same `node` the line oracle used, so
    # the basis's line U_t agrees with `manually_unreachable`. 0 when classification did not run.
    from .validity import normalize_validity, unresolved_mutant_records

    # `_load_failed` rides INTO the validity rather than being ANDed on top of it. The local
    # conjunction below was correct for audit and invisible to everyone else: converge read
    # `admits_certificate` on the same measurement and got True, so one run was ungateable here
    # and clean there. Carried on the object, both surfaces read the one refusal, and it arrives
    # with a typed reason (`target_load_failed`) instead of an anonymous False.
    validity = normalize_validity(result, load_failed=_load_failed, routing_failed=_harvest_routing_failed)
    mutant_complete = mutant_complete and validity.admits_certificate
    # Each test read by its TYPED baseline outcome (#124, Wesker#17), once, for both lists below.
    _typed = baseline_typed_outcomes(result)
    _failing = function_failing_tests(
        list(result.failing_tests), result.kill_matrix, result.line_coverage, _typed
    )
    _errored = function_errored_tests(result.kill_matrix, result.line_coverage, _typed)
    _basis = function_basis(
        result,
        validity,
        os.path.abspath(project_root),
        node,
        candidate_equivalent=candidate_equivalent + manual_equivalent,
    )
    return SuiteAudit(
        function=result.function_key,
        test_count=len(test_names),
        kill_pct=round(100 * result.total_killed / total, 1) if total else 100.0,
        mutant_complete=mutant_complete,
        line_complete=not missing and validity.admits_certificate,
        line_basis=line_basis,
        redundant_tests=tuple(sorted(redundant)),
        # Scoped by `suite` for the SAME reason test_names is, and it must stay that way:
        # `result.failing_tests` is the baseline's REPO-WIDE list (the baseline runs every
        # discovered test, for every function), so passing it through raw put thousands of
        # unrelated names into a report whose whole contract is ONE function. Measured on
        # Regenesis: 2153 names, 2126 of them for other functions, 56KB on one line — which
        # both buried the real finding and exceeded an MCP client's token ceiling, so `audit`
        # returned nothing usable at all. It also read as "your suite is broken" when the
        # suite was 2154-green: the names came from a live-session baseline whose re-runs
        # poison each other (pytest_runner._reset_item leaves fixture _finalizers uncleared,
        # so setup eventually dies on pytest's own `assert not self._finalizers` and the
        # wrapper relabels that setup failure as an AssertionError). Scoping does not fix
        # THAT — it bounds the blast radius to this function's own tests, where a false
        # positive is visible and investigable instead of 2126 names of unrelated noise.
        # Scoping cannot hide a genuine one: a test that fails BECAUSE of this function
        # executed its lines, so it is in `suite` via line_coverage; one that fails elsewhere
        # touches none of them and is not this report's business. `function_failing_tests` is
        # the one derivation; converge's floor gate consumes the same (#114), typed outcomes
        # included, so a test whose call raised is named as well as one whose assertion failed (#124).
        # Its errored sibling reads the same typed outcomes over the same suite (Wesker#17): a test
        # whose setup or teardown failed never ran to a verdict, and is named apart.
        failing_tests=_failing,
        errored_tests=_errored,
        killable_gaps=killable_gaps,
        missing_lines=tuple(missing),
        missing_line_standings=tuple(
            (ln, missing_line_standing(ln, result.line_coverage, list(_failing), list(_errored)))
            for ln in missing
        ),
        manually_unreachable=len(manually_unreachable),
        contradicted_line_flags=contradicted_flags,
        minimal_test_count=len(minimal),
        manual_equivalent=manual_equivalent,
        authored_fence=fence,
        candidate_equivalent=candidate_equivalent,
        candidate_equivalent_ids=candidate_equivalent_ids,
        crash_only_equivalent=crash_only_equivalent,
        crash_only_ids=crash_only_ids,
        boundary_probe=boundary_probe,
        unclassified=unclassified,
        write_refused=write_refused,
        write_refused_survivors=write_refused_named,
        step_budget_divergent=step_budget_divergent,
        unresolved_mutants=unresolved_mutant_records(getattr(result, "unscored_records", None) or ()),
        value_killed=result.value_killed,
        total_mutants=total,
        intent_tests=_origins["intent"],
        characterized_tests=_origins["characterization"],
        unattributed_tests=_origins["unattributed"],
        function_basis=_basis,
        load_failed=_load_failed,
        inputs_expressible=_report_expressible,
        note=_report_note,
        cut_reasons=validity.cut_reasons,
        not_entered=validity.not_entered,
    )


def _candidate_test_files(candidates) -> set[str]:
    """The distinct test FILES a set of candidate test ids point at (Cor. 10.6). A candidate id is a
    nodeid — ``[legacy:]path::name[::case]`` — so the file is the segment before the first ``::`` with any
    ``legacy:`` routing prefix stripped. These files are force-loaded into a neighbor's profile so a
    cross-file bridge test is not hidden by Detective's import-reachability discovery."""
    files: set[str] = set()
    for cid in candidates:
        head = cid.split("::", 1)[0]
        if head.startswith(_LEGACY_PREFIX):
            head = head[len(_LEGACY_PREFIX) :]
        if head:
            files.add(head)
    return files


def _is_test_file(rel_path: str) -> bool:
    """A pytest test file by default convention (``test_*.py`` / ``*_test.py``). Cor. 10.6 profiles a
    call-graph neighbor AS A TARGET, so a test-function neighbor (a test that CALLS the target — hence a
    caller in the graph) must be filtered out: profiling a test function as a target is meaningless."""
    base = os.path.basename(rel_path)
    return base.startswith("test_") or base.endswith("_test.py")


def _test_identity(test_id: str, root: str) -> str:
    """One test's identity across spellings: the nodeid, the legacy form, absolute or root-relative."""
    path, separator, case = test_id.removeprefix(_LEGACY_PREFIX).partition("::")
    return os.path.realpath(os.path.join(root, path)) + separator + case


def removal_measurement_state(admissible: bool, needed_count: int) -> str:
    """Keep unknown removal evidence distinct from measured need (#112, pure — pinned)."""
    if not admissible:
        return "unverified"
    if needed_count > 0:
        return "needed"
    return "redundant"


@dataclass(frozen=True)
class RemovalEvidence:
    """One function's removal evidence; an empty needed set alone proves nothing."""

    state: str
    needed: frozenset[str] = frozenset()
    cut_reasons: tuple[str, ...] = ()


def _removal_needs(result, candidates: set[str], root: str) -> RemovalEvidence:
    """Match candidate spellings to measured identities without inventing need on refusal."""
    from .validity import normalize_validity

    validity = normalize_validity(result)
    if removal_measurement_state(validity.admits_certificate, 0) == "unverified":
        return RemovalEvidence("unverified", cut_reasons=validity.cut_reasons)
    needed = set(_obligations_by_test(result.kill_matrix, result.line_coverage)) - redundant_2axis(
        result.kill_matrix, result.line_coverage
    )
    measured = {_test_identity(name, root) for name in needed}
    matched = frozenset(candidate for candidate in candidates if _test_identity(candidate, root) in measured)
    return RemovalEvidence(removal_measurement_state(True, len(matched)), matched)


def _record_removal_evidence(
    evidence: RemovalEvidence,
    subject: tuple[str, str],
    wanted: set[str],
    retained: dict[str, str],
    gaps: dict[tuple[str, str], str],
    causes: dict[tuple[str, str], tuple[str, ...]],
    *,
    display: str,
) -> None:
    """Consume sibling, neighbor and observed-reach evidence by the same rule (#112)."""
    if evidence.state == "unverified":
        gaps[subject] = "unmeasured"
        causes[subject] = evidence.cut_reasons
        return
    for name in sorted(wanted & evidence.needed):
        retained[name] = display
    wanted.difference_update(evidence.needed)


def removal_safety(needed_by: str, reach_status: str, unmeasured: int, over_budget: int) -> str:
    """Whether one deletion candidate may go, once every function it touches was consulted (#103,
    pure — pinned).

    The defect, measured through the real CLI: `test_mixed` asserted `f(3) == 6` (a duplicate) and
    `h(200) == 400`, and was the only test reaching `h`'s `x > 100` branch. `h` calls `g` calls `f`,
    each in its own module. `audit f --remove` checked `f`'s file and its one-hop neighbour `g`, found
    `test_mixed` redundant in both, and deleted it: `h` fell from 12/14 value-pinned to 5/14, with line
    6 uncovered, under "complete=True". The neighbourhood docstring named the hole ("A test serving a
    function OUTSIDE that neighborhood is still beyond audit's evidence") and the verb deleted anyway.

    Every code but ``removable`` keeps the test, and no two causes share a code, because each has its
    own remedy:

      "retained_for"          ``needed_by`` names a function that still needs it: a kill or a line only
                              it supplies there. Outranks everything; it is a measured need.
      "reach_unobserved"      no collected test answered to it (``reach_status`` ``not_collected``), so
                              it never ran. Remedy: the collection (re-run the audit).
      "reach_not_reproduced"  re-run by itself it did not pass as it did when measured (any other
                              status but ``known``), so what it executes is unknown. Remedy: the test.
      "reach_unmeasured"      ``unmeasured`` functions it executes had no valid measurement. Remedy:
                              their measurement. Outranks the budget, which raising cannot fix.
      "reach_over_budget"     ``over_budget`` functions it executes were left unchecked when the reach
                              budget ran out. Remedy: a larger budget.
      "removable"             redundant for the target and for every function it was observed to
                              execute. Correct, however far from the target those functions are.
    """
    if needed_by.strip():
        return "retained_for"
    if reach_status != "known":
        return "reach_unobserved" if reach_status == "not_collected" else "reach_not_reproduced"
    if unmeasured > 0:
        return "reach_unmeasured"
    if over_budget > 0:
        return "reach_over_budget"
    return "removable"


def probe_reach_status(raised: bool, item_status: str) -> str:
    """What one probe run of a deletion candidate establishes about its reach (#103, pure — pinned).

    The probe re-runs the candidate by itself to see what it executes, and that reach stands for the
    run that was measured only if this run PASSED as that one did. A live pytest item returns normally
    for a pass, a skip and an expected failure alike, so its category travels beside the return
    (Wesker's ``callable_item_status``: ``passed`` / ``failed`` / ``error`` / ``skipped`` / ``xfailed``,
    or ``unobserved`` for a callable that carries none). Split from `candidate_reach`, which holds the
    callable, so the decision takes only the two facts.

      "known"     it passed, or a callable that carries no category (a plain function) returned
                  normally: what it executed is its reach.
      "raised"    the call raised and no category names why.
      <category>  the item's own category when it did not pass (``failed`` / ``error`` / ``skipped`` /
                  ``xfailed``, or one this does not know), passed through as the cause: a skipped run
                  executed only what came before the skip, so its reach is partial, never complete.
    """
    status = item_status or "unobserved"
    if raised and status in ("passed", "unobserved"):
        return "raised"
    if status in ("passed", "unobserved"):
        return "known"
    return status


def candidate_reach(
    project_root: str,
    file: str,
    function: str,
    candidates: Sequence[str],
    *,
    per_test_timeout_s: float = 5.0,
) -> tuple[dict[str, tuple[str, frozenset[tuple[str, str]]]], dict[str, Any]]:
    """Every project function each candidate test EXECUTES, observed by running it once (#103).

    A test can kill a mutant only in a function it executes: a mutant changes one function, and a
    change to a function that never runs is unobservable. So a candidate's obligations lie exactly
    in its observed reach (tests deterministic, as everywhere the kill matrix is read). The probe runs
    the SAME callable the profile ran, the live pytest item with its fixtures, under an owned
    monitoring subscription in a bounded worker and the threads started in its observation window.
    It keeps the frames whose code is the project's own source:
    - under the root, and outside hidden, skipped and interpreter (site-packages) directories;
    - not a collected test file, and not a ``conftest.py``.
    A nested function counts as its outermost enclosing function, the unit Wesker mutates.

    Returns ``({candidate: (status, {(rel_file, qualname)})}, {candidate: callable})``. ``status`` is
    ``not_collected`` when no collected test answers to the id, else `probe_reach_status`'s code for
    the run: ``known`` only for a run that passed as the measured one did. `removal_safety` reads every
    other status as a reach not observed, never as an empty one.
    """
    import contextlib
    import io
    import sys

    from Wesker.ci import callable_item_status, callable_origin, callable_test_id, discover_test_callables
    from Wesker.monitoring import MonitoringObservationFailed

    from .capture import ObservationIncomplete, _run_for_effects
    from .kappa import _SKIP_DIRS

    root = os.path.abspath(project_root)
    rroot = os.path.realpath(root)
    full = file if os.path.isabs(file) else os.path.join(root, file)
    callables = list(discover_test_callables(root, os.path.relpath(full, root), [function]))
    test_files = {os.path.realpath(o) for c in callables if (o := callable_origin(c))}
    # Deduplicated (the three prefixes often coincide) in a deterministic order.
    interpreter = tuple(
        dict.fromkeys(os.path.realpath(p) + os.sep for p in (sys.prefix, sys.base_prefix, sys.exec_prefix))
    )
    by_identity: dict[str, Any] = {}
    for c in callables:
        by_identity.setdefault(_test_identity(callable_test_id(c, root), root), c)
    rel_of: dict[str, str] = {}

    def _project_rel(filename: str) -> str:
        """The root-relative path of a frame's file when it is project source, else ''."""
        rel = rel_of.get(filename)
        if rel is None:
            real = os.path.realpath(filename)
            parts = os.path.relpath(real, rroot).split(os.sep) if real.startswith(rroot + os.sep) else []
            project = (
                bool(parts)
                and real.endswith(".py")
                and real not in test_files
                and parts[-1] != "conftest.py"
                and not real.startswith(interpreter)
                and not any(
                    p in _SKIP_DIRS or p.startswith(".") or p in ("site-packages", "dist-packages")
                    for p in parts[:-1]
                )
            )
            rel = os.sep.join(parts) if project else ""
            rel_of[filename] = rel
        return rel

    reach: dict[str, tuple[str, frozenset[tuple[str, str]]]] = {}
    matched: dict[str, Any] = {}
    for cid in candidates:
        call = by_identity.get(_test_identity(cid, root))
        if call is None:
            reach[cid] = ("not_collected", frozenset())
            continue
        matched[cid] = call
        seen: set[tuple[str, str]] = set()

        def observed(code: Any, offset: int, _seen: set = seen, **kwargs: Any) -> None:
            rel = _project_rel(code.co_filename)
            qual = code.co_qualname.split(".<locals>.", 1)[0]
            if rel and "<" not in qual:
                _seen.add((rel, qual))

        raised = False

        def trial(_call=call) -> None:
            nonlocal raised
            try:
                _call()
            except (KeyboardInterrupt, SystemExit):
                raise
            except BaseException:  # noqa: BLE001
                raised = True

        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                run = _run_for_effects(
                    trial,
                    timeout_s=per_test_timeout_s,
                    event=sys.monitoring.events.PY_START,
                    observer=observed,
                    selectors=[rroot],
                    include_children=True,
                )
        except (ObservationIncomplete, MonitoringObservationFailed) as exc:
            if isinstance(exc, ObservationIncomplete) and not exc.contained:
                return {c: ("uncontained", frozenset()) for c in candidates}, matched
            reach[cid] = (f"observation_failed:{exc.code}", frozenset())
            continue
        if not run.contained:
            # Every later clearance would share the unbounded work left in this process.
            return {c: ("uncontained", frozenset()) for c in candidates}, matched
        elif run.timed_out:
            status = "timed_out"
        elif run.incomplete_thread:
            status = "incomplete_thread"
        else:
            status = probe_reach_status(raised, callable_item_status(call))
        reach[cid] = (status, frozenset(seen))
    return reach, matched


def removal_gate(target_action: str) -> str:
    """Whether `--remove` may act on this function's redundant set at all (#103, pure — pinned).

    ``target_action`` is the FunctionBasis terminal state of the target's OWN audit (`basis_action`).
    The redundant set is read off that measurement's kill matrix, and `module_safe_removals` re-checks
    every OTHER function a candidate serves, never the target. So a measurement that admits no
    certificate (a truncated search, mutants that could not be built, a module that would not load)
    leaves "redundant here" unestablished. Measured: re-audited in-process after a mid-file test edit,
    such a run built 2 of 11 mutants and listed a boundary mutant's only killer as redundant.

      "proceed"            ``complete`` or ``gap``: a valid measurement. A gap is mutants no test kills,
                           which no deletion changes; every kill observed stays observed.
      "refuse_unresolved"  anything else (``unresolved``, or a state this does not know): nothing is
                           deleted, and every candidate is kept as ``target_unresolved``.
    """
    return "proceed" if target_action in ("complete", "gap") else "refuse_unresolved"


def removal_after_reading(before: str, after: str, newly_open: int) -> str:
    """What the post-removal re-check says about the removal (#103, pure — pinned).

    ``before`` / ``after`` are the target's FunctionBasis states (`basis_action`) measured before and
    after the deletions; ``newly_open`` counts obligations open after that were not open before
    (killable survivors and uncovered lines; the target's file is never edited, so they compare
    directly). Every deleted test was redundant wherever it ran, so a removal cannot open an
    obligation unless that reasoning failed, and this is the check that would say so. Reading only
    ``after`` printed a gap the target ALREADY had as if the removal made it.

      "complete"    the re-check reads complete.
      "gap_kept"    it reads a gap, the same one the target had before; nothing newly open.
      "gap_new"     it reads an obligation open that was not before: a removal may have broken the
                    target, and it is reported as such, never as done.
      "unmeasured"  the re-check admits no certificate (measured: in-process after a mid-file edit it
                    built 2 of 11 mutants), so it says nothing either way; a fresh run must confirm.
    """
    if after == "complete":
        return "complete"
    if after == "gap":
        return "gap_kept" if before == "gap" and newly_open <= 0 else "gap_new"
    return "unmeasured"


# The most reached functions `--remove` profiles in one run beyond the target's file and its one-hop
# neighbours (#103). A count of profiles, never seconds, so the same run always reads the same.
REACH_BUDGET = 32


def module_safe_removals(
    file: str,
    function: str,
    project_root: str = ".",
    candidates: Sequence[str] = (),
    reach_budget: int = REACH_BUDGET,
    *,
    two_sign: bool = False,
) -> tuple[tuple[str, ...], dict[str, str], dict[str, tuple[str, str]]]:
    """Filter deletion candidates against every function they serve: the file's siblings, the target's
    one-hop neighbours, and every function each candidate is observed to execute.

    ``redundant_tests`` is measured against ONE function's mutants and lines —
    evidence that says nothing about the rest of the module. A test that kills
    no mutant of ``f`` can still be the only killer of a mutant of ``g`` in the
    same file (measured: ``test_invalid_weight_raises`` — "pointless" for a
    post-decompose wrapper, sole killer of the helper's ``<=`` boundary mutant).
    Deleting on single-function evidence is how a prune silently un-pins a
    sibling.

    A candidate survives only if, for every sibling, it is UNINVOLVED there
    (kills none of its mutants, covers none of its lines) or redundant there
    too. Anything else is retained, mapped to the sibling that needs it.

    The evidence boundary (Cor. 10.6, bounded κ-neighborhood) is this file's
    functions PLUS the target's DIRECT call-graph neighbors — callers and callees
    (``kappa.call_graph_neighbors``) — which reach across file boundaries: a
    candidate redundant here and for every file-sibling can still be a BRIDGE
    (Def. 10.2), the sole killer of an immediate caller/callee's mutant in another
    module. Because Detective's import-reachability discovery would HIDE such a
    bridge test when profiling the neighbor (it imports the caller's module, not
    the neighbor's), the candidate's test files are force-included via profile's
    explicit ``tests=``.

    One hop was not enough (#103): a test can serve a function two hops away in another module, and
    the one-hop guard deleted it. So the boundary also covers each remaining candidate's OBSERVED
    REACH (`candidate_reach`): every function it executes and nothing above has consulted is profiled
    the same way, with the candidates force-included as their live items. The unit stays per function
    (each reached function is one profile, bounded by what the test runs), never a repo-wide trace,
    and at most ``reach_budget`` such profiles run (`reach_consultation_plan`). Each candidate then
    gets one verdict from `removal_safety`.

    Returns ``(safe, retained, unverified)``:
    - the candidates proven removable;
    - those kept, mapped to the function that still needs each;
    - those kept because their reach was not fully established, mapped to ``(code, subject)``: the
      `removal_safety` code and the detail its sentence names.
    """
    wanted = set(candidates)
    if not wanted:
        return (), {}, {}
    root = os.path.abspath(project_root)
    full = file if os.path.isabs(file) else os.path.join(root, file)
    with open(full, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=full)
    rel_target = os.path.relpath(full, root)
    retained: dict[str, str] = {}
    checked: set[tuple[str, str]] = set()
    gaps: dict[tuple[str, str], str] = {}
    causes: dict[tuple[str, str], tuple[str, ...]] = {}
    for qn, _node in walk_functions(tree):
        checked.add((rel_target, qn))
        if qn == function or not wanted:
            continue
        result = profile(file, qn, root, isolated=True, use_cache=False, two_sign=two_sign)
        _record_removal_evidence(
            _removal_needs(result, wanted, root), (rel_target, qn), wanted, retained, gaps, causes, display=qn
        )
    # Cor. 10.6 — the cross-file BRIDGE check over the κ-neighborhood. A candidate redundant for
    # `function` AND every file-sibling can still be the sole killer of a mutant of an immediate
    # caller/callee in ANOTHER file (Def. 10.2). Detective's import-reachability discovery HIDES such a
    # bridge test when profiling the neighbor (it imports the caller's module, not the neighbor's), so the
    # candidate's test files are FORCE-INCLUDED via profile's explicit `tests=`, bypassing the filter. One
    # hop only, so the neighbor set stays per-function-bounded (the sandwich thesis), never the closure.
    if wanted:
        from Wesker.ci import discover_test_callables, load_test_callables

        from .kappa import build_call_graph, call_graph_neighbors, function_locations

        cand_files = [f for f in _candidate_test_files(wanted) if os.path.exists(f)]
        cand_callables = load_test_callables(cand_files, root) if cand_files else []
        if cand_callables:
            locs = function_locations(root)
            for nb in sorted(call_graph_neighbors(build_call_graph(root), function.split(".")[-1])):
                if not wanted:
                    break
                for nb_file, nb_qn in locs.get(nb, ()):
                    if not wanted:
                        break
                    if (nb_file, nb_qn) == (rel_target, function) or _is_test_file(nb_file):
                        continue
                    # Judge the candidate's uniqueness for the neighbor by the SAME `needed` rule the
                    # file-sibling loop uses — the neighbor's own reachable tests PLUS the force-included
                    # candidates — so a bridge is caught but a candidate the neighbor's own suite already
                    # covers is not spuriously retained.
                    checked.add((nb_file, nb_qn))
                    # Statically routed tests only (#103). Since a foreign-file neighbour is measured on
                    # its own per-function baseline (`engine.session_baseline_scope`), the whole live
                    # suite here would be a full trace per neighbour. Fewer of the neighbour's own tests
                    # can only make a candidate look MORE needed, so the narrowing errs toward keeping.
                    nb_own = list(discover_test_callables(root, nb_file, [nb_qn], conservative=True))
                    nb_result = profile(
                        nb_file,
                        nb_qn,
                        root,
                        tests=nb_own + cand_callables,
                        isolated=True,
                        use_cache=False,
                        two_sign=two_sign,
                    )
                    _record_removal_evidence(
                        _removal_needs(nb_result, wanted, root),
                        (nb_file, nb_qn),
                        wanted,
                        retained,
                        gaps,
                        causes,
                        display=nb_qn,
                    )
    reach: dict[str, tuple[str, frozenset[tuple[str, str]]]] = {}
    if wanted:
        reach, live = candidate_reach(root, file, function, sorted(wanted))
        gaps.update(
            _consult_reach(
                root, reach, live, wanted, checked, retained, reach_budget, causes, two_sign=two_sign
            )
        )
    safe: list[str] = []
    unverified: dict[str, tuple[str, str]] = {}
    for cid in sorted(set(candidates)):
        status, reached = reach.get(cid, ("known", frozenset()))
        unmeasured = sorted(
            f"{f}::{q}" + (f" ({', '.join(causes[(f, q)])})" if causes.get((f, q)) else "")
            for f, q in reached
            if gaps.get((f, q)) == "unmeasured"
        )
        over = sorted(f"{f}::{q}" for f, q in reached if gaps.get((f, q)) == "over_budget")
        verdict = removal_safety(retained.get(cid, ""), status, len(unmeasured), len(over))
        if verdict == "removable":
            safe.append(cid)
        elif verdict != "retained_for":
            detail = {
                "reach_not_reproduced": status,
                "reach_unmeasured": _named_functions(unmeasured),
                "reach_over_budget": _named_functions(over),
            }
            unverified[cid] = (verdict, detail.get(verdict, ""))
    return tuple(safe), retained, unverified


def _named_functions(names: list[str]) -> str:
    """Up to three names in full, then a count, so a long reach stays one readable clause."""
    shown = ", ".join(names[:3])
    return shown if len(names) <= 3 else f"{shown} and {len(names) - 3} more"


def reach_consultation_plan(unchecked: dict[str, list[str]], budget: int) -> dict[str, str]:
    """Which candidates get their unchecked reach profiled within ``budget`` profiles (#103, pure —
    pinned).

    ``unchecked`` maps each candidate still in question to the functions it executes that nothing has
    consulted yet; ``budget`` is how many of those functions this run may profile. A candidate is
    decided only once EVERY function it executes has been consulted, so the budget is spent a whole
    candidate at a time, smallest unchecked reach first (then by id, so the same run always reads the
    same): one integration test that reaches hundreds of functions cannot starve the unit tests that
    reach two. A function several candidates share is paid for once. Split from `_consult_reach`,
    which holds live callables, so the decision takes only names.

      "covered"      it executes nothing unchecked: the measurements already taken decide it.
      "consult"      its unchecked reach fits in what remains, so each of those functions is profiled.
      "over_budget"  it does not fit, so it is kept (``reach_over_budget``), never deleted on a guess.
    """
    plan: dict[str, str] = {}
    scheduled: set[str] = set()
    # No clamp: a budget at or below zero schedules nothing either way, since every non-empty reach
    # costs at least one (pinned: the clamp's mutants were each provably equivalent).
    remaining = budget
    for cid in sorted(unchecked, key=lambda c: (len(set(unchecked[c])), c)):
        reach = set(unchecked[cid])
        new = reach - scheduled
        if not reach:
            plan[cid] = "covered"
        elif len(new) <= remaining:
            scheduled |= new
            remaining -= len(new)
            plan[cid] = "consult"
        else:
            plan[cid] = "over_budget"
    return plan


def _consult_reach(
    root: str,
    reach: dict[str, tuple[str, frozenset[tuple[str, str]]]],
    live: dict[str, Any],
    wanted: set[str],
    checked: set[tuple[str, str]],
    retained: dict[str, str],
    budget: int,
    causes: dict[tuple[str, str], tuple[str, ...]],
    *,
    two_sign: bool = False,
) -> dict[tuple[str, str], str]:
    """Profile what the remaining candidates execute that nothing has consulted yet, within ``budget``
    profiles (#103).

    Each reached function is one profile over its own statically routed tests plus the candidates
    themselves, force-included as their LIVE items so a fixture-using test runs as it did in the
    measurement. Narrowing the function's own tests can only make a candidate look MORE needed (fewer
    other tests share its kills), so the narrowing errs toward keeping, never toward deleting. A
    candidate still needed there is moved to ``retained`` (mutating ``wanted`` and ``retained``).
    Whose reach is consulted is `reach_consultation_plan`'s decision.

    Returns every reached function left without a verdict, with why: ``unmeasured`` (its profile was
    not a valid measurement) or ``over_budget`` (the budget ran out before it), which `removal_safety`
    turns into ``reach_unmeasured`` / ``reach_over_budget`` for each candidate that reached it.
    """
    from Wesker.ci import callable_test_id, discover_test_callables

    eligible = {cid for cid in wanted if reach[cid][0] == "known"}
    unchecked = {cid: sorted(f"{f}::{q}" for f, q in reach[cid][1] - checked) for cid in sorted(eligible)}
    plan = reach_consultation_plan(unchecked, budget)
    gaps: dict[tuple[str, str], str] = {}
    pending = sorted({fn for cid in eligible if plan[cid] == "consult" for fn in reach[cid][1]} - checked)
    for rel_file, qual in pending:
        if not any((rel_file, qual) in reach[cid][1] for cid in wanted & eligible):
            continue  # every candidate that reached it is already kept
        checked.add((rel_file, qual))
        routed = list(discover_test_callables(root, rel_file, [qual], conservative=True))
        seen = {_test_identity(callable_test_id(c, root), root) for c in routed}
        forced = [
            c for cid, c in sorted(live.items()) if cid in wanted and _test_identity(cid, root) not in seen
        ]
        result = profile(
            rel_file, qual, root, tests=routed + forced, isolated=True, use_cache=False, two_sign=two_sign
        )
        _record_removal_evidence(
            _removal_needs(result, wanted, root),
            (rel_file, qual),
            wanted,
            retained,
            gaps,
            causes,
            display=f"{rel_file}::{qual}",
        )
    for cid in sorted(wanted & eligible):
        if plan[cid] == "over_budget":
            for fn in reach[cid][1] - checked:
                gaps.setdefault(fn, "over_budget")
    return gaps
