"""Intent: the tests the engine may RUN for one function are the tests routing CONSULTED — never the
collection.

The defect (measured 2026-09-27, `docs/ENGINEERING_PASS_2026-09-26.md` §7). Target-first seeds the traced
baseline with the candidates and discloses every no-path test as `not_consulted` (founder ruling
2026-09-05: such a test is never traced or run for that function). But `profile` handed the engine the
whole collection minus the proof-grade impossibles as its POOL, and the engine RUNS its whole pool
wherever it cannot scope a mutant to covering tests — a mutant off the body's lines, such as one in a
parameter annotation on the `def` line. Converging `Wesker/monitoring.py::step_budget_verdict` from
Wesker's repo, one annotation mutant (`cap: int | None` → `int & None`, inert under
`from __future__ import annotations`, so no candidate can kill it) ran 694 tests of which two were
traced; one of the other 692 runs the engine inside the engine, deadlocked on its execution lock, and
orphaned it — every later run of that converge was refused. The two-sign return-type harvest had the
same leak, and ran the whole collection even for a leaf orphan with no reacher at all.

Pinned here, through a REAL pytest live session (a fresh subprocess per session, as the target-first
integration gate does): a no-path test that counts its own executions is never executed — not by an
unscoped mutant's fallback, and not by the two-sign harvest of a leaf orphan. The direction of the
trade stays the ruling's: a missed dynamic reacher costs a redundant generated test, never a
certificate (`test_target_first_live_session_intent.py` states it).
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

# argv = root, function, "two_sign" | "one_sign". Prints the comparable facts as JSON on the last line;
# `ran` is how many times the no-path test executed during the profile.
_SESSION_SCRIPT = """
import sys, os, json
root, fn, two_sign = sys.argv[1], sys.argv[2], sys.argv[3] == "two_sign"
from Wesker.ci import run_with_live_suite
import Detective.engine as deng
out = {}
def body():
    out["r"] = deng.profile(
        "pkg/mod.py", fn, root, scope_tests=True, use_cache=False, two_sign=two_sign
    )
run_with_live_suite(
    root, body, target_files=[os.path.join(root, "pkg", "mod.py")], paths=[os.path.join(root, "tests")]
)
assert "r" in out, "the live session never ran the body"
import pkg
r = out["r"]
print(json.dumps({
    "ran": len(pkg.RAN),
    "total_mutants": r.total_mutants,
    "survivors": sorted(x.get("mutant_id") for x in r.survivor_records),
    "test_routing": r.test_routing,
}))
"""


def _repo(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\ntestpaths = ['tests']\nmarkers = ['detective: generated']\n"
    )
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("RAN = []\n")
    # `target`'s annotation holds the one mutation site no candidate can reach: the `|` on the `def`
    # line. The future import keeps it a string on every supported interpreter, so the mutant is built
    # and survives, exactly as in the measured converge. `orphan` has no test and no caller.
    (pkg / "mod.py").write_text(
        "from __future__ import annotations\n"
        "\n"
        "\n"
        "def target(x: int | None) -> int:\n"
        "    if x is None:\n"
        "        return 0\n"
        "    return x * 2\n"
        "\n"
        "\n"
        "def orphan(x):\n"
        "    return x + 1\n"
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_target.py").write_text(
        "from pkg.mod import target\n\n"
        "def test_none():\n    assert target(None) == 0\n\n"
        "def test_double():\n    assert target(3) == 6\n"
    )
    # No static path to either function: routed `not_consulted`, and it records every execution.
    (tests / "test_unrelated.py").write_text("import pkg\n\ndef test_u():\n    pkg.RAN.append('test_u')\n")
    script = tmp_path / "_session_probe.py"
    script.write_text(_SESSION_SCRIPT)
    return str(tmp_path), str(script)


def _session(script, root, fn, sign):
    proc = subprocess.run(
        [sys.executable, script, root, fn, sign],
        capture_output=True,
        text=True,
        env=os.environ,  # inherits PYTHONPATH (local) or the venv (pinned Wesker under uv run)
        timeout=300,
    )
    assert proc.returncode == 0, f"session {fn}/{sign} failed:\n{proc.stdout}\n{proc.stderr}"
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_an_unscoped_mutant_never_runs_a_not_consulted_test(tmp_path):
    root, script = _repo(tmp_path)
    out = _session(script, root, "target", "one_sign")
    assert out["test_routing"]["not_consulted"] == 1  # `test_u`, disclosed
    # The annotation mutant is built and no candidate can kill it — the case that reaches the fallback.
    assert any(m.startswith("ARITHMETIC_") for m in out["survivors"]), out["survivors"]
    assert out["ran"] == 0, "a not-consulted test was executed for this function"


def test_a_leaf_orphans_two_sign_harvest_runs_nothing(tmp_path):
    root, script = _repo(tmp_path)
    out = _session(script, root, "orphan", "two_sign")
    assert out["total_mutants"] > 0
    assert out["ran"] == 0, "the two-sign harvest ran a test for a function nothing reaches"
