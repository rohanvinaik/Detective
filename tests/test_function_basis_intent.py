"""function_basis assembles the FunctionBasis from a completed profile (#D2/#X3 §9, §15.3).

The accessor holds only object handling; its decisions (basis_action, has_open_obligations) are
pinned separately. These drive it end-to-end on fake results to prove the CORRECTED assembly (G3):
L_t / U_t on the ADMISSIBLE coverage view (never the raw observed union), M_t from the APPLIED
mutant records (killed ∪ survived, keyed on ``mutant_id`` — not the disjoint ``kill_matrix`` keys),
the undischargeable line half from the human unreachability oracle, and the equivalent count
CALLER-SUPPLIED (0 here, as at profile() time). A cut is unresolved; a killable survivor is a gap; a
candidate-equivalent is neither.
"""

from __future__ import annotations

import ast
from types import SimpleNamespace

from Detective.engine import FunctionBasis, function_basis
from Detective.validity import MeasurementValidity

_NODE = ast.parse("def g():\n    a = 1\n    b = 2\n    return a + b\n").body[0]


def _result(**kw):
    base = dict(
        function_key="f.py::g",
        executable_lines=[1, 2, 3],
        admissible_line_coverage={"t": [1, 2, 3]},
        killed_records=[{"mutant_id": "m0"}],
        survivor_records=[],
        total_survived=0,
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
    assert b.obligations.mutation_dims == ("m0",)  # from killed_records, keyed on mutant_id
    assert b.obligations.arcs == ()  # A_t intentionally empty (arc tracing is opt-in)
    assert b.undischargeable.lines == ()
    assert b.excluded == () and b.unresolved == ()  # D3/D5, empty by design
    # admitted is now WIRED (#D1): one witness for the covering test "t", warranted `proof`
    # (fresh admissible cover), discharging the three lines it owns.
    assert len(b.admitted) == 1
    assert b.admitted[0].test == "t"
    assert b.admitted[0].warrant == "proof"
    assert b.admitted[0].discharged.lines == (1, 2, 3)


def test_mutation_dims_are_the_applied_universe_killed_and_survived():
    b = function_basis(
        _result(
            killed_records=[{"mutant_id": "m0"}],
            survivor_records=[{"mutant_id": "m1"}],
            total_survived=1,
        ),
        _GATEABLE,
    )
    # M_t is the applied universe (killed ∪ survived), keyed on mutant_id — not kill_matrix keys.
    assert b.obligations.mutation_dims == ("m0", "m1")


def test_a_killable_survivor_is_a_gap():
    b = function_basis(_result(total_survived=1, survivor_records=[{"mutant_id": "m1"}]), _GATEABLE)
    assert b.action == "gap"


def test_line_coverage_rests_on_the_admissible_view_not_the_raw_union():
    # The raw union covers all three lines, but the ADMISSIBLE view covers only 1,2 — line 3 is open.
    r = _result(admissible_line_coverage={"t": [1, 2]}, line_coverage={"t": [1, 2, 3]})
    b = function_basis(r, _GATEABLE)
    assert b.action == "gap", "an uncovered admissible line is open even if the raw union covered it"


def test_the_unreachability_oracle_runs_without_a_flag_store_and_flags_nothing(tmp_path):
    # func_node supplied so classify_missing_lines runs; no flag store in tmp_path, so line 3 stays a
    # real gap (nothing enters undischargeable). The flag path itself is pinned by line_flags' tests.
    b = function_basis(
        _result(admissible_line_coverage={"t": [1, 2]}),
        _GATEABLE,
        project_root=str(tmp_path),
        func_node=_NODE,
    )
    assert b.action == "gap"
    assert b.undischargeable.lines == ()


def test_a_candidate_equivalent_survivor_is_not_a_gap():
    # survived == candidate_equivalent (caller-supplied): only undecidable equivalents remain.
    got = function_basis(
        _result(
            total_survived=2,
            survivor_records=[{"mutant_id": "m1"}, {"mutant_id": "m2"}],
        ),
        _GATEABLE,
        candidate_equivalent=2,
    )
    assert got.action == "complete"


def test_a_cut_measurement_is_unresolved_regardless_of_obligations():
    assert function_basis(_result(total_survived=1), _CUT).action == "unresolved"
    assert function_basis(_result(), _CUT).action == "unresolved"


def test_missing_fields_degrade_to_empty_never_crash():
    b = function_basis(SimpleNamespace(function_key="x.py::y", line_coverage={}), _GATEABLE)
    assert b.target == "x.py::y"
    assert b.obligations.lines == ()
    assert b.obligations.mutation_dims == ()
    assert b.undischargeable.lines == ()
    assert b.action == "complete"  # nothing open, gateable
