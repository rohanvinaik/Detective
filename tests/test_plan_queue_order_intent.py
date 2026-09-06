"""Intent tests for the plan's driver queues (2026-09-06 — the first `plan Detective/` dogfood).

The defect: with nothing funded, the terse block's "converge first" line — the plan's own next
move — named `binding.py::classify_target` (agreement 2) while `engine.py::classify_survivors`
(agreement 5, the plan's strongest case) sat lower in the report. `controller.plan_moves` sorts
only what it FUNDS by the plan's law (strongest agreement first, then cheapest, then name); its
exclusions come out in traversal order, the alphabetical file walk, and the three queue helpers in
`plan.py` handed that order straight to both surfaces. A driver reads a queue top-down; a queue
whose top is "the first file" contradicts the law the same report states.

Written from intent: every queue the plan hands a driver — converge-first, the AMBIGUOUS "yours"
queue, the reopened judgments — is in the plan's ONE order, and the pure `queue_order` is that
order over literals: agreement descending, cost ascending, name.
"""

from __future__ import annotations

from Detective import pins
from Detective.controller import AMBIGUOUS, CONSTRUCTIVE, COST_STATIC_DOF_PROXY, RegionRead, plan_moves
from Detective.parsimony import ParsimonyLens
from Detective.plan import (
    PlanAssembly,
    RegionDetail,
    clean_disposition,
    converge_first,
    escalated_regions,
    queue_order,
    reopened_regions,
)


def _detail(
    region: str, verdict: str, agreement: int, cost: float, *, status: str = pins.UNPINNED, judgment: str = ""
) -> RegionDetail:
    lenses = (ParsimonyLens("complexity", -1 if agreement >= 1 else 1, 0, "detail", measured=True),)
    read = RegionRead(region, verdict, agreement, None, False, cost, status, COST_STATIC_DOF_PROXY, judgment)
    return RegionDetail(
        read=read,
        lenses=lenses,
        clean=clean_disposition(verdict, True),
        template_evidence="",
        gate="",
        judgment=judgment,
    )


def _assembly(*details: RegionDetail) -> PlanAssembly:
    plan = plan_moves(tuple(d.read for d in details), 100.0)
    return PlanAssembly(scope="pkg", budget=100.0, regions=details, plan=plan)


# --- the pure order --------------------------------------------------------------------------------


def test_strongest_agreement_first_whatever_the_traversal_order():
    rows = [("binding.py::classify_target", 2, 69.0), ("engine.py::classify_survivors", 5, 814.0)]
    assert queue_order(rows) == ["engine.py::classify_survivors", "binding.py::classify_target"]


def test_same_agreement_then_cheapest():
    rows = [("z.py::expensive", 3, 300.0), ("a.py::cheap", 3, 20.0)]
    assert queue_order(rows) == ["a.py::cheap", "z.py::expensive"]


def test_same_agreement_and_cost_then_name_so_the_order_is_total():
    rows = [("b.py::g", 2, 10.0), ("a.py::f", 2, 10.0)]
    assert queue_order(rows) == ["a.py::f", "b.py::g"]
    assert queue_order([]) == []


# --- the three queues the surfaces render ------------------------------------------------------------


def test_converge_first_names_the_plans_strongest_case_first():
    # Traversal order (alphabetical) would put binding.py first; the law puts agreement 5 first.
    assembly = _assembly(
        _detail("binding.py::classify_target", CONSTRUCTIVE, 2, 69.0),
        _detail("cli.py::_format_decompose", CONSTRUCTIVE, 4, 175.0),
        _detail("engine.py::classify_survivors", CONSTRUCTIVE, 5, 814.0),
    )
    assert converge_first(assembly) == (
        "engine.py::classify_survivors",
        "cli.py::_format_decompose",
        "binding.py::classify_target",
    )


def test_an_answered_proceed_joins_the_converge_queue_in_the_same_order():
    assembly = _assembly(
        _detail("a.py::weak", CONSTRUCTIVE, 1, 5.0),
        _detail("b.py::answered", AMBIGUOUS, 1, 1.0, judgment="proceed"),
    )
    # same agreement: the cheaper one first, whatever its file
    assert converge_first(assembly) == ("b.py::answered", "a.py::weak")


def test_the_yours_queue_is_in_the_plans_order_too():
    assembly = _assembly(
        _detail("a.py::one_lens", AMBIGUOUS, 1, 50.0),
        _detail("b.py::cheaper_one_lens", AMBIGUOUS, 1, 5.0),
    )
    assert escalated_regions(assembly) == ("b.py::cheaper_one_lens", "a.py::one_lens")


def test_reopened_judgments_are_queued_in_the_plans_order():
    assembly = _assembly(
        _detail("a.py::f", AMBIGUOUS, 1, 50.0, judgment="reopened_definition"),
        _detail("b.py::g", AMBIGUOUS, 2, 50.0, judgment="reopened_reading"),
        _detail("c.py::h", AMBIGUOUS, 3, 50.0),
    )
    assert reopened_regions(assembly) == ("b.py::g", "a.py::f")
