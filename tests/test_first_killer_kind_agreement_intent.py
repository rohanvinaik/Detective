"""converge and audit agree on which mutants are value-pinned when the first killer only crashes it.

The lane brief's claim: on `Wesker/monitoring.py::harness_slowdown`, `converge` ended `Incomplete: 1 killable
(no value pin) · 47/50 killed` while `audit` said `complete … 46/50 value-pinned`, and the mutant it named
(`return (ratio, 'slower')` -> `return None`) is value-pinned by an existing test. The suspected mechanism was
credit to the FIRST killer's kind. This file states the agreement the two verbs owe on the smallest fixture of
that shape: test A (runs first) kills the mutant by a CRASH, test B pins its value by an ASSERTION.

Measured finding (see the commit): the first-killer mechanism does not exist on this code (Wesker's
`killed_by` is "assertion" whenever ANY test pins the value, independent of order), and this fixture agrees.
The harness_slowdown disagreement is an in-process versus isolated difference for a function the measuring
engine itself calls, not an accounting rule; `converge --isolated` on it is COMPLETE, 48/50, no new test.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

_SOURCE = "def f(x):\n    return (x + 1, 'k')\n"
_TESTS = (
    "from m import f\n\n\n"
    "def test_a_crash_first():\n    n, tag = f(1)\n    assert n is not None\n\n\n"
    "def test_b_value_pin():\n    assert f(1) == (2, 'k')\n"
)


def _run(cwd: Path, *argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "Detective", *argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
        env={k: v for k, v in os.environ.items() if k != "PYTHONUNBUFFERED"},
    )


def test_a_mutant_a_later_test_value_pins_is_value_pinned_by_both_verbs(tmp_path):
    project = tmp_path / "proj"
    (project / "tests").mkdir(parents=True)
    (project / "m.py").write_text(_SOURCE)
    (project / "tests" / "test_m.py").write_text(_TESTS)
    (project / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\npythonpath = ["."]\ntestpaths = ["tests"]\n'
    )
    assert _run(project, "regime", "--migrate", "--project-root", str(project)).returncode == 0
    audit = json.loads(_run(project, "audit", "m.py::f", "--json").stdout)
    converge = json.loads(_run(project, "converge", "m.py::f", "--json").stdout)
    return_none = [r for r in audit.get("killable_gaps", []) if "return None" in str(r) or "STATE" in str(r)]
    assert not return_none, "audit calls a value-pinned mutant a gap"
    assert audit["value_killed"] == converge["value_killed"], (
        audit["value_killed"],
        converge["value_killed"],
    )
    assert converge["functionally_complete"] is True
