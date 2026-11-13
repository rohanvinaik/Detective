"""Intent: a converge that writes tests keeps every pass's verdict row, and its bare re-run hits the final
row it stored (#100). The real CLI, in a fresh project.

This is the end-to-end half of `tests/test_verdict_cache_siblings_intent.py` (which holds the decisions it
rests on: the named question a row answers, and the canonical test fingerprint). It is a file of its own
because each case runs two converges in subprocesses, more wall than the traced baseline allows a single
test when a converge pins `verdict_cache.key_question`, and it reads the cache by the key's own text so
that a converge routing that function does not run it.

THE DEFECT: eviction compared the last three key fields, so each pass of a converge evicted the others
(`{budgets}:defer_shaped:{regime}` has no pass field), and a test the converge wrote fingerprinted
differently in the next session (a bare node id and un-stamped installed-package fixtures), so the bare
re-run never hit its own final row.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

_TARGET = (
    "def grade(score):\n    if score >= 90:\n        return 'A'\n"
    "    if score >= 80:\n        return 'B'\n    return 'C'\n"
)
_TEST = 'from m import grade\n\n\ndef test_a():\n    assert grade(95) == "A"\n'


def _detective(cwd, *argv):
    env = dict(os.environ)
    env.pop("PYTHONUNBUFFERED", None)
    return subprocess.run(
        [sys.executable, "-m", "Detective", *argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
        env=env,
    )


def _rows(project):
    return set(json.loads((project / ".detective" / "verdict_cache.json").read_text()))


def _project(tmp_path):
    project = tmp_path / "proj"
    (project / "tests").mkdir(parents=True)
    (project / "m.py").write_text(_TARGET)
    (project / "tests" / "test_m.py").write_text(_TEST)
    (project / "pyproject.toml").write_text("[tool.pytest.ini_options]\npythonpath = ['.']\n")
    assert _detective(project, "regime", "--migrate", "--project-root", str(project)).returncode == 0
    return project


def _passes(rows):
    """The pass indices the rows were measured for. A key reads
    `m.py::grade:<engine>:<src>:<tests>:<max>:<pass>:<budgets>…`; the function key holds the only `::`,
    so after splitting on `:` the pass is field 7."""
    return {row.split(":")[7] for row in rows}


@pytest.mark.parametrize("two_sign", [False, True])
def test_a_converge_that_writes_a_test_hits_its_own_final_row_on_the_bare_rerun(tmp_path, two_sign):
    """Counter-test 3, and counter-tests 1 and 2 on the real engine. Run 1 writes tests across several
    passes: every pass's row must survive its successors (pass 0, 1, 2 and the relation-bearing final
    measurement). Run 2 changes no byte of the written file, so its final measurement is a hit: no row of
    the relation-bearing question is replaced."""
    project = _project(tmp_path)
    flags = ["--two-sign"] if two_sign else []
    first = _detective(project, "converge", "m.py::grade", *flags)
    assert first.returncode == 0 and "tests/detective/" in first.stdout, first.stdout + first.stderr
    written = (next((project / "tests" / "detective").glob("*_synth.py"))).read_bytes()
    after_first = _rows(project)

    assert {"0", "1"} <= _passes(after_first), after_first
    final_rows = {r for r in after_first if "+relation" in r}
    assert final_rows, "no relation-bearing final row was stored"

    second = _detective(project, "converge", "m.py::grade", *flags)
    assert second.returncode == 0, second.stdout + second.stderr
    assert next((project / "tests" / "detective").glob("*_synth.py")).read_bytes() == written
    # the final row of run 1 is still there: the bare re-run hit it instead of replacing it
    assert final_rows <= _rows(project), (final_rows, _rows(project))
