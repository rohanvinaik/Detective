"""The Fix B integration gate: target-first through a REAL pytest live session.

The unit oracles install session baselines by hand. This drives the whole path the way Detective
does — `run_with_live_suite` opens a real pytest session (fixtures, an autouse conftest,
parametrized node IDs, real collection), and `Detective.engine.profile` forks a per-function holder,
seeds the tests that name the target, and lazily widens. It asserts what the closeout review asked:

  * target-first ACTIVATES and its result (kill matrix + covered-line set) is byte-identical to a
    full-baseline run of the same function (`_WESKER_TARGET_FIRST` toggled off);
  * a SIBLING function profiled after the target is NOT corrupted by the target's seed — the
    reproduced `baseline seeded for alpha killed 0/3 of beta`, closed end to end.

Each live session runs in a FRESH subprocess: `run_with_live_suite` starts a pytest session, and
nesting that inside this very pytest run accumulates plugin/import state that breaks later sessions.
A subprocess per session is the clean way to test "a real pytest session". Skipped when the installed
Wesker predates the feature.
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

# One live session per invocation: argv = root, fn, mode. `fn == "sibling_shared"` profiles `target`
# FIRST (seeding it) then `sibling` on the same shared holder, and reports sibling — the corruption
# probe. Prints the comparable disposition as JSON on the last line.
_SESSION_SCRIPT = """
import sys, os, json
root, fn, mode = sys.argv[1], sys.argv[2], sys.argv[3]
from Wesker.ci import run_with_live_suite
import Detective.engine as deng
deng._WESKER_TARGET_FIRST = (mode == "on")
modpath = [os.path.join(root, "pkg", "mod.py")]
testsdir = [os.path.join(root, "tests")]
out = {}
def body():
    if fn == "sibling_shared":
        deng.profile("pkg/mod.py", "target", root, scope_tests=True, use_cache=False)
        out["r"] = deng.profile("pkg/mod.py", "sibling", root, scope_tests=True, use_cache=False)
    else:
        out["r"] = deng.profile("pkg/mod.py", fn, root, scope_tests=True, use_cache=False)
run_with_live_suite(root, body, target_files=modpath, paths=testsdir)
assert "r" in out, "the live session never ran the body"
r = out["r"]
print(json.dumps({
    "total_mutants": r.total_mutants,
    "total_killed": r.total_killed,
    "kill_matrix": {m: sorted(k) for m, k in r.kill_matrix.items()},
    "survivors": sorted(x.get("mutant_id") for x in r.survivor_records),
    "covered_lines": sorted({ln for lines in r.line_coverage.values() for ln in lines}),
}))
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
        "def sibling(flag):\n"
        "    if flag:\n"
        "        return 'a'\n"
        "    return 'b'\n"
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "conftest.py").write_text(
        "import pytest\n\n"
        "@pytest.fixture(autouse=True)\ndef _auto():\n    yield\n\n"
        "@pytest.fixture\ndef base():\n    return 0\n"
    )
    (tests / "test_target.py").write_text(
        "import pytest\nfrom pkg.mod import target\n\n"
        "@pytest.mark.parametrize('x,exp', [(3, 6), (-4, 4), (0, 0)])\n"
        "def test_target(x, exp, base):\n    assert target(x) == exp + base\n"
    )
    (tests / "test_sibling.py").write_text(
        "from pkg.mod import sibling\n\n"
        "def test_sib_true():\n    assert sibling(1) == 'a'\n\n"
        "def test_sib_false():\n    assert sibling(0) == 'b'\n"
    )
    (tests / "test_unrelated.py").write_text(
        "def test_u1():\n    assert 1 + 1 == 2\n\ndef test_u2():\n    assert 'x'.upper() == 'X'\n"
    )
    script = tmp_path / "_session_probe.py"
    script.write_text(_SESSION_SCRIPT)
    return str(tmp_path), str(script)


def _session(script, root, fn, mode):
    proc = subprocess.run(
        [sys.executable, script, root, fn, mode],
        capture_output=True,
        text=True,
        env=os.environ,  # inherits PYTHONPATH (local) or the venv (pinned Wesker under uv run)
        timeout=300,
    )
    assert proc.returncode == 0, f"session {fn}/{mode} failed:\n{proc.stdout}\n{proc.stderr}"
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_target_first_matches_full_in_a_real_session(tmp_path):
    root, script = _repo(tmp_path)
    tf = _session(script, root, "target", "on")
    full = _session(script, root, "target", "off")
    assert full["total_mutants"] > 0
    assert tf == full, "target-first through a live session diverged from the full baseline"


def test_a_sibling_profiled_after_the_target_is_not_corrupted(tmp_path):
    root, script = _repo(tmp_path)
    # `sibling` profiled right after `target` (which seeds first) vs `sibling` alone. Equal => the
    # fork isolated the holders; unequal => target's seed contaminated the sibling's baseline.
    shared = _session(script, root, "sibling_shared", "on")
    alone = _session(script, root, "sibling", "on")
    assert alone["total_killed"] > 0  # sibling has kills to lose to corruption
    assert shared == alone, "sibling corrupted by target's seed — the fork did not isolate the holders"
