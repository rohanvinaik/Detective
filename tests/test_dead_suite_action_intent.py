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
far below could not see it, so it re-derived a narrower proxy ("uncovered lines exist ⇒ ask for
inputs") and sent the reader into a loop. `synthesized_only` is True in BOTH the healthy case
(a real suite, no test happens to reach this function) and the broken one (no suite at all), so
nothing downstream could distinguish them.

ORDER IS THE WHOLE CONTRACT, and it bit twice in opposite directions:

  * ranking the line gap first is the original bug — advice that cannot work;
  * ranking the collection reason first is a SECOND bug, found by running the fix rather than
    reasoning about it. `session_reason` describes collection at the START of the run, and
    converge can finish a run that began with nothing collectable: it synthesizes, writes, and
    re-profiles. Measured, a config-less run opened `empty_collection` and closed
    `✓ COMPLETE · 11/11` — printing "pytest collected NO tests, fix your regime" directly above
    a green certificate. A remedy for a problem the run already solved is the same class of
    defect as ignoring one it did not.
"""

from __future__ import annotations

from Detective.cli import converge_next_action

# ── the original defect ──


def test_a_dead_suite_outranks_a_line_gap():
    """THE regression. With nothing collected, no `--input` can close anything, so the gap ask
    must not be what the reader is shown."""
    assert converge_next_action("empty_collection", has_killable=True, has_line_gap=True) == "fix_collection"
    assert converge_next_action("empty_collection", has_killable=False, has_line_gap=True) == "fix_collection"


def test_a_working_suite_still_gets_the_gap_ask():
    """The healthy path is the default and must be untouched: witnesses and `--input` are the
    documented interface and here they actually work."""
    assert converge_next_action("", has_killable=True, has_line_gap=False) == "close_the_gap"
    assert converge_next_action("", has_killable=False, has_line_gap=True) == "close_the_gap"


# ── the defect found by running the fix ──


def test_a_completed_run_is_never_handed_a_remedy():
    """Converge can OPEN with nothing collectable and CLOSE complete, because it synthesizes the
    suite it then measures. `settled` therefore outranks every reason — the reason describes the
    start of the run, and by the end it is history."""
    assert converge_next_action("empty_collection", has_killable=False, has_line_gap=False) == "settled"
    assert converge_next_action("collection_errors", has_killable=False, has_line_gap=False) == "settled"
    assert converge_next_action("pytest_missing", has_killable=False, has_line_gap=False) == "settled"


def test_settled_is_reached_the_same_way_with_or_without_a_reason():
    """If these differed, the same finished run would advise differently depending on how it
    began — which is precisely the stale-remedy bug."""
    assert converge_next_action("", False, False) == converge_next_action("empty_collection", False, False)


# ── the reasons are not interchangeable ──


def test_a_missing_pytest_is_not_a_collection_problem():
    """Distinct remedies. `pip install pytest` and `regime --migrate` are not substitutes, and
    telling a user to migrate a regime when the interpreter has no pytest is another loop."""
    assert converge_next_action("pytest_missing", True, True) == "install_pytest"
    assert converge_next_action("empty_collection", True, True) == "fix_collection"


def test_every_non_empty_reason_blocks_the_input_ask():
    """`_run_live` writes a reason ONLY when the live session did not run at all, so any reason
    at all means the suite is dead — including one from a future Wesker this code has never
    seen. Defaulting an unknown reason to the input ask would reinstate the defect for exactly
    the cases nobody anticipated."""
    for reason in ("empty_collection", "collection_errors", "pytest_crashed", "some_future_reason"):
        assert converge_next_action(reason, True, True) != "close_the_gap", reason


def test_an_engine_that_reports_no_reason_behaves_exactly_as_before():
    """Older Wesker populates no diagnostic. Absence must degrade to the previous behaviour, not
    to a spurious refusal — the unnamed-capability rule (#60) in the other direction."""
    assert converge_next_action("", True, True) == "close_the_gap"
    assert converge_next_action("", False, False) == "settled"
