"""Intent tests for `outcome` propagation (`docs/INVOCATION_LEDGER.md` §6).

`outcome` is the NAMED next-action code a command emitted. It is what turns a repeat finding from
"you ran this three times with nothing changing" into "you ran `fix_load` three times" — and only
the second names what to stop doing. The founder's ruling was to pay the propagation cost now
rather than build narrow and iterate.

THE CONSTRAINT THE WHOLE STEP RESTS ON: it must not change any command's rendered output or exit
code. A run's verdict cannot depend on whether the ledger is watching. The strongest evidence for
that is not in this file — it is the 126 pre-existing audit tests that pass unchanged over the
refactored renderer.
"""

from __future__ import annotations

import pytest

from Detective.cli import audit_next_action, diagnose_next_action
from Detective.ledger import reset_observations, take_observations

# ---------------------------------------------------------------- audit's ladder


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"block": "fix_load"}, "fix_load"),
        ({"block": "provide_sample"}, "provide_sample"),
        ({"has_failing_tests": True}, "fix_failing_test"),
        ({"killable_gaps": 2}, "close_the_gap"),
        ({"missing_lines": 3}, "close_the_gap"),
        ({"redundant_tests": 1}, "remove_redundant"),
        ({"redundant_tests": 1, "removing": True}, "removing_now"),
        ({"candidate_equivalent": 2, "has_equivalent_ids": True}, "flag_equivalents"),
        ({"unclassified": 4}, "done_unclassified"),
        ({}, "done_complete"),
    ],
)
def test_each_audit_state_gets_its_own_code(kwargs, expected) -> None:
    base = dict(
        block="",
        has_failing_tests=False,
        killable_gaps=0,
        missing_lines=0,
        redundant_tests=0,
        removing=False,
        candidate_equivalent=0,
        has_equivalent_ids=False,
        unclassified=0,
    )
    assert audit_next_action(**{**base, **kwargs}) == expected


def test_a_measurement_that_could_not_RUN_outranks_everything(monkeypatch) -> None:
    """Finding E's rank, preserved by the extraction. Every count below a load failure is
    blindness, so no number of gaps, failing tests or equivalents may take the lead from it."""
    for block in ("fix_load", "provide_sample"):
        assert audit_next_action(block, True, 9, 9, 9, False, 9, True, 9) == block, (
            "a blocked measurement must not be outranked by the counts it invalidates"
        )


def test_a_failing_suite_outranks_the_numbers_it_invalidates() -> None:
    """Every other number was measured against a suite that does not pass; acting on them first is
    acting on sand."""
    assert audit_next_action("", True, 5, 5, 5, False, 5, True, 5) == "fix_failing_test"


def test_flagging_is_never_offered_while_a_real_gap_is_open() -> None:
    """`flag` is the one claim a human makes against the engine, and offering it beside an open gap
    invites recording a judgement instead of doing the work. It ranks below every gap on purpose."""
    assert audit_next_action("", False, 1, 0, 0, False, 3, True, 0) == "close_the_gap"
    assert audit_next_action("", False, 0, 0, 1, False, 3, True, 0) == "remove_redundant"


def test_an_equivalent_count_without_ids_is_not_a_flag_instruction() -> None:
    """The render names a specific id to flag. A count with no ids cannot produce that line, so the
    code must not claim it can — the branch condition is both, and the extraction keeps both."""
    assert audit_next_action("", False, 0, 0, 0, False, 3, False, 0) == "done_complete"


def test_removing_now_is_a_different_fact_from_recommending_removal() -> None:
    """`--remove` EXECUTING must not recommend `--remove`: that is a stale self-instruction computed
    for the pre-action state. Two codes because two different things are printed."""
    assert audit_next_action("", False, 0, 0, 2, True, 0, False, 0) == "removing_now"
    assert audit_next_action("", False, 0, 0, 2, False, 0, False, 0) == "remove_redundant"


# ---------------------------------------------------------------- diagnose


@pytest.mark.parametrize(
    ("entangled", "seams", "dof", "expected"),
    [
        (True, 1, 5, "decompose_first"),
        (True, 0, 5, "close_the_gap"),
        (False, 3, 5, "close_the_gap"),
        (False, 0, 0, "settled"),
    ],
)
def test_diagnose_splits_before_it_pins(entangled, seams, dof, expected) -> None:
    """Priority IS the judgement. `decompose` wins only when BOTH signals agree — entangled and at
    least one seam — because pinning a tangle and then splitting means re-deriving the suite."""
    assert diagnose_next_action("", entangled, seams, dof) == expected


def test_diagnose_reuses_converges_vocabulary_rather_than_paraphrasing_it() -> None:
    """The ledger records (kind, verb, code), so the verb disambiguates. A shared vocabulary makes
    "you got `close_the_gap` from diagnose and then from converge" one coherent story; two
    spellings of the same state would be two, and the repeat would be invisible."""
    assert diagnose_next_action("", False, 0, 1) == "close_the_gap"
    assert diagnose_next_action("", False, 0, 0) == "settled"


# ---------------------------------------------------------------- the observation channel


def test_each_wired_verb_records_its_own_code(tmp_path, capsys) -> None:
    """Through `main`, because what is under test is the WIRING. Four sites are live — converge,
    audit, diagnose, doctor — and each tags its observation with its own verb so a repeat of one is
    not confused with a repeat of another."""
    from Detective.cli import main
    from Detective.ledger import read_recent

    (tmp_path / "m.py").write_text("def add(a, b):\n    if a > b:\n        return a\n    return b\n")
    main(["doctor", "m.py", "--project-root", str(tmp_path)])
    capsys.readouterr()
    # Read the LEDGER, not the channel: `_record_invocation` drains the channel in its `finally`,
    # which is the per-invocation property the next test pins. Asserting on the channel afterwards
    # tests the drain, not the wiring — a distinction worth one failed test to notice.
    rows = read_recent(str(tmp_path))
    assert rows, "the invocation was recorded"
    assert any(kind == "outcome" and verb == "doctor" for kind, verb, _ in rows[-1]["outcome"])


def test_the_channel_is_drained_per_invocation_so_codes_do_not_leak_between_runs() -> None:
    """The record is about ONE invocation. A code left in the channel would attach to the next
    command's record and manufacture a repeat that never happened — a false spiral, which is the
    worse error direction."""
    from Detective.ledger import observe

    reset_observations()
    observe("outcome", "converge", "settled")
    assert len(take_observations()) == 1
    assert take_observations() == (), "draining is what makes the record per-invocation"


def test_observing_never_raises_on_junk() -> None:
    """It is wired into every command's hot path. A channel that can throw would make the ledger a
    new failure source for the work it is only watching."""
    from Detective.ledger import observe

    reset_observations()
    observe(None, None, None)  # type: ignore[arg-type]
    observe("outcome", "converge", "settled")
    assert take_observations() is not None
