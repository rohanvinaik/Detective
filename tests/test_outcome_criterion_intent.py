"""W1 — `outcome` propagation, closed by a CRITERION rather than by wiring eleven sites.

`INVOCATION_LEDGER.md` §10 listed eleven verbs recording `outcome: []` and called it "a real gap and
not a finished job", with the honest note that building them all now would be speculative. Working
through them 2026-09-09 produced the thing that was actually missing — not eleven propagations, but
the rule that says which of them the field is FOR:

    `outcome` earns its place where a verb's named ending is NOT recoverable from its exit code,
    AND the verb issues an instruction an operator would repeat.

Both halves are load-bearing. Without the first, `outcome` duplicates a column the ledger already
has — `decompose_exit` and `verify_rewrite_exit` are decisions, but a decision whose output IS the
exit code adds nothing to a record that stores the exit code. Without the second, the field fills up
with re-reads: an operator reading a `survey` report twice is not in a spiral, and red would learn to
cry wolf.

Applying it moved three verbs, and each was a NON-1:1 mapping hiding in plain sight:

    verify-rewrite   7 verdicts → 4 codes. CHANGED/UNREVIEWED share 1; INVALID_RECEIPT,
                     STALE_RECEIPT and BASIS_MOVED all share 2 — three different things to fix,
                     one number.
    decompose        6 structural endings → 3 codes, and the two sharing 3 have OPPOSITE remedies:
                     `proof_cut` says re-run, `preservation_unproven` says supply the residual
                     --input. Decompose is also the slowest verb here, so repeating the wrong one is
                     the most expensive spiral in the CLI.
    regime           every conflict KIND exits 2. And after a `--migrate` the conflict should be
                     gone, so the same code twice is a migration that missed the cause.

The remaining eight — plan, survey, extract, parsimony, censor, receipt, flag, purge — fail the
second half rather than the first, and that is recorded as a reason instead of a TODO.
"""

from __future__ import annotations

from itertools import product

from Detective.cli import regime_outcome
from Detective.decompose_apply import decompose_exit, decompose_outcome
from Detective.rewrite import verify_rewrite_exit

_DECOMPOSE_FACTS = list(product((True, False), (0, 1, 5), (True, False), (True, False), (0, 1, 3)))


# ---------------------------------------------------------------- the criterion, as measurement


def test_verify_rewrite_verdicts_are_not_recoverable_from_the_exit_code() -> None:
    """The criterion is a measurable property, not a judgement call: count the states, count the
    codes. If the map were injective, `outcome` would be a second copy of `exit`."""
    verdicts = (
        "PRESERVED",
        "CHANGED",
        "UNREVIEWED",
        "INVALID_RECEIPT",
        "STALE_RECEIPT",
        "BASIS_MOVED",
        "POLICY_MOVED",
        "ABSTAIN",
    )
    codes = {verify_rewrite_exit(v) for v in verdicts}
    assert len(verdicts) == 8
    assert len(codes) == 4, "8 verdicts over 4 codes — four collisions the ledger could not see"
    assert verify_rewrite_exit("INVALID_RECEIPT") == verify_rewrite_exit("STALE_RECEIPT")


def test_decompose_endings_collide_on_the_exit_code_with_opposite_remedies() -> None:
    """The sharpest instance. Both exit 3, and a reader who cannot tell them apart re-runs the
    slowest command in the tool when what they needed was to supply an input."""
    cut = decompose_outcome(
        apply_requested=False, applied=0, proof_complete=True, budget_exhausted=True, unsafe=0
    )
    unproven = decompose_outcome(
        apply_requested=True, applied=0, proof_complete=False, budget_exhausted=False, unsafe=0
    )
    assert cut == "proof_cut" and unproven == "preservation_unproven"
    assert decompose_exit(False, 0, True, True, 0) == decompose_exit(True, 0, False, False, 0) == 3


def test_every_decompose_ending_is_reachable() -> None:
    """A code nothing can produce is a code that lies about the state space it claims to cover."""
    reachable = {decompose_outcome(*f) for f in _DECOMPOSE_FACTS}
    assert reachable == {
        "proof_cut",
        "applied",
        "proposed",
        "preservation_unproven",
        "blocked_unsafe",
        "already_atomic",
    }


# ---------------------------------------------------------------- one derivation, two renderers


def test_the_exit_code_CONSUMES_the_outcome_rather_than_re_deriving_it() -> None:
    """`decompose_exit` used to carry its own copy of this ladder. Two ladders over one set of facts
    agree only until someone edits one — the sibling drift every repair in CORRECTNESS_REPAIRS
    turned out to be. This pins that the extraction changed no behaviour, over the WHOLE input
    space rather than over the cases someone thought to try."""

    def previous(apply_requested, applied, proof_complete, budget_exhausted, unsafe):
        if budget_exhausted:
            return 3
        if applied > 0:
            return 0
        if not apply_requested:
            return 0
        if not proof_complete:
            return 3
        if unsafe > 0:
            return 1
        return 0

    for facts in _DECOMPOSE_FACTS:
        assert decompose_exit(*facts) == previous(*facts), facts


# ---------------------------------------------------------------- regime


def test_a_regime_conflict_KIND_passes_through_verbatim() -> None:
    """The regime's own vocabulary, consumed rather than paraphrased — the same discipline
    `diagnose_next_action` follows with the shared block. A second spelling would make one state
    read as two across `doctor`'s green axis, `regime`'s own report and the ledger."""
    assert regime_outcome("shadowed-target", False, False) == "shadowed-target"
    assert regime_outcome("conftest-collision", True, True) == "conftest-collision"


def test_clean_and_migration_available_are_different_facts() -> None:
    """ "Nothing to do" and "something to do that you have not done" are different states of the
    OPERATOR, which is what this axis reports on."""
    assert regime_outcome("", False, False) == "clean"
    assert regime_outcome("", False, True) == "migration_available"
    assert regime_outcome("", True, False) == "migrated"


def test_a_conflict_outranks_a_migration_that_ran() -> None:
    """A migration that ran and left a conflict standing has not fixed anything, and reporting
    `migrated` there would be the tool showing evidence of a repair that did not land."""
    assert regime_outcome("shadowed-target", True, True) == "shadowed-target"
