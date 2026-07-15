"""Remember the Zone-2 sample inputs a human supplied for a function.

A ``--input`` is the one thing in the pipeline Detective cannot derive: the semantic prior
that synthesis provably could not build (a lookup key, a valid domain object, a specific
source string — §10). Everything else is regeneratable; this is not. Asking for it twice is
asking the human to do the same irreducible work twice — and `decompose` did exactly that,
re-running its internal converge cold and re-printing the residual the user had just filled
for `converge` a moment earlier.

So supplied inputs are USER DATA, kept beside `.detective/equivalents.json` and never
purged (§8). Stored per function key; a later run unions the remembered samples with any
freshly supplied on the CLI, so supplying more only ever adds knowledge.

Literal-only, matching `--input` itself: what is written here round-trips through
``ast.literal_eval``, so the file can never smuggle code into a later run.
"""

from __future__ import annotations

import ast
import json
import os

_FILE = os.path.join(".detective", "inputs.json")


def _path(project_root: str) -> str:
    return os.path.join(os.path.abspath(project_root), _FILE)


def load(project_root: str, func_key: str) -> list[tuple]:
    """The samples remembered for ``func_key``, or [] — never raising: a missing or
    corrupt store means "nothing remembered", which is exactly the cold-start behavior."""
    try:
        with open(_path(project_root), encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return []
    out: list[tuple] = []
    for entry in data.get(func_key, []) or []:
        try:
            value = ast.literal_eval(entry)
        except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
            continue  # not a literal -> not something we wrote -> ignore, never exec
        out.append(tuple(value) if isinstance(value, tuple) else (value,))
    return out


def remember(project_root: str, func_key: str, inputs: list[tuple]) -> None:
    """Union ``inputs`` into the store for ``func_key``. Best-effort: failing to record a
    sample must never fail the run that produced it."""
    if not inputs:
        return
    path = _path(project_root)
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}

    existing = list(data.get(func_key, []) or [])
    seen = set(existing)
    for args in inputs:
        entry = repr(tuple(args))
        if entry not in seen:
            existing.append(entry)
            seen.add(entry)
    data[func_key] = existing
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
    except OSError:
        return


def merge(project_root: str, func_key: str, supplied: list[tuple] | None) -> list[tuple]:
    """The samples a run should use: everything remembered for this function, plus anything
    supplied now (which is also recorded). Order is remembered-then-new and de-duplicated,
    so a run is deterministic in the samples it sees."""
    fresh = list(supplied or [])
    if fresh:
        remember(project_root, func_key, fresh)
    out: list[tuple] = []
    seen: set[str] = set()
    for args in [*load(project_root, func_key), *fresh]:
        key = repr(args)
        if key not in seen:
            seen.add(key)
            out.append(args)
    return out


def describe(project_root: str, func_key: str) -> str:
    """One line naming how many samples were recalled, for the CLI narrative — so a run
    that silently benefits from an earlier `--input` says so."""
    n = len(load(project_root, func_key))
    return f"recalled {n} supplied input(s) from a previous run" if n else ""
