"""Intent: a not-entered mutant is rendered under the cause Wesker named, with that cause's repair (#77).

The defect, reproduced 2026-10-25 through `detective audit` on a PLAIN, undecorated function
(``def f(x, n=3)``) whose one routed test imports it and never calls it. Wesker#18 named the cause
of its two not-entered default-argument mutants ``not_reached`` (every test that ran against them was
traced in full and none executed a line), and the report still said:

    INCOMPLETE:  one or more mutants were installed but no test ever called them, so their survival
    measures REACH, not specification — the namespace holds the mutant while the caller holds the
    original (the decorator/registry capture); route a test through the patched name, or pin the caller
      · Resolve            the reported measurement causes before acting on suite gaps or redundancy.

Three defects in one block: the sentence named a mechanism that was absent; the run-level cut left
thirteen unrelated survivors "unclassified — the search could not run on them"; and the next step was
not one — no re-measurement changes a function no test calls.

Intent:
- each Wesker cause is its own cut reason with its own repair sentence, and a cause this version does
  not know (or none at all) falls back to a sentence that names NO mechanism;
- a captured copy is stated as what it is: the install replaces only module attributes, so the copy is
  unreachable through itself — a floor with its reason — and WHERE it lives is printed;
- a not-entered mutant names itself, so the other survivors are classified beside it;
- "no consulted test calls this function" is a reach gap whose repair is a test (converge), and that
  repair changes the verdict; a captured copy's repair (a test through the module attribute) does too.
"""

from __future__ import annotations

import os
import subprocess
import sys
import types

import pytest

from Detective.cli import _audit_measurement_block, _not_entered_rows, repair_measurement_route
from Detective.validity import (
    CUT_REASONS,
    NOT_ENTERED_CAUSE_REASONS,
    NOT_ENTERED_REASONS,
    classification_standing,
    cut_reason_sentence,
    measurement_cut_kind,
    measurement_cut_reasons,
    normalize_validity,
    not_entered_detail,
    not_entered_reasons,
    unresolved_mutant_records,
    unscored_record_reason,
)

_WESKER_CAUSES = (
    "not_reached",
    "decorator_wrapper",
    "captured_at_import",
    "pre_bound_reference",
    "holder_not_found",
    "no_reach_data",
)

# ── the decisions ───────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("cause", _WESKER_CAUSES)
def test_each_named_cause_is_its_own_reason(cause):
    (reason,) = not_entered_reasons([cause])
    assert reason == f"mutant_not_entered_{cause}"
    assert reason in CUT_REASONS, "a reason outside the exhaustive vocabulary cannot render consistently"


@pytest.mark.parametrize("causes", [[], ["unclassified"], ["a_cause_from_the_future"], [""]])
def test_an_unnamed_or_unknown_cause_is_the_mechanism_free_fallback(causes):
    assert not_entered_reasons(causes) == ("mutant_not_entered",)


def test_several_causes_are_all_named_in_declaration_order():
    got = not_entered_reasons(["pre_bound_reference", "not_reached", "unclassified", "not_reached"])
    assert got == (
        "mutant_not_entered_not_reached",
        "mutant_not_entered_pre_bound_reference",
        "mutant_not_entered",
    )


def test_the_cause_table_and_the_vocabulary_agree():
    assert set(NOT_ENTERED_CAUSE_REASONS) == set(_WESKER_CAUSES)
    assert set(NOT_ENTERED_REASONS) == {f"mutant_not_entered_{c}" for c in _WESKER_CAUSES} | {
        "mutant_not_entered"
    }
    assert NOT_ENTERED_REASONS <= set(CUT_REASONS)


def test_the_boolean_path_without_causes_still_names_a_reason():
    """An engine before Wesker#18 reports `not_entered` with no cause: never silently clean."""
    base = {
        "reported_gateable": True,
        "gateable": False,
        "budget_exhausted": False,
        "coverage_depth": "profiled",
        "containment": "contained",
        "identity_ambiguous": False,
    }
    assert measurement_cut_reasons(**base, not_entered=True) == ("mutant_not_entered",)
    assert measurement_cut_reasons(**base, not_entered=True, not_entered_causes=("captured_at_import",)) == (
        "mutant_not_entered_captured_at_import",
    )
    # A cause without the boolean (the records are the evidence) is still named.
    assert measurement_cut_reasons(**base, not_entered_causes=["not_reached"]) == (
        "mutant_not_entered_not_reached",
    )


@pytest.mark.parametrize(
    ("reasons", "standing"),
    [
        (["mutant_not_entered_not_reached"], "classify_beside_unresolved"),
        (["mutant_not_entered_captured_at_import", "mutant_wall_undetermined"], "classify_beside_unresolved"),
        (["mutant_not_entered"], "classify_beside_unresolved"),
        (["mutant_not_entered_not_reached", "coverage_truncated"], "blocked"),
        (["mutant_not_entered_decorator_wrapper", "uncontained_worker"], "blocked"),
        (["mutant_not_installed"], "blocked"),
    ],
)
def test_a_not_entered_mutant_names_itself_and_the_others_are_classified(reasons, standing):
    assert classification_standing(reasons) == standing


def test_a_not_entered_mutant_is_not_relabelled_no_verdict():
    """It has its own rows; `⚠ no verdict` stays the wall/step outcomes only."""
    assert unresolved_mutant_records([{"mutant_id": "VALUE_a", "disposition": "not_entered"}]) == ()


@pytest.mark.parametrize(
    ("reasons", "kind"),
    [
        ([], "none"),
        (["mutant_not_entered_not_reached"], "reach_gap"),
        (["mutant_not_entered_not_reached", "mutant_not_entered_not_reached"], "reach_gap"),
        (["mutant_not_entered_not_reached", "mutant_not_entered_captured_at_import"], "repair"),
        (["mutant_not_entered_not_reached", "mutant_wall_undetermined"], "repair"),
        (["mutant_not_entered"], "repair"),
        (["mutant_not_entered_no_reach_data"], "repair"),
    ],
)
def test_only_a_function_no_test_calls_is_a_reach_gap(reasons, kind):
    assert measurement_cut_kind(reasons) == kind


@pytest.mark.parametrize("reason", sorted(NOT_ENTERED_REASONS))
def test_every_not_entered_reason_routes_to_the_mutant_phase(reason):
    assert repair_measurement_route((reason,)) == "mutant_phase"
    # ...and a run-level blocker still outranks it.
    assert repair_measurement_route(("collection_incomplete", reason)) == "fix_collection"


@pytest.mark.parametrize(
    ("record", "reason"),
    [
        (
            {"disposition": "not_entered", "cause": "captured_at_import"},
            "mutant_not_entered_captured_at_import",
        ),
        ({"disposition": "not_entered", "cause": "not_reached"}, "mutant_not_entered_not_reached"),
        ({"disposition": "not_entered"}, "mutant_not_entered"),
        ({"disposition": "not_entered", "cause": None}, "mutant_not_entered"),
        ({"disposition": "harness_error"}, "mutant_construction_failed"),
        ({"disposition": "undetermined"}, "mutant_wall_undetermined"),
        ({"disposition": "a_future_disposition"}, "engine_refused_unspecified"),
        ({}, "engine_refused_unspecified"),
    ],
)
def test_one_record_carries_its_own_reason(record, reason):
    assert unscored_record_reason(record) == reason


# ── the sentences ───────────────────────────────────────────────────────────────────────────────


def test_no_sentence_names_a_mechanism_its_cause_did_not_observe():
    old = "the decorator/registry capture"
    for reason in NOT_ENTERED_REASONS:
        sentence = cut_reason_sentence(reason)
        assert old not in sentence, reason
        assert not sentence.startswith("an unrecognised"), f"{reason} has no sentence of its own"
    for reason in NOT_ENTERED_REASONS - {"mutant_not_entered_decorator_wrapper"}:
        assert "decorator" not in cut_reason_sentence(reason), reason
    assert "registry" not in cut_reason_sentence("mutant_not_entered_not_reached")
    assert "registry" not in cut_reason_sentence("mutant_not_entered")


def test_each_cause_names_a_different_repair():
    sentences = {reason: cut_reason_sentence(reason) for reason in NOT_ENTERED_REASONS}
    assert len(set(sentences.values())) == len(sentences)
    assert "converge" in sentences["mutant_not_entered_not_reached"]
    assert "__wrapped__" in sentences["mutant_not_entered_decorator_wrapper"]
    assert "module.fn(...)" in sentences["mutant_not_entered_captured_at_import"]
    assert "m.fn(...)" in sentences["mutant_not_entered_pre_bound_reference"]
    assert "UNKNOWN, not negative" in sentences["mutant_not_entered_no_reach_data"]


def test_a_captured_copy_is_stated_as_a_floor_with_its_reason():
    """D#77: state whether the install replaces only the module attribute, and that the copy is
    unreachable through that copy."""
    sentence = cut_reason_sentence("mutant_not_entered_captured_at_import")
    assert "replaces only module attributes" in sentence
    assert "never the captured copy" in sentence
    assert "floor" in sentence


# ── the adapter and the detail ──────────────────────────────────────────────────────────────────


def _result(records, *, causes=True, **fields):
    counts: dict[str, int] = {}
    for r in records:
        counts[r["disposition"]] = counts.get(r["disposition"], 0) + 1
    base = {
        "is_gateable": not records,
        "coverage_depth": "profiled",
        "collection_conflicts": [],
        "all_contained": True,
        "collection_errors": [],
        "execution_mode": "in_process",
        "budget_exhausted": False,
        "per_category": [types.SimpleNamespace(unscored_by=counts)],
        "unscored_records": list(records),
    }
    if causes:
        named: dict[str, int] = {}
        for r in records:
            if r["disposition"] == "not_entered":
                c = str(r.get("cause") or "unclassified")
                named[c] = named.get(c, 0) + 1
        base["not_entered_causes"] = named
    base.update(fields)
    return types.SimpleNamespace(**base)


def test_the_adapter_reads_the_named_cause():
    records = [{"mutant_id": "VALUE_a", "disposition": "not_entered", "cause": "not_reached", "holders": []}]
    validity = normalize_validity(_result(records))
    assert validity.cut_reasons == ("mutant_not_entered_not_reached",)
    assert not validity.admits_certificate, "a mutant no test entered never lets a certificate stand"
    assert validity.not_entered[0]["mutants"] == ["VALUE_a"]


def test_an_engine_that_names_no_cause_keeps_the_fallback():
    records = [{"mutant_id": "VALUE_a", "disposition": "not_entered"}]
    validity = normalize_validity(_result(records, causes=False))
    assert validity.cut_reasons == ("mutant_not_entered",)


def test_the_detail_carries_where_the_original_is_held_and_a_cut_scan():
    records = [
        {
            "mutant_id": "VALUE_a",
            "disposition": "not_entered",
            "cause": "captured_at_import",
            "holders": [{"kind": "captured", "where": "m.HANDLERS['inc']"}],
            "holder_scan": "complete",
        },
        {
            "mutant_id": "VALUE_b",
            "disposition": "not_entered",
            "cause": "captured_at_import",
            "holders": [{"kind": "captured", "where": "m.HANDLERS['inc']"}],
            "holder_scan": "complete",
        },
        {
            "mutant_id": "STMT_c",
            "disposition": "not_entered",
            "cause": "holder_not_found",
            "holder_scan": "budget_cut",
        },
        {"mutant_id": "STMT_d", "disposition": "undetermined"},
        "not a record",
    ]
    detail = not_entered_detail(records)
    assert [e["cause"] for e in detail] == ["captured_at_import", "holder_not_found"], "declaration order"
    captured, unfound = detail
    assert captured["mutants"] == ["VALUE_a", "VALUE_b"]
    assert captured["holders"] == ["captured m.HANDLERS['inc']"], "one holder, named once"
    assert unfound["holder_scan"] == "budget_cut"
    rows = "\n".join(_not_entered_rows(detail))
    assert "cause captured_at_import: VALUE_a, VALUE_b" in rows
    assert "captured m.HANDLERS['inc']" in rows
    assert "budget_cut" in rows and "may exist" in rows, "a cut scan's silence must not read as 'no holder'"
    assert _not_entered_rows(()) == []


def test_a_reach_gap_is_not_a_measurement_block_and_a_captured_copy_is():
    gap = types.SimpleNamespace(
        cut_reasons=("mutant_not_entered_not_reached",),
        load_failed=False,
        note="",
        killable_gaps=(),
        missing_lines=(2, 3, 4),
    )
    assert _audit_measurement_block(gap) != "repair_measurement"
    captured = types.SimpleNamespace(
        cut_reasons=("mutant_not_entered_captured_at_import",), load_failed=False
    )
    assert _audit_measurement_block(captured) == "repair_measurement"


def test_a_reach_gap_with_nothing_left_to_write_never_closes_on_done():
    """Adversarial edge: every line flagged unreachable and no killable survivor, yet the not-entered
    mutants withhold the certificate. Falling through, the ladder printed `DONE: the suite is complete
    and minimal` over a withheld certificate; it stays a measurement block and names the repair."""
    from Detective.audit import SuiteAudit
    from Detective.cli import _audit_action

    a = SuiteAudit(
        function="m.py::f",
        test_count=1,
        kill_pct=0.0,
        mutant_complete=False,
        line_complete=False,
        redundant_tests=(),
        failing_tests=(),
        killable_gaps=(),
        missing_lines=(),
        minimal_test_count=1,
        manually_unreachable=3,
        total_mutants=2,
        cut_reasons=("mutant_not_entered_not_reached",),
    )
    assert _audit_measurement_block(a) == "repair_measurement"
    text = "\n".join(_audit_action(a))
    assert "DONE" not in text, text
    assert text.startswith("INCOMPLETE:  ") and "converge writes one" in text, text


# ── end to end: the plain function, and the captured copy, through the real CLI ─────────────────

_PLAIN = "def f(x, n=3):\n    if x > n:\n        return x + 1\n    return x - 1\n"
_IMPORTS_ONLY = "from m import f\n\n\ndef test_imports_only():\n    assert callable(f)\n"
_CAPTURED = "def f(x):\n    if x > 0:\n        return x + 1\n    return x - 1\n\n\nHANDLERS = {'inc': f}\n"
_THROUGH_REGISTRY = (
    "import m\nfrom m import f\n\n\ndef test_through_registry():\n    assert callable(f)\n"
    "    assert m.HANDLERS['inc'](2) == 3\n    assert m.HANDLERS['inc'](-2) == -3\n"
)
_THROUGH_ATTRIBUTE = (
    "import m\n\n\ndef test_f_through_module_attribute():\n"
    "    assert m.f(2) == 3\n    assert m.f(-2) == -3\n    assert m.f(0) == -1\n    assert m.f(1) == 2\n"
)


def _detective(cwd, *argv):
    return subprocess.run(
        [sys.executable, "-m", "Detective", *argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
        env=dict(os.environ),
    )


def _project(tmp_path, source, test):
    (tmp_path / "m.py").write_text(source)
    (tmp_path / "test_m.py").write_text(test)
    migrate = _detective(tmp_path, "regime", "--migrate", "--project-root", str(tmp_path))
    assert migrate.returncode == 0, migrate.stdout + migrate.stderr


def test_a_plain_function_no_test_calls_reads_its_cause_and_converge_moves_the_verdict(tmp_path):
    _project(tmp_path, _PLAIN, _IMPORTS_ONLY)
    before = _detective(tmp_path, "audit", "m.py::f").stdout
    assert "decorator" not in before and "registry" not in before, before
    assert "cause not_reached" in before, before
    assert "unclassified" not in before, "two not-entered mutants left unrelated survivors unclassified"
    assert "DO THIS:  detective converge 'm.py::f'" in before, "the repair is a test, and converge writes it"
    _detective(tmp_path, "converge", "m.py::f")
    after = _detective(tmp_path, "audit", "m.py::f").stdout
    assert "not entered" not in after, after
    assert "INCOMPLETE" not in after, after


def test_a_captured_copy_names_where_it_lives_and_its_repair_moves_the_verdict(tmp_path):
    _project(tmp_path, _CAPTURED, _THROUGH_REGISTRY)
    before = _detective(tmp_path, "audit", "m.py::f").stdout
    assert "cause captured_at_import" in before, before
    assert "captured m.HANDLERS['inc']" in before, before
    assert "replaces only module attributes" in before, before
    (tmp_path / "test_direct.py").write_text(_THROUGH_ATTRIBUTE)
    after = _detective(tmp_path, "audit", "m.py::f").stdout
    assert "not entered" not in after, after
    assert (
        "· complete"
        in after.splitlines()[next(i for i, ln in enumerate(after.splitlines()) if "— audit" in ln)]
    )
