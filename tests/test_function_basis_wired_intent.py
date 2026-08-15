"""profile() attaches the FunctionBasis, and diagnose carries it — the D-phase object goes live (X4).

TEST_BASIS §16 X4 (Part V gap ledger, G4 — wiring). Before this, `function_basis` had NO production
consumer: the corrected assembler (X3) was computed nowhere. X4 attaches it at BOTH of profile()'s
return sites — the fresh compute AND the cache hit — as a Detective-side attribute on the Wesker
result (the `served_from_cache` convention), and `scope_from_profiling` carries it onto the ScopeMap
so `diagnose --json` (`asdict(scope)`) surfaces the one authoritative per-function object.
"""

from __future__ import annotations

from dataclasses import asdict

from _support import make_pr

from Detective.engine import FunctionBasis, function_basis, profile
from Detective.scope import scope_from_profiling
from Detective.validity import MeasurementValidity


def _repo(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[tool.pytest.ini_options]\ntestpaths = ["tests"]\n')
    (tmp_path / "m.py").write_text("def f(n):\n    if n > 0:\n        return n\n    return -n\n")
    tdir = tmp_path / "tests"
    tdir.mkdir()
    (tdir / "test_m.py").write_text("from m import f\n\n\ndef test_pos():\n    assert f(2) == 2\n")
    return str(tmp_path)


def test_profile_attaches_a_basis_on_both_the_fresh_and_cached_paths(tmp_path):
    root = _repo(tmp_path)
    cold = profile("m.py", "f", root, use_cache=True)  # cache empty → fresh return site
    cold_basis = getattr(cold, "function_basis", None)
    assert isinstance(cold_basis, FunctionBasis), "profile() must attach a FunctionBasis (G4)"
    assert cold_basis.target == "m.py::f"
    # M_t is the applied mutant universe; a real profile has some mutants.
    assert len(cold_basis.obligations.mutation_dims) > 0

    warm = profile("m.py", "f", root, use_cache=True)  # same inputs → cache HIT return site
    warm_basis = getattr(warm, "function_basis", None)
    assert isinstance(warm_basis, FunctionBasis), "a warm (cached) run must attach a basis too"
    assert warm_basis.target == "m.py::f"


def test_scope_from_profiling_carries_the_basis_into_diagnose_json(tmp_path):
    # Unit-level: a result with a basis attached is carried onto the ScopeMap and survives asdict
    # (the exact serialization `diagnose --json` uses), so the object reaches the machine surface.
    pr = make_pr(
        categories=[{"category": "VALUE", "killed": 1, "survived": 0, "assertion": 1}],
        killed_records=[{"category": "VALUE", "killed_by": "assertion", "test": "t"}],
    )
    basis = function_basis(pr, MeasurementValidity(gateable=True, cut_reasons=()))
    pr.function_basis = basis
    scope = scope_from_profiling(pr)
    assert scope.function_basis is basis
    js = asdict(scope)
    assert js["function_basis"]["target"] == basis.target
    assert js["function_basis"]["action"] in {"complete", "gap", "unresolved", "trace_next"}


def test_a_result_without_a_basis_leaves_the_scope_field_none(tmp_path):
    # getattr-defaulted: an older engine that does not attach a basis reads as None, never a crash.
    pr = make_pr(categories=[{"category": "VALUE", "killed": 1, "survived": 0, "assertion": 1}])
    scope = scope_from_profiling(pr)
    assert scope.function_basis is None
