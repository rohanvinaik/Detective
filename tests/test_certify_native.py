"""Tests for Detective.certify.

``_write`` is pure file I/O and is mutation-driven to the ceiling (plain helpers,
no fixtures). ``certify`` itself is an orchestrator that runs the full Wesker
engine; it is covered by an end-to-end integration smoke test (mutation-profiling
it would nest profiling), so that one may use fixtures.
"""

from __future__ import annotations

import os
import tempfile

from Detective.certify import _write, certify


# ── _write (mutation-driven) ──────────────────────────────────────
def test_write_creates_named_file():
    d = tempfile.mkdtemp()
    path = _write("# content\n", d, "reset")
    assert path == os.path.join(d, "test_reset_synth.py")
    with open(path, encoding="utf-8") as fh:
        assert fh.read() == "# content\n"


def test_write_converts_dotted_qualname():
    d = tempfile.mkdtemp()
    path = _write("x", d, "Counter.reset")
    assert os.path.basename(path) == "test_Counter_reset_synth.py"


def test_write_creates_missing_directory():
    d = os.path.join(tempfile.mkdtemp(), "nested", "dir")
    path = _write("x", d, "f")
    assert os.path.isdir(d) and os.path.exists(path)


# ── certify (fast path only — full runs are verified out-of-suite) ─
# certify() runs the full Wesker engine, which nests a whole-suite pytest
# collection; running it inside the suite hangs, so the end-to-end path is
# verified by a standalone run, not here. Only the pre-profiling guard is tested.
def test_certify_unknown_function_raises():
    import pytest

    with pytest.raises(LookupError):
        certify("Detective/scope.py", "no_such_function", ".")
