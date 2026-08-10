"""#59 — audit's line ledger rests on ADMISSIBLE evidence, not the raw observed union.

"A trace observed this line" and "a green test proves this line under the certificate regime" are
different facts. Audit judged line completeness from `result.line_coverage`, which includes the
coverage of tests that FAIL against the unmutated program — so a line reached only by a failing
test read as covered, and audit reported `line_complete` on evidence that proves nothing.
Reproduced: `choose(flag)` with a green test for the True branch and a FAILING test whose only
contribution is covering the False branch → audit said line-complete.

INTENT tests: the defect is a false line-complete, so a characterization of current output cannot
catch it. Driven through `audit_suite` (the real read-only assessment), asserting the failing
test's coverage does not close the ledger, and a control where a GREEN test legitimately does.
"""

from __future__ import annotations

import sys

from Detective.audit import audit_suite

_APP = "def choose(flag):\n    if flag:\n        return 1\n    return 0\n"


def _project(tmp_path, mod: str, test_body: str) -> str:
    """Write a project with a UNIQUE app-module name per test.

    Two projects sharing the module name `app`/`test_app` collide in `sys.modules` across nested
    pytest sessions (the second imports the first's since-deleted copy → nothing collected,
    test_count 0), a harness artifact, not an audit fact. Distinct names plus an evict keep each
    test hermetic. Returns the source file to audit."""
    (tmp_path / f"{mod}.py").write_text(_APP)
    (tmp_path / f"test_{mod}.py").write_text(test_body.format(mod=mod))
    for name in (mod, f"test_{mod}"):
        sys.modules.pop(name, None)
    return f"{mod}.py"


def test_a_line_reached_only_by_a_failing_test_is_a_gap(tmp_path):
    """The reproduced hole. Line 4 (`return 0`) is covered ONLY by the baseline-failing test; the
    admissible ledger excludes it, so the line is a real gap and `line_basis` names the strong
    evidence it rested on."""
    src = _project(
        tmp_path,
        "appgap",
        "from {mod} import choose\n\n\n"
        "def test_green_branch():\n    assert choose(True) == 1\n\n\n"
        "def test_failing_only_cover():\n    assert choose(False) == 1\n",
    )
    a = audit_suite(src, "choose", str(tmp_path))
    assert a.test_count > 0, "harness: the suite was not discovered"
    assert a.line_complete is False, "a failing test's coverage closed the line ledger — #59"
    assert 4 in a.missing_lines
    assert a.line_basis == "admissible"


def test_a_green_test_legitimately_closes_the_line(tmp_path):
    """The control: the SAME line, covered by a GREEN test, is admissibly proven — the fix must
    exclude only inadmissible evidence, not all coverage of the line."""
    src = _project(
        tmp_path,
        "appok",
        "from {mod} import choose\n\n\n"
        "def test_true_branch():\n    assert choose(True) == 1\n\n\n"
        "def test_false_branch():\n    assert choose(False) == 0\n",
    )
    a = audit_suite(src, "choose", str(tmp_path))
    assert a.test_count > 0, "harness: the suite was not discovered"
    assert a.line_complete is True
    assert 4 not in a.missing_lines
