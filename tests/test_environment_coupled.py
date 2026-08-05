"""Environment-coupled golden refusal (issue #23).

Field shape: a golden capture of a no-arg loader pinned the CONTENTS of a
repo data file — green until the data legitimately changed, then a phantom
regression. The static purity gate missed it because the open() sat behind a
nested call, so the watch is a runtime audit hook. The capture is refused
with a typed note naming the touched path; a path derived from the call's own
arguments stays capturable — that is the function doing its job.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from Detective.converge import converge
from Detective.synthesis.characterization import _environment_paths


def test_environment_paths_filters_code_and_arg_derived():
    opened = [
        "/repo/data/exemplars.json",  # default-path data — the offender
        "/repo/src/module.py",  # code loading — not data
        "/repo/__pycache__/m.cpython-312.pyc",  # ditto
        "/inputs/given.txt",  # equals an argument — the function's job
        "/inputs/dir/child.csv",  # derived from an argument directory
    ]
    envs = _environment_paths(opened, args=("/inputs/given.txt", "/inputs/dir"), kwargs={})
    assert envs == ("/repo/data/exemplars.json",)


def test_default_path_io_golden_is_refused(tmp_path: Path):
    (tmp_path / "exemplars.txt").write_text("banked exemplar v1\n")
    (tmp_path / "library.py").write_text(
        textwrap.dedent(
            """
            import os

            _DATA = os.path.join(os.path.dirname(__file__), "exemplars.txt")


            def _read():
                with open(_DATA, encoding="utf-8") as fh:
                    return fh.read()


            def load():
                return _read().strip()
            """
        )
    )
    result = converge("library.py", "load", str(tmp_path), max_iterations=1)

    assert result.environment_coupled, "the default-path open was not detected"
    note = result.environment_coupled[0]
    assert "exemplars.txt" in note
    assert "refused" in note
    # No golden pinning the data file's contents may exist on disk.
    written = Path(result.written_path).read_text() if result.written_path else ""
    assert "banked exemplar v1" not in written
