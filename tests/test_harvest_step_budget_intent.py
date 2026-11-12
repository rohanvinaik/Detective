"""Intent: Detective#80 item 3 — the capture harvest has the per-test loop budget and a liveness bound.

The defect, verbatim from the issue: "`capture.py` imports and re-exports `step_budget` but never calls
it. The harvest has only its per-test wall (`per_test_timeout=5.0`) and the aggregate deadline." A test
that loops inside the target waited out a fixed 5 s wall, which is a different answer on every machine,
and the harvest then read `cut`: a wall's word for something a count can say exactly.

`capture_call_inputs` and `capture_return_types` now run each test under a loop budget of the target's
own iterations (Wesker's `STEP_PROBE_CAP` by default: the budget an original gets where no test fixed a
count) and a wall stretched by the machine's calibrated slowdown. A test the budget stops ends the
harvest `step_budget`: partial, named, deterministic, and a different remedy from `cut`.
"""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest
from Wesker.monitoring import STEP_PROBE_CAP

from Detective import capture
from Detective.capture import (
    HarvestIncomplete,
    capture_call_inputs,
    capture_return_types,
    harvest_stop_status,
)
from Detective.cli import _incomplete_observation_lines, observation_incomplete_remedy


def spin(n):
    i = 0
    while i < n:
        i += 1
    return i


def _runs_spin_long():
    spin(10_000_000)


def _runs_spin_short():
    spin(5)


@pytest.mark.parametrize(
    ("base", "contained", "stepped", "timed_out", "expected"),
    [
        ("complete", True, False, False, "complete"),
        ("enough", True, False, False, "enough"),
        ("empty", True, False, False, "empty"),
        ("complete", True, True, False, "step_budget"),
        ("complete", True, False, True, "cut"),
        # both: the wall is named (its remedy is the one a person can act on); the budget stop is kept
        # on the result's own field
        ("complete", True, True, True, "cut"),
        ("complete", False, True, True, "uncontained"),
        ("cut", True, False, False, "cut"),
    ],
)
def test_the_status_a_harvest_ends_with(base, contained, stepped, timed_out, expected):
    assert harvest_stop_status(base, contained, stepped, timed_out) == expected


def test_a_test_that_loops_inside_the_target_is_stopped_by_the_count_not_the_wall():
    started = time.monotonic()
    result = capture_call_inputs(spin, [_runs_spin_long], per_test_timeout=60.0, step_cap=1000)
    elapsed = time.monotonic() - started
    assert result.status == "step_budget" and result.step_stopped
    assert result.contained
    assert result.samples == ((10_000_000,),), "the entry was captured before the loop ran away"
    assert elapsed < 20, "the count decided long before the 60 s wall could"


def test_the_stop_is_the_same_every_time():
    seen = {
        (r.status, r.step_stopped, r.samples)
        for r in (
            capture_call_inputs(spin, [_runs_spin_long], per_test_timeout=60.0, step_cap=500)
            for _ in range(3)
        )
    }
    assert seen == {("step_budget", True, ((10_000_000,),))}


def test_a_test_that_swallows_the_stop_is_still_stopped():
    def stubborn():
        try:
            spin(10_000_000)
        except BaseException:  # noqa: BLE001
            pass

    result = capture_call_inputs(spin, [stubborn], per_test_timeout=60.0, step_cap=500)
    assert result.status == "step_budget" and result.step_stopped


def test_a_harvest_inside_its_budget_is_untouched():
    result = capture_call_inputs(spin, [_runs_spin_short], per_test_timeout=60.0)
    assert (result.status, result.step_stopped, result.samples) == ("complete", False, ((5,),))
    assert STEP_PROBE_CAP > 5


def test_the_default_budget_is_weskers_probe_cap():
    import inspect

    default = inspect.signature(capture_call_inputs).parameters["step_cap"].default
    assert default == STEP_PROBE_CAP
    assert inspect.signature(capture_return_types).parameters["step_cap"].default == STEP_PROBE_CAP


def test_a_later_test_still_runs_after_one_is_stopped():
    def other():
        spin(7)

    result = capture_call_inputs(spin, [_runs_spin_long, other], per_test_timeout=60.0, step_cap=500)
    assert result.status == "step_budget"
    assert set(result.samples) == {(10_000_000,), (7,)}


def test_the_codomain_harvest_names_the_stop_and_keeps_it_partial():
    def returns():
        spin(3)

    with pytest.raises(HarvestIncomplete) as caught:
        capture_return_types(spin, [returns, _runs_spin_long], per_test_timeout=60.0, step_cap=500)
    exc = caught.value
    assert exc.code == "harvest_step_budget"
    assert exc.result.status == "step_budget" and exc.result.step_stopped
    assert exc.result.codomain == frozenset({"int"}), (
        "what was observed before the stop is kept, as diagnostic"
    )


def test_the_codomain_harvest_inside_its_budget_returns_the_types():
    assert capture_return_types(spin, [_runs_spin_short], per_test_timeout=60.0) == frozenset({"int"})


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
    capture_call_inputs(spin, [_runs_spin_short])
    capture_return_types(spin, [_runs_spin_short])
    assert walls == [20.0, 20.0]


def test_the_page_for_a_step_budget_stop_offers_no_command_that_changes_nothing():
    assert observation_incomplete_remedy("harvest_step_budget", None, True) == "step_budget_stop"
    # a wall's remedy is still a wall's
    assert observation_incomplete_remedy("harvest_timeout", None, True) == "raise_deadline"
    exc = SimpleNamespace(code="harvest_step_budget")
    page, command, remedy = _incomplete_observation_lines(
        exc, SimpleNamespace(command="audit", deadline=None), ["audit"]
    )
    text = "\n".join(page)
    assert remedy == "step_budget_stop" and command == ""
    assert "DO THIS" not in text and "larger --deadline changes nothing" in text
