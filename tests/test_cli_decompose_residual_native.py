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

from Detective.cli import _MAX_BATCH, _format_decompose
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
    # Pass the target, as the CLI does. `DecompositionApply.function` is the BARE name, and a
    # bare name is not a resolvable CLI target — the fallback exists for direct library callers,
    # never for a printed command.
    return _format_decompose(_result(_proof(**over)), applied_mode=True, target="p.py::quote")


# ── count what blocks ────────────────────────────────────────────────
def test_counts_only_the_blocking_population():
    """5 killable block; 17 candidate-equivalent do not. The old renderer said 22."""
    out = _out()
    assert "5 behaviour(s)" in out and "block the proof" in out
    assert "22" not in out


def test_names_equivalents_as_non_blocking():
    """Silence about the non-blockers is what made the number stop responding to input."""
    assert "17 more look equivalent and do NOT block." in _out()


def test_unclassified_counted_and_attributed_apart_from_killable():
    """Different cause, different fix: an unclassified survivor was never reached at all."""
    out = _out(survivor_report=_rep(verdicts=(), unclassified=("U0", "U1"), inputs_expressible=None))
    assert "2 behaviour(s)" in out and "block the proof" in out
    # No internal nouns: "synthesis" is a word from the engine's implementation, not the
    # reader's vocabulary, and it appeared with no referent anywhere in the report.
    assert "synthesis" not in out
    assert "no input Detective built reaches them" in out


# ── the action must run ──────────────────────────────────────────────
def test_a_witness_is_printed_as_the_literal_input_not_a_slot():
    """A witness is a call the engine RAN — `assert f(args) == original` is a fact about this
    code, not a template. Printing `<weight>` there discards the derivation the pipeline
    exists to do, and hands it back to the reader."""
    out = _out()
    assert '--input "(1,)"' in out  # the witness's real args
    assert "<weight>" not in out  # never a slot when a real call is known
    assert "SUGGESTED" in out  # derived, unverified -> stated, not applied


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
    """The product is the report. The typeable and no-classification branches stay tight; the
    scaffold branch is allowed more because its extra lines ARE the product — a file's exact
    contents is not padding, and the alternative (a one-line description) is what failed."""
    for out in (_out(), _out(survivor_report=None)):
        assert len(out.splitlines()) <= 20
    assert len(_out(survivor_report=_rep(inputs_expressible=False)).splitlines()) <= 26


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


# ── ONE action, always --input ───────────────────────────────────────
def test_the_only_action_is_supply_an_input():
    """The README states the whole interface: "You supply what only you know; Detective
    derives the rest" — and it names "a valid domain object" as one of the things you supply.
    There is no second workflow. A fork here ("write a test yourself") inverts the tool: this
    pipeline DERIVES tests, so asking the reader to author one hands back its only job. That
    fork existed solely because INPUT_MODULES was {ast} and rejected Account(...) — a bug at
    the allowlist, not a state to render."""
    for rep in (_rep(inputs_expressible=True), _rep(inputs_expressible=False), _rep(inputs_expressible=None)):
        out = _out(survivor_report=rep)
        assert "detective decompose 'p.py::quote' --apply --input" in out
        assert "create tests/" not in out  # no scaffold, ever
        assert "add ONE test" not in out  # no hand-authoring, ever


def test_a_domain_object_is_expressible_in_the_input_slot():
    """The allowlist gate is what the whole interface rested on: with {ast} only, the tool
    printed `supply --input "(<account>, ...)"` for a slot no --input could fill — its own
    docstring names that dead end for ast.FunctionDef, one type narrower."""
    import ast as _ast

    from Detective.equivalence import parse_input_expression

    class Account:
        def __init__(self, tier):
            self.tier = tier

    ns = {"Account": Account, "__name__": "billing"}
    (arg,) = parse_input_expression("(Account('gold'),)", ns)
    assert arg.value.tier == "gold"  # the live object ran
    assert repr(arg) == "Account('gold')"  # SourceExpr renders the CONSTRUCTOR, not <object at 0x..>
    assert "from billing import Account" in arg.imports  # so the generated test can import it
    assert _ast  # literals still parse without a namespace
    assert parse_input_expression("(1, 'a')") == (1, "a")


# ── batching: --input is repeatable, so say what ALL the requirements are ──


def test_witnesses_batch_too_and_carry_the_suggested_label():
    """A witness is a call the engine RAN. Several are several real calls — batch them, and
    keep the abstention on the line, not four rows below it."""
    out = _out()  # 5 killable, all with witnesses
    assert out.count('--input "(1,)"') == 5  # ALL of them, batched into one command
    assert "SUGGESTED" in out


# ── batching: --input is repeatable, so name ALL the derived requirements ──
def _boundary(mid: str, n: int) -> MutantVerdict:
    """A real BOUNDARY diff: `q > n` shifted to `q >= n`, both whole-function bodies.

    Operands must MATCH between original and mutant or `_boundary_hint` cannot recover them —
    that is the point of the hint: it derives the equality edge from the comparison whose
    OPERATOR moved, so a fixture that also moves the operand tests nothing.
    """
    orig = f"def f(q):\n    if q > {n}:\n        pass"
    mut = f"def f(q):\n    if q >= {n}:\n        pass"
    return MutantVerdict(mid, "BOUNDARY", f"- {orig}\n+ {mut}", killable=False, witness=None, searched=9)


def test_every_derived_requirement_is_named_not_just_the_first():
    """`--input` is repeatable and each call kills what it reaches, so N requirements close in
    one command — but only if the report SAYS what they are. Printing next(...) turned a
    batchable job into N sequential rounds and never disclosed that N-1 more existed."""
    rep = _rep(verdicts=(_boundary("B0", 0), _boundary("B1", 5)), inputs_expressible=True)
    out = _out(survivor_report=rep)
    assert "1. where q == 0" in out
    assert "2. where q == 5" in out
    # One --input per requirement: the repetition IS the signal for how many calls to author.
    assert out.count('--input "(<weight>') == 2


def test_the_batch_cap_is_disclosed_never_silent():
    """A bound that is not named reads as "this is all of them"."""
    many = tuple(_boundary(f"B{i}", i) for i in range(_MAX_BATCH + 4))
    out = _out(survivor_report=_rep(verdicts=many, inputs_expressible=True))
    assert "(+4 more in" in out
    # Count the FLAG, not the word — the prose says "each as its own --input" too.
    assert out.count('--input "(<weight>') == _MAX_BATCH


def test_derive_inputs_returns_data_so_both_surfaces_cannot_drift():
    """The derivation is shared; the RENDERING is not. A human runs `--input "(...)"`, a tool
    caller passes `inputs=["(...)"]` — sharing the rendered string put terminal syntax into an
    MCP response, telling a caller to use a flag that does not exist there."""
    from Detective.cli import _derive_inputs

    kind, items, total = _derive_inputs(_proof(), _rep(verdicts=(_boundary("B0", 0),)))
    assert (kind, items, total) == ("boundary", ["where q == 0"], 1)
    kind, items, total = _derive_inputs(_proof(), _rep())  # 5 killable, each with a witness
    assert kind == "witness" and items[0] == "(1,)" and total == 5
    kind, items, total = _derive_inputs(_proof(), _rep(verdicts=(), unclassified=("U0",)))
    assert (kind, items, total) == ("author", [], 0)
