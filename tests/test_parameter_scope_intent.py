"""Intent tests for the no-parameters / unknown-parameters distinction (Detective #8).

`None` and `()` mean OPPOSITE things when deciding whether a residual can be handed back as an
input recipe, and three call sites fused them with `param_names or None`.

  ()    the function takes NO parameters — a FACT, and the strongest possible evidence that a
        comparison over named locals is an internal condition, because there is no parameter it
        could be
  None  not supplied — nothing is known, so no classification is possible

The collapse sent the certain case down the uncertain path. `param_names=None` is the one value
that skips both #8 guards and restores the pre-#8 rendering, so a function with no parameters —
the case where abstention is most certainly correct — received the confident answer: "supply an
input where risk > 4", for a function that accepts no input.

TRUTHINESS IS WHAT HID IT. `()` and `None` are both falsy, so `or None` reads as a harmless
normalisation at every one of the three sites.

MEASURED, on a zero-parameter target:

    DO THIS:  detective converge 'src/n.py::status' --input "(<value>,)"
    · Signature          status()

Two lines apart: an input recipe, and the signature proving no input exists. That second defect
was found only by running the fixed code end to end — it lives in `_input_template`, a sibling
of the function being fixed, and shares the identical falsy-collapse.
"""

from __future__ import annotations

from Detective.cli import _input_template, parameter_scope


def test_no_parameters_is_a_fact_not_an_absence():
    """The whole bug in one assertion."""
    assert parameter_scope(()) == "none"
    assert parameter_scope(None) == "unknown"
    assert parameter_scope(()) != parameter_scope(None)


def test_a_real_parameter_list_is_known():
    assert parameter_scope(("weight",)) == "known"
    assert parameter_scope(("a", "b")) == "known"


def test_a_zero_parameter_target_gets_no_input_recipe():
    """There is no literal that reaches a residual in a function with no inputs.

    A pasteable recipe here is a false hand-back: the reader supplies it, the value goes
    nowhere, and the residual is unchanged.
    """
    assert _input_template(()) == ""


def test_an_unknown_parameter_list_still_gets_the_generic_placeholder():
    """The fix must not overcorrect. Not-supplied is not the same fact as no-parameters, and
    only the latter licenses abstention — silently abstaining on `None` would remove a working
    hand-back from every caller that does not thread the names through."""
    assert _input_template(None) == '--input "(<value>,)"'


def test_a_known_parameter_list_gets_named_slots():
    assert _input_template(("weight",)) == '--input "(<weight>,)"'
    assert _input_template(("a", "b")) == '--input "(<a>, <b>)"'


def test_the_empty_and_unknown_templates_are_not_interchangeable():
    """The regression guard: any future `or None` / `or ()` normalisation breaks this."""
    assert _input_template(()) != _input_template(None)
