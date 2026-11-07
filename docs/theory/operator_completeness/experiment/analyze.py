"""Turn the raw experiment records (results/<lib>/) into the numbers reported in the paper's section 9.5.

Two oracles, as in the paper. A covering test KILLS a mutant under
  the value oracle   -- if it fails by its own check on the result ("assert");
  the any-failure oracle -- if it fails in any way ("assert" or "crash").

(1) Pseudo-testedness under a uniform constant. The constant mutant `return c` of a sampled function is
    exactly non-equivalent (some observed, hence reachable, output differs from c). It is pseudo-tested under
    an oracle iff no covering test kills it under that oracle.

(2) The prediction of Proposition 9.4 / 9.3. Under the model (an oracle that reads each returned value on
    its own, omega: R -> Omega), Det(return c) is the union over observed r != c of Det(swap r -> c), so
        the constant is killed  <=>  some point swap r -> c is killed.
    Each sampled function with a complete swap set is one test of this biconditional per oracle; with a
    sampled (partial) swap set only the direction "a swap killed => the constant killed" is tested.
    A disagreement means the suite's oracle is not of the model's form for that function.

Usage: python analyze.py   (writes results/summary.json and prints the tables)
"""

from __future__ import annotations

import gzip
import json
import random
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEED = 20261106
B = 10000


def killed(recs: list[dict], oracle: str) -> bool:
    hows = {"assert"} if oracle == "value" else {"assert", "crash"}
    return any(r["outcome"] == "fail" and r["how"] in hows for r in recs)


def bootstrap_ci(pairs: list[tuple[int, int]], rng: random.Random) -> tuple[float, float]:
    """95% percentile CI of mean(a - b) over functions, resampling functions (paired)."""
    n = len(pairs)
    stats = []
    for _ in range(B):
        s = [pairs[rng.randrange(n)] for _ in range(n)]
        stats.append(sum(a - b for a, b in s) / n)
    stats.sort()
    return stats[int(0.025 * B)], stats[int(0.975 * B) - 1]


def main() -> int:
    rng = random.Random(SEED)
    libs = [d.name for d in sorted((HERE / "results").iterdir()) if (d / "mutants.jsonl.gz").exists()]
    rows, pred, per_fn = [], {}, []
    for lib in libs:
        base = HERE / "results" / lib
        plan = {f["fn"]: f for f in json.loads((base / "plan.json").read_text(encoding="utf-8"))}
        muts = defaultdict(dict)
        with gzip.open(base / "mutants.jsonl.gz", "rt", encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        for ln in lines:
            r = json.loads(ln)
            muts[r["fn"]][r["operator"]] = r
        for fn, f in plan.items():
            ops = muts[fn]
            swaps = [ops[f"swap:{k}"] for k in f["swap_from"]]
            unfired = sum(1 for sw in swaps if not sw.get("fired"))
            rec = {
                "lib": lib,
                "fn": fn,
                "constant": f["constant_repr"],
                "type_preserving": f["type_preserving"],
                "n_tests": len(f["tests"]),
                "n_swaps": len(swaps),
                "unfired_swaps": unfired,
                "const_fired": bool(ops["const"].get("fired")),
                # the converse direction needs every observed value's swap, each actually applied
                "complete": not f["swaps_partial"] and unfired == 0,
            }
            for oracle in ("value", "any"):
                const_k = killed(ops["const"]["tests"], oracle)
                swap_k = any(killed(sw["tests"], oracle) for sw in swaps)
                rec[f"const_killed_{oracle}"] = const_k
                rec[f"any_swap_killed_{oracle}"] = swap_k
                if rec["complete"]:
                    verdict = "agree" if const_k == swap_k else ("const_only" if const_k else "swap_only")
                elif swap_k:
                    verdict = "agree" if const_k else "swap_only"
                else:
                    verdict = "untestable"
                rec[f"prediction_{oracle}"] = verdict
            per_fn.append(rec)
    for subset_name, keep in (("all", lambda r: True), ("type_preserving", lambda r: r["type_preserving"])):
        for lib in [*libs, "pooled"]:
            fs = [r for r in per_fn if keep(r) and (lib == "pooled" or r["lib"] == lib)]
            if not fs:
                continue
            pv = sum(not r["const_killed_value"] for r in fs)
            pa = sum(not r["const_killed_any"] for r in fs)
            row = {
                "subset": subset_name,
                "lib": lib,
                "functions": len(fs),
                "pseudo_tested_value": pv,
                "pseudo_tested_any": pa,
                "rate_value": pv / len(fs),
                "rate_any": pa / len(fs),
            }
            if lib == "pooled":
                pairs = [(int(not r["const_killed_value"]), int(not r["const_killed_any"])) for r in fs]
                row["gap_ci95"] = bootstrap_ci(pairs, rng)
            rows.append(row)
    for subset_name, keep in (("all", lambda r: True), ("type_preserving", lambda r: r["type_preserving"])):
        for oracle in ("value", "any"):
            for lib in [*libs, "pooled"]:
                fs = [r for r in per_fn if keep(r) and (lib == "pooled" or r["lib"] == lib)]
                c = defaultdict(int)
                for r in fs:
                    c[("complete " if r["complete"] else "partial ") + r[f"prediction_{oracle}"]] += 1
                pred[(subset_name, oracle, lib)] = dict(sorted(c.items()))
    summary = {
        "pseudo_tested": rows,
        "prediction": {f"{sub}/{oracle}/{lib}": v for (sub, oracle, lib), v in pred.items()},
        "functions": per_fn,
    }
    (HERE / "results" / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print("pseudo-tested under the uniform constant")
    for r in rows:
        ci = f"  gap 95% CI [{r['gap_ci95'][0]:.3f}, {r['gap_ci95'][1]:.3f}]" if "gap_ci95" in r else ""
        print(
            f"  {r['subset']:15s} {r['lib']:9s} n={r['functions']:3d}  value {r['rate_value']:.0%}"
            f"  any-failure {r['rate_any']:.0%}{ci}"
        )
    print("Prop 9.4 prediction (constant killed <=> some swap r->c killed)")
    for k, v in summary["prediction"].items():
        print(f"  {k:34s} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
