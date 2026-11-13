"""Intent: Wesker#27 / Detective#80 — a certificate says WHY a measurement could not support it.

The defect, verbatim from the issue: "the certificate `standing` is the generic `ungateable` for both
`undetermined` and `diverged`". The cut reasons already told them apart (`step_budget_exceeded` /
`mutant_wall_undetermined`), but the standing is what every surface reads first, and two states whose
remedies differ must not share a sign: a mutant the loop budget stopped is deterministic and for good
(no input or flag applies); a mutant whose liveness wall fired is machine-bound (raise the compute
budget, or measure on a quieter machine).

`ungateable` stays the standing of every other refusal, and of a refusal that records no reason: a
standing is narrowed only by a reason that was recorded, never by a guess.
"""

from __future__ import annotations

import dataclasses

import pytest

from Detective.certificates import (
    UNGATEABLE_STANDINGS,
    certificate_cut_reasons,
    load_certificate,
    record_certificate,
)
from Detective.certify import behavior_status
from Detective.cli import converge_exit_code, converge_next_action
from Detective.converge import ConvergeResult, certificate_standing, ungateable_standing
from Detective.pins import MEASUREMENT_INVALID

DIVERGED = "step_budget_exceeded"
UNDETERMINED = "mutant_wall_undetermined"


@pytest.mark.parametrize(
    ("reasons", "expected"),
    [
        ((DIVERGED,), "mutants_diverged"),
        ((UNDETERMINED,), "mutants_undetermined"),
        ((DIVERGED, UNDETERMINED), "mutants_diverged_and_undetermined"),
        ((UNDETERMINED, DIVERGED), "mutants_diverged_and_undetermined"),
        # Anything else in the reasons keeps the umbrella: the run has a cause no mutant explains.
        ((DIVERGED, "uncontained_worker"), "ungateable"),
        ((UNDETERMINED, "budget_exhausted"), "ungateable"),
        (("uncontained_worker",), "ungateable"),
        # Absence is not a value: no recorded reason narrows nothing.
        ((), "ungateable"),
    ],
)
def test_the_standing_is_named_by_the_reasons_the_measurement_was_refused_with(reasons, expected):
    assert ungateable_standing(reasons) == expected


def test_the_two_states_never_share_a_sign():
    assert len({ungateable_standing((DIVERGED,)), ungateable_standing((UNDETERMINED,)), "ungateable"}) == 3


def test_certificate_standing_consumes_the_reasons():
    args = (True, True, False, False, False)
    assert (
        certificate_standing(*args, admits_certificate=False, cut_reasons=(DIVERGED,)) == "mutants_diverged"
    )
    assert (
        certificate_standing(*args, admits_certificate=False, cut_reasons=(UNDETERMINED,))
        == "mutants_undetermined"
    )
    # no reasons passed: exactly the standing it always was
    assert certificate_standing(*args, admits_certificate=False) == "ungateable"
    # a measurement that admits a certificate is untouched by reasons that name per-mutant causes
    assert certificate_standing(*args, admits_certificate=True, cut_reasons=(DIVERGED,)) == "complete"
    # stale outranks, as it always did
    assert certificate_standing(True, True, True, False, False, False, cut_reasons=(DIVERGED,)) == "stale"


def _result(**overrides) -> ConvergeResult:
    base = ConvergeResult(
        function="m.py::f",
        converged=True,
        at_ceiling=False,
        initial_survivors=[],
        final_survivors=[],
        iterations=1,
        written_path="",
        total_mutants=10,
        killed=8,
    )
    fields = {"functionally_complete": True, "line_complete": True, **overrides}
    return dataclasses.replace(base, **fields)


def test_a_converge_result_reports_the_named_standing():
    diverged = _result(measurement_gateable=False, cut_reasons=(DIVERGED,))
    undetermined = _result(measurement_gateable=False, cut_reasons=(UNDETERMINED,))
    assert diverged.standing == "mutants_diverged"
    assert undetermined.standing == "mutants_undetermined"
    assert not diverged.complete and not undetermined.complete


def test_the_certificate_file_records_the_named_standing_and_its_reason(tmp_path):
    for reasons, standing in (((DIVERGED,), "mutants_diverged"), ((UNDETERMINED,), "mutants_undetermined")):
        result = _result(measurement_gateable=False, cut_reasons=reasons)
        record_certificate(
            str(tmp_path),
            f"m.py::{standing}",
            "d1",
            result.standing,
            "",
            cut_reasons=certificate_cut_reasons(result.standing, result.validity_cut_reasons),
        )
        assert load_certificate(str(tmp_path), f"m.py::{standing}") == {
            "function_digest": "d1",
            "standing": standing,
            "refusal": "",
            "cut_reasons": list(reasons),
        }


def test_every_ungateable_standing_is_still_an_invalid_measurement_everywhere():
    for standing in UNGATEABLE_STANDINGS:
        assert converge_exit_code(standing) == 3
        assert converge_next_action(standing, "", False, False) == "repair_measurement"
        assert behavior_status(standing, True, False, False, False, False, False) == MEASUREMENT_INVALID
    # and the standings that are not invalid measurements are not swept in
    assert converge_exit_code("complete") == 0
    assert converge_exit_code("floor_failing") == 1
