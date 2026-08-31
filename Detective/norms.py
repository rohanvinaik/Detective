"""Norms mining for the bank geometry — the Wave 1 pure decisions (EXP-DS-002).

Design: ``docs/theory/deterministic_sicp/DETERMINISTIC_SICP.md`` §4.2 (the norms discipline) and
§12 Wave 1. A bank's zero is MINED from the corpus, κ-weighted (call-graph in-degree, so dead or
unreferenced code cannot drag the norm — the Peitho median-of-active move), and SPLIT-VALIDATED
(mined independently on each hash-parity half; a norm whose halves disagree is rejected, never
tuned — the EXP-RF-005a protocol). This module holds only the PURE decisions of that discipline —
total functions over literals, each Detective-pinned; the corpus walking and the call-graph read
live with their callers (`kappa.build_call_graph`, the dev/ measurement harness).

Also here: :func:`verdict_isolation_cost`, the σ_form read-cost of one region — the quantity whose
corpus distribution locates the bulk/tail knee (the transport's go/no-go measurement).
"""

from __future__ import annotations

import hashlib


def split_of(qualname: str) -> str:
    """Hash-parity corpus split (pure — pinned): ``"A"`` or ``"B"`` by the parity of the last
    byte of the name's sha256. Deterministic and seedless, so the same function lands in the
    same half in every session — the property that makes "mine on A, validate on unseen B"
    (EXP-RF-005a) reproducible rather than a shuffled accident."""
    return "A" if hashlib.sha256(qualname.encode("utf-8")).digest()[-1] % 2 == 0 else "B"


def weighted_median(values: list[float], weights: list[float]) -> float | None:
    """The mined-zero estimator (pure — pinned): the κ-weighted median — the smallest value at
    which cumulative weight reaches half the total. ``None`` — cannot-determine, never a
    fabricated 0.0 — when the inputs are degenerate: empty, length-mismatched, or carrying no
    positive weight. Weighting is what lets a call-graph hub count more than dead code without
    EXCLUDING anything outright (an entry point has no callers and still belongs in the corpus;
    weight 1 means it counts once and cannot drag)."""
    if not values or len(values) != len(weights):
        return None
    pairs = sorted((v, w) for v, w in zip(values, weights, strict=True) if w > 0)
    total = sum(w for _, w in pairs)
    if total <= 0:
        return None
    acc = 0.0
    for v, w in pairs:
        acc += w
        if acc * 2 >= total:
            return v
    # Unreachable totality fall-through (the flag-line class): on the last pair acc == total
    # exactly — the same additions in the same order as `total`'s sum — so the loop always
    # returns. Kept only so the function is total for the type checker; no input reaches it.
    return pairs[-1][0]


def norm_disposition(zero_a: float | None, zero_b: float | None, rel_tolerance: float) -> str:
    """Split-validation verdict for one mined norm (pure — pinned). Named codes, never a bool —
    the three states demand different actions and must not collapse:

      "admissible"  both halves minable and agreeing within ``rel_tolerance`` — the norm may
                    be adopted as a bank zero
      "drifting"    both halves minable but disagreeing — the norm FAILS out-of-sample and is
                    rejected (never tuned toward agreement; §4.2 law 1)
      "degenerate"  either half unminable (too little data / no positive weight) — a
                    measurement limit, not a verdict about the norm
    """
    if zero_a is None or zero_b is None:
        return "degenerate"
    scale = max(abs(zero_a), abs(zero_b))
    if scale == 0:
        return "admissible"  # both halves agree the norm is exactly zero
    return "admissible" if abs(zero_a - zero_b) / scale <= rel_tolerance else "drifting"


def verdict_isolation_cost(votes: tuple[int, ...], flag_floor: int = 2) -> int:
    """σ_form's per-region read cost (pure — pinned): consuming the priority-ordered bank votes
    one at a time, the number of reads after which the flagged/clean verdict is INVARIANT to
    every remaining read — decided-flagged the moment the smell count reaches ``flag_floor``
    (more reads cannot un-flag), decided-clean the moment the smells so far plus every remaining
    read could no longer reach it. The corpus distribution of this quantity is the bulk/tail
    knee measurement (DETERMINISTIC_SICP §3.2): a large early-decided mass is the bulk the
    transport predicts; the late-decided residual is the tail. Empty votes (or a floor already
    met by nothing) cost 0 — there is nothing to read."""
    if flag_floor <= 0:
        return 0
    smells = 0
    n = len(votes)
    for i, vote in enumerate(votes):
        if vote == -1:
            smells += 1
        reads = i + 1
        if smells >= flag_floor or smells + (n - reads) < flag_floor:
            return reads
    return 0
