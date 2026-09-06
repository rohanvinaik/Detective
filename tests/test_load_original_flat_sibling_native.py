"""Tests for Detective.engine._load_original — a flat (non-package) module that imports a SIBLING.

The flat-repo idiom: a top-level script (no ``__init__.py`` anywhere) whose module scope runs
``from arc_types import *`` / ``import sibling``. `_load_original`'s dotted-package branch is skipped
(there is no dotted name), so it falls to the bare path-load, which ``exec_module``s the file — and
that exec runs the sibling import. The module's OWN directory must therefore be importable, exactly
as CPython puts a directly-run script's dir on ``sys.path[0]`` and as the dotted branch places its
package root.

The regression this pins (surfaced dogfooding michaelhodel/arc-dsl, whose ``dsl.py`` opens with
``from arc_types import *``): without the directory on the path the exec raised ModuleNotFoundError,
``_load_original`` returned None, and every survivor was lost to "the live original could not be
loaded" — converge then scored 0/N and its action block advised ``regime --migrate``, which cannot
fix this: the pythonpath a migrate writes reaches the pytest session, NOT this loader. A flat
multi-file repo spiralled converge<->migrate forever.
"""

from __future__ import annotations

import importlib.util
import sys

from Detective.engine import _load_original

SIB_SRC = "VALUE = 42\n"
MOD_SRC = "from _flatrepo_sib import VALUE\n\n\ndef f():\n    return VALUE\n"


def _flat_repo(tmp_path):
    """A two-file flat repo: ``_flatrepo_mod.py`` imports a sibling ``_flatrepo_sib.py`` at module scope."""
    (tmp_path / "_flatrepo_sib.py").write_text(SIB_SRC)
    mod = tmp_path / "_flatrepo_mod.py"
    mod.write_text(MOD_SRC)
    return mod


def _cleanup(tmp_path):
    """Undo the loader's side effects so the sibling/UUT modules and path entry do not leak."""
    for name in ("_flatrepo_sib", "_flatrepo_mod", "_detective_uut__flatrepo_mod"):
        sys.modules.pop(name, None)
    p = str(tmp_path)
    while p in sys.path:
        sys.path.remove(p)


def test_bare_path_load_without_the_dir_cannot_resolve_the_sibling(tmp_path):
    """The trap itself: a plain spec-load of the module, with its dir off sys.path, dies on the sibling."""
    mod = _flat_repo(tmp_path)
    assert str(tmp_path) not in sys.path
    spec = importlib.util.spec_from_file_location("_flatrepo_probe", str(mod))
    loaded = importlib.util.module_from_spec(spec)
    try:
        raised = False
        try:
            spec.loader.exec_module(loaded)
        except ModuleNotFoundError:
            raised = True
        assert raised, "fixture is broken: the sibling import resolved without the dir on the path"
    finally:
        _cleanup(tmp_path)


def test_load_original_resolves_a_flat_sibling_import(tmp_path):
    """The fix: `_load_original` makes the module's own directory importable, so the sibling loads."""
    mod = _flat_repo(tmp_path)
    assert str(tmp_path) not in sys.path
    try:
        fn = _load_original(str(mod), "f")
        assert fn is not None, "the live original could not be loaded (flat sibling import regression)"
        assert fn() == 42
    finally:
        _cleanup(tmp_path)
