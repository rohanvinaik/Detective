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
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from Wesker.engine import CategoryResult, MutationCategory, ProfilingResult

_CACHE_REL = (".detective", "verdict_cache.json")


def _sha(text: str) -> str:
    """Stable 16-hex content hash — same construction as Wesker's ``_code_hash``."""
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


def cache_key(
    func_key: str, func_source: str, tests: list[Callable[..., Any]],
    max_per_category: int, pass_index: int,
) -> str:
    """The content-addressed key: identity + fn-hash + tests-hash + sampling params."""
    return (
        f"{func_key}:{_sha(func_source)}:{tests_fingerprint(tests)}"
        f":{max_per_category}:{pass_index}"
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
    """Cached ProfilingResult for ``key``, or None on miss / unreadable entry."""
    entry = load(project_root).get(key)
    if entry is None:
        return None
    try:
        return _from_json(entry)
    except (TypeError, ValueError, KeyError):
        return None  # a schema drift is a miss, never a crash


def put(project_root: str, key: str, prefix: str, result: ProfilingResult) -> None:
    """Store ``result`` under ``key``, purging this function's stale-hash entries first
    (single-valid-copy) so the file cannot grow unbounded across edits."""
    cache = load(project_root)
    # Drop any OTHER entry for the same function/params prefix — those are prior versions
    # that can never be served again (their hash won't match current source).
    same_params_suffix = key[key.rfind(":", 0, key.rfind(":")) :]  # ":max:pass"
    cache = {
        k: v
        for k, v in cache.items()
        if not (k.startswith(prefix) and k.endswith(same_params_suffix) and k != key)
    }
    cache[key] = _to_json(result)
    path = _cache_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2))
