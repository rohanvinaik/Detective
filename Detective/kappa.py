"""κ (marginal coverage) over the code CALL GRAPH — the Q1 port of Regenesis's significance engine.

NEGATIVE_SPECIFICATION §14 computes κ over a *rule* graph in Regenesis; §18 Q1's sole code-specific
residual was the GRAPH CHOICE. Chosen (2026): the **call graph** — Def. 9.1 derives censors from
observed near-misses "across the population of call sites", and Detective already discovers call sites
(``call_sites.py``), so this is both the theory-aligned and the cheapest adapter.

The κ ENGINE transports UNCHANGED from Regenesis ``significance.py``: every function below is pure over
an adjacency dict ``adj: {node -> set(callee nodes)}`` and is ported VERBATIM so the two implementations
cannot silently drift (the manifest-pinning discipline, one owner per quantity). Only
:func:`build_call_graph` (the adapter) is code-specific here; the admissibility GUARD conjuncts
(spine-sourced + retained-plurality, §14) and the full censor-promotion loop are deferred — this module
is the graph + the κ engine + the fragmentation measurement (the C7 prediction), no promotion.
"""

from __future__ import annotations

import ast
import os

from Wesker.ci import walk_functions

# Directories a source scan must never descend into — caches, envs, build artifacts, vendored code.
_SKIP_DIRS = {"__pycache__", "node_modules", ".venv", "venv", ".tox", "build", "dist", ".git"}


def _callee_name(func: ast.expr) -> str | None:
    """The bare callee name of a call — ``f`` for ``f(...)`` or ``x.f(...)`` — or None.

    Mirrors ``call_sites._callee_simple_name`` deliberately: κ must not take a reverse dependency on the
    input-harvester, and the rule (a call site carries only the trailing attribute) is the same one.
    """
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def build_call_graph(project_root: str) -> dict[str, set[str]]:
    """The package's CALL GRAPH as an adjacency dict ``{fn -> set(callee fns)}``, keyed by the BARE
    function name (the §18 Q1 adapter — the ONE code-specific piece).

    A call site's AST carries only the simple callee name, so callees resolve by name and same-named
    functions across modules MERGE into one node — the known static-call-graph limitation the §18 Q1
    measurement caveat names (a finer key needs the runner-derived import identity of Detective #58).
    Only edges INTO package-defined functions are kept: a call to ``print``/``len`` is external and
    dropped, so ``adj`` is the intra-package dependency structure κ is read over. Reads the repo, never
    writes; a self-loop (a function calling itself) is not an edge (it joins no new node).
    """
    root = os.path.abspath(project_root)
    defined: set[str] = set()
    bodies: list[tuple[str, ast.AST]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")]
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            try:
                with open(os.path.join(dirpath, filename), encoding="utf-8") as fh:
                    tree = ast.parse(fh.read())
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue
            for qual, node in walk_functions(tree):
                name = qual.split(".")[-1]
                defined.add(name)
                bodies.append((name, node))
    adj: dict[str, set[str]] = {name: set() for name, _ in bodies}
    for name, node in bodies:
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                callee = _callee_name(sub.func)
                if callee is not None and callee in defined and callee != name:
                    adj[name].add(callee)
    return adj


# ─── the κ engine — ported VERBATIM from Regenesis significance.py (pure over `adj`) ───
def reachable(adj: dict, start) -> set:
    """The forward-reachable set of ``start`` (excluding itself) — every node a chain from ``start``
    reaches. Iterative BFS, cycle-safe (a visited set), so a recursive/cyclic call graph terminates."""
    seen: set = set()
    frontier = list(adj.get(start, ()))
    while frontier:
        node = frontier.pop()
        if node in seen:
            continue
        seen.add(node)
        frontier.extend(adj.get(node, ()))
    seen.discard(start)
    return seen


def coverage(adj: dict) -> dict:
    """κ per node = ``|cover(v)|`` = the size of its forward-reachable set (SSL's marginal-coverage base,
    before curriculum subtraction). A source hub scores high, a leaf 0. Pure over ``adj``."""
    nodes = set(adj) | {t for outs in adj.values() for t in outs}
    return {n: len(reachable(adj, n)) for n in nodes}


def marginal_coverage(adj: dict, node, selected) -> int:
    """κ(v|S) = ``|cover(v) \\ cover(S)|`` — the marginal coverage of ``node`` given the already-selected
    set ``selected``: how many nodes it reaches that ``selected`` does NOT already. ``selected`` empty →
    κ(v|∅) = |cover(v)| (the base, exactly). The quantity the greedy bound and antitonicity are over."""
    covered: set = set()
    for s in selected:
        covered |= reachable(adj, s)
        covered.add(s)  # a selected node is itself already accounted for
    return len(reachable(adj, node) - covered)


def components(adj: dict) -> list:
    """The WEAKLY-connected components (edges read undirected) — the structure §13's bridge argument is
    about: two nodes in different components are joined by NO chain in either direction, so a rule/censor
    whose endpoints lie in different components is exactly one that joins disjoint clusters (a bridge)."""
    nodes = set(adj) | {t for outs in adj.values() for t in outs}
    undirected: dict = {n: set() for n in nodes}
    for src, outs in adj.items():
        for dst in outs:
            undirected[src].add(dst)
            undirected[dst].add(src)
    seen: set = set()
    out: list = []
    for n in nodes:
        if n in seen:
            continue
        comp: set = set()
        frontier = [n]
        while frontier:  # iterative BFS — the same cycle-safe shape as `reachable`
            cur = frontier.pop()
            if cur in comp:
                continue
            comp.add(cur)
            frontier.extend(undirected.get(cur, ()))
        seen |= comp
        out.append(comp)
    return out


def is_bridge(adj: dict, antecedent, consequent) -> bool:
    """Is adding ``antecedent -> consequent`` a BRIDGE — does it JOIN two previously-DISJOINT components
    (§13, the constructive witness that coverage is not submodular under adoption)? A node absent from the
    graph is its own (empty) component, so an edge introducing a brand-new callee bridges only if it joins
    two EXISTING clusters, never merely by being new."""
    comps = components(adj)
    home = {n: i for i, c in enumerate(comps) for n in c}
    a, c = home.get(antecedent), home.get(consequent)
    return a is not None and c is not None and a != c


def call_graph_shape(adj: dict) -> dict:
    """The FRAGMENTATION of the call graph — the C7 measurement (§18 Q1, App C). The theory predicts a
    code call graph is fragmented (sparse; many weakly-connected components), so the borrowed submodular
    ``(1−1/e)`` greedy bound is far from holding and the bounded-curvature object (§14.6) is the correct
    one. This returns the STATIC shape — component structure + the κ distribution; the ADOPTION-time
    supermodular degree ``d`` (Feige–Izsak, measured on the rule graph) needs the censor-promotion loop
    (§14, deferred), and this is the graph it would be measured over."""
    nodes = set(adj) | {t for outs in adj.values() for t in outs}
    comps = components(adj)
    sizes = sorted((len(c) for c in comps), reverse=True)
    cov = coverage(adj)
    edges = sum(len(o) for o in adj.values())
    return {
        "nodes": len(nodes),
        "edges": edges,
        "components": len(comps),
        "largest_component": sizes[0] if sizes else 0,
        "singletons": sum(1 for s in sizes if s == 1),
        "max_kappa": max(cov.values(), default=0),
        "mean_kappa": round(sum(cov.values()) / len(cov), 2) if cov else 0.0,
    }
