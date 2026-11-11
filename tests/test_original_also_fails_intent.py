"""Intent: a mutant whose every failing test fails the same way against the ORIGINAL has a NAMED reason on
every surface, in the sign of its own cause (Detective #127, consuming Wesker #55 / KNOWABILITY Def. 2.3).

The defect, measured on the integrated pair: Wesker's new unscored disposition ``original_also_fails`` read as
an unnamed engine refusal, and a kill ratio silently lost eight mutants. The fixture of
``test_typed_baseline_failing_intent`` has ``test_wrong_expectation: assert f(-5) == 99``, which fails on the
unmutated code, and an ``xfail`` test beside it. Under the old Wesker the audit read ``15 mutants, 15
value-killed, 100%``: eight of those "kills" were credited to a test that fails on the original, i.e. false.
Under the new one the same audit read ``total_mutants 7, value_killed 7`` with cut reason
``engine_refused_unspecified`` and ended ``INCOMPLETE: the engine refused to gate this measurement without
naming a reason``, decision ``repair_measurement / inspect_refusal``, where it used to (correctly) direct
``pytest test_wrong.py::test_wrong_expectation``. ``7/7 ... 100%`` stood as a complete ratio with nothing
beside it to say eight mutants were in neither side of it.

Two causes, two signs (COMMUNICATING_DETERMINISM §3), decided from the record's own facts and never guessed:
the named test FAILS on the unmutated code at baseline (the failing floor's cause, whose repair is a person's
call about the test or the code), or it PASSES there and the original fails it only in the state a
mutant's run left behind (repaired in the test). And ``Wesker.shared_arguments``, the arguments no
evaluation could be handed a fresh copy of, were computed and read by nobody.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import types

import pytest

from Detective.audit import SuiteAudit, unresolved_gate_standing
from Detective.cli import (
    _audit_code,
    _audit_measurement_block,
    _floor_caused,
    _format_audit,
    no_verdict_ratio_clause,
    original_also_fails_text,
    repair_measurement_route,
    shared_arguments_text,
)
from Detective.converge import certificate_standing
from Detective.validity import (
    CUT_REASONS,
    PER_MUTANT_REASONS,
    cut_reason_sentence,
    floor_cause_standing,
    measurement_cut_reasons,
    normalize_validity,
    original_also_fails_cause,
    original_also_fails_detail,
    original_also_fails_reasons,
    reasons_beyond_floor,
    unresolved_mutant_records,
    unscored_record_reason,
)

_CAUSE_REASONS = (
    "original_also_fails_failing_test",
    "original_also_fails_shared_state",
    "original_also_fails",
)


# ── the vocabulary: every surface that lists reasons knows the family ───────────────────────────


def test_the_family_is_in_the_vocabulary_and_is_a_per_mutant_reason():
    for reason in _CAUSE_REASONS:
        assert reason in CUT_REASONS
        assert reason in PER_MUTANT_REASONS, "a mutant with no verdict, not a run-level refusal"
        assert not cut_reason_sentence(reason).startswith("an unrecognised engine refusal")
    sentences = {cut_reason_sentence(reason) for reason in _CAUSE_REASONS}
    assert len(sentences) == 3, "three states, three sentences: none may share a sign"


def test_each_cause_names_its_own_repair_and_does_not_promise_isolation_helps():
    failing = cut_reason_sentence("original_also_fails_failing_test")
    leaked = cut_reason_sentence("original_also_fails_shared_state")
    assert "fails at baseline" in failing and "decide whether the test or the code is wrong" in failing
    assert "restore the state it shares" in leaked
    # The isolated worker is reused across mutants and recycled only after a bounded count, so it keeps the
    # state: the sentence must not send the reader to --isolated as a repair.
    assert "--isolated does not clear it" in leaked


@pytest.mark.parametrize(
    ("test", "outcome", "named", "cause"),
    [
        ("t::a", "failed", True, "failing_test"),
        ("t::a", "failed", False, "failing_test"),
        ("t::a", "xfailed", False, "failing_test"),
        ("t::a", "unrecorded", True, "failing_test"),
        ("t::a", "passed", False, "shared_state"),
        (
            "t::a",
            "passed",
            True,
            "shared_state",
        ),  # typed outcome outranks the engine's list (baseline_failure_disposition)
        ("t::a", "unrecorded", False, "unnamed"),  # never typed passed: not asserted to pass
        ("t::a", "error", False, "unnamed"),
        ("t::a", "skipped", False, "unnamed"),
        ("", "failed", True, "unnamed"),  # the record names no test
    ],
)
def test_the_cause_is_decided_from_the_recorded_baseline_of_the_named_test(test, outcome, named, cause):
    assert original_also_fails_cause(test, outcome, named) == cause


def test_reasons_are_one_per_cause_in_declaration_order_and_never_empty():
    assert original_also_fails_reasons([]) == ("original_also_fails",)
    assert original_also_fails_reasons(["shared_state", "failing_test"]) == (
        "original_also_fails_failing_test",
        "original_also_fails_shared_state",
    )
    assert original_also_fails_reasons(["something_new"]) == ("original_also_fails",)


# ── an unscored disposition Wesker named never falls into engine_refused_unspecified ────────────


def _result(**fields):
    base = {
        "is_gateable": False,
        "coverage_depth": "profiled",
        "collection_conflicts": (),
        "all_contained": True,
        "collection_errors": (),
        "execution_mode": "isolated",
        "shared_arguments": (),
        "budget_exhausted": False,
        "per_category": [types.SimpleNamespace(unscored_by={"original_also_fails": 8})],
    }
    base.update(fields)
    return types.SimpleNamespace(**base)


def _record(mid, test="", disposition="original_also_fails"):
    rec = {"mutant_id": mid, "disposition": disposition}
    if test:
        rec["test"] = test
    return rec


def test_a_result_that_carries_no_unscored_records_still_names_the_disposition_it_counted():
    validity = normalize_validity(_result())  # per_category counts 8, and there are no records at all
    assert validity.cut_reasons == ("original_also_fails",)
    assert "engine_refused_unspecified" not in validity.cut_reasons
    assert validity.original_also_fails == ()


def test_the_validity_reads_each_cause_off_the_records_and_the_typed_baseline():
    result = _result(
        unscored_records=[_record("A", "t::floor"), _record("B", "t::leaky"), _record("C")],
        failing_tests=["t::floor"],
        trace_evidence=[
            types.SimpleNamespace(test_id="t::floor", baseline_outcome="failed"),
            types.SimpleNamespace(test_id="t::leaky", baseline_outcome="passed"),
        ],
    )
    validity = normalize_validity(result)
    assert validity.cut_reasons == (
        "original_also_fails_failing_test",
        "original_also_fails_shared_state",
        "original_also_fails",
    )
    by_cause = {entry["cause"]: entry for entry in validity.original_also_fails}
    assert by_cause["failing_test"]["mutants"] == ["A"] and by_cause["failing_test"]["baseline"] == "failed"
    assert by_cause["shared_state"]["test"] == "t::leaky" and by_cause["shared_state"]["baseline"] == "passed"
    assert by_cause["unnamed"]["test"] == ""
    assert validity.schema_version == 9


def test_the_no_verdict_mutants_carry_the_new_disposition_by_id():
    records = [
        _record("A", "t::a"),
        _record("B", "t::a", "undetermined"),
        {"mutant_id": "C", "disposition": "cut"},
    ]
    assert unresolved_mutant_records(records) == (("A", "original_also_fails"), ("B", "undetermined"))
    assert original_also_fails_detail([], {}, []) == ()
    assert original_also_fails_detail([{"disposition": "undetermined"}, "junk", None], {}, []) == ()


def test_a_flag_refusal_names_the_records_own_cause_not_the_family():
    rec = _record("A", "t::a")
    assert unscored_record_reason(rec) == "original_also_fails"
    assert unscored_record_reason(rec, "shared_state") == "original_also_fails_shared_state"
    assert unscored_record_reason(rec, "failing_test") == "original_also_fails_failing_test"
    assert (
        unscored_record_reason(_record("A", disposition="never_heard_of_it")) == "engine_refused_unspecified"
    )


# ── precedence: the floor leads over what it caused; a measurement that could not run still outranks it ──


def test_the_floors_own_reason_is_set_aside_only_while_the_floor_is_failing():
    mixed = ["original_also_fails_failing_test", "mutant_not_installed"]
    assert reasons_beyond_floor(mixed, True) == ("mutant_not_installed",)
    assert reasons_beyond_floor(mixed, False) == tuple(mixed), "no failing test to lead the page: it stays"
    assert reasons_beyond_floor([], True) == ()
    # the state-leak cause is NOT the floor's: the test passes at baseline
    assert reasons_beyond_floor(["original_also_fails_shared_state"], True) == (
        "original_also_fails_shared_state",
    )


def test_floor_cause_standing_is_floor_caused_only_when_nothing_else_is():
    assert floor_cause_standing(["original_also_fails_failing_test"], True) == "floor_caused"
    assert floor_cause_standing(["original_also_fails_failing_test"], False) == "not_floor_caused"
    assert floor_cause_standing([], True) == "not_floor_caused"
    assert floor_cause_standing(["original_also_fails_failing_test", "budget_exhausted"], True) == (
        "not_floor_caused"
    )
    assert floor_cause_standing(["original_also_fails_shared_state"], True) == "not_floor_caused"


def test_certificate_standing_ranks_a_floor_caused_refusal_beneath_its_floor_only():
    kw = {"functionally_complete": False, "line_complete": False, "stale_target": False}
    base = (kw["functionally_complete"], kw["line_complete"], kw["stale_target"], False, False)
    assert certificate_standing(*base, False, floor_failing=True, floor_caused=True) == "floor_failing"
    # a measurement that could not run (floor_caused False) outranks the failing suite, as before
    assert certificate_standing(*base, False, floor_failing=True, floor_caused=False) == "ungateable"
    # floor_caused without a failing floor refuses nothing it did not already refuse
    assert certificate_standing(*base, False, floor_failing=False, floor_caused=True) == "ungateable"
    assert certificate_standing(*base, True, floor_failing=True) == "floor_failing"


def _audit(**fields):
    base = {
        "function": "m.py::f",
        "test_count": 1,
        "kill_pct": 100.0,
        "mutant_complete": False,
        "line_complete": False,
        "line_basis": "admissible",
        "redundant_tests": (),
        "failing_tests": (),
        "errored_tests": (),
        "killable_gaps": (),
        "missing_lines": (),
        "candidate_equivalent": 0,
        "unclassified": 0,
        "value_killed": 7,
        "total_mutants": 7,
        "minimal_test_count": 1,
    }
    base.update(fields)
    return SuiteAudit(**base)


def test_audit_leads_with_the_failing_floor_over_a_mutant_the_floor_left_without_a_verdict():
    audit = _audit(
        failing_tests=("test_wrong.py::test_wrong_expectation",),
        cut_reasons=("original_also_fails_failing_test",),
    )
    assert _audit_measurement_block(audit) == ""
    assert _audit_code(audit) == "fix_failing_test"


def test_audit_still_repairs_a_measurement_that_could_not_run_before_the_floor_and_names_both():
    audit = _audit(
        failing_tests=("test_wrong.py::test_wrong_expectation",),
        cut_reasons=("original_also_fails_failing_test", "mutant_not_installed"),
    )
    assert _audit_measurement_block(audit) == "repair_measurement"
    assert _audit_code(audit) == "repair_measurement"
    page = _format_audit(audit)
    assert cut_reason_sentence("mutant_not_installed") in page, "the unrelated reason is named"
    assert cut_reason_sentence("original_also_fails_failing_test") in page, "and so is the floor's"


def test_a_leaked_state_cause_is_a_measurement_repair_even_beside_a_failing_floor():
    audit = _audit(
        failing_tests=("test_wrong.py::test_wrong_expectation",),
        cut_reasons=("original_also_fails_shared_state",),
    )
    assert _audit_code(audit) == "repair_measurement"


def test_a_floor_caused_reason_with_no_failing_test_to_lead_is_a_measurement_repair_of_its_own():
    audit = _audit(cut_reasons=("original_also_fails_failing_test",))
    assert _audit_code(audit) == "repair_measurement"


def test_the_converge_helper_reads_the_same_reasons_the_standing_reads():
    floor = types.SimpleNamespace(
        floor_failing_tests=("t::w",),
        validity_cut_reasons=("original_also_fails_failing_test",),
        cut_reasons=(),
    )
    assert _floor_caused(floor) is True
    other = types.SimpleNamespace(
        floor_failing_tests=("t::w",),
        validity_cut_reasons=("original_also_fails_failing_test", "budget_exhausted"),
        cut_reasons=(),
    )
    assert _floor_caused(other) is False
    assert _floor_caused(types.SimpleNamespace(floor_failing_tests=(), cut_reasons=())) is False


def test_each_cause_has_its_own_route_and_a_measurement_that_could_not_run_still_leads():
    assert repair_measurement_route(("original_also_fails_failing_test",)) == "fix_original_failure"
    assert repair_measurement_route(("original_also_fails",)) == "fix_original_failure"
    assert repair_measurement_route(("original_also_fails_shared_state",)) == "restore_shared_state"
    assert (
        repair_measurement_route(("original_also_fails_shared_state", "mutant_not_installed"))
        == "mutant_phase"
    )
    assert repair_measurement_route(("original_also_fails_shared_state", "budget_exhausted")) == (
        "restore_shared_state"
    ), "a per-mutant cause is repaired before a deadline is raised"


# ── the strict gate: both causes are the reader's to fix ────────────────────────────────────────


def test_both_causes_fail_the_strict_gate_as_repairable():
    assert unresolved_gate_standing("original_also_fails") == "repairable"
    assert unresolved_gate_standing("write_outside_authority") == "repairable"
    assert unresolved_gate_standing("diverged") == "budget_floor"
    assert unresolved_gate_standing("undetermined") == "machine_bound"
    assert unresolved_gate_standing("never_heard_of_it") == "unknown"


# ── the page: the ratio does not stand alone; the because-row says which cause ──────────────────


def test_the_kill_ratio_line_carries_what_it_left_out():
    assert no_verdict_ratio_clause(0) == ""
    assert no_verdict_ratio_clause(-3) == ""
    assert no_verdict_ratio_clause(8) == " (+8 with no verdict, below)"


def test_the_because_row_tells_the_two_causes_apart_and_never_names_an_expected_failure():
    failing = original_also_fails_text("failing_test", "t::wrong", "failed", 3)
    xfail = original_also_fails_text("failing_test", "t::xf", "xfailed", 3)
    leaked = original_also_fails_text("shared_state", "t::leaky", "passed", 3)
    unnamed = original_also_fails_text("unnamed", "", "", 3)
    assert "t::wrong fails at baseline" in failing
    assert "t::xf" not in xfail and "marked expected-failure (xfail)" in xfail
    assert (
        "t::leaky passes on the unmutated code at baseline" in leaked
        and "--isolated does not clear it" in leaked
    )
    assert "names no test" in unnamed
    assert len({failing, xfail, leaked, unnamed}) == 4


@pytest.mark.parametrize(
    ("shared", "expected"),
    [
        ([], ""),
        (
            ["t.py::a[0] :: box (uncopyable)"],
            "1 argument(s) of 1 test(s) left shared (uncopyable): measured on the authored objects; "
            "a mutant that writes into them is guarded only by the original control",
        ),
        (
            [
                "t.py::a[0] :: x (uncopyable)",
                "t.py::a[0] :: y (identity_sensitive)",
                "t.py::b :: z (uncopyable)",
            ],
            "3 argument(s) of 2 test(s) left shared (uncopyable, identity_sensitive): measured on the "
            "authored objects; a mutant that writes into them is guarded only by the original control",
        ),
    ],
)
def test_the_shared_arguments_row_counts_arguments_and_tests_and_is_empty_when_none(shared, expected):
    assert shared_arguments_text(shared) == expected


def test_an_engine_that_does_not_report_shared_arguments_is_a_named_state_not_an_empty_list():
    old = normalize_validity(types.SimpleNamespace(budget_exhausted=False))
    assert "absent:shared_arguments" in old.capability_flags
    reported_none = normalize_validity(types.SimpleNamespace(budget_exhausted=False, shared_arguments=[]))
    assert "absent:shared_arguments" not in reported_none.capability_flags
    reported = normalize_validity(
        types.SimpleNamespace(budget_exhausted=False, shared_arguments=["t::a :: x (uncopyable)"])
    )
    assert reported.shared_arguments == ("t::a :: x (uncopyable)",)


def test_the_audit_page_prints_the_shared_row_only_when_something_was_shared():
    clean = _format_audit(_audit(failing_tests=("t::w",)))
    assert "shared args" not in clean
    shared = _format_audit(_audit(failing_tests=("t::w",), shared_arguments=("t::a :: x (uncopyable)",)))
    assert "shared args" in shared and "1 argument(s) of 1 test(s) left shared (uncopyable)" in shared


def test_the_measurement_cut_reasons_decision_names_the_disposition_beside_known_reasons():
    reasons = measurement_cut_reasons(
        reported_gateable=True,
        gateable=False,
        budget_exhausted=False,
        coverage_depth="profiled",
        containment="contained",
        identity_ambiguous=False,
        original_also_fails=True,
    )
    assert reasons == ("original_also_fails",)
    beside = measurement_cut_reasons(
        reported_gateable=True,
        gateable=False,
        budget_exhausted=False,
        coverage_depth="profiled",
        containment="contained",
        identity_ambiguous=False,
        mutant_wall_undetermined=True,
        original_also_fails_causes=("shared_state",),
    )
    assert beside == ("mutant_wall_undetermined", "original_also_fails_shared_state")


# ── end to end through the real CLI, in scratch projects ────────────────────────────────────────


def _detective(cwd, home, *argv):
    env = dict(os.environ, HOME=str(home))
    return subprocess.run(
        [sys.executable, "-m", "Detective", *argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
        env=env,
    )


def _project(root, files):
    root.mkdir()
    for name, text in files.items():
        (root / name).write_text(text)


_FLOOR_FILES = {
    "m.py": "def f(x):\n    if x > 0:\n        return x + 1\n    return x - 1\n",
    "conftest.py": (
        "import pytest\n\nfrom m import f\n\n\n@pytest.fixture\ndef broken_setup():\n"
        "    f(1)\n    assert False, 'fixture setup is broken'\n"
    ),
    "test_m.py": (
        "import pytest\n\nfrom m import f\n\n\n"
        "def test_errors_in_setup(broken_setup):\n    assert f(2) == 3\n\n\n"
        "@pytest.mark.xfail(reason='known', strict=False)\n"
        "def test_expected_failure():\n    assert f(-2) == 99\n\n\n"
        "@pytest.mark.skip(reason='not today')\ndef test_skipped():\n    assert f(0) == -1\n\n\n"
        "def test_passes():\n    assert f(5) == 6\n"
    ),
    "test_wrong.py": "from m import f\n\n\ndef test_wrong_expectation():\n    assert f(-5) == 99\n",
}

# A ratchet: every call lowers the limit a mutant of the constant 3 can reach, and the original never
# raises it back. The test passes at baseline (the limit is already 3) and fails the ORIGINAL once a mutant
# ran, which is state the arguments' copies cannot reach.
_LEAK_FILES = {
    "m.py": (
        "_limit = [3]\n\n\ndef f(x):\n    _limit[0] = min(_limit[0], 3)\n"
        "    return x if x <= _limit[0] else _limit[0]\n"
    ),
    "test_m.py": (
        "from m import f\n\n\ndef test_at_the_limit():\n    assert f(3) == 3\n\n\n"
        "def test_below():\n    assert f(1) == 1\n"
    ),
}

_IDENTITY_FILES = {
    "m.py": "CACHE = [1, 2]\n\n\ndef lookup(k):\n    if k > 0:\n        return CACHE\n    return []\n",
    "test_m.py": (
        "import pytest\nimport m\nfrom m import lookup\n\n\n"
        '@pytest.mark.parametrize("x", [m.CACHE])\ndef test_identity(x):\n    assert lookup(1) is x\n\n\n'
        "def test_empty():\n    assert lookup(0) == []\n"
    ),
}


@pytest.fixture(scope="module")
def home(tmp_path_factory):
    return tmp_path_factory.mktemp("home")


def _migrated(tmp_path_factory, home, name, files):
    root = tmp_path_factory.mktemp(name) / "proj"
    _project(root, files)
    migrate = _detective(root, home, "regime", "--migrate", "--project-root", str(root))
    assert migrate.returncode == 0, migrate.stdout + migrate.stderr
    return root


@pytest.fixture(scope="module")
def floor_project(tmp_path_factory, home):
    return _migrated(tmp_path_factory, home, "floor", _FLOOR_FILES)


@pytest.fixture(scope="module")
def leak_project(tmp_path_factory, home):
    return _migrated(tmp_path_factory, home, "leak", _LEAK_FILES)


@pytest.fixture(scope="module")
def identity_project(tmp_path_factory, home):
    return _migrated(tmp_path_factory, home, "identity", _IDENTITY_FILES)


@pytest.fixture(scope="module")
def floor_audit(floor_project, home):
    return _detective(floor_project, home, "audit", "m.py::f")


@pytest.fixture(scope="module")
def leak_audit(leak_project, home):
    return _detective(leak_project, home, "audit", "m.py::f")


def test_cause_one_the_page_leads_with_the_failing_test_and_names_the_eight_mutants(floor_audit):
    out = floor_audit.stdout
    assert "engine refused to gate" not in out, out
    assert "pytest test_wrong.py::test_wrong_expectation" in out, out
    assert "⚠ no verdict         8 —" in out and out.count("(original_also_fails)") >= 5, out
    assert "marked expected-failure (xfail)" in out, "the because-row says why they have no verdict"
    assert "7/7 value-pinned (+8 with no verdict, below)" in out, "the ratio does not stand alone"
    assert out.index("⚠ no verdict") < out.index("DO THIS:"), out
    assert "test_expected_failure" not in out, "an expected failure is described, never named as failing"


def test_cause_one_json_carries_the_reason_the_standing_and_the_decision(floor_project, home):
    run = _detective(floor_project, home, "audit", "m.py::f", "--json")
    payload = json.loads(run.stdout)
    assert payload["cut_reasons"] == ["original_also_fails_failing_test"]
    assert payload["decision"]["code"] == "fix_failing_test"
    assert len(payload["unresolved_mutants"]) == 8
    assert {d for _, d in payload["unresolved_mutants"]} == {"original_also_fails"}
    (entry,) = payload["original_also_fails"]
    assert entry["cause"] == "failing_test" and entry["baseline"] == "xfailed" and len(entry["mutants"]) == 8
    assert "shared_arguments" in payload and payload["shared_arguments"] == []


def test_cause_two_the_page_is_the_tests_to_repair_and_is_not_an_unnamed_refusal(leak_audit):
    out = leak_audit.stdout
    assert "engine refused to gate" not in out, out
    assert "⚠ no verdict" in out and "(original_also_fails)" in out, out
    assert "test_m.py::test_at_the_limit passes on the unmutated code at baseline" in out, out
    assert "Restore the state the test shares; --isolated does not clear it" in out, out
    assert "INCOMPLETE:" in out and "restore the state it shares" in out, out
    assert "pytest test_m.py" not in out, (
        "the test passes at baseline: there is nothing to hand back to pytest"
    )


def test_cause_two_json_names_the_route_and_the_cause(leak_project, home):
    payload = json.loads(_detective(leak_project, home, "audit", "m.py::f", "--json").stdout)
    assert payload["cut_reasons"] == ["original_also_fails_shared_state"]
    assert payload["decision"]["code"] == "repair_measurement"
    assert payload["decision"]["route"] == "restore_shared_state"
    (entry,) = payload["original_also_fails"]
    assert entry["cause"] == "shared_state" and entry["baseline"] == "passed"


def test_isolation_does_not_clear_the_state_so_the_page_does_not_promise_it(leak_project, home):
    """The claim the sentence makes, checked: the same mutants stay without a verdict under --isolated."""
    run = _detective(leak_project, home, "converge", "m.py::f", "--isolated")
    assert "(original_also_fails)" in run.stdout, run.stdout + run.stderr
    assert "· because" in run.stdout and "passes on the unmutated code at baseline" in run.stdout
    assert "engine refused to gate" not in run.stdout


def test_converge_names_the_reason_and_the_repair_in_the_page_and_the_final_line(leak_project, home):
    run = _detective(leak_project, home, "converge", "m.py::f")
    out = run.stdout
    assert run.returncode == 3, out + run.stderr
    assert "⚠ no verdict" in out and "· because" in out, out
    assert "STOP:" in out and "restore the state it shares" in out, out
    assert "restore the state the test shares, then re-measure." in out, out
    assert out.count("· because") == 1, "the cause is said once, under the row that has no verdict"
    assert "engine refused to gate" not in out


def test_the_strict_gate_fails_both_causes_and_the_plain_gate_stays_a_claim_about_the_code(
    floor_project, leak_project, home
):
    strict = _detective(leak_project, home, "audit", "m.py::f", "--check-strict", "--json")
    gate = json.loads(strict.stdout)["gate"]
    assert strict.returncode == 2 and gate["exit"] == 2, strict.stdout
    assert gate["measurement_incomplete"] is True and gate["spec_gap"] is False
    assert [u[2] for u in gate["unmeasured"]["unresolved_mutants"]] == ["repairable"] * 4
    plain = _detective(leak_project, home, "audit", "m.py::f", "--check")
    assert plain.returncode == 0, "a measurement limit is never a plain-ratchet failure: " + plain.stderr
    # cause one: the failing test is a spec gap, which outranks the measurement limit (1, not 2)
    floor_strict = _detective(floor_project, home, "audit", "m.py::f", "--check-strict")
    assert floor_strict.returncode == 1, floor_strict.stdout + floor_strict.stderr


def test_flag_refuses_a_mutant_with_no_verdict_in_the_words_of_its_cause(leak_project, home):
    listing = json.loads(_detective(leak_project, home, "audit", "m.py::f", "--json").stdout)
    mutant = listing["unresolved_mutants"][0][0]
    refused = _detective(leak_project, home, "flag", "m.py::f", mutant, "--note", "x")
    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert "reached no verdict (original_also_fails)" in refused.stderr
    assert cut_reason_sentence("original_also_fails_shared_state") in refused.stderr
    as_json = json.loads(
        _detective(leak_project, home, "flag", "m.py::f", mutant, "--note", "x", "--json").stdout
    )
    assert as_json["verdict"] == "REFUSED" and as_json["reason"] == "unscored_mutant"
    assert as_json["disposition"] == "original_also_fails"
    assert "restore the state it shares" in as_json["detail"]


def test_shared_arguments_are_on_the_page_the_json_and_the_full_report_and_nowhere_when_empty(
    identity_project, leak_project, home
):
    audit = _detective(identity_project, home, "audit", "m.py::lookup")
    assert "· shared args" in audit.stdout and "(identity_sensitive)" in audit.stdout, audit.stdout
    assert "guarded only by the original control" in audit.stdout
    payload = json.loads(_detective(identity_project, home, "audit", "m.py::lookup", "--json").stdout)
    assert payload["shared_arguments"] == ["test_m.py::test_identity[x0] :: x (identity_sensitive)"]

    converge = _detective(identity_project, home, "converge", "m.py::lookup")
    assert "· shared args" in converge.stdout, converge.stdout
    report = (identity_project / ".detective" / "reports" / "converge_lookup.txt").read_text()
    assert "test_m.py::test_identity[x0] :: x (identity_sensitive)" in report
    converge_json = json.loads(
        _detective(identity_project, home, "converge", "m.py::lookup", "--json").stdout
    )
    assert converge_json["shared_arguments"] == payload["shared_arguments"]

    # nothing shared: nothing printed
    clean = _detective(leak_project, home, "audit", "m.py::f")
    assert "shared args" not in clean.stdout
