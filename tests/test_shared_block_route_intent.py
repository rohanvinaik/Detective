"""Intent tests for R3 — one shared derivation, consulted unconditionally.

Design: `docs/CORRECTNESS_REPAIRS_2026-09-08.md` §R3.

`measurement_block_route` exists so converge and audit can never diverge on the same survivor
report — its own docstring says so. It was consulted by audit unconditionally, and by converge
only INSIDE `if session_reason:` — a condition about whether the BASELINE suite collected at the
start of the run, which has nothing to do with whether the measurement could run over the target.

The consequence, on any repo whose suite collects cleanly (i.e. most of them): `fix_load` was
structurally unreachable from converge, and an unreached function or an inexpressible parameter
fell through to the generic `close_the_gap`. One shared decision, two different answers for one
report — the exact drift it was written to end.

Observed 2026-09-08 on conorheins `str2bool` with the collection cut removed: audit named
`ModuleNotFoundError: No module named 'funcy'`; converge asked the operator to author inputs for a
module that cannot import, at exit 0, and re-emitted byte-identically when they did.
"""

from __future__ import annotations

import types

import pytest

from Detective.cli import (
    _converge_action,
    converge_next_action,
    measurement_block_route,
    repair_measurement_route,
)


@pytest.mark.parametrize("session_reason", ["", "empty_collection", "collection_errors", "pytest_crashed"])
def test_a_load_failure_is_named_whatever_the_baseline_collection_did(session_reason):
    """THE defect. Whether the baseline suite collected is independent of whether the target
    module imports, so it must not gate the answer to the second question."""
    assert converge_next_action("incomplete", session_reason, True, True, load_failed=True) == "fix_load"


@pytest.mark.parametrize("session_reason", ["", "empty_collection"])
def test_an_unreached_function_asks_for_a_sample_whatever_the_baseline_did(session_reason):
    """GofL's case generalised: the module loaded and the search ran, but no input reached the
    function. That is true regardless of how the baseline collected."""
    assert (
        converge_next_action("incomplete", session_reason, True, True, needs_sample=True) == "provide_sample"
    )


def test_the_healthy_path_is_unchanged():
    """No signal set means nothing blocks the measurement, and the ordinary gap ask stands. An
    unconditional consultation must not become an unconditional interruption."""
    assert converge_next_action("incomplete", "", True, True) == "close_the_gap"
    assert converge_next_action("incomplete", "empty_collection", True, True) == "fix_collection"


def test_settled_still_outranks_the_block_route():
    """Deliberately BELOW settled, not above it. These signals describe obstacles to MEASURING;
    a run that measured everything has no obstacle left to report. Re-pinned here because R3
    moved the call and this ordering is the thing most at risk from that move."""
    for signal in ({"load_failed": True}, {"needs_sample": True}, {"inputs_expressible": False}):
        assert converge_next_action("complete", "empty_collection", False, False, **signal) == "settled"


def test_an_ungateable_measurement_still_outranks_everything():
    """R1's layer, re-asserted from here: a load-failed target is ungateable BEFORE this ladder is
    reached, so the latent 'settled over a run that measured nothing' case is closed one level up
    rather than by reordering this function."""
    assert converge_next_action("ungateable", "", False, False, load_failed=True) == "repair_measurement"


def test_converge_and_audit_read_the_identical_derivation():
    """The property the shared route exists for. Not 'both look right' — the SAME function, so
    they cannot drift by construction. If converge ever re-derives its own version of this, this
    test keeps passing and the guarantee is gone, so it asserts identity of the route itself."""
    for load_failed in (True, False):
        for expressible in (True, False, None):
            for needs_sample in (True, False):
                shared = measurement_block_route(load_failed, expressible, needs_sample)
                via_converge = converge_next_action(
                    "incomplete",
                    "",
                    True,
                    True,
                    load_failed=load_failed,
                    inputs_expressible=expressible,
                    needs_sample=needs_sample,
                )
                if shared:
                    assert via_converge == shared, (load_failed, expressible, needs_sample)


def test_a_load_failure_outranks_a_needed_sample():
    """Nothing ran at all, so there is nothing to sample. Preserved from the original pinning —
    the hoist must not reorder the block route's own internal precedence."""
    assert (
        converge_next_action("incomplete", "", True, True, needs_sample=True, load_failed=True) == "fix_load"
    )


# ------------------------------------------------ the standing path: converge must name the DEP
#
# R1 made a load failure ungateable, which is right — but `standing` is consumed BEFORE this
# ladder, so a load-failed run routes to `repair_measurement` and never reaches `fix_load`. R1
# added the cut reason and did not teach `repair_measurement_route` about it, so the run fell
# through to `inspect_refusal` and got "inspect the reported engine failure" for an import error
# (S7) — while audit, from the SAME report, printed the missing dependency by name.


def _ungateable_result(cut_reasons: tuple[str, ...]):
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


_NOTE = "the live original could not be loaded: ModuleNotFoundError: No module named 'funcy'"


def _loadfail_rep(note=_NOTE):
    return types.SimpleNamespace(
        equivalent=[],
        killable=[],
        unclassified=[1, 2],
        inputs_expressible=None,
        load_failed=True,
        note=note,
    )


def test_a_load_failure_has_its_own_repair_route():
    assert repair_measurement_route(("target_load_failed",), False, False) == "fix_load"


def test_the_load_failure_outranks_every_other_cut_reason():
    """Nothing downstream of a failed import is meaningful — no mutant was evaluated, so every
    other reason on the run describes an empty observation."""
    for other in (
        "ambiguous_module_identity",
        "collection_incomplete",
        "budget_exhausted",
        "coverage_truncated",
        "mutant_not_entered",
    ):
        assert repair_measurement_route(("target_load_failed", other), True, True) == "fix_load", other


def test_converge_names_the_dependency_exactly_as_audit_does():
    """THE Finding E property, on the path R1 opened. Both commands read one report; both must
    name `funcy`. Converge printed the generic form here while audit printed the dep."""
    out = "\n".join(_converge_action(_ungateable_result(("target_load_failed",)), _loadfail_rep()))
    assert "No module named 'funcy'" in out
    assert "could not be imported" in out
    assert "--trace-budget" not in out, "a budget cannot fix an import"


def test_a_missing_note_degrades_to_the_typed_sentence_not_a_blank_row():
    """An older engine may not carry the note. The typed reason still names the class of failure;
    what must not happen is an empty '· The error' row implying nothing was reported."""
    out = "\n".join(_converge_action(_ungateable_result(("target_load_failed",)), _loadfail_rep(note="")))
    assert "could not be imported" in out
    assert "· The error" not in out


def test_the_fallback_resolve_no_longer_asserts_an_engine_failure():
    """S7. `mutant_not_entered` means the engine worked perfectly and no test called the mutant;
    telling that operator to 'inspect the reported engine failure' sends them to repair something
    that is not broken. The typed sentence already carries the remedy."""
    out = "\n".join(_converge_action(_ungateable_result(("mutant_not_entered",)), None))
    assert "inspect the reported engine failure" not in out
    assert "the reason above names the repair" in out
    assert "no test ever called them" in out
