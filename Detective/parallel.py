"""Parallel mutation profiling — fan mutants across worker processes (model A).

Each worker re-imports, re-discovers the tests, and evaluates ONE contiguous slice of the
(deterministically generated) mutant list; the parent then merges the partials into a
result BIT-IDENTICAL to a serial run. Because mutants are generated in a fixed order,
slice ``[a, b)`` is the same set a serial run would evaluate at those indices, and records
concatenated in shard order reproduce serial order exactly.

The fleet size IS the portable memory guarantee (``memory_guard.worker_count``): with
``workers × per_worker_peak <= budget`` by construction, the run cannot exceed the budget
on any OS — no reliance on ``RLIMIT_AS`` (a Linux-only bonus applied inside each worker).
Uses the ``spawn`` start method (fork is unsafe with the engine's timeout threads); the
worker entry is a module-level function so macOS/Windows spawn re-imports it cleanly.

Parallelism is EXPLICIT opt-in (``profile(use_parallel=True)`` / ``--parallel``): whether it
beats serial depends on the per-mutant cost, which varies ~1000x across functions (fast pure
code vs slow/heavy suites) and cannot be estimated cheaply or reliably up front — so the
choice is the user's, never an auto-guess that could slow a small function.
"""

from __future__ import annotations

import multiprocessing as mp
from typing import Any

from Wesker.engine import CategoryResult, ProfilingResult
from Wesker.memory_guard import _DEFAULT_WORKER_PEAK, apply_address_limit

from . import verdict_cache

# Adaptive auto mode. Rather than guess from a stale global rate, MEASURE this function's
# per-mutant cost with a small serial probe, then parallelize only when the remaining work
# justifies the fan-out — so the decision is right across the ~1000x per-mutant range (fast
# pure code vs slow/heavy suites). The probe doubles as shard 0 (its results are kept), so it
# is never wasted.
PROBE_SIZE = 4  # mutants to time serially before deciding
PROBE_MIN_MUTANTS = 8  # below this, just run serial — too few to shard usefully
PARALLEL_MIN_REMAINING_MS = 2000.0  # parallelize only if est. remaining serial time exceeds this


def mean_mutant_ms(result: ProfilingResult) -> float:
    """Mean per-mutant evaluation time (ms) from a profile's per-mutant records — the ACTUAL
    cost under the current (scoped) path, excluding the one-off baseline pass. 0.0 if empty."""
    times = [
        rec.get("elapsed_ms", 0.0) for rec in (list(result.survivor_records) + list(result.killed_records))
    ]
    return sum(times) / len(times) if times else 0.0


def shard_bounds(start: int, end: int, workers: int) -> list[tuple[int, int]]:
    """Contiguous, near-equal ``[a, b)`` index ranges tiling ``[start, end)`` — deterministic,
    so the same input always shards the same way (a prerequisite for reproducible merges)."""
    n = end - start
    if n <= 0:
        return []
    if workers <= 1:
        return [(start, end)]
    per = (n + workers - 1) // workers  # ceil, so the last shard is the short one
    return [(i, min(i + per, end)) for i in range(start, end, per)]


def _shard_worker(payload: dict) -> dict:
    """Spawn-safe worker: cap address space (best-effort), profile ONE mutant slice, and
    return it as a JSON-safe dict (so nothing but plain data crosses the process boundary)."""
    from .engine import profile  # local import keeps the module light for serial callers

    apply_address_limit(payload["per_worker_peak"])  # Linux bonus; no-op elsewhere
    result = profile(
        payload["file"],
        payload["function"],
        payload["project_root"],
        max_per_category=payload["max_per_category"],
        pass_index=payload["pass_index"],
        scope_tests=payload["scope_tests"],
        mutant_slice=tuple(payload["mutant_slice"]),
        use_cache=False,  # workers compute partials; only the parent caches the whole result
    )
    return verdict_cache._to_json(result)


def merge_results(partials: list[ProfilingResult]) -> ProfilingResult:
    """Combine shard results into one identical to a serial run. Records concatenate in
    shard (= mutant-index) order; per-category counts sum; the baseline fields (line
    coverage, executable lines, failing tests) are computed identically by every worker, so
    shard 0's are authoritative. ``per_category`` is emitted in sorted-category order — the
    same order ``generate_mutants`` (hence a serial run) produces."""
    partials = [p for p in partials if p is not None]
    if not partials:
        raise RuntimeError("parallel profiling produced no shard results")
    base = partials[0]

    by_cat: dict[Any, CategoryResult] = {}
    for p in partials:
        for cr in p.per_category:
            agg = by_cat.get(cr.category)
            if agg is None:
                by_cat[cr.category] = CategoryResult(
                    category=cr.category,
                    total=cr.total,
                    killed=cr.killed,
                    survived=cr.survived,
                    killed_by_assertion=cr.killed_by_assertion,
                    killed_by_crash=cr.killed_by_crash,
                    timed_out=cr.timed_out,
                    equivalent=cr.equivalent,
                )
            else:
                agg.total += cr.total
                agg.killed += cr.killed
                agg.survived += cr.survived
                agg.killed_by_assertion += cr.killed_by_assertion
                agg.killed_by_crash += cr.killed_by_crash
                agg.timed_out += cr.timed_out
                agg.equivalent += cr.equivalent
    per_category = [by_cat[c] for c in sorted(by_cat, key=lambda c: c.value)]

    survivor_records = [r for p in partials for r in p.survivor_records]
    killed_records = [r for p in partials for r in p.killed_records]
    kill_matrix: dict[str, list[str]] = {}
    for p in partials:
        for desc, tests in p.kill_matrix.items():
            kill_matrix.setdefault(desc, []).extend(tests)

    total = sum(cr.total for cr in per_category)
    killed = sum(cr.killed for cr in per_category)
    return ProfilingResult(
        function_key=base.function_key,
        categories_tested=len(per_category),
        total_mutants=total,
        total_killed=killed,
        total_survived=total - killed,
        survival_rate=(total - killed) / total if total else 0.0,
        per_category=per_category,
        kill_matrix=kill_matrix,
        survivor_records=survivor_records,
        killed_records=killed_records,
        budget_exhausted=any(p.budget_exhausted for p in partials),
        elapsed_ms=max(p.elapsed_ms for p in partials),
        line_coverage=base.line_coverage,
        executable_lines=base.executable_lines,
        failing_tests=base.failing_tests,
        tests_discovered=base.tests_discovered,
    )


def parallel_profile(
    file: str,
    function: str,
    project_root: str,
    *,
    end: int,
    start: int = 0,
    max_per_category: int,
    pass_index: int,
    scope_tests: bool,
    workers: int,
    per_worker_peak: int | None = None,
    notify: bool = True,
) -> ProfilingResult:
    """Shard the mutant index range ``[start, end)`` across ``workers`` spawned processes and
    merge. ``end`` is the EXACT count a serial ``generate_mutants`` yields, so the shards tile
    the real index space; ``start`` > 0 lets an adaptive probe own ``[0, start)`` as shard 0.
    Returns a ProfilingResult indistinguishable from a serial run of that range (verified
    bit-identical). ``notify`` prints a one-line stderr notice, since per-mutant streaming is
    not possible across the process boundary — so a fanned-out run never 'looks hung'."""
    import sys

    peak = per_worker_peak or _DEFAULT_WORKER_PEAK
    bounds = shard_bounds(start, end, workers)
    if notify:
        sys.stderr.write(
            f"  ⚡ {function}: {end - start} mutants across {len(bounds)} worker(s) "
            f"(fleet ≤ {len(bounds) * (peak // (1024 * 1024))} MB) — no per-mutant stream\n"
        )
        sys.stderr.flush()
    payloads = [
        {
            "file": file,
            "function": function,
            "project_root": project_root,
            "max_per_category": max_per_category,
            "pass_index": pass_index,
            "scope_tests": scope_tests,
            "mutant_slice": [a, b],
            "per_worker_peak": peak,
        }
        for (a, b) in bounds
    ]
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=len(payloads)) as pool:
        parts = pool.map(_shard_worker, payloads)
    return merge_results([verdict_cache._from_json(p) for p in parts])
