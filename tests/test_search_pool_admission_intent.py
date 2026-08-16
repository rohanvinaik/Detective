"""Defer shape-hazardous tests from the speculative search — the pure admission decision.

Usability (ARC dogfood): the converge/diagnose widen (kill-measurement) speculatively traces tests
whose reachability is unconfirmed. A shape-hazardous test (non-hermetic — subprocess/thread/signal/
custom-collector) forces the expensive isolation path, and a 50s live-game system test traced per
widen step dominates cost while almost never being the minimal witness for a unit mutant. So a
non-hermetic test is DEFERRED from the speculative widen by default — and, critically, DISCLOSED,
never silently dropped: ``--include-shaped`` forces them back in.

INTENT test authored from the design: the truth table pins the total function completely, and the
key invariant is that deferral is a NAMED disposition (`defer_shaped`), distinct from admission —
so a caller can count and disclose it rather than lose a suite-kill in silence.
"""

from __future__ import annotations

import itertools

from Detective.engine import search_pool_admission


def test_admission_truth_table():
    # Two booleans, four rows, complete. A hermetic test is ALWAYS admitted regardless of the opt-in;
    # a non-hermetic test is admitted only when the caller opted in, else deferred (disclosed).
    for is_hermetic, include_shaped in itertools.product([False, True], repeat=2):
        if is_hermetic:
            expected = "admit"
        else:
            expected = "admit_shaped" if include_shaped else "defer_shaped"
        assert search_pool_admission(is_hermetic, include_shaped) == expected, (
            is_hermetic,
            include_shaped,
        )


def test_a_hermetic_test_is_never_deferred_even_without_the_opt_in():
    # The default must not touch the cheap floor — only speculative isolation-hazardous tests.
    assert search_pool_admission(True, False) == "admit"


def test_deferral_is_a_distinct_named_code_not_a_dropped_admit():
    # Deferral MUST be its own code so the caller can count + disclose it; collapsing it into a
    # falsy "not admitted" is exactly the silent-exclusion the design forbids.
    deferred = search_pool_admission(False, False)
    assert deferred == "defer_shaped"
    assert deferred not in {"admit", "admit_shaped"}


def test_opt_in_forces_a_shaped_test_back_into_the_pool():
    assert search_pool_admission(False, True) == "admit_shaped"
