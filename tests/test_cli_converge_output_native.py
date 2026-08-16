"""Tests for the converge terminal-output contract — the minimal terse view, the
plain-language verdict, and the stable ``FINAL`` banner.

These format a ``ConvergeResult`` (a rich frozen dataclass the CLI cannot synthesize
as ``--input``), so they follow the same hand-written native pattern as the rest of
test_cli_native.py — the sanctioned exemption for presentation helpers. The invariants
pinned here are a downstream CONTRACT: the ``FINAL`` line is greppable and ALWAYS last,
and its status token is stable, so tooling that tails the output always finds the result.
"""

from __future__ import annotations

from Detective.certify import PytestWiring
from Detective.cli import (
    _final_banner,
    _format_converge_terse,
    _plain_terms,
    deep_structure_caveat,
)
from Detective.converge import ConvergeResult
from Detective.equivalence import MutantVerdict, SurvivorReport, Witness


def _cr(**over) -> ConvergeResult:
    base = dict(
        function="m.py::f",
        converged=True,
        at_ceiling=True,
        initial_survivors=4,
        final_survivors=0,
        iterations=(),
        written_path="tests/test_f_synth.py",
        total_mutants=10,
        killed=10,
        functionally_complete=True,
        line_complete=True,
        # The two counts are deliberately DIFFERENT, because they are different quantities and
        # the banner conflated them: `minimal_test_count` is the two-axis minimal cover over the
        # whole suite (the consumer's tests included), `wiring.passed` is what WE wrote, measured
        # by running our file. Equal fixtures cannot tell the two apart — which is exactly how
        # `wrote 3 test(s)` shipped for a file holding one test.
        minimal_test_count=3,
        wiring=PytestWiring(None, True, 1, ""),
    )
    base.update(over)
    return ConvergeResult(**base)


def _equiv(mid: str = "B1") -> MutantVerdict:
    return MutantVerdict(mid, "BOUNDARY", "- >\n+ >=", killable=False, witness=None, searched=5)


def _killable(mid: str = "K1") -> MutantVerdict:
    w = Witness((1,), "1", "2")
    return MutantVerdict(mid, "VALUE", "- x\n+ x+1", killable=True, witness=w, searched=5)


def _crash_only(mid: str = "C1") -> MutantVerdict:
    # Non-killable by VALUE but distinguished by a crash — a value_residual, never a structural one.
    return MutantVerdict(
        mid, "VALUE", "- x\n+ x+1", killable=False, witness=None, searched=5, crash_only=True
    )


# ── _final_banner ─────────────────────────────────────────────────
def test_banner_complete_clean():
    b = _final_banner(_cr())
    # the claim is scoped to the operator universe, and the banner says so — the
    # report body's qualifier alone left the summary line more confident than
    # the evidence (measured: a 150.0 -> 149.0 threshold shift survived "COMPLETE")
    assert b.startswith("FINAL m.py::f: ✓ COMPLETE (operator universe)")
    assert "10/10 killed" in b
    assert "1 test(s)" in b  # what we WROTE (wiring.passed) …
    assert "3 test(s)" not in b  # … never the minimal cover, which counts the consumer's tests
    assert b.endswith("→ tests/test_f_synth.py")


def test_banner_complete_modulo_unproven_equivalent():
    rep = SurvivorReport((_equiv(),), ())
    b = _final_banner(_cr(final_survivors=1, killed=9, survivor_report=rep))
    assert "✓ COMPLETE (operator universe · modulo 1 unproven-equivalent)" in b
    assert "9/10 killed" in b


def test_banner_incomplete_names_killable_residuals():
    # "Incomplete", not "✗ INCOMPLETE": the residual is named right here, and a ✗ brands a
    # run that pinned every killable behavior as a failure.
    rep = SurvivorReport((_killable(),), ())
    b = _final_banner(_cr(functionally_complete=False, final_survivors=1, killed=8, survivor_report=rep))
    assert b.startswith("FINAL m.py::f: Incomplete")
    assert "✗" not in b
    assert "1 killable" in b


def test_banner_incomplete_names_line_gap():
    # every killable killed, but a line gap remains → Incomplete names the gap, not just kills
    b = _final_banner(_cr(line_complete=False, missing_lines=(8, 10), killed=8, final_survivors=0))
    assert "Incomplete" in b
    assert "✗" not in b
    assert "2-line gap" in b


def test_banner_omits_arrow_when_nothing_written():
    b = _final_banner(_cr(written_path=None))
    assert "→" not in b


# ── _plain_terms ──────────────────────────────────────────────────
def test_plain_terms_complete_clean_has_no_jargon():
    t = _plain_terms(_cr())
    assert "nothing killable remains" in t
    assert "DOF" not in t and "every-killable-killed" not in t


def test_plain_terms_flags_unproven_equivalent():
    rep = SurvivorReport((_equiv(),), ())
    t = _plain_terms(_cr(final_survivors=1, killed=9, survivor_report=rep))
    assert "UNPROVEN" in t and "flag" in t


def test_plain_terms_names_line_gap():
    # a line gap is a first-class remaining disposition — plain-terms must name it
    t = _plain_terms(_cr(line_complete=False, missing_lines=(8, 10), killed=8, final_survivors=0))
    assert "2 line(s)" in t


def test_terse_line_gap_leads_with_supply_not_flag():
    # candidate-equivalents + a line gap: lead with input authoring (progress), not 'flag'.
    # The angle-bracket shape is deliberately not rendered as an executable DO THIS command.
    rep = SurvivorReport((_equiv(),), ())
    out = _format_converge_terse(
        _cr(line_complete=False, missing_lines=(8, 10), survivor_report=rep, final_survivors=1, killed=9),
        "r.txt",
    )
    action = out.split("AUTHOR INPUTS:")[1].split("FINAL")[0]
    assert "flag" not in action
    assert "THEN RUN:" in action


def test_plain_terms_incomplete_points_at_inputs():
    rep = SurvivorReport((_killable(),), ())
    t = _plain_terms(_cr(functionally_complete=False, final_survivors=1, survivor_report=rep))
    assert "killable" in t


# ── _format_converge_terse ────────────────────────────────────────
def test_terse_banner_is_the_last_line():
    rep = SurvivorReport((_equiv(),), ())
    out = _format_converge_terse(_cr(final_survivors=1, killed=9, survivor_report=rep), "r.txt")
    assert out.splitlines()[-1].startswith("FINAL m.py::f:")


def test_terse_surfaces_flag_command_for_equivalent():
    rep = SurvivorReport((_equiv("B7"),), ())
    out = _format_converge_terse(_cr(final_survivors=1, killed=9, survivor_report=rep), "r.txt")
    assert "detective flag 'm.py::f' B7" in out


def test_terse_points_at_the_report_file():
    out = _format_converge_terse(_cr(), "reports/converge_f.txt")
    assert "reports/converge_f.txt" in out


def test_terse_is_minimal_when_complete_clean():
    # clean complete: header, what was written, the report pointer, one DONE, the banner —
    # and nothing per-mutant. The budget is the point: the product is the report.
    out = _format_converge_terse(_cr(), "r.txt")
    assert len(out.splitlines()) <= 10


# ── F2: the deep-structure caveat must reach the DEFAULT terse surface ─────────
def test_deep_structure_caveat_truth_table():
    # Warn ONLY on a deep_structural target that HAS a CANDIDATE-EQUIVALENT survivor (the second arg);
    # a crash-only survivor is a value_residual and must not trigger it (see the crash-only test).
    assert deep_structure_caveat("deep_structural", True) is True
    assert deep_structure_caveat("deep_structural", False) is False  # no candidate-equiv → no caveat
    assert deep_structure_caveat("flat", True) is False
    assert deep_structure_caveat("", True) is False


def test_terse_surfaces_the_deep_structure_caveat_on_a_flag_eligible_survivor():
    # A candidate-equivalent survivor on a deep_structural target: the terse DEFAULT surface — the one
    # that invites a `flag` — must carry the caution that it may be killable-with-harder-input (F2).
    rep = SurvivorReport((_equiv(),), ())
    out = _format_converge_terse(
        _cr(
            functionally_complete=True,
            final_survivors=1,
            killed=9,
            survivor_report=rep,
            structural_difficulty="deep_structural",
        ),
        "",
    )
    assert "deep-structure" in out
    assert "may be KILLABLE" in out


def test_terse_omits_the_caveat_on_a_flat_target():
    rep = SurvivorReport((_equiv(),), ())
    out = _format_converge_terse(
        _cr(
            functionally_complete=True,
            final_survivors=1,
            killed=9,
            survivor_report=rep,
            structural_difficulty="flat",
        ),
        "",
    )
    assert "deep-structure" not in out


def _deep_structural_terse(inputs_expressible):
    rep = SurvivorReport((_equiv(),), (), inputs_expressible=inputs_expressible)
    return _format_converge_terse(
        _cr(
            functionally_complete=True,
            final_survivors=1,
            killed=9,
            survivor_report=rep,
            structural_difficulty="deep_structural",
        ),
        "",
    )


def test_terse_caveat_asks_for_input_when_the_structural_input_is_expressible():
    out = _deep_structural_terse(inputs_expressible=True)
    assert "nested/cross-referential --input" in out


def test_terse_caveat_asks_for_a_fixture_when_the_input_is_not_expressible():
    # F2 dispatch: no `--input` can express the shape, so the caveat asks for a hand-built object,
    # never the broken `--input` ask.
    out = _deep_structural_terse(inputs_expressible=False)
    assert "hand-built object (no --input expresses it)" in out


def test_converge_result_carries_the_function_basis_into_json():
    # Review "governs converge": converge rebuilds the basis and carries it on ConvergeResult, so
    # `converge --json` (asdict) exposes the one authoritative obligation object.
    from dataclasses import asdict
    from types import SimpleNamespace

    from Detective.engine import function_basis
    from Detective.validity import MeasurementValidity

    pr = SimpleNamespace(
        function_key="m.py::f",
        executable_lines=[1],
        admissible_line_coverage={"t": [1]},
        killed_records=[{"mutant_id": "m0"}],
        survivor_records=[],
        total_survived=0,
    )
    basis = function_basis(pr, MeasurementValidity(gateable=True, cut_reasons=()))
    js = asdict(_cr(function_basis=basis))
    assert js["function_basis"]["target"] == "m.py::f"
    assert js["function_basis"]["action"] in {"complete", "gap", "unresolved", "trace_next"}


def test_terse_omits_the_caveat_for_a_crash_only_only_residual_on_deep_structural():
    # A crash-only survivor is a value_residual (a crash input DOES distinguish it), NOT a
    # structural_residual — so it must NOT receive the structural-input caveat even on a
    # deep_structural target. The merged candidate-OR-crash flag was the bug that let it (P1 review).
    rep = SurvivorReport((_crash_only(),), ())
    out = _format_converge_terse(
        _cr(
            functionally_complete=True,
            final_survivors=1,
            killed=9,
            survivor_report=rep,
            structural_difficulty="deep_structural",
        ),
        "",
    )
    assert "deep-structure" not in out
    assert "crash-only-equiv" in out  # the crash-only row itself is still shown
