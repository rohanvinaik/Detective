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
# 3: `mutant_evaluation_failed` split into the three dispositions it collapsed —
#    `mutant_construction_failed` / `mutant_not_installed` / `mutant_not_entered` (S13). A changed
#    reason vocabulary is exactly what this number exists to signal.
MEASUREMENT_VALIDITY_SCHEMA = 3

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
    # Wesker's OWN precedence, earliest failed phase first (`engine.mutant_disposition`). These
    # were one reason, `mutant_evaluation_failed`, rendered "the harness failed" — true only of
    # the first. See `cut_reason_sentence` for why the other two are not harness failures at all.
    "mutant_construction_failed",
    "mutant_not_installed",
    "mutant_not_entered",
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
    construction_failed: bool = False,
    not_installed: bool = False,
    not_entered: bool = False,
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
    # THREE reasons, not one. They were collapsed into `mutant_evaluation_failed` and rendered
    # "the harness failed" — which is true of construction and FALSE of the other two: an
    # un-installed mutant means the harness built it fine and the patch could not bind it, and an
    # un-entered mutant means both worked and no test called it. Three causes, three remedies,
    # one sentence that named the first. Wesker's own precedence order (S13).
    if construction_failed:
        reasons.append("mutant_construction_failed")
    if not_installed:
        reasons.append("mutant_not_installed")
    if not_entered:
        reasons.append("mutant_not_entered")
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
        "mutant_not_entered": "one or more mutants were installed but no test ever called them, so"
        " their survival measures REACH, not specification — the namespace holds the mutant while"
        " the caller holds the original (the decorator/registry capture); route a test through the"
        " patched name, or pin the caller",
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
    """`unreported` when the engine did not say — never folded into `uncontained`, since "it did
    not contain the run" and "it did not tell us" are different facts about the measurement."""
    if contained_raw is _ABSENT:
        return "unreported"
    return "contained" if contained_raw else "uncontained"


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
