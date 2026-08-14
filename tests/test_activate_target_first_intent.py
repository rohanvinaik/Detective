"""_activate_target_first: target-first needs a REACHER, and an empty seed is one only with a caller
reach (#15 B) — a leaf orphan falls back to the full baseline.

INTENT: target-first pays off only when a plausible reacher exists to trace (a direct/fixture
candidate, or a caller-reaching test) AND something is deferred to widen. The empty-seed path (0
candidates) is productive ONLY when a caller-reaching test exists — a private target tested through a
public caller. A LEAF ORPHAN (0 candidates, no tested caller) has no reacher: activating would widen
the whole irrelevant suite and bypass the orphan short-circuit, perturbing the verdict — so it must
fall back to the full baseline (the caught regression). A no-reacher target thus behaves exactly as
the pre-caller-stratum code did.
"""

from __future__ import annotations

from Detective.engine import _activate_target_first


def test_a_caller_reacher_on_an_empty_seed_activates_the_caller_only_scenario():
    """#15 B: 0 candidates but a caller-reaching test exists -> seed([]) then widen, never the full
    baseline. n == 1 pins the `> 0` boundary on the deferred count."""
    assert _activate_target_first(0, True, 3, 0) == "seed"
    assert _activate_target_first(0, True, 1, 0) == "seed"


def test_a_leaf_orphan_with_no_reacher_falls_back_to_the_full_baseline():
    """The regression fix: 0 candidates AND no caller-reaching test (a leaf nothing reaches) -> full
    baseline, preserving the orphan short-circuit. Activating would widen an irrelevant suite."""
    assert _activate_target_first(0, False, 3, 0) == "full_baseline"
    assert _activate_target_first(0, False, 1, 0) == "full_baseline"


def test_a_candidate_reacher_with_something_deferred_seeds():
    """A direct/fixture candidate is a reacher; a deferred unknown or an excluded impossible makes the
    split proper. n == 1 pins the `> 0` boundary on candidate and unknown counts."""
    assert _activate_target_first(2, False, 5, 0) == "seed"
    assert _activate_target_first(1, False, 0, 2) == "seed"
    assert _activate_target_first(1, False, 1, 0) == "seed"


def test_nothing_deferred_falls_back_even_with_a_reacher():
    """Everything is a candidate (nothing to widen or exclude) -> the seed equals the suite, no
    benefit -> full baseline."""
    assert _activate_target_first(4, False, 0, 0) == "full_baseline"
    assert _activate_target_first(1, True, 0, 0) == "full_baseline"


def test_a_deferred_impossible_alone_with_a_reacher_seeds():
    """Only an excluded impossible deferred (no unknown) still benefits — the seed drops it. n == 1
    pins the `> 0` boundary on the impossible count."""
    assert _activate_target_first(1, False, 0, 1) == "seed"
