"""Intent tests for the environment gate (Detective #23/#30/#39).

The defect: `converge` certified `✓ COMPLETE` while writing goldens that pin THIS machine.
Three doors, each a different channel into the same failure, and each closed only after the
previous fix proved too narrow:

  door 3  a machine PATH in the returned value      — `assert result == "/private/tmp/ms/data"`
  door 1  an environment VARIABLE read, any spelling — `assert mode() == "STAGING"`
  door 2  a CLOCK read, at any depth                 — `assert result == "abc:2026-08-09"`

Doors 1 and 2 share one root cause that the generated suites alongside this file cannot state,
because they pin behaviour rather than intent: A CAPTURE THAT CALLS THE FUNCTION TWICE IN ONE
ENVIRONMENT CANNOT SEE ENVIRONMENT DEPENDENCE. The two calls agree precisely because nothing
varied between them, so `deterministic` reads True and the value looks perfectly portable. Only
perturbing — proxying `os.environ`, replaying under a different epoch — makes the dependence
observable. Tests written from current output would happily pin the old, wrong answer.

The load-bearing test here is `test_the_proxy_keeps_putenv_in_step_so_a_child_process_sees_it`.
The recording proxy subclasses the real `os._Environ` rather than wrapping a dict, and that
choice is invisible until a captured function sets a variable and spawns a subprocess. A dict
proxy passes every other test in this file and breaks that one.
"""

from __future__ import annotations

import datetime
import os
import subprocess
import sys

from Detective.synthesis.characterization import (
    _EffectSink,
    _RecordingEnviron,
    _try_capture,
    golden_capture_disposition,
    value_capture_coupling,
)

# --------------------------------------------------------------------------------------
# Door 1 — the environment read, under every spelling
# --------------------------------------------------------------------------------------


def test_an_aliased_getenv_is_recorded(monkeypatch):
    """`from os import getenv` was the exact repro, and the reason a static scan cannot win.

    The name `os.environ` never appears in this function's source, so the AST scan that guards
    the witness pass sees nothing. `getenv` resolves `os.environ` at CALL time, which is what
    makes a runtime proxy alias-proof where a scan is not.
    """
    monkeypatch.setenv("APP_MODE", "staging")
    from os import getenv

    def mode(default: str = "dev") -> str:
        return getenv("APP_MODE", default).upper()

    capture = _try_capture(mode, (), {})
    assert capture is not None
    assert "APP_MODE" in capture.environment_reads


def test_an_environment_read_one_helper_down_is_recorded(monkeypatch):
    """Indirection is the other half: the read is not in the function under test at all."""
    monkeypatch.setenv("APP_REGION", "eu")

    def _region() -> str:
        return os.environ.get("APP_REGION", "us")

    def describe(label: str) -> str:
        return f"{label}@{_region()}"

    capture = _try_capture(describe, ("svc",), {})
    assert capture is not None
    assert "APP_REGION" in capture.environment_reads


def test_a_membership_test_counts_as_a_read(monkeypatch):
    """`"CI" in os.environ` branching two ways pins whichever way this machine went."""
    monkeypatch.setenv("CI_PROBE", "1")

    def flavour() -> str:
        return "ci" if "CI_PROBE" in os.environ else "local"

    capture = _try_capture(flavour, (), {})
    assert capture is not None
    assert "CI_PROBE" in capture.environment_reads


def test_a_function_that_reads_nothing_records_nothing():
    """The gate must not refuse ordinary code — a false refusal costs a real pin."""
    capture = _try_capture(lambda n: n * 2, (3,), {})
    assert capture is not None
    assert capture.environment_reads == ()


def test_one_variable_read_many_ways_is_named_once():
    """`get` delegates to `__getitem__`, so a single read arrives twice.

    Not cosmetic: the refusal message names the variables, and "$PATH, $PATH, $PATH" reads as
    three findings.
    """
    sink = _EffectSink()
    proxy = _RecordingEnviron(os.environ, sink)
    proxy.get("PATH")
    proxy["PATH"]
    assert "PATH" in proxy
    assert sink.env_reads == ["PATH"]


def test_the_proxy_keeps_putenv_in_step_so_a_child_process_sees_it():
    """THE reason this subclasses `os._Environ` instead of wrapping a dict.

    The real class is what calls `putenv`, keeping the C-level environment — the one a child
    process inherits — in step with the mapping. A dict proxy satisfies every other test in this
    file and silently breaks this, which is precisely the kind of damage a green suite hides.
    """
    saved = os.environ
    os.environ = _RecordingEnviron(saved, _EffectSink())  # type: ignore[assignment] # noqa: B003
    try:
        os.environ["DETECTIVE_PROBE_VAR"] = "on"
        out = subprocess.run(
            [sys.executable, "-c", "import os; print(os.environ.get('DETECTIVE_PROBE_VAR'))"],
            capture_output=True,
            text=True,
        ).stdout.strip()
    finally:
        os.environ = saved  # type: ignore[assignment] # noqa: B003
        os.environ.pop("DETECTIVE_PROBE_VAR", None)
    assert out == "on"


def test_the_proxy_never_outlives_the_capture():
    """Left installed, every later capture would inherit the previous one's reads."""
    before = os.environ
    _try_capture(lambda: os.environ.get("HOME"), (), {})
    assert os.environ is before


def test_the_proxy_is_restored_even_when_the_function_raises():
    before = os.environ

    def boom() -> str:
        os.environ.get("HOME")
        raise ValueError("boom")

    assert _try_capture(boom, (), {}) is None
    assert os.environ is before


# --------------------------------------------------------------------------------------
# Door 2 — the clock read, at any depth
# --------------------------------------------------------------------------------------


def test_a_clock_read_one_helper_down_is_detected():
    """The #23 repro: `date.today()` below the function under test.

    Captured twice in one second the value is stable, so `deterministic` is True and the golden
    looks sound. It fails the next morning.
    """

    def _stamp() -> str:
        return datetime.date.today().isoformat()

    def report(label: str) -> str:
        return f"{label}:{_stamp()}"

    capture = _try_capture(report, ("abc",), {})
    assert capture is not None
    assert capture.deterministic, "the two same-moment calls agree — that is the trap"
    assert capture.clock_dependent


def test_a_clock_free_function_is_not_flagged():
    capture = _try_capture(lambda n: n + 1, (1,), {})
    assert capture is not None
    assert capture.clock_dependent is False


def test_a_capture_with_a_planned_freeze_is_not_flagged():
    """When `--clock` is in play the emitted test freezes the clock itself, so movement is
    PINNED rather than refused. Flagging it here would regress #24 and refuse a capture the
    tool can legitimately make."""

    def stamp() -> str:
        return datetime.date.today().isoformat()

    capture = _try_capture(stamp, (), {}, clock=1_000_000_000.0)
    assert capture is not None
    assert capture.clock_dependent is False


# --------------------------------------------------------------------------------------
# The decision, stated from intent
# --------------------------------------------------------------------------------------


def test_a_deterministic_environment_read_is_still_refused():
    """The crux of both doors in one line.

    `deterministic=True` is exactly what the old code took as permission to pin. It means "the
    value did not change between two calls in the SAME environment", which is not evidence of
    portability at all.
    """
    assert golden_capture_disposition((), (), ("APP_MODE",), "", False, True) == "refuse_environment_read"


def test_a_deterministic_clock_reader_is_still_refused():
    assert golden_capture_disposition((), (), (), "", True, True) == "refuse_clock_dependent"


def test_a_clean_capture_is_pinned():
    assert golden_capture_disposition((), (), (), "", False, True) == "pin"


def test_each_refusal_reason_stays_distinguishable():
    """Named codes, not a bool: the four reasons ask the author for four different things.

    Collapsing them into one falsy result is what let three defects share a silent drop.
    """
    codes = {
        golden_capture_disposition(("/tmp/x",), (), (), "", False, True),
        golden_capture_disposition((), ("/etc/data",), (), "", False, True),
        golden_capture_disposition((), (), ("HOME",), "", False, True),
        golden_capture_disposition((), (), (), "/Users/me", False, True),
        golden_capture_disposition((), (), (), "", True, True),
    }
    assert len(codes) == 5


def test_an_unstable_value_is_dropped_not_refused():
    """A drop and a refusal are different events: one prints a reason, one does not.

    Keeping them apart is what stops "we said why" and "we said nothing" reading alike.
    """
    assert golden_capture_disposition((), (), (), "", False, False) == "drop_nondeterministic"


def test_an_environment_reason_shuts_the_witness_pass_for_the_whole_function():
    """The link that made the fix actually land.

    With the capture-side refusals in place and this absent, `converge` printed
    "2 golden(s) refused — environment-dependent" AND wrote `assert result == "STAGING"` in the
    same run, because the witness pass is a second, independent producer.
    """
    assert value_capture_coupling("refuse_environment_read") == "function_coupled"
    assert value_capture_coupling("refuse_clock_dependent") == "function_coupled"


def test_a_machine_path_stays_a_per_value_objection():
    """Handled by `golden_assert_line` wherever a value is rendered (#30), so the witness pass
    is correctly left open rather than shut for a reason already covered per-value."""
    assert value_capture_coupling("refuse_machine_path") == "value_local"


def test_a_pinnable_capture_couples_nothing():
    assert value_capture_coupling("pin") == "none"
    assert value_capture_coupling("drop_nondeterministic") == "none"
