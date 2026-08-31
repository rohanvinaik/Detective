"""Intent tests AND pins — Wave 2 / EXP-DS-003, the budget bank (docs/theory/deterministic_sicp/ §7).

**Pin status, and the second targeted exemption (founder-granted 2026-08-31: "I agree with B.
This is specifically a problem here, in this situation").** `growth_class` carries an
engine-written synth (`tests/detective/test_Detective_budget_growth_class_*_synth.py`, banked
before the batch was stopped). The other three pure decisions — `budget_verdict`,
`paired_disposition`, `ladder_value` — are pinned by the truth tables below, under the same
scoped exemption as Wave 1's: in this repo a pin BATCH is serial-cold by construction (each
pin's own synth write invalidates the session baseline and the next pin's trace cache — the
thrice-observed idiom, recorded in the paper's Wave 2 entry). Scope: these three functions,
this idiom, this repo. NOT a precedent; converge remains the rule, and the next exemption
needs its own grant.

What the code is FOR, stated from intent:

- The efficiency observable is a COUNT, never wall-clock; its boundary is stated (Python-level
  opcodes — C work is invisible and the read never claims otherwise).
- ``growth_class`` names coarse bands with stated boundaries and answers "unmeasurable" on
  anything degenerate — never a fabricated class off bad points.
- ``budget_verdict`` lets asymptotic class DOMINATE the small-n ratio, and holds the parity
  band open ("no payoff measured" is a real outcome, distinct from refund and regression).
- ``paired_disposition`` is the two-ledger law: NO budget number means anything under a nonzero
  behavior delta — "inadmissible" outranks every verdict.
- ``count_opcodes`` is deterministic on fixed inputs (the whole point) and restores any
  pre-existing trace hook (a session/coverage tracer must survive the instrument).
"""

import sys

import pytest

from Detective.budget import (
    budget_verdict,
    count_opcodes,
    growth_class,
    ladder_value,
    paired_disposition,
)

# ── growth_class ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "sizes, counts, expected",
    [
        ([2, 4, 8], [5, 5], "unmeasurable"),  # length mismatch
        ([2, 4], [5, 9], "unmeasurable"),  # too few points
        ([2, 4, 4], [1, 2, 3], "unmeasurable"),  # non-increasing size
        ([2, 4, 8], [1, 0, 4], "unmeasurable"),  # non-positive count
        ([2, 4, 8, 16, 32], [7, 7, 7, 7, 7], "constant"),
        ([2, 4, 8, 16, 32], [10, 20, 40, 80, 160], "linear"),
        ([2, 4, 8, 16, 32], [4, 16, 64, 256, 1024], "quadratic_plus"),
        ([2, 4, 8, 16, 32], [10, 14, 20, 28, 40], "sublinear"),  # ~sqrt growth (slope 0.5)
        ([2, 4, 8, 16, 32], [10, 28, 79, 223, 630], "superlinear"),  # ~n^1.5
    ],
)
def test_growth_class_bands(sizes, counts, expected) -> None:
    assert growth_class([float(s) for s in sizes], [float(c) for c in counts]) == expected


def test_growth_class_tail_ignores_warmup_noise() -> None:
    # A noisy first hop (interpreter warmup shapes) must not name the band: the tail is linear.
    sizes = [2.0, 4.0, 8.0, 16.0, 32.0, 64.0]
    counts = [100.0, 110.0, 220.0, 440.0, 880.0, 1760.0]  # flat hop, then clean doubling
    assert growth_class(sizes, counts) == "linear"


# ── budget_verdict ───────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "inc, cand, ratio, expected",
    [
        ("quadratic_plus", "linear", 1.5, "refund"),  # class dominates a worse small-n ratio
        ("linear", "quadratic_plus", 0.5, "regression"),  # …in both directions
        ("linear", "linear", 0.5, "refund"),  # same class, cheaper inside the band
        ("linear", "linear", 1.0, "parity"),  # the honest "no payoff measured"
        ("linear", "linear", 1.3, "regression"),
        ("unmeasurable", "linear", 1.0, "unmeasurable"),
        ("linear", "linear", 0.0, "unmeasurable"),  # a non-positive ratio is no measurement
    ],
)
def test_budget_verdict(inc, cand, ratio, expected) -> None:
    assert budget_verdict(inc, cand, ratio) == expected


# ── paired_disposition — the two-ledger law ──────────────────────────────────────────────────


def test_nonzero_delta_is_inadmissible_regardless_of_payoff() -> None:
    assert paired_disposition(False, "refund") == "inadmissible"
    assert paired_disposition(False, "parity") == "inadmissible"


def test_zero_delta_passes_the_verdict_through_untouched() -> None:
    for v in ("refund", "parity", "regression", "unmeasurable"):
        assert paired_disposition(True, v) == v


# ── ladder_value ─────────────────────────────────────────────────────────────────────────────


def test_ladder_values_are_sized_and_deterministic() -> None:
    assert ladder_value("list[int]", 8) == ladder_value("list[int]", 8)  # no randomness, ever
    assert len(ladder_value("list[int]", 8)) == 8
    assert len(ladder_value("str", 7)) == 7
    assert len(ladder_value("dict[str,int]", 5)) == 5
    assert ladder_value("Account", 8) is None  # outside the expressible allowlist: no ladder
    assert ladder_value("list[int]", 0) is None  # non-positive size: cannot-determine


# ── count_opcodes — the instrument shell ─────────────────────────────────────────────────────


def _quadratic_dupes(xs: list) -> list:
    out = []
    for i, a in enumerate(xs):
        for b in xs[i + 1 :]:
            if a == b and a not in out:
                out.append(a)
    return out


def test_count_is_deterministic_and_grows_with_input() -> None:
    xs = ladder_value("list[int]", 16)
    a = count_opcodes(_quadratic_dupes, (xs,))
    assert a == count_opcodes(_quadratic_dupes, (xs,))  # deterministic on fixed input
    assert a is not None and a > 0
    bigger = count_opcodes(_quadratic_dupes, (ladder_value("list[int]", 32),))
    assert bigger is not None and bigger > a


def test_count_reads_none_on_crash_and_releases_its_tool_slot() -> None:
    assert count_opcodes(lambda x: 1 // x, (0,)) is None  # a crashed arm has no budget read
    # The slot must be free again — a surrounding session's monitoring survives the instrument.
    mon = sys.monitoring
    mon.use_tool_id(5, "slot-free-check")  # would raise ValueError if the instrument leaked it
    mon.free_tool_id(5)


def test_count_abstains_when_no_tool_slot_is_free() -> None:
    mon = sys.monitoring
    held = []
    try:
        for slot in (2, 3, 4, 5):
            try:
                mon.use_tool_id(slot, f"hog-{slot}")
                held.append(slot)
            except ValueError:
                pass  # already held by the environment — even better for this test
        assert count_opcodes(len, ([1, 2],)) is None  # no slot → cannot-determine, never a guess
    finally:
        for slot in held:
            mon.free_tool_id(slot)
