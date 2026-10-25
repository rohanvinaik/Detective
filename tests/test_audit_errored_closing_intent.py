"""Intent: an errored test displaces exactly the audit endings it makes false (Wesker#17).

THE DEFECT, reproduced 2026-10-25 through `detective audit m.py::f` on a function its suite pins in
full, beside one fixture that asserts in its own setup (pytest: ERROR). The page named the errored test
(ddbd7c2's ERRORED NOW row), then closed:

    DONE:  the suite is complete and minimal. Nothing to do.

`DONE` is the forward channel's claim that no next action exists (COMMUNICATING_DETERMINISM §5), and
one did: the fixture's repair, then a re-audit with that test's evidence in it. Two states with
different remedies shared one sign (§3), and the ledger recorded `done_complete` for both. Under
`--two-sign` the same project printed "· Why  the setup is clean: the suite loads and no intent test
fails" one row below "error in setup or teardown".

THE RULING. `repair_errored_test` ranks directly below redundancy and above every ending it falsifies:
`flag_equivalents` (a flag offer against candidates the errored test may kill once it runs),
`done_divergent`, `done_unclassified` and `done_complete`. It ranks below everything that stays true
with the errored test present: a measurement that could not run or be trusted, a failing test, a
sample request, real gaps, and redundancy (a redundant test stays redundant when another starts to
run, because a cover only grows). Its step is `stop` in both modes: a setup with a broken fixture is
not clean, so under `--two-sign` it never maps to `run`. Where the two-sign line still runs converge
over a real gap, the Why no longer claims a clean setup, and an `· Also` row names the repair.
Exit codes are unchanged: bare audit 0 (the page names the cause), `--check` 0, `--check-strict` 2.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from Detective.cli import _audit_commands, audit_next_action, audit_step

# block, has_failing_tests, killable_gaps, missing_lines, redundant_tests, removing,
# candidate_equivalent, has_equivalent_ids, unclassified — then diverged=, errored=
_CLEAN = ("", False, 0, 0, 0, False, 0, False, 0)


@pytest.mark.parametrize(
    ("args", "diverged", "ending"),
    [
        (_CLEAN, 0, "done_complete"),
        (("", False, 0, 0, 0, False, 0, False, 3), 0, "done_unclassified"),
        (_CLEAN, 2, "done_divergent"),
        (("", False, 0, 0, 0, False, 2, True, 0), 0, "flag_equivalents"),
    ],
)
def test_an_errored_test_displaces_every_ending_it_makes_false(args, diverged, ending):
    assert audit_next_action(*args, diverged=diverged) == ending
    assert audit_next_action(*args, diverged=diverged, errored=1) == "repair_errored_test"


@pytest.mark.parametrize(
    ("args", "kept"),
    [
        (("fix_load", False, 0, 0, 0, False, 0, False, 0), "fix_load"),
        (("repair_measurement", False, 0, 0, 0, False, 0, False, 0), "repair_measurement"),
        (("", True, 0, 0, 0, False, 0, False, 0), "fix_failing_test"),
        (("provide_sample", False, 0, 0, 0, False, 0, False, 0), "provide_sample"),
        (("", False, 1, 0, 0, False, 0, False, 0), "close_the_gap"),
        (("", False, 0, 1, 0, False, 0, False, 0), "close_the_gap"),
        (("", False, 0, 0, 1, False, 0, False, 0), "remove_redundant"),
        (("", False, 0, 0, 1, True, 0, False, 0), "removing_now"),
    ],
)
def test_an_errored_test_never_displaces_an_ending_that_stays_true(args, kept):
    assert audit_next_action(*args, errored=3) == kept


@pytest.mark.parametrize("two_sign", [False, True])
def test_a_broken_fixture_stops_the_line_in_both_modes_and_names_the_re_audit(two_sign):
    assert audit_step("repair_errored_test", two_sign) == ("stop", "repair_errored_test")
    argv, then = _audit_commands("repair_errored_test", "m.py::f", two_sign)
    assert argv is None, "the repair is the person's: no Detective command runs before it"
    assert then is not None and then[:2] == ("audit", "m.py::f")
    assert ("--two-sign" in then) is two_sign, "the re-audit carries the universe it was measured in"


# ── end to end through the real CLI ─────────────────────────────────────────────────────────────

_BROKEN = (
    "import pytest\n\nfrom m import f\n\n\n@pytest.fixture\ndef broken_setup():\n"
    "    f(1)\n    assert False, 'fixture setup is broken'\n"
)
_REPAIRED = "import pytest\n\nfrom m import f\n\n\n@pytest.fixture\ndef broken_setup():\n    f(1)\n"


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


def _project(root, target, tests):
    (root / "m.py").write_text(target)
    (root / "conftest.py").write_text(_BROKEN)
    (root / "test_m.py").write_text(tests)
    migrate = _detective(root, "regime", "--migrate", "--project-root", str(root))
    assert migrate.returncode == 0, migrate.stdout + migrate.stderr


def test_a_pinned_suite_with_a_broken_fixture_is_told_to_repair_it_and_the_repair_lands(tmp_path):
    _project(
        tmp_path,
        "def f(x):\n    return x + 1\n",
        "from m import f\n\n\ndef test_errors_in_setup(broken_setup):\n    assert f(2) == 3\n\n\n"
        "def test_passes():\n    assert f(1) == 2\n",
    )
    run = _detective(tmp_path, "audit", "m.py::f")
    assert run.returncode == 0, "bare audit names the cause, so it exits 0: " + run.stderr
    page = run.stdout
    assert "Nothing to do" not in page and "DONE" not in page, page
    assert "DO THIS:  pytest test_m.py::test_errors_in_setup" in page, page
    assert "expectation wrong" not in page, "a test that never ran is asked a failing test's question"
    assert "detective audit 'm.py::f'" in page.split("· After fixing", 1)[-1], page

    record = json.loads(_detective(tmp_path, "audit", "m.py::f", "--json").stdout)
    assert record["decision"]["code"] == "repair_errored_test"
    assert record["decision"]["step"]["kind"] == "stop"

    shown = subprocess.run(
        [sys.executable, "-m", "pytest", "test_m.py::test_errors_in_setup", "-p", "no:cacheprovider"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert "1 error" in shown.stdout, "the printed command must run the test it is about: " + shown.stdout

    # Following the block lands: once the fixture runs, its test testifies, and the next instruction is
    # about the suite it now completes. Here it duplicates test_passes's kills, so that test becomes
    # redundant: the cover only grew, exactly why redundancy outranks an errored test.
    (tmp_path / "conftest.py").write_text(_REPAIRED)
    after = _detective(tmp_path, "audit", "m.py::f", "--json").stdout
    assert json.loads(after)["errored_tests"] == []
    assert json.loads(after)["decision"]["code"] == "remove_redundant", after


def test_the_two_sign_line_never_calls_a_setup_with_a_broken_fixture_clean(tmp_path):
    # A real gap under any universe: the negative branch has no test, so the line still runs converge.
    _project(
        tmp_path,
        "def f(x):\n    if x > 0:\n        return x + 1\n    return x - 1\n",
        "from m import f\n\n\ndef test_errors_in_setup(broken_setup):\n    assert f(2) == 3\n\n\n"
        "def test_positive():\n    assert f(1) == 2\n",
    )
    page = _detective(tmp_path, "audit", "m.py::f", "--two-sign").stdout
    assert "DO THIS:  detective converge 'm.py::f' --two-sign" in page, page
    assert "the setup is clean" not in page, "a fixture that errors is a setup that is not clean"
    assert "1 test(s) error in setup or teardown (above)" in page.split("· Also", 1)[-1], page
