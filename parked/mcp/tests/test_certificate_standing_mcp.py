"""PARKED with the MCP surface (see parked/mcp/README.md): the MCP renderer's half of
tests/test_certificate_standing_intent.py (Detective #17, #38, #60).

Split out 2026-09-13. These tests import `Detective.mcp_server`, which does not exist while the
surface is parked; they run again once it is restored to the package. The certificate-standing
tests that never touched a renderer stayed where they were.
"""

from __future__ import annotations

import dataclasses
from types import SimpleNamespace

from Detective.converge import ConvergeResult
from Detective.mcp_server import _render_converge


def _result(**overrides) -> ConvergeResult:
    base = ConvergeResult(
        function="m.py::f",
        converged=True,
        at_ceiling=False,
        initial_survivors=[],
        final_survivors=[],
        iterations=1,
        written_path="",
        total_mutants=10,
        killed=10,
    )
    fields = {"functionally_complete": True, "line_complete": True, **overrides}
    return dataclasses.replace(base, **fields)


def _verification(ok: bool, status: str = "tests_failed") -> SimpleNamespace:
    return SimpleNamespace(ok=ok, status="passed" if ok else status)


def _rendered(**overrides) -> str:
    result = _result(**overrides)
    return _render_converge(result, "m.py", "f", None)


def test_the_mcp_surface_refuses_a_stale_measurement():
    """It used to print "DONE: every killable mutant is killed" over a void measurement."""
    text = _rendered(stale_target=True)
    assert "STOP" in text
    assert "CHANGED" in text
    assert "DONE" not in text


def test_the_mcp_surface_refuses_an_unverified_basis():
    text = _rendered(verification=_verification(False, "collection_failed"))
    assert "STOP" in text
    assert "collection_failed" in text
    assert "DONE" not in text


def test_the_mcp_surface_still_reports_a_clean_run():
    """A guard that refuses everything would pass both tests above and be useless."""
    text = _rendered(verification=_verification(True))
    assert "STOP" not in text


def test_the_mcp_renderer_reads_the_same_derivation():
    """The renderer's half of `test_every_surface_reads_the_same_derivation`, split out when the
    surface was parked: the renderer must refuse exactly the standings the property refuses, over
    the same cases — including the `ungateable` one that exposed the drift (#60)."""
    cases = [
        {"stale_target": True},
        {"verification": _verification(False)},
        {"verification": _verification(True)},
        {"functionally_complete": False},
        {"line_complete": False},
        {},
        # The case the five-argument call could not reach: the engine reports gateable while a cut
        # reason is present, which is the absorbing seam (#60) and the shape of every in-repo
        # target that refuses with `mutant_not_entered`.
        {"measurement_gateable": True, "cut_reasons": ("mutant_not_entered",)},
        {"measurement_gateable": False, "cut_reasons": ("uncontained_worker",)},
    ]
    refusing = ("stale", "unverified", "ungateable")
    for overrides in cases:
        result = _result(**overrides)
        refused = "STOP" in _render_converge(result, "m.py", "f", None)
        assert refused is (result.standing in refusing), overrides


def test_the_mcp_surface_names_the_cut_reason_rather_than_guessing_at_it():
    """The refusal branch hardcoded "the profile was cut, or a timed-out worker could not be
    contained ... re-run with a larger budget" — two causes offered for eleven typed reasons, which
    is S13's collapse in a second renderer. `cut_reason_sentence`'s docstring names this surface:
    "ONE OWNER, because #60 requires CLI, --json, MCP and receipts to preserve IDENTICAL cut
    reasons"."""
    text = _rendered(measurement_gateable=True, cut_reasons=("mutant_not_entered",))
    assert "STOP" in text
    assert "DONE" not in text
    assert "mutant_not_entered" in text, "the reason is named, not paraphrased"
    assert "larger budget" not in text, "a remedy that cannot help this cause"


def test_the_mcp_refusal_uses_the_same_sentence_the_other_surfaces_do() -> None:
    from Detective.validity import cut_reason_sentence

    text = _rendered(measurement_gateable=True, cut_reasons=("target_load_failed",))
    assert cut_reason_sentence("target_load_failed") in text
