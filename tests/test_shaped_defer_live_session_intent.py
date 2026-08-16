"""shaped-defer end-to-end: a shape-hazardous widen reacher is DEFERRED by default, disclosed.

Usability (ARC dogfood): the converge/diagnose widen speculatively traces UNKNOWN-stratum reachers,
and a non-hermetic one (subprocess/thread/signal) forces the expensive isolation path — a 50s
live-game system test per widen step dominated a real converge and cut it at the deadline. This
drives the REAL target-first widen through a live pytest session (the same subprocess harness the
Fix B oracle uses — nesting a live session inside this pytest run corrupts later sessions).

A test that reaches ``target`` only through the production caller ``run_target`` routes as an UNKNOWN
widen reacher; a ``subprocess.run`` in its body makes it shape-hazardous. By DEFAULT ``profile``
defers it from the widen and records ``deferred_shaped`` in the routing census (the disclosure —
never a silent exclusion); ``include_shaped=True`` traces it and the disclosure disappears. A direct
hermetic test keeps ``target`` seeded so the run still activates target-first.
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
        "def target(x):\n"
        "    if x > 0:\n"
        "        return x * 2\n"
        "    return -x\n"
        "\n"
        "def run_target(x):\n"  # a production caller — a test of THIS routes target as caller_reaches
        "    return target(x)\n"
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    # A direct hermetic candidate keeps target seeded (target-first activates on a real candidate).
    (tests / "test_direct.py").write_text(
        "from pkg.mod import target\n\ndef test_target_direct():\n    assert target(3) == 6\n"
    )
    # A caller reacher (UNKNOWN widen stratum for target) that is SHAPE-HAZARDOUS: the subprocess in
    # its body makes collection stamp spawns_subprocess -> non-hermetic -> deferred from the widen.
    (tests / "test_caller.py").write_text(
        "import subprocess\n"
        "from pkg.mod import run_target\n\n"
        "def test_via_caller():\n"
        "    subprocess.run(['true'])\n"
        "    assert run_target(4) == 8\n"
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


def test_a_shaped_widen_reacher_is_deferred_and_disclosed_by_default(tmp_path):
    routing = _routing(_repo(tmp_path), include=False)
    # The subprocess test routed as an unknown reacher of target and is shape-hazardous, so it is
    # held out of the widen — and the count is DISCLOSED in the census, never silently dropped.
    assert routing.get("deferred_shaped", 0) >= 1, routing


def test_include_shaped_traces_the_shaped_reacher_and_drops_the_disclosure(tmp_path):
    routing = _routing(_repo(tmp_path), include=True)
    # With the opt-in, the shaped reacher re-enters the widen; nothing is deferred, so the disclosure
    # key is absent (it only appears when there is something to disclose).
    assert "deferred_shaped" not in routing, routing
