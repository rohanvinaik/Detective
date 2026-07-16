"""Content-hashed verdict cache for ``profile()`` — the iterative-loop speedup.

A function's mutation profile is fully determined by (1) the function's own source,
(2) the source of the tests that exercise it, and (3) the sampling parameters
(``max_per_category``/``pass_index`` — fast vs comprehensive vs each greedy pass give
different mutant sets). Key the cached ``ProfilingResult`` on all three, so re-profiling
an unchanged function while OTHER functions are being edited returns instantly, while ANY
edit to the function or its tests misses — never a stale verdict.

Content-addressed, never path-addressed: an out-of-band edit changes the hash and
invalidates the entry. Single-valid-copy: writing a new hash for a function purges its
prior entries, so ``.detective/verdict_cache.json`` stays bounded (one row per
function/params, not one per edit).
"""

from __future__ import annotations

import hashlib
import inspect
import json
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

from Wesker.engine import CategoryResult, MutationCategory, ProfilingResult

_CACHE_REL = (".detective", "verdict_cache.json")


def _sha(text: str) -> str:
    """Stable 16-hex content hash.

    Was documented as "same construction as Wesker's ``_code_hash``" — a symbol removed in
    Wesker 0.6.0 along with the per-function cache it served, which nothing outside its own
    tests ever called and which invalidated on the function's hash but NOT its tests'. This
    module is that idea done once, keyed on everything that can change the answer.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def tests_fingerprint(tests: list[Callable[..., Any]]) -> str:
    """Order-independent content hash of the discovered test callables' sources.

    Uses each test's source text, so editing ANY exercising test changes the hash and
    invalidates the cache. Sorted, so discovery order does not affect the key. Falls back
    to a qualified name when a callable has no recoverable source (dynamically built), so a
    fingerprint is always produced (conservatively coarse, never wrong)."""
    parts: list[str] = []
    for t in tests:
        try:
            parts.append(inspect.getsource(t))
        except (OSError, TypeError):
            parts.append(f"{getattr(t, '__module__', '?')}.{getattr(t, '__qualname__', repr(t))}")
    return _sha("\n".join(sorted(parts)))


# The key is a POSITIONAL CONTRACT with two readers: `cache_key` builds it, `put` re-parses it
# to find which entries are stale copies of the same question. Nothing tied them together, so
# `put` hardcoded "the last two fields are :max:pass" as a bare `rfind`. Appending the trace
# budgets silently redefined that slice as ":pass:budgets", and a `--fast` run then evicted the
# comprehensive entry it should have sat beside — same function, different question, one copy
# destroyed. The field count lives HERE, beside the builder, and any new trailing param must
# bump it. Better still: keep params trailing and content leading, so this stays a count.
_PARAM_FIELDS = 3  # max_per_category, pass_index, trace_budgets


def params_suffix(key: str) -> str:
    """The trailing param fields of ``key``.

    Two entries sharing this suffix answer the SAME question about the same function, so the
    older one is a stale copy. Two entries differing in it answer DIFFERENT questions (a fast
    sample vs a comprehensive run; one trace budget vs another) and must coexist.
    """
    return ":" + ":".join(key.rsplit(":", _PARAM_FIELDS)[1:])


def cache_key(
    func_key: str,
    func_source: str,
    tests: list[Callable[..., Any]],
    max_per_category: int,
    pass_index: int,
    trace_budgets: tuple[float | None, float | None] = (None, None),
) -> str:
    """The content-addressed key: identity + fn-hash + tests-hash + sampling + trace budgets.

    ``trace_budgets`` is ``(per_test, session)``. They are in the key because they CHANGE THE
    ANSWER: a budget cuts the traced baseline, and what it cut lands in the result as
    ``truncated`` and as absent ``line_coverage``. Two runs of identical code and identical tests
    under different budgets are therefore different results, and a key blind to them serves the
    tighter run's coverage to the looser one.

    That is not a stale-data nuisance, it is an unfollowable instruction: the CLI's own remedy for
    a cut trace is "raise --trace-budget (or pass 0 for unbounded) to measure them fully", and
    doing so returned the cached under-count unchanged — measured on Regenesis, 152 cuts served
    where a fresh run computes 210. The user does the one thing the tool asks for and nothing
    moves. A verdict must be keyed on everything that could have produced it.
    """
    budgets = ",".join("∞" if b is None else f"{b:g}" for b in trace_budgets)
    return (
        f"{func_key}:{_sha(func_source)}:{tests_fingerprint(tests)}:{max_per_category}:{pass_index}:{budgets}"
    )


def key_prefix(func_key: str) -> str:
    """The function's version-independent prefix, for single-valid-copy purging."""
    return f"{func_key}:"


def _to_json(result: ProfilingResult) -> dict:
    """ProfilingResult -> JSON-safe dict (enum categories -> their string values)."""
    d = asdict(result)
    for cat in d.get("per_category", []):
        cat["category"] = getattr(cat["category"], "value", cat["category"])
    return d


def _from_json(d: dict) -> ProfilingResult:
    """Inverse of :func:`_to_json`. Rebuilds the nested CategoryResult + enum so the
    reconstructed result is indistinguishable from a fresh profile (derived ``value_*``
    properties recompute from ``per_category``)."""
    d = dict(d)
    d["per_category"] = [
        CategoryResult(
            category=MutationCategory(cd["category"]),
            total=cd.get("total", 0),
            killed=cd.get("killed", 0),
            survived=cd.get("survived", 0),
            killed_by_assertion=cd.get("killed_by_assertion", 0),
            killed_by_crash=cd.get("killed_by_crash", 0),
            timed_out=cd.get("timed_out", 0),
            equivalent=cd.get("equivalent", 0),
        )
        for cd in d.get("per_category", [])
    ]
    return ProfilingResult(**d)


def _cache_path(project_root: str) -> Path:
    return Path(project_root, *_CACHE_REL)


def purge(project_root: str) -> tuple[tuple[str, ...], int]:
    """Delete THIS package's regeneratable state. Returns ``(removed_paths, reclaimed_bytes)``.

    `detective purge` used to call only Wesker's ``purge_caches``, which by construction knows
    only ``.wesker/`` — written back when Wesker owned all the state. Detective's own cache
    arrived later and nothing extended the contract, so the command purged a file that (outside
    Wesker's tests) is never written, missed the 3.1 MB one that is, and reported "a clean state"
    over it. That is not merely untidy: it removes the only escape from a stale entry, and a
    cached verdict is exactly the thing a user reaches for purge to be rid of.

    ONLY regeneratable things. ``inputs.json`` and ``equivalents.json`` are USER DATA — the
    semantic prior synthesis provably could not derive, and a human's equivalence judgement.
    Purging those would ask the person to do the one irreducible piece of work over again, which
    is the opposite of this command's purpose (see :mod:`Detective.samples` §8). Everything named
    here is rebuilt from the current code on the next run, so purging can only ever cost time.
    """
    removed: list[str] = []
    reclaimed = 0
    targets: list[Path] = [_cache_path(project_root)]
    reports = Path(project_root, ".detective", "reports")
    if reports.is_dir():
        targets += sorted(p for p in reports.iterdir() if p.is_file())
    for path in targets:
        try:
            size = path.stat().st_size
            path.unlink()
        except OSError:
            continue
        removed.append(str(path))
        reclaimed += size
    return tuple(removed), reclaimed


def load(project_root: str) -> dict:
    """Load the raw cache map (``key -> result-dict``); empty on any read failure."""
    path = _cache_path(project_root)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def get(project_root: str, key: str) -> ProfilingResult | None:
    """Cached ProfilingResult for ``key``, or None on miss / unreadable entry.

    A hit is TAGGED ``served_from_cache`` (an attribute, not a field: whether a verdict was
    replayed is this cache's business, not the shape of Wesker's measurement, and it must never
    round-trip through ``_to_json`` into a stored row). Consumers read it with ``getattr(...,
    False)``, so a fresh result is untagged and reads False.

    It exists because ``trace_truncated`` alone cannot be reported honestly. "152 tests were CUT"
    is a claim about the run that traced them — and a hit traced NOTHING; it is replaying a cut
    some earlier run took, under a machine load that no longer exists and cannot be reproduced
    (the budgets are WALL-CLOCK, so truncation is a fact about that afternoon, not about the
    suite). Rendered in the present tense on a hit, it invites the reader to fix a measurement
    this call never made — measured on a human: an hour spent re-running budgets against a
    warning that was a recording. A replayed cut and a fresh cut are different claims; say which.
    """
    entry = load(project_root).get(key)
    if entry is None:
        return None
    try:
        hit = _from_json(entry)
    except (TypeError, ValueError, KeyError):
        return None
    hit.served_from_cache = True  # type: ignore[attr-defined]
    return hit  # a schema drift is a miss, never a crash


def put(project_root: str, key: str, prefix: str, result: ProfilingResult) -> None:
    """Store ``result`` under ``key``, purging this function's stale-hash entries first
    (single-valid-copy) so the file cannot grow unbounded across edits."""
    cache = load(project_root)
    # Drop any OTHER entry for the same function/params prefix — those are prior versions
    # that can never be served again (their hash won't match current source). The suffix comes
    # from `params_suffix`, NOT an inline slice: this is the second reader of the key's field
    # layout, and the two drifting apart is exactly how a `--fast` run started evicting the
    # comprehensive entry beside it.
    same_params_suffix = params_suffix(key)
    # A row written under an OLDER key layout (fewer trailing params) is a FOSSIL: unreachable,
    # because the builder now appends a field the reader requires — and unpurgeable by the suffix
    # rule above, because with fewer fields to split, `params_suffix`'s rsplit reaches back into
    # the TESTS-HASH and yields a suffix nothing current can match. Unreachable AND unpurgeable is
    # immortal: one dead row per function per layout change, forever, in a file whose entire claim
    # is single-valid-copy. Evict on field COUNT, which is layout-agnostic and needs no list of
    # historical formats. Different BUDGETS have the same count and still coexist — they are
    # different questions, which is what `endswith` is for; a different count is not a sibling
    # question but a dead one.
    n_fields = key[len(prefix) :].count(":")
    cache = {
        k: v
        for k, v in cache.items()
        if not (
            k.startswith(prefix)
            and k != key
            and (k.endswith(same_params_suffix) or k[len(prefix) :].count(":") != n_fields)
        )
    }
    cache[key] = _to_json(result)
    path = _cache_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2))
