"""Ledger B/E: a refused empty measurement cannot become a complete audit or preserved rewrite."""

import ast
import hashlib
from types import SimpleNamespace

import pytest
from _support import make_pr

from Detective import audit, engine, pins
from Detective.equivalence import SurvivorReport
from Detective.rewrite import RewriteReceipt, verify_rewrite
from Detective.verdict_cache import wesker_policy_id


def test_an_empty_invalid_profile_is_not_a_completed_audit(monkeypatch, tmp_path):
    (tmp_path / "missing.py").write_text("def f():\n    return 1\n")
    result = make_pr(function_key="missing.py::f")
    result.is_gateable = False
    result.collection_errors = ("test_broken.py",)
    monkeypatch.setattr(audit, "profile", lambda *a, **k: result)
    report = audit.audit_suite("missing.py", "f", str(tmp_path))
    assert not report.mutant_complete
    assert not report.line_complete
    classification = engine.classify_survivors("missing.py", "f", str(tmp_path), profile_result=result)
    assert not classification.measurement_valid
    assert classification.note


def test_an_invalid_neighbor_cannot_authorize_a_test_removal(tmp_path):
    result = make_pr()
    result.is_gateable = False
    result.collection_errors = ("test_broken.py",)
    result.kill_matrix = {"M": ["test_a"]}
    result.line_coverage = {"test_a": [2]}
    candidates = {"test_a", "legacy:test_b.py::test_b"}
    evidence = audit._removal_needs(result, candidates, str(tmp_path))
    assert evidence.state == "unverified"
    assert evidence.needed == frozenset()
    assert "collection_incomplete" in evidence.cut_reasons


@pytest.mark.parametrize(
    "fault", ["load", "measurement", "uncontained", "unavailable", "observer_fault", "advisory"]
)
def test_a_refused_empty_classification_cannot_preserve_a_rewrite(monkeypatch, tmp_path, fault):
    import importlib

    from Wesker.monitoring import MonitoringObservationFailed, MonitoringUnavailable

    from Detective.capture import ObservationIncomplete

    certify = importlib.import_module("Detective.certify")

    original = "def f(x):\n    return x + 1\n"
    (tmp_path / "rewrite_closure.py").write_text("def f(x):\n    return 1 + x\n")
    proof = tmp_path / "test_proof.py"
    proof.write_text("def test_proof():\n    assert True\n")
    receipt = RewriteReceipt(
        function="rewrite_closure.py::f",
        original_source=original,
        source_digest=hashlib.sha256(original.encode()).hexdigest(),
        function_digest=pins.function_digest(ast.parse(original).body[0]),
        # The engine's live policy: the policy gate runs before classification, so a placeholder id
        # would return POLICY_MOVED and this test would pass without ever reaching the empty
        # measurement it exists to check.
        policy_id=wesker_policy_id(),
        universe_size=1,
        proof_suite=(proof.name,),
        proof_status="passed",
        functionally_complete=True,
        proof_digests=((proof.name, hashlib.sha256(proof.read_bytes()).hexdigest()),),
    )
    monkeypatch.setattr(
        certify, "run_pytest_verification", lambda *a, **k: SimpleNamespace(ok=True, status="passed")
    )
    error = {
        "uncontained": ObservationIncomplete("outcome_uncontained", "live worker", contained=False),
        "unavailable": MonitoringUnavailable("monitoring unavailable"),
        "observer_fault": MonitoringObservationFailed("observer_fault: broken observer", 1),
        "advisory": RuntimeError("ordinary advisory failure"),
    }.get(fault)

    def classification(*args, **kwargs):
        if error is not None:
            raise error
        return SurvivorReport(
            verdicts=(),
            unclassified=(),
            load_failed=fault == "load",
            measurement_valid=fault != "measurement",
            note=fault,
        )

    monkeypatch.setattr(engine, "classify_survivors", classification)
    if isinstance(error, MonitoringUnavailable):
        with pytest.raises(type(error)) as caught:
            verify_rewrite(receipt, "rewrite_closure.py", "f", str(tmp_path))
        assert caught.value is error
        return
    result = verify_rewrite(receipt, "rewrite_closure.py", "f", str(tmp_path))
    assert result.verdict != "PRESERVED"
    assert result.note == ("classification: unavailable" if fault == "advisory" else fault)
