"""The ladders consume the classes of an equivalents residual, not a count that includes them all
(Detective #140 item 1, #142 item 2).

The defect: the report-content lane gave a surviving stale its own class (`history_dependent`) and an
identical mutant its own state (`identical`), and removed both from the flag ROWS. But `audit_next_action`
still received `bool(a.candidate_equivalent_ids)`, which counts both, so a residual made only of identical
mutants or only of stale-return survivors still returned `flag_equivalents`; and converge's DONE sentence
for a stale-only residual named its remedy ("supply two inputs") with no command to run them with.

These tests pin `equivalents_route`, the ladder codes and steps, the decision record's residual, the pages
for each class, and the mixed residual (one identical, one stale, one genuinely flaggable survivor).
"""

import json
import os
import subprocess
import sys
import types

import pytest

from Detective.audit import SuiteAudit
from Detective.cli import (
    _audit_action,
    _audit_decision,
    _converge_action,
    _converge_decision,
    audit_next_action,
    audit_step,
    equivalents_route,
)


@pytest.mark.parametrize(
    ("flaggable", "candidates", "identical", "history", "route"),
    [
        (0, 0, 0, 0, "none"),
        (1, 3, 1, 1, "flag"),
        (2, 2, 0, 0, "flag"),
        (0, 1, 1, 0, "identical_only"),
        (0, 3, 3, 0, "identical_only"),
        (0, 1, 0, 1, "history_only"),
        (0, 2, 1, 1, "history_only"),
        (0, 2, 0, 1, "unflaggable"),  # a stale and something else that is not flaggable (crash-only)
        (0, 1, 0, 0, "unflaggable"),
        (0, 3, 1, 0, "unflaggable"),
    ],
)
def test_equivalents_route_reads_the_classes(flaggable, candidates, identical, history, route):
    assert equivalents_route(flaggable, candidates, identical, history) == route


def _ladder(**kw) -> str:
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
    return audit_next_action(**{**base, **kw})


def test_the_ladder_offers_flag_only_for_a_flaggable_residual():
    assert _ladder(equivalents="flag") == "flag_equivalents"
    assert _ladder(equivalents="unflaggable") == "flag_equivalents", "the basis block says what remains"
    assert _ladder() == "flag_equivalents", "a caller that supplies no route keeps the previous reading"
    assert _ladder(equivalents="identical_only") == "done_identical"
    assert _ladder(equivalents="history_only") == "supply_second_call"
    assert _ladder(equivalents="history_only", killable_gaps=1) == "close_the_gap"
    assert _ladder(equivalents="identical_only", has_failing_tests=True) == "fix_failing_test"
    assert audit_step("done_identical", False) == ("done", "")
    assert audit_step("done_identical", True) == ("run", "")
    assert (
        audit_step("supply_second_call", False)
        == audit_step("supply_second_call", True)
        == (
            "supply",
            "history_second_call",
        )
    )


def _audit(**fields) -> SuiteAudit:
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
        "value_killed": 9,
        "total_mutants": 10,
        "minimal_test_count": 1,
        "boundary_probe": "run",
        "takes_arguments": True,
    }
    base.update(fields)
    return SuiteAudit(**base)


def test_a_residual_of_identical_mutants_is_done_and_says_there_is_nothing_to_flag():
    audit = _audit(candidate_equivalent=1, candidate_equivalent_ids=("SWAP_a",), identical_ids=("SWAP_a",))
    decision = _audit_decision(audit)
    assert decision.code == "done_identical" and decision.kind == "done"
    page = "\n".join(_audit_action(audit, decision=decision))
    assert page.startswith("DONE:") and "nothing to prove, nothing to flag" in page
    assert "detective flag" not in page and "no VALUE assertion pins" not in page


def test_a_residual_of_stale_survivors_hands_back_the_two_call_remedy_with_its_command():
    audit = _audit(
        candidate_equivalent=1, candidate_equivalent_ids=("OUTPUT_a",), history_dependent_ids=("OUTPUT_a",)
    )
    decision = _audit_decision(audit)
    assert decision.code == "supply_second_call"
    assert (decision.kind, decision.remedy, decision.argv) == ("supply", "history_second_call", None)
    assert decision.then == ("converge", "m.py::f")
    assert decision.residual == ("history", ())
    page = "\n".join(_audit_action(audit, decision=decision))
    assert page.startswith("AUTHOR INPUT:") and "second call" in page
    assert '--input "(<A>,)" --input "(<B>,)"' in page and "detective flag" not in page
    two = _audit_decision(audit, two_sign=True)
    assert two.code == "supply_second_call" and two.kind == "supply", (
        "never a bare converge that changes nothing"
    )


def test_a_mixed_residual_offers_flag_only_for_the_genuinely_flaggable_id():
    audit = _audit(
        candidate_equivalent=3,
        candidate_equivalent_ids=("SWAP_i", "OUTPUT_h", "VALUE_f"),
        identical_ids=("SWAP_i",),
        history_dependent_ids=("OUTPUT_h",),
    )
    decision = _audit_decision(audit)
    assert decision.code == "flag_equivalents"
    assert decision.residual == ("probed", ("VALUE_f",)), "--json's residual agrees with the page"
    page = "\n".join(_audit_action(audit, decision=decision))
    assert "detective flag 'm.py::f' VALUE_f" in page
    assert "SWAP_i" not in page and "OUTPUT_h" not in page


def _verdict(mutant_id, **kw):
    base = dict(
        crash_only=False, diverged=False, identical=False, history="", category="VALUE", diff_summary="d"
    )
    return types.SimpleNamespace(mutant_id=mutant_id, **{**base, **kw})


def _converge(equivalent):
    rep = types.SimpleNamespace(
        equivalent=equivalent,
        killable=[],
        unclassified=[],
        boundary_probe="run",
        takes_arguments=True,
        step_budget_divergent=(),
        inputs_expressible=True,
        load_failed=False,
        note="",
    )
    result = types.SimpleNamespace(
        function="m.py::one",
        functionally_complete=True,
        final_survivors=0,
        missing_lines=(),
        signature="one(x)",
        param_names=("x",),
        environment_gated=(),
        admits_certificate=True,
        policy_id="p",
        synthesized_only=False,
    )
    decision = _converge_decision(result, rep, render_tests=False)
    return decision, "\n".join(_converge_action(result, rep, decision=decision))


def test_converge_done_for_a_stale_only_residual_names_the_command_and_offers_no_flag():
    decision, page = _converge([_verdict("OUTPUT_h", history="needs_second_call")])
    assert decision.residual == ("history", ())
    assert 'detective converge \'m.py::one\' --input "(<A>,)" --input "(<B>,)"' in page
    assert "detective flag" not in page


def test_converge_mixed_residual_flags_only_the_flaggable_and_keeps_the_second_call_command():
    decision, page = _converge(
        [
            _verdict("OUTPUT_h", history="needs_second_call"),
            _verdict("VALUE_f"),
            _verdict("SWAP_i", identical=True),
        ]
    )
    assert decision.residual == ("probed", ("VALUE_f",))
    assert "detective flag 'm.py::one' VALUE_f" in page and "OUTPUT_h" not in page and "SWAP_i" not in page
    assert "--input" not in page.replace("(--input twice)", ""), (
        "the second-call ask belongs to a stale-only one"
    )


_SOURCE = "def g(a, b, c):\n    return (a, b, c)\n\n\ndef f(x):\n    return g(False, False, x)\n"
_TEST = "from swp import f\n\n\ndef test_f():\n    assert f(3) == (False, False, 3)\n"


def test_an_identical_mutant_only_residual_end_to_end(tmp_path):
    root = tmp_path / "proj"
    (root / "tests").mkdir(parents=True)
    (root / "swp.py").write_text(_SOURCE)
    (root / "tests" / "test_swp.py").write_text(_TEST)

    def run(*argv):
        return subprocess.run(
            [sys.executable, "-m", "Detective", *argv],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
            env={k: v for k, v in os.environ.items() if k != "PYTHONUNBUFFERED"},
        )

    assert run("regime", "--migrate", "--project-root", str(root)).returncode == 0
    report = json.loads(run("audit", "swp.py::f", "--json").stdout)
    assert report["identical_ids"] and report["decision"]["code"] == "done_identical"
    assert report["decision"]["residual"]["flaggable_ids"] == []
    page = run("audit", "swp.py::f").stdout
    assert "nothing to prove, nothing to flag" in page and "detective flag" not in page
