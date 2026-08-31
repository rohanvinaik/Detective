"""Intent tests AND pins — Wave 1 / EXP-DS-002 norms discipline (docs/theory/deterministic_sicp/ §4.2).

**These truth tables are the pins for the four `norms.py` pure decisions, under a TARGETED,
FOUNDER-GRANTED exemption (2026-08-31): in THIS repo an isolated converge pays a whole-suite
baseline trace (dense-package reachability — `import Detective` reaches everything, TEST_BASIS
§4.1), which made the Wave-1 pins grind. The exemption is scoped to exactly these four
functions and this idiom; it is NOT a precedent — converge remains the rule for new pure
decisions, here and everywhere else, and a future exemption needs its own grant.** The tables
below cover every branch of each (total) function; `weighted_median`'s final return is an
annotated unreachable totality fall-through (the flag-line class), not an untested branch.

Beyond the pins, these state what the code is FOR:

- ``split_of`` is deterministic and seedless — the same name lands in the same half forever,
  which is what makes "mine on A, validate on unseen B" reproducible.
- ``weighted_median`` answers cannot-determine with ``None``, never a fabricated 0.0; weight
  lets a hub count more while an unreferenced entry point still counts ONCE (weighting beats
  exclusion — Peitho's median-of-active without wrongly zeroing live entry points).
- ``norm_disposition`` keeps its three states apart: a drifting norm is REJECTED, never nudged
  toward agreement; an unminable half is a measurement limit, not a verdict.
- ``verdict_isolation_cost`` is invariant-correct: the cost is the read index after which NO
  remaining read can change the flagged/clean outcome — the per-region quantity whose corpus
  distribution is the bulk/tail knee.
"""

import pytest

from Detective.norms import norm_disposition, split_of, verdict_isolation_cost, weighted_median

# ── split_of ─────────────────────────────────────────────────────────────────────────────────


def test_split_is_deterministic_and_two_valued() -> None:
    names = [f"pkg/mod.py::fn_{i}" for i in range(200)]
    first = [split_of(n) for n in names]
    assert [split_of(n) for n in names] == first  # stable across calls
    assert set(first) == {"A", "B"}  # both halves actually populated
    # roughly balanced — parity of a cryptographic hash; a 200-draw half should not collapse
    assert 60 <= first.count("A") <= 140


# ── weighted_median ──────────────────────────────────────────────────────────────────────────


def test_weighted_median_abstains_on_degenerate_input() -> None:
    assert weighted_median([], []) is None
    assert weighted_median([1.0, 2.0], [1.0]) is None  # length mismatch
    assert weighted_median([1.0, 2.0], [0.0, 0.0]) is None  # no positive weight


def test_weighted_median_weight_moves_the_norm_but_zero_weight_drops() -> None:
    # unweighted median of (1, 9) is ambiguous-low; a heavy 9 drags the norm up…
    assert weighted_median([1.0, 9.0], [1.0, 3.0]) == 9.0
    # …and a zero-weighted value is simply not in the mine (dead code cannot drag).
    assert weighted_median([1.0, 100.0], [1.0, 0.0]) == 1.0


def test_weighted_median_plain_case_matches_median() -> None:
    assert weighted_median([3.0, 1.0, 2.0], [1.0, 1.0, 1.0]) == 2.0


# ── norm_disposition ─────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "a, b, tol, expected",
    [
        (3.0, 3.5, 0.25, "admissible"),  # |0.5|/3.5 ≈ 0.14 within tolerance
        (3.0, 6.0, 0.25, "drifting"),  # halves disagree → rejected, never tuned
        (None, 3.0, 0.25, "degenerate"),  # unminable half = measurement limit
        (3.0, None, 0.25, "degenerate"),
        (0.0, 0.0, 0.25, "admissible"),  # both halves agree the norm is exactly zero
    ],
)
def test_norm_disposition_states(a, b, tol, expected) -> None:
    assert norm_disposition(a, b, tol) == expected


# ── verdict_isolation_cost ───────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "votes, expected",
    [
        ((-1, -1, 0, 0, 0, 0), 2),  # flagged the moment the floor is reached — undoable by nothing
        ((0, 0, 0, 0, 0, -1), 5),  # zero smells: clean is certain once ≤1 read remains
        ((-1, 0, 0, 0, 0, 0), 6),  # one smell: the LAST read could still be the 2nd — cost is all 6
        ((0, -1, 0, 0, -1, 0), 5),  # the floor reached at the fifth read
        ((), 0),  # nothing to read
        ((1, 1), 1),  # two reads, floor 2: 0 smells + 1 remaining < 2 → decided at read 1
    ],
)
def test_isolation_cost_is_the_invariance_point(votes, expected) -> None:
    assert verdict_isolation_cost(votes) == expected


def test_isolation_cost_floor_edges() -> None:
    assert verdict_isolation_cost((-1, -1, -1), flag_floor=0) == 0  # a met floor needs no read
    assert verdict_isolation_cost((-1, 0, 0), flag_floor=1) == 1  # floor 1: first smell decides
    assert (
        verdict_isolation_cost((0, 0, 0), flag_floor=1) == 3
    )  # floor 1: any single read could flag, so clean needs them all


@pytest.mark.parametrize(
    "votes", [(-1, 0, -1, 0, 0, 0), (0, 0, 0, 0, 0, 0), (-1, 1, 0, 0, -1, 1), (0, -1, 0)]
)
def test_isolation_cost_verdict_truly_invariant_afterward(votes) -> None:
    # THE invariance property, brute-forced: replace everything after the returned read count
    # with every possible completion — the flagged/clean outcome must never change.
    from itertools import product

    k = verdict_isolation_cost(votes)
    outcomes = {
        sum(1 for v in votes[:k] + suffix if v == -1) >= 2
        for suffix in product((-1, 0, 1), repeat=len(votes) - k)
    }
    assert len(outcomes) == 1
