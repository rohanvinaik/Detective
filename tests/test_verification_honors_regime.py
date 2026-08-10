"""#58 — final verification runs under the project's OWN pytest regime, not a stripped one.

A certificate claims the proof suite passes under the project's real pytest configuration. The
verifier used to clear that configuration (`-o addopts=`) to dodge a `-q`-doubling parse quirk, and
in doing so it also erased pass/fail-affecting options — `--strict-markers`, `-W error`, a required
`-p plugin`. A suite that could not even COLLECT under its own regime then read as `passed`: a
false certificate in the only direction that matters. Reproduced before the fix: a project with
`addopts = --strict-markers` and an unregistered marker returns rc 2 natively, yet verification said
`passed`.

INTENT tests: the defect is a false PASS, so a characterization of current output cannot catch it.
These assert the regime is honored (the failing regime does not certify) and that closing the hole
did not reintroduce the `-q`-doubling miscount it was papering over.
"""

from __future__ import annotations

from Detective.certify import run_pytest_verification


def test_a_suite_that_fails_its_own_regime_is_not_certified(tmp_path):
    """The reproduced hole, closed. `--strict-markers` turns an unregistered marker into a
    collection error under the project's real regime; verification must reflect that, not strip the
    option and call the suite green."""
    (tmp_path / "pytest.ini").write_text("[pytest]\naddopts = --strict-markers\n")
    (tmp_path / "test_m.py").write_text(
        "import pytest\n\n@pytest.mark.this_marker_is_not_registered\ndef test_x():\n    assert True\n"
    )
    v = run_pytest_verification(str(tmp_path), "test_m.py")
    assert v.status != "passed", "a suite that fails its own regime was certified — the #58 false pass"
    assert v.status == "collection_failed"


def test_a_plain_passing_suite_still_certifies_with_correct_counts(tmp_path):
    """The regression guard: closing the hole must keep a genuinely green suite green, with its
    count parsed (the count splits passed-from-empty at rc 0)."""
    (tmp_path / "test_ok.py").write_text(
        "def test_a():\n    assert True\n\n\ndef test_b():\n    assert 1 + 1 == 2\n"
    )
    v = run_pytest_verification(str(tmp_path), "test_ok.py")
    assert v.status == "passed"
    assert v.passed == 2


def test_a_project_that_sets_q_itself_still_reports_a_pass(tmp_path):
    """The original bug the `-o addopts=` strip was added for must stay fixed WITHOUT the strip: a
    target carrying `-q` in addopts once doubled with our own `-q` into `-qq`, suppressing the
    summary and reporting 0 passed. We now add no `-q` of our own, so a single `-q` keeps the
    summary and the pass is seen."""
    (tmp_path / "pytest.ini").write_text("[pytest]\naddopts = -q\n")
    (tmp_path / "test_q.py").write_text("def test_a():\n    assert True\n")
    v = run_pytest_verification(str(tmp_path), "test_q.py")
    assert v.status == "passed"
    assert v.passed == 1
