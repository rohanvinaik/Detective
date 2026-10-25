"""Intent: converge never certifies over a floor that does not hold (Detective #114).

THE DEFECT. `converge` printed ``✓ COMPLETE (operator universe) · 9/9 killed`` over
``def scale(x): return x * 3`` whose only routed test, ``assert scale(2) == 4``, FAILS on current
code. It wrote characterization tests for the code as it is and never mentioned the failing test.
`audit` on the same folder named it ``⚠ FAILING NOW`` and stopped. Two causes, both measured:

1. converge never consulted the baseline's failing tests at all (zero reads of `failing_tests`
   in converge.py, engine.py and validity.py);
2. its pytest verification ran every test FILE defining a def with a killer's bare name, so a
   failing test that kills nothing never entered the basis — unless it happened to share a file
   with a killer, where the report blamed "the written suite" for a hand-written test's failure,
   and an UNRELATED failing test in that file withheld a certificate about one function.

THE RULING (the sandwich: the suite is the floor; audit is the line's setup): one derivation of a
function's failing tests (`audit.function_failing_tests`) gates BOTH verbs. Converge applies it to
the suite on disk BEFORE it synthesizes anything; a non-empty result stops the run, writes nothing,
and stands as ``floor_failing`` on every surface, with audit's remedy — whether the TEST or the CODE
is wrong is a person's call. Verification runs the exact proof basis (node ids), never by name.

The acceptance matrix, each case through the real CLI in a fresh directory:
  (i)   the only routed test reaches the target and fails        -> floor_failing, nothing written
  (ii)  a MUST-NOT test of a constant function fails             -> floor_failing, no `flag` offered
  (iii) a failing routed test shares a file with a passing killer -> floor_failing (not "the written
        suite did not verify")
  (iv)  a routed test fails BEFORE reaching the target            -> not this function's floor (it
        executed none of its lines, killed none of its mutants), as audit scopes it: COMPLETE
  (v)   an unrelated failing test in the SAME file as the killer   -> COMPLETE, verified by exact ids
  (vi)  an unrelated failing test in another file                  -> COMPLETE
  (vii) passing killers pin EVERY mutant beside the failing test   -> floor_failing all the same:
        completeness withheld, no reproducibility check run, the receipt reads floor_failing (exit 3)
"""

from __future__ import annotations

import itertools
import json
import os
import subprocess
import sys
import textwrap

import pytest

from Detective import pins
from Detective.audit import function_failing_tests, function_test_suite
from Detective.certify import behavior_status
from Detective.cli import converge_next_action, converge_step
from Detective.controller import CONSTRUCTIVE, admission_reason
from Detective.converge import ConvergeResult, certificate_standing
from Detective.decompose_apply import exact_proof_basis, preservation_admissible, proof_basis_selector
from Detective.plan import next_move

# ------------------------------------------------------------------ the shared derivation (pure)

KILL = {"ARITH_1": ["tests/test_m.py::test_doubles"], "VALUE_2": ["tests/test_m.py::test_doubles"]}
LINES = {
    "tests/test_m.py::test_doubles": [2],
    "tests/test_m.py::test_intent": [2],  # reached the target and failed (line coverage is raw)
    "tests/test_m.py::test_before_reach": [],  # routed, but failed before the call
    "tests/test_other.py::test_other_broken": [],  # another function's test
}


def test_the_suite_is_killers_and_line_owners_never_empty_contributions():
    assert function_test_suite(KILL, LINES) == {
        "tests/test_m.py::test_doubles",
        "tests/test_m.py::test_intent",
    }


def test_a_failing_test_that_reached_the_function_is_its_floor():
    failing = ["tests/test_m.py::test_intent"]
    assert function_failing_tests(failing, KILL, LINES) == ("tests/test_m.py::test_intent",)


def test_a_failing_test_that_never_reached_the_function_is_not_its_floor():
    # (iv) failed before the call, (v)/(vi) another function's test: none executed a line here.
    failing = ["tests/test_m.py::test_before_reach", "tests/test_other.py::test_other_broken", "unseen::t"]
    assert function_failing_tests(failing, KILL, LINES) == ()


def test_order_is_the_engines_and_a_killer_that_fails_still_counts():
    failing = ["tests/test_m.py::test_intent", "x::unrelated", "tests/test_m.py::test_doubles"]
    assert function_failing_tests(failing, KILL, LINES) == (
        "tests/test_m.py::test_intent",
        "tests/test_m.py::test_doubles",
    )


def test_no_failing_test_is_an_empty_floor():
    assert function_failing_tests([], KILL, LINES) == ()
    assert function_failing_tests(["tests/test_m.py::test_intent"], {}, {}) == ()


# ------------------------------------------------------------------ the standing (pure)


def _expected_standing(fc, lc, stale, ran, ok, admits, floor):
    # Written from the docstring's ranking, not from the code.
    if stale:
        return "stale"
    if not admits:
        return "ungateable"
    if floor:
        return "floor_failing"
    if ran and not ok:
        return "unverified"
    if not (fc and lc):
        return "incomplete"
    return "complete"


@pytest.mark.parametrize("row", list(itertools.product((False, True), repeat=7)))
def test_certificate_standing_ranks_the_floor_below_validity_and_above_verification(row):
    fc, lc, stale, ran, ok, admits, floor = row
    assert certificate_standing(fc, lc, stale, ran, ok, admits, floor) == _expected_standing(*row)


def test_a_failing_floor_is_never_complete_even_over_a_perfect_score():
    assert certificate_standing(True, True, False, True, True, True, floor_failing=True) == "floor_failing"
    assert certificate_standing(True, True, False, False, False, True, floor_failing=True) == "floor_failing"


def test_the_result_consumes_its_own_floor():
    base = {
        "function": "m.py::f",
        "converged": True,
        "at_ceiling": True,
        "initial_survivors": 0,
        "final_survivors": 0,
        "iterations": (),
        "written_path": None,
    }
    held = ConvergeResult(**base, total_mutants=1, killed=1, functionally_complete=True)
    failing = ConvergeResult(
        **base,
        total_mutants=1,
        killed=1,
        functionally_complete=True,
        floor_failing_tests=("tests/test_m.py::test_intent",),
    )
    assert held.standing == "complete" and held.complete
    assert failing.standing == "floor_failing" and not failing.complete


# ------------------------------------------------------------------ the exact proof basis


@pytest.mark.parametrize(
    ("test_id", "kind"),
    [
        ("tests/test_m.py::test_doubles", "nodeid"),
        ("tests/t.py::TestC::test_m[x-1]", "nodeid"),
        ("test_m.py::test_doubles[2-4]", "nodeid"),
        ("legacy:test_doubles", "by_name"),
        ("legacy:tests/t.py::test_doubles", "by_name"),
        ("?::test_doubles", "by_name"),
        ("::test_doubles", "by_name"),
        ("tests/t.py::test_doubles#2", "by_name"),
        ("test_doubles", "by_name"),
        ("", "none"),
    ],
)
def test_the_selector_names_what_pytest_can_select_exactly(test_id, kind):
    assert proof_basis_selector(test_id) == kind


def test_the_basis_is_the_killers_and_owners_never_their_neighbours(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_m.py").write_text(
        "def test_doubles():\n    pass\n\n\ndef test_other_broken():\n    assert False\n"
    )
    kill = {"M1": ["tests/test_m.py::test_doubles"]}
    owners = ("tests/test_m.py::test_lines",)
    assert exact_proof_basis(str(tmp_path), kill, owners) == (
        "tests/test_m.py::test_doubles",
        "tests/test_m.py::test_lines",
    )


def test_the_generated_file_is_passed_whole_so_its_ids_are_not_selected_twice(tmp_path):
    gen = tmp_path / "tests" / "detective" / "test_m_f_synth.py"
    gen.parent.mkdir(parents=True)
    gen.write_text("def test_g():\n    pass\n")
    kill = {"M1": ["tests/detective/test_m_f_synth.py::test_g", "tests/test_m.py::test_doubles"]}
    assert exact_proof_basis(str(tmp_path), kill, exclude_file=str(gen)) == ("tests/test_m.py::test_doubles",)


def test_an_id_pytest_cannot_select_falls_back_to_the_files_defining_its_name(tmp_path):
    (tmp_path / "test_legacy.py").write_text("def test_old():\n    pass\n")
    assert exact_proof_basis(str(tmp_path), {"M1": ["legacy:test_old"]}) == ("test_legacy.py",)


# ------------------------------------------------------------------ every surface consumes the standing


def test_the_next_action_is_audits_own_code_whatever_else_is_open():
    for killable, gap, diverged in itertools.product((False, True), repeat=3):
        assert (
            converge_next_action("floor_failing", "", killable, gap, has_diverged=diverged)
            == "fix_failing_test"
        )
    assert converge_next_action("floor_failing", "empty_collection", False, False, load_failed=True) == (
        "fix_failing_test"
    )


def test_the_move_is_a_persons_decision_never_a_stop_or_a_rerun():
    assert converge_step("fix_failing_test", "", "", False, "", "not_applicable") == (
        "decide",
        "fix_failing_test",
    )


@pytest.mark.parametrize(
    ("standing", "code"),
    [
        ("complete", 0),
        ("incomplete", 0),
        ("floor_failing", 1),  # a typed refusal over a trustworthy measurement; audit --check says 1
        ("stale", 3),
        ("ungateable", 3),
        ("unverified", 3),
        ("a_code_from_the_future", 3),  # never read as success
    ],
)
def test_the_exit_code_reads_the_standing(standing, code):
    from Detective.cli import converge_exit_code

    assert converge_exit_code(standing) == code


def test_the_behavior_layer_records_it_and_never_routes_it_to_converge():
    assert behavior_status("floor_failing", True, False, False, False, False, False) == pins.FLOOR_FAILING
    # A floor failure recorded for an OLDER definition is stale like any other record.
    assert behavior_status("floor_failing", False, False, False, False, False, False) == pins.PINNED_STALE
    assert admission_reason(CONSTRUCTIVE, pins.FLOOR_FAILING, True, True) == "floor_failing"
    assert next_move(pins.FLOOR_FAILING, "decompose x") == ""


def test_decompose_never_treats_a_failing_floor_as_proof():
    # Every mutant killed and nothing stale is a proof — unless a test of the function fails, when a
    # green before/after trial only shows the rewrite kept behaviour that test says is wrong.
    assert preservation_admissible(True, False, 0) is True
    assert preservation_admissible(True, False, 0, floor_failing=True) is False


# ------------------------------------------------------------------ the acceptance matrix, real CLI


def _project(tmp_path, files: dict[str, str]):
    project = tmp_path / "proj"
    for rel, text in files.items():
        path = project / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text))
    return project


def _cli(project, *args: str) -> subprocess.CompletedProcess:
    script = os.path.join(os.path.dirname(sys.executable), "detective")
    assert os.path.isfile(script), f"the installed console script is required beside {sys.executable}"
    return subprocess.run(
        [script, *args, "--project-root", str(project)],
        cwd=str(project),
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )


def _final(out: str) -> str:
    return next(ln for ln in out.splitlines() if ln.startswith("FINAL"))


def _synths(project) -> list[str]:
    return sorted(p.name for p in project.rglob("*_synth.py"))


SCALE_TIMES_3 = "def scale(x):\n    return x * 3\n"
SCALE_TIMES_2 = "def scale(x):\n    return x * 2\n"
WITH_OTHER = SCALE_TIMES_2 + "\n\ndef other():\n    return 1\n"

INTENT_DOUBLES = """
    from m import scale


    def test_intent_doubles():
        assert scale(2) == 4
"""
FENCE_DEPENDS = """
    from m import scale


    def test_fence_depends_on_input():
        assert scale(1) != scale(2)
"""
ZERO_AND_WRONG = """
    from m import scale


    def test_zero():
        assert scale(0) == 0


    def test_wrong():
        assert scale(1) == 3
"""
DOUBLES = """
    from m import scale


    def test_doubles():
        assert scale(2) == 4
        assert scale(3) == 6
"""
BEFORE_REACH = (
    DOUBLES
    + """

    def test_before_reach():
        assert 1 == 2, "fails before the call"
        scale(1)
"""
)
OTHER_BROKEN_BESIDE_DOUBLES = """
    from m import other, scale


    def test_doubles():
        assert scale(2) == 4
        assert scale(3) == 6


    def test_other_broken():
        assert other() == 2
"""
OTHER_BROKEN = """
    from m import other


    def test_other_broken():
        assert other() == 2
"""
DOUBLES_AND_WRONG = (
    DOUBLES
    + """

    def test_wrong():
        assert scale(1) == 3
"""
)


def test_i_the_only_routed_test_fails_so_nothing_is_written_or_certified(tmp_path):
    project = _project(tmp_path, {"m.py": SCALE_TIMES_3, "tests/test_m.py": INTENT_DOUBLES})
    run = _cli(project, "converge", "m.py::scale", "--two-sign")
    out = run.stdout + run.stderr
    assert run.returncode == 1, out
    assert "⚠ FAILING NOW" in out and "tests/test_m.py::test_intent_doubles" in out, out
    assert "DO THIS:  pytest tests/test_m.py::test_intent_doubles" in out, out
    assert "is the TEST's expectation wrong, or is the CODE broken?" in out, out
    assert _final(out).startswith("FINAL m.py::scale: ⚠ FAILING NOW"), out
    assert "COMPLETE" not in _final(out) and "DONE:" not in out, out
    assert _synths(project) == [], "converge wrote a characterization over a failing floor"
    # The certificate ledger records the refusal, so `plan` cannot read an older `complete` over it.
    ledger = json.loads((project / "tests" / "detective" / "certificates.json").read_text())
    assert ledger["m.py::scale"]["standing"] == "floor_failing"
    # --json carries the same decision and the same exit code.
    as_json = _cli(project, "converge", "m.py::scale", "--two-sign", "--json")
    payload = json.loads(as_json.stdout)
    assert as_json.returncode == 1, as_json.stdout + as_json.stderr
    assert payload["decision"]["code"] == "fix_failing_test"
    assert payload["floor_failing_tests"] == ["tests/test_m.py::test_intent_doubles"]


def test_ii_a_failing_must_not_offers_no_flag(tmp_path):
    project = _project(tmp_path, {"m.py": "def scale(x):\n    return 0\n", "tests/test_m.py": FENCE_DEPENDS})
    run = _cli(project, "converge", "m.py::scale", "--two-sign")
    out = run.stdout + run.stderr
    assert run.returncode == 1, out
    assert "tests/test_m.py::test_fence_depends_on_input" in out, out
    assert "detective flag" not in out and "COMPLETE" not in _final(out), out
    assert _synths(project) == []


def test_iii_a_failing_test_beside_a_killer_is_the_floor_not_the_written_suite(tmp_path):
    project = _project(tmp_path, {"m.py": SCALE_TIMES_2, "tests/test_m.py": ZERO_AND_WRONG})
    run = _cli(project, "converge", "m.py::scale", "--two-sign")
    out = run.stdout + run.stderr
    assert run.returncode == 1, out
    assert "tests/test_m.py::test_wrong" in out and "test_zero" not in _final(out), out
    assert "did not verify" not in out, out
    assert _synths(project) == []


def test_iv_a_routed_test_that_fails_before_reaching_the_function_is_not_its_floor(tmp_path):
    # As audit scopes it: the test executed none of scale's lines and killed none of its mutants, so
    # its failure is evidence about something else. scale's own killer pins it, and the verification
    # runs that killer by node id — never the whole file the failing test happens to share.
    project = _project(tmp_path, {"m.py": SCALE_TIMES_2, "tests/test_m.py": BEFORE_REACH})
    run = _cli(project, "converge", "m.py::scale")
    out = run.stdout + run.stderr
    assert run.returncode == 0, out
    assert "FAILING NOW" not in out, out
    assert _final(out).startswith("FINAL m.py::scale: ✓ COMPLETE"), out


def test_v_an_unrelated_failing_test_in_the_killers_file_does_not_withhold_the_certificate(tmp_path):
    project = _project(tmp_path, {"m.py": WITH_OTHER, "tests/test_m.py": OTHER_BROKEN_BESIDE_DOUBLES})
    run = _cli(project, "converge", "m.py::scale")
    out = run.stdout + run.stderr
    assert run.returncode == 0, out
    assert "UNVERIFIED" not in out and "FAILING NOW" not in out, out
    assert _final(out).startswith("FINAL m.py::scale: ✓ COMPLETE"), out


def test_vi_an_unrelated_failing_test_in_another_file_does_not_block(tmp_path):
    project = _project(
        tmp_path, {"m.py": WITH_OTHER, "tests/test_m.py": DOUBLES, "tests/test_other.py": OTHER_BROKEN}
    )
    run = _cli(project, "converge", "m.py::scale")
    out = run.stdout + run.stderr
    assert run.returncode == 0, out
    assert _final(out).startswith("FINAL m.py::scale: ✓ COMPLETE"), out


def test_vii_killers_that_pin_every_mutant_do_not_lift_the_floor(tmp_path):
    # The passing test kills every mutant, so only the floor withholds the certificate. Completeness is
    # withheld with it, and the certificate-facing reproducibility check does not run where no
    # certificate can stand: its refusal would outrank the floor (measured through a symlinked project
    # root, the run ended UNGATEABLE under its own FAILING NOW row).
    project = _project(tmp_path, {"m.py": SCALE_TIMES_2, "tests/test_m.py": DOUBLES_AND_WRONG})
    run = _cli(project, "converge", "m.py::scale", "--json")
    payload = json.loads(run.stdout)
    assert run.returncode == 1, run.stdout + run.stderr
    assert payload["killed"] == payload["total_mutants"] > 0
    assert payload["floor_failing_tests"] == ["tests/test_m.py::test_wrong"]
    assert payload["functionally_complete"] is False
    assert payload["decision"]["state"]["standing"] == "floor_failing"
    assert payload["decision"]["code"] == "fix_failing_test"
    assert payload["decision"]["final"].startswith("FINAL m.py::scale: ⚠ FAILING NOW"), payload["decision"]
    assert "verifying reproducibility" not in run.stderr, run.stderr
    # The receipt reads the same refusal: never a "passed" baseline verify-rewrite could preserve against.
    receipt = _cli(project, "receipt", "m.py::scale")
    rec = json.loads(receipt.stdout)
    assert receipt.returncode == 3, receipt.stdout + receipt.stderr
    assert rec["proof_status"] == "floor_failing" and rec["functionally_complete"] is False
