"""Content-hashed verdict cache for ``profile()`` — the iterative-loop speedup.

A function's mutation profile is fully determined by (1) the function's own source,
(2) the source of the tests that exercise it, (3) the sampling parameters
(``max_per_category``/``pass_index`` — fast vs comprehensive vs each greedy pass give
different mutant sets), and (4) THE CODE THAT COMPUTES IT — Detective and the Wesker engine
themselves. Key the cached ``ProfilingResult`` on all four, so re-profiling an unchanged
function while OTHER functions are being edited returns instantly, while ANY edit to the
function, its tests, or the engine misses — never a stale verdict.

Content-addressed, never path-addressed: an out-of-band edit changes the hash and
invalidates the entry. Single-valid-copy: writing a new hash for a function purges its
prior entries, so ``.detective/verdict_cache.json`` stays bounded (one row per
function/params, not one per edit).
"""

from __future__ import annotations

import contextlib
import hashlib
import inspect
import json
import os
from collections.abc import Callable
from dataclasses import asdict, fields
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


def engine_fingerprint() -> str:
    """The versions of the code that PRODUCES a verdict — Detective's and Wesker's.

    In the key for the same reason the budgets are: they CHANGE THE ANSWER. Wesker generates the
    mutants, runs the baseline and attributes the kills; Detective decides which categories are
    generated at all (purity detection, `filter_categories`). An engine fix therefore does not
    merely make new verdicts better — it makes the OLD ones wrong, and a key blind to it serves
    them back as fresh, indefinitely.

    That is not hypothetical, and it is why this exists. Wesker 0.7.2 fixed a fixture reset that
    made a green suite report thousands of failing tests; the verdicts computed before it stayed in
    `.detective/verdict_cache.json`, keyed identically, and survived the upgrade. On Regenesis three
    rows held 2153 / 2138 / 2135 fabricated failures AFTER the engine that fabricated them was
    gone — a bug outliving its own fix, served silently to anyone who trusted the cache. Only a
    manual `purge` cleared them, which requires knowing to distrust it in the first place.

    A verdict must be keyed on everything that could have produced it, and the engine is not
    "everything else" — it is the thing doing the producing. Imported lazily: `Detective/__init__`
    imports this module, so a module-level import would be circular.
    """
    from Wesker import __version__ as _wesker

    from . import __version__ as _detective

    base = f"d{_detective}+w{_wesker}"
    pid = wesker_policy_id()
    # Package version alone is insufficient the day policy semantics move
    # independently of a release (issue #14): the policy id is behavior-hashed
    # upstream (Wesker fingerprints its own eligibility over an embedded
    # corpus), so a universe change invalidates these verdicts even if someone
    # forgets every other bump.
    return f"{base}+p{pid}" if pid else base


def wesker_policy_id() -> str | None:
    """The engine's versioned mutation-policy id, when the installed Wesker
    publishes one (``mutation_policy()``, Wesker > 0.11). ``None`` on older
    engines — callers must treat that as "policy unversioned", never as
    "policy unchanged". Lazily imported for the same circularity reason as
    ``engine_fingerprint``."""
    try:
        # Feature detection, not a hard import: the checker resolves against
        # the FLOOR Wesker (0.11.0, pre-policy), the runtime may see newer.
        from Wesker import mutation_policy  # type: ignore[attr-defined]
    except ImportError:
        return None
    return mutation_policy().policy_id


def cache_key(
    func_key: str,
    func_source: str,
    tests: list[Callable[..., Any]],
    max_per_category: int,
    pass_index: int,
    trace_budgets: tuple[float | None, float | None] = (None, None),
) -> str:
    """The content-addressed key: engine + identity + fn-hash + tests-hash + sampling + budgets.

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
        f"{func_key}:{engine_fingerprint()}:{_sha(func_source)}:{tests_fingerprint(tests)}"
        f":{max_per_category}:{pass_index}:{budgets}"
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
    properties recompute from ``per_category``).

    The per-category fields are read off the DATACLASS, never restated here. A hand-written
    list silently drops whatever the engine adds later, and it had: ``killed_by_exception``
    — the DECLARED-failure kills, a pin rather than a crash — was absent from it, so every
    cached readback zeroed those and a warm run reported FEWER pinned behaviours than the
    cold run that populated the cache (67 -> 64, reproducibly, on a four-branch function).
    Nothing raised. The two numbers simply disagreed, which is the one thing a verdict cache
    must never do: the whole point of it is that a replayed verdict IS the measured one.

    Unknown keys in an older row are ignored and a missing one keeps its default, so a
    shape change degrades to a partial row rather than a wrong one — and anything
    ``CategoryResult`` still rejects becomes a cache MISS in :func:`get`, which recomputes.
    """
    d = dict(d)
    cat_fields = {f.name for f in fields(CategoryResult)} - {"category"}
    d["per_category"] = [
        CategoryResult(
            category=MutationCategory(cd["category"]),
            **{k: v for k, v in cd.items() if k in cat_fields},
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

    ONLY regeneratable things. ``inputs.json``, ``equivalents.json`` and ``line_flags.json``
    are USER DATA — the semantic prior synthesis provably could not derive, a human's
    equivalence judgement, and a human's unreachability judgement.
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


def _atomic_write(path: Path, text: str) -> None:
    """Replace ``path``'s contents in ONE step, or not at all (#63).

    The cache was written with a plain `write_text`, which truncates and then fills. A crash,
    a full disk or a killed process between those leaves a HALF-WRITTEN file — and a
    half-written JSON file does not parse, so the next `load` treats it as empty and the next
    `put` writes one entry over the remains. Every other cached verdict is gone, silently, from
    an interruption that never touched them.

    The temp file lives in the SAME directory on purpose: `os.replace` is atomic only within a
    filesystem, and `/tmp` is routinely a different one. The pid suffix keeps two concurrent
    processes from writing the same temp path — it does not make the read-modify-write itself
    safe (that wants the lock #63 also asks for), but it stops them corrupting each other's
    staging file, which is the failure this function is about.
    """
    tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        with contextlib.suppress(OSError):
            tmp.unlink()


def load(project_root: str) -> dict:
    """Load the raw cache map (``key -> result-dict``); empty when there is nothing to load.

    A PARSE failure quarantines the file rather than reporting empty (#63). Reporting empty is
    what turns corruption into loss: `put` reads, adds one entry and writes the whole map back,
    so an unparseable file became a one-row file and every other verdict was destroyed by the
    next ordinary run. Moving it aside means the next write starts clean AND the evidence is
    still on disk for anyone who wants to know what happened.

    An OSError is NOT treated the same way. A file that cannot be read right now — a permission
    blip, a lock, a transient mount — may be perfectly good, and renaming it would turn a
    temporary condition into a permanent one. Unreadable degrades to a cold cache; unparseable
    is quarantined. The two are different facts and only one of them is about the contents.
    """
    path = _cache_path(project_root)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except OSError:
        return {}
    except ValueError:
        # One preserved copy, deliberately overwritten if it recurs: an unbounded set of
        # `.corrupt-N` files is its own disk problem, and the LATEST corruption is the one that
        # matches whatever the user is currently debugging.
        with contextlib.suppress(OSError):
            path.replace(path.with_name(path.name + ".corrupt"))
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
    hit.served_from_cache = True  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]
    return hit  # a schema drift is a miss, never a crash


def proof_cache_admits(gateable: bool, budget_exhausted: bool, engine_reports_gateable: bool) -> bool:
    """Whether a measurement may be STORED as replayable proof (#60, pure — pinned).

    The cache admitted on ``not budget_exhausted``, which is not the same question. A budget
    overrun is ONE way a measurement becomes invalid; the engine also refuses to gate on an
    uncontained worker, a cut phase, or a coverage depth that never reached the universe — and
    reports every one of those as ``is_gateable=False`` with ``budget_exhausted`` still False.
    Each was cached and later served as a verdict, with the fact of its invalidity dropped at
    the moment of storage, where nothing downstream could recover it.

    Wesker #19 WIDENED this. An uncontained BASELINE TRACE now clears gateability without
    touching the budget, so the exact state this check misses became more reachable — a fix
    upstream that makes a downstream proxy wronger is the argument for consuming the
    authoritative signal rather than a correlate of it.

    ``engine_reports_gateable`` is separate because absence and falsehood are different facts.
    An engine that does not publish the field has not told us the measurement is invalid; it has
    told us nothing, and refusing every insertion on that basis would disable the cache against
    any engine predating the field. The compatibility decision is therefore EXPLICIT and
    conservative in the direction that preserves behaviour: fall back to the budget proxy, which
    is what the cache already did, rather than silently assuming a capability (the assumption
    #60 forbids) or silently assuming failure.

    Gateability is ABSORBING when it IS reported: no combination of other signals restores it,
    because downstream code may diagnose a refusal but never reconstruct it as a pass.
    """
    if not engine_reports_gateable:
        return not budget_exhausted
    return gateable and not budget_exhausted


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
    # Atomic replace, not truncate-then-fill (#63). This is a read-modify-write over the WHOLE
    # map, so an interrupted write does not lose one row — it loses the file, and with the old
    # empty-on-parse-failure loader it then lost every row on the next run.
    _atomic_write(path, json.dumps(cache, indent=2))
