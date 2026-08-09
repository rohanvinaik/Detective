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
from typing import Any

from Wesker.ci import discover_test_callables, walk_functions

try:
    from Wesker.ci import callable_origin
except ImportError:  # Wesker < 0.9.5 — same resolution rules, applied locally

    def callable_origin(call: Any) -> str | None:
        """Absolute path of the test file a discovered callable came from.

        Discovery hands out WRAPPERS: a live pytest item's runner and a
        re-collected parametrized case are closures whose ``co_filename`` is
        Wesker's own module, not the test's. Resolution must go tag →
        ``__wrapped__`` → code object, or every wrapper "locates" to
        ``pytest_runner.py`` and removal silently no-ops (or worse, edits it).
        """
        tagged = getattr(call, "__wesker_origin__", None)
        if tagged:
            return str(tagged)
        real = getattr(call, "__wrapped__", call)
        code = getattr(real, "__code__", None)
        f = getattr(code, "co_filename", None)
        return os.path.abspath(f) if f else None


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
    # Bracketed names (test_x[case]) — ROWS of a live parametrized test. Removal
    # works at function granularity: deleting the function to prune a row would
    # take the live rows with it, so these are never attempted, only reported.
    parametrized: tuple[str, ...] = ()


def nodeid_kind(identifier: str) -> str:
    """What an audit-reported test identifier NAMES, so removal can act on it (#54, pure — pinned).

    Test identity is a pytest nodeid (Wesker #16), and Wesker emits an explicitly namespaced
    ``legacy:<origin>::<base>[<case>]`` when collection produced no nodeid. So this receives five
    spellings — bare, qualified, parametrized, and the two legacy forms — and used to match only
    the bare one. Every other spelling fell through to ``not_found``, which the CLI renders as
    "outside this function's editable test scope": a POLICY sentence, over a string-format miss.

    Measured: ``apply_removals`` given ``tests/…::test_grade_boundary_0`` removed nothing;
    given ``test_grade_boundary_0`` removed it. The audit passes the former, so `--remove`
    could not remove anything it proposed, and said so in the language of a safety guarantee.

    ``parametrized_case`` — one ROW of a live test. The function is alive (its other rows earn
    their keep), so it must never be deleted to get at the row; the user prunes the row.
    ``qualified`` — carries the file, so removal can target the exact definition.
    ``bare`` — a name only; resolvable, but ambiguous if two files define it.
    ``empty`` — nothing to act on.
    """
    if not identifier:
        return "empty"
    if "[" in identifier:
        return "parametrized_case"
    if "::" in identifier:
        return "qualified"
    return "bare"


def nodeid_function_name(identifier: str) -> str:
    """The bare function name an audit-reported identifier denotes (#54, pure — pinned).

    Strips the ``legacy:`` namespace, any ``path::`` qualifier, and any ``[case]`` row suffix.
    This is what must be matched against a discovered callable's ``__name__``.
    """
    rest = identifier[len("legacy:") :] if identifier.startswith("legacy:") else identifier
    if "::" in rest:
        rest = rest.rsplit("::", 1)[1]
    return rest.split("[", 1)[0]


def nodeid_file_hint(identifier: str) -> str:
    """The FILE an identifier names, or "" when it does not name one (#54, pure — pinned).

    Used to delete the RIGHT definition when two files define the same test name — matching on
    the bare name alone would pick whichever the discovery happened to yield first, and deleting
    the wrong test is the one mistake this module must never make.

    ``?`` is Wesker's explicit unknown-origin placeholder in the legacy form; it names no file,
    so it must not be treated as one.
    """
    rest = identifier[len("legacy:") :] if identifier.startswith("legacy:") else identifier
    if "::" not in rest:
        return ""
    head = rest.rsplit("::", 1)[0]
    return "" if head == "?" else head


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
    # Match on the RESOLVED function name, not the raw identifier (#54). `names` arrives as
    # pytest nodeids, so comparing them to a callable's `__name__` never matched and every
    # request became `not_found`. A file hint, where the identifier carries one, additionally
    # pins WHICH definition — two files defining one test name must not resolve to whichever
    # discovery yielded first.
    wanted_names = {nodeid_function_name(n) for n in names}
    hints: dict[str, set[str]] = {}
    for n in names:
        hints.setdefault(nodeid_function_name(n), set()).add(nodeid_file_hint(n))
    by_file: dict[str, set[str]] = {}
    for call in callables:
        name = getattr(call, "__name__", "")
        if name not in wanted_names:
            continue
        path = callable_origin(call)
        if not path:
            continue
        # An identifier that named a file only matches the definition IN that file. An empty
        # hint means the identifier named none, so any in-root definition of the name qualifies.
        _hints = {h for h in hints.get(name, set()) if h}
        if _hints and not any(
            os.path.abspath(path) == os.path.abspath(os.path.join(root, h)) for h in _hints
        ):
            continue
        # Only files under the project root are candidates for editing. A path
        # outside it means origin resolution fell through to a wrapper's own
        # module (site-packages) — deleting "a test" from THERE is the one edit
        # this function must never make, so the name stays unlocated instead.
        if not os.path.abspath(path).startswith(root + os.sep):
            continue
        by_file.setdefault(path, set()).add(name)
    return by_file


def apply_removals(file: str, project_root: str, names: list[str]) -> RemovalReport:
    """Delete the named test functions from their source files.

    CALLER MUST HAVE CONFIRMATION: this writes to the user's test files. It removes
    only the ``names`` it is given (the audit's redundant set), and rewrites each
    file once. A name whose definition cannot be located is reported in
    ``not_found``, never guessed at."""
    wanted = set(names)
    # A bracketed name is one CASE of a parametrized test — a row, not a
    # function. The function is alive (its other rows earn their keep, or it
    # would have been proposed by its bare name), so it must not be deleted to
    # get at the row. Set aside and report; the user prunes the row.
    cases = {n for n in wanted if nodeid_kind(n) == "parametrized_case"}
    wanted -= cases
    by_file = _locate(project_root, file, wanted)
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
    # Keyed off REMOVED, not located: a name can locate to a file whose parse
    # then shows no such top-level def (a stale collection, a nested test). The
    # old `wanted - located` accounting made that case silently vanish from the
    # report — neither removed nor not_found — which is how a total no-op once
    # printed as a clean "removed nothing" with no reason attached.
    # Report in the spelling the CALLER used. `removed` accumulates resolved function names, but
    # the user was shown nodeids and a report that answers in a different vocabulary reads as a
    # different set of tests.
    _removed_names = set(removed)
    removed_ids = [n for n in wanted if nodeid_function_name(n) in _removed_names]
    not_found = tuple(sorted(wanted - set(removed_ids)))
    return RemovalReport(tuple(sorted(removed_ids)), not_found, tuple(sorted(changed)), tuple(sorted(cases)))
