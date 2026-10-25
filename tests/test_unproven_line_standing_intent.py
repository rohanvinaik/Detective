"""Intent: a line only a failing test runs is unproven, never "uncovered", and is never offered an
`--input` (#139).

THE DEFECT, measured 2026-10-25 on fcd3348 and again on 01337aa, in #114's own reproduction:

    $ cat m.py                 # def scale(x): return x * 3
    $ cat tests/test_m.py      # assert scale(2) == 4   (fails on current code)
    $ detective converge 'm.py::scale' --two-sign
      ⚠ FAILING NOW        1 test(s) that reach this function fail on current code:
      ✗ uncovered          1 line(s): 2

`scale(2)` executes line 2. The full report went further:
- `✗ line gap: 1 executable line(s) no test covers: [2]`;
- `template: --input "(<x>,)" … to execute line(s) [2]`;
- "supply input/evidence below to finish".

That is an input for a line that already runs. The line IS unproven, correctly: coverage is admissible
only from a passing test (#59, Wesker#17). But "uncovered" / "no test covers" is a claim about
EXECUTION, and it was false. The two states have different remedies and printed one sign
(COMMUNICATING_DETERMINISM §3).

THE RULING. `audit.missing_line_standing` names why each missing line is unproven:
- run_by_failing;
- run_by_errored;
- run_inadmissibly;
- unexecuted.

One derivation, rendered on both pages (one shared row renderer), in converge's full report and in
`--json`. `missing_lines` keeps its meaning for every completeness gate. The `--input` template is
offered wherever a test written from an input can cover the line: everywhere except a line only a
failing test runs, because converge writes nothing over that floor.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from Detective.audit import missing_line_standing
from Detective.cli import _missing_line_report, _missing_line_rows, _unexecuted_lines
from Detective.converge import ConvergeResult

# ── the decision ───────────────────────────────────────────────────────────────────────────────

_COV = {"t::fails": [2, 3], "t::errors": [3, 4], "t::cut": [5], "t::passes": [6]}


@pytest.mark.parametrize(
    ("line", "standing"),
    [
        (2, "run_by_failing"),
        (3, "run_by_failing"),  # a failing runner outranks an errored one: the floor comes first
        (4, "run_by_errored"),
        (5, "run_inadmissibly"),  # observed, but by no failing or errored test: only where it cannot count
        (7, "unexecuted"),
    ],
)
def test_each_missing_line_is_named_by_what_its_observations_show(line, standing):
    assert missing_line_standing(line, _COV, ["t::fails"], ["t::errors"]) == standing


def test_no_observation_at_all_is_unexecuted_whatever_the_test_lists_hold():
    assert missing_line_standing(2, {}, ["t::fails"], ["t::errors"]) == "unexecuted"
    assert missing_line_standing(2, {"t::fails": []}, ["t::fails"], []) == "unexecuted"


# ── the renderers ──────────────────────────────────────────────────────────────────────────────


def _text(rows):
    return "\n".join(rows)


def test_the_page_names_a_failing_only_line_unproven_and_keeps_uncovered_for_the_rest():
    rows = _text(_missing_line_rows([2, 7], ((2, "run_by_failing"), (7, "unexecuted"))))
    assert "✗ unproven" in rows and "1 line(s): 2 — run only by a failing test" in rows
    assert "✗ uncovered" in rows and "1 line(s): 7" in rows
    assert "1 line(s): 2, 7" not in rows


def test_a_result_with_no_standings_renders_as_it_always_did():
    rows = _text(_missing_line_rows([2, 7], ()))
    assert "✗ uncovered" in rows and "2 line(s): 2, 7" in rows and "unproven" not in rows
    assert _unexecuted_lines([2, 7], ()) == [2, 7]


def test_a_standing_the_renderer_does_not_know_is_named_never_dropped():
    rows = _text(_missing_line_rows([9], ((9, "run_somewhere_new"),)))
    assert "✗ unproven" in rows and "9" in rows and "run_somewhere_new" in rows


def _cr(missing, standings):
    return ConvergeResult(
        function="m.py::scale",
        converged=False,
        at_ceiling=True,
        initial_survivors=1,
        final_survivors=1,
        iterations=(),
        written_path=None,
        missing_lines=tuple(missing),
        missing_line_standings=tuple(standings),
        line_complete=not missing,
        signature="scale(x)",
        param_names=("x",),
    )


def test_the_report_never_offers_an_input_for_a_line_only_a_failing_test_runs():
    report = _text(_missing_line_report(_cr([2], [(2, "run_by_failing")])))
    assert "run only by a failing test: [2]" in report
    assert "no --input applies" in report
    assert "template:" not in report and "no test covers" not in report


def test_the_report_offers_the_input_where_a_written_test_can_cover_the_line():
    report = _text(
        _missing_line_report(
            _cr([2, 4, 7], [(2, "run_by_failing"), (4, "run_by_errored"), (7, "unexecuted")])
        )
    )
    assert "no test covers: [7]" in report
    assert "run only by a test that errored in setup or teardown: [4]" in report
    assert "repairing its fixture covers them" in report
    assert 'template: --input "(<x>,)"' in report
    assert "execute line(s) [4, 7]" in report, "the failing-only line must not join the template"


# ── end to end through the real CLI: #114's own reproduction ────────────────────────────────────


def _detective(cwd, *argv):
    return subprocess.run(
        [sys.executable, "-m", "Detective", *argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
        env=dict(os.environ),
    )


def test_a_failing_test_s_line_is_unproven_on_every_surface_and_offered_no_input(tmp_path):
    project = tmp_path / "proj"
    (project / "tests").mkdir(parents=True)
    (project / "m.py").write_text("def scale(x):\n    return x * 3\n")
    (project / "tests" / "test_m.py").write_text(
        "from m import scale\n\n\ndef test_intent_doubles():\n    assert scale(2) == 4\n"
    )
    assert _detective(project, "regime", "--migrate", "--project-root", str(project)).returncode == 0

    audit = _detective(project, "audit", "m.py::scale")
    assert "✗ unproven           1 line(s): 2 — run only by a failing test" in audit.stdout, audit.stdout
    assert "✗ uncovered" not in audit.stdout, audit.stdout

    converge = _detective(project, "converge", "m.py::scale", "--two-sign")
    assert converge.returncode == 1, converge.stdout + converge.stderr  # the floor's exit, unchanged
    assert "run only by a failing test" in converge.stdout and "✗ uncovered" not in converge.stdout
    report = (project / ".detective" / "reports" / "converge_scale.txt").read_text()
    assert "run only by a failing test: [2]" in report, report
    assert "template:" not in report and "no test covers" not in report, report
    assert "supply input/evidence below to finish" not in report, report

    record = json.loads(_detective(project, "audit", "m.py::scale", "--json").stdout)
    assert record["missing_lines"] == [2]
    assert record["missing_line_standings"] == [[2, "run_by_failing"]]


def test_a_line_no_test_executes_is_still_uncovered_and_offered_the_input(tmp_path):
    project = tmp_path / "proj"
    (project / "tests").mkdir(parents=True)
    (project / "m.py").write_text("def sign(x):\n    if x < 0:\n        return -1\n    return 1\n")
    (project / "tests" / "test_m.py").write_text(
        "from m import sign\n\n\ndef test_positive():\n    assert sign(3) == 1\n"
    )
    assert _detective(project, "regime", "--migrate", "--project-root", str(project)).returncode == 0

    audit = _detective(project, "audit", "m.py::sign")
    assert "✗ uncovered          1 line(s): 3" in audit.stdout, audit.stdout
    assert "unproven           1 line(s)" not in audit.stdout, audit.stdout
    record = json.loads(_detective(project, "audit", "m.py::sign", "--json").stdout)
    assert record["missing_line_standings"] == [[3, "unexecuted"]]
