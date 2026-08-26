"""`verify-rewrite`'s verdict maps onto the four-valued exit contract, with no epistemic collapse.

Defect this closes (CLI Demand 1): `_run_verify_rewrite` returned `0 if PRESERVED else 1` for every
ending, laundering three distinct states into "a real gap" — a receipt that could not be measured with
(a precondition), a baseline that could not be trusted (an invalid measurement), and a rewrite that
provably changed behavior (a determined gap) all exited `1`. A CI consumer branching on `exit_meaning`
was told "gap_or_refusal" when the truth was "fix your receipt" or "re-run". `verify_rewrite_exit`
restores the four-valued distinction the tool's own `_EXIT_CODES` contract promises.

Intent: each verdict is a distinct epistemic state and maps to its own code; the receipt-unusable
family (2) and the invalid-measurement (3) are NOT collapsed into the determined-gap (1); an
unrecognized verdict is never a false pass.
"""

from __future__ import annotations

from Detective.rewrite import verify_rewrite_exit


def test_preserved_is_the_only_clean_pass():
    assert verify_rewrite_exit("PRESERVED") == 0


def test_determined_negatives_are_a_gap():
    # Behavior provably changed, or a new uncovered dimension — a real gap CI must catch.
    assert verify_rewrite_exit("CHANGED") == 1
    assert verify_rewrite_exit("UNREVIEWED") == 1


def test_unusable_receipts_are_a_precondition_not_a_gap():
    # Malformed/foreign; describes no rewrite; or the frozen proof basis moved — regenerate the
    # receipt. Re-running the same command cannot change the answer, so it is 2, never 1.
    assert verify_rewrite_exit("INVALID_RECEIPT") == 2
    assert verify_rewrite_exit("STALE_RECEIPT") == 2
    assert verify_rewrite_exit("BASIS_MOVED") == 2


def test_abstain_is_an_invalid_measurement_to_rerun():
    # No valid baseline / classification did not run / unresolved survivors — 'no measurement, no
    # verdict'. This is the contract's "weak receipt baseline", exit 3, NOT a gap.
    assert verify_rewrite_exit("ABSTAIN") == 3


def test_no_epistemic_class_collapses_into_another():
    codes = {v: verify_rewrite_exit(v) for v in ("PRESERVED", "CHANGED", "STALE_RECEIPT", "ABSTAIN")}
    # clean / determined-gap / precondition / invalid-measurement are four different codes.
    assert len(set(codes.values())) == 4, codes


def test_unknown_verdict_is_never_a_false_pass():
    # A verdict the mapping does not know is a bug, not a success — it must be caught by CI, never 0.
    assert verify_rewrite_exit("WHAT_IS_THIS") == 1
    assert verify_rewrite_exit("") == 1
