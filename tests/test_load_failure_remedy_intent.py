"""Intent: a load failure's Fix row names the repair its own error names, never one cause for all (#129).

THE DEFECT, measured 2026-10-25 on fcd3348 through diagnose, audit and converge. Two no-package-context
targets were used: a module at the project root with `from .helpers import double`, and
`tools/voice/deep.py` with `from ...metrics import number`, deeper than any import root can parent.
Every verb printed

    STOP:  the live original could not be loaded: ImportError: attempted relative import with no
           known parent package
      · Fix                run under an interpreter/venv that has the missing dependency

and converge's STOP and FINAL added "run under an interpreter that has the module's dependencies". Nothing
was missing, and no interpreter can load a module whose relative import has no parent package. The row
sent the reader to install something (COMMUNICATING_DETERMINISM §3: a false cause is worse than
silence). One Fix row, `_RUN_UNDER_INTERPRETER`, served four renderers over every load failure.

THE RULING: `load_failure_remedy` reads the error the page already prints:
- a ModuleNotFoundError → the dependency row, unchanged;
- a relative import with no parent → give it a package;
- another ImportError → resolve the import it names;
- a named exception the module raised → fix that error;
- no error recorded → no cause asserted.
The cut reason's sentence no longer names a cause either.

Also here: converge's progress line said "✓ every mutant killed" over a pass where nothing was scored.
`zero_survivor_standing` names what the pass established.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from Detective.cli import load_failure_remedy
from Detective.converge import zero_survivor_standing


@pytest.mark.parametrize(
    ("reason", "code"),
    [
        (
            "the live original could not be loaded: ModuleNotFoundError: No module named 'funcy'",
            "missing_module",
        ),
        ("ImportError: attempted relative import with no known parent package", "no_package_context"),
        ("ImportError: attempted relative import beyond top-level package", "no_package_context"),
        ("ImportError: cannot import name 'x' from 'y' (/p/y.py)", "import_failed"),
        ("the live original could not be loaded: RuntimeError: needs a config file", "import_raised"),
        ("the target module could not be imported", "unknown"),
        ("", "unknown"),
    ],
)
def test_the_error_decides_the_repair(reason, code):
    assert load_failure_remedy(reason) == code


def test_a_pass_that_scored_nothing_never_claims_a_kill():
    assert zero_survivor_standing(3, 0) == "all_killed"
    assert zero_survivor_standing(3, 1) == "some_unscored", "a mutant with no verdict was not killed"
    assert zero_survivor_standing(0, 11) == "none_scored", "nothing scored is nothing killed"


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


def _project(root, files):
    for rel, text in {"tests/test_smoke.py": "def test_smoke():\n    assert 1 + 1 == 2\n", **files}.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    migrate = _detective(root, "regime", "--migrate", "--project-root", str(root))
    assert migrate.returncode == 0, migrate.stdout + migrate.stderr


_SCALE = "def scale(x):\n    if x > 10:\n        return 10\n    return x\n"


def test_a_relative_import_with_no_package_is_told_to_get_one_never_to_install_a_dependency(tmp_path):
    _project(
        tmp_path,
        {
            "helpers.py": "def double(x):\n    return 2 * x\n",
            "standalone.py": "from .helpers import double\n\n\n" + _SCALE,
        },
    )
    for verb in ("diagnose", "audit"):
        page = _detective(tmp_path, verb, "standalone.py::scale").stdout
        assert "attempted relative import" in page, page
        assert "missing dependency" not in page, f"{verb} named a dependency for a relative import"
        assert "give its relative imports a parent" in page, page
    run = _detective(tmp_path, "converge", "standalone.py::scale")
    assert run.returncode == 3, run.stdout + run.stderr
    assert "module's dependencies" not in run.stdout and "missing dependency" not in run.stdout, run.stdout
    assert "give its relative imports a parent" in run.stdout, run.stdout


def test_a_missing_dependency_is_still_named_one(tmp_path):
    _project(tmp_path, {"m.py": "import definitely_not_installed_xyz  # noqa: F401\n\n\n" + _SCALE})
    page = _detective(tmp_path, "audit", "m.py::scale").stdout
    assert "ModuleNotFoundError" in page and "missing dependency" in page, page


def test_a_module_that_raises_on_import_is_told_to_fix_that_error(tmp_path):
    _project(tmp_path, {"m.py": "raise RuntimeError('needs a config file')\n\n\n" + _SCALE})
    page = _detective(tmp_path, "audit", "m.py::scale").stdout
    assert "RuntimeError" in page and "missing dependency" not in page, page
    assert "fix the error the module raises while importing" in page, page


# #105's own end-to-end fixture (tests/test_write_authority_consumption_intent.py), restated here because
# test modules do not import one another.
_STORE = (
    "import os\n\n\n"
    "def atomic_write_text(path, text):\n"
    "    staging = f'{path}.tmp-{os.getpid()}'\n"
    "    with open(staging, 'w') as fh:\n"
    "        fh.write(text)\n"
    "    os.replace(staging, path)\n\n\n"
    "def save(path, text):\n"
    "    atomic_write_text(path, text)\n"
    "    return path\n"
)
_TEST = (
    "from store import save\n\n\n"
    "def test_save_writes_the_file(tmp_path):\n"
    "    target = tmp_path / 'store.json'\n"
    "    assert save(str(target), '{\"a\": 1}') == str(target)\n"
    "    assert target.exists()\n"
    "    assert target.read_text() == '{\"a\": 1}'\n"
)


def test_a_pass_with_an_unscored_mutant_says_so_and_never_claims_every_mutant_killed(tmp_path):
    # #105's own fixture: a SWAP mutant makes the test write outside its authority; the write is
    # prevented, so that mutant reaches no verdict while the three others are killed.
    _project(tmp_path, {"store.py": _STORE, "tests/test_store.py": _TEST})
    run = _detective(tmp_path, "converge", "store.py::save")
    assert "write_outside_authority" in run.stdout, run.stdout
    assert "every mutant killed" not in run.stderr, run.stderr
    assert "every scored mutant killed; 1 reached no verdict" in run.stderr, run.stderr


def test_a_pass_that_scored_nothing_renders_as_nothing_killed():
    from types import SimpleNamespace

    from Detective.converge import _zero_survivor_line

    nothing = SimpleNamespace(total_mutants=0, unscored_records=[{}] * 11)
    assert _zero_survivor_line(0, nothing) == "pass 0: no mutant reached a verdict, so none was killed"
    assert _zero_survivor_line(2, SimpleNamespace(total_mutants=4, unscored_records=[])) == (
        "pass 2: ✓ every mutant killed"
    )
