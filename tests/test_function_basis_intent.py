"""function_basis assembles the FunctionBasis from a completed profile (#D2 §9).

The accessor holds only object handling; its decisions (basis_action, has_open_obligations) are
pinned separately. These drive it end-to-end on fake results to prove the assembly: obligations from
the executable-line denominator, undischargeable from the uncovered lines, and the terminal action
from the engine's OWN validity — a cut is unresolved, a killable survivor is a gap, a
candidate-equivalent is neither.
"""

from __future__ import annotations

from types import SimpleNamespace

from Detective.engine import FunctionBasis, function_basis
from Detective.validity import MeasurementValidity


def _result(**kw):
    base = dict(
        function_key="f.py::g",
        executable_lines=[1, 2, 3],
        line_coverage={"t": [1, 2, 3]},
        kill_matrix={"m0": ["t"]},
        total_survived=0,
        total_equivalent=0,
    )
    base.update(kw)
    return SimpleNamespace(**base)


_GATEABLE = MeasurementValidity(gateable=True, cut_reasons=())
_CUT = MeasurementValidity(gateable=True, cut_reasons=("budget_exhausted",))


def test_complete_when_gateable_all_covered_no_survivors():
    b = function_basis(_result(), _GATEABLE)
    assert isinstance(b, FunctionBasis)
    assert b.target == "f.py::g"
    assert b.action == "complete"
    assert b.obligations.lines == (1, 2, 3)
    assert b.obligations.mutation_dims == ("m0",)
    assert b.undischargeable.lines == ()
    assert b.admitted == () and b.excluded == () and b.unresolved == ()  # D3/D5, empty by design


def test_a_killable_survivor_is_a_gap():
    assert function_basis(_result(total_survived=1), _GATEABLE).action == "gap"


def test_an_uncovered_line_is_a_gap_and_enters_undischargeable():
    b = function_basis(_result(line_coverage={"t": [1, 2]}), _GATEABLE)  # line 3 uncovered
    assert b.undischargeable.lines == (3,)
    assert b.action == "gap"


def test_a_candidate_equivalent_survivor_is_not_a_gap():
    # survived == equivalent: only undecidable equivalents remain — complete, not gap.
    got = function_basis(_result(total_survived=2, total_equivalent=2), _GATEABLE)
    assert got.action == "complete"


def test_a_cut_measurement_is_unresolved_regardless_of_obligations():
    assert function_basis(_result(total_survived=1), _CUT).action == "unresolved"
    assert function_basis(_result(), _CUT).action == "unresolved"


def test_missing_fields_degrade_to_empty_never_crash():
    b = function_basis(SimpleNamespace(function_key="x.py::y"), _GATEABLE)
    assert b.target == "x.py::y"
    assert b.obligations.lines == ()
    assert b.undischargeable.lines == ()
    assert b.action == "complete"  # nothing open, gateable
