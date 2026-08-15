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
    elif fn == "sibling_after_widen":
        deng.profile("pkg/mod.py", "gappy", root, scope_tests=True, use_cache=False)
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
    "test_routing": r.test_routing,
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
        "\n"
        "def gappy(x):\n"
        "    if x > 0:\n"
        "        return 1\n"
        "    return 0\n"
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
    (tests / "test_gappy.py").write_text(
        "from pkg.mod import gappy\n\ndef test_gappy_true():\n    assert gappy(1) == 1\n"
    )
    script = tmp_path / "_session_probe.py"
    script.write_text(_SESSION_SCRIPT)
    return str(tmp_path), str(script)


def _caller_repo(tmp_path):
    """A repo where `_priv` is tested ONLY through its public caller `pub` (which calls it) — the #15
    B empty-seed case: `_priv` has no direct-naming test, so its candidates are EMPTY and target-first
    must still activate off the caller slice (seed([]) + widen the caller-reaching tests)."""
    (tmp_path / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\ntestpaths = ['tests']\nmarkers = ['detective: generated']\n"
    )
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text(
        "def _priv(x):\n"
        "    if x > 0:\n"
        "        return x + 100\n"
        "    return x - 100\n"
        "\n"
        "def pub(x):\n"
        "    return _priv(x) * 2\n"
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_pub.py").write_text(
        "from pkg.mod import pub\n\n"
        "def test_pub_pos():\n    assert pub(3) == 206\n\n"
        "def test_pub_neg():\n    assert pub(-3) == -206\n"
    )
    (tests / "test_unrelated.py").write_text("def test_u():\n    assert 1 + 1 == 2\n")
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
    routing = tf.pop("test_routing")
    full.pop("test_routing")
    assert routing == {"candidate": 3, "unknown": 5, "impossible": 0, "observed": 0}
    assert full["total_mutants"] > 0
    assert tf == full, "target-first through a live session diverged from the full baseline"


def test_a_sibling_profiled_after_the_target_is_not_corrupted(tmp_path):
    root, script = _repo(tmp_path)
    # `sibling` profiled right after `target` (which seeds first) vs `sibling` alone. Equal => the
    # fork isolated the holders; unequal => target's seed contaminated the sibling's baseline.
    shared = _session(script, root, "sibling_shared", "on")
    alone = _session(script, root, "sibling", "on")
    shared.pop("test_routing")
    alone.pop("test_routing")
    assert alone["total_killed"] > 0  # sibling has kills to lose to corruption
    assert shared == alone, "sibling corrupted by target's seed — the fork did not isolate the holders"


def test_a_caller_only_target_activates_off_the_caller_slice(tmp_path):
    """#15 B empty-seed: `_priv` is tested only through `pub` (which calls it), so it has ZERO direct
    candidates — its `pub` tests are caller-reaching UNKNOWNS. Target-first must ACTIVATE anyway
    (seed([]) then widen the caller tests) and match the full baseline; the old `_cands and ...` guard
    sent every caller-only target to the full baseline instead. The disposition is identical either
    way (a perf bug, not a correctness one), so the census proves the caller-only shape and this gate
    proves the empty-seed live path runs correctly end to end."""
    root, script = _caller_repo(tmp_path)
    tf = _session(script, root, "_priv", "on")
    full = _session(script, root, "_priv", "off")
    routing = tf.pop("test_routing")
    full.pop("test_routing")
    assert routing["candidate"] == 0, "a caller-only target must have no direct candidate"
    assert routing["unknown"] >= 2, "the public caller's tests must route as (caller-reaching) unknowns"
    assert full["total_mutants"] > 0
    assert tf == full, "caller-only target-first (empty seed + caller widen) diverged from the full baseline"


def test_a_full_widen_becomes_observed_routing_for_the_next_function(tmp_path):
    """Fresh file-wide reach from one gap routes a sibling; the sibling proves only its fresh seed.

    POSITIVE-ONLY (X1/G1): the prior widen's REACHING cells route this sibling's two candidates, but a
    cached non-reach is no longer replayed as an exclusion — `test_fingerprint` cannot certify a test's
    imported-helper closure is unchanged, so a stale negative could exclude a now-reaching test (a
    false COMPLETE). The six former `impossible_observed` tests are therefore UNKNOWN now — re-traced
    fresh — not excluded: `observed` counts only the two positives, `impossible` is 0, `unknown` is 6.
    """
    root, script = _repo(tmp_path)
    sibling = _session(script, root, "sibling_after_widen", "on")
    assert sibling["test_routing"] == {
        "candidate": 2,
        "unknown": 6,
        "impossible": 0,
        "observed": 2,
    }
