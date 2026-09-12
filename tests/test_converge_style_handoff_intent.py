"""Intent tests for the pin->style handoff at converge ✓ COMPLETE (Finding A, revalidation_2026-09-06.md).

The defect: at ✓ COMPLETE, converge's DONE block pointed ONLY to `flag` (when unproven-equivalents
existed) or to a parenthetical "Next (optional): decompose" — never loudly signposting the style half
(`plan` / `decompose` / `survey`). Correctness is DONE at exactly that moment, which is when the style
pass should fire as the self-evident next move. These pin the fix from intent: both DONE branches carry
the loud handoff; the `flag` pointer stays where equivalents exist; and the handoff is CONDITIONAL on
completion (it is structurally only in the settled DONE branches, never in an incomplete/gap render).
"""

from __future__ import annotations

import types

from Detective.cli import _converge_action


def _complete_result():
    # A converge result that reaches the settled DONE branch: complete on every axis, gateable,
    # nothing outstanding -> converge_next_action returns "settled".
    return types.SimpleNamespace(
        function="dsl.py::add",
        functionally_complete=True,
        verification=None,
        line_complete=True,
        missing_lines=(),
        stale_target=False,
        admits_certificate=True,
        written_path="tests/detective/test_dsl_add_synth.py",
        synthesized_only=False,
        environment_gated=(),
    )


def _rep(equivalent):
    return types.SimpleNamespace(
        equivalent=equivalent,
        killable=[],
        unclassified=[],
        inputs_expressible=True,
        load_failed=False,
        note="",
    )


def _has_style_handoff(out: str) -> bool:
    return (
        "NEXT — the style pass" in out
        and "detective plan 'dsl.py'" in out
        and "detective decompose 'dsl.py::add'" in out
        and "detective survey 'dsl.py'" in out
    )


def test_complete_with_equivalents_keeps_flag_and_adds_the_style_handoff():
    rep = _rep([types.SimpleNamespace(mutant_id="ARITHMETIC_x")])
    out = "\n".join(_converge_action(_complete_result(), rep))
    # The flag pointer is correct WHEN unproven-equivalents exist — it must stay.
    assert "detective flag 'dsl.py::add' ARITHMETIC_x" in out
    # ...and the loud style handoff is now ALSO there (it was absent before — Finding A).
    assert _has_style_handoff(out)


def test_complete_without_equivalents_shows_the_loud_handoff_not_the_optional_parenthetical():
    out = "\n".join(_converge_action(_complete_result(), _rep([])))
    assert _has_style_handoff(out)
    # The old undersell — a parenthetical "(optional)" pointing only at decompose — is gone.
    assert "Next (optional)" not in out


def test_the_handoff_names_the_whole_second_beat_including_efficiency():
    out = "\n".join(_converge_action(_complete_result(), _rep([])))
    # plan (the map), decompose (act), survey (find more), and verify-rewrite --budget (efficiency).
    assert "detective plan" in out
    assert "detective decompose" in out
    assert "detective survey" in out
    assert "verify-rewrite" in out
    assert "--budget" in out
