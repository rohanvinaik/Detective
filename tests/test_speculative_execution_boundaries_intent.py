"""D#105/#108: speculative work must finish or refuse without filesystem damage.

These are live worker/audit-hook boundaries, guarded with authored intent tests.
The target's ordinary exception handlers must not turn blocked effects into proof.
"""

import pytest

from Detective.capture import ObservationIncomplete
from Detective.converge import property_holds
from Detective.equivalence import _outcome


def test_property_loop_is_bounded_and_a_following_check_remains_usable(tmp_path):
    with pytest.raises(ObservationIncomplete) as caught:
        property_holds("", "while True:\n    pass", str(tmp_path), timeout_s=0.02)

    assert caught.value.code == "property_timeout"
    assert caught.value.contained is True
    assert property_holds("", "assert 1 == 1", str(tmp_path))


def test_property_verification_cannot_write_into_the_project(tmp_path):
    destination = tmp_path / "project.txt"
    code = f"from pathlib import Path\nPath({str(destination)!r}).write_text('changed')"
    with pytest.raises(ObservationIncomplete) as caught:
        property_holds("", code, str(tmp_path))

    assert caught.value.code == "filesystem_write_blocked"
    assert not destination.exists()


def test_a_blocked_write_is_an_observation_refusal_not_a_target_outcome(tmp_path):
    destination = tmp_path / "output.txt"

    def target():
        destination.write_text("changed")
        return 1

    with pytest.raises(ObservationIncomplete) as caught:
        _outcome(target, ())

    assert caught.value.code == "filesystem_write_blocked"
    assert not destination.exists()


def test_swallowing_the_write_guard_does_not_make_the_run_admissible(tmp_path):
    destination = tmp_path / "output.txt"

    def target():
        try:
            destination.write_text("changed")
        except BaseException:
            pass
        return 1

    with pytest.raises(ObservationIncomplete) as caught:
        _outcome(target, ())

    assert caught.value.code == "filesystem_write_blocked"
    assert not destination.exists()


def test_a_blocked_iterator_effect_cannot_be_reported_as_iterator_behavior(tmp_path):
    destination = tmp_path / "output.txt"

    def target():
        yield 1
        destination.write_text("changed")

    with pytest.raises(ObservationIncomplete) as caught:
        _outcome(target, ())

    assert caught.value.code == "filesystem_write_blocked"
    assert not destination.exists()
