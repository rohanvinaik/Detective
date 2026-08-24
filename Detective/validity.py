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
MEASUREMENT_VALIDITY_SCHEMA = 1

# Every typed reason this module can emit. Exhaustive on purpose: a reason that is not in this
# tuple cannot be rendered consistently across CLI, --json, MCP and receipts, which is the
# requirement that "identical cut reasons" is stated in.
CUT_REASONS: tuple[str, ...] = (
    "budget_exhausted",
    "uncontained_worker",
    "coverage_truncated",
    "sampled_universe",
    "collection_incomplete",
    "ambiguous_module_identity",
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
) -> tuple[str, ...]:
    """Every reason THIS measurement cannot support a certificate (#60, pure — pinned).

    Plural on purpose. A run can be cut for more than one reason at once, and reporting only the
    first makes the second invisible to whoever fixes the first — they re-run, hit the next
    refusal, and have no way to know it was always there.

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
        "budget_exhausted": "the aggregate deadline was exhausted, so the universe was never fully measured",
        "uncontained_worker": "a timed-out worker could not be stopped, so later phases"
        " shared a process with it",
        "coverage_truncated": "the profile was cut before the universe was measured",
        "sampled_universe": "the universe was sampled, not enumerated",
        "collection_incomplete": "one or more test files failed to collect (an import error), so the"
        " routed suite is missing tests the layout implies — fix the collection errors and re-run",
        "ambiguous_module_identity": "the live collection resolved one module name to more than one file",
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


def normalize_validity(result: object, engine_version: str = "") -> MeasurementValidity:
    """Adapt a Wesker profiling result into ONE Detective validity object.

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
    collection_incomplete = (
        bool(collection_errors_raw) if collection_errors_raw is not _ABSENT else False
    )

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

    # In-process mutant EVALUATION shares the target module's mutable state across mutants, so a
    # borderline mutant's SCORED disposition (crash-kill vs unscored) is not reproducible run-to-run
    # — the mutant-universe COUNT / kill% is an in-process ESTIMATE, not an exact figure. This flags
    # the NUMBER, never the specification: the value-kill PROOF the certificate rests on IS exact and
    # deterministic (`certificate_standing` reads killable/unclassified survivors, not the count). The
    # isolated worker (#19) has fresh per-mutant state and is exact, so it is NOT flagged. Found
    # dogfooding python-slugify: total 133 vs 140 at a FIXED hash seed. A consumer reads this to
    # present the universe count as `≈`, never as a precise gateable measurement — and it does NOT
    # refuse the certificate (it is not a cut reason): the proof is gateable, the count is an estimate.
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
