"""Intent tests for three forced-exception degrade paths the local Sonar pass found never exercised
(2026-09-06).

Each is a documented "degrade, never raise" seam: a best-effort call whose failure must be absorbed
because raising would be worse than the stale state it leaves behind. None had a test that FORCED
the failure — so each guard's promise was pinned by nothing but its comment. Written from intent:
the failing callee is injected, and the seam's own contract (what it returns, what it must not do)
is asserted.

- ``certify._publish_suite_change``: telling a live pytest session a generated file changed on
  disk is best-effort. An older Wesker without the seam, or a collection hiccup inside it, must
  never fail the run that just wrote the file — the cost is a stale verdict, which the caller
  then reports honestly.
- ``decompose_apply._kill_matrix``: with no profile there is no proof suite, and the only honest
  disposition is to PROPOSE and never apply — an empty matrix, not an exception.
- ``equivalence.parse_input_expression``: an ``--input`` that passes the grammar gate and still
  fails to evaluate is the user's usage error, reported as ``InputExpressionError`` with the
  offending source — never a traceback.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import Wesker.ci

from Detective import engine
from Detective.certify import _publish_suite_change
from Detective.decompose_apply import _kill_matrix
from Detective.equivalence import InputExpressionError, parse_input_expression

# --- certify._publish_suite_change -------------------------------------------------------------


def test_a_refresh_that_raises_never_fails_the_write_that_triggered_it(monkeypatch):
    def boom(project_root, path):
        raise RuntimeError("collection hiccup")

    monkeypatch.setattr(Wesker.ci, "refresh_live_suite", boom)
    assert _publish_suite_change("/repo", "/repo/tests/test_x.py") is None


def test_a_refresh_that_works_is_told_the_root_and_the_path(monkeypatch):
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(Wesker.ci, "refresh_live_suite", lambda root, path: calls.append((root, path)))
    _publish_suite_change("/repo", "/repo/tests/test_x.py")
    assert calls == [("/repo", "/repo/tests/test_x.py")]


def test_no_project_root_means_no_session_to_tell(monkeypatch):
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(Wesker.ci, "refresh_live_suite", lambda root, path: calls.append((root, path)))
    _publish_suite_change("", "/repo/tests/test_x.py")
    _publish_suite_change(None, "/repo/tests/test_x.py")
    assert calls == []


# --- decompose_apply._kill_matrix ---------------------------------------------------------------


def test_no_profile_means_an_empty_matrix_so_the_apply_can_only_propose(monkeypatch):
    def boom(file, function, project_root):
        raise RuntimeError("no profile")

    monkeypatch.setattr(engine, "profile", boom)
    assert _kill_matrix("mod.py", "fn", "/repo") == {}


def test_a_profile_that_exists_hands_back_its_own_kill_matrix(monkeypatch):
    matrix = {"m1": ["tests/test_a.py::test_one"]}
    monkeypatch.setattr(
        engine, "profile", lambda file, function, project_root: SimpleNamespace(kill_matrix=matrix)
    )
    assert _kill_matrix("mod.py", "fn", "/repo") is matrix


# --- equivalence.parse_input_expression ---------------------------------------------------------


def test_an_input_that_parses_but_cannot_evaluate_is_a_usage_error_not_a_crash():
    # A permitted constructor (`ast` is allowlisted, the call is a plain Call) over an argument it
    # rejects: not a literal, so it takes the expression path; passes the grammar gate; raises
    # SyntaxError under eval — the user's error, named with the source that caused it.
    with pytest.raises(InputExpressionError) as excinfo:
        parse_input_expression("ast.parse('def')")
    assert "failed to evaluate" in str(excinfo.value)
    assert "ast.parse('def')" in str(excinfo.value)


def test_a_plain_literal_still_takes_the_literal_path():
    assert parse_input_expression("(1, 'a')") == (1, "a")
    assert parse_input_expression("7") == (7,)
