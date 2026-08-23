"""Cor. 10.6 intent — κ-gated `audit --remove` catches a CROSS-FILE bridge test.

`module_safe_removals` extends the safe-removal evidence set from file-siblings to the bounded
κ-neighborhood (the target's direct call-graph callers + callees, Def. 10.2). A test locally redundant for
the caller can be the SOLE killer of a callee's mutant in another module — a bridge — and deleting it
silently un-pins the callee. Detective's import-reachability discovery HIDES that bridge test when profiling
the callee (it imports the caller's module, not the callee's), so it is force-included via profile's
explicit ``tests=`` (the seam grounded 2026-08-23). These pin: a real cross-file bridge is RETAINED (mapped
to the callee); a genuinely redundant candidate is still removable (no over-retention).
"""

from __future__ import annotations

from Detective.audit import module_safe_removals

_HELPER = "def parse(s):\n    if not s:\n        raise ValueError('empty')\n    return s.strip()\n"
# ATTRIBUTE-ACCESS call (helper_mod.parse) so a callee mutant propagates to the caller via Wesker's
# module-qualified patch. (A from-import binds at import time and is immune — but then the callee mutant is
# unkillable via the caller anyway, so a from-import "bridge" is correctly not a mutation bridge.)
_MAIN = "import helper_mod\n\n\ndef run(s):\n    return helper_mod.parse(s)\n"
_TESTS = (
    "import pytest\n\n"
    "from main_mod import run\n\n\n"
    "def test_run():\n    assert run('hi') == 'hi'\n\n\n"
    "def test_run_dup():\n    assert run('hi') == 'hi'\n\n\n"
    "def test_run_empty():\n    with pytest.raises(ValueError):\n        run('')\n"
)
_PYPROJECT = '[tool.pytest.ini_options]\ntestpaths = ["."]\nmarkers = ["detective: generated"]\n'


def _repo(tmp_path):
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT)
    (tmp_path / "helper_mod.py").write_text(_HELPER)
    (tmp_path / "main_mod.py").write_text(_MAIN)
    # Uniquely named so the nested (in-process) neighbor profile cannot import-collide with the outer suite.
    (tmp_path / "test_cor106_repo.py").write_text(_TESTS)
    return str(tmp_path)


def _cid(root, name):
    return f"legacy:{root}/test_cor106_repo.py::{name}"


def test_cross_file_bridge_is_retained_via_the_callee(tmp_path):
    root = _repo(tmp_path)
    # test_run_empty is redundant for `run` (a pure wrapper) but the SOLE killer of parse's raise-guard,
    # which lives in helper_mod.py — a cross-file bridge the file-scoped guard would wrongly delete.
    safe, retained = module_safe_removals("main_mod.py", "run", root, [_cid(root, "test_run_empty")])
    assert safe == ()  # not removable
    assert retained.get(_cid(root, "test_run_empty")) == "parse"  # retained, needed by the callee


def test_a_genuinely_redundant_candidate_is_still_removable(tmp_path):
    root = _repo(tmp_path)
    # test_run_dup duplicates test_run — redundant for `run` AND `parse` (covers only the happy path), so no
    # neighbor needs it: the κ-neighborhood extension must not over-retain a real redundancy.
    safe, retained = module_safe_removals("main_mod.py", "run", root, [_cid(root, "test_run_dup")])
    assert safe == (_cid(root, "test_run_dup"),)
    assert not retained
