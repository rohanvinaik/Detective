"""Intent: a mutant the memory cap stopped is one mutant with no verdict, on every surface (Wesker #45).

THE DEFECT, measured on `converge --isolated --mem-limit-mb 64` over a function that allocates in a loop,
against a Wesker where #45 has landed. Wesker now returns the capped mutant as an unscored record whose
disposition is `memory_cut`, and reads the function `profiled`. Detective had no row for the disposition:
it fell to `engine_refused_unspecified`, and the page said

    STOP:  the engine refused to gate this measurement without naming a reason
    FINAL: UNGATEABLE — the engine refused to gate this measurement without naming a reason

over a measurement whose cause is known and named. The truth is a cause of its own: the cap stopped a
mutant, a stop by a budget says nothing about the value (neither a kill nor a survivor), and every other
mutant was evaluated. The remedy is not `diverged`'s or `undetermined`'s: raise `--mem-limit-mb` only if the
tests legitimately need more than the cap; otherwise the mutant is a runaway and the stop is right.

These tests name no engine: each builds the record Wesker's contract describes, so they hold whichever
Wesker is installed.
"""

from __future__ import annotations

import types
from types import SimpleNamespace

import pytest

from Detective.audit import audit_measurement_incomplete, unresolved_gate_standing
from Detective.certificates import NO_VERDICT_STANDINGS, UNGATEABLE_STANDINGS
from Detective.cli import (
    _memory_cap_rows,
    _unscored_flag_refusal,
    memory_cut_remedy,
    memory_cut_text,
    repair_measurement_route,
    universe_tail,
)
from Detective.converge import ungateable_standing
from Detective.validity import (
    CUT_REASONS,
    MEASUREMENT_VALIDITY_SCHEMA,
    PER_MUTANT_REASONS,
    UNSCORED_DISPOSITION_REASONS,
    classification_standing,
    cut_reason_sentence,
    measurement_cut_reasons,
    normalize_validity,
    unresolved_mutant_records,
)


def _result(records, **extra):
    """What the engine reports after #45: the function evaluated in full, some mutants unscored."""
    counts: dict[str, int] = {}
    for record in records:
        counts[record["disposition"]] = counts.get(record["disposition"], 0) + 1
    return SimpleNamespace(
        is_gateable=False,
        coverage_depth="profiled",
        all_contained=True,
        budget_exhausted=False,
        collection_errors=[],
        collection_conflicts=[],
        execution_mode="isolated",
        per_category=[SimpleNamespace(unscored_by=counts)],
        unscored_records=list(records),
        **extra,
    )


CAPPED = {"mutant_id": "ARITHMETIC_a1", "disposition": "memory_cut"}


def test_the_disposition_has_its_own_per_mutant_reason_not_the_unspecified_refusal():
    assert UNSCORED_DISPOSITION_REASONS["memory_cut"] == "memory_cut"
    assert "memory_cut" in CUT_REASONS
    assert "memory_cut" in PER_MUTANT_REASONS
    assert MEASUREMENT_VALIDITY_SCHEMA >= 10, "a changed reason vocabulary bumps the schema"
    validity = normalize_validity(_result([CAPPED]))
    assert validity.cut_reasons == ("memory_cut",), validity.cut_reasons
    assert "engine_refused_unspecified" not in validity.cut_reasons
    assert validity.coverage_depth == "profiled", "a capped mutant does not cut the function"


def test_it_is_reported_in_declaration_order_beside_the_other_per_mutant_reasons():
    reasons = measurement_cut_reasons(
        True, False, False, "profiled", "contained", False, mutant_wall_undetermined=True, memory_cut=True
    )
    assert reasons == ("mutant_wall_undetermined", "memory_cut")
    assert list(reasons) == [r for r in CUT_REASONS if r in reasons]
    assert measurement_cut_reasons(True, True, False, "profiled", "contained", False) == ()


def test_the_sentence_states_the_cause_and_both_readings_of_the_remedy():
    sentence = cut_reason_sentence("memory_cut")
    assert "memory cap" in sentence and "--mem-limit-mb" in sentence
    assert "neither killed nor survived" in sentence
    assert "runaway" in sentence and "legitimately need" in sentence
    assert "unrecognised" not in sentence
    assert "cut before" not in sentence, "the cap no longer cuts the function"


@pytest.mark.parametrize(
    ("reasons", "standing"),
    [
        (["memory_cut"], "classify_beside_unresolved"),
        (["memory_cut", "mutant_wall_undetermined"], "classify_beside_unresolved"),
        (["memory_cut", "coverage_truncated"], "blocked"),
    ],
)
def test_the_other_survivors_are_still_classified(reasons, standing):
    assert classification_standing(reasons) == standing


def test_the_unresolved_records_name_it():
    assert unresolved_mutant_records([CAPPED]) == (("ARITHMETIC_a1", "memory_cut"),)


@pytest.mark.parametrize(
    ("reasons", "standing"),
    [
        (("memory_cut",), "mutants_memory_cut"),
        (("step_budget_exceeded",), "mutants_diverged"),
        (("mutant_wall_undetermined",), "mutants_undetermined"),
        # Beside another reason its sign is the umbrella; the reasons list names each.
        (("memory_cut", "step_budget_exceeded"), "ungateable"),
        (("memory_cut", "mutant_wall_undetermined"), "ungateable"),
        (("memory_cut", "coverage_truncated"), "ungateable"),
        ((), "ungateable"),
    ],
)
def test_the_standing_has_its_own_name_and_never_shares_a_sign(reasons, standing):
    assert ungateable_standing(reasons) == standing


def test_the_named_standing_is_an_ungateable_standing_everywhere_that_asks():
    assert "mutants_memory_cut" in NO_VERDICT_STANDINGS
    assert "mutants_memory_cut" in UNGATEABLE_STANDINGS


@pytest.mark.parametrize(
    ("reasons", "route"),
    [
        (("memory_cut",), "memory_cap"),
        (("memory_cut", "step_budget_exceeded"), "execution_budget"),
        (("memory_cut", "mutant_wall_undetermined"), "execution_budget"),
        (("memory_cut", "write_outside_authority"), "write_authority"),
        (("memory_cut", "nested_measurement"), "isolate"),
        (("memory_cut", "budget_exhausted"), "memory_cap"),
    ],
)
def test_the_route_is_its_own_unless_a_run_level_reason_leads(reasons, route):
    assert repair_measurement_route(reasons) == route


def test_the_universe_line_says_a_mutant_reached_no_verdict():
    assert universe_tail(False, ["memory_cut"]) == "exhaustive_unresolved"


def test_the_strict_gate_names_it_and_never_fails_on_it():
    assert unresolved_gate_standing("memory_cut") == "memory_floor"
    # the CLI gates on repairable / unknown only; a memory_floor mutant leaves the count at zero
    gating = [s for s in map(unresolved_gate_standing, ("memory_cut",)) if s in ("repairable", "unknown")]
    assert audit_measurement_incomplete(0, 0, len(gating), 0) is False
    # the sibling that IS repairable still gates, and a reason nobody knows still gates
    assert unresolved_gate_standing("original_also_fails") == "repairable"
    assert unresolved_gate_standing("memory_cut_but_misspelled") == "unknown"


def test_the_page_row_names_the_mutants_from_the_records_and_the_cap():
    text = memory_cut_text(64, ["A", "B"])
    assert text.startswith("2 — A, B:")
    assert "64 MB memory cap" in text and "not kills, not survivors" in text
    assert memory_cut_text(64, []) == ""
    many = memory_cut_text(64, [f"M{i}" for i in range(8)])
    assert "M4, … +3" in many and "M5" not in many.split("…")[0]
    assert "64 MB" not in memory_cut_text(0, ["A"]), "no number is invented for an unknown cap"


def test_the_remedy_is_a_hand_back_that_states_both_readings():
    text = memory_cut_remedy(64)
    assert "--mem-limit-mb" in text and "legitimately need" in text and "64 MB" in text
    assert "runaway" in text
    assert "64 MB" not in memory_cut_remedy(0)


def test_the_converge_page_rows_come_from_unscored_records_not_from_a_cut():
    # Only the unresolved pairs decide; the standing says nothing about WHICH mutants (it is function-level)
    rows = _memory_cap_rows("cut", 64, (("CAPPED_1", "memory_cut"), ("LOOPS_2", "diverged")))
    assert len(rows) == 1 and "memory cut" in rows[0] and "CAPPED_1" in rows[0] and "LOOPS_2" not in rows[0]
    assert _memory_cap_rows("cut", 64, (("LOOPS_2", "diverged"),)) == [], (
        "a cap that fired names no mutant by itself"
    )
    assert _memory_cap_rows("cut", 64) == []
    both = _memory_cap_rows("telemetry_only", 64, (("CAPPED_1", "memory_cut"),))
    assert len(both) == 2, "an unapplied cap and a capped mutant are different facts, two rows"


def test_flag_refuses_it_by_name(capsys):
    args = types.SimpleNamespace(mutant_id="ARITHMETIC_a1", json=False, target="m.py::f")
    assert _unscored_flag_refusal(args, _result([CAPPED])) == 1
    err = capsys.readouterr().err
    assert "reached no verdict (memory_cut)" in err
    assert "memory cap" in err and "unrecognised" not in err and "refused to gate" not in err
    survivor = types.SimpleNamespace(mutant_id="OTHER", json=False, target="m.py::f")
    assert _unscored_flag_refusal(survivor, _result([CAPPED])) is None, "only a no-verdict id is refused"


def test_flag_refuses_it_in_json_with_the_disposition(capsys):
    args = types.SimpleNamespace(mutant_id="ARITHMETIC_a1", json=True, target="m.py::f")
    assert _unscored_flag_refusal(args, _result([CAPPED])) == 1
    out = capsys.readouterr().out
    assert '"reason": "unscored_mutant"' in out and '"disposition": "memory_cut"' in out
