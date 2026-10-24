"""D#108: late observations must not enter an aggregate-deadline harvest.

Detective 1.2.1's macOS 3.14 release CI retained (1,) after its 50ms wall.
Control the clock instead of hoping a sleep reproduces the scheduling race:
the worker may finish before the parent resumes, so a join timeout is not
the observation's admission rule. Setup, copying and repr consume the wall too.
"""

import threading
from types import SimpleNamespace

import pytest

import Detective.capture as capture


def _target(value):
    return value


@pytest.mark.parametrize("late_time", (20.0, 21.0))
def test_late_entry_is_discarded_even_if_the_worker_finishes(monkeypatch, late_time):
    now = [10.0]
    monkeypatch.setattr(capture, "time", SimpleNamespace(monotonic=lambda: now[0]))
    ran = []

    def late():
        ran.append("late")
        now[0] = late_time
        _target(1)

    def following():
        ran.append("following")
        _target(2)

    result = capture.capture_call_inputs(_target, [late, following], deadline=20.0)
    assert result.samples == ()
    assert result.status == "cut"
    assert result.deadline_passed is True
    assert result.contained is True
    assert ran == ["late"]


def test_timely_input_is_kept_but_late_input_is_not(monkeypatch):
    now = [10.0]
    monkeypatch.setattr(capture, "time", SimpleNamespace(monotonic=lambda: now[0]))

    def reaches():
        _target("early")
        now[0] = 20.0
        _target("late")

    result = capture.capture_call_inputs(_target, [reaches], deadline=20.0)
    assert result.samples == (("early",),)
    assert result.status == "cut"
    assert result.deadline_passed is True


def test_a_snapshot_crossing_the_wall_is_neither_rendered_nor_admitted(monkeypatch):
    now = [10.0]
    rendered = []
    monkeypatch.setattr(capture, "time", SimpleNamespace(monotonic=lambda: now[0]))

    class Snapshot:
        def __repr__(self):
            rendered.append(True)
            return "snapshot"

    class SlowCopy:
        def __deepcopy__(self, memo):
            now[0] = 20.0
            return Snapshot()

    result = capture.capture_call_inputs(_target, [lambda: _target(SlowCopy())], deadline=20.0)
    assert result.samples == ()
    assert result.status == "cut"
    assert result.deadline_passed is True
    assert rendered == []


def test_a_repr_crossing_the_wall_cannot_commit_its_snapshot(monkeypatch):
    now = [10.0]
    monkeypatch.setattr(capture, "time", SimpleNamespace(monotonic=lambda: now[0]))

    class SlowRepr:
        def __repr__(self):
            now[0] = 20.0
            return "snapshot"

    result = capture.capture_call_inputs(_target, [lambda: _target(SlowRepr())], deadline=20.0)
    assert result.samples == ()
    assert result.status == "cut"
    assert result.deadline_passed is True


def test_late_return_types_are_excluded_and_the_partial_harvest_is_refused(monkeypatch):
    now = [10.0]
    monkeypatch.setattr(capture, "time", SimpleNamespace(monotonic=lambda: now[0]))

    def reaches():
        _target(1)
        now[0] = 20.0
        _target("late")

    with pytest.raises(capture.HarvestIncomplete) as error:
        capture.capture_return_types(_target, [reaches], deadline=20.0)
    assert error.value.code == "harvest_cut"
    assert error.value.result.codomain == frozenset({"int"})
    assert error.value.result.contained is True
    assert error.value.result.deadline_passed is True


@pytest.mark.parametrize("phase", ("subscription", "startup"))
def test_setup_expiry_runs_no_test(monkeypatch, phase):
    now = [10.0]
    monkeypatch.setattr(capture, "time", SimpleNamespace(monotonic=lambda: now[0]))
    ran = []
    if phase == "subscription":
        subscribe = capture.subscribe

        def delayed_subscribe(*args, **kwargs):
            handle = subscribe(*args, **kwargs)
            now[0] = 20.0
            return handle

        monkeypatch.setattr(capture, "subscribe", delayed_subscribe)
    else:
        start = capture.JoinedWorker.start

        def delayed_start(worker):
            now[0] = 20.0
            return start(worker)

        monkeypatch.setattr(capture.JoinedWorker, "start", delayed_start)

    def reaches():
        ran.append(True)
        _target(1)

    result = capture.capture_call_inputs(_target, [reaches], deadline=20.0)
    assert ran == []
    assert result.samples == ()
    assert result.status == "cut"
    assert result.deadline_passed is True


def test_join_uses_the_budget_remaining_after_worker_start(monkeypatch):
    now = [10.0]
    monkeypatch.setattr(capture, "time", SimpleNamespace(monotonic=lambda: now[0]))
    start = capture.JoinedWorker.start
    join = capture.bounded_join
    allowances = []

    def delayed_start(worker):
        now[0] = 15.0
        return start(worker)

    def observed_join(worker, timeout_s, **kwargs):
        allowances.append(timeout_s)
        return join(worker, timeout_s, **kwargs)

    monkeypatch.setattr(capture.JoinedWorker, "start", delayed_start)
    monkeypatch.setattr(capture, "bounded_join", observed_join)
    result = capture.capture_call_inputs(_target, [lambda: _target(1)], deadline=20.0, per_test_timeout=30.0)
    assert allowances == [5.0]
    assert result.samples == ((1,),)
    assert result.status == "complete"
    assert result.deadline_passed is False


def test_interrupt_while_computing_remaining_time_reaps_the_started_worker(monkeypatch):
    owner = threading.get_ident()
    workers = []
    release = threading.Event()
    start = capture.JoinedWorker.start

    def clock():
        if workers and threading.get_ident() == owner:
            raise KeyboardInterrupt
        return 10.0

    def record_start(worker):
        workers.append(worker)
        return start(worker)

    def runaway():
        _target(1)
        while not release.is_set():
            pass

    monkeypatch.setattr(capture, "time", SimpleNamespace(monotonic=clock))
    monkeypatch.setattr(capture.JoinedWorker, "start", record_start)
    try:
        with pytest.raises(KeyboardInterrupt):
            capture.capture_call_inputs(_target, [runaway], deadline=20.0)
        assert workers
        assert not workers[0].is_alive()
    finally:
        release.set()
        for worker in workers:
            worker.join(2)
