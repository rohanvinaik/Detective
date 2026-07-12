"""Apply confirmed deletions to a test suite — remove named test functions.

The audit PROPOSES which tests are pointless (redundant for both completeness
axes); this module carries out the removal once a human confirms it. Deletion is
never automatic: a test the mutation+line matrices call redundant may still guard
a regression neither matrix models, so the caller gates every removal behind an
explicit confirmation (the ``--remove`` flag), and only tests the audit itself
flagged are ever eligible.

The core (:func:`remove_function_from_source`) is pure — source in, source out —
so the risky part (which functions to drop) is deterministic and testable; the
file I/O and discovery are a thin shell around it.
"""

from __future__ import annotations

import ast
import os
from dataclasses import dataclass

from Wesker.ci import discover_test_callables, walk_functions


def remove_function_from_source(source: str, name: str) -> str | None:
    """``source`` with the top-level function ``name`` (and any decorators) removed,
    or None if no such function is defined.

    Removes the whole definition span — from the first decorator (or the ``def``
    line when undecorated) through ``end_lineno`` — plus a single blank separator
    line left behind, so the file does not accumulate blank gaps."""
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            start = min([node.lineno, *(d.lineno for d in node.decorator_list)])
            end = node.end_lineno or node.lineno
            lines = source.splitlines(keepends=True)
            del lines[start - 1 : end]
            if start - 1 < len(lines) and lines[start - 1].strip() == "":
                del lines[start - 1]  # drop the single blank the removed block left
            return "".join(lines)
    return None


@dataclass(frozen=True)
class RemovalReport:
    """Outcome of applying deletions: what was removed and from where."""

    removed: tuple[str, ...]  # test names actually deleted
    not_found: tuple[str, ...]  # requested names no source definition matched
    files_changed: tuple[str, ...]  # files rewritten


def _locate(project_root: str, file: str, names: set[str]) -> dict[str, set[str]]:
    """Map each test file path to the requested test names it defines, via Wesker's
    discovery — the same callables that were profiled, so a name resolves to the
    exact function that ran."""
    root = os.path.abspath(project_root)
    full = file if os.path.isabs(file) else os.path.join(root, file)
    rel = os.path.relpath(full, root)
    with open(full, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=full)
    func_names = [qn for qn, _ in walk_functions(tree)]
    callables = discover_test_callables(root, rel, func_names)
    by_file: dict[str, set[str]] = {}
    for call in callables:
        name = getattr(call, "__name__", "")
        if name not in names:
            continue
        path = getattr(getattr(call, "__code__", None), "co_filename", None)
        if path:
            by_file.setdefault(path, set()).add(name)
    return by_file


def apply_removals(file: str, project_root: str, names: list[str]) -> RemovalReport:
    """Delete the named test functions from their source files.

    CALLER MUST HAVE CONFIRMATION: this writes to the user's test files. It removes
    only the ``names`` it is given (the audit's redundant set), and rewrites each
    file once. A name whose definition cannot be located is reported in
    ``not_found``, never guessed at."""
    wanted = set(names)
    by_file = _locate(project_root, file, wanted)
    located = {n for group in by_file.values() for n in group}
    removed: list[str] = []
    changed: list[str] = []
    for path, file_names in by_file.items():
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        touched = False
        for name in sorted(file_names):
            new_source = remove_function_from_source(source, name)
            if new_source is not None:
                source = new_source
                removed.append(name)
                touched = True
        if touched:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(source)
            changed.append(path)
    not_found = tuple(sorted(wanted - located))
    return RemovalReport(tuple(sorted(removed)), not_found, tuple(sorted(changed)))
