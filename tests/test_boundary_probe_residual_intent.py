"""Intent tests for #71 — `modulo N unproven-equivalent` asserted a frontier it had not established.

The defect, verbatim from converge's DONE block: *"What remains cannot be distinguished by any input
Detective found — whether it is truly equivalent is UNDECIDABLE in general, so the engine will not
claim it. Leave them; they are not a gap."* The first clause is scoped; the rest files the residual
under Rice-undecidability, and measurement said much of it was SEARCH BUDGET (§R5b), five targets of
five:

* `ledger.outcome_disposition(int, int, bool)` — four "candidate-equivalents" killed by the obvious
  `(1,0,False)`, `(2,0,True)`, `(0,1,False)`, `(1,1,False)`: `bounded_product` truncated the 50-row
  product to 15 rotations that never paired `matching_count=1` with `other_count=0`;
* `consumption.consumption_disposition(int, int, str)` — `(0, 0, "")` never formed;
* `doctor.same_recorded_state(dict | None, dict | None)` — a DICT domain probed with `{}` alone;
* `Wesker/monitoring.py::step_budget_verdict(iterations, cap: int | None)` — `if cap is None:` →
  `if False:` survived "25 tried" because the `None` half of `cap` was never probed at all, while
  `(0, None)` distinguishes it at once.

An operator following the printed advice would `flag` those as equivalent, and a flag is honoured —
the certificate silently weakens on the tool's own recommendation.

The fix has two halves, and these tests hold each to its intent:
(b) the search — a boundary-probe pass over fully-expressible signatures (the `None` of an Optional
    first, both sides of every comparison edge, float interiors, dict keys the body reads), full
    product or a pairwise covering array, residual-only and positive-only;
(a) the wording — the DONE block names search budget vs probed-and-still-undistinguished, names the
    remedy, and offers `flag` for no mutant an input distinguishes or a printed boundary input might.
"""

from __future__ import annotations

import ast
import itertools
import math
import textwrap
import types

import pytest

from Detective.cli import (
    _converge_action,
    _flaggable_ids,
    _format_survivor_report,
    residual_done_basis,
    residual_done_why,
)
from Detective.engine import _boundary_probe_inputs, _compile_mutant, _input_grids, boundary_probe_gate
from Detective.equivalence import (
    MutantVerdict,
    SurvivorReport,
    Witness,
    _search_witness,
    boundary_probe_values,
    bounded_product,
    find_witness,
    probe_rows,
)

# --- (b) the gate --------------------------------------------------------------------------------


def test_the_gate_names_why_a_residual_was_not_probed():
    assert boundary_probe_gate(3, False, True, False) == "run"
    assert boundary_probe_gate(0, False, True, False) == "skip_no_residual"
    # An effectful target is never fed a fabricated value — even when its inputs could be typed.
    assert boundary_probe_gate(3, True, True, False) == "skip_effects"
    assert boundary_probe_gate(3, False, False, False) == "skip_inexpressible"
    assert boundary_probe_gate(3, False, True, True) == "skip_wall"
    # The binding reason: nothing to probe outranks every other.
    assert boundary_probe_gate(0, True, False, True) == "skip_no_residual"


# --- (b) the probe values ------------------------------------------------------------------------


def test_the_none_of_an_optional_is_probed_first():
    probes = boundary_probe_values("int", True, [], [])
    assert probes is not None and probes[0] is None
    assert boundary_probe_values("dict", True, [], ["k"])[0] is None


def test_int_probes_straddle_every_edge_the_body_draws():
    probes = boundary_probe_values("int", False, [50], [])
    assert {49, 50, 51} <= set(probes)
    assert {0, 1, -1} <= set(probes)
    assert all(type(p) is int for p in probes)


def test_float_probes_land_inside_the_region_a_value_mutant_moves():
    """`<= 0` mutated to `<= -1` differs only strictly inside (-1, 0) — no integer lands there."""
    probes = boundary_probe_values("float", False, [0], [])
    assert -0.5 in probes and 0.5 in probes and 0.0 in probes
    assert all(type(p) is float and math.isfinite(p) for p in probes)


def test_str_probes_include_the_strip_edge_and_the_literals():
    probes = boundary_probe_values("str", False, ["pro"], [])
    assert probes[0] == "pro"
    assert "" in probes and " " in probes


def test_dict_probes_read_the_keys_the_body_reads():
    probes = boundary_probe_values("dict", False, [], ["suite", "suite_exact"])
    assert {} in probes
    assert {"suite": "x"} in probes and {"suite": "y"} in probes and {"suite": ""} in probes
    assert {"suite_exact": "x"} in probes
    assert {"suite": "x", "suite_exact": "x"} in probes


def test_a_type_with_no_probe_domain_declines():
    assert boundary_probe_values("list", False, [], []) is None
    assert boundary_probe_values("Account", False, [], []) is None


def test_non_finite_and_huge_constants_never_crash_the_probe():
    assert boundary_probe_values("int", False, [math.inf, 10**400], []) == [0, 1, -1]
    assert boundary_probe_values("float", False, [math.nan], []) == [0.0, 0.5, -0.5, 1.0, -1.0]


# --- (b) the rows --------------------------------------------------------------------------------


def test_the_full_product_is_taken_when_it_fits():
    grids = [[0, 1, 2], [-1, 0, 1], [False, True]]
    assert probe_rows(grids) == list(itertools.product(*grids))


def test_above_the_cap_every_pair_of_values_still_meets():
    grids = [list(range(7)) for _ in range(5)]  # 16807 rows in the product
    rows = probe_rows(grids, cap=256)
    assert len(rows) <= 256
    for p, q in itertools.combinations(range(5), 2):
        met = {(r[p], r[q]) for r in rows}
        assert met == set(itertools.product(range(7), range(7))), (p, q)
    assert probe_rows(grids, cap=256) == rows  # deterministic


# --- (b) the search reaches what the grid did not --------------------------------------------------


def _fn(src: str):
    tree = ast.parse(textwrap.dedent(src))
    node = tree.body[0]
    ns: dict = {}
    exec(compile(tree, "<fixture>", "exec"), ns)  # noqa: S102
    return node, ns[node.name]


def _grid_pool(node: ast.FunctionDef, ns: dict | None = None) -> list[tuple]:
    """The pool the witness search drew from before #71 — the function's own edges leading each
    parameter's typed grid, through `bounded_product` (cap 32)."""
    return bounded_product(_input_grids(node, ns or {}))


def _mutant(node: ast.FunctionDef, original, transform) -> object:
    """A hand-made mutant: `transform` rewrites a deep copy of the function node."""
    import copy

    mutated = copy.deepcopy(node)
    transform(mutated)
    return _compile_mutant(types.SimpleNamespace(mutated_node=mutated, wrapper_factory=None), original)


def _replace_compare(node: ast.AST, src_from: str, src_to: str) -> None:
    """Swap the first sub-expression whose source is ``src_from`` — a field or a list element."""
    for sub in ast.walk(node):
        for field, value in ast.iter_fields(sub):
            if isinstance(value, ast.expr) and ast.unparse(value) == src_from:
                setattr(sub, field, ast.parse(src_to, mode="eval").body)
                return
            if isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, ast.expr) and ast.unparse(item) == src_from:
                        value[i] = ast.parse(src_to, mode="eval").body
                        return
    raise AssertionError(f"{src_from!r} not found")


_OUTCOME = """
def outcome_disposition(matching_count: int, other_count: int, matching_are_identical: bool) -> str:
    if matching_count == 0:
        return "nested_only" if other_count > 0 else "unobserved"
    if matching_count > 1 and not matching_are_identical:
        return "ambiguous"
    return "authoritative"
"""


def test_outcome_disposition_shape_the_grid_missed_the_probes_kill():
    node, original = _fn(_OUTCOME)
    mutant = _mutant(
        node, original, lambda n: _replace_compare(n, "matching_count > 1", "matching_count >= 1")
    )
    # The pre-#71 pool: a 5x5x2 product truncated to 15 rotations that never pairs 1 with 0/False.
    assert find_witness(original, mutant, _grid_pool(node)) is None
    witness = find_witness(original, mutant, _boundary_probe_inputs(node, {}))
    assert witness is not None and witness.args[0] == 1 and witness.args[2] is False


_STEP = """
def step_budget_verdict(iterations: int, cap: int | None) -> str:
    if cap is None:
        return "unbounded"
    return "exceeded" if iterations > cap else "within"
"""


def test_the_none_half_of_an_optional_is_reached():
    node, original = _fn(_STEP)
    mutant = _mutant(node, original, lambda n: _replace_compare(n, "cap is None", "False"))
    probes = _boundary_probe_inputs(node, {})
    assert probes[0][1] is None  # the None is probed FIRST
    witness, crash_witness, _blocked = _search_witness(original, mutant, probes)
    # `(…, None)` distinguishes it at once: the mutant compares `iterations > None` and raises.
    assert witness is None and crash_witness is not None and crash_witness.args[1] is None


_SPREAD = """
import math
def spread_ratio(spread_daughter_um: float, spread_parent_um: float) -> float:
    return math.nan if spread_parent_um <= 0 else spread_daughter_um / spread_parent_um
"""


def test_a_value_mutant_moving_a_float_edge_is_killed_inside_the_region():
    tree = ast.parse(_SPREAD)
    ns: dict = {}
    exec(compile(tree, "<fixture>", "exec"), ns)  # noqa: S102
    node, original = tree.body[1], ns["spread_ratio"]
    mutant = _mutant(
        node, original, lambda n: _replace_compare(n, "spread_parent_um <= 0", "spread_parent_um <= -1")
    )
    # The grid only crash-distinguishes it (ZeroDivisionError at 0)…
    grid_witness, grid_crash, _ = _search_witness(original, mutant, _grid_pool(node, ns))
    assert grid_witness is None and grid_crash is not None
    # …the probes find the VALUE witness strictly inside (-1, 0).
    witness = find_witness(original, mutant, _boundary_probe_inputs(node, ns))
    assert witness is not None and -1 < witness.args[1] < 0


_CONSUMED = """
def consumption_disposition(production_callers: int, other_callers: int, exemption_reason: str) -> str:
    if production_callers > 0:
        return "exemption_stale" if exemption_reason.strip() else "consumed"
    if exemption_reason.strip():
        return "exempt_declared"
    if other_callers > 0:
        return "pinned_unconsumed"
    return "unreferenced"
"""


def test_consumption_shape_the_grid_missed_the_probes_kill():
    node, original = _fn(_CONSUMED)
    mutant = _mutant(node, original, lambda n: _replace_compare(n, "other_callers > 0", "other_callers >= 0"))
    assert find_witness(original, mutant, _grid_pool(node)) is None
    witness = find_witness(original, mutant, _boundary_probe_inputs(node, {}))
    # No production caller, no other caller, no reason: where `> 0` and `>= 0` part ways.
    assert (
        witness is not None and witness.args[0] <= 0 and witness.args[1] == 0 and not witness.args[2].strip()
    )


_SAME_STATE = """
def same_recorded_state(a: dict | None, b: dict | None) -> bool:
    a, b = a or {}, b or {}
    for key in {k for k in (*a, *b) if k not in ("suite", "suite_exact")}:
        if a.get(key) != b.get(key):
            return False
    a_exact, b_exact = a.get("suite_exact", ""), b.get("suite_exact", "")
    if a_exact and b_exact:
        return a_exact == b_exact
    return a.get("suite") == b.get("suite")
"""


def test_a_dict_domain_is_probed_with_the_keys_the_body_reads():
    node, original = _fn(_SAME_STATE)
    mutant = _mutant(
        node,
        original,
        lambda n: _replace_compare(n, "a.get('suite_exact', '')", "a.get('suite_exact', 'mutated')"),
    )
    assert find_witness(original, mutant, _grid_pool(node)) is None
    assert find_witness(original, mutant, _boundary_probe_inputs(node, {})) is not None


def test_a_signature_with_an_inexpressible_parameter_is_not_probed():
    """A domain-object slot has no literal probe domain: the pass declines (`skip_inexpressible`)
    rather than probe around it — the domain-object passes and the fixture caveat own that residual."""
    import dataclasses

    @dataclasses.dataclass
    class Account:
        tier: str = "gold"
        balance: float = 1.0

    node = ast.parse("def charge(account: Account, amount: int) -> float:\n    return amount\n").body[0]
    assert _boundary_probe_inputs(node, {"Account": Account}) == []


# --- (a) the wording -----------------------------------------------------------------------------


def test_the_basis_separates_probed_unprobed_and_crash_only():
    assert residual_done_basis(0, 0, "run") == "none"
    assert residual_done_basis(0, 2, "") == "crash_only"
    assert residual_done_basis(2, 1, "run") == "probed"
    assert residual_done_basis(2, 0, "skip_effects") == "unprobed"
    assert residual_done_basis(2, 0, "") == "unprobed"  # an engine that never reached the gate


def test_no_basis_files_the_residual_under_undecidability_by_default():
    unprobed = residual_done_why("unprobed")
    assert "SEARCH BUDGET" in unprobed and "None" in unprobed and "--input" in unprobed
    assert "UNDECIDABLE" not in unprobed and "not a gap" not in unprobed
    probed = residual_done_why("probed")
    assert "probed" in probed and "None" in probed
    assert "not a gap" not in probed
    assert "nothing is offered to `flag`" in residual_done_why("crash_only")
    assert residual_done_why("bogus").startswith("unrecognised")


def _verdict(mid: str, category: str = "VALUE", diff: str = "", crash_only: bool = False) -> MutantVerdict:
    w = Witness(args=(0,), original="1", mutant="<raised ValueError>") if crash_only else None
    return MutantVerdict(mid, category, diff, False, None, 5, crash_only=crash_only, crash_witness=w)


_BOUNDARY_DIFF = (
    "- def f(x):\n    if x >= 50:\n        return 1\n    return 0\n"
    "+ def f(x):\n    if x > 50:\n        return 1\n    return 0"
)


def _settled(param_names=("x",)):
    return types.SimpleNamespace(
        function="m.py::f",
        functionally_complete=True,
        verification=None,
        line_complete=True,
        missing_lines=(),
        stale_target=False,
        admits_certificate=True,
        written_path="tests/detective/test_m_f_synth.py",
        synthesized_only=False,
        environment_gated=(),
        param_names=param_names,
    )


def test_an_unprobed_residual_names_the_remedy_and_withholds_flag_beside_a_printed_boundary():
    rep = SurvivorReport(
        verdicts=(_verdict("BOUNDARY_a", "BOUNDARY", _BOUNDARY_DIFF), _verdict("VALUE_b")),
        unclassified=(),
        boundary_probe="skip_effects",
    )
    out = "\n".join(_converge_action(_settled(), rep))
    assert "SEARCH BUDGET" in out and "UNDECIDABLE" not in out
    # BOUNDARY_a carries a printed `supply an input where x == 50` nobody has tried: no flag for it.
    assert "flag 'm.py::f' BOUNDARY_a" not in out
    assert "detective flag 'm.py::f' VALUE_b" in out
    assert _flaggable_ids(rep, "unprobed", ("x",)) == ["VALUE_b"]


def test_a_probed_residual_may_be_flagged_and_says_what_was_tried():
    rep = SurvivorReport(
        verdicts=(_verdict("BOUNDARY_a", "BOUNDARY", _BOUNDARY_DIFF),),
        unclassified=(),
        boundary_probe="run",
        boundary_probes=24,
    )
    out = "\n".join(_converge_action(_settled(), rep))
    assert "probed this signature's boundaries" in out
    assert "detective flag 'm.py::f' BOUNDARY_a" in out
    report = "\n".join(_format_survivor_report(rep, "f(x)", ("x",)))
    assert "boundary-probed: 24 further probe input(s)" in report


def test_a_crash_only_mutant_is_never_offered_to_flag():
    """An input DOES distinguish it (by crash): an equivalence `flag` would contradict the evidence."""
    rep = SurvivorReport(
        verdicts=(_verdict("BOUNDARY_c", crash_only=True),), unclassified=(), boundary_probe="run"
    )
    out = "\n".join(_converge_action(_settled(), rep))
    assert "detective flag" not in out
    assert "differs from your function only by a CRASH" in out
    report = "\n".join(_format_survivor_report(rep, "f(x)", ("x",)))
    assert "`flag` if truly equivalent" not in report
    assert "nothing to `flag`" in report


def test_audit_closes_with_the_same_basis_and_never_flags_a_crash_only_mutant():
    from Detective.cli import _audit_closing_action

    audit = types.SimpleNamespace(
        function="m.py::f",
        candidate_equivalent=2,
        candidate_equivalent_ids=("CRASH_x", "VALUE_y"),
        crash_only_ids=("CRASH_x",),
        boundary_probe="skip_effects",
    )
    out = "\n".join(_audit_closing_action(audit, "flag_equivalents"))
    assert "SEARCH BUDGET" in out and "UNDECIDABLE" not in out
    assert "detective flag 'm.py::f' VALUE_y" in out
    assert "CRASH_x" not in out


@pytest.mark.parametrize("probe", ["run", "skip_effects", "skip_inexpressible", "skip_wall", ""])
def test_the_report_always_says_whether_the_residual_was_probed(probe):
    rep = SurvivorReport(
        verdicts=(_verdict("VALUE_v"),), unclassified=(), boundary_probe=probe, boundary_probes=3
    )
    report = "\n".join(_format_survivor_report(rep, "f(x)", ("x",)))
    assert ("boundary-probed:" in report) == (probe == "run")
    assert ("NOT boundary-probed" in report) == (probe != "run")


_TABLE = """
def why(code: str) -> str:
    return {"none": "first", "crash_only": "second"}.get(code, f"unrecognised {code}")
"""


def test_a_string_dispatch_parameter_is_probed_with_the_table_keys():
    """A str parameter used as a KEY into a table has its domain written in the table, not in a
    comparison — the shape of `residual_done_why` itself, whose `'none'` entry no probe reached until
    the table's keys joined the probes."""
    node, original = _fn(_TABLE)
    mutant = _mutant(node, original, lambda n: _replace_compare(n, "'first'", "''"))
    assert find_witness(original, mutant, _grid_pool(node)) is None
    witness = find_witness(original, mutant, _boundary_probe_inputs(node, {}))
    assert witness is not None and witness.args == ("none",)


def test_a_module_level_table_lends_its_keys_too():
    node = ast.parse("def lookup(k: str) -> int:\n    return _RATES.get(k, 0)\n").body[0]
    probes = {row[0] for row in _boundary_probe_inputs(node, {"_RATES": {"gold": 3, "silver": 2}})}
    assert {"gold", "silver"} <= probes
