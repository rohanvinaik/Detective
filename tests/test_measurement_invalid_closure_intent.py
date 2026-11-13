"""Intent tests for the `measurement_invalid` repair — a status that prescribed a loop.

Design: `docs/CORRECTNESS_REPAIRS_2026-09-08.md` §S4/§S5/§S15. Written from intent, not from the
code, and paired with `test_behavior_status_intent.py`'s truth table (which pins the decision) and
`test_certificates_intent.py` (which pins the record shape).

THE DEFECT. `certificate_standing` produces five codes; `certify._TERMINAL_STANDINGS` admitted
three. `stale` and `ungateable` were excluded correctly — an invalid measurement asserts nothing
about the definition — but exclusion is not representation, and with no state of their own they
fell through into codes that describe an ABSENCE. Measured on this repo, 2026-09-08, five
`ungateable` certificates:

    converge_next_action        ungateable -> unpinned            ("no certificate ever")
    line_gap_why                ungateable -> pinned_unverified   ("re-converge to find out")
    repair_measurement_route    ungateable -> unpinned
    survey_disposition          ungateable -> unpinned
    measurement_cut_reasons     ungateable -> pinned_unverified

Both codes are false where they land: a certificate exists, and for `ungateable` the answer is
already recorded. The consequence is not a mislabel, it is a LOOP —
`plan` -> `admission_reason` -> `next_move` -> `next_command` -> `detective converge '<region>'`,
and converge is what produced the `ungateable` in the first place. All five are functions the
running Detective calls while profiling itself (S15), so no re-run can change any of them.

That loop is not new. `certificates.py`'s own docstring records it being closed once already, for
a different standing: a `complete` run that wrote no synth read `unpinned`, "an over-refusal that
would send the best-pinned functions to `converge` forever, since converging them again writes
nothing again". The ledger exists because of it. `ungateable` reopened it through the reader.

WHAT IS NOT WRONG, and was checked before changing anything: `admission_reason` is honest — only
`pinned` is admissible and every exclusion is named. The gate never lied. The PRESCRIPTION looped.

AND WHAT I GOT WRONG FIRST, recorded because the correction is the point: this was filed as "the
`refusal` field is empty on an ungateable record". It is not a defect. `certificate_refusal`'s
docstring scopes that field to disambiguating `incomplete` into `pinned_incomplete` vs `refused`,
and `behavior_status` reads it under exactly that standing. The empty string is contract-conformant.
The field's NAME was read instead of its contract.
"""

from __future__ import annotations

import pytest

from Detective import pins
from Detective.certificates import certificate_cut_reasons, load_certificate, record_certificate
from Detective.certify import behavior_status
from Detective.controller import CONSTRUCTIVE, admission_reason
from Detective.converge import ConvergeResult
from Detective.plan import next_command, next_move
from Detective.validity import MeasurementValidity, measurement_cut_reasons, normalize_validity

# ------------------------------------------------------- the loop, closed (the point of the repair)


def test_measurement_invalid_is_the_one_status_that_does_not_prescribe_converge() -> None:
    """The whole repair, in one assertion. Every other non-pinned status routes to `converge`,
    which `pins.py`'s vocabulary comment states as a rule; this one must not, because converge is
    the command that produced it and repeating it reproduces it."""
    assert next_move(pins.MEASUREMENT_INVALID, "decompose x") == ""
    assert next_command(pins.MEASUREMENT_INVALID, "m.py::f", "decompose x", "split") == ""
    for other in (pins.UNPINNED, pins.PINNED_STALE, pins.PINNED_UNVERIFIED, pins.PINNED_INCOMPLETE):
        assert next_move(other, "decompose x") == "converge", f"{other} still routes to converge"


def test_it_is_named_as_its_own_exclusion_rather_than_falling_to_status_unknown() -> None:
    """`admission_reason` passes a known status through as its own reason and names anything else
    `status_unknown`. A new code that is not in the vocabulary would be admitted as a mystery."""
    assert admission_reason(CONSTRUCTIVE, pins.MEASUREMENT_INVALID, True, True) == "measurement_invalid"
    assert pins.MEASUREMENT_INVALID in pins.BEHAVIOR_STATUSES


def test_it_can_never_arm_a_style_gate() -> None:
    # The ordering law is unchanged by this repair: only `pinned` is admissible.
    assert admission_reason(CONSTRUCTIVE, pins.MEASUREMENT_INVALID, True, True) != "admissible"


# ------------------------------------------------------- stale keeps converge; only its label moves


def test_stale_still_prescribes_converge_because_its_source_settled() -> None:
    """`stale` and `ungateable` are both invalid measurements and they are NOT the same fact. A
    stale run measured a source that moved during the run; the next run measures the settled one,
    so `converge` is right. Only the claim that no record exists was wrong."""
    assert behavior_status("stale", True, False, False, False, False, False) == pins.PINNED_STALE
    assert next_move(pins.PINNED_STALE, "decompose x") == "converge"


# ------------------------------------------------------- the recorded reason (the second half)


@pytest.mark.parametrize(
    ("standing", "reasons", "expected"),
    [
        ("ungateable", ("mutant_not_entered",), ("mutant_not_entered",)),
        (
            "ungateable",
            ("target_load_failed", "coverage_truncated"),
            ("target_load_failed", "coverage_truncated"),
        ),
        ("ungateable", (), ("reason_unrecorded",)),
        ("complete", (), ()),
        ("incomplete", (), ()),
        ("stale", ("budget_exhausted",), ("budget_exhausted",)),
    ],
)
def test_certificate_cut_reasons_names_a_refusal_and_never_an_empty_list(standing, reasons, expected) -> None:
    assert certificate_cut_reasons(standing, reasons) == expected


def test_the_recorded_reason_survives_a_round_trip_through_the_ledger(tmp_path) -> None:
    """End-to-end through the real writer and reader: the remedy S13 named is now legible to
    anyone reading the file, which it was not — the ledger predates that vocabulary."""
    record_certificate(str(tmp_path), "m.py::f", "d1", "ungateable", "", cut_reasons=("mutant_not_entered",))
    assert load_certificate(str(tmp_path), "m.py::f") == {
        "function_digest": "d1",
        "standing": "ungateable",
        "refusal": "",
        "cut_reasons": ["mutant_not_entered"],
    }


def test_the_recorded_tuple_comes_from_the_same_source_the_standing_did() -> None:
    """`admits_certificate` reads `validity.cut_reasons` when validity is present and the flattened
    field when it is not. A recorder that picked its own source would be the sibling that drifts
    the moment those part — the R3 defect. `validity_cut_reasons` mirrors the selection instead."""
    with_validity = ConvergeResult(
        "m.py::f",
        False,
        False,
        0,
        0,
        (),
        "",
        validity=MeasurementValidity(gateable=False, engine_reports_gateable=True, cut_reasons=("a",)),
        cut_reasons=("b",),  # deliberately different: proves WHICH source is read
    )
    assert with_validity.validity_cut_reasons == ("a",)

    without_validity = ConvergeResult("m.py::f", False, False, 0, 0, (), "", cut_reasons=("b",))
    assert without_validity.validity_cut_reasons == ("b",)


# ------------------------------------------------------- the premise the recorded reason rests on


def test_through_the_adapter_a_refusal_always_carries_a_reason() -> None:
    """Why `reason_unrecorded` is a corner and not the common case. `normalize_validity` sets
    `gateable=True` whenever the engine did not report `is_gateable`, so the "refused without
    reporting" state the guard cannot cover is unreachable through it."""

    class _Refusing:
        is_gateable = False
        coverage_depth = "exhaustive"
        all_contained = True

    class _Silent:  # an older engine that reports nothing
        pass

    assert not normalize_validity(_Refusing()).admits_certificate
    assert normalize_validity(_Refusing()).cut_reasons == ("engine_refused_unspecified",)
    assert normalize_validity(_Silent()).admits_certificate, "silence is not a refusal"


def test_but_the_decision_itself_permits_a_silent_refusal_which_is_why_the_corner_is_named() -> None:
    """Measured over all 7680 input combinations: six refuse with an empty tuple, every one of them
    `reported_gateable=False`. Unreachable through the adapter, constructible on a directly-built
    result — which `admits_certificate` explicitly supports. So the recorder names it rather than
    persisting the empty list `measurement_cut_reasons`' own docstring calls "no problems found"."""
    reasons = measurement_cut_reasons(
        reported_gateable=False,
        gateable=False,
        budget_exhausted=False,
        coverage_depth="exhaustive",
        containment="contained",
        identity_ambiguous=False,
    )
    silent = MeasurementValidity(gateable=False, engine_reports_gateable=False, cut_reasons=reasons)
    assert reasons == ()
    assert not silent.admits_certificate
    assert certificate_cut_reasons("ungateable", reasons) == ("reason_unrecorded",)
