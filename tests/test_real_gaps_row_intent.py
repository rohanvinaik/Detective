"""The audit's `✗ real gaps` row says what is true of a mutant a test kills only by a crash (Detective #101).

THE DEFECT (lane DX, `parse_compute_budget` before its value tests existed): `✗ real gaps  N killable
mutant(s) no test kills`, when the mutant IS killed (a test fails under it by a crash) and merely lacks a
value pin. "No test kills" is false of it: the suite is not blind to it, it asserts nothing about the value.
The count of such gaps is `SuiteAudit.killable_crash_detected`.

Second sentence (Detective #142, audit's closing block): for a function that reads external state, the block
said `Writes  the missing tests, and wires them into pytest`, though the converge it names hands back to a
fixture first. `environment_route` is the question converge answers; audit now asks it too.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from Detective.cli import audit_writes_text, environment_route, real_gaps_text


@pytest.mark.parametrize(
    ("gaps", "crash", "says", "never"),
    [
        (3, 0, "3 killable mutant(s) no test kills", "crash"),
        (2, 2, "a test kills only by a crash", "no test kills"),
        (5, 2, "3 no test kills; 2 a test kills only by a crash", None),
        (1, 1, "no test pins the value", "no test kills"),
    ],
)
def test_the_row_states_the_fact_each_count_rests_on(gaps, crash, says, never):
    text = real_gaps_text(gaps, crash)
    assert says in text and text.startswith(str(gaps))
    if never:
        assert never not in text


def test_a_count_larger_than_the_gaps_is_not_read_as_undetected():
    assert "no test kills" not in real_gaps_text(1, 4)


_SOURCE = "def f(x):\n    return x + 1\n"
# Crashes under `return None`, pins no value: the mutant is killed, and unpinned.
_TEST = "from m import f\n\n\ndef test_runs():\n    assert f(1) + 1 is not None\n"


def _run(cwd, *argv):
    return subprocess.run(
        [sys.executable, "-m", "Detective", *argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
        env={k: v for k, v in os.environ.items() if k != "PYTHONUNBUFFERED"},
    )


def test_the_real_page_does_not_say_no_test_kills_of_a_crash_killed_mutant(tmp_path: Path):
    project = tmp_path / "proj"
    (project / "tests").mkdir(parents=True)
    (project / "m.py").write_text(_SOURCE)
    (project / "tests" / "test_m.py").write_text(_TEST)
    (project / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\npythonpath = ["."]\ntestpaths = ["tests"]\n'
    )
    assert _run(project, "regime", "--migrate", "--project-root", str(project)).returncode == 0
    page = _run(project, "audit", "m.py::f").stdout
    payload = json.loads(_run(project, "audit", "m.py::f", "--json").stdout)
    assert payload["killable_crash_detected"] >= 1, payload["killable_crash_detected"]
    row = next(line for line in page.splitlines() if "real gaps" in line)
    assert "a test kills only by a crash" in row, row
    assert "no test kills" not in row or "no test kills;" in row


# ── the closing block's `Writes` row (#142) ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("gate", "line_gap", "killable", "route"),
    [
        ("process_state", False, True, "environment_fixture"),  # outranks the witness
        ("process_state", True, True, "environment_fixture"),
        ("fixture", True, False, "environment_fixture"),
        ("fixture", True, True, ""),  # a killable witness is left to pin: converge writes it
        ("fixture", False, True, ""),
        ("clock", False, True, "declare_clock"),
        ("env", True, True, "declare_env"),
        ("clock_env", False, False, "declare_clock"),
        ("none", True, True, ""),
        ("", True, True, ""),
    ],
)
def test_the_environment_route_is_the_question_converge_answers(gate, line_gap, killable, route):
    assert environment_route(gate, line_gap, killable) == route


def test_the_writes_row_promises_only_what_the_named_converge_does():
    assert audit_writes_text("") == "the missing tests, and wires them into pytest."
    for route in ("environment_fixture", "declare_clock", "declare_env"):
        text = audit_writes_text(route)
        assert "missing tests" not in text and text.startswith("nothing"), text
    assert "--clock" in audit_writes_text("declare_clock") and "--env" in audit_writes_text("declare_env")
    assert audit_writes_text("a_route_nobody_decided") == audit_writes_text(""), "unknown reads as no gate"


_STATE_SOURCE = (
    "import sys\n\n\ndef backend(name: str) -> str:\n"
    "    mod = sys.modules.get(name)\n    if mod is None:\n        return name\n"
    "    return f\"{name} {getattr(mod, '__version__', '')}\".strip()\n"
)
_STATE_TEST = (
    "from mod import backend\n\n\ndef test_unloaded():\n"
    '    assert backend("definitely_not_loaded_xyz") == "definitely_not_loaded_xyz"\n\n\n'
    'def test_loaded_weak():\n    assert backend("json").startswith("json")\n'
)


def _page(tmp_path, source, test, function):
    project = tmp_path / "proj"
    (project / "tests").mkdir(parents=True)
    (project / "mod.py").write_text(source)
    (project / "tests" / "test_mod.py").write_text(test)
    (project / "pyproject.toml").write_text('[tool.pytest.ini_options]\ntestpaths = ["tests"]\n')
    assert _run(project, "regime", "--migrate", "--project-root", str(project)).returncode == 0
    return _run(project, "audit", f"mod.py::{function}").stdout


def test_a_process_state_function_is_not_promised_written_tests(tmp_path: Path):
    page = _page(tmp_path, _STATE_SOURCE, _STATE_TEST, "backend")
    writes = next(line for line in page.splitlines() if "· Writes" in line)
    assert "missing tests" not in writes and "fixture" in writes, writes


def test_a_plain_function_keeps_the_promise(tmp_path: Path):
    page = _page(
        tmp_path,
        "def g(x):\n    return x + 1\n",
        "from mod import g\n\n\ndef test_g():\n    assert g(1) > 0\n",
        "g",
    )
    writes = next(line for line in page.splitlines() if "· Writes" in line)
    assert "the missing tests, and wires them into pytest" in writes, writes
