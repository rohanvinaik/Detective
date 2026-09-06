"""shaped-defer end-to-end: a shape-hazardous CALLER-REACHING unknown is deferred from the widen and
disclosed; a shape-hazardous FILE-PEER is not consulted at all — and that is disclosed too.

Usability (ARC dogfood): the converge/diagnose widen — INCLUDING the witness pass, which re-profiles
internally — speculatively traces UNKNOWN-stratum tests to find distinguishers. A non-hermetic one
(subprocess/thread/signal) forces the expensive isolation path, and a 50s live-game system test
traced per widen step dominated a real converge (~488s over 13 slow unknowns) and cut it at the
deadline. This drives the REAL target-first widen through a live pytest session (the same subprocess
harness the Fix B oracle uses — nesting a live session inside this pytest run corrupts later ones).

Two shaped tests, two strata (founder ruling 2026-09-05, `engine.widen_admission`):

  * `test_slow_caller` names a same-module CALLER of the target (`pub`) — a `caller_reaches` unknown,
    the ONE stratum the widen still consults. By DEFAULT ``profile`` defers it for its shape and
    records ``deferred_shaped`` (the disclosure — never a silent exclusion); ``include_shaped=True``
    traces it and that disclosure disappears.
  * `test_slow_unrelated` never names the target or a caller; only its FILE does (a sibling test calls
    `mod.target`). That is a `file_peer` — no evidence THIS item reaches the target — so it is never
    widened, shaped or not: it is counted as ``not_consulted``, and no opt-in changes that.

Regression guard for the witness pass specifically: an earlier fix deferred converge's DIRECT profile
calls but MISSED ``classify_survivors``' internal re-profile (the witness pass), so the widen there
ran undeferred — the whole ~488s. This pins that the deferral reaches the unknown widen at all.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from Detective import engine as deng

pytestmark = pytest.mark.skipif(
    not getattr(deng, "_WESKER_TARGET_FIRST", False),
    reason="installed Wesker has no target-first seed/widen path",
)

_SCRIPT = """
import sys, os, json
root, include = sys.argv[1], sys.argv[2] == "include"
from Wesker.ci import run_with_live_suite
import Detective.engine as deng
out = {}
def body():
    out["r"] = deng.profile(
        "pkg/mod.py", "target", root, scope_tests=True, use_cache=False, include_shaped=include
    )
run_with_live_suite(
    root, body,
    target_files=[os.path.join(root, "pkg", "mod.py")],
    paths=[os.path.join(root, "tests")],
)
print(json.dumps({"test_routing": out["r"].test_routing}))
"""


def _repo(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\ntestpaths = ['tests']\nmarkers = ['detective: generated']\n"
    )
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text(
        "def target(x):\n    if x > 0:\n        return x * 2\n    return -x\n\n"
        "def pub(x):\n    return target(x)\n"
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_direct.py").write_text(
        "from pkg.mod import target\n\ndef test_target_direct():\n    assert target(3) == 6\n"
    )
    # `test_peer_reaches` names the target (a candidate). `test_slow_caller` is shape-hazardous and
    # names the same-module caller `pub` — a caller_reaches unknown, widened, therefore shaped-deferred.
    # `test_slow_unrelated` is shape-hazardous with NO path of its own — a file_peer, never consulted.
    (tests / "test_peer_slow.py").write_text(
        "import subprocess\n"
        "from pkg import mod\n\n"
        "def test_peer_reaches():\n    assert mod.target(1) == 2\n\n"
        "def test_slow_caller():\n"
        "    subprocess.run(['true'])\n"
        "    assert mod.pub(1) == 2\n\n"
        "def test_slow_unrelated():\n"
        "    subprocess.run(['true'])\n"
        "    assert 1 + 1 == 2\n"
    )
    return str(tmp_path)


def _routing(root, *, include):
    proc = subprocess.run(
        [sys.executable, "-c", _SCRIPT, root, "include" if include else "defer"],
        capture_output=True,
        text=True,
        env=os.environ,  # inherits PYTHONPATH (local repos) or the venv (pinned Wesker under uv run)
        timeout=300,
    )
    assert proc.returncode == 0, f"session failed:\n{proc.stderr}"
    return json.loads(proc.stdout.strip().splitlines()[-1])["test_routing"]


def test_a_shaped_unknown_is_deferred_from_the_widen_and_disclosed_by_default(tmp_path):
    routing = _routing(_repo(tmp_path), include=False)
    # Two unknowns: the shaped caller-reacher (widened stratum → held out for its shape, DISCLOSED) and
    # the shaped file-peer (no path of its own → not consulted, DISCLOSED). Neither is silently dropped.
    assert routing.get("unknown", 0) == 2, routing
    assert routing.get("deferred_shaped", 0) == 1, routing
    assert routing.get("not_consulted", 0) == 1, routing


def test_include_shaped_traces_the_shaped_unknown_and_drops_the_disclosure(tmp_path):
    routing = _routing(_repo(tmp_path), include=True)
    # With the opt-in, the shaped caller-reacher re-enters the widen; nothing is deferred, so that
    # disclosure key is absent (it only appears when there is something to disclose). The file-peer
    # stays not consulted — there is no opt-in for a test with no path of its own.
    assert routing.get("unknown", 0) == 2, routing
    assert "deferred_shaped" not in routing, routing
    assert routing.get("not_consulted", 0) == 1, routing
