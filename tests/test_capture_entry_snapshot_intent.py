"""D#108/D#127: harvest entry state before the target can mutate its arguments.

The capture shell accepts live callables, so ordinary boundary tests protect it.
Rows must preserve aliases internally and stay independent of later executions;
an argument we cannot snapshot is an observation refusal, never an empty pool.
"""

import pytest

from Detective.capture import ObservationIncomplete, capture_call_inputs
from Detective.equivalence import _outcome, _pair_disposition


def test_harvest_retains_each_calls_entry_state():
    values = [1]

    def target(items):
        items.append(len(items) + 1)

    def reaches():
        target(values)
        target(values)

    rows = capture_call_inputs(target, [reaches])

    assert values == [1, 2, 3]
    assert rows == [([1],), ([1, 2],)]
    assert rows[0][0] is not values
    assert rows[0][0] is not rows[1][0]


def test_aliases_within_a_row_survive_while_rows_are_independent():
    values = []

    def target(left, right):
        assert left is right
        left.append("next")

    def reaches():
        target(values, values)
        target(values, values)

    rows = capture_call_inputs(target, [reaches])

    assert rows == [([], []), (["next"], ["next"])]
    assert rows[0][0] is rows[0][1]
    assert rows[1][0] is rows[1][1]
    rows[0][0].append("local")
    assert rows[1][0] == ["next"]
    assert values == ["next", "next"]


def test_recursive_accumulator_rows_retain_their_entry_prefixes():
    def walk(node, out):
        out.append(node[0])
        for child in node[1]:
            walk(child, out)
        return out

    def reaches():
        assert walk(("root", [("child", [])]), []) == ["root", "child"]

    rows = capture_call_inputs(walk, [reaches])

    assert [row[1] for row in rows] == [[], ["root"]]
    for row in rows:
        assert _pair_disposition(_outcome(walk, row), _outcome(walk, row)) == "same"
    assert [row[1] for row in rows] == [[], ["root"]]


def test_uncopyable_entry_is_a_named_refusal():
    class Uncopyable:
        def __deepcopy__(self, memo):
            raise TypeError("no independent snapshot")

    def target(value):
        return value

    def reaches():
        target(Uncopyable())

    with pytest.raises(ObservationIncomplete) as caught:
        capture_call_inputs(target, [reaches])

    assert caught.value.code == "input_snapshot_failed"
    assert caught.value.contained is True


def test_unrepresentable_snapshot_is_not_silently_an_empty_pool():
    class Unrepresentable:
        def __repr__(self):
            raise ValueError("no stable representation")

    def target(value):
        return value

    def reaches():
        target(Unrepresentable())

    with pytest.raises(ObservationIncomplete) as caught:
        capture_call_inputs(target, [reaches])

    assert caught.value.code == "input_snapshot_unrepresentable"
