"""Detective's missing-dependency advice must be knowably correct — reproduced on ARC_AGI_3.

Three real usability facts, all found by running detective on a real outside repo (ARC_AGI_3)
through its proper workflow — the first end-to-end dogfood on a greenfield target:
  1. the install example hardcoded `.[test]`, but a project may declare `dev` and NOT `test`, so the
     copied command errors. `install_extra_target` names the project's ACTUAL declared extra.
  2. when the missing module is already installed in a sibling venv that can RUN the suite, the fix
     is to run detective from there, not to install into detective's own interpreter.
  3. that venv must be CAPABLE — module + pytest + detective. Recommending a runtime-only venv (ARC's
     `.venv` has arc_agi but no pytest/detective) sends the user in a circle; `_ready_venv` requires
     all three, so ARC's capable `.venv312` is chosen over the module-only `.venv` that sorts first.
"""

from __future__ import annotations

import os

from Detective.cli import (
    _declared_extras,
    _format_session_warning,
    _ready_venv,
    install_extra_target,
)


# ── install_extra_target: name the DECLARED extra, never a convention ──
def test_names_dev_when_there_is_no_test_extra():
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
    assert _declared_extras(str(tmp_path)) == []
    assert _declared_extras(None) == []


# ── _ready_venv: recommend only a venv that can RUN the suite ──
def _make_venv(root, name, modules, *, pytest=True, detective=True):
    """Fake a venv: bin/python, the given site-packages module dirs, and (optionally) pytest and a
    detective console script — the three things a venv needs to actually run detective's live suite.
    """
    site = os.path.join(root, name, "lib", "python3.12", "site-packages")
    os.makedirs(site)
    os.makedirs(os.path.join(root, name, "bin"))
    open(os.path.join(root, name, "bin", "python"), "w").close()
    for module_dir in modules:
        os.makedirs(os.path.join(site, module_dir))
    if pytest:
        os.makedirs(os.path.join(site, "pytest"))
    if detective:
        open(os.path.join(root, name, "bin", "detective"), "w").close()


def test_finds_a_capable_sibling_venv(tmp_path):
    _make_venv(str(tmp_path), ".venv312", ["arc_agi"])  # pytest + detective by default
    assert _ready_venv(str(tmp_path), "arc-agi") == os.path.join(str(tmp_path), ".venv312")


def test_ignores_a_runtime_only_venv_that_cannot_run_the_suite(tmp_path):
    # The ARC bug in isolation: has the module, but no pytest and no detective -> not recommended.
    _make_venv(str(tmp_path), ".venv", ["arc_agi"], pytest=False, detective=False)
    assert _ready_venv(str(tmp_path), "arc-agi") is None


def test_prefers_the_capable_venv_over_a_runtime_only_one(tmp_path):
    # ARC's exact layout: `.venv` (module only) sorts FIRST, `.venv312` is the capable one.
    _make_venv(str(tmp_path), ".venv", ["arc_agi"], pytest=False, detective=False)
    _make_venv(str(tmp_path), ".venv312", ["arc_agi"])
    assert _ready_venv(str(tmp_path), "arc-agi") == os.path.join(str(tmp_path), ".venv312")


def test_none_when_no_venv_has_the_module(tmp_path):
    _make_venv(str(tmp_path), ".venv", ["numpy"])
    assert _ready_venv(str(tmp_path), "arc-agi") is None
    assert _ready_venv(None, "arc-agi") is None


# ── _format_session_warning: the fixes, end to end ──
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


def test_advice_points_at_a_capable_venv_instead_of_installing(tmp_path):
    _make_venv(str(tmp_path), ".venv312", ["arc_agi"])
    msg = _format_session_warning(_import_diag("arc_agi"), project_root=str(tmp_path))
    assert ".venv312" in msg
    assert "ALREADY installed" in msg
    assert "uv pip install" not in msg  # nothing to install — a capable env already exists


def test_a_runtime_only_venv_falls_through_to_install_advice(tmp_path):
    # `.venv` has the module but can't run the suite -> do NOT recommend it; give install advice.
    _make_venv(str(tmp_path), ".venv", ["arc_agi"], pytest=False, detective=False)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\n[project.optional-dependencies]\ndev = []\n'
    )
    msg = _format_session_warning(_import_diag("arc_agi"), project_root=str(tmp_path))
    assert "ALREADY installed" not in msg
    assert ".[dev]" in msg  # falls through to install advice, with the real extra
