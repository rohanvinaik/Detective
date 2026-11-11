"""A measurement leaves the process as it found it (Detective #86, EP-H4).

"Determinism is the product: any run repeatable" (ARCHITECTURE §11), and every evaluation must be
independent of the others: a measurement's result may not depend on what the process measured
before it. A library-level ``profile()`` imports the project's modules and puts its root on
``sys.path``; left behind, a LATER profile of a different project with a same-named module (``m``)
binds the previous project's ``f`` — the cached module, or once that is evicted the stale file
through ``sys.path`` — and measures code it never wrote (alone: 7 mutants killed; after a
predecessor: 0). The CLI is one process per command and never sees it; library callers and any
long-lived host do.

So the OUTERMOST entry snapshots ``sys.path`` and ``sys.modules`` and, on every exit path, restores
what it changed: the ``sys.path`` entries it added are removed, the project-root modules it caused to
be imported are evicted, and a name it re-bound or dropped is put back to the object it held at
entry. Nested entries (converge's passes, audit's sibling profiles, a profile inside Wesker's live
session) do nothing, so the state the outer one still needs is never torn down and nothing is
re-imported per pass.

``module_restoration`` is the pure decision; ``restoring_process_state`` is the impure boundary.
"""

from __future__ import annotations

import contextlib
import functools
import importlib
import inspect
import os
import sys
import sysconfig
import threading
from collections.abc import Callable, Iterator

# The tool's own top-level packages: never evicted. A lazily imported ``Detective.x`` that landed
# under a project root (self-analysis puts this very tree there) would otherwise be re-imported as a
# second copy and break every ``isinstance`` across the two.
RESERVED_PACKAGES = ("Detective", "Wesker")

_MISSING = object()
_lock = threading.Lock()
_depth = 0


def _within(path: str, root: str) -> bool:
    """True when ``path`` is ``root`` or lies beneath it (a component boundary, not a prefix)."""
    if not path or not root:
        return False
    p, r = os.path.normpath(path), os.path.normpath(root)
    return p == r or p.startswith(r.rstrip(os.sep) + os.sep)


def module_restoration(
    before: dict[str, str],
    after: dict[str, str],
    rebound: list[str],
    roots: list[str],
    protected: list[str],
    reserved: list[str],
) -> dict[str, str]:
    """Which module names a finished measurement must undo, and why (#86, pure — pinned).

    Split out because the impure restore holds live module objects, which no ``--input`` can express;
    the decision is a function of names and ORIGINS only. ``before`` / ``after`` map a module name to
    its origin (a real path, or "" when it has none: builtin, frozen); they need hold only the names
    that CHANGED — present on one side only, or re-bound to a different object (``rebound``).
    ``roots`` are the project's real paths, ``protected`` the real paths that are never the project's
    even when they sit under a root (a venv's site-packages), ``reserved`` top-level package names.

    Returns one code per name:

    * ``unchanged`` — present on both sides, the same object: nothing to do.
    * ``restored_rebound`` — the name now holds a different module and one of the two is the
      project's: put the entry-time object back (deleting it would lose the caller's own import).
    * ``kept_foreign_rebound`` — re-bound, but neither module is the project's: not ours to undo.
    * ``restored_removed`` — held at entry, gone now, and the project's: put it back.
    * ``kept_foreign_removed`` — gone now, but not the project's: not ours to undo.
    * ``evicted`` — new, and its origin is under a project root: it would shadow a later project.
    * ``kept_reserved`` — new, but the tool's own package.
    * ``kept_installed`` — new, under a root but in a protected tree (an installed distribution).
    * ``kept_no_origin`` — new, with no origin (builtin, frozen, a namespace with no path).
    * ``kept_foreign_origin`` — new, with an origin outside every project root.
    """
    codes: dict[str, str] = {}
    for name in sorted(set(before) | set(after)):
        old, new = before.get(name), after.get(name)
        if old is not None and new is not None:
            if name not in rebound:
                codes[name] = "unchanged"
            else:
                mine = any(_within(o, r) for o in (old, new) for r in roots)
                codes[name] = "restored_rebound" if mine else "kept_foreign_rebound"
        elif old is not None:
            mine = any(_within(old, r) for r in roots) and not any(_within(old, p) for p in protected)
            codes[name] = "restored_removed" if mine else "kept_foreign_removed"
        else:
            origin = new or ""
            if name.partition(".")[0] in reserved:
                codes[name] = "kept_reserved"
            elif not origin:
                codes[name] = "kept_no_origin"
            elif not any(_within(origin, r) for r in roots):
                codes[name] = "kept_foreign_origin"
            elif any(_within(origin, p) for p in protected):
                codes[name] = "kept_installed"
            else:
                codes[name] = "evicted"
    return codes


def _realpath(path: str) -> str:
    try:
        return os.path.realpath(path)
    except (OSError, ValueError):
        return ""


def _origin_of(module: object, roots: list[str]) -> str:
    """The real path a live module came from; "" when it has none.

    A regular module reports ``__file__``. A namespace package has none and reports ``__path__``:
    the entry under a project root if there is one, else the first.
    """
    # BLE001: sys.modules holds arbitrary objects; one whose attributes raise has no origin to read
    try:
        file = getattr(module, "__file__", None)
        if isinstance(file, str) and file:
            return _realpath(file)
        entries = [_realpath(str(p)) for p in list(getattr(module, "__path__", None) or ())]
    except Exception:  # noqa: BLE001
        return ""
    for entry in entries:
        if any(_within(entry, r) for r in roots):
            return entry
    return entries[0] if entries else ""


def _protected_trees(path_before: list[str], roots: list[str]) -> list[str]:
    """Real paths that are never the project's though they sit under its root (a venv inside it)."""
    trees = {sys.prefix, sys.base_prefix, sys.exec_prefix}
    with contextlib.suppress(Exception):
        trees.update(
            v for k, v in sysconfig.get_paths().items() if k in ("stdlib", "platstdlib", "purelib", "platlib")
        )
    protected = {_realpath(t) for t in trees if t}
    # An entry the caller already had on sys.path and which sits strictly INSIDE a root is the
    # caller's own import location (an editable install, a src dir): their modules stay.
    for entry in path_before:
        real = _realpath(entry) if entry else ""
        if real and any(_within(real, r) and real != r for r in roots):
            protected.add(real)
    return sorted(p for p in protected if p)


def _evict(name: str, modules: dict[str, object]) -> None:
    sys.modules.pop(name, None)
    parent, _, child = name.rpartition(".")
    owner = sys.modules.get(parent) if parent else None
    if owner is not None and getattr(owner, child, None) is modules.get(name):
        # The kept parent still points at the evicted child; `import parent.child` would return it.
        with contextlib.suppress(Exception):
            delattr(owner, child)


def _restore(
    modules_before: dict[str, object],
    path_before: list[str],
    importer_before: set[str],
    extra_roots: list[str],
) -> None:
    modules_after = dict(sys.modules)
    added_path = [p for p in sys.path if p not in path_before]
    roots = sorted(
        {r for r in (_realpath(p) for p in [*extra_roots, *added_path] if p) if r and r != os.path.sep}
    )
    changed = [
        n
        for n in set(modules_before) | set(modules_after)
        if modules_before.get(n, _MISSING) is not modules_after.get(n, _MISSING)
    ]
    before = {n: _origin_of(modules_before[n], roots) for n in changed if n in modules_before}
    after = {n: _origin_of(modules_after[n], roots) for n in changed if n in modules_after}
    rebound = [n for n in changed if n in before and n in after]
    codes = module_restoration(
        before, after, rebound, roots, _protected_trees(path_before, roots), list(RESERVED_PACKAGES)
    )
    for name in sorted(codes, key=lambda n: -n.count(".")):  # children first
        code = codes[name]
        if code == "evicted":
            _evict(name, modules_after)
        elif code in ("restored_rebound", "restored_removed"):
            sys.modules[name] = modules_before[name]  # ty: ignore[invalid-assignment]
    sys.path[:] = path_before
    for key in [k for k in sys.path_importer_cache if k not in importer_before]:
        sys.path_importer_cache.pop(key, None)
    importlib.invalidate_caches()


def _in_live_session() -> bool:
    """True inside Wesker's live session body, whose own boundary owns the state it set up."""
    try:
        from Wesker.ci import _PROJECT_ROOT
    except ImportError:  # an older Wesker without the session holder: there is no session to defer to
        return False
    return _PROJECT_ROOT.get() is not None


@contextlib.contextmanager
def restoring_process_state(*project_roots: str) -> Iterator[None]:
    """Run a measurement and leave ``sys.path`` / ``sys.modules`` as they were found (#86).

    Outermost entry only: a nested entry (any depth, any thread) and an entry inside a live session
    are no-ops, so what the outer scope still needs is never torn down. Restores on every exit path
    — return, refusal, exception, ``KeyboardInterrupt`` — and never masks the exception in flight.
    """
    global _depth
    with _lock:
        outermost = _depth == 0 and not _in_live_session()
        _depth += 1
    if not outermost:
        try:
            yield
        finally:
            with _lock:
                _depth -= 1
        return
    modules_before = dict(sys.modules)
    path_before = list(sys.path)
    importer_before = set(sys.path_importer_cache)
    try:
        yield
    finally:
        try:
            _restore(modules_before, path_before, importer_before, [p for p in project_roots if p])
        finally:
            with _lock:
                _depth -= 1


def restores_process_state[**P, R](
    roots_of: Callable[[inspect.BoundArguments], list[str]],
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorate a top-level entry so it runs under ``restoring_process_state`` (#86).

    ``roots_of`` reads the project roots from the call's bound arguments. The wrapper keeps the
    entry's signature (``functools.wraps``), so introspection and type checkers see the original.
    """

    def decorate(fn: Callable[P, R]) -> Callable[P, R]:
        signature = inspect.signature(fn)

        @functools.wraps(fn)
        def entry(*args: P.args, **kwargs: P.kwargs) -> R:
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()
            with restoring_process_state(*roots_of(bound)):
                return fn(*args, **kwargs)

        return entry

    return decorate
