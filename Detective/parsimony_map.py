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
    gamma_seam_lens_from_candidates,
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


def static_lenses(func: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ParsimonyLens]:
    """Every AST-only lens for one function, ONE seam scan: complexity · cohesion · interface width,
    then seam and γ-seam off the same `find_extraction_candidates` enumeration. Shared by this map
    and by the plan (`plan.region_lenses`, §14.3) — one reader of the static banks, not two."""
    lenses = [lens(func) for lens in _STATIC_LENSES]
    try:
        from .decompose import find_extraction_candidates

        cands = find_extraction_candidates(func)
    except Exception:  # noqa: BLE001 — a structural read must never fail the map
        # A failed scan ABSTAINS on both seam lenses (vote 0, unmeasured) — it must never vote
        # clean: the old `seams = 0` fallback rendered "we could not look" as "+1 atomic body".
        lenses.append(ParsimonyLens("seam", 0, 0, "seam scan failed", measured=False))
        lenses.append(ParsimonyLens("gamma_seam", 0, 0, "seam scan failed", measured=False))
        return lenses
    seams = len(cands)
    lenses.append(
        ParsimonyLens(
            "seam", _seam_vote(seams), seams, f"{seams} seam(s)", depth=float(seams), zero_state=0.0
        )
    )
    # Wave 0: the γ-seam bank rides the same candidate enumeration (one scan per function).
    lenses.append(gamma_seam_lens_from_candidates(cands))
    return lenses


def read_function(func: ast.FunctionDef | ast.AsyncFunctionDef, qualname: str) -> FunctionRead:
    """Static per-function read: the AST lens votes, fused by the same ≥2-agreement rule (reusing
    the pinned ``_agreement`` / ``_flagged``). Attribution kept for the offenders list."""
    lenses = static_lenses(func)
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


def module_functions(tree: ast.Module, module_name: str):
    """Every REGION in a module, in source order — the ONE traversal this map (`_module_scope`)
    and the plan (`plan.assemble_plan`, §14.3) share, so the two surfaces can never disagree
    about what a region is. Yields ``(func_key, node, is_method, class_key | None)`` where
    ``func_key`` is ``module::name`` or ``module::Class.method`` — the same key `converge`
    writes, so a plan's next command pastes. Nested functions are not regions: no proof gate
    addresses them (converge targets are module-level functions and methods)."""
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield f"{module_name}::{node.name}", node, False, None
        elif isinstance(node, ast.ClassDef):
            for m in node.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield f"{module_name}::{node.name}.{m.name}", m, True, f"{module_name}::{node.name}"


def _module_scope(tree: ast.Module, module_name: str) -> ScopeScore:
    reads: list[FunctionRead] = []
    by_class: dict[str, list[FunctionRead]] = {}
    for func_key, node, is_method, class_key in module_functions(tree, module_name):
        r = _read(node, func_key)
        if r is None:
            continue
        if is_method and class_key is not None:
            by_class.setdefault(class_key, []).append(r)
        else:
            reads.append(r)
    children = tuple(_scope(cls, "class", methods, ()) for cls, methods in by_class.items())
    all_reads = reads + [r for c in children for r in c.reads]
    return _scope(module_name, "module", all_reads, children)


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


def _group_rank(max_smells: int, flagged_count: int) -> tuple[int, int]:
    """Sort key for a trace group in the work plan (issue #51, pure — pinned): worst FIRST, by the
    single most-flagged function's lens agreement, then by how many functions are flagged. Negated so
    a plain ascending sort puts the heaviest module at the top. Ranking WHERE the budget goes first —
    it asserts nothing about any function's quality, the claim the project's refusal actually forbids."""
    return (-max_smells, -flagged_count)


def parsimony_plan(score: ScopeScore) -> tuple[tuple[str, tuple[FunctionRead, ...]], ...]:
    """A trace-grouped, worst-first WORK QUEUE from a scored path (issue #51). SCHEDULES work; ranks no
    quality. Each group is a MODULE — its functions share one baseline trace, the larger of the two
    savings — ordered worst-group-first (:func:`_group_rank`); within a group, functions worst-first
    (most lens agreement). Only flagged functions appear; an empty plan means nothing scored heavy.
    Emits nothing, proves nothing, runs no mutant — it inherits parsimony's advisory labelling."""
    groups: list[tuple[str, tuple[FunctionRead, ...]]] = []
    for module in score.children:
        flagged = tuple(sorted((r for r in module.reads if r.flagged), key=lambda r: (-r.smells, r.qualname)))
        if flagged:
            groups.append((module.name, flagged))
    groups.sort(key=lambda g: (*_group_rank(max(r.smells for r in g[1]), len(g[1])), g[0]))
    return tuple(groups)


def iter_functions(path: str, project_root: str = "."):
    """Every region under ``path`` (a file or directory), project-root-relative func_keys, via the
    same file walk and the same per-module traversal the map uses. Yields ``(func_key, node,
    is_method)``. Unreadable or unparseable files are skipped, not fatal — advisory: what cannot
    be read is not counted, and is never reported as anything."""
    root_abs = os.path.abspath(project_root)
    for f in _python_files(os.path.abspath(path)):
        try:
            with open(f, encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), filename=f)
        except (OSError, SyntaxError):
            continue
        for func_key, node, is_method, _cls in module_functions(tree, os.path.relpath(f, root_abs)):
            yield func_key, node, is_method


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
