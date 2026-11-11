"""After `audit --remove` edits a test file, the re-check MEASURES the edited suite (#104).

THE DEFECT, measured 2026-10-26 on the issue's fixture (`f` returns "pos" for x > 0, else "nonpos"; `test_pos`
and `test_nonpos` are its cover; a redundant `test_dup` sits mid-file, with a two-row parametrized test after
it): `audit 'src/calc.py::f' --remove` re-audited IN-PROCESS right after its edit and read `test_count` 3
though 4 tests remained, `total_mutants` 2 of 11, the basis still admitting the deleted `test_dup`, and
`cut_reasons ["mutant_construction_failed"]`. The page said "after removal: not re-measured".

THE CAUSE (proved by listing the session's collection after the edit): the live session holds the pre-edit
test callables, their old first lines, the imported test module and a baseline that still lists the deleted
test, and nothing told it the file changed. The measurement describes the OLD suite.

WHY NOT AN IN-PROCESS REFRESH. `Wesker.ci.refresh_live_suite` re-collects one file into the session and, on a
file of plain test functions, the re-check then read 4 tests, 11/11, complete. But its collect-only backend
cannot bind a fixture-taking test and drops it: on the same fixture with `test_pos(tmp_path)` and
`test_nonpos(monkeypatch)` it re-collected 2 tests where 4 remained. So the re-check is a fresh `audit` in a
NEW process (`cli._fresh_audit`), which shares no state with the session that made the edit, and it is read as
a measurement only when it counts exactly what the edit left (`audit.removal_recheck_standing`).

THE CONTRACT (docs/TEST_SUITE_CLEANUP_CONTRACT.md §9 step 5, §10, C01, C09, C12, C17): after an edit,
recollect and remeasure from a fresh process; the live workspace is compared to its expected basis before
promotion, so a file edited between the proposal and the write is refused
(`suite_edit.removal_basis_disposition`); an unexpectedly reduced collection refuses acceptance; a report
missing a field fails closed. The deletion gate is unchanged: an unresolved re-check never drives a further
deletion and never prints as a verdict.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from Detective.audit import removal_after_reading, removal_recheck_standing
from Detective.suite_edit import (
    file_digest,
    removal_basis_disposition,
    removal_outcome_why,
    removal_summary,
)

_PYPROJECT = '[tool.pytest.ini_options]\npythonpath = ["src"]\ntestpaths = ["tests"]\n'
_CALC = 'def f(x):\n    if x > 0:\n        return "pos"\n    return "nonpos"\n'
_ISSUE_TESTS = textwrap.dedent(
    """\
    import pytest
    from calc import f


    def test_pos():
        assert f(1) == "pos"


    def test_nonpos():
        assert f(0) == "nonpos"


    def test_dup():
        assert f(5) == "pos"


    @pytest.mark.parametrize("x", [3, 4])
    def test_more_pos(x):
        assert f(x) == "pos"
    """
)


def _run(cwd: Path, *argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
        env=dict(os.environ),
    )


def _project(root: Path, tests: dict[str, str]) -> Path:
    (root / "src").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "pyproject.toml").write_text(_PYPROJECT)
    (root / "src" / "calc.py").write_text(_CALC)
    for name, text in tests.items():
        (root / "tests" / name).write_text(text)
    assert _run(root, "-m", "Detective", "regime", "--migrate", "--project-root", str(root)).returncode == 0
    return root


def _audit(project: Path, *flags: str) -> dict:
    (project / ".detective" / "verdict_cache.json").unlink(missing_ok=True)
    done = _run(project, "-m", "Detective", "audit", "src/calc.py::f", *flags, "--json")
    return json.loads(done.stdout)


def _clean_copy(project: Path, dest: Path) -> Path:
    """The edited tree without any measurement state: what a fresh `audit` of a clean checkout reads."""
    shutil.copytree(
        project, dest, ignore=shutil.ignore_patterns(".wesker", ".detective", "__pycache__", ".pytest_cache")
    )
    assert _run(dest, "-m", "Detective", "regime", "--migrate", "--project-root", str(dest)).returncode == 0
    return dest


def _reading(report: dict) -> dict:
    return {
        "test_count": report["test_count"],
        "state": report["function_basis"]["action"],
        "cover": report["minimal_test_count"],
        "total_mutants": report["total_mutants"],
        "value_killed": report["value_killed"],
        "redundant": sorted(t.rsplit("::", 1)[1] for t in report["redundant_tests"]),
    }


# --- the pure decisions ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("expected", "current", "code"),
    [
        ("abc", "abc", "unchanged"),
        ("abc", "abd", "changed"),
        ("", "abc", "unrecorded"),  # nothing recorded: no basis, never a pass
        ("abc", "", "unrecorded"),  # the file cannot be read now
        ("", "", "unrecorded"),
    ],
)
def test_a_removal_is_checked_against_the_file_as_it_was_measured(expected, current, code):
    assert removal_basis_disposition(expected, current) == code


@pytest.mark.parametrize(
    ("ran", "before", "removed", "after", "code"),
    [
        (True, 5, 1, 4, "measured"),
        (True, 1, 1, 0, "measured"),  # the last test of the function
        (True, 6, 2, 4, "measured"),  # two in one run
        (True, 5, 1, 3, "collection_short"),  # a test the edit did not touch is missing
        (True, 5, 1, 2, "collection_short"),
        (True, 5, 1, 5, "collection_extra"),  # the deleted test is still being measured
        (False, 5, 1, 4, "not_run"),  # no report: nothing is known, whatever the numbers
        (False, 5, 1, 0, "not_run"),
    ],
)
def test_the_recheck_is_a_measurement_only_when_it_counts_what_the_edit_left(
    ran, before, removed, after, code
):
    assert removal_recheck_standing(ran, before, removed, after) == code


def test_an_unresolved_recheck_is_never_read_as_a_verdict():
    assert removal_after_reading("complete", "unresolved", 0) == "unmeasured"
    assert removal_after_reading("gap", "unresolved", 3) == "unmeasured"


@pytest.mark.parametrize("standing", ["not_run", "collection_short", "collection_extra", "measured", "weird"])
def test_a_recheck_that_is_no_measurement_says_which_kind_and_names_the_confirming_command(standing):
    from Detective.cli import _recheck_unmeasured_why, _removal_lines

    record = {
        "target": "src/calc.py::f",
        "gate": "proceed",
        "outcomes": [{"test": "t::test_dup", "code": "removed", "why": "deleted"}],
        "removed": ["t::test_dup"],
        "after": {
            "test_count": None,
            "state": "unresolved",
            "reading": "unmeasured",
            "newly_open": 0,
            "cover": None,
            "recheck": standing,
        },
    }
    lines = _removal_lines(record)
    assert f"  after removal: not re-measured — {_recheck_unmeasured_why(standing)}" in lines
    assert lines[-1] == "DONE:  removed 1 test(s). Confirm in a fresh run: detective audit 'src/calc.py::f'"
    assert "complete" not in "\n".join(lines[-2:]) and "GAP" not in "\n".join(lines)
    assert len({_recheck_unmeasured_why(c) for c in ("not_run", "collection_short", "collection_extra")}) == 3
    assert "weird" in _recheck_unmeasured_why("weird")


_FRESH = {
    "test_count": 4,
    "function_basis": {
        "action": "complete",
        "admitted": [{"test": "t.py::test_b"}, {"test": "t.py::test_a"}],
    },
    "killable_gaps": [],
    "missing_lines": [],
    "minimal_test_count": 2,
    "value_killed": 11,
    "total_mutants": 11,
}


def test_a_fresh_report_missing_a_field_is_no_report(tmp_path, monkeypatch):
    """Fail closed (C17): a child that prints nothing, prints non-JSON, or omits a field this reads."""
    from Detective import cli

    def child(stdout):
        return lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(subprocess, "run", child(json.dumps(_FRESH)))
    assert cli._fresh_audit("m.py", "f", str(tmp_path), False) == _FRESH
    for broken in ("", "not json", "[]", json.dumps({k: v for k, v in _FRESH.items() if k != "test_count"})):
        monkeypatch.setattr(subprocess, "run", child(broken))
        assert cli._fresh_audit("m.py", "f", str(tmp_path), False) is None
    for basis in ({}, {"action": "complete"}, {"admitted": []}, "complete"):
        monkeypatch.setattr(subprocess, "run", child(json.dumps({**_FRESH, "function_basis": basis})))
        assert cli._fresh_audit("m.py", "f", str(tmp_path), False) is None

    def refuses(*a, **k):
        raise OSError("no interpreter")

    monkeypatch.setattr(subprocess, "run", refuses)
    assert cli._fresh_audit("m.py", "f", str(tmp_path), False) is None


def test_the_fresh_audit_runs_this_interpreter_on_the_same_target_and_policy(tmp_path, monkeypatch):
    from Detective import cli

    seen = []

    def child(argv, **kw):
        seen.append((argv, kw.get("cwd")))
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", child)
    cli._fresh_audit("src/m.py", "C.f", str(tmp_path), True)
    argv, cwd = seen[0]
    assert argv[:4] == [sys.executable, "-m", "Detective", "audit"]
    assert "src/m.py::C.f" in argv and "--json" in argv and "--two-sign" in argv
    assert argv[argv.index("--project-root") + 1] == os.path.abspath(tmp_path) == cwd
    cli._fresh_audit("src/m.py", "f", str(tmp_path), False)
    assert "--two-sign" not in seen[1][0]


def test_a_recheck_that_did_not_run_or_miscounted_is_unresolved_and_never_a_verdict(tmp_path):
    """Wired: `_audit_remove` reads the fresh report through `removal_recheck_standing`."""
    from types import SimpleNamespace
    from unittest.mock import patch

    from Detective import cli

    report = SimpleNamespace(
        function="m.py::f",
        redundant_tests=("t.py::test_dup",),
        function_basis=SimpleNamespace(action="complete"),
        removal_basis={},
        test_count=5,
        killable_gaps=(),
        missing_lines=(),
    )
    applied = SimpleNamespace(
        removed=("t.py::test_dup",), outcomes=(("t.py::test_dup", "removed"),), files_changed=()
    )
    cases = [
        (_FRESH, ("measured", "complete", "complete", 4, 2)),
        (None, ("not_run", "unresolved", "unmeasured", None, None)),
        ({**_FRESH, "test_count": 3}, ("collection_short", "unresolved", "unmeasured", None, None)),
        ({**_FRESH, "test_count": 5}, ("collection_extra", "unresolved", "unmeasured", None, None)),
        (
            {**_FRESH, "function_basis": {"action": "unresolved", "admitted": []}},
            ("measured", "unresolved", "unmeasured", 4, 2),
        ),
        (
            {**_FRESH, "function_basis": {"action": "gap", "admitted": []}, "killable_gaps": ["new"]},
            ("measured", "gap", "gap_new", 4, 2),
        ),
    ]
    for payload, expected in cases:
        with (
            patch("Detective.audit.module_safe_removals", return_value=(("t.py::test_dup",), {}, {})),
            patch("Detective.suite_edit.apply_removals", return_value=applied),
            patch.object(cli, "_fresh_audit", return_value=payload),
        ):
            after = cli._audit_remove("m.py", "f", str(tmp_path), report, two_sign=False)["after"]
        assert (
            after["recheck"],
            after["state"],
            after["reading"],
            after["test_count"],
            after["cover"],
        ) == expected


def test_the_basis_outcomes_have_sentences_and_a_summary_clause():
    for code in ("basis_changed", "basis_unrecorded"):
        assert not removal_outcome_why(code).startswith("unrecognised")
        assert removal_summary([code]).startswith("1 ")
        assert code not in removal_summary([code])


def test_a_file_digest_is_its_bytes_and_empty_when_unreadable(tmp_path):
    path = tmp_path / "t.py"
    path.write_bytes(b"def test_a(): pass\n")
    first = file_digest(str(path))
    assert first and first == file_digest(str(path))
    path.write_bytes(b"def test_a(): pass\n\n")
    assert file_digest(str(path)) != first
    assert file_digest(str(tmp_path / "missing.py")) == ""


# --- the issue's own fixture, end to end -----------------------------------------------------------------


@pytest.fixture(scope="module")
def issue_run(tmp_path_factory):
    base = tmp_path_factory.mktemp("recheck")
    project = _project(base / "proj", {"test_calc.py": _ISSUE_TESTS})
    before = _audit(project)
    pristine = shutil.copytree(
        project,
        base / "again",
        # not the bytecode: pytest's rewritten test pyc keeps the path it was compiled at
        ignore=shutil.ignore_patterns(".wesker", ".detective", "__pycache__", ".pytest_cache"),
    )
    removed = _audit(project, "--remove")
    clean = _clean_copy(project, base / "clean")
    # the page, from the same removal on an untouched copy of the fixture
    page = _run(pristine, "-m", "Detective", "audit", "src/calc.py::f", "--remove").stdout
    return {"before": before, "removed": removed, "fresh": _audit(clean), "project": project, "page": page}


def test_the_recheck_after_a_mid_file_removal_measures_the_edited_suite(issue_run):
    after = issue_run["removed"]["removal"]["after"]
    assert issue_run["before"]["test_count"] == 5 and issue_run["before"]["total_mutants"] == 11
    assert "def test_dup" not in (issue_run["project"] / "tests" / "test_calc.py").read_text()
    assert after["test_count"] == 4  # not 3, and not the deleted test's
    assert (after["value_killed"], after["total_mutants"]) == (11, 11)  # not 2 of 11
    assert after["state"] == "complete" and after["reading"] == "complete" and after["recheck"] == "measured"
    assert not [t for t in after["basis"] if "test_dup" in t] and len(after["basis"]) == 4
    assert "after removal: 4 test(s) · 11/11 value-pinned, complete" in issue_run["page"]


def test_the_recheck_equals_what_a_fresh_audit_of_a_clean_copy_reads(issue_run):
    after = issue_run["removed"]["removal"]["after"]
    fresh = _reading(issue_run["fresh"])
    assert {k: after[k] for k in ("test_count", "state", "cover", "value_killed", "total_mutants")} == {
        k: fresh[k] for k in ("test_count", "state", "cover", "value_killed", "total_mutants")
    }
    assert after["basis"] == sorted(w["test"] for w in issue_run["fresh"]["function_basis"]["admitted"])
    assert fresh["total_mutants"] == 11 and fresh["value_killed"] == 11


def test_the_recheck_page_prints_the_measured_state_not_a_refusal_to_measure():
    from Detective.cli import _removal_lines

    record = {
        "target": "src/calc.py::f",
        "gate": "proceed",
        "outcomes": [{"test": "t::test_dup", "code": "removed", "why": "deleted"}],
        "removed": ["t::test_dup"],
        "after": {
            "test_count": 4,
            "value_killed": 11,
            "total_mutants": 11,
            "state": "complete",
            "reading": "complete",
            "newly_open": 0,
            "cover": 2,
            "recheck": "measured",
        },
    }
    page = "\n".join(_removal_lines(record))
    assert "after removal: 4 test(s) · 11/11 value-pinned, complete, greedy cover=2" in page
    assert "not re-measured" not in page
    record["after"]["cover"] = None
    assert "cover=None" not in "\n".join(_removal_lines(record))


# --- the edge cases the issue names ------------------------------------------------------------------------


_TWO_DUPS = _ISSUE_TESTS.replace(
    "@pytest.mark.parametrize",
    'def test_dup_again():\n    assert f(7) == "pos"\n\n\n@pytest.mark.parametrize',
)
_UNFORMATTED = (
    "import pytest\nfrom calc import f\n\ndef test_pos():\n  assert f(1)=='pos'\n\n"
    "def test_nonpos():\n  assert f(0)=='nonpos'  \n\ndef test_dup():\n  assert f(5)=='pos'\n"
    "def test_more():\n  assert f(9)=='pos'\n"
)
_ONLY_REDUNDANT_FILE = 'from calc import f\n\n\ndef test_only_dup():\n    assert f(5) == "pos"\n'
_ALL_ROWS = textwrap.dedent(
    """\
    import pytest
    from calc import f


    def test_pos():
        assert f(1) == "pos"


    def test_nonpos():
        assert f(0) == "nonpos"


    @pytest.mark.parametrize("x", [3, 4])
    def test_rows(x):
        assert f(x) == "pos"
    """
)


def _removal_vs_clean(tmp_path: Path, tests: dict[str, str]):
    project = _project(tmp_path / "proj", tests)
    removed = _audit(project, "--remove")
    clean = _clean_copy(project, tmp_path / "clean")
    return project, removed, _audit(clean)


def _same_as_fresh(removed: dict, fresh: dict) -> None:
    after = removed["removal"]["after"]
    assert after is not None
    assert (
        after["test_count"],
        after["state"],
        after["cover"],
        after["value_killed"],
        after["total_mutants"],
        after["basis"],
    ) == (
        fresh["test_count"],
        fresh["function_basis"]["action"],
        fresh["minimal_test_count"],
        fresh["value_killed"],
        fresh["total_mutants"],
        sorted(w["test"] for w in fresh["function_basis"]["admitted"]),
    )


def test_removing_two_tests_in_one_run_measures_the_suite_that_remains(tmp_path):
    project, removed, fresh = _removal_vs_clean(tmp_path, {"test_calc.py": _TWO_DUPS})
    assert sorted(removed["removal"]["removed"]) == [
        "tests/test_calc.py::test_dup",
        "tests/test_calc.py::test_dup_again",
    ]
    text = (project / "tests" / "test_calc.py").read_text()
    assert "test_dup" not in text
    _same_as_fresh(removed, fresh)
    assert fresh["total_mutants"] == 11 and removed["removal"]["after"]["state"] == "complete"


def test_an_edit_that_leaves_the_file_unformatted_is_remeasured_all_the_same(tmp_path):
    project, removed, fresh = _removal_vs_clean(tmp_path, {"test_calc.py": _UNFORMATTED})
    assert "tests/test_calc.py::test_dup" in removed["removal"]["removed"]
    assert "test_dup" not in (project / "tests" / "test_calc.py").read_text()
    _same_as_fresh(removed, fresh)
    assert fresh["total_mutants"] == 11


def test_removing_the_last_test_of_a_file_remeasures_a_suite_that_no_longer_has_the_file(tmp_path):
    project, removed, fresh = _removal_vs_clean(
        tmp_path,
        {
            "test_calc.py": _ISSUE_TESTS.replace("def test_dup", "def test_dupx"),
            "test_zdup.py": _ONLY_REDUNDANT_FILE,
        },
    )
    gone = [t for t in removed["removal"]["removed"] if "test_zdup" in t]
    assert gone, removed["removal"]
    assert "def test_only_dup" not in (project / "tests" / "test_zdup.py").read_text()
    _same_as_fresh(removed, fresh)
    assert removed["removal"]["after"]["state"] == "complete"


def test_a_file_whose_remaining_tests_take_fixtures_is_remeasured_in_full(tmp_path):
    """The shape an in-process re-collection cannot serve: it dropped both fixture-taking tests and counted
    2 where 4 remained."""
    tests = _ISSUE_TESTS.replace("def test_pos():", "def test_pos(tmp_path):").replace(
        "def test_nonpos():", "def test_nonpos(monkeypatch):"
    )
    project, removed, fresh = _removal_vs_clean(tmp_path, {"test_calc.py": tests})
    assert removed["removal"]["removed"] == ["tests/test_calc.py::test_dup"]
    after = removed["removal"]["after"]
    assert (after["recheck"], after["test_count"], after["state"]) == ("measured", 4, "complete")
    _same_as_fresh(removed, fresh)


def test_a_parametrized_function_whose_rows_are_all_redundant_is_kept_and_nothing_is_remeasured(tmp_path):
    project = _project(tmp_path / "proj", {"test_calc.py": _ALL_ROWS})
    before = (project / "tests" / "test_calc.py").read_text()
    removed = _audit(project, "--remove")
    rows = [o for o in removed["removal"]["outcomes"] if o["code"] == "parametrized_row"]
    assert len(rows) == 2 and removed["removal"]["removed"] == []
    assert (project / "tests" / "test_calc.py").read_text() == before
    assert removed["removal"]["after"] is None


def test_an_intervening_manual_edit_between_the_proposal_and_the_apply_is_refused(tmp_path, monkeypatch):
    """The proposal was measured against one file; the file changed before the write. Nothing is removed from
    it, each of its ids says why, and the user's edit is untouched."""
    from Detective import audit as audit_mod
    from Detective.cli import _audit_remove

    project = _project(tmp_path / "proj", {"test_calc.py": _ISSUE_TESTS})
    path = project / "tests" / "test_calc.py"
    seen: dict = {}

    def intervening(*args, **kwargs):
        safe, retained, unverified = real(*args, **kwargs)
        path.write_text(path.read_text().replace('f(5) == "pos"', 'f(5) == "pos" and f(-5) == "nonpos"'))
        seen["edited"] = path.read_text()
        return safe, retained, unverified

    real = audit_mod.module_safe_removals
    monkeypatch.setattr(audit_mod, "module_safe_removals", intervening)
    monkeypatch.chdir(project)
    from Detective.audit import audit_suite

    def body():
        report = audit_suite("src/calc.py", "f", str(project))
        return _audit_remove("src/calc.py", "f", str(project), report, two_sign=False)

    from Wesker.ci import run_with_live_suite

    record = run_with_live_suite(str(project), body, target_files=["src/calc.py"])
    assert record["removed"] == [] and record["files_changed"] == []
    assert path.read_text() == seen["edited"]  # the manual edit survives untouched
    codes = {o["test"]: o["code"] for o in record["outcomes"]}
    assert codes["tests/test_calc.py::test_dup"] == "basis_changed"
    assert record["after"] is None  # nothing was removed, so nothing is re-measured


def test_a_recorded_basis_that_matches_lets_the_removal_through_and_none_checks_nothing(tmp_path):
    from Detective.suite_edit import apply_removals

    for expected in (None, "match"):
        project = _project(tmp_path / f"p_{expected}", {"test_calc.py": _ISSUE_TESTS})
        path = project / "tests" / "test_calc.py"
        digests = None if expected is None else {"tests/test_calc.py": file_digest(str(path))}
        report = apply_removals("src/calc.py", str(project), ["tests/test_calc.py::test_dup"], digests)
        assert report.removed == ("tests/test_calc.py::test_dup",)
        assert "def test_dup" not in path.read_text()


def test_an_unrecorded_file_is_refused_not_passed(tmp_path):
    from Detective.suite_edit import apply_removals

    project = _project(tmp_path / "proj", {"test_calc.py": _ISSUE_TESTS})
    path = project / "tests" / "test_calc.py"
    before = path.read_text()
    report = apply_removals("src/calc.py", str(project), ["tests/test_calc.py::test_dup"], {})
    assert (
        report.removed == () and dict(report.outcomes)["tests/test_calc.py::test_dup"] == "basis_unrecorded"
    )
    assert path.read_text() == before
