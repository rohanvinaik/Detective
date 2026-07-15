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
import sys
from collections.abc import Callable
from typing import Any

from Wesker.ci import discover_test_callables, walk_functions

try:  # older Wesker without the live-session seam: no live suite can be active
    from Wesker.ci import live_suite_active as _live_suite_active
except ImportError:  # pragma: no cover

    def _live_suite_active() -> bool:
        return False


from Wesker.engine import (
    DEFAULT_TRACE_BUDGET_S as _WESKER_DEFAULT_TRACE_BUDGET_S,  # imported, never restated — one owner
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
    is_scalar_type,
    synth_ast_input,
)
from .purity import is_pure as _is_pure
from .scope import ScopeMap, scope_from_profiling


def _resolve(
    tree: ast.Module, function: str
) -> tuple[str | None, ast.FunctionDef | ast.AsyncFunctionDef | None]:
    """Find the target function node by name (supports ``Class.method``)."""
    for qualname, node in walk_functions(tree):
        if qualname == function or qualname.split(".")[-1] == function:
            return qualname, node
    return None, None


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


def _shift_progress(
    progress: Callable[[int, int, float], None] | None, done_already: int, universe: int
) -> Callable[[int, int, float], None] | None:
    """Re-base a slice's progress onto the FULL mutant universe.

    A sliced run counts itself from zero, so the adaptive probe's already-evaluated mutants
    fall off the axis and the stream under-reports: "72/72 mutants" for a function the same
    run reports as 76 variants. Nothing is wrong with either number — they are just measured
    against different denominators, which a reader cannot know. Shifting by the probe's count
    makes the live stream and the final verdict describe the same universe."""
    if progress is None:
        return None

    def _shifted(done: int, _slice_total: int, rate: float) -> None:
        progress(done_already + done, universe, rate)

    return _shifted


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
    use_parallel: bool | None = None,
    trace_budget_s: float | None = _WESKER_DEFAULT_TRACE_BUDGET_S,
    trace_progress: Callable[[int, int, float], None] | None = None,
    trace_session_budget_s: float | None = None,
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

    tests_auto = tests is None  # workers re-discover; explicit callables can't cross spawn
    if tests is None:
        func_names = [qn for qn, _ in walk_functions(tree)]
        tests = discover_test_callables(root, rel, func_names, extra_dirs=list(extra_test_dirs) or None)

    # Content-hashed verdict cache: an unchanged function + unchanged exercising
    # tests + same sampling params yield the same profile, so serve it from disk
    # instead of re-running every mutant — the re-audit-while-editing win. Keyed on
    # the function's AST dump (position-independent: editing OTHER functions never
    # invalidates this one) + the tests' sources + (max_per_category, pass_index).
    # Scope-invariant: scoped and full runs are proven verdict-identical.
    from . import verdict_cache

    ck = verdict_cache.cache_key(func_key, ast.dump(node), tests, max_per_category, pass_index)
    if use_cache:
        hit = verdict_cache.get(root, ck)
        if hit is not None:
            return hit

    # Parallel fan-out (model A). Three modes via ``use_parallel``:
    #   True  → force: fan the whole run out across workers (caller has dropped progress).
    #   None  → AUTO: MEASURE this function's per-mutant cost with a small serial probe, then
    #           parallelize the remainder only if the remaining serial work justifies the
    #           spawn tax — correct across the ~1000x per-mutant range, not a stale-rate guess.
    #   False → off: plain serial.
    # Never for a shard (``mutant_slice``), explicit tests (workers re-discover; callables
    # can't cross spawn), a budgeted run (a sharded wall-clock budget is not equivalent),
    # or a LIVE pytest session — the live suite is closures over live pytest items, bound
    # to this interpreter's session/fixtures/conftest, so it cannot cross spawn either. A
    # worker started from inside one re-discovers with the collect-only backend, silently
    # drops every fixture-taking test, and reports its shard's mutants as survivors; the
    # parent then merges that into an otherwise-correct result. Measured on Prism:
    # 1/131 behaviors "pinned" fanned out, versus 16/16 in-session — the fan-out was
    # reporting a fully-specified function as almost entirely unspecified. Staying serial
    # is not a loss here: the session baseline is already paid once, so per-function cost
    # is small (~2.3s), whereas each spawned worker would re-pay it in full.
    # The fleet size is the portable memory guarantee; verdicts are proven bit-identical.
    if (
        use_parallel is not False
        and mutant_slice is None
        and tests_auto
        and budget_ms is None
        and not _live_suite_active()
    ):
        from Wesker.memory_guard import worker_count

        from . import parallel

        workers = worker_count()
        if workers > 1:
            # Generate ONCE; the probe and the serial remainder reuse this list rather than
            # regenerating (~37ms each), so the adaptive measurement is nearly free.
            _mutants = generate_mutants(  # type: ignore[arg-type]
                node, categories, max_per_category=max_per_category, pass_index=pass_index
            )
            exact = len(_mutants)
            fanned: ProfilingResult | None = None
            if use_parallel is True and exact >= 2:
                fanned = parallel.parallel_profile(
                    file,
                    function,
                    project_root,
                    end=exact,
                    max_per_category=max_per_category,
                    pass_index=pass_index,
                    scope_tests=scope_tests,
                    workers=workers,
                )
            elif use_parallel is None and exact >= parallel.PROBE_MIN_MUTANTS:
                # Adaptive: time a small serial probe (silent), then decide. The probe is ALWAYS
                # kept as shard 0 — merged with a parallel remainder (slow function) or a serial
                # remainder that REUSES the probe's baseline line-coverage pass (fast function),
                # so the measurement adds ~no cost beyond splitting one run into two.
                probe_n = min(parallel.PROBE_SIZE, exact)
                _orig = _load_original(full, qualname or function)
                probe = run_function_profiling(  # type: ignore[arg-type]
                    node,
                    func_key,
                    categories,
                    tests,
                    _orig,
                    max_per_category=max_per_category,
                    pass_index=pass_index,
                    scope_tests=scope_tests,
                    mutant_slice=(0, probe_n),
                    pregenerated=_mutants,
                    # only the probe traces; `rest` reuses its precomputed_line_data
                    trace_budget_s=trace_budget_s,
                    trace_progress=trace_progress,
                    trace_session_budget_s=trace_session_budget_s,
                )
                if exact <= probe_n:
                    fanned = probe  # the probe was the whole run
                elif parallel.mean_mutant_ms(probe) * (exact - probe_n) > parallel.PARALLEL_MIN_REMAINING_MS:
                    rest = parallel.parallel_profile(
                        file,
                        function,
                        project_root,
                        start=probe_n,
                        end=exact,
                        max_per_category=max_per_category,
                        pass_index=pass_index,
                        scope_tests=scope_tests,
                        workers=workers,
                    )
                    fanned = parallel.merge_results([probe, rest])
                else:
                    # Cheap enough to stay serial: finish the remainder in-process, REUSING the
                    # probe's baseline (no second line-coverage trace) and streaming its progress.
                    #
                    # The remainder is a SLICE, so Wesker counts it 0..(exact - probe_n): the
                    # stream said "72/72 mutants" for a function the same run then reports as 76
                    # variants, because the probe's mutants are already done and never appear on
                    # the axis. Shift the counts back onto the TRUE universe so the two numbers a
                    # user sees in one run cannot disagree.
                    rest = run_function_profiling(  # type: ignore[arg-type]
                        node,
                        func_key,
                        categories,
                        tests,
                        _orig,
                        max_per_category=max_per_category,
                        pass_index=pass_index,
                        scope_tests=scope_tests,
                        mutant_slice=(probe_n, exact),
                        progress=_shift_progress(progress, probe_n, exact),
                        precomputed_line_data=(probe.line_coverage, probe.failing_tests),
                        pregenerated=_mutants,
                    )
                    fanned = parallel.merge_results([probe, rest])
            if fanned is not None:
                if use_cache and not fanned.budget_exhausted:
                    verdict_cache.put(root, ck, verdict_cache.key_prefix(func_key), fanned)
                return fanned

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
    learn: bool = False,
    use_parallel: bool | None = None,
    progress: Callable[[int, int, float], None] | None = None,
    trace_budget_s: float | None = _WESKER_DEFAULT_TRACE_BUDGET_S,
    trace_progress: Callable[[int, int, float], None] | None = None,
    trace_session_budget_s: float | None = None,
) -> ScopeMap:
    """Profile ``function`` and reshape the result into a behavioral-scope map.

    Always attaches the STRUCTURAL decomposition signal (``decompose_seams``) so the CLI can
    pair it with regime B — the convergent "really two things" flag. ``learn=True`` also folds
    this run's per-category value-survival into ``.wesker/mutation_report.json`` and attaches
    the learned-weak priors (see :func:`learn_priors`). ``use_parallel=True`` fans the mutants
    across worker processes (mutually exclusive with ``progress``).
    """
    result = profile(
        file,
        function,
        project_root,
        is_pure=is_pure,
        tests=tests,
        budget_ms=budget_ms,
        use_parallel=use_parallel,
        progress=progress,
        trace_budget_s=trace_budget_s,
        trace_progress=trace_progress,
        trace_session_budget_s=trace_session_budget_s,
    )
    scope = scope_from_profiling(result)

    from dataclasses import replace

    updates: dict[str, Any] = {"decompose_seams": _count_decompose_seams(file, function, project_root)}
    if learn:
        priors = learn_priors(result, project_root)
        updates["learned_priors"] = [(p.category.value, p.prior) for p in priors]
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
    synthesized value), PLUS a length-2 variant for each sequence param so
    length-dependent branches (empty/single/2+) get exercised. Golden capture pins the
    output at each; the minimize/audit pass then keeps only the sites that uniquely cover
    a kill or a line — so the suite stays minimal without a per-grid explosion."""
    base: list = []
    seq_variants: list[tuple[int, str]] = []  # (arg index, repr of the length-2 value)
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
        else:
            value = _synth_from_ann(arg.annotation, namespace)
            # A SourceExpr passes through as the OBJECT (eval_call_site skips
            # non-strings), so it reaches capture intact and renders as its
            # constructor source; a plain synthesized value renders via repr.
            base.append(value if isinstance(value, SourceExpr) else repr(value if value is not None else n))
            variants = _seq_length_variants(arg.annotation, namespace)
            if variants is not None and variants[-1]:  # the [elem, elem] length-2 variant
                seq_variants.append((len(base) - 1, repr(variants[-1])))
    sites = [{"positional_args": base}]
    for idx, two_repr in seq_variants:
        variant = list(base)
        variant[idx] = two_repr
        sites.append({"positional_args": variant})
    return sites


def _unreachable_inputs_note(node: ast.AST, qualname: str, inferred: dict[str, str] | None = None) -> str:
    """Actionable Zone-3 message when synthesized inputs can't exercise a function.

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
    inputs = supplied + discovered + inferred_tuples + bounded_product(_input_grids(node, ns))
    # When deterministic synthesis provably can't exercise the function — every
    # candidate raises, i.e. a domain-object parameter no grid can fabricate — reuse
    # a REAL input the covering tests already pass: capture the actual arguments at
    # every entry to the target while the discovered tests run, and retry. This
    # closes structured-input functions to a verdict WITHOUT ever fabricating an
    # input (the abstention below stays the honest fallback when even the tests do
    # not exercise the DOF). Captured real inputs rank just behind a human-supplied
    # residual and ahead of the synthesized grids.
    if not any(not _outcome(original, args).startswith("<raised") for args in inputs):
        func_names = [qn for qn, _ in walk_functions(tree)]
        harvest_tests = discover_test_callables(
            root, os.path.relpath(full, root), func_names, extra_dirs=list(extra_test_dirs) or None
        )
        captured = capture_call_inputs(original, harvest_tests)
        inputs = supplied + captured + inputs
    # Soundness gate: if the original STILL raises on every candidate input, the
    # inputs don't fit this function — any "equivalent" verdict would be spurious.
    if not any(not _outcome(original, args).startswith("<raised") for args in inputs):
        # Execution can't run here — but a manual flag stands regardless.
        unclassified_descs, manual_eq = _split(survivors)
        note = (
            _unreachable_inputs_note(node, qualname or function, inferred_types)
            if unclassified_descs
            else None
        )
        return SurvivorReport((), unclassified_descs, note=note, manual_equivalent=manual_eq)

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
        tuple(verdicts), tuple(unclassified), None, manual_equivalent=tuple(manual_equivalent)
    )


def learn_priors(result: Any, project_root: str) -> list:
    """Optional learned-weak signal (opt-in via ``diagnose --learn``): accumulate this
    run's per-category VALUE-survival into ``.wesker/mutation_report.json`` — a running
    aggregate across runs — and return the resulting priors, categories ordered by
    HISTORICAL value-survival (weakest, i.e. highest-survival, first).

    Uses ``value_survived`` (true + crash/timeout kills) rather than raw survivors, so the
    learned-weak signal measures the same thing the rest of the pipeline does: which
    categories this project's own code + tests recurrently leave the VALUE unspecified.
    Reuses Wesker's ``prioritize_categories`` over the accumulated state — the same signal
    Wesker's own budgeted runs prioritize by — so Detective and Wesker read it identically.
    """
    import json
    from pathlib import Path

    from Wesker.filter import prioritize_categories

    report = Path(project_root) / ".wesker" / "mutation_report.json"
    state: dict = {}
    if report.exists():
        try:
            state = json.loads(report.read_text())
        except (OSError, ValueError):
            state = {}
    agg: dict[str, dict] = {
        e["category"]: dict(e)
        for e in state.get("per_category", [])
        if isinstance(e, dict) and e.get("category")
    }
    for cr in result.per_category:
        cat = cr.category.value
        cur = agg.setdefault(cat, {"category": cat, "total": 0, "survived": 0})
        cur["total"] = cur.get("total", 0) + cr.total
        cur["survived"] = cur.get("survived", 0) + cr.value_survived
    state["per_category"] = list(agg.values())
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(state, indent=2))
    return prioritize_categories({cr.category for cr in result.per_category}, state)
