"""Intent test for #60: a measurement the engine calls gateable but which carries a cut reason
must NOT stand COMPLETE.

THE BUG. converge stored ``measurement_gateable=_validity.gateable`` and ``ConvergeResult.complete``
gated the certificate on that raw boolean. ``normalize_validity`` derives ``cut_reasons``
INDEPENDENTLY of ``is_gateable`` (containment, coverage truncation, budget, ambiguous module
identity), so ``gateable=True`` with a non-empty ``cut_reasons`` is reachable — and such a run
printed ✓ COMPLETE, an upstream refusal evaporating at the seam.

THE FIX. ``complete`` consumes ``admits_certificate`` (gateable AND no cut reason), sourced from the
single normalized ``MeasurementValidity`` on the result — absorbing: any reason at all refuses.
"""

from __future__ import annotations

from dataclasses import replace

from Detective.converge import ConvergeResult
from Detective.validity import MeasurementValidity


def _complete_result(**over) -> ConvergeResult:
    base = ConvergeResult(
        function="m.py::f",
        converged=True,
        at_ceiling=False,
        initial_survivors=3,
        final_survivors=0,
        iterations=(),
        written_path="t.py",
        total_mutants=3,
        killed=3,
        functionally_complete=True,
        line_complete=True,
        signature="f(x)",
        param_names=("x",),
    )
    return replace(base, **over) if over else base


def test_admits_certificate_from_validity_is_absorbing():
    assert (
        _complete_result(validity=MeasurementValidity(gateable=True, cut_reasons=())).admits_certificate
        is True
    )
    # gateable, but a cut reason is present -> the certificate is refused (absorbing)
    cut = _complete_result(validity=MeasurementValidity(gateable=True, cut_reasons=("uncontained_worker",)))
    assert cut.admits_certificate is False
    assert (
        _complete_result(validity=MeasurementValidity(gateable=False, cut_reasons=())).admits_certificate
        is False
    )


def test_admits_certificate_fallback_without_a_validity_object():
    # A directly-built result (no validity object — older callers, test construction) still obeys
    # the absorbing rule over the flattened projection fields.
    r = _complete_result(validity=None, measurement_gateable=True, cut_reasons=("budget_exhausted",))
    assert r.admits_certificate is False
    ok = _complete_result(validity=None, measurement_gateable=True, cut_reasons=())
    assert ok.admits_certificate is True


def test_complete_refuses_a_gateable_but_cut_run():
    # THE bug end-to-end: functionally + line complete, no failed verification, engine says
    # gateable=True — but a cut reason is present. Before #60 this stood COMPLETE; now it must not.
    cut = _complete_result(validity=MeasurementValidity(gateable=True, cut_reasons=("coverage_truncated",)))
    assert cut.complete is False
    assert _complete_result(validity=MeasurementValidity(gateable=True, cut_reasons=())).complete is True
