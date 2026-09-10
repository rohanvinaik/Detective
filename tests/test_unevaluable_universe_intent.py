"""D5 / U1 — an un-evaluable universe REFUSES; a genuinely empty one stays Incomplete.

THE FOUNDER'S RULING, 2026-09-09, and the distinction IS the decision:

    "It depends on WHY it was un-evaluable. Refuse when the cause is STRUCTURAL; stay Incomplete
    when the universe was genuinely empty of killable mutants."

    | the module would not import; no mutant was installed; no test entered one | REFUSE |
    | the universe genuinely held no killable mutants                           | Incomplete |

    "nothing was observed. A 0-kill here is BLINDNESS, not a result" versus "something WAS measured
    and it found nothing to pin. That is a real, honest answer about the code."

GROUNDED 2026-09-09, AND THE RULING TURNED OUT TO BE THE LIVE BEHAVIOUR ALREADY. U1 was filed
before R1, S13 and §MI landed, and between them they built exactly this:

    R1   made `target_load_failed` a typed cut reason, so a module that never imported cannot
         admit a certificate no matter how clean every other axis reads.
    S13  split `evaluation_failed` into `mutant_construction_failed` / `mutant_not_installed` /
         `mutant_not_entered` — the three STRUCTURAL causes, each now nameable.
    §MI  made them readable from the certificate, and routed `ungateable` to `measurement_invalid`
         rather than to a code meaning "absence".

So `certificate_standing` refuses on ANY cut reason via the absorbing `admits_certificate`, and the
structural causes are all cut reasons. No new standing was needed — which is why `OPEN_ITEMS` §2a's
build note ("do NOT extend `admits_certificate`") pointed the right way and the build it described
was already done.

WHAT WAS ACTUALLY MISSING was a guard. The property held and nothing asserted it, exactly as with
W7's exit codes — a correct behaviour with no test is one edit away from being an incorrect one.
Evidence it holds today, from `tests/detective/certificates.json` rather than from reasoning:
`repair_measurement_route` and `measurement_cut_reasons` both stand `ungateable` carrying
`cut_reasons: ["mutant_not_entered"]`, while `classify_target` stands `incomplete` with none.
"""

from __future__ import annotations

import pytest

from Detective.converge import certificate_standing
from Detective.validity import CUT_REASONS, MeasurementValidity

# The three the ruling names as STRUCTURAL — "nothing was observed" — plus the import failure R1
# added. Each is a different way of failing to look, which is why S13 refused to keep them as one.
_STRUCTURAL = (
    "target_load_failed",
    "mutant_construction_failed",
    "mutant_not_installed",
    "mutant_not_entered",
)


@pytest.mark.parametrize("reason", _STRUCTURAL)
def test_a_structural_cause_refuses_rather_than_reporting_a_gap(reason) -> None:
    """The ruling's first row. A 0-kill under any of these is BLINDNESS, and `incomplete` would send
    the reader to close a gap the numbers never established."""
    v = MeasurementValidity(gateable=True, cut_reasons=(reason,))
    assert v.admits_certificate is False
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


@pytest.mark.parametrize("reason", _STRUCTURAL)
def test_each_structural_cause_is_a_DECLARED_reason(reason) -> None:
    """A refusal whose reason is not in the vocabulary cannot be rendered, routed or recorded — it
    becomes the anonymous `admits_certificate=False` that `measurement_cut_reasons` exists to
    prevent."""
    assert reason in CUT_REASONS


def test_a_genuinely_empty_universe_is_NOT_refused() -> None:
    """The ruling's second row, and the half that keeps this honest rather than merely cautious.
    Nothing was cut; the run looked and found nothing to pin. That is a real answer about the code,
    and refusing it would make "we could not measure" and "there is nothing here" one state — the
    exact collapse this project exists to prevent."""
    v = MeasurementValidity(gateable=True, cut_reasons=())
    assert v.admits_certificate is True
    assert (
        certificate_standing(
            functionally_complete=False,
            line_complete=True,
            stale_target=False,
            verification_ran=False,
            verification_ok=False,
            admits_certificate=v.admits_certificate,
        )
        == "incomplete"
    )


def test_an_empty_universe_with_every_axis_discharged_still_certifies() -> None:
    """A function with nothing killable and full line coverage has been fully specified, not
    under-measured. Refusing here would punish the simplest correct code in the codebase."""
    assert (
        certificate_standing(
            functionally_complete=True,
            line_complete=True,
            stale_target=False,
            verification_ran=False,
            verification_ok=False,
            admits_certificate=True,
        )
        == "complete"
    )


def test_the_refusal_is_absorbing_and_cannot_be_argued_down() -> None:
    """`OPEN_ITEMS` §2a: "the absorbing rule is deliberately absorbing". A structural cause beside
    any amount of good news still refuses — otherwise the reader could point at the good news."""
    v = MeasurementValidity(gateable=True, cut_reasons=("mutant_not_entered", "coverage_truncated"))
    assert v.admits_certificate is False
    assert (
        certificate_standing(True, True, False, True, True, admits_certificate=v.admits_certificate)
        == "ungateable"
    )
