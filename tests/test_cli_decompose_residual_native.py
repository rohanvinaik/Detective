"""Tests for the decompose report — the counts, and the ONE next action.

Hand-written native, same sanctioned exemption as test_cli_converge_output_native.py:
these format a ``DecompositionApply`` + ``ConvergeResult``, rich frozen dataclasses the
CLI cannot synthesize as ``--input``.

Two contracts, and the second is the reason this file exists.

COUNT WHAT BLOCKS. ``functionally_complete`` (converge.py) is ``not killable and not
unclassified`` — a candidate-equivalent does NOT block. Rendering ``final_survivors`` fused
all three populations into one number, so the report counted 22 blockers where 5 blocked and
asked for an input to close all of them.

THE ACTION MUST RUN. ``--input`` parses an allowlist (literals + ``ast.*``) — that is what
makes "no arbitrary code execution" checkable. So for a function taking a domain object NO
string satisfies ``--input "(<account>, ...)"``, and printing it hands the reader a command
that always errors: `--input only [ast] are available — 'Account' is not`. They do exactly
what the tool says, it fails, and they conclude the tool is broken. ``inputs_expressible``
answers "can a human type this?" from the input that actually exercised the function, and it
must decide which action is printed.
"""

from __future__ import annotations

from Detective.cli import _format_decompose
from Detective.converge import ConvergeResult
from Detective.decompose_apply import Decomposition, DecompositionApply, Extraction
from Detective.equivalence import MutantVerdict, SurvivorReport, Witness

_HELPER_SRC = (
    "import os\n\n\nclass Account:\n    pass\n\n\ndef _compute_base(weight):\n"
    "    base = 500\n    return base\n"
)


def _killable(mid: str) -> MutantVerdict:
    return MutantVerdict(
        mid, "VALUE", "- x\n+ x+1", killable=True, witness=Witness((1,), "1", "2"), searched=5
    )


def _equiv(mid: str) -> MutantVerdict:
    return MutantVerdict(mid, "BOUNDARY", "- >\n+ >=", killable=False, witness=None, searched=14)


def _rep(**over) -> SurvivorReport:
    base = dict(
        verdicts=tuple(_killable(f"K{i}") for i in range(5)) + tuple(_equiv(f"E{i}") for i in range(17)),
        unclassified=(),
        inputs_expressible=True,
    )
    base.update(over)
    return SurvivorReport(**base)


def _proof(**over) -> ConvergeResult:
    base = dict(
        function="p.py::quote",
        converged=False,
        at_ceiling=True,
        initial_survivors=69,
        # The fused total the renderer used to print. Deliberately != the blocking count, so
        # a regression to `final_survivors` fails loudly instead of reading plausibly.
        final_survivors=22,
        iterations=(),
        written_path="tests/test_quote_synth.py",
        total_mutants=93,
        killed=71,
        functionally_complete=False,
        line_complete=True,
        minimal_test_count=9,
        signature="quote(weight, distance, tier, rush, insured)",
        param_names=("weight", "distance", "tier", "rush", "insured"),
        survivor_report=_rep(),
    )
    base.update(over)
    return ConvergeResult(**base)


def _result(proof: ConvergeResult | None, validated: bool = False) -> DecompositionApply:
    ex = Extraction("_compute_base", ("weight",), ("base",), _HELPER_SRC)
    return DecompositionApply("quote", (), (Decomposition(ex, validated=validated),), (), proof=proof)


def _out(**over) -> str:
    return _format_decompose(_result(_proof(**over)), applied_mode=True)


# ── count what blocks ────────────────────────────────────────────────
def test_counts_only_the_blocking_population():
    """5 killable block; 17 candidate-equivalent do not. The old renderer said 22."""
    out = _out()
    assert "5 block the proof" in out
    assert "22" not in out


def test_names_equivalents_as_non_blocking():
    """Silence about the non-blockers is what made the number stop responding to input."""
    assert "17 candidate-equivalent do NOT block." in _out()


def test_unclassified_counted_and_attributed_apart_from_killable():
    """Different cause, different fix: an unclassified survivor was never reached at all."""
    out = _out(survivor_report=_rep(verdicts=(), unclassified=("U0", "U1"), inputs_expressible=None))
    assert "2 block the proof" in out
    assert "synthesis never reached them." in out


# ── the action must run ──────────────────────────────────────────────
def test_typeable_params_get_the_input_command():
    out = _out()
    assert "--apply" in out and "--input" in out
    assert "<weight>" in out


def test_untypeable_params_never_get_an_input_command():
    """THE regression. `--input` rejects a domain object by design, so naming it here prints
    a command that cannot run. Ask for the test whose arguments get captured instead."""
    out = _out(survivor_report=_rep(inputs_expressible=False))
    # No `--input` COMMAND. The word itself is fine — and load-bearing — in the sentence
    # explaining why it cannot carry this parameter; what must never appear is a template
    # the reader would paste and watch fail.
    assert '--input "' not in out
    assert "<weight>" not in out
    assert "add ONE test that calls quote(weight, distance, tier, rush, insured)" in out
    assert "no literal form" in out


def test_cause_line_agrees_with_the_action():
    """ "an input can kill them" above "--input cannot carry it" is two true sentences that
    read as a contradiction; a reader resolves that by distrusting both."""
    out = _out(survivor_report=_rep(inputs_expressible=False))
    assert "an input can kill them" not in out
    assert "only a real object reaches it." in out


def test_exactly_one_terminal_action():
    for out in (_out(), _out(survivor_report=_rep(inputs_expressible=False))):
        assert sum(out.count(k) for k in ("DO THIS:", "DONE:", "STOP.")) == 1


# ── the preview must show the helper ─────────────────────────────────
def test_preview_shows_the_helper_not_the_head_of_the_file():
    """`new_source` is the whole rewritten MODULE. Slicing its head showed whatever sat at
    line 1 — for a file starting `import os` / `class Account:` the report named the helper
    and displayed the imports."""
    out = _out()
    assert "│ def _compute_base(weight):" in out
    assert "│ import os" not in out
    assert "│ class Account:" not in out


# ── terminal states ──────────────────────────────────────────────────
def test_no_classification_abstains_instead_of_naming_a_population():
    out = _out(survivor_report=None)
    assert "the classification did not run" in out
    assert "block the proof" not in out


def test_mutation_complete_rejection_is_a_verdict_not_a_gap():
    out = _out(functionally_complete=True)
    assert "STOP." in out
    assert "--input" not in out and "block the proof" not in out


def test_proven_but_not_written_asks_for_apply():
    out = _format_decompose(_result(_proof(), validated=True), applied_mode=False)
    assert "DO THIS:  detective decompose 'quote' --apply" in out


def test_no_suite_asks_for_converge_first():
    out = _format_decompose(_result(None), applied_mode=True)
    assert "DO THIS:  detective converge 'quote'" in out


def test_no_separable_block_is_done_not_an_action():
    empty = DecompositionApply("quote", (), (), (), proof=None)
    out = _format_decompose(empty, applied_mode=True)
    assert "DONE:" in out and "no separable block" in out


def test_report_stays_within_its_line_budget():
    """The product is the report. 20 lines was 4 lines of verdict under 16 of scaffolding."""
    for out in (_out(), _out(survivor_report=_rep(inputs_expressible=False)), _out(survivor_report=None)):
        assert len(out.splitlines()) <= 20


# ── never offer an input that cannot be typed ────────────────────────
def test_gap_desc_omits_witness_args_that_have_no_literal_form():
    """`witness.args` is repr'd, so a domain object renders `<billing.Account object at
    0x105fe6ad0>` — a memory address, presented as the input to kill with. It cannot be typed
    and changes every run, and an LLM reading it does not skip it: it passes the string, or
    invents a constructor from it. Handing a caller a pointer and calling it an input is worse
    than silence, because silence is at least not actionable."""
    from Detective.audit import _gap_desc

    class _W:
        args = (object(),)

    class _V:
        category, mutant_id, witness = "VALUE", "V0", _W()

    out = _gap_desc(_V(), expressible=False)
    assert out == "VALUE [V0]"
    assert "object at 0x" not in out


def test_gap_desc_keeps_witness_args_that_can_be_typed():
    """The other half: for literal params the input IS the finding, and dropping it would cost
    the reader the one thing that makes the gap actionable."""
    from Detective.audit import _gap_desc

    class _W:
        args = (0, "gold")

    class _V:
        category, mutant_id, witness = "LOGICAL", "L1", _W()

    assert _gap_desc(_V(), expressible=True) == "LOGICAL [L1] — kill with (0, 'gold')"
