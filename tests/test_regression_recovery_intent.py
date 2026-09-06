"""The regression guard retries the un-minimized suite before restoring the prior one (#62, reopened
2026-09-06 by the dogfood sweep on `typed_synthesis._extract`).

The defect: the guard compares this run's suite to the one on disk as obligation sets and, on any
regression, restored the prior file. When MINIMIZATION was what regressed — a redundancy call made
on a live-session kill matrix dropped a test the prior suite needed — the restore also threw away
the distinguishing tests the witness pass had just written. Measured, three runs in a row: witness
pass "+4 distinguishing kill tests", "minimizing — dropped 3", "kept the suite already on disk —
this run's would stop pinning contract:LOGICAL_42de79ad", and the verdict "5 killable — a witness
exists for each". A loop with no exit, on a region whose inputs were all authored.

The decision, pinned from intent: nothing regressed → ship; the minimized suite regressed and the
superset built before trimming has not been tried → retry it (it holds every test the prior pinned
plus the new witnesses; minimality is the price, never the proof); otherwise → restore the prior.
"""

from __future__ import annotations

import pytest

from Detective.converge import RESTORE_PRIOR, RETRY_UNMINIMIZED, SHIP, regression_recovery


def test_no_regression_ships_whatever_was_built():
    assert regression_recovery(False, False, False) == SHIP
    assert regression_recovery(False, True, False) == SHIP
    assert regression_recovery(False, True, True) == SHIP


def test_a_regressed_minimized_suite_is_retried_un_minimized_once():
    assert regression_recovery(True, True, False) == RETRY_UNMINIMIZED


def test_a_regression_with_nothing_left_to_try_restores_the_prior():
    # Never minimized: there is no superset to fall back to.
    assert regression_recovery(True, False, False) == RESTORE_PRIOR
    # Already retried: the superset regressed too.
    assert regression_recovery(True, True, True) == RESTORE_PRIOR


@pytest.mark.parametrize("minimized", [False, True])
def test_a_retry_never_happens_twice(minimized):
    assert regression_recovery(True, minimized, True) != RETRY_UNMINIMIZED
