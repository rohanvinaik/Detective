"""Tests for HarvestResult, in-worker thread binding, and containment gating (W#32).

Verifies:
1. HarvestResult exposes typed samples, codomain, contained, and status.
2. Uncontained worker execution produces contained=False and status="uncontained".
3. In-worker thread binding ignores target calls from ambient threads.
4. Foreign profiler on sys.setprofile does not cause harvest refusal.
5. classify_survivors sets measurement_valid=False on uncontained harvest.
"""

from __future__ import annotations

import sys
import threading
import time

import pytest

from Detective.capture import (
    HarvestIncomplete,
    HarvestResult,
    capture_call_inputs,
    capture_return_types,
)


def test_a_type_sample_cap_cannot_hide_a_later_none_return():
    def target(flag):
        return 7 if flag else None

    with pytest.raises(HarvestIncomplete) as error:
        capture_return_types(target, [lambda: target(True), lambda: target(False)], max_samples=1)
    assert error.value.code == "harvest_sample_limit"
    assert error.value.result.codomain == frozenset({"int"})


def _target(x: int, y: str = "ok") -> str:
    return f"{y}:{x}"


def test_harvest_result_typed_properties() -> None:
    res = HarvestResult(((1, "a"), (2, "b")), contained=True, status="enough")
    assert len(res) == 2
    assert res[0] == (1, "a")
    assert res.contained is True
    assert res.status == "enough"
    # Backwards-compatible equality with list/tuple
    assert res == [(1, "a"), (2, "b")]
    assert [(0, "z")] + res == [(0, "z"), (1, "a"), (2, "b")]


def test_in_worker_thread_binding_ignores_ambient_threads() -> None:
    """Target calls from ambient non-worker threads must not be captured."""
    ambient_done = threading.Event()

    def ambient_worker():
        _target(999, "ambient")
        ambient_done.set()

    def test_fn():
        # Spin up an ambient thread that calls the target
        t = threading.Thread(target=ambient_worker)
        t.start()
        ambient_done.wait(5.0)
        t.join(5.0)
        # Call target from within the test worker
        _target(42, "legit")

    result = capture_call_inputs(_target, [test_fn])
    assert result.contained is True
    # 999 from ambient thread must be filtered out
    assert result == [(42, "legit")]


def test_uncontained_execution_marks_contained_false() -> None:
    """A worker that refuses to stop within timeout is marked uncontained."""

    def stubborn_test():
        _target(1, "start")
        # Run in a loop that swallows async exceptions to simulate an uncontainable worker
        end = time.time() + 0.5
        while time.time() < end:
            try:
                time.sleep(0.01)
            except BaseException:
                pass

    # Use a tiny per_test_timeout so bounded_join times out quickly
    result = capture_call_inputs(_target, [stubborn_test], per_test_timeout=0.02)
    assert result.contained is False
    assert result.status == "uncontained"


def test_foreign_profiler_on_setprofile_does_not_block_sys_monitoring(monkeypatch) -> None:
    """A C-level profiler occupying sys.setprofile must not cause harvest refusal."""

    class MockForeignProfilerState:
        pass

    # Mock foreign C profiler state in sys.getprofile()
    monkeypatch.setattr(sys, "getprofile", lambda: MockForeignProfilerState())

    def test_fn():
        _target(10, "profiled")

    result = capture_call_inputs(_target, [test_fn])
    assert result.contained is True
    assert result == [(10, "profiled")]

    codomain = capture_return_types(_target, [test_fn])
    assert "str" in codomain


def test_return_observation_includes_none_as_a_real_type() -> None:
    """Fork-2 applicability must account for every observed return type, including None."""

    def optional(flag):
        return 7 if flag else None

    def reaches_both():
        assert optional(True) == 7
        assert optional(False) is None

    assert capture_return_types(optional, [reaches_both]) == frozenset({"int", "NoneType"})


def test_return_observation_refuses_a_contained_timeout() -> None:
    """A worker stopping is containment evidence, not evidence the observation completed."""

    def runaway():
        _target(1)
        while True:
            pass

    with pytest.raises(HarvestIncomplete) as error:
        capture_return_types(_target, [runaway], per_test_timeout=0.01)
    assert error.value.code == "harvest_cut"
    assert error.value.result.codomain == frozenset({"str"})
    assert error.value.result.contained is True


def test_return_observation_refuses_an_uncontained_worker(monkeypatch) -> None:
    """A partial type set cannot escape as an ordinary successful codomain observation."""
    from Wesker import interrupt

    release = threading.Event()
    finished = threading.Event()

    def blocked():
        try:
            _target(1)
            release.wait(2)
        finally:
            finished.set()

    monkeypatch.setattr(interrupt, "abandon", lambda worker: False)
    try:
        with pytest.raises(HarvestIncomplete) as error:
            capture_return_types(_target, [blocked], per_test_timeout=0.01)
        assert error.value.code == "harvest_uncontained"
        assert error.value.result.codomain == frozenset({"str"})
        assert error.value.result.contained is False
    finally:
        release.set()
        assert finished.wait(2)


@pytest.mark.parametrize("status", ["cut", "uncontained"])
def test_cli_reports_incomplete_codomain_observation_as_invalid_measurement(
    status, monkeypatch, tmp_path, capsys
):
    """The observation's failure must survive the real CLI boundary in its own channel."""
    import json

    from Detective import cli

    partial = HarvestResult(codomain=frozenset({"int"}), contained=status != "uncontained", status=status)

    def refused(args):
        raise HarvestIncomplete(partial)

    monkeypatch.setattr(cli, "_run_live", refused)
    result = cli.main(["audit", "m.py::f", "--json", "--project-root", str(tmp_path)])
    report = json.loads(capsys.readouterr().out)
    assert result == 3
    assert report["verdict"] == "INVALID_MEASUREMENT"
    assert report["reason"] == f"harvest_{status}"
    assert report["observation"]["partial_return_types"] == ["int"]
    assert report["observation"]["contained"] is (status != "uncontained")


@pytest.mark.parametrize("fault", ["uncontained", "unavailable", "observer_fault"])
@pytest.mark.parametrize("phase", ["classification", "verification", "audit"])
@pytest.mark.parametrize("surface", ["library", "human", "json"])
def test_proof_consumers_preserve_required_observation_refusal(
    tmp_path, monkeypatch, capsys, fault, phase, surface
):
    """Communicating Determinism §3: different refusal causes must survive every consumer."""
    import importlib
    import json

    from Wesker.monitoring import MonitoringObservationFailed, MonitoringUnavailable

    from Detective import cli
    from Detective.capture import ObservationIncomplete

    convergence = importlib.import_module("Detective.converge")
    (tmp_path / "probe.py").write_text("def scale(x: int) -> int:\n    return x * 2\n")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_probe.py").write_text(
        "from probe import scale\n\ndef test_zero():\n    assert scale(0) == 0\n"
        + ("\ndef test_nonzero():\n    assert scale(1) == 2\n" if phase != "classification" else "")
    )
    (tmp_path / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\npythonpath = ["."]\ntestpaths = ["tests"]\n'
    )
    error = {
        "uncontained": ObservationIncomplete("outcome_uncontained", "live worker", contained=False),
        "unavailable": MonitoringUnavailable("monitoring unavailable"),
        "observer_fault": MonitoringObservationFailed("observer_fault: broken observer", 7),
    }[fault]

    def refused(*args, **kwargs):
        raise error

    if phase == "audit":
        audit = importlib.import_module("Detective.audit")
        monkeypatch.setattr(audit, "classify_survivors", refused)
    elif phase == "classification":
        monkeypatch.setattr(convergence, "classify_survivors", refused)
    else:
        measured = convergence.profile

        def verification_refused(*args, **kwargs):
            if kwargs.get("isolated"):
                raise error
            return measured(*args, **kwargs)

        monkeypatch.setattr(convergence, "profile", verification_refused)
    if surface == "library":
        with pytest.raises(type(error)) as caught:
            if phase == "audit":
                audit.audit_suite("probe.py", "scale", str(tmp_path))
            else:
                convergence.converge("probe.py", "scale", str(tmp_path), write_dir=None, deadline_s=10)
        assert caught.value is error
        return

    command = "audit" if phase == "audit" else "converge"
    argv = [command, "probe.py::scale", "--project-root", str(tmp_path)]
    if command == "converge":
        argv += ["--write-dir", "", "--deadline", "10"]
    if surface == "json":
        argv.append("--json")
    code = cli.main(argv)
    emitted = capsys.readouterr().out
    assert code == (2 if fault == "unavailable" else 3)
    assert "✓ COMPLETE" not in emitted
    assert "AUTHOR INPUT" not in emitted
    assert "behaviour is pinned" not in emitted
    assert "DO THIS" not in emitted
    if surface == "json":
        payload = json.loads(emitted)
        assert (
            payload["reason"]
            == {
                "uncontained": "outcome_uncontained",
                "unavailable": "monitoring_unavailable",
                "observer_fault": "observer_fault",
            }[fault]
        )
        assert payload["verdict"] == ("REFUSED" if fault == "unavailable" else "INVALID_MEASUREMENT")
        if fault == "uncontained":
            assert payload["observation"]["contained"] is False
    else:
        assert str(error) in emitted
        assert emitted.rstrip().endswith(str(error))
