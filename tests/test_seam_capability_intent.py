"""The live seam is called ONCE; an internal TypeError is never swallowed as an old-Wesker signature.

The defect: `_run_live` wrapped `run_with_live_suite(root, lambda: _run(args), …)` in an
`except TypeError:` ladder to feature-detect an older Wesker. But Wesker deliberately PROPAGATES
exceptions from the body (it returns None only when the body never ran), and `_run(args)` writes
test files. So an ORDINARY TypeError raised *inside* `_run` — a real bug, not a signature mismatch —
was caught as "old Wesker" and the whole body was RE-RUN, up to three times, replaying its writes.

The fix calls the seam once with explicit kwargs. The published Detective/Wesker pair is version
pinned to a matched seam, so a genuine signature mismatch is a broken install that fails loudly
rather than being retried. This test is authored from that intent: the body must run exactly once
and the TypeError must propagate. It fails on the old ladder (body ran three times).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import Detective.cli as cli


def _fake_seam(
    project_root,
    fn,
    target_files=None,
    paths=None,
    trace_progress=None,
    trace_budget_s=None,
    trace_session_budget_s=None,
    diagnostic=None,
):
    """Mimics Wesker's real contract: run the body and PROPAGATE its exception (it returns None
    only when the body never ran)."""
    return fn()


def test_an_internal_typeerror_in_the_body_propagates_and_runs_the_body_once(tmp_path, monkeypatch):
    calls = {"n": 0}

    def fake_run(args):
        calls["n"] += 1
        raise TypeError("an ordinary bug inside the command body, not a seam signature mismatch")

    # The seam is imported locally as `from Wesker.ci import run_with_live_suite`, so patch it there.
    monkeypatch.setattr("Wesker.ci.run_with_live_suite", _fake_seam)
    monkeypatch.setattr(cli, "_run", fake_run)
    # Isolate from the caller's real interpreter/venv: this test is about retry, not disposition.
    monkeypatch.setattr(cli, "_execution_context", lambda: SimpleNamespace(disposition="ready"))

    args = SimpleNamespace(command="diagnose", project_root=str(tmp_path), target=None, json=False)

    with pytest.raises(TypeError):
        cli._run_live(args)

    assert calls["n"] == 1, f"body re-run {calls['n']}x — the TypeError ladder replayed a side-effecting body"
