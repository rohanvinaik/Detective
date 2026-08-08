"""A certificate must name the evidence it stood on (issue #59).

`✓ COMPLETE` required every executable line to be covered, and judged that from the OBSERVED
union — which includes tests that FAIL against the unmutated program. Such a test is already
barred from kill attribution, because it cannot distinguish a mutant from correct code; its
coverage nonetheless closed the line ledger. So completeness could rest on evidence that proves
nothing. Wesker #17 exposes the outcome-qualified view; this is Detective consuming it.

THREE STATES, and collapsing any two is the defect. The one that matters most is the difference
between "the engine cannot tell me" and "the engine told me nothing qualifies" — a single truthy
check conflates them, and the second is a measurement, not a missing capability.
"""

from __future__ import annotations

from Detective.converge import line_proof_basis


def test_an_engine_that_reports_qualifying_evidence_gives_the_strong_basis():
    assert line_proof_basis(has_admissible=True, engine_reports_it=True) == "admissible"


def test_an_engine_that_cannot_report_it_falls_back_and_says_so():
    """An older Wesker has no admissible view. Falling back is correct — refusing would break
    every user on a released engine — but doing it SILENTLY reproduces the defect while printing
    the same verdict, which is the unnamed-capability assumption #60 forbids."""
    assert line_proof_basis(has_admissible=False, engine_reports_it=False) == "observed"


def test_an_empty_admissible_view_is_a_measurement_not_a_missing_capability():
    """THE distinction. The engine measured and NOTHING qualified — every owner was
    baseline-failing, truncated or uncontained. Reading that as 'absent, fall back' would hand
    the ledger straight back to the tests #59 exists to exclude, turning the strongest possible
    refusal into a pass."""
    assert line_proof_basis(has_admissible=False, engine_reports_it=True) == "none_admissible"


def test_the_two_inputs_are_independent():
    """A single truthy check on the map would make these two cases indistinguishable, and they
    have opposite meanings: one is 'I don't know', the other is 'I know, and the answer is
    none'."""
    cannot_tell = line_proof_basis(has_admissible=False, engine_reports_it=False)
    told_us_none = line_proof_basis(has_admissible=False, engine_reports_it=True)
    assert cannot_tell != told_us_none


def test_only_the_missing_capability_case_is_named_observed():
    """`observed` is the one value that means the weaker union was used. If any other state
    could produce it, a certificate could claim the weak basis while standing on the strong one
    — or worse, the reverse."""
    bases = {
        line_proof_basis(has_admissible=h, engine_reports_it=r) for h in (True, False) for r in (True, False)
    }
    assert "observed" in bases
    assert line_proof_basis(has_admissible=True, engine_reports_it=False) == "observed"
