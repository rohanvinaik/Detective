"""Tests for the shadowed-target guard — Detective.engine.shadowed_target and its parts.

The guard answers ONE question: is the file under analysis the file Python imports under its own
name? It exists because "0 of 935 tests cover this" was a TRUE measurement of a target whose name
resolved to a different checkout entirely — an honest number that read as "untested" and sent the
next step off to write a suite against a copy nobody runs.

These use real trees on disk (`tmp_path`) and the real subprocess resolver: a guard that decides
whether every other command runs is not worth testing against a mock of the thing it guards.
"""

from __future__ import annotations

from Detective.engine import _resolve_origin, _suite_path, shadowed_target


def _pkg(root, name: str, module: str = "mod.py", body: str = "") -> None:
    """A real importable package `name` under `root`, containing `module`."""
    (root / name).mkdir(parents=True, exist_ok=True)
    (root / name / "__init__.py").write_text("")
    (root / name / module).write_text(body)


# ── shadowed_target ───────────────────────────────────────────────
def test_no_shadow_when_the_name_resolves_to_the_very_file_analysed(tmp_path):
    _pkg(tmp_path, "pkg")
    assert shadowed_target("pkg/mod.py", str(tmp_path)) is None


def test_no_shadow_when_nothing_resolves_the_name_at_all(tmp_path):
    # Not installed and not on the path — most of this author's repos. "Not installed" is not a
    # shadow, and claiming one would refuse every scripts-only tree.
    (tmp_path / "deep").mkdir()
    (tmp_path / "deep" / "thing.py").write_text("")
    assert shadowed_target("deep/thing.py", str(tmp_path)) is None


def test_shadow_when_the_name_resolves_to_a_DIFFERENT_file(tmp_path):
    # The ModelAtlas shape: the analysed tree and the imported tree are both real, and the
    # imported one wins. Nothing about the target file is wrong — it is simply not the one
    # the suite runs.
    other = tmp_path / "other"
    here = tmp_path / "here"
    here.mkdir()
    _pkg(other, "pkg")
    _pkg(here, "pkg")
    (here / "pyproject.toml").write_text('[tool.pytest.ini_options]\npythonpath = ["../other"]\n')
    shadow = shadowed_target("pkg/mod.py", str(here))
    assert shadow is not None
    assert shadow.module == "pkg.mod"
    assert shadow.target == str(here / "pkg" / "mod.py")
    assert shadow.imported == str((other / "pkg" / "mod.py").resolve())


def test_no_shadow_for_a_file_that_does_not_exist(tmp_path):
    assert shadowed_target("pkg/nope.py", str(tmp_path)) is None


def test_no_shadow_for_a_target_outside_the_root(tmp_path):
    # Its dotted name is not ours to derive, so no claim can be made either way.
    outside = tmp_path / "outside"
    _pkg(outside, "pkg")
    root = tmp_path / "root"
    root.mkdir()
    assert shadowed_target(str(outside / "pkg" / "mod.py"), str(root)) is None


def test_src_layout_that_points_at_ITSELF_is_not_shadowed(tmp_path):
    # The distinction that matters: a src-layout whose own `pythonpath` puts its tree first is
    # HEALTHY, even though `src/` is not part of the module name. Resolving the way this
    # process does — rather than the way the suite does — reported a shadow here.
    _pkg(tmp_path / "src", "pkg")
    (tmp_path / "pyproject.toml").write_text('[tool.pytest.ini_options]\npythonpath = ["src"]\n')
    assert shadowed_target("src/pkg/mod.py", str(tmp_path)) is None


def test_the_guard_never_imports_the_target(tmp_path):
    # A module-level side effect must not fire: this runs before EVERY command, and executing
    # someone's import-time code to decide whether to run is not a guard, it is a hazard.
    marker = tmp_path / "fired.txt"
    _pkg(tmp_path, "pkg", body=f"open({str(marker)!r}, 'w').write('x')\n")
    shadowed_target("pkg/mod.py", str(tmp_path))
    assert not marker.exists()


# ── _suite_path ───────────────────────────────────────────────────
def test_suite_path_is_EMPTY_without_a_conftest_or_a_pythonpath(tmp_path):
    # The suite gets NOTHING extra here, and saying otherwise is the whole defect: pytest puts
    # the rootdir on sys.path only for a ROOT conftest.py, so claiming it unconditionally hands
    # `shadowed_target` a path entry the suite does not have — and every shadow that entry would
    # hide becomes invisible to the guard built to find it.
    assert _suite_path(str(tmp_path)) == []


def test_suite_path_is_the_root_when_a_root_conftest_anchors_it(tmp_path):
    (tmp_path / "conftest.py").write_text("")
    assert _suite_path(str(tmp_path)) == [str(tmp_path)]


def test_suite_path_puts_pythonpath_BEFORE_the_root(tmp_path):
    # pytest inserts pythonpath at the FRONT. Listing root first resolves a src-layout to
    # whatever sits at the root and masks the shadow this exists to find.
    (tmp_path / "src").mkdir()
    (tmp_path / "conftest.py").write_text("")  # what puts the root on the path at all
    (tmp_path / "pyproject.toml").write_text('[tool.pytest.ini_options]\npythonpath = ["src"]\n')
    assert _suite_path(str(tmp_path)) == [str(tmp_path / "src"), str(tmp_path)]


def test_suite_path_drops_entries_that_are_not_directories(tmp_path):
    (tmp_path / "conftest.py").write_text("")
    (tmp_path / "pyproject.toml").write_text('[tool.pytest.ini_options]\npythonpath = ["nope"]\n')
    assert _suite_path(str(tmp_path)) == [str(tmp_path)]


def test_suite_path_survives_an_unparseable_pyproject(tmp_path):
    # A broken config must not break the guard — root is still the honest floor.
    (tmp_path / "conftest.py").write_text("")
    (tmp_path / "pyproject.toml").write_text("this is not toml {{{")
    assert _suite_path(str(tmp_path)) == [str(tmp_path)]


def test_suite_path_survives_a_pyproject_with_no_pytest_section(tmp_path):
    (tmp_path / "conftest.py").write_text("")
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
    assert _suite_path(str(tmp_path)) == [str(tmp_path)]


# ── _resolve_origin ───────────────────────────────────────────────
def test_resolve_origin_finds_a_module_on_the_given_path(tmp_path):
    _pkg(tmp_path, "pkg")
    origin = _resolve_origin("pkg.mod", str(tmp_path), [str(tmp_path)])
    assert origin == str(tmp_path / "pkg" / "mod.py")


def test_resolve_origin_is_none_for_a_name_nothing_provides(tmp_path):
    assert _resolve_origin("no_such_module_xyz", str(tmp_path), [str(tmp_path)]) is None


def test_resolve_origin_is_none_when_the_path_does_not_reach_it(tmp_path):
    # The same module, but the path does not include its directory: not found, not a shadow.
    _pkg(tmp_path, "pkg")
    empty = tmp_path / "empty"
    empty.mkdir()
    assert _resolve_origin("pkg.mod", str(empty), [str(empty)]) is None
