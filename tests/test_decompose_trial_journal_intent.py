"""A `decompose` trial can never be left in the user's source (EP-A1 — docs/ENGINEERING_PASS_2026-09-26.md).

`decompose` proves an extraction by writing it into the user's own file and running the proof suite.
The revert was a plain statement after the suite ran: no try/finally, and in dry-run mode too. An
exception, a Ctrl-C during a suite that runs for minutes, or the hang watchdog's hard exit left the
TRIAL in the user's source — possibly a rewrite the suite had just rejected — and nothing said so.

Pinned here from intent: every exit that runs Python restores the original; a hard kill, which runs
nothing, leaves a journal the next command restores from; a file the user has edited since is never
overwritten; and an unresolved journal is never clobbered by a second trial.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from Detective import trial_journal
from Detective.trial_journal import SourceTrial, UnresolvedTrial, recover_interrupted_trials

ORIGINAL = "def f(x):\n    return x + 1\n"
TRIAL = "def _helper(x):\n    return x + 1\n\n\ndef f(x):\n    return _helper(x)\n"


def _project(tmp_path: Path) -> tuple[str, Path]:
    source = tmp_path / "mod.py"
    source.write_text(ORIGINAL, encoding="utf-8")
    return str(tmp_path), source


def _journals(root: str) -> list[Path]:
    return sorted(Path(root, trial_journal.TRIALS_REL).glob("*.json"))


def _interrupted_while_on_disk(root: str, source: Path, interrupt: BaseException) -> None:
    """Enter a trial and raise WHILE it is on disk — the moment EP-A1's restore exists for."""
    with SourceTrial(root, str(source), ORIGINAL, TRIAL):
        assert source.read_text(encoding="utf-8") == TRIAL
        raise interrupt


@pytest.mark.parametrize("interrupt", [RuntimeError("the suite crashed"), KeyboardInterrupt()])
def test_every_exit_that_runs_python_restores_the_original(tmp_path, interrupt):
    root, source = _project(tmp_path)
    with pytest.raises(type(interrupt)):
        _interrupted_while_on_disk(root, source, interrupt)
    assert source.read_text(encoding="utf-8") == ORIGINAL
    assert _journals(root) == []


def test_an_interrupted_trial_leaves_no_trial_bytecode_for_the_next_import(tmp_path):
    """Review finding (2026-09-29): the exception path restored the SOURCE but not its cache. The proof
    suite imports the trial, so the trial's ``.pyc`` exists; CPython accepts a ``.pyc`` whose recorded
    source mtime (whole seconds) and size match the file, so a restore landing in the same second at the
    same size let the next import run the TRIAL over the original. The journal recovery and the normal
    revert already retired the cache; this exit did not. Forced deterministically here: equal-length
    sources, the trial compiled while on disk, and the restored file given the trial's mtime."""
    import importlib.util
    import py_compile

    original, trial = "def f(x):\n    return x + 1\n", "def f(x):\n    return x + 2\n"
    assert len(original) == len(trial)
    source = tmp_path / "samesize.py"
    source.write_text(original, encoding="utf-8")
    cache = importlib.util.cache_from_source(str(source))
    trial_mtime = 0.0
    with pytest.raises(RuntimeError), SourceTrial(str(tmp_path), str(source), original, trial):
        py_compile.compile(
            str(source), cfile=cache, doraise=True, invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP
        )
        trial_mtime = os.stat(source).st_mtime
        raise RuntimeError("the suite crashed")
    assert source.read_text(encoding="utf-8") == original
    os.utime(source, (trial_mtime, trial_mtime))  # the same-second restore, made certain
    spec = importlib.util.spec_from_file_location("samesize_after_restore", source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.f(1) == 2, "the next import ran the trial's cached bytecode, not the restored source"


def test_a_kept_trial_stays_and_leaves_no_journal(tmp_path):
    root, source = _project(tmp_path)
    with SourceTrial(root, str(source), ORIGINAL, TRIAL) as trial:
        trial.keep()
    assert source.read_text(encoding="utf-8") == TRIAL
    assert _journals(root) == []


def test_the_journal_is_written_before_the_trial_touches_the_source(tmp_path):
    """Write-ahead: there is no instant at which the source holds the trial and no record says so."""
    root, source = _project(tmp_path)
    with SourceTrial(root, str(source), ORIGINAL, TRIAL):
        (journal,) = _journals(root)
        recorded = json.loads(journal.read_text(encoding="utf-8"))
        assert recorded["path"] == str(source)
        assert recorded["original"] == ORIGINAL


def _hard_kill_mid_trial(root: str, source: Path) -> None:
    """Enter a trial in a child process and die with os._exit — no finally, no __exit__ runs."""
    script = textwrap.dedent(
        f"""
        import os
        from Detective.trial_journal import SourceTrial
        t = SourceTrial({root!r}, {str(source)!r}, {ORIGINAL!r}, {TRIAL!r})
        t.__enter__()
        os._exit(9)
        """
    )
    subprocess.run([sys.executable, "-c", script], check=False, env=os.environ.copy())


def test_a_hard_kill_leaves_a_journal_that_the_next_command_restores_from(tmp_path):
    """Through the REAL CLI: the next command — any command — restores before it reads source."""
    root, source = _project(tmp_path)
    _hard_kill_mid_trial(root, source)
    assert source.read_text(encoding="utf-8") == TRIAL, "the kill must have left the trial on disk"
    assert len(_journals(root)) == 1

    done = subprocess.run(
        [sys.executable, "-m", "Detective.cli", "regime", "--project-root", root],
        capture_output=True,
        text=True,
        check=False,
        env=os.environ.copy(),
        cwd=root,
    )
    assert source.read_text(encoding="utf-8") == ORIGINAL
    assert _journals(root) == []
    assert "restored" in done.stderr


def test_a_file_edited_since_the_trial_is_never_overwritten(tmp_path, capsys):
    root, source = _project(tmp_path)
    _hard_kill_mid_trial(root, source)
    edited = "def f(x):\n    return x + 2  # the person's own edit\n"
    source.write_text(edited, encoding="utf-8")

    outcome = recover_interrupted_trials(root)

    assert list(outcome.values()) == ["diverged"]
    assert source.read_text(encoding="utf-8") == edited
    (journal,) = _journals(root)  # kept: it holds the only copy of the original
    assert json.loads(journal.read_text(encoding="utf-8"))["original"] == ORIGINAL
    assert "nothing was restored" in capsys.readouterr().err


def test_a_second_trial_never_clobbers_an_unresolved_journal(tmp_path):
    root, source = _project(tmp_path)
    _hard_kill_mid_trial(root, source)
    source.write_text("def f(x):\n    return 0\n", encoding="utf-8")  # diverged: recovery keeps the journal
    recover_interrupted_trials(root)
    (journal,) = _journals(root)
    before = journal.read_bytes()
    with pytest.raises(UnresolvedTrial), SourceTrial(root, str(source), "def f(x):\n    return 0\n", TRIAL):
        pass
    assert journal.read_bytes() == before
    assert source.read_text(encoding="utf-8") == "def f(x):\n    return 0\n"


# ── through the real decompose ───────────────────────────────────────────────────────────────────

# A function with a genuine seam: an independent filtered count-and-total loop inside a function
# whose remainder does real work, so the value gate admits the extraction and a trial is WRITTEN.
# (The e2e fixture `shipping_cost` never reaches a trial: its one candidate leaves a pure delegating
# wrapper, which the value gate rejects before anything touches the file.)
_SUMMARY = """\
def summarize(values, threshold):
    count = 0
    total = 0
    for v in values:
        if v > threshold:
            count += 1
            total += v
    mean = total / count if count else 0.0
    if mean > 10:
        grade = "high"
    elif mean > 5:
        grade = "mid"
    else:
        grade = "low"
    return count, mean, grade
"""

_SUMMARY_TESTS = """\
from summary import summarize


def test_high():
    assert summarize([20, 30, 1], 5) == (2, 25.0, "high")


def test_mid_and_low():
    assert summarize([6, 8], 0) == (2, 7.0, "mid")
    assert summarize([1, 2], 0) == (2, 1.5, "low")
    assert summarize([], 0) == (0, 0.0, "low")
"""


def test_a_ctrl_c_while_a_real_trial_is_on_disk_leaves_the_users_source_untouched(tmp_path, monkeypatch):
    """The EP-A1 repro, in dry-run mode — the mode ARCHITECTURE describes as writing nothing."""
    from Detective import engine
    from Detective.decompose_apply import apply_decomposition

    (tmp_path / "summary.py").write_text(_SUMMARY, encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_summary.py").write_text(_SUMMARY_TESTS, encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\n"
        'markers = ["detective: test generated by Detective"]\n'
        'pythonpath = ["."]\n',
        encoding="utf-8",
    )
    real_purge = engine._purge_stale_bytecode
    fired: list[str] = []

    def interrupt_while_the_trial_is_on_disk(path: str) -> None:
        # Only when the file on disk is NOT the original — i.e. inside a trial, never during the
        # proof converge that runs first.
        if os.path.basename(path) == "summary.py" and Path(path).read_text(encoding="utf-8") != _SUMMARY:
            fired.append(path)
            raise KeyboardInterrupt("simulated Ctrl-C while the trial is on disk")
        real_purge(path)

    monkeypatch.setattr(engine, "_purge_stale_bytecode", interrupt_while_the_trial_is_on_disk)
    try:
        apply_decomposition("summary.py", "summarize", str(tmp_path), write=False)
    except KeyboardInterrupt:
        pass
    if not fired:
        # A FAIL, not a skip: a skip here would quietly stop guarding EP-A1 (S11).
        pytest.fail("decompose wrote no trial for this target; the fixture no longer exercises EP-A1")
    assert (tmp_path / "summary.py").read_text(encoding="utf-8") == _SUMMARY
    assert _journals(str(tmp_path)) == []
