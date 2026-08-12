"""One authoritative answer to "may this measurement support a certificate?" (issue #60).

Detective reconstructed usability from whichever overlapping signal a given call site happened
to read — `budget_exhausted`, survivor counts, line completeness, `is_gateable`, coverage depth,
containment. So an upstream REFUSAL could be weakened at the integration seam: a result with
`is_gateable=False` and `budget_exhausted=False` was, at several boundaries, indistinguishable
from a clean one.

TWO RULES, and every test here is one of them.

GATEABILITY IS ABSORBING. Downstream may diagnose a refusal, never reconstruct it as a pass.

ABSENCE IS NOT FALSEHOOD. An engine that does not publish a field has not said the measurement
is invalid; it has said nothing. Refusing on that basis breaks every user on a released engine;
assuming support is the unnamed-capability assumption #60 forbids. So the decision is explicit,
recorded in `capability_flags`, and conservative toward preserving prior behaviour.
"""

from __future__ import annotations

from Detective.validity import (
    CUT_REASONS,
    MEASUREMENT_VALIDITY_SCHEMA,
    MeasurementValidity,
    measurement_cut_reasons,
    normalize_validity,
)


class _Result:
    """A stand-in Wesker result. Attributes are set only when the engine reports them, so an
    OLDER engine is modelled by ABSENCE rather than by a falsy value — the distinction the
    adapter exists to preserve."""

    def __init__(self, **fields):
        for key, value in fields.items():
            setattr(self, key, value)


# ── the reasons ──


def test_a_clean_measurement_has_no_reasons():
    assert measurement_cut_reasons(True, True, False, "profiled", "contained", False) == ()


def test_every_reason_is_reported_not_just_the_first():
    """A run cut for two reasons must say both. Reporting only the first makes the second
    invisible to whoever fixes the first: they re-run, hit the next refusal, and cannot tell it
    was there all along."""
    reasons = measurement_cut_reasons(True, False, True, "cut", "uncontained", True)
    assert set(reasons) == {
        "budget_exhausted",
        "uncontained_worker",
        "coverage_truncated",
        "ambiguous_module_identity",
    }


def test_an_unexplained_refusal_is_named_rather_than_returned_empty():
    """THE load-bearing state. The engine says not gateable and nothing we understand explains
    it. An empty reason list beside a refusal reads as 'no problems found' — which is precisely
    how a refusal gets talked past, and the shape this whole issue is about."""
    assert measurement_cut_reasons(True, False, False, "profiled", "contained", False) == (
        "engine_refused_unspecified",
    )


def test_a_future_reason_degrades_to_a_named_unknown_not_a_pass():
    """A Wesker that refuses for a cause this version has never heard of must not read as
    clean."""
    reasons = measurement_cut_reasons(True, False, False, "some_future_depth", "contained", False)
    assert reasons == ("engine_refused_unspecified",)


def test_unspecified_is_not_added_when_a_real_reason_is_known():
    """It is the fallback for an unexplained refusal, not noise on every cut."""
    assert measurement_cut_reasons(True, False, True, "profiled", "contained", False) == ("budget_exhausted",)


def test_an_engine_that_does_not_report_gateability_is_not_treated_as_refusing():
    """Absence is not falsehood. An older engine says nothing, and nothing is not a refusal."""
    assert measurement_cut_reasons(False, True, False, "profiled", "contained", False) == ()


def test_reason_order_is_stable_so_every_surface_agrees():
    """CLI, --json, MCP and receipts must render identical reasons; discovery order would make
    two identically-cut runs differ."""
    a = measurement_cut_reasons(True, False, True, "cut", "uncontained", True)
    b = measurement_cut_reasons(True, False, True, "cut", "uncontained", True)
    assert a == b
    assert list(a) == [r for r in CUT_REASONS if r in set(a)]


def test_sampled_and_truncated_are_different_facts():
    """A sampled universe was never enumerated; a cut one was and stopped. Both bar a
    certificate, for different reasons a reader acts on differently."""
    assert measurement_cut_reasons(True, False, False, "sampled", "contained", False) == ("sampled_universe",)
    assert measurement_cut_reasons(True, False, False, "cut", "contained", False) == ("coverage_truncated",)


def test_every_emitted_reason_is_in_the_declared_vocabulary():
    """A reason outside `CUT_REASONS` cannot be rendered consistently across surfaces."""
    for depth in ("profiled", "cut", "sampled", "unreported"):
        for containment in ("contained", "uncontained", "unreported"):
            for gateable in (True, False):
                got = measurement_cut_reasons(True, gateable, True, depth, containment, True)
                assert set(got) <= set(CUT_REASONS), got


# ── the absorbing rule ──


def test_any_reason_at_all_refuses_a_certificate():
    assert MeasurementValidity(gateable=True, cut_reasons=()).admits_certificate is True
    assert MeasurementValidity(gateable=True, cut_reasons=("budget_exhausted",)).admits_certificate is False
    assert MeasurementValidity(gateable=False, cut_reasons=()).admits_certificate is False


def test_the_object_is_frozen_so_a_refusal_cannot_be_relaxed():
    """The absorbing rule only means something if nothing downstream can edit the verdict."""
    import dataclasses

    import pytest

    validity = MeasurementValidity(gateable=False, cut_reasons=("uncontained_worker",))
    with pytest.raises(dataclasses.FrozenInstanceError):
        validity.gateable = True  # type: ignore[misc]


# ── the adapter / capability matrix ──


def test_a_current_engine_normalizes_to_a_clean_validity():
    validity = normalize_validity(
        _Result(
            is_gateable=True,
            budget_exhausted=False,
            coverage_depth="profiled",
            collection_conflicts=(),
            all_contained=True,
            execution_mode="in_process",
        )
    )
    assert validity.admits_certificate is True
    assert validity.capability_flags == ()
    assert validity.schema_version == MEASUREMENT_VALIDITY_SCHEMA


def test_an_engine_refusal_survives_normalization_with_its_reason():
    validity = normalize_validity(
        _Result(
            is_gateable=False,
            budget_exhausted=False,
            coverage_depth="cut",
            collection_conflicts=(),
            all_contained=False,
        )
    )
    assert validity.admits_certificate is False
    assert set(validity.cut_reasons) == {"uncontained_worker", "coverage_truncated"}


def test_the_regression_requirement_verbatim():
    """`is_gateable=False`, `budget_exhausted=False` cannot produce a usable measurement — the
    exact combination the old proxy admitted."""
    validity = normalize_validity(_Result(is_gateable=False, budget_exhausted=False))
    assert validity.admits_certificate is False
    assert validity.cut_reasons  # and it says why, rather than refusing mutely


def test_an_older_engine_names_every_field_it_could_not_supply():
    """The compatibility decision is EXPLICIT: absent capabilities are recorded, so a certificate
    can state which parts of its validity were observed and which were merely not contradicted."""
    validity = normalize_validity(_Result(budget_exhausted=False))
    assert validity.engine_reports_gateable is False
    assert set(validity.capability_flags) == {
        "absent:is_gateable",
        "absent:coverage_depth",
        "absent:collection_conflicts",
        "absent:all_contained",
        "absent:execution_mode",
    }


def test_an_older_engine_is_not_refused_merely_for_being_older():
    """Refusing on absence would break every user on a released engine."""
    validity = normalize_validity(_Result(budget_exhausted=False))
    assert validity.admits_certificate is True


def test_an_older_engine_that_blew_its_budget_is_still_refused():
    """Conservative compatibility is not blanket trust: the signals an old engine DOES report
    are still consumed."""
    validity = normalize_validity(_Result(budget_exhausted=True))
    assert validity.admits_certificate is False
    assert "budget_exhausted" in validity.cut_reasons


def test_an_ambiguous_collection_identity_refuses_even_when_counts_are_clean():
    """#58's shadowed-collection condition: the counts may be perfectly measured and still be
    about the wrong copy of the code."""
    validity = normalize_validity(
        _Result(
            is_gateable=False,
            budget_exhausted=False,
            coverage_depth="profiled",
            collection_conflicts=("pkg.mod",),
            all_contained=True,
        )
    )
    assert validity.admits_certificate is False
    assert "ambiguous_module_identity" in validity.cut_reasons


# ── execution mode: how the measurement ran, described honestly, never assumed ──


def test_a_reported_isolated_run_is_recorded_as_isolated_not_the_default():
    """The #7 defect: ``MeasurementValidity.execution_mode`` defaults to ``"in_process"`` and the
    adapter never read it — so an ISOLATED measurement was silently described as in-process, a false
    claim about how it ran. A reported mode must reach the validity object. Fails before the fix
    (the default stood)."""
    validity = normalize_validity(_Result(is_gateable=True, execution_mode="isolated"))
    assert validity.execution_mode == "isolated"
    assert "absent:execution_mode" not in validity.capability_flags


def test_a_reported_in_process_run_is_a_positive_observation_not_the_default():
    """Reported ``"in_process"`` and UNREPORTED both surface as the string ``"in_process"``; only
    ``capability_flags`` tells them apart, which is the whole point of the absent-sentinel. A
    reported mode is observed, so it is NOT flagged absent."""
    validity = normalize_validity(_Result(is_gateable=True, execution_mode="in_process"))
    assert validity.execution_mode == "in_process"
    assert "absent:execution_mode" not in validity.capability_flags


def test_an_engine_that_omits_execution_mode_keeps_the_default_and_is_flagged():
    """Absence is not falsehood: an engine that does not publish ``execution_mode`` keeps the
    conservative ``"in_process"`` default AND is named in ``capability_flags``, so a certificate can
    state the mode was not observed rather than fabricated as in-process."""
    validity = normalize_validity(_Result(is_gateable=True))
    assert validity.execution_mode == "in_process"
    assert "absent:execution_mode" in validity.capability_flags
