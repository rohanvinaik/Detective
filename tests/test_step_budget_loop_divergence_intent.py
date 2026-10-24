"""Intent tests for deterministic step budget loop divergence in Detective (#80, #126).

Verifies:
1. In-thread execution aborts promptly via sys.monitoring step budgeting on runaway loops.
2. Divergence vocabulary: outcome returns _OUTCOME_DIVERGED, search sets diverged=True, blocked=False.
3. classify_survivor yields verdict with diverged=True, label="step-budget-divergent".
4. SurvivorReport carries step_budget_divergent, excluded from candidate_equivalent.
5. audit_partition_sums and SuiteAudit honestly partition diverged mutants.
6. audit_next_action returns "done_divergent" without offering flag or authoring inputs.
"""

from __future__ import annotations

import argparse

import pytest

from Detective.audit import SuiteAudit, audit_partition_sums
from Detective.cli import (
    _audit_closing_action,
    _converge_action,
    _converge_decision,
    _run_flag,
    audit_next_action,
)
from Detective.equivalence import (
    _OUTCOME_DIVERGED,
    SurvivorReport,
    _outcome,
    _search_witness,
    classify_survivor,
)


def terminating_loop(n: int) -> int:
    i = 0
    total = 0
    while i < n:
        total += i
        i += 1
    return total


def non_terminating_loop(n: int) -> int:
    i = 0
    total = 0
    while i < n:
        total += i
        # mutant removes increment: i += 1 -> pass
    return total


def test_outcome_divergence_under_step_budget() -> None:
    # Original terminates well within 100 steps
    orig_steps: list[int] = []
    orig_res = _outcome(terminating_loop, (5,), cap=200, step_count=orig_steps)
    assert orig_res == "10"
    assert orig_steps and orig_steps[0] > 0

    # Mutant exceeds step budget and returns _OUTCOME_DIVERGED without waiting out wall timeout
    mut_res = _outcome(non_terminating_loop, (5,), cap=200)
    assert mut_res == _OUTCOME_DIVERGED


def test_search_witness_divergence_detection() -> None:
    witness, crash_witness, blocked, diverged = _search_witness(
        terminating_loop, non_terminating_loop, [(5,)]
    )
    assert witness is None
    assert crash_witness is None
    assert blocked is False
    assert diverged is True


def test_classify_survivor_divergence_verdict() -> None:
    verdict = classify_survivor(
        "M_LOOP",
        "LOOP_TERMINATION",
        "- i += 1\n+ pass",
        terminating_loop,
        non_terminating_loop,
        [(5,)],
    )
    assert verdict.diverged is True
    assert verdict.blocked is False
    assert verdict.witness is None
    assert verdict.label == "step-budget-divergent"


def test_survivor_report_partitions_divergence() -> None:
    v = classify_survivor(
        "M_LOOP",
        "LOOP_TERMINATION",
        "- i += 1\n+ pass",
        terminating_loop,
        non_terminating_loop,
        [(5,)],
    )
    report = SurvivorReport((v,), ())
    assert len(report.step_budget_divergent) == 1
    assert report.step_budget_divergent[0].mutant_id == "M_LOOP"
    assert len(report.candidate_equivalent) == 0
    assert len(report.equivalent) == 0
    assert len(report.unclassified) == 0
    assert len(report.killable) == 0


def test_audit_partition_sums_accounting() -> None:
    # Diverged mutants must be preserved in the exact sum
    assert audit_partition_sums(
        total=10,
        value_killed=7,
        killable=1,
        candidate_equivalent=1,
        manual=0,
        fence=0,
        unclassified=0,
        diverged=1,
    )

    # Discrepancy caught
    assert not audit_partition_sums(
        total=10,
        value_killed=7,
        killable=1,
        candidate_equivalent=1,
        manual=0,
        fence=0,
        unclassified=0,
        diverged=0,
    )


def test_audit_next_action_done_divergent() -> None:
    action = audit_next_action(
        block="",
        has_failing_tests=False,
        killable_gaps=0,
        missing_lines=0,
        redundant_tests=0,
        removing=False,
        candidate_equivalent=0,
        has_equivalent_ids=False,
        unclassified=0,
        diverged=2,
    )
    assert action == "done_divergent"

    dummy_audit = SuiteAudit(
        function="fn",
        test_count=1,
        kill_pct=100.0,
        mutant_complete=True,
        line_complete=True,
        redundant_tests=(),
        failing_tests=(),
        killable_gaps=(),
        missing_lines=(),
        minimal_test_count=1,
        step_budget_divergent=2,
    )
    closing = _audit_closing_action(dummy_audit, action)
    rendered = "\n".join(closing)
    assert "INCOMPLETE:  2 survivor(s) diverged deterministically" in rendered
    assert "DONE:  no gaps found." not in rendered
    assert "nothing to `flag`" in rendered


def test_flag_refusal_on_divergent_mutant(monkeypatch: pytest.MonkeyPatch) -> None:
    # A mutant that diverged cannot be flagged as equivalent
    class DummyResult:
        function_key = "dummy::fn"
        value_survivor_records = [
            {
                "mutant_id": "M_INF",
                "diff_summary": "loop removal",
                "killed_by": "diverged",
                "disposition": "step-budget-divergent",
            }
        ]

    monkeypatch.setattr("Detective.engine.profile", lambda *a, **kw: DummyResult())

    args = argparse.Namespace(
        style=False,
        mutant_id="M_INF",
        project_root=".",
        target="dummy::fn",
        json=True,
        fence=False,
        note="assume equivalent",
    )
    code = _run_flag(args, "dummy.py", "fn")
    assert code == 1


def test_converge_divergence_action_and_decision() -> None:
    v = classify_survivor(
        "M_LOOP",
        "LOOP_TERMINATION",
        "- i += 1\n+ pass",
        terminating_loop,
        non_terminating_loop,
        [(5,)],
    )
    rep = SurvivorReport((v,), ())

    class DummyConvergeResult:
        function = "dummy.py::loop_fn"
        functionally_complete = False
        missing_lines = ()
        stale_target = False
        admits_certificate = True
        verification = None
        written_path = ""
        synthesized_only = False

    res = DummyConvergeResult()
    decision = _converge_decision(res, rep, render_tests=False)
    assert decision.code == "step_budget_divergent"
    assert decision.residual == ("step_budget_divergent", ("M_LOOP",))
    assert decision.state.get("step_budget_divergent") == ["M_LOOP"]

    action = _converge_action(res, rep, decision=decision)
    rendered = "\n".join(action)
    assert "INCOMPLETE:  1 mutant(s) diverged deterministically" in rendered
    assert "AUTHOR INPUT" not in rendered
    assert "DONE:" not in rendered
    assert "the style pass" not in rendered
