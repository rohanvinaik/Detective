"""#70 — a golden of a BLAS result is a platform-specific observation, and now says so.

THE DEFECT, from the issue: `converge` on two numpy-linalg functions wrote VALUE goldens asserting
exact float equality; the same suites fail on a different BLAS, each off by one unit in the last
place (macOS/Accelerate `0.44001427868311976` vs ubuntu/OpenBLAS `0.44001427868311965`). Every
pure-Python float pin in the same repository passes on both, so the certificates are sound and the
failure is confined to captures whose value came through a BLAS call. Its own sharpest line:

    "the certificate reads as a platform-independent claim, but a golden of a BLAS result is a
    platform-specific observation."

THE EPISTEMIC SHAPE is this session's recurring one. A capture is called deterministic because
`corroborate_captures` observed it twice — ON ONE MACHINE. That establishes stability over the
subspace it sampled, says nothing about the other axis, and nothing recorded that the subspace was
a subspace.

FOUNDER RULING 2026-09-09: the issue's option 2 — **scope the claim, do not weaken it.** Not
tolerance, not approximate equality. The pin stays EXACT and the file states what it is exact ABOUT,
so a mismatch elsewhere reads as a different platform before it reads as a regression.

A MISTAKE WORTH KEEPING, because driving it is the only reason it was caught. The first version
asked only "is a numeric backend loaded in this process". A pure-Python `ratio(a, b)` then came out
STAMPED, because a sibling generated test in the same project had imported numpy into the live
pytest session. "Loaded somewhere" is true of every file in any project that uses numpy at all — a
stamp on all of them is the line that always appears, which is the signpost discipline's own named
defect, and it is also false about the ordinary case. The signal is now the TARGET'S OWN imports.
"""

from __future__ import annotations

from Detective.synthesis.characterization import (
    float_bearing,
    golden_observation_scope,
    observation_stamp,
)
from Detective.synthesis.oracle_light import ExecutableProperty
from Detective.synthesis.writer import _has_float_golden, numeric_backend_for, render_module


def _golden(args_repr: str, expected_repr: str) -> ExecutableProperty:
    return ExecutableProperty(
        category="VALUE",
        inputs={},
        setup_code="",
        assertion_code=f"assert result == {expected_repr}",
        preconditions=[],
        confidence=0.9,
        golden_case=(args_repr, expected_repr),
    )


# ---------------------------------------------------------------- whose imports, not whose process


def test_the_signal_is_the_TARGETS_imports() -> None:
    """The correction. Asking the process answers "does anything here use numpy", which is a fact
    about the project, not about this function."""
    assert numeric_backend_for("import numpy as np\n").startswith("numpy")
    assert numeric_backend_for("from scipy.linalg import norm\n").startswith("scipy")
    assert numeric_backend_for("def f():\n    return 1\n") == ""


def test_a_relative_import_is_not_a_numeric_backend() -> None:
    """`from . import x` has a module of `x` with a non-zero level. Reading the name without the
    level would let a local module called `numpy` — or any sibling — masquerade as the backend."""
    assert numeric_backend_for("from . import sibling\n") == ""


def test_an_unparseable_target_stamps_NOTHING() -> None:
    """The safe direction for a provenance note: a stamp naming a backend nobody established is
    worse than no stamp, because it looks like provenance and carries none."""
    assert numeric_backend_for("def broken(:\n") == ""
    assert numeric_backend_for("") == ""


# ---------------------------------------------------------------- the scope decision


def test_BOTH_facts_are_required() -> None:
    """This is what keeps the stamp meaningful rather than universal — and what keeps it TRUE.
    Pure-Python float arithmetic is IEEE-deterministic across platforms, so a 17-digit repr from it
    is not platform-specific and must not be marked as though it were."""
    assert golden_observation_scope(True, "numpy 2.4.6") == "platform_specific"
    assert golden_observation_scope(True, "") == "platform_independent"
    assert golden_observation_scope(False, "numpy 2.4.6") == "platform_independent"
    assert golden_observation_scope(False, "") == "platform_independent"


def test_a_float_is_found_wherever_it_hides() -> None:
    """A golden of `{"score": 0.44…}` is exactly as platform-exposed as a bare float."""
    assert float_bearing(1.5) is True
    assert float_bearing([1, 2.5]) is True
    assert float_bearing({"a": 1.0}) is True
    assert float_bearing({1.0: "a"}) is True
    assert float_bearing((1, (2, 3.0))) is True


def test_bools_and_ints_are_exact_everywhere() -> None:
    """`bool` is an `int` subclass in Python and never carries a last ULP. Ints and strings are
    exact on every platform, which is the whole reason the question is asked at all."""
    assert float_bearing(True) is False
    assert float_bearing(3) is False
    assert float_bearing("0.5") is False
    assert float_bearing([1, 2, "x"]) is False


# ---------------------------------------------------------------- the stamp itself


def test_the_stamp_says_platform_before_regression() -> None:
    """The issue's stated goal, in its own terms: "so a mismatch elsewhere reads as 'different
    platform' rather than 'regression'". Written to be read by someone who did not generate the
    file, at the moment it fails."""
    note = observation_stamp("darwin-arm64", "numpy 2.4.6")
    assert "darwin-arm64" in note and "numpy 2.4.6" in note
    assert "DIFFERENT PLATFORM before it is a" in note
    assert "regression" in note


def test_an_incomplete_stamp_is_no_stamp() -> None:
    assert observation_stamp("", "numpy 2.4.6") == ""
    assert observation_stamp("darwin-arm64", "") == ""


# ---------------------------------------------------------------- through the renderer


def test_a_float_golden_from_a_numeric_target_stamps_the_suite() -> None:
    src = render_module(
        "num.py::frob", [_golden("(1, 2)", "0.44001427868311976")], numeric_backend="numpy 2.4.6"
    )
    assert "OBSERVED on" in src
    assert "0.44001427868311976" in src, "the pin stays EXACT — this scopes the claim, never weakens it"


def test_a_pure_python_float_golden_is_untouched() -> None:
    """The control that the first implementation failed."""
    src = render_module("pure.py::ratio", [_golden("(1, 3)", "0.3333333333333333")])
    assert "OBSERVED on" not in src


def test_a_non_float_golden_from_a_numeric_target_is_untouched() -> None:
    """A numpy-importing module whose golden is a string has nothing platform-specific to say."""
    src = render_module("num.py::name", [_golden("(1,)", "'big'")], numeric_backend="numpy 2.4.6")
    assert "OBSERVED on" not in src


def test_the_header_is_byte_identical_when_nothing_is_stamped() -> None:
    """The opt-in contract `function_digest` already keeps: a caller that supplies nothing renders
    exactly what it always did, so no existing suite churns and no content digest moves."""
    props = [_golden("(1, 3)", "0.3333333333333333")]
    assert render_module("m.py::f", props, numeric_backend="") == render_module("m.py::f", props)


def test_has_float_golden_reads_the_repr_back() -> None:
    """`golden_case` holds reprs, not values. A non-literal repr cannot be read this way and is
    treated as float-free — under-stamping rather than guessing."""
    assert _has_float_golden([_golden("(1,)", "0.5")]) is True
    assert _has_float_golden([_golden("(1,)", "'x'")]) is False
    assert _has_float_golden([_golden("(1,)", "<Obj object at 0x1>")]) is False
