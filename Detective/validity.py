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
"""

from __future__ import annotations

import dataclasses

# Bumped when the MEANING of a field changes, so a stored receipt cannot be read under a
# different contract than the one that produced it. Additive fields do not require a bump;
# a changed reason vocabulary does.
MEASUREMENT_VALIDITY_SCHEMA = 2

# Every typed reason this module can emit. Exhaustive on purpose: a reason that is not in this
# tuple cannot be rendered consistently across CLI, --json, MCP and receipts, which is the
# requirement that "identical cut reasons" is stated in.
CUT_REASONS: tuple[str, ...] = (
    "target_load_failed",
    "budget_exhausted",
    "uncontained_worker",
    "coverage_truncated",
    "sampled_universe",
    "collection_incomplete",
    "ambiguous_module_identity",
    "nonreproducible_in_process",
    "invalid_verification",
    "cached_verification",
    "unknown_verification_basis",
    "verification_basis_changed",
    "verification_failed",
    "verification_universe_changed",
    "mutant_evaluation_failed",
    "engine_refused_unspecified",
)


def measurement_cut_reasons(
    reported_gateable: bool,
    gateable: bool,
    budget_exhausted: bool,
    coverage_depth: str,
    containment: str,
    identity_ambiguous: bool,
    collection_incomplete: bool = False,
    evaluation_failed: bool = False,
    target_load_failed: bool = False,
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
    """
    reasons: list[str] = []
    if target_load_failed:
        reasons.append("target_load_failed")
    if budget_exhausted:
        reasons.append("budget_exhausted")
    if containment == "uncontained":
        reasons.append("uncontained_worker")
    if coverage_depth == "cut":
        reasons.append("coverage_truncated")
    elif coverage_depth == "sampled":
        reasons.append("sampled_universe")
    if collection_incomplete:
        reasons.append("collection_incomplete")
    if identity_ambiguous:
        reasons.append("ambiguous_module_identity")
    if evaluation_failed:
        reasons.append("mutant_evaluation_failed")
    if reported_gateable and not gateable and not reasons:
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
        "budget_exhausted": "the aggregate deadline was exhausted, so the universe was never fully measured",
        "uncontained_worker": "a timed-out worker could not be stopped, so later phases"
        " shared a process with it",
        "coverage_truncated": "the profile was cut before the universe was measured",
        "sampled_universe": "the universe was sampled, not enumerated",
        "collection_incomplete": "one or more test files failed to collect (an import error), so the"
        " routed suite is missing tests the layout implies — fix the collection errors and re-run",
        "ambiguous_module_identity": "the live collection resolved one module name to more than one file",
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
        "mutant_evaluation_failed": "one or more mutations could not be evaluated "
        "because the harness failed; repair the measurement before claiming adequacy",
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

    @property
    def admits_certificate(self) -> bool:
        """Whether a certificate may rest on this. Absorbing: any reason at all refuses."""
        return self.gateable and not self.cut_reasons


_ABSENT = object()


def normalize_validity(
    result: object, engine_version: str = "", load_failed: bool = False
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

    THE ADAPTER IS THE CAPABILITY MATRIX. Each field is read with an explicit absent-sentinel so
    "the engine did not report this" is distinguishable from "the engine reported a falsy value"
    — the distinction that a plain ``getattr(x, name, False)`` destroys, and that #60 requires be
    an explicit compatibility decision rather than an assumption.

    Every field the engine could not supply is named in ``capability_flags``, so a certificate
    can state which parts of its validity were OBSERVED and which were merely not contradicted.
    """
    gateable_raw = getattr(result, "is_gateable", _ABSENT)
    reports_gateable = gateable_raw is not _ABSENT
    gateable = bool(gateable_raw) if reports_gateable else True

    depth_raw = getattr(result, "coverage_depth", _ABSENT)
    depth = str(depth_raw) if depth_raw is not _ABSENT else "unreported"

    conflicts_raw = getattr(result, "collection_conflicts", _ABSENT)
    identity_ambiguous = bool(conflicts_raw) if conflicts_raw is not _ABSENT else False

    contained_raw = getattr(result, "all_contained", _ABSENT)
    if contained_raw is _ABSENT:
        containment = "unreported"
    else:
        containment = "contained" if contained_raw else "uncontained"

    # Collection completeness (the test FLOOR). Tests that failed to COLLECT (an import error — a
    # torch dep, a broken conftest) are SILENTLY absent from the routed suite, so a mutant only that
    # file's tests would kill reads as candidate-equivalent and the COMPLETE claim is unsafe. The
    # engine reports the erroring test node-ids; a non-empty list cuts the run. Same absent-sentinel
    # as the others: an older engine that does not report it is flagged absent, never a fabricated
    # "collection was complete".
    collection_errors_raw = getattr(result, "collection_errors", _ABSENT)
    collection_incomplete = bool(collection_errors_raw) if collection_errors_raw is not _ABSENT else False

    # The engine's own execution mode (in_process / isolated). The field defaults to "in_process",
    # so an UNREAD isolated run is silently mislabeled as in-process — a false description of how the
    # measurement ran. Read with the same absent-sentinel as the others: an older engine that does
    # not report it keeps the default AND is flagged absent, never a fabricated "in_process".
    execution_mode_raw = getattr(result, "execution_mode", _ABSENT)
    execution_mode = str(execution_mode_raw) if execution_mode_raw is not _ABSENT else "in_process"

    missing: list[str] = []
    if not reports_gateable:
        missing.append("is_gateable")
    if depth_raw is _ABSENT:
        missing.append("coverage_depth")
    if conflicts_raw is _ABSENT:
        missing.append("collection_conflicts")
    if contained_raw is _ABSENT:
        missing.append("all_contained")
    if collection_errors_raw is _ABSENT:
        missing.append("collection_errors")
    if execution_mode_raw is _ABSENT:
        missing.append("execution_mode")

    # Shared interpreter state can change scored obligations as well as counts. The
    # approximate label is advisory; converge's independent isolated observation is
    # the certificate gate. Isolation contains execution but does not decide arbitrary
    # determinism or equivalence, and recycled workers need not be fresh per mutant.
    approximate: list[str] = []
    if execution_mode == "in_process":
        approximate.append("approximate:mutant_universe")

    reasons = measurement_cut_reasons(
        reported_gateable=reports_gateable,
        gateable=gateable,
        budget_exhausted=bool(getattr(result, "budget_exhausted", False)),
        coverage_depth=depth,
        containment=containment,
        identity_ambiguous=identity_ambiguous,
        collection_incomplete=collection_incomplete,
        evaluation_failed=any(
            bool(getattr(category, "unscored_by", {}).get(reason, 0))
            for category in (getattr(result, "per_category", ()) or ())
            for reason in ("harness_error", "not_installed", "not_entered")
        ),
        target_load_failed=bool(load_failed),
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
    )
