"""Wesker adapter — the only module that imports the engine.

Resolves a target function, discovers its tests through Wesker's pytest-aware
collection (which binds ``@parametrize`` cases into runnable callables), profiles
it, and hands the ``ProfilingResult`` to :mod:`Detective.scope`. Everything the
rest of the package sees is a Detective type; Wesker stays behind this seam.

Mirrors Wesker's own single-function wiring (``ci.profile_function``) but calls
``run_function_profiling`` directly so scope receives a typed result object.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import importlib.util
import inspect
import os
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from types import CodeType
from typing import TYPE_CHECKING, Any

from Wesker.ci import discover_test_callables, walk_functions
from Wesker.line_coverage import executable_lines as _executable_lines
from Wesker.line_coverage import trace_line_coverage as _trace_line_coverage

from Detective.validity import MeasurementValidity, normalize_validity

if TYPE_CHECKING:
    from .parsimony import ParsimonySignals
    from .regime import TestId  # annotation-only: regime imports engine, so never import at runtime
from Wesker.engine import (  # imported, never restated — one owner for each of these numbers
    DEFAULT_TRACE_BUDGET_S as _WESKER_DEFAULT_TRACE_BUDGET_S,
)
from Wesker.engine import (
    DEFAULT_TRACE_SESSION_BUDGET_S as _WESKER_DEFAULT_TRACE_SESSION_BUDGET_S,
)
from Wesker.engine import ProfilingResult, generate_mutants, run_function_profiling
from Wesker.filter import filter_categories
from Wesker.isolation import callable_shape_hazards, fast_mode_standing, scan_source_hazards

from ._contain import budget_is_exhausted, remaining_budget_ms
from .binding import ReceiverFactory, resolve_execution, wrap_callable
from .call_sites import discover_call_site_inputs, infer_param_types
from .capture import capture_call_inputs
from .equivalence import (
    MutantVerdict,
    SourceExpr,
    SurvivorReport,
    _grid_for,
    _outcome,
    _reached_lines,
    _type_of,
    ast_grid,
    bounded_product,
    classify_survivor,
    is_expressible,
    is_scalar_type,
    structural_input_difficulty,
    structural_shape,
    synth_ast_input,
)
from .purity import is_pure as _is_pure
from .purity import world_effects
from .scope import ScopeMap, scope_from_profiling

# Fix B target-first: does the installed Wesker support the per-function seed + lazy-widen path?
# Feature-detected ONCE so an older pinned engine degrades to the full-baseline run rather than
# crashing on an unknown `widen_tests` kwarg. `LazySessionBaseline.fork` + `split_live_callables`
# arrived with it, so the profiling signature alone is a sufficient probe.
try:
    import inspect as _inspect

    _WESKER_TARGET_FIRST = "widen_tests" in _inspect.signature(run_function_profiling).parameters
except Exception:  # noqa: BLE001 — a capability probe must never break import
    _WESKER_TARGET_FIRST = False


def _resolve(
    tree: ast.Module, function: str
) -> tuple[str | None, ast.FunctionDef | ast.AsyncFunctionDef | None]:
    """Find the target function node by name (supports ``Class.method``)."""
    for qualname, node in walk_functions(tree):
        if qualname == function or qualname.split(".")[-1] == function:
            return qualname, node
    return None, None


@dataclasses.dataclass(frozen=True)
class ShadowedTarget:
    """The target file is NOT the file its own name imports.

    ``module`` resolves to ``imported``, but the analysis was pointed at ``target``. Every test
    in the suite that imports ``module`` therefore exercises a DIFFERENT FILE, so a profile of
    ``target`` measures a suite that never runs it: honest, and worthless. Reported as data — the
    CLI and the MCP word the refusal differently, and the paths are the whole message.
    """

    module: str
    target: str
    imported: str


def shadowed_target(file: str, project_root: str = ".") -> ShadowedTarget | None:
    """Is the file under analysis the file Python actually imports under its own name?

    This is the check that would have saved a whole investigation. Pointed at
    `tools/ModelAtlas/src/model_atlas/query_navigate.py`, the engine correctly reported "0 of 935
    tests cover this" — because a `.pth` aimed `model_atlas` at a DIFFERENT CHECKOUT entirely
    (`infrastructure/ModelAtlas/src`). The measurement was right; every test really did exercise
    another file. What was missing was the reason, so "0 covering tests" read as "this code is
    untested" and the honest next step — write tests — built a suite against a copy nobody runs.

    Shadowing has many causes (a stale copy in site-packages, a non-editable install, two
    checkouts of one distribution) and they all present identically. So this does not detect
    causes: it resolves the target's own module name and compares the file. Same file → fine.
    Different file → the suite is not talking about this code, and no verdict from it means
    anything.

    Resolution must happen the way THE SUITE resolves, not the way this process does, or the
    check answers a question nobody asked. A repo whose `pythonpath = ["src"]` puts its own tree
    first is NOT shadowed even when an unrelated install owns the same name — pytest never
    consults that install. Reading the suite's path config is therefore not a refinement; a check
    that skips it reports a shadow on a healthy src-layout, which is worse than no check.

    Runs in a SUBPROCESS. Resolving in-process would import parent packages, cache them in
    ``sys.modules``, and execute another checkout's module-level code inside the analyzer — to
    answer a question asked before every command. A subprocess costs one interpreter start and
    cannot contaminate the run it is guarding.

    Returns None whenever nothing can be claimed: the name is not importable at all (a
    scripts-only tree, an uninstalled package — most of this author's repos), the target is
    outside the root, or nothing resolves. A silent None is the honest answer to "not installed";
    only a resolved-and-DIFFERENT file is a shadow.
    """
    from .synthesis.oracle_light import importable_module

    root = os.path.abspath(project_root)
    full = os.path.abspath(file if os.path.isabs(file) else os.path.join(root, file))
    if not os.path.isfile(full):
        return None
    rel = os.path.relpath(full, root)
    if rel.startswith(os.pardir):
        return None  # outside the root: its dotted name is not ours to derive
    module = importable_module(rel, root)
    origin = _resolve_origin(module, root, _suite_path(root))
    if not origin or os.path.realpath(origin) == os.path.realpath(full):
        return None
    return ShadowedTarget(module=module, target=full, imported=os.path.realpath(origin))


def _suite_path(root: str) -> list[str]:
    """The sys.path entries the SUITE gets that this process does not.

    Two, because two are what this author's repos actually rely on (the rest install their
    package and need neither):

    * ``pythonpath`` under ``[tool.pytest.ini_options]`` — pytest prepends these itself;
    * ``root`` — but ONLY when a root ``conftest.py`` exists, because that is what makes pytest's
      prepend import-mode insert the rootdir. This function used to append ``root``
      unconditionally, while the line above it already stated the condition. The gap is not
      cosmetic: it asserts a ``sys.path`` entry the suite does not have, so ``shadowed_target``
      resolves the target against a path that only THIS process enjoys, finds the tree, and
      reports no shadow. Measured on Wesker's own repo, after its generated conftest was removed:
      bare ``pytest`` resolved ``import Wesker`` to site-packages and failed 10 tests, while
      ``detective regime`` called the same repo "resolves cleanly". A shadow this module could not
      see, in the engine this tool is built on.

    ``python -m pytest`` is what hides it — it puts cwd on ``sys.path`` for free, so a repo that
    only works that way looks fine until CI (or anyone) runs the bare ``pytest`` console script.
    This reads the path the SUITE gets, not the one our invocation happens to have.

    ORDER MATTERS: pytest inserts `pythonpath` at the FRONT of sys.path, so those entries win
    over the rootdir. Listing root first would resolve a src-layout to whatever sits at the root
    and mask the very shadow this looks for.

    Missing a real entry invents a shadow on a repo that resolves itself correctly; inventing one
    hides a shadow on a repo that does not. Both directions cost a verdict, so this claims exactly
    what pytest does and nothing more.
    """
    configured: list[str] = []
    config = os.path.join(root, "pyproject.toml")
    try:
        import tomllib

        with open(config, "rb") as fh:
            entries = tomllib.load(fh).get("tool", {}).get("pytest", {}).get("ini_options", {})
        configured = [os.path.join(root, p) for p in entries.get("pythonpath", []) or []]
    except (OSError, ValueError, ImportError, AttributeError):
        pass  # no config, or unreadable: `root` alone is still the honest floor
    # The rootdir is on the suite's path IFF a root conftest.py puts it there. No conftest, no
    # entry — pytest inserts the TEST file's own directory instead, and the root is reachable
    # only through an install or a declared `pythonpath`.
    anchored = [root] if os.path.isfile(os.path.join(root, "conftest.py")) else []
    # Deduped, order preserved: `pythonpath = ["."]` resolves to root, so a repo that declares it
    # would otherwise list root twice — which reads as two different entries and is just noise.
    seen: dict[str, None] = {}
    for p in [*configured, *anchored]:
        if os.path.isdir(p):
            seen.setdefault(os.path.abspath(p))
    return list(seen)


def _resolve_origin(module: str, root: str, extra_path: list[str]) -> str | None:
    """The file ``module`` resolves to, found in a subprocess so nothing here is imported."""
    script = (
        "import sys, importlib.util\n"
        f"sys.path[:0] = {extra_path!r}\n"
        "try:\n"
        f"    spec = importlib.util.find_spec({module!r})\n"
        "    sys.stdout.write((spec.origin or '') if spec else '')\n"
        "except BaseException:\n"
        "    pass\n"
    )
    try:
        # `-B`: find_spec imports parent packages, and importing writes __pycache__ into the
        # consumer's tree. This runs before EVERY command — a read-only guard that leaves
        # bytecode behind is not read-only, and it dirties repos it was only asked to look at.
        #
        # `-P`: do NOT prepend cwd to sys.path. `python -c` does that by default, and this runs
        # with `cwd=root` — so the check resolved the target the way THIS subprocess does rather
        # than the way the SUITE does, silently handing itself the one path entry whose absence
        # is the whole question. Every shadow that `sys.path.insert(0, root)` would hide was
        # therefore invisible to the guard built to find it. Measured on Wesker's own repo: the
        # subprocess resolved `Wesker` to the tree while bare `pytest` resolved it to
        # site-packages and failed 10 tests, and `regime` called it "resolves cleanly".
        # `extra_path` is the suite's path, computed by `_suite_path`; it is the ONLY thing that
        # should be on there. (3.11+, which this package requires.)
        done = subprocess.run(  # noqa: S603 — our own script, our own interpreter
            [sys.executable, "-B", "-P", "-c", script],
            check=False,
            capture_output=True,
            text=True,
            cwd=root,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() or None


def _package_qualname(full_path: str) -> tuple[str, str]:
    """(dotted module name, importable sys.path root) for ``full_path``, by walking up while an
    ``__init__.py`` exists — the first ancestor WITHOUT one is the root that belongs on ``sys.path``.
    ``src/mneme/anamnesis.py`` -> (``mneme.anamnesis``, ``.../src``). A module with no package parent
    returns its bare stem (no dot), signalling "load it by path, there is nothing to import."
    """
    full = os.path.abspath(full_path)
    d = os.path.dirname(full)
    parts = [os.path.splitext(os.path.basename(full))[0]]
    while os.path.isfile(os.path.join(d, "__init__.py")):
        parts.append(os.path.basename(d))
        d = os.path.dirname(d)
    parts.reverse()
    return ".".join(parts), d


def _purge_stale_bytecode(source_path: str) -> None:
    """Drop the cached ``.pyc`` for ``source_path`` so imports compile the file on disk.

    CPython validates a timestamp-based ``.pyc`` by source mtime truncated to WHOLE
    SECONDS plus source size, so a same-second, same-size source replacement (a
    scripted edit-run-revert loop, a git checkout or stash pop) leaves a stale cache
    the import system happily serves — and every value measured from that import
    describes a file that is no longer on disk: golden captures pin phantom
    behaviour and an apply trial "proves" a change that never happened. A number
    measured against the wrong file is worse than no number, so spend the one
    recompile and unlink the cache before anything imports the target.
    """
    try:
        os.remove(importlib.util.cache_from_source(os.path.abspath(source_path)))
    except OSError:  # no cache, already gone, or unwritable tree — import handles it
        pass


def _codes_equal(a: CodeType, b: CodeType) -> bool:
    """Structural equality of two code objects, recursing into nested code consts."""
    if (
        a.co_code != b.co_code
        or a.co_names != b.co_names
        or a.co_varnames != b.co_varnames
        or len(a.co_consts) != len(b.co_consts)
    ):
        return False
    for x, y in zip(a.co_consts, b.co_consts, strict=True):
        if isinstance(x, CodeType) != isinstance(y, CodeType):
            return False
        if isinstance(x, CodeType):
            if not _codes_equal(x, y):
                return False
        elif type(x) is not type(y) or x != y:
            return False
    return True


def _sha256_of(path: str) -> str | None:
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        return None


def _live_module_is_stale(mod: Any, real: str, qualname: str, disk_sha: str | None) -> bool:
    """True when a cached module's target no longer matches the source on disk.

    ``_purge_stale_bytecode`` guarantees every FRESH import compiles the file on
    disk, but a long-lived process (the MCP server) can already hold a module
    imported before the file changed — and no cache purge fixes a live object.

    Two tiers. A module ``_load_original`` itself imported carries the source
    hash it was imported from (stamped below), so freshness is an exact hash
    comparison — it catches ANY edit, including a module-level constant the
    target reads. A module someone else imported (pytest, the user) has no
    stamp; for those, compare the live target's ``__code__`` against the same
    function compiled from today's source — catches body edits, and honestly
    cannot see global-only edits. Only a plain function whose compiled qualname
    matches the request is verifiable that way; anything else — a decorated
    wrapper, a non-function target — reports fresh, preserving the reuse fast
    path exactly as before.
    """
    stamp = getattr(mod, "__detective_source_sha256__", None)
    if stamp is not None and disk_sha is not None:
        return stamp != disk_sha
    live = _attr_path(mod, qualname)
    live_code = getattr(live, "__code__", None)
    if live_code is None or live_code.co_qualname != qualname:
        return False
    try:
        with open(real, encoding="utf-8") as fh:
            disk = compile(fh.read(), real, "exec")
    except (OSError, SyntaxError):
        return False  # unreadable or unparsable NOW: let the import path report that
    stack = [disk]
    while stack:
        code = stack.pop()
        for const in code.co_consts:
            if isinstance(const, CodeType):
                if const.co_qualname == qualname:
                    return not _codes_equal(const, live_code)
                stack.append(const)
    return True  # the function is gone from the file on disk — definitely stale


def _load_original(full_path: str, qualname: str) -> Any | None:
    """Return the live target object from the module under test.

    Wesker seeds each mutant's namespace from ``original_func.__globals__`` so the
    mutant can resolve the module's sibling helpers, constants, and imports. Tries, in order:
    (1) the already-imported module whose ``__file__`` matches — free, and the correct package context;
    (2) an import by the module's DOTTED PACKAGE NAME (walk up while ``__init__.py`` exists, with the
    package root placed on ``sys.path``) — so a module whose top level uses a RELATIVE import
    (``from .sibling import x``) loads with a real parent package instead of raising; then only
    (3) a bare path-load, for a genuinely top-level (non-package) module.
    Returns None if all three fail (Wesker then degrades to an empty namespace).
    """
    real = os.path.abspath(full_path)
    _purge_stale_bytecode(real)  # a fresh import below must compile the file on disk
    disk_sha = _sha256_of(real)  # read once; stamped onto whatever this call imports

    def _live_matches():
        """Already-imported modules whose file IS ``real`` — cheap spellings first.

        IDENTITY, not spelling, is what this has to answer: on a case-insensitive
        filesystem (macOS default) `wesker/engine.py` and `Wesker/engine.py` are one file
        with two spellings. String equality missed the already-imported module, both
        fallback imports then died on the package's relative imports, and the target
        loaded as None — line coverage read empty ("18-line gap") while kills, which never
        consult the path, stayed green ("80/80 killed") about the same body.

        But identity costs two stats, and asking it as a single predicate paid them on
        every NON-match — once per module in the table, on every call. String equality
        answers the same question for every module imported under the caller's own
        spelling, which is all of them until a symlink or a rename is involved. So: two
        passes, not one predicate. The identity scan runs only if no spelling matched, and
        because this is a generator the caller's first accepted match ends the search
        before that pass begins. Same set of matches either way; only the order differs,
        and it now prefers the caller's own spelling.
        """
        entries = [(n, m, getattr(m, "__file__", None)) for n, m in list(sys.modules.items())]
        exact: set[str] = set()
        for name, mod, mod_file in entries:
            if mod_file and os.path.abspath(mod_file) == real:
                exact.add(name)
                yield name, mod
        for name, mod, mod_file in entries:
            if not mod_file or name in exact:
                continue
            try:
                if os.path.samefile(os.path.abspath(mod_file), real):
                    yield name, mod
            except OSError:
                continue

    for name, mod in _live_matches():
        if _live_module_is_stale(mod, real, qualname, disk_sha):
            # A long-lived process (the MCP server) can hold a module imported
            # before the file changed on disk; serving it would measure retired
            # code. Evict every alias and fall through to a fresh import.
            sys.modules.pop(name, None)  # an alias may already be gone; that is not an error
            continue
        return _attr_path(mod, qualname)

    # Import by dotted package name so module-level RELATIVE imports resolve. A parentless path-load
    # (branch 3) execs the file with no package and dies on `from .x import y`, losing every survivor to
    # "the live original could not be loaded" — the failure mode for any target inside a real package.
    dotted, pkg_root = _package_qualname(real)
    if "." in dotted:
        try:
            if pkg_root and pkg_root not in sys.path:
                sys.path.insert(0, pkg_root)
            imported = importlib.import_module(dotted)
            if disk_sha is not None:
                # Stamped on the module object so a later import can tell WHICH source it
                # holds; a dynamic attribute, absent from ModuleType's stub.
                imported.__detective_source_sha256__ = disk_sha  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]
            obj = _attr_path(imported, qualname)
            if obj is not None:
                return obj
        except Exception:
            pass

    try:
        stem = os.path.splitext(os.path.basename(full_path))[0]
        name = f"_detective_uut_{stem}"
        spec = importlib.util.spec_from_file_location(name, full_path)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod  # register before exec (dataclass/pickle resolution)
        spec.loader.exec_module(mod)
        if disk_sha is not None:
            mod.__detective_source_sha256__ = disk_sha  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]
    except Exception:
        return None
    return _attr_path(mod, qualname)


def _attr_path(obj: Any, qualname: str) -> Any | None:
    for part in qualname.split("."):
        obj = getattr(obj, part, None)
        if obj is None:
            return None
    return obj


def _activate_target_first(n_cands: int, has_caller_reacher: bool, n_unknowns: int, n_impossible: int) -> str:
    """Whether the routed partition warrants the target-first seed+widen, and why (#15, pure — pinned).

    Target-first pays off only when BOTH a plausible reacher exists to trace AND something is deferred
    to widen. A reacher is a direct/fixture candidate (``n_cands``) OR a caller-reaching test
    (``has_caller_reacher`` — #15 B: a test of a public caller reaches the private target through the
    call, though it never names it). An EMPTY candidate seed is productive when a caller-reacher
    exists: ``seed([])`` then widen the caller tests first — the exact caller-only scenario the old
    ``_cands and …`` guard sent to the full baseline.

    A LEAF ORPHAN — nothing names the target and it has no tested caller — has NO reacher, so it
    SYNTHESIZES from an empty baseline: it does NOT trace the suite ("The synthesis floor", TEST_BASIS).
    A zero-candidate routed subset honestly means no reaching test exists; the whole-suite trace the
    old code fell back to is the sandwich-thesis category error (it deadlocked converge for an hour on
    ~1000 in-process traces). Disposition-exact: a true orphan's whole suite kills ZERO of its mutants,
    identical to the empty set, so both conclude "all survive → synthesize".
      * ``"seed"``          — fork, seed the candidates (possibly none), widen the unknowns.
      * ``"synthesize"``    — leaf orphan (no reacher): seed([]), no trace, mutants survive → synthesize.
      * ``"full_baseline"`` — a reacher exists but nothing is deferred: the plain full run over the
                              candidates (which ARE the whole routed set here, so no waste).
    """
    if not (n_cands > 0 or has_caller_reacher):
        return "synthesize"  # leaf orphan — never trace the suite (the synthesis floor)
    return "seed" if (n_unknowns > 0 or n_impossible > 0) else "full_baseline"


def basis_membership(observed: str, freshness: str, admissibility: str) -> str:
    """Why one test item is, or is not, evidence about the target (#D1 §9, pure — pinned).

    The per-item warrant a ``FunctionBasis`` records — a NAMED CODE, never a bool, because the
    observed-vs-admissible distinction (§2.1) is the recurring defect and its cases must not
    collapse into one truthy check.

      observed      the reach observation ∈ {"covers", "non_reach", "unseen"}
      freshness     provenance of that observation ∈ {"fresh", "replayed"}  (§2.1)
      admissibility ∈ {"admissible", "barred", "inadmissible"}
                      "admissible"   — may enter the proof basis
                      "barred"       — baseline outcome bars it: inert / baseline-failing (§4.6)
                      "inadmissible" — observed but cannot prove: truncated / uncontained (§2.1)

    Returns the warrant:
      "proof"     fresh, admissible, covers — may discharge an obligation (enters B_t)
      "routing"   covers, but replayed OR inadmissible — orders only, never proves (§2.1)
      "barred"    covers, but its baseline outcome bars it (inert / failing) (§4.6)
      "disjoint"  a FRESH outcome-qualified non-reach — the only observation that may EXCLUDE (§2.1)
      "pending"   not observed, or a non-reach not freshly re-observed — the stratum rank is the prior
    """
    if observed == "covers":
        if admissibility == "barred":
            return "barred"
        if freshness == "replayed" or admissibility == "inadmissible":
            return "routing"
        return "proof"
    if observed == "non_reach" and freshness == "fresh":
        return "disjoint"
    return "pending"


def basis_action(admits_certificate: bool, has_open_obligations: bool) -> str:
    """The FunctionBasis terminal state, from the engine's OWN validity (§1.3, #D2 — pure, pinned).

    Consumes ``admits_certificate`` (Wesker's gateability, absorbing over every cut reason) — NEVER a
    re-derived proxy like ``bool(survivors)``, the measurement/decision gap this whole phase closes.
    A truncated or ungateable search is ``unresolved``, and a truncated search is NEVER a gap (#16,
    ``303289b``): only a search that actually EXHAUSTED its eligible unknowns may conclude one.

      "complete"    gateable, and every obligation discharged
      "gap"         gateable, exhausted, but an obligation is open — a real specification gap
      "unresolved"  not gateable / cut — the search was truncated; no negative conclusion is earned

    (``next_routing_action``'s fourth state ``trace_next`` is a widen-loop state; a FINAL result —
    the only thing this sees — never carries it.)
    """
    if not admits_certificate:
        return "unresolved"
    return "gap" if has_open_obligations else "complete"


def has_open_obligations(surviving_mutants: int, candidate_equivalents: int, uncovered_lines: int) -> bool:
    """Whether any PROOF obligation is still open (§1.2/§1.3, #D2 — pure, pinned).

    A candidate-equivalent mutant is NOT an open obligation — it is the undischargeable residue U_t
    ("modulo N unproven-equivalent"), resolved by ``detective flag``, never by grinding the suite. So
    a surviving mutant counts as open ONLY if it is killable (survivors minus candidate-equivalents);
    an uncovered executable line always counts. This is what keeps ``basis_action`` from reporting a
    ``gap`` that is really an undecidable equivalence, or a ``complete`` that still has a killable hole.
    """
    killable_survivors = surviving_mutants - candidate_equivalents
    return killable_survivors > 0 or uncovered_lines > 0


@dataclasses.dataclass(frozen=True)
class Obligations:
    """O_t = L_t ∪ A_t ∪ M_t — what a proof basis for one function must discharge (§1.2, #D1).

    L_t executable-line obligations · A_t branch arcs (both endpoints in L_t) · M_t the mutation
    dimensions. A carrier only; the counting lives where the profile is read. Reported as U_t too,
    for the undischargeable residue (candidate-equivalent mutants, flagged-unreachable lines).
    """

    lines: tuple[int, ...] = ()
    arcs: tuple[tuple[int, int], ...] = ()
    mutation_dims: tuple[str, ...] = ()


@dataclasses.dataclass(frozen=True)
class BasisWitness:
    """One admitted test and exactly what it discharges (§9, #D1).

    Named ``BasisWitness``, not ``Witness``: ``equivalence.Witness`` is the mutation-difference
    witness (a concrete input on which original and mutant differ) — a different object entirely,
    and conflating the two would be the §6 identity error in a new spelling.
    """

    test: TestId
    discharged: Obligations
    warrant: str  # basis_membership's code: proof | routing | barred (§9)
    origin: str  # intent | characterization | unattributed (§2.3 — from the write ledger, not a glob)


@dataclasses.dataclass(frozen=True)
class FunctionBasis:
    """The per-function value the subsystem produces and every reporting consumer reads (§9, #D1).

    WIRED as a REPORTING projection: `profile` attaches it (both return sites), `diagnose` carries it
    into `--json`, and `audit` rebuilds it with the real classified equivalent count. NOT YET the
    loop's governor — seed/widen termination is still `next_routing_action`'s own decision (#18),
    `converge` does not rebuild or consume this object, and `unresolved` / `excluded` stay unpopulated
    (`excluded` is vacuous post-X1: no fresh negative reaches an assembled certificate). `action` is
    the terminal state (§1.3): complete | trace_next | gap | unresolved.
    """

    target: str
    obligations: Obligations = Obligations()
    undischargeable: Obligations = Obligations()
    admitted: tuple[BasisWitness, ...] = ()
    unresolved: tuple[TestId, ...] = ()
    excluded: tuple[tuple[TestId, str], ...] = ()
    action: str = "trace_next"


def function_basis(
    result: ProfilingResult,
    validity: MeasurementValidity,
    project_root: str = ".",
    func_node: ast.AST | None = None,
    candidate_equivalent: int = 0,
) -> FunctionBasis:
    """Assemble the FunctionBasis a completed profile earned (§9, #D2/#X3 — the accessor).

    The DECISIONS it calls are pinned separately: ``basis_action`` and ``has_open_obligations``.
    This accessor holds only object handling, reusing the SAME helpers converge and audit use so the
    three cannot drift (#59, the G3 fix):

    - L_t / U_t lines rest on ``admissible_proof_coverage`` — the admissible view, never the raw
      observed union: a baseline-FAILING test's coverage may not discharge a line. Imported in the
      body because converge imports engine at module scope, so a top-level import would cycle.
    - The undischargeable line half is ``classify_missing_lines``' ``manually_unreachable`` — a line a
      human flagged unreachable is U_t, closed on the line ledger only (#9), NOT merely "uncovered".
      Skipped (no flags applied) when no ``func_node`` is supplied.
    - M_t is the APPLIED mutation universe — the ``mutant_id``s Wesker actually built, killed OR
      survived. ``kill_matrix`` keys are ``"mid: desc"`` (a key space disjoint from ``mutant_id``),
      so they are NOT used. On an in-process run the COUNT is ``≈`` (``validity.approximate`` carries
      the flag); the value-kill proof the action rests on is exact.

    A_t (arcs) is intentionally left empty: arc tracing is opt-in and off on a normal run, so an arc
    obligation would read vacuously complete. The equivalent count is CALLER-SUPPLIED — 0 at
    ``profile()`` time, where no ``SurvivorReport`` exists and a killable-looking survivor is an OPEN
    obligation; converge supplies a real count once classification has run. ``admitted`` /
    ``unresolved`` / ``excluded`` are D3/D5, empty here by design. Every result field is read
    defensively so an older engine that omits one degrades to an empty obligation, never a crash.
    """
    from .converge import admissible_proof_coverage
    from .line_flags import classify_missing_lines

    func_key = str(getattr(result, "function_key", ""))
    lines = tuple(sorted(getattr(result, "executable_lines", ()) or ()))

    proof_coverage, _line_basis = admissible_proof_coverage(result)
    covered: set[int] = {ln for cov in proof_coverage.values() for ln in cov}
    missing: list[int] = sorted(set(lines) - covered)

    # U_t line half: a missing line a human flagged unreachable is undischargeable, not open — the
    # same oracle converge (converge.py:1942) and audit (audit.py:310) apply, on the admissible view.
    manually_unreachable: list[int] = []
    if missing and func_node is not None:
        missing, manually_unreachable, _contradicted = classify_missing_lines(
            os.path.abspath(project_root), func_key, func_node, missing, covered
        )

    mutation_dims = tuple(
        sorted(
            {mid for rec in (getattr(result, "killed_records", ()) or ()) if (mid := rec.get("mutant_id"))}
            | {
                mid
                for rec in (getattr(result, "survivor_records", ()) or ())
                if (mid := rec.get("mutant_id"))
            }
        )
    )

    # Admitted witnesses (§9, #D1 wiring): each test that discharged an obligation, with its warrant
    # and ℋ/𝒢 origin — the basis B_t made per-test, so `basis_membership` and `BasisWitness` go live.
    # The admissible line owners (`proof_coverage`) and the killers ARE the proof basis. A test's
    # warrant is `basis_membership` over (covers, freshness, admissibility): freshness is the whole
    # result's replay status (§2.1 — a warm result's coverage only ROUTES, never proves), and
    # admissibility follows the line basis (an `observed` union is not admissible, so it only routes).
    # `witness_origin_of_nodeid` reads each test's recorded authorship. Bounded to ONE function's
    # covering tests (the sandwich unit), so the per-test read is a handful, not the suite.
    from .certify import witness_origin_of_nodeid  # local: certify imports engine at module scope

    # function_basis assembles from a VALIDATED profile: a fresh compute, OR a verdict-cache hit —
    # which stores ONLY gateable certificates keyed on the function AST + test sources + regime +
    # budgets (verdict_cache.proof_cache_admits). A hit therefore REPLAYS an established proof over
    # unchanged inputs and REGAINS proof status; it is NOT §2.1's trace-cache routing replay (that is
    # the coverage-ROUTING layer BELOW an assembled certificate, and it never reaches here). So the
    # coverage is proof-eligible regardless of `served_from_cache`; the ONLY routing downgrade is an
    # inadmissible (observed-union) line basis, where a baseline-failing owner may order but not prove.
    _warrant = basis_membership(
        "covers", "fresh", "admissible" if _line_basis == "admissible" else "inadmissible"
    )
    _kills: dict[str, set[str]] = {}
    for _key, _tests in (getattr(result, "kill_matrix", {}) or {}).items():
        _mid = _key.split(": ", 1)[0]  # kill_matrix keys are "mutant_id: desc" — take the id
        for _t in _tests or ():
            _kills.setdefault(_t, set()).add(_mid)
    admitted = tuple(
        BasisWitness(
            # A plain nodeid str. `TestId = NewType("TestId", str)` is runtime-identity and is
            # TYPE_CHECKING-only in engine (importing it at runtime cycles regime↔engine), so it
            # cannot be called to cast here; the value already IS the str the NewType wraps.
            test=_tid,  # ty: ignore[invalid-argument-type]
            discharged=Obligations(
                lines=tuple(sorted(int(ln) for ln in proof_coverage.get(_tid, ()))),
                mutation_dims=tuple(sorted(_kills.get(_tid, ()))),
            ),
            warrant=_warrant,
            origin=witness_origin_of_nodeid(project_root, _tid),
        )
        for _tid in sorted(set(proof_coverage) | set(_kills))
    )

    open_obligations = has_open_obligations(
        int(getattr(result, "total_survived", 0) or 0),
        candidate_equivalent,
        len(missing),
    )
    return FunctionBasis(
        target=func_key,
        obligations=Obligations(lines=lines, mutation_dims=mutation_dims),
        undischargeable=Obligations(lines=tuple(manually_unreachable)),
        admitted=admitted,
        action=basis_action(validity.admits_certificate, open_obligations),
    )


def _module_callers_of(tree: ast.Module, target_name: str) -> set[str]:
    """Names of production functions in THIS module that TRANSITIVELY reach ``target_name`` — the
    same-module backward slice (#15 B, extended to MULTI-HOP in F1). A test that names any such caller
    reaches the target through a chain of same-module calls (``resolve`` → ``_helper`` →
    ``_compute_sets``) though it never names the target, so it routes as a ``caller_reaches`` widen
    stratum rather than a bare unknown — traced BEFORE the weak signals. That promotion IS the deep
    re-rank: a multi-hop reacher moves from the weakest unknown stratum up to caller_reaches.

    Bounded to ONE module (the sandwich unit): the transitive closure is computed over THIS module's
    own functions only, by BFS backward from the target. Cross-module chains are deliberately NOT
    followed — that would be a codebase-scale scoping, the category error the sandwich thesis forbids;
    a cross-module reacher simply stays a lower stratum and the widen still reaches it.

    Positive-only and conservative: it only PROMOTES a plausible reacher, never rules one out, so a
    false promotion just traces a test earlier and a miss keeps it a lower stratum — both
    certificate-safe. The target excludes itself; dynamic dispatch / aliases / decorators are not
    resolved and stay unknown, never falsely promoted.
    """
    # This module's name-reference graph: each function's SIMPLE name → the simple names its body
    # references. Simple-name keying matches the one-hop slice's coarseness (a name collision keeps
    # the conservative, promote-only behaviour rather than inventing a false negative).
    references: dict[str, set[str]] = {}
    for qual, fnode in walk_functions(tree):
        simple = qual.split(".")[-1]
        named: set[str] = set()
        for n in ast.walk(fnode):
            if isinstance(n, ast.Name):
                named.add(n.id)
            elif isinstance(n, ast.Attribute):
                named.add(n.attr)
        references[simple] = named
    # BFS backward from the target: a function is a caller when it names any member of the current
    # frontier — distance 1 names the target, distance 2 names a distance-1 caller, and so on. The
    # `not in callers` guard makes cycles terminate; the closure is bounded by this module's function
    # count, so this is O(module), never O(repo).
    callers: set[str] = set()
    frontier = {target_name}
    while frontier:
        nxt = {
            simple
            for simple, named in references.items()
            if simple != target_name and simple not in callers and (named & frontier)
        }
        if not nxt:
            break
        callers |= nxt
        frontier = nxt
    return callers


def _attach_function_basis(result: ProfilingResult, root: str, node: ast.AST) -> ProfilingResult:
    """Attach the profile-time FunctionBasis to the result, so diagnose reads it and audit rebuilds
    it (#X4/G4 — the D-phase object goes LIVE as a reporting projection).

    The attach precedent is Detective-side state riding on the Wesker result without threading it
    through 13 callers: ``result.test_routing = _routing_counts`` (below) and ``hit.served_from_cache
    = True``. ``candidate_equivalent`` is 0 here — ``profile()`` has no ``SurvivorReport``, so a
    killable-looking survivor is an OPEN obligation and the profile-time action is honestly ``gap``.
    The REAL classified count comes from ``audit_suite`` (the ONLY consumer that runs
    ``classify_survivors`` and rebuilds the basis); ``converge`` does not yet rebuild or consume it, so
    this profile-time object stays advisory and MAY read ``gap`` where the classified result is
    complete-modulo-equivalent — converge's own verdict (``functionally_complete`` / ``complete``) is
    unaffected. ``function_basis`` is defensive (degrades, never crashes) on a real result, so it is
    attached directly — a basis is advisory, and a bug in it is a bug to fix, not a swallow (§14).
    """
    # An ATTRIBUTE, not a Wesker field (the `served_from_cache` convention, verdict_cache.get): the
    # basis is Detective's per-function object, not the shape of Wesker's measurement, and it must
    # never round-trip through the result's JSON into a stored row. Wesker cannot type it either —
    # `FunctionBasis` lives in Detective, so a field would need a back-import Wesker forbids.
    result.function_basis = function_basis(  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]
        result, normalize_validity(result), root, node
    )
    return result


def profile(
    file: str,
    function: str,
    project_root: str = ".",
    *,
    is_pure: bool | None = None,
    tests: list[Callable[..., Any]] | None = None,
    budget_ms: float | None = None,
    max_per_category: int = 0,
    pass_index: int = 0,
    extra_test_dirs: tuple[str, ...] = (),
    progress: Callable[[int, int, float], None] | None = None,
    scope_tests: bool = True,
    use_cache: bool = True,
    mutant_slice: tuple[int, int] | None = None,
    trace_budget_s: float | None = _WESKER_DEFAULT_TRACE_BUDGET_S,
    trace_progress: Callable[[int, int, float], None] | None = None,
    trace_session_budget_s: float | None = _WESKER_DEFAULT_TRACE_SESSION_BUDGET_S,
    include_shaped: bool = True,
    two_sign: bool = False,
) -> ProfilingResult:
    """Profile one function with Wesker and return the raw ``ProfilingResult``.

    When ``tests`` is None, they are discovered via Wesker's pytest-first backend
    (``discover_test_callables``), so idiomatic parametrized suites are bound and
    run — not skipped. When ``is_pure`` is None it is auto-detected (purity module),
    which lets Wesker drop STATE mutations for pure functions.

    ``extra_test_dirs`` are roots OUTSIDE ``project_root`` to also collect tests
    from — so a re-profile counts tests a caller wrote out-of-tree (converge's
    ``--write-dir`` on a scratch dir). Without it those tests are invisible and the
    kill count is a misleading 0%.
    """
    root = os.path.abspath(project_root)
    full = file if os.path.isabs(file) else os.path.join(root, file)
    # Before ANY import can touch the target — test discovery and the traced
    # baseline both import it transitively — retire a possibly-stale bytecode
    # cache, or every number below describes a file no longer on disk.
    _purge_stale_bytecode(full)
    with open(full, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=full)

    qualname, node = _resolve(tree, function)
    if node is None:
        raise LookupError(f"function {function!r} not found in {file}")

    pure = _is_pure(node, is_method="." in (qualname or "")) if is_pure is None else is_pure
    # AsyncFunctionDef has the same shape Wesker's mutators walk. two_sign opts the codomain
    # operator μ⁻ (MutationCategory.OUTPUT) into the universe — the two-sign contract
    # σ(P, μ ∪ μ⁻); off by default, so the one-sign universe and its policy id are unchanged.
    categories = filter_categories(node, pure, two_sign=two_sign)  # type: ignore[arg-type]
    rel = os.path.relpath(full, root)
    func_key = f"{rel}::{qualname}"

    if tests is None:
        func_names = [qn for qn, _ in walk_functions(tree)]
        # Honor the repo's pytest `testpaths` (the regime is the single source of truth) so a suite
        # pytest collects ONLY because testpaths names it — a bare `test.py`, say — is not invisible
        # to Wesker's static discovery and silently reported as 0%. Found dogfooding python-slugify:
        # pytest collected its 82-test `test.py`, static discovery saw zero, `slugify` read 0 pinned.
        from .regime import resolve_regime

        testpaths = resolve_regime(root).testpaths
        tests = discover_test_callables(
            root,
            rel,
            func_names,
            extra_dirs=list(extra_test_dirs) or None,
            testpaths=testpaths,
        )

    # The budgets above default to the ENGINE's, imported — not to `None`. `None` is a real
    # value meaning "unbounded", so restating the session default as None claimed every
    # library/MCP run was unbounded when the baseline had actually used the engine's 300s. The
    # key then recorded `∞` for a bounded run — a false statement about how the verdict was
    # measured — and, because the key differs, the CLI (`:50,300`) and every library caller
    # (`:50,∞`) wrote SEPARATE rows for the identical question. Neither could ever warm the
    # other: alternating the two surfaces paid the full cold trace every time, ~100x, silently,
    # and it read as "the tool is slow". One number, one owner; a default that disagrees with
    # the engine's is a second copy wearing a default's clothes.
    #
    # Content-hashed verdict cache: an unchanged function + unchanged exercising
    # tests + same sampling params + same trace budgets yield the same profile, so serve it
    # from disk instead of re-running every mutant — the re-audit-while-editing win. Keyed on
    # the function's AST dump (position-independent: editing OTHER functions never
    # invalidates this one) + the tests' sources + (max_per_category, pass_index) + the trace
    # budgets, which decide how much of the baseline was measured at all and therefore what
    # `truncated`/`line_coverage` say. Scope-invariant: scoped and full runs are proven
    # verdict-identical, so `paths`-scoped collection does NOT belong in the key.
    from . import verdict_cache

    # Which budgets actually produced this verdict? Inside a live session, NOT these arguments:
    # `_build_test_scope` prefers the session baseline and never consults them, so the suite is
    # traced under the SEAM's budgets and `truncated`/`line_coverage` follow from those. Keying on
    # the arguments instead states a number that had no bearing on the answer — and every caller
    # that does not thread budgets through (audit_suite, converge, certify, decompose_apply,
    # classify_survivors, and this package's MCP surface) then writes its result under the
    # DEFAULTS' key, so a tightly-budgeted run's under-count is served to a later default run as
    # if it were whole. Ask the session what it measured under; fall back to the arguments only
    # outside one, where they do drive the per-function trace and the key is honest again.
    # Non-forcing by construction: this must not build the baseline a cache hit exists to skip.
    try:
        from Wesker.engine import session_budgets as _session_budgets

        _measured_under = _session_budgets()
    except ImportError:  # older Wesker without the accessor — the arguments are all there is
        _measured_under = None

    # The pytest REGIME this verdict is measured under (#63): plugins / import-mode / rootdir / ini.
    # Read non-forcingly from the session holder (like the budgets above), so a warm verdict measured
    # under one regime is not served under another. Empty outside a session or on an older Wesker —
    # `cache_key` then leaves the key byte-identical, never invalidating on unknown-regime.
    try:
        from Wesker.engine import session_regime_digest as _session_regime

        _regime = _session_regime()
    except ImportError:  # older Wesker without the accessor — regime unknown, key unchanged
        _regime = ""
    # Inside a live session, an empty regime means at least one plugin/config identity was not
    # observable. Two unknown regimes must never compare equal: bypass both verdict-cache read and
    # write. Outside a session `_measured_under is None`; the historical standalone cache remains.
    _cache_allowed = use_cache and not (_measured_under is not None and not _regime)

    ck = verdict_cache.cache_key(
        func_key,
        ast.dump(node),
        tests,
        max_per_category,
        pass_index,
        _measured_under if _measured_under is not None else (trace_budget_s, trace_session_budget_s),
        _regime,
        include_shaped=include_shaped,
        two_sign=two_sign,
    )
    if _cache_allowed:
        hit = verdict_cache.get(root, ck)
        if hit is not None:
            # A cached verdict is a real ProfilingResult; attach the basis fresh (the cache serializes
            # known fields, not this Detective-side object) so a warm run reads it too (#X4).
            return _attach_function_basis(hit, root, node)

    # Pass the live target so Wesker seeds the mutant namespace from its
    # __globals__ (module helpers/constants/imports resolve inside the mutant).
    original = _load_original(full, qualname or function)

    # Fix B — TARGET-FIRST. In a live session, fork a per-function baseline holder, SEED it with the
    # tests that statically name THIS target, and hand the rest to Wesker for lazy widening on a
    # survivor (or an uncovered line). The fork means seeding this function cannot corrupt a sibling
    # profiled in the same session. A LEAF ORPHAN (nothing reaches the target) SYNTHESIZES from an
    # empty baseline instead of tracing the suite (the synthesis floor, TEST_BASIS); the full-baseline
    # path is kept only when a reacher exists but nothing is deferred. Wrapped so any failure degrades
    # to the ordinary full run: a speedup must never break a verdict.
    _seed_token = None
    _widen_tests: list[Callable[..., Any]] | None = None
    _session_baseline = None
    _routing_counts: dict[str, int] = {}
    _synthesize_orphan = False
    _impossible_ids: set[int] = set()
    if _WESKER_TARGET_FIRST and scope_tests and tests:
        from Wesker.engine import _SESSION_BASELINE as _session_baseline

        try:
            from Wesker.ci import (
                callable_origin,
                partition_live_callables,
            )
            from Wesker.trace_cache import observed_function_reach

            _holder = _session_baseline.get()
            if _holder is not None:
                _target_name = (qualname or function).split(".")[-1]
                _scoped_files = list({o for t in tests if (o := callable_origin(t))})
                _route_budgets = (
                    _measured_under
                    if _measured_under is not None
                    else (trace_budget_s, trace_session_budget_s)
                )
                _observed = observed_function_reach(
                    root,
                    {full},
                    _route_budgets,
                    _regime,
                    tests,
                    full,
                    _executable_lines(node),
                )
                # One-hop backward slice (#15 B): production functions in the target's module that
                # reach it, so a test of a public caller that never names the private target still
                # routes as a `caller_reaches` widen stratum (traced before the weak unknowns).
                _caller_names = _module_callers_of(tree, _target_name)
                _cands, _unknowns, _impossible = partition_live_callables(
                    tests,
                    _scoped_files,
                    _target_name,
                    [_target_name],
                    _observed,
                    _caller_names,
                )
                _routing_counts = {
                    "candidate": len(_cands),
                    "unknown": len(_unknowns),
                    "impossible": len(_impossible),
                    "observed": len(_observed),
                }
                # A proof-grade impossible test (observed non-reach under a complete regime) provably
                # cannot kill any of this target's mutants, so it leaves the POOL entirely (#D3, §14),
                # not merely the widen list — else it re-enters through every `_tests_for` fallback and
                # is run for nothing. Sound: a non-reacher's exclusion is a Layer-3 observation.
                _impossible_ids = {id(t) for t in _impossible}
                # A reacher must exist for an empty seed to be productive: a direct/fixture candidate,
                # or a caller-reaching test (#15 B — a test whose body names a production caller of the
                # target). A LEAF ORPHAN (no candidate, no tested caller) has no reacher, so it
                # SYNTHESIZES from an empty baseline — it NEVER traces the suite (the synthesis floor).
                # The route code travels WITH each unknown now (#D3), so read `caller_reaches` off the
                # tag instead of re-parsing every unknown's body a second time.
                _has_caller_reacher = bool(_caller_names) and any(
                    code == "caller_reaches" for _, code in _unknowns
                )
                _disposition = _activate_target_first(
                    len(_cands), _has_caller_reacher, len(_unknowns), len(_impossible)
                )
                if _disposition == "seed":
                    _seeded = _holder.fork()
                    _seeded.seed(_cands)
                    _seed_token = _session_baseline.set(_seeded)
                    # Defer shape-hazardous unknowns from the SPECULATIVE widen (shaped-defer): a
                    # non-hermetic test forces the expensive isolation path (a subprocess per mutant,
                    # a 50s live-game system test per widen step) and is almost never the minimal
                    # witness for a unit mutant. Disclosed via test_routing["deferred_shaped"];
                    # --include-shaped (include_shaped=True) forces them back in. The scoped baseline
                    # is untouched — this only trims the speculative widen of unconfirmed reachers.
                    _widen_tests, _deferred_shaped = _admit_search_pool(
                        [c for c, _ in _unknowns],  # unknowns are tagged (callable, code)
                        include_shaped,
                    )
                    # Disclose only when there IS a deferral — a zero would clutter the census and
                    # break its exact-partition consumers for the hermetic common case.
                    if _deferred_shaped:
                        _routing_counts["deferred_shaped"] = _deferred_shaped
                elif _disposition == "synthesize":
                    # Seed EMPTY (the forked baseline traces nothing) and profile against NO tests, so
                    # every mutant survives and routes to the existing synthesis pass. Disposition-exact:
                    # a true orphan's whole suite kills zero of its mutants, identical to the empty set.
                    _seeded = _holder.fork()
                    _seeded.seed([])
                    _seed_token = _session_baseline.set(_seeded)
                    _widen_tests = []
                    _synthesize_orphan = True
        except Exception:  # noqa: BLE001 — target-first is an optimisation; never fail the run
            _seed_token = None
            _widen_tests = None
    _prof_kwargs = {"widen_tests": _widen_tests} if _WESKER_TARGET_FIRST else {}
    if two_sign:
        # μ⁻ Fork 2: observe the codomain — harvest the ORIGINAL's return types under the covering
        # tests — so the two-sign profile emits the type-conditional output perturbations only where
        # they apply (→negate on a numeric return, →empty on a sized one). Guarded on two_sign so the
        # one-sign default never passes this newer kwarg to a pre-two-sign Wesker.
        from .capture import capture_return_types

        _prof_kwargs["observed_return_types"] = capture_return_types(
            original, [t for t in tests if id(t) not in _impossible_ids]
        )
    try:
        result = run_function_profiling(  # type: ignore[arg-type]
            node,
            func_key,
            categories,
            [] if _synthesize_orphan else [t for t in tests if id(t) not in _impossible_ids],
            original,
            budget_ms=budget_ms,
            max_per_category=max_per_category,
            pass_index=pass_index,
            progress=progress,
            scope_tests=scope_tests,
            mutant_slice=mutant_slice,
            trace_budget_s=trace_budget_s,
            trace_progress=trace_progress,
            trace_session_budget_s=trace_session_budget_s,
            **_prof_kwargs,
        )
    finally:
        if _seed_token is not None and _session_baseline is not None:
            _session_baseline.reset(_seed_token)
    if _routing_counts:
        result.test_routing = _routing_counts
    if two_sign:
        # Carry the observed codomain (μ⁻ Fork 2) as a Detective-side attribute — the same
        # convention as test_routing / function_basis — so classify_survivors can regenerate the
        # SAME content-addressed OUTPUT mutants (its by_id) that it must witness-search. Absent on a
        # cache hit (which returns before the capture above); classify re-captures as the fallback.
        result.observed_return_types = _prof_kwargs.get("observed_return_types")  # type: ignore[attr-defined]
    # Collection completeness (the "degrade loudly" enforcement for the test FLOOR). Tests that failed
    # to COLLECT (an import error — a torch dep, a broken conftest) are silently absent from the routed
    # suite, so a mutant only their tests would kill reads as candidate-equivalent and the COMPLETE
    # claim is unsafe. The runner captured the erroring node-ids during THIS profiling's collection
    # (Wesker `last_collection_errors`, live in this context); attach them the same way as test_routing
    # so `normalize_validity` cuts the run. Attached even when empty (collection observed, 0 errors), so
    # a clean run reads "observed, none" rather than "absent" — a cache hit returns above and stays
    # absent, correctly, because it re-collected nothing.
    from Wesker.pytest_discovery import last_collection_errors as _last_collection_errors

    result.collection_errors = _last_collection_errors()  # type: ignore[attr-defined]
    # Only cache COMPLETE runs — a budget/memory-exhausted partial must not be served
    # later as if it were the whole profile.
    # Admit on the engine's OWN validity verdict, not a correlate of it (#60). `not
    # budget_exhausted` answers a narrower question: a budget overrun is one way a measurement
    # becomes invalid, and the engine also refuses to gate on an uncontained worker or a cut
    # phase — reporting those as `is_gateable=False` with `budget_exhausted` still False. Every
    # such result was cached here and later served as a verdict, its invalidity discarded at the
    # one point downstream code could no longer recover it. Wesker #19 made that state MORE
    # reachable by clearing gateability from the baseline trace.
    # Normalized ONCE, at the adapter boundary, rather than re-read field by field here (#60).
    # This site used to do its own `getattr(result, "is_gateable", sentinel)` dance, which is the
    # same reconstruction performed in a second place — and a second place is where the two
    # answers drift. `admits_certificate` is absorbing and strictly stronger than the old
    # conjunction: a result the engine calls gateable but whose coverage depth is `cut` is now
    # refused here too, which is the "truncated depth cannot satisfy completeness" requirement.
    _validity = normalize_validity(result)
    if _cache_allowed and verdict_cache.proof_cache_admits(
        gateable=_validity.admits_certificate,
        budget_exhausted=result.budget_exhausted,
        engine_reports_gateable=_validity.engine_reports_gateable,
    ):
        verdict_cache.put(root, ck, verdict_cache.key_prefix(func_key), result)
    return _attach_function_basis(result, root, node)


@dataclasses.dataclass(frozen=True)
class TraceTier:
    """Tier 1 (issue #52): what the BASELINE TRACE alone knows — no mutation. `tests_reaching` /
    `tests_total` is the fan-in (how many discovered tests execute a line of this function); the
    line counts are the coverage; `mutant_count` is the universe size the mutation tier WOULD run,
    generated from the AST without executing anything. The cheap-honest answer `audit --plan` reports
    to decide whether the mutation budget is worth spending — every field is available before the
    first mutant, and it proves nothing about behaviour on its own."""

    function: str
    tests_reaching: int
    tests_total: int
    executable_lines: int
    covered_lines: int
    mutant_count: int


def trace_tier(
    file: str,
    function: str,
    project_root: str = ".",
    *,
    trace_progress: Callable[[int, int, float], None] | None = None,
) -> TraceTier:
    """Compute :class:`TraceTier` — the trace-only tier (issue #52), reusing the exact discovery and
    trace primitives ``profile`` does but STOPPING before mutation. No kills, no verdict; the fan-in,
    the line coverage, and the mutant-universe size, which is all the mutation budget decision needs."""
    root = os.path.abspath(project_root)
    full = file if os.path.isabs(file) else os.path.join(root, file)
    _purge_stale_bytecode(full)
    with open(full, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=full)
    qualname, node = _resolve(tree, function)
    if node is None:
        raise LookupError(f"function {function!r} not found in {file}")
    rel = os.path.relpath(full, root)
    func_names = [qn for qn, _ in walk_functions(tree)]
    # Match `profile`'s universe (§4.6, E1): scope discovery to the regime's testpaths, or the
    # trace-only tier predicts fan-in / mutant-budget over a BROADER set than the mutation tier runs —
    # `audit --plan`'s numbers would describe a different universe than the profile they inform (e.g.
    # counting `.venv*` test files a declared testpaths excludes). One of the five call sites #4.6
    # named as not threading the regime; this is the trace tier's.
    from .regime import resolve_regime

    testpaths = resolve_regime(root).testpaths
    tests = discover_test_callables(root, rel, func_names, testpaths=testpaths)
    original = _load_original(full, qualname or function)
    exec_lines = set(_executable_lines(node))  # type: ignore[arg-type]
    coverage = (
        _trace_line_coverage(tests, original, exec_lines, progress=trace_progress)
        if tests and original is not None and exec_lines
        else {}
    )
    covered = {ln for lines in coverage.values() for ln in lines}
    pure = _is_pure(node, is_method="." in (qualname or ""))
    mutant_count = sum(1 for _ in generate_mutants(node, filter_categories(node, pure)))  # type: ignore[arg-type]
    return TraceTier(
        function=f"{rel}::{qualname}",
        tests_reaching=sum(1 for lines in coverage.values() if lines),
        tests_total=len(tests),
        executable_lines=len(exec_lines),
        covered_lines=len(exec_lines & covered),
        mutant_count=mutant_count,
    )


def _count_decompose_seams(file: str, function: str, project_root: str = ".") -> int:
    """ACTIONABLE structural extraction candidates for ``function`` — single-exit, small-interface,
    AND worth applying — the STRUCTURAL decomposability signal, read from the AST alone (no tests).

    Single-sources the actionable-seam predicate with ``apply_decomposition`` (issue #33): it counts
    only candidates that also pass the wrapper / body-fraction value gate apply trials, so a diagnose
    that reports a 'clean seam' and routes to ``decompose --apply`` cannot land on a candidate apply
    then declines as low-value. Best-effort: any failure returns 0, so a structural read never breaks
    a diagnose. Paired with regime B in the CLI as the convergent flag.
    """
    try:
        from .decompose_apply import actionable_seam_count

        root = os.path.abspath(project_root)
        full = file if os.path.isabs(file) else os.path.join(root, file)
        with open(full, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=full)
        _, node = _resolve(tree, function)
        return actionable_seam_count(node) if node is not None else 0
    except Exception:  # noqa: BLE001 — a structural read must never fail a diagnose
        return 0


def _parsimony_signals(
    file: str, function: str, scope: ScopeMap, project_root: str = "."
) -> ParsimonySignals | None:
    """The SICP parsimony advisory read for ``function`` — cohesion / complexity / interface width
    (from the AST) fused with the overload / regime / seam lenses off ``scope`` (from the mutation
    profile). Advisory ONLY, never a proof, and never drives the ``DO THIS`` action. Best-effort:
    any failure returns None, so the stylistic read never breaks a diagnose — the same discipline
    as :func:`_count_decompose_seams`. Takes ``scope`` already carrying ``decompose_seams`` so the
    seam / regime lenses read the finished map."""
    try:
        from .parsimony import parsimony_from_function

        root = os.path.abspath(project_root)
        full = file if os.path.isabs(file) else os.path.join(root, file)
        with open(full, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=full)
        _, node = _resolve(tree, function)
        if node is None:
            return None
        line_span = (node.end_lineno or node.lineno) - node.lineno + 1
        return parsimony_from_function(node, scope, line_span)  # type: ignore[arg-type]
    except Exception:  # noqa: BLE001 — an advisory read must never fail a diagnose
        return None


def diagnose(
    file: str,
    function: str,
    project_root: str = ".",
    *,
    is_pure: bool | None = None,
    tests: list[Callable[..., Any]] | None = None,
    budget_ms: float | None = None,
    progress: Callable[[int, int, float], None] | None = None,
    trace_budget_s: float | None = _WESKER_DEFAULT_TRACE_BUDGET_S,
    trace_progress: Callable[[int, int, float], None] | None = None,
    trace_session_budget_s: float | None = _WESKER_DEFAULT_TRACE_SESSION_BUDGET_S,
    include_shaped: bool = True,
    two_sign: bool = False,
) -> ScopeMap:
    """Profile ``function`` and reshape the result into a behavioral-scope map.

    Always attaches the STRUCTURAL decomposition signal (``decompose_seams``) so the CLI can
    pair it with regime B — the convergent "really two things" flag.
    """
    result = profile(
        file,
        function,
        project_root,
        is_pure=is_pure,
        tests=tests,
        budget_ms=budget_ms,
        progress=progress,
        trace_budget_s=trace_budget_s,
        trace_progress=trace_progress,
        trace_session_budget_s=trace_session_budget_s,
        include_shaped=include_shaped,
        two_sign=two_sign,
    )
    scope = scope_from_profiling(result)

    from dataclasses import replace

    # Attach the structural seam count FIRST, then the parsimony read — its seam / regime lenses
    # read the finished map (§ the advisory is a superset of the seam+regime "is this >1 thing").
    scope = replace(scope, decompose_seams=_count_decompose_seams(file, function, project_root))
    return replace(scope, parsimony=_parsimony_signals(file, function, scope, project_root))


def _compile_mutant(mutant: Any, original: Callable[..., Any]) -> Callable[..., Any] | None:
    """Compile a mutant's AST into a callable, seeded with the original's globals so
    it resolves sibling helpers/constants/imports. None if it won't build.

    A μ⁻ Form-B wrapper mutant has no compilable AST — its codomain is delivered otherwise than by
    the return value (a generator's yields), so it is a RUNTIME wrapper of the original. Build it by
    calling the factory, exactly as Wesker's ``evaluate_mutant`` does, so its survivors are
    witness-searched here too rather than dropped as un-buildable."""
    if getattr(mutant, "wrapper_factory", None) is not None:
        try:
            return mutant.wrapper_factory(original) if original is not None else None
        except Exception:  # noqa: BLE001 — a wrapper that won't build simply cannot be witnessed
            return None
    try:
        module_ast = ast.Module(body=[mutant.mutated_node], type_ignores=[])
        ast.fix_missing_locations(module_ast)
        code = compile(module_ast, "<mutant>", "exec")
        namespace: dict[str, Any] = dict(getattr(original, "__globals__", None) or {})
        exec(code, namespace)  # noqa: S102  # nosec B102 — intentional: compiling an AST mutant
        name = getattr(mutant.mutated_node, "name", None)
        return namespace.get(name) if name else None
    except Exception:  # noqa: BLE001 — a mutant that won't compile simply cannot be witnessed
        return None


_SCALAR_SAMPLE: dict[str, Any] = {
    "int": 1,
    "str": "x",
    "float": 1.0,
    "bool": True,
    "tuple": (1,),
    "list": [1],
    "dict": {},
}


def _field_type_name(field: Any) -> str | None:
    """Base type name of a dataclass field, whether its annotation is a live type or
    a string (``from __future__ import annotations`` makes them strings)."""
    ann = field.type
    if isinstance(ann, str):
        return ann.split("|")[0].split("[")[0].strip() or None
    return getattr(ann, "__name__", None)


def _synth_value(type_name: str | None, namespace: dict, depth: int = 0) -> Any:
    """One representative value for a bare type NAME (used for dataclass fields,
    whose annotations arrive as strings): a scalar sample, or a dataclass instance
    with each field recursively synthesized. None when not constructible."""
    if type_name in _SCALAR_SAMPLE:
        return _SCALAR_SAMPLE[type_name]
    cls = namespace.get(type_name) if type_name else None
    if depth < 4 and isinstance(cls, type) and dataclasses.is_dataclass(cls):
        try:
            return cls(**{f.name: _synth_field(f, namespace, depth + 1) for f in dataclasses.fields(cls)})
        except Exception:  # noqa: BLE001 — an unconstructible field just yields no instance
            return None
    return None


def _synth_field(field: Any, namespace: dict, depth: int) -> Any:
    """Synthesize one dataclass field, honoring PARAMETRIZED annotations
    (``tuple[str, str]`` -> ``('x', 'x')``, ``list[int]`` -> ``[1]``, ``X | None``) by
    parsing the annotation string and routing through ``_synth_from_ann`` — not just the
    coarse base type name, which would give a bare ``(1,)`` for ``tuple[str, str]`` and
    break callers that unpack it."""
    ann = field.type
    if isinstance(ann, str):
        try:
            return _synth_from_ann(ast.parse(ann, mode="eval").body, namespace, depth)
        except (SyntaxError, ValueError):
            return _synth_value(_field_type_name(field), namespace, depth)
    return _synth_value(getattr(ann, "__name__", None), namespace, depth)


def _dataclass_field_variants(value: Any, cap: int = 4) -> list:
    """A few variants of a synthesized dataclass INSTANCE that differ in their bool and
    Optional fields — so branches that test those fields (``if x.flag``, ``if x.opt is
    not None``) are exercised, and mutants on them are distinguished. The base instance
    plus, per bool field, a flipped copy and, per Optional-typed field, a ``None`` copy;
    capped. Returns ``[value]`` unchanged when ``value`` is not a dataclass instance."""
    if not (dataclasses.is_dataclass(value) and not isinstance(value, type)):
        return [value]
    variants = [value]
    for f in dataclasses.fields(value):
        if len(variants) >= cap:
            break
        cur = getattr(value, f.name)
        ann = f.type if isinstance(f.type, str) else getattr(f.type, "__name__", "")
        if isinstance(cur, bool):
            variants.append(dataclasses.replace(value, **{f.name: not cur}))
        elif isinstance(ann, str) and "None" in ann and cur is not None:
            variants.append(dataclasses.replace(value, **{f.name: None}))
    return variants


def distinct_field_value(current: Any) -> Any:
    """A value guaranteed ``!= current`` and of a compatible shape, or ``None`` when none can
    be synthesized from the value alone (#67 B2, pure — pinned).

    The DIFFERENTIAL half of domain-object synthesis. B0 (topology) and B1 (guard) get a survivor
    REACHED; this VARIES a synthesized dataclass field so a mutation that READS that field is
    distinguished. ``_dataclass_field_variants`` already flips bool fields and nulls Optionals — this
    extends the same idea to the VALUE-bearing fields (str / int / float / list / tuple) whose specific
    content a ``serialize_rule``-style mutation reads and which the bool/None grid never moves: the §6
    band-2 (expressible-but-hard) increment, the differential ``p_field`` of Def. 11.8(vi).

    ``bool`` is tested BEFORE ``int`` because it is an ``int`` subclass and the two mean different
    fences (a flipped flag vs a boundary step); collapsing them was the recurring conflation bug. The
    string prefix and the list/tuple length change are chosen only to GUARANTEE distinctness from
    ``current`` — the down-payment B0/B1 also make (a fixed candidate that may or may not distinguish;
    the search adopts it only on a NEW kill). ``None`` return is the honest limit: a dict / set /
    nested-object field, or a ``None`` current (which the annotation-driven Optional path already
    covers), yields no value-only variant, so such a residual stays a fixture hand-back rather than a
    fabricated — and possibly cross-field-invalid — object.
    """
    if isinstance(current, bool):
        return not current
    if isinstance(current, int):
        return current + 1
    if isinstance(current, float):
        return current + 1.0
    if isinstance(current, str):
        return "x" + current
    if isinstance(current, (list, tuple)):
        rest = list(current)[1:] if current else ["x"]
        return type(current)(rest)
    return None


def _synth_from_ann(ann, namespace: dict, depth: int = 0) -> Any:
    """One representative value for an annotation NODE, recursing into container
    element types (``list[str]`` -> ``['x']``, ``dict[str, int]`` -> ``{'x': 1}``)
    and ``X | None`` unions, then falling back to name-based scalar/dataclass synth.

    An ``ast.*``-typed parameter yields a :class:`SourceExpr` (a parsed node paired
    with the source that rebuilds it), so AST-consuming functions become exercisable
    and round-trip into a runnable test."""
    ast_input = synth_ast_input(_type_of(ann))
    if ast_input is not None:
        return ast_input
    if depth < 5 and isinstance(ann, ast.Subscript) and isinstance(ann.value, ast.Name):
        container, elt = ann.value.id, ann.slice
        if container in ("dict", "Dict", "Mapping") and isinstance(elt, ast.Tuple) and len(elt.elts) == 2:
            return {
                _synth_from_ann(elt.elts[0], namespace, depth + 1): _synth_from_ann(
                    elt.elts[1], namespace, depth + 1
                )
            }
        if container in ("list", "List", "Sequence", "Iterable"):
            return [_synth_from_ann(elt, namespace, depth + 1)]
        if container in ("set", "Set", "frozenset"):
            return {_synth_from_ann(elt, namespace, depth + 1)}
        if container in ("tuple", "Tuple"):
            elts = elt.elts if isinstance(elt, ast.Tuple) else [elt]
            return tuple(
                _synth_from_ann(e, namespace, depth + 1)
                for e in elts
                if not (isinstance(e, ast.Constant) and e.value is Ellipsis)
            )
        if container == "Optional":
            return _synth_from_ann(elt, namespace, depth + 1)
    if isinstance(ann, ast.BinOp) and isinstance(ann.op, ast.BitOr):
        for side in (ann.left, ann.right):  # X | None -> synth X
            if not (isinstance(side, ast.Constant) and side.value is None):
                return _synth_from_ann(side, namespace, depth + 1)
    return _synth_value(_type_of(ann), namespace, depth)


def _literal_values(node: ast.AST) -> list:
    """The constant value(s) a comparator denotes: a bare literal, or the elements of a
    literal tuple/list/set (``x in ("a", "b")``). A non-literal yields nothing."""
    if isinstance(node, ast.Constant):
        return [node.value]
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return [e.value for e in node.elts if isinstance(e, ast.Constant)]
    return []


def _compared_literals(node: ast.AST) -> dict[str, list]:
    """Per parameter, the literal values the function's own body tests it AGAINST.

    ``if plan == "pro"`` is not a semantic prior. The domain of ``plan`` is written in the
    source — it is a fact in the symbol table, free to read. Without this an unannotated
    string-dispatch parameter fell to the int grid, every candidate died on the function's
    own ``raise ValueError(f"unknown plan: {plan}")``, and the CLI handed the user a
    ``--input`` residual for a value the AST already held. §10 counted that as the Zone-3
    domain-value boundary; it is not one. The boundary is where a value appears NOWHERE in
    the text — a valid ProfilingResult, a domain object — not where the function spells its
    own domain out in equality tests.

    Only equality/membership ops: ``>``/``>=`` describe an ORDER, not a domain, and belong
    to the BOUNDARY mutator, which already names the edge it needs.
    """
    found: dict[str, list] = {}
    for cmp_node in ast.walk(node):
        if not isinstance(cmp_node, ast.Compare) or not isinstance(cmp_node.left, ast.Name):
            continue
        name = cmp_node.left.id
        for op, comparator in zip(cmp_node.ops, cmp_node.comparators, strict=False):
            if not isinstance(op, (ast.Eq, ast.NotEq, ast.In, ast.NotIn)):
                continue
            for value in _literal_values(comparator):
                bucket = found.setdefault(name, [])
                if value not in bucket:
                    bucket.append(value)
    return found


def _neighbor_inputs(supplied: list[tuple]) -> list[tuple]:
    """±1 neighbors of each numeric coordinate of a SUPPLIED input, one coordinate at a time.

    A human supplies an input because its region matters — almost always a boundary the
    synthesized grids cannot reach — and a boundary mutant can differ only one step PAST the
    supplied edge: `quantity >= 50` mutated to `quantity == 50` agrees at the supplied
    `(50, …)` and differs at `(51, …)`. The neighbors are OURS, not the human's — they are
    fabrications, and the caller must gate them behind the same world-effects check as every
    other invented value. Bounded by |supplied| × arity × 2.
    """
    out: list[tuple] = []
    for args in supplied:
        for i, v in enumerate(args):
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                continue
            for nv in (v - 1, v + 1):
                cand = args[:i] + (nv,) + args[i + 1 :]
                if cand not in out and cand not in supplied:
                    out.append(cand)
    return out


def _ordering_edge_values(node: ast.AST) -> dict[str, list]:
    """Per parameter, the ordering-comparison edges the body tests it against — each integer
    edge bracketed by its neighbors.

    `_compared_literals` deliberately stops at equality/membership: `>= 50` describes an
    ORDER, not a domain. But the order's EDGE is still where behavior changes, and the
    witness search can only distinguish a boundary mutant if some candidate lands on each
    side of it. `quantity >= 50` mutated to `quantity == 50` differs only STRICTLY ABOVE
    the edge — a value the built-in integer grid (±3) can never reach when the edge is 50,
    so the mutant read "candidate-equivalent" while `quantity == 51` kills it. For an
    integer edge C: C-1, C, C+1 (one candidate on each side plus the edge itself, which
    brackets every one-sided mutation of the comparison); a float edge contributes itself.
    """
    found: dict[str, list] = {}
    for cmp_node in ast.walk(node):
        if not isinstance(cmp_node, ast.Compare) or not isinstance(cmp_node.left, ast.Name):
            continue
        name = cmp_node.left.id
        for op, comparator in zip(cmp_node.ops, cmp_node.comparators, strict=False):
            if not isinstance(op, (ast.Lt, ast.LtE, ast.Gt, ast.GtE)):
                continue
            for value in _literal_values(comparator):
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    continue
                neighbors = [value - 1, value, value + 1] if isinstance(value, int) else [value]
                bucket = found.setdefault(name, [])
                for v in neighbors:
                    if v not in bucket:
                        bucket.append(v)
    return found


def _input_grids(node: ast.FunctionDef | ast.AsyncFunctionDef, namespace: dict) -> list[list]:
    """Per-parameter candidate value lists: the literals the function tests the parameter
    against (its own declared domain) first, then a built-in grid for scalars; for an
    AST-typed param a GRID of real nodes; for a sequence param a set of LENGTH VARIANTS
    (empty / single / two field-variant elements); for a bare dataclass param its FIELD
    VARIANTS (bool flipped, Optional None); else the integer fallback — so functions
    taking structured inputs become exercisable and their field/length branches are all
    covered.
    """
    domain = _compared_literals(node)
    edges = _ordering_edge_values(node)
    grids: list[list] = []
    for arg in node.args.args:
        if arg.arg in ("self", "cls"):
            continue
        name = _type_of(arg.annotation)
        if name is not None and name.startswith("ast."):
            # An AST parameter needs MANY nodes, not one. Going through
            # ``_synth_from_ann`` yields a single representative, and one input can only
            # distinguish a mutant on a line it happens to reach — every other survivor
            # is then reported "equivalent but UNPROVEN", which is a fact about the
            # synthesizer masquerading as a fact about the code. Measured on Wesker's
            # ``_deletable_stmt_ids``: 64 of 68 behaviors unprovable from one sample.
            grid = list(ast_grid(name))
        elif name is not None and not is_scalar_type(name):
            variants = _seq_length_variants(arg.annotation, namespace)
            if variants is not None:
                grid = variants
            else:
                value = _synth_from_ann(arg.annotation, namespace)
                grid = _dataclass_field_variants(value) if value is not None else _grid_for(name)
        else:
            grid = _grid_for(name)
        # The function's own equality literals LEAD: they are the values it actually
        # distinguishes between, and a synthesized int can only ever reach the else/raise.
        # Ordering EDGES (with their integer neighbors) follow — the values that put a
        # candidate on each side of every boundary the body draws.
        lead = domain.get(arg.arg, []) + [
            v for v in edges.get(arg.arg, []) if v not in domain.get(arg.arg, [])
        ]
        if lead:
            grid = lead + [v for v in grid if v not in lead]
        grids.append(grid)
    return grids


def _seq_length_variants(ann: ast.AST | None, namespace: dict) -> list | None:
    """For a ``list``/``Sequence`` annotation, candidate values at lengths 0, 1, and 2 —
    the length-2 case pairing two field-variant elements so branches that depend on both
    sequence LENGTH (empty/single/2+) and on the ELEMENTS' bool/Optional fields are all
    exercised. None when the annotation is not a recognized sequence.

    ``ann`` is Optional because an UNANNOTATED parameter has ``arg.annotation is None``, and
    that is one of the "not a recognized sequence" cases this already answers — the isinstance
    below rejects it on the first line. The signature said otherwise until the callers were
    narrowed to real function nodes and the mismatch stopped being hidden behind a blanket
    ``type: ignore``."""
    if not (isinstance(ann, ast.Subscript) and isinstance(ann.value, ast.Name)):
        return None
    if ann.value.id not in ("list", "List", "Sequence", "Iterable"):
        return None
    elem = _synth_from_ann(ann.slice, namespace, depth=1)
    if elem is None:
        return None
    variants = _dataclass_field_variants(elem)
    v0 = variants[0]
    v1 = variants[1] if len(variants) > 1 else v0
    return [[], [v0], [v0, v1]]


# B0 (#15 F0): the fixed cross-referential topology library — index-valid adjacency lists a scalar
# or length-variant grid cannot construct. Each inner integer is a VALID index into the outer list
# for that list's own length, so a worklist/fixpoint target (structural_input_difficulty ==
# "deep_structural") is actually driven through its recursive states rather than skimming the
# empty/single/pair length branches _seq_length_variants already covers. Small and fixed on purpose:
# a bounded down-payment on routing the un-killed residual to synthesis (F0's tractable case), NOT
# general worklist synthesis — arbitrary depth and arbitrary cross-reference stay the open frontier.
# All are --input-expressible, so a witness found here still renders as a pasteable nested list.
_ADJACENCY_TOPOLOGIES: list[list[list[int]]] = [
    [[0]],  # one node, self-loop
    [[1], [0]],  # two-node cycle
    [[1], [2], []],  # three-node chain, terminating
    [[], []],  # two nodes, no edges (disconnected)
    [[1, 2], [2], []],  # branch with a shared successor
]

_NESTED_SEQ = ("list", "List", "Sequence", "Iterable", "tuple", "Tuple")


def _is_nested_int_container(ann: ast.AST | None) -> bool:
    """True for a ``list[list[int]]`` / ``list[tuple[int, ...]]`` style annotation — a sequence whose
    element is itself a sequence of ``int``. Restricted to an ``int`` leaf on purpose: the topology
    trick is that the inner values are valid INDICES back into the outer list, so a non-int leaf is
    not indexable that way and stays ordinary synthesis's job.
    """

    def _seq_over(n: ast.AST | None) -> ast.AST | None:
        if isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name) and n.value.id in _NESTED_SEQ:
            inner = n.slice
            # tuple[X, ...] carries an ast.Tuple slice; the element type is its first entry.
            if isinstance(inner, ast.Tuple) and inner.elts:
                inner = inner.elts[0]
            return inner
        return None

    inner = _seq_over(ann)
    leaf = _seq_over(inner)
    return isinstance(leaf, ast.Name) and leaf.id == "int"


def _nested_int_container_positions(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[int]:
    """Indices — in the SAME ``self``/``cls``-skipped order :func:`_input_grids` builds its grids in —
    of positional parameters annotated as a nested integer container: the slots an adjacency topology
    fills, aligned so the caller can swap them into the grid list position-for-position.
    """
    positions: list[int] = []
    idx = 0
    for arg in node.args.args:
        if arg.arg in ("self", "cls"):
            continue
        if _is_nested_int_container(arg.annotation):
            positions.append(idx)
        idx += 1
    return positions


def _structural_topology_inputs(node: ast.FunctionDef | ast.AsyncFunctionDef, namespace: dict) -> list[tuple]:
    """B0 (#15 F0): full positional-argument tuples that place a cross-referential adjacency topology
    in every nested-int-container slot and the ordinary synthesized grid in every other, for a
    ``deep_structural`` (worklist) target. Empty when the target has no such parameter.

    These are OUR fabrications, so the caller applies the same world-effects gate the rest of the
    fabricated pool obeys; the search is positive-only, so a topology that distinguishes a survivor
    upgrades it to a proven KILL and one that does not leaves the residual exactly as it was.
    """
    positions = _nested_int_container_positions(node)
    if not positions:
        return []
    grids = _input_grids(node, namespace)
    for i in positions:
        if i < len(grids):
            grids[i] = list(_ADJACENCY_TOPOLOGIES)
    return bounded_product(grids)


def representative_site(node: ast.FunctionDef | ast.AsyncFunctionDef, namespace: dict) -> list[dict]:
    """Golden call sites: a base site (numeric/unannotated params get 1, 2, 3… for
    order-distinction, other scalars a sample value, container/dataclass params a
    synthesized value), PLUS a variant site for each param whose domain has genuinely
    distinct shapes — a length-2 value for a sequence param, each further grid node for
    an AST param. Golden capture pins the output at each; the minimize/audit pass then
    keeps only the sites that uniquely cover a kill or a line — so the suite stays
    minimal without a per-grid explosion.

    AST PARAMS NEED VARIANTS FOR THE SAME REASON SEQUENCES DO. A sequence param's
    length-2 variant exists because empty/single/many are different branches; an AST
    param's node shapes are different branches in exactly the same way (a tuple-unpack
    target, an except handler, a ``*args`` signature), and one representative reaches
    none of them. Without this the witness search could PROVE a mutant killable while
    the written tests never executed the line it lives on — measured on Wesker's
    ``_deletable_stmt_ids``: 29 mutants proven killable, a 22-line gap that would not
    close, and 11/68 killed no matter how rich the grid got, because generation drew
    one input while classification drew eight.
    """
    base: list = []
    variant_sites: list[tuple[int, Any]] = []  # (arg index, alternative value for it)
    n = 1
    for arg in node.args.args:
        if arg.arg in ("self", "cls"):
            continue
        name = _type_of(arg.annotation)
        if name in (None, "int"):
            base.append(repr(n))
            n += 1
        elif is_scalar_type(name):
            base.append(repr(_grid_for(name)[-1]))
        elif name is not None and name.startswith("ast."):
            grid = ast_grid(name)
            if not grid:
                base.append(repr(n))
                n += 1
                continue
            # A SourceExpr passes through as the OBJECT (eval_call_site skips
            # non-strings), so it reaches capture intact and renders as its
            # constructor source.
            base.append(grid[0])
            variant_sites.extend((len(base) - 1, alt) for alt in grid[1:])
        else:
            value = _synth_from_ann(arg.annotation, namespace)
            base.append(value if isinstance(value, SourceExpr) else repr(value if value is not None else n))
            variants = _seq_length_variants(arg.annotation, namespace)
            if variants is not None and variants[-1]:  # the [elem, elem] length-2 variant
                variant_sites.append((len(base) - 1, repr(variants[-1])))
    sites = [{"positional_args": base}]
    for idx, alt in variant_sites:
        variant = list(base)
        variant[idx] = alt
        sites.append({"positional_args": variant})
    return sites


def _unreachable_inputs_note(
    node: ast.AST,
    qualname: str,
    inferred: dict[str, str] | None = None,
    effects: tuple[str, ...] = (),
) -> str:
    """Actionable Zone-3 message when synthesized inputs can't exercise a function.

    ``effects`` changes the REASON, and the reason is the whole message. When the function
    escapes the process we did not try the grids and find them wanting — we refused to invent a
    value at all. Saying "every candidate raised" there would be a plain lie about our own
    behaviour, and it would send someone hunting for a type problem that does not exist.

    The opaque "candidate inputs don't exercise this function" leaves the user with
    nothing to do. Per the three-zone contract, an un-exercisable function is a
    handoff, not a dead end: name each parameter and its declared type (``unannotated``
    when the signature omits it, or the call-site-inferred type when we recovered one)
    and say exactly how to supply a real sample, so the user can resolve the tiny
    fraction the deterministic layer provably cannot.
    """
    inferred = inferred or {}
    params: list[str] = []
    args = getattr(node, "args", None)
    for a in getattr(args, "args", []) or []:
        if a.arg in ("self", "cls"):
            continue
        if a.annotation is not None:
            ann = ast.unparse(a.annotation)
        elif a.arg in inferred:
            ann = f"{inferred[a.arg]} (inferred from call site)"
        else:
            ann = "unannotated"
        params.append(f"{a.arg}: {ann}")
    sig = ", ".join(params) if params else "no positional params"
    if effects:
        return (
            f"{qualname}({sig}) {effects[0]}, so NO input was invented for it — a fabricated "
            "value for a function that escapes this process is not a guess, it is damage. "
            "Only a real sample can classify these: supply an --input, or add a test that "
            "calls it (its arguments are then evidence, and are used)"
        )
    return (
        f"synthesized inputs don't exercise {qualname}({sig}) — every candidate raised; "
        "provide a real sample (pass call_site_inputs to converge, or add a literal "
        "call site) so killability can be determined"
    )


def _resolve_class(type_name: str, project_root: str) -> type | None:
    """Resolve a type NAME (``ScopeMap``; ``list[X]`` -> ``list``, so pass a base name)
    to its class object by finding the ``class`` definition in the repo and importing that
    module. Synthesis then runs in the DEFINING module's namespace, where the class AND its
    sibling nested types resolve — the target's own module usually does not import them, so
    synthesizing there returns None. None if the class is not found or not importable."""
    base = type_name.split("[")[0].split("|")[0].strip()
    if not base.isidentifier():
        return None
    root = os.path.abspath(project_root)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != "__pycache__"]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            path = os.path.join(dirpath, fn)
            try:
                with open(path, encoding="utf-8") as fh:
                    src = fh.read()
            except OSError:
                continue
            if f"class {base}" not in src:  # cheap prefilter before parsing
                continue
            try:
                tree = ast.parse(src)
            except SyntaxError:
                continue
            if any(isinstance(n, ast.ClassDef) and n.name == base for n in tree.body):
                obj = _load_original(path, base)
                if isinstance(obj, type):
                    return obj
    return None


def _synth_inferred_inputs(
    node: ast.AST, qualname: str, project_root: str, namespace: dict
) -> tuple[list[tuple], dict[str, str]]:
    """One correlated input tuple for a function whose UNANNOTATED params have types
    recoverable from call sites ([[infer_param_types]]). Each inferred type is resolved to
    its defining module and synthesized there (so nested dataclass / ``list[Dataclass]``
    fields build correctly); an annotated param synthesizes from its annotation; anything
    left over gets an integer. Returns ``([tuple] or [], inferred_types)`` — the tuple
    exercises the formatter/domain-object functions the per-parameter integer grids cannot,
    and the types feed the actionable note even when a value cannot be built.
    """
    args = [a for a in getattr(getattr(node, "args", None), "args", []) or [] if a.arg not in ("self", "cls")]
    inferred = infer_param_types(qualname, project_root, [a.arg for a in args])
    if not inferred:
        return [], {}
    values: list[Any] = []
    for a in args:
        if a.annotation is not None:
            values.append(_synth_from_ann(a.annotation, namespace))
        elif a.arg in inferred:
            cls = _resolve_class(inferred[a.arg], project_root)
            mod = sys.modules.get(cls.__module__) if cls is not None else None
            value = _synth_value(cls.__name__, vars(mod)) if (cls is not None and mod is not None) else None
            if value is None:
                return [], inferred  # type known (for the note) but no value could be built
            values.append(value)
        else:
            values.append(1)
    return [tuple(values)], inferred


def _safely_fresh(candidate: tuple, pool: Sequence[tuple]) -> bool:
    """True when ``candidate`` is not already in ``pool`` — surviving hostile ``__eq__``.

    Membership runs ``==`` between CAPTURED user values and pool inputs; a captured object
    whose comparison raises (a test double asserting "never compare me") took down the whole
    converge run at the dedup step. A raising comparison means "not provably a duplicate":
    keep the candidate — the worst case is one redundant classification pass, not a crash.
    """
    try:
        return candidate not in pool
    except Exception:  # noqa: BLE001 — any raising __eq__/__contains__ counts as "fresh"
        return True


def rescue_disposition(expressible: bool, rescuable: bool, has_inexpressible_witness: bool) -> str:
    """Whether the pool-poverty rescue — an expensive capture that RUNS the covering tests — is
    worth running, or the run should terminate early and ask for ``--input`` (pure — pinned).

    The rescue's value is STRUCTURED inputs a grid cannot fabricate ("a domain-object parameter no
    grid can build", "a witness only a test can build"). When the function is grid-FRIENDLY —
    ``exercising`` is a literal input (``expressible``) and no killable witness is inexpressible —
    captures cannot supply what the grid could not, so running the whole suite to hunt a
    distinguishing literal is futile (it burned the full --deadline on ARC-scale suites). The honest,
    fast path is to ask the human for the value only they know — the same "supply what only you know"
    contract as elsewhere. A named code, never a bool:

      "nothing"         not rescuable — no residual to rescue
      "skip_ask_input"  grid-friendly + no inexpressible witness — skip the capture, ask for --input
      "run"             a non-literal (structured/object) input is in play — the capture may help
    """
    if not rescuable:
        return "nothing"
    if expressible and not has_inexpressible_witness:
        return "skip_ask_input"
    return "run"


def structural_retry_gate(
    is_deep_structural: bool,
    has_persisting_candidate: bool,
    has_effects: bool,
    wall_exhausted: bool,
) -> str:
    """B0 (#15 F0, pure — pinned): whether to retry classification over the cross-referential
    topology library after the first pass (and any capture-rescue) still leaves a candidate-
    equivalent survivor on a ``deep_structural`` (worklist/fixpoint) target.

    The topologies are FABRICATED inputs, so the retry obeys the same two gates the fabricated grid
    pool does: never on an effectful target — a fabricated adjacency list is damage, not a guess —
    and never once the aggregate wall is gone (#31: a cut run keeps its first-pass verdicts rather
    than starting a search it cannot finish). And there is nothing to gain when no candidate-
    equivalent residual remains to upgrade. A named code, never a bool:

      "skip"  not deep_structural, nothing left to upgrade, effectful, or wall exhausted
      "run"   a worklist target still has a candidate-equivalent residual and the search is safe
    """
    if not is_deep_structural:
        return "skip"
    if not has_persisting_candidate:
        return "skip"
    if has_effects:
        return "skip"
    if wall_exhausted:
        return "skip"
    return "run"


def guard_comparison_target(op: str, const: int) -> int | None:
    """The integer a variable must take to satisfy a simple comparison guard ``<var> OP const``
    (B1 guard-directed synthesis, #15 F0 — pure, pinned).

    A reachability-identified survivor sits behind a branch the grid never entered; the branch's OWN
    guard names the reaching condition, so for a comparison against a constant we synthesize the single
    adjacent integer that satisfies it. For ``len(<var>) OP const`` the same target is the LENGTH the
    container must have (the caller builds a list of it). None when the operator is not one a single
    adjacent integer satisfies — the honest limit that keeps this bounded, leaving the survivor a caveat
    rather than a fabricated kill.

      ">": const+1   "<": const-1   ">=": const   "<=": const   "==": const   "!=": const+1
    """
    if op == ">":
        return const + 1
    if op == "<":
        return const - 1
    if op in (">=", "==", "<="):
        return const
    if op == "!=":
        return const + 1
    return None


def guard_retry_gate(has_candidate_equivalent: bool, has_effects: bool, wall_exhausted: bool) -> str:
    """Whether to run the B1 guard-directed retry after the first pass (and B0) left a candidate-
    equivalent (#15 F0, pure — pinned). A named code, never a bool.

    Like B0's gate, the synthesized inputs are OUR fabrications, so the retry obeys the same two gates
    the fabricated grid pool does: never on an effectful target — a guard-satisfying value CALLS the
    target, damage not a guess — and never once the aggregate wall is gone (#31: a cut run keeps its
    first-pass verdicts). And there is nothing to gain when no candidate-equivalent remains to upgrade.

      "run"   a candidate-equivalent remains and the search is safe
      "skip"  nothing left to upgrade, effectful, or wall exhausted
    """
    if not has_candidate_equivalent:
        return "skip"
    if has_effects:
        return "skip"
    if wall_exhausted:
        return "skip"
    return "run"


def domain_variant_retry_gate(has_candidate_equivalent: bool, has_effects: bool, wall_exhausted: bool) -> str:
    """Whether to run the B2 domain-object differential retry after B0/B1 left a candidate-equivalent
    (#67, pure — pinned). A named code, never a bool.

    Same three gates every fabricated-pool retry obeys, kept a SEPARATE symbol from B1's
    ``guard_retry_gate`` so the B2 stage is independently tunable and independently disablable in a
    test (the B0/B1 precedent: each active-search stage owns its gate). The synthesized dataclass
    variants CALL the target, so never on an effectful one (damage, not a guess); never once the
    aggregate wall is gone (#31: a cut run keeps its first-pass verdicts); nothing to gain when no
    candidate-equivalent remains to upgrade.

      "run"   a candidate-equivalent remains and the search is safe
      "skip"  nothing left to upgrade, effectful, or wall exhausted
    """
    if not has_candidate_equivalent:
        return "skip"
    if has_effects:
        return "skip"
    if wall_exhausted:
        return "skip"
    return "run"


_GUARD_OPS: dict[type, str] = {
    ast.Gt: ">",
    ast.Lt: "<",
    ast.GtE: ">=",
    ast.LtE: "<=",
    ast.Eq: "==",
    ast.NotEq: "!=",
}


def _guard_pins(node: ast.AST, lineno: int, params: list[str]) -> dict[int, Any]:
    """B1: {param-index -> a value that satisfies the SIMPLE comparison guard gating ``lineno``}.

    Handles ``<param> OP const`` (the param, an int, takes the adjacent value) and ``len(<param>) OP
    const`` (the param, a list, takes ``[1..target]`` — a non-trivial list of the target length, so a
    value-mutant on its elements is distinguishable, not zeroed out). Only the branch tests that ENCLOSE
    ``lineno`` (``if``/``while`` whose body spans it), matching :func:`_line_guards`. Anything else — a
    boolean op, a call, a non-int constant, a comparison against a non-param — is left un-pinned: the
    honest bound that keeps a survivor a caveat rather than a fabricated kill.
    """

    def _spans(stmts: list) -> bool:
        return any(
            getattr(s, "lineno", 1 << 30) <= lineno <= getattr(s, "end_lineno", getattr(s, "lineno", -1))
            for s in stmts
        )

    pins: dict[int, Any] = {}
    for n in ast.walk(node):
        body = getattr(n, "body", None)
        if not (isinstance(n, (ast.If, ast.While)) and body and _spans(body)):
            continue
        test = n.test
        if not (isinstance(test, ast.Compare) and len(test.ops) == 1 and len(test.comparators) == 1):
            continue
        op = _GUARD_OPS.get(type(test.ops[0]))
        right = test.comparators[0]
        if op is None or not (isinstance(right, ast.Constant) and isinstance(right.value, int)):
            continue
        left = test.left
        target = guard_comparison_target(op, right.value)
        if target is None:
            continue
        if isinstance(left, ast.Name) and left.id in params:
            pins[params.index(left.id)] = target
        elif (
            isinstance(left, ast.Call)
            and isinstance(left.func, ast.Name)
            and left.func.id == "len"
            and len(left.args) == 1
            and isinstance(left.args[0], ast.Name)
            and left.args[0].id in params
            and target >= 0
        ):
            pins[params.index(left.args[0].id)] = list(range(1, target + 1))
    return pins


def _guard_directed_inputs(
    node: ast.FunctionDef | ast.AsyncFunctionDef, namespace: dict, target_lines: frozenset[int]
) -> list[tuple]:
    """B1 (#15 F0): full positional-arg tuples that satisfy the simple comparison guard gating each
    target line, so a reachability-identified survivor behind ``len(x) > 5`` / ``x == 42`` is actually
    REACHED. Each tuple pins the guarded parameter(s) to a satisfying value and takes the ordinary grid
    default elsewhere. Empty when no target line has a synthesizable guard — the honest limit.

    These are OUR fabrications, so the caller applies the same world-effects gate the rest of the
    fabricated pool obeys; the search is positive-only, so an input that distinguishes a survivor
    upgrades it to a proven KILL and one that does not leaves the residual exactly as it was.
    """
    params = [
        a.arg for a in getattr(getattr(node, "args", None), "args", []) or [] if a.arg not in ("self", "cls")
    ]
    if not params:
        return []
    grids = _input_grids(node, namespace)
    base = [g[0] if g else 0 for g in grids]
    seen: set[tuple] = set()
    out: list[tuple] = []
    for ln in target_lines:
        pins = _guard_pins(node, ln, params)
        if not pins:
            continue
        args = list(base)
        for i, v in pins.items():
            if i < len(args):
                args[i] = v
        try:
            key = tuple(tuple(a) if isinstance(a, list) else a for a in args)
        except TypeError:
            key = None
        if key is not None and key in seen:
            continue
        if key is not None:
            seen.add(key)
        out.append(tuple(args))
    return out


def _as_domain_source(instance: Any) -> SourceExpr | None:
    """A synthesized dataclass INSTANCE as a :class:`SourceExpr` — the live value plus the constructor
    ``repr`` and the import that names its class — so a B2 witness renders as ``Cls(field=...)`` (#67 B2).

    ``None`` when any field value is not itself expressible (a nested object / built state). A standard
    dataclass ``repr`` IS its own constructor source, but only the instance's OWN class import is
    emitted, so a nested-object field would render an unresolvable name. That case is the honest
    residual — a fixture hand-back — not something to fabricate an incomplete render for.
    """
    if not (dataclasses.is_dataclass(instance) and not isinstance(instance, type)):
        return None
    if not all(is_expressible(getattr(instance, f.name)) for f in dataclasses.fields(instance)):
        return None
    cls = type(instance)
    top = cls.__qualname__.split(".")[0]  # dataclass repr uses __qualname__; import its head name
    imports = () if cls.__module__ in ("builtins", None) else (f"from {cls.__module__} import {top}",)
    return SourceExpr(value=instance, expr=repr(instance), imports=imports)


def _domain_variants(value: Any, cap: int = 4) -> list | None:
    """SourceExpr variants of a synthesized dataclass instance that differ in ONE value-bearing field
    each (via :func:`distinct_field_value`), plus the base — or ``None`` when ``value`` is not a
    renderable dataclass instance (#67 B2). This is the differential grid B0's topologies and B1's
    scalar guards do not build: the field a ``serialize_rule``-style mutation reads is varied so the
    mutation is distinguished. Capped, like ``_dataclass_field_variants`` (which varies only bool /
    Optional fields — this extends the same idea to str / int / float / list / tuple content).
    """
    base = _as_domain_source(value)
    if base is None:
        return None
    out = [base]
    for f in dataclasses.fields(value):
        if len(out) >= cap:
            break
        alt = distinct_field_value(getattr(value, f.name))
        if alt is None:
            continue
        try:
            varied = _as_domain_source(dataclasses.replace(value, **{f.name: alt}))
        except Exception:  # noqa: BLE001 — a replace a field validator rejects just yields no variant
            varied = None
        if varied is not None:
            out.append(varied)
    return out


def _domain_object_variant_inputs(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    namespace: dict,
    qualname: str,
    project_root: str,
) -> list[tuple]:
    """B2 (#67): full positional-arg tuples that place FIELD-VARIED dataclass instances in every
    domain-object slot and the ordinary grid elsewhere, so a candidate-equivalent behind a
    domain-object parameter — one whose VALUE-bearing field a mutation reads — is distinguished.

    The differential generalization of B0 (nested-int topologies) and B1 (scalar guards): synthesis
    already REACHES the object (``_synth_from_ann`` from an annotation, or ``_synth_value`` from a
    call-site-inferred type — the ``serialize_rule`` case is unannotated), so this VARIES one field
    per variant and lets the search find the differentiator. Each variant is a SourceExpr constructor,
    so a kill renders as ``Cls(field=...)`` — never an ``--input`` literal (a constructor is outside
    the allowlist), never a flag. Empty when no parameter resolves to a renderable dataclass — the
    honest limit (a non-introspectable or cross-field-invariant object stays a fixture hand-back).

    OUR fabrications, so the caller applies the same world-effects gate the fabricated pool obeys;
    positive-only, so a variant that distinguishes a survivor upgrades it to a proven KILL and one
    that does not leaves the residual exactly as it was.
    """
    args = [a for a in getattr(getattr(node, "args", None), "args", []) or [] if a.arg not in ("self", "cls")]
    if not args:
        return []
    grids = _input_grids(node, namespace)
    inferred = infer_param_types(qualname, project_root, [a.arg for a in args])
    replaced = False
    for i, a in enumerate(args):
        if i >= len(grids):
            continue
        if a.annotation is not None:
            value = _synth_from_ann(a.annotation, namespace)
        elif a.arg in inferred:
            cls = _resolve_class(inferred[a.arg], project_root)
            mod = sys.modules.get(cls.__module__) if cls is not None else None
            value = _synth_value(cls.__name__, vars(mod)) if (cls is not None and mod is not None) else None
        else:
            value = None
        variants = _domain_variants(value) if value is not None else None
        if variants is not None:
            grids[i] = variants
            replaced = True
    if not replaced:
        return []
    return bounded_product(grids)


def search_pool_admission(is_hermetic: bool, include_shaped: bool) -> str:
    """Whether a candidate test enters the SPECULATIVE widen pool — the converge/diagnose
    kill-measurement that speculatively traces unconfirmed reachers (shaped-defer, pure — pinned).

    A shape-hazardous test (non-hermetic per ``fast_mode_standing`` — it spawns a subprocess, starts
    a thread, signals, or needs a custom collector) forces the expensive isolation path: ONE such
    test in the scope drags the whole run out of ``in_process`` and pays a subprocess per mutant, so a
    50s live-game system test traced per widen step dominates cost. Those tests are almost never the
    minimal distinguishing witness for a unit-level mutant. So by DEFAULT they are DEFERRED from the
    speculative pool — never silently: the caller counts them and the report discloses the count with
    a ``--include-shaped`` opt-in that forces them back in. A hermetic test is always admitted; this
    touches ONLY the speculative widen/capture, never the scoped baseline (which already ran them if
    they reached). A named code, never a bool:

      "admit"        — hermetic; always searched
      "admit_shaped" — non-hermetic but the caller opted in (--include-shaped)
      "defer_shaped" — non-hermetic and not opted in — deferred, DISCLOSED, never silently dropped
    """
    if is_hermetic:
        return "admit"
    return "admit_shaped" if include_shaped else "defer_shaped"


def _callable_is_hermetic(c: Callable[..., Any]) -> bool:
    """Whether a test callable is in_process-safe (hermetic), RESILIENT to the live-session path.

    ``callable_shape_hazards`` reads the ``__wesker_shape__`` stamp ``_build_callables`` sets at
    non-live collection. But converge/diagnose run through a LIVE pytest session, and those callables
    carry NO stamp — so a stamped read defaults every hazard to hermetic and NOTHING would ever defer
    (measured: a subprocess-spawning widen reacher read hermetic in a live session). So when the stamp
    is absent, RE-DERIVE the source-detectable hazards (#19's ``scan_source_hazards``) from the
    callable's own source, which the live path DOES expose via ``__wrapped__``. Unreadable source →
    hermetic (conservative: never defer a test we cannot classify). The source scan recovers
    subprocess / thread / signal — the isolation-forcing hazards; ``custom_collector`` is only caught
    when the stamp is present, an accepted gap in the live path.
    """
    stamped = getattr(c, "__wesker_shape__", None)
    if isinstance(stamped, dict):
        return fast_mode_standing(**callable_shape_hazards(c)) == "hermetic"
    real = getattr(c, "__wrapped__", c)
    try:
        src = inspect.getsource(real)
    except (OSError, TypeError):
        return True
    return not scan_source_hazards(src)


def _admit_search_pool(
    candidates: list[Callable[..., Any]], include_shaped: bool
) -> tuple[list[Callable[..., Any]], int]:
    """Partition a speculative-search candidate list into ``(admitted, deferred_count)`` by shape
    admission (shaped-defer). A test is deferred iff it is non-hermetic (:func:`_callable_is_hermetic`,
    resilient to the live-session path) and the caller did not opt in. The count is RETURNED so the
    caller can disclose it; deferral is never a silent drop.
    """
    admitted: list[Callable[..., Any]] = []
    deferred = 0
    for c in candidates:
        if search_pool_admission(_callable_is_hermetic(c), include_shaped) == "defer_shaped":
            deferred += 1
        else:
            admitted.append(c)
    return admitted, deferred


def classify_survivors(
    file: str,
    function: str,
    project_root: str = ".",
    *,
    max_int: int = 3,
    call_site_inputs: list[tuple] | None = None,
    extra_test_dirs: tuple[str, ...] = (),
    deadline_s: float | None = None,
    receiver_factory: ReceiverFactory | None = None,
    profile_result: ProfilingResult | None = None,
    include_shaped: bool = True,
    two_sign: bool = False,
) -> SurvivorReport:
    """Classify each surviving mutant as killable (with a distinguishing witness),
    equivalent-candidate, or unclassified — by running the original against the
    mutant over candidate integer inputs.

    ``call_site_inputs`` are user-SUPPLIED positional-argument tuples — the Zone-2
    residual filled in through the CLI when deterministic synthesis provably could not
    exercise a degree of freedom. They are tried FIRST, so a human-provided sample can
    kill a mutant that would otherwise read as candidate-equivalent. The human supplies
    only the input; the witness search and test generation stay deterministic.

    Every survivor is accounted for: a mutant that can't be built lands in
    ``unclassified``; when the integer inputs don't *exercise* the function (it
    takes strings, or it's a method needing ``self``) the whole run is unclassified
    with a ``note``, because a verdict there would be a false "equivalent".
    """
    root = os.path.abspath(project_root)
    full = file if os.path.isabs(file) else os.path.join(root, file)
    # Before ANY import can touch the target — test discovery and the traced
    # baseline both import it transitively — retire a possibly-stale bytecode
    # cache, or every number below describes a file no longer on disk.
    _purge_stale_bytecode(full)
    # The classification phase (issue #31, phase 4) draws from the caller's aggregate wall.
    # #42 bounds each individual witness ``_outcome`` at 5s so no single mutant hangs; the
    # DEADLINE bounds the SEARCH ACROSS survivors, so a countdown with many non-terminating
    # mutants (each paying its 5s classifier timeout) cannot sum past the command budget.
    # When the wall runs out mid-search the survivors not yet reached become ``unclassified``
    # (honest uncertainty), never a false candidate-equivalent. ``deadline_s`` None = unbounded.
    # None = unbounded; any number (INCLUDING 0.0) = that many ms remain. This is a computed
    # REMAINING budget from the caller, so 0.0 means EXHAUSTED — search nothing — NOT the CLI's
    # "--deadline 0 = unbounded" opt-out, which the command layer already mapped to None before
    # it ever reaches here. Conflating the two let an exhausted wall run the classifier unbounded.
    _cls_deadline_ms = None if deadline_s is None else max(0.0, deadline_s * 1000.0)
    _cls_t0 = time.monotonic()
    # Absolute monotonic cutoff handed to the per-mutant witness search, so it stops mid-pool
    # (a non-terminating mutant costs 5s PER input) rather than only between survivors.
    _cls_abs_deadline = None if _cls_deadline_ms is None else _cls_t0 + _cls_deadline_ms / 1000.0

    def _cls_budget_ms() -> float | None:
        return remaining_budget_ms(_cls_deadline_ms, (time.monotonic() - _cls_t0) * 1000.0)

    def _cls_exhausted() -> bool:
        # The pattern the other three sites drifted from; now all four read one owner.
        return budget_is_exhausted(_cls_budget_ms())

    with open(full, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=full)
    qualname, node = _resolve(tree, function)
    if node is None:
        raise LookupError(f"function {function!r} not found in {file}")

    # Human equivalence flags (the oracle execution cannot be) — keyed by the
    # mutation diff, which embeds the code, so a flag applies only to the exact
    # version it was made on. A flagged survivor is treated as equivalent UNLESS a
    # real distinguishing witness is found (proof outranks the flag).
    from .equivalents import contract_disposition, flag_verdict, load_flags

    flags = load_flags(root)
    func_key = f"{os.path.relpath(full, root)}::{qualname}"

    def _fv(rec: dict) -> str:
        # The recorded flag verdict ("" / "equivalent" / "fence") for this exact mutation. A `fence`
        # is an authored MUST-NOT (Def. 12.1 `invalid`), NEVER collapsed into "equivalent" (Q8).
        return flag_verdict(flags, func_key, rec.get("diff_summary", "")) if flags else ""

    def _split(recs: list[dict]) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
        """(still unclassified, flagged-equivalent diffs, flagged-fence diffs) — the NO-VERDICT
        partition (execution could not run at all), routed by the flag alone. contract_disposition
        with buildable=killable=blocked=False decides, so a fence is never suppressed as equivalent."""
        _u: list[str] = []
        _e: list[str] = []
        _f: list[str] = []
        for r in recs:
            disp = contract_disposition(False, False, False, _fv(r))
            if disp == "equivalent":
                _e.append(r.get("diff_summary", ""))
            elif disp == "fence":
                _f.append(r.get("diff_summary", ""))
            else:  # "unclassified" — no flag speaks for it
                _u.append(r.get("mutant", r.get("mutant_id", "?")))
        return tuple(_u), tuple(_e), tuple(_f)

    # Count survivors against the SAME test set the caller's headline profile used (#65). audit_suite
    # computes ONE profile for its `total`/`value_killed` counts and passes it here as
    # `profile_result`; classifying its survivors from THAT object binds the counts and the survivor
    # buckets to one measurement. Re-profiling with "the same args" — the old approach — could still
    # discover a different test set under a cold-collection race, so the two measurements disagreed by
    # a mutant and the audit partition assertion crashed the tool with a raw traceback. Reuse only
    # when the passed result is for THIS target and no out-of-tree dirs are in play (a pre-computed
    # result cannot reflect an extra_test_dirs the caller adds here); otherwise re-profile as before.
    if profile_result is not None and profile_result.function_key == func_key and not extra_test_dirs:
        result = profile_result
    else:
        result = profile(
            file,
            function,
            project_root,
            budget_ms=_cls_budget_ms(),
            extra_test_dirs=extra_test_dirs,
            include_shaped=include_shaped,
            two_sign=two_sign,
        )
    # Value-survivors: true survivors PLUS crash/timeout kills — the mutants whose RETURN
    # VALUE no test pins. Classifying THESE is how a crash-killed mutant gets a real
    # value-distinguishing witness (or is judged equivalent), instead of being silently
    # treated as specified because the code merely raised under some test.
    survivors = result.value_survivor_records
    if not survivors:
        return SurvivorReport((), (), None)

    original = _load_original(full, qualname or function)
    if original is None:
        unclassified_descs, manual_eq, fence_eq = _split(survivors)
        note = "the live original could not be loaded" if unclassified_descs else None
        return SurvivorReport(
            (), unclassified_descs, note=note, manual_equivalent=manual_eq, authored_fence=fence_eq
        )

    # METHOD BINDING (issue #25): `_load_original` returns the UNBOUND method, so the witness search
    # would call it with `self`/`cls` fed a grid value — `_search_witness` correctly SKIPS that via
    # `_binds` (leaving a `0/N killed` residual). `original_call` prepends a FRESH receiver per call
    # so the search actually exercises the method; `original` (unbound) is kept for `_compile_mutant`,
    # which seeds each mutant from `original.__globals__`. A property or a constructor that needs
    # arguments is a NAMED refusal here, not a silent all-survive.
    exb = resolve_execution(node, qualname or function, original, factory=receiver_factory)
    if exb.refusal is not None:
        unclassified_descs, manual_eq, fence_eq = _split(survivors)
        note = exb.refusal if unclassified_descs else None
        return SurvivorReport(
            (), unclassified_descs, note=note, manual_equivalent=manual_eq, authored_fence=fence_eq
        )
    original_call = wrap_callable(exb.underlying, exb.make_receiver)

    # Typed + dataclass-synthesized inputs from annotations, so a str/typed/object
    # function is exercised with type-appropriate values (not integers) — otherwise
    # its killable mutants read as false "equivalent".
    # Real call-site inputs FIRST — the honest record of how the function is actually
    # called, which exercises list/dict/unannotated arguments the per-parameter grids
    # cannot synthesize — then the synthesized grids. Discovery proposes; the soundness
    # gate below disposes (a spurious match just raises and is dropped).
    ns = getattr(original, "__globals__", {}) or {}
    discovered = discover_call_site_inputs(qualname or function, project_root)
    # Inputs whose TYPE is recovered from call sites even though the signature is
    # unannotated (formatters/domain-object fns) — synthesized in the type's defining
    # module so nested dataclass fields build. Placed after the real call-sites, before
    # the integer grids, so a genuine sample still wins.
    inferred_tuples, inferred_types = _synth_inferred_inputs(node, qualname or function, project_root, ns)
    # User-SUPPLIED inputs FIRST — the Zone-2 residual filled through the CLI. A
    # human-provided sample is ground truth for a DOF deterministic synthesis could not
    # exercise, so it wins over discovery, inferred-type synth, and the integer grids.
    supplied = [tuple(x) for x in (call_site_inputs or [])]
    # NEVER FABRICATE AN INPUT FOR A FUNCTION THAT ESCAPES THE PROCESS. The search below CALLS
    # the target — original and mutant — on every candidate, so for a function that writes files
    # a fabricated value is not a guess, it is damage. Measured, on this repo: the str grid is
    # `["", "a", "abc"]`, and `_declare_pythonpath("")` resolved `pyproject.toml` against the CWD
    # and rewrote Detective's own config, during classification AND in the test then emitted.
    #
    # The line is EVIDENCE vs INVENTION, not safe vs unsafe. `supplied` is a value a human typed;
    # `discovered`/`captured` are calls the repo already makes, so their effects already happen
    # when the suite runs. The grids and the inferred-type synthesis are ours, and ours are the
    # only ones that can surprise someone. Dropping them costs the search on effectful code — the
    # residual says so and asks for `--input`, which is the same "you supply what only you know"
    # contract as everywhere else, and it keeps the dangerous value one a human chose.
    effects = world_effects(node)
    # Neighbors of the supplied inputs rank just behind the evidence (supplied + discovered)
    # and ahead of the grids: they are the region a human just said matters, stepped one past
    # its edges. They are still OUR fabrications, so they obey the world-effects gate.
    fabricated = (
        []
        if effects
        else _neighbor_inputs(supplied) + inferred_tuples + bounded_product(_input_grids(node, ns))
    )
    inputs = supplied + discovered + fabricated

    # When deterministic synthesis provably can't exercise the function — every
    # candidate raises, i.e. a domain-object parameter no grid can fabricate — reuse
    # a REAL input the covering tests already pass: capture the actual arguments at
    # every entry to the target while the discovered tests run, and retry. This
    # closes structured-input functions to a verdict WITHOUT ever fabricating an
    # input (the abstention below stays the honest fallback when even the tests do
    # not exercise the DOF). Captured real inputs rank just behind a human-supplied
    # residual and ahead of the synthesized grids.
    def _first_exercising(candidates: list[tuple]) -> tuple | None:
        """The first input the ORIGINAL does not raise on — i.e. the one that actually
        reaches the function's body. Returned rather than discarded, because WHICH input
        works decides the next action: one a user can type is an `--input`, one only their
        tests can build is a request for a test."""
        for args in candidates:
            if not _outcome(original_call, args).startswith("<raised"):
                return args
        return None

    _deferred_shaped_capture = 0
    exercising = _first_exercising(inputs)
    if exercising is None:
        func_names = [qn for qn, _ in walk_functions(tree)]
        harvest_tests = discover_test_callables(
            root, os.path.relpath(full, root), func_names, extra_dirs=list(extra_test_dirs) or None
        )
        # shaped-defer the capture HARVEST too, not just the widen: `capture_call_inputs` RUNS every
        # harvested test to profile-hook its inputs, so a 50s live-game system test is traced here even
        # when the widen already deferred it — the residual slow path a pure function's survivors hit.
        # Held out by default, disclosed, restored by --include-shaped (the `search_pool_admission`
        # contract), so a candidate-equivalent is never silently attributed to code a deferred test
        # might have distinguished.
        harvest_tests, _hd = _admit_search_pool(harvest_tests, include_shaped)
        _deferred_shaped_capture = max(_deferred_shaped_capture, _hd)
        captured = capture_call_inputs(original, harvest_tests)
        inputs = supplied + captured + inputs
        exercising = _first_exercising(inputs)
    # Whether the working input has a literal form. Computed HERE, where the input that
    # actually ran is in hand; a renderer downstream can only guess at it from the signature,
    # which is unannotated in exactly the cases this decides.
    expressible = None if exercising is None else all(is_expressible(a) for a in exercising)
    # Soundness gate: if the original STILL raises on every candidate input, the
    # inputs don't fit this function — any "equivalent" verdict would be spurious.
    if exercising is None:
        # Execution can't run here — but a manual flag stands regardless.
        unclassified_descs, manual_eq, fence_eq = _split(survivors)
        note = (
            _unreachable_inputs_note(node, qualname or function, inferred_types, effects)
            if unclassified_descs
            else None
        )
        return SurvivorReport(
            (),
            unclassified_descs,
            note=note,
            manual_equivalent=manual_eq,
            authored_fence=fence_eq,
            inputs_expressible=None,  # nothing exercised it; `note` carries the reason
            deferred_shaped=_deferred_shaped_capture,
        )

    pure = _is_pure(node, is_method="." in (qualname or ""))
    # by_id maps a survivor's content-addressed id to its mutant object, so it MUST regenerate under
    # the same policy the profile used — else an OUTPUT (μ⁻) survivor's id is absent, it reads as
    # "un-buildable", and falls to `unclassified` instead of being witness-searched (the Fork-2 →abs
    # gap this closes). Under the two-sign contract, regenerate WITH two_sign and the profile's observed
    # codomain (carried on the result, re-captured on a cache hit that returned before the capture), so
    # the OUTPUT mutant ids match. The one-sign default stays byte-identical and passes no newer kwarg,
    # so it still resolves against a pre-two-sign Wesker.
    if two_sign:
        from .capture import capture_return_types

        _observed = getattr(result, "observed_return_types", None)
        if _observed is None:
            _obs_names = [qn for qn, _ in walk_functions(tree)]
            _observed = capture_return_types(
                original,
                discover_test_callables(
                    root,
                    os.path.relpath(full, root),
                    _obs_names,
                    extra_dirs=list(extra_test_dirs) or None,
                ),
            )
        by_id = {
            m.mutant_id: m
            for m in generate_mutants(
                node,
                filter_categories(node, pure, two_sign=True),  # type: ignore[arg-type]
                observed_return_types=_observed,
            )
        }
    else:
        by_id = {
            m.mutant_id: m
            for m in generate_mutants(node, filter_categories(node, pure))  # type: ignore[arg-type]
        }

    def _classify_pool(
        pool: list[tuple],
    ) -> tuple[list[MutantVerdict], list[str], list[str], list[str]]:
        _verdicts: list[MutantVerdict] = []
        _unclassified: list[str] = []
        _manual: list[str] = []
        _fence: list[str] = []

        def _route(disp: str, rec: dict, verdict: MutantVerdict | None) -> None:
            # contract_disposition's named code → the terminal bucket. `killable`/`candidate` only
            # arise on the buildable path, where `verdict` is never None (the guard is type-honesty).
            if disp in ("killable", "candidate") and verdict is not None:
                _verdicts.append(verdict)
            elif disp == "equivalent":
                _manual.append(rec.get("diff_summary", ""))
            elif disp == "fence":
                _fence.append(rec.get("diff_summary", ""))
            else:  # "unclassified" — no verdict to trust and no flag speaks for it
                _unclassified.append(rec.get("mutant", rec.get("mutant_id", "?")))

        for rec in survivors:
            # Aggregate wall exhausted (issue #31): stop starting new witness searches. Every
            # survivor not yet classified is UNCLASSIFIED — honest uncertainty, the same bucket
            # #42's per-mutant timeout uses — never defaulted to a false candidate-equivalent.
            if _cls_exhausted():
                _unclassified.append(rec.get("mutant", rec.get("mutant_id", "?")))
                continue
            mutant = by_id.get(rec.get("mutant_id", ""))
            # Compile the mutant from the UNBOUND original (its `__globals__` seeds the mutant's
            # namespace), then receiver-bind it with the SAME plan as the original so the two are
            # arity-symmetric — both called `fn(fresh_receiver, *args)` (issue #25).
            mutant_fn = _compile_mutant(mutant, original) if mutant is not None else None
            if mutant_fn is not None:
                mutant_fn = wrap_callable(mutant_fn, exb.make_receiver)
            if mutant_fn is None:
                # Un-buildable: no execution verdict; the flag alone decides (a fence stays a fence,
                # never suppressed as equivalent — the Q8 soundness split).
                _route(contract_disposition(False, False, False, _fv(rec)), rec, None)
                continue
            verdict = classify_survivor(
                rec.get("mutant_id", ""),
                rec.get("category", ""),
                rec.get("diff_summary", ""),
                original_call,
                mutant_fn,
                pool,
                # A crash-survivor record is a reshaped KILL record and carries `killed_by`; a
                # true survivor carries none. That single field is whether "your suite already
                # detects this by crash" is TRUE of this mutant — carried so the renderer can
                # say it per mutant instead of assuming it for the bucket.
                suite_detected=bool(rec.get("killed_by")),
                deadline=_cls_abs_deadline,
            )
            # A real witness is PROOF of killability and outranks the flag (contract_disposition
            # returns "killable"); a flag on a no-witness survivor is honored by its verdict —
            # "equivalent" suppressed, "fence" reported as an unenforced must-not, "blocked" → unclassified.
            _route(contract_disposition(True, verdict.killable, verdict.blocked, _fv(rec)), rec, verdict)
        return _verdicts, _unclassified, _manual, _fence

    verdicts, unclassified, manual_equivalent, fence = _classify_pool(inputs)
    final_pool = inputs  # the pool the FINAL verdicts were classified over; updated when a retry adopts
    note: str | None = None

    # POOL-POVERTY RESCUE. The capture fallback above triggers on "every candidate
    # RAISES" — reachability. But a total function can be reached by a degenerate
    # input and still never be DISCRIMINATED by one: `callable_origin(1)` returns
    # None just like every mutant of it, so ints exercise it, the raise-gate stays
    # quiet, and survivors file as candidate-equivalent — a claim about the input
    # pool wearing the costume of a claim about the code. The rescue used to fire
    # only when NO survivor proved killable; the field case (issue #22) is PARTIAL
    # poverty — some survivors proven by synthetic inputs while others filed
    # candidate-equivalent, or proved killable with witnesses only a test can
    # build, while the covering tests were constructing the real objects all
    # along. So it now fires when ANY residual is rescuable: a non-crash-only
    # unprovable (crash-only is a terminal per-semantics verdict richer inputs
    # cannot move), or a killable whose witness cannot be rendered as a
    # paste-able `--input`. Captures rank ahead of synthetics in the retry pool,
    # so a witness that CAN come from a suite-built value does. Adopt the retry
    # only if it improved something: more kills, or same kills with witnesses
    # the renderer can actually hand back.
    def _inexpressible_witness(v: MutantVerdict) -> bool:
        return v.killable and v.witness is not None and not all(is_expressible(a) for a in v.witness.args)

    # The rescue re-runs the whole classification over a richer pool — real work, so it is
    # skipped once the aggregate wall is gone (issue #31): a cut run keeps its first-pass
    # verdicts rather than starting a second search it cannot finish.
    rescuable = any((not v.killable and not v.crash_only) or _inexpressible_witness(v) for v in verdicts)
    _rescue = rescue_disposition(
        bool(expressible), rescuable, any(_inexpressible_witness(v) for v in verdicts)
    )
    if _rescue == "skip_ask_input":
        # Grid-friendly survivors no synthesized input discriminates: the distinguishing value is a
        # literal only the caller knows. Running the covering suite to hunt it is futile — it burned
        # the full --deadline on ARC-scale suites — so ask for --input, the fast honest path.
        note = (
            "no synthesized input discriminates the remaining survivor(s), and their inputs are "
            "expressible as literals — supply the distinguishing value(s) with --input rather than "
            "searching the covering suite"
        )
    elif _rescue == "run" and not _cls_exhausted():
        func_names = [qn for qn, _ in walk_functions(tree)]
        harvest_tests = discover_test_callables(
            root, os.path.relpath(full, root), func_names, extra_dirs=list(extra_test_dirs) or None
        )
        harvest_tests, _hd = _admit_search_pool(harvest_tests, include_shaped)  # shaped-defer (see above)
        _deferred_shaped_capture = max(_deferred_shaped_capture, _hd)
        captured = capture_call_inputs(original, harvest_tests)
        fresh = [t for t in captured if _safely_fresh(t, inputs)]
        if fresh:
            retry = _classify_pool(supplied + fresh + inputs)
            before_kills = sum(1 for v in verdicts if v.killable)
            after_kills = sum(1 for v in retry[0] if v.killable)
            improved = after_kills > before_kills or (
                after_kills == before_kills
                and sum(1 for v in retry[0] if _inexpressible_witness(v))
                < sum(1 for v in verdicts if _inexpressible_witness(v))
            )
            if improved:
                verdicts, unclassified, manual_equivalent, fence = retry
                final_pool = supplied + fresh + inputs
                # Expressibility must be judged on the WITNESS inputs, not the first
                # input that merely exercised the function: a captured function object
                # discriminates but cannot be typed, and the renderer's contract is
                # that any `--input` it prints can be pasted and will parse.
                witness_args = [v.witness.args for v in verdicts if v.killable and v.witness is not None]
                if witness_args:
                    expressible = all(is_expressible(a) for args in witness_args for a in args)
            elif after_kills == 0:
                note = (
                    f"no candidate input discriminates any survivor — pool included "
                    f"{len(fresh)} captured real input(s) from the covering tests"
                )
        elif not any(v.killable for v in verdicts):
            note = (
                "no candidate input discriminates any survivor, and the covering tests "
                "never call this function with inputs beyond the synthesized pool — "
                "equivalence here is a claim about the input pool, not the code"
            )

    # B0 (#15 F0): active structural search — the tractable half of routing the un-killed residual
    # to synthesis. A deep_structural (worklist/fixpoint) target whose residual neither the scalar
    # grid nor the capture-rescue killed may still be killable by a CROSS-REFERENTIAL input: an
    # index-valid adjacency topology that the length-variant grid (default inner values) and a
    # captured real call do not construct. Retry ONCE over the topology library through the same
    # _classify_pool machinery, and adopt only if it proved a NEW kill (positive-only, so this can
    # never manufacture a false COMPLETE). General worklist synthesis stays the open frontier.
    _struct = structural_retry_gate(
        structural_input_difficulty(**structural_shape(node)) == "deep_structural",
        any(not v.killable and not v.crash_only for v in verdicts),
        bool(effects),
        _cls_exhausted(),
    )
    if _struct == "run":
        struct_inputs = _structural_topology_inputs(node, ns)
        fresh = [t for t in struct_inputs if _safely_fresh(t, inputs)]
        if fresh:
            retry = _classify_pool(supplied + fresh + inputs)
            if sum(1 for v in retry[0] if v.killable) > sum(1 for v in verdicts if v.killable):
                verdicts, unclassified, manual_equivalent, fence = retry
                final_pool = supplied + fresh + inputs
                # A "no input discriminates / equivalence is about the pool" note set above is
                # falsified by the new kill — clear it rather than ship a stale claim.
                note = None
                # Topology witnesses are nested lists, which is_expressible accepts, so a topology
                # kill still renders as a pasteable --input. Recompute on the WITNESS args.
                witness_args = [v.witness.args for v in verdicts if v.killable and v.witness is not None]
                if witness_args:
                    expressible = all(is_expressible(a) for args in witness_args for a in args)

    # The mutated line of each survivor — shared by the B1 guard-directed search and the reachability pass.
    _id_line = {r.get("mutant_id"): r.get("mutated_line") for r in survivors}

    # B1 (#15 F0): guard-directed active search — the generalization of B0 from a fixed topology library
    # to the SIMPLE comparison guard a candidate-equivalent sits behind (``len(x) > 5``, ``x == 42``). The
    # scalar grid never entered that branch, so the mutation is unreached; an input satisfying the guard,
    # read off the branch's OWN AST, reaches it. Retry positive-only through _classify_pool (adopt only a
    # NEW kill, so never a false COMPLETE). The differential / domain-object reach stays the open frontier
    # (a fixture caveat), exactly as B0 left general worklist synthesis.
    _guard = guard_retry_gate(
        any(not v.killable and not v.crash_only for v in verdicts), bool(effects), _cls_exhausted()
    )
    if _guard == "run":
        _cand_lines = frozenset(
            ln
            for v in verdicts
            if not v.killable and not v.crash_only and (ln := _id_line.get(v.mutant_id)) is not None
        )
        guard_inputs = _guard_directed_inputs(node, ns, _cand_lines)
        fresh = [t for t in guard_inputs if _safely_fresh(t, inputs)]
        if fresh:
            retry = _classify_pool(supplied + fresh + inputs)
            if sum(1 for v in retry[0] if v.killable) > sum(1 for v in verdicts if v.killable):
                verdicts, unclassified, manual_equivalent, fence = retry
                final_pool = supplied + fresh + inputs
                note = None
                witness_args = [v.witness.args for v in verdicts if v.killable and v.witness is not None]
                if witness_args:
                    expressible = all(is_expressible(a) for args in witness_args for a in args)

    # B2 (#67): domain-object differential search — the generalization of B0/B1 from nested-int
    # topologies and scalar guards to a DATACLASS parameter whose VALUE-bearing field a mutation reads.
    # Synthesis already REACHES the object (a Relation is constructed); the differential grid VARIES one
    # field per variant (distinct_field_value) so the mutation is distinguished, each carried as a
    # SourceExpr constructor so a kill renders as `Cls(field=...)` — never an --input, never a flag.
    # Retry positive-only through _classify_pool (adopt only a NEW kill, so never a false COMPLETE). The
    # cross-field-invariant and non-introspectable objects stay a fixture hand-back — the honest residual.
    _domain = domain_variant_retry_gate(
        any(not v.killable and not v.crash_only for v in verdicts), bool(effects), _cls_exhausted()
    )
    if _domain == "run":
        domain_inputs = _domain_object_variant_inputs(node, ns, qualname or function, project_root)
        fresh = [t for t in domain_inputs if _safely_fresh(t, inputs)]
        if fresh:
            retry = _classify_pool(supplied + fresh + inputs)
            if sum(1 for v in retry[0] if v.killable) > sum(1 for v in verdicts if v.killable):
                verdicts, unclassified, manual_equivalent, fence = retry
                final_pool = supplied + fresh + inputs
                note = None
                # A domain-object witness is a SourceExpr constructor (is_expressible False by design —
                # a constructor is not an --input literal), so expressibility stays False; the kill
                # renders via the SourceExpr source, not a paste-able literal. Recompute on witnesses.
                witness_args = [v.witness.args for v in verdicts if v.killable and v.witness is not None]
                if witness_args:
                    expressible = all(is_expressible(a) for args in witness_args for a in args)

    # Reachability (RIP-R, §6 door 2 / Def. 1.4): a candidate-equivalent whose mutated line was never
    # EXECUTED by the final pool is killable with a reaching input the search did not construct — not an
    # equivalence. Trace the ORIGINAL over the pool once and mark each such verdict, so the renderer's
    # `residual_disposition` routes it to a caveat, never a flag. Skipped when the wall is gone (#31:
    # keep the flag-safe reached=True default) or nothing is candidate-equivalent (no flag to guard).
    _cand = [v for v in verdicts if not v.killable and not v.crash_only]
    if _cand and not _cls_exhausted():
        _want = frozenset(ln for v in _cand if (ln := _id_line.get(v.mutant_id)) is not None)
        _fname = getattr(getattr(original, "__code__", None), "co_filename", None)
        if _want and _fname is not None:
            _reach_budget = (
                5.0 if _cls_abs_deadline is None else max(0.0, min(5.0, _cls_abs_deadline - time.monotonic()))
            )
            _reached = _reached_lines(original_call, final_pool, _fname, _want, _reach_budget)
            verdicts = [
                dataclasses.replace(v, reached=(_id_line.get(v.mutant_id) in _reached))
                if (not v.killable and not v.crash_only and _id_line.get(v.mutant_id) is not None)
                else v
                for v in verdicts
            ]

    return SurvivorReport(
        tuple(verdicts),
        tuple(unclassified),
        note,
        manual_equivalent=tuple(manual_equivalent),
        authored_fence=tuple(fence),
        inputs_expressible=expressible,
        deferred_shaped=_deferred_shaped_capture,
    )
