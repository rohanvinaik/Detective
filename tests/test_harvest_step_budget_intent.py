"""Intent: Detective#80 item 3, as reworked — the harvest bounds a test by count where it can, never refuses.

The first version made a test that loops past `STEP_PROBE_CAP` inside the target END the harvest
`step_budget` and raised `harvest_step_budget` from the codomain harvest, with a page offering no command.
Those are the user's real, baseline-passing tests and the real function: nothing diverged, and a function
that legitimately does a million iterations used to complete under the wall and could not complete at all.

The rule is the engine's own: when the original's counted run does not finish inside the probe cap the
observation is NOT ARMED, so the count cannot decide it and the calibrated wall bounds it, exactly as
before step budgets existed. A test the budget stops runs ONCE MORE without it, and the harvest is taken
from that run (what the stopped run captured is dropped). Only the wall can then cut it, which already has
its `--deadline` remedy. The tests the count could not bound are named on `HarvestResult.unarmed`.
"""

from __future__ import annotations

import time

import pytest
from Wesker.monitoring import STEP_PROBE_CAP

from Detective import capture
from Detective.capture import (
    capture_call_inputs,
    capture_return_types,
    harvest_stop_status,
)
from Detective.cli import observation_incomplete_remedy

LONG = 300_000  # past STEP_PROBE_CAP
assert LONG > STEP_PROBE_CAP


def tally(n, x):
    total = 0
    for _ in range(n):
        total += x
    return total


def _long():
    assert tally(LONG, 2) == 2 * LONG


def _short():
    assert tally(5, 2) == 10


@pytest.mark.parametrize(
    ("base", "contained", "timed_out", "expected"),
    [
        ("complete", True, False, "complete"),
        ("enough", True, False, "enough"),
        ("empty", True, False, "empty"),
        ("complete", True, True, "cut"),
        ("complete", False, True, "uncontained"),
        ("cut", True, False, "cut"),
    ],
)
def test_the_status_a_harvest_ends_with(base, contained, timed_out, expected):
    assert harvest_stop_status(base, contained, timed_out) == expected


def test_a_loop_past_the_cap_completes_the_call_input_harvest_with_the_same_inputs():
    long = capture_call_inputs(tally, [_long], per_test_timeout=60.0)
    assert long.status == "complete" and long.contained
    assert long.samples == ((LONG, 2),)
    short = capture_call_inputs(tally, [_short], per_test_timeout=60.0)
    assert short.status == "complete" and short.unarmed == ()
    assert short.samples == ((5, 2),)


def test_the_test_the_count_could_not_bound_is_named_and_makes_nothing_partial():
    result = capture_call_inputs(tally, [_long], per_test_timeout=60.0)
    assert [name.rsplit(".", 1)[-1] for name in result.unarmed] == ["_long"]
    assert result.status == "complete" and not result.deadline_passed


def test_a_loop_past_the_cap_completes_the_codomain_harvest_with_the_same_types():
    unarmed: list[str] = []
    assert capture_return_types(tally, [_long], per_test_timeout=60.0, unarmed=unarmed) == frozenset({"int"})
    assert [name.rsplit(".", 1)[-1] for name in unarmed] == ["_long"]
    assert capture_return_types(tally, [_short], per_test_timeout=60.0) == frozenset({"int"})


def test_a_stopped_first_run_leaves_nothing_half_captured():
    # The stopped run captures its entry before the loop runs away; the unarmed run captures the same
    # entry again. One run's capture, not two: a sample, not a duplicate and not a leftover.
    seen = capture_call_inputs(tally, [_long, _long], per_test_timeout=60.0)
    assert seen.samples == ((LONG, 2),)

    def varied():
        tally(LONG, 3)
        tally(7, 3)

    result = capture_call_inputs(tally, [varied], per_test_timeout=60.0)
    assert set(result.samples) == {(LONG, 3), (7, 3)} and len(result.samples) == 2


def test_the_codomain_of_a_stopped_run_is_replaced_by_the_unarmed_runs():
    def returns_a_float():
        tally(LONG, 1.5)

    types = capture_return_types(tally, [returns_a_float], per_test_timeout=60.0)
    assert types == frozenset({"float"})


def test_a_test_that_swallows_the_stop_still_completes():
    def stubborn():
        try:
            tally(LONG, 2)
        except BaseException:  # noqa: BLE001
            pass
        tally(LONG, 2)

    result = capture_call_inputs(tally, [stubborn], per_test_timeout=60.0)
    assert result.status == "complete" and result.samples == ((LONG, 2),)


def test_only_the_wall_can_cut_an_unarmed_test():
    def runaway():
        while True:
            tally(LONG, 1)

    started = time.monotonic()
    result = capture_call_inputs(tally, [runaway], per_test_timeout=1.0, step_cap=1000)
    assert result.status == "cut", "the wall, not the count, ended an unarmed test"
    assert time.monotonic() - started < 30


def test_a_cap_that_is_never_reached_changes_nothing():
    result = capture_call_inputs(tally, [_short], per_test_timeout=60.0)
    assert (result.status, result.unarmed, result.samples) == ("complete", (), ((5, 2),))


def test_the_default_budget_is_weskers_probe_cap():
    import inspect

    assert inspect.signature(capture_call_inputs).parameters["step_cap"].default == STEP_PROBE_CAP
    assert inspect.signature(capture_return_types).parameters["step_cap"].default == STEP_PROBE_CAP


def test_no_step_budget_status_or_refusal_remains():
    assert not hasattr(capture, "HARVEST_STEP_BUDGET")
    assert observation_incomplete_remedy("harvest_step_budget", None, True) == "none"
    assert not hasattr(capture.HarvestResult(), "step_stopped")


def test_the_per_test_wall_is_stretched_by_the_calibrated_slowdown(monkeypatch):
    from Wesker import monitoring

    monkeypatch.setattr(monitoring, "machine_slowdown", lambda refresh=False: (4.0, "slower"))
    assert capture._stretched_timeout(5.0) == 20.0
    monkeypatch.setattr(monitoring, "machine_slowdown", lambda refresh=False: (1.0, "reference"))
    assert capture._stretched_timeout(5.0) == 5.0
    monkeypatch.setattr(monitoring, "machine_slowdown", lambda refresh=False: (0.3, "reference"))
    assert capture._stretched_timeout(5.0) == 5.0


def test_the_walls_each_call_uses_are_the_stretched_ones(monkeypatch):
    from Wesker import monitoring

    monkeypatch.setattr(monitoring, "machine_slowdown", lambda refresh=False: (4.0, "slower"))
    walls: list[float] = []
    real = capture._run_for_effects

    def spy(test, timeout_s=5.0, **kwargs):
        walls.append(timeout_s)
        return real(test, timeout_s, **kwargs)

    monkeypatch.setattr(capture, "_run_for_effects", spy)
    capture_call_inputs(tally, [_short])
    capture_return_types(tally, [_short])
    assert walls == [20.0, 20.0]


def test_the_unarmed_rerun_gets_a_wall_and_no_budget(monkeypatch):
    seen: list[tuple[float, int | None]] = []
    real = capture._run_for_effects

    def spy(test, timeout_s=5.0, **kwargs):
        seen.append((timeout_s, kwargs.get("step_cap")))
        return real(test, timeout_s, **kwargs)

    monkeypatch.setattr(capture, "_run_for_effects", spy)
    capture_call_inputs(tally, [_long], per_test_timeout=60.0)
    assert [cap for _wall, cap in seen] == [STEP_PROBE_CAP, None]
    assert seen[1][0] > 0
