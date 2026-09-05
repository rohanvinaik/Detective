"""The controller — orientation, interference, and the gated priced plan (Wave 4 / EXP-DS-005).

Design: ``docs/theory/deterministic_sicp/DETERMINISTIC_SICP.md`` §5. The estimator's banks are
oriented toward ONE question — *should improvement attention flow to this region, and through
which admissible move* — and the decision is interference over the oriented votes, never a
weighted sum. The verdict vocabulary is Peitho's, mapped to this domain's warrants:

  SILENT        no oriented signal — the majority, and the honest default (leave it alone)
  CONSTRUCTIVE  ≥2 smell-supports and no fence — plan a move, PENDING its proof gate
  AMBIGUOUS     exactly one support (one lens is necessary, never sufficient — parsimony's own
                law, now a NAMED state instead of a dropped one), or a fence colliding with a
                ≥2 consensus — either way: ESCALATE TO THE DRIVER. This is where taste lives,
                by the automation boundary (NEG_SPEC Thm 6.2), not a failure mode.
  DESTRUCTIVE   a fence (an admissible censor / an authored must-not) opposes the move family —
                censor-grade elimination, with the warrant carried, never inferred from clean
                votes (cleanliness on axis A is NOT evidence against fixing axis B — the
                informational zero; opposition requires a WARRANT, and only censors carry one)

The plan is v1-degenerate flow, stated as such: with one fungible attention budget and
independent unit arcs, exact min-cost selection reduces to a sort — the transportation
structure (Peitho `query/flow.py`) becomes load-bearing only when multi-resource constraints
arrive, and porting the SSP solver for a degenerate case would be machinery without a question.
The no-gate-no-arc law (§8) binds: a move without a proof gate never enters the plan, and every
exclusion carries a NAMED reason (the residual must explain itself — the cheat-sheet
discipline).

Everything here is a pure decision over literals; nothing reads a repo, runs a mutant, or
writes source. The controller proposes; the driver decides; the gates prove.
"""

from __future__ import annotations

from dataclasses import dataclass

from .pins import BEHAVIOR_STATUSES, PINNED

SILENT = "SILENT"
CONSTRUCTIVE = "CONSTRUCTIVE"
AMBIGUOUS = "AMBIGUOUS"
DESTRUCTIVE = "DESTRUCTIVE"


def orient_for_change(vote: int) -> int:
    """One bank vote, oriented toward the attention question (pure — pinned): a smell (−1)
    SUPPORTS change (+1); a clean (+1) orients to 0, NOT to opposition — cleanliness on one
    axis is orthogonal to a defect on another (the informational zero doing its job), and
    letting clean votes veto would make every mostly-clean function unimprovable. Opposition
    is reserved for warrants (censors/fences), which arrive on their own channel."""
    return 1 if vote == -1 else 0


def controller_verdict(supports: int, fence_opposes: int, support_min: int = 2) -> str:
    """The interference verdict over one region (pure — pinned). ``supports`` = count of
    oriented smell-votes; ``fence_opposes`` = count of admissible fences against the region's
    move family (censors are pre-warranted by their own admissibility gate, so ONE suffices to
    fence — but a fence colliding with a full smell consensus is a genuine disagreement between
    the two signs and must ESCALATE, never silently resolve either way):

      fence ∧ supports ≥ min → AMBIGUOUS   (the two signs disagree — the driver's call)
      fence                  → DESTRUCTIVE (fenced, warrant carried)
      supports ≥ min         → CONSTRUCTIVE
      0 < supports < min     → AMBIGUOUS   (evidence present but below the floor: escalate —
                                            SILENT must mean NO signal, and the two states
                                            must not collapse at any floor, not only 2)
      otherwise              → SILENT
    """
    if fence_opposes > 0 and supports >= support_min:
        return AMBIGUOUS
    if fence_opposes > 0:
        return DESTRUCTIVE
    if supports >= support_min:
        return CONSTRUCTIVE
    if supports > 0:
        return AMBIGUOUS
    return SILENT


@dataclass(frozen=True)
class RegionRead:
    """One region's controller-facing read: the verdict, its strength, the recognized move
    (template) if any, whether that move's gate exists, the region's cost estimate and WHERE it
    came from, and the region's BEHAVIOR status (§14.1 — style after behavior, strictly).

    `status` and `cost_provenance` carry NO defaults on purpose: a default status would let a
    producer that never checked the contract pass as admissible, and a cost without provenance
    is a number, not a measurement. Every constructor states both."""

    region: str
    verdict: str
    agreement: int  # oriented supports — the interference strength
    template: str | None  # the recognized move family, None when the library abstained
    gate_exists: bool  # §8: no gate, no arc
    cost: float  # the arc-price estimate (v1: the static DOF proxy; live: `audit --plan`)
    status: str  # `certify.behavior_status` (pins.BEHAVIOR_STATUSES); only PINNED arms a gate
    cost_provenance: str  # "static_dof_proxy" | "audit_plan_measured"


@dataclass(frozen=True)
class Plan:
    """The controller's output: the funded moves in order, and the residual with NAMED reasons —
    a plan that cannot explain what it excluded is a score, not a decision."""

    funded: tuple[RegionRead, ...]
    excluded: tuple[tuple[str, str], ...]  # (region, reason) — the residual artifact
    budget_spent: float


def admission_reason(verdict: str, status: str, has_template: bool, gate_exists: bool) -> str:
    """Why one region is, or is not, admissible to the plan (§14.1 / §14.4 — pure, pinned).

    Extracted from `plan_moves` so the decision is over literals (`RegionRead` is a domain object
    input synthesis cannot express). The residual must explain itself, so every non-admission is
    a NAMED reason, checked in the order the laws rank them: the taste verdict first, then the
    BEHAVIOR status — style after behavior, strictly: a CONSTRUCTIVE region with no current
    contract is a `converge` target whatever move the library recognized — then the move, then
    its gate:

      "fenced"             DESTRUCTIVE — censor-grade elimination, warrant on the censor ledger
      "escalated"          AMBIGUOUS — the driver's queue, not the plan's
      "silent"             SILENT — no case for change
      "verdict_unknown"    a verdict outside the four — named, never admitted by fall-through
      "unpinned" · "pinned_stale" · "pinned_unverified"
                           CONSTRUCTIVE but no CURRENT Detective contract: the status code IS the
                           reason, because the three collapse into one otherwise and they are
                           three different facts (§14.1); next command `converge`
      "status_unknown"     a status outside `pins.BEHAVIOR_STATUSES` — named, never admitted
      "no_template"        CONSTRUCTIVE ∧ pinned, but no recognized move — a library gap, grown
                           at population level (never a reason to loosen a recognizer)
      "no_gate"            a recognized move whose transform has no proof gate — no arc (§8)
      "admissible"         CONSTRUCTIVE ∧ pinned ∧ recognized ∧ gated — may carry flow
    """
    if verdict == DESTRUCTIVE:
        return "fenced"
    if verdict == AMBIGUOUS:
        return "escalated"
    if verdict == SILENT:
        return "silent"
    if verdict != CONSTRUCTIVE:
        return "verdict_unknown"
    if status != PINNED:
        return status if status in BEHAVIOR_STATUSES else "status_unknown"
    if not has_template:
        return "no_template"
    if not gate_exists:
        return "no_gate"
    return "admissible"


def plan_moves(regions: tuple[RegionRead, ...], budget: float) -> Plan:
    """The gated, priced, budgeted plan (pure over `RegionRead`s; the per-region decision is the
    pinned :func:`admission_reason`). Admission: CONSTRUCTIVE ∧ PINNED ∧ a recognized template ∧
    its gate exists. Order: strongest agreement first, then cheapest, then name (a deterministic
    total order — no wall-clock, no randomness). Funding: greedy under the budget — EXACTLY
    optimal here, not merely approximate, because the arcs are independent and the budget is one
    fungible pool (the degenerate transportation case; the flow solver becomes warranted with
    multi-resource constraints, recorded in the module docstring). Every exclusion carries its
    reason — the `admission_reason` codes, plus the one only the plan can decide:

      "over_budget"   admissible but unfunded this cycle
    """
    admissible = []
    excluded: list[tuple[str, str]] = []
    for r in regions:
        reason = admission_reason(r.verdict, r.status, r.template is not None, r.gate_exists)
        if reason == "admissible":
            admissible.append(r)
        else:
            excluded.append((r.region, reason))
    admissible.sort(key=lambda r: (-r.agreement, r.cost, r.region))
    funded: list[RegionRead] = []
    spent = 0.0
    for r in admissible:
        if spent + r.cost <= budget:
            funded.append(r)
            spent += r.cost
        else:
            excluded.append((r.region, "over_budget"))
    return Plan(tuple(funded), tuple(excluded), spent)


def interference_isolation_cost(votes: tuple[int, ...], support_min: int = 2) -> int:
    """The Wave-1 knee instrument, refined to the FOUR-VALUED verdict (pure — pinned; the
    clean-side refinement Wave 1 named as owed to this wave). Reading the priority-ordered
    ORIENTED votes one at a time — fences are a separate channel and not part of this read
    stream — the cost is the first read count after which `controller_verdict`'s outcome
    (fences held at 0) is invariant under EVERY completion of the remaining reads, decided by
    exhaustive completion (the vote alphabet is {0, 1} once oriented, so the check is exact,
    never a heuristic). Empty votes cost 0. Unlike the binary-flag instrument, SILENT and
    AMBIGUOUS are distinct outcomes here, so a clean region's verdict is NOT structurally
    pinned to the last read — the degeneracy that made the Wave-1 clean-side measurement
    uninformative."""
    from itertools import product

    n = len(votes)

    def verdict_at(prefix: tuple[int, ...], suffix: tuple[int, ...]) -> str:
        return controller_verdict(sum(prefix) + sum(suffix), 0, support_min)

    for k in range(n + 1):
        prefix = votes[:k]
        outcomes = {verdict_at(prefix, s) for s in product((0, 1), repeat=n - k)}
        if len(outcomes) == 1:
            return k
    return n
