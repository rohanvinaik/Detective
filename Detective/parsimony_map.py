"""Static, repo / module / class-shaped SICP parsimony map — Detective's ONE repo-scale surface,
and it is **advisory, not a proof**.

It never runs a mutant and never writes source. It rolls up the AST-only lenses from
:mod:`Detective.parsimony` — complexity · cohesion · interface width · structural seam — over a
tree, so a reader can see the SHAPE of a codebase's parsimony at a glance and which functions are
the worst offenders. It is deliberately the exception to "there is no ``detective src/``": that law
is about *proof* (there is no repo-scale mutation profile, and never will be); this is a static
read that proves nothing and says so. The behavioural lenses (overload, regime), the per-function
detail, and any actual proof stay in ``diagnose`` / ``converge``, one function at a time.

Because it is advisory it must never crash a run: a file that will not parse, or a function a lens
chokes on, is skipped, not fatal. What it cannot read it simply does not count.
"""

from __future__ import annotations

import ast
import os
from dataclasses import dataclass

from .parsimony import (
    ParsimonyLens,
    _agreement,
    _flagged,
    _seam_vote,
    cohesion_lens,
    complexity_lens,
    interface_width_lens,
)

# The AST-only lenses that can vote −1 (a smell). purity is excluded on purpose — it never votes
# −1 (impurity is the informational zero), so it cannot contribute to a flag; overload and regime
# need a mutation profile and so belong to the per-function `diagnose`, not this static map.
_STATIC_LENSES = (complexity_lens, cohesion_lens, interface_width_lens)


@dataclass(frozen=True)
class FunctionRead:
    """One function's static read: how many lenses call it a smell, and the smell detail."""

    qualname: str
    smells: int  # count of −1 lenses
    flagged: bool  # ≥2 lenses agree (the same consensus rule as the per-function read)
    detail: str  # the −1 lenses, glossed — for the offenders list


@dataclass(frozen=True)
class ScopeScore:
    """A repo / module / class scope: how many functions under it, how many flagged, and the
    parsimony score (percent NOT flagged). ``reads`` are every leaf function under the scope
    (for ranking offenders); ``children`` are the immediate sub-scopes (for drill-down)."""

    name: str
    kind: str  # "repo" | "module" | "class"
    functions: int
    flagged: int
    clean_pct: int
    reads: tuple[FunctionRead, ...]
    children: tuple[ScopeScore, ...]


def _clean_pct(flagged: int, total: int) -> int:
    """A scope's parsimony score: the percent of its functions NOT flagged. Empty scope → 100
    (nothing to fault). Advisory — 'flagged' is a ≥2 static-lens agreement, never a proof."""
    if total == 0:
        return 100
    return round((total - flagged) * 100 / total)


def _static_lenses(func: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ParsimonyLens]:
    lenses = [lens(func) for lens in _STATIC_LENSES]
    try:
        from .decompose import find_extraction_candidates

        seams = len(find_extraction_candidates(func))
    except Exception:  # noqa: BLE001 — a structural read must never fail the map
        seams = 0
    lenses.append(ParsimonyLens("seam", _seam_vote(seams), seams, f"{seams} seam(s)"))
    return lenses


def read_function(func: ast.FunctionDef | ast.AsyncFunctionDef, qualname: str) -> FunctionRead:
    """Static per-function read: the AST lens votes, fused by the same ≥2-agreement rule (reusing
    the pinned ``_agreement`` / ``_flagged``). Attribution kept for the offenders list."""
    lenses = _static_lenses(func)
    votes = tuple(lens.vote for lens in lenses)
    agree = _agreement(votes)
    detail = " · ".join(f"{lens.name} ({lens.detail})" for lens in lenses if lens.vote == -1)
    return FunctionRead(qualname, agree, _flagged(agree), detail)


def _scope(name: str, kind: str, reads: list[FunctionRead], children: tuple[ScopeScore, ...]) -> ScopeScore:
    flagged = sum(1 for r in reads if r.flagged)
    return ScopeScore(
        name, kind, len(reads), flagged, _clean_pct(flagged, len(reads)), tuple(reads), children
    )


def _read(func: ast.FunctionDef | ast.AsyncFunctionDef, qualname: str) -> FunctionRead | None:
    try:
        return read_function(func, qualname)
    except Exception:  # noqa: BLE001 — one odd function must not sink the whole map
        return None


def _module_scope(tree: ast.Module, module_name: str) -> ScopeScore:
    reads: list[FunctionRead] = []
    children: list[ScopeScore] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if (r := _read(node, f"{module_name}::{node.name}")) is not None:
                reads.append(r)
        elif isinstance(node, ast.ClassDef):
            methods = [
                r
                for m in node.body
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                and (r := _read(m, f"{module_name}::{node.name}.{m.name}")) is not None
            ]
            if methods:
                children.append(_scope(f"{module_name}::{node.name}", "class", methods, ()))
    all_reads = reads + [r for c in children for r in c.reads]
    return _scope(module_name, "module", all_reads, tuple(children))


def _python_files(target: str) -> list[str]:
    if os.path.isfile(target):
        return [target] if target.endswith(".py") else []
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(target):
        # Skip the trees that are never the project's own source (mirrors Uroboros's `_is_source`).
        _skip = {"__pycache__", ".git", ".venv", "venv", "build", "dist"}
        dirnames[:] = [d for d in dirnames if d not in _skip and not d.startswith(".")]
        found.extend(os.path.join(dirpath, f) for f in filenames if f.endswith(".py"))
    return sorted(found)


def score_path(path: str, project_root: str = ".") -> ScopeScore:
    """Walk ``path`` (a file or directory) and build the repo → module → class → function map.
    Names are project-root-relative so the report reads the way the repo is laid out."""
    root_abs = os.path.abspath(project_root)
    target = os.path.abspath(path)
    modules: list[ScopeScore] = []
    for f in _python_files(target):
        try:
            with open(f, encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), filename=f)
        except (OSError, SyntaxError):
            continue  # advisory: unreadable is uncounted, never fatal
        modules.append(_module_scope(tree, os.path.relpath(f, root_abs)))
    all_reads = [r for m in modules for r in m.reads]
    rel = os.path.relpath(target, root_abs)
    name = rel if rel != "." else (os.path.basename(root_abs) or "repo")
    return _scope(name, "repo", all_reads, tuple(modules))
