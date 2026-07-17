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
from Detective.cli import _final_banner, _format_converge_terse, _plain_terms
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


# ── _final_banner ─────────────────────────────────────────────────
def test_banner_complete_clean():
    b = _final_banner(_cr())
    assert b.startswith("FINAL m.py::f: ✓ COMPLETE")
    assert "10/10 killed" in b
    assert "1 test(s)" in b  # what we WROTE (wiring.passed) …
    assert "3 test(s)" not in b  # … never the minimal cover, which counts the consumer's tests
    assert b.endswith("→ tests/test_f_synth.py")


def test_banner_complete_modulo_unproven_equivalent():
    rep = SurvivorReport((_equiv(),), ())
    b = _final_banner(_cr(final_survivors=1, killed=9, survivor_report=rep))
    assert "✓ COMPLETE (modulo 1 unproven-equivalent)" in b
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
    # candidate-equivalents + a line gap: lead with 'supply an input' (progress), not 'flag'
    rep = SurvivorReport((_equiv(),), ())
    out = _format_converge_terse(
        _cr(line_complete=False, missing_lines=(8, 10), survivor_report=rep, final_survivors=1, killed=9),
        "r.txt",
    )
    action = out.split("DO THIS:")[1].split("FINAL")[0]
    assert "flag" not in action


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
