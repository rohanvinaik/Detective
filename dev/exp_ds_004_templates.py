"""EXP-DS-004 — the template library's end-to-end measurement (Wave 3).

Per template: (1) the recognizer FIRES on the naive arm; (2) it is DISCHARGED on the optimized
arm (memoize excepted at v1 granularity — the memoized form still IS pure recursion, a measured
fact stated in the intent suite, its discharge evidence is budget-only); (3) the Wave-2 paired
read pays at behavior-delta exactly 0. Both arms of every pair are pure Python so the
instruction counter sees the work (the counter's stated C-invisibility boundary).

The index-iteration pair is deliberately a RATIO-band case (same growth class, constant-factor
saving): its honest expected outcome is "ratio < 1", whether that lands refund or parity — the
harness reports which, and forces neither.

Run:  PYTHONPATH=.:../Wesker python3 dev/exp_ds_004_templates.py
"""

from __future__ import annotations

import ast
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from Detective.budget import (  # noqa: E402
    budget_verdict,
    count_opcodes,
    growth_class,
    ladder_value,
    paired_disposition,
)
from Detective.templates import template_matches  # noqa: E402

# ── the five seeded pairs (naive, optimized — behavior-identical by construction) ───────────


def fib_naive(n: int) -> int:
    if n < 2:
        return n
    return fib_naive(n - 1) + fib_naive(n - 2)


def fib_memo(n: int, memo=None) -> int:
    memo = {} if memo is None else memo
    if n < 2:
        return n
    if n not in memo:
        memo[n] = fib_memo(n - 1, memo) + fib_memo(n - 2, memo)
    return memo[n]


def dedupe_naive(xs: list) -> list:
    out = []
    for x in xs:
        if x not in out:
            out.append(x)
    return out


def dedupe_set(xs: list) -> list:
    seen: set = set()
    out = []
    for x in xs:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _total(xs: list) -> int:  # Python-level on purpose: sum() is C and invisible to the counter
    t = 0
    for v in xs:
        t += v
    return t


def scale_naive(xs: list) -> list:
    out = []
    for x in xs:
        out.append(x + _total(xs))
    return out


def scale_hoisted(xs: list) -> list:
    t = _total(xs)
    out = []
    for x in xs:
        out.append(x + t)
    return out


def series_naive(xs: list) -> int:
    total = 0
    for i in range(len(xs)):
        total += i
    return total


def series_closed(xs: list) -> int:
    n = len(xs)
    return n * (n - 1) // 2


def isum_indexed(xs: list) -> int:
    t = 0
    for i in range(len(xs)):
        t += xs[i]
    return t


def isum_direct(xs: list) -> int:
    t = 0
    for x in xs:
        t += x
    return t


LIST_LADDER = (16, 32, 64, 128, 256, 512)
FIB_LADDER = (8, 10, 12, 14, 16, 18)

PAIRS = (
    # (name, template, naive, optimized, inputs, mode, expected verdicts, discharge expected)
    # mode "payoff": the budget read must land in the expected verdict set.
    # mode "boundary": the SECOND measured finding of this experiment — the naive arm's
    #   quadratic work is `x in <list>`, a C-level scan executing ZERO Python opcodes, so the
    #   v1 instruction axis is STRUCTURALLY BLIND to this template's payoff (both arms read
    #   linear; the set arm even pays more visible Python scaffolding). The pair's honest
    #   expectation is that blindness, confirmed: equal classes at delta 0, with the payoff
    #   deferred to a C-call-counting axis (instrument v2, a named deliverable — recognizable
    #   is not the same as priceable, and the two banks' reaches genuinely differ here).
    ("memoize", "memoizable_pure_recursion", fib_naive, fib_memo, "fib", "payoff", {"refund"}, False),
    (
        "set_membership",
        "quadratic_membership_scan",
        dedupe_naive,
        dedupe_set,
        "list_scaling_distincts",
        "boundary",
        set(),
        True,
    ),
    (
        "hoist_invariant",
        "loop_invariant_recompute",
        scale_naive,
        scale_hoisted,
        "list",
        "payoff",
        {"refund"},
        True,
    ),
    ("closed_form", "accumulator_series", series_naive, series_closed, "list", "payoff", {"refund"}, True),
    (
        "direct_iteration",
        "manual_index_iteration",
        isum_indexed,
        isum_direct,
        "list",
        "payoff",
        {"refund", "parity"},
        True,
    ),
)


def _inputs(kind: str):
    if kind == "fib":
        return [(n, (n,)) for n in FIB_LADDER]
    if kind == "list_scaling_distincts":
        # The measured lesson of this experiment's first run: `ladder_value("list[int]")` holds
        # distinct-value cardinality CONSTANT (i % 7), so the membership scan's `out` capped at
        # 7 and the quadratic shape never manifested — the pair read linear→linear parity. A
        # growth class is a property of (code, INPUT FAMILY), not code alone; the ladder must
        # scale the dimension the shape is quadratic in. Here: distincts ≈ n/2.
        return [(n, ([i % max(1, n // 2) for i in range(n)],)) for n in LIST_LADDER]
    return [(n, (list(ladder_value("list[int]", n)),)) for n in LIST_LADDER]


def _src_fn(fn) -> ast.FunctionDef:
    import inspect
    import textwrap

    return ast.parse(textwrap.dedent(inspect.getsource(fn))).body[0]


def run_pair(name, template, naive, optimized, kind, mode, expected, discharge_expected) -> dict:
    fired = {m.template for m in template_matches(_src_fn(naive))}
    discharged = template not in {m.template for m in template_matches(_src_fn(optimized))}
    sizes, a_counts, b_counts = [], [], []
    delta_zero = True
    for size, args in _inputs(kind):
        if naive(*[list(a) if isinstance(a, list) else a for a in args]) != optimized(
            *[list(a) if isinstance(a, list) else a for a in args]
        ):
            delta_zero = False
        ca = count_opcodes(naive, tuple(list(a) if isinstance(a, list) else a for a in args))
        cb = count_opcodes(optimized, tuple(list(a) if isinstance(a, list) else a for a in args))
        if ca is None or cb is None:
            delta_zero = False
            continue
        sizes.append(float(size))
        a_counts.append(float(ca))
        b_counts.append(float(cb))
    inc_class, cand_class = growth_class(sizes, a_counts), growth_class(sizes, b_counts)
    ratio = b_counts[-1] / a_counts[-1] if a_counts and a_counts[-1] > 0 else 0.0
    verdict = paired_disposition(delta_zero, budget_verdict(inc_class, cand_class, ratio))
    if mode == "boundary":
        ok = template in fired and discharged == discharge_expected and delta_zero and inc_class == cand_class
        outcome = f"C-blindness confirmed (classes equal: {inc_class})" if ok else "UNEXPECTED"
    else:
        ok = template in fired and discharged == discharge_expected and delta_zero and verdict in expected
        outcome = f"disposition {verdict} (expected ∈ {sorted(expected)})"
    print(f"── {name} ({template}) ──")
    print(f"  recognized on naive arm:   {template in fired}")
    print(
        f"  discharged on optimized:   {discharged}"
        + ("" if discharge_expected else "   (budget-only discharge at v1 granularity — stated)")
    )
    print(f"  classes: {inc_class} → {cand_class} · ratio at top {ratio:.4f} · delta 0: {delta_zero}")
    print(f"  {outcome}   PASS: {ok}\n")
    return {"pair": name, "verdict": verdict, "classes": [inc_class, cand_class], "pass": ok}


def main() -> None:
    print(f"EXP-DS-004 — list ladder {LIST_LADDER} · fib ladder {FIB_LADDER}\n")
    results = [run_pair(*p) for p in PAIRS]
    print(json.dumps(results))
    print(f"\n{sum(r['pass'] for r in results)}/5 pairs pass end-to-end")


if __name__ == "__main__":
    main()
