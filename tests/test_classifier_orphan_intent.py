"""The classifier's bounded executions leave no runaway behind when the CLASSIFIER ITSELF is cut
(2026-09-06 — found by `detective converge 'Detective/engine.py::classify_survivors'`).

The defect: `_outcome` (and `_reached_lines`) ran a mutant in a worker thread, joined it with a
timeout, and abandoned it only if it was still alive AFTER the join — `join; if alive: abandon`.
When the thread calling `_outcome` is itself abandoned while parked in that join — which is exactly
what Wesker's traced baseline does to a test that runs the classifier (its per-test budget cuts
the worker the test runs in) — the injected exception lands at the first bytecode after the join,
before the abandon, and the runaway mutant is orphaned: a live thread hogging the GIL for the rest
of the process. Measured: `test_b0_kills_a_residual…` runs plainly in 110 s with zero leaked
threads; run the way the baseline runs it, cut at 50 s, it left a runaway `_run` thread alive, and
a converge whose baseline traced that test stalled for 13 minutes against a 300 s wall.

The fix is `Wesker.interrupt.bounded_join`, which hands the runaway to `abandon` on every exit
from the wait. Pinned here at Detective's two sites as a CONTROL-FLOW claim, with a FAKE worker
thread whose `join` raises the abandonment itself and which always reports alive — the nested case
with no interpreter in the loop. Not with a real runaway: where an injection lands, and what else
it does, varies with the interpreter and with a tracer (under coverage's C tracer — every CI
cell, 3.10 through 3.13, measured locally on the pinned 3.11 — the caller's abandonment also
ended the runaway on its own, and a first version of these tests, built
on real runaways, leaked two of them into the pinned suite and slowed every later test to a crawl
— the very defect, committed by its own test). The ordinary timeout path is pinned on a real
runaway, leashed to a stop flag so nothing can outlive its test.
"""

from __future__ import annotations

import threading
import time

import pytest
from Wesker import interrupt
from Wesker.interrupt import Abandoned

from Detective import equivalence
from Detective.equivalence import _OUTCOME_TIMEOUT, _outcome, _reached_lines


def _identity(x: int) -> int:
    return x


class _CutInsideTheJoin:
    """Stands in for the worker `threading.Thread` the classifier builds: its `join` is where the
    caller's abandonment lands, and it is still running afterwards."""

    ident = None
    name = "fake (_run)"
    instances: list = []

    def __init__(self, target=None, args=(), daemon=False) -> None:
        self.target = target
        _CutInsideTheJoin.instances.append(self)

    def start(self) -> None:
        pass  # the target never runs: the point is the wait, not the work

    def join(self, timeout=None) -> None:
        raise Abandoned

    def is_alive(self) -> bool:
        return True


@pytest.fixture
def fake_worker(monkeypatch):
    """The classifier's `threading.Thread` becomes the fake, for the duration of one test."""
    _CutInsideTheJoin.instances.clear()
    monkeypatch.setattr(equivalence.threading, "Thread", _CutInsideTheJoin)
    return _CutInsideTheJoin.instances


@pytest.fixture
def recorded_abandon(monkeypatch):
    seen: list = []
    real = interrupt.abandon

    def recording(thread):
        seen.append(thread)
        return real(thread)

    monkeypatch.setattr(interrupt, "abandon", recording)
    return seen


def test_outcome_hands_its_worker_to_abandon_when_the_caller_is_cut_inside_the_join(
    fake_worker, recorded_abandon
):
    with pytest.raises(Abandoned):
        _outcome(_identity, (1,), 0.5)
    assert len(fake_worker) == 1
    assert recorded_abandon == fake_worker, "no orphan: the worker was handed to abandon on the way out"


def test_reached_lines_hands_its_worker_to_abandon_when_the_caller_is_cut_inside_the_join(
    fake_worker, recorded_abandon
):
    target_lines = frozenset({1})
    with pytest.raises(Abandoned):
        _reached_lines(_identity, [(1,)], __file__, target_lines, 0.5)
    assert len(fake_worker) == 1
    assert recorded_abandon == fake_worker


# --- the ordinary path, on a real runaway -----------------------------------------------------------

_STOP = threading.Event()


def _spin_forever(_x: int) -> int:
    n = 0
    while not _STOP.is_set():  # a non-terminating mutant, as the classifier meets them — with a leash
        n += 1
    return n


def test_outcome_still_reports_a_timeout_on_the_ordinary_path(recorded_abandon):
    _STOP.clear()
    try:
        assert _outcome(_spin_forever, (1,), 0.2) == _OUTCOME_TIMEOUT
        assert [t.name.endswith("(_run)") for t in recorded_abandon] == [True]
    finally:
        _STOP.set()  # whatever was asserted, no runaway outlives this test
        time.sleep(0.05)
