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

import ast
import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from Wesker.ci import walk_functions

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
    failing_tests: tuple[str, ...]  # assert-fail on current code -> WARN, never delete
    killable_gaps: tuple[str, ...]  # killable mutants the suite fails to kill
    missing_lines: tuple[int, ...]  # executable lines no test covers (after the line oracle)
    minimal_test_count: int  # size of the two-axis minimal cover
    manually_unreachable: int = 0  # lines closed by a manual unreachability flag (issue #9)
    contradicted_line_flags: tuple[str, ...] = ()  # flags overridden by observed execution
    manual_equivalent: int = 0  # survivors manually flagged equivalent (oracle)
    candidate_equivalent: int = 0  # survivors with no distinguishing input found (UNPROVEN — flag to confirm)
    unclassified: int = 0  # survivors the search could not classify (may be killable OR equivalent)
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
    # Mutants a test pins by VALUE (assertion kills). Exposed so the whole universe partitions,
    # derivably and provably: `total_mutants = value_killed + len(killable_gaps) + candidate_equivalent
    # + manual_equivalent + unclassified` (asserted in `audit_suite` via `audit_partition_sums`).
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


def audit_check_failed(killable_gaps: int, missing_lines: int, failing_tests: int) -> bool:
    """Whether ``detective audit --check`` should FAIL the CI ratchet on a SPECIFICATION gap (#35, #50).

    True ONLY for a real, actionable claim about the USER's code or suite: a KILLABLE mutant it does
    not kill (a spec hole), a reachable line no test covers, or a currently-FAILING test. This is the
    default gate; it must fail only when the code got WORSE, never when Detective's own measurement got
    shorter. An UNCLASSIFIED survivor is a MEASUREMENT limit — the equivalence search could not run on
    it, which is the tool's uncertainty, not the developer's regression — so it is EXCLUDED here (issue
    #50, the over-gating direction; #35 fixed the under-gating one) and handled by
    :func:`audit_measurement_incomplete`, fatal only under ``--check-strict``. Candidate-equivalent and
    crash-only survivors are likewise excluded: unproven-equivalent, resolved by ``flag`` or a killing
    input, never a spec hole a green-field edit introduced. A ratchet that reddens on tool-internal
    conditions gets deleted from the pipeline, taking the real gate with it.
    """
    return bool(killable_gaps) or bool(missing_lines) or bool(failing_tests)


def audit_measurement_incomplete(unclassified: int) -> bool:
    """Whether the audit's MEASUREMENT was incomplete — honest tool-side uncertainty, not a code gap.

    An UNCLASSIFIED survivor (issue #50) is one the equivalence search could not evaluate — it may be
    killable OR equivalent; Detective simply could not decide. That is the same class as a budget CUT:
    a limit on the measurement, not a finding about the suite. It is surfaced ALWAYS (visible), but is
    fatal only under ``--check-strict`` — so the default ``--check`` stays a claim about the code alone,
    and a green suite that has not changed can never be reddened because a search got shorter."""
    return unclassified > 0


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
    total: int, value_killed: int, killable: int, candidate_equivalent: int, manual: int, unclassified: int
) -> bool:
    """Whether every mutant lands in EXACTLY one terminal value-bucket (issue #55, pure — pinned).

    The universe partitions by VALUE specification, mutually exclusive and exhaustive:
    ``total == value_killed + killable + candidate_equivalent + manual + unclassified``. Each mutant is
    value-pinned, a killable-unkilled gap, value-equivalent (candidate), manually-flagged equivalent, or
    unclassifiable. When this is False the headline % cannot be reconstructed from the classification
    beneath it — a Detective ACCOUNTING bug, not a fact about the suite — so :func:`audit_suite` raises
    rather than print a number that does not reconcile. ``crash_only_equivalent`` is a sub-count of
    ``candidate_equivalent`` and never a term here; ``kill_pct`` counts crash kills too and is a
    different (detection) lens that does not enter this partition."""
    return total == value_killed + killable + candidate_equivalent + manual + unclassified


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
        return f"{verdict.category} [{verdict.mutant_id}] — kill with {verdict.witness.args}"
    return f"{verdict.category} [{verdict.mutant_id}]"


def audit_suite(
    file: str,
    function: str,
    project_root: str = ".",
    *,
    progress: Callable[[int, int, float], None] | None = None,
    trace_progress: Callable[[int, int, float], None] | None = None,
) -> SuiteAudit:
    """Assess the function's existing suite on both completeness axes.

    Runs one profile of the CURRENT suite (kill matrix + baseline line coverage),
    then classifies the survivors so a *killable* gap (a specification hole) is not
    conflated with an *equivalent* survivor (nothing to fix). Never writes.

    ``trace_progress`` reports the BASELINE-TRACE phase, which dominates a large suite's wall clock
    and, unreported, made audit look hung for minutes before the first byte (issue #53).
    """
    result = profile(file, function, project_root, progress=progress, trace_progress=trace_progress)
    # A test belongs to THIS function's suite only if it discharges an obligation for
    # it — kills one of its mutants OR covers one of its lines. The baseline pass runs
    # every discovered test against the original, so tests for OTHER functions appear
    # in line_coverage with an EMPTY covered-line list; counting those would inflate
    # test_count and bloat. Require a non-empty contribution.
    suite = set(t for tests in result.kill_matrix.values() for t in tests) | {
        t for t, lines in result.line_coverage.items() if lines
    }
    test_names = sorted(suite)
    # ℋ ⊎ 𝒢 origin census (§2.3, D5): attribute each obligation-discharging test to its half from the
    # RECORDED authorship fact its file carries, never a path glob. The nodeid's path segment resolves
    # the file; `witness_origin_of` reads its Detective header. A test whose file cannot be read is
    # unattributed — "we did not measure this", kept apart from both halves.
    from .certify import witness_origin_of_nodeid

    _root_abs = os.path.abspath(project_root)
    _origins = {"intent": 0, "characterization": 0, "unattributed": 0}
    for _tid in test_names:
        # `witness_origin_of_nodeid` owns the nodeid→file resolution (live `file.py::name` or a
        # `legacy:/abs/...::name`), so this census and the FunctionBasis witnesses agree file-for-file.
        _origins[witness_origin_of_nodeid(_root_abs, _tid)] += 1
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
        full_path = file if os.path.isabs(file) else os.path.join(root_abs, file)
        try:
            with open(full_path, encoding="utf-8") as fh:
                node = next((n for qn, n in walk_functions(ast.parse(fh.read())) if qn == function), None)
        except (OSError, SyntaxError):
            node = None
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
    candidate_equivalent = 0
    candidate_equivalent_ids: tuple[str, ...] = ()
    crash_only_equivalent = 0
    unclassified = 0
    classified = False
    try:
        # Reuse THIS profile (#65): classify the survivors of the exact measurement whose counts the
        # partition below checks, so the two can never come from two divergent profiles and crash the
        # assertion. `classify_survivors` re-profiles only when no compatible result is handed to it.
        report = classify_survivors(file, function, project_root, profile_result=result)
        # Whether a killable gap may name the input to kill it with — see `_gap_desc`.
        expressible = bool(report.inputs_expressible)
        killable_gaps = tuple(_gap_desc(v, expressible) for v in report.killable)
        manual_equivalent = len(report.manual_equivalent)
        candidate_equivalent = len(report.equivalent)
        candidate_equivalent_ids = tuple(v.mutant_id for v in report.equivalent)
        crash_only_equivalent = sum(1 for v in report.equivalent if v.crash_only)
        unclassified = len(report.unclassified)
        mutant_complete = not report.killable and not report.unclassified
        classified = True
    except Exception:  # noqa: BLE001 — classification is advisory, never fails the audit
        killable_gaps = tuple(
            f"{r.get('category', '?')} [{r.get('mutant_id', '?')}]" for r in result.value_survivor_records
        )
        mutant_complete = result.value_survived == 0

    total = result.total_mutants
    # REFUSE rather than report a headline that cannot be reconstructed from the classification (#55).
    # The value partition must be exact; a mismatch is a Detective accounting bug, surfaced loudly here
    # instead of shipped as a wrong percentage. Only when classification actually ran (the advisory
    # fallback above does not produce the terminal buckets).
    if classified and not audit_partition_sums(
        total, result.value_killed, len(killable_gaps), candidate_equivalent, manual_equivalent, unclassified
    ):
        # With the single-profile reuse above this cannot arise from two divergent measurements — it
        # is now a genuine defensive last resort for an internal accounting inconsistency. Typed (not a
        # bare AssertionError) so the CLI renders a clean "please report" refusal instead of leaking a
        # raw Python traceback to a user (#65).
        raise AuditAccountingError(
            f"audit partition does not sum for {result.function_key}: total={total} "
            f"value_killed={result.value_killed} killable={len(killable_gaps)} "
            f"candidate_equivalent={candidate_equivalent} manual={manual_equivalent} "
            f"unclassified={unclassified}"
        )
    # The FunctionBasis this audit earned (#X4 tail): built with the REAL undischargeable-equivalent
    # count — `candidate_equivalent` here is the UNION of true-equivalent and crash-only, and a
    # crash-only survivor is KILLABLE (a crash input distinguishes it), NOT undischargeable, so
    # subtract it. Same `node` the line oracle used, so the basis's U_t agrees with this audit's
    # `manually_unreachable`. Both counts are 0 when classification did not run, giving a conservative
    # basis rather than a crash.
    from .validity import normalize_validity

    _basis = function_basis(
        result,
        normalize_validity(result),
        os.path.abspath(project_root),
        node,
        candidate_equivalent=candidate_equivalent - crash_only_equivalent,
    )
    return SuiteAudit(
        function=result.function_key,
        test_count=len(test_names),
        kill_pct=round(100 * result.total_killed / total, 1) if total else 100.0,
        mutant_complete=mutant_complete,
        line_complete=not missing,
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
        # touches none of them and is not this report's business.
        failing_tests=tuple(f for f in result.failing_tests if f in suite),
        killable_gaps=killable_gaps,
        missing_lines=tuple(missing),
        manually_unreachable=len(manually_unreachable),
        contradicted_line_flags=contradicted_flags,
        minimal_test_count=len(minimal),
        manual_equivalent=manual_equivalent,
        candidate_equivalent=candidate_equivalent,
        candidate_equivalent_ids=candidate_equivalent_ids,
        crash_only_equivalent=crash_only_equivalent,
        unclassified=unclassified,
        value_killed=result.value_killed,
        total_mutants=total,
        intent_tests=_origins["intent"],
        characterized_tests=_origins["characterization"],
        unattributed_tests=_origins["unattributed"],
        function_basis=_basis,
    )


def module_safe_removals(
    file: str,
    function: str,
    project_root: str = ".",
    candidates: Sequence[str] = (),
) -> tuple[tuple[str, ...], dict[str, str]]:
    """Filter deletion candidates against every SIBLING function in ``file``.

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

    The evidence boundary is THIS FILE: a test serving a function in another
    module is outside every kill matrix audit has, so the caller's report must
    scope its claim to the file — not "nothing else changes".
    """
    wanted = set(candidates)
    if not wanted:
        return (), {}
    root = os.path.abspath(project_root)
    full = file if os.path.isabs(file) else os.path.join(root, file)
    with open(full, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=full)
    retained: dict[str, str] = {}
    for qn, _node in walk_functions(tree):
        if qn == function or not wanted:
            continue
        result = profile(file, qn, root)
        needed = set(_obligations_by_test(result.kill_matrix, result.line_coverage)) - redundant_2axis(
            result.kill_matrix, result.line_coverage
        )
        for name in sorted(wanted & needed):
            retained[name] = qn
        wanted -= needed
    return tuple(sorted(wanted)), retained
