"""D#108: rendering evidence must belong to the bounded call that established it.

The instrumentation accepts live callables and receivers, so boundary tests guard
single-invocation value/state provenance and the worker's copying boundary.
"""

import threading

import pytest

from Detective.binding import ReceiverBound
from Detective.capture import ObservationIncomplete
from Detective.equivalence import (
    _OUTCOME_WALL_UNDETERMINED,
    _outcome,
    _search_witness,
    _state_fallback_witness,
)


def test_value_witness_does_not_reexecute_either_arm_for_its_payload():
    calls = {"original": 0, "mutant": 0}

    def original():
        calls["original"] += 1
        return {calls["original"]}

    def mutant():
        calls["mutant"] += 1
        return {10 + calls["mutant"]}

    witness, _, _, _ = _search_witness(original, mutant, [()])

    assert witness is not None
    assert calls == {"original": 1, "mutant": 1}
    assert witness.original == "{1}"
    assert witness.original_value == {1}
    assert witness.mutant_value == {11}


def test_original_payload_is_frozen_before_the_mutant_changes_shared_state():
    shared = [1]

    def original():
        return shared

    def mutant():
        shared[:] = [2]
        return shared

    witness, _, _, _ = _search_witness(original, mutant, [()])

    assert witness is not None
    assert witness.original == "[1]"
    assert witness.original_value == [1]
    assert witness.mutant_value == [2]


def test_none_is_a_valid_observed_return_value():
    def original():
        return None

    def mutant():
        return 1

    witness, _, _, _ = _search_witness(original, mutant, [()])

    assert witness is not None
    assert witness.original == "None"
    assert witness.original_value is None
    assert witness.mutant_value == 1


def test_state_pins_come_from_the_same_calls_as_the_state_markers():
    calls = {"original": 0, "mutant": 0}

    class Receiver:
        answer = 0

    def original(receiver):
        calls["original"] += 1
        receiver.answer = calls["original"]

    def mutant(receiver):
        calls["mutant"] += 1
        receiver.answer = 10 + calls["mutant"]

    witness, blocked = _state_fallback_witness(
        ReceiverBound(original, Receiver), ReceiverBound(mutant, Receiver), [()], deadline=None
    )

    assert witness is not None
    assert blocked is False
    assert calls == {"original": 1, "mutant": 1}
    assert witness.state_pins == (("answer", "1"),)


def test_candidate_copying_runs_inside_the_bounded_worker():
    copy_threads = []

    class Value:
        def __deepcopy__(self, memo):
            copy_threads.append(threading.get_ident())
            return Value()

    def target(value):
        return 1

    assert _outcome(target, (Value(),)) == "1"
    assert copy_threads
    assert threading.get_ident() not in copy_threads


def test_uncopyable_return_is_an_observation_refusal_not_a_target_raise():
    class Uncopyable:
        def __deepcopy__(self, memo):
            raise TypeError("no independent result")

    def target():
        return Uncopyable()

    observations = []
    with pytest.raises(ObservationIncomplete) as caught:
        _outcome(target, (), observations=observations)

    assert caught.value.code == "outcome_snapshot_failed"
    assert observations == []


def test_runaway_result_copy_is_bounded_and_retains_no_partial_payload():
    class RunawayCopy:
        def __deepcopy__(self, memo):
            while True:
                pass

    def target():
        return RunawayCopy()

    observations = []
    outcome = _outcome(target, (), timeout_s=0.02, observations=observations)

    assert outcome == _OUTCOME_WALL_UNDETERMINED
    assert observations == []
