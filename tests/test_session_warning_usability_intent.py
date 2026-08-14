"""Detective's missing-dependency advice must be knowably correct — reproduced on ARC_AGI_3.

Two real usability bugs, both found by running detective on a real outside repo (ARC_AGI_3) via the
project's proper workflow:
  1. the install example hardcoded `.[test]`, but a project may declare `dev` and NOT `test`, so the
     copied command errors. `install_extra_target` names the project's ACTUAL declared extra.
  2. when the missing module is ALREADY installed in a sibling venv, the fix is to RUN detective from
     that environment, not to install into detective's own interpreter. `_venv_with_module` detects
     it — the accurate remedy when detective was invoked from outside the project's env.
"""

from __future__ import annotations

import os

from Detective.cli import (
    _declared_extras,
    _format_session_warning,
    _venv_with_module,
    install_extra_target,
)


# ── install_extra_target: name the DECLARED extra, never a convention ──
def test_names_dev_when_there_is_no_test_extra():
    # ARC_AGI_3's real shape: dev / game / perf, no `test`. A guessed `.[test]` would error.
    assert install_extra_target(["dev", "game", "perf"]) == ".[dev]"


def test_prefers_a_test_extra_over_dev_when_both_exist():
    assert install_extra_target(["dev", "test"]) == ".[test]"


def test_preserves_the_declared_casing():
    assert install_extra_target(["Dev"]) == ".[Dev]"


def test_bare_project_when_no_test_or_dev_extra():
    assert install_extra_target(["game", "perf"]) == "."
    assert install_extra_target([]) == "."


# ── _declared_extras: read the project's real pyproject ──
def test_reads_the_declared_extras(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\n[project.optional-dependencies]\ndev = []\ngame = []\n'
    )
    assert sorted(_declared_extras(str(tmp_path))) == ["dev", "game"]


def test_no_or_unreadable_pyproject_declares_no_extras(tmp_path):
    assert _declared_extras(str(tmp_path)) == []  # no pyproject at all
    assert _declared_extras(None) == []


# ── _venv_with_module: detect an already-satisfied sibling venv ──
def _make_venv(root: str, name: str, module_dir: str) -> None:
    site = os.path.join(root, name, "lib", "python3.12", "site-packages")
    os.makedirs(site)
    os.makedirs(os.path.join(root, name, "bin"))
    open(os.path.join(root, name, "bin", "python"), "w").close()
    os.makedirs(os.path.join(site, module_dir))


def test_finds_the_sibling_venv_that_has_the_module(tmp_path):
    _make_venv(str(tmp_path), ".venv312", "arc_agi")
    # given the PACKAGE name (hyphenated), maps to the arc_agi import dir
    assert _venv_with_module(str(tmp_path), "arc-agi") == os.path.join(str(tmp_path), ".venv312")


def test_none_when_no_sibling_venv_has_the_module(tmp_path):
    _make_venv(str(tmp_path), ".venv", "numpy")
    assert _venv_with_module(str(tmp_path), "arc-agi") is None
    assert _venv_with_module(None, "arc-agi") is None


# ── _format_session_warning: both fixes, end to end ──
def _import_diag(module: str) -> dict:
    return {
        "reason": "collection_errors",
        "errors": [("tests/conftest.py", f"ModuleNotFoundError: No module named '{module}'")],
    }


def test_advice_names_the_real_extra_not_a_guessed_test(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\n[project.optional-dependencies]\ndev = []\n'
    )
    msg = _format_session_warning(_import_diag("arc_agi"), project_root=str(tmp_path))
    assert ".[dev]" in msg  # the project's ACTUAL extra
    assert ".[test]" not in msg  # never the guessed one


def test_advice_points_at_an_existing_venv_instead_of_installing(tmp_path):
    _make_venv(str(tmp_path), ".venv312", "arc_agi")
    msg = _format_session_warning(_import_diag("arc_agi"), project_root=str(tmp_path))
    assert ".venv312" in msg
    assert "ALREADY installed" in msg
    assert "uv pip install" not in msg  # nothing to install — the deps already exist there
