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
import importlib.util
import os
import subprocess
import sys
from collections.abc import Callable
from typing import Any

from Wesker.ci import discover_test_callables, walk_functions
from Wesker.engine import (  # imported, never restated — one owner for each of these numbers
    DEFAULT_TRACE_BUDGET_S as _WESKER_DEFAULT_TRACE_BUDGET_S,
)
from Wesker.engine import (
    DEFAULT_TRACE_SESSION_BUDGET_S as _WESKER_DEFAULT_TRACE_SESSION_BUDGET_S,
)
from Wesker.engine import ProfilingResult, generate_mutants, run_function_profiling
from Wesker.filter import filter_categories

from .call_sites import discover_call_site_inputs, infer_param_types
from .capture import capture_call_inputs
from .equivalence import (
    MutantVerdict,
    SourceExpr,
    SurvivorReport,
    _grid_for,
    _outcome,
    _type_of,
    ast_grid,
    bounded_product,
    classify_survivor,
    is_expressible,
    is_scalar_type,
    synth_ast_input,
)
from .purity import is_pure as _is_pure
from .purity import world_effects
from .scope import ScopeMap, scope_from_profiling


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


def _load_original(full_path: str, qualname: str) -> Any | None:
    """Return the live target object from the module under test.

    Wesker seeds each mutant's namespace from ``original_func.__globals__`` so the
    mutant can resolve the module's sibling helpers, constants, and imports. Prefers
    the already-imported module (correct package context, so module-level *relative*
    imports resolve); falls back to loading by path. Returns None if neither works
    (Wesker then degrades to an empty namespace).
    """
    real = os.path.abspath(full_path)
    for mod in list(sys.modules.values()):
        mod_file = getattr(mod, "__file__", None)
        if mod_file and os.path.abspath(mod_file) == real:
            return _attr_path(mod, qualname)

    try:
        stem = os.path.splitext(os.path.basename(full_path))[0]
        name = f"_detective_uut_{stem}"
        spec = importlib.util.spec_from_file_location(name, full_path)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod  # register before exec (dataclass/pickle resolution)
        spec.loader.exec_module(mod)
    except Exception:
        return None
    return _attr_path(mod, qualname)


def _attr_path(obj: Any, qualname: str) -> Any | None:
    for part in qualname.split("."):
        obj = getattr(obj, part, None)
        if obj is None:
            return None
    return obj


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
    with open(full, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=full)

    qualname, node = _resolve(tree, function)
    if node is None:
        raise LookupError(f"function {function!r} not found in {file}")

    pure = _is_pure(node, is_method="." in (qualname or "")) if is_pure is None else is_pure
    # AsyncFunctionDef has the same shape Wesker's mutators walk.
    categories = filter_categories(node, pure)  # type: ignore[arg-type]
    rel = os.path.relpath(full, root)
    func_key = f"{rel}::{qualname}"

    if tests is None:
        func_names = [qn for qn, _ in walk_functions(tree)]
        tests = discover_test_callables(root, rel, func_names, extra_dirs=list(extra_test_dirs) or None)

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

    ck = verdict_cache.cache_key(
        func_key,
        ast.dump(node),
        tests,
        max_per_category,
        pass_index,
        _measured_under if _measured_under is not None else (trace_budget_s, trace_session_budget_s),
    )
    if use_cache:
        hit = verdict_cache.get(root, ck)
        if hit is not None:
            return hit

    # Pass the live target so Wesker seeds the mutant namespace from its
    # __globals__ (module helpers/constants/imports resolve inside the mutant).
    original = _load_original(full, qualname or function)
    result = run_function_profiling(  # type: ignore[arg-type]
        node,
        func_key,
        categories,
        tests,
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
    )
    # Only cache COMPLETE runs — a budget/memory-exhausted partial must not be served
    # later as if it were the whole profile.
    if use_cache and not result.budget_exhausted:
        verdict_cache.put(root, ck, verdict_cache.key_prefix(func_key), result)
    return result


def _count_decompose_seams(file: str, function: str, project_root: str = ".") -> int:
    """Clean structural extraction candidates (single-exit, small-interface, worth-it) the
    deterministic clustering finds for ``function`` — the STRUCTURAL decomposability signal,
    read from the AST alone (no tests). Best-effort: any failure returns 0, so a structural
    read never breaks a diagnose. Paired with regime B in the CLI as the convergent flag."""
    try:
        from .decompose import find_extraction_candidates

        root = os.path.abspath(project_root)
        full = file if os.path.isabs(file) else os.path.join(root, file)
        with open(full, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=full)
        _, node = _resolve(tree, function)
        return len(find_extraction_candidates(node)) if node is not None else 0  # type: ignore[arg-type]
    except Exception:  # noqa: BLE001 — a structural read must never fail a diagnose
        return 0


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
    )
    scope = scope_from_profiling(result)

    from dataclasses import replace

    updates: dict[str, Any] = {"decompose_seams": _count_decompose_seams(file, function, project_root)}
    return replace(scope, **updates)


def _compile_mutant(mutant: Any, original: Callable[..., Any]) -> Callable[..., Any] | None:
    """Compile a mutant's AST into a callable, seeded with the original's globals so
    it resolves sibling helpers/constants/imports. None if it won't build."""
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


def _input_grids(node: ast.AST, namespace: dict) -> list[list]:
    """Per-parameter candidate value lists: the literals the function tests the parameter
    against (its own declared domain) first, then a built-in grid for scalars; for an
    AST-typed param a GRID of real nodes; for a sequence param a set of LENGTH VARIANTS
    (empty / single / two field-variant elements); for a bare dataclass param its FIELD
    VARIANTS (bool flipped, Optional None); else the integer fallback — so functions
    taking structured inputs become exercisable and their field/length branches are all
    covered.
    """
    domain = _compared_literals(node)
    grids: list[list] = []
    for arg in node.args.args:  # type: ignore[attr-defined]
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
        declared = domain.get(arg.arg, [])
        if declared:
            grid = declared + [v for v in grid if v not in declared]
        grids.append(grid)
    return grids


def _seq_length_variants(ann: ast.AST, namespace: dict) -> list | None:
    """For a ``list``/``Sequence`` annotation, candidate values at lengths 0, 1, and 2 —
    the length-2 case pairing two field-variant elements so branches that depend on both
    sequence LENGTH (empty/single/2+) and on the ELEMENTS' bool/Optional fields are all
    exercised. None when the annotation is not a recognized sequence."""
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


def representative_site(node: ast.AST, namespace: dict) -> list[dict]:
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
    for arg in node.args.args:  # type: ignore[attr-defined]
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


def classify_survivors(
    file: str,
    function: str,
    project_root: str = ".",
    *,
    max_int: int = 3,
    call_site_inputs: list[tuple] | None = None,
    extra_test_dirs: tuple[str, ...] = (),
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
    with open(full, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=full)
    qualname, node = _resolve(tree, function)
    if node is None:
        raise LookupError(f"function {function!r} not found in {file}")

    # Human equivalence flags (the oracle execution cannot be) — keyed by the
    # mutation diff, which embeds the code, so a flag applies only to the exact
    # version it was made on. A flagged survivor is treated as equivalent UNLESS a
    # real distinguishing witness is found (proof outranks the flag).
    from .equivalents import is_flagged_equivalent, load_flags

    flags = load_flags(root)
    func_key = f"{os.path.relpath(full, root)}::{qualname}"

    def _flagged(rec: dict) -> bool:
        return bool(flags) and is_flagged_equivalent(flags, func_key, rec.get("diff_summary", ""))

    def _split(recs: list[dict]) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """(descriptions still unclassified, diffs manually flagged equivalent)."""
        return (
            tuple(r.get("mutant", r.get("mutant_id", "?")) for r in recs if not _flagged(r)),
            tuple(r.get("diff_summary", "") for r in recs if _flagged(r)),
        )

    # Count survivors against the SAME test set the caller's headline profile used —
    # including any out-of-tree write-dir (extra_test_dirs). Without this, an out-of-tree
    # written test that already kills a mutant is invisible here, so the survivor report
    # would classify a mutant the headline count reports as killed (a real inconsistency).
    result = profile(file, function, project_root, extra_test_dirs=extra_test_dirs)
    # Value-survivors: true survivors PLUS crash/timeout kills — the mutants whose RETURN
    # VALUE no test pins. Classifying THESE is how a crash-killed mutant gets a real
    # value-distinguishing witness (or is judged equivalent), instead of being silently
    # treated as specified because the code merely raised under some test.
    survivors = result.value_survivor_records
    if not survivors:
        return SurvivorReport((), (), None)

    original = _load_original(full, qualname or function)
    if original is None:
        unclassified_descs, manual_eq = _split(survivors)
        note = "the live original could not be loaded" if unclassified_descs else None
        return SurvivorReport((), unclassified_descs, note=note, manual_equivalent=manual_eq)

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
    fabricated = [] if effects else inferred_tuples + bounded_product(_input_grids(node, ns))
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
            if not _outcome(original, args).startswith("<raised"):
                return args
        return None

    exercising = _first_exercising(inputs)
    if exercising is None:
        func_names = [qn for qn, _ in walk_functions(tree)]
        harvest_tests = discover_test_callables(
            root, os.path.relpath(full, root), func_names, extra_dirs=list(extra_test_dirs) or None
        )
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
        unclassified_descs, manual_eq = _split(survivors)
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
            inputs_expressible=None,  # nothing exercised it; `note` carries the reason
        )

    pure = _is_pure(node, is_method="." in (qualname or ""))
    by_id = {m.mutant_id: m for m in generate_mutants(node, filter_categories(node, pure))}  # type: ignore[arg-type]

    verdicts: list[MutantVerdict] = []
    unclassified: list[str] = []
    manual_equivalent: list[str] = []
    for rec in survivors:
        mutant = by_id.get(rec.get("mutant_id", ""))
        mutant_fn = _compile_mutant(mutant, original) if mutant is not None else None
        if mutant_fn is None:
            # Un-buildable: the manual flag is the only signal we have.
            (manual_equivalent if _flagged(rec) else unclassified).append(
                rec.get("diff_summary", "") if _flagged(rec) else rec.get("mutant", rec.get("mutant_id", "?"))
            )
            continue
        verdict = classify_survivor(
            rec.get("mutant_id", ""),
            rec.get("category", ""),
            rec.get("diff_summary", ""),
            original,
            mutant_fn,
            inputs,
        )
        # A real witness is PROOF of killability and outranks the flag (keep the
        # killable verdict); a flag on a no-witness survivor confirms equivalence.
        if not verdict.killable and _flagged(rec):
            manual_equivalent.append(rec.get("diff_summary", ""))
        else:
            verdicts.append(verdict)
    return SurvivorReport(
        tuple(verdicts),
        tuple(unclassified),
        None,
        manual_equivalent=tuple(manual_equivalent),
        inputs_expressible=expressible,
    )
