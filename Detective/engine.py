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
from Wesker.engine import ProfilingResult, generate_mutants, run_function_profiling
from Wesker.filter import filter_categories

from .equivalence import (
    MutantVerdict,
    SurvivorReport,
    _grid_for,
    _outcome,
    _type_of,
    bounded_product,
    classify_survivor,
    is_scalar_type,
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


def profile(
    file: str,
    function: str,
    project_root: str = ".",
    *,
    is_pure: bool | None = None,
    tests: list[Callable[..., Any]] | None = None,
    budget_ms: float | None = None,
) -> ProfilingResult:
    """Profile one function with Wesker and return the raw ``ProfilingResult``.

    When ``tests`` is None, they are discovered via Wesker's pytest-first backend
    (``discover_test_callables``), so idiomatic parametrized suites are bound and
    run — not skipped. When ``is_pure`` is None it is auto-detected (purity module),
    which lets Wesker drop STATE mutations for pure functions.
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
        tests = discover_test_callables(root, rel, func_names)

    # Pass the live target so Wesker seeds the mutant namespace from its
    # __globals__ (module helpers/constants/imports resolve inside the mutant).
    original = _load_original(full, qualname or function)
    return run_function_profiling(node, func_key, categories, tests, original, budget_ms=budget_ms)  # type: ignore[arg-type]


def diagnose(
    file: str,
    function: str,
    project_root: str = ".",
    *,
    is_pure: bool | None = None,
    tests: list[Callable[..., Any]] | None = None,
    budget_ms: float | None = None,
) -> ScopeMap:
    """Profile ``function`` and reshape the result into a behavioral-scope map."""
    result = profile(
        file, function, project_root, is_pure=is_pure, tests=tests, budget_ms=budget_ms
    )
    return scope_from_profiling(result)


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
    "int": 1, "str": "x", "float": 1.0, "bool": True, "tuple": (1,), "list": [1], "dict": {}
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
            return cls(**{
                f.name: _synth_value(_field_type_name(f), namespace, depth + 1)
                for f in dataclasses.fields(cls)
            })
        except Exception:  # noqa: BLE001 — an unconstructible field just yields no instance
            return None
    return None


def _synth_from_ann(ann, namespace: dict, depth: int = 0) -> Any:
    """One representative value for an annotation NODE, recursing into container
    element types (``list[str]`` -> ``['x']``, ``dict[str, int]`` -> ``{'x': 1}``)
    and ``X | None`` unions, then falling back to name-based scalar/dataclass synth."""
    if depth < 5 and isinstance(ann, ast.Subscript) and isinstance(ann.value, ast.Name):
        container, elt = ann.value.id, ann.slice
        if container in ("dict", "Dict", "Mapping") and isinstance(elt, ast.Tuple) and len(elt.elts) == 2:
            return {_synth_from_ann(elt.elts[0], namespace, depth + 1):
                    _synth_from_ann(elt.elts[1], namespace, depth + 1)}
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


def _input_grids(node: ast.AST, namespace: dict) -> list[list]:
    """Per-parameter candidate value lists: a built-in grid for scalars, a
    recursively-synthesized value for a container/dataclass param (element types
    honored), else the integer fallback — so functions taking structured inputs
    become exercisable."""
    grids: list[list] = []
    for arg in node.args.args:  # type: ignore[attr-defined]
        if arg.arg in ("self", "cls"):
            continue
        name = _type_of(arg.annotation)
        if name is not None and not is_scalar_type(name):
            value = _synth_from_ann(arg.annotation, namespace)
            grids.append([value] if value is not None else _grid_for(name))
        else:
            grids.append(_grid_for(name))
    return grids


def representative_site(node: ast.AST, namespace: dict) -> list[dict]:
    """A SINGLE golden call site (not the full grid product): numeric/unannotated
    params get 1, 2, 3… for order-distinction, other scalars a sample value, and
    container/dataclass params a synthesized value. Golden capture pins the output at
    one input; the witness pass adds inputs for killability — so this keeps the
    generated suite minimal instead of emitting one golden test per grid combination."""
    args: list[str] = []
    n = 1
    for arg in node.args.args:  # type: ignore[attr-defined]
        if arg.arg in ("self", "cls"):
            continue
        name = _type_of(arg.annotation)
        if name in (None, "int"):
            args.append(repr(n))
            n += 1
        elif is_scalar_type(name):
            args.append(repr(_grid_for(name)[-1]))
        else:
            value = _synth_from_ann(arg.annotation, namespace)
            args.append(repr(value if value is not None else n))
    return [{"positional_args": args}]


def classify_survivors(
    file: str, function: str, project_root: str = ".", *, max_int: int = 3
) -> SurvivorReport:
    """Classify each surviving mutant as killable (with a distinguishing witness),
    equivalent-candidate, or unclassified — by running the original against the
    mutant over candidate integer inputs.

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

    result = profile(file, function, project_root)
    survivors = result.survivor_records
    descs = tuple(r.get("mutant", r.get("mutant_id", "?")) for r in survivors)
    if not survivors:
        return SurvivorReport((), (), None)

    original = _load_original(full, qualname or function)
    if original is None:
        return SurvivorReport((), descs, note="the live original could not be loaded")

    # Typed + dataclass-synthesized inputs from annotations, so a str/typed/object
    # function is exercised with type-appropriate values (not integers) — otherwise
    # its killable mutants read as false "equivalent".
    inputs = bounded_product(_input_grids(node, getattr(original, "__globals__", {}) or {}))
    # Soundness gate: if the original raises on every candidate input, the inputs
    # don't fit this function — any "equivalent" verdict would be spurious.
    if not any(not _outcome(original, args).startswith("<raised") for args in inputs):
        return SurvivorReport(
            (), descs, note="candidate inputs don't exercise this function — killability undetermined"
        )

    pure = _is_pure(node, is_method="." in (qualname or ""))
    by_id = {m.mutant_id: m for m in generate_mutants(node, filter_categories(node, pure))}  # type: ignore[arg-type]

    verdicts: list[MutantVerdict] = []
    unclassified: list[str] = []
    for rec in survivors:
        mutant = by_id.get(rec.get("mutant_id", ""))
        mutant_fn = _compile_mutant(mutant, original) if mutant is not None else None
        if mutant_fn is None:
            unclassified.append(rec.get("mutant", rec.get("mutant_id", "?")))
            continue
        verdicts.append(
            classify_survivor(
                rec.get("mutant_id", ""),
                rec.get("category", ""),
                rec.get("diff_summary", ""),
                original,
                mutant_fn,
                inputs,
            )
        )
    return SurvivorReport(tuple(verdicts), tuple(unclassified), None)
