"""Intent tests for R4 — "unresolved" is a third answer, not a shade of silence.

Design: `docs/CORRECTNESS_REPAIRS_2026-09-08.md` §R4.

v1 inferred `ndarray` from a tuple subscript. That is unsound — a tuple-keyed dict accepts
`p[i, j]` exactly as an ndarray does — and the 2026-09-07 wave was right to stop. What it did not
do is give the case anywhere else to go, so GofL `Game.update_cell` / `count_neighbors` fell from
`extractable_core` straight to `reachable`: the same silence as a plain `int`. Removing an unsound
CLAIM was correct; sending the parameter to silence was the regression.

The failure this file guards against is symmetric, and BOTH directions matter:

* under-reporting — an object-shaped param reads as clean, and a real trapped decision is invisible
  (the observed regression);
* over-reporting — `unresolved` gets rendered as a finding, which is the cry-wolf the wave removed,
  earned back with extra steps. The headline and prose must claim only what is known.
"""

from __future__ import annotations

import ast

from Detective.call_sites import _param_usages, usage_evidence_class, usage_inferred_type
from Detective.survey import render_survey, survey_disposition, survey_source


def _fn(src: str) -> ast.FunctionDef:
    return ast.parse(src).body[0]  # type: ignore[return-value]


_GOFL = """
class Game:
    def update_cell(self, step, xy):
        if step[xy[0], xy[1]] == 1:
            return 1
        return 0
    def plain(self, a, b):
        return a + b
    def indexed(self, seq):
        return seq[0]
"""


# ---------------------------------------------------------------- the evidence class


def test_ambiguous_evidence_and_absent_evidence_are_different_answers():
    """THE repair. Both used to be `""`."""
    tuple_sub = _param_usages(_fn("def f(p, i, j):\n    return p[i, j]\n"), "p")
    arithmetic = _param_usages(_fn("def f(n):\n    return n + 1\n"), "n")
    assert usage_evidence_class(tuple_sub) == "unresolved_object"
    assert usage_evidence_class(arithmetic) == "none"


def test_a_resolved_signal_is_still_resolved():
    assert usage_evidence_class(("attr:shape",)) == "resolved"
    assert usage_evidence_class(("call:lower",)) == "resolved"


def test_the_unsound_inference_stays_removed():
    """Not a revert. A tuple subscript must still NOT name a type — the dict counterexample is
    real, and re-inferring ndarray here would undo a correct fix."""
    assert usage_inferred_type(("subscript", "subscript_tuple")) == ""


def test_a_resolved_signal_outranks_an_ambiguous_one():
    """`p[i, j]` alongside `p.lower()` is a str being subscripted, not an open question."""
    assert usage_evidence_class(("subscript_tuple", "call:lower")) == "resolved"


def test_only_the_tuple_subscript_opens_the_question():
    """Scoped deliberately. Every widening is a fresh chance to cry wolf on an advisory surface
    with no run to dispose a wrong guess, so v1 admits exactly the one signal the regression was
    about."""
    for tags in (("subscript",), ("subscript", "subscript_int"), ("arith",), ("compare", "iter"), ()):
        assert usage_evidence_class(tags) == "none", tags


# ---------------------------------------------------------------- the disposition


def test_unresolved_ranks_below_every_proven_block():
    """It is weaker evidence than any of them, and must never displace a proven finding."""
    assert survey_disposition(True, False, False, True) == "extractable_core"
    assert survey_disposition(False, True, False, True) == "impure_body"
    assert survey_disposition(False, False, True, True) == "trapped_by_imports"


def test_unresolved_ranks_above_silence():
    assert survey_disposition(False, False, False, True) == "unresolved_param"
    assert survey_disposition(False, False, False, False) == "reachable"


def test_the_default_preserves_every_existing_caller():
    """#60 in the small: a caller that does not supply the new signal behaves exactly as before."""
    assert survey_disposition(False, False, False) == "reachable"


# ---------------------------------------------------------------- end to end, and the honesty of it


def test_the_gofl_shape_is_visible_again():
    """The regression, stated as the behaviour that must hold."""
    flagged = {f.qualname: f.disposition for f in survey_source(_GOFL)}
    assert flagged.get("Game.update_cell") == "unresolved_param"


def test_expressible_params_are_still_silent():
    """The false-positive half. A plain `a + b` and a plain `seq[0]` are ordinary primitives; the
    survey must not start flagging them because it gained a new state to flag things with."""
    flagged = {f.qualname for f in survey_source(_GOFL)}
    assert "Game.plain" not in flagged
    assert "Game.indexed" not in flagged


def test_an_annotated_param_is_never_unresolved():
    """An annotation IS an answer. Whatever it says, the question is closed."""
    src = "class G:\n    def m(self, step: dict, xy):\n        return step[xy[0], xy[1]]\n"
    assert not any(f.disposition == "unresolved_param" for f in survey_source(src))


def test_the_headline_does_not_call_an_unresolved_param_a_trapped_decision():
    """The over-reporting guard. Counting these as "trapped pure decisions" would assert precisely
    what unresolved means we do not know — the cry-wolf the tuple inference was removed for,
    re-earned in the summary line."""
    out = "\n".join(render_survey("game.py", list(survey_source(_GOFL))))
    assert "unresolved param(s)" in out
    assert "trapped pure decision(s)" not in out
    assert "hide a pinnable pure decision" not in out
    assert "the question is open" in out
