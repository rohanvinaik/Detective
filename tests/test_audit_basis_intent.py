"""audit attaches a FunctionBasis with the REAL equivalent count (X4 tail).

TEST_BASIS §16 X4. profile() attaches a basis with candidate_equivalent=0 (it has no SurvivorReport),
so an all-equivalent survivor set reads `gap` there. audit runs classify_survivors, so it KNOWS the
true undischargeable-equivalent count and attaches a basis whose `action` is accurate — `complete`
when every remaining survivor is candidate-equivalent (no distinguishing input), not a false `gap`.
A crash-only survivor is NOT counted equivalent: a crash input distinguishes it, so it stays a
killable open obligation.
"""

from __future__ import annotations

from types import SimpleNamespace

from _support import make_pr

from Detective import audit as audit_mod
from Detective.audit import audit_suite


def _verdict(mutant_id, *, crash_only):
    return SimpleNamespace(mutant_id=mutant_id, crash_only=crash_only, killable=False)


def _report(equivalent):
    return SimpleNamespace(
        inputs_expressible=True,
        killable=(),
        manual_equivalent=(),
        equivalent=tuple(equivalent),
        unclassified=(),
    )


def test_audit_basis_reads_complete_when_every_survivor_is_candidate_equivalent(monkeypatch, tmp_path):
    # Two survivors, both candidate-equivalent (no distinguishing input, not crash-only).
    pr = make_pr(
        survivor_records=[{"mutant_id": "m1"}, {"mutant_id": "m2"}],
        mutants=2,
    )
    monkeypatch.setattr(audit_mod, "profile", lambda *a, **k: pr)
    monkeypatch.setattr(
        audit_mod,
        "classify_survivors",
        lambda *a, **k: _report([_verdict("m1", crash_only=False), _verdict("m2", crash_only=False)]),
    )
    a = audit_suite("mod.py", "f", str(tmp_path))
    assert a.function_basis is not None
    assert a.candidate_equivalent == 2
    # No OPEN obligation: all survivors are undischargeable equivalents, all lines covered → complete.
    # A profile-time basis (equivalent=0) would read `gap`; the audit basis uses the real count.
    assert a.function_basis.action == "complete"


def test_a_crash_only_survivor_keeps_the_basis_a_gap(monkeypatch, tmp_path):
    # One true candidate-equivalent + one crash-only. The crash-only is KILLABLE (a crash input
    # distinguishes it), so it is subtracted from the equivalent count and remains an open obligation.
    pr = make_pr(
        survivor_records=[{"mutant_id": "m1"}, {"mutant_id": "m2"}],
        mutants=2,
    )
    monkeypatch.setattr(audit_mod, "profile", lambda *a, **k: pr)
    monkeypatch.setattr(
        audit_mod,
        "classify_survivors",
        lambda *a, **k: _report([_verdict("m1", crash_only=False), _verdict("m2", crash_only=True)]),
    )
    a = audit_suite("mod.py", "f", str(tmp_path))
    # candidate_equivalent (union) is 2, but one is crash-only → the basis sees 1 undischargeable, so
    # one survivor stays killable → gap.
    assert a.crash_only_equivalent == 1
    assert a.function_basis.action == "gap"
