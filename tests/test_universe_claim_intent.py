"""W11a — the count-noise label was computed for a wave and rendered to nobody.

`normalize_validity` has flagged `approximate:mutant_universe` on in-process runs since fix A2,
precisely because the SCORED COUNT is run-to-run noisy under shared module state. The pabkit ledger
recorded the consequence without the cause: the label was *"never seen in any output during the
A/B"*. Traced 2026-09-09 — `capability_flags` had **no production consumer**, read only by tests.
Meanwhile the report said `comprehensive — full mutant universe` on exactly those runs.

So the tool measured its own count to be an estimate and then reported it as exact. Same shape as
`state_basis`: a computed signal with nothing consuming it.

A CORRECTION worth keeping, because it changes what the guard can promise. The first sweep for this
concluded the label was absent from `--json` too. It is not: `converge --json` carries it inside
`validity`, because serialization goes through `asdict`/`to_json` by REFLECTION and never names the
field. An AST scan for attribute access cannot see that, and neither can the reference graph — the
same blind spot the no-grep hook names for `getattr` dynamic access. The machine contract was fine;
only the human surface was not.

SCOPE, and why it is narrow on purpose: this is not a soundness hole. Isolated runs are exact and
unflagged, converge re-observes in isolation before certifying, and the certificate rests on the
deterministic proof. What was wrong was one report line claiming an exactness the run had already
measured itself not to have.
"""

from __future__ import annotations

from Detective.cli import universe_claim


def test_the_three_claims_are_three_different_facts() -> None:
    assert universe_claim(fast=True, approximate_universe=False) == "fast_sampled"
    assert universe_claim(fast=False, approximate_universe=True) == "comprehensive_estimated"
    assert universe_claim(fast=False, approximate_universe=False) == "comprehensive_exact"


def test_sampling_outranks_the_count_caveat() -> None:
    """A fast run is already making the weaker claim, and its own (1−1/e) floor is what the reader
    acts on. Qualifying its COUNT as well would bury the stronger caveat under a lesser one."""
    assert universe_claim(fast=True, approximate_universe=True) == "fast_sampled"


def test_an_isolated_run_claims_exactness_because_it_HAS_it() -> None:
    """The direction that keeps this honest rather than merely cautious. `--isolated` does not carry
    the flag, and a blanket caveat on every run would be the same failure inverted — a disclosure
    that is always true is one nobody can act on."""
    assert universe_claim(fast=False, approximate_universe=False) == "comprehensive_exact"


def test_estimated_is_distinct_from_exact_rather_than_folded_into_fast() -> None:
    """Three codes, not two. "we sampled the universe" and "we tested all of it and counted it
    loosely" are different claims with different remedies — re-run comprehensive vs re-run isolated
    — and a bool over `fast` would have made them one."""
    codes = {
        universe_claim(True, False),
        universe_claim(False, True),
        universe_claim(False, False),
    }
    assert len(codes) == 3
