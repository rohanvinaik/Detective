"""The one rule for a file's dotted name when its relative imports need a package (D#129).

Detective names a source file in three places, each for its own consumer: the loader
(``engine._load_original``), the generated tests' import line and the regime report
(``synthesis.oracle_light.importable_module``), and routing (``reachability.module_name``). Each keeps
the name it already gives every file that loads today; they legitimately differ for a plain
directory without ``__init__.py`` (routing names it from the deepest import root, the loader by the
regular-package walk), and both work in their own context.

They agreed only where they were all wrong together. A module with RELATIVE imports in a directory
without ``__init__.py`` — a PEP 420 namespace layout such as ``tools/voice/references.py`` doing
``from .metrics import …`` under ``pythonpath = ["src", "tools/voice"]`` — was named the bare
``references`` by every derivation, and under that name it can never load: the regime called it
clean while ``diagnose`` and ``converge`` refused with "attempted relative import with no known
parent package". This module owns the override every consumer applies to its own name.

The override reads one file and the suite's declared import roots, never the suite itself
(ARCHITECTURE §11), and it is advisory: a file it cannot read or parse keeps its consumer's name.
"""

from __future__ import annotations

import ast
import functools
import os
import tokenize
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class ModuleIdentity:
    """A consumer's dotted name for one file, the rule that chose it, and its import root.

    ``import_root`` is the directory that must be on ``sys.path`` for ``name`` to import, spelled as
    the caller spelled it; "" when the consumer's own name stands (the consumer knows its own root).
    """

    code: str
    name: str
    import_root: str


def relative_import_level(source: str) -> int:
    """The deepest relative import in ``source``: 0 for none or unparsable (D#129, pure — pinned).

    Function-level relative imports count as well as module-level ones: a module loaded with no
    package context imports, but each function that does ``from .x import y`` then raises when it
    runs, in the tests and in every mutant alike (W#46's shape).

    Unparsable means for any reason the parser gives: a syntax error, a null byte, or a source too
    deep for it (``MemoryError: Parser stack overflowed``, ``RecursionError: Stack overflow during
    compilation``). Naming is advisory: the consumer's own name then stands, and the load reports
    the real failure instead of the override raising first.
    """
    try:
        tree = ast.parse(source)
    # BLE001: the try holds only the parse; a source it rejects for any reason has no level to read
    except Exception:  # noqa: BLE001
        return 0
    return relative_level_of(tree)


def relative_level_of(tree: ast.AST) -> int:
    """The deepest relative import in an already-parsed module (0 for none)."""
    return max((n.level for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)), default=0)


def namespace_candidates(rel_parts: list[str], roots: list[str], relative_level: int) -> list[list[str]]:
    """``[name, root]`` pairs under which the file's relative imports have a parent (D#129, pure — pinned).

    ``rel_parts`` is the file's path relative to a base, one element per directory, the stem last
    (``["tools", "voice", "references"]``). ``roots`` are import roots relative to that base,
    ``"/"``-joined, with ``""`` the base itself. Deepest root first, so ``src/pkg/mod.py`` prefers
    ``pkg.mod`` (via ``src``) to ``src.pkg.mod``. A name needs ``relative_level + 1`` components for a
    module and ``relative_level`` for a package's ``__init__`` (whose name IS the package).
    """
    ordered = sorted(roots, key=lambda r: len([p for p in r.split("/") if p]), reverse=True)
    out: list[list[str]] = []
    for root in ordered:
        root_parts = [p for p in root.split("/") if p]
        if rel_parts[: len(root_parts)] != root_parts or len(rel_parts) <= len(root_parts):
            continue
        cand = rel_parts[len(root_parts) :]
        need = relative_level + 1
        if cand[-1] == "__init__":
            cand = cand[:-1]
            need = relative_level
        if cand and len(cand) >= need:
            out.append([".".join(cand), root])
    return out


def module_identity_name(
    current: str, rel_parts: list[str], roots: list[str], relative_level: int
) -> tuple[str, str, str]:
    """``(code, name, root)``: which dotted name the file is imported by (D#129, pure — pinned).

    Codes, each a different fact:

    * ``current`` — the consumer's own name stands: there are no relative imports, or the name is
      deep enough for them. Every file that loads today stays here, so nothing that works moves.
    * ``namespace`` — the name is too shallow; the namespace name under the deepest import root that
      gives the relative imports a parent. Deepest first is routing's own rule (``src/pkg/mod.py``
      is ``pkg.mod``, not ``src.pkg.mod``), so a file with two valid names gets the one routing
      already gives it. Choosing by what the tests import instead would mean reading the suite to
      name one file — the scaling ARCHITECTURE §11 forbids.
    * ``no_package_context`` — relative imports, and no import root gives them a parent: the current
      name stands, and nothing under any root can load it.

    The stem counts as a component of ``current`` unless it is a package's stripped ``__init__``.
    """
    names = current.split(".")
    stem_in_name = bool(rel_parts) and names[-1] == rel_parts[-1]
    need = relative_level + 1 if stem_in_name else relative_level
    # With no relative imports `need` is at most 1, which every name meets: one test covers both.
    if len(names) >= need:
        return "current", current, ""
    candidates = namespace_candidates(rel_parts, roots, relative_level)
    if candidates:
        name, root = candidates[0]
        return "namespace", name, root
    return "no_package_context", current, ""


def _suite_pythonpath(project_root: str) -> tuple[str, ...]:
    """The suite's declared ``pythonpath`` entries, absolute, from the regime's one config reader.

    ``pytest.ini``, ``tox.ini`` and ``setup.cfg`` outrank ``pyproject.toml``, and a bare string is a
    one-entry list; ``regime._pytest_table`` already answers both, so this consumes it rather than
    re-reading ``pyproject.toml`` on faith. Imported at call time because regime imports reachability,
    which imports this module.
    """
    from .regime import _path_list, _pytest_table

    entries = _path_list(_pytest_table(project_root).get("pythonpath"))
    return tuple(os.path.join(project_root, e) for e in entries)


def _source_level(full_path: str) -> int:
    """The file's relative-import level, parsed once per version of the file."""
    try:
        stat = os.stat(full_path)
    except OSError:
        return 0
    return _parsed_level(full_path, stat.st_mtime_ns, stat.st_size)


@functools.lru_cache(maxsize=256)
def _parsed_level(full_path: str, mtime_ns: int, size: int) -> int:
    # `mtime_ns` and `size` key the cache and are never read: every generated test's import line
    # names the target, and a 10k-line module takes ~75 ms to parse, so it parses once per version.
    del mtime_ns, size
    # tokenize.open honours a PEP 263 coding cookie; an unknown cookie is a SyntaxError, and bytes
    # the declared encoding cannot decode are a UnicodeDecodeError (a ValueError).
    try:
        with tokenize.open(full_path) as fh:
            return relative_import_level(fh.read())
    except (OSError, SyntaxError, ValueError):
        return 0


def _relative(path: str, base: str) -> str | None:
    """``path`` below ``base``, ``/``-joined ("" for ``base`` itself); None when it is not below."""
    try:
        rel = os.path.relpath(path, base).replace(os.sep, "/")
    except ValueError:  # another drive (Windows): not below
        return None
    if rel == ".":
        return ""
    return None if rel == os.pardir or rel.startswith(os.pardir + "/") else rel


def _decide(full: str, base: str, current: str, root_dirs: Sequence[str], level: int) -> ModuleIdentity:
    """Apply the pinned rule to one file; only reached when the file HAS relative imports.

    Both sides are compared by real path: a ``sys.path`` entry and the target can name one
    directory by two spellings (``/tmp`` and ``/private/tmp`` on macOS), and a spelling mismatch
    would read as "not under this root" and lose the name. The root comes back as the caller
    spelled it, so a consumer that checks ``sys.path`` for it finds the entry it already has.
    """
    real_base = os.path.realpath(base)
    rel_file = _relative(os.path.realpath(full), real_base) or ""
    rel_parts = [p for p in rel_file.removesuffix(".py").split("/") if p]
    roots: list[str] = []
    spelled: dict[str, str] = {}
    for d in root_dirs:
        rel = _relative(os.path.realpath(d), real_base)
        if rel is not None:
            roots.append(rel)
            spelled.setdefault(rel, d)
    code, name, root = module_identity_name(current, rel_parts, roots, level)
    return ModuleIdentity(code, name, spelled[root] if code == "namespace" else "")


def project_identity(
    project_root: str,
    path: str,
    current: str,
    import_roots: Sequence[str] | None = None,
    relative_level: int | None = None,
) -> ModuleIdentity:
    """The override for a consumer that knows the project: the root plus the suite's import roots.

    The project root is always a root: Detective's live session puts it on ``sys.path`` and its
    pytest verification runs ``python -m pytest`` from it, so a namespace name under it imports in
    every context Detective executes the target. ``import_roots`` defaults to the suite's declared
    ``pythonpath``; ``relative_level`` saves a re-read when the caller already parsed the file.
    """
    root = os.path.abspath(project_root)
    full = os.path.abspath(path if os.path.isabs(path) else os.path.join(root, path))
    level = _source_level(full) if relative_level is None else relative_level
    if not level:
        # The pinned rule's first branch, taken before any filesystem work: no relative imports,
        # no override. Routing names every file in the suite through here.
        return ModuleIdentity("current", current, "")
    extra = _suite_pythonpath(root) if import_roots is None else tuple(import_roots)
    return _decide(full, root, current, (root, *extra), level)


def loader_identity(full_path: str, current: str, path_entries: Sequence[object]) -> ModuleIdentity:
    """The override for the loader, which has no project root: the roots are what this process can
    import from — the ``sys.path`` entries that are directories, read as the import system reads
    them ("" is the working directory; a non-str entry is skipped)."""
    full = os.path.abspath(full_path)
    level = _source_level(full)
    if not level:
        return ModuleIdentity("current", current, "")
    dirs = [
        os.path.abspath(e) if e else os.getcwd()
        for e in path_entries
        if isinstance(e, str) and os.path.isdir(e or os.curdir)
    ]
    return _decide(full, os.path.splitdrive(full)[0] + os.sep, current, dirs, level)
