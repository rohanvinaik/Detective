"""Intent tests for the capture harvest's exception policy (2026-09-06, the local Sonar pass).

The defect: both harvest loops in ``Detective.capture`` swallowed ``BaseException`` — correct
for pytest's ``Skipped``/``Failed`` outcomes (they derive from ``BaseException``, so ``Exception``
is too narrow) and WRONG for the operator's ``KeyboardInterrupt`` and ``SystemExit``, which the
same clause ate: a Ctrl-C during a harvest of N discovered tests was absorbed N times over and
the command ran on. The fix is one helper, ``_run_for_effects``, shared by both loops: run the
test for its side effects on the profile hook, swallow its verdict, never swallow the interrupt.

Written from intent, not from the code: the interrupt must propagate, the previous profile hook
must be restored on the way out, and a skip/failure must still be swallowed so the harvest
continues to the next test.
"""

from __future__ import annotations

import sys

import pytest

from Detective.capture import capture_call_inputs, capture_return_types


def target(x: int) -> int:
    return x * 2


@pytest.mark.parametrize("interrupt", [KeyboardInterrupt, SystemExit])
def test_the_operators_interrupt_propagates_out_of_the_input_harvest(interrupt):
    def interrupted():
        raise interrupt

    prev = sys.getprofile()
    with pytest.raises(interrupt):
        capture_call_inputs(target, [interrupted])
    assert sys.getprofile() is prev, "the profile hook must be restored even when the harvest is interrupted"


@pytest.mark.parametrize("interrupt", [KeyboardInterrupt, SystemExit])
def test_the_operators_interrupt_propagates_out_of_the_return_type_harvest(interrupt):
    def interrupted():
        raise interrupt

    prev = sys.getprofile()
    with pytest.raises(interrupt):
        capture_return_types(target, [interrupted])
    assert sys.getprofile() is prev


def test_an_interrupt_stops_the_harvest_where_it_happens_and_keeps_nothing_after_it():
    seen: list[str] = []

    def first():
        seen.append("first")
        target(1)

    def interrupted():
        seen.append("interrupted")
        raise KeyboardInterrupt

    def never():
        seen.append("never")
        target(3)

    with pytest.raises(KeyboardInterrupt):
        capture_call_inputs(target, [first, interrupted, never])
    assert seen == ["first", "interrupted"], "the test after the interrupt must not run"


def test_a_pytest_skip_is_swallowed_and_the_harvest_continues_to_the_next_test():
    # pytest.skip raises Skipped, a BaseException subclass — the case `except Exception` misses.
    def skipped():
        pytest.skip("not today")

    def reaches():
        target(7)

    assert capture_call_inputs(target, [skipped, reaches]) == [(7,)]
    assert capture_return_types(target, [skipped, reaches]) == frozenset({"int"})


def test_a_failing_assertion_is_swallowed_and_the_harvest_continues():
    def fails():
        target(1)
        assert target(1) == 999, "the verdict is irrelevant to the harvest"

    def reaches():
        target(2)

    assert capture_call_inputs(target, [fails, reaches]) == [(1,), (2,)]


def test_runaway_test_is_bounded_by_per_test_execution_boundary():
    import time

    def runaway():
        target(1)
        while True:
            time.sleep(0.001)

    def reaches():
        target(2)

    # runaway is stopped and the harvest still collects reaches
    got = capture_call_inputs(
        target,
        [runaway, reaches],
        per_test_timeout=0.1,
        deadline=time.monotonic() + 2.0,
    )
    assert (1,) in got
    assert (2,) in got


def test_monitoring_unavailable_raises_capability_outcome(monkeypatch):
    from Wesker.monitoring import MonitoringUnavailable

    def _fail_tool_id():
        raise MonitoringUnavailable("simulated tool id exhaustion")

    monkeypatch.setattr("Detective.capture.tool_id", _fail_tool_id)

    def dummy():
        pass

    with pytest.raises(MonitoringUnavailable):
        capture_call_inputs(target, [dummy])
