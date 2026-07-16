"""Which test files could possibly execute a target module's lines.

WHY: the baseline trace runs EVERY collected test under a per-line callback to discover
which ones touch the target's lines. Scoping (``Wesker.engine._tests_for``) is correct but
derived FROM that trace, so the trace is the whole bill and it scales with the SUITE, not
the function. Measured on Regenesis: 2134 test functions traced to profile one 13-line
function; the mutation phase never started. 1928 of those (90%) are in modules that cannot
import the target's module even transitively, so they provably cannot execute one of its
lines, so tracing them can only ever produce the empty set.

This computes that "provably cannot" statically, so the live session collects only the rest.

SOUNDNESS IS THE WHOLE POINT. A test wrongly excluded is a lost kill, which surfaces as an
overstated survivor — a tool reporting behavior as unspecified when a test does pin it. That
is precisely the lie the project refuses everywhere else, so this module is conservative in
one direction only: ANY doubt returns None (or includes the file), and None means the caller
collects everything exactly as it does today. It never trades a verdict for speed.
"""

from __future__ import annotations

import ast
import os

# Modules that can reach anything: importing these makes reachability undecidable here.
_DYNAMIC = frozenset({"importlib", "pkgutil", "__import__", "pytest_plugins"})

_SKIP_DIRS = frozenset({"__pycache__", ".git", ".venv", "venv", "dist", "build", ".tox", "node_modules"})


def module_name(root: str, path: str) -> str:
    """Dotted module name for ``path`` relative to ``root``. ``a/b/__init__.py`` -> ``a.b``."""
    rel = os.path.relpath(os.path.abspath(path), os.path.abspath(root))
    stem = rel[:-3] if rel.endswith(".py") else rel
    parts = [p for p in stem.split(os.sep) if p not in ("", ".")]
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _imports_of(tree: ast.AST, this_module: str) -> tuple[set[str], bool]:
    """Every dotted name ``tree`` imports, and whether it does anything undecidable.

    The bool is the escape hatch: a star-import or a dynamic-import module means this file's
    reachability cannot be settled statically, and the caller must assume it reaches.
    Relative imports are resolved against ``this_module``'s package, since an unresolved
    relative import would otherwise look like "imports nothing" — a false NEGATIVE, the one
    error direction that costs a verdict.
    """
    out: set[str] = set()
    opaque = False
    pkg = this_module.rsplit(".", 1)[0] if "." in this_module else ""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out.add(a.name)
                if a.name.split(".")[0] in _DYNAMIC:
                    opaque = True
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                # `from . import x` inside a.b.c -> a.b ; `from .. import x` -> a
                anchor = this_module.split(".")
                anchor = anchor[: len(anchor) - node.level] if node.level <= len(anchor) else []
                base = ".".join([*anchor, base]) if base else ".".join(anchor)
            if not base:
                opaque = True
                continue
            out.add(base)
            for a in node.names:
                if a.name == "*":
                    opaque = True
                else:
                    out.add(f"{base}.{a.name}")
            if base.split(".")[0] in _DYNAMIC:
                opaque = True
        elif isinstance(node, ast.Call):
            fn = node.func
            name = getattr(fn, "id", None) or getattr(fn, "attr", None)
            if name in ("__import__", "import_module"):
                opaque = True
    if pkg:
        out.add(pkg)
    return out, opaque


def _build_graph(root: str) -> tuple[dict[str, set[str]], dict[str, str], set[str]]:
    """``(module -> imported names, module -> path, modules whose imports are opaque)``."""
    graph: dict[str, set[str]] = {}
    paths: dict[str, str] = {}
    opaque: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            p = os.path.join(dirpath, fn)
            try:
                with open(p, encoding="utf-8") as fh:
                    tree = ast.parse(fh.read(), filename=p)
            except (OSError, SyntaxError, ValueError):
                # Unparseable: cannot rule it out, so let it reach (never exclude on error).
                m = module_name(root, p)
                paths[m] = p
                graph[m] = set()
                opaque.add(m)
                continue
            m = module_name(root, p)
            paths[m] = p
            graph[m], is_opaque = _imports_of(tree, m)
            if is_opaque:
                opaque.add(m)
    return graph, paths, opaque


def _reaches(start: str, target: str, graph: dict[str, set[str]], opaque: set[str]) -> bool:
    """Can ``start`` transitively import ``target``? Opaque modules reach everything."""
    seen: set[str] = set()
    stack = [start]
    while stack:
        m = stack.pop()
        if m in seen:
            continue
        seen.add(m)
        if m in opaque:
            return True  # undecidable -> assume yes
        for dep in graph.get(m, ()):
            if dep == target or dep.startswith(target + "."):
                return True
            # `from a.b import c` records "a.b.c"; the module is "a.b". Walk the prefixes
            # so an attribute import still lands on the module that defines it.
            base = dep
            while base:
                if base == target:
                    return True
                if base in graph and base not in seen:
                    stack.append(base)
                if "." not in base:
                    break
                base = base.rsplit(".", 1)[0]
    return False


def reachable_test_paths(root: str, target_file: str) -> list[str] | None:
    """Test files that could execute ``target_file``'s lines, or None to collect everything.

    None is returned whenever the analysis is not trustworthy — no target module, nothing
    found, or every test reaching anyway — so the caller's behavior is byte-identical to
    today. ``conftest.py`` is always included: pytest needs it to collect at all, and a
    dropped conftest turns a scoped collection into a broken one.
    """
    root = os.path.abspath(root)
    target = module_name(root, target_file)
    if not target:
        return None
    graph, paths, opaque = _build_graph(root)
    if target not in graph:
        return None  # target outside the tree -> cannot reason -> collect everything

    keep: list[str] = []
    tests = 0
    for m, p in paths.items():
        base = os.path.basename(p)
        if base == "conftest.py":
            keep.append(p)
            continue
        if not base.startswith("test_"):
            continue
        tests += 1
        if m == target or _reaches(m, target, graph, opaque):
            keep.append(p)
    if not tests:
        return None
    if not any(os.path.basename(p).startswith("test_") for p in keep):
        return None  # nothing reachable is more likely a broken analysis than a real answer
    return sorted(keep)
