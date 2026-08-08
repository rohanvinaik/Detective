"""Intent tests for what a converge result may CLAIM (Detective #17, #38).

Both issues are one defect wearing two hats: a fact the engine computed correctly did not reach
every surface that speaks for it.

  #17  the target file changed mid-run, so the kill-count and line numbers describe a source that
       no longer exists — and `complete` returned True anyway
  #38  the proof basis did not come back green under real pytest — the CLI knew, the MCP surface
       did not

MEASURED BEFORE THE FIX: a `ConvergeResult` with `stale_target=True` and nothing else wrong
returned `complete == True`. The path is worth stating because it is not an oversight anyone
would spot by reading: staleness SKIPS verification (there is nothing worth verifying against a
moved source), which leaves `verification is None`, and the old gate refused only on a
verification that RAN AND FAILED. So the strongest possible objection — "this measurement is
void" — fell through the one branch designed to catch a weaker one.

These tests are written from what a certificate is FOR. The generated suites alongside them pin
behaviour, so they would have happily pinned `complete == True` on a stale result.

The load-bearing test is `test_every_surface_reads_the_same_derivation`. Three places answered
this question and disagreed; a test that only checks one of them is how they drifted apart in
the first place.
"""

from __future__ import annotations

import dataclasses
from types import SimpleNamespace

from Detective.converge import ConvergeResult, certificate_standing
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


# --------------------------------------------------------------------------------------
# #17 — a measurement against a source that moved
# --------------------------------------------------------------------------------------


def test_a_stale_run_is_not_complete():
    """The exact regression. Everything else about this result is perfect."""
    assert _result(stale_target=True).complete is False


def test_a_stale_run_is_its_own_state_not_merely_incomplete():
    """ "Incomplete" invites the reader to go close a gap — computed against moved lines.

    The distinction is the whole point of a named code: a stale run's numbers are not small,
    they are void, and the only correct next action is to re-run rather than to write a test.
    """
    assert certificate_standing(True, True, True, False, False) == "stale"
    assert certificate_standing(False, False, True, False, False) == "stale"


def test_staleness_outranks_a_failed_verification():
    """Both true means the verification also ran against the moved source, so naming the
    verification would send the reader to debug a result that never meant anything."""
    assert certificate_standing(True, True, True, True, False) == "stale"


# --------------------------------------------------------------------------------------
# #38 — a basis that does not run
# --------------------------------------------------------------------------------------


def test_a_red_proof_basis_is_not_complete():
    assert _result(verification=_verification(False)).complete is False


def test_a_green_proof_basis_is_complete():
    assert _result(verification=_verification(True)).complete is True


def test_a_verification_that_never_ran_changes_nothing():
    """The subprocess is paid for only when the run is otherwise complete. A None must keep
    meaning "not computed", never "failed" — otherwise every already-incomplete run acquires a
    second, invented reason."""
    assert certificate_standing(True, True, False, False, False) == "complete"
    assert _result(verification=None).complete is True


def test_an_honest_gap_is_incomplete_and_nothing_else():
    assert certificate_standing(False, True, False, False, False) == "incomplete"
    assert certificate_standing(True, False, False, False, False) == "incomplete"


def test_a_clean_run_is_complete():
    assert certificate_standing(True, True, False, True, True) == "complete"


# --------------------------------------------------------------------------------------
# The surfaces
# --------------------------------------------------------------------------------------


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


def test_every_surface_reads_the_same_derivation():
    """THE anti-drift test.

    `complete` and the MCP renderer both answer "may this be presented as a certificate", and
    they answered it independently — which is exactly how one came to refuse a stale run while
    the other announced it was done. Any future state added to `certificate_standing` is checked
    against both here, rather than against whichever surface the author happened to be editing.
    """
    cases = [
        {"stale_target": True},
        {"verification": _verification(False)},
        {"verification": _verification(True)},
        {"functionally_complete": False},
        {"line_complete": False},
        {},
    ]
    for overrides in cases:
        result = _result(**overrides)
        standing = certificate_standing(
            result.functionally_complete,
            result.line_complete,
            result.stale_target,
            result.verification is not None,
            result.verification is not None and result.verification.ok,
        )
        assert result.complete is (standing == "complete"), overrides
        refused = "STOP" in _render_converge(result, "m.py", "f", None)
        assert refused is (standing in ("stale", "unverified")), overrides
