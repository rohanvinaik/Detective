"""A line gated on the interpreter's own state is a fixture hand-back, never an `--input` ask
(Detective #96, #101, #140 item 2).

The defect: `purity.process_state_read` (#96) made converge refuse a golden that "reads process state via
sys.modules", and `environment_gate_kind` (#101) routed a read no capability covers to the fixture
hand-back, but that hand-back yields to an open killable witness. For
`def backend() -> str: return "numpy" if "numpy" in sys.modules else "none"` the witness's golden is
refused, so the page printed `golden refused - reads process state via sys.modules` and then
`DO THIS: detective converge ... --input "()"`: a function that takes no argument asked for an `--input`,
for a line no argument reaches. Both halves were false.

These tests run the real CLI end to end on that fixture, and on a function that DOES take an argument but
whose open lines sit behind the same read, and pin the pure gate.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from Detective.capabilities import process_state_covers
from Detective.cli import _residual_action, converge_next_action, converge_step, environment_gate_kind

_PROCESS = "reads process state via sys.modules"
_FILE = "reads the filesystem via os.path.exists()"
_CLOCK = "reads the clock via time.time()"
_ENV = "reads process env via os.environ"

_ZERO_ARG = (
    'import sys\n\n\ndef backend() -> str:\n    return "numpy" if "numpy" in sys.modules else "none"\n'
)
_WITH_ARG = (
    "import sys\n\n\ndef backend(prefer: str) -> str:\n"
    '    if prefer == "a":\n        return "a"\n'
    '    return "numpy" if "numpy" in sys.modules else "none"\n'
)


def _run(cwd: Path, *argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "Detective", *argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
        env=dict(os.environ),
    )


def _project(tmp_path: Path, source: str, test: str) -> Path:
    project = tmp_path / "proj"
    (project / "tests").mkdir(parents=True)
    (project / "pyproject.toml").write_text('[tool.pytest.ini_options]\ntestpaths = ["tests"]\n')
    (project / "b.py").write_text(source)
    (project / "tests" / "test_x.py").write_text(test)
    assert _run(project, "regime", "--migrate", "--project-root", str(project)).returncode == 0
    return project


@pytest.mark.parametrize(
    ("source", "test"),
    [
        (_ZERO_ARG, "def test_unrelated():\n    assert 1 + 1 == 2\n"),
        (_WITH_ARG, 'from b import backend\n\n\ndef test_a():\n    assert backend("a") == "a"\n'),
    ],
    ids=["takes_no_argument", "takes_an_argument"],
)
def test_a_process_state_gated_function_is_handed_back_never_asked_for_an_input(tmp_path, source, test):
    project = _project(tmp_path, source, test)
    done = _run(project, "converge", "b.py::backend", "--json")
    decision = json.loads(done.stdout)["decision"]
    assert decision["code"] == "environment_fixture"
    assert decision["step"]["kind"] == "hand_back" and decision["step"]["argv"] is None
    assert decision["plan"] is None
    page = _run(project, "converge", "b.py::backend").stdout
    assert "--input" not in page.split("WRITE TEST")[-1].replace("no --input", "")
    assert "DO THIS:  detective converge" not in page
    assert "WRITE TEST:" in page
    assert "reads process state via sys.modules" in page
    assert "monkeypatch.setitem(sys.modules" in page


# ── the pure gate ─────────────────────────────────────────────────────────────────────────────────────


def test_process_state_covers_only_the_interpreter_state_words():
    assert process_state_covers(_PROCESS)
    assert process_state_covers("reads process state via platform.system")
    assert not process_state_covers(_ENV), "the process ENVIRONMENT is --env's, not interpreter state"
    assert (
        not process_state_covers(_CLOCK) and not process_state_covers(_FILE) and not process_state_covers("")
    )


@pytest.mark.parametrize(
    ("reads", "clock", "env", "kind"),
    [
        ([_PROCESS], False, False, "process_state"),
        ([_PROCESS], True, True, "process_state"),
        ([_PROCESS, _FILE], False, False, "process_state"),
        ([_PROCESS, _CLOCK], False, False, "clock"),
        ([_PROCESS, _CLOCK], True, False, "process_state"),
        ([_PROCESS, _ENV], False, False, "env"),
        ([_FILE], False, False, "fixture"),
        ([], False, False, "none"),
    ],
)
def test_environment_gate_kind_names_process_state_after_the_declarable_capabilities(reads, clock, env, kind):
    assert environment_gate_kind(reads, clock, env) == kind


def _next(gate, killable=False, gap=True):
    return converge_next_action("incomplete", "", killable, gap, env_gate=gate)


def test_process_state_outranks_a_killable_witness_but_a_file_fixture_still_yields_to_one():
    assert _next("process_state") == "environment_fixture"
    assert _next("process_state", killable=True) == "environment_fixture"
    assert _next("process_state", killable=True, gap=False) == "environment_fixture"
    assert _next("fixture", killable=True) == "close_the_gap", "the #101 ranking for a file read stands"
    assert _next("clock", killable=True) == "declare_clock"
    assert converge_next_action("complete", "", False, False, env_gate="process_state") == "settled"
    assert _next("process_state", gap=False) == "settled"
    assert converge_step("environment_fixture", "", "", False, "", "not_applicable") == (
        "hand_back",
        "environment_gated",
    )


def test_decompose_names_the_fixture_for_a_process_state_gate_and_not_an_env_declaration():
    proof = SimpleNamespace(environment_gated=(_PROCESS,), missing_lines=(5,))
    page = "\n".join(_residual_action(None, proof, None, "b.py::backend"))
    assert "STOP." in page and "sys.modules" in page
    assert "build that state in a test, then re-run" in page and "declare --env on converge" not in page
    proof = SimpleNamespace(environment_gated=(_FILE,), missing_lines=(5,))
    assert "declare --env" in "\n".join(_residual_action(None, proof, None, "b.py::backend"))


# ── what the hand-back is FOR (integrator follow-up to the process-state routing) ─────────────────────

from Detective.cli import fixture_purpose  # noqa: E402

_COVERED = (
    "import sys\n\n\ndef numeric_backend_for(name: str) -> str:\n"
    "    mod = sys.modules.get(name)\n    if mod is None:\n        return name\n"
    "    return f\"{name} {getattr(mod, '__version__', '')}\".strip()\n"
)
_COVERED_TESTS = (
    "from mod import numeric_backend_for\n\n\ndef test_unloaded():\n"
    '    assert numeric_backend_for("definitely_not_loaded_xyz") == "definitely_not_loaded_xyz"\n\n\n'
    'def test_loaded_weak():\n    assert numeric_backend_for("json").startswith("json")\n'
)


def test_fixture_purpose_names_which_of_the_open_things_the_block_is_for():
    assert fixture_purpose(True, False) == "lines"
    assert fixture_purpose(False, True) == "mutants"
    assert fixture_purpose(True, True) == "both"
    assert fixture_purpose(False, False) == "none"


def _converge_page(tmp_path, source, test, name="mod"):
    project = tmp_path / "proj"
    (project / "tests").mkdir(parents=True)
    (project / "pyproject.toml").write_text('[tool.pytest.ini_options]\ntestpaths = ["tests"]\n')
    (project / f"{name}.py").write_text(source)
    (project / "tests" / f"test_{name}.py").write_text(test)
    assert _run(project, "regime", "--migrate", "--project-root", str(project)).returncode == 0
    return project, _run(
        project, "converge", f"{name}.py::{'numeric_backend_for' if name == 'mod' else 'backend'}"
    )


def test_every_line_covered_and_only_killable_mutants_the_block_names_the_mutants_not_a_line_gap(tmp_path):
    project, done = _converge_page(tmp_path, _COVERED, _COVERED_TESTS)
    page = done.stdout
    assert "✗ uncovered" not in page, "the fixture covers every line"
    assert "still killable" in page
    block = page.split("WRITE TEST")[-1]
    assert "killable mutant(s)" in block.splitlines()[0]
    assert "uncovered line(s)" not in page.split("FINAL")[0].split("WRITE TEST")[-1]
    assert "reads process state via sys.modules" in block and "monkeypatch.setitem(sys.modules" in block
    assert "no --input value pins them either" in block


def test_a_line_gap_alone_keeps_the_line_header_and_both_name_both(tmp_path):
    _, done = _converge_page(tmp_path, _ZERO_ARG, "def test_unrelated():\n    assert 1 + 1 == 2\n", "b")
    assert "build the external state the uncovered line(s) read" not in done.stdout.split("WRITE TEST")[0]
    header = done.stdout.split("WRITE TEST:")[-1].splitlines()[0]
    assert "uncovered line(s)" in header and "killable mutant(s)" in header, "a line gap AND killable mutants"


def test_following_the_pages_next_step_never_prints_a_second_input_ask(tmp_path):
    project, first = _converge_page(tmp_path, _COVERED, _COVERED_TESTS)
    assert "DO THIS" not in first.stdout and "--input" not in first.stdout.split("WRITE TEST")[-1].replace(
        "no --input", ""
    )
    decision = json.loads(_run(project, "converge", "mod.py::numeric_backend_for", "--json").stdout)[
        "decision"
    ]
    assert decision["step"]["kind"] == "hand_back" and decision["step"]["argv"] is None
    again = _run(project, *decision["step"]["then"])
    assert "DO THIS" not in again.stdout, "the next step is the hand-back again, never an --input command"
