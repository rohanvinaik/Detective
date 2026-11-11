"""#101: a clock-gated residual was routed to an `--input` converge had already run, never to the `--clock`
it names. `converge_next_action` had no environment input, so `environment_gated` was only a caveat
prepended to the action and the decision fell through to `close_the_gap`.

The pure decision now takes the gating fact (`environment_gate_kind`'s code): a declarable capability
(clock, env) routes to `--clock` / the `--env` declaration, a read no capability covers routes to the
fixture hand-back, and the `--input` ask remains for argument-gated lines only."""

import os
import subprocess
import sys
import textwrap

import pytest

from Detective.cli import converge_next_action, converge_step, environment_gate_kind

CLOCK = "reads the clock via time.time()"
ENVV = "reads process env via os.environ['MODE']"
FILE = "reads the filesystem via Path.exists()"
DATE = "reads the clock via datetime.now()"


@pytest.mark.parametrize(
    ("reads", "clock", "env", "expected"),
    [
        ([], False, False, "none"),
        ([CLOCK], False, False, "clock"),
        ([CLOCK], True, False, "none"),
        ([ENVV], False, False, "env"),
        ([ENVV], False, True, "none"),
        ([CLOCK, ENVV], False, False, "clock_env"),
        ([CLOCK, ENVV], True, False, "env"),
        ([FILE], False, False, "fixture"),
        ([DATE], True, True, "fixture"),
        ([CLOCK, FILE], False, False, "clock"),
        ([CLOCK, FILE], True, False, "fixture"),
    ],
)
def test_environment_gate_kind(reads, clock, env, expected):
    assert environment_gate_kind(reads, clock, env) == expected


def _next(gate, killable=False, gap=True, session_reason="", **kw):
    return converge_next_action("incomplete", session_reason, killable, gap, env_gate=gate, **kw)


def test_clock_gated_gap_routes_to_clock_not_input():
    assert _next("clock") == "declare_clock"
    assert _next("clock_env") == "declare_clock"
    assert _next("clock", killable=True) == "declare_clock"


def test_env_gated_gap_routes_to_env_declaration():
    assert _next("env") == "declare_env"


def test_fixture_gated_gap_is_a_hand_back_but_yields_to_a_killable_witness():
    assert _next("fixture") == "environment_fixture"
    assert _next("fixture", killable=True) == "close_the_gap"


def test_argument_gated_gap_keeps_the_input_ask():
    assert _next("none") == "close_the_gap"
    assert converge_next_action("incomplete", "", True, True) == "close_the_gap"


def test_gate_never_outranks_a_measurement_block_or_a_settled_run():
    assert converge_next_action("complete", "", False, False, env_gate="clock") == "settled"
    assert _next("clock", load_failed=True) == "fix_load"
    assert converge_next_action("stale", "", True, True, env_gate="clock") == "rerun_stale"
    assert _next("clock", session_reason="empty_collection") == "fix_collection"
    assert _next("clock", session_reason="empty_collection", wrote_runnable_suite=True) == "declare_clock"


def test_steps_name_the_move_each_code_prints():
    assert converge_step("declare_clock", "", "", False, "", "not_applicable") == ("run", "")
    assert converge_step("declare_env", "", "", False, "", "not_applicable") == ("supply", "")
    assert converge_step("environment_fixture", "", "", False, "", "not_applicable") == (
        "hand_back",
        "environment_gated",
    )


def _converge(d, *extra):
    env = dict(os.environ, HOME=os.path.join(d, "home"))
    env["PYTHONPATH"] = os.pathsep.join(sys.path)
    return subprocess.run(
        [sys.executable, "-m", "Detective.cli", "converge", "cases.py::stamp", *extra],
        cwd=d,
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
    ).stdout


def test_the_issues_three_run_sequence(tmp_path):
    """Run 1 names `--clock`; the printed command, run verbatim, reaches COMPLETE; no `--input` is asked
    for the line no argument reaches."""
    d = str(tmp_path)
    os.makedirs(os.path.join(d, "home"))
    os.makedirs(os.path.join(d, "tests"))
    with open(os.path.join(d, "cases.py"), "w") as fh:
        fh.write(
            textwrap.dedent(
                """\
                import time

                def stamp(label: str) -> str:
                    return f"{label}@{int(time.time())}"
                """
            )
        )
    with open(os.path.join(d, "tests", "test_other.py"), "w") as fh:
        fh.write("def test_other():\n    assert 1 + 1 == 2\n")
    env = dict(os.environ, HOME=os.path.join(d, "home"), PYTHONPATH=os.pathsep.join(sys.path))
    subprocess.run(
        [sys.executable, "-m", "Detective.cli", "regime", "--migrate", "--project-root", d],
        cwd=d,
        env=env,
        capture_output=True,
        timeout=300,
    )
    first = _converge(d)
    do_this = next(line for line in first.splitlines() if line.startswith("DO THIS:"))
    assert "--clock" in do_this and "--input" not in do_this
    printed = do_this.removeprefix("DO THIS:").split("--clock")[1].split()[0]
    second = _converge(d, "--clock", printed)
    assert any(ln.startswith("FINAL") and "✓ COMPLETE" in ln for ln in second.splitlines())
