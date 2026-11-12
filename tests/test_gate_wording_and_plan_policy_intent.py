"""Two wrong words on otherwise right pages (Detective #101, #52).

(a) The terse converge row `· env-gated N read(s) gate uncovered line(s) — fixture/manual, not --input` said
"fixture/manual" for a clock read that `--clock` covers, directly above a `DO THIS … --clock` that was right.
The row now takes `environment_gate_kind`'s code, the one the ladder routes on.

(b) `audit --plan` estimated the ONE-sign mutant count under `--two-sign` (`engine.trace_tier` took no
policy), so it priced an audit it would not run. The estimate takes the run's policy and the page
labels the policy it was made under.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from Detective.cli import env_gated_row_text, plan_policy_label

_CLOCK_TARGET = (
    "import time\n\n\ndef is_old(ts: float) -> str:\n"
    '    if time.time() - ts > 60:\n        return "old"\n    return "new"\n'
)
_CLOCK_TEST = (
    'import time\n\nfrom m import is_old\n\n\ndef test_new():\n    assert is_old(time.time()) == "new"\n'
)


def _run(cwd: Path, *argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "Detective", *argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
        env=dict(os.environ),
    )


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    (root / "tests").mkdir(parents=True)
    (root / "m.py").write_text(_CLOCK_TARGET)
    (root / "tests" / "test_m.py").write_text(_CLOCK_TEST)
    (root / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\npythonpath = ["."]\ntestpaths = ["tests"]\n'
    )
    assert _run(root, "regime", "--migrate", "--project-root", str(root)).returncode == 0
    return root


@pytest.mark.parametrize(
    ("kind", "phrase"),
    [
        ("clock", "`--clock` covers them"),
        ("env", "`--env` covers them"),
        ("clock_env", "`--clock` and `--env` cover them"),
        ("process_state", "controls the interpreter state"),
        ("fixture", "fixture/manual"),
        ("none", "covered by what this run declared"),
    ],
)
def test_the_row_says_what_the_gate_kind_says_and_only_fixture_says_fixture(kind, phrase):
    text = env_gated_row_text(kind, 2)
    assert text.startswith("2 read(s) gate uncovered line(s) — ") and phrase in text
    assert ("fixture/manual" in text) == (kind == "fixture")
    assert "not --input" in text or kind == "none"


def test_an_unknown_kind_is_named_never_given_another_kinds_remedy():
    assert "unrecognised gate kind zzz" in env_gated_row_text("zzz", 1)


def test_a_clock_read_row_names_clock_above_the_clock_directive(project):
    page = _run(project, "converge", "m.py::is_old").stdout
    row = next(line for line in page.splitlines() if "· env-gated" in line)
    assert "`--clock` covers them" in row and "fixture/manual" not in row
    assert "DO THIS:  detective converge 'm.py::is_old' --clock" in page


def test_the_row_after_the_clock_is_declared_stops_claiming_the_gate(project):
    page = _run(project, "converge", "m.py::is_old", "--clock", "1700000000").stdout
    rows = [line for line in page.splitlines() if "· env-gated" in line]
    assert all("fixture/manual" not in row for row in rows)


def test_the_plan_policy_label_names_each_policy():
    assert plan_policy_label(False) == "one-sign universe"
    assert "two-sign universe" in plan_policy_label(True) and "lower bound" not in plan_policy_label(False)


def test_the_plan_estimates_the_universe_of_the_run_it_prices(project):
    one = json.loads(_run(project, "audit", "m.py::is_old", "--plan", "--json").stdout)
    two = json.loads(_run(project, "audit", "m.py::is_old", "--plan", "--two-sign", "--json").stdout)
    assert one["tier2"]["policy"] == "one-sign universe"
    assert two["tier2"]["policy"].startswith("two-sign universe")
    assert two["tier2"]["mutant_count"] > one["tier2"]["mutant_count"], "OUTPUT operators join the universe"
    page = _run(project, "audit", "m.py::is_old", "--plan", "--two-sign").stdout
    assert "[two-sign universe" in page
    assert "[one-sign universe]" in _run(project, "audit", "m.py::is_old", "--plan").stdout
