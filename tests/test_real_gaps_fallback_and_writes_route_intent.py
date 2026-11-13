"""Two places `4165577` (#101) left the audit page saying what its own measurement does not support.

THE DEFECTS (warrant audit, entry 2, 2026-11-13):

1. **The `✗ real gaps` row on the classification fallback.** When `classify_survivors` raises, audit keeps
   every value-survivor record as a gap, crash-kill records included, and `killable_crash_detected` stayed at
   its default 0 (it was set only inside the branch that raised). The row then said "no test kills" of a
   mutant whose own record says a test crashed under it: "the classification did not run" rendered exactly
   like "measured 0 crash-detected" (COMMUNICATING_DETERMINISM §9, invariant 5). The count now comes from
   each record's own `killed_by`, read through the one spelling `classify_survivors` uses
   (`SUITE_DETECTION_KILLS`).

2. **The closing block's `· Writes` row predicted a converge that does not run.** It asked
   `environment_route` with audit's KILLABLE count, while converge asks it with `_converge_blocked` (any
   killable, unclassified or fenced survivor open). For a function that reads external state, with an
   uncovered line, no killable gap and an unclassified survivor open, the row said converge "names the
   fixture a test must build and hands back", and converge's own ladder read `close_the_gap` and asked for
   inputs. Both now read one fact, `open_residual`.

Not closed here: `has_line_gap` still differs (audit drops lines whose reach was not observed, converge counts
every missing line); no case inside `close_the_gap` where that changes the route has been shown.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from _support import with_full_relation

from Detective import audit as audit_mod
from Detective.audit import SuiteAudit, audit_suite
from Detective.cli import (
    _audit_action,
    _converge_blocked,
    converge_next_action,
    open_residual,
    real_gaps_text,
)

# ── 1. the fallback's crash count ─────────────────────────────────────────────────────────────────────────

_SURVIVOR = {"mutant_id": "m_survives", "category": "VALUE"}  # a true survivor carries no `killed_by`
_CRASHED = {"mutant_id": "m_crashes", "category": "VALUE", "killed_by": "crash"}  # a reshaped kill record


def _profile(records):
    return with_full_relation(
        SimpleNamespace(
            function_key="mod.py::f",
            kill_matrix={},
            executable_lines=[1],
            line_coverage={"t": [1]},
            admissible_line_coverage={"t": [1]},
            total_mutants=len(records),
            total_killed=sum(1 for r in records if r.get("killed_by")),
            value_killed=0,
            value_survived=len(records),
            total_equivalent=0,
            value_survivor_records=list(records),
            killed_records=[r for r in records if r.get("killed_by")],
            per_category=[],
            universe_size=0,
            failing_tests=[],
            trace_truncated=[],
            served_from_cache=False,
        )
    )


def _fallback_audit(monkeypatch, tmp_path, records):
    def classification_fails(*_a, **_k):
        raise RuntimeError("the witness search could not run")

    monkeypatch.setattr(audit_mod, "profile", lambda *a, **k: _profile(records))
    monkeypatch.setattr(audit_mod, "classify_survivors", classification_fails)
    return audit_suite("mod.py", "f", str(tmp_path))


def test_the_fallback_counts_the_crash_each_record_names(monkeypatch, tmp_path):
    a = _fallback_audit(monkeypatch, tmp_path, [_SURVIVOR, _CRASHED])
    assert len(a.killable_gaps) == 2
    assert a.killable_crash_detected == 1, (
        "the crash record says a test detects it; 0 is not what was measured"
    )
    row = real_gaps_text(len(a.killable_gaps), a.killable_crash_detected)
    assert "1 no test kills; 1 a test kills only by a crash" in row, row


def test_the_fallback_never_calls_a_crash_killed_record_undetected(monkeypatch, tmp_path):
    a = _fallback_audit(monkeypatch, tmp_path, [_CRASHED])
    assert "no test kills" not in real_gaps_text(len(a.killable_gaps), a.killable_crash_detected)


def test_the_fallback_without_a_crash_record_still_says_no_test_kills(monkeypatch, tmp_path):
    a = _fallback_audit(monkeypatch, tmp_path, [_SURVIVOR])
    assert a.killable_crash_detected == 0
    assert (
        real_gaps_text(len(a.killable_gaps), a.killable_crash_detected)
        == "1 killable mutant(s) no test kills"
    )


# ── 2. the `· Writes` row asks converge's question with converge's fact ───────────────────────────────────


@pytest.mark.parametrize(
    ("complete", "divergent", "survivors_open", "open_"),
    [
        (True, False, False, False),
        (True, False, True, False),  # without divergence the flag decides
        (False, False, False, True),  # e.g. only an unclassified survivor: the flag is false, it is open
        (False, False, True, True),
        (False, True, False, False),  # divergence alone has its own hand-back: not open
        (False, True, True, True),
        (True, True, False, False),
        (True, True, True, True),  # with divergence the survivors decide
    ],
)
def test_open_residual_is_converges_reading(complete, divergent, survivors_open, open_):
    assert open_residual(complete, divergent, survivors_open) is open_


_READS = ("reads the filesystem via os.path.exists()",)  # `environment_gate_kind` reads this as "fixture"


def _audit(**fields) -> SuiteAudit:
    base = {
        "function": "mod.py::f",
        "test_count": 1,
        "kill_pct": 50.0,
        "mutant_complete": True,
        "line_complete": False,
        "line_basis": "admissible",
        "redundant_tests": (),
        "failing_tests": (),
        "errored_tests": (),
        "killable_gaps": (),
        "missing_lines": (3,),
        "candidate_equivalent": 0,
        "unclassified": 0,
        "value_killed": 1,
        "total_mutants": 2,
        "minimal_test_count": 1,
        "boundary_probe": "run",
        "takes_arguments": True,
        "environment_gated": _READS,
    }
    base.update(fields)
    return SuiteAudit(**base)


def _writes(a: SuiteAudit) -> str:
    page = _audit_action(a)
    assert page[0].startswith("DO THIS:") and "converge" in page[0], page
    return next(line for line in page if "· Writes" in line)


def _converge_reads(a: SuiteAudit) -> str:
    """The route converge's own ladder takes on the same measurement, through converge's own accessor."""
    result = SimpleNamespace(functionally_complete=a.mutant_complete)
    rep = SimpleNamespace(
        killable=("k",) * len(a.killable_gaps),
        unclassified=("u",) * a.unclassified,
        authored_fence=("f",) * a.authored_fence,
        step_budget_divergent=("d",) * a.step_budget_divergent,
    )
    return converge_next_action("measured", "", _converge_blocked(result, rep), True, env_gate="fixture")


def test_an_unclassified_survivor_keeps_converge_on_the_gap_and_the_row_says_so():
    a = _audit(mutant_complete=False, unclassified=1, total_mutants=2, value_killed=1)
    assert _converge_reads(a) == "close_the_gap"
    writes = _writes(a)
    assert "hands back" not in writes, writes
    assert "the missing tests, and wires them into pytest" in writes, writes


def test_nothing_open_but_the_line_hands_back_to_the_fixture_as_converge_does():
    a = _audit()
    assert _converge_reads(a) == "environment_fixture"
    assert "hands back" in _writes(a)


def test_divergence_alone_is_not_read_as_an_open_survivor():
    # The flag is false because of divergence, which has its own hand-back; converge's question is whether a
    # killable, unclassified or fenced survivor is open, and none is.
    a = _audit(mutant_complete=False, step_budget_divergent=1)
    assert _converge_reads(a) == "environment_fixture"
    assert "hands back" in _writes(a)
