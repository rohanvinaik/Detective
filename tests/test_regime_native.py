"""Tests for Detective.regime — the stage that answers "how does this repo run its tests?".

Real trees on disk (`tmp_path`). The whole point of this module is that it reports what a repo
ACTUALLY does, so a test that mocks the filesystem would test the mock.
"""

from __future__ import annotations

from Detective.regime import TestRegime, apply_migration, plan_migration, resolve_regime


def _pkg(root, *parts: str) -> None:
    d = root.joinpath(*parts)
    d.mkdir(parents=True, exist_ok=True)
    (d / "__init__.py").write_text("")
    (d / "mod.py").write_text("def f():\n    return 1\n")


def _cfg(root, body: str) -> None:
    (root / "pyproject.toml").write_text(body)


# ── layout ────────────────────────────────────────────────────────
def test_src_layout_is_recognised(tmp_path):
    _pkg(tmp_path, "src", "pkg")
    assert resolve_regime(str(tmp_path)).layout == "src"


def test_flat_layout_is_recognised(tmp_path):
    _pkg(tmp_path, "pkg")
    assert resolve_regime(str(tmp_path)).layout == "flat"


def test_a_bare_src_dir_without_a_package_is_not_a_src_layout(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "loose.py").write_text("")
    assert resolve_regime(str(tmp_path)).layout == "scripts"


def test_scripts_only_layout(tmp_path):
    (tmp_path / "run.py").write_text("")
    assert resolve_regime(str(tmp_path)).layout == "scripts"


# ── the target's importable name ──────────────────────────────────
def test_the_module_is_the_name_the_repo_types_not_the_path(tmp_path):
    # `src/` is a source root, not a package — the bug this whole module exists to end.
    _pkg(tmp_path, "src", "pkg")
    assert resolve_regime(str(tmp_path), "src/pkg/mod.py").module == "pkg.mod"


def test_no_target_still_resolves_the_repo_level_facts(tmp_path):
    # `detective regime` with no target must work: the repo facts are the point.
    _pkg(tmp_path, "src", "pkg")
    regime = resolve_regime(str(tmp_path))
    assert regime.module is None and regime.target is None
    assert regime.layout == "src"


def test_a_target_outside_the_root_gets_no_module(tmp_path):
    _pkg(tmp_path, "outside", "pkg")
    root = tmp_path / "root"
    root.mkdir()
    regime = resolve_regime(str(root), str(tmp_path / "outside" / "pkg" / "mod.py"))
    assert regime.module is None


def test_a_target_that_does_not_exist_gets_no_module(tmp_path):
    assert resolve_regime(str(tmp_path), "nope.py").module is None


# ── suite path ────────────────────────────────────────────────────
def test_suite_path_reflects_the_repos_own_pythonpath(tmp_path):
    _pkg(tmp_path, "src", "pkg")
    (tmp_path / "conftest.py").write_text("")  # the root is on the suite's path only via this
    _cfg(tmp_path, '[tool.pytest.ini_options]\npythonpath = ["src"]\n')
    assert resolve_regime(str(tmp_path)).suite_path == (str(tmp_path / "src"), str(tmp_path))


# ── conftest topology ─────────────────────────────────────────────
def test_two_conftests_in_non_package_dirs_collide(tmp_path):
    # Both are the module `conftest`; the second import in one process raises `import file
    # mismatch`, which kills the live session and silently drops fixture-taking tests.
    (tmp_path / "conftest.py").write_text("")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "conftest.py").write_text("")
    regime = resolve_regime(str(tmp_path))
    assert set(regime.colliding_conftests) == {"conftest.py", "tests/conftest.py"}
    assert regime.conflicts == ("conftest-collision",)


def test_a_package_dir_gives_its_conftest_a_distinct_name(tmp_path):
    # `tests/__init__.py` makes it `tests.conftest` — a different module, so no collision.
    (tmp_path / "conftest.py").write_text("")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "__init__.py").write_text("")
    (tmp_path / "tests" / "conftest.py").write_text("")
    regime = resolve_regime(str(tmp_path))
    assert regime.colliding_conftests == ()
    assert regime.conflicts == ()


def test_one_conftest_alone_never_collides(tmp_path):
    (tmp_path / "conftest.py").write_text("")
    assert resolve_regime(str(tmp_path)).colliding_conftests == ()


def test_conftests_pytest_never_loads_are_not_counted(tmp_path):
    # A `mutants/` shadow tree is full of conftests the project's own norecursedirs prunes.
    # Counting them would invent a conflict in a repo that has none.
    (tmp_path / "conftest.py").write_text("")
    (tmp_path / "mutants").mkdir()
    (tmp_path / "mutants" / "conftest.py").write_text("")
    _cfg(tmp_path, '[tool.pytest.ini_options]\nnorecursedirs = ["mutants"]\n')
    regime = resolve_regime(str(tmp_path))
    assert "mutants/conftest.py" not in regime.conftests
    assert regime.conflicts == ()


def test_detectives_own_conftest_is_identified_as_ours(tmp_path):
    # Decides the refusal: if one of a colliding pair is OURS, the fix is exact (delete it).
    # If neither is, the safe alternative is not safe, so we must not guess.
    (tmp_path / "conftest.py").write_text("# Auto-generated by Detective: makes the root importable.\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "conftest.py").write_text('"""The consumer\'s own."""\n')
    regime = resolve_regime(str(tmp_path))
    assert regime.generated_conftests == ("conftest.py",)


def test_a_consumers_conftest_is_never_claimed_as_ours(tmp_path):
    (tmp_path / "conftest.py").write_text("# my own conftest\n")
    assert resolve_regime(str(tmp_path)).generated_conftests == ()


# ── marker ────────────────────────────────────────────────────────
def test_marker_declared_is_read_from_pyproject(tmp_path):
    _cfg(tmp_path, '[tool.pytest.ini_options]\nmarkers = ["detective: test generated by Detective"]\n')
    assert resolve_regime(str(tmp_path)).marker_declared is True


def test_marker_not_declared_when_absent(tmp_path):
    _cfg(tmp_path, '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n')
    assert resolve_regime(str(tmp_path)).marker_declared is False


def test_an_unrelated_marker_does_not_count_as_ours(tmp_path):
    _cfg(tmp_path, '[tool.pytest.ini_options]\nmarkers = ["slow: takes a while"]\n')
    assert resolve_regime(str(tmp_path)).marker_declared is False


# ── conflicts ─────────────────────────────────────────────────────
def test_a_clean_repo_has_no_conflicts(tmp_path):
    _pkg(tmp_path, "src", "pkg")
    _cfg(tmp_path, '[tool.pytest.ini_options]\npythonpath = ["src"]\n')
    assert resolve_regime(str(tmp_path), "src/pkg/mod.py").conflicts == ()


def test_conflicts_is_empty_not_none_so_callers_can_just_test_it(tmp_path):
    assert resolve_regime(str(tmp_path)).conflicts == ()


def test_a_shadowed_target_is_a_conflict(tmp_path):
    regime = TestRegime(
        root="/r",
        layout="src",
        suite_path=(),
        testpaths=(),
        pythonpath=(),
        marker_declared=False,
        has_config=False,
        conftests=(),
        colliding_conftests=(),
        shadow=object(),  # type: ignore[arg-type] — presence is what `conflicts` reads
    )
    assert regime.conflicts == ("shadowed-target",)


def test_both_conflicts_are_reported_together(tmp_path):
    regime = TestRegime(
        root="/r",
        layout="src",
        suite_path=(),
        testpaths=(),
        pythonpath=(),
        marker_declared=False,
        has_config=False,
        conftests=("conftest.py", "tests/conftest.py"),
        colliding_conftests=("conftest.py", "tests/conftest.py"),
        shadow=object(),  # type: ignore[arg-type]
    )
    assert regime.conflicts == ("shadowed-target", "conftest-collision")


# ── it reads; it never writes ─────────────────────────────────────
def test_resolving_a_regime_changes_nothing_on_disk(tmp_path):
    # Every command runs this first. A read-only stage that writes is a stage that edits repos
    # nobody asked it to touch.
    _pkg(tmp_path, "src", "pkg")
    _cfg(tmp_path, '[tool.pytest.ini_options]\npythonpath = ["src"]\n')
    before = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*"))
    resolve_regime(str(tmp_path), "src/pkg/mod.py")
    after = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*"))
    assert before == after


# ── plan_migration / apply_migration (the write half) ─────────────
def _migrate(root) -> tuple[object, tuple[str, ...]]:
    plan = plan_migration(resolve_regime(str(root)))
    return plan, apply_migration(plan)


def test_a_scripts_repo_gets_pythonpath_so_the_console_script_can_import_it(tmp_path):
    # THE regression that made this necessary. pytest does NOT put the rootdir on sys.path — it
    # inserts the TEST file's directory — so a repo whose code lives at the root and is imported
    # bare only ever worked via `python -m pytest` (which adds cwd) or a conftest doing the
    # insert. Measured after removing that conftest: `pytest tests/` ->
    # `ModuleNotFoundError: No module named 'scorer'`. `pythonpath = ["."]` is the exact
    # declarative equivalent, and it holds for EVERY invocation.
    (tmp_path / "scorer.py").write_text("def score():\n    return 1\n")
    plan, done = _migrate(tmp_path)
    assert plan.declare_pythonpath is True
    assert resolve_regime(str(tmp_path)).pythonpath == (".",)
    assert any("pythonpath" in d for d in done)


def test_an_installed_package_layout_does_not_get_a_spurious_pythonpath(tmp_path):
    # A flat/src layout resolves through its install; declaring a path it does not need is noise
    # in someone else's config.
    _pkg(tmp_path, "pkg")
    plan, _ = _migrate(tmp_path)
    assert plan.declare_pythonpath is False


def test_our_conftest_is_removed_only_after_its_job_is_declared(tmp_path):
    # The conftest did TWO things (marker + sys.path insert). Removing it without replacing BOTH
    # breaks the repo — so the replacements are written first, and the file goes last.
    (tmp_path / "scorer.py").write_text("")
    (tmp_path / "conftest.py").write_text("# Auto-generated by Detective: makes the root importable.\n")
    plan, done = _migrate(tmp_path)
    assert plan.remove_conftests == ("conftest.py",)
    assert not (tmp_path / "conftest.py").exists()
    order = [i for i, d in enumerate(done)]
    assert done[order[-1]].startswith("removed conftest.py")  # last, after both declarations
    after = resolve_regime(str(tmp_path))
    assert after.marker_declared and after.pythonpath == (".",)


def test_a_conftest_we_did_not_write_is_never_removed(tmp_path):
    (tmp_path / "conftest.py").write_text("# my own conftest\n")
    plan, _ = _migrate(tmp_path)
    assert plan.remove_conftests == ()
    assert (tmp_path / "conftest.py").exists()


def test_an_existing_pytest_config_keeps_every_setting_it_had(tmp_path):
    _pkg(tmp_path, "pkg")
    _cfg(tmp_path, '[tool.pytest.ini_options]\ntestpaths = ["tests"]\naddopts = "-q"\n')
    _migrate(tmp_path)
    body = (tmp_path / "pyproject.toml").read_text()
    assert 'testpaths = ["tests"]' in body and 'addopts = "-q"' in body
    assert resolve_regime(str(tmp_path)).marker_declared


def test_a_declared_pythonpath_is_never_rewritten(tmp_path):
    # The repo already made this decision. Ours is to add what is missing, not to relitigate.
    (tmp_path / "scorer.py").write_text("")
    (tmp_path / "src").mkdir()
    _cfg(tmp_path, '[tool.pytest.ini_options]\npythonpath = ["src"]\n')
    _migrate(tmp_path)
    assert resolve_regime(str(tmp_path)).pythonpath == ("src",)


def test_migration_is_idempotent(tmp_path):
    (tmp_path / "scorer.py").write_text("")
    _migrate(tmp_path)
    once = (tmp_path / "pyproject.toml").read_text()
    plan, done = _migrate(tmp_path)
    assert plan.needed is False
    assert done == ()
    assert (tmp_path / "pyproject.toml").read_text() == once


def test_a_clean_repo_needs_no_migration(tmp_path):
    _pkg(tmp_path, "pkg")
    _cfg(tmp_path, '[tool.pytest.ini_options]\nmarkers = ["detective: test generated by Detective"]\n')
    assert plan_migration(resolve_regime(str(tmp_path))).needed is False


def test_a_shadow_is_reported_as_blocked_not_silently_tidied(tmp_path):
    # Migration must never make a repo LOOK healthier without making a verdict truer. A shadowed
    # target needs an install decision no config rewrite can make.
    regime = TestRegime(
        root=str(tmp_path),
        layout="src",
        suite_path=(),
        testpaths=(),
        pythonpath=(),
        marker_declared=False,
        has_config=False,
        conftests=(),
        colliding_conftests=(),
        shadow=type("S", (), {"module": "pkg.mod", "imported": "/elsewhere/pkg/mod.py"})(),
    )
    plan = plan_migration(regime)
    assert len(plan.blocked) == 1
    assert "pkg.mod" in plan.blocked[0] and "/elsewhere/pkg/mod.py" in plan.blocked[0]


def test_two_conftests_of_YOURS_are_blocked_not_guessed_at(tmp_path):
    (tmp_path / "conftest.py").write_text("# mine\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "conftest.py").write_text("# also mine\n")
    plan = plan_migration(resolve_regime(str(tmp_path)))
    assert any("neither is ours" in b for b in plan.blocked)
    assert plan.remove_conftests == ()
