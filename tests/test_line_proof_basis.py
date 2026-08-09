"""A certificate must name the evidence it stood on (issue #59).

`✓ COMPLETE` required every executable line to be covered, and judged that from the OBSERVED
union — which includes tests that FAIL against the unmutated program. Such a test is already
barred from kill attribution, because it cannot distinguish a mutant from correct code; its
coverage nonetheless closed the line ledger. So completeness could rest on evidence that proves
nothing. Wesker #17 exposes the outcome-qualified view; this is Detective consuming it.

FOUR STATES, and collapsing any two is the defect. The one that matters most is the difference
between "the engine cannot tell me" and "the engine told me nothing qualifies" — a single truthy
check conflates them, and the second is a measurement, not a missing capability.

The fourth (`malformed`) was added when `ty` found that `_admissible or {}` at the call site
returned the truthy SENTINEL OBJECT whenever the attribute was absent. That value never reached
`missing_lines` — but only because of an invariant established on a different line, by a
different function, three lines away. The bug it guarded against was unreachable; the reason it
was unreachable was unwritten. See `test_a_view_that_is_not_a_ledger_is_not_an_empty_ledger`.
"""

from __future__ import annotations

from Detective.converge import line_proof_basis


def test_an_engine_that_reports_qualifying_evidence_gives_the_strong_basis():
    assert line_proof_basis(has_admissible=True, engine_reports_it=True, is_mapping=True) == "admissible"


def test_an_engine_that_cannot_report_it_falls_back_and_says_so():
    """An older Wesker has no admissible view. Falling back is correct — refusing would break
    every user on a released engine — but doing it SILENTLY reproduces the defect while printing
    the same verdict, which is the unnamed-capability assumption #60 forbids."""
    assert line_proof_basis(has_admissible=False, engine_reports_it=False, is_mapping=False) == "observed"


def test_an_empty_admissible_view_is_a_measurement_not_a_missing_capability():
    """THE distinction. The engine measured and NOTHING qualified — every owner was
    baseline-failing, truncated or uncontained. Reading that as 'absent, fall back' would hand
    the ledger straight back to the tests #59 exists to exclude, turning the strongest possible
    refusal into a pass."""
    assert (
        line_proof_basis(has_admissible=False, engine_reports_it=True, is_mapping=True) == "none_admissible"
    )


def test_a_view_that_is_not_a_ledger_is_not_an_empty_ledger():
    """A broken engine contract and a clean measurement of nothing take the SAME action — close
    the ledger with no evidence — and have opposite causes. A user told "nothing qualified"
    audits their tests; a user told "malformed" audits their Wesker install. Reporting the action
    as the reason is how a toolchain fault gets filed as a test problem."""
    assert line_proof_basis(has_admissible=False, engine_reports_it=True, is_mapping=False) == "malformed"
    assert line_proof_basis(has_admissible=True, engine_reports_it=True, is_mapping=False) == "malformed"


def test_the_absent_case_outranks_the_malformed_case():
    """The sentinel is not a mapping either, so `is_mapping` is False in the ABSENT case too.
    If `malformed` were tested first, every older Wesker would be reported as a broken engine
    rather than an old one — the check order carries the whole distinction."""
    assert line_proof_basis(has_admissible=False, engine_reports_it=False, is_mapping=False) == "observed"


def test_the_three_inputs_are_independent():
    """A single truthy check on the map would make these cases indistinguishable, and they have
    opposite meanings: 'I don't know', 'I know, and the answer is none', and 'I was handed
    something I cannot read'."""
    cannot_tell = line_proof_basis(has_admissible=False, engine_reports_it=False, is_mapping=False)
    told_us_none = line_proof_basis(has_admissible=False, engine_reports_it=True, is_mapping=True)
    unreadable = line_proof_basis(has_admissible=False, engine_reports_it=True, is_mapping=False)
    assert len({cannot_tell, told_us_none, unreadable}) == 3


def test_only_the_missing_capability_case_is_named_observed():
    """`observed` is the one value that means the weaker union was used. If any other state
    could produce it, a certificate could claim the weak basis while standing on the strong one
    — or worse, the reverse."""
    bases = {
        line_proof_basis(has_admissible=h, engine_reports_it=r, is_mapping=m)
        for h in (True, False)
        for r in (True, False)
        for m in (True, False)
    }
    assert bases == {"observed", "admissible", "none_admissible", "malformed"}
    assert line_proof_basis(has_admissible=True, engine_reports_it=False, is_mapping=True) == "observed"
