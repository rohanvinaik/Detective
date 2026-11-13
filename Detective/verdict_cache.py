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

References:
    §2.1, D4  docs/TEST_BASIS.md
    §14.1     docs/theory/deterministic_sicp/DETERMINISTIC_SICP.md
    §8        ARCHITECTURE.md
"""

from __future__ import annotations

import contextlib
import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict, fields
from pathlib import Path
from typing import Any

from Wesker.engine import CategoryResult, MutationCategory, ProfilingResult
from Wesker.trace_evidence import TraceEvidence

_CACHE_REL = (".detective", "verdict_cache.json")


def _sha(text: str) -> str:
    """Stable 16-hex content hash.

    Was documented as "same construction as Wesker's ``_code_hash``" — a symbol removed in
    Wesker 0.6.0 along with the per-function cache it served, which nothing outside its own
    tests ever called and which invalidated on the function's hash but NOT its tests'. This
    module is that idea done once, keyed on everything that can change the answer.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def canonical_test_identity(node_id: str, origin: str) -> str:
    """The identity a test fingerprints under, the same whichever route collected it (#100, pure — pinned).

    A test collected as a live pytest item carries its node id relative to the rootdir
    (``tests/t.py::test_x``). The same test reached through a re-collection route (a file the run wrote
    after the session collected) carries only its bare name (``test_x``). Both are the one test in the one
    file, so a fingerprint that folds the id in as given keys the writing session's final verdict apart
    from every later session's: the next run missed its own row. The identity is the test's FILE (the
    real path ``origin``) and its member path inside it (everything after the first ``::`` of a full id,
    the whole of a bare one, parametrization included). A test whose file is unknown keeps the id it has.
    """
    if not origin:
        return node_id
    member = node_id.partition("::")[2] if "::" in node_id else node_id
    return f"{origin}::{member}"


def fixture_origin_scope(path: str, installed_roots: list[str]) -> str:
    """Whether a fixture-definition file is part of the PROJECT or an installed package (#100, pure — pinned).

    "installed"  under the interpreter's standard library or site-packages: pytest's own fixtures
                 (``request``, ``tmp_path``) and distribution plugins. Their identity is already in the
                 verdict's key through the pytest regime digest (pytest version, plugin versions), and a
                 live item stamps them while a re-collected one does not, so folding the file into the
                 test's fingerprint made one test hash two ways.
    "project"    anywhere else: an edit to it can change what a test does, so it stays in the hash.
    """
    for root in installed_roots:
        if root and (path == root or path.startswith(root.rstrip("/") + "/")):
            return "installed"
    return "project"


def _installed_roots() -> list[str]:
    """The real paths of the interpreter's standard library and site-packages directories (the accessor
    for `fixture_origin_scope`)."""
    import os
    import sysconfig

    paths = sysconfig.get_paths()
    return [
        os.path.realpath(paths[k]) for k in ("stdlib", "platstdlib", "purelib", "platlib") if paths.get(k)
    ]


def _canonical_test(fn: Callable[..., Any]) -> Callable[..., Any]:
    """A stand-in for ``fn`` that Wesker's `test_fingerprint` hashes the same whichever route collected
    the test (#100): the same source, the id `canonical_test_identity` names, and only the project's
    fixture files. The accessor over the two pure decisions; it adds no decision of its own."""
    import os

    from Wesker.ci import callable_fixture_origins, callable_node_id, callable_origin, callable_source

    origin = os.path.realpath(callable_origin(fn) or "") if callable_origin(fn) else ""
    identity = canonical_test_identity(callable_node_id(fn), origin)
    roots = _installed_roots()
    kept = tuple(
        path
        for path in callable_fixture_origins(fn)
        if fixture_origin_scope(os.path.realpath(path), roots) == "project"
    )

    def stand_in() -> None:  # never called: only its attributes are read
        return None

    stand_in.__wrapped__ = callable_source(fn)  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]
    stand_in.__name__ = stand_in.__qualname__ = identity
    if origin:
        stand_in.__wesker_origin__ = origin  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]
    stand_in.__wesker_fixture_origins__ = kept  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]
    return stand_in


def tests_fingerprint(tests: list[Callable[..., Any]]) -> str:
    """Order-independent execution-context hash of the discovered TestIds (#15/#20, #100).

    Delegates each item to Wesker's routing/proof cache identity, which covers exact node ID, whole
    test module, fixture definitions, and governing conftests. Two caches answering the same
    question must not disagree about whether a fixture edit changed it; source-only here used to
    serve a stale final verdict before the correctly-invalidated routing layer could even run.

    Each test is first put in its canonical form (`_canonical_test`): the SAME file must fingerprint the
    same in the session that wrote it and in the next one, which it did not (#100): a written test's
    bare node id and its un-stamped installed-package fixtures hashed differently from the live item the
    next session collected, so a writing converge never hit its own final row.
    """
    from Wesker.trace_cache import test_fingerprint

    return _sha("\n".join(sorted(test_fingerprint(_canonical_test(t)) for t in tests)))


# The key has two readers: `cache_key` builds it and `put` re-parses it to find which entries are stale
# copies of the SAME question. The first reader compared a positional suffix (the last three fields), and
# the key grew optional tail fields (`:defer_shaped`, `:two_sign`, the regime digest) that made the
# suffix wander: a default converge's suffix had no pass field at all, so each pass evicted the others;
# a two-sign pass evicted its sibling; a two-sign put evicted the one-sign row (#100). The question a row
# answers is now read by NAME (`key_question`), never by position from the end.
_FIXED_FIELDS = 6  # engine, source hash, tests hash, max_per_category, pass_index, trace_budgets


def key_question(key: str, prefix: str) -> str:
    """The NAMED parameters that define which question a cached row answers (#100, pure — pinned).

    ``key`` is a `cache_key` and ``prefix`` its `key_prefix`. A row is identified by what it was asked,
    not by what was measured: ``max`` / ``pass`` / ``budgets`` (the trace budgets, with the ``+relation``
    mark of a per-test-kill measurement), ``shaped`` (``full`` or ``defer``), ``sign`` (``one`` or
    ``two``) and ``regime`` (the pytest regime digest, empty when unknown). The engine fingerprint, the
    function's hash and the tests' hash are deliberately NOT in it: two rows that differ only there
    answer the same question at different times, so the older is a stale copy and is evicted. Rows that
    differ in any named parameter are sibling questions (fast vs comprehensive, one pass vs the next,
    two-sign vs one-sign, deferred vs shaped) and coexist.

    Returns ``""`` for a key that does not parse under the current layout (an older layout's fossil, or
    a key outside ``prefix``): unreachable by any current request, so the caller evicts it. A
    parameter is never guessed from position: the optional tail is read marker by marker, in the order
    `cache_key` writes it, and anything left over is the regime digest or the key is unparseable.
    """
    if not prefix or not key.startswith(prefix):
        return ""
    tokens = key[len(prefix) :].split(":")
    if len(tokens) < _FIXED_FIELDS or "," not in tokens[_FIXED_FIELDS - 1]:
        return ""
    max_per_category, pass_index, budgets = tokens[_FIXED_FIELDS - 3 : _FIXED_FIELDS]
    tail = tokens[_FIXED_FIELDS:]
    shaped = "full"
    if tail[:1] == ["defer_shaped"]:
        shaped = "defer"
        tail = tail[1:]
    sign = "one"
    if tail[:1] == ["two_sign"]:
        sign = "two"
        tail = tail[1:]
    if len(tail) > 1:
        return ""
    regime = tail[0] if tail else ""
    return (
        f"max={max_per_category};pass={pass_index};budgets={budgets};"
        f"shaped={shaped};sign={sign};regime={regime}"
    )


ROUTING_REVISION = "2"


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

    # The static route decides which tests a verdict consulted; a route that follows helpers, aliases and
    # constants (#107, #77) consults tests the earlier one did not, so rows from before it are not replayed.
    base = f"d{_detective}+w{_wesker}+r{ROUTING_REVISION}"
    pid = wesker_policy_id()
    # Package version alone is insufficient the day policy semantics move
    # independently of a release (issue #14): the policy id is behavior-hashed
    # upstream (Wesker fingerprints its own eligibility over an embedded
    # corpus), so a universe change invalidates these verdicts even if someone
    # forgets every other bump.
    return f"{base}+p{pid}" if pid else base


def wesker_policy_id(two_sign: bool = False) -> str | None:
    """The engine's versioned mutation-policy id, when the installed Wesker
    publishes one (``mutation_policy()``, Wesker > 0.11). ``None`` on older
    engines — callers must treat that as "policy unversioned", never as
    "policy unchanged". Lazily imported for the same circularity reason as
    ``engine_fingerprint``.

    ``two_sign`` requests the σ(P, μ ∪ μ⁻) policy, which carries its own ``+neg`` id — so a
    two-sign certificate honestly names the universe it was measured over."""
    try:
        # Feature detection, not a hard import: the checker resolves against
        # the FLOOR Wesker (0.11.0, pre-policy), the runtime may see newer.
        from Wesker import mutation_policy  # type: ignore[attr-defined]
    except ImportError:
        return None
    # Only pass the kwarg when set, so the default one-sign path still resolves against a
    # pre-two-sign Wesker (mutation_policy() with no args); two_sign requires the newer engine.
    return (mutation_policy(two_sign=True) if two_sign else mutation_policy()).policy_id


def regime_keyed(base_key: str, regime_digest: str) -> str:
    """Fold the pytest execution-regime digest into a verdict cache key (#63, pure — pinned).

    A verdict is measured under a pytest regime — plugin set, import mode, rootdir, ini file. Two
    runs of identical code, tests, and budgets under DIFFERENT regimes are different results, and a
    key blind to the regime serves one to the other. Appending the digest keys them apart.

    An EMPTY digest leaves the key BYTE-IDENTICAL. That is the release-skew / no-session guard #60
    forbids breaking: outside a live session, or against an older Wesker that cannot report the
    regime, the regime is UNKNOWN — and an unknown regime must not silently rewrite every key and
    drop the whole warm cache. "Absent" is not "a different regime"; it is "no new information", so
    the two cases must not collapse into one truthy check.
    """
    return f"{base_key}:{regime_digest}" if regime_digest else base_key


def cache_key(
    func_key: str,
    func_source: str,
    tests: list[Callable[..., Any]],
    max_per_category: int,
    pass_index: int,
    trace_budgets: tuple[float | None, float | None] = (None, None),
    regime_digest: str = "",
    include_shaped: bool = True,
    two_sign: bool = False,
    full_matrix: bool = False,
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
    # A profile that also measured the per-test kill relation (#145) carries a field the plain one does
    # not, so the plain verdict must never answer a request for the relation, and the two must COEXIST:
    # they are different questions about one function. The mark rides in the budgets token, which
    # `key_question` reads by name, so the two are sibling questions and coexist. Off leaves the key
    # byte-identical; only a relation-bearing verdict marks it.
    if full_matrix:
        budgets += "+relation"
    engine = engine_fingerprint()
    if two_sign:
        from .capture import RETURN_OBSERVATION_POLICY

        engine += f"+o{RETURN_OBSERVATION_POLICY}"
        # The two-sign universe has its OWN policy id (`9+neg.…`), and it moves when a μ⁻ family
        # enters or leaves while the one-sign id stays put. Keyed on the one-sign id alone, a two-sign
        # run replayed the smaller universe: measured with #44's operators, `diagnose --two-sign`
        # served 10 cached behaviours where a fresh run measures 15.
        neg = wesker_policy_id(two_sign=True)
        if neg:
            engine += f"+n{neg}"
    base = (
        f"{func_key}:{engine}:{_sha(func_source)}:{tests_fingerprint(tests)}"
        f":{max_per_category}:{pass_index}:{budgets}"
    )
    # A shaped-DEFERRED run measures a strictly smaller speculative pool (widen + capture) than a full
    # one, so it is a DIFFERENT result and must never be served to an --include-shaped request — the
    # same reason `trace_budgets` are keyed (the user asks for the full measurement and the cache hands
    # back the deferred under-count). `include_shaped=True` (measure-everything, the library default)
    # leaves the key byte-identical, so no existing entry is invalidated; only a deferred run marks it.
    if not include_shaped:
        base += ":defer_shaped"
    # The two-sign contract σ(P, μ ∪ μ⁻) profiles a strictly LARGER universe (the μ⁻ OUTPUT
    # operator) than the one-sign default, so it is a different result and must never be served
    # across. two_sign=False (default) leaves the key byte-identical; only a two-sign run marks it.
    if two_sign:
        base += ":two_sign"
    # Bind the pytest regime the verdict was measured under (#63) — empty leaves the key unchanged.
    return regime_keyed(base, regime_digest)


def key_prefix(func_key: str) -> str:
    """The function's version-independent prefix, for single-valid-copy purging."""
    return f"{func_key}:"


# The observed codomain (μ⁻ Fork 2, #92) — the one Detective-side fact a verdict is computed UNDER. It is
# not a ProfilingResult field, so `asdict` drops it, yet it decided which type-conditional OUTPUT mutants
# exist; classification must regenerate exactly those. Stored beside the fields, restored as an attribute.
_CODOMAIN_KEY = "observed_return_types"
_DYNAMIC_KEY = "not_consulted_dynamic"


def _to_json(result: ProfilingResult) -> dict:
    """ProfilingResult -> JSON-safe dict (enum categories -> their string values), plus the observed
    codomain the verdict was computed under (#92).

    The codomain is carried so a warm two-sign hit hands classification the cold run's own observation.
    Without it every warm run re-captured it over the whole live collection — not-consulted tests
    executed for a value computed once already. Sorted for a deterministic row; stored only when the
    result HAS one, so a one-sign verdict's row is byte-identical to before and an EMPTY observation
    round-trips as empty rather than as absent — two facts `engine.codomain_source` keeps apart.
    """
    d = asdict(result)
    for cat in d.get("per_category", []):
        cat["category"] = getattr(cat["category"], "value", cat["category"])
    # A literal attribute name, so invariant 7's guard (`absorption.py`) sees this read.
    codomain = getattr(result, "observed_return_types", None)
    if codomain is not None:
        d[_CODOMAIN_KEY] = sorted(codomain)
    d[_DYNAMIC_KEY] = list(getattr(result, "not_consulted_dynamic", ()) or ())
    return d


def _retyped_trace_row(cd: dict) -> dict:
    """One JSON trace row -> ``TraceEvidence`` constructor kwargs, tuple fields restored (#6b, pure — pinned).

    ``asdict`` + ``json`` flatten each ``TraceEvidence`` to a dict and its ``lines`` / ``arcs``
    tuples to lists. ``ProfilingResult.admissible_arc_union`` builds a SET from ``arcs``, so a
    list-of-lists is unhashable and a WARM read raises where the COLD one did not — the round-trip
    must restore the tuple TYPES, not merely the values. Unknown keys are dropped and missing ones
    left to the dataclass default, so a shape change degrades to a partial row rather than a wrong
    one (the same contract as :func:`_from_json`).
    """
    fieldset = {f.name for f in fields(TraceEvidence)}
    row = {k: v for k, v in cd.items() if k in fieldset}
    if "lines" in row:
        row["lines"] = tuple(row["lines"])
    if "arcs" in row:
        row["arcs"] = tuple(tuple(a) for a in row["arcs"])
    return row


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
    # Popped before construction — `ProfilingResult(**d)` rejects a key it does not declare — and
    # restored below as the attribute it was (#92). A row written before the codomain was carried has
    # no key and restores none: absence, which `engine.codomain_source` re-observes, never empty.
    codomain = d.pop(_CODOMAIN_KEY, None)
    dynamic = tuple(d.pop(_DYNAMIC_KEY, ()) or ())
    cat_fields = {f.name for f in fields(CategoryResult)} - {"category"}
    d["per_category"] = [
        CategoryResult(
            category=MutationCategory(cd["category"]),
            **{k: v for k, v in cd.items() if k in cat_fields},
        )
        for cd in d.get("per_category", [])
    ]
    # `trace_evidence` is the one OTHER nested dataclass `asdict` flattened (#6b); rebuild it, or a
    # warm result carries dicts and every `admissible_*_union` property raises. Only when present, so
    # an older row without it keeps the ProfilingResult default rather than becoming an empty tuple.
    if "trace_evidence" in d:
        # A rehydrated row is REPLAYED, never fresh (§2.1, D4 repair 2): a cache HIT traced nothing
        # this session, so its rows may ORDER but never PROVE. Stamp `provenance='replayed'`
        # UNCONDITIONALLY, whatever the stored value was — a warm result that ships rows claiming they
        # were traced this session is the live replayed-positive violation the algebra forbids.
        replayed: list[TraceEvidence] = []
        for cd in d["trace_evidence"]:
            row: dict[str, Any] = {**_retyped_trace_row(cd), "provenance": "replayed"}
            replayed.append(TraceEvidence(**row))
        d["trace_evidence"] = tuple(replayed)
    # `json` also degraded these tuple-typed fields to lists; restore the declared type so a warm
    # value compares and hashes exactly like the cold one it replays (a verdict cache's whole point).
    if "collection_conflicts" in d:
        d["collection_conflicts"] = tuple(d["collection_conflicts"])
    if "proof_basis" in d:
        d["proof_basis"] = tuple(tuple(pair) for pair in d["proof_basis"])
    result = ProfilingResult(**d)
    result.not_consulted_dynamic = dynamic  # ty: ignore[unresolved-attribute]
    if codomain is not None:
        result.observed_return_types = frozenset(codomain)  # ty: ignore[unresolved-attribute]
    return result


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
    # The certificate ledger (§14.1) is NOT purged: it lives beside the suite it certifies
    # (`certificates.CERTIFICATES_REL_PATH`, versioned with the synths — founder ruling 2026-09-06).
    # It is regenerable by converge, but it is the one static fact the style layer's admissibility
    # rests on, and a purge that reset every region to `unpinned` would be the opposite of a clean
    # state. Only the cache and the reports are here.
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
    from .atomic_store import atomic_write_text

    # The one shared atomic writer (#63) — same-dir temp + os.replace, so the cache and the durable
    # user oracles all get the SAME truncate/clobber-on-interruption guarantee, not the cache alone.
    atomic_write_text(path, text)


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
    # Drop any OTHER entry that answers the SAME question about this function: those are prior versions
    # (another engine, source or tests hash) that can never be served again. The question is read by
    # NAME (`key_question`), so a sibling question coexists: a fast run beside a comprehensive one, each
    # pass of a converge beside the next, two-sign beside one-sign, deferred beside shaped (#100). A row
    # whose key does not parse under the current layout (`key_question` is empty) is a FOSSIL: unreachable
    # by any current request, and immortal unless evicted, so it goes with the stale copies.
    question = key_question(key, prefix)
    cache = {
        k: v
        for k, v in cache.items()
        if not (
            k.startswith(prefix) and k != key and ((row := key_question(k, prefix)) == "" or row == question)
        )
    }
    cache[key] = _to_json(result)
    path = _cache_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic replace, not truncate-then-fill (#63). This is a read-modify-write over the WHOLE
    # map, so an interrupted write does not lose one row — it loses the file, and with the old
    # empty-on-parse-failure loader it then lost every row on the next run.
    _atomic_write(path, json.dumps(cache, indent=2))
