"""Intent tests for audit's measurement-block routing (Finding E, revalidation_2026-09-06.md).

The defect: `audit` on an unloadable module (a missing dep) said the generic "unclassified 27 →
DO THIS: converge · Writes the missing tests" — never naming the dependency and sending the reader to
a converge that also cannot run — while `converge` on the same target named the dep (fix_load). The
two sibling renderers diverged because audit's SuiteAudit had dropped `load_failed`/`note`. These pin
the fix from intent: both commands consult ONE shared decision (`measurement_block_route`), and audit
names the SAME escape converge does. Written from the defect, not the code.
"""

from __future__ import annotations

from Detective.audit import SuiteAudit
from Detective.cli import _audit_action, measurement_block_route

# ------------------------------------------------------------------ measurement_block_route (shared decision)


def test_load_failure_routes_to_fix_load_and_outranks_the_others():
    assert measurement_block_route(True, None, False) == "fix_load"
    # Nothing ran, so the other signals are moot — the import failure wins.
    assert measurement_block_route(True, False, True) == "fix_load"


def test_an_inexpressible_param_routes_to_close_the_gap():
    assert measurement_block_route(False, False, False) == "close_the_gap"


def test_a_loaded_module_no_input_reached_routes_to_provide_sample():
    assert measurement_block_route(False, None, True) == "provide_sample"


def test_a_measurement_that_ran_does_not_block():
    # inputs_expressible True/None with no needs_sample -> "" (the caller proceeds to its own ladder).
    assert measurement_block_route(False, True, False) == ""
    assert measurement_block_route(False, None, False) == ""


# ------------------------------------------------------------------ audit render (via _audit_action)


def _audit(**over) -> SuiteAudit:
    base = dict(
        function="m.py::f",
        test_count=0,
        kill_pct=0.0,
        mutant_complete=False,
        line_complete=False,
        redundant_tests=(),
        failing_tests=(),
        killable_gaps=(),
        missing_lines=(143,),
        minimal_test_count=0,
    )
    base.update(over)
    return SuiteAudit(**base)


def test_audit_on_an_unloadable_module_names_the_dep_not_generic_converge():
    a = _audit(
        unclassified=27,
        load_failed=True,
        note="the live original could not be loaded: ModuleNotFoundError: No module named 'funcy'",
    )
    out = "\n".join(_audit_action(a))
    assert "STOP:" in out
    assert "No module named 'funcy'" in out
    # The generic "converge writes the missing tests" row (which sent the reader to a converge that
    # also cannot run) must NOT be what audit shows here.
    assert "Writes" not in out
    assert "missing dependency" in out


def test_audit_on_an_inexpressible_target_asks_for_a_sample():
    a = _audit(
        unclassified=31,
        inputs_expressible=None,
        note="synthesized inputs don't exercise f(step, xy) — every candidate raised; provide a real sample",
    )
    out = "\n".join(_audit_action(a))
    assert "AUTHOR INPUT:" in out
    assert "provide a real sample" in out
    assert "detective converge 'm.py::f'" in out
    assert "Writes" not in out


def test_a_healthy_measurement_still_gets_the_normal_gap_ladder():
    # load_failed False, inputs_expressible True, a real killable gap -> the block must NOT fire; the
    # existing "converge writes the missing tests" ask is correct here.
    a = _audit(inputs_expressible=True, killable_gaps=("ARITHMETIC [x]",))
    out = "\n".join(_audit_action(a))
    assert "detective converge 'm.py::f'" in out
    assert "Writes" in out
    assert "STOP:" not in out
    assert "AUTHOR INPUT:" not in out
