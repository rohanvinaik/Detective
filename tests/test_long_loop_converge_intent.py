"""Intent: Detective#80 rework — a function that legitimately loops 300,000 times is not refused.

The first version of the harvest and witness-search step budgets turned an original that runs past
`STEP_PROBE_CAP` into a dead end: the codomain harvest raised `harvest_step_budget` with no command, and an
input the original loops on past the cap was `original-step-budget`, never classified. Before that change
this function converged `✓ COMPLETE`; with it, `converge` ended `Incomplete`. These are the user's real,
baseline-passing tests, and nothing diverged.

This runs the real CLI end to end on a one-test project whose result depends on an argument, and asserts
the FINAL line is the complete one.
"""

from __future__ import annotations

import os
import subprocess
import sys

_LOOPY = "def total(x):\n    t = 0\n    for _ in range(300_000):\n        t += x\n    return t\n"
_TEST = "from loopy import total\n\n\ndef test_total():\n    assert total(2) == 600_000\n"
_PYPROJECT = '[project]\nname = "fx"\nversion = "0"\n[tool.pytest.ini_options]\npythonpath = ["."]\n'


def _run(args, cwd, home):
    env = {k: v for k, v in os.environ.items() if k != "PYTHONUNBUFFERED"}
    env["HOME"] = str(home)
    return subprocess.run(
        [sys.executable, "-m", "Detective", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )


def test_a_function_that_loops_past_the_probe_cap_converges_complete(tmp_path):
    project = tmp_path / "project"
    (project / "tests").mkdir(parents=True)
    (project / "loopy.py").write_text(_LOOPY)
    (project / "tests" / "test_loopy.py").write_text(_TEST)
    (project / "pyproject.toml").write_text(_PYPROJECT)
    home = tmp_path / "home"
    home.mkdir()
    migrated = _run(["regime", "--migrate", "--project-root", str(project)], project, home)
    assert migrated.returncode == 0, migrated.stdout + migrated.stderr

    result = _run(["converge", "loopy.py::total", "--deadline", "900"], project, home)
    finals = [line for line in result.stdout.splitlines() if line.startswith("FINAL ")]
    assert len(finals) == 1, result.stdout[-2000:]
    assert finals[0].startswith("FINAL loopy.py::total: ✓ COMPLETE"), finals[0]
    assert "INCOMPLETE" not in result.stdout and "harvest_step_budget" not in result.stdout
