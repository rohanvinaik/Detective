"""The corpus self-teaching LEDGER for code censors — §14 persistence + promotion (Q1, last piece).

The per-censor DECISION core is :mod:`Detective.censor` (the admissibility guard + the κ-gated propose
rule); the κ ENGINE is :mod:`Detective.kappa` (marginal coverage over the call graph). This module is the
CORPUS layer above them, mirroring Regenesis ``promotion_ledger.py`` over CENSORS instead of induced rules:
persist the proposed censors, rank them by marginal-κ over the call graph, PROMOTE the admissible/high-κ
ones, DEMOTE the corpus-vetoed ones, and iterate to the κ→0 fixpoint (Def. 14.3, Prop. 14.2).

**v1 uses a STATIC call graph** (κ computed once per scan). A code censor forbids an input/output region;
it does NOT add a *call* edge, so the κ *re-flow* (Def. 14.3, Cor. 14.5 — where adopting a censor mutates
the graph κ is read from) is the paper's OWN open code measurement (§18 Q5 / C7, Rem. 14.8), not a v1
invention. As in Regenesis, the loop is **conservative-empty on clean data by construction**: a positive
promotion needs a corpus whose near-misses bridge otherwise-disjoint call clusters.

The PURE decisions below (the fixpoint gate, the halt, L_ind) are pinned in isolation. The persistence and
the corpus loop are the impure shell around them — hand-tested for durability, never converge-pinned.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass

from .censor import Censor


@dataclass
class CensorLedgerEntry:
    """One proposed censor accumulated in the ledger. ``kappa`` = its marginal coverage over the call
    graph (filled by :func:`rank_ledger`; ``None`` until then). ``state`` is ``proposed`` (ranked, not
    yet gated), ``promoted`` (first-class this corpus), or ``demoted`` (the corpus vetoed it — sticky,
    never re-promoted). ``generation`` is the fixpoint round that last moved it. Nothing here decides —
    :func:`ledger_disposition` is the gate; the entry only records."""

    censor: Censor
    kappa: int | None = None
    state: str = "proposed"  # proposed | promoted | demoted
    generation: int = 0


def ledger_key(censor: Censor) -> str:
    """The stable identity of a censor in the ledger — ``func_key::kind::subject::source``. Two harvests
    of the same near-miss collapse to one entry (the dedup the fixpoint's monotone `seen`/`demoted` sets
    rely on), mirroring Regenesis ``_rule_key``."""
    return f"{censor.func_key}::{censor.kind}::{censor.subject}::{censor.source}"


def ledger_disposition(censor_disposition: str, demoted: bool, promoted: bool) -> str:
    """The corpus-loop gate for ONE censor (§14 fixpoint inner decision, pure — pinned).

    Composes the per-censor score (:func:`Detective.censor.score_censor` → ``propose`` /
    ``abstain_low_kappa`` / ``refuse_inadmissible``) with the censor's LEDGER STATE into this round's
    action. Mirrors Regenesis ``corpus_fixpoint``'s ``fresh = [e for e in admissible_promotions(...) if
    key not in seen and key not in demoted]``, split into named codes so the reasons stay distinct and a
    re-merge (e.g. letting a demoted censor re-promote) fails a pin:

    * ``skip_demoted``   — the corpus vetoed it in an earlier round: monotone, sticky, NEVER re-promoted;
      this outranks everything (a vetoed censor is out regardless of how it re-scores this round).
    * ``skip_promoted``  — already first-class: promoted at most once (termination); a re-score does not
      eject it — only demotion does.
    * ``refuse``         — inadmissible (the guard failed): never eligible, κ irrelevant.
    * ``hold_low_kappa`` — admissible but κ→0: the SSL tail, taught not fenced (never self-promoted).
    * ``promote``        — admissible, κ>0, fresh: a bulk censor to adopt this round.
    """
    if demoted:
        return "skip_demoted"
    if promoted:
        return "skip_promoted"
    if censor_disposition == "refuse_inadmissible":
        return "refuse"
    if censor_disposition == "abstain_low_kappa":
        return "hold_low_kappa"
    return "promote"


def fixpoint_reached(fresh_promotions: int, pending_demotions: int) -> bool:
    """The κ→0 corpus fixpoint halt (§14, pure — pinned). Mirrors Regenesis ``if not fresh and not pulled:
    break`` — a round is a fixpoint iff it PROMOTES nothing new AND has nothing left to demote: then every
    source has been read under the final promoted set, so that set is order-independent. A round that still
    demotes (``pending_demotions > 0``) is NOT a fixpoint even with no fresh promotion — the veto changed
    the set and the next round must re-scan under it."""
    return fresh_promotions == 0 and pending_demotions == 0


def self_teaching_fraction(kappas: list[int], confirmed: list[bool]) -> float:
    """L_ind, the self-teaching fraction (§14.3 / §16.5, pure — pinned).

    Of all the marginal coverage the proposed censors would add (Σκ), the fraction that is ADMISSIBLY
    SELF-TAUGHT — spine-confirmed (§14(i), the well-definedness guard) — versus proposed-but-unconfirmed,
    the I_ext residual a teacher must supply. A DIRECT port of Regenesis ``self_teaching_fraction``, and —
    like it — operationalized in COVERAGE units, NOT SSL's entropy bits (the H-series is unwired, §18 Q9).
    ``0.0`` on an empty or zero-coverage ledger (nothing to teach → nothing self-taught). ``kappas[i]`` and
    ``confirmed[i]`` are the i-th proposed censor's κ and spine-confirmation, taken in parallel."""
    total = sum(kappas)
    if total == 0:
        return 0.0
    self_taught = sum(k for k, c in zip(kappas, confirmed, strict=False) if c)
    return self_taught / total


# ─── persistence (mirrors Detective.equivalents' atomic JSON store) ───
_REL_PATH = ".detective/censors.json"


def _store_path(project_root: str) -> str:
    return os.path.join(project_root, _REL_PATH)


def load_ledger(project_root: str) -> dict[str, CensorLedgerEntry]:
    """Every persisted ledger entry, keyed by :func:`ledger_key`. Empty (never an error) when the store is
    absent or unreadable — a missing ledger is simply no ledger, mirroring
    :func:`Detective.equivalents.load_flags`. A malformed entry is skipped, never fatal."""
    try:
        with open(_store_path(project_root), encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return {}
    out: dict[str, CensorLedgerEntry] = {}
    for key, value in raw.items():
        try:
            out[key] = CensorLedgerEntry(
                censor=Censor(**value["censor"]),
                kappa=value.get("kappa"),
                state=value.get("state", "proposed"),
                generation=value.get("generation", 0),
            )
        except (TypeError, ValueError, KeyError):
            continue  # a malformed entry is skipped, never fatal
    return out


def save_ledger(project_root: str, entries: dict[str, CensorLedgerEntry]) -> None:
    """Persist the censor ledger, creating ``.detective/`` if needed. Atomic replace (#63): a proposed
    censor is a corpus-derived artifact, and a mid-write crash must not clobber the store into an empty
    file the next load silently accepts."""
    from .atomic_store import atomic_write_text

    path = _store_path(project_root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {
        key: {"censor": asdict(e.censor), "kappa": e.kappa, "state": e.state, "generation": e.generation}
        for key, e in entries.items()
    }
    atomic_write_text(path, json.dumps(payload, indent=2))


# ─── the corpus loop (impure — hand-tested, never converge-pinned) ───
def _func_node(censor: Censor) -> str:
    """The censor's function as a call-graph node — the bare qualname of ``func_key`` (``path::qual`` →
    ``qual``), matching :func:`Detective.kappa.build_call_graph`'s name-keyed nodes."""
    return censor.func_key.split("::")[-1]


def accumulate(censors: list[Censor], generation: int = 0) -> list[CensorLedgerEntry]:
    """Fold harvested censors into ledger entries, deduped by :func:`ledger_key` (the same near-miss
    harvested twice is one entry — the monotone dedup the fixpoint's ``seen``/``demoted`` sets need).
    Mirrors Regenesis ``accumulate``; κ is unfilled (:func:`rank_ledger` fills it). First-seen order kept."""
    out: dict[str, CensorLedgerEntry] = {}
    for c in censors:
        key = ledger_key(c)
        if key not in out:
            out[key] = CensorLedgerEntry(censor=c, generation=generation)
    return list(out.values())


def rank_ledger(adj: dict, entries: list[CensorLedgerEntry], selected: list) -> list[CensorLedgerEntry]:
    """Fill each entry's ``kappa`` = the marginal coverage its function adds over the call graph BEYOND the
    already-``selected`` (promoted) functions, and return the ledger sorted by κ DESCENDING (stable on
    ties) — the promotion PRIORITY (Prop. 14.2). Mirrors Regenesis ``rank_ledger``; mutates ``kappa`` in
    place; κ is read over the STATIC graph (v1; the re-flow is §18 Q5)."""
    from .kappa import marginal_coverage

    for e in entries:
        e.kappa = marginal_coverage(adj, _func_node(e.censor), selected)
    return sorted(entries, key=lambda e: -(e.kappa or 0))


def build_ledger(project_root: str, censors: list[Censor], *, generation: int = 0) -> list[CensorLedgerEntry]:
    """★ PROMOTION OFF. Rank a bag of proposed censors by marginal-κ over the package's call graph and
    return the ranked ledger — the promotion PRIORITY, mutating no library. Mirrors Regenesis
    ``build_ledger``. ``censors`` are harvested by the caller
    (:func:`Detective.censor.harvest_call_site_censors` + :func:`Detective.censor.censors_from_verification`);
    this only scores and orders them."""
    from .kappa import build_call_graph

    adj = build_call_graph(project_root)
    return rank_ledger(adj, accumulate(censors, generation), selected=[])


def corpus_fixpoint(
    project_root: str,
    censors: list[Censor],
    *,
    sigma_hat_after: int = 1,
    vetoed_keys: set | None = None,
    prior_promoted: list[CensorLedgerEntry] | None = None,
    max_generations: int = 50,
) -> dict:
    """★ PROMOTION ON — the corpus fixpoint (Prop. 14.2 / Def. 14.3). Greedily PROMOTE the single
    highest-κ ADMISSIBLE censor (:func:`Detective.censor.score_censor` → ``propose``), re-rank the remaining
    censors against the expanded selected set (marginal κ shrinks — the bulk→tail knee, Prop. 14.2's κ→0
    stop), and repeat until no fresh admissible censor remains. A censor whose :func:`ledger_key` is in
    ``vetoed_keys`` is DEMOTED and never re-promoted (monotone — the code analog of Regenesis
    ``_demotion_keys``: the world/domain vetoed it).

    Three guarantees mirror Regenesis: (1) **termination** — each promotion adds one censor to ``seen`` and
    the deduped candidate set is finite, so the loop empties in ≤ len(censors) rounds; (2)
    **order-independence** at the fixpoint (every censor scored under the final selected set); (3) **safety**
    — the only promote path is the computed :func:`ledger_disposition` gate. **v1**: STATIC call graph;
    ``sigma_hat_after=1`` retains plurality by default (wire Detective's candidate-equivalent count here for
    the real σ̂); ``vetoed_keys`` empty on clean data → conservative-empty by construction (the honest 'the
    spine is the bottleneck' outcome). Returns
    ``{promoted, generations, ledger, self_teaching, n_demoted}``."""
    from .censor import score_censor
    from .kappa import build_call_graph

    adj = build_call_graph(project_root)
    demoted = set(vetoed_keys or ())
    # Seed from a prior run's promotions (the persisted ledger): a censor promoted earlier is DEMOTED here
    # if the corpus now vetoes it (the cross-run pull that makes demotion — and fixpoint_reached's
    # pending-demotions arm — live), and is never re-promoted (its key rides `seen`).
    promoted: list[CensorLedgerEntry] = list(prior_promoted or [])
    seen: set = {ledger_key(p.censor) for p in promoted}
    n_demoted = 0
    # The initial ranked ledger (κ over the static graph, given the seeded promotions) — the reporting
    # artifact and the L_ind base, BEFORE greedy promotion depletes marginal κ.
    initial = rank_ledger(adj, accumulate(censors), [_func_node(p.censor) for p in promoted])
    generation = 0
    while generation < max_generations:
        selected = [_func_node(p.censor) for p in promoted]
        ledger = rank_ledger(adj, accumulate(censors, generation), selected)
        # DEMOTION — pull any promoted censor the corpus now vetoes (monotone, sticky).
        pulled = [p for p in promoted if ledger_key(p.censor) in demoted]
        for p in pulled:
            p.state = "demoted"
        promoted = [p for p in promoted if ledger_key(p.censor) not in demoted]
        n_demoted += len(pulled)
        # PROMOTE — the single highest-κ admissible-and-fresh censor (greedy; κ re-subtracted next round).
        fresh: CensorLedgerEntry | None = None
        for e in ledger:
            key = ledger_key(e.censor)
            disp = score_censor(e.censor, e.kappa or 0, sigma_hat_after)
            if ledger_disposition(disp, key in demoted, key in seen) == "promote":
                fresh = e
                break
        if fixpoint_reached(0 if fresh is None else 1, len(pulled)):
            break
        if fresh is not None:  # a demotion-only round (fresh None, pulled>0) re-scans without promoting
            fresh.state = "promoted"
            fresh.generation = generation
            seen.add(ledger_key(fresh.censor))
            promoted.append(fresh)
        generation += 1
    # L_ind (§16.5): of the final ledger's total κ, the share that is admissibly self-promotable (propose)
    # — the bulk the corpus fences itself — versus the κ→0 tail a teacher must supply (I_ext).
    self_promotable = [score_censor(e.censor, e.kappa or 0, sigma_hat_after) == "propose" for e in initial]
    stf = self_teaching_fraction([e.kappa or 0 for e in initial], self_promotable)
    return {
        "promoted": promoted,
        "generations": generation,
        "ledger": initial,
        "self_teaching": stf,
        "n_demoted": n_demoted,
    }
