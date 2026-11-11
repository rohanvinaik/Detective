"""A measurement leaves the process as it found it (Detective #86, EP-H4).

The defect: a library-level ``profile()`` left its project's modules in ``sys.modules`` AND its root
on ``sys.path``. A later profile of a DIFFERENT project with a same-named module (``m``) then bound the
previous project's ``f`` and measured code it never wrote — alone the victim's two tests cover
``[2, 3]`` / ``[2, 4]`` and kill 10 of 13 mutants; after a predecessor the same tests covered ``[]``
and killed 0, and ``is_gateable`` still read True. ``tests/conftest.py`` snapshots and restores around
every TEST (the harness fix, ``5666523``); these tests make the PRODUCT clean up after itself, and so
assert the state inside the test body, before that fixture can help.

Determinism is the product: a measurement's result may not depend on what the process measured
before it. So the outermost ``profile`` restores ``sys.path`` and the project-root modules on every
exit path, and a nested one tears down nothing the outer still needs.
"""

from __future__ import annotations

import contextlib
import os
import sys

import pytest

from Detective import process_state
from Detective.engine import profile
from Detective.process_state import module_restoration, restoring_process_state

PRED_BODY = "def f(x):\n    return x + 100\n"
VICTIM_BODY = "def f(x):\n    if x > 0:\n        return x * 2\n    return -x\n"
PRED_TEST = "def test_f():\n    assert f(1) == 101\n"
VICTIM_TEST = "def test_pos():\n    assert f(3) == 6\n\n\ndef test_neg():\n    assert f(-2) == 2\n"
PYTEST_CFG = '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n'
SRC_CFG = '[tool.pytest.ini_options]\ntestpaths = ["tests"]\npythonpath = ["src"]\n'


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _project(root, shape, role):
    """A project of ``shape`` whose ``m`` is the predecessor's or the victim's code. Returns the
    target file relative to the root."""
    body, test = (PRED_BODY, PRED_TEST) if role == "pred" else (VICTIM_BODY, VICTIM_TEST)
    if shape == "flat":
        _write(root / "m.py", body)
        _write(root / "test_m.py", "from m import f\n\n\n" + test)
        return "m.py"
    if shape == "tests_dir":
        _write(root / "pyproject.toml", PYTEST_CFG)
        _write(root / "m.py", body)
        _write(root / "tests" / "test_m.py", "from m import f\n\n\n" + test)
        return "m.py"
    if shape == "package":
        _write(root / "pkg" / "__init__.py", "")
        _write(root / "pkg" / "m.py", body)
        _write(root / "test_m.py", "from pkg.m import f\n\n\n" + test)
        return "pkg/m.py"
    assert shape == "src"
    _write(root / "pyproject.toml", SRC_CFG)
    _write(root / "src" / "pkg" / "__init__.py", "")
    _write(root / "src" / "pkg" / "m.py", body)
    _write(root / "tests" / "test_m.py", "from pkg.m import f\n\n\n" + test)
    return "src/pkg/m.py"


def _measure(root, shape, role):
    rel = _project(root, shape, role)
    return profile(rel, "f", str(root), use_cache=False)


def _projection(r):
    """The victim's result, field by field — everything the measurement says, nothing about where."""
    return {
        "total": r.total_mutants,
        "killed": r.total_killed,
        "discovered": r.tests_discovered,
        "line_coverage": {k.split("::")[-1]: v for k, v in sorted(r.line_coverage.items())},
        "kill_matrix": {k: sorted(t.split("::")[-1] for t in v) for k, v in sorted(r.kill_matrix.items())},
        "executable": r.executable_lines,
        "basis": r.measurement_basis,
        "gateable": r.is_gateable,
    }


def _project_modules(root):
    real = os.path.realpath(root)
    names = set()
    for name, mod in list(sys.modules.items()):
        file = getattr(mod, "__file__", None)
        if isinstance(file, str) and os.path.realpath(file).startswith(real + os.sep):
            names.add(name)
    return names


SHAPES = ("flat", "tests_dir", "package", "src")


@contextlib.contextmanager
def _harness_snapshot():
    """pytester's snapshot/restore, local to the standard measurement, so that it never depends on the
    product behaviour under test."""
    modules, path = dict(sys.modules), list(sys.path)
    try:
        yield
    finally:
        sys.path[:] = path
        sys.modules.clear()
        sys.modules.update(modules)


def _alone_then_after(tmp_path, first, second):
    """The victim measured alone, then re-measured in the SAME directory after a predecessor.

    Same directory, because the tests fingerprint (``measurement_basis``) names the files it hashed:
    a different directory would differ for a reason that is not the contamination."""
    victim = tmp_path / "victim"
    with _harness_snapshot():  # the standard is measured on a clean process whatever the product does
        alone = _projection(_measure(victim, second, "victim"))
    assert alone["killed"] > 0 and alone["line_coverage"], "the standard must be a real measurement"
    _measure(tmp_path / "pred", first, "pred")
    return alone, _projection(_measure(victim, second, "victim"))


@pytest.mark.parametrize("first", SHAPES)
@pytest.mark.parametrize("second", SHAPES)
def test_a_victim_after_a_predecessor_equals_the_victim_alone(first, second, tmp_path):
    alone, after = _alone_then_after(tmp_path, first, second)
    assert after == alone


def test_the_issue_repro_pair_in_both_orders(tmp_path):
    alone, after = _alone_then_after(tmp_path / "one", "flat", "flat")
    assert after == alone
    # the other order: the predecessor's code is now the one measured second
    with _harness_snapshot():
        pred_alone = _projection(_measure(tmp_path / "two" / "pred", "flat", "pred"))
    _measure(tmp_path / "two" / "victim", "flat", "victim")
    assert _projection(_measure(tmp_path / "two" / "pred", "flat", "pred")) == pred_alone


@pytest.mark.parametrize("shape", SHAPES)
def test_after_profile_returns_sys_path_and_project_modules_equal_their_entry_values(shape, tmp_path):
    path_before, modules_before = list(sys.path), set(sys.modules)
    _measure(tmp_path, shape, "victim")
    assert sys.path == path_before
    assert _project_modules(tmp_path) == set()
    assert not [n for n in set(sys.modules) - modules_before if n.partition(".")[0] in {"m", "pkg", "test_m"}]


def test_a_symlinked_project_root_leaves_nothing_behind(tmp_path):
    real = tmp_path / "real"
    _project(real, "flat", "victim")
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    path_before = list(sys.path)
    profile("m.py", "f", str(link), use_cache=False)
    assert sys.path == path_before
    assert _project_modules(real) == set()
    assert _project_modules(link) == set()


def test_an_exception_inside_profile_still_restores(tmp_path, monkeypatch):
    import Detective.engine as engine

    _project(tmp_path, "flat", "victim")
    real_load = engine._load_original

    def load_then_fail(full, qualname):
        real_load(full, qualname)  # imports the project's m and puts paths where it likes
        sys.path.insert(0, str(tmp_path))
        raise RuntimeError("boom")

    monkeypatch.setattr(engine, "_load_original", load_then_fail)
    path_before = list(sys.path)
    with pytest.raises(RuntimeError, match="boom"):
        profile("m.py", "f", str(tmp_path), use_cache=False)
    assert sys.path == path_before
    assert _project_modules(tmp_path) == set()


def test_a_keyboard_interrupt_inside_profile_still_restores(tmp_path, monkeypatch):
    import Detective.engine as engine

    _project(tmp_path, "flat", "victim")
    real_load = engine._load_original

    def load_then_interrupt(full, qualname):
        real_load(full, qualname)
        raise KeyboardInterrupt

    monkeypatch.setattr(engine, "_load_original", load_then_interrupt)
    path_before = list(sys.path)
    with pytest.raises(KeyboardInterrupt):
        profile("m.py", "f", str(tmp_path), use_cache=False)
    assert sys.path == path_before
    assert _project_modules(tmp_path) == set()


def test_a_refused_lookup_restores_and_leaves_depth_zero(tmp_path):
    _project(tmp_path, "flat", "victim")
    path_before = list(sys.path)
    with pytest.raises(LookupError):
        profile("m.py", "no_such_function", str(tmp_path), use_cache=False)
    assert sys.path == path_before
    assert process_state._depth == 0


def test_a_suite_that_cannot_be_collected_still_restores(tmp_path):
    _project(tmp_path, "tests_dir", "victim")
    _write(tmp_path / "conftest.py", "import not_a_real_dependency_xyz  # noqa: F401\n")
    path_before = list(sys.path)
    profile("m.py", "f", str(tmp_path), use_cache=False)
    assert sys.path == path_before
    assert _project_modules(tmp_path) == set()


def test_a_conftest_and_generated_synth_modules_do_not_outlive_the_measurement(tmp_path):
    _project(tmp_path, "tests_dir", "victim")
    _write(tmp_path / "conftest.py", "FLAG = 1\n")
    _write(
        tmp_path / "tests" / "detective" / "m_f_synth.py",
        "from m import f\n\n\ndef test_synth():\n    assert f(5) == 10\n",
    )
    _write(tmp_path / "tests" / "detective" / "__init__.py", "")
    profile("m.py", "f", str(tmp_path), use_cache=False)
    assert _project_modules(tmp_path) == set()


def test_a_prior_conftest_of_the_caller_is_the_object_held_afterwards(tmp_path):
    held = sys.modules.get("conftest")  # the harness's own, if pytest imported it under this name
    _project(tmp_path, "tests_dir", "victim")
    _write(tmp_path / "conftest.py", "FLAG = 1\n")
    profile("m.py", "f", str(tmp_path), use_cache=False)
    assert sys.modules.get("conftest") is held


def test_the_callers_own_already_imported_project_survives_a_profile_of_it(tmp_path):
    _project(tmp_path, "package", "victim")
    sys.path.insert(0, str(tmp_path))
    try:
        import pkg.m

        held = sys.modules["pkg"], sys.modules["pkg.m"]
        profile("pkg/m.py", "f", str(tmp_path), use_cache=False)
        assert (sys.modules["pkg"], sys.modules["pkg.m"]) == held
        assert sys.path[0] == str(tmp_path)
        assert pkg.m.f(3) == 6
        import importlib

        assert importlib.import_module("pkg.m").f(-2) == 2
    finally:
        sys.path.remove(str(tmp_path))
        for name in ("pkg", "pkg.m"):
            sys.modules.pop(name, None)


def test_a_name_the_caller_already_holds_is_put_back_when_the_measurement_rebinds_it(tmp_path):
    caller, other = tmp_path / "caller", tmp_path / "other"
    _project(caller, "flat", "pred")
    sys.path.insert(0, str(caller))
    try:
        import m as callers_m

        assert callers_m.f(1) == 101
        _project(other, "flat", "victim")
        profile("m.py", "f", str(other), use_cache=False)
        assert sys.modules["m"] is callers_m
        assert sys.path[0] == str(caller)
        assert not any(p == str(other) for p in sys.path)
    finally:
        sys.path.remove(str(caller))
        sys.modules.pop("m", None)


# --- the context manager itself: nesting, namespaces, caches, duplicates ----------------------------


def _scratch_module(root, name="scratch_mod_86", body="X = 1\n"):
    _write(root / f"{name}.py", body)
    return name


def test_a_nested_entry_tears_down_nothing_the_outer_still_needs(tmp_path):
    name = _scratch_module(tmp_path)
    import importlib

    with restoring_process_state(str(tmp_path)):
        sys.path.insert(0, str(tmp_path))
        first = importlib.import_module(name)
        with restoring_process_state(str(tmp_path)):
            sys.path.insert(0, str(tmp_path))
        assert sys.modules[name] is first, "the inner exit must not evict what the outer holds"
        assert str(tmp_path) in sys.path
        assert importlib.import_module(name) is first, "and nothing is re-imported per pass"
    assert name not in sys.modules
    assert str(tmp_path) not in sys.path
    assert process_state._depth == 0


def test_profile_nested_in_an_outer_entry_does_not_restore_until_the_outer_exits(tmp_path):
    _project(tmp_path, "flat", "victim")
    with restoring_process_state(str(tmp_path)):
        profile("m.py", "f", str(tmp_path), use_cache=False)
        profile("m.py", "f", str(tmp_path), use_cache=False)
        assert "m" in sys.modules or "_detective_uut_m" in sys.modules or _project_modules(tmp_path)
    assert _project_modules(tmp_path) == set()


def test_a_namespace_package_with_no_file_is_evicted_by_its_path(tmp_path):
    import importlib

    _write(tmp_path / "ns86pkg" / "sub.py", "Y = 2\n")
    with restoring_process_state(str(tmp_path)):
        sys.path.insert(0, str(tmp_path))
        importlib.import_module("ns86pkg.sub")
        assert getattr(sys.modules["ns86pkg"], "__file__", None) is None
    assert "ns86pkg" not in sys.modules
    assert "ns86pkg.sub" not in sys.modules


def test_a_kept_parent_loses_its_attribute_for_an_evicted_child(tmp_path):
    import importlib

    _write(tmp_path / "pk86" / "__init__.py", "")
    _write(tmp_path / "pk86" / "kid.py", "Z = 3\n")
    sys.path.insert(0, str(tmp_path))
    try:
        parent = importlib.import_module("pk86")
        with restoring_process_state(str(tmp_path)):
            importlib.import_module("pk86.kid")
            assert hasattr(parent, "kid")
        assert sys.modules["pk86"] is parent
        assert "pk86.kid" not in sys.modules
        assert not hasattr(parent, "kid")
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("pk86", None)


def test_entries_already_on_sys_path_are_never_removed_even_duplicated(tmp_path):
    keep = str(tmp_path / "keep")
    os.makedirs(keep)
    sys.path.append(keep)
    try:
        before = list(sys.path)
        with restoring_process_state(str(tmp_path)):
            sys.path.insert(0, str(tmp_path))
            sys.path.insert(0, str(tmp_path))
            sys.path.append(keep)
            sys.path.remove(keep)
        assert sys.path == before
    finally:
        sys.path.remove(keep)


def test_an_entry_the_run_removed_is_put_back(tmp_path):
    keep = str(tmp_path / "gone")
    os.makedirs(keep)
    sys.path.insert(0, keep)
    try:
        before = list(sys.path)
        with restoring_process_state(str(tmp_path)):
            sys.path.remove(keep)
        assert sys.path == before
    finally:
        sys.path.remove(keep)


def test_a_project_module_dropped_or_rebound_during_the_run_is_restored(tmp_path):
    import importlib

    name = _scratch_module(tmp_path, "held86")
    sys.path.insert(0, str(tmp_path))
    try:
        held = importlib.import_module(name)
        with restoring_process_state(str(tmp_path)):
            del sys.modules[name]
        assert sys.modules[name] is held
        with restoring_process_state(str(tmp_path)):
            sys.modules[name] = importlib.util.module_from_spec(
                importlib.util.spec_from_file_location(name, tmp_path / f"{name}.py")
            )
        assert sys.modules[name] is held
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop(name, None)


def test_the_path_importer_cache_entries_the_run_added_are_pruned(tmp_path):
    import importlib

    name = _scratch_module(tmp_path)
    before = set(sys.path_importer_cache)
    with restoring_process_state(str(tmp_path)):
        sys.path.insert(0, str(tmp_path))
        importlib.import_module(name)
        assert str(tmp_path) in sys.path_importer_cache
    assert set(sys.path_importer_cache) == before


def test_exit_restores_on_exception_and_keyboard_interrupt_and_never_masks_them(tmp_path):
    for exc in (ValueError("x"), KeyboardInterrupt()):
        name = _scratch_module(tmp_path)
        import importlib

        before = list(sys.path)
        with pytest.raises(type(exc)):
            with restoring_process_state(str(tmp_path)):
                sys.path.insert(0, str(tmp_path))
                importlib.import_module(name)
                raise exc
        assert sys.path == before
        assert name not in sys.modules
        assert process_state._depth == 0


def test_a_module_from_a_path_entry_the_caller_already_had_inside_the_root_is_kept(tmp_path):
    # A venv or src dir the CALLER put on sys.path, living under the project root: its modules are
    # the caller's installed code, not the project the measurement imported.
    import importlib

    site = tmp_path / ".venv" / "site-packages"
    _write(site / "heavy86.py", "H = 1\n")
    sys.path.insert(0, str(site))
    try:
        with restoring_process_state(str(tmp_path)):
            sys.path.insert(0, str(tmp_path))
            importlib.import_module("heavy86")
        assert "heavy86" in sys.modules
        assert str(site) in sys.path
    finally:
        sys.path.remove(str(site))
        sys.modules.pop("heavy86", None)


# --- the pure decision --------------------------------------------------------------------------------

ROOT = "/p/proj"


def _codes(
    before=None, after=None, rebound=(), roots=(ROOT,), protected=(), reserved=("Detective", "Wesker")
):
    return module_restoration(
        before or {}, after or {}, list(rebound), list(roots), list(protected), list(reserved)
    )


def test_decision_a_new_project_module_is_evicted():
    assert _codes(after={"m": f"{ROOT}/m.py"}) == {"m": "evicted"}


def test_decision_a_new_module_outside_every_root_is_kept():
    assert _codes(after={"numpy": "/usr/lib/numpy/__init__.py"}) == {"numpy": "kept_foreign_origin"}


def test_decision_a_prefix_that_is_not_a_path_component_is_not_under_the_root():
    assert _codes(after={"m": "/p/proj2/m.py"}) == {"m": "kept_foreign_origin"}


def test_decision_no_origin_is_kept_not_guessed():
    assert _codes(after={"_frozen": ""}) == {"_frozen": "kept_no_origin"}


def test_decision_the_tools_own_package_is_kept_even_under_a_root():
    assert _codes(after={"Detective.x": f"{ROOT}/Detective/x.py"}) == {"Detective.x": "kept_reserved"}
    assert _codes(after={"Wesker": f"{ROOT}/Wesker/__init__.py"}) == {"Wesker": "kept_reserved"}


def test_decision_an_installed_tree_under_a_root_is_kept():
    sp = f"{ROOT}/.venv/lib/site-packages"
    assert _codes(after={"numpy": f"{sp}/numpy/__init__.py"}, protected=[sp]) == {"numpy": "kept_installed"}


def test_decision_a_rebound_project_name_is_restored_not_deleted():
    assert _codes(before={"m": "/q/m.py"}, after={"m": f"{ROOT}/m.py"}, rebound=["m"]) == {
        "m": "restored_rebound"
    }
    assert _codes(before={"m": f"{ROOT}/m.py"}, after={"m": "/q/m.py"}, rebound=["m"]) == {
        "m": "restored_rebound"
    }


def test_decision_a_rebound_name_that_is_nobodys_project_is_left_alone():
    assert _codes(before={"x": "/a/x.py"}, after={"x": "/b/x.py"}, rebound=["x"]) == {
        "x": "kept_foreign_rebound"
    }


def test_decision_a_present_unchanged_module_needs_nothing():
    assert _codes(before={"m": f"{ROOT}/m.py"}, after={"m": f"{ROOT}/m.py"}) == {"m": "unchanged"}


def test_decision_a_dropped_project_module_is_restored_a_dropped_foreign_one_is_not():
    assert _codes(before={"m": f"{ROOT}/m.py"}) == {"m": "restored_removed"}
    assert _codes(before={"z": "/elsewhere/z.py"}) == {"z": "kept_foreign_removed"}
    sp = f"{ROOT}/.venv/site-packages"
    assert _codes(before={"n": f"{sp}/n.py"}, protected=[sp]) == {"n": "kept_foreign_removed"}


def test_decision_empty_in_empty_out_and_any_root_matches():
    assert _codes() == {}
    assert _codes(after={"a": "/r2/a.py"}, roots=[ROOT, "/r2"]) == {"a": "evicted"}
    assert _codes(after={"a": "/r2/a.py"}, roots=[]) == {"a": "kept_foreign_origin"}
