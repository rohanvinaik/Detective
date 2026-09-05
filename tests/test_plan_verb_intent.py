"""Intent tests for the `plan` verb (DETERMINISTIC_SICP §14.3 / §14.7, slice 5) — driven through the
REAL command (`Detective.cli.main`), never by calling the assembly directly.

What the verb is FOR, stated from intent:

- one ENTRY verb for the style layer, co-equal with `diagnose`: `plan <path>` over a tree,
  `plan file.py::fn` over one region, both STATIC (no live session, no mutant) and both writing
  nothing but the report file under `.detective/reports/`;
- exit codes on the shared four-valued contract, the advisory rule applied: a completed read is 0
  whatever it found; a precondition — no such function, nothing to read — is 2; never 1;
- the terse block is the default, `--full` prints the archive, `--json` carries the same rows with
  the exit field; the report FILE is written on every human run;
- the path form must not fall into the `file::function` menu: `plan` is dispatched before the
  target is split;
- `parsimony` is deprecated as a verb: it still runs unchanged, and says on stderr where its job
  went;
- the help teaches the epistemic role (style AFTER behavior; advisory; the residual names itself)
  and carries the regime stage for the `file::fn` form.
"""

from __future__ import annotations

import json
import os
import textwrap
from pathlib import Path

import pytest

from Detective import pins
from Detective.certificates import record_certificate
from Detective.cli import _STATIC_COMMANDS, main
from Detective.plan import plan_exit

_SMELLY = textwrap.dedent(
    """
    def dedupe_many(xs, a, b, c, d, e):
        out = []
        for x in xs:
            if x not in out:
                if a:
                    if b:
                        if c:
                            if d:
                                if e:
                                    out.append(x)
        return out
    """
)
_QUIET = textwrap.dedent(
    '''
    def describe(x):
        """A label for x."""
        name = str(x)
        return name
    '''
)


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "smelly.py").write_text(_SMELLY, encoding="utf-8")
    (tmp_path / "pkg" / "quiet.py").write_text(_QUIET, encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------- plan_exit (pure)


@pytest.mark.parametrize("conflict", [False, True])
@pytest.mark.parametrize("missing", [False, True])
@pytest.mark.parametrize("nothing", [False, True])
def test_plan_exit_is_zero_or_precondition_never_one(conflict, missing, nothing) -> None:
    # The full truth table over the three preconditions (the hand-written pin, under the targeted
    # exemption protocol — converge's witness pass grinds on plan.py targets, recorded in §14.9).
    expected = 2 if (conflict or missing or nothing) else 0
    assert plan_exit(conflict, missing, nothing) == expected
    assert plan_exit(conflict, missing, nothing) != 1


# ---------------------------------------------------------------- dispatch and statics


def test_plan_is_a_static_command_dispatched_before_the_target_split() -> None:
    assert "plan" in _STATIC_COMMANDS


def test_path_form_does_not_fall_into_the_separator_menu(tmp_path, capsys) -> None:
    root = _repo(tmp_path)
    code = main(["plan", str(root / "pkg"), "--project-root", str(root)])
    out = capsys.readouterr().out
    assert code == 0
    assert "target must be" not in out and "::" not in out.splitlines()[0]


# ---------------------------------------------------------------- the path form, end to end


def test_path_form_prints_the_terse_block_and_writes_the_report(tmp_path, capsys) -> None:
    root = _repo(tmp_path)
    code = main(["plan", str(root / "pkg"), "--project-root", str(root)])
    out = capsys.readouterr().out
    lines = out.strip().splitlines()
    assert code == 0
    assert lines[-1].startswith("FINAL plan pkg:") and lines[-1].endswith("advisory — writes nothing")
    assert "1 constructive" in lines[1] and "1 silent (clean 1 · unread 0)" in lines[1]
    assert "every exclusion named" in out and "unpinned 1" in out
    assert "converge first" in out and "pkg/smelly.py::dedupe_many" in out
    report = root / ".detective" / "reports" / "plan_pkg.txt"
    assert report.exists()
    assert "pkg/quiet.py::describe" in report.read_text(encoding="utf-8")
    assert "· full report" in out


def test_the_ordering_law_through_the_verb(tmp_path, capsys) -> None:
    root = _repo(tmp_path)
    import ast

    node = ast.parse(_SMELLY).body[0]
    record_certificate(str(root), "pkg/smelly.py::dedupe_many", pins.function_digest(node), "complete", "")
    code = main(["plan", str(root / "pkg"), "--project-root", str(root), "--budget", "500"])
    out = capsys.readouterr().out
    assert code == 0
    assert "1 funded" in out.strip().splitlines()[-1]
    assert "DO THIS" in out and "detective receipt 'pkg/smelly.py::dedupe_many'" in out


def test_json_form_carries_the_rows_and_the_exit_field(tmp_path, capsys) -> None:
    root = _repo(tmp_path)
    code = main(["plan", str(root / "pkg"), "--project-root", str(root), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["kind"] == "plan" and payload["exit_code"] == 0 and payload["exit_meaning"] == "clean"
    assert payload["verdicts"]["CONSTRUCTIVE"] == 1 and payload["clean"]["clean"] == 1
    assert {r["region"] for r in payload["excluded"]} == {
        "pkg/smelly.py::dedupe_many",
        "pkg/quiet.py::describe",
    }
    assert payload["report"] and payload["report"].endswith("plan_pkg.txt")


def test_full_form_prints_every_region(tmp_path, capsys) -> None:
    root = _repo(tmp_path)
    code = main(["plan", str(root / "pkg"), "--project-root", str(root), "--full"])
    out = capsys.readouterr().out
    assert code == 0
    assert "  pkg/smelly.py::dedupe_many\n" in out and "  pkg/quiet.py::describe\n" in out
    assert "smells:" in out


# ---------------------------------------------------------------- the file::fn form


def test_region_form_plans_one_region(tmp_path, capsys) -> None:
    root = _repo(tmp_path)
    code = main(["plan", "pkg/smelly.py::dedupe_many", "--project-root", str(root), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["regions"] == 1
    assert [r["region"] for r in payload["excluded"]] == ["pkg/smelly.py::dedupe_many"]
    assert payload["excluded"][0]["reason"] == "unpinned"
    assert payload["excluded"][0]["next_command"] == "detective converge 'pkg/smelly.py::dedupe_many'"


def test_region_form_with_no_such_function_is_a_precondition(tmp_path, capsys) -> None:
    root = _repo(tmp_path)
    code = main(["plan", "pkg/smelly.py::nope", "--project-root", str(root)])
    err = capsys.readouterr()
    assert code == 2
    assert "nope" in (err.out + err.err)


def test_nothing_to_read_is_a_precondition_not_clean(tmp_path, capsys) -> None:
    (tmp_path / "empty").mkdir()
    code = main(["plan", str(tmp_path / "empty"), "--project-root", str(tmp_path)])
    text = capsys.readouterr()
    assert code == 2
    assert "nothing to read" in (text.out + text.err)


def test_nothing_to_read_json_is_a_typed_refusal(tmp_path, capsys) -> None:
    (tmp_path / "empty").mkdir()
    code = main(["plan", str(tmp_path / "empty"), "--project-root", str(tmp_path), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 2 and payload["verdict"] == "REFUSED" and payload["exit_code"] == 2


# ---------------------------------------------------------------- parsimony, deprecated as a verb


def test_parsimony_still_runs_and_says_where_its_job_went(tmp_path, capsys) -> None:
    root = _repo(tmp_path)
    code = main(["parsimony", str(root / "pkg"), "--project-root", str(root)])
    text = capsys.readouterr()
    assert code == 0
    assert "parsimony" in text.out  # the map still prints
    assert "DEPRECATED" in text.err and "detective plan" in text.err


# ---------------------------------------------------------------- help as pedagogy


def test_plan_help_teaches_the_role(capsys) -> None:
    with pytest.raises(SystemExit):
        main(["plan", "--help"])
    out = capsys.readouterr().out
    assert "AFTER behavior" in out or "after behavior" in out
    assert "advisory" in out.lower()
    assert "TESTING REGIME" in out  # the regime stage, for the file::fn form
    assert "--budget" in out and "--full" in out and "--json" in out


def test_root_help_names_the_second_entry_verb(capsys) -> None:
    with pytest.raises(SystemExit):
        main(["--help"])
    out = capsys.readouterr().out
    assert "detective plan" in out


def test_report_file_is_written_under_the_project_root(tmp_path, capsys) -> None:
    root = _repo(tmp_path)
    cwd = os.getcwd()
    try:
        os.chdir(root)
        main(["plan", "pkg"])
    finally:
        os.chdir(cwd)
    capsys.readouterr()
    assert (root / ".detective" / "reports" / "plan_pkg.txt").exists()
