"""A one-shot iterator return is observed by CONTENT, never by object repr (address).

funcy dogfood: `where` returns a `filter`, `pluck` a `map`. Converge compared the raw iterator
OBJECTS by repr — `<filter object at 0x1109c160>` — so two behaviourally-identical results 'differed'
only by address and a mutant manufactured a witness no test could ever pin, while a real content
difference could never be declared equivalent either. `_observe` consumes a bounded prefix: an
exhausted iterator is pinnable exactly, a differing prefix is a real kill, and an equal TRUNCATED
prefix is UNKNOWN — never falsely equivalent on a long / infinite generator. `_pair_disposition`
enforces that last rule. A re-iterable container (list/str/dict) is untouched — its repr is stable.
"""

from __future__ import annotations

import itertools

from Detective.equivalence import _observe, _pair_disposition


def test_a_reiterable_container_is_repr_unchanged():
    # list / str / dict: `iter(x)` is a NEW iterator, so `iter(x) is x` is False and repr is used.
    assert _observe([1, 2, 3]) == repr([1, 2, 3])
    assert _observe("ab") == repr("ab")
    assert _observe({"a": 1}) == repr({"a": 1})
    assert _observe(42) == repr(42)


def test_a_one_shot_iterator_is_observed_by_content_not_address():
    a = _observe(filter(None, [1, 2, 0, 3]))  # 0 is falsy -> yields 1, 2, 3
    b = _observe(filter(None, [1, 2, 0, 3]))
    assert "0x" not in a  # no memory address survives into the outcome
    assert a == b  # two equal results observe EQUAL, where their raw reprs would differ by address
    assert a == "<iter filter exhausted ['1', '2', '3']>"


def test_equal_iterator_contents_are_the_same_outcome():
    assert _pair_disposition(_observe(map(str, [1, 2, 3])), _observe(map(str, [1, 2, 3]))) == "same"


def test_a_differing_iterator_prefix_is_a_real_kill():
    orig = _observe(map(str, [1, 2, 3]))
    mut = _observe(map(str, [1, 2, 4]))
    assert orig != mut
    assert _pair_disposition(orig, mut) == "witness"


def test_an_equal_truncated_prefix_is_unknown_never_equivalent():
    # Two infinite generators sharing an identical observed prefix must NOT be called equivalent —
    # their suffixes past the bound are unobserved, so 'same' would be a false certificate.
    o = _observe(itertools.count())
    m = _observe(itertools.count())
    assert o.startswith("<iter~trunc")
    assert o == m
    assert _pair_disposition(o, m) == "blocked"  # UNKNOWN, not "same"


def test_a_differing_truncated_prefix_is_still_a_kill():
    o = _observe(itertools.count(0))
    m = _observe(itertools.count(1))
    assert o != m
    assert _pair_disposition(o, m) == "witness"


def test_an_iterator_that_raises_during_iteration_is_its_own_outcome():
    def boom():
        yield 1
        raise ValueError("boom")

    out = _observe(boom())
    assert out.startswith("<iter generator raised@1 ValueError")
