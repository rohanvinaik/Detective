"""Why a receipt cannot ground a preservation verdict is NAMED, not folded into one ABSTAIN (#114).

THE DEFECT. `verify_rewrite` folded every way a receipt can fail to be a baseline into one
`receipt_valid` bool. Each cause then rendered as the same generic ABSTAIN, "old vs new could not
be compared at every point — treat as unproven; review by hand", under exit 3, whose contract is
"re-run". Two things were wrong with that sign:
- it named a cause that never happened. An invalid receipt stops the check before any old-vs-new
  comparison, so "could not be compared at every point" is a false cause, which
  COMMUNICATING_DETERMINISM §3.1 ranks worse than silence;
- #114 added a cause whose remedy is not "re-run". A receipt taken while a test that reaches the
  function fails records `proof_status: floor_failing`, and converge stops at that floor every time,
  so re-running loops. Two states whose remedies differ shared a signifier (§3).

PINNED HERE:
- `receipt_baseline_standing` returns one named code per cause, ordered by which remedy must come
  first. A failing floor outranks every other cause, because it blocks every other repair;
- the code rides on the verdict's `reason`, so `--json` consumers can branch on it;
- the page renders each code's own remedy, never the generic comparison sentence, and the failing
  floor's remedy says that re-running cannot help;
- the order-evidence causes keep their own messages. A receipt cause outranks them, because
  `rewrite_verdict` consults the receipt first.
"""

from __future__ import annotations

import pytest

from Detective.cli import _format_rewrite
from Detective.rewrite import RewriteVerification, receipt_baseline_standing


@pytest.mark.parametrize(
    ("complete", "proof_status", "freshness", "policy", "expected"),
    [
        (True, "passed", "fresh", "match", "valid"),
        (True, "floor_failing", "fresh", "match", "floor_failing"),
        # A failing floor outranks every other cause: its repair must come first.
        (False, "floor_failing", "unfrozen", "unrecorded", "floor_failing"),
        (False, "passed", "fresh", "match", "incomplete"),
        (False, "tests_failed", "unfrozen", "unrecorded", "incomplete"),
        (True, "tests_failed", "fresh", "match", "proof_not_passed"),
        (True, "unverified", "fresh", "match", "proof_not_passed"),
        (True, "passed", "unfrozen", "match", "unfrozen"),
        (True, "passed", "unfrozen", "unversioned", "unfrozen"),
        (True, "passed", "fresh", "unrecorded", "policy_unestablished"),
        (True, "passed", "fresh", "unversioned", "policy_unestablished"),
    ],
)
def test_each_cause_has_its_own_code(complete, proof_status, freshness, policy, expected):
    assert receipt_baseline_standing(complete, proof_status, freshness, policy) == expected


def _abstain(reason: str) -> RewriteVerification:
    return RewriteVerification(
        verdict="ABSTAIN",
        function="m.py::scale",
        proof_replayed="skipped",
        new_dimensions=(),
        differences=(),
        abstentions=(),
        reason=reason,
    )


@pytest.mark.parametrize(
    "reason",
    [
        "receipt_floor_failing",
        "receipt_incomplete",
        "receipt_proof_not_passed",
        "receipt_unfrozen",
        "receipt_policy_unestablished",
    ],
)
def test_a_receipt_cause_renders_its_own_remedy_never_the_comparison_sentence(reason):
    page = _format_rewrite(_abstain(reason))
    assert "NO BASELINE" in page, page
    assert "could not be compared at every point" not in page, (
        "the comparison never ran: naming it as the cause is a false cause"
    )
    # The sentence wraps on the page; read it as words.
    assert "re-take the receipt" in " ".join(page.lower().split()), page


def test_the_failing_floor_says_re_running_cannot_help():
    page = _format_rewrite(_abstain("receipt_floor_failing"))
    assert "Re-running will not change" in page, page
    assert "fix the failing test or the code" in page, page


def test_the_receipt_causes_are_distinct_signs():
    """Injectivity over the five receipt causes and the generic abstention: no two share a page."""
    reasons = [
        "",
        "receipt_floor_failing",
        "receipt_incomplete",
        "receipt_proof_not_passed",
        "receipt_unfrozen",
        "receipt_policy_unestablished",
    ]
    pages = {_format_rewrite(_abstain(r)) for r in reasons}
    assert len(pages) == len(reasons)


def test_the_order_causes_keep_their_own_messages():
    page = _format_rewrite(_abstain("baseline_order_withheld"))
    assert "argument-order questions" in page and "NO BASELINE" not in page, page
