"""The plan — the controller's assembly over a tree (DETERMINISTIC_SICP §14.3, slice 3).

One traversal (the parsimony map's own, `parsimony_map.iter_functions`) → one `RegionDetail` per
region → `controller.plan_moves`. This is `dev/exp_ds_005_controller.main` made a library function,
with the experiment's stated proxies kept as stated proxies:

- **the banks** are the static lenses (`parsimony_map.static_lenses`: complexity · cohesion ·
  interface width · seam · γ-seam), purity, and an overload read off the STATIC DOF proxy — in
  `parsimony._LENS_PRIORITY` order, minus `regime`, which needs a mutation profile this static
  assembly never runs (its absence is a named non-measurement, not a silent 0);
- **the price** is the static mutant-universe size (`static_dof_proxy`), provenance
  `COST_STATIC_DOF_PROXY`; a region the instrument cannot price carries `COST_UNMEASURED` and the
  plan excludes it as "unpriced" rather than fund it on a guess. The live upgrade is
  `audit --plan` (`COST_AUDIT_PLAN_MEASURED`), not wired here;
- **fences are held at 0** — the form-censor spine (§5.3) is unbuilt, so DESTRUCTIVE is
  structurally unexercised; `FENCES_NOTE` says so on every report rather than let a 0 read as
  "nothing is fenced";
- **the behavior status** is read off the certificate ledger and the suite
  (`certify.read_behavior_status`) — the ordering law's one fact per region (§14.1).

ADVISORY: runs no mutant, writes nothing, proves nothing. What it produces is a decision artifact
for the driver — the funded moves with their gates, and the residual with every exclusion named —
and the actuators remain the behavior layer's gates.
"""

from __future__ import annotations

import ast
import os
from dataclasses import dataclass

from .certify import read_behavior_status
from .controller import (
    COST_STATIC_DOF_PROXY,
    COST_UNMEASURED,
    SILENT,
    Plan,
    RegionRead,
    controller_verdict,
    orient_for_change,
    plan_moves,
)
from .parsimony import (
    _LENS_PRIORITY,
    _OVERLOAD_ZERO,
    ParsimonyLens,
    _overload_vote,
    deviation_depth,
    purity_lens,
)
from .parsimony_map import iter_functions, static_lenses
from .templates import TEMPLATE_GRAMMAR, template_matches

FENCES_NOTE = "fences held at 0 — the form-censor spine (§5.3) is unbuilt, so DESTRUCTIVE is unexercised"

CLEAN = "clean"
UNREAD = "unread"
NOT_CLEAN = "not_clean"


def clean_disposition(verdict: str, all_measured: bool) -> str:
    """Sussman's word, defined (§14.2 demand 1 — pure, pinned). "Clean" is kept because it is the
    SICP word for the goal state; it is DEFINED so it can never cover a non-measurement:

      "clean"      SILENT — no bank has a case for change — AND every lens was measured
      "unread"     SILENT, but some lens abstained for want of a measurement: we do not know
      "not_clean"  any verdict with a case in it (CONSTRUCTIVE · AMBIGUOUS · DESTRUCTIVE)

    The informational zero survives the vocabulary: a region nobody could read is not clean, it is
    unread, and `clean%` is clean / measured regions.
    """
    if verdict != SILENT:
        return NOT_CLEAN
    return CLEAN if all_measured else UNREAD


def static_dof_proxy(node: ast.FunctionDef | ast.AsyncFunctionDef, is_method: bool) -> int | None:
    """The static mutant-universe size — the v1 arc price (I/O-free but engine-bound: unit-guarded,
    not pinned). ``None`` when the engine cannot generate for this node: an unpriceable region is
    reported unpriced, never priced by a guess."""
    try:
        from Wesker.engine import generate_mutants
        from Wesker.filter import filter_categories

        from .purity import is_pure

        return len(generate_mutants(node, filter_categories(node, is_pure(node, is_method=is_method))))
    except Exception:  # noqa: BLE001 — the plan is advisory; a region the engine chokes on is unpriced, not fatal
        return None


def overload_lens_static(dof: int | None, span: int) -> ParsimonyLens:
    """The overload bank read off the STATIC DOF proxy (the map excludes overload because it needs a
    mutation profile; the plan reads the static universe instead and SAYS so in the detail). An
    unpriceable region abstains — vote 0, ``measured=False`` — so it reads `unread`, never clean."""
    if dof is None:
        return ParsimonyLens("overload", 0, 0, "DOF proxy unavailable", measured=False)
    density = dof / max(1, span)
    return ParsimonyLens(
        "overload",
        _overload_vote(density),
        density,
        f"{dof} DOF / {span} lines (static proxy)",
        depth=deviation_depth(density, _OVERLOAD_ZERO),
        zero_state=_OVERLOAD_ZERO,
    )


def region_lenses(
    node: ast.FunctionDef | ast.AsyncFunctionDef, is_method: bool, dof: int | None
) -> tuple[ParsimonyLens, ...]:
    """Every bank the plan reads for one region, in `_LENS_PRIORITY` order. `regime` is absent by
    construction (it needs a live profile); everything else is the map's own static readers plus the
    static overload read and purity."""
    span = (node.end_lineno or node.lineno) - node.lineno + 1
    built = {lens.name: lens for lens in static_lenses(node)}
    built["overload"] = overload_lens_static(dof, span)
    built["purity"] = purity_lens(node, is_method=is_method)
    return tuple(built[name] for name in _LENS_PRIORITY if name in built)


@dataclass(frozen=True)
class RegionDetail:
    """One region as the plan reports it: the controller-facing read plus the attribution the
    renderer needs — every lens (with its `measured` flag), the clean disposition, the template's
    evidence, and the gate prose the grammar names for the recognized move."""

    read: RegionRead
    lenses: tuple[ParsimonyLens, ...]
    clean: str  # clean | unread | not_clean
    template_evidence: str  # "line N: …" or ""
    gate: str  # the TEMPLATE_GRAMMAR gate for the recognized move, "" when none


@dataclass(frozen=True)
class PlanAssembly:
    """The plan over one scope: every region's detail, the controller's `Plan` (funded + the named
    residual), the budget it was planned under, and the standing caveat about fences."""

    scope: str
    budget: float
    regions: tuple[RegionDetail, ...]
    plan: Plan
    fences_note: str = FENCES_NOTE


def region_detail(
    root: str,
    write_dir: str,
    func_key: str,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    is_method: bool,
) -> RegionDetail:
    """Assemble one region (the impure shell: reads the ledger, the suite, and the engine)."""
    dof = static_dof_proxy(node, is_method)
    lenses = region_lenses(node, is_method, dof)
    supports = sum(orient_for_change(lens.vote) for lens in lenses)
    verdict = controller_verdict(supports, 0)  # fences held at 0 — FENCES_NOTE
    matches = template_matches(node)
    template = matches[0].template if matches else None
    gate_exists = template in TEMPLATE_GRAMMAR
    read = RegionRead(
        region=func_key,
        verdict=verdict,
        agreement=supports,
        template=template,
        gate_exists=gate_exists,
        cost=float(dof) if dof is not None else 0.0,
        status=read_behavior_status(root, write_dir, func_key, node),
        cost_provenance=COST_STATIC_DOF_PROXY if dof is not None else COST_UNMEASURED,
    )
    return RegionDetail(
        read=read,
        lenses=lenses,
        clean=clean_disposition(verdict, all(lens.measured for lens in lenses)),
        template_evidence=f"line {matches[0].line}: {matches[0].evidence}" if matches else "",
        gate=TEMPLATE_GRAMMAR[template][1] if gate_exists and template is not None else "",
    )


def assemble_plan(
    path: str,
    project_root: str = ".",
    budget: float = 500.0,
    write_dir: str = os.path.join("tests", "detective"),
) -> PlanAssembly:
    """The controller over a tree: every region under ``path`` read, priced, status-checked, and
    planned under ``budget`` (DOF-proxy units, stated). Writes nothing."""
    root_abs = os.path.abspath(project_root)
    target = os.path.abspath(path)
    details = tuple(
        region_detail(root_abs, write_dir, func_key, node, is_method)
        for func_key, node, is_method in iter_functions(target, root_abs)
    )
    plan = plan_moves(tuple(d.read for d in details), budget)
    rel = os.path.relpath(target, root_abs)
    scope = rel if rel != "." else (os.path.basename(root_abs) or "repo")
    return PlanAssembly(scope=scope, budget=budget, regions=details, plan=plan)
