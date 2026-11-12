"""A line open only because named tests were not consulted is not a gap converge writes (Detective #107, #77).

The defect: `audit.missing_line_standing` types such a line ``unconsulted`` and the page printed
``✗ unproven`` with the tests named, yet the LADDER (`audit_next_action`, `converge_next_action`) read the
line as a count of missing lines and returned ``close_the_gap``: ``DO THIS: detective converge …``, a
command that writes a test from an input for a line no consulted test runs, over a line a named test may
already run. The fact the page already printed never reached the decision.

These tests drive the real CLI on a project whose only test of the branch dispatches by a computed
``getattr`` (the fixture of `test_static_route_completeness_intent`), and pin the pure decisions.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from Detective.audit import unconsulted_gap_standing
from Detective.cli import audit_next_action, audit_step, converge_next_action, converge_step

_PYPROJECT = '[tool.pytest.ini_options]\npythonpath = ["src", "tests"]\ntestpaths = ["tests"]\n'
_DYNAMIC_TEST = (
    "from pkg import m\n\n\ndef test_big_by_computed_name():\n"
    "    name = chr(102)\n    assert getattr(m, name)(50) == {big}\n"
)
# Only-unconsulted: the branch body is `pass`, so every mutant that matters is equivalent and no killable
# mutant is left; the one open line is the `pass`, run only by the dynamic test.
_ONLY = (
    "def f(x):\n    y = x\n    if x > 10:\n        pass\n    return y\n",
    "from pkg.m import f\n\n\ndef test_one():\n    assert f(1) == 1\n\n\n"
    "def test_two():\n    assert f(2) == 2\n",
    "50",
)
# Mixed: the big branch is also a killable gap (the plain tests never reach `return "big"`).
_MIXED = (
    'def f(x):\n    if x > 10:\n        return "big"\n    return "small"\n',
    "from pkg.m import f\n\n\ndef test_one():\n    assert f(1) == 'small'\n\n\n"
    "def test_two():\n    assert f(2) == 'small'\n",
    "'big'",
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


def _project(tmp_path: Path, shape: tuple[str, str, str]) -> Path:
    target, plain, big = shape
    project = tmp_path / "proj"
    (project / "src" / "pkg").mkdir(parents=True)
    (project / "tests").mkdir()
    (project / "pyproject.toml").write_text(_PYPROJECT)
    (project / "src" / "pkg" / "__init__.py").write_text("")
    (project / "src" / "pkg" / "m.py").write_text(target)
    (project / "tests" / "test_plain.py").write_text(plain)
    (project / "tests" / "test_m.py").write_text(_DYNAMIC_TEST.format(big=big))
    assert _run(project, "regime", "--migrate", "--project-root", str(project)).returncode == 0
    return project


def test_audit_over_only_unconsulted_lines_hands_back_and_names_the_tests(tmp_path):
    project = _project(tmp_path, _ONLY)
    report = json.loads(_run(project, "audit", "src/pkg/m.py::f", "--json").stdout)
    decision = report["decision"]
    assert [s for _, s in report["missing_line_standings"]] == ["unconsulted"]
    assert decision["code"] == "consult_named_tests"
    assert decision["step"]["kind"] == "hand_back" and decision["step"]["remedy"] == "consult_named_tests"
    assert decision["step"]["argv"] is None
    assert decision["step"]["then"] == ["audit", "src/pkg/m.py::f"]
    assert decision["state"]["not_consulted_dynamic"] == report["not_consulted_dynamic"] != []
    page = _run(project, "audit", "src/pkg/m.py::f").stdout
    assert "DO THIS" not in page and "detective converge" not in page
    assert "HAND BACK:" in page and "test_big_by_computed_name" in page


def test_converge_over_only_unconsulted_lines_hands_back_the_same_way(tmp_path):
    project = _project(tmp_path, _ONLY)
    done = _run(project, "converge", "src/pkg/m.py::f", "--json")
    decision = json.loads(done.stdout)["decision"]
    assert decision["code"] == "consult_named_tests"
    assert decision["step"]["kind"] == "hand_back" and decision["step"]["argv"] is None
    page = _run(project, "converge", "src/pkg/m.py::f").stdout
    assert "AUTHOR INPUT" not in page and "--input" not in page
    assert "HAND BACK:" in page and "test_big_by_computed_name" in page


def test_audit_with_a_killable_gap_and_unconsulted_lines_still_runs_converge_and_names_them(tmp_path):
    project = _project(tmp_path, _MIXED)
    report = json.loads(_run(project, "audit", "src/pkg/m.py::f", "--json").stdout)
    assert report["killable_gaps"], "the fixture holds a killable gap"
    assert report["decision"]["code"] == "close_the_gap"
    assert report["decision"]["state"]["not_consulted_dynamic"] == report["not_consulted_dynamic"] != []
    page = _run(project, "audit", "src/pkg/m.py::f").stdout
    assert "DO THIS:  detective converge" in page
    assert "Not converge's" in page and "test_big_by_computed_name" in page
    assert "uncovered line(s) — real gaps" not in page, "the waiting line is not a gap converge writes"


# ── the pure decisions ────────────────────────────────────────────────────────────────────────────────


def test_unconsulted_gap_standing_codes():
    assert unconsulted_gap_standing(0, [], ["t"]) == "none"
    assert unconsulted_gap_standing(3, [], []) == "none"
    assert unconsulted_gap_standing(0, ["unconsulted"], ["t"]) == "unconsulted_only"
    assert unconsulted_gap_standing(0, ["unconsulted", "unconsulted"], ["t"]) == "unconsulted_only"
    assert unconsulted_gap_standing(1, ["unconsulted"], ["t"]) == "writable"
    assert unconsulted_gap_standing(0, ["unconsulted", "unexecuted"], ["t"]) == "writable"
    assert unconsulted_gap_standing(0, ["unconsulted"], []) == "writable", "no named test: nothing to consult"


def _audit(**kw) -> str:
    base = dict(
        block="",
        has_failing_tests=False,
        killable_gaps=0,
        missing_lines=1,
        redundant_tests=0,
        removing=False,
        candidate_equivalent=0,
        has_equivalent_ids=False,
        unclassified=0,
    )
    return audit_next_action(**{**base, **kw})


def test_audit_ladder_ranks_consult_named_tests_above_the_gap_and_below_the_floor():
    assert _audit(unconsulted_only=True) == "consult_named_tests"
    assert _audit(unconsulted_only=False) == "close_the_gap"
    assert _audit(unconsulted_only=True, killable_gaps=2) == "close_the_gap"
    assert _audit(unconsulted_only=True, has_failing_tests=True) == "fix_failing_test"
    assert _audit(unconsulted_only=True, block="provide_sample") == "provide_sample"
    assert _audit(unconsulted_only=True, block="repair_measurement") == "repair_measurement"
    assert audit_step("consult_named_tests", False) == ("hand_back", "consult_named_tests")
    assert audit_step("consult_named_tests", True) == ("hand_back", "consult_named_tests")


def test_converge_ladder_ranks_consult_named_tests_above_the_gap_beside_env_gate():
    kw = dict(standing="incomplete", session_reason="", has_killable=False, has_line_gap=True)
    assert converge_next_action(**kw, unconsulted_only=True) == "consult_named_tests"
    assert converge_next_action(**kw) == "close_the_gap"
    assert converge_next_action(**{**kw, "has_killable": True}, unconsulted_only=True) == "close_the_gap"
    assert converge_next_action(**kw, unconsulted_only=True, env_gate="clock") == "declare_clock"
    assert (
        converge_next_action(**{**kw, "standing": "floor_failing"}, unconsulted_only=True)
        == "fix_failing_test"
    )
    assert converge_next_action(**{**kw, "standing": "complete", "has_line_gap": False}) == "settled"
    assert converge_step("consult_named_tests", "", "", False, "", "not_applicable") == (
        "hand_back",
        "consult_named_tests",
    )
