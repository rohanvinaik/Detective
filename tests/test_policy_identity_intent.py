"""Intent pins for binding a rewrite receipt to the QUESTION SET it was measured under.

THE GAP, grounded 2026-09-11 with Serena. ``RewriteReceipt.policy_id`` is written by
``make_receipt`` (from ``conv.policy_id``) and read by NO production consumer —
``find_referencing_symbols`` returned ``make_receipt`` and three test constructors, nothing else.
So a receipt taken under mutation policy 6 could be handed to ``verify-rewrite`` after a policy
bump, and the new-dimension scan would ask the NEW set of questions while the verdict spoke for the
old one. The pending SWAP work bumps the policy 6 -> 7, which is exactly the event that makes this
live: under policy 6 an argument-order question about non-neighbouring positions was never asked,
so a receipt frozen under 6 records a completeness that 7 does not grant it.

THE RULE: "measured under a different policy" is a PRECONDITION to fix, not a gap and not a pass.
And the ways to be unable to compare are not one fact — an engine that cannot name its own policy,
a receipt that never recorded one, and two policies that genuinely differ have three different
remedies (upgrade the engine / re-take the receipt / re-take the receipt against the new questions),
so they get three different names. Absence of a match never becomes a silent match.

These tests are written from what the decision must do, not from what it currently returns, and they
call through the MODULE ATTRIBUTE (``rewrite.policy_identity``) rather than a from-import: that is
the routing ``converge`` asks for so an installed mutant is the thing the test actually calls.
"""

from __future__ import annotations

import ast
import hashlib

import pytest

from Detective import pins, rewrite
from Detective.rewrite import RewriteReceipt, verify_rewrite, verify_rewrite_exit
from Detective.verdict_cache import wesker_policy_id

# The real ids at the boundary this decision exists to police: the policy the committed receipts
# were taken under, and the one the argument-order work moves to.
POLICY_6 = "6.13a1fd436d29"


def test_a_receipt_from_a_different_policy_is_moved() -> None:
    """The case the whole gate exists for: the bump must not silently re-ask a different set."""
    assert rewrite.policy_identity(POLICY_6, "7.0000000000") == "moved"


def test_the_same_policy_is_a_match() -> None:
    assert rewrite.policy_identity(POLICY_6, POLICY_6) == "match"


def test_a_receipt_that_never_recorded_a_policy_is_unrecorded_not_a_match() -> None:
    """A pre-#14 receipt. Nothing to compare is not 'nothing changed' — the remedy is to re-take
    the receipt, and a consumer must be able to tell that from a detected change."""
    assert rewrite.policy_identity(None, POLICY_6) == "unrecorded"


def test_an_engine_that_cannot_name_its_policy_is_unversioned_even_with_a_recorded_receipt() -> None:
    """``wesker_policy_id()`` returns None on a pre-policy Wesker. This run then cannot name the
    questions it is ABOUT to ask, so no comparison is possible whatever the receipt holds — and
    that is the more fundamental gap, so it is reported ahead of the receipt's own silence."""
    assert rewrite.policy_identity(POLICY_6, None) == "unversioned"


def test_both_absent_reports_the_engine_gap_first() -> None:
    assert rewrite.policy_identity(None, None) == "unversioned"


@pytest.mark.parametrize("empty", ["", None])
def test_an_empty_id_is_no_id_never_a_value_that_compares_equal(empty) -> None:
    """Two blank ids must not read as 'the same policy' — that is the one way absence could
    manufacture a match."""
    assert rewrite.policy_identity(empty, empty) == "unversioned"
    assert rewrite.policy_identity(empty, POLICY_6) == "unrecorded"
    assert rewrite.policy_identity(POLICY_6, empty) == "unversioned"


def test_moved_is_never_returned_when_a_side_is_missing() -> None:
    """'could not compare' and 'compared, and they differ' are different claims. Only the second
    may say ``moved``; conflating them would report a change nobody detected."""
    for receipt_id, current_id in ((None, POLICY_6), (POLICY_6, None), (None, None), ("", "")):
        assert rewrite.policy_identity(receipt_id, current_id) != "moved"


def test_the_four_states_are_four_distinct_signifiers() -> None:
    """Injectivity: facts with different remedies must not share a name."""
    seen = {
        rewrite.policy_identity(POLICY_6, POLICY_6),
        rewrite.policy_identity(POLICY_6, "7.0000000000"),
        rewrite.policy_identity(None, POLICY_6),
        rewrite.policy_identity(POLICY_6, None),
    }
    assert seen == {"match", "moved", "unrecorded", "unversioned"}


def test_only_match_may_ever_support_a_preserved_verdict() -> None:
    """The disposition the wiring rests on: exactly one state clears the receipt for PRESERVED."""
    clears = [
        s
        for s in ("match", "moved", "unrecorded", "unversioned")
        if s == rewrite.policy_identity(POLICY_6, POLICY_6)
    ]
    assert clears == ["match"]


# ── the exit contract ──────────────────────────────────────────────────────────


def test_a_moved_policy_is_a_precondition_not_a_gap() -> None:
    """Exit 2, with the other unusable-receipt endings. Reporting 1 would tell CI the rewrite broke
    something, when in fact nothing about the rewrite was measured."""
    assert verify_rewrite_exit("POLICY_MOVED") == 2
    assert verify_rewrite_exit("POLICY_MOVED") != verify_rewrite_exit("CHANGED")
    assert verify_rewrite_exit("POLICY_MOVED") != verify_rewrite_exit("ABSTAIN")


# ── end to end, through verify_rewrite itself ──────────────────────────────────


def test_a_receipt_from_another_policy_is_refused_before_anything_is_measured(tmp_path) -> None:
    """The defect, reproduced through the real entry point. The receipt is otherwise PERFECT — a
    complete, green, frozen baseline over a genuinely rewritten source — and differs only in the
    policy it was measured under. It must not be replayed against this engine's questions."""
    root = str(tmp_path)
    original = "def f(x):\n    return x + 1\n"
    (tmp_path / "polmod.py").write_text("def f(x):\n    return x + 2\n")  # a real rewrite
    proof = tmp_path / "test_polmod.py"
    proof.write_text("def test_f():\n    assert True\n")

    node = next(n for n in ast.walk(ast.parse(original)) if isinstance(n, ast.FunctionDef))
    receipt = RewriteReceipt(
        function="polmod.py::f",
        original_source=original,
        source_digest=hashlib.sha256(original.encode()).hexdigest(),
        function_digest=pins.function_digest(node),
        policy_id="0.0deadbeefff",  # a policy this engine does not ask
        universe_size=1,
        proof_suite=(proof.name,),
        proof_status="passed",
        functionally_complete=True,
        proof_digests=((proof.name, hashlib.sha256(proof.read_bytes()).hexdigest()),),
    )
    v = verify_rewrite(receipt, "polmod.py", "f", root)
    assert v.verdict == "POLICY_MOVED", (
        f"a receipt from another mutation policy was replayed anyway (got {v.verdict})"
    )
    # Refused BEFORE measurement: nothing was replayed, nothing classified.
    assert v.proof_replayed == "skipped"
    assert (v.new_dimensions, v.differences, v.abstentions) == ((), (), ())
    assert "0.0deadbeefff" in (v.note or "")


def test_a_receipt_with_no_policy_still_runs_but_cannot_be_preserved(tmp_path) -> None:
    """`unrecorded` is a missing record, not a detected change — so it must NOT hijack the verdict
    the way `moved` does. It only withholds PRESERVED, exactly as an unfrozen basis does."""
    root = str(tmp_path)
    original = "def f(x):\n    return x + 1\n"
    (tmp_path / "polmod2.py").write_text("def f(x):\n    return x + 2\n")
    node = next(n for n in ast.walk(ast.parse(original)) if isinstance(n, ast.FunctionDef))
    receipt = RewriteReceipt(
        function="polmod2.py::f",
        original_source=original,
        source_digest=hashlib.sha256(original.encode()).hexdigest(),
        function_digest=pins.function_digest(node),
        policy_id=None,  # a pre-#14 receipt
        universe_size=1,
        proof_suite=(),
        proof_status="passed",
        functionally_complete=True,
    )
    v = verify_rewrite(receipt, "polmod2.py", "f", root)
    assert v.verdict != "POLICY_MOVED", "a receipt that recorded nothing is not a detected change"
    assert v.verdict != "PRESERVED", "an unrecorded policy must never ground preservation"


def test_the_live_engine_verifies_its_own_receipts() -> None:
    """The gate must not be a wall: a receipt taken under the policy this engine asks passes it and
    goes on to be measured normally."""
    assert rewrite.policy_identity(wesker_policy_id(), wesker_policy_id()) == "match"
