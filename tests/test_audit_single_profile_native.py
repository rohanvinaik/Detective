"""Intent tests for #65: the audit classifies survivors from the SAME profile it counts.

THE BUG. ``audit_suite`` profiled once for its ``total``/``value_killed`` counts and
``classify_survivors`` re-profiled internally. Under a cold-collection race the two discovered
different test sets, disagreed by one mutant, and ``audit_partition_sums`` failed — crashing the
tool with a raw ``AssertionError`` traceback. Reproduced live on insitro/redun (traced 279 unscoped
vs reported 76 scoped for the same function).

THE FIX. ``classify_survivors`` accepts the caller's ``profile_result`` and reuses it (when it is
for this target and no out-of-tree dirs are in play), binding the counts and the survivor buckets to
ONE measurement — so the partition cannot diverge. The residual assertion becomes a typed
``AuditAccountingError`` rendered cleanly, never a raw traceback.
"""

from __future__ import annotations

import pytest

from Detective import audit as audit_mod
from Detective import engine
from Detective.audit import AuditAccountingError, audit_suite
from Detective.engine import classify_survivors, profile

_SRC = "def f(x):\n    if x > 0:\n        return 1\n    return 0\n"


def test_classify_survivors_reuses_the_passed_profile_and_never_reprofiles(tmp_path, monkeypatch):
    (tmp_path / "m.py").write_text(_SRC)
    root = str(tmp_path)
    r = profile("m.py", "f", root)  # the ONE headline profile audit_suite would compute

    def boom(*a, **k):
        raise RuntimeError("classify_survivors re-profiled instead of reusing the passed result (#65)")

    monkeypatch.setattr(engine, "profile", boom)
    # With the passed result for this exact target, no second profile call may happen.
    rep = classify_survivors("m.py", "f", root, profile_result=r)
    assert rep is not None  # a real classification came back from the single reused measurement


def test_a_profile_result_for_a_different_target_is_not_reused(tmp_path, monkeypatch):
    (tmp_path / "m.py").write_text("def f(x):\n    return x + 1\n\n\ndef g(x):\n    return x - 1\n")
    root = str(tmp_path)
    r_g = profile("m.py", "g", root)  # a result for g, not f
    real = engine.profile
    seen = {"reprofiled": False}

    def counting(*a, **k):
        seen["reprofiled"] = True
        return real(*a, **k)

    monkeypatch.setattr(engine, "profile", counting)
    classify_survivors("m.py", "f", root, profile_result=r_g)  # func_key mismatch -> must re-profile f
    assert seen["reprofiled"] is True


def test_a_partition_mismatch_is_a_typed_error_not_a_bare_assertion(tmp_path, monkeypatch):
    (tmp_path / "m.py").write_text(_SRC)
    # Force the defensive branch: the reuse makes divergence impossible, so drive the mismatch
    # directly and assert it surfaces as the TYPED AuditAccountingError (which the CLI renders
    # cleanly), never a raw AssertionError.
    monkeypatch.setattr(audit_mod, "audit_partition_sums", lambda *a: False)
    with pytest.raises(AuditAccountingError):
        audit_suite("m.py", "f", str(tmp_path))
