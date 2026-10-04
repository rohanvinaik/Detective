"""Apply confirmed deletions to a test suite — remove named test functions.

The audit PROPOSES which tests are pointless (redundant for both completeness
axes); this module carries out the removal once a human confirms it. Deletion is
never automatic: a test the mutation+line matrices call redundant may still guard
a regression neither matrix models, so the caller gates every removal behind an
explicit confirmation (the ``--remove`` flag), and only tests the audit itself
flagged are ever eligible.

The core (:func:`remove_definition_from_source`) is pure — source in, source out —
so the risky part (which definition to drop) is deterministic and testable; the
file I/O and discovery are a thin shell around it. Every id gets a named outcome
(`removal_disposition`, `removal_outcome_why`), and only the definition an id
exactly names is ever deleted (#103).
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


def remove_definition_from_source(source: str, qualname: str) -> tuple[str, str]:
    """``source`` with ONE test definition removed, and the outcome (#103, #106, pure — pinned).

    ``qualname`` is the definition's Python qualified name: ``test_x`` for a module-level test,
    ``TestC.test_m`` for a method (classes may nest). The span removed runs from the first decorator
    (or the ``def`` line when undecorated) through ``end_lineno``, plus ONE of the two blank-line
    separators around it: the one after it when another statement follows it in its block, the one
    before it when it is the block's last statement. The spacing left between its neighbours is then
    one the file already had, so a formatter-clean file stays clean (#106: the single trailing blank
    this replaced left three blank lines between top-level functions, and trailing blanks at the end).

      "removed"   the definition is gone. A class it leaves with no statement keeps a ``pass``, so the
                  file still parses and the class's other members, decorators and bases are untouched.
      "missing"   no definition of that qualified name exists in this source: the collection that
                  proposed it is stale, or the source does not parse. Any parser failure counts, not
                  only a SyntaxError: on 3.14 a deep expression overflows the parser stack as a
                  MemoryError, and a lone surrogate raises UnicodeEncodeError (measured).
      "shadowed"  the name is bound more than once in its scope. Python keeps the LAST binding, so
                  removing either copy deletes the live test or resurrects a dead one; neither is the
                  edit that was asked for. (The function this replaced removed the FIRST copy: the dead
                  one, reporting the live test as deleted.)
    """
    try:
        tree = ast.parse(source)
    # BLE001: whatever the parser raises on a str (syntax, surrogate, stack overflow), it defines nothing
    except Exception:  # noqa: BLE001
        return ("missing", source)
    parts = [p for p in qualname.split(".") if p]
    if not parts:
        return ("missing", source)
    body: list[ast.stmt] = tree.body
    owner: ast.ClassDef | None = None
    for name in parts[:-1]:
        classes = [n for n in body if isinstance(n, ast.ClassDef) and n.name == name]
        if len(classes) != 1:
            return ("shadowed" if classes else "missing", source)
        owner = classes[0]
        body = owner.body
    defs = [n for n in body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == parts[-1]]
    if len(defs) != 1:
        return ("shadowed" if defs else "missing", source)
    node = defs[0]
    start = min([node.lineno, *(d.lineno for d in node.decorator_list)])
    end = node.end_lineno or node.lineno
    lines = source.splitlines(keepends=True)
    if owner is not None and len(owner.body) == 1:
        # The method was the class's only statement, and an empty class body is a syntax error.
        lines[start - 1 : end] = [" " * node.col_offset + "pass\n"]
    elif node is body[-1]:
        # The block's last statement takes the separator BEFORE it, so whatever follows the block (the
        # next outer statement, or the end of the file) keeps the spacing it had. Counted over a finite
        # slice rather than walked with a loop, so no mutant of the count can fail to terminate.
        above = lines[: start - 1]
        start -= next((i for i, line in enumerate(reversed(above)) if line.strip()), len(above))
        del lines[start - 1 : end]
    else:
        # Any other takes the separator AFTER it, so the statement before it keeps its own spacing.
        below = lines[end:]
        end += next((i for i, line in enumerate(below) if line.strip()), len(below))
        del lines[start - 1 : end]
    return ("removed", "".join(lines))


@dataclass(frozen=True)
class RemovalReport:
    """Outcome of applying deletions: what was removed and from where."""

    removed: tuple[str, ...]  # ids whose OWN definition was deleted (exact, never by bare name)
    not_found: tuple[str, ...]  # ids kept for any reason but being a row; each has its cause in `outcomes`
    files_changed: tuple[str, ...]  # files rewritten
    # Bracketed names (test_x[case]) — ROWS of a live parametrized test. Removal
    # works at function granularity: deleting the function to prune a row would
    # take the live rows with it, so these are never attempted, only reported.
    parametrized: tuple[str, ...] = ()
    # (id, code) for EVERY requested id — `removal_disposition`'s codes plus the edit's own
    # "removed" / "stale_collection" / "shadowed" — so no id is reported without its cause (#103).
    outcomes: tuple[tuple[str, str], ...] = ()


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


def nodeid_parts(identifier: str) -> tuple[str, str, str]:
    """The (file, qualified name, case) an audit-reported identifier names (#103, pure — pinned).

    ``tests/t.py::TestC::test_m[x-1]`` → ``("tests/t.py", "TestC.test_m", "x-1")``. The file is the
    FIRST ``::`` segment and every later one is a scope. Before #103 the file was everything before
    the LAST ``::``, so a class-method id named ``tests/t.py::TestC`` as its file, which equals no path:
    every class-method candidate fell to `not_found`, under a sentence calling it a scope policy.
    The ``legacy:`` namespace is stripped, Wesker's ``?`` unknown-origin placeholder names no file, and
    its ``#display`` disambiguator is not part of the name. A bare name names no file.
    """
    rest = identifier[len("legacy:") :] if identifier.startswith("legacy:") else identifier
    rest, bracket, case = rest.partition("[")
    if bracket and case.endswith("]"):
        case = case[:-1]
    if "::" not in rest:
        return ("", rest.split("#", 1)[0], case)
    head, _, tail = rest.partition("::")
    return ("" if head == "?" else head, tail.split("#", 1)[0].replace("::", "."), case)


def removal_disposition(kind: str, located: int, shape: str) -> str:
    """What `--remove` may do with ONE candidate it was handed, before any file is touched (#103,
    pure — pinned).

    ``kind`` is `nodeid_kind`'s code; ``located`` counts the distinct definitions the id resolves to
    in the current suite; ``shape`` is ``function`` or ``method`` for a definition the editor can
    remove intact, anything else otherwise.

      "parametrized_row"  one row of a live parametrized test. Its function is alive while any other
                          row earns its keep, so a row is never edited here (rows: #102 A3).
      "not_located"       nothing in the current source answers to the id.
      "ambiguous"         the id names no file and several definitions answer to it. Deleting all of
                          them deletes tests nobody proposed (the function this replaced did exactly
                          that), and picking one is a guess.
      "unsupported_shape" exactly one definition, but not a module-level function or a class method.
      "remove"            exactly one supported definition: the edit that was asked for.
    """
    if kind == "parametrized_case":
        return "parametrized_row"
    if kind == "empty" or located <= 0:
        return "not_located"
    if located > 1:
        return "ambiguous"
    if shape not in ("function", "method"):
        return "unsupported_shape"
    return "remove"


def removal_outcome_why(code: str, subject: str = "") -> str:
    """The one sentence each removal outcome renders as (#103, pure — pinned).

    One owner, so the per-test lines, the closing summary and the JSON carry the same words and cannot
    drift apart. ``subject`` is the detail a code's sentence names: the function a kept candidate is
    still needed by (``retained_for``), the target (``target_unresolved``), how its re-run ended
    (``reach_not_reproduced``), or the functions it runs that went unchecked (``reach_unmeasured``,
    ``reach_over_budget``). An unknown code renders NAMED, never blank: a blank beside a kept test reads
    as "no reason".
    """
    sentences = {
        "removed": "deleted: redundant for this function and for every function it was observed to execute",
        "retained_for": (
            f"kept: {subject or 'another function'} still needs it (a kill or a line only it supplies)"
        ),
        "target_unresolved": (
            f"kept: {subject or 'this function'}'s own measurement admits no certificate,"
            " so its redundancy there is not established"
        ),
        "reach_unobserved": "kept: no collected test answers to this id, so its run could not be observed",
        "reach_not_reproduced": (
            f"kept: re-run by itself it did not pass (it {subject or 'gave no verdict'}),"
            " so what it executes is unknown"
        ),
        "reach_unmeasured": (
            f"kept: it executes {subject or 'a function'} with no valid measurement,"
            " so its removal is not proven safe"
        ),
        "reach_over_budget": (
            f"kept: it executes {subject or 'functions'} left unchecked when the reach budget ran out;"
            " re-run with a larger --reach-budget"
        ),
        "parametrized_row": (
            "kept: a row of a live parametrized test; rows are never edited (prune it by hand)"
        ),
        "not_located": "kept: no definition in the current source answers to this id",
        "ambiguous": (
            "kept: the id names no file and several definitions answer to it; deleting any would be a guess"
        ),
        "unsupported_shape": (
            "kept: not a module-level test or a class method, so it cannot be removed intact"
        ),
        "stale_collection": "kept: collected, but the source no longer defines it there; re-run the audit",
        "shadowed": (
            "kept: its name is defined twice in one scope, and removing either copy changes which test runs"
        ),
    }
    return sentences.get(code, f"unrecognised removal outcome: {code}")


_SUMMARY_ORDER = (
    ("retained_for", "still needed by another function"),
    ("target_unresolved", "unestablished (the target's own measurement admits no certificate)"),
    ("reach_unobserved", "not collected, so never run"),
    ("reach_not_reproduced", "did not pass when re-run by themselves"),
    ("reach_unmeasured", "run a function with no valid measurement"),
    ("reach_over_budget", "past the reach budget (re-run with a larger --reach-budget)"),
    ("parametrized_row", "parametrized row(s), report-only"),
    ("not_located", "not found in the current source"),
    ("ambiguous", "ambiguous (an id naming no file, with several definitions)"),
    ("unsupported_shape", "of a shape that cannot be removed intact"),
    ("stale_collection", "stale (re-run the audit)"),
    ("shadowed", "defined twice in one scope"),
)


def removal_summary(codes: list[str]) -> str:
    """Why a `--remove` run deleted nothing, as one clause (#103, pure — pinned).

    Counts the kept candidates by outcome, in a fixed order so the same run always reads the same.
    A code outside the vocabulary is still counted, by its own name, never folded into another; and
    an empty list says so, rather than going silent.
    """
    if not codes:
        return "no candidate was safely removable"
    known = dict(_SUMMARY_ORDER)
    parts = [f"{codes.count(code)} {label}" for code, label in _SUMMARY_ORDER if code in codes]
    parts += [f"{codes.count(code)} {code}" for code in sorted(set(codes)) if code not in known]
    return ", ".join(parts)


def _test_qualname(call: Any) -> str:
    """The Python qualified name of the test a discovered callable runs.

    The ``__wrapped__`` function's when discovery wrapped the test (the live-item shape); else the
    scopes of the nodeid a live wrapper carries as its ``__qualname__``; else the callable's own
    ``__name__`` when its qualname is a closure's. pytest collects no nested test, so a ``<locals>``
    qualname is always a wrapper's own, never the test's.
    """
    wrapped = getattr(call, "__wrapped__", None)
    if wrapped is not None:
        return str(getattr(wrapped, "__qualname__", "") or getattr(wrapped, "__name__", "") or "")
    qual = str(getattr(call, "__qualname__", "") or "")
    if "::" in qual:
        return nodeid_parts(qual)[1]
    if not qual or "<locals>" in qual:
        return str(getattr(call, "__name__", "") or "")
    return qual


def _definition_shape(qualname: str) -> str:
    """``function`` / ``method`` for a definition the editor can remove intact, ``unsupported`` else."""
    if not qualname or "<" in qualname:
        return "unsupported"
    return "method" if "." in qualname else "function"


def _resolve_definitions(project_root: str, file: str, ids: set[str]) -> dict[str, set[tuple[str, str]]]:
    """Each requested id → the (real path, qualified name) definitions it denotes in the current suite.

    Resolution goes through Wesker's discovery, the same callables that were profiled, so an id
    resolves to the exact test that ran (#54). An id that names a file matches only the definition IN
    that file with that qualified name, so two files defining one test name never resolve to each
    other. An id that names no file matches every definition of that name, and `removal_disposition`
    refuses more than one as ``ambiguous`` (#103: the function this replaced deleted them ALL). Only
    files under the project root answer: an origin outside it is a wrapper's own module
    (site-packages), the one file this module must never edit.
    """
    aroot = os.path.abspath(project_root)
    rroot = os.path.realpath(project_root)
    full = file if os.path.isabs(file) else os.path.join(aroot, file)
    with open(full, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=full)
    callables = discover_test_callables(
        aroot, os.path.relpath(full, aroot), [qn for qn, _ in walk_functions(tree)]
    )
    wanted = {ident: nodeid_parts(ident) for ident in ids}
    found: dict[str, set[tuple[str, str]]] = {ident: set() for ident in ids}
    for call in callables:
        origin = callable_origin(call)
        if not origin:
            continue
        real = os.path.realpath(origin)
        if not real.startswith(rroot + os.sep):
            continue
        qual = _test_qualname(call)
        for ident, (hint, name, _case) in wanted.items():
            if hint:
                if qual == name and os.path.realpath(os.path.join(aroot, hint)) == real:
                    found[ident].add((real, qual))
            elif name and (qual == name or qual.rsplit(".", 1)[-1] == name):
                found[ident].add((real, qual))
    return found


def apply_removals(file: str, project_root: str, names: list[str]) -> RemovalReport:
    """Delete the named test definitions from their source files, and name every id's outcome.

    CALLER MUST HAVE CONFIRMATION: this writes to the user's test files. It removes only the ``names``
    it is given (the audit's redundant set, already filtered by `audit.module_safe_removals`), each
    resolved to exactly ONE definition (`removal_disposition`), and rewrites each file once,
    atomically. An id is reported removed only when its own definition was deleted: the function this
    replaced accounted by bare name, so a same-named test in another file read as removed (#103).
    """
    wanted = set(names)
    # A bracketed name is one CASE of a parametrized test — a row, not a function. The function is
    # alive (its other rows earn their keep), so it must not be deleted to get at the row.
    outcomes: dict[str, str] = {
        n: "parametrized_row" for n in wanted if nodeid_kind(n) == "parametrized_case"
    }
    rest = sorted(wanted - set(outcomes))
    found = _resolve_definitions(project_root, file, set(rest)) if rest else {}
    plan: dict[str, list[tuple[str, str]]] = {}
    for ident in rest:
        defs = found.get(ident, set())
        path, qual = next(iter(defs)) if len(defs) == 1 else ("", "")
        disposition = removal_disposition(nodeid_kind(ident), len(defs), _definition_shape(qual))
        if disposition == "remove":
            plan.setdefault(path, []).append((ident, qual))
        else:
            outcomes[ident] = disposition
    changed: list[str] = []
    for path, items in sorted(plan.items()):
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        touched = False
        for ident, qual in items:
            edit, edited = remove_definition_from_source(source, qual)
            # "missing" after a definite resolution means the source moved under the collection.
            outcomes[ident] = edit if edit in ("removed", "shadowed") else "stale_collection"
            if edit == "removed":
                source, touched = edited, True
        if touched:
            from .atomic_store import atomic_write_text

            # Atomic (EP-A4): this is the USER's test file; an interrupted removal must leave the
            # original file whole, never half a test module.
            atomic_write_text(path, source)
            changed.append(path)
    removed = tuple(sorted(i for i, c in outcomes.items() if c == "removed"))
    rows = tuple(sorted(i for i, c in outcomes.items() if c == "parametrized_row"))
    kept = tuple(sorted(i for i, c in outcomes.items() if c not in ("removed", "parametrized_row")))
    return RemovalReport(removed, kept, tuple(changed), rows, tuple(sorted(outcomes.items())))
