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
import importlib.util
import os
import sys
from collections.abc import Callable
from typing import Any

from Wesker.ci import discover_test_callables, walk_functions
from Wesker.engine import ProfilingResult, run_function_profiling
from Wesker.filter import filter_categories

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
    """Import the module under test and return the live target object.

    Wesker seeds each mutant's namespace from ``original_func.__globals__`` so the
    mutant can resolve the module's sibling helpers, constants, and imports. Returns
    None if the module can't be imported (Wesker degrades to an empty namespace).
    """
    try:
        stem = os.path.splitext(os.path.basename(full_path))[0]
        name = f"_detective_uut_{stem}"
        spec = importlib.util.spec_from_file_location(name, full_path)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        # Register before exec: dataclass processing (and pickling) resolves the
        # class's module via sys.modules[cls.__module__].
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    except Exception:
        return None
    obj: Any = mod
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
