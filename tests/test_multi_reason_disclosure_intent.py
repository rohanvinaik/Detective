"""Intent tests for S14 — a multi-reason cut disclosed one reason and led with the wrong one.

Design: `docs/CORRECTNESS_REPAIRS_2026-09-08.md` §S14. Two separable halves, both landing here
because the second makes the first far less harmful and neither is complete alone.

S14a — DISCLOSURE. `measurement_cut_reasons` is plural on purpose and states the requirement:
"A run can be cut for more than one reason at once, and reporting only the first makes the second
invisible to whoever fixes the first — they re-run, hit the next refusal, and have no way to know
it was always there." Three repair renders showed NO reason at all (`regime` / `deadline` /
`trace_budget` printed a command and a hardcoded why-line) and two hardcoded exactly one
(`fix_load`, `fix_collection`). The engine's plural verdict reached the operator as a singular —
Finding F's spiral in a new spelling, since the budget the output asked for left the other cause
in place with nothing having named it.

S14b — ORDER. The three reasons S13 split out (`mutant_construction_failed`,
`mutant_not_installed`, `mutant_not_entered`) had NO branch in the ladder, so they were reachable
only as the residual and every partiality reason outranked them. Measured before the fix:

    (mutant_construction_failed, budget_exhausted) -> deadline
    (mutant_not_installed, sampled_universe)       -> enumerate
    (coverage_truncated, mutant_not_entered)       -> trace_budget

The first is the clearest defect: the engine could not BUILD the mutant — its own sentence says to
report a defect, "it measures the engine, not your suite" — and the operator was sent to raise a
deadline. The ordering is not a preference: `Wesker.engine.mutant_disposition` fixes it as
"earliest failed phase first — each answers a question the later ones presuppose", ranking
harness_error -> not_installed -> not_entered -> cut. `coverage_truncated` IS the cut family, so
the ladder was inverting its own engine.

`repair_measurement_route` is one of the five in-repo decisions that refuse with
`mutant_not_entered` while the running Detective profiles itself (S15, founder ruling: stay on hard
pins). These ARE that pin.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from Detective.cli import _ROUTE_ADDRESSES, _also_live_rows, repair_measurement_route
from Detective.validity import CUT_REASONS, cut_reason_sentence

# ------------------------------------------------------------------ S14b: Wesker's phase precedence


@pytest.mark.parametrize(
    ("reasons", "expected"),
    [
        # The three measured inversions. Each used to take the partiality remedy.
        (("mutant_construction_failed", "budget_exhausted"), "mutant_phase"),
        (("mutant_not_installed", "sampled_universe"), "mutant_phase"),
        (("coverage_truncated", "mutant_not_entered"), "mutant_phase"),
        # Alone, they used to reach the residual. Now they name the band they are in.
        (("mutant_construction_failed",), "mutant_phase"),
        (("mutant_not_installed",), "mutant_phase"),
        (("mutant_not_entered",), "mutant_phase"),
    ],
)
def test_a_mutant_phase_failure_outranks_every_partiality_reason(reasons, expected) -> None:
    assert repair_measurement_route(reasons, False, False) == expected


@pytest.mark.parametrize(
    "blocker", ["target_load_failed", "ambiguous_module_identity", "collection_incomplete"]
)
def test_but_a_run_level_blocker_still_outranks_the_mutant_phase_band(blocker) -> None:
    """The band is inserted BETWEEN two existing bands, not on top. Nothing was measured, or the
    test FLOOR is wrong, still leads: a mutant phase presupposes a suite that collected and a module
    that imported, which is the same "the later ones presuppose" argument one level up."""
    route = repair_measurement_route((blocker, "mutant_not_entered"), False, False)
    assert route != "mutant_phase"
    assert route in ("fix_load", "regime", "fix_collection")


@pytest.mark.parametrize(
    ("reason", "route"),
    [
        ("nonreproducible_in_process", "reprofile"),
        ("uncontained_worker", "isolate"),
        ("budget_exhausted", "deadline"),
        ("sampled_universe", "enumerate"),
        ("coverage_truncated", "trace_budget"),
        ("engine_refused_unspecified", "inspect_refusal"),
    ],
)
def test_every_other_reason_keeps_the_route_it_had(reason, route) -> None:
    """The repair is an INSERTION. A reordering that also moved the existing bands would be a
    second, unrequested change hiding inside this one."""
    assert repair_measurement_route((reason,), False, False) == route


def test_mutant_phase_and_inspect_refusal_are_different_facts() -> None:
    """Two codes, one render, deliberately. `inspect_refusal` means the engine refused and named
    nothing we recognise (`engine_refused_unspecified`); `mutant_phase` means it named the phase
    exactly. Collapsing them would put a precise diagnosis behind a vague one's name — the S13
    collapse, one layer out."""
    assert repair_measurement_route(("engine_refused_unspecified",), False, False) == "inspect_refusal"
    assert repair_measurement_route(("mutant_not_entered",), False, False) == "mutant_phase"


# ------------------------------------------------------------------ S14a: nothing goes unmentioned


def test_a_reason_the_remedy_does_not_address_is_named() -> None:
    rows = _also_live_rows(("coverage_truncated", "mutant_not_entered"), "trace_budget")
    body = "\n".join(rows)
    assert "mutant_not_entered" in body, "the reason the trace-budget remedy cannot fix must be named"
    assert cut_reason_sentence("mutant_not_entered") in body, "with its remedy, not just its code"
    assert "coverage_truncated" not in body, "the reason the remedy DOES address is not repeated"


def test_it_says_the_remaining_causes_survive_the_fix() -> None:
    """The sentence that closes the spiral. Naming a second cause without saying it survives the
    first fix still invites 'do the DO THIS, then see' — which is the loop."""
    rows = _also_live_rows(("budget_exhausted", "mutant_not_entered"), "deadline")
    assert any("does NOT clear these" in r for r in rows)


def test_a_single_reason_run_gains_no_noise() -> None:
    """A line that always appears is a line nobody reads (the signpost discipline)."""
    assert _also_live_rows(("coverage_truncated",), "trace_budget") == []
    assert _also_live_rows(("target_load_failed",), "fix_load") == []
    assert _also_live_rows((), "trace_budget") == []


def test_a_route_with_no_addressed_reason_discloses_everything() -> None:
    """`_ROUTE_ADDRESSES` has no entry for the routes that already render every reason. A route
    absent from the map must therefore hold back nothing, rather than silently addressing all."""
    reasons = ("uncontained_worker", "mutant_not_entered")
    body = "\n".join(_also_live_rows(reasons, "some_future_route"))
    for r in reasons:
        assert r in body


def test_every_addressed_reason_is_a_real_cut_reason() -> None:
    """A typo in the map would silently stop suppressing — and the row would repeat the reason the
    remedy already named. Bound to the vocabulary rather than to a copy of it."""
    for route, addressed in _ROUTE_ADDRESSES.items():
        for reason in addressed:
            assert reason in CUT_REASONS, f"{route} claims to address unknown reason {reason!r}"


# ------------------------------------------------------------------ the structural guard


def test_no_repair_render_can_return_without_disclosing_its_reasons() -> None:
    """A property of the MODULE, asserted at source level for the reason S1's guard was.

    The end-to-end behaviour is verified through the real command; what this catches is the defect
    as it actually arose — a render added later that names a command and forgets the reasons. A
    behavioural test at this seam needs a ~25-field fixture for `_converge_action`, and a fixture
    that large rots into testing itself.

    Every `return` inside the `repair_measurement` block must either splice `_also_live_rows` or
    iterate `reasons` itself (the `"; ".join(... for r in reasons)` form).
    """
    tree = ast.parse(pathlib.Path("Detective/cli.py").read_text())
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_converge_action")
    block = next(
        n
        for n in ast.walk(fn)
        if isinstance(n, ast.If)
        and isinstance(n.test, ast.Compare)
        and ast.unparse(n.test) == "kind == 'repair_measurement'"
    )
    offenders = []
    for node in ast.walk(block):
        if not isinstance(node, ast.Return) or node.value is None:
            continue
        src = ast.unparse(node.value)
        if "_also_live_rows" not in src and "for r in reasons" not in src:
            offenders.append(node.lineno)
    assert offenders == [], (
        f"a repair render at cli.py:{offenders} names a remedy without naming the live cut reasons"
    )
