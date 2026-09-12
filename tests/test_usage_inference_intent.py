"""Intent tests (the SPEC, before the code) for USAGE-BASED param type inference — the sibling of
call-site inference (`infer_param_types`) that recovers an unannotated param's type from how the
target uses it in its OWN body. Surfaced by the follow-graph dogfood: GofL `Game.update_cell(step,
xy)` indexes `step[xy[0], xy[1]]` — a tuple subscript no list/str/dict accepts — so `step` is an
ndarray, which call-site inference misses (its call site passes a pass-through local).

TWO safety bars, by consumer (the founder's point + its sharpening):
  * converge SYNTHESIS runs the fabricated value, so a wrong guess is disposed by the soundness gate —
    it could afford low-confidence guesses. v1 does NOT rely on that; it emits only high-confidence.
  * survey is ADVISORY (no run to dispose), so it may consume ONLY high-confidence inferences.
v1 therefore emits a type ONLY when the usage is high-precision (a tuple subscript, an ndarray
attribute, a str method); everything ambiguous returns "" — no guess. Low-confidence numeric/iterable
inference is a later converge-synthesis-only extension, deliberately out of scope here.
"""

from __future__ import annotations

import ast

from Detective.call_sites import _param_usages, usage_evidence_class, usage_inferred_type

# ------------------------------------------------------------------ usage_inferred_type (pure decision)


def test_a_tuple_subscript_also_accepts_a_literal_dictionary():
    assert {(0, 0): 7}[0, 0] == 7
    assert usage_inferred_type(("subscript", "subscript_tuple")) == ""


def test_array_attributes_mean_ndarray():
    assert usage_inferred_type(("attr:shape",)) == "ndarray"
    assert usage_inferred_type(("attr:dtype",)) == "ndarray"
    assert usage_inferred_type(("call:reshape",)) == "ndarray"


def test_str_methods_mean_str():
    assert usage_inferred_type(("call:lower",)) == "str"
    assert usage_inferred_type(("call:split",)) == "str"
    assert usage_inferred_type(("call:startswith",)) == "str"


def test_ambiguous_or_empty_usage_is_no_guess():
    # A plain subscript could be list OR dict OR ndarray; arithmetic could be int/float/ndarray;
    # comparison says nothing. v1 refuses to guess rather than cry wolf. "" means "unknown".
    assert usage_inferred_type(()) == ""
    assert usage_inferred_type(("subscript",)) == ""
    assert usage_inferred_type(("arith",)) == ""
    assert usage_inferred_type(("compare", "iter")) == ""
    assert usage_inferred_type(("subscript", "subscript_int")) == ""  # p[0] — list-like, not tuple idx


def test_ambiguous_subscript_does_not_override_a_method_signal():
    assert usage_inferred_type(("subscript_tuple", "call:split")) == "str"


# ------------------------------------------------------------------ _param_usages (AST extractor)


def _fn(src: str) -> ast.FunctionDef:
    return next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef))


def test_extracts_tuple_subscript_for_the_gofl_shape():
    fn = _fn("def update_cell(step, xy):\n    return step[xy[0], xy[1]]\n")
    tags = set(_param_usages(fn, "step"))
    assert "subscript" in tags
    assert "subscript_tuple" in tags


def test_the_index_param_is_not_mistaken_for_an_array():
    # `xy[0]` / `xy[1]` are INT subscripts, not tuple subscripts — xy must not read as an ndarray.
    fn = _fn("def update_cell(step, xy):\n    return step[xy[0], xy[1]]\n")
    assert usage_inferred_type(_param_usages(fn, "xy")) != "ndarray"


def test_extracts_str_method_calls():
    fn = _fn("def s2b(v):\n    return v.lower() in ('yes', 'no')\n")
    assert "call:lower" in set(_param_usages(fn, "v"))


def test_extracts_array_attribute_access():
    fn = _fn("def f(a):\n    return a.shape[0]\n")
    assert "attr:shape" in set(_param_usages(fn, "a"))


def test_plain_arithmetic_yields_only_low_signal_tags():
    fn = _fn("def f(n):\n    return n + 1\n")
    assert usage_inferred_type(_param_usages(fn, "n")) == ""


# ------------------------------------------------------------------ integration: the two dogfood shapes


def test_gofl_update_cell_step_is_unresolved_not_inferred_and_not_silent():
    """RENAMED 2026-09-08. This was `test_gofl_update_cell_step_infers_ndarray` while asserting
    `== ""` — the name claimed the capability worked, the body pinned that it does not, and anyone
    reading the test list concluded the opposite of the truth. That is how the R4 regression stayed
    invisible through a whole audit wave.

    Both halves are the intent now. `usage_inferred_type` must NOT name a type — a tuple-keyed dict
    accepts `p[i, j]` exactly as an ndarray does, and inferring from it was unsound. AND the
    evidence must not read as absent: `unresolved_object` is what distinguishes "we cannot resolve
    this" from "there is nothing here", which is the distinction the two-valued result destroyed."""
    fn = _fn("def update_cell(step, xy):\n    return step[xy[0], xy[1]]\n")
    usages = _param_usages(fn, "step")
    assert usage_inferred_type(usages) == "", "a tuple subscript must not name a type"
    assert usage_evidence_class(usages) == "unresolved_object", "nor may it read as no evidence"


def test_str2bool_v_infers_str():
    fn = _fn("def s2b(v):\n    if v.lower() in ('yes',):\n        return True\n    return False\n")
    assert usage_inferred_type(_param_usages(fn, "v")) == "str"
