"""Intent tests for the invocation ledger's pure decisions.

Design: `docs/INVOCATION_LEDGER.md`. These are written from INTENT — what each decision must do
for doctor's process axis to be trustworthy — not from what the code currently returns. The
generated suites beside them are characterizations and would pin a wrong implementation wrong.

The defects these exist to prevent, in order of how much damage each would do:

1. **A false spiral report.** Edit-then-rerun is how the tool is USED. If ordinary iteration
   reads as a spiral, doctor becomes noise, an operator learns to ignore it, and the one time it
   fires correctly they will ignore that too. `repeat_state_changed` must never be a finding.
2. **Collapsing two ordering faults into one.** "You ran a static read on a target nothing has
   ever measured" and "you ran it on a measured-but-unpinned target" have different remedies.
   A bool would make them the same.
3. **Reporting a consequence instead of a cause.** When an interpreter changes, the engine paths
   usually change with it. Naming the engine change sends the operator to fix PYTHONPATH when
   what happened is that they installed into the wrong python — the 2026-09-08 case exactly.
"""

import pytest

from Detective.ledger import (
    environment_drift_disposition,
    order_disposition,
    spiral_disposition,
)

# ---------------------------------------------------------------- spiral_disposition


def test_edit_then_rerun_is_never_a_finding():
    """THE load-bearing intent. An operator who changes something and re-runs is working, not
    spiralling. Reporting this would make the process axis worthless."""
    for repeats in (0, 1, 2, 5, 50):
        assert (
            spiral_disposition(has_prior=True, same_args=True, same_state=False, identical_repeats=repeats)
            == "repeat_state_changed"
        )


def test_a_changed_command_is_progress_regardless_of_state():
    """Supplying a different --input IS the documented way to close a gap. It is progress even
    when nothing else moved."""
    assert (
        spiral_disposition(has_prior=True, same_args=False, same_state=True, identical_repeats=9)
        == "progressed"
    )


def test_the_conorheins_case_is_a_spiral():
    """2026-09-08: converge printed AUTHOR INPUTS, the inputs were supplied verbatim, and the
    output came back byte-identical with the same instruction. Same command, unchanged state,
    more than one repeat — the state doctor must name loudly."""
    assert (
        spiral_disposition(has_prior=True, same_args=True, same_state=True, identical_repeats=2) == "spiral"
    )


def test_one_repeat_is_not_yet_a_spiral():
    """Re-reading a verdict is legitimate. A spiral is a RUN of them, so the threshold must not
    fire on the first repeat — that would punish ordinary use."""
    assert (
        spiral_disposition(has_prior=True, same_args=True, same_state=True, identical_repeats=1)
        == "repeat_no_change"
    )


def test_no_history_yields_no_claim():
    """A first invocation cannot be a repeat of anything. Silence, not a guess."""
    for same_args in (True, False):
        for same_state in (True, False):
            assert (
                spiral_disposition(
                    has_prior=False,
                    same_args=same_args,
                    same_state=same_state,
                    identical_repeats=7,
                )
                == "no_prior"
            )


def test_every_spiral_state_is_distinguishable():
    """Five conditions that mean five different things. If any two collapse, the remedy doctor
    prescribes for one gets prescribed for the other."""
    codes = {
        spiral_disposition(False, True, True, 0),
        spiral_disposition(True, False, True, 0),
        spiral_disposition(True, True, False, 0),
        spiral_disposition(True, True, True, 1),
        spiral_disposition(True, True, True, 2),
    }
    assert len(codes) == 5


# ---------------------------------------------------------------- order_disposition


@pytest.mark.parametrize("herb", ["green", "red"])
def test_setup_and_process_commands_carry_no_ordering_constraint(herb):
    """Only the taste half is conditional on behaviour being pinned. A green or red command is
    never out of order for this reason, whatever the target's pin state."""
    for pinned in (True, False):
        for measured in (True, False):
            assert order_disposition(herb, pinned, measured) == "ok"


def test_an_unmeasured_target_and_an_unpinned_one_are_different_faults():
    """Different remedies: one says 'measure it first', the other says 'pin it first'. Collapsing
    them into a single 'wrong order' sends half the operators to the wrong action."""
    unmeasured = order_disposition("yellow", target_ever_pinned=False, target_has_prior_measurement=False)
    unpinned = order_disposition("yellow", target_ever_pinned=False, target_has_prior_measurement=True)
    assert unmeasured == "taste_without_measurement"
    assert unpinned == "taste_before_behaviour"
    assert unmeasured != unpinned


def test_taste_after_a_pin_is_the_intended_workflow():
    """The style pass AT ✓ COMPLETE is the documented next move — it must never be flagged."""
    assert order_disposition("yellow", target_ever_pinned=True, target_has_prior_measurement=True) == "ok"


# ---------------------------------------------------------------- environment_drift_disposition


def test_a_changed_interpreter_outranks_its_own_consequences():
    """2026-09-08, the motivating case. Installing into the wrong python changes the interpreter
    AND drags the engine paths and version with it. Naming a consequence sends the operator to
    fix PYTHONPATH when the actual repair is 'install into the interpreter Detective runs under'."""
    assert (
        environment_drift_disposition(
            has_prior=True, same_interpreter=False, same_engine_paths=False, same_version=False
        )
        == "interpreter_changed"
    )


def test_the_two_knob_fact_is_reported_when_the_interpreter_held():
    """Same python, different Detective/Wesker resolved — PYTHONPATH moved, or an installed copy
    shadowed a local checkout. A real and separate fault, and the one that silently makes an A/B
    vacuous."""
    assert (
        environment_drift_disposition(
            has_prior=True, same_interpreter=True, same_engine_paths=False, same_version=True
        )
        == "engine_changed"
    )


def test_a_stable_environment_says_so():
    assert (
        environment_drift_disposition(
            has_prior=True, same_interpreter=True, same_engine_paths=True, same_version=True
        )
        == "stable"
    )


def test_drift_makes_no_claim_without_history():
    """Drift is a relation between two runs. With one run there is nothing to relate, and the
    honest answer is that — not 'stable', which asserts something unmeasured."""
    assert (
        environment_drift_disposition(
            has_prior=False, same_interpreter=False, same_engine_paths=False, same_version=False
        )
        == "no_prior"
    )
