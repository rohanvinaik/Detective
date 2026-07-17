"""Tests for Detective.converge.

The pure pieces (property_holds, _progressed, _converged) are mutation-driven to
the ceiling. converge() runs the full engine in a loop and is verified by a
standalone run, not here. Plain helpers only (no fixtures).
"""

from __future__ import annotations

import pytest

from Detective.converge import (
    _converged,
    _golden_property,
    _numeric_inputs,
    _progressed,
    _raises_witness_property,
    _witness_property,
    converge,
    property_holds,
)
from Detective.equivalence import Witness
from Detective.synthesis.characterization import GoldenCapture


# ── _witness_property (mutation-driven — pins the built test verbatim) ─
def test_witness_property_builds_golden_test_at_the_witness_input():
    p = _witness_property("m::sign", Witness((0,), "0", "1"))
    assert p.category == "VALUE" and p.needs_oracle is False
    assert p.setup_code == "from m import sign"
    assert p.assertion_code == "result = sign(0)\nassert result == 0"
    assert p.source_lenses == ["witness"] and p.confidence == 0.95
    assert p.preconditions == ["distinguishing witness (equivalence search)"]
    assert p.inputs == {}


def test_witness_property_reprs_multiple_args():
    p = _witness_property("m::f", Witness((-1, 2), "3", "0"))
    assert p.assertion_code == "result = f(-1, 2)\nassert result == 3"


def test_witness_property_bare_func_key_has_no_import():
    # no "::" -> mod is empty -> no import line (exercises the fallback branch)
    p = _witness_property("plainfunc", Witness((1,), "2", "9"))
    assert p.setup_code == ""
    assert p.assertion_code == "result = plainfunc(1)\nassert result == 2"


# ── _raises_witness_property (the killing test for an original that raises) ─
def test_raises_witness_property_pins_the_message_when_the_witness_carries_one():
    # THE fix: `except KeyError: pass` catches a mutant that raises the right type with the
    # wrong message, so it pins nothing and the mutant survives forever. Asserting the message
    # is the only form that kills it. `str(_exc)` must be the SAME form `_outcome` captured.
    p = _raises_witness_property("m::render", Witness(("a", {}), "<raised KeyError: unknown slot a>", "'a'"))
    assert p is not None
    assert "except KeyError as _exc:" in p.assertion_code
    assert "assert str(_exc) == 'unknown slot a'" in p.assertion_code
    assert p.preconditions == ["distinguishing witness (original raises KeyError: unknown slot a)"]


def test_raises_witness_property_falls_back_to_type_only_without_a_message():
    # `_outcome` omits the message when it is empty or volatile. This function must honour that
    # exactly: pinning a message the witness never recorded would fail `property_holds`.
    p = _raises_witness_property("m::f", Witness((1,), "<raised ValueError>", "2"))
    assert p is not None
    assert "except ValueError:\n    pass" in p.assertion_code
    assert "assert str(_exc)" not in p.assertion_code
    assert p.preconditions == ["distinguishing witness (original raises ValueError)"]


def test_raises_witness_property_still_fails_a_mutant_that_returns_or_swaps_type():
    # Both other ways a mutant can differ stay covered — the message pin is an addition, not a
    # replacement. Losing either branch re-opens the crash-kill loop this form exists to close.
    p = _raises_witness_property("m::f", Witness((1,), "<raised ValueError: bad>", "2"))
    assert p is not None
    assert "except BaseException as _exc:" in p.assertion_code
    assert "else:" in p.assertion_code
    assert p.assertion_code.count("pytest.fail") == 2


def test_raises_witness_property_message_with_a_colon_survives_the_round_trip():
    # The marker is "<raised T: msg>" and the message may itself contain ": " — a non-greedy
    # parse would truncate it and pin a message the original never raises.
    p = _raises_witness_property("m::f", Witness((1,), "<raised ValueError: bad: very>", "2"))
    assert p is not None
    assert "assert str(_exc) == 'bad: very'" in p.assertion_code


def test_raises_witness_property_none_when_the_marker_is_not_a_raise():
    assert _raises_witness_property("m::f", Witness((1,), "42", "43")) is None


def test_raises_witness_property_builds_code_that_compiles():
    # The whole point is a file a user runs. A form that does not compile pins nothing.
    p = _raises_witness_property("m::f", Witness((1,), "<raised ValueError: bad>", "2"))
    assert p is not None
    compile(f"{p.setup_code}\n{p.assertion_code}", "<generated>", "exec")


# ── property_holds ────────────────────────────────────────────────
def test_property_holds_true_on_passing_assertion():
    assert property_holds("", "assert 1 == 1", ".") is True


def test_property_holds_false_on_failing_assertion():
    assert property_holds("", "assert 1 == 2", ".") is False


def test_property_holds_runs_setup():
    assert property_holds("y = 5", "assert y == 5", ".") is True


def test_property_holds_false_on_unresolvable_import():
    assert property_holds("from nonexistent_module_xyz import thing", "assert thing", ".") is False


def test_property_holds_false_on_runtime_error():
    assert property_holds("", "assert (1 / 0) == 0", ".") is False


def test_property_holds_preserves_preexisting_sys_path_entry():
    import os
    import sys

    root = os.path.abspath(".")
    if root not in sys.path:
        sys.path.insert(0, root)
    property_holds("", "assert True", ".")  # we did not add root -> must not remove it
    assert root in sys.path


# ── _progressed ───────────────────────────────────────────────────
def test_progressed_true_when_decreased():
    assert _progressed(5, 3) is True


def test_progressed_false_when_equal():
    assert _progressed(3, 3) is False


def test_progressed_false_when_increased():
    assert _progressed(3, 5) is False


# ── _converged ────────────────────────────────────────────────────
def test_converged_true_at_ceiling():
    assert _converged(at_ceiling=True, hit_max_iterations=True) is True


def test_converged_true_when_stabilized_before_max():
    assert _converged(at_ceiling=False, hit_max_iterations=False) is True


def test_converged_false_when_hit_max_still_progressing():
    assert _converged(at_ceiling=False, hit_max_iterations=True) is False


# ── golden-capture helpers ────────────────────────────────────────
def test_numeric_inputs_for_params():
    assert _numeric_inputs(["a", "b", "c"]) == [{"positional_args": ["1", "2", "3"]}]


def test_numeric_inputs_empty():
    assert _numeric_inputs([]) == [{"positional_args": []}]


def test_golden_property_pins_exact_repr():
    cap = GoldenCapture(inputs=(1, 2), output="3", deterministic=True)
    p = _golden_property("m::add", cap)
    assert p.category == "VALUE" and p.needs_oracle is False
    assert p.setup_code == "from m import add"
    assert p.assertion_code == "result = add(1, 2)\nassert result == 3"
    assert p.source_lenses == ["golden_capture"] and p.confidence == 0.9
    assert p.preconditions == ["golden capture (pure + deterministic)"]
    assert p.inputs == {}


def test_golden_property_bare_func_key():
    p = _golden_property("plainfunc", GoldenCapture(inputs=(1,), output="2", deterministic=True))
    assert p.setup_code == ""  # no module component -> no import line
    assert p.assertion_code == "result = plainfunc(1)\nassert result == 2"


# ── converge (fast guard only) ────────────────────────────────────
def test_converge_unknown_function_raises():
    with pytest.raises(LookupError):
        converge("Detective/scope.py", "no_such_function", ".")
