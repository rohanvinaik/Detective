"""Intent: the universe count and every denominator come from the measured policy and count unit
(Detective #134).

THE DEFECT, measured 2026-10-26 on a two-sign empty-string target: the report said
`universe: 2 operator mutants · … 7/12 …` and `--json` gave `universe_size: 2` beside `total_mutants: 12`.
`_converge_impl` built the universe from the ONE-sign `filter_categories` / `estimate_universe_size`
before profiling, so a two-sign population was divided by a one-sign count. The same estimate fed
verify-rewrite's receipt.

THE RULING: `universe_standing` takes the figure from the measured population (a comprehensive run's
scored + unscored mutants), or, for a sampled or cut run, from the static count under the SAME categories
and the codomain the final profile observed, and names the basis. A percentage is never clamped.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from Detective.converge import universe_standing


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        ((False, 2, 12, 0), (12, "measured_census")),  # the defect: the one-sign estimate was 2
        ((False, 12, 11, 1), (12, "measured_census")),  # unscored mutants stay in the universe
        ((False, 99, 12, 0), (12, "measured_census")),  # a comprehensive run's census beats an estimate
        ((True, 20, 12, 0), (20, "estimate")),  # a sample is divided by the policy's own count
        ((True, 12, 12, 0), (12, "estimate")),
        (
            (True, 2, 12, 1),
            (13, "estimate_below_measured"),
        ),  # an estimate under the measured: named, not hidden
        ((False, 0, 0, 0), (0, "measured_census")),  # nothing measured is a zero, not a made-up count
        ((False, 5, -3, -1), (0, "measured_census")),  # absence never goes negative
    ],
)
def test_the_universe_comes_from_the_measured_population(args, expected):
    assert universe_standing(*args) == expected


_SOURCE = 'def label(flag):\n    return ""\n'
_TEST = 'from emp import label\n\n\ndef test_label():\n    assert label(True) == ""\n'


def _detective(cwd, *argv):
    return subprocess.run(  # noqa: S603 — the CLI under test
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
    (root / "emp.py").write_text(_SOURCE)
    (root / "tests" / "test_emp.py").write_text(_TEST)
    assert _detective(root, "regime", "--migrate", "--project-root", str(root)).returncode == 0
    return root


def _record(root, *flags):
    return json.loads(_detective(root, "converge", "emp.py::label", *flags, "--json").stdout)


def test_a_two_sign_universe_is_the_two_sign_population(project):
    record = _record(project, "--two-sign")
    assert record["universe_size"] == record["total_mutants"] > 2, record["universe_size"]
    assert record["universe_basis"] == "measured_census"
    page = _detective(project, "converge", "emp.py::label", "--two-sign").stdout
    report = (project / ".detective" / "reports" / "converge_label.txt").read_text()
    total = record["total_mutants"]
    assert f"universe: {total} operator mutants" in report, report
    assert f"{record['value_killed']}/{total} = " in report, report
    assert "FINAL" in page


def test_a_sampled_universe_is_an_estimate_under_the_same_policy_and_says_so(project):
    record = _record(project, "--two-sign", "--fast")
    assert record["universe_size"] >= record["total_mutants"], record
    assert record["universe_basis"] in ("estimate", "estimate_below_measured")
    _detective(project, "converge", "emp.py::label", "--two-sign", "--fast")
    report = (project / ".detective" / "reports" / "converge_label.txt").read_text()
    assert "(estimated under the measured policy)" in report or "(measured census:" in report, report


def test_one_sign_is_unchanged_in_kind(project):
    record = _record(project)
    assert record["universe_size"] == record["total_mutants"]
