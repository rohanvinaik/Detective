"""Manual equivalence flags — the oracle the execution search cannot be.

``classify_survivors`` decides killable / equivalent / uncertain BY EXECUTION. But a
real distinguishing input can need a domain value the synthesizer cannot produce (a
lookup key, a specific object), so a genuinely-equivalent mutant may read as
``uncertain`` or as a false ``equivalent``. A user who KNOWS a survivor is
equivalent records it here; the flag persists per project and classification honors
it — UNLESS execution later finds a real distinguishing witness, because a witness
is proof that the mutant is killable and proof outranks an opinion (the flag is then
ignored and the contradiction surfaced).

The store is USER DATA — manual judgments, not regeneratable analysis — so ``purge``
must never delete it. It is keyed by ``func_key`` plus a hash of the mutation diff,
so a flag applies exactly as long as that mutation still exists on the code.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass

_REL_PATH = os.path.join(".detective", "equivalents.json")


@dataclass(frozen=True)
class EquivalenceFlag:
    """A manual assertion that one mutation of one function is truly equivalent."""

    func_key: str
    diff: str  # the mutation's diff_summary — its stable identity
    verdict: str = "equivalent"
    note: str = ""  # optional rationale


def flag_key(func_key: str, diff: str) -> str:
    """Stable, compact identity for a (function, mutation) pair: the func_key plus a
    hash of the mutation diff. Survives exactly as long as that mutation exists — if
    the code changes so the mutation differs, the key no longer matches (the flag
    simply stops applying rather than silently mis-applying to different code)."""
    digest = hashlib.sha256(diff.encode("utf-8")).hexdigest()[:16]
    return f"{func_key}::{digest}"


def _store_path(project_root: str) -> str:
    return os.path.join(project_root, _REL_PATH)


def load_flags(project_root: str) -> dict[str, EquivalenceFlag]:
    """Every persisted flag, keyed by :func:`flag_key`. Empty (never an error) when
    the store is absent or unreadable — a missing oracle is simply no oracle."""
    try:
        with open(_store_path(project_root), encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return {}
    flags: dict[str, EquivalenceFlag] = {}
    for key, value in raw.items():
        try:
            flags[key] = EquivalenceFlag(**value)
        except (TypeError, ValueError):
            continue  # a malformed entry is skipped, never fatal
    return flags


def save_flags(project_root: str, flags: dict[str, EquivalenceFlag]) -> None:
    """Persist the flag store, creating ``.detective/`` if needed."""
    path = _store_path(project_root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {key: asdict(flag) for key, flag in flags.items()}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)


def add_flag(project_root: str, func_key: str, diff: str, note: str = "") -> EquivalenceFlag:
    """Record (or replace) a manual equivalence flag for one mutation and persist it."""
    flags = load_flags(project_root)
    flag = EquivalenceFlag(func_key=func_key, diff=diff, verdict="equivalent", note=note)
    flags[flag_key(func_key, diff)] = flag
    save_flags(project_root, flags)
    return flag


def is_flagged_equivalent(flags: dict[str, EquivalenceFlag], func_key: str, diff: str) -> bool:
    """True when a user has flagged this exact mutation equivalent."""
    return flag_key(func_key, diff) in flags
