"""Intent: audit reads each named failure by its TYPED baseline outcome — an errored, skipped or
expected-failure test is never "failing" (Wesker#17).

The defect, reproduced 2026-10-25 through `detective audit` on a plain function whose suite has a
fixture that reaches the target and then asserts in its own setup (pytest: ERROR), an xfail, a skip and
a passing test. Wesker named the errored test in `failing_tests` (the run code was "assertion"; the
typed outcome in the same result's ledger was `error`), and audit printed:

    ⚠ FAILING NOW        1 test(s) fail on current code:
                         test_m.py::test_errors_in_setup
    DO THIS:  pytest -k 'test_m.py::test_errors_in_setup'
      · Then decide        is the TEST's expectation wrong, or is the CODE broken?

— an accusation of a wrong expectation against a test that never reached its own assertions. Wesker now
names only typed failures (`baseline_failure_standing`); this side consumes the typed outcome too, so an
older engine (or a cached result) that still names an errored test cannot put it back.

Intent: `failing` only for a named test typed `failed` (or `unrecorded`, where the engine's word is all
there is); `errored` for anything typed `error`, named apart and never gated; a pass, skip or expected
failure is neither. A genuine wrong expectation is still FAILING NOW.
"""

from __future__ import annotations

import os
import subprocess
import sys
import types

import pytest

from Detective.audit import (
    audit_gate_exit,
    audit_measurement_incomplete,
    baseline_failure_disposition,
    function_errored_tests,
    function_failing_tests,
)


@pytest.mark.parametrize(
    ("named", "outcome", "disposition"),
    [
        (True, "failed", "failing"),
        (True, "unrecorded", "failing"),  # no ledger row: the engine's word stands
        (True, "error", "errored"),  # the defect
        (False, "error", "errored"),  # an errored test the engine did not name is still named here
        (True, "skipped", "not_failing"),
        (True, "xfailed", "not_failing"),
        (True, "passed", "not_failing"),
        # A call that raised is a failing test whether or not an older engine named it (#124): it is
        # in the floor, and every kill it reports over this function is meaningless.
        (False, "failed", "failing"),
        (False, "passed", "not_failing"),
        (False, "unrecorded", "not_failing"),
    ],
)
def test_the_typed_outcome_decides_what_the_reader_is_told(named, outcome, disposition):
    assert baseline_failure_disposition(named, outcome) == disposition


def _ev(test_id, outcome):
    return types.SimpleNamespace(test_id=test_id, baseline_outcome=outcome)


def test_an_older_engine_that_names_an_errored_test_cannot_make_it_failing():
    named = ["t::errored", "t::wrong", "t::skipped", "t::no_row", "t::not_in_suite"]
    typed = {
        "t::errored": "error",
        "t::wrong": "failed",
        "t::skipped": "skipped",
        "t::unnamed_error": "error",
        "t::raised": "failed",  # a call that raised, which an older engine never named (#124)
        "t::passes": "passed",
    }
    # This function's suite: each test killed a mutant or ran one of its lines (`function_test_suite`).
    suite = [
        "t::errored",
        "t::wrong",
        "t::skipped",
        "t::no_row",
        "t::unnamed_error",
        "t::raised",
        "t::passes",
    ]
    kill_matrix = {"M1": ["t::wrong"]}
    line_coverage = {t: [1] for t in suite}
    failing = function_failing_tests(named, kill_matrix, line_coverage, typed)
    errored = function_errored_tests(kill_matrix, line_coverage, typed)
    assert failing == ("t::wrong", "t::no_row", "t::raised"), (
        "the engine's order, then its unnamed typed failures"
    )
    assert errored == ("t::errored", "t::unnamed_error")
    assert function_failing_tests([], {}, {}, {}) == ()
    assert function_errored_tests({}, {}, {}) == ()
    # A test the ledger does not carry reads unrecorded: the engine's word stands, never green.
    assert function_failing_tests(["t::x"], {}, {"t::x": [3]}, {}) == ("t::x",)
    # Sorted whatever the ledger's order: no engine order exists for a test it did not name.
    reversed_typed = {"t::z": "error", "t::a": "error"}
    assert function_errored_tests({}, {"t::z": [1], "t::a": [1]}, reversed_typed) == ("t::a", "t::z")
    # Outside this function's suite, neither list names it.
    assert function_errored_tests({}, {"t::other": []}, {"t::other": "error"}) == ()


def test_an_errored_test_is_an_unmeasured_test_under_the_strict_gate():
    """Absent evidence is not clean evidence (COMMUNICATING_DETERMINISM §3.1, "measured no gap ·
    could not measure"). An errored test never ran to a verdict, so it is a measurement limit: the
    strict gate's distinct ``2``, never a pass. It is no code gap, so never a ``1``, and the plain
    ratchet stays a claim about the code alone."""
    assert audit_measurement_incomplete(0, 1) is True
    assert audit_measurement_incomplete(0, 0) is False
    assert audit_measurement_incomplete(2) is True, "the search's own limit is unchanged"
    assert audit_measurement_incomplete(0) is False, "a caller that passes no errored count reports none"
    assert audit_gate_exit(False, audit_measurement_incomplete(0, 1), strict=True) == 2
    assert audit_gate_exit(False, audit_measurement_incomplete(0, 1), strict=False) == 0
    assert audit_gate_exit(True, audit_measurement_incomplete(0, 1), strict=True) == 1, (
        "a specification gap still outranks it"
    )


# ── end to end through the real CLI ─────────────────────────────────────────────────────────────

_TARGET = "def f(x):\n    if x > 0:\n        return x + 1\n    return x - 1\n"
_CONFTEST = (
    "import pytest\n\nfrom m import f\n\n\n@pytest.fixture\ndef broken_setup():\n"
    "    f(1)\n    assert False, 'fixture setup is broken'\n"
)
_TESTS = (
    "import pytest\n\nfrom m import f\n\n\n"
    "def test_errors_in_setup(broken_setup):\n    assert f(2) == 3\n\n\n"
    "@pytest.mark.xfail(reason='known', strict=False)\n"
    "def test_expected_failure():\n    assert f(-2) == 99\n\n\n"
    "@pytest.mark.skip(reason='not today')\ndef test_skipped():\n    assert f(0) == -1\n\n\n"
    "def test_passes():\n    assert f(5) == 6\n"
)
_WRONG = "from m import f\n\n\ndef test_wrong_expectation():\n    assert f(-5) == 99\n"


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


def test_an_errored_test_is_named_apart_and_a_wrong_expectation_still_fails(tmp_path):
    (tmp_path / "m.py").write_text(_TARGET)
    (tmp_path / "conftest.py").write_text(_CONFTEST)
    (tmp_path / "test_m.py").write_text(_TESTS)
    migrate = _detective(tmp_path, "regime", "--migrate", "--project-root", str(tmp_path))
    assert migrate.returncode == 0, migrate.stdout + migrate.stderr
    out = _detective(tmp_path, "audit", "m.py::f").stdout
    assert "FAILING NOW" not in out, out
    assert "expectation wrong" not in out, out
    assert "ERRORED NOW" in out and "test_errors_in_setup" in out, out
    assert "test_skipped" not in out and "test_expected_failure" not in out, out

    (tmp_path / "test_wrong.py").write_text(_WRONG)
    out = _detective(tmp_path, "audit", "m.py::f").stdout
    failing_rows = out.split("⚠ FAILING NOW", 1)[-1].split("⚠ ERRORED NOW", 1)[0]
    assert "test_wrong_expectation" in failing_rows, out
    assert "test_errors_in_setup" not in failing_rows, "the errored test rode back in as failing"
    assert "pytest test_wrong.py::test_wrong_expectation" in out, out


# ── the gate's warning names the cause the run holds ────────────────────────────────────────────


def test_the_gate_warning_names_each_unmeasured_cause_apart():
    """Since Wesker#17 an errored test alone makes the audit's measurement incomplete, and the gate's
    warning still said "{unclassified} survivor(s) the equivalence search could not classify" whatever
    the run held: an errored fixture read as "0 survivor(s) the equivalence search could not
    classify". That names a false cause, whose repair (a longer search) cannot fix a broken setup
    (COMMUNICATING_DETERMINISM §3)."""
    from Detective.cli import _unmeasured_clause

    errored_only = _unmeasured_clause(0, 1)
    assert "errored in setup or teardown" in errored_only
    assert "survivor" not in errored_only, "an errored test was reported as an unclassified survivor"
    unclassified_only = _unmeasured_clause(2, 0)
    assert unclassified_only.startswith("2 survivor(s)") and "errored" not in unclassified_only
    both = _unmeasured_clause(2, 1)
    assert both.index("survivor") < both.index("errored"), "both causes, each named, in a fixed order"
    assert _unmeasured_clause(0, 0) == ""


def test_an_errored_fixture_over_a_pinned_suite_is_warned_as_itself_through_the_gate(tmp_path):
    (tmp_path / "m.py").write_text("def f(x):\n    return x + 1\n")
    (tmp_path / "conftest.py").write_text(_CONFTEST)
    (tmp_path / "test_m.py").write_text(
        "from m import f\n\n\ndef test_errors_in_setup(broken_setup):\n    assert f(2) == 3\n\n\n"
        "def test_passes():\n    assert f(1) == 2\n"
    )
    migrate = _detective(tmp_path, "regime", "--migrate", "--project-root", str(tmp_path))
    assert migrate.returncode == 0, migrate.stdout + migrate.stderr
    check = _detective(tmp_path, "audit", "m.py::f", "--check")
    assert check.returncode == 0, "an errored test is no specification gap: " + check.stdout + check.stderr
    warning = check.stderr.split("⚠ measurement incomplete", 1)[-1]
    assert "1 test(s) errored in setup or teardown" in warning, check.stderr
    assert "could not classify" not in warning, "the warning named the search for a broken fixture"
    strict = _detective(tmp_path, "audit", "m.py::f", "--check-strict")
    assert strict.returncode == 2, "could not measure must not pass the strict gate: " + strict.stderr
