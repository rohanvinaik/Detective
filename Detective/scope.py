"""Behavioral-scope reshaping of a Wesker profiling result.

Reads a mutant set *backwards*: not "what tests are missing" but "what
behavioral distinctions does this function make". Each killed mutant is a
distinction the tests pin; each survivor is an unspecified degree of freedom;
each equivalent mutant is behaviorally-null freedom. The load-bearing signal is
kill *quality* — killed by a value-assertion vs. killed only by a crash: an
all-crash kill pins that the code RUNS, not WHAT it returns.

Clean-room port of LintGate's reshaper, consuming Wesker's real ``ProfilingResult``
(and ``SamplingResult``) rather than an ad-hoc dict, and reading the engine's own
per-category ``killed_by_assertion``/``killed_by_crash`` aggregates directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from Wesker.engine import CategoryResult, ProfilingResult

_CRASH_DOMINATED = (
    "crash-dominated: every mutant dies by raising, not by a value assertion — the tests pin "
    "that the code RUNS, not WHAT it returns; the return-value behavior may be under-specified"
)
_CRASH_HEAVY = (
    "crash-heavy: most kills are exceptions rather than value assertions; verify return-value coverage"
)

# A survivor's category count of >= this many pushes a function into regime B
# (entangled — multiple interleaved responsibilities).
_ENTANGLED_CATEGORY_THRESHOLD = 2

# Crash kills outnumbering assertion kills by more than this factor is "crash-heavy".
_CRASH_HEAVY_FACTOR = 3

# Cap on the survivor descriptions surfaced in the map.
_MAX_UNSPECIFIED = 20


@dataclass(frozen=True)
class CategoryScope:
    """One mutation category's behavioral degrees of freedom."""

    category: str
    distinctions_pinned: int
    unspecified: int
    inert: int
    by_value_assertion: int
    by_crash_only: int


@dataclass(frozen=True)
class KillQuality:
    """The value-assertion vs. crash split across all kills."""

    by_value_assertion: int
    by_crash: int
    warning: str | None


@dataclass(frozen=True)
class Specification:
    """Scalar summary of the function's behavioral specification."""

    behavioral_variants: int
    distinctions_pinned: int
    unspecified_dof: int
    inert_freedom: int
    sigma_proxy_teaching_set: int


@dataclass(frozen=True)
class ScopeMap:
    """A function's behavioral scope, read backwards out of its mutant set."""

    function: str
    regime: str
    surviving_categories: list[str]
    specification: Specification
    kill_quality: KillQuality
    behavioral_dof: list[CategoryScope]
    load_bearing_tests: list[str] = field(default_factory=list)
    unspecified_behaviors: list[str] = field(default_factory=list)
    # Test callables discovered for this function. 0 means the 0% kill rate is because
    # there is NOTHING to kill with — a "write a test" signal, not weak tests. -1 = the
    # profiler did not report it (backward-compatible).
    tests_discovered: int = -1
    # Structural decomposition seams: the count of clean single-exit, small-interface
    # extraction candidates the deterministic clustering finds (independent of tests). It is
    # the STRUCTURAL half of the "is this two things?" question; regime B is the BEHAVIORAL
    # (mutation) half. When BOTH fire, two independent methods agree — a high-value target.
    decompose_seams: int = 0
    # Tests whose TRACED baseline pass hit the engine's `trace_budget_s` and was CUT (Wesker
    # >=0.5.0). Their line coverage is under-counted, so a line gap this run reports MAY be an
    # artifact of the budget rather than a real hole — and the two are indistinguishable from the
    # numbers alone. Surfaced so the reader can tell; a completeness verdict that quietly rests on
    # a truncated measurement is the one failure this tool cannot afford.
    trace_truncated: list[str] = field(default_factory=list)
    # Whether this verdict was REPLAYED from the on-disk cache rather than measured by this run.
    # Only meaningful next to `trace_truncated`, and it is what makes that field reportable: a cut
    # is a fact about the run that traced the suite, and a cache hit traces nothing. Replaying
    # "152 tests were CUT" in the present tense describes a measurement this call never made, taken
    # under a machine load that is gone — the budgets are WALL-CLOCK, so what got cut depends on
    # what else was running at the time. The reader cannot act on that the way they can act on a
    # fresh cut, so the two must not render identically.
    served_from_cache: bool = False


def _kill_quality_warning(by_assertion: int, by_crash: int, total_killed: int) -> str | None:
    if not total_killed:
        return None
    if by_assertion == 0 and by_crash:
        return _CRASH_DOMINATED
    if by_crash > by_assertion * _CRASH_HEAVY_FACTOR:
        return _CRASH_HEAVY
    return None


def scope_from_profiling(result: ProfilingResult) -> ScopeMap:
    """Reshape a Wesker profiling result into a behavioral-scope map."""
    killed = result.killed_records
    # Specification-relevant survivors: true survivors PLUS crash/timeout kills (the
    # value-unspecified DOF). A crash-dominated function is under-specified, not pinned.
    survivors = result.value_survivor_records
    total_killed = result.total_killed
    universe = result.universe_size or result.total_mutants or total_killed

    by_assertion = sum(1 for k in killed if k.get("killed_by") == "assertion")
    by_crash = sum(1 for k in killed if k.get("killed_by") == "crash")

    behavioral_dof = [_category_scope(cr, killed) for cr in result.per_category]
    surviving_categories = [c.category for c in behavioral_dof if c.unspecified > 0]
    regime = "B" if len(surviving_categories) >= _ENTANGLED_CATEGORY_THRESHOLD else "A"

    tests: set[str] = set()
    for k in killed:
        t = k.get("test")
        if isinstance(t, str):
            tests.add(t)
    load_bearing = sorted(tests)

    return ScopeMap(
        function=result.function_key,
        regime=regime,
        surviving_categories=surviving_categories,
        specification=Specification(
            behavioral_variants=universe,
            distinctions_pinned=result.value_killed,
            unspecified_dof=result.value_survived,
            inert_freedom=result.total_equivalent,
            sigma_proxy_teaching_set=len(load_bearing),
        ),
        kill_quality=KillQuality(
            by_value_assertion=by_assertion,
            by_crash=by_crash,
            warning=_kill_quality_warning(by_assertion, by_crash, total_killed),
        ),
        behavioral_dof=behavioral_dof,
        load_bearing_tests=load_bearing,
        unspecified_behaviors=[_survivor_desc(s) for s in survivors[:_MAX_UNSPECIFIED]],
        tests_discovered=getattr(result, "tests_discovered", -1),
        # getattr-defaulted: an older engine simply does not report it (same contract as
        # tests_discovered above), and a missing field must never read as "nothing was cut".
        trace_truncated=list(getattr(result, "trace_truncated", ()) or ()),
        # Tagged by `verdict_cache.get` on a hit; absent (False) on a fresh measurement. Same
        # getattr contract as above, and for the same reason: unset must read as "this run
        # measured it", which is the claim the renderer can safely make in the present tense.
        served_from_cache=bool(getattr(result, "served_from_cache", False)),
    )


def _category_scope(cr: CategoryResult, killed: list[dict]) -> CategoryScope:
    cat = cr.category.value
    cat_killed = [k for k in killed if k.get("category") == cat]
    return CategoryScope(
        category=cat,
        # Specification counts only value-assertion kills; a crash/timeout kill leaves
        # the return value unspecified, so it counts as unspecified DOF, not pinned.
        distinctions_pinned=cr.value_killed,
        unspecified=cr.value_survived,
        inert=cr.equivalent,
        by_value_assertion=sum(1 for k in cat_killed if k.get("killed_by") == "assertion"),
        by_crash_only=sum(1 for k in cat_killed if k.get("killed_by") == "crash"),
    )


def _survivor_desc(record: dict) -> str:
    return record.get("mutant") or record.get("mutant_id") or ""
