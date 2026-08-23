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
    from .atomic_store import atomic_write_text

    path = _store_path(project_root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {key: asdict(flag) for key, flag in flags.items()}
    # Atomic replace (#63): an equivalence declaration is irreducible human input; a mid-write crash
    # must not clobber the store into an empty file the next load silently accepts and overwrites.
    atomic_write_text(path, json.dumps(payload, indent=2))


def add_flag(project_root: str, func_key: str, diff: str, note: str = "") -> EquivalenceFlag:
    """Record (or replace) a manual equivalence flag for one mutation and persist it."""
    flags = load_flags(project_root)
    flag = EquivalenceFlag(func_key=func_key, diff=diff, verdict="equivalent", note=note)
    flags[flag_key(func_key, diff)] = flag
    save_flags(project_root, flags)
    return flag


def is_flagged_equivalent(flags: dict[str, EquivalenceFlag], func_key: str, diff: str) -> bool:
    """True when a user has flagged this exact mutation equivalent.

    Verdict-BLIND on purpose (back-compat): ``True`` for ANY flag whose key matches. The
    two-sign contract must instead branch on the flag's ``verdict`` — use :func:`flag_verdict`
    and :func:`contract_disposition`, which do not collapse ``fence`` into ``equivalent``.
    """
    return flag_key(func_key, diff) in flags


def flag_verdict(flags: dict[str, EquivalenceFlag], func_key: str, diff: str) -> str:
    """The verdict a user recorded for this exact mutation, or ``""`` when unflagged.

    The verdict-AWARE accessor :func:`contract_disposition` consumes: ``"equivalent"`` (the
    survivor computes the intended function) or ``"fence"`` (an authored MUST-NOT — this
    survival is a bug, Def. 12.1 ``invalid``). Object handling only; it holds no decision.
    """
    flag = flags.get(flag_key(func_key, diff))
    return flag.verdict if flag is not None else ""


def contract_disposition(
    buildable: bool,
    killable: bool,
    blocked: bool,
    flag_verdict: str,
) -> str:
    """The two-sign contract's per-survivor disposition (§18 Q8, pure — pinned).

    ``classify_survivors`` combines a mutant's execution verdict with any manual flag. The
    one-sign predecessor, :func:`is_flagged_equivalent`, was verdict-BLIND: it read a flag as
    "equivalent" regardless of its ``verdict`` field. A two-sign contract also carries
    ``fence`` flags (an authored MUST-NOT), and collapsing the two into one truthy check would
    route a fenced bug into the ``equivalent`` bucket — silently marking a must-not as valid,
    the exact soundness inversion Def. 9.5 forbids. This is that split, made total over the
    states the classifier actually distinguishes.

    ``flag_verdict`` is ``""`` (no flag), ``"equivalent"``, or ``"fence"``. Returns a named
    code, never a bool (two conditions that mean different things must not fuse):

    * ``"killable"``     — a distinguishing witness exists; PROOF outranks any flag.
    * ``"unclassified"`` — no verdict to trust (the search was ``blocked``/timed out, or the
      mutant was un-buildable and no flag speaks for it): honest uncertainty.
    * ``"equivalent"``   — flagged valid, no witness: the survivor computes the intended
      function; suppress it (the ``manual_equivalent`` bucket).
    * ``"fence"``        — flagged a must-not, no witness: the authored negative fence is
      UNENFORCED by the suite — report it as an unpinned negative degree of freedom, never
      suppress it as equivalent.
    * ``"candidate"``    — no flag, no witness, buildable, not blocked: the plain
      candidate-equivalent / crash-only verdict stands.
    """
    if not buildable:
        # No execution verdict exists; the flag is the only signal we have.
        if flag_verdict == "equivalent":
            return "equivalent"
        if flag_verdict == "fence":
            return "fence"
        return "unclassified"
    if killable:
        return "killable"  # a real witness — proof outranks the flag
    if blocked:
        return "unclassified"  # the witness search timed out: honest uncertainty, not equivalence
    if flag_verdict == "equivalent":
        return "equivalent"
    if flag_verdict == "fence":
        return "fence"
    return "candidate"
