"""Intent: a call Detective runs on an input it invented or replayed cannot change Detective's own
process, and a survivor that kept the search out this way is named by what the function does (D#141).

THE DEFECT, measured 2026-10-25 on c4a014f:
- `equivalence._outcome(lower, (1,))`, where `lower` lowers the `RLIMIT_NOFILE` soft limit, returned
  `"2"` as an ordinary observation, and Detective's own soft limit dropped from 1048576 to 200.
- `detective converge 'm.py::notify'`, where `notify` runs `subprocess.run(["touch", ...])` and its
  only test stubs `subprocess.run`, spawned a real `touch`. A file appeared OUTSIDE the project, from
  the test's harvested argument replayed outside its monkeypatch.
- The page called the three survivors that only the child's behaviour distinguishes
  "unproven-equivalent" and offered `flag`. The test that pins them stubs the call and asserts its
  arguments.

`block_fs_writes` refused file writes (#105) and nothing else. Wesker#29 measured the same hazard in
Wesker's own equivalence check: an invented input set `RLIMIT_AS = (1, 1)` on the measuring process,
and no thread could start after it.

THE RULING:
- Detective's own audit hook refuses the process effects Wesker refuses (`_PROCESS_EFFECT_EVENTS`,
  kept one with `Wesker.write_authority._PROCESS_EFFECTS` by a fence below) before they run, scoped by
  the ContextVar like a write. Not Wesker's process-wide window: a speculative worker Detective
  abandons on its deadline would leave that window armed for the rest of the run.
- The refusal is the input's own outcome, `<effect-refused>`, never the write marker
  (`speculative_refusal`, one decision for all four sites). A target that swallows the refusal is
  refused anyway, because the sink's record decides. That rule now holds for golden capture's
  writes too.
- A survivor refused this way joins #105's family and keeps its standing. The page names it by its
  events ("calls subprocess.Popen") and asks for a test that stubs the call, never "writes files".
- Golden capture refuses such a function with `refuse_process_effect`. The declared `--env` is applied
  outside the armed window: setting a variable is a process effect, and that one is Detective's own.
"""

from __future__ import annotations

import os
import resource
import subprocess
import sys

import pytest

from Detective.cli import _refusal_phrase, _write_refused_action, _write_refused_rows
from Detective.equivalence import (
    _OUTCOME_EFFECT_REFUSED,
    _OUTCOME_WRITE_REFUSED,
    _outcome,
    _pair_disposition,
    speculative_refusal,
)
from Detective.synthesis.characterization import (
    _PROCESS_EFFECT_EVENTS,
    _try_capture,
    golden_capture_disposition,
    value_capture_coupling,
)


@pytest.fixture
def nofile():
    before = resource.getrlimit(resource.RLIMIT_NOFILE)
    yield before
    resource.setrlimit(resource.RLIMIT_NOFILE, before)  # a guard that failed must not break the session


def _lower(n):
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    resource.setrlimit(resource.RLIMIT_NOFILE, (min(soft, 64), hard))
    return n + 1


def _lower_quietly(n):
    try:
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        resource.setrlimit(resource.RLIMIT_NOFILE, (min(soft, 64), hard))
    except BaseException:  # noqa: BLE001, S110 — the target swallows everything, as real code may
        pass
    return n + 1


def test_the_refused_effects_are_wesker_s_list():
    # One list of what a speculative call may not do to the measuring process, in both tools.
    from Wesker.write_authority import _PROCESS_EFFECTS

    assert frozenset(_PROCESS_EFFECTS) == _PROCESS_EFFECT_EVENTS


@pytest.mark.parametrize("target", [_lower, _lower_quietly], ids=["raised", "swallowed"])
def test_a_speculative_call_cannot_lower_a_limit_of_detectives_process(nofile, target):
    effects: list[str] = []
    assert _outcome(target, (1,), refused_effects=effects) == _OUTCOME_EFFECT_REFUSED
    assert effects == ["resource.setrlimit"]
    assert resource.getrlimit(resource.RLIMIT_NOFILE) == nofile, "the limit landed"


def test_a_speculative_call_spawns_nothing_and_its_child_writes_nothing(tmp_path):
    sentinel = tmp_path / "outside" / "sentinel"
    sentinel.parent.mkdir()

    def notify(path):
        subprocess.run(["touch", path], check=False)  # noqa: S603, S607 — the hazard under test
        return len(path)

    effects: list[str] = []
    assert _outcome(notify, (str(sentinel),), refused_effects=effects) == _OUTCOME_EFFECT_REFUSED
    assert effects == ["subprocess.Popen"]
    assert not sentinel.exists(), "a speculative run spawned a process"


def test_a_speculative_chdir_and_environment_change_are_refused():
    cwd, environ = os.getcwd(), dict(os.environ)

    def wander(path):
        os.environ["D141_PROBE"] = "1"
        os.chdir(path)
        return path

    assert _outcome(wander, ("/",)) == _OUTCOME_EFFECT_REFUSED
    assert os.getcwd() == cwd and dict(os.environ) == environ


def test_an_effect_refusal_has_its_own_sign_and_both_sides_block():
    assert _OUTCOME_EFFECT_REFUSED != _OUTCOME_WRITE_REFUSED
    assert _pair_disposition(_OUTCOME_EFFECT_REFUSED, "1") == "blocked"
    assert _pair_disposition("1", _OUTCOME_EFFECT_REFUSED) == "blocked"


@pytest.mark.parametrize(
    ("code", "refusal"),
    [
        ("filesystem_write_blocked", "write_refused"),
        ("process_effect_blocked", "effect_refused"),
        ("outcome_uncontained", "abort"),
        ("", "abort"),
    ],
)
def test_only_a_refused_write_or_effect_is_an_inputs_own_outcome(code, refusal):
    assert speculative_refusal(code) == refusal


@pytest.mark.parametrize("target", [_lower, _lower_quietly], ids=["raised", "swallowed"])
def test_golden_capture_refuses_a_function_that_makes_a_process_effect(nofile, target):
    capture = _try_capture(target, (1,), {})
    assert capture is not None and capture.process_effects == ("resource.setrlimit",)
    assert resource.getrlimit(resource.RLIMIT_NOFILE) == nofile
    disposition = golden_capture_disposition(
        capture.filesystem_writes,
        capture.environment_paths,
        capture.environment_reads,
        "",
        capture.clock_dependent,
        capture.deterministic,
        capture.process_effects,
    )
    assert disposition == "refuse_process_effect"
    assert value_capture_coupling(disposition) == "function_coupled"


def test_golden_capture_refuses_a_write_the_target_swallowed(tmp_path):
    # Decided from the record: the guard's exception was swallowed, and the function returned from the
    # branch the real run never takes.
    def save(path):
        try:
            with open(path, "w") as fh:  # noqa: PTH123
                fh.write("x")
        except BaseException:  # noqa: BLE001, S110
            pass
        return "saved"

    capture = _try_capture(save, (str(tmp_path / "f.txt"),), {})
    assert capture is not None and capture.filesystem_writes, "a swallowed write was pinned as a golden"
    assert not (tmp_path / "f.txt").exists()


def test_a_declared_environment_is_still_applied_and_restored_around_the_capture():
    # The capability is Detective's own process effect, applied outside the armed window.
    def mode():
        return os.environ.get("D141_MODE", "unset")

    assert "D141_MODE" not in os.environ
    capture = _try_capture(mode, (), {}, env=(("D141_MODE", "on"),))
    assert capture is not None and capture.output == "'on'" and not capture.process_effects
    assert "D141_MODE" not in os.environ, "the declared variable outlived the capture"


def test_a_process_effect_is_never_called_a_write():
    assert _refusal_phrase([("V", "c", "open", "", "subprocess.Popen")]) == "calls subprocess.Popen"
    assert _refusal_phrase([("V", "c", "open", "", "write")]) == "writes files"
    assert _refusal_phrase([("V", "c", "open", "", "write, os.kill")]) == "writes files and calls os.kill"


def test_the_block_names_the_call_and_asks_for_a_stubbed_test():
    survivors = (("VALUE_a", "run(['touch', p]) → run(['', p])", "open", "", "subprocess.Popen"),)
    block = "\n".join(_write_refused_action(survivors, ("converge", "m.py::notify")))
    assert "pin the 1 survivor(s) nothing in the suite detects: the function calls subprocess.Popen" in block
    assert "stubs the call" in block and "writes files" not in block and "tmp_path" not in block
    rows = "\n".join(_write_refused_rows(survivors))
    assert "the function calls subprocess.Popen" in rows and "writes files" not in rows


# ── end to end: converge spawns nothing, names the call, and the advised test closes it ──────────────

_NOTIFY = (
    "import subprocess\n\n\n"
    "def notify(name):\n"
    "    subprocess.run(['touch', f'{{SENTINEL}}_{name}'], check=False)\n"
    "    return len(name)\n"
)
_NOTIFY_TEST = (
    "from m import notify\n\n\n"
    "def test_notify_spawns_nothing_here(monkeypatch):\n"
    "    calls = []\n"
    "    monkeypatch.setattr('m.subprocess.run', lambda *a, **k: calls.append(a))\n"
    "    assert notify('t') == 1\n"
    "    assert calls\n"
)


def _detective(cwd, *argv):
    return subprocess.run(  # noqa: S603 — the CLI under test
        [sys.executable, "-m", "Detective", *argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
        env=dict(os.environ),
    )


def test_converge_on_a_function_that_spawns_spawns_nothing_and_names_the_call(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    project = tmp_path / "proj"
    (project / "tests").mkdir(parents=True)
    (project / "m.py").write_text(_NOTIFY.replace("{{SENTINEL}}", str(outside / "sentinel")))
    (project / "tests" / "test_m.py").write_text(_NOTIFY_TEST)
    assert _detective(project, "regime", "--migrate", "--project-root", str(project)).returncode == 0

    converge = _detective(project, "converge", "m.py::notify")
    assert converge.returncode == 0, converge.stdout + converge.stderr
    assert not list(outside.iterdir()), "a speculative run spawned a process that wrote outside the project"
    page = converge.stdout
    assert "the function calls subprocess.Popen" in page, page
    assert "WRITE TEST:  pin the 3 survivor(s) nothing in the suite detects" in page, page
    assert "flag" not in page.split("WRITE TEST")[1], "a survivor no search judged was offered to flag"
