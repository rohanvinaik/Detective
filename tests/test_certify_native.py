"""Tests for Detective.certify.

``_write`` is pure file I/O and is mutation-driven to the ceiling (plain helpers,
no fixtures). ``certify`` itself is an orchestrator that runs the full Wesker
engine; it is covered by an end-to-end integration smoke test (mutation-profiling
it would nest profiling), so that one may use fixtures.
"""

from __future__ import annotations

import os
import tempfile

from Detective.certify import (
    _CONFTEST_MARKER,
    _wiring_message,
    _write,
    certify,
    ensure_conftest,
)


# ── _wiring_message (mutation-driven — the exact CLI wording IS the product) ─
# The message is the idiot-proof surface a first-time user reads, so its full text
# is the contract: assert it verbatim (kills every VALUE mutant, incl. the prose).
_WIRED_TAIL = (
    "the generated tests import your module by name, which the `pytest` console "
    "script cannot resolve without the project root on sys.path"
)


def test_wiring_message_wired_and_verified_verbatim():
    msg = _wiring_message(conftest_wired="/proj/conftest.py", collects=True, passed=3)
    assert msg == (
        f"pytest wiring: wired /proj/conftest.py — {_WIRED_TAIL}; "
        "verified 3 test(s) pass under pytest"
    )


def test_wiring_message_conftest_already_present_verbatim():
    msg = _wiring_message(conftest_wired=None, collects=True, passed=2)
    assert msg == (
        "pytest wiring: conftest.py already present — imports resolve; "
        "verified 2 test(s) pass under pytest"
    )


def test_wiring_message_warns_when_tests_do_not_collect_verbatim():
    msg = _wiring_message(conftest_wired="/proj/conftest.py", collects=False, passed=0)
    assert msg == (
        f"pytest wiring: wired /proj/conftest.py — {_WIRED_TAIL}; "
        "⚠ pytest could NOT collect the generated tests — check the import path"
    )


# ── ensure_conftest (mutation-driven — pins the RETURN, not just that it runs) ─
def test_ensure_conftest_writes_and_returns_its_path():
    d = tempfile.mkdtemp()
    path = ensure_conftest(d)
    assert path == os.path.join(d, "conftest.py")
    assert os.path.exists(path)


def test_ensure_conftest_body_puts_root_on_sys_path():
    d = tempfile.mkdtemp()
    with open(ensure_conftest(d), encoding="utf-8") as fh:
        body = fh.read()
    assert _CONFTEST_MARKER in body
    assert "sys.path.insert(0, os.path.dirname(__file__))" in body


def test_ensure_conftest_returns_none_and_preserves_existing():
    d = tempfile.mkdtemp()
    existing = os.path.join(d, "conftest.py")
    with open(existing, "w", encoding="utf-8") as fh:
        fh.write("# the consumer's own conftest\n")
    assert ensure_conftest(d) is None  # never clobbers
    with open(existing, encoding="utf-8") as fh:
        assert fh.read() == "# the consumer's own conftest\n"


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
