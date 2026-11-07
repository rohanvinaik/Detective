"""pytest plugin for the output-mutation experiment (loaded with `-p omut_plugin`).

* Sets `omut.CURRENT_TEST` to the running test's node id, so recorded values are attributed per test.
* If OMUT_SELECT names a file of node ids, deselects every other collected test.
* Writes one JSON line per test to OMUT_RESULTS: its outcome, and for a failure, how it failed.

Failure classes (the two oracles of the paper's section 9.5):
  "assert" -- the test's own check rejected the result: an AssertionError raised from test code,
              pytest.fail / pytest.raises' DID NOT RAISE, or a doctest output mismatch;
  "crash"  -- anything else: an exception raised by library code (including an `assert` inside the
              library), an error in setup or teardown, or a per-test timeout.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import omut
import pytest

_SELECT = None
_OUT = None
_LIB_ROOT = os.environ.get("OMUT_LIB_ROOT", "")
_status: dict = {}


def pytest_collection_modifyitems(config, items):
    global _SELECT
    path = os.environ.get("OMUT_SELECT")
    if not path:
        return
    with open(path, encoding="utf-8") as fh:
        _SELECT = {ln.rstrip("\n") for ln in fh if ln.strip()}
    keep, drop = [], []
    for it in items:
        (keep if it.nodeid in _SELECT else drop).append(it)
    if drop:
        config.hook.pytest_deselected(items=drop)
    items[:] = keep


def _classify(call) -> str:
    exc = call.excinfo
    if exc is None:
        return "crash"  # failed without an exception (e.g. a strict XPASS): not a check on the value
    tname = exc.type.__name__
    if tname == "Failed" and str(exc.value).startswith("Timeout"):
        return "crash"  # pytest-timeout
    if tname in ("Failed", "DocTestFailure", "MultipleDoctestFailures"):
        return "assert"
    if issubclass(exc.type, AssertionError):
        try:
            last = str(exc.traceback[-1].path)
        except Exception:  # noqa: BLE001
            last = ""
        parts = Path(last).parts
        in_tests = any(part in ("tests", "test") for part in parts) or Path(last).name.startswith("test_")
        if _LIB_ROOT and last.startswith(_LIB_ROOT) and not in_tests:
            return "crash"  # an assert inside the library's own code, not the test's check
        return "assert"
    return "crash"


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    omut.CURRENT_TEST[0] = item.nodeid
    outcome = yield
    rep = outcome.get_result()
    st = _status.setdefault(item.nodeid, {"outcome": "pass", "how": None, "exc": None})
    if rep.skipped and st["outcome"] != "fail":
        st["outcome"] = "skip"
    elif rep.failed and st["outcome"] != "fail":
        how = _classify(call) if call.when == "call" else "crash"
        st.update(outcome="fail", how=how, exc=call.excinfo.typename if call.excinfo else None)
    elif rep.when == "call" and getattr(rep, "wasxfail", None) is not None and st["outcome"] == "pass":
        st["outcome"] = "xfail"


def pytest_runtest_setup(item):
    omut.CURRENT_TEST[0] = item.nodeid


def pytest_runtest_logfinish(nodeid, location):  # noqa: ARG001
    global _OUT
    path = os.environ.get("OMUT_RESULTS")
    if not path:
        return
    if _OUT is None:
        _OUT = open(path, "a", encoding="utf-8")  # noqa: SIM115
    st = _status.get(nodeid, {"outcome": "pass", "how": None, "exc": None})
    _OUT.write(json.dumps({"test": nodeid, **st}) + "\n")
    _OUT.flush()
