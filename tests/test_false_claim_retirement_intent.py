"""Intent tests for R2 — retire two claims the renderers asserted without deriving.

Design: `docs/CORRECTNESS_REPAIRS_2026-09-08.md` §R2, §R5, §R5b.

Both defects are the same shape: a sentence that is TRUE in the common case, hardcoded, and
therefore also emitted in the cases where it is false. Neither was a logic error — the renderers
held the data that contradicts them.

R2a — `_derived_input`'s "lines" branch printed, as a string literal:

    · Why    Every killable mutant is already dead. What is left is ...

True on arc-dsl. False on conorheins `str2bool`, where the module could not import so
classification never ran: `0/27 killed`, `0 pinned`, and `⚠ unclassified 27 — the search could
not run on them` printed TWO ROWS ABOVE the claim, from the same report the renderer already had.

S3/R5 — both converge and audit rendered:

    · unproven-equiv   N survivor(s) — no input distinguishes them

A claim about ALL inputs, asserted from a BOUNDED search, while converge's own DONE block scoped
the identical fact correctly ("any input Detective FOUND"). Measured false on
`Detective/cli.py::outcome_disposition`: ✓ COMPLETE modulo 4 unproven-equivalent, and four
literal inputs killed all four.
"""

from __future__ import annotations

import ast
import pathlib
import types

from Detective.cli import (
    _UNPROVEN_EQUIV_BASIS,
    _derived_input,
    line_gap_rationale,
    line_gap_why,
)

# ---------------------------------------------------------------- R2a: the derived Why


def _rep(unclassified=(), killable=()):
    return types.SimpleNamespace(
        equivalent=[],
        killable=list(killable),
        unclassified=list(unclassified),
        inputs_expressible=True,
        load_failed=False,
        note="",
    )


def _gap_result():
    return types.SimpleNamespace(
        function="m.py::f",
        functionally_complete=False,
        verification=None,
        line_complete=False,
        final_survivors=2,
        missing_lines=(7, 9),
        signature="f(a, b)",
        param_names=("a", "b"),
        stale_target=False,
        admits_certificate=True,
        written_path="tests/detective/test_m_f_synth.py",
        synthesized_only=False,
        environment_gated=(),
    )


def test_an_unfinished_classification_never_claims_the_killables_are_dead():
    """THE conorheins case. `unclassified` and the claim came from the same object; the renderer
    simply never asked."""
    assert line_gap_rationale(unclassified=27, killable=0) == "classification_incomplete"


def test_an_open_killable_gap_is_not_reported_as_nothing_left_to_kill():
    assert line_gap_rationale(unclassified=0, killable=3) == "killable_remain"


def test_the_original_claim_survives_where_it_was_earned():
    """This is not a retraction. Where classification finished and nothing killable remains, the
    sentence was correct and must still be said — the repair is that it is now DERIVED."""
    assert line_gap_rationale(unclassified=0, killable=0) == "every_killable_dead"


def test_an_unfinished_classification_outranks_the_killable_count():
    """If the classifier did not finish, the killable count is itself untrustworthy. Reporting
    'a killable remains' from an incomplete classification states more than was measured."""
    assert line_gap_rationale(unclassified=5, killable=5) == "classification_incomplete"


def test_the_three_rationales_are_distinguishable():
    assert len({line_gap_rationale(27, 0), line_gap_rationale(0, 3), line_gap_rationale(0, 0)}) == 3


def test_the_rendered_why_does_not_assert_dead_killables_when_none_was_measured():
    """End-to-end through the renderer, not just the decision: the output an operator actually
    reads must not carry the false sentence."""
    out = "\n".join(_derived_input(None, _gap_result(), _rep(unclassified=[1, 2, 3]), "m.py::f"))
    assert "Every killable mutant is already dead" not in out
    assert "UNKNOWN" in out


def test_the_rendered_why_still_says_it_when_it_is_true():
    out = "\n".join(_derived_input(None, _gap_result(), _rep(), "m.py::f"))
    assert "Every killable mutant is already dead" in out


# ------------------------------------------------ line_gap_why: a HAND truth table, on purpose
#
# `detective converge` REFUSES this function: ⚠ UNGATEABLE, cut_reasons ["mutant_evaluation_failed"],
# stably, with and without supplied --inputs. That refusal is the tool working, and a pin is not
# faked around it — the project's rule is to say so and write ordinary tests instead.
#
# It is also a finding in its own right (docs §S13): `normalize_validity` collapses three distinct
# reasons — harness_error, not_installed, not_entered — into one `evaluation_failed` flag rendered
# as "the harness failed". An operator cannot tell from that whether to repair a harness, install
# something, or close a coverage gap. `measurement_cut_reasons` (§S5) refuses for the same reason,
# which is why the function that decides what refuses a certificate cannot earn one.


def test_every_rationale_has_its_own_sentence():
    """One owner per state — the whole point of extracting this. Three states, three distinct
    sentences, none of them empty."""
    sentences = {
        r: line_gap_why(r) for r in ("classification_incomplete", "killable_remain", "every_killable_dead")
    }
    assert len(set(sentences.values())) == 3
    assert all(s.strip() for s in sentences.values())


def test_the_incomplete_sentence_says_unknown_rather_than_asserting_either_way():
    s = line_gap_why("classification_incomplete")
    assert "UNKNOWN" in s
    assert "already dead" not in s


def test_the_earned_sentence_is_preserved_verbatim():
    """The repair derives the claim; it does not reword the case where it was true."""
    assert line_gap_why("every_killable_dead").startswith("Every killable mutant is already dead")


def test_an_unknown_rationale_is_named_not_blank():
    """A blank Why beside an input request reads as 'no reason' — the shape this whole repair
    exists to remove, so the fallback must not reintroduce it."""
    s = line_gap_why("some_future_state")
    assert s.strip()
    assert "some_future_state" in s


def test_each_sentence_survives_the_split_the_renderer_does():
    """The caller does `.split("\\n")` and maps to rows; an empty trailing line would render a
    blank row under the Why."""
    for r in ("classification_incomplete", "killable_remain", "every_killable_dead"):
        assert all(line.strip() for line in line_gap_why(r).split("\n"))


# ---------------------------------------------------------------- S3: the bounded-search basis


def test_the_equivalence_row_does_not_claim_anything_about_all_inputs():
    """`no input distinguishes them` quantifies over every input. The search is bounded, and
    R5b showed four such survivors killed by four literal inputs."""
    assert "no input distinguishes" not in _UNPROVEN_EQUIV_BASIS
    assert "search" in _UNPROVEN_EQUIV_BASIS


def test_no_renderer_reintroduces_the_unbounded_claim():
    """A property of the MODULE, not of one call site. The claim lived at two render sites that
    could drift; this fails if a third appears, which is how the first two happened."""
    tree = ast.parse(pathlib.Path("Detective/cli.py").read_text())
    offenders = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and "no input distinguishes them" in node.value
    ]
    assert offenders == [], f"the unbounded claim reappeared at cli.py lines {offenders}"
