"""Intent: a DO THIS never names a trace bound the run already lifted (Detective #142).

THE DEFECT. `converge 'Detective/validity.py::original_also_fails_cause' --trace-budget 0
--trace-session-budget 0` (both "0 = unbounded") ended `UNGATEABLE — the profile was cut`, and its
DO THIS was the same command with the same two flags: a loop. The cut itself came from Wesker
185985c (a routed test parked on a child process could not be stopped; Wesker 62bf514 kills the wait
and the same command is COMPLETE), but the page's advice was Detective's own: `_converge_commands`
printed `--trace-budget 0 --trace-session-budget 0` whatever the run carried.

THE RULING. `trace_remedy` decides from which bounds the run still has: lift both / the per-test one /
the session one, or `none_left`, where no trace flag can change the cut and the page hands back
(`inspect_refusal`) instead of naming a command that will do nothing.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from types import SimpleNamespace

import pytest

from Detective.cli import (
    UniverseOptions,
    _converge_commands,
    _trace_budget,
    _trace_session_budget,
    trace_remedy,
)


@pytest.mark.parametrize(
    ("per_test", "session", "code"),
    [
        (True, True, "lift_both"),
        (True, False, "lift_per_test"),
        (False, True, "lift_session"),
        (False, False, "none_left"),
    ],
)
def test_the_remedy_names_only_the_bounds_the_run_still_has(per_test, session, code):
    assert trace_remedy(per_test, session) == code


def _argv(universe):
    argv, _then = _converge_commands(
        "repair_measurement", "trace_budget", "run", "m.py::f", ".", (), None, universe=universe
    )
    return argv


def test_a_run_with_both_bounds_is_told_to_lift_both():
    argv = _argv(UniverseOptions())
    assert argv[-4:] == ("--trace-budget", "0", "--trace-session-budget", "0")


def test_a_run_that_lifted_one_bound_is_told_only_the_other():
    assert _argv(UniverseOptions(trace_bounded=False))[-2:] == ("--trace-session-budget", "0")
    assert _argv(UniverseOptions(trace_session_bounded=False))[-2:] == ("--trace-budget", "0")
    assert "--trace-session-budget" not in _argv(UniverseOptions(trace_session_bounded=False))


def test_a_fully_unbounded_run_gets_no_command():
    assert _argv(UniverseOptions(trace_bounded=False, trace_session_bounded=False)) is None


def test_the_options_are_read_from_the_parsed_arguments_through_the_cli_derivation():
    args = SimpleNamespace(trace_budget=0, trace_session_budget=0)
    u = UniverseOptions.of(args)
    assert (u.trace_bounded, u.trace_session_bounded) == (False, False)
    assert _trace_budget(args) is None and _trace_session_budget(args) is None
    u = UniverseOptions.of(SimpleNamespace(trace_budget=5, trace_session_budget=0))
    assert (u.trace_bounded, u.trace_session_bounded) == (True, False)


# ------------------------------------------------------------------ the real CLI, a slow routed test

MOD = '''
def classify(n):
    """Sign of n.

    Operations:
        COMPARE: n below zero, and equal to zero
    """
    if n < 0:
        return "neg"
    if n == 0:
        return "zero"
    return "pos"
'''
TESTS = """
    import time
    from mod import classify


    def test_neg():
        time.sleep(1.5)
        assert classify(-1) == "neg"


    def test_zero():
        assert classify(0) == "zero"


    def test_pos():
        assert classify(5) == "pos"
"""


def test_a_slow_routed_test_under_unbounded_flags_completes_and_prints_no_repeat(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "mod.py").write_text(textwrap.dedent(MOD))
    (tmp_path / "tests" / "test_mod.py").write_text(textwrap.dedent(TESTS))
    (tmp_path / "pyproject.toml").write_text('[tool.pytest.ini_options]\npythonpath = ["."]\n')
    env = {**os.environ, "HOME": str(tmp_path / "home"), "PYTHONPATH": os.pathsep.join(sys.path)}
    (tmp_path / "home").mkdir()
    run = lambda *a: subprocess.run(  # noqa: E731
        [sys.executable, "-m", "Detective", *a],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
    )
    run("regime", "--migrate", "--project-root", str(tmp_path))
    flags = ("--trace-budget", "0", "--trace-session-budget", "0")
    out = run("converge", "mod.py::classify", "--deadline", "600", *flags, "--json")
    rec = json.loads(out.stdout)
    assert rec["cut_reasons"] == [], out.stderr[-2000:]
    # whatever it ended on, a printed command never repeats an option the invocation already carried
    argv = (rec.get("decision") or {}).get("step", {}).get("argv") or []
    assert not (set(flags) & {a for a in argv if a.startswith("--")} and set(argv) >= set(flags))
