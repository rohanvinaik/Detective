"""Intent tests for the repair-measurement routing (Finding F, revalidation_2026-09-06.md).

The defect, observed on a fresh conorheins clone: `converge` on an unloadable-dep module reported the
profile "cut" and advised `--trace-budget 0 --trace-session-budget 0`; following that produced
byte-identical output with the same advice — an infinite spiral. The cut was a COLLECTION failure (2
test files could not import jax), but the render gave the remedy for a TIMEOUT cut. These pin the fix
from intent: a collection-failure cut routes to "fix the collection errors", never a budget re-run;
and the render for that route names the import failure and offers NO --trace-budget/--deadline command.
"""

from __future__ import annotations

import types

from Detective.cli import _converge_action, repair_measurement_route

# ------------------------------------------------------------------ repair_measurement_route (truth table)


def test_collection_failure_routes_to_fix_not_a_budget_rerun():
    # The load-bearing case: a collection failure must NOT get the timeout remedy that looped.
    assert repair_measurement_route(("collection_incomplete",), False, False) == "fix_collection"


def test_each_typed_reason_routes_to_its_own_remedy():
    assert repair_measurement_route(("ambiguous_module_identity",), False, False) == "regime"
    assert repair_measurement_route(("budget_exhausted",), False, False) == "deadline"
    # A genuine trace cut keeps the (now residual, not catch-all) trace-budget remedy.
    assert repair_measurement_route(("coverage_truncated",), False, False) == "trace_budget"
    assert repair_measurement_route(("sampled_universe",), False, False) == "enumerate"
    assert repair_measurement_route(("uncontained_worker",), False, False) == "isolate"
    assert repair_measurement_route(("engine_refused_unspecified",), False, False) == "inspect_refusal"


def test_raw_boolean_fallbacks_preserve_prior_behaviour_for_older_results():
    # An engine that reports the boolean but not the typed reason (older Wesker, #60) still routes.
    assert repair_measurement_route((), True, False) == "regime"  # collection_conflicts
    assert repair_measurement_route((), False, True) == "deadline"  # budget_exhausted
    # Missing reasons do not justify a fabricated budget diagnosis.
    assert repair_measurement_route((), False, False) == "inspect_refusal"


def test_precedence_most_blocking_first():
    # A missing import outranks a budget: no budget change fixes an import, so name that first.
    assert (
        repair_measurement_route(("collection_incomplete", "budget_exhausted"), False, False)
        == "fix_collection"
    )
    # An ambiguous module identity (a structural import-layout problem) outranks the collection error.
    assert (
        repair_measurement_route(("ambiguous_module_identity", "collection_incomplete"), False, False)
        == "regime"
    )


# ------------------------------------------------------------------ the render (via _converge_action)


def _ungateable_result(cut_reasons: tuple[str, ...]):
    # A duck-typed converge result that routes to repair_measurement (admits_certificate False →
    # certificate_standing "ungateable" → converge_next_action "repair_measurement").
    return types.SimpleNamespace(
        function="jax_backend/src/utils.py::str2bool",
        functionally_complete=False,
        verification=None,
        line_complete=False,
        missing_lines=(143,),
        stale_target=False,
        admits_certificate=False,
        written_path="",
        cut_reasons=cut_reasons,
        collection_conflicts=(),
        budget_exhausted=False,
    )


def test_fix_collection_render_names_the_import_failure_and_offers_no_budget_command():
    out = "\n".join(_converge_action(_ungateable_result(("collection_incomplete",)), None))
    assert "STOP:" in out
    assert "failed to collect" in out
    # The whole point of F: the looping budget COMMAND must NOT be offered on this route. (The prose
    # names --trace-budget/--deadline to say they do NOT help — that is the fix, not the defect — so
    # the check is on the command forms, and on this being a STOP rather than the old DO THIS command.)
    assert "DO THIS:" not in out
    assert "--trace-budget 0" not in out
    assert "--deadline 0" not in out
    # It routes to the actual fix instead.
    assert "run under the venv" in out or "missing dependency" in out


def test_a_genuine_trace_cut_still_gets_the_trace_budget_remedy():
    out = "\n".join(_converge_action(_ungateable_result(("coverage_truncated",)), None))
    assert "--trace-budget 0" in out
    assert "the profile was cut before the mutant universe was measured" in out
