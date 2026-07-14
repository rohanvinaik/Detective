"""Generate tests/test_scope_oracle.py — oracle-warranted conformance for scope.

Dev-time only. Runs LintGate's `_scope_from_result` (the reference implementation
Detective's `scope.py` was ported from) as the conformance ORACLE over a corpus
of constructed Wesker `ProfilingResult` fixtures, and emits a static, parametrized
pytest module whose expected values are the oracle's output baked in as literals.

LintGate is imported here, at generation time, ONLY — never by the shipped package
or the test at runtime. Run from the Detective repo root:

    python dev/generators/gen_scope_oracle_tests.py

The corpus is designed to exercise exactly the degrees of freedom the Detective
characterization flagged as unspecified in the reference: the crash-quality
thresholds, the regime-B boundary, the survivor-slice cap, and the universe
fallback.
"""

from __future__ import annotations

import os
import sys
from dataclasses import asdict

# LintGate (the oracle) lives in the sibling repo. Dev-time path only.
_LINTGATE = os.environ.get(
    "LINTGATE_ROOT", os.path.join(os.path.dirname(__file__), "..", "..", "..", "lintgate")
)
sys.path.insert(0, os.path.abspath(_LINTGATE))

from mcp_tools._mutation_tools_impl import _scope_from_result as oracle  # noqa: E402
from Wesker.engine import CategoryResult, MutationCategory, ProfilingResult  # noqa: E402

from Detective.scope import scope_from_profiling  # noqa: E402

# Fields Detective's ScopeMap owns (the port defers LintGate enrichment fields
# like is_pure/parameter_count/topology/truth_label, which are not on a
# ProfilingResult). Conformance is asserted on this shared subset.
SHARED_FIELDS = [
    "function",
    "regime",
    "surviving_categories",
    "specification",
    "kill_quality",
    "behavioral_dof",
    "load_bearing_tests",
    "unspecified_behaviors",
]


def _k(cat: str, by: str, test: str | None, mid: str) -> dict:
    return {"mutant_id": mid, "mutant": f"{mid}: mutation", "category": cat, "killed_by": by, "test": test}


def _s(mid: str, desc: str) -> dict:
    return {"mutant_id": mid, "mutant": desc, "category": mid.split("_")[0]}


def _cat(category: str, killed: int, survived: int, equivalent: int, assertion: int, crash: int) -> dict:
    return {
        "category": category,
        "total": killed + survived + equivalent,
        "killed": killed,
        "survived": survived,
        "equivalent": equivalent,
        "killed_by_assertion": assertion,
        "killed_by_crash": crash,
    }


def _build(raw: dict) -> ProfilingResult:
    return ProfilingResult(
        function_key=raw["function_key"],
        per_category=[
            CategoryResult(
                category=MutationCategory(c["category"]),
                total=c["total"],
                killed=c["killed"],
                survived=c["survived"],
                equivalent=c["equivalent"],
                killed_by_assertion=c["killed_by_assertion"],
                killed_by_crash=c["killed_by_crash"],
            )
            for c in raw["categories"]
        ],
        killed_records=raw["killed_records"],
        survivor_records=raw["survivor_records"],
        total_killed=raw["total_killed"],
        total_survived=raw["total_survived"],
        total_equivalent=raw["total_equivalent"],
        universe_size=raw["universe_size"],
        total_mutants=raw["total_mutants"],
    )


def _raw(
    function_key, categories, killed_records, survivor_records, equivalent=0, universe=None, mutants=None
):
    tk, ts = len(killed_records), len(survivor_records)
    total = tk + ts + equivalent
    return {
        "function_key": function_key,
        "categories": categories,
        "killed_records": killed_records,
        "survivor_records": survivor_records,
        "total_killed": tk,
        "total_survived": ts,
        "total_equivalent": equivalent,
        "universe_size": total if universe is None else universe,
        "total_mutants": total if mutants is None else mutants,
    }


def corpus() -> list[tuple[str, dict]]:
    """Constructed ProfilingResult fixtures, each targeting flagged DOF."""
    return [
        (
            "clean_mixed_regime_a",
            _raw(
                "m::clean",
                [_cat("VALUE", 4, 0, 0, 3, 1), _cat("BOUNDARY", 2, 0, 0, 2, 0)],
                [_k("VALUE", "assertion", f"t{i}", f"VALUE_{i}") for i in range(3)]
                + [_k("VALUE", "crash", "t3", "VALUE_3")]
                + [_k("BOUNDARY", "assertion", f"t{i}", f"BOUNDARY_{i}") for i in range(4, 6)],
                [],
            ),
        ),
        (
            "crash_dominated_warns",
            _raw(
                "m::crashdom",
                [_cat("VALUE", 3, 0, 0, 0, 3)],
                [_k("VALUE", "crash", "t0", f"VALUE_{i}") for i in range(3)],
                [],
            ),
        ),
        (
            "crash_heavy_warns",
            _raw(
                "m::crashheavy",
                [_cat("VALUE", 5, 0, 0, 1, 4)],
                [_k("VALUE", "assertion", "t0", "VALUE_0")]
                + [_k("VALUE", "crash", "t1", f"VALUE_{i}") for i in range(1, 5)],
                [],
            ),
        ),
        (
            "regime_b_entangled",
            _raw(
                "m::entangled",
                [_cat("VALUE", 5, 3, 0, 5, 0), _cat("BOUNDARY", 2, 2, 0, 2, 0)],
                [_k("VALUE", "assertion", f"t{i}", f"VALUE_{i}") for i in range(5)]
                + [_k("BOUNDARY", "assertion", f"t{i}", f"BOUNDARY_{i}") for i in range(5, 7)],
                [_s(f"VALUE_{i}", f"VALUE_{i}: replace constant") for i in range(10, 13)]
                + [_s(f"BOUNDARY_{i}", f"BOUNDARY_{i}: off-by-one") for i in range(10, 12)],
            ),
        ),
        (
            "fully_specified_no_survivors",
            _raw(
                "m::pinned",
                [_cat("VALUE", 6, 0, 0, 6, 0), _cat("LOGICAL", 3, 0, 0, 3, 0)],
                [_k("VALUE", "assertion", f"t{i}", f"VALUE_{i}") for i in range(6)]
                + [_k("LOGICAL", "assertion", f"t{i}", f"LOGICAL_{i}") for i in range(6, 9)],
                [],
            ),
        ),
        (
            "universe_fallback_to_total_mutants",
            {
                **_raw(
                    "m::fallback", [_cat("VALUE", 1, 0, 0, 0, 1)], [_k("VALUE", "crash", "t0", "VALUE_0")], []
                ),
                "universe_size": 0,
                "total_mutants": 1,
            },
        ),
        (
            "survivor_slice_capped_at_20",
            _raw(
                "m::manysurv",
                [_cat("VALUE", 2, 25, 0, 2, 0)],
                [_k("VALUE", "assertion", f"t{i}", f"VALUE_{i}") for i in range(2)],
                [_s(f"VALUE_{100 + i}", f"VALUE_{100 + i}: replace constant") for i in range(25)],
            ),
        ),
        (
            "empty_no_mutants",
            _raw("m::empty", [], [], []),
        ),
    ]


def build_cases() -> list[tuple[str, dict, dict]]:
    cases = []
    for case_id, raw in corpus():
        pr = _build(raw)
        expected = {k: oracle(pr.to_dict())[k] for k in SHARED_FIELDS}
        # Dev-time guard: the port must already conform to the oracle.
        got = {k: asdict(scope_from_profiling(pr))[k] for k in SHARED_FIELDS}
        if got != expected:
            raise SystemExit(f"PORT DIVERGES from oracle on '{case_id}':\n  port={got}\n  oracle={expected}")
        cases.append((case_id, raw, expected))
    return cases


_HEADER = '''"""Oracle-warranted conformance tests for Detective.scope.scope_from_profiling.

GENERATED by dev/generators/gen_scope_oracle_tests.py — do not hand-edit.

Each case feeds a constructed Wesker ProfilingResult to the port and asserts the
behavioral-scope map matches the LintGate reference implementation's output
(the oracle), captured at generation time. No LintGate import at runtime.
"""

from __future__ import annotations

from dataclasses import asdict

import pytest

from Detective.scope import scope_from_profiling
from Wesker.engine import CategoryResult, MutationCategory, ProfilingResult

SHARED_FIELDS = {shared_fields!r}


def _build(raw: dict) -> ProfilingResult:
    return ProfilingResult(
        function_key=raw["function_key"],
        per_category=[
            CategoryResult(
                category=MutationCategory(c["category"]),
                total=c["total"],
                killed=c["killed"],
                survived=c["survived"],
                equivalent=c["equivalent"],
                killed_by_assertion=c["killed_by_assertion"],
                killed_by_crash=c["killed_by_crash"],
            )
            for c in raw["categories"]
        ],
        killed_records=raw["killed_records"],
        survivor_records=raw["survivor_records"],
        total_killed=raw["total_killed"],
        total_survived=raw["total_survived"],
        total_equivalent=raw["total_equivalent"],
        universe_size=raw["universe_size"],
        total_mutants=raw["total_mutants"],
    )


'''


def render(cases: list[tuple[str, dict, dict]]) -> str:
    lines = [_HEADER.format(shared_fields=SHARED_FIELDS)]
    lines.append("CASES = [")
    for case_id, raw, expected in cases:
        lines.append(
            f"    pytest.param(\n        {raw!r},\n        {expected!r},\n        id={case_id!r},\n    ),"
        )
    lines.append("]\n\n")
    lines.append('@pytest.mark.parametrize("raw, expected", CASES)\n')
    lines.append("def test_scope_conforms_to_reference(raw: dict, expected: dict) -> None:\n")
    lines.append("    scope = scope_from_profiling(_build(raw))\n")
    lines.append("    got = {k: asdict(scope)[k] for k in SHARED_FIELDS}\n")
    lines.append("    assert got == expected\n")
    return "".join(lines)


def main() -> None:
    cases = build_cases()
    out = os.path.join(os.path.dirname(__file__), "..", "..", "tests", "test_scope_oracle.py")
    with open(os.path.abspath(out), "w", encoding="utf-8") as fh:
        fh.write(render(cases))
    print(f"wrote {os.path.abspath(out)} — {len(cases)} conformance cases")


if __name__ == "__main__":
    main()
