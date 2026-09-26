"""Every write of a file the USER owns is atomic (EP-A4, EP-A5 — docs/ENGINEERING_PASS_2026-09-26.md).

#63 made Detective's own durable stores replace-or-preserve. The writes that edit the USER's files
were still truncate-then-fill: `audit --remove` rewriting their test file, `regime --migrate` and the
marker registration rewriting their `pyproject.toml`, the generated suite itself, converge restoring a
prior suite, and `receipt -o`. A kill between the truncate and the fill — a Ctrl-C, the hang
watchdog's hard exit, a full disk — left a half-written test module or config. Pinned here from
intent: an interrupted rewrite leaves the user's file BYTE-IDENTICAL; and the one atomic writer syncs
its bytes to the device before the rename, as Wesker's trace-cache writer already did.
"""

from __future__ import annotations

import os
import textwrap
from unittest.mock import patch

import pytest

from Detective.atomic_store import atomic_write_text
from Detective.certify import ensure_marker_registered
from Detective.suite_edit import apply_removals


def _crash(_src, _dst):
    raise OSError("simulated crash mid-replace")


def _wrapper(name: str, origin: str):
    """A discovery-style wrapper tagged with the test file it came from (see test_suite_edit_native)."""

    def run() -> None:  # pragma: no cover — never called
        pass

    run.__name__ = name
    run.__wesker_origin__ = origin  # type: ignore[attr-defined]
    return run


def test_an_interrupted_audit_remove_leaves_the_users_test_file_whole(tmp_path, monkeypatch):
    (tmp_path / "m.py").write_text("def f(x):\n    return x + 1\n")
    test_file = tmp_path / "test_m.py"
    test_file.write_text(
        textwrap.dedent(
            """
            from m import f

            def test_a():
                assert f(1) == 2

            def test_b():
                assert f(0) == 1
            """
        )
    )
    before = test_file.read_bytes()
    discovered = [_wrapper("test_a", str(test_file))]
    monkeypatch.setattr(os, "replace", _crash)
    with (
        patch("Detective.suite_edit.discover_test_callables", return_value=discovered),
        pytest.raises(OSError),
    ):
        apply_removals("m.py", str(tmp_path), ["test_a"])
    assert test_file.read_bytes() == before
    assert not list(tmp_path.glob("*.tmp-*")), "no staging file is left beside the user's test"


def test_an_interrupted_marker_registration_leaves_the_users_config_whole(tmp_path, monkeypatch):
    config = tmp_path / "pyproject.toml"
    config.write_text('[project]\nname = "theirs"\n\n[tool.pytest.ini_options]\ntestpaths = ["tests"]\n')
    before = config.read_bytes()
    monkeypatch.setattr(os, "replace", _crash)
    assert ensure_marker_registered(str(tmp_path)) is None  # "nothing written", by its own contract
    assert config.read_bytes() == before


def test_the_one_atomic_writer_syncs_before_it_renames(tmp_path, monkeypatch):
    order: list[str] = []
    real_fsync, real_replace = os.fsync, os.replace
    monkeypatch.setattr(os, "fsync", lambda fd: (order.append("fsync"), real_fsync(fd))[1])
    monkeypatch.setattr(os, "replace", lambda a, b: (order.append("replace"), real_replace(a, b))[1])
    atomic_write_text(tmp_path / "store.json", '{"a": 1}')
    assert order == ["fsync", "replace"]
    assert (tmp_path / "store.json").read_text(encoding="utf-8") == '{"a": 1}'


def test_an_error_names_the_file_the_caller_asked_for_never_the_staging_file(tmp_path):
    """The staging file carries this process's pid; an error naming it differs on every run, so no caller
    or golden could rely on it. Found by a generated characterization of regime.apply_migration."""
    missing = tmp_path / "no_such_dir" / "store.json"
    with pytest.raises(FileNotFoundError) as info:
        atomic_write_text(missing, "x")
    assert info.value.filename == str(missing)
    assert ".tmp-" not in str(info.value)
