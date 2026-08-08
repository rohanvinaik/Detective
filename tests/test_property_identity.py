"""A property's identity is what it ASSERTS, under what setup, about which obligation (#61).

Accumulation across convergence passes was keyed on `assertion_code` alone. Two properties
whose assertion text matches but whose setup, inputs, preconditions or intended mutant differ
are different obligations — and the second was dropped as a duplicate, silently unpinning a
real behaviour because its assertion happened to read the same.

It must also not be positional. Generated test names (`test_f_value_0`, `_value_1`, …) and
pytest's parameter ids shift the moment a property is inserted or removed, so anything keyed on
order renames the survivors of an edit and makes two runs incomparable.

And it must EXCLUDE provenance. Confidence and source lenses say how well we believe a property
and where it came from, not what it claims; folding them in would accumulate the same behaviour
twice with two tests that can never disagree.
"""

from __future__ import annotations

from Detective.synthesis.oracle_light import (
    ExecutableProperty,
    property_id,
    property_identity,
)


def _prop(**over) -> ExecutableProperty:
    base = dict(
        category="VALUE",
        inputs=(1,),
        setup_code="obj = Counter()",
        assertion_code="assert f(1) == 2",
        preconditions=(),
        confidence=0.9,
        function_key="m.py::f",
        mutant_id="VALUE_abc",
    )
    base.update(over)
    return ExecutableProperty(**base)


def test_the_same_assertion_under_different_setup_is_a_different_obligation():
    """THE defect. Same text, different receiver — one of these was dropped as a duplicate."""
    a = _prop(setup_code="obj = Counter()")
    b = _prop(setup_code="obj = Counter(start=5)")
    assert property_identity(a) != property_identity(b)


def test_the_same_assertion_on_different_inputs_is_a_different_obligation():
    assert property_identity(_prop(inputs=(1,))) != property_identity(_prop(inputs=(2,)))


def test_the_same_assertion_for_a_different_mutant_is_a_different_obligation():
    """The obligation a property exists to discharge is part of what it IS. Two tests that read
    identically but pin different mutants are two pins, not one."""
    a, b = _prop(mutant_id="VALUE_abc"), _prop(mutant_id="LOGICAL_xyz")
    assert property_identity(a) != property_identity(b)


def test_different_preconditions_are_a_different_obligation():
    assert property_identity(_prop(preconditions=())) != property_identity(_prop(preconditions=("n > 0",)))


def test_argument_order_is_not_normalised_away():
    """`f(1, 2)` and `f(2, 1)` are different calls. A set-like canonicalisation of inputs would
    fuse them and pin only one."""
    assert property_identity(_prop(inputs=(1, 2))) != property_identity(_prop(inputs=(2, 1)))


def test_identical_semantics_give_one_identity():
    """The control. Regeneration must recognise a property as the SAME obligation across passes,
    which is the entire reason accumulation works at all."""
    assert property_identity(_prop()) == property_identity(_prop())


def test_provenance_is_not_identity():
    """Confidence and lenses are how well we believe it and where it came from. Folding them in
    would accumulate one behaviour twice, with two tests that can never disagree."""
    assert property_identity(_prop(confidence=0.9)) == property_identity(_prop(confidence=0.4))
    assert property_identity(_prop(source_lenses=("a",))) == property_identity(
        _prop(source_lenses=("b", "c"))
    )


def test_the_identity_is_not_an_ordinal():
    """Position must not appear anywhere in it: an id that moved when a neighbour was inserted
    would rename every survivor of an edit."""
    props = [_prop(inputs=(i,)) for i in range(3)]
    first = [property_identity(p) for p in props]
    second = [property_identity(p) for p in reversed(props)]
    assert set(first) == set(second)
    assert len(set(first)) == 3


def test_field_boundaries_cannot_be_forged():
    """Fields are joined on a NUL, which cannot occur in Python source or a repr — so no
    combination of values can impersonate the boundary between two others and collide."""
    a = property_id("m.py::f", "VALUE", "ab", "c", "", "", "")
    b = property_id("m.py::f", "VALUE", "a", "bc", "", "", "")
    assert a != b
