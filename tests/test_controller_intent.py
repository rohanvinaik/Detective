"""Intent tests AND truth-table pins — Wave 4 / EXP-DS-005, the controller
(docs/theory/deterministic_sicp/ §5).

What the code is FOR, stated from intent:

- Orientation reserves OPPOSITION for warrants: a clean vote orients to 0, never −1 —
  cleanliness on one axis is not evidence against fixing another (the informational zero),
  and only a censor/fence carries a warrant to oppose.
- The verdict keeps four states apart: SILENT (no case) · AMBIGUOUS (one lens — necessary,
  never sufficient — or the two SIGNS disagreeing: both are the driver's queue, where taste
  lives by the automation boundary) · CONSTRUCTIVE (consensus, pending the gate) ·
  DESTRUCTIVE (fenced, warrant carried).
- The plan admits only gated moves (§8: no gate, no arc), orders deterministically, funds
  greedily under one fungible budget (EXACTLY optimal in the degenerate transportation case,
  stated), and names every exclusion — a plan that cannot explain its residual is a score.
- The four-valued isolation cost is decided by exhaustive completion (exact, never a
  heuristic); its clean-side behavior is measured in EXP-DS-005, not assumed.

Converge is attempted against the settled tree after this file lands (the serial-cold
sequencing lesson); these tables stand as the pins meanwhile.
"""

import pytest

from Detective.controller import (
    AMBIGUOUS,
    CONSTRUCTIVE,
    DESTRUCTIVE,
    SILENT,
    Plan,
    RegionRead,
    controller_verdict,
    interference_isolation_cost,
    orient_for_change,
    plan_moves,
)

# ── orient_for_change ────────────────────────────────────────────────────────────────────────


def test_orientation_truth_table() -> None:
    assert orient_for_change(-1) == 1  # a smell supports change
    assert orient_for_change(0) == 0  # no opinion stays none
    assert orient_for_change(1) == 0  # clean is ORTHOGONAL to change, never opposition


# ── controller_verdict ───────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "supports, fences, expected",
    [
        (0, 0, SILENT),
        (1, 0, AMBIGUOUS),  # one lens: necessary, never sufficient — escalate
        (2, 0, CONSTRUCTIVE),
        (5, 0, CONSTRUCTIVE),
        (0, 1, DESTRUCTIVE),  # a fence needs no consensus — its warrant is its admissibility
        (1, 1, DESTRUCTIVE),  # sub-consensus support does not outweigh a warrant
        (2, 1, AMBIGUOUS),  # the two SIGNS disagree — the driver's call, never silent resolution
        (4, 2, AMBIGUOUS),
    ],
)
def test_verdict_truth_table(supports: int, fences: int, expected: str) -> None:
    assert controller_verdict(supports, fences) == expected


def test_verdict_respects_the_support_floor() -> None:
    assert controller_verdict(2, 0, support_min=3) == AMBIGUOUS  # below a raised floor
    assert controller_verdict(3, 0, support_min=3) == CONSTRUCTIVE


# ── plan_moves ───────────────────────────────────────────────────────────────────────────────


def _r(region, verdict, agreement=2, template="t", gate=True, cost=1.0) -> RegionRead:
    return RegionRead(region, verdict, agreement, template, gate, cost)


def test_every_exclusion_reason_is_named() -> None:
    plan = plan_moves(
        (
            _r("a", DESTRUCTIVE),
            _r("b", AMBIGUOUS),
            _r("c", SILENT),
            _r("d", CONSTRUCTIVE, template=None),
            _r("e", CONSTRUCTIVE, gate=False),
            _r("f", CONSTRUCTIVE),
        ),
        budget=10.0,
    )
    assert dict(plan.excluded) == {
        "a": "fenced",
        "b": "escalated",
        "c": "silent",
        "d": "no_template",
        "e": "no_gate",
    }
    assert [r.region for r in plan.funded] == ["f"]


def test_plan_orders_by_agreement_then_cost_then_name() -> None:
    plan = plan_moves(
        (
            _r("late", CONSTRUCTIVE, agreement=2, cost=1.0),
            _r("cheap", CONSTRUCTIVE, agreement=3, cost=1.0),
            _r("dear", CONSTRUCTIVE, agreement=3, cost=2.0),
        ),
        budget=10.0,
    )
    assert [r.region for r in plan.funded] == ["cheap", "dear", "late"]


def test_budget_is_respected_and_overflow_is_named() -> None:
    plan = plan_moves((_r("a", CONSTRUCTIVE, cost=3.0), _r("b", CONSTRUCTIVE, cost=3.0)), budget=5.0)
    assert [r.region for r in plan.funded] == ["a"]
    assert ("b", "over_budget") in plan.excluded
    assert plan.budget_spent == 3.0


def test_empty_regions_yield_the_empty_plan() -> None:
    assert plan_moves((), 5.0) == Plan((), (), 0.0)


# ── interference_isolation_cost ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "votes, expected",
    [
        ((), 0),  # nothing to read
        ((1, 1), 2),  # CONSTRUCTIVE locks the moment the floor is reached
        ((1, 1, 0, 0), 2),  # …and later reads cannot unlock it
        ((1, 0, 0), 3),  # one support: AMBIGUOUS-vs-CONSTRUCTIVE rides the last read
        ((0, 0, 0), 3),  # clean: SILENT-vs-AMBIGUOUS rides the last read too — measured, not hidden
    ],
)
def test_isolation_cost_four_valued(votes: tuple, expected: int) -> None:
    assert interference_isolation_cost(votes) == expected


def test_isolation_cost_invariance_is_exhaustive() -> None:
    # The definition IS exhaustive completion; cross-check one case by hand: after (1,1) every
    # completion of two remaining reads yields supports ≥ 2 → CONSTRUCTIVE, exactly one outcome.
    from itertools import product

    votes = (1, 1, 0, 0)
    k = interference_isolation_cost(votes)
    outcomes = {
        controller_verdict(sum(votes[:k]) + sum(s), 0) for s in product((0, 1), repeat=len(votes) - k)
    }
    assert len(outcomes) == 1
