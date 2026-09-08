"""Intent tests for the reproducibility gate (Finding B, revalidation_2026-09-06.md).

The defect [HIGH]: converge claimed ✓ COMPLETE while audit's fresh profile said "N killable" and the
two never reconciled — the in-process mutant universe's borderline dispositions (crash-kill vs
value-survivor) wobble under shared module state, so a COMPLETE resting on candidate-equivalents is not
reproducible. Founder ruling: the in-process scoring is an EFFICIENCY hack; where it cannot be trusted,
converge must REFUSE, not auto-apply. These pin, from intent: the gate fires only where a wobble can
flip the verdict; a survivor-set mismatch reads nonreproducible; and a nonreproducible run REFUSES the
certificate (via the existing cut-reason machinery) and routes to isolated measurement.
Semantic flags resolve equivalence claims; they cannot repair measurement invalidity.
"""

from __future__ import annotations

import types

from Detective.cli import _converge_action, repair_measurement_route
from Detective.converge import (
    certificate_standing,
    reproducibility_verdict,
    should_verify_reproducibility,
)
from Detective.validity import CUT_REASONS, MeasurementValidity, cut_reason_sentence

# ------------------------------------------------------------------ the pure gate + verdict


def test_every_shared_state_certificate_needs_verification():
    assert should_verify_reproducibility("in_process", True, True) is True
    assert should_verify_reproducibility("in_process", True, False) is True
    assert should_verify_reproducibility("isolated", True, True) is False
    assert should_verify_reproducibility("in_process", False, True) is False
    assert should_verify_reproducibility("unknown", True, False) is True


def test_the_verdict_is_set_equality_over_the_survivor_ids():
    assert reproducibility_verdict(("m1", "m2"), ("m2", "m1")) == "reproducible"  # order-independent
    assert reproducibility_verdict((), ()) == "reproducible"
    # A borderline mutant flipped in/out of the survivor set between the two profiles.
    assert reproducibility_verdict(("m1",), ("m1", "m2")) == "nonreproducible"


# ------------------------------------------------------------------ the refusal chain (validity -> standing)


def test_the_reason_is_a_declared_cut_reason_with_an_actionable_sentence():
    assert "nonreproducible_in_process" in CUT_REASONS
    s = cut_reason_sentence("nonreproducible_in_process")
    assert s and "nonreproducible_in_process" not in s  # a sentence, not the raw code
    assert "isolated" in s  # a semantic flag cannot repair invalid measurement


def test_a_nonreproducible_validity_refuses_the_certificate():
    v = MeasurementValidity(gateable=True, cut_reasons=("nonreproducible_in_process",))
    # Absorbing: a gateable engine answer carrying this reason still cannot support a certificate.
    assert v.admits_certificate is False
    # certificate_standing reads that and returns ungateable — so ✓ COMPLETE cannot stand.
    assert (
        certificate_standing(
            functionally_complete=True,
            line_complete=True,
            stale_target=False,
            verification_ran=False,
            verification_ok=False,
            admits_certificate=v.admits_certificate,
        )
        == "ungateable"
    )


# ------------------------------------------------------------------ routing + render


def test_the_route_names_reprofile_and_outranks_a_trace_budget_catch_all():
    assert repair_measurement_route(("nonreproducible_in_process",), False, False) == "reprofile"
    # A run cut BOTH ways: the non-reproducibility (a real soundness issue) outranks a trace-budget cut.
    assert (
        repair_measurement_route(("nonreproducible_in_process", "coverage_truncated"), False, False)
        == "reprofile"
    )


def _reprofile_result():
    return types.SimpleNamespace(
        function="m.py::f",
        functionally_complete=False,
        verification=None,
        line_complete=True,
        missing_lines=(),
        stale_target=False,
        admits_certificate=False,
        written_path="w.py",
        cut_reasons=("nonreproducible_in_process",),
        collection_conflicts=(),
        budget_exhausted=False,
    )


def test_the_render_routes_invalid_measurement_to_isolation():
    out = "\n".join(_converge_action(_reprofile_result(), None))
    assert "STOP:" in out
    assert "detective converge" in out and "--isolated" in out
    assert "detective flag" not in out
    assert "--trace-budget" not in out
    assert "--deadline 0" not in out
