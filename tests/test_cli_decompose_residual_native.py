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

from dataclasses import replace

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
    # `replace`, not a dict splatted into the constructor: the dict widens every value to the
    # union of its members, so a checker cannot tell `unclassified=()` from
    # `inputs_expressible=True` and reports one error per field of the dataclass.
    base = SurvivorReport(
        verdicts=tuple(_killable(f"K{i}") for i in range(5)) + tuple(_equiv(f"E{i}") for i in range(17)),
        unclassified=(),
        inputs_expressible=True,
    )
    return replace(base, **over) if over else base


def _proof(**over) -> ConvergeResult:
    base = ConvergeResult(
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
    return replace(base, **over) if over else base


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


def test_identical_witnesses_collapse_to_one_input_and_say_what_they_cover():
    """Five mutants sharing ONE distinguishing call is one `--input`, not five. Passing the
    same tuple five times kills exactly what passing it once kills, so the repetition bought
    nothing and cost the line: at ten shared witnesses it rendered ~600 characters of argv,
    which is not a thing anyone pastes. The count it was carrying is stated instead."""
    out = _out()  # 5 killable, all with the SAME witness (1,)
    assert out.count('--input "(1,)"') == 1
    assert "1 distinct — they cover 5 mutant(s)" in out
    assert "SUGGESTED" in out


def test_distinct_witnesses_still_all_batch_into_one_command():
    """Collapsing duplicates must not collapse DIFFERENT calls — each real call still has to
    reach the reader, in one command, or the batch job becomes N sequential rounds again."""
    rep = _rep(
        verdicts=(
            MutantVerdict(
                "K0", "VALUE", "- x\n+ x+1", killable=True, witness=Witness((1,), "1", "2"), searched=5
            ),
            MutantVerdict(
                "K1", "VALUE", "- y\n+ y+1", killable=True, witness=Witness((7,), "7", "8"), searched=5
            ),
        )
    )
    out = _out(survivor_report=rep)
    assert '--input "(1,)"' in out and '--input "(7,)"' in out
    assert "the 2 call(s) above" in out
    assert "distinct — they cover" not in out  # nothing collapsed, so nothing to disclose


# ── batching: --input is repeatable, so name ALL the derived requirements ──
def _boundary(mid: str, n: int) -> MutantVerdict:
    """A real BOUNDARY diff: `weight > n` shifted to `weight >= n`, both whole-function bodies.

    `weight` is one of the proof's declared parameters — issue #8 classifies a
    comparison over a non-parameter as an INTERNAL condition, which is its own kind.

    Operands must MATCH between original and mutant or `_boundary_hint` cannot recover them —
    that is the point of the hint: it derives the equality edge from the comparison whose
    OPERATOR moved, so a fixture that also moves the operand tests nothing.
    """
    orig = f"def f(weight):\n    if weight > {n}:\n        pass"
    mut = f"def f(weight):\n    if weight >= {n}:\n        pass"
    return MutantVerdict(mid, "BOUNDARY", f"- {orig}\n+ {mut}", killable=False, witness=None, searched=9)


def test_every_derived_requirement_is_named_not_just_the_first():
    """`--input` is repeatable and each call kills what it reaches, so N requirements close in
    one command — but only if the report SAYS what they are. Printing next(...) turned a
    batchable job into N sequential rounds and never disclosed that N-1 more existed."""
    rep = _rep(verdicts=(_boundary("B0", 0), _boundary("B1", 5)), inputs_expressible=True)
    out = _out(survivor_report=rep)
    assert "1. where weight == 0" in out
    assert "2. where weight == 5" in out
    # The count is the Task line's job, not argv's: every copy of an UNFILLED template is the
    # same string, so repeating it says nothing the sentence does not, and the reader has to
    # edit each one anyway. What must never regress is that both requirements are NAMED.
    assert "Author 2 call(s)" in out
    assert out.count('--input "(<weight>') == 1


def test_the_batch_cap_is_disclosed_never_silent():
    """A bound that is not named reads as "this is all of them"."""
    many = tuple(_boundary(f"B{i}", i) for i in range(_MAX_BATCH + 4))
    out = _out(survivor_report=_rep(verdicts=many, inputs_expressible=True))
    assert "(+4 more in" in out
    # The cap is disclosed in prose now that the slot is printed once — `_MAX_BATCH`
    # requirements are named in the list, and the remainder is named beside them.
    assert f"Author {_MAX_BATCH} call(s)" in out
    assert out.count('--input "(<weight>') == 1


def test_derive_inputs_returns_data_so_both_surfaces_cannot_drift():
    """The derivation is shared; the RENDERING is not. A human runs `--input "(...)"`, a tool
    caller passes `inputs=["(...)"]` — sharing the rendered string put terminal syntax into an
    MCP response, telling a caller to use a flag that does not exist there."""
    from Detective.cli import _derive_inputs

    kind, items, total = _derive_inputs(_proof(), _rep(verdicts=(_boundary("B0", 0),)))
    assert (kind, items, total) == ("boundary", ["where weight == 0"], 1)
    kind, items, total = _derive_inputs(_proof(), _rep())  # 5 killable, each with a witness
    assert kind == "witness" and items[0] == "(1,)" and total == 5
    kind, items, total = _derive_inputs(_proof(), _rep(verdicts=(), unclassified=("U0",)))
    assert (kind, items, total) == ("author", [], 0)


def test_derive_inputs_untypeable_witness_becomes_test_kind_never_a_command():
    """A captured object (a function a test built) DISTINGUISHES a mutant while
    satisfying no `--input` string ever — `--input` parses literals + ast.*. The
    old behavior rendered its repr as a paste-this command that always errors;
    the derivation now returns kind "test": name the object, ask for a test."""
    from Detective.cli import _derive_inputs

    def _built_by_a_test():  # pragma: no cover — a value, never called
        pass

    untypeable = MutantVerdict(
        "K0",
        "STATE",
        "- return f\n+ return None",
        killable=True,
        witness=Witness((_built_by_a_test,), "'/x_test.py'", "None"),
        searched=5,
    )
    kind, items, total = _derive_inputs(_proof(), _rep(verdicts=(untypeable,)))
    assert kind == "test"
    assert total == 1
    assert "a function" in items[0]
    # A typeable witness alongside it still wins the command path.
    kind, items, total = _derive_inputs(_proof(), _rep(verdicts=(untypeable, _killable("K1"))))
    assert kind == "witness" and items == ["(1,)"] and total == 1


# ── a dark line outranks an equivalent's edge ────────────────────────
def test_uncovered_lines_outrank_a_candidate_equivalents_boundary_edge():
    """With nothing killable left, the only progress available is EXECUTING a line.

    `hints`/`internal` are read off CANDIDATE-EQUIVALENT survivors, so reaching them means
    every killable mutant is already dead. Asking for the edge then cannot move the number:
    the reader supplies it, the run returns byte-identical, and the same request comes back.
    Observed on a real 207-mutant target that sat at 144/207 across three rounds asking for
    `billable == 1` — already satisfied — while seven lines were never executed. A mutant on
    a line that never runs can never die, so coverage is a PRECONDITION for the kill axis."""
    from Detective.cli import _derive_inputs

    proof = _proof(missing_lines=(30, 41), missing_line_guards=((30, "service == 'overnight'"),))
    kind, items, total = _derive_inputs(proof, _rep(verdicts=(_equiv("E0"),)))

    assert kind == "lines"
    assert total == 2
    assert items[0] == "line 30 — reached only when: service == 'overnight'"
    # An unconditional line sits behind no branch; it is still named, because "line 41" is
    # actionable and silence is not.
    assert items[1] == "line 41 — reach it"


def test_a_killable_witness_still_outranks_an_uncovered_line():
    """A witness is a call the engine RAN and saw a mutant differ on — proven progress. The
    line ask exists for when that well is dry, not to displace it."""
    from Detective.cli import _derive_inputs

    proof = _proof(missing_lines=(30,), missing_line_guards=())
    kind, items, _ = _derive_inputs(proof, _rep(verdicts=(_killable("K0"),)))
    assert kind == "witness" and items == ["(1,)"]


def test_a_decompose_proof_carries_no_line_axis_and_is_unchanged():
    """Only converge measures line coverage. A proof without those fields must derive exactly
    as before — the line ask is additive, never a behaviour change for decompose."""
    from Detective.cli import _derive_inputs

    class _NoLines:
        signature, param_names = "", ()

    kind, _, _ = _derive_inputs(_NoLines(), _rep(verdicts=(_equiv("E0"),)))
    assert kind in {"boundary", "internal", "author"}


def test_the_line_ask_names_every_gap_not_just_the_first():
    """`missing_line_guards` was added so a line gap could be closed by the guidance, and it
    reached only the informational row — capped at three — while the ACTION still asked the
    mutant axis. Naming one line of seven is the same failure the guards were added to fix."""
    from Detective.cli import _derive_inputs

    proof = _proof(missing_lines=(30, 40, 41, 42, 43, 45, 46), missing_line_guards=())
    kind, items, total = _derive_inputs(proof, _rep(verdicts=(_equiv("E0"),)))
    assert kind == "lines" and total == 7 and len(items) == 7


def test_the_line_ask_renders_a_runnable_command_and_names_each_condition():
    """The renderer, not just the derivation: one `--input` slot per line so the count of
    slots IS the number of calls to author, and every guard printed verbatim. The block a
    reader pastes has to carry the conditions, because the informational row above it caps
    at three and the report file is the thing they did not open."""
    from Detective.cli import _derived_input

    proof = _proof(
        missing_lines=(30, 45),
        missing_line_guards=((30, "service == 'overnight'"), (45, "hazmat == 'limited'")),
    )
    out = "\n".join(
        _derived_input(
            None,
            proof,
            _rep(verdicts=(_equiv("E0"),)),
            "p.py::quote",
            verb="detective converge 'p.py::quote'",
        )
    )

    command = out.splitlines()[0]
    assert command.startswith("DO THIS:  detective converge 'p.py::quote' --input ")
    assert command.count("--input") == 1  # ONE slot; the count is the Task line's job
    assert "Author 2 call(s)" in out
    assert "line 30 — reached only when: service == 'overnight'" in out
    assert "line 45 — reached only when: hazmat == 'limited'" in out
    # The reason must be in the block: an edge on an equivalent cannot move a dark line.
    assert "Every killable mutant is already dead" in out


# ── the hand-pin remedy, only where it is the remedy ─────────────────
def test_two_plain_values_do_not_get_told_that_equality_cannot_separate_them():
    """It printed `unsound (34.41 vs 33.24 observed — if == cannot tell those apart, pin
    type/repr by hand)`. `==` separates 34.41 from 33.24 perfectly well, so the advice
    contradicted the evidence one line above it. The observed pair still prints; the remedy
    does not."""
    from Detective.cli import _outcome_needs_hand_pin

    assert _outcome_needs_hand_pin("34.41", "33.24") is False

    rep = _rep(
        verdicts=(
            MutantVerdict(
                "K0", "VALUE", "- x\n+ x+1", killable=True,
                witness=Witness((1,), "34.41", "33.24"), searched=5,
            ),
        )
    )
    out = _out(survivor_report=rep)
    assert "34.41 vs 33.24 observed" in out  # the evidence stays
    assert "pin the" not in out and "type/message by hand" not in out


def test_a_raised_outcome_still_gets_the_hand_pin_remedy():
    """Where it IS apt: no return-value assertion reaches an outcome that raised, so the
    reader genuinely has to pin the exception by hand."""
    from Detective.cli import _outcome_needs_hand_pin

    assert _outcome_needs_hand_pin("<raised ValueError: nope>", "None") is True
    assert _outcome_needs_hand_pin("None", "<raised ValueError: nope>") is True
    # Identical reprs too: nothing for `==` to grip.
    assert _outcome_needs_hand_pin("7", "7") is True

    rep = _rep(
        verdicts=(
            MutantVerdict(
                "K0", "EXCEPTION", "- raise A\n+ raise B", killable=True,
                witness=Witness((1,), "<raised ValueError: nope>", "None"), searched=5,
            ),
        )
    )
    out = _out(survivor_report=rep)
    assert "type/message by hand" in out
