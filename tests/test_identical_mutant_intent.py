"""Intent: a survivor whose mutant changed nothing is equivalent BY IDENTITY, named so, and never offered
to `flag` (Detective #142, item 2).

THE DEFECT, measured 2026-10-26 on `candidate_equivalent_caveat`: the SWAP operator transposed two
identical `False` arguments, so the mutant was the original. The report printed `→ mutant SWAP_...: `
with nothing after it, the DONE block offered `flag` for it, and the headline read
"modulo 1 unproven-equivalent". A reader was asked to prove equivalent a mutant that changed nothing.
Wesker should not generate it (Wesker #53, a later wave); Detective is right either way.

THE RULING: `mutant_identity` reads the two syntax trees. An identical mutant is never searched, never
killable, never a candidate for `flag`, and is counted under its own state in every surface.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from Detective.equivalence import classify_survivor, mutant_identity


@pytest.mark.parametrize(
    ("original", "mutated", "code"),
    [
        ("Module(body=[Return()])", "Module(body=[Return()])", "identical"),
        ("Module(body=[Return()])", "Module(body=[Pass()])", "differs"),
        ("", "Module()", "unknown"),
        ("Module()", "", "unknown"),
        ("", "", "unknown"),  # two missing trees are not two equal ones
    ],
)
def test_identity_is_read_from_both_trees_and_absence_is_not_identity(original, mutated, code):
    assert mutant_identity(original, mutated) == code


def test_an_identical_mutant_is_never_searched_or_killable():
    def boom(*_args):
        raise AssertionError("an identical mutant must not be executed")

    verdict = classify_survivor("m", "SWAP", "", boom, boom, [(1,), (2,)], identical=True)
    assert verdict.identical is True
    assert verdict.killable is False and verdict.witness is None and verdict.crash_only is False
    assert verdict.searched == 0 and verdict.label == "identical-to-original"


_SOURCE = "def g(a, b, c):\n    return (a, b, c)\n\n\ndef f(x):\n    return g(False, False, x)\n"
_TEST = "from swp import f\n\n\ndef test_f():\n    assert f(3) == (False, False, 3)\n"


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
    (root / "swp.py").write_text(_SOURCE)
    (root / "tests" / "test_swp.py").write_text(_TEST)
    assert _detective(root, "regime", "--migrate", "--project-root", str(root)).returncode == 0
    return root


def test_converge_names_the_unchanged_mutant_and_never_offers_it_to_flag(project):
    run = _detective(project, "converge", "swp.py::f")
    assert run.returncode == 0, run.stdout + run.stderr
    page = run.stdout
    assert "· identical" in page and "equivalent by identity" in page, page
    assert "detective flag" not in page and "unproven" not in page, page
    assert "modulo 1 identical to the original" in page, page
    report = (project / ".detective" / "reports" / "converge_f.txt").read_text()
    assert "identical to the original (1: SWAP)" in report and "(no textual change)" in report, report
    assert "candidate-equivalent — retained" not in report and "`flag` what you can" not in report, report


def test_the_record_counts_it_under_its_own_state(project):
    record = json.loads(_detective(project, "converge", "swp.py::f", "--json").stdout)
    verdicts = record["survivor_report"]["verdicts"]
    assert [v["identical"] for v in verdicts] == [True]
    assert verdicts[0]["killable"] is False and verdicts[0]["searched"] == 0


def test_audit_does_not_call_it_unproven(project):
    page = _detective(project, "audit", "swp.py::f").stdout
    assert "· identical" in page and "unproven" not in page, page
