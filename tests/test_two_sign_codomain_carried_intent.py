"""Intent: the observed codomain travels WITH the verdict — a warm two-sign run re-harvests nothing (#92).

The defect (found by the static trace of the pool fix, `docs/ENGINEERING_PASS_2026-09-26.md` §7). Under the
two-sign contract the profile OBSERVES the target's codomain — the return types its covering tests see (μ⁻
Fork 2) — and generates the type-conditional OUTPUT mutants (→negate, →abs, …) from it. Classification
regenerates the same content-addressed mutants to witness-search them, so it needs the SAME observation.
That observation was a Detective stash on `ProfilingResult`, not a field, and the verdict cache stores
`asdict(result)`: it was dropped. On every warm two-sign run `classify_survivors` re-captured it over
`discover_test_callables(...)`, which in a live session IS the whole collection — not-consulted tests
executed (the 2026-09-05 ruling) and a whole-suite pass paid for a value the cold run had already computed
over the consulted pool: two derivations of one value (invariant 8). Measured on the fixture below: the
cold classification ran the no-path test 0 times, the warm one 1 time.

The repair, EP-C2's compute-once: the codomain is stored with the verdict and restored with it, and a row
written before that (or a foreign result) observes it over the CONSULTED pool by `profile`'s own derivation
— `engine.codomain_source`, pinned. Absent and EMPTY are different facts and must stay apart: an empty
codomain is an observation and is not re-harvested; an absent one must never be read as empty, or the
type-conditional survivors' ids vanish from classification and they fall to `unclassified`. Every
behavioural test runs through a REAL live session in a fresh subprocess and counts executions of a no-path
test, the counter-test pattern of `test_engine_pool_is_the_consulted_set_intent.py`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest
from Wesker.engine import ProfilingResult

from Detective import engine as deng
from Detective import verdict_cache

needs_target_first = pytest.mark.skipif(
    not getattr(deng, "_WESKER_TARGET_FIRST", False),
    reason="installed Wesker has no target-first seed/widen path",
)

# argv = root, mode. Last stdout line is JSON. `ran` counts executions of the no-path test; `hits` counts
# verdict-cache hits, so a "warm" claim is checked rather than assumed.
_SESSION_SCRIPT = """
import sys, os, json
root, mode = sys.argv[1], sys.argv[2]
from Wesker.ci import run_with_live_suite
import Detective.engine as deng
import Detective.verdict_cache as vc

_real_get = vc.get
hits = []


def _counting_get(project_root, key):
    got = _real_get(project_root, key)
    if got is not None:
        hits.append(key)
    return got


vc.get = _counting_get
# Which result each of converge's classifications was handed — warm (served from the cache) or fresh —
# and how many no-path executions it cost: the warm path is the one #92 is about, so it is observed.
import importlib
dconv = importlib.import_module("Detective.converge")
_real_classify = dconv.classify_survivors
classified = []


def _observed_classify(*a, **k):
    import pkg
    before = len(pkg.RAN)
    rep = _real_classify(*a, **k)
    warm = bool(getattr(k.get("profile_result"), "served_from_cache", False))
    classified.append({"warm": warm, "ran": len(pkg.RAN) - before})
    return rep


dconv.classify_survivors = _observed_classify
out = {}


def _classification(rep):
    if rep is None:
        return None
    return {
        "killable": sorted(v.mutant_id for v in rep.killable),
        "candidate_equivalent": sorted(v.mutant_id for v in rep.candidate_equivalent),
        "crash_only": sorted(v.mutant_id for v in rep.crash_only),
        "unclassified": sorted(rep.unclassified),
        "routing_error": getattr(rep, "routing_error", None),
    }


def _measure(tag):
    import pkg
    before = len(pkg.RAN)
    r = deng.profile("pkg/mod.py", "flip", root, scope_tests=True, use_cache=True, two_sign=True)
    carried = getattr(r, "observed_return_types", None)
    rep = deng.classify_survivors("pkg/mod.py", "flip", root, profile_result=r, two_sign=True)
    out[tag] = {
        "served_from_cache": bool(getattr(r, "served_from_cache", False)),
        "codomain": None if carried is None else sorted(carried),
        "survivors": sorted(x.get("mutant_id") for x in r.value_survivor_records),
        "classification": _classification(rep),
        "ran": len(pkg.RAN) - before,
    }


def body():
    if mode == "cold_then_warm":
        _measure("cold")
        _measure("warm")
    elif mode == "old_row":
        _measure("old_row")
    elif mode == "converge":
        import pkg
        # The cold reference: a fresh profile (no cache read or write), classified.
        cold = deng.profile("pkg/mod.py", "flip", root, scope_tests=True, use_cache=False, two_sign=True)
        cold_rep = deng.classify_survivors("pkg/mod.py", "flip", root, profile_result=cold, two_sign=True)
        out["cold_classification"] = _classification(cold_rep)
        before = len(pkg.RAN)
        # Writes nothing and runs one pass, so its final measurement asks pass 0's exact question and is
        # served from the row pass 0 stored — this run's, or the previous session's: a WARM converge.
        res = dconv.converge(
            "pkg/mod.py", "flip", root, two_sign=True, write_dir=None, max_iterations=1, deadline_s=None
        )
        out["converge"] = {
            "classification": _classification(res.survivor_report),
            "final_survivors": res.final_survivors,
            "cut_reasons": list(res.cut_reasons),
            "ran": len(pkg.RAN) - before,
        }
        out["classified"] = classified


run_with_live_suite(
    root, body, target_files=[os.path.join(root, "pkg", "mod.py")], paths=[os.path.join(root, "tests")]
)
out["hits"] = len(hits)
print(json.dumps(out))
"""


def _repo(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\ntestpaths = ['tests']\nmarkers = ['detective: generated']\n"
    )
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("RAN = []\n")
    # `flip` returns a non-negative int, so under two-sign the codomain is OBSERVED as {int} and the
    # type-conditional →abs perturbation is generated — and is EQUIVALENT (abs of a non-negative is
    # itself). Classifying it needs the observed codomain: read as empty, its id would be missing and it
    # would fall to `unclassified`. `x < 0` -> `x <= 0` is equivalent too (flip(0) == 0 either way).
    (pkg / "mod.py").write_text("def flip(x):\n    return -x if x < 0 else x\n")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_flip.py").write_text(
        "from pkg.mod import flip\n\n"
        "def test_neg():\n    assert flip(-3) == 3\n\n"
        "def test_pos():\n    assert flip(4) == 4\n"
    )
    # No static path to `flip`: never consulted, and it records every execution.
    (tests / "test_unrelated.py").write_text("import pkg\n\ndef test_u():\n    pkg.RAN.append('test_u')\n")
    (tmp_path / "_session_probe.py").write_text(_SESSION_SCRIPT)
    return str(tmp_path)


def _session(root, mode):
    proc = subprocess.run(
        [sys.executable, os.path.join(root, "_session_probe.py"), root, mode],
        capture_output=True,
        text=True,
        env=os.environ,  # inherits PYTHONPATH (local) or the venv (pinned Wesker under uv run)
        timeout=300,
    )
    assert proc.returncode == 0, f"session {mode} failed:\n{proc.stdout}\n{proc.stderr}"
    return json.loads(proc.stdout.strip().splitlines()[-1])


def _strip_codomain(root) -> int:
    """Rewrite every cached row as a row written BEFORE the codomain was carried. Returns how many."""
    path = os.path.join(root, ".detective", "verdict_cache.json")
    with open(path, encoding="utf-8") as fh:
        rows = json.load(fh)
    stripped = sum(1 for row in rows.values() if row.pop("observed_return_types", None) is not None)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(rows, fh)
    return stripped


# ── the pure decision ──────────────────────────────────────────────────────────────────────────────


def test_where_the_codomain_comes_from():
    assert deng.codomain_source(two_sign=False, carried=False) == deng.CODOMAIN_NOT_NEEDED
    assert deng.codomain_source(two_sign=False, carried=True) == deng.CODOMAIN_NOT_NEEDED
    assert deng.codomain_source(two_sign=True, carried=True) == deng.CODOMAIN_CARRIED
    assert deng.codomain_source(two_sign=True, carried=False) == deng.CODOMAIN_HARVEST
    assert len({deng.CODOMAIN_NOT_NEEDED, deng.CODOMAIN_CARRIED, deng.CODOMAIN_HARVEST}) == 3


# ── the cache carries it ───────────────────────────────────────────────────────────────────────────


def _round_trip(result: ProfilingResult) -> ProfilingResult:
    return verdict_cache._from_json(json.loads(json.dumps(verdict_cache._to_json(result))))


def test_the_codomain_round_trips_with_the_verdict():
    cold = ProfilingResult(function_key="m.py::f")
    cold.observed_return_types = frozenset({"int", "float"})  # ty: ignore[unresolved-attribute]
    warm = _round_trip(cold)
    assert warm.observed_return_types == frozenset({"int", "float"})  # ty: ignore[unresolved-attribute]
    assert isinstance(warm.observed_return_types, frozenset)  # ty: ignore[unresolved-attribute]


def test_an_empty_codomain_is_an_observation_not_an_absence():
    """Nothing reached the function, or it only returned None: observed, and empty. Restored as absent,
    a warm run would re-harvest for nothing; the two must not collapse."""
    cold = ProfilingResult(function_key="m.py::f")
    cold.observed_return_types = frozenset()  # ty: ignore[unresolved-attribute]
    warm = _round_trip(cold)
    assert getattr(warm, "observed_return_types", None) == frozenset()


def test_a_one_sign_verdict_carries_no_codomain_and_an_old_row_restores_none():
    one_sign = ProfilingResult(function_key="m.py::f")
    row = verdict_cache._to_json(one_sign)
    assert "observed_return_types" not in row
    assert getattr(verdict_cache._from_json(row), "observed_return_types", None) is None


def test_the_real_put_get_path_carries_it(tmp_path):
    cold = ProfilingResult(function_key="m.py::f")
    cold.observed_return_types = frozenset({"int"})  # ty: ignore[unresolved-attribute]
    verdict_cache.put(str(tmp_path), "m.py::f:k:1:2:3", "m.py::f:", cold)
    hit = verdict_cache.get(str(tmp_path), "m.py::f:k:1:2:3")
    assert hit is not None
    assert hit.observed_return_types == frozenset({"int"})  # ty: ignore[unresolved-attribute]


# ── the audit consumes the same codomain ───────────────────────────────────────────────────────────


def test_a_two_sign_audit_classifies_its_output_survivors(tmp_path):
    """Found tracing who consumes the observation: `audit --two-sign` profiled under σ(P, μ ∪ μ⁻) but
    classified ONE-sign, so every OUTPUT survivor's id was missing from the regenerated universe and it
    fell to `unclassified` — measured, 4 of them on this function — instead of surfacing as the killable
    gap the two-sign audit exists to gate on. A degenerate suite (`scale(0) == 0`) leaves them killable
    at x = -1. Unique module names: the nested audit imports them in this process."""
    (tmp_path / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\ntestpaths = ["."]\nmarkers = ["detective: generated"]\n'
    )
    (tmp_path / "a92_codomain_mod.py").write_text("def scale(x):\n    return x * 2\n")
    (tmp_path / "test_a92_codomain_repo.py").write_text(
        "from a92_codomain_mod import scale\n\n\ndef test_zero():\n    assert scale(0) == 0\n"
    )
    from Detective.audit import audit_suite

    audit = audit_suite("a92_codomain_mod.py", "scale", str(tmp_path), two_sign=True)
    assert audit.unclassified == 0
    assert any(gap.startswith("OUTPUT") for gap in audit.killable_gaps), audit.killable_gaps


# ── through a real live session ────────────────────────────────────────────────────────────────────


@needs_target_first
def test_a_warm_two_sign_classification_runs_nothing_and_classifies_as_the_cold_one(tmp_path):
    out = _session(_repo(tmp_path), "cold_then_warm")
    cold, warm = out["cold"], out["warm"]
    assert not cold["served_from_cache"] and warm["served_from_cache"], "the second profile must be warm"
    assert cold["codomain"] == ["int"]
    assert warm["codomain"] == cold["codomain"], "the observation did not travel with the verdict"
    assert cold["ran"] == 0
    assert warm["ran"] == 0, "the warm classification re-harvested over the whole collection"
    assert warm["survivors"] == cold["survivors"]
    assert warm["classification"] == cold["classification"]
    # The type-conditional survivor is classified, never dropped to `unclassified`.
    assert cold["classification"]["unclassified"] == []
    assert any(m.startswith("OUTPUT_") for m in cold["classification"]["candidate_equivalent"])


@needs_target_first
def test_an_old_row_observes_over_the_consulted_pool_not_the_collection(tmp_path):
    """The fallback: a row cached before the codomain was carried. It is observed again — over the tests
    `profile` would consult — and classifies exactly as the cold run did."""
    root = _repo(tmp_path)
    cold = _session(root, "cold_then_warm")["cold"]
    assert _strip_codomain(root) >= 1
    out = _session(root, "old_row")["old_row"]
    assert out["served_from_cache"]
    assert out["codomain"] is None  # the row carries none: the fallback is what classified it
    assert out["ran"] == 0, "the fallback harvested over the whole collection"
    assert out["classification"] == cold["classification"]


@needs_target_first
def test_a_warm_two_sign_converge_runs_nothing_and_classifies_as_the_cold_one(tmp_path):
    """The acceptance, through `converge` itself. Its final measurement is served from the cache — from
    the row its own pass 0 stored in the first session, and from the previous session's in the second —
    so its classification is handed a WARM result, the path #92 is about (checked, not assumed). Each
    must run no not-consulted test and classify exactly as a fresh profile does. Measured on the
    previous code: each warm classification here executed the no-path test once."""
    root = _repo(tmp_path)
    for session in (_session(root, "converge"), _session(root, "converge")):
        warm = [c for c in session["classified"] if c["warm"]]
        assert warm, "no classification was handed a warm result — the scenario did not occur"
        assert all(c["ran"] == 0 for c in session["classified"]), session["classified"]
        assert session["converge"]["ran"] == 0, "a warm two-sign converge executed a not-consulted test"
        assert session["converge"]["classification"] == session["cold_classification"]
        assert session["converge"]["cut_reasons"] == []
    assert session["hits"] >= 2  # the second session: pass 0 and the final measurement both warm
