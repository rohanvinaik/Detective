"""Integration tests for Detective.rewrite's receipt/target binding (issue #37, reopened).

The pure verdict logic (``rewrite_verdict``) and the pure refusal gate (``receipt_refusal``) are
mutation-driven in their ``*_synth.py`` suites. What those cannot exercise is the IMPURE wiring that
was the actual soundness hole: ``verify_rewrite`` never bound the receipt to the requested target, so
a receipt for ``a.py::a`` would happily "verify" ``b.py::b`` and report a preservation verdict for a
function nobody examined. These tests pin that binding end-to-end on a real filesystem, plus the
``from_json`` load-boundary integrity checks (schema + source digest) that a hand-edited receipt used
to slip past.
"""

from __future__ import annotations

import hashlib
import json
import os

import pytest

from Detective.rewrite import RewriteReceipt, receipt_refusal, verify_rewrite

_A_SRC = "def a(x):\n    return x\n"


def _receipt_for_a() -> RewriteReceipt:
    """A perfectly VALID, complete, green-verified receipt — but for ``a.py::a`` only."""
    return RewriteReceipt(
        function="a.py::a",
        original_source=_A_SRC,
        source_digest=hashlib.sha256(_A_SRC.encode("utf-8")).hexdigest(),
        function_digest="deadbeef",
        policy_id=None,
        universe_size=1,
        proof_suite=(),
        proof_status="passed",
        functionally_complete=True,
    )


def _write_ab(root: str) -> None:
    with open(os.path.join(root, "a.py"), "w", encoding="utf-8") as fh:
        fh.write(_A_SRC)
    with open(os.path.join(root, "b.py"), "w", encoding="utf-8") as fh:
        fh.write("def b(x):\n    return x * 2\n")


def test_verify_rewrite_refuses_receipt_for_a_different_function(tmp_path):
    """The reopened-#37 repro: a receipt for a.py::a must NOT certify b.py::b as PRESERVED."""
    _write_ab(str(tmp_path))
    res = verify_rewrite(_receipt_for_a(), "b.py", "b", str(tmp_path))
    assert res.verdict == "INVALID_RECEIPT"
    # The report names the REQUESTED target, never the receipt's own identity — so it can never
    # mislabel which function was checked (the old bug reported "a.py::a").
    assert res.function == "b.py::b"
    assert "a.py::a" in res.note and "b.py::b" in res.note


def test_verify_rewrite_refuses_a_corrupt_receipt(tmp_path):
    """A receipt whose recorded source no longer hashes to its digest is not trustworthy: the old
    implementation is RUN from ``original_source``, so a tampered source must be refused, not run."""
    _write_ab(str(tmp_path))
    rec = _receipt_for_a()
    tampered = RewriteReceipt(**{**rec.__dict__, "original_source": _A_SRC + "  # edited\n"})
    res = verify_rewrite(tampered, "a.py", "a", str(tmp_path))
    assert res.verdict == "INVALID_RECEIPT"
    assert "digest" in res.note


def test_receipt_refusal_passes_only_when_schema_digest_and_identity_all_hold():
    rec = _receipt_for_a()
    key = rec.function
    assert receipt_refusal(rec.schema, rec.original_source, rec.source_digest, key, key) is None
    # schema
    assert receipt_refusal("other/1", rec.original_source, rec.source_digest, key, key) is not None
    # digest
    assert receipt_refusal(rec.schema, rec.original_source, "0" * 64, key, key) is not None
    # identity
    assert receipt_refusal(rec.schema, rec.original_source, rec.source_digest, key, "b.py::b") is not None


def test_from_json_rejects_tampered_and_unknown_schema_but_round_trips_clean():
    rec = _receipt_for_a()
    good = rec.to_json()
    assert RewriteReceipt.from_json(good).function == "a.py::a"  # clean round-trip

    tampered = json.loads(good)
    tampered["original_source"] = _A_SRC + "  # edited\n"  # digest now stale
    with pytest.raises(ValueError, match="digest"):
        RewriteReceipt.from_json(json.dumps(tampered))

    foreign = json.loads(good)
    foreign["schema"] = "some-other-tool/9"
    with pytest.raises(ValueError, match="schema"):
        RewriteReceipt.from_json(json.dumps(foreign))

    missing = json.loads(good)
    missing.pop("schema", None)  # no schema field at all
    with pytest.raises(ValueError, match="schema"):
        RewriteReceipt.from_json(json.dumps(missing))
