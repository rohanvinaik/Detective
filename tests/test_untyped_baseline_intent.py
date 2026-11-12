"""A test the route could not TYPE is neither passing nor failing, and the audit says so (Wesker#17).

The defect: on the legacy direct-call route (a library `audit_suite(...)` outside a live pytest session)
Wesker now types a marked or non-assertion-raising callable as ``untyped`` instead of guessing ``failed`` or
``error``. `audit.baseline_failure_disposition` mapped any outcome it did not know to ``not_failing``, so an
untypable test read as passing: not named on the page, not counted by the strict gate, and the DONE endings
stood over a suite that was not measured.

These tests pin the disposition, the page row, the ladder code and the strict gate, on a suite where one test
is untyped and on one where every test is.
"""

import subprocess
import sys
import types

import pytest

from Detective.audit import (
    SuiteAudit,
    audit_measurement_incomplete,
    baseline_failure_disposition,
    function_errored_tests,
    function_failing_tests,
    function_untyped_tests,
)
from Detective.cli import (
    _audit_code,
    _audit_decision,
    _format_audit,
    _unmeasured_clause,
    audit_next_action,
    audit_step,
)


@pytest.mark.parametrize(
    ("named", "outcome", "disposition"),
    [
        (False, "untyped", "untyped"),
        (True, "untyped", "untyped"),  # even a name from an engine does not accuse it: the route cannot say
        (True, "failed", "failing"),
        (False, "error", "errored"),
        (True, "skipped", "not_failing"),
        (False, "passed", "not_failing"),
        (False, "unrecorded", "not_failing"),
    ],
)
def test_the_untyped_outcome_has_its_own_disposition(named, outcome, disposition):
    assert baseline_failure_disposition(named, outcome) == disposition


def test_an_untyped_test_is_this_functions_business_only_when_it_ran_its_lines_or_killed_its_mutants():
    kills = {"M1": ["t::a"]}
    lines = {"t::a": [2], "t::b": [], "t::c": [3]}
    typed = {"t::a": "untyped", "t::b": "untyped", "t::c": "passed", "t::d": "untyped"}
    assert function_untyped_tests(kills, lines, typed) == ("t::a",)
    assert function_untyped_tests(kills, lines, None) == ()
    assert function_untyped_tests({}, {}, typed) == ()
    # it is neither failing nor errored
    assert function_failing_tests(["t::a"], kills, lines, typed) == ()
    assert function_errored_tests(kills, lines, typed) == ()


def test_the_strict_gate_counts_an_untyped_test_as_an_unmeasured_one():
    assert audit_measurement_incomplete(0, 0, 0, 0) is False
    assert audit_measurement_incomplete(0, 0, 0, 1) is True
    assert audit_measurement_incomplete(0, 1, 0, 0) is True, "an errored test, the rule already here"
    assert "could not be typed on this route" in _unmeasured_clause(0, 0, 0, 2)
    assert _unmeasured_clause(0, 0, 0, 0) == ""


def _audit(**fields):
    base = {
        "function": "m.py::f",
        "test_count": 2,
        "kill_pct": 100.0,
        "mutant_complete": True,
        "line_complete": True,
        "line_basis": "admissible",
        "redundant_tests": (),
        "failing_tests": (),
        "errored_tests": (),
        "killable_gaps": (),
        "missing_lines": (),
        "candidate_equivalent": 0,
        "unclassified": 0,
        "value_killed": 4,
        "total_mutants": 4,
        "minimal_test_count": 1,
    }
    base.update(fields)
    return SuiteAudit(**base)


def test_the_page_names_untyped_tests_in_one_row_and_the_ladder_hands_back_instead_of_done():
    one = _audit(untyped_tests=("legacy:t::a",))
    every = _audit(untyped_tests=("legacy:t::a", "legacy:t::b"), test_count=2)
    assert "UNTYPED" not in _format_audit(_audit())
    for audit, count in ((one, 1), (every, 2)):
        page = _format_audit(audit)
        assert f"⚠ UNTYPED            {count} test(s) could not be typed on this route" in page
        assert "run through the CLI / a live session" in page
        assert "DONE:" not in page, "no ending may claim the suite is complete over an unmeasured test"
        assert "HAND BACK:" in page and "legacy:t::a" in page
        decision = _audit_decision(audit)
        assert decision.code == _audit_code(audit) == "type_the_route"
        assert decision.kind == "hand_back" and decision.remedy == "untyped_route"
        assert decision.argv is None and decision.then == ("audit", "m.py::f")


def test_the_untyped_code_ranks_below_the_floor_and_the_gap_and_above_the_endings():
    base = dict(
        block="",
        has_failing_tests=False,
        killable_gaps=0,
        missing_lines=0,
        redundant_tests=0,
        removing=False,
        candidate_equivalent=2,
        has_equivalent_ids=True,
        unclassified=0,
    )
    assert audit_next_action(**base, untyped=1) == "type_the_route"
    assert audit_next_action(**base, untyped=1, errored=1) == "type_the_route"
    assert audit_next_action(**base) == "flag_equivalents"
    assert audit_next_action(**{**base, "has_failing_tests": True}, untyped=1) == "fix_failing_test"
    assert audit_next_action(**{**base, "killable_gaps": 1}, untyped=1) == "close_the_gap"
    assert (
        audit_step("type_the_route", False)
        == audit_step("type_the_route", True)
        == (
            "hand_back",
            "untyped_route",
        )
    )


_SCRIPT = """
import sys
from Detective.audit import audit_suite
a = audit_suite("m.py", "f", ".")
print(sorted(a.untyped_tests))
"""


def test_a_library_audit_of_marked_tests_types_them_untyped_and_names_them(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "m.py").write_text("def f(x):\n    return x + 1\n")
    (tmp_path / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\npythonpath = ["."]\ntestpaths = ["tests"]\n'
    )
    (tmp_path / "tests" / "test_m.py").write_text(
        "import pytest\nfrom m import f\n\n\n"
        '@pytest.mark.skip(reason="no")\ndef test_a():\n    assert f(2) == 3\n\n\n'
        '@pytest.mark.xfail(reason="no")\ndef test_b():\n    assert f(2) == 99\n'
    )
    done = subprocess.run(
        [sys.executable, "-c", _SCRIPT], cwd=tmp_path, capture_output=True, text=True, check=False
    )
    assert done.returncode == 0, done.stderr
    assert "test_a" in done.stdout and "test_b" in done.stdout, done.stdout


def test_an_untyped_ledger_row_reaches_the_audit_from_the_results_trace_evidence():
    rows = (types.SimpleNamespace(test_id="t::a", baseline_outcome="untyped"),)
    from Detective.audit import baseline_typed_outcomes

    assert baseline_typed_outcomes(types.SimpleNamespace(trace_evidence=rows)) == {"t::a": "untyped"}
