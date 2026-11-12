"""Intent: a read of the interpreter's own state is an environment read, so no golden describes the process
(Detective #96).

THE DEFECT (EP-B4, `synthesis/writer.numeric_backend_for`): its golden captured `'numpy'` but the function
returned `'numpy 2.5.3'` once any earlier test had imported numpy - order-dependent inside one
interpreter. `purity.environment_reads` counted the clock, the filesystem, `os.environ` and entropy, but
not `sys.modules`, `sys.path`, `sys.flags`, `platform.*` or `sys.version*`, so converge wrote a golden
at the witness input and called it deterministic.

THE RULING: those reads are counted (`process_state_read`), by their own reason, controlled by no
capability (`--clock` and `--env` cover neither), and routed exactly as the other uncovered reads: the
golden is refused and the page names why.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys

import pytest

from Detective.purity import environment_reads, process_state_read, uncovered_env_reads


@pytest.mark.parametrize(
    ("dotted", "reason"),
    [
        ("sys.modules", "reads process state via sys.modules"),
        ("sys.modules.get", "reads process state via sys.modules"),
        ("sys.path", "reads process state via sys.path"),
        ("sys.flags", "reads process state via sys.flags"),
        ("sys.version", "reads process state via sys.version"),
        ("sys.version_info", "reads process state via sys.version_info"),
        ("sys.platform", "reads process state via sys.platform"),
        ("platform.system", "reads process state via platform.system"),
        ("platform.python_version", "reads process state via platform.python_version"),
        ("sys.exit", ""),  # control flow, not a read of state
        ("sys.stdout", ""),
        ("os.environ", ""),  # the process ENVIRONMENT has its own class (`--env`)
        ("mysys.modules", ""),
        ("platformer.x", ""),
        ("sys", ""),
        ("", ""),
    ],
)
def test_process_state_is_named_by_its_own_reason(dotted, reason):
    assert process_state_read(dotted) == reason


def _reads(source: str) -> tuple[str, ...]:
    return environment_reads(ast.parse(source).body[0])


@pytest.mark.parametrize(
    "body",
    [
        'return "numpy" in sys.modules',
        "return sys.path[0]",
        "return sys.flags.optimize",
        "return sys.version_info >= (3, 12)",
        "return platform.system()",
        "return sys.version",
    ],
)
def test_a_read_of_process_state_is_an_environment_read(body):
    reads = _reads(f"def f(x):\n    {body}\n")
    assert reads and all(r.startswith("reads process state via ") for r in reads), reads


def test_a_function_that_reads_nothing_of_the_process_reads_nothing():
    assert _reads("def f(x):\n    return x + 1\n") == ()
    assert _reads("def f(x):\n    sys.exit(x)\n") == ()


def test_no_capability_covers_process_state():
    reads = _reads('def f(x):\n    return "numpy" in sys.modules\n')
    assert uncovered_env_reads(reads, clock_supplied=True, env_supplied=True) == reads


_SOURCE = (
    "import sys\n\n\ndef backend(kind):\n"
    '    if kind == "array" and "numpy" in sys.modules:\n'
    '        return "numpy " + sys.modules["numpy"].__version__\n'
    '    return "python"\n'
)
_TEST = 'from bk import backend\n\n\ndef test_backend():\n    assert backend("scalar") == "python"\n'


def _detective(cwd, *argv):
    return subprocess.run(  # noqa: S603 — the CLI under test
        [sys.executable, "-m", "Detective", *argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
        env=dict(os.environ),
    )


def test_converge_writes_no_golden_that_describes_the_process(tmp_path):
    root = tmp_path / "proj"
    (root / "tests").mkdir(parents=True)
    (root / "bk.py").write_text(_SOURCE)
    (root / "tests" / "test_bk.py").write_text(_TEST)
    assert _detective(root, "regime", "--migrate", "--project-root", str(root)).returncode == 0
    page = _detective(root, "converge", "bk.py::backend").stdout
    assert "· env-coupled" in page and "reads process state via sys.modules" in page, page
    written = list((root / "tests" / "detective").glob("test_bk_backend_*_synth.py"))
    assert not written, [p.read_text() for p in written]
    report = (root / ".detective" / "reports" / "converge_backend.txt").read_text()
    assert "golden refused — reads process state via sys.modules" in report, report
