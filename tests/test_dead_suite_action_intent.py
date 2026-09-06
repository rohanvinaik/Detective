"""converge told the reader to do something that provably could not work.

In a directory with no pytest config, `detective converge 'spine.py::spine'` printed:

    WARNING: pytest collected no tests — the live suite has nothing to run.
    ...
    DO THIS:  detective converge 'spine.py::spine' --input "(3,)" --input "(2,)" --input "(4,)"

That command was RUN, literally, as given. Output was byte-identical — still `0/11 killed`.
Adding a pytest config took the same target to `✓ COMPLETE · 11/11`, and `detective regime`
already printed the correct remedy. Every part of the answer existed; none of it reached the
decision.

THE MEASUREMENT/DECISION GAP, exactly. `_run_live` fills a `diagnostic` dict, writes that
warning from it, then falls back to `_run(args)` — and `diagnostic` is a LOCAL. The renderer
far below could not see it, so it re-derived a narrower proxy ("uncovered lines exist => ask for
inputs") and sent the reader into a loop. `synthesized_only` is True in BOTH the healthy case
(a real suite, no test happens to reach this function) and the broken one (no suite at all), so
nothing downstream could distinguish them.

ORDER IS THE WHOLE CONTRACT, and it bit twice in opposite directions:

  * ranking the line gap first is the original bug — advice that cannot work;
  * ranking the collection reason first is a SECOND bug, found by running the fix rather than
    reasoning about it.

THE STANDING IS NOW CONSUMED, NOT RE-DERIVED. `converge_next_action` takes `certificate_standing`'s
resolved code as its first argument — the same derivation `ConvergeResult.complete` and the MCP
renderer already read. The terse CLI renderer used to re-derive a narrower proxy (gateable + line
gap) that could not see a STALE target or a FAILED verification, so a run whose source moved under
it, or whose written suite did not run green, printed DONE. Consuming the code closes both.
"""

from __future__ import annotations

from Detective.cli import converge_next_action

# ── the original defect: order of reason vs gap (standing == "incomplete") ──


def test_a_dead_suite_outranks_a_line_gap():
    """THE regression. With nothing collected, no `--input` can close anything, so the gap ask
    must not be what the reader is shown."""
    assert converge_next_action("incomplete", "empty_collection", True, True) == "fix_collection"
    assert converge_next_action("incomplete", "empty_collection", False, True) == "fix_collection"


def test_a_working_suite_still_gets_the_gap_ask():
    """The healthy path is the default and must be untouched: witnesses and `--input` are the
    documented interface and here they actually work."""
    assert converge_next_action("incomplete", "", True, False) == "close_the_gap"
    assert converge_next_action("incomplete", "", False, True) == "close_the_gap"


def test_a_completed_run_is_never_handed_a_remedy():
    """Converge can OPEN with nothing collectable and CLOSE complete, because it synthesizes the
    suite it then measures. A `complete` standing therefore outranks every reason — the reason
    describes the start of the run, and by the end it is history."""
    assert converge_next_action("complete", "empty_collection", False, False) == "settled"
    assert converge_next_action("complete", "collection_errors", False, False) == "settled"
    assert converge_next_action("complete", "pytest_missing", False, False) == "settled"


def test_settled_is_reached_the_same_way_with_or_without_a_reason():
    """If these differed, the same finished run would advise differently depending on how it
    began — which is precisely the stale-remedy bug."""
    assert converge_next_action("complete", "", False, False) == converge_next_action(
        "complete", "empty_collection", False, False
    )


def test_a_missing_pytest_is_not_a_collection_problem():
    """Distinct remedies. `pip install pytest` and `regime --migrate` are not substitutes, and
    telling a user to migrate a regime when the interpreter has no pytest is another loop."""
    assert converge_next_action("incomplete", "pytest_missing", True, True) == "install_pytest"
    assert converge_next_action("incomplete", "empty_collection", True, True) == "fix_collection"


def test_every_non_empty_reason_blocks_the_input_ask():
    """`_run_live` writes a reason ONLY when the live session did not run at all, so any reason at
    all means the suite is dead — including one from a future Wesker this code has never seen."""
    for reason in ("empty_collection", "collection_errors", "pytest_crashed", "some_future_reason"):
        assert converge_next_action("incomplete", reason, True, True) != "close_the_gap", reason


def test_an_engine_that_reports_no_reason_behaves_exactly_as_before():
    """Older Wesker populates no diagnostic. Absence must degrade to the previous behaviour, not
    to a spurious refusal — the unnamed-capability rule (#60) in the other direction."""
    assert converge_next_action("incomplete", "", True, True) == "close_the_gap"
    assert converge_next_action("complete", "", False, False) == "settled"


# ── the certificate standing is consumed: stale / ungateable / unverified are never DONE ──


def test_a_stale_target_outranks_every_remedy_and_never_asks_for_input():
    """A run whose target moved describes a source that no longer exists; no `--input` closes a
    moved gap, so `stale` must win regardless of suite health or whether a residual is open."""
    for reason in ("", "empty_collection", "pytest_missing"):
        assert converge_next_action("stale", reason, True, True) == "rerun_stale"
        assert converge_next_action("stale", reason, False, False) == "rerun_stale"


def test_a_failed_verification_is_its_own_action_not_settled():
    """functionally_complete with no gap but a RED proof basis is `unverified`, not `settled` — the
    exact false-DONE this closes: a perfect score over a suite that does not run is not a cert."""
    assert converge_next_action("unverified", "", False, False) == "fix_verification"
    assert converge_next_action("unverified", "empty_collection", False, False) == "fix_verification"


def test_an_ungateable_measurement_is_repaired_before_any_input_or_done():
    """A cut / uncontained measurement is not a verdict; it outranks both the gap ask and DONE."""
    assert converge_next_action("ungateable", "", False, False) == "repair_measurement"
    assert converge_next_action("ungateable", "", True, True) == "repair_measurement"


# ── the follow-graph dogfood: one catch-all `regime --migrate` wore three disguises (2026-09-06).
# The baseline collection reason must not be the remedy named when a LATER fact overrides it. Each
# new signal defaults off, so an older caller/Wesker that supplies none keeps the previous behaviour
# (the #60 unnamed-capability contract). ──


def test_a_load_failure_is_named_not_migrated():
    """conorheins/str2bool: the module would not IMPORT (No module named 'jax'). migrate cannot fix
    an import and no --input runs without the module, so a load failure gets its OWN action."""
    assert converge_next_action("incomplete", "empty_collection", True, True, load_failed=True) == "fix_load"
    # load_failed outranks the other overrides — nothing runs, so nothing else is relevant.
    assert (
        converge_next_action(
            "incomplete",
            "empty_collection",
            True,
            True,
            load_failed=True,
            wrote_runnable_suite=True,
            inputs_expressible=False,
        )
        == "fix_load"
    )


def test_an_inexpressible_input_asks_for_a_sample_not_migration():
    """GofL/Game.update_cell: the search RAN but the param has no literal form (an ndarray). The move
    is a real-sample test (close_the_gap -> _derived_input 'test' kind), never collection repair."""
    assert (
        converge_next_action("incomplete", "empty_collection", True, True, inputs_expressible=False)
        == "close_the_gap"
    )


def test_a_suite_written_this_run_makes_the_empty_baseline_stale():
    """arc-dsl/add run-1: converge synthesized AND wrote a runnable suite this run, so the empty
    BASELINE reason is stale — the residual is closable by --input, so the gap ask wins, not migrate."""
    assert (
        converge_next_action("incomplete", "empty_collection", True, True, wrote_runnable_suite=True)
        == "close_the_gap"
    )
    assert (
        converge_next_action("incomplete", "empty_collection", False, True, wrote_runnable_suite=True)
        == "close_the_gap"
    )


def test_the_new_overrides_default_off_preserving_prior_behaviour():
    """With none of the new signals, empty_collection still routes to fix_collection — the #60
    unnamed-capability contract, so an older caller/Wesker is byte-for-byte unchanged."""
    assert converge_next_action("incomplete", "empty_collection", True, True) == "fix_collection"
    assert converge_next_action("incomplete", "collection_errors", True, True) == "fix_collection"


def test_settled_still_outranks_every_new_override():
    """A completed run is never handed a remedy, even with the new signals set — settled is checked
    before session_reason, so a load failure / inexpressible flag on a finished run is moot."""
    assert converge_next_action("complete", "empty_collection", False, False, load_failed=True) == "settled"
    assert (
        converge_next_action("complete", "empty_collection", False, False, inputs_expressible=False)
        == "settled"
    )


def test_a_loaded_module_no_input_exercises_asks_for_a_sample_not_migration():
    """GofL/Game.update_cell: the module LOADED and the search ran in-process, but no input reached
    the function (an unannotated ndarray param — expressibility UNKNOWN, not False). migrate cannot
    fix that, so the report's own 'provide a real sample' guidance is surfaced, not a testpaths remedy."""
    assert (
        converge_next_action("incomplete", "empty_collection", True, True, needs_sample=True)
        == "provide_sample"
    )
    # a KNOWN-inexpressible input is the richer `_derived_input` 'test' renderer's job, not this one.
    assert (
        converge_next_action("incomplete", "empty_collection", True, True, inputs_expressible=False)
        == "close_the_gap"
    )
    # a load failure still outranks: nothing ran at all, so there is nothing to sample.
    assert (
        converge_next_action(
            "incomplete", "empty_collection", True, True, needs_sample=True, load_failed=True
        )
        == "fix_load"
    )
