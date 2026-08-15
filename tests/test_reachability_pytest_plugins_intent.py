"""A conftest reaching the target only through `pytest_plugins` keeps the fixture-only test (G2).

TEST_BASIS §15.2 (Part V gap ledger, G2 — soundness / lost kill). `_DYNAMIC` listed
`pytest_plugins`, but it was only ever checked against IMPORT-statement names, and
`pytest_plugins = [...]` is a module-level ASSIGNMENT, never an import — so the entry was dead.
A conftest that reaches the target solely via a declared plugin scored `conftest_reach=False`
and its fixture-only test (which names the target nowhere) was silently DROPPED — a lost kill,
the one error direction reachability forbids. The fix detects the assignment structurally and
marks the declaring module opaque, the module's own "any doubt → include" escape hatch.
"""

from __future__ import annotations

import os

from Detective.reachability import reachable_test_paths


def _repo(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[tool.pytest.ini_options]\ntestpaths = ["tests"]\n')
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("")
    (tmp_path / "pkg" / "mod.py").write_text("def quote(s):\n    return repr(s)\n")
    # A plugin module that imports the target and exposes it as a fixture.
    (tmp_path / "myplugin.py").write_text(
        "import pytest\nfrom pkg.mod import quote\n\n\n@pytest.fixture\ndef q():\n    return quote\n"
    )
    tdir = tmp_path / "tests"
    tdir.mkdir()
    (tdir / "__init__.py").write_text("")
    # conftest reaches the target ONLY through the declared plugin — imports nothing from pkg.mod.
    (tdir / "conftest.py").write_text('pytest_plugins = ["myplugin"]\n')
    # fixture-only test: names the target nowhere, uses only the fixture.
    (tdir / "test_via_plugin.py").write_text("def test_via_plugin(q):\n    assert q('x') == \"'x'\"\n")


def test_pytest_plugins_conftest_keeps_the_fixture_only_reacher(tmp_path):
    _repo(tmp_path)
    kept = reachable_test_paths(str(tmp_path), str(tmp_path / "pkg" / "mod.py"), "pkg.mod", (), ("tests",))
    names = {os.path.basename(p) for p in (kept or [])}
    # pytest itself collects and runs test_via_plugin (it resolves the plugin fixture); reachability
    # must not drop it, or the tests that DO pin the target are excluded and its kills are lost.
    assert "test_via_plugin.py" in names, "a pytest_plugins-only reacher must be kept, not dropped"


def test_a_plain_assignment_named_otherwise_does_not_force_opaque(tmp_path):
    # Guard the over-approximation: only `pytest_plugins` forces opaque, not any module-level list.
    (tmp_path / "pyproject.toml").write_text('[tool.pytest.ini_options]\ntestpaths = ["tests"]\n')
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("")
    (tmp_path / "pkg" / "mod.py").write_text("def quote(s):\n    return repr(s)\n")
    tdir = tmp_path / "tests"
    tdir.mkdir()
    (tdir / "__init__.py").write_text("")
    (tdir / "conftest.py").write_text('collect_ignore = ["nope.py"]\n')
    # A test that names the target nowhere and rides a conftest that does NOT reach it stays dropped.
    (tdir / "test_unrelated.py").write_text("def test_unrelated():\n    assert True\n")
    kept = reachable_test_paths(str(tmp_path), str(tmp_path / "pkg" / "mod.py"), "pkg.mod", (), ("tests",))
    names = {os.path.basename(p) for p in (kept or [])}
    assert "test_unrelated.py" not in names, "a non-pytest_plugins assignment must not force opaque"
