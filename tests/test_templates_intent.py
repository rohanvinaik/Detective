"""Intent tests — Wave 3 / EXP-DS-004, the template library (docs/theory/deterministic_sicp/ §6).

The seeded expert-labeled corpus for the taste-as-recognition claim: per template, positives
that MUST fire and adversarial near-misses that MUST NOT (a recognizer that matches a near-miss
invites a wrong transform — conservatism is the law, and every negative here encodes one way a
shape can *rhyme* without being the shape). The labels are the founder-side expert judgment of
record for v1; a held-out third-party-labeled corpus is future work, stated in the paper.

Recognizers are the unit-guarded AST harvest class (parsimony's standing classification) —
these fixtures ARE their guard. The discharge property (the transform un-fires its own
recognizer) is tested here per template and measured with budget payoff in EXP-DS-004.
"""

import ast

import pytest

from Detective.templates import (
    TEMPLATE_GRAMMAR,
    recognize_accumulator_series,
    recognize_loop_invariant_recompute,
    recognize_manual_index_iteration,
    recognize_memoizable_pure_recursion,
    recognize_quadratic_membership_scan,
    template_matches,
)


def _fn(src: str) -> ast.FunctionDef:
    return ast.parse(src).body[0]  # type: ignore[return-value]


# ── memoizable_pure_recursion ────────────────────────────────────────────────────────────────

_FIB = "def fib(n):\n    if n < 2:\n        return n\n    return fib(n - 1) + fib(n - 2)\n"
_FIB_MEMO = (
    "def fib(n, memo=None):\n"
    "    memo = {} if memo is None else memo\n"
    "    if n < 2:\n"
    "        return n\n"
    "    if n not in memo:\n"
    "        memo[n] = fib(n - 1, memo) + fib(n - 2, memo)\n"
    "    return memo[n]\n"
)
_IMPURE_RECURSION = "def walk(n):\n    print(n)\n    if n > 0:\n        return walk(n - 1)\n    return 0\n"


def test_pure_recursion_fires_on_fib() -> None:
    m = recognize_memoizable_pure_recursion(_fn(_FIB))
    assert m is not None and m.template == "memoizable_pure_recursion"


def test_impure_recursion_is_a_near_miss() -> None:
    # Memoizing an effectful function CHANGES behavior — the recognizer must abstain.
    assert recognize_memoizable_pure_recursion(_fn(_IMPURE_RECURSION)) is None


def test_non_recursive_pure_function_abstains() -> None:
    assert recognize_memoizable_pure_recursion(_fn("def f(a):\n    return a + 1\n")) is None


# ── quadratic_membership_scan ────────────────────────────────────────────────────────────────

_LIST_SCAN = (
    "def dedupe(xs):\n"
    "    out = []\n"
    "    for x in xs:\n"
    "        if x not in out:\n"
    "            out.append(x)\n"
    "    return out\n"
)
_SET_SCAN = (
    "def dedupe(xs):\n"
    "    seen = set()\n"
    "    out = []\n"
    "    for x in xs:\n"
    "        if x not in seen:\n"
    "            seen.add(x)\n"
    "            out.append(x)\n"
    "    return out\n"
)
_PARAM_SCAN = (
    "def f(xs, allowed):\n"
    "    out = []\n"
    "    for x in xs:\n"
    "        if x in allowed:\n"
    "            out.append(x)\n"
    "    return out\n"
)


def test_list_membership_scan_fires() -> None:
    m = recognize_quadratic_membership_scan(_fn(_LIST_SCAN))
    assert m is not None and "out" in m.evidence


def test_set_membership_is_already_right_and_must_not_match() -> None:
    assert recognize_quadratic_membership_scan(_fn(_SET_SCAN)) is None


def test_unknown_typed_param_abstains() -> None:
    # `allowed` has no local list evidence — its type is not knowable here; a conservative
    # recognizer does not guess (it might already be a set).
    assert recognize_quadratic_membership_scan(_fn(_PARAM_SCAN)) is None


# ── loop_invariant_recompute ─────────────────────────────────────────────────────────────────

_INVARIANT = (
    "def scale(xs):\n    out = []\n    for x in xs:\n        out.append(x + total(xs))\n    return out\n"
)
_HOISTED = (
    "def scale(xs):\n"
    "    t = total(xs)\n"
    "    out = []\n"
    "    for x in xs:\n"
    "        out.append(x + t)\n"
    "    return out\n"
)
_LOOP_DEPENDENT = (
    "def scale(xs):\n    out = []\n    for x in xs:\n        out.append(total(x))\n    return out\n"
)
_BODY_WRITTEN = (
    "def f(xs, k):\n"
    "    out = []\n"
    "    for x in xs:\n"
    "        k = k + 1\n"
    "        out.append(g(k))\n"
    "    return out\n"
)


def test_invariant_call_in_loop_fires() -> None:
    m = recognize_loop_invariant_recompute(_fn(_INVARIANT))
    assert m is not None and "total" in m.evidence


def test_loop_dependent_argument_must_not_match() -> None:
    assert recognize_loop_invariant_recompute(_fn(_LOOP_DEPENDENT)) is None


def test_body_written_argument_is_not_invariant() -> None:
    # k is rewritten every iteration — a value the loop writes is not invariant.
    assert recognize_loop_invariant_recompute(_fn(_BODY_WRITTEN)) is None


def test_hoisted_form_discharges_the_template() -> None:
    assert recognize_loop_invariant_recompute(_fn(_HOISTED)) is None


# ── accumulator_series ───────────────────────────────────────────────────────────────────────

_SERIES = "def s(n):\n    total = 0\n    for i in range(n):\n        total += i\n    return total\n"
_NOT_JUST_SERIES = (
    "def s(n):\n    total = 0\n    for i in range(n):\n        total += i\n        log(i)\n    return total\n"
)
_SUM_OF_ITEMS = "def s(xs):\n    total = 0\n    for x in xs:\n        total += x\n    return total\n"


def test_series_fires() -> None:
    assert recognize_accumulator_series(_fn(_SERIES)) is not None


def test_series_with_side_work_still_names_the_series_line() -> None:
    # The += i statement is still a series; the template points AT it (the transform's gate
    # then decides whether the surrounding loop allows the closed form — recognition ≠ license).
    assert recognize_accumulator_series(_fn(_NOT_JUST_SERIES)) is not None


def test_summing_items_is_not_the_series_shape() -> None:
    # total += x over items is not the index series — no closed form over the loop variable.
    assert recognize_accumulator_series(_fn(_SUM_OF_ITEMS)) is None


# ── manual_index_iteration ───────────────────────────────────────────────────────────────────

_INDEXED = "def total(xs):\n    t = 0\n    for i in range(len(xs)):\n        t += xs[i]\n    return t\n"
_DIRECT = "def total(xs):\n    t = 0\n    for x in xs:\n        t += x\n    return t\n"
_COUNTING = "def count_to_len(xs):\n    n = 0\n    for i in range(len(xs)):\n        n += 1\n    return n\n"


def test_index_iteration_fires() -> None:
    m = recognize_manual_index_iteration(_fn(_INDEXED))
    assert m is not None and "xs[i]" in m.evidence


def test_direct_iteration_discharges_the_template() -> None:
    assert recognize_manual_index_iteration(_fn(_DIRECT)) is None


def test_range_len_without_indexing_is_counting_not_iterating() -> None:
    assert recognize_manual_index_iteration(_fn(_COUNTING)) is None


# ── the library as a whole ───────────────────────────────────────────────────────────────────


def test_every_template_names_its_transform_and_its_gate() -> None:
    # The §8 actuator law as data: no template without a transform, none without a gate.
    for template, (transform, gate) in TEMPLATE_GRAMMAR.items():
        assert transform and gate, template
    assert set(TEMPLATE_GRAMMAR) == {
        "memoizable_pure_recursion",
        "quadratic_membership_scan",
        "loop_invariant_recompute",
        "accumulator_series",
        "manual_index_iteration",
    }


@pytest.mark.parametrize(
    "src, expected",
    [
        (_FIB, {"memoizable_pure_recursion"}),
        (_LIST_SCAN, {"quadratic_membership_scan"}),
        (_SERIES, {"accumulator_series"}),
        (_DIRECT, set()),  # clean code: the honest empty verdict (not a claim of optimality)
    ],
)
def test_template_matches_reports_side_by_side(src: str, expected: set) -> None:
    assert {m.template for m in template_matches(_fn(src))} == expected


def test_discharge_property_across_the_seeded_pairs() -> None:
    # A correct transform un-fires its own recognizer — checked on every pair whose transform
    # removes the SHAPE; EXP-DS-004 adds the paired budget refund at behavior-delta exactly 0.
    pairs = [
        (recognize_quadratic_membership_scan, _LIST_SCAN, _SET_SCAN),
        (recognize_loop_invariant_recompute, _INVARIANT, _HOISTED),
        (recognize_manual_index_iteration, _INDEXED, _DIRECT),
    ]
    for recognize, naive, optimized in pairs:
        assert recognize(_fn(naive)) is not None, recognize.__name__
        assert recognize(_fn(optimized)) is None, recognize.__name__


def test_memoize_discharge_is_budget_only_at_v1_granularity() -> None:
    # A recognizer-granularity FACT, measured and recorded rather than papered over: the
    # memoized form still IS pure self-recursion (is_pure says so), so memoize's discharge is
    # invisible on the recognition axis — its discharge evidence is the budget refund
    # (EXP-DS-004). A cache-evidence-aware recognizer is a future population-level growth of
    # the library, never a tweak made here to force this pair to un-fire.
    assert recognize_memoizable_pure_recursion(_fn(_FIB)) is not None
    assert recognize_memoizable_pure_recursion(_fn(_FIB_MEMO)) is not None  # still fires — stated
