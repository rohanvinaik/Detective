"""EXP-DS-002 — the κ-weighted, split-validated norms mine + the bulk/tail knee (Wave 1).

Design: docs/theory/deterministic_sicp/DETERMINISTIC_SICP.md §4.2 (the norms discipline), §12
Wave 1, §3.2 (the transported dynamics this measurement gates). Two questions, one pass:

1. **The mined zeros.** For the two numeric banks whose zeros are mined (complexity, overload),
   mine the κ-weighted median per hash-parity half (`norms.split_of` — the EXP-RF-005a protocol)
   and report `norms.norm_disposition` at a STATED tolerance. κ-weight = 1 + call-graph in-degree
   (`kappa.build_call_graph` — a hub counts more; dead code counts once and cannot drag; an
   entry point with no callers still counts, which is why weighting beats exclusion). The
   overload raw is STATIC here: DOF = the function's mutant-universe size (one function's
   operators — a property of its AST, per the sandwich thesis), never a run.

2. **The knee.** `norms.verdict_isolation_cost` per function over the measured banks in priority
   order; the corpus distribution of that cost is the bulk/tail measurement: a large early-
   decided mass is the bulk the σ_form transport predicts (§3.2), the late residual is the tail.

Advisory instrumentation: reads everything, judges nothing, writes nothing.

Run:  PYTHONPATH=.:../Wesker python3 dev/exp_ds_002_norms_knee.py [tree ...]
"""

from __future__ import annotations

import ast
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from Detective.kappa import build_call_graph  # noqa: E402
from Detective.norms import (  # noqa: E402
    norm_disposition,
    split_of,
    verdict_isolation_cost,
    weighted_median,
)
from Detective.parsimony import (  # noqa: E402
    _CC_ZERO,
    _OVERLOAD_ZERO,
    _overload_vote,
    cohesion_lens,
    complexity_lens,
    gamma_seam_lens,
    interface_width_lens,
    purity_lens,
    seam_lens_static,
)

# The measurement's one free parameter, stated here and reported with the results: the halves
# must agree within this relative drift for a norm to be admissible.
REL_TOLERANCE = 0.25

# Priority order for the knee = the fusion's `_LENS_PRIORITY` restricted to what this static
# pass can measure (regime needs a live profile and is absent, not zero-filled).
_KNEE_ORDER = ("overload", "cohesion", "seam", "gamma_seam", "complexity", "interface_width", "purity")


def _functions(tree: ast.Module):
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node.name, node, False
        elif isinstance(node, ast.ClassDef):
            for m in node.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield f"{node.name}.{m.name}", m, True


def _py_files(target: str) -> list[str]:
    if os.path.isfile(target):
        return [target]
    skip = {"__pycache__", ".git", ".venv", "venv", "build", "dist", "tests", "test"}
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(target):
        dirnames[:] = [d for d in dirnames if d not in skip and not d.startswith(".")]
        found.extend(os.path.join(dirpath, f) for f in filenames if f.endswith(".py"))
    return sorted(found)


def _static_dof(node: ast.FunctionDef | ast.AsyncFunctionDef, is_method: bool) -> int | None:
    """The function's mutant-universe size, statically — one function's operators off its own
    AST. None (cannot-determine) when generation itself refuses; never a fabricated 0."""
    try:
        from Wesker.engine import generate_mutants
        from Wesker.filter import filter_categories

        from Detective.purity import is_pure

        cats = filter_categories(node, is_pure(node, is_method=is_method))
        return len(generate_mutants(node, cats))
    except Exception:  # noqa: BLE001 — a measurement instrument records the miss, never dies
        return None


def main(targets: list[str]) -> None:
    in_degree: Counter[str] = Counter()
    for target in targets:
        adj = build_call_graph(target)
        for callees in adj.values():
            in_degree.update(callees)

    rows = []  # (qualname, weight, split, cc, dof_density, votes_in_knee_order)
    dof_misses = 0
    for target in targets:
        for path in _py_files(target):
            try:
                with open(path, encoding="utf-8") as fh:
                    tree = ast.parse(fh.read(), filename=path)
            except (OSError, SyntaxError):
                continue
            for qualname, node, is_method in _functions(tree):
                full = f"{os.path.relpath(path)}::{qualname}"
                bare = qualname.split(".")[-1]
                weight = 1.0 + in_degree.get(bare, 0)
                cc_lens = complexity_lens(node)
                span = (node.end_lineno or node.lineno) - node.lineno + 1
                dof = _static_dof(node, is_method)
                if dof is None:
                    dof_misses += 1
                    density, overload_vote = None, None
                else:
                    density = dof / max(1, span)
                    overload_vote = _overload_vote(density)
                votes = {
                    "overload": overload_vote,
                    "cohesion": cohesion_lens(node).vote,
                    "seam": seam_lens_static(node).vote,
                    "gamma_seam": gamma_seam_lens(node).vote,
                    "complexity": cc_lens.vote,
                    "interface_width": interface_width_lens(node).vote,
                    "purity": purity_lens(node, is_method=is_method).vote,
                }
                knee_votes = tuple(votes[k] for k in _KNEE_ORDER if votes[k] is not None)
                rows.append((full, weight, split_of(full), float(cc_lens.raw), density, knee_votes))

    print(f"EXP-DS-002 over {targets}: {len(rows)} functions · dof unminable on {dof_misses}")
    print(f"tolerance (stated parameter): {REL_TOLERANCE}\n")

    print("── the mined zeros ──")
    for bank, current, values in (
        ("complexity (CC)", _CC_ZERO, [(r[3], r[1], r[2]) for r in rows]),
        ("overload (DOF/line)", _OVERLOAD_ZERO, [(r[4], r[1], r[2]) for r in rows if r[4] is not None]),
    ):
        za = weighted_median([v for v, _, s in values if s == "A"], [w for _, w, s in values if s == "A"])
        zb = weighted_median([v for v, _, s in values if s == "B"], [w for _, w, s in values if s == "B"])
        full_w = weighted_median([v for v, _, _ in values], [w for _, w, _ in values])
        full_u = weighted_median([v for v, _, _ in values], [1.0] * len(values))
        disp = norm_disposition(za, zb, REL_TOLERANCE)
        print(
            f"  {bank:22s} half-A {za} · half-B {zb} → {disp:10s} · "
            f"κ-weighted {full_w} · unweighted {full_u} · current constant {current}"
        )

    print("\n── the knee (verdict-isolation cost over the measured banks) ──")
    costs = Counter(verdict_isolation_cost(r[5]) for r in rows)
    n = len(rows)
    cum = 0
    for k in sorted(costs):
        cum += costs[k]
        pct, cum_pct = costs[k] * 100 / n, cum * 100 / n
        print(f"  decided by read {k}: {costs[k]:5d}  ({pct:5.1f}%)   cumulative {cum_pct:5.1f}%")
    print(json.dumps({"functions": n, "cost_hist": dict(sorted(costs.items()))}))


if __name__ == "__main__":
    main(sys.argv[1:] or ["Detective", os.path.join("..", "Wesker", "Wesker")])
