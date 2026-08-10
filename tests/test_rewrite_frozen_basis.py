"""#37 — the rewrite proof basis is FROZEN; a moved basis cannot ground PRESERVED.

`verify_rewrite` replays `receipt.proof_suite` and reruns survivor classification on the CURRENT
suite. The receipt stored only file PATHS, so a test added or EDITED after the receipt — one that
suppresses a newly introduced dimension — was replayed as if it were the original basis, helping
produce a false `PRESERVED`. Freezing each proof file's content digest closes that: a changed basis
is `BASIS_MOVED`, and a pre-#37 (unfrozen) receipt cannot reach PRESERVED at all.

INTENT tests: the defect is a false preservation certificate, so a characterization cannot catch
it. The pure `basis_freshness` asserts the three states; an end-to-end `verify_rewrite` asserts a
proof file edited after the receipt is refused before any replay.
"""

from __future__ import annotations

import ast
import hashlib

from Detective import pins
from Detective.rewrite import RewriteReceipt, basis_freshness, verify_rewrite

# ── the pure decision ──────────────────────────────────────────────────────────


def test_an_unfrozen_receipt_is_named_not_trusted():
    """No digests (pre-#37) is a MISSING capability, distinct from a detected move."""
    assert basis_freshness({}, {"a.py": "x"}) == "unfrozen"


def test_a_changed_or_missing_proof_file_is_moved():
    assert basis_freshness({"a.py": "x"}, {"a.py": "y"}) == "moved"
    assert basis_freshness({"a.py": "x"}, {}) == "moved"  # gone → matches no digest


def test_an_intact_basis_is_fresh():
    assert basis_freshness({"a.py": "x"}, {"a.py": "x"}) == "fresh"


# ── round-trip: digests survive load ───────────────────────────────────────────


def test_proof_digests_round_trip_through_json():
    original = "def f(x):\n    return x + 1\n"
    node = next(n for n in ast.walk(ast.parse(original)) if isinstance(n, ast.FunctionDef))
    rec = RewriteReceipt(
        function="m.py::f",
        original_source=original,
        source_digest=hashlib.sha256(original.encode()).hexdigest(),
        function_digest=pins.function_digest(node),
        policy_id="p",
        universe_size=1,
        proof_suite=("test_m.py",),
        proof_status="passed",
        functionally_complete=True,
        proof_digests=(("test_m.py", "abc123"),),
    )
    back = RewriteReceipt.from_json(rec.to_json())
    assert back.proof_digests == (("test_m.py", "abc123"),)


# ── end-to-end: a proof file edited after the receipt is refused ────────────────


def test_a_proof_file_edited_after_the_receipt_is_refused(tmp_path):
    """The reproduced defect. The receipt freezes the proof suite's digest; editing that file after
    the receipt makes the basis `moved`, so verification returns BASIS_MOVED before any replay —
    it can never reach a PRESERVED verdict against a suite that changed under it."""
    root = str(tmp_path)
    original = "def f(x):\n    return x + 1\n"
    rewritten = "def f(x):\n    return x + 2\n"  # the CURRENT (rewritten) source
    (tmp_path / "m37.py").write_text(rewritten)

    proof = tmp_path / "test_m37.py"
    proof.write_text("def test_f():\n    assert True\n")
    frozen_digest = hashlib.sha256(proof.read_bytes()).hexdigest()
    # the edit that would suppress a dimension — the basis the receipt froze is gone
    proof.write_text("def test_f():\n    assert True  # edited after the receipt\n")

    onode = next(n for n in ast.walk(ast.parse(original)) if isinstance(n, ast.FunctionDef))
    receipt = RewriteReceipt(
        function="m37.py::f",
        original_source=original,
        source_digest=hashlib.sha256(original.encode()).hexdigest(),
        function_digest=pins.function_digest(onode),
        policy_id="p",
        universe_size=1,
        proof_suite=("test_m37.py",),
        proof_status="passed",
        functionally_complete=True,
        proof_digests=(("test_m37.py", frozen_digest),),
    )
    v = verify_rewrite(receipt, "m37.py", "f", root)
    assert v.verdict == "BASIS_MOVED", (
        f"a moved proof basis was not refused (got {v.verdict}) — the #37 false PRESERVED"
    )
