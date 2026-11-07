"""Inject `@__omut__("module:Qual.name")` as the innermost decorator of every candidate function.

Candidates: public (no leading underscore), synchronous functions defined at module level or directly in a
module-level class, in the library package's public modules (no underscore-prefixed module; tests
excluded). The decorator line is inserted textually, directly above the `def` line, so it is the
innermost decorator and the rest of the source (comments, docstrings, doctests) is untouched.

Usage: python transform.py <package_dir> <module_prefix> <candidates.json>
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path


def candidates(tree: ast.Module):
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            yield node, node.name
        elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef) and not sub.name.startswith("_"):
                    decos = {ast.unparse(d) for d in sub.decorator_list}
                    if any(d.endswith((".setter", ".deleter")) or d == "overload" for d in decos):
                        continue
                    yield sub, f"{node.name}.{sub.name}"


def transform_file(path: Path, module: str, root: Path) -> list[dict]:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    lines = src.splitlines(keepends=True)
    found = []
    for node, qual in candidates(tree):
        if any(isinstance(d, ast.Name) and d.id == "overload" for d in node.decorator_list):
            continue
        found.append((node.lineno, node.col_offset, f"{module}:{qual}"))
    for lineno, col, name in sorted(found, reverse=True):
        lines.insert(lineno - 1, " " * col + f"@__omut__({name!r})\n")
    path.write_text("".join(lines), encoding="utf-8")
    return [{"name": n, "file": str(path.relative_to(root)), "line": ln} for ln, _, n in sorted(found)]


def main(argv: list[str]) -> int:
    pkg, prefix, out = Path(argv[1]), argv[2], Path(argv[3])
    allc = []
    for f in sorted(pkg.rglob("*.py")):
        rel = f.relative_to(pkg)
        if any(part in ("tests", "test") for part in rel.parts) or rel.name.startswith("test_"):
            continue
        if any(part.startswith("_") and part != "__init__.py" for part in rel.parts):
            continue  # private module: not public API
        mod = ".".join([prefix, *rel.with_suffix("").parts])
        if mod.endswith(".__init__"):
            mod = mod[: -len(".__init__")]
        allc += transform_file(f, mod, pkg.parent)
    out.write_text(json.dumps(allc, indent=1), encoding="utf-8")
    print(f"decorated {len(allc)} functions under {pkg}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
