"""Tests for Detective.engine._purge_stale_bytecode — measurements must describe the file on disk.

CPython validates a timestamp-based ``.pyc`` by source mtime truncated to WHOLE SECONDS
plus source size, so a same-second, same-size source replacement (scripted
edit-run-revert, git checkout) leaves a stale cache the import system serves as a hit.
The race is reproduced deterministically here by pinning the replacement's mtime to the
second the cache recorded.
"""

from __future__ import annotations

import importlib.util
import os
import py_compile
import sys

from Detective.engine import _load_original, _purge_stale_bytecode

SRC_A = "RATE = 1.20\n\n\ndef rate():\n    return RATE\n"
SRC_B = "RATE = 1.25\n\n\ndef rate():\n    return RATE\n"
assert len(SRC_A) == len(SRC_B), "the trap requires a same-size replacement"


def _poisoned_module(tmp_path):
    """A module whose on-disk source says 1.25 but whose ``.pyc`` still computes 1.20."""
    mod = tmp_path / "poisoned_rate_mod.py"
    mod.write_text(SRC_A)
    py_compile.compile(str(mod), doraise=True)  # cache records A's (mtime-second, size)
    recorded = os.stat(mod).st_mtime
    mod.write_text(SRC_B)
    os.utime(mod, (recorded, recorded))  # same second, same size: cache reads as valid
    return mod


def test_stale_cache_would_be_served_without_the_purge(tmp_path):
    """The trap itself: prove the poisoned state fools a plain source-file import."""
    mod = _poisoned_module(tmp_path)
    spec = importlib.util.spec_from_file_location("poisoned_probe", str(mod))
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    assert loaded.RATE == 1.20, "poisoned state did not reproduce; the fixture is broken"


def test_purge_then_import_compiles_the_file_on_disk(tmp_path):
    mod = _poisoned_module(tmp_path)
    _purge_stale_bytecode(str(mod))
    spec = importlib.util.spec_from_file_location("purged_probe", str(mod))
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    assert loaded.RATE == 1.25


def test_load_original_sees_the_file_on_disk(tmp_path):
    """The UUT loader must never hand Wesker a function from retired bytecode."""
    mod = _poisoned_module(tmp_path)
    fn = _load_original(str(mod), "rate")
    assert fn is not None
    assert fn() == 1.25


def test_purge_is_silent_when_no_cache_exists(tmp_path):
    mod = tmp_path / "never_imported.py"
    mod.write_text(SRC_A)
    _purge_stale_bytecode(str(mod))  # must not raise


def test_load_original_evicts_a_stale_live_module(tmp_path):
    """A long-lived process must not serve a module imported before the file changed.

    No bytecode cache is involved here: the first load parks the module in
    ``sys.modules``, the file then changes on disk, and the second load must
    notice the live object describes retired code — evict, reimport, remeasure.
    """
    mod = tmp_path / "long_lived_mod.py"
    mod.write_text(SRC_A)
    first = _load_original(str(mod), "rate")
    assert first is not None and first() == 1.20
    mod.write_text(SRC_B)
    second = _load_original(str(mod), "rate")
    assert second is not None and second() == 1.25


def test_load_original_reuses_a_fresh_live_module(tmp_path):
    """The staleness check must not tax the fast path: unchanged file, same object."""
    mod = tmp_path / "reused_mod.py"
    mod.write_text(SRC_A)
    first = _load_original(str(mod), "rate")
    second = _load_original(str(mod), "rate")
    assert second is first, "an unchanged module was needlessly reimported"


def test_load_original_heuristic_catches_a_body_edit_in_a_foreign_module(tmp_path):
    """A module imported by someone ELSE carries no stamp; body edits must still evict.

    (Global-only edits are honestly invisible on this tier — the stamp tier above
    covers every module Detective itself imported.)
    """
    mod = tmp_path / "foreign_mod.py"
    mod.write_text(SRC_A)
    spec = importlib.util.spec_from_file_location("foreign_mod", str(mod))
    foreign = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(foreign)
    sys.modules["foreign_mod"] = foreign  # pytest-style: imported outside Detective
    try:
        mod.write_text("RATE = 1.20\n\n\ndef rate():\n    return -RATE\n")
        fn = _load_original(str(mod), "rate")
        assert fn is not None and fn() == -1.20
    finally:
        sys.modules.pop("foreign_mod", None)
