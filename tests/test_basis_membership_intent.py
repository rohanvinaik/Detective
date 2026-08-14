"""basis_membership warrants each test's evidentiary role — the FunctionBasis lattice (#D1 §9).

Written from intent (TEST_BASIS §9 / §2.1), not from current output. The observed-vs-admissible
distinction is the project's recurring measurement/decision defect (§4.6), so the five warrants must
stay DISTINCT — "we did not observe this", "we observed it and it proves", and "we observed it but
it only orders" must never render identically. The generated *_synth golden is characterization; this
file pins the meaning. Input-synthesis cannot guess domain string literals like the ('non_reach',
'fresh') pair, so the `disjoint` branch is only reachable from an authored call — here.
"""

from __future__ import annotations

from Detective.engine import basis_membership


def test_fresh_admissible_cover_is_proof():
    # The only warrant that may discharge an obligation (enter B_t).
    assert basis_membership("covers", "fresh", "admissible") == "proof"


def test_a_replayed_cover_only_routes():
    # §2.1: a replayed positive may order, never prove — even though it covers.
    assert basis_membership("covers", "replayed", "admissible") == "routing"


def test_an_inadmissible_cover_only_routes():
    # Truncated / uncontained: observed, but cannot be evidence of presence (§2.1).
    assert basis_membership("covers", "fresh", "inadmissible") == "routing"


def test_a_baseline_barred_cover_is_barred_even_when_fresh_or_replayed():
    # §4.6: an inert / baseline-failing test is barred by its outcome, regardless of freshness —
    # the baseline bar is the stronger fact and must not be reported as mere "routing".
    assert basis_membership("covers", "fresh", "barred") == "barred"
    assert basis_membership("covers", "replayed", "barred") == "barred"


def test_a_fresh_non_reach_is_disjoint_the_only_warrant_that_may_exclude():
    # §2.1 / the Three-Layer Law: only a FRESH outcome-qualified non-reach may exclude.
    assert basis_membership("non_reach", "fresh", "admissible") == "disjoint"


def test_a_replayed_non_reach_is_pending_not_disjoint():
    # A non-reach not freshly re-observed cannot exclude here; replay-exclusion is decided upstream
    # under a complete regime (§2.2/B3), never from this per-item lattice. Absence ≠ falsehood.
    assert basis_membership("non_reach", "replayed", "admissible") == "pending"


def test_an_unseen_item_is_pending():
    # Never observed: the stratum rank is the only prior; it is not disjoint and not proof.
    assert basis_membership("unseen", "fresh", "admissible") == "pending"
