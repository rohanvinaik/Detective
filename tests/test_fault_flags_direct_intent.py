"""#95: a fault flag is read directly where its type declares it, and three-valued where it may be unreported.

THE DEFECT (Detective#95, EP-G3): `getattr(result, "stale_target", False)` and its kin read a FAULT flag with
a default that means "no problem". A producer that renames the flag, or an object that never carried it,
turns every page that reads it quietly clean. Founder ruling: the implementation that aligns with strict
information-theoretic rigour on knowability. A flag is read directly (a rename then raises at the read) or,
where the object can legitimately lack it, as present-true / present-false / ABSENT, ABSENT a named state.

These tests state what must now be true per converted family; the standing guard that forbids a NEW
clean-default read is in test_absorbed_rename_intent.py.
"""

from __future__ import annotations

import types

import pytest

from Detective.cli import _converge_decision, _final_banner_status
from Detective.validity import normalize_validity


def _converge_like(**over):
    base = {
        "function": "m.py::f",
        "functionally_complete": False,
        "missing_lines": (),
        "line_complete": True,
        "admits_certificate": True,
        "verification": None,
        "written_path": "",
        "synthesized_only": False,
        "cut_reasons": (),
        "measurement_gateable": True,
        "stale_target": False,
        "budget_exhausted": False,
    }
    base.update(over)
    return types.SimpleNamespace(**base)


# ---------------------------------------------------------------- stale_target


def test_a_result_that_cannot_say_whether_it_is_stale_is_not_read_as_fresh() -> None:
    """The renamed-flag case: a result without `stale_target` must fail LOUDLY at the read, where the old
    default quietly answered 'fresh' and printed counts over a measurement that did not happen."""
    res = _converge_like()
    del res.stale_target
    with pytest.raises(AttributeError, match="stale_target"):
        _final_banner_status(res)


def test_a_stale_result_still_overrides_the_headline() -> None:
    assert "STALE" in _final_banner_status(_converge_like(stale_target=True)).upper()


# ---------------------------------------------------------------- budget_exhausted (ConvergeResult)


def test_a_result_that_cannot_say_whether_its_budget_ran_out_is_not_read_as_uncut() -> None:
    res = _converge_like()
    del res.budget_exhausted
    rep = types.SimpleNamespace(
        equivalent=[], killable=[], unclassified=[], inputs_expressible=True, load_failed=False, note=""
    )
    with pytest.raises(AttributeError, match="budget_exhausted"):
        _converge_decision(res, rep, render_tests=False)


# ------------------------------------------------------- budget_exhausted (Wesker result, three-valued)


def _wesker_result(**over):
    base = {"is_gateable": True, "coverage_depth": "full"}
    base.update(over)
    return types.SimpleNamespace(**base)


def test_an_engine_that_does_not_report_budget_exhausted_is_named_absent_not_clean() -> None:
    validity = normalize_validity(_wesker_result())
    assert "absent:budget_exhausted" in validity.capability_flags
    assert "budget_exhausted" not in validity.cut_reasons  # absent is not asserted as a cut either


def test_a_reported_false_is_present_false_and_a_reported_true_cuts() -> None:
    clean = normalize_validity(_wesker_result(budget_exhausted=False))
    assert "absent:budget_exhausted" not in clean.capability_flags
    assert "budget_exhausted" not in clean.cut_reasons
    cut = normalize_validity(_wesker_result(budget_exhausted=True))
    assert "absent:budget_exhausted" not in cut.capability_flags
    assert "budget_exhausted" in cut.cut_reasons


# ---------------------------------------------------------------- load_failed


def test_an_audit_that_cannot_say_whether_the_module_failed_to_load_is_not_read_as_loaded() -> None:
    """`_audit_measurement_block` reads `load_failed` off the SuiteAudit, which declares it. An object that
    lacks it must raise at the read; the old default said 'the module loaded'."""
    from Detective.cli import _audit_measurement_block

    with pytest.raises(AttributeError, match="load_failed"):
        _audit_measurement_block(types.SimpleNamespace())


def test_the_classification_status_is_decided_on_a_present_report_or_names_its_absence() -> None:
    """verify_rewrite passes `report.load_failed` only when a report exists; with none, the first code
    (`unavailable`) is what the decision returns, whatever else is passed."""
    from Detective.rewrite import rewrite_classification_status

    assert rewrite_classification_status(False, False, True) == "unavailable"
    assert rewrite_classification_status(True, True, True) == "load_failed"
