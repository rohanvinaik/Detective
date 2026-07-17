"""Tests for the MCP decompose RESIDUAL contract — the agent-facing hand-back.

Hand-written native (rich frozen dataclasses; same sanctioned exemption as
test_cli_converge_output_native.py). ``mcp`` is NOT needed: the renderers are plain
functions and the package is imported lazily inside ``build_server``.

Why this file exists. ``mcp_server.py`` already carries the principle, at the top of this
very function: "The four causes of 'unproven' are NOT interchangeable... Collapsing them
is how a caller gets told to supply an input for a hole that does not exist — and then
goes looking for why its input 'didn't work'." That was honoured for the four CAUSES and
then broken for the three POPULATIONS inside one of them: the residual rendered
``final_survivors`` — killable + unclassified + candidate-equivalent fused — and demanded
one input to close all of them. An input cannot close a candidate-equivalent; no input
distinguishes one, which is what the classification MEANS. So the number did not move when
an input WAS supplied, the identical demand re-emitted, and the caller did exactly what the
comment predicts: supplied input after input, then went looking for why they "didn't work".

The gate reads `not killable and not unclassified` (converge.py). Count that, or the agent
reads the total as its backlog and chases mutants nothing can ever kill.
"""

from __future__ import annotations

from Detective.converge import ConvergeResult
from Detective.decompose_apply import Decomposition, DecompositionApply, Extraction
from Detective.equivalence import MutantVerdict, SurvivorReport, Witness
from Detective.mcp_server import _render_decompose


def _killable(mid: str) -> MutantVerdict:
    return MutantVerdict(
        mid, "VALUE", "- x\n+ x+1", killable=True, witness=Witness((1,), "1", "2"), searched=5
    )


def _equiv(mid: str) -> MutantVerdict:
    return MutantVerdict(mid, "BOUNDARY", "- >\n+ >=", killable=False, witness=None, searched=14)


def _proof(**over) -> ConvergeResult:
    base = dict(
        function="p.py::quote",
        converged=False,
        at_ceiling=True,
        initial_survivors=69,
        # The fused total the renderer used to print — deliberately != the blocking count,
        # so a regression to `final_survivors` fails loudly instead of reading plausibly.
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
        survivor_report=SurvivorReport(
            tuple(_killable(f"K{i}") for i in range(5)) + tuple(_equiv(f"E{i}") for i in range(17)),
            (),
        ),
    )
    base.update(over)
    return ConvergeResult(**base)


def _result(proof: ConvergeResult | None) -> DecompositionApply:
    ex = Extraction("_compute_base", ("weight",), ("base",), "def _compute_base(weight):\n    return 1\n")
    return DecompositionApply("quote", (), (Decomposition(ex, validated=False),), (), proof=proof)


def _out(**over) -> str:
    return _render_decompose(_result(_proof(**over)), "p.py", "quote", False)


def test_residual_counts_only_the_blocking_population():
    """5 killable block. 17 candidate-equivalent do not. The old renderer demanded 22."""
    out = _out()
    assert "5 behaviour(s) block the proof" in out
    assert "22 behaviour(s)" not in out


def test_residual_tells_the_agent_the_equivalents_are_not_its_work():
    """The load-bearing line. Without it the agent reads the total as a backlog and burns
    itself on mutants no input can ever move — the failure this whole surface exists to stop."""
    out = _out()
    assert "17 survivor(s) are candidate-equivalent" in out
    assert "do NOT block" in out
    assert "not your work" in out


def test_residual_splits_killable_from_unclassified():
    """Different causes: a killable mutant HAS a witness; an unclassified one could not be
    searched at all. One number for both hides which fix applies."""
    out = _out(survivor_report=SurvivorReport((_killable("K0"),), ("U0", "U1")))
    assert "3 behaviour(s) block the proof" in out
    assert "1 killable" in out and "2 unclassified" in out


def test_residual_abstains_when_classification_did_not_run():
    """No classification means WHICH ones block is unknown. Naming a population there would
    invent a fact the engine declined to produce."""
    out = _out(survivor_report=None)
    assert "classification did not run" in out
    assert "block the proof" not in out


def test_residual_never_says_source_was_touched():
    """The agent's first question is always "did it write?". Unproven never writes."""
    assert "Your source was NOT touched." in _out()


def test_mutation_complete_rejection_is_a_verdict_not_a_residual():
    """A complete suite that rejects has PROVEN behaviour changed. Asking for an input there
    sends the agent to close a hole that does not exist."""
    out = _out(functionally_complete=True)
    assert "STOP." in out
    assert "block the proof" not in out


# ── the hand-back must be a call the caller can actually make ────────
def _ask(expressible):
    from Detective.mcp_server import _ask_for_input

    return "\n".join(
        _ask_for_input("converge", "p.py", "settle", ("account", "charges"), "why.", expressible)
    )


def test_typeable_params_get_the_inputs_call():
    out = _ask(True)
    assert "converge(file='p.py', function='settle', inputs=[" in out
    assert "<account>, <charges>" in out


def test_untypeable_params_get_a_test_never_an_inputs_call():
    """THE regression, on the surface an agent actually uses. `inputs=` goes through the same
    allowlist as the CLI's `--input` (literals + `ast.*`), so for a domain object no string
    satisfies it and the call is rejected on arrival. A caller that does exactly what it was
    told, watches it fail, and is told the same thing again does not conclude it misread — it
    concludes the tool is broken and improvises around it."""
    out = _ask(False)
    assert "inputs=[" not in out
    assert "write ONE test that calls settle(account, charges)" in out
    assert "no literal form" in out


def test_none_expressible_is_not_treated_as_typeable():
    """None means NOTHING exercised the function — the case that most needs a test. A truthy
    check must not let it fall through to the `inputs=` branch."""
    assert "inputs=[" not in _ask(None)


def test_the_test_handback_forbids_the_workarounds_by_name():
    """A caller told only "you cannot pass it" invents a way to pass it anyway."""
    out = _ask(False)
    for forbidden in ("Do not encode the object as a dict", "Do not shell out"):
        assert forbidden in out


# ── a capped sample is not a count ───────────────────────────────────
def test_diagnose_reports_the_dof_not_the_capped_sample():
    """`unspecified_behaviors` is hard-capped at scope._MAX_UNSPECIFIED (20);
    `specification.unspecified_dof` is the fact. Rendering len() of the sample stated 20 for a
    71-DOF function — and a caller cannot see a cap, so it reads as the whole list, closes
    "all 20", reports done, and 51 unpinned behaviours are gone. A bound that is not named is
    a silent truncation wearing a finding's clothes."""
    from Detective.mcp_server import _render_diagnose
    from Detective.scope import KillQuality, ScopeMap, Specification

    scope = ScopeMap(
        function="m.py::f",
        regime="A",
        surviving_categories=["VALUE"],
        specification=Specification(
            behavioral_variants=71,
            distinctions_pinned=0,
            unspecified_dof=71,
            inert_freedom=0,
            sigma_proxy_teaching_set=0,
        ),
        kill_quality=KillQuality(by_value_assertion=0, by_crash=0, warning=None),
        behavioral_dof=[],
        unspecified_behaviors=[f"VALUE_{i}: off-by-one comparison" for i in range(20)],
        tests_discovered=3,
    )
    out = _render_diagnose(scope, "m.py", "f")
    assert "71 behaviour(s) nothing distinguishes" in out
    assert "20 behaviour(s) nothing distinguishes" not in out
    assert "sample of 20" in out  # the cap is NAMED, never silent
