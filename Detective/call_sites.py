"""Discover real inputs by harvesting a function's own call-sites from the repo.

Detective's job is to discover what a function DOES; the honest record of how it is
actually called already lives in the codebase. This walks the project's ASTs, finds
calls to the target, and realizes their positional arguments into concrete values via
``ast.literal_eval`` — deterministic, stdlib-only, and it never executes project code.

A realized call-site is a *correlated, real* input tuple (unlike the per-parameter grids,
which combine each parameter independently and can produce nonsensical mixes). It is the
richest, most honest input source, and it is exactly what lets a function taking
list/dict/unannotated arguments become exercisable — the input-synthesis bottleneck.

Discovery PROPOSES inputs; the profiling engine DISPOSES: a spurious match (a same-named
call elsewhere) yields an input the soundness gate simply drops, so approximate callee
matching is safe.

MVP bounds (extend later, each is additive): positional args only (calls with keywords
are skipped); ``literal_eval`` only (an arg that is a variable / constructor / call is not
realized, so that whole site is skipped); no cross-call caching.
"""

from __future__ import annotations

import ast
import os

_SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".lintgate",
    ".serena",
    "node_modules",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    "build",
    "dist",
}


def _callee_matches(func: ast.expr, target: str) -> bool:
    """True if this call's callee is named ``target`` — a bare name ``target(...)`` or
    an attribute ``x.target(...)``. Approximate by design (see module docstring)."""
    if isinstance(func, ast.Name):
        return func.id == target
    if isinstance(func, ast.Attribute):
        return func.attr == target
    return False


def _realize_args(args: list[ast.expr]) -> tuple | None:
    """All positional args realized to concrete values via ``literal_eval``, or None if
    any is not a literal — realizing a variable/constructor would require executing
    project code, which discovery never does."""
    out = []
    for a in args:
        try:
            out.append(ast.literal_eval(a))
        except (ValueError, SyntaxError, TypeError):
            return None
    return tuple(out)


def _callee_simple_name(func: ast.expr) -> str | None:
    """The bare callee name of a call — ``f`` for ``f(...)`` or ``x.f(...)`` — or None."""
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _return_annotations(trees: list[ast.Module]) -> dict[str, str]:
    """Map function name -> its return annotation source (e.g. ``diagnose`` -> ``ScopeMap``),
    across the whole repo. The first definition seen wins; used to type a call argument
    that is the result of an annotated-return call."""
    anns: dict[str, str] = {}
    for tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.returns is not None:
                anns.setdefault(node.name, ast.unparse(node.returns))
    return anns


def _local_type_bindings(fn: ast.AST, return_anns: dict[str, str]) -> dict[str, str]:
    """Within one function body, ``name -> inferred type source`` for locals whose type
    is statically recoverable: an annotated assignment ``name: T = ...`` (T), or an
    assignment from an annotated-return call ``name = callee(...)`` (callee's return type).

    Only UNAMBIGUOUS names are returned: a variable reused across branches with different
    types — e.g. ``result`` in a CLI dispatcher, bound to ``converge()`` in one branch and
    ``audit()`` in another — is not soundly typeable without flow analysis, so it is
    dropped rather than guessed. A wrong inferred type would mislead both synthesis and the
    actionable note; honest "unannotated" beats a confident wrong answer.
    """
    seen: dict[str, set[str]] = {}
    for stmt in ast.walk(fn):
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            seen.setdefault(stmt.target.id, set()).add(ast.unparse(stmt.annotation))
        elif isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call):
            callee = _callee_simple_name(stmt.value.func)
            ann = return_anns.get(callee) if callee else None
            if ann is not None:
                for tgt in stmt.targets:
                    if isinstance(tgt, ast.Name):
                        seen.setdefault(tgt.id, set()).add(ann)
    return {name: next(iter(types)) for name, types in seen.items() if len(types) == 1}


def infer_param_types(qualname: str, project_root: str, param_names: list[str]) -> dict[str, str]:
    """Best-effort TYPE-NAME per parameter, inferred from how the target is CALLED across
    the repo — for parameters its signature leaves unannotated. Deterministic (stdlib
    ast, no execution): for a call ``target(...args...)`` inside some function, a positional
    arg that is
      * a call ``callee(...)`` whose callee has a return annotation  -> that return type,
      * a local ``name`` bound to ``= callee(...)`` (annotated return) or ``name: T = ...``
        -> that type,
    types the corresponding parameter. Returns ``{param_name: type_source}`` for the params
    it could resolve. Approximate by design — a wrong guess just yields a synthesized value
    the soundness gate drops. Mirrors [[discover_call_site_inputs]]: discovery proposes.
    """
    target = qualname.split(".")[-1]
    root = os.path.abspath(project_root)
    trees: list[ast.Module] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")]
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            try:
                with open(os.path.join(dirpath, filename), encoding="utf-8") as fh:
                    trees.append(ast.parse(fh.read()))
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue
    return_anns = _return_annotations(trees)
    resolved: dict[str, str] = {}
    for tree in trees:
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            local = _local_type_bindings(fn, return_anns)
            for node in ast.walk(fn):
                if not (isinstance(node, ast.Call) and _callee_matches(node.func, target)):
                    continue
                for i, arg in enumerate(node.args):
                    if i >= len(param_names) or param_names[i] in resolved:
                        continue
                    type_src: str | None = None
                    if isinstance(arg, ast.Call):
                        type_src = return_anns.get(_callee_simple_name(arg.func) or "")
                    elif isinstance(arg, ast.Name):
                        type_src = local.get(arg.id)
                    if type_src:
                        resolved[param_names[i]] = type_src
    return resolved


def discover_call_site_inputs(qualname: str, project_root: str, max_sites: int = 12) -> list[tuple]:
    """Realized positional-arg tuples from every literal call to ``qualname`` in the
    repo, ordered by discovery and deduplicated by value. Empty when the function is
    never called with realizable literals (→ the caller falls back to synthesis, and if
    that also can't exercise it, that is an honest Zone-3 'provide a sample input')."""
    target = qualname.split(".")[-1]
    seen: set[str] = set()
    found: list[tuple] = []
    root = os.path.abspath(project_root)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")]
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            try:
                with open(os.path.join(dirpath, filename), encoding="utf-8") as fh:
                    tree = ast.parse(fh.read())
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and not node.keywords and _callee_matches(node.func, target):
                    realized = _realize_args(node.args)
                    if realized is None:
                        continue
                    key = repr(realized)
                    if key in seen:
                        continue
                    seen.add(key)
                    found.append(realized)
                    if len(found) >= max_sites:
                        return found
    return found
