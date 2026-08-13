"""Deletion and minimization weigh tests on the ADMISSIBLE ledger, not the raw union (#59).

Reproduced live (src-layout project, converge cold then warm): on a WARM run the trace cache replays
traces that are proof-inadmissible, so `final_result.line_coverage` (raw) shows lines covered while
`admissible_line_coverage` — what the certificate rests on — is empty. Minimization/redundancy read
the RAW union (converge.py:1930) and the deletion path did too (1698), so converge proposed deleting
a generated test as line-redundant while completeness reported that same line as an uncovered gap:
an impossible residual, and under `--write-dir` a deletion of a test the certificate needs. C feeds
the admissible ledger to both sites, so they agree with completeness.

This pins the CONTRACT at the minimize seam: a line's SOLE admissible coverer must not be judged
redundant just because the raw union shows another (inadmissible) coverer. The end-to-end wiring is
verified by the repro — cold reaches COMPLETE, warm no longer self-contradicts.
"""

from __future__ import annotations

from Detective.minimize import redundant_2axis


def test_a_sole_admissible_coverer_is_not_redundant_even_if_raw_shows_a_co_coverer():
    # `kill_matrix` is `{mutant_id: [killing_test_ids]}`. BOTH tests kill m1, so neither is a unique
    # killer — the kill axis is neutral and redundancy turns on the LINE axis, which is what this
    # pins. `test_keep` is the only ADMISSIBLE coverer of line 5; `test_stale` reaches lines 5 and 9
    # only via a replayed / baseline-red trace, so the admissible ledger bars its coverage.
    km = {"m1": ["test_keep", "test_stale"]}
    raw = {"test_keep": [5], "test_stale": [5, 9]}
    admissible = {"test_keep": [5]}  # test_stale's inadmissible trace excluded

    # RAW union: test_stale covers 5 and 9, so test_keep is line-redundant and gets proposed to drop
    # — exactly the delete-a-needed-test the certificate would then be missing.
    assert "test_keep" in redundant_2axis(km, raw)

    # ADMISSIBLE ledger: test_keep is the sole coverer of line 5, so it is NOT redundant and is kept.
    assert "test_keep" not in redundant_2axis(km, admissible)
