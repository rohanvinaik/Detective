"""EXP-DS-001 — the discrimination-guarantee audit (Wave 0, docs/theory/deterministic_sicp/).

Measures whether the static bank signature DISCRIMINATES over a real corpus: for every
module-level function and method in the target trees, compute the ternary signature under

  A) the pre-Wave-0 static lens set   (complexity, cohesion, interface_width, seam), and
  B) the Wave-0 set                   (A + gamma_seam + purity),

and report function count, distinct-signature count under each, and the largest collision
clusters under B. The Peitho discrimination guarantee (DESIGN §4.4 / DETERMINISTIC_SICP §4.2
law 4): two regions an expert treats differently sharing one signature is a STRUCTURAL bug
whose fix is a new orthogonal bank — this audit is how such collisions become visible. The
audit MEASURES distinctness; it does not judge quality and it writes nothing.

Run:  PYTHONPATH=.:../Wesker python3 dev/exp_ds_001_signature_audit.py [tree ...]
Default trees: Detective/ and ../Wesker/Wesker (the 527-function calibration corpus's spine).
"""

from __future__ import annotations

import ast
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from Detective.parsimony import (  # noqa: E402
    cohesion_lens,
    complexity_lens,
    gamma_seam_lens,
    interface_width_lens,
    purity_lens,
    seam_lens_static,
)

# Fixed signature order — the canonical bank-space tuple (sorted-by-name, the Peitho rule).
_SET_A = ("cohesion", "complexity", "interface_width", "seam")
_SET_B = ("cohesion", "complexity", "gamma_seam", "interface_width", "purity", "seam")


def _functions(tree: ast.Module) -> list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef, bool]]:
    """(qualname, node, is_method) for module-level functions and class methods."""
    out: list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef, bool]] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append((node.name, node, False))
        elif isinstance(node, ast.ClassDef):
            for m in node.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out.append((f"{node.name}.{m.name}", m, True))
    return out


def _lenses(func: ast.FunctionDef | ast.AsyncFunctionDef, is_method: bool) -> dict[str, int]:
    reads = {
        "complexity": complexity_lens(func),
        "cohesion": cohesion_lens(func),
        "interface_width": interface_width_lens(func),
        "seam": seam_lens_static(func),
        "gamma_seam": gamma_seam_lens(func),
        "purity": purity_lens(func, is_method=is_method),
    }
    return {name: lens.vote if lens.measured else 0 for name, lens in reads.items()}


def _py_files(target: str) -> list[str]:
    if os.path.isfile(target):
        return [target]
    skip = {"__pycache__", ".git", ".venv", "venv", "build", "dist", "tests", "test"}
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(target):
        dirnames[:] = [d for d in dirnames if d not in skip and not d.startswith(".")]
        found.extend(os.path.join(dirpath, f) for f in filenames if f.endswith(".py"))
    return sorted(found)


def main(targets: list[str]) -> None:
    rows: list[tuple[str, tuple[int, ...], tuple[int, ...]]] = []
    for target in targets:
        for path in _py_files(target):
            try:
                with open(path, encoding="utf-8") as fh:
                    tree = ast.parse(fh.read(), filename=path)
            except (OSError, SyntaxError):
                continue
            for qualname, node, is_method in _functions(tree):
                try:
                    votes = _lenses(node, is_method)
                except Exception:  # noqa: BLE001 — an audit skips what it cannot read
                    continue
                sig_a = tuple(votes[n] for n in _SET_A)
                sig_b = tuple(votes[n] for n in _SET_B)
                rows.append((f"{os.path.relpath(path)}::{qualname}", sig_a, sig_b))

    n = len(rows)
    distinct_a = len({sig_a for _, sig_a, _ in rows})
    distinct_b = len({sig_b for _, _, sig_b in rows})
    clusters: dict[tuple[int, ...], list[str]] = defaultdict(list)
    for name, _, sig_b in rows:
        clusters[sig_b].append(name)
    biggest = sorted(clusters.items(), key=lambda kv: -len(kv[1]))[:10]

    print(f"EXP-DS-001 — discrimination-guarantee audit over {targets}")
    print(f"functions read:               {n}")
    print(f"distinct signatures, set A (4 static banks):  {distinct_a}  (space 3^4 = 81)")
    print(f"distinct signatures, set B (6 static banks):  {distinct_b}  (space 3^6 = 729)")
    print(f"collision mass: largest cluster holds {len(biggest[0][1])} functions" if biggest else "")
    print(f"\nlargest collision clusters under set B (signature order {_SET_B}):")
    for sig, names in biggest:
        print(f"  {sig}  ×{len(names):4d}   e.g. {', '.join(names[:3])}")
    dist_a = Counter(sig for _, sig, _ in rows)
    print(f"\nset A top cluster sizes: {[c for _, c in dist_a.most_common(5)]}")
    print(json.dumps({"functions": n, "distinct_A": distinct_a, "distinct_B": distinct_b}))


if __name__ == "__main__":
    args = sys.argv[1:] or ["Detective", os.path.join("..", "Wesker", "Wesker")]
    main(args)
