"""Stale-snapshot detection (issue #17): a verdict over a file that changed
under the run must say so, everywhere a verdict speaks.

Field shape: a mid-run lint edit produced a clean-looking `0/26 killed` whose
line numbers pointed at moved lines. The measurement was incoherent — mutants
from the start-of-run parse, suite importing the edited module — and nothing
in the output said so. Now the result carries `stale_target`, the FINAL banner
stamps it, and a stale converge can never stand as a decomposition proof.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from Detective.cli import _final_banner
from Detective.converge import ConvergeResult, _target_changed, converge


def _project(tmp_path: Path) -> Path:
    (tmp_path / "calc.py").write_text(
        textwrap.dedent(
            """
            def add(a, b):
                return a + b
            """
        )
    )
    return tmp_path


def test_target_changed_is_two_hashes(tmp_path):
    target = _project(tmp_path) / "calc.py"
    import hashlib

    snapshot = hashlib.sha256(target.read_text().encode("utf-8")).hexdigest()
    assert not _target_changed(str(target), snapshot)
    target.write_text(target.read_text() + "# edited\n")
    assert _target_changed(str(target), snapshot)


def test_deleted_target_is_the_limit_case_of_edited(tmp_path):
    target = _project(tmp_path) / "calc.py"
    import hashlib

    snapshot = hashlib.sha256(target.read_text().encode("utf-8")).hexdigest()
    target.unlink()
    assert _target_changed(str(target), snapshot)


def test_mid_run_edit_stamps_the_verdict(tmp_path):
    root = _project(tmp_path)
    target = root / "calc.py"
    edited = False

    def edit_once(_msg: str) -> None:
        nonlocal edited
        if not edited:
            target.write_text(target.read_text() + "# mid-run edit\n")
            edited = True

    result = converge(
        "calc.py",
        "add",
        str(root),
        max_iterations=1,
        notify=edit_once,
    )
    assert edited, "the notify hook never fired — the test exercised nothing"
    assert result.stale_target
    banner = _final_banner(result)
    assert "STALE" in banner
    assert "re-run" in banner
    # STALE overrides every status wording — neither claim may appear.
    assert "COMPLETE" not in banner
    assert "Incomplete" not in banner


def test_unedited_run_is_not_stale(tmp_path):
    root = _project(tmp_path)
    result = converge("calc.py", "add", str(root), max_iterations=1)
    assert not result.stale_target
    assert "STALE" not in _final_banner(result)


def test_stale_result_serializes_the_flag():
    # The receipt field exists with an honest default, for JSON consumers.
    r = ConvergeResult(
        function="f",
        converged=True,
        at_ceiling=True,
        initial_survivors=0,
        final_survivors=0,
        iterations=(),
        written_path=None,
    )
    assert r.stale_target is False
