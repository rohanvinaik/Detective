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
    candidates = {"test_a", "legacy:test_b.py::test_b"}
    assert audit._removal_needs(result, candidates, str(tmp_path)) == candidates


@pytest.mark.parametrize("fault", ["load", "measurement"])
def test_a_refused_empty_classification_cannot_preserve_a_rewrite(monkeypatch, tmp_path, fault):
    import importlib

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
    monkeypatch.setattr(
        engine,
        "classify_survivors",
        lambda *a, **k: SurvivorReport(
            verdicts=(),
            unclassified=(),
            load_failed=fault == "load",
            measurement_valid=fault != "measurement",
            note=fault,
        ),
    )
    result = verify_rewrite(receipt, "rewrite_closure.py", "f", str(tmp_path))
    assert result.verdict != "PRESERVED"
    assert result.note == fault
