"""One authoritative answer to "may this measurement support a certificate?" (issue #60).

Detective and Wesker expose several partially overlapping signals — ``budget_exhausted``,
survivor counts, line completeness, ``is_gateable``, coverage depth, containment, collection
identity. Detective RECONSTRUCTED usability from whichever subset a given call site happened to
read, so an upstream refusal could be weakened at the integration seam: a result with
``is_gateable=False`` and ``budget_exhausted=False`` was, at several boundaries, indistinguishable
from a clean one.

This module is the seam. Wesker's result is normalized ONCE into a versioned object, and
downstream code consumes that object rather than re-deriving a narrower proxy from raw fields.

TWO RULES CARRY THE DESIGN.

Gateability is ABSORBING. Downstream code may diagnose a refusal, never reconstruct it as a
pass. There is deliberately no code path here that turns ``gateable=False`` back into True.

Absence is not falsehood. An engine that does not publish a field has not said the measurement
is invalid; it has said nothing. Refusing on that basis would break every user on a released
engine, and assuming support is the unnamed-capability assumption #60 exists to forbid — so the
compatibility decision is explicit, recorded in ``capability_flags``, and conservative in the
direction that preserves prior behaviour.

References: S-codes = docs/CORRECTNESS_REPAIRS_2026-09-08.md
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

# Bumped when the MEANING of a field changes, so a stored receipt cannot be read under a
# different contract than the one that produced it. Additive fields do not require a bump;
# a changed reason vocabulary does.
# 3: `mutant_evaluation_failed` split into the three dispositions it collapsed —
#    `mutant_construction_failed` / `mutant_not_installed` / `mutant_not_entered` (S13). A changed
#    reason vocabulary is exactly what this number exists to signal.
# 4: `routing_failed` joins the vocabulary (#91). Additive, but the vocabulary is exhaustive on
#    purpose, so a reader that switches over it must learn the new member rather than meet it.
# 5: execution bounds have distinct reasons: step exhaustion and unresolved wall time.
# 6: shape hazard refusals (refuse_signal, refuse_subprocess, refuse_thread, refuse_collector,
#    refuse_fixture) and containment_unknown join the vocabulary.
# 7: `nested_measurement` (Wesker #28's refusal) and `nondeterministic_baseline` (Wesker's opt-in
#    determinism check) join the vocabulary; both used to surface as `engine_refused_unspecified`,
#    or as nothing at all when a recognised reason stood beside them. An unscored disposition this
#    version does not know now adds `engine_refused_unspecified` even beside known reasons.
# 8: `mutant_not_entered` splits by the cause Wesker names (#77, Wesker#18) into six reasons, one per
#    cause, and keeps its own name only for a not-entered mutant whose cause is absent or unknown. A
#    reader that switched on the one code has to learn the family.
#    And `write_outside_authority` (#105: a test run under a mutant tried to write outside its write
#    authority, and the write was prevented) joins the vocabulary as a per-mutant reason.
MEASUREMENT_VALIDITY_SCHEMA = 8

# Every typed reason this module can emit. Exhaustive on purpose: a reason that is not in this
# tuple cannot be rendered consistently across CLI, --json, MCP and receipts, which is the
# requirement that "identical cut reasons" is stated in.
CUT_REASONS: tuple[str, ...] = (
    "target_load_failed",
    "routing_failed",
    "budget_exhausted",
    "uncontained_worker",
    "containment_unknown",
    "step_budget_exceeded",
    "mutant_wall_undetermined",
    "write_outside_authority",
    "coverage_truncated",
    "sampled_universe",
    "collection_incomplete",
    "ambiguous_module_identity",
    "nondeterministic_baseline",
    "refuse_signal",
    "refuse_subprocess",
    "refuse_thread",
    "refuse_collector",
    "refuse_fixture",
    "nested_measurement",
    "nonreproducible_in_process",
    "invalid_verification",
    "cached_verification",
    "unknown_verification_basis",
    "verification_basis_changed",
    "verification_failed",
    "verification_universe_changed",
    # Wesker's OWN precedence, earliest failed phase first (`engine.mutant_disposition`). These
    # were one reason, `mutant_evaluation_failed`, rendered "the harness failed" — true only of
    # the first. See `cut_reason_sentence` for why the other two are not harness failures at all.
    "mutant_construction_failed",
    "mutant_not_installed",
    # One reason per cause Wesker names for a not-entered mutant (`engine.not_entered_cause`), in
    # its order, then the cause-free fallback. They were one reason whose sentence named a
    # decorator/registry capture whatever the cause, on plain functions that had neither (#77).
    "mutant_not_entered_not_reached",
    "mutant_not_entered_decorator_wrapper",
    "mutant_not_entered_captured_at_import",
    "mutant_not_entered_pre_bound_reference",
    "mutant_not_entered_holder_not_found",
    "mutant_not_entered_no_reach_data",
    "mutant_not_entered",
    "engine_refused_unspecified",
)

_HAZARD_TO_CUT_REASON = {
    "signal_main_thread": "refuse_signal",
    "spawns_subprocess": "refuse_subprocess",
    "starts_background_thread": "refuse_thread",
    "custom_collector": "refuse_collector",
    "stateful_fixture": "refuse_fixture",
}

# Wesker's unscored dispositions (`engine.mutant_disposition`) -> the reason each one cuts the run
# with. One table, read by `normalize_validity`'s completeness guard and by `flag`'s refusal of a
# mutant with no verdict, so the two cannot name the same disposition differently. "cut" (an
# uncontained mutant) is known but has no row: containment owns it (`uncontained_worker`).
UNSCORED_DISPOSITION_REASONS: dict[str, str] = {
    "harness_error": "mutant_construction_failed",
    "not_installed": "mutant_not_installed",
    "not_entered": "mutant_not_entered",
    "diverged": "step_budget_exceeded",
    "undetermined": "mutant_wall_undetermined",
    "nested_measurement": "nested_measurement",
    "write_outside_authority": "write_outside_authority",
}
_KNOWN_UNSCORED = frozenset(UNSCORED_DISPOSITION_REASONS) | {"cut"}

# The reasons that describe SOME mutants rather than the run: every mutant was evaluated, and these
# name the ones that reached no verdict. Classification of the OTHER survivors stands beside them
# (`classification_standing`); a certificate does not. A prevented write (#105) is one of them: it
# happened under ONE mutant's run, and the other mutants' verdicts were measured as before.
PER_MUTANT_REASONS: frozenset[str] = frozenset(
    {"mutant_wall_undetermined", "step_budget_exceeded", "write_outside_authority"}
)

# Wesker's named not-entered causes (`engine.not_entered_cause`) -> the reason each one cuts the run
# with (#77). A cause this version does not know, or a record that carries none (an engine before
# Wesker#18, `not_entered_causes`' own ``unclassified``), falls back to `mutant_not_entered`.
NOT_ENTERED_CAUSE_REASONS: dict[str, str] = {
    "not_reached": "mutant_not_entered_not_reached",
    "decorator_wrapper": "mutant_not_entered_decorator_wrapper",
    "captured_at_import": "mutant_not_entered_captured_at_import",
    "pre_bound_reference": "mutant_not_entered_pre_bound_reference",
    "holder_not_found": "mutant_not_entered_holder_not_found",
    "no_reach_data": "mutant_not_entered_no_reach_data",
}
NOT_ENTERED_REASONS: frozenset[str] = frozenset(NOT_ENTERED_CAUSE_REASONS.values()) | {"mutant_not_entered"}

# The reasons beside which the OTHER survivors may still be classified. A not-entered mutant names
# itself, exactly as a no-verdict one does: it was installed and no test called it, which says
# nothing about a survivor some test did enter — and the witness search calls the original directly,
# so no install topology reaches it. Kept apart from PER_MUTANT_REASONS, which also decides what
# reads as "no verdict" (`unresolved_mutant_records`): a not-entered mutant has its own rows.
CLASSIFY_BESIDE_REASONS: frozenset[str] = PER_MUTANT_REASONS | NOT_ENTERED_REASONS


def not_entered_reasons(causes: list[str]) -> tuple[str, ...]:
    """The cut reasons a run's not-entered mutants earn, one per named cause (#77, pure — pinned).

    `mutant_not_entered` was ONE reason whose sentence named "the decorator/registry capture" and
    told the operator to "route a test through the patched name, or pin the caller". Wesker#18 now
    decides the cause from the baseline's reach and a scan of module-level holders, and on a plain
    function no consulted test called — no decorator, no registry — the sentence still named one.
    So each cause has its own reason and its own repair.

    ``causes`` are the causes Wesker named (`ProfilingResult.not_entered_causes`' keys). A cause this
    version does not know, ``unclassified``, or an empty list (a not-entered mutant from an engine that
    names none) is `mutant_not_entered`, whose sentence names no mechanism: falling back to the old
    decorator wording would assert a cause nobody observed. Declaration order, so two runs cut the same
    way read the same.
    """
    named = {NOT_ENTERED_CAUSE_REASONS.get(cause, "mutant_not_entered") for cause in causes} or {
        "mutant_not_entered"
    }
    return tuple(reason for reason in CUT_REASONS if reason in named)


def unscored_record_reason(record: dict) -> str:
    """The reason ONE unscored mutant record carries (#77, pure — pinned).

    The disposition's reason (`UNSCORED_DISPOSITION_REASONS`), refined for a not-entered record by the
    cause Wesker named on it, so `flag`'s refusal of that mutant names its own repair and not the
    family's. A disposition this version does not know is `engine_refused_unspecified`.
    """
    disposition = str(record.get("disposition", ""))
    if disposition == "not_entered":
        return not_entered_reasons([str(record.get("cause") or "unclassified")])[0]
    return UNSCORED_DISPOSITION_REASONS.get(disposition, "engine_refused_unspecified")


def holder_names(record: dict) -> list[str]:
    """What holds the original, as one not-entered record names it: ``"<kind> <where>"`` per holder
    Wesker recorded, in its order (#77, pure — pinned). A holder that is not a mapping names nothing."""
    return [
        f"{holder.get('kind', '?')} {holder.get('where', '?')}"
        for holder in record.get("holders") or ()
        if isinstance(holder, dict)
    ]


def not_entered_detail(unscored_records: Iterable[object]) -> tuple[dict, ...]:
    """Per named cause: its reason, the mutants it accounts for, and what holds the original (#77).

    A cause code cannot carry WHERE the original is held, and "print what still holds the original" is
    the repair a captured or aliased reference needs (#77). Wesker puts each holder's ``kind`` and
    ``where`` on the record, and the scan's own status beside them: ``budget_cut`` / ``limit_reached``
    mean the scan stopped early, so "no holder found" there is NOT "no holder", and the entry carries
    the first status that was not ``complete`` so a renderer can say so.
    """
    by_cause: dict[str, dict] = {}
    for record in unscored_records:
        if not isinstance(record, dict) or record.get("disposition") != "not_entered":
            continue
        cause = str(record.get("cause") or "unclassified")
        entry = by_cause.setdefault(
            cause,
            {
                "cause": cause,
                "reason": unscored_record_reason(record),
                "mutants": [],
                "holders": [],
                "holder_scan": "complete",
            },
        )
        entry["mutants"].append(str(record.get("mutant_id", "?")))
        entry["holders"] = list(dict.fromkeys([*entry["holders"], *holder_names(record)]))
        scan = str(record.get("holder_scan") or "complete")
        if entry["holder_scan"] == "complete" and scan != "complete":
            entry["holder_scan"] = scan
    return tuple(sorted(by_cause.values(), key=lambda e: (CUT_REASONS.index(e["reason"]), e["cause"])))


def measurement_cut_kind(cut_reasons: list[str]) -> str:
    """Whether a cut run needs its MEASUREMENT repaired, or a test written (#77, pure — pinned).

    "none"       no reason: nothing is cut.
    "reach_gap"  every reason is `mutant_not_entered_not_reached`: each test that ran against those
                 mutants was traced in full and none executed a line of the function, so no install
                 topology explains the silence — the suite has no test that calls it. The repair is
                 a test that does (converge writes one), and the gaps beside it are real gaps: a
                 re-measurement changes nothing, which is what the old "resolve the measurement
                 causes" left the operator with — a next step that was not one.
    "repair"     anything else: the measurement itself is the thing to fix.
    """
    if not cut_reasons:
        return "none"
    if all(reason == "mutant_not_entered_not_reached" for reason in cut_reasons):
        return "reach_gap"
    return "repair"


def unresolved_mutant_records(unscored_records: Iterable[object]) -> tuple[tuple[str, str], ...]:
    """``(mutant_id, disposition)`` for every mutant that reached NO verdict (#80/#126).

    The mutants behind the per-mutant reasons, by id: Wesker's `unscored_records` whose disposition
    maps to a PER_MUTANT_REASONS member. One derivation for converge and audit, so the two verbs name
    the same mutants in the same class.
    """
    return tuple(
        (str(r.get("mutant_id", "?")), str(r.get("disposition", "")))
        for r in unscored_records
        if isinstance(r, dict)
        and UNSCORED_DISPOSITION_REASONS.get(str(r.get("disposition", ""))) in PER_MUTANT_REASONS
    )


def classification_standing(cut_reasons: list[str]) -> str:
    """Whether the survivors of a measurement may be classified (Detective #80/#126, pure — pinned).

    `classify_survivors` used to return EVERY survivor unclassified whenever the measurement did not
    admit a certificate, for any reason. That is right for a RUN-level refusal — the module did not
    load, routing failed, the run was cut or uncontained, the collection was incomplete, the identity
    ambiguous, the baseline nondeterministic, a fast-mode shape hazard, a nested measurement, or any
    reason this version does not recognise: nothing measured there can anchor a witness. It is wrong
    for a reason that names SOME mutants: two that reached a wall-clock bound made a six-line loop
    function's ten unrelated survivors "unclassified — the search could not run on them", and the
    report then asked the operator to inspect an execution none of them was part of.

      "classify"                    no reason: classify, and the measurement may certify.
      "classify_beside_unresolved"  only per-mutant reasons: classify the survivors; the no-verdict
                                    mutants stay named and the certificate stays withheld.
      "blocked"                     any run-level (or unrecognised) reason: classify nothing.

    A not-entered mutant is per-mutant too (#77, `CLASSIFY_BESIDE_REASONS`): two default-argument
    mutants that no consulted test entered left thirteen unrelated survivors of a plain function
    "unclassified — the search could not run on them", when the search ran fine.
    """
    if not cut_reasons:
        return "classify"
    if all(reason in CLASSIFY_BESIDE_REASONS for reason in cut_reasons):
        return "classify_beside_unresolved"
    return "blocked"


def measurement_cut_reasons(
    reported_gateable: bool,
    gateable: bool,
    budget_exhausted: bool,
    coverage_depth: str,
    containment: str,
    identity_ambiguous: bool,
    collection_incomplete: bool = False,
    construction_failed: bool = False,
    not_installed: bool = False,
    not_entered: bool = False,
    target_load_failed: bool = False,
    routing_failed: bool = False,
    step_budget_exceeded: bool = False,
    mutant_wall_undetermined: bool = False,
    fast_mode: str = "",
    shape_hazards: tuple[dict, ...] | list[dict] = (),
    nondeterministic_baseline: bool = False,
    nested_measurement: bool = False,
    unrecognised_unscored: bool = False,
    not_entered_causes: tuple[str, ...] | list[str] = (),
    write_outside_authority: bool = False,
) -> tuple[str, ...]:
    """Every reason THIS measurement cannot support a certificate (#60, pure — pinned).

    Plural on purpose. A run can be cut for more than one reason at once, and reporting only the
    first makes the second invisible to whoever fixes the first — they re-run, hit the next
    refusal, and have no way to know it was always there.

    ``target_load_failed`` is FIRST because nothing downstream of it is meaningful: if the module
    would not import, no mutant was ever evaluated, so every count on the run describes an empty
    observation. Before this reason existed, that state produced NO cut reason at all — validity
    stayed gateable, `certificate_standing` read clean, and converge's routing passed all three
    standing guards and asked the operator to author inputs for a module that cannot load.
    Observed 2026-09-08 on conorheins ``str2bool``: 0/27 killed, 27 unclassified, **exit 0**.
    Worse and reachable by inspection: a load-failed target with no static line gap satisfies
    `not (has_killable or has_line_gap)` and returns ``settled`` — DONE over a run that measured
    nothing.

    The fact was not unavailable, only uncarried: `audit` already ANDed a local `_load_failed`
    into its own completeness, which is precisely the "re-derive a narrower proxy" shape this
    module exists to end. One object carries it now, so every consumer reads the same refusal
    instead of each re-deriving its own.

    ``routing_failed`` is SECOND, beside it and for the same reason (#91): routing is the
    applicability bound, so when it raises no test is authorised and no mutant meets one — every count
    on the run describes an empty observation. It replaced a silent widening: the failure used to run
    the whole collection, not-consulted tests included, and the run came back gateable with no reason.

    ``collection_incomplete`` is the "degrade loudly" enforcement for the test FLOOR: a test file
    that failed to COLLECT (an ImportError at collection — a torch dep, a broken conftest) is
    silently absent from the routed suite, so a mutant only that file's tests would kill reads as
    candidate-equivalent, and the COMPLETE claim is unsafe. Since an uncollected file cannot be
    reach-analysed, ANY collection error cuts the run — the sound over-approximation — rather than
    let the measurement rest on fewer tests than the layout implies without saying so.

    ``engine_refused_unspecified`` is the load-bearing state. When the engine reports
    ``is_gateable=False`` and none of the signals we DO understand explains it, the honest answer
    is to say that rather than return an empty tuple. An empty reason list beside a refusal reads
    as "no problems found", which is exactly how a refusal gets talked past — and it is the shape
    this whole issue is about. It also means a future Wesker that refuses for a reason this
    version has never heard of degrades to a named unknown instead of a silent pass.

    Order is the declaration order of ``CUT_REASONS``, not discovery order, so two runs cut the
    same way produce byte-identical output on every surface.

    ``nested_measurement`` (Wesker #28's refusal: a test that runs the engine inside a held
    evaluation) and ``nondeterministic_baseline`` (Wesker's opt-in check saw the unmutated suite
    disagree with itself) are Wesker gateability inputs with names of their own now. Unnamed, the
    first read as `engine_refused_unspecified` and the second vanished whenever a per-mutant reason
    stood beside it — a run-level fault hidden behind a mutant-level one. ``unrecognised_unscored``
    closes the same hole for the future: an unscored disposition this version has never heard of
    adds `engine_refused_unspecified` even when known reasons are present.

    ``not_entered_causes`` (#77) are the causes Wesker named for its not-entered mutants; each earns its
    own reason (`not_entered_reasons`). ``not_entered`` with no cause named is the cause-free
    `mutant_not_entered` — an engine that names none is never read as one that named a decorator.
    """
    reasons: list[str] = []
    if target_load_failed:
        reasons.append("target_load_failed")
    if routing_failed:
        reasons.append("routing_failed")
    if budget_exhausted:
        reasons.append("budget_exhausted")
    if containment == "uncontained":
        reasons.append("uncontained_worker")
    elif containment == "unknown":
        reasons.append("containment_unknown")
    if step_budget_exceeded:
        reasons.append("step_budget_exceeded")
    if mutant_wall_undetermined:
        reasons.append("mutant_wall_undetermined")
    if write_outside_authority:
        reasons.append("write_outside_authority")
    if coverage_depth == "cut":
        reasons.append("coverage_truncated")
    elif coverage_depth == "sampled":
        reasons.append("sampled_universe")
    if collection_incomplete:
        reasons.append("collection_incomplete")
    if identity_ambiguous:
        reasons.append("ambiguous_module_identity")
    if nondeterministic_baseline:
        reasons.append("nondeterministic_baseline")
    hazard_reasons: set[str] = set()
    if fast_mode.startswith("refuse_"):
        hazard_reasons.add(fast_mode)
    for rec in shape_hazards:
        if isinstance(rec, dict):
            h = rec.get("hazard")
            if h in _HAZARD_TO_CUT_REASON:
                hazard_reasons.add(_HAZARD_TO_CUT_REASON[h])
    for hr in ("refuse_signal", "refuse_subprocess", "refuse_thread", "refuse_collector", "refuse_fixture"):
        if hr in hazard_reasons:
            reasons.append(hr)
    if nested_measurement:
        reasons.append("nested_measurement")
    # THREE reasons, not one. They were collapsed into `mutant_evaluation_failed` and rendered
    # "the harness failed" — which is true of construction and FALSE of the other two: an
    # un-installed mutant means the harness built it fine and the patch could not bind it, and an
    # un-entered mutant means both worked and no test called it. Three causes, three remedies,
    # one sentence that named the first. Wesker's own precedence order (S13).
    if construction_failed:
        reasons.append("mutant_construction_failed")
    if not_installed:
        reasons.append("mutant_not_installed")
    if not_entered or not_entered_causes:
        reasons.extend(not_entered_reasons(list(not_entered_causes)))
    if (reported_gateable and not gateable and not reasons) or unrecognised_unscored:
        reasons.append("engine_refused_unspecified")
    return tuple(reasons)


def cut_reason_sentence(reason: str) -> str:
    """One sentence per typed reason (#60, pure — pinned).

    ONE OWNER, because #60 requires CLI, --json, MCP and receipts to preserve IDENTICAL cut
    reasons. Two renderers of the same vocabulary is how "the CLI said the worker was
    uncontained and the receipt said the budget ran out" happens, and a reader reconciling two
    accounts of one refusal has no way to tell which is the measurement.

    Each sentence names what the reader should DO something about, not the internal state: a
    truncated universe sends them to `--deadline`, an ambiguous module identity sends them to
    their import layout, and those are not interchangeable.

    An unknown reason returns a NAMED unknown rather than "" — a blank beside a refusal reads as
    "no reason", which is the failure this vocabulary exists to prevent, and a future engine's
    reason must degrade to visible-but-unrecognised.
    """
    return {
        "target_load_failed": "the target module could not be imported, so no mutant was ever"
        " evaluated and every count on this run describes an empty observation — run under an"
        " interpreter that has the module's dependencies; no --input, --deadline or regime"
        " migration substitutes for an import that fails",
        "routing_failed": "routing — the bound on which tests may run for this function — failed, so no"
        " test was authorised, no mutant met a test, and every count on this run describes an empty"
        " observation; the error reported with it names the cause: an ImportError means the installed"
        " Wesker lacks the routing Detective requires (run under an interpreter whose Wesker meets"
        " Detective's declared floor), anything else is a defect to report with that error — no --input,"
        " --deadline or budget replaces the bound",
        "budget_exhausted": "the aggregate deadline was exhausted, so the universe was never fully measured",
        "uncontained_worker": "a timed-out worker could not be stopped, so later phases"
        " shared a process with it",
        "containment_unknown": "the engine could not establish whether worker execution was contained —"
        " re-measure under an isolated worker",
        "step_budget_exceeded": "one or more mutants exceeded an explicit deterministic step budget;"
        " this is budget-relative evidence, not proof of nontermination or equivalence — inspect the"
        " execution and its declared bound before re-measuring",
        "mutant_wall_undetermined": "one or more mutants reached a wall-clock execution bound without"
        " a verdict; this is neither a kill nor survival evidence — inspect the execution and its"
        " allowance before re-measuring",
        "write_outside_authority": "one or more mutants made a test try to write outside its write"
        " authority (the session's pytest temporary directory, or a temporary entry the test created)"
        " — the working directory is the project root, so the write was prevented before it landed,"
        " and those mutants are neither killed nor survived; keep the test's writes inside its"
        " temporary directory (resolve relative paths there, e.g. monkeypatch.chdir(tmp_path)) to"
        " measure them",
        "coverage_truncated": "the profile was cut before the universe was measured",
        "sampled_universe": "the universe was sampled, not enumerated",
        "collection_incomplete": "one or more test files failed to collect (an import error), so the"
        " routed suite is missing tests the layout implies — fix the collection errors and re-run",
        "ambiguous_module_identity": "the live collection resolved one module name to more than one file",
        "nondeterministic_baseline": "the repeated baseline check saw the unmutated suite disagree with"
        " itself, so no mutant verdict here is reproducible — remove the nondeterminism (time,"
        " randomness, test order, shared state) and re-run",
        "nested_measurement": "one or more mutants could not be measured in-process because a test"
        " that reaches them runs the mutation engine itself — a measurement inside a measurement,"
        " which is refused rather than waited into a deadlock; re-measure with --isolated",
        "refuse_signal": "one or more tests reference signal handling on the main thread; in-process"
        " execution cannot contain signal handlers — re-measure with --isolated",
        "refuse_subprocess": "one or more tests spawn a subprocess; in-process execution cannot contain"
        " child processes — re-measure with --isolated",
        "refuse_thread": "one or more tests start background threads; in-process execution cannot"
        " isolate thread state — re-measure with --isolated",
        "refuse_collector": "one or more tests use a custom collector; in-process execution cannot"
        " verify collector lifecycle — re-measure with --isolated",
        "refuse_fixture": "one or more tests use stateful runtime fixtures; in-process execution cannot"
        " isolate fixture state — re-measure with --isolated",
        "nonreproducible_in_process": "the in-process mutant universe did not reproduce under isolated "
        "evaluation — COMPLETE is withheld; re-measure with --isolated, preserving the same inputs and tests",
        "invalid_verification": "the required verification measurement was invalid; "
        "resolve its reported reasons",
        "cached_verification": "verification replayed cached evidence instead of making a fresh observation",
        "unknown_verification_basis": "verification did not identify the function and test basis it measured",
        "verification_basis_changed": "the function or test basis changed between the two measurements",
        "verification_failed": "the required verification measurement could not run; "
        "no certificate was issued",
        "verification_universe_changed": "the verification did not account for the same mutation obligations",
        # THREE sentences where there was one. Wesker's `mutant_disposition` distinguishes these
        # deliberately — "each answers a question the later ones presuppose" — and Detective
        # collapsed them back into "the harness failed", which is true of the first and false of
        # the other two. An operator who cannot tell them apart cannot act on any of them (S13).
        "mutant_construction_failed": "one or more mutants could not be BUILT, so they say nothing"
        " about any test — this measures the engine, not your suite; it is a defect to report, not"
        " a gap to close",
        "mutant_not_installed": "one or more mutants were built but never bound at any call site,"
        " so their survival is a PATCH blind spot rather than a specification gap — a target hidden"
        " behind a wrapper with no __code__ (lru_cache, partial, a decorator) lands here; unwrap it"
        " or pin the wrapped callable directly",
        # One sentence per not-entered CAUSE (#77). The single sentence named "the decorator/registry
        # capture" for every cause, on plain functions with neither; each now names its own repair,
        # and a captured copy is stated as what it is — a floor with its reason, not a suite gap.
        "mutant_not_entered_not_reached": "one or more mutants were installed but no consulted test"
        " calls this function by any route — every test that ran against them was traced in full and"
        " none executed a line of it — so their survival is a REACH gap, not a specification verdict;"
        " write a test that calls the function (converge writes one)",
        "mutant_not_entered_decorator_wrapper": "one or more mutants were installed but the consulted"
        " tests reach the function through a decorator's WRAPPER, which calls the original from inside"
        " its closure; the install rebinds module names, never the closure, so no test through that"
        " wrapper can enter a mutant — a floor of this measurement, not a gap in your suite: pin the"
        " undecorated callable (its __wrapped__) directly, or measure the wrapper's caller",
        "mutant_not_entered_captured_at_import": "one or more mutants were installed but the consulted"
        " tests reach the function through a copy CAPTURED at import — a module-level constant,"
        " registry, container, field, default argument or partial holding the original; the install"
        " replaces only module attributes, never the captured copy, so no test calling through it can"
        " enter a mutant — a floor of this measurement with this reason, not a gap in your suite: to"
        " measure them, call the function through its module attribute (module.fn(...)) in a test",
        "mutant_not_entered_pre_bound_reference": "one or more mutants were installed but the consulted"
        " tests reach the function through an ALIAS — a module binds the original under another name"
        " (from m import fn as alias), and the install rebinds by NAME, so callers through the alias run"
        " the original; call the function by its own name in a test (import m; m.fn(...)), or pin the"
        " alias's caller",
        "mutant_not_entered_holder_not_found": "one or more mutants were installed and the consulted"
        " tests reached the function on the baseline, yet none entered a mutant and no module-level"
        " holder of the original was found — the reference lives where the bounded scan does not look"
        " (a closure, an instance, a local); call the function through its module attribute in a test,"
        " or pin the caller that holds it",
        "mutant_not_entered_no_reach_data": "one or more mutants were installed but never entered, no"
        " holder of the original was found, and no test that ran against them has a complete baseline"
        " trace (one cut by its budget, a thread that outlived its test, or a child process the tracer"
        " cannot follow), so whether any of them reaches the function is UNKNOWN, not negative —"
        " re-measure with --trace-budget 0 if a trace was cut, otherwise call the function in-process"
        " from a test",
        "mutant_not_entered": "one or more mutants were installed but no test ever called them, and the"
        " engine named no cause, so their survival measures REACH, not specification — route a test"
        " through the function's module attribute (module.fn(...)), or pin its caller",
        "engine_refused_unspecified": "the engine refused to gate this measurement without naming a reason",
    }.get(reason, f"an unrecognised engine refusal ({reason})")


@dataclasses.dataclass(frozen=True)
class MeasurementValidity:
    """The normalized, versioned verdict on one measurement's usability.

    Frozen: a validity that can be edited after the fact is not a verdict, and the absorbing
    rule is only meaningful if nothing downstream can relax it.
    """

    schema_version: int = MEASUREMENT_VALIDITY_SCHEMA
    gateable: bool = True
    engine_reports_gateable: bool = False
    cut_reasons: tuple[str, ...] = ()
    containment_status: str = "unreported"
    coverage_depth: str = "unreported"
    execution_mode: str = "in_process"
    engine_version: str = ""
    capability_flags: tuple[str, ...] = ()
    policy_id: str = ""
    shape_hazards: tuple[dict, ...] = ()
    # Per not-entered cause: its reason, mutants, and the holders of the original Wesker named, with
    # where they live (`not_entered_detail`, #77). The cause codes alone cannot say WHERE.
    not_entered: tuple[dict, ...] = ()

    @property
    def admits_certificate(self) -> bool:
        """Whether a certificate may rest on this. Absorbing: any reason at all refuses."""
        return self.gateable and not self.cut_reasons


_ABSENT = object()


def _unscored_by(result: object, disposition: str) -> bool:
    """Did ANY category leave a mutant unscored for this specific Wesker disposition.

    One disposition per call, never a set. The three that matter — ``harness_error``,
    ``not_installed``, ``not_entered`` — were read as a single `any(...)` over all three, which
    is what collapsed them into one flag and one sentence (S13). Reading them apart is the whole
    repair; a helper that took a tuple would invite the collapse straight back.

    Absent `per_category` (an older engine) reads False rather than fabricating a failure — the
    same absence-is-not-falsehood rule the adapter applies to every other field.
    """
    return any(
        bool(getattr(category, "unscored_by", {}).get(disposition, 0))
        for category in (getattr(result, "per_category", ()) or ())
    )


def _unrecognised_unscored(result: object) -> bool:
    """Did any category leave a mutant unscored for a disposition this version does not know.

    A known reason standing beside an unknown disposition used to hide it: the unknown reached no
    reason of its own, and `engine_refused_unspecified` fires only when no other reason exists.
    """
    return any(
        disposition not in _KNOWN_UNSCORED and bool(count)
        for category in (getattr(result, "per_category", ()) or ())
        for disposition, count in (getattr(category, "unscored_by", {}) or {}).items()
    )


# The engine fields this adapter reads, IN THE ORDER `capability_flags` reports them absent. One
# list, so the read and the "which did the engine not supply?" answer cannot fall out of step —
# they were a chain of six reads and a parallel chain of six ifs, which is two places to edit.
_ADAPTED_FIELDS: tuple[str, ...] = (
    "is_gateable",
    "coverage_depth",
    "collection_conflicts",
    "all_contained",
    "collection_errors",
    "execution_mode",
)


def _containment_status(contained_raw: object) -> str:
    """`unreported` when the engine did not say, `unknown` when explicitly None — never folded into
    `uncontained`, since "it did not contain the run", "it could not establish containment", and
    "it did not tell us" are different facts about the measurement."""
    if contained_raw is _ABSENT:
        return "unreported"
    if contained_raw is None:
        return "unknown"
    return "contained" if contained_raw else "uncontained"


def normalize_validity(
    result: object, engine_version: str = "", load_failed: bool = False, routing_failed: bool = False
) -> MeasurementValidity:
    """Adapt a Wesker profiling result into ONE Detective validity object.

    ``load_failed`` is supplied by the caller, not read off ``result``, because it is not a
    Wesker fact: the engine profiles fine (mutants are generated from the AST without importing
    anything), and the import failure is only discovered later, by Detective's own
    ``classify_survivors``. It rides here — beside ``engine_version``, the other non-result
    input — so the ONE validity object carries it and every consumer reads the same refusal.
    Before this, `audit` ANDed a local ``not _load_failed`` into its own completeness while
    `converge` had no equivalent, so the same measurement was ungateable on one surface and
    clean on the other. Defaults False: a caller that does not know keeps the previous behaviour
    exactly (#60).

    ROUTING (#91) is Detective's own fact too, and it arrives two ways. The profile names its own
    failure ON the result — ``routing_outcome``, the code `engine.routing_outcome` decided — and it is
    consumed here, so every consumer of one measurement reads one refusal. The capture harvest's
    failure is found later, by classification, so it rides in beside ``load_failed`` as
    ``routing_failed``. Either cuts the run: no test was authorised, so nothing was observed. An
    absent ``routing_outcome`` (a cache hit — a cut run is never stored — or a foreign result) says
    nothing failed, the same no-information default as ``load_failed``.

    THE ADAPTER IS THE CAPABILITY MATRIX. Each field is read with an explicit absent-sentinel so
    "the engine did not report this" is distinguishable from "the engine reported a falsy value"
    — the distinction that a plain ``getattr(x, name, False)`` destroys, and that #60 requires be
    an explicit compatibility decision rather than an assumption.

    Every field the engine could not supply is named in ``capability_flags``, so a certificate
    can state which parts of its validity were OBSERVED and which were merely not contradicted.
    """
    # Read every adapted field ONCE, keeping the absent-sentinel intact, so the "did the engine
    # report this?" question is asked in one place instead of six near-identical branches — and the
    # capability list below is derived from the same dict rather than a parallel chain of ifs that
    # could fall out of step with it.
    raw = {name: getattr(result, name, _ABSENT) for name in _ADAPTED_FIELDS}

    reports_gateable = raw["is_gateable"] is not _ABSENT
    gateable = bool(raw["is_gateable"]) if reports_gateable else True

    depth = str(raw["coverage_depth"]) if raw["coverage_depth"] is not _ABSENT else "unreported"

    conflicts_raw = raw["collection_conflicts"]
    identity_ambiguous = bool(conflicts_raw) if conflicts_raw is not _ABSENT else False

    containment = _containment_status(raw["all_contained"])

    # Collection completeness (the test FLOOR). Tests that failed to COLLECT (an import error — a
    # torch dep, a broken conftest) are SILENTLY absent from the routed suite, so a mutant only that
    # file's tests would kill reads as candidate-equivalent and the COMPLETE claim is unsafe. The
    # engine reports the erroring test node-ids; a non-empty list cuts the run. Same absent-sentinel
    # as the others: an older engine that does not report it is flagged absent, never a fabricated
    # "collection was complete".
    collection_errors_raw = raw["collection_errors"]
    collection_incomplete = bool(collection_errors_raw) if collection_errors_raw is not _ABSENT else False

    # The engine's own execution mode (in_process / isolated). The field defaults to "in_process",
    # so an UNREAD isolated run is silently mislabeled as in-process — a false description of how the
    # measurement ran. Read with the same absent-sentinel as the others: an older engine that does
    # not report it keeps the default AND is flagged absent, never a fabricated "in_process".
    execution_mode_raw = raw["execution_mode"]
    execution_mode = str(execution_mode_raw) if execution_mode_raw is not _ABSENT else "in_process"

    # Declaration order is `_ADAPTED_FIELDS`' order, which is what `capability_flags` serialises.
    missing = [name for name in _ADAPTED_FIELDS if raw[name] is _ABSENT]

    # Shared interpreter state can change scored obligations as well as counts. The
    # approximate label is advisory; converge's independent isolated observation is
    # the certificate gate. Isolation contains execution but does not decide arbitrary
    # determinism or equivalence, and recycled workers need not be fresh per mutant.
    approximate = ["approximate:mutant_universe"] if execution_mode == "in_process" else []

    fast_mode_raw = getattr(result, "fast_mode", _ABSENT)
    fast_mode = str(fast_mode_raw) if fast_mode_raw is not _ABSENT else ""
    shape_hazards = tuple(getattr(result, "shape_hazards", ()) or ())

    # The causes Wesker named for its not-entered mutants (#77): `not_entered_causes` is derived from
    # `unscored_records`, so a cache hit recomputes it. Absent (an engine before Wesker#18) leaves the
    # cause-free reason, never a guessed mechanism.
    causes_raw = getattr(result, "not_entered_causes", _ABSENT)
    not_entered_causes = (
        tuple(sorted(c for c, n in causes_raw.items() if n)) if isinstance(causes_raw, dict) else ()
    )

    reasons = measurement_cut_reasons(
        reported_gateable=reports_gateable,
        gateable=gateable,
        budget_exhausted=bool(getattr(result, "budget_exhausted", False)),
        coverage_depth=depth,
        containment=containment,
        identity_ambiguous=identity_ambiguous,
        collection_incomplete=collection_incomplete,
        construction_failed=_unscored_by(result, "harness_error"),
        not_installed=_unscored_by(result, "not_installed"),
        not_entered=_unscored_by(result, "not_entered"),
        target_load_failed=bool(load_failed),
        # `engine.ROUTING_FAILED` — the outcome code is this module's cut reason by the same name.
        routing_failed=bool(routing_failed) or getattr(result, "routing_outcome", "") == "routing_failed",
        step_budget_exceeded=_unscored_by(result, "diverged"),
        mutant_wall_undetermined=_unscored_by(result, "undetermined"),
        fast_mode=fast_mode,
        shape_hazards=shape_hazards,
        nondeterministic_baseline=getattr(result, "determinism", "") == "nondeterministic",
        nested_measurement=_unscored_by(result, "nested_measurement"),
        unrecognised_unscored=_unrecognised_unscored(result),
        not_entered_causes=not_entered_causes,
        write_outside_authority=_unscored_by(result, "write_outside_authority"),
    )
    return MeasurementValidity(
        gateable=gateable,
        engine_reports_gateable=reports_gateable,
        cut_reasons=reasons,
        containment_status=containment,
        coverage_depth=depth,
        execution_mode=execution_mode,
        engine_version=engine_version,
        capability_flags=tuple([f"absent:{name}" for name in missing] + approximate),
        policy_id=str(getattr(result, "policy_id", "") or ""),
        shape_hazards=shape_hazards,
        not_entered=not_entered_detail(getattr(result, "unscored_records", None) or ()),
    )
