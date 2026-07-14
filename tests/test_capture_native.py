"""Tests for Detective.capture — runtime harvest of real argument tuples.

Engine-core: ``capture_call_inputs`` takes a live function and live test callables,
which converge cannot synthesize as ``--input`` (a code object is not literal-
eval'able), so it is guarded by this unit suite — the sanctioned exemption to the
converge-generate discipline (mirrors test_equivalence_native.py). Plain module-
level callables, no fixtures. The end-to-end proof is a converge run over a
domain-object function whose covering tests pass objects no grid can fabricate.
"""

from __future__ import annotations

from Detective.capture import capture_call_inputs


class _Entity:
    """A domain object no integer grid can fabricate — the case the harvest exists for."""

    def __init__(self, rank: int) -> None:
        self.rank = rank

    def __repr__(self) -> str:
        return f"_Entity({self.rank})"


def _outranks(censor, candidate):
    return candidate.rank > censor.rank


def test_harvests_real_object_args_the_covering_tests_pass():
    def t_a():
        assert _outranks(_Entity(1), _Entity(2)) is True

    def t_b():
        assert _outranks(_Entity(5), _Entity(2)) is False

    got = capture_call_inputs(_outranks, [t_a, t_b])
    assert len(got) == 2
    # the captured tuples are the REAL objects — re-invoking reproduces the outcome
    assert all(isinstance(a, _Entity) and isinstance(b, _Entity) for a, b in got)
    assert _outranks(*got[0]) is True
    assert _outranks(*got[1]) is False


def test_empty_when_tests_never_reach_the_target():
    def other():
        return 1

    def t_unrelated():
        assert other() == 1

    assert capture_call_inputs(_outranks, [t_unrelated]) == []


def test_dedups_by_value_and_caps_at_max_samples():
    def target(a):
        return a

    def t_repeat():
        for _ in range(50):
            target(7)  # same value every call → one deduped tuple

    assert capture_call_inputs(target, [t_repeat], max_samples=3) == [(7,)]


def test_distinct_values_capped_at_max_samples():
    def target(a):
        return a

    def t_many():
        for i in range(20):
            target(i)

    got = capture_call_inputs(target, [t_many], max_samples=4)
    assert got == [(0,), (1,), (2,), (3,)]


def test_swallows_a_failing_test_but_keeps_the_input_it_passed():
    def target(a):
        return a

    def t_boom():
        target(9)
        raise ValueError("boom")  # the harvest wants the input, not the verdict

    assert capture_call_inputs(target, [t_boom]) == [(9,)]


def test_no_code_object_returns_empty():
    # a builtin / non-Python callable has no __code__ → nothing to key on
    assert capture_call_inputs(len, [lambda: len([1, 2])]) == []


def test_no_tests_returns_empty():
    def target(a):
        return a

    assert capture_call_inputs(target, []) == []


def test_restores_the_previous_profile_hook():
    import sys

    sentinel = sys.getprofile()

    def target(a):
        return a

    def t():
        target(1)

    capture_call_inputs(target, [t])
    assert sys.getprofile() is sentinel
