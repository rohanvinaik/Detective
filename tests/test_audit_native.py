"""`audit_suite` reports ONE function's suite — including on `failing_tests`.

The scope rule is stated once in `audit_suite` and every emitted field is bound by it.
`failing_tests` was the field that escaped it: Wesker's baseline runs every discovered
test in the repo, so its `failing_tests` is REPO-WIDE, and passing it through raw put
thousands of unrelated names into a per-function report. Measured on Regenesis: 2153
names for a function whose suite was 2 tests.

Zero-arg and fixture-free (see `_support`): a fixture-dependent test contributes no
kill power under Wesker, so `profile` is swapped with a plain context manager.
"""

from __future__ import annotations

from unittest.mock import patch

from Detective.audit import audit_suite

from _support import make_pr


def _audit_with(pr):
    """Run `audit_suite` against a constructed ProfilingResult, bypassing the real profile."""
    with patch("Detective.audit.profile", return_value=pr):
        return audit_suite("m.py", "f", ".")


def _pr_two_functions():
    """A baseline as Wesker really returns one: this function's tests AND other
    functions' tests, the latter present in line_coverage with an EMPTY line list."""
    pr = make_pr(function_key="m.py::f")
    pr.kill_matrix = {"MUT1": ["test_mine_kills"]}
    pr.line_coverage = {
        "test_mine_kills": [1, 2],
        "test_mine_covers": [2],
        "test_other_function": [],  # ran in the baseline, but touches nothing of f
    }
    pr.executable_lines = [1, 2]
    return pr


def test_failing_tests_excludes_other_functions_tests():
    """A repo-wide failure that never touched this function is not this report's business."""
    pr = _pr_two_functions()
    pr.failing_tests = ["test_other_function", "test_never_discovered_here"]
    assert _audit_with(pr).failing_tests == ()


def test_failing_tests_keeps_a_test_that_covers_this_function():
    """Scoping must not HIDE a real one: a test that fails because of this function
    executed its lines, so it is in the suite via line_coverage and is still reported."""
    pr = _pr_two_functions()
    pr.failing_tests = ["test_mine_covers", "test_other_function"]
    assert _audit_with(pr).failing_tests == ("test_mine_covers",)


def test_failing_tests_keeps_a_killing_test_and_preserves_order():
    """A test in the kill matrix is in the suite too; the baseline's order is kept."""
    pr = _pr_two_functions()
    pr.failing_tests = ["test_mine_kills", "test_other_function", "test_mine_covers"]
    assert _audit_with(pr).failing_tests == ("test_mine_kills", "test_mine_covers")


def test_failing_tests_is_empty_when_the_baseline_reports_none():
    """No failures in, no failures out — the field does not invent one."""
    pr = _pr_two_functions()
    pr.failing_tests = []
    assert _audit_with(pr).failing_tests == ()


def test_test_count_counts_only_this_functions_suite():
    """The sibling field the scope rule was already applied to — pinned so the two
    cannot drift apart again (test_count and failing_tests share one `suite` set)."""
    pr = _pr_two_functions()
    pr.failing_tests = []
    assert _audit_with(pr).test_count == 2  # not 3: test_other_function is excluded
