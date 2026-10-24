"""#80/#126: Wesker's unresolved executions cannot turn into proof or input advice.

The engine excludes these mutants from its score. The integration seam must retain
why they are unmeasured, even if the ordinary survivor set is empty.
"""

from types import SimpleNamespace

import pytest

from Detective.cli import (
    _audit_action,
    _audit_decision,
    _converge_action,
    _converge_decision,
    repair_measurement_route,
)
from Detective.validity import CUT_REASONS, cut_reason_sentence, measurement_cut_reasons, normalize_validity


@pytest.mark.parametrize(
    ("disposition", "reason"),
    [("diverged", "step_budget_exceeded"), ("undetermined", "mutant_wall_undetermined")],
)
def test_unresolved_execution_keeps_its_reason_through_the_real_engine_adapter(
    disposition, reason, monkeypatch, tmp_path
):
    from Wesker.engine import CategoryResult, MutationCategory, ProfilingResult

    category = CategoryResult(category=MutationCategory.VALUE, unscored=1, unscored_by={disposition: 1})
    profile = ProfilingResult(
        function_key="calc.py::target",
        is_gateable=False,
        coverage_depth="cut",
        per_category=[category],
    )
    validity = normalize_validity(profile)
    assert not validity.admits_certificate
    assert reason in validity.cut_reasons
    assert reason in CUT_REASONS
    assert "unrecognised" not in cut_reason_sentence(reason)
    result = SimpleNamespace(
        function="calc.py::target",
        functionally_complete=False,
        missing_lines=(),
        admits_certificate=validity.admits_certificate,
        cut_reasons=validity.cut_reasons,
        stale_target=False,
        verification=None,
        written_path="",
        synthesized_only=False,
    )
    decision = _converge_decision(result, None, render_tests=False)
    assert decision.code == "repair_measurement"
    assert decision.route == "execution_budget"
    assert decision.kind == "stop"
    assert decision.argv is None
    rendered = "\n".join(_converge_action(result, None, decision=decision))
    assert "INCOMPLETE:" in rendered
    assert "AUTHOR INPUT" not in rendered
    assert "detective flag" not in rendered
    assert "--trace-budget" not in rendered
    assert "behaviour is pinned" not in rendered
    from Detective.audit import audit_suite
    from Detective.equivalence import SurvivorReport

    (tmp_path / "calc.py").write_text("def target(x):\n    return x + 1\n")
    monkeypatch.setattr("Detective.audit.profile", lambda *a, **kw: profile)
    monkeypatch.setattr("Detective.audit.classify_survivors", lambda *a, **kw: SurvivorReport((), ()))
    audit = audit_suite("calc.py", "target", str(tmp_path))
    assert not audit.complete
    assert reason in audit.cut_reasons
    for two_sign in (False, True):
        audit_decision = _audit_decision(audit, two_sign=two_sign)
        assert audit_decision.code == "repair_measurement"
        assert audit_decision.route == "execution_budget"
        assert audit_decision.kind == "stop"
        assert audit_decision.argv is None
        closing = "\n".join(_audit_action(audit, decision=audit_decision))
        assert "INCOMPLETE:" in closing
        assert "DONE:" not in closing
        assert "AUTHOR INPUT" not in closing
        assert "detective flag" not in closing


def test_execution_reasons_remain_distinct_and_ordered():
    reasons = measurement_cut_reasons(
        True,
        False,
        False,
        "cut",
        "contained",
        False,
        step_budget_exceeded=True,
        mutant_wall_undetermined=True,
    )
    assert reasons == ("step_budget_exceeded", "mutant_wall_undetermined", "coverage_truncated")
    assert repair_measurement_route(reasons) == "execution_budget"
    assert repair_measurement_route(("uncontained_worker", *reasons)) == "isolate"
    assert repair_measurement_route(("mutant_not_installed", *reasons)) == "mutant_phase"
