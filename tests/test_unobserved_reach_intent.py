"""A line only a test of unobserved reach may run is unknown, not uncovered (Wesker#17, Detective #77).

The defect: Wesker's trace ledger now says when a test's reach was not observed (`TraceEvidence.reach` is
``complete``, or ``incomplete_thread`` / ``incomplete_preexisting_thread`` / ``incomplete_subprocess``
joined by ``+``; such a row holds an empty or partial line set), but no Detective code read it. A test
that called the target through a `ThreadPoolExecutor` warmed at import printed as `0 test(s)`,
`✗ uncovered 2 line(s)` and `✗ real gaps`, and the ladder directed `converge` or an `--input`
at lines that test may well run.

These tests run the real CLI on the three causes (a pool warmed at import, a thread the test started that
outlives it, a child process), alone and together on one line, and pin the pure decisions.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from Detective.audit import (
    baseline_unobserved_reach,
    missing_line_standing,
    reach_causes,
    reach_remedies,
    unconsulted_gap_standing,
)
from Detective.cli import audit_next_action, audit_step, converge_next_action, converge_step

_PYPROJECT = '[tool.pytest.ini_options]\npythonpath = ["src", "tests"]\ntestpaths = ["tests"]\n'
# `branch` holds a killable mutant on its body; `quiet` has an equivalent body, so no killable mutant remains.
_TARGET = {
    "branch": "def f(x):\n    if x > 10:\n        y = x * 3\n        return y\n    return x\n",
    "quiet": "def f(x):\n    y = x\n    if x > 10:\n        pass\n    return y\n",
}
_PLAIN = (
    "from pkg.m import f\n\n\ndef test_small():\n    assert f(1) == 1\n\n\n"
    "def test_small_again():\n    assert f(2) == 2\n"
)
_POOL = (
    "from concurrent.futures import ThreadPoolExecutor\n\nfrom pkg.m import f\n\n"
    "_POOL = ThreadPoolExecutor(max_workers=1)\n_POOL.submit(lambda: 0).result()\n\n\n"
    "def test_big_through_a_warmed_pool():\n    assert _POOL.submit(f, 50).result()\n"
)
_STARTED = (
    "import threading\nimport time\n\nfrom pkg.m import f\n\n\n"
    "def test_big_in_a_thread_that_outlives_it():\n"
    "    def work():\n        time.sleep(0.3)\n        f(50)\n\n"
    "    threading.Thread(target=work).start()\n"
)
_CHILD = (
    "import subprocess\nimport sys\n\nfrom pkg.m import f\n\n"
    "CHILD = \"import sys; sys.path.insert(0, 'src'); from pkg.m import f; print(f(50))\"\n\n\n"
    "def test_big_in_a_child_process():\n    assert f(1) == 1\n"
    "    subprocess.run([sys.executable, '-c', CHILD], capture_output=True, text=True, check=True)\n"
)
_CAUSES = {"pool": _POOL, "started": _STARTED, "child": _CHILD}


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


def _project(tmp_path: Path, target: str, causes: list[str]) -> Path:
    project = tmp_path / "proj"
    (project / "src" / "pkg").mkdir(parents=True)
    (project / "tests").mkdir()
    (project / "pyproject.toml").write_text(_PYPROJECT)
    (project / "src" / "pkg" / "__init__.py").write_text("")
    (project / "src" / "pkg" / "m.py").write_text(_TARGET[target])
    (project / "tests" / "test_plain.py").write_text(_PLAIN)
    for name in causes:
        (project / "tests" / f"test_{name}.py").write_text(_CAUSES[name])
    assert _run(project, "regime", "--migrate", "--project-root", str(project)).returncode == 0
    return project


def _audit_json(project: Path) -> dict:
    return json.loads(_run(project, "audit", "src/pkg/m.py::f", "--json").stdout)


_REMEDY_WORDS = {
    "pool": ("create the pool or thread inside the test",),
    "started": ("join the thread before the test returns",),
    "child": ("a mutant installed here never reaches a child's code",),
}


@pytest.mark.parametrize("cause", sorted(_CAUSES))
def test_a_line_only_an_unobserved_test_may_run_is_handed_back_with_its_cause_never_asked_for_an_input(
    tmp_path, cause
):
    project = _project(tmp_path, "quiet", [cause])
    report = _audit_json(project)
    decision = report["decision"]
    assert {s for _, s in report["missing_line_standings"]} == {"reach_unobserved"}
    assert decision["code"] == "observe_reach"
    assert decision["step"]["kind"] == "hand_back" and decision["step"]["remedy"] == "observe_reach"
    assert decision["step"]["argv"] is None and decision["step"]["then"] == ["audit", "src/pkg/m.py::f"]
    assert [t for t, _ in decision["state"]["unobserved_reach"]] == [t for t, _ in report["unobserved_reach"]]
    page = _run(project, "audit", "src/pkg/m.py::f").stdout
    assert (
        "✗ uncovered" not in page
        and "DO THIS" not in page
        and "--input" not in page.replace("Not --input", "")
    )
    assert all(test in page for test, _ in report["unobserved_reach"]) and report["unobserved_reach"]
    for words in _REMEDY_WORDS[cause]:
        assert words in page
    assert "Reach unobserved" in page


def test_the_converge_page_hands_back_the_same_way(tmp_path):
    project = _project(tmp_path, "quiet", ["pool"])
    decision = json.loads(_run(project, "converge", "src/pkg/m.py::f", "--json").stdout)["decision"]
    assert decision["code"] == "observe_reach"
    assert decision["step"]["kind"] == "hand_back" and decision["step"]["argv"] is None
    page = _run(project, "converge", "src/pkg/m.py::f").stdout
    assert "AUTHOR INPUT" not in page and "HAND BACK:" in page and "create the pool" in page


def test_one_line_with_a_test_of_each_cause_names_each_test_with_its_own_remedy(tmp_path):
    project = _project(tmp_path, "branch", sorted(_CAUSES))
    report = _audit_json(project)
    assert {s for _, s in report["missing_line_standings"]} == {"reach_unobserved"}
    assert {reach for _, reach in report["unobserved_reach"]} == {
        "incomplete_preexisting_thread",
        "incomplete_thread",
        "incomplete_subprocess",
    }
    assert report["decision"]["code"] == "close_the_gap", "a killable gap is open: converge is still right"
    page = _run(project, "audit", "src/pkg/m.py::f").stdout
    for words in (w for ws in _REMEDY_WORDS.values() for w in ws):
        assert words in page
    assert "✗ uncovered" not in page
    assert "the killable count above is taken without what these tests did not show" in page
    assert "line(s) are unknown, not uncovered" in page


# ── the pure decisions ────────────────────────────────────────────────────────────────────────────────


def test_reach_causes_and_remedies():
    assert reach_causes("complete") == [] and reach_causes("") == []
    assert reach_causes("incomplete_thread") == ["incomplete_thread"]
    assert reach_causes("incomplete_thread+incomplete_subprocess") == [
        "incomplete_thread",
        "incomplete_subprocess",
    ]
    assert reach_causes("incomplete_novel") == ["incomplete_novel"], "an unknown cause is named, not dropped"
    assert len(reach_remedies("incomplete_thread+incomplete_preexisting_thread+incomplete_subprocess")) == 3
    assert "never reaches a child's code" in reach_remedies("incomplete_subprocess")[0][1]
    assert reach_remedies("incomplete_novel")[0][0] == "its reach is incomplete_novel"
    assert reach_remedies("complete") == []


def test_baseline_unobserved_reach_reads_the_ledger_rows_by_name():
    rows = (
        SimpleNamespace(test_id="a::t1", reach="complete"),
        SimpleNamespace(test_id="a::t2", reach="incomplete_thread"),
        SimpleNamespace(test_id="a::t3", reach="incomplete_thread+incomplete_subprocess"),
        SimpleNamespace(test_id="", reach="incomplete_thread"),
        SimpleNamespace(test_id="a::t4"),
    )
    assert baseline_unobserved_reach(SimpleNamespace(trace_evidence=rows)) == {
        "a::t2": "incomplete_thread",
        "a::t3": "incomplete_thread+incomplete_subprocess",
    }
    assert baseline_unobserved_reach(SimpleNamespace(trace_evidence=None)) == {}
    assert baseline_unobserved_reach(SimpleNamespace()) == {}


def test_missing_line_standing_ranks_reach_unobserved_below_a_runner_and_above_unconsulted():
    cov = {"t": [2]}
    assert missing_line_standing(3, cov, [], [], ["d"], ["u"]) == "reach_unobserved"
    assert missing_line_standing(3, cov, [], [], [], ["u"]) == "reach_unobserved"
    assert missing_line_standing(3, cov, [], [], ["d"], []) == "unconsulted"
    assert missing_line_standing(3, cov, [], [], [], None) == "unexecuted"
    assert missing_line_standing(2, cov, [], [], [], ["u"]) == "run_inadmissibly"
    assert missing_line_standing(2, cov, ["t"], [], [], ["u"]) == "run_by_failing"


def test_unobserved_gap_standing_codes():
    assert unconsulted_gap_standing(0, ["reach_unobserved"], [], ["u"]) == "reach_unobserved_only"
    assert unconsulted_gap_standing(0, ["reach_unobserved"], [], []) == "writable", "no named test"
    assert unconsulted_gap_standing(1, ["reach_unobserved"], [], ["u"]) == "writable"
    assert unconsulted_gap_standing(0, ["reach_unobserved", "unexecuted"], [], ["u"]) == "writable"
    both = unconsulted_gap_standing(0, ["reach_unobserved", "unconsulted"], ["t"], ["u"])
    assert both == "unconsulted_only", "an unconsulted line outranks: consult first, the block names both"


def test_both_ladders_rank_observe_reach_above_the_gap_and_below_the_floor():
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
    assert audit_next_action(**base, reach_unobserved_only=True) == "observe_reach"
    assert audit_next_action(**{**base, "killable_gaps": 1}, reach_unobserved_only=True) == "close_the_gap"
    assert audit_next_action(**{**base, "has_failing_tests": True}, reach_unobserved_only=True) == (
        "fix_failing_test"
    )
    assert (
        audit_step("observe_reach", False)
        == audit_step("observe_reach", True)
        == (
            "hand_back",
            "observe_reach",
        )
    )
    kw = dict(standing="incomplete", session_reason="", has_killable=False, has_line_gap=True)
    assert converge_next_action(**kw, reach_unobserved_only=True) == "observe_reach"
    assert converge_next_action(**{**kw, "has_killable": True}, reach_unobserved_only=True) == "close_the_gap"
    assert converge_next_action(**kw) == "close_the_gap"
    assert converge_step("observe_reach", "", "", False, "", "not_applicable") == (
        "hand_back",
        "observe_reach",
    )
