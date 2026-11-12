"""`flag` classifies over the measurement `audit` shows (Detective #127, Wesker#55).

The defect, measured: on a suite holding a test that fails on the unmutated code (here an xfail),
`detective flag` ran its own default profile, in which that test is excluded from the floor, and so offered
and recorded ``equivalent`` for a mutant that `detective audit` reports as having NO VERDICT
(``original_also_fails``): "not kills, not survivors; no input or flag applies". The refusal that names such
a mutant's cause (`_unscored_flag_refusal`) existed, but the profile `flag` measured never produced the
record it reads.

The fix is one derivation: `audit.audit_profile` is the measurement for both verbs. These tests drive the
real CLI on that suite under both policies and on a control suite whose genuine survivor still flags.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

_SOURCE = "def g(x):\n    y = x\n    if x > 10:\n        pass\n    return y\n"
_FLOOR_TEST = (
    "import pytest\n\nfrom m import g\n\n\ndef test_ok():\n    assert g(1) == 1\n\n\n"
    '@pytest.mark.xfail(reason="known", strict=False)\ndef test_expected_failure():\n    assert g(50) == 51\n'
)
_CLEAN_TEST = "from m import g\n\n\ndef test_ok():\n    assert g(1) == 1\n"


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


def _project(tmp_path: Path, test: str) -> Path:
    project = tmp_path / "proj"
    (project / "tests").mkdir(parents=True)
    (project / "m.py").write_text(_SOURCE)
    (project / "tests" / "test_m.py").write_text(test)
    (project / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\npythonpath = ["."]\ntestpaths = ["tests"]\n'
    )
    assert _run(project, "regime", "--migrate", "--project-root", str(project)).returncode == 0
    return project


def _no_verdict_ids(project: Path, *policy: str) -> list[str]:
    report = json.loads(_run(project, "audit", "m.py::g", "--json", *policy).stdout)
    return [mid for entry in report["original_also_fails"] for mid in entry["mutants"]]


def _recorded(project: Path) -> bool:
    store = project / ".detective" / "equivalents.json"
    return store.exists() and bool(json.loads(store.read_text()))


def test_flag_refuses_a_mutant_audit_reports_with_no_verdict_in_the_words_of_its_cause(tmp_path):
    project = _project(tmp_path, _FLOOR_TEST)
    ids = _no_verdict_ids(project)
    assert ids, "the fixture leaves mutants with no verdict"
    for mutant_id in ids[:3]:
        done = _run(project, "flag", "m.py::g", mutant_id, "--note", "equal")
        assert done.returncode == 1, done.stdout + done.stderr
        assert "reached no verdict (original_also_fails)" in done.stderr
        assert "fails at baseline" in done.stderr or "fail only a test that fails" in done.stderr
        assert "recorded" not in done.stdout
    assert not _recorded(project), "nothing may be recorded for a mutant with no verdict"


def test_the_json_refusal_names_the_reason(tmp_path):
    project = _project(tmp_path, _FLOOR_TEST)
    mutant_id = _no_verdict_ids(project)[0]
    done = _run(project, "flag", "m.py::g", mutant_id, "--json")
    payload = json.loads(done.stdout)
    assert done.returncode == 1 and payload["verdict"] == "REFUSED" and payload["reason"] == "unscored_mutant"
    assert payload["disposition"] == "original_also_fails"


def test_flag_under_two_sign_classifies_over_the_same_measurement(tmp_path):
    project = _project(tmp_path, _FLOOR_TEST)
    ids = _no_verdict_ids(project, "--two-sign")
    assert ids and any(i.startswith("OUTPUT") for i in ids), "the two-sign universe holds OUTPUT mutants too"
    for mutant_id in ids[:3] + [i for i in ids if i.startswith("OUTPUT")][:1]:
        done = _run(project, "flag", "m.py::g", mutant_id, "--two-sign", "--note", "equal")
        assert done.returncode == 1, done.stdout + done.stderr
        assert "reached no verdict (original_also_fails)" in done.stderr
    assert not _recorded(project)


def test_a_fence_on_a_mutant_with_no_verdict_is_refused_too(tmp_path):
    project = _project(tmp_path, _FLOOR_TEST)
    done = _run(project, "flag", "m.py::g", _no_verdict_ids(project)[0], "--fence")
    assert done.returncode == 1 and "reached no verdict" in done.stderr
    assert not _recorded(project)


def test_a_genuine_survivor_on_a_clean_suite_still_flags(tmp_path):
    project = _project(tmp_path, _CLEAN_TEST)
    report = json.loads(_run(project, "audit", "m.py::g", "--json").stdout)
    assert report["original_also_fails"] == []
    mutant_id = report["candidate_equivalent_ids"][0]
    done = _run(project, "flag", "m.py::g", mutant_id, "--note", "equal")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "recorded" in done.stdout and _recorded(project)
