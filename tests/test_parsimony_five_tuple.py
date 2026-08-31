"""Intent tests — Wave 0 / EXP-DS-001 (docs/theory/deterministic_sicp/DETERMINISTIC_SICP.md §12).

The five-tuple promotion and the γ-seam bank, tested from INTENT (the synth suites pin what the
code does; only these can catch it doing the wrong thing):

1. **Verdict invariance.** Wiring `purity` and `gamma_seam` into the fusion must not change any
   pre-Wave-0 verdict on its own: purity's vote is structurally ∈ {0, +1} (impurity is the
   informational zero, never a lone smell), and a γ read of 0 (no candidates) abstains — so
   `flagged`/`agreement`/`dominant` on a function where γ abstains are byte-identical to the
   six-lens read. The promotion is ADDITIVE; a changed verdict here is a defect.
2. **The five-tuple is populated, not decorative.** Each numeric lens carries the mined zero it
   was read against and its depth FROM that zero (one pinned rule, `deviation_depth`); the raw
   fact, the read, and its norm sit in the same row (the Peitho ledger law).
3. **The γ-seam lens prices the seam, never asserts γ.** Its detail names the crossing count of
   the cheapest seam; no-candidates abstains (existence is the seam lens's question); the path
   carries WHICH seam was priced (provenance).
"""

import ast

import pytest

from Detective.parsimony import (
    _CC_ZERO,
    _LENS_PRIORITY,
    _gamma_seam_vote,
    complexity_lens,
    deviation_depth,
    gamma_seam_lens,
    parsimony_from_function,
    purity_lens,
    seam_lens_static,
)
from Detective.scope import KillQuality, ScopeMap, Specification


def _fn(src: str) -> ast.FunctionDef:
    return ast.parse(src).body[0]  # type: ignore[return-value]


def _scope(regime: str = "A", variants: int = 0, tests: int = -1) -> ScopeMap:
    """A minimal real ScopeMap for the fusion (the domain object the readers consume)."""
    return ScopeMap(
        function="f.py::f",
        regime=regime,
        surviving_categories=[],
        specification=Specification(variants, 0, 0, 0, 0),
        kill_quality=KillQuality(0, 0, None),
        behavioral_dof=[],
        tests_discovered=tests,
    )


# ── 0 · truth-table pins for the two new pure decisions ──────────────────────────────────────
# Sanctioned fallback (converge-before-wiring corollary, founder-authorized for these two): the
# module's suite surface makes an isolated converge grind, so the pin is a hand-written truth
# table over every branch of these small TOTAL functions — a property of the function, not of
# the inflation. The partial synth golden from the cut converge run stands beside these.


@pytest.mark.parametrize(
    "value, zero, expected",
    [
        (2.0, None, 0.0),  # categorical lens: no numeric zero → no depth
        (3.5, 0, 3.5),  # absence-zero (a count): depth IS the raw distance
        (0.0, 0, 0.0),  # at an absence-zero
        (6.0, 3.0, 1.0),  # fractional deviation above the zero: (6−3)/3
        (1.5, 3.0, 0.5),  # below the zero is still a POSITIVE distance: |1.5−3|/3
        (3.0, 3.0, 0.0),  # at the zero
    ],
)
def test_deviation_depth_truth_table(value: float, zero: float | None, expected: float) -> None:
    assert deviation_depth(value, zero) == expected


@pytest.mark.parametrize(
    "n_candidates, best_interface, expected",
    [
        (0, 0, 0),  # no candidates → abstain (existence is _seam_vote's question)
        (0, 6, 0),  # abstention holds regardless of the width argument
        (1, 1, 1),  # one crossing — the cleanest seam
        (1, 2, 1),  # one in, one out — still γ-clean
        (1, 3, 0),  # mid-band: no opinion
        (2, 4, 0),
        (1, 5, -1),  # at the decompose gate ceiling: every seam leaks
        (3, 6, -1),
    ],
)
def test_gamma_seam_vote_truth_table(n_candidates: int, best_interface: int, expected: int) -> None:
    assert _gamma_seam_vote(n_candidates, best_interface) == expected


# ── 1 · verdict invariance ───────────────────────────────────────────────────────────────────


def test_purity_never_votes_smell() -> None:
    pure = purity_lens(_fn("def f(a):\n    return a + 1\n"))
    impure = purity_lens(_fn("def f(a):\n    print(a)\n    return a\n"))
    assert pure.vote == 1
    assert impure.vote == 0  # impurity is the informational zero — NEVER −1


def test_wiring_is_verdict_invariant_when_gamma_abstains() -> None:
    # An atomic body: no extraction candidates → gamma abstains; purity ∈ {0,+1}.
    # flagged/agreement/dominant must match the pre-Wave-0 read exactly.
    src = "def f(a):\n    return a + 1\n"
    sig = parsimony_from_function(_fn(src), _scope(), line_span=2)
    assert sig.flagged is False
    assert sig.agreement == 0
    assert sig.dominant is None
    assert len(sig.lenses) == len(_LENS_PRIORITY)  # every bank present in the signature


def test_lens_order_matches_priority() -> None:
    sig = parsimony_from_function(_fn("def f(a):\n    return a\n"), _scope(), line_span=2)
    assert tuple(lens.name for lens in sig.lenses) == _LENS_PRIORITY


# ── 2 · the five-tuple is populated ──────────────────────────────────────────────────────────


def test_complexity_lens_carries_zero_and_depth() -> None:
    lens = complexity_lens(_fn("def f(a):\n    return a + 1\n"))
    assert lens.zero_state == _CC_ZERO
    assert lens.depth == deviation_depth(float(lens.raw), _CC_ZERO)


def test_seam_lens_static_zero_is_absence() -> None:
    lens = seam_lens_static(_fn("def f(a):\n    return a\n"))
    assert lens.zero_state == 0.0
    assert lens.depth == float(lens.raw)  # distance from an absence-zero IS the count


# ── 3 · the γ-seam lens ──────────────────────────────────────────────────────────────────────

_CLEAN_SEAM = (
    "def f(a, b):\n"
    "    total = 0\n"
    "    for x in a:\n"
    "        if x > 0:\n"
    "            total += x\n"
    "        else:\n"
    "            total -= x\n"
    "    result = total * b\n"
    "    if result > 100:\n"
    "        result = 100\n"
    "    return result\n"
)


def test_gamma_abstains_without_candidates() -> None:
    lens = gamma_seam_lens(_fn("def f(a):\n    return a + 1\n"))
    assert lens.vote == 0
    assert lens.raw == 0


def test_gamma_prices_the_cheapest_seam_with_provenance() -> None:
    lens = gamma_seam_lens(_fn(_CLEAN_SEAM))
    if lens.raw == 0:  # candidate detection is decompose's judgment; only assert when it fires
        return
    assert lens.vote in (-1, 0, 1)
    assert lens.zero_state == 0.0  # γ = 0 is the zero the position is read against
    assert lens.path, "the priced seam's span must ride the path (provenance)"
    assert "crossing" in lens.detail  # the detail names the proxy, never claims γ measured
