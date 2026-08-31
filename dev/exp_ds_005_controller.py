"""EXP-DS-005 — the controller measured over the real corpus (Wave 4).

Four reads, one pass over Detective + Wesker:

1. **The verdict distribution** — the interference verdict per function (fences held at 0:
   `detective censor` is conservative-empty on clean data by construction, so the DESTRUCTIVE
   channel is structurally unexercised in this run — stated, not hidden). The SILENT majority
   is the clean-side measurement Wave 1's binary instrument could not make.
2. **The four-valued knee** — `interference_isolation_cost` over the oriented static votes.
3. **The graph shape** — `kappa.call_graph_shape` (the C7 fragmentation measurement); the
   ADOPTION-time supermodular degree d needs the censor-promotion loop and stays deferred
   exactly as kappa.py records — this is the graph it will be measured over.
4. **The plan** — the gated, priced, budgeted plan vs `parsimony_plan`'s unpriced queue: of the
   functions parsimony flags, how many the controller funds / escalates / excludes and WHY
   (the named-residual comparison — the controller's value over the queue is that its
   exclusions explain themselves). Costs are the static DOF proxy (stated; the live upgrade is
   `audit --plan`, whose in-repo run cost is the serial-cold idiom — recorded, not paid here).

Run:  PYTHONPATH=.:../Wesker python3 dev/exp_ds_005_controller.py
"""

from __future__ import annotations

import ast
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from Detective.controller import (  # noqa: E402
    RegionRead,
    controller_verdict,
    interference_isolation_cost,
    orient_for_change,
    plan_moves,
)
from Detective.kappa import build_call_graph, call_graph_shape  # noqa: E402
from Detective.parsimony import (  # noqa: E402
    _overload_vote,
    cohesion_lens,
    complexity_lens,
    gamma_seam_lens,
    interface_width_lens,
    purity_lens,
    seam_lens_static,
)
from Detective.parsimony_map import parsimony_plan, score_path  # noqa: E402
from Detective.templates import TEMPLATE_GRAMMAR, template_matches  # noqa: E402

BUDGET = 500.0  # stated: DOF-proxy units for this run
_ORDER = ("overload", "cohesion", "seam", "gamma_seam", "complexity", "interface_width", "purity")


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


def _static_dof(node, is_method: bool) -> int | None:
    """The static mutant-universe size — duplicated from exp_ds_002 (dev-sibling; 12 lines)."""
    try:
        from Wesker.engine import generate_mutants
        from Wesker.filter import filter_categories

        from Detective.purity import is_pure

        return len(generate_mutants(node, filter_categories(node, is_pure(node, is_method=is_method))))
    except Exception:  # noqa: BLE001
        return None


def main(targets: list[str]) -> None:
    reads: list[RegionRead] = []
    knee = Counter()
    for target in targets:
        for path in _py_files(target):
            try:
                with open(path, encoding="utf-8") as fh:
                    tree = ast.parse(fh.read(), filename=path)
            except (OSError, SyntaxError):
                continue
            for qualname, node, is_method in _functions(tree):
                span = (node.end_lineno or node.lineno) - node.lineno + 1
                dof = _static_dof(node, is_method)
                density_vote = _overload_vote(dof / max(1, span)) if dof is not None else 0
                votes = {
                    "overload": density_vote,
                    "cohesion": cohesion_lens(node).vote,
                    "seam": seam_lens_static(node).vote,
                    "gamma_seam": gamma_seam_lens(node).vote,
                    "complexity": complexity_lens(node).vote,
                    "interface_width": interface_width_lens(node).vote,
                    "purity": purity_lens(node, is_method=is_method).vote,
                }
                oriented = tuple(orient_for_change(votes[k]) for k in _ORDER)
                supports = sum(oriented)
                verdict = controller_verdict(supports, 0)
                knee[interference_isolation_cost(oriented)] += 1
                matches = template_matches(node)
                template = matches[0].template if matches else None
                reads.append(
                    RegionRead(
                        region=f"{os.path.relpath(path)}::{qualname}",
                        verdict=verdict,
                        agreement=supports,
                        template=template,
                        gate_exists=template in TEMPLATE_GRAMMAR if template else False,
                        cost=float(dof) if dof is not None else 999.0,
                    )
                )

    n = len(reads)
    dist = Counter(r.verdict for r in reads)
    print(f"EXP-DS-005 over {targets}: {n} functions · fences held at 0 (stated)\n")
    print("── verdict distribution (the clean-side measurement) ──")
    for v, c in dist.most_common():
        print(f"  {v:12s} {c:5d}  ({c * 100 / n:5.1f}%)")

    print("\n── the four-valued knee (isolation cost, oriented reads) ──")
    cum = 0
    for k in sorted(knee):
        cum += knee[k]
        pct, cum_pct = knee[k] * 100 / n, cum * 100 / n
        print(f"  decided by read {k}: {knee[k]:5d}  ({pct:5.1f}%)  cumulative {cum_pct:5.1f}%")

    print("\n── the graph shape (C7; adoption-time d deferred to the promotion loop — kappa's own record) ──")
    for target in targets:
        print(f"  {target}: {call_graph_shape(build_call_graph(target))}")

    plan = plan_moves(tuple(reads), BUDGET)
    reasons = Counter(reason for _, reason in plan.excluded)
    print(f"\n── the plan (budget {BUDGET} DOF-units, stated) ──")
    print(f"  funded: {len(plan.funded)} · spent {plan.budget_spent}")
    for r in plan.funded[:8]:
        print(f"    {r.region}  (agreement {r.agreement}, {r.template}, cost {r.cost})")
    print(f"  exclusions: {dict(reasons)}")

    flagged_queue = [
        r.qualname for _, group in parsimony_plan(score_path(targets[0], targets[0])) for r in group
    ]
    by_name = {r.region.split("::")[-1]: r for r in reads}
    fates = Counter()
    for qual in flagged_queue:
        bare = qual.split("::")[-1]
        read = by_name.get(bare)
        if read is None:
            fates["unmatched"] += 1
        elif any(f.region == read.region for f in plan.funded):
            fates["funded"] += 1
        else:
            fates[dict(plan.excluded).get(read.region, "unknown")] += 1
    print(f"\n── vs parsimony --plan's unpriced queue ({targets[0]}) ──")
    print(f"  parsimony flags {len(flagged_queue)} function(s); controller fate: {dict(fates)}")
    print(
        json.dumps(
            {
                "functions": n,
                "verdicts": dict(dist),
                "knee": dict(sorted(knee.items())),
                "funded": len(plan.funded),
            }
        )
    )


if __name__ == "__main__":
    main(sys.argv[1:] or ["Detective", os.path.join("..", "Wesker", "Wesker")])
