"""Intent tests for the plan's communication surface (DETERMINISTIC_SICP §14.3 / §14.6, slice 4).

What the surface is FOR, stated from intent:

- every funded move ends by naming its gate invocation — the ONE pinned decision `next_command`
  spells it, and a verb that does not exist yet is never named;
- the residual explains itself: every exclusion reason present is named with its count, the
  constructive regions with no current contract are listed under "converge first" (the ordering
  law made visible), and the AMBIGUOUS regions are marked as the driver's;
- clean is a defined count (clean · unread), never a percentage of "not flagged";
- the unexamined line closes every report: what the plan did not propose is UNEXAMINED, not
  approved — regime unread, fences held at 0, the recognizer count;
- the FINAL banner is LAST and says "advisory";
- the JSON carries the same rows and tallies as the human text, wrapped with the exit field, and
  the taste claims live in the tallies, never in the exit label.
"""

from __future__ import annotations

import json

import pytest

from Detective import pins
from Detective.cli import (
    _format_plan_full,
    _format_plan_terse,
    _plan_payload,
    _with_exit,
)
from Detective.controller import (
    AMBIGUOUS,
    CONSTRUCTIVE,
    COST_STATIC_DOF_PROXY,
    COST_UNMEASURED,
    SILENT,
    RegionRead,
    plan_moves,
)
from Detective.parsimony import ParsimonyLens
from Detective.plan import (
    CLEAN,
    FENCES_NOTE,
    FUNDED,
    NOT_CLEAN,
    UNREAD,
    PlanAssembly,
    RegionDetail,
    clean_disposition,
    next_command,
    receipt_path,
    summarize,
    unexamined,
)

GATE = "receipt + verify-rewrite + paired budget"


def _lens(name: str, vote: int, measured: bool = True) -> ParsimonyLens:
    return ParsimonyLens(name, vote, 0, f"{name} detail", measured=measured)


def _detail(
    region: str,
    verdict: str,
    agreement: int,
    *,
    template: str | None = None,
    gate: str = "",
    status: str = pins.PINNED,
    cost: float = 10.0,
    provenance: str = COST_STATIC_DOF_PROXY,
    unmeasured: bool = False,
) -> RegionDetail:
    lenses = (
        _lens("complexity", -1 if agreement >= 1 else 1),
        _lens("interface_width", -1 if agreement >= 2 else 1),
        _lens("cohesion", -1 if agreement >= 3 else 1),
        _lens("overload", 0, measured=not unmeasured),
    )
    read = RegionRead(region, verdict, agreement, template, bool(gate), cost, status, provenance)
    return RegionDetail(
        read=read,
        lenses=lenses,
        clean=clean_disposition(verdict, all(lens.measured for lens in lenses)),
        template_evidence="line 3: `in out` (list-evidenced) inside a loop" if template else "",
        gate=gate,
    )


def _assembly(budget: float = 100.0) -> PlanAssembly:
    details = (
        _detail("a.py::f", CONSTRUCTIVE, 3, template="quadratic_membership_scan", gate=GATE, cost=20.0),
        _detail("a.py::g", CONSTRUCTIVE, 2),  # pinned, no recognized move
        _detail(
            "b.py::h", CONSTRUCTIVE, 2, template="quadratic_membership_scan", gate=GATE, status=pins.UNPINNED
        ),
        _detail("c.py::k", AMBIGUOUS, 1),
        _detail("d.py::s", SILENT, 0),
        _detail("d.py::u", SILENT, 0, unmeasured=True),
        _detail(
            "e.py::p", CONSTRUCTIVE, 2, template="accumulator_series", gate=GATE, provenance=COST_UNMEASURED
        ),
    )
    plan = plan_moves(tuple(d.read for d in details), budget)
    return PlanAssembly(scope="pkg", budget=budget, regions=details, plan=plan)


# ---------------------------------------------------------------- next_command (pure)


@pytest.mark.parametrize(
    "reason, gate, expected_start",
    [
        (FUNDED, "decompose --apply", "detective decompose 'm.py::f' --apply"),
        (FUNDED, GATE, "detective receipt 'm.py::f' -o .detective/receipts/m_py__f.json"),
        (FUNDED, "some future gate", ""),
        (pins.UNPINNED, GATE, "detective converge 'm.py::f'"),
        (pins.PINNED_STALE, GATE, "detective converge 'm.py::f'"),
        (pins.PINNED_UNVERIFIED, GATE, "detective converge 'm.py::f'"),
        (pins.PINNED_INCOMPLETE, GATE, "detective converge 'm.py::f'"),
        (pins.REFUSED, GATE, "detective converge 'm.py::f'"),
        ("escalated", GATE, "detective flag 'm.py::f' --style --leave"),
        ("judged_leave", GATE, ""),
        ("unpriced", GATE, "detective audit 'm.py::f' --plan"),
        ("fenced", GATE, ""),
        ("silent", GATE, ""),
        ("no_template", "", ""),
        ("no_gate", "", ""),
        ("over_budget", GATE, ""),
        ("verdict_unknown", GATE, ""),
        ("status_unknown", GATE, ""),
        ("something_else", GATE, ""),
    ],
)
def test_next_command_names_exactly_one_move(reason, gate, expected_start) -> None:
    cmd = next_command(reason, "m.py::f", gate, "set_membership")
    if expected_start:
        assert cmd.startswith(expected_start)
    else:
        assert cmd == ""


def test_a_receipt_gate_brackets_the_rewrite_with_both_commands() -> None:
    cmd = next_command(FUNDED, "m.py::f", GATE, "set_membership")
    assert "detective receipt 'm.py::f' -o .detective/receipts/m_py__f.json" in cmd
    assert "detective verify-rewrite .detective/receipts/m_py__f.json 'm.py::f'" in cmd
    assert "'set_membership'" in cmd  # the transform is named; the surface never applies it


def test_no_command_names_a_verb_that_does_not_exist() -> None:
    # `plan` never tells the driver to run `plan`; and the escalation names BOTH of the driver's
    # moves — record the judgment (slice 6's `flag --style`) or ground it first with converge.
    for reason in ("escalated", "funded", pins.UNPINNED, "unpriced", "fenced", "no_template", "judged_leave"):
        assert "detective plan" not in next_command(reason, "m.py::f", GATE, "x")
    escalated = next_command("escalated", "m.py::f", GATE, "x")
    assert (
        "--style --leave" in escalated
        and "--proceed" in escalated
        and "detective converge 'm.py::f'" in escalated
    )


def test_receipt_path_is_a_safe_suggestion() -> None:
    assert receipt_path("pkg/mod.py::C.m") == ".detective/receipts/pkg_mod_py__C_m.json"


# ---------------------------------------------------------------- summarize / unexamined


def test_summary_tallies_named_codes_only() -> None:
    s = summarize(_assembly())
    assert dict(s.verdicts) == {"CONSTRUCTIVE": 4, "AMBIGUOUS": 1, "DESTRUCTIVE": 0, "SILENT": 2}
    assert dict(s.clean) == {CLEAN: 1, UNREAD: 1, NOT_CLEAN: 5}
    assert dict(s.reasons) == {"silent": 2, "escalated": 1, "no_template": 1, "unpinned": 1, "unpriced": 1}
    assert s.funded == 1 and s.spent == 20.0
    assert s.regions == 7


def test_unexamined_always_leads_with_the_sentence() -> None:
    items = unexamined(FENCES_NOTE, 5)
    assert items[0] == "what this plan did not propose is UNEXAMINED, not approved"
    assert (
        any("regime" in i for i in items) and FENCES_NOTE in items and any("5 template" in i for i in items)
    )


# ---------------------------------------------------------------- the terse block


def test_terse_block_shape() -> None:
    text = _format_plan_terse(_assembly(), report_path=".detective/reports/plan_pkg.txt")
    lines = text.splitlines()
    assert lines[-1].startswith(
        "FINAL plan pkg: 1 funded · 4 constructive · 1 escalated · 0 fenced · 2 silent (clean 1 · unread 1)"
    )
    assert lines[-1].endswith("advisory — writes no project files")
    assert "4 constructive · 1 ambiguous · 0 destructive · 2 silent (clean 1 · unread 1)" in lines[1]
    assert "(advisory — static, writes nothing to your project)" in lines[1]
    # the funded move and its next command
    assert any(
        "a.py::f   agreement 3 · quadratic_membership_scan → set_membership · cost 20" in ln for ln in lines
    )
    assert any("DO THIS" in ln and "detective receipt 'a.py::f'" in ln for ln in lines)
    # the residual names every reason present
    residual = next(ln for ln in lines if "every exclusion named" in ln)
    for reason in ("silent 2", "escalated 1", "no_template 1", "unpinned 1", "unpriced 1"):
        assert reason in residual
    # the ordering law, visible
    assert any("converge first" in ln and "b.py::h" in ln for ln in lines)
    # the driver's queue
    assert any("· yours" in ln and "1 AMBIGUOUS" in ln for ln in lines)
    # the unexamined line, the report pointer
    assert any("UNEXAMINED, not approved" in ln for ln in lines)
    assert any("regime — unread" in ln for ln in lines)
    assert any(".detective/reports/plan_pkg.txt" in ln for ln in lines)
    # no percentage anywhere but clean-as-defined; no "score"
    assert "%" not in text and "score" not in text.lower()


def test_terse_block_with_nothing_funded_says_so() -> None:
    assembly = _assembly(budget=1.0)  # the one admissible move costs 20
    text = _format_plan_terse(assembly)
    assert "nothing funded — every constructive region is excluded below, by name" in text
    assert "over_budget 1" in text


# ---------------------------------------------------------------- the full report and the JSON


def test_full_report_lists_every_region_once_with_its_reason_and_command() -> None:
    text = _format_plan_full(_assembly())
    for region in ("a.py::f", "a.py::g", "b.py::h", "c.py::k", "d.py::s", "d.py::u", "e.py::p"):
        assert text.count(f"  {region}\n") == 1
    assert (
        text.index("  a.py::f\n")
        < text.index("  b.py::h\n")
        < text.index("  c.py::k\n")
        < text.index("  d.py::s\n")
    )
    assert "unmeasured: overload" in text  # d.py::u
    assert "detective audit 'e.py::p' --plan" in text
    assert text.splitlines()[-1].startswith("FINAL plan pkg:")


def test_json_carries_the_same_rows_and_the_exit_field() -> None:
    payload = _with_exit(_plan_payload(_assembly(), ".detective/reports/plan_pkg.txt"), 0)
    json.dumps(payload)  # serialisable
    assert payload["kind"] == "plan" and payload["exit_code"] == 0 and payload["exit_meaning"] == "clean"
    assert payload["verdicts"] == {"CONSTRUCTIVE": 4, "AMBIGUOUS": 1, "DESTRUCTIVE": 0, "SILENT": 2}
    assert payload["clean"] == {CLEAN: 1, UNREAD: 1, NOT_CLEAN: 5}
    assert [r["region"] for r in payload["funded"]] == ["a.py::f"]
    assert payload["funded"][0]["next_command"].startswith("detective receipt 'a.py::f'")
    excluded = {r["region"]: r for r in payload["excluded"]}
    assert (
        excluded["b.py::h"]["reason"] == "unpinned"
        and excluded["b.py::h"]["next_command"] == "detective converge 'b.py::h'"
    )
    assert excluded["d.py::u"]["unmeasured"] == ["overload"] and excluded["d.py::u"]["clean"] == UNREAD
    assert excluded["d.py::s"]["next_command"] is None
    assert payload["unexamined"][0].endswith("UNEXAMINED, not approved")
    assert payload["report"] == ".detective/reports/plan_pkg.txt"
