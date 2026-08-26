"""`decompose`'s structural outcome maps onto the four-valued exit contract, with no refusal-as-clean.

Defect this closes (CLI Demand 1): `_run_decompose` returned `3 if budget_exhausted else 0`, so an
`--apply` whose proof could NOT establish preservation (the tool refused to decompose because it could
not prove safety) exited `0` — a refusal reported as clean, the dangerous direction. `decompose_exit`
restores the four-valued distinction: a cut / unprovable proof is an invalid measurement (3), an
unsafe-block refusal is a determined gap (1), and only a real apply or a dry-run proposal is clean (0).

Intent: each structural outcome is a distinct epistemic state; a requested `--apply` that did not
happen is never a false 0.
"""

from __future__ import annotations

from Detective.decompose_apply import decompose_exit


def test_cut_proof_is_invalid_measurement():
    # budget_exhausted outranks everything — a cut proof proves nothing, re-run.
    assert (
        decompose_exit(apply_requested=True, applied=0, proof_complete=False, budget_exhausted=True, unsafe=0)
        == 3
    )
    assert (
        decompose_exit(apply_requested=False, applied=2, proof_complete=True, budget_exhausted=True, unsafe=0)
        == 3
    )


def test_applied_extraction_is_clean():
    assert (
        decompose_exit(apply_requested=True, applied=1, proof_complete=True, budget_exhausted=False, unsafe=0)
        == 0
    )


def test_dry_run_proposal_is_advisory_not_a_gate():
    # No --apply: a proposal is advisory, always clean, even with an incomplete proof or unsafe blocks.
    assert (
        decompose_exit(
            apply_requested=False, applied=0, proof_complete=False, budget_exhausted=False, unsafe=3
        )
        == 0
    )


def test_apply_with_unprovable_proof_is_invalid_measurement_not_clean():
    # THE COLLAPSE, closed: --apply requested, preservation could not be established → 3 (supply the
    # residual --input, re-run), never the prior 0.
    assert (
        decompose_exit(
            apply_requested=True, applied=0, proof_complete=False, budget_exhausted=False, unsafe=0
        )
        == 3
    )


def test_apply_blocked_by_unsafe_block_is_a_determined_refusal():
    # --apply requested, proof was fine, but a block could not be safely extracted → a determined gap.
    assert (
        decompose_exit(apply_requested=True, applied=0, proof_complete=True, budget_exhausted=False, unsafe=2)
        == 1
    )


def test_apply_with_nothing_to_extract_is_a_clean_no_op():
    # --apply requested, proof complete, no unsafe blocks, nothing applied → already atomic, clean.
    assert (
        decompose_exit(apply_requested=True, applied=0, proof_complete=True, budget_exhausted=False, unsafe=0)
        == 0
    )


def test_the_two_refusal_states_no_longer_collapse_into_clean():
    unprovable = decompose_exit(
        apply_requested=True, applied=0, proof_complete=False, budget_exhausted=False, unsafe=0
    )
    unsafe = decompose_exit(
        apply_requested=True, applied=0, proof_complete=True, budget_exhausted=False, unsafe=1
    )
    assert unprovable == 3 and unsafe == 1  # neither is 0
