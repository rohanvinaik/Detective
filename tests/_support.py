"""Plain test-support helpers (not a pytest fixture module).

Builders live here as importable functions rather than fixtures because a
fixture-dependent test contributes no mutation kill power under Wesker (its
discovery skips tests needing real fixtures). Native tests that must pin
survivors call these directly, so they are zero-arg and Wesker-runnable.

Named ``_support.py`` (not ``test_*``) so pytest does not collect it as tests.
"""

from __future__ import annotations

from Wesker.engine import CategoryResult, MutationCategory, ProfilingResult


def make_pr(
    *,
    function_key: str = "m::f",
    categories: list[dict] | None = None,
    killed_records: list[dict] | None = None,
    survivor_records: list[dict] | None = None,
    equivalent: int = 0,
    universe: int | None = None,
    mutants: int | None = None,
) -> ProfilingResult:
    """Build a constructed Wesker ``ProfilingResult``.

    Categories are compact dicts:
    ``{"category", "killed", "survived", "equivalent"?, "assertion"?, "crash"?}``.
    """
    killed_records = killed_records or []
    survivor_records = survivor_records or []
    per_category = [
        CategoryResult(
            category=MutationCategory(c["category"]),
            total=c.get("total", c["killed"] + c["survived"] + c.get("equivalent", 0)),
            killed=c["killed"],
            survived=c["survived"],
            equivalent=c.get("equivalent", 0),
            killed_by_assertion=c.get("assertion", 0),
            killed_by_crash=c.get("crash", 0),
        )
        for c in (categories or [])
    ]
    total = len(killed_records) + len(survivor_records) + equivalent
    return ProfilingResult(
        function_key=function_key,
        per_category=per_category,
        killed_records=killed_records,
        survivor_records=survivor_records,
        total_killed=len(killed_records),
        total_survived=len(survivor_records),
        total_equivalent=equivalent,
        universe_size=total if universe is None else universe,
        total_mutants=total if mutants is None else mutants,
    )
