"""EXP-DS-003 — the budget bank re-derives known optimizations' payoffs (Wave 2).

Design: docs/theory/deterministic_sicp/DETERMINISTIC_SICP.md §7, §12 Wave 2. Two seeded pairs,
each a classic optimization whose payoff is KNOWN a priori; the measurement passes iff the bank,
reading only deterministic opcode counts along the size ladder, re-derives it blind:

  dedupe   naive O(n²) scan  →  seen-set first-occurrence scan     expect quadratic_plus → linear
  series   linear index loop →  closed-form Gauss                  expect linear → constant

Every pair runs under the two-ledger law: the behavior delta (output identity on every ladder
input) is checked FIRST, and `paired_disposition` refuses the budget read outright on any
nonzero delta. Counts are Python-frame opcodes (`budget.count_opcodes` — the stated boundary:
C-level work is invisible; both arms here are pure Python, so the reads are comparable).

Advisory instrumentation: reads, judges nothing beyond its stated expectations, writes nothing.

Run:  PYTHONPATH=.:../Wesker python3 dev/exp_ds_003_budget_bank.py
"""

from __future__ import annotations

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

LADDER = (16, 32, 64, 128, 256, 512)


# ── pair 1: dedupe — the classic quadratic→linear rewrite ────────────────────────────────────


def dupes_naive(xs: list) -> list:
    out = []
    for i, a in enumerate(xs):
        for b in xs[i + 1 :]:
            if a == b and a not in out:
                out.append(a)
    return out


def dupes_seen(xs: list) -> list:
    seen: set = set()
    dup: set = set()
    out = []
    for a in xs:
        if a in seen and a not in dup:
            dup.add(a)
            out.append(a)
        seen.add(a)
    return out


# ── pair 2: series — the loop→closed-form rewrite ────────────────────────────────────────────


def index_sum_loop(xs: list) -> int:
    total = 0
    for i in range(len(xs)):
        total += i
    return total


def index_sum_gauss(xs: list) -> int:
    n = len(xs)
    return n * (n - 1) // 2


def run_pair(name: str, incumbent, candidate, expect: tuple[str, str]) -> dict:
    sizes, inc_counts, cand_counts = [], [], []
    delta_zero = True
    for size in LADDER:
        xs = ladder_value("list[int]", size)
        if incumbent(list(xs)) != candidate(list(xs)):  # the delta gate, per input, first
            delta_zero = False
        ci = count_opcodes(incumbent, (list(xs),))
        cc = count_opcodes(candidate, (list(xs),))
        if ci is None or cc is None:
            delta_zero = delta_zero and False
            continue
        sizes.append(float(size))
        inc_counts.append(float(ci))
        cand_counts.append(float(cc))

    inc_class = growth_class(sizes, inc_counts)
    cand_class = growth_class(sizes, cand_counts)
    ratio = cand_counts[-1] / inc_counts[-1] if inc_counts and inc_counts[-1] > 0 else 0.0
    verdict = paired_disposition(delta_zero, budget_verdict(inc_class, cand_class, ratio))
    rederived = (inc_class, cand_class) == expect and verdict == "refund"
    print(f"── {name} ──")
    print(f"  delta gate:        {'0 on every ladder input' if delta_zero else 'NONZERO — inadmissible'}")
    print(f"  incumbent counts:  {[int(c) for c in inc_counts]} → {inc_class}")
    print(f"  candidate counts:  {[int(c) for c in cand_counts]} → {cand_class}")
    print(f"  ratio at top:      {ratio:.4f}")
    print(f"  disposition:       {verdict}")
    print(f"  expected classes:  {expect[0]} → {expect[1]}   re-derived blind: {rederived}\n")
    return {"pair": name, "inc": inc_class, "cand": cand_class, "verdict": verdict, "rederived": rederived}


def main() -> None:
    print(f"EXP-DS-003 — ladder {LADDER}\n")
    results = [
        run_pair("dedupe (quadratic → linear)", dupes_naive, dupes_seen, ("quadratic_plus", "linear")),
        run_pair("series (linear → constant)", index_sum_loop, index_sum_gauss, ("linear", "constant")),
    ]
    print(json.dumps(results))


if __name__ == "__main__":
    main()
