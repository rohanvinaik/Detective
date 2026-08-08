"""The verdict cache admits on the engine's validity verdict, not a correlate (issue #60).

Insertion was gated on `not budget_exhausted`, which answers a narrower question than the one
that matters. A budget overrun is ONE way a measurement becomes invalid; Wesker also refuses to
gate on an uncontained worker, a cut phase, or a coverage depth that never reached the universe,
and reports every one of those as `is_gateable=False` with `budget_exhausted` still False. Each
was stored and later replayed as a verdict — with the fact of its invalidity dropped at the one
point downstream code could no longer recover it.

Wesker #19 widened the window: an uncontained BASELINE TRACE now clears gateability without
touching the budget, so the precise state this check missed became more reachable. An upstream
fix that makes a downstream proxy wronger is the argument for consuming the authoritative signal.
"""

from __future__ import annotations

from Detective.verdict_cache import proof_cache_admits


def test_a_gateable_finished_measurement_is_admitted():
    """The common case must still cache, or the fix costs every run its reuse."""
    assert proof_cache_admits(gateable=True, budget_exhausted=False, engine_reports_gateable=True) is True


def test_a_non_gateable_measurement_is_refused_even_within_budget():
    """THE defect. `is_gateable=False` with `budget_exhausted=False` is exactly the state the
    old proxy admitted — an uncontained worker or a cut phase, stored as replayable proof."""
    assert proof_cache_admits(gateable=False, budget_exhausted=False, engine_reports_gateable=True) is False


def test_budget_exhaustion_still_refuses():
    """The original guard is not replaced, it is joined. A cut run remains inadmissible even if
    the engine somehow reports it gateable."""
    assert proof_cache_admits(gateable=True, budget_exhausted=True, engine_reports_gateable=True) is False


def test_gateability_is_absorbing():
    """No combination of other signals restores it. Downstream may DIAGNOSE a refusal; it may
    never reconstruct it as a pass."""
    assert not any(
        proof_cache_admits(gateable=False, budget_exhausted=b, engine_reports_gateable=True)
        for b in (True, False)
    )


def test_an_engine_that_does_not_report_it_falls_back_to_the_budget_proxy():
    """Absence is not falsehood. An engine that does not publish the field has not said the
    measurement is invalid — it has said nothing, and refusing every insertion on that basis
    would disable the cache entirely. The compatibility decision is explicit and preserves the
    prior behaviour rather than assuming a capability in either direction."""
    assert proof_cache_admits(gateable=False, budget_exhausted=False, engine_reports_gateable=False) is True
    assert proof_cache_admits(gateable=False, budget_exhausted=True, engine_reports_gateable=False) is False


def test_reported_false_and_unreported_are_different_answers():
    """The distinction the fallback rests on: with the field absent the budget decides, with it
    present and False nothing does. A single truthy check would collapse them and silently
    disable the cache against older engines."""
    unreported = proof_cache_admits(gateable=False, budget_exhausted=False, engine_reports_gateable=False)
    reported_false = proof_cache_admits(gateable=False, budget_exhausted=False, engine_reports_gateable=True)
    assert unreported != reported_false
