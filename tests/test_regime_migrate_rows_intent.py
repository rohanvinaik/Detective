"""Intent: regime's offer to migrate says what the migration will write, read from its plan.

THE DEFECT, measured 2026-10-25 in nine fresh foreign folders (the #114 and #124 reproductions). Each
held only `m.py` and `tests/test_m.py`, with no conftest and no config, and `detective regime` offered:

    DO THIS:  detective regime --migrate --project-root '<folder>'
      · writes          the marker (and pythonpath, if a conftest WE wrote was
                        supplying it) into pyproject — then removes that conftest.

The migration then created pyproject.toml with `pythonpath = ["."]` in every folder. The code sits at
the root and is imported bare, and the plan declares a root for exactly that case. No conftest
existed, so both of the sentence's conditions were false (COMMUNICATING_DETERMINISM: every printed
clause must be true). The rows are now the plan's own fields: what is created, what is declared,
what is removed, never a fixed sentence.
"""

from __future__ import annotations

import os
import subprocess
import sys

from Detective.cli import _migration_rows
from Detective.regime import Migration


def _plan(**fields):
    base = {
        "root": "/r",
        "declare_marker": False,
        "declare_pythonpath": False,
        "remove_conftests": (),
        "create_config": False,
        "blocked": (),
    }
    return Migration(**{**base, **fields})


def test_a_bare_root_tree_is_told_it_gets_a_config_the_marker_and_pythonpath_and_nothing_removed():
    page = "\n".join(_migration_rows(_plan(declare_marker=True, declare_pythonpath=True, create_config=True)))
    assert "· creates" in page and "pyproject.toml" in page
    assert "the detective marker" in page and 'pythonpath = ["."]' in page
    assert "· removes" not in page and "conftest" not in page, "nothing is removed, so nothing says so"


def test_a_conftest_detective_wrote_is_named_as_the_one_removed():
    page = "\n".join(_migration_rows(_plan(declare_pythonpath=True, remove_conftests=("conftest.py",))))
    assert "· removes" in page and "conftest.py: Detective wrote it" in page
    assert "· creates" not in page and "the detective marker" not in page


def test_a_marker_only_migration_declares_only_the_marker():
    page = "\n".join(_migration_rows(_plan(declare_marker=True)))
    assert "the detective marker in the config file pytest reads" in page
    assert "pythonpath" not in page and "· creates" not in page and "· removes" not in page
    assert page.rstrip().endswith("a file you wrote.")


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


def test_the_offer_matches_what_the_migration_then_does(tmp_path):
    (tmp_path / "m.py").write_text("def f(x):\n    return x + 1\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_m.py").write_text(
        "from m import f\n\n\ndef test_f():\n    assert f(1) == 2\n"
    )
    offer = _detective(tmp_path, "regime", "--project-root", str(tmp_path)).stdout
    assert "regime --migrate" in offer, offer
    assert "if a conftest WE wrote" not in offer and "· removes" not in offer, offer
    assert "· creates" in offer and 'pythonpath = ["."]' in offer, offer

    applied = _detective(tmp_path, "regime", "--migrate", "--project-root", str(tmp_path))
    assert applied.returncode == 0, applied.stdout + applied.stderr
    config = (tmp_path / "pyproject.toml").read_text()
    assert 'pythonpath = ["."]' in config and "detective:" in config, config
    assert not (tmp_path / "conftest.py").exists()
