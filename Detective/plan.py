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

from . import pins
from .certify import read_behavior_status
from .controller import (
    CONSTRUCTIVE,
    COST_STATIC_DOF_PROXY,
    COST_UNMEASURED,
    SILENT,
    Plan,
    RegionRead,
    controller_verdict,
    orient_for_change,
    plan_moves,
)
from .judgments import DISPOSITIONS, PROCEED, judgment_for, judgment_standing
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
    # BLE001: the plan is advisory; a region the engine chokes on is unpriced rather than fatal
    except Exception:  # noqa: BLE001
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
    # The recorded style judgment's STANDING (§14.5 — `judgments.judgment_standing`): "" when none,
    # leave / proceed when it applies, reopened_digest / reopened_verdict when the code or the
    # reading moved since. The renderer prints a reopened judgment as such — never silently
    # honoured, never silently dropped. `read.judgment` carries only a standing disposition.
    judgment: str = ""


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
    recorded = judgment_for(root, func_key)
    standing = judgment_standing(
        recorded.function_digest if recorded else "",
        pins.function_digest(node),
        recorded.verdict if recorded else "",
        verdict,
        recorded.disposition if recorded else "",
    )
    read = RegionRead(
        region=func_key,
        verdict=verdict,
        agreement=supports,
        template=template,
        gate_exists=gate_exists,
        cost=float(dof) if dof is not None else 0.0,
        status=read_behavior_status(root, write_dir, func_key, node),
        cost_provenance=COST_STATIC_DOF_PROXY if dof is not None else COST_UNMEASURED,
        judgment=standing if standing in DISPOSITIONS else "",
    )
    return RegionDetail(
        read=read,
        lenses=lenses,
        clean=clean_disposition(verdict, all(lens.measured for lens in lenses)),
        template_evidence=f"line {matches[0].line}: {matches[0].evidence}" if matches else "",
        gate=TEMPLATE_GRAMMAR[template][1] if gate_exists and template is not None else "",
        judgment=standing,
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


REGIME_CONFLICT = "regime_conflict"
NO_SUCH_FUNCTION = "no_such_function"
NOTHING_TO_READ = "nothing_to_read"


@dataclass(frozen=True)
class PlanResolution:
    """What `plan <target>` resolved to, BEFORE any rendering: the assembly, or a typed refusal.
    ONE resolver for both surfaces (CLI `_run_plan`, MCP `plan`), so the regime check, the narrowing
    to one region and the three preconditions cannot drift between them. ``detail`` carries a
    refusal's message without a channel prefix; ``regime`` rides along on a conflict so the surface
    renders the conflicts in its own idiom."""

    refusal: str  # "" · regime_conflict · no_such_function · nothing_to_read
    assembly: PlanAssembly | None
    detail: str = ""
    regime: object = None
    file: str = ""
    function: str = ""


def resolve_plan(
    target: str, project_root: str = ".", budget: float = 500.0, write_dir: str = "tests/detective"
) -> PlanResolution:
    """Resolve a `plan` target — a path (a tree) or `file.py::function` (one region) — to its
    assembly, or refuse (§14.3 / §14.7). The `::` form resolves the testing regime FIRST and refuses
    a shadowed / colliding target exactly as the live verbs do: a plan over the wrong file is a
    finding about nothing. Then the preconditions in `plan_exit`'s order: no such function (the
    file's regions are named) · nothing to read (no Python functions — unmeasured, not clean).
    STATIC: no live session, no mutant; reads the ledgers and the suite, writes nothing."""
    root = os.path.abspath(project_root)
    file = function = ""
    region_key: str | None = None
    scope_path = target
    if "::" in target:
        file, function = target.rsplit("::", 1)
        regime = None
        try:
            from .regime import resolve_regime

            regime = resolve_regime(root, file)
        # BLE001: a guard must never be what breaks the run
        except Exception:  # noqa: BLE001
            regime = None
        if regime is not None and regime.conflicts:
            return PlanResolution(REGIME_CONFLICT, None, regime=regime, file=file, function=function)
        full = file if os.path.isabs(file) else os.path.join(root, file)
        region_key = f"{os.path.relpath(full, root)}::{function}"
        scope_path = full
    assembly = assemble_plan(scope_path, root, budget, write_dir)
    if region_key is not None:
        details = tuple(d for d in assembly.regions if d.read.region == region_key)
        if not details:
            names = ", ".join(d.read.region.split("::", 1)[1] for d in assembly.regions) or "none"
            return PlanResolution(
                NO_SUCH_FUNCTION,
                None,
                f"no function {function!r} in {file} — regions in that file: {names}",
                file=file,
                function=function,
            )
        assembly = PlanAssembly(
            scope=region_key,
            budget=assembly.budget,
            regions=details,
            plan=plan_moves(tuple(d.read for d in details), assembly.budget),
            fences_note=assembly.fences_note,
        )
    if not assembly.regions:
        return PlanResolution(
            NOTHING_TO_READ,
            None,
            f"nothing to read under {target} — no Python functions found (unmeasured, not clean)",
        )
    return PlanResolution("", assembly, file=file, function=function)


# ─────────────────────────────────────────────────────────────────────────────
# The communication side (§14.3 / §14.6): what a region's row SAYS the driver does next, and the
# counts a report is made of. Pure over literals and tuples — what the renderers consume.
# ─────────────────────────────────────────────────────────────────────────────

FUNDED = "funded"
_STATUS_REASONS = (
    pins.PINNED_STALE,
    pins.PINNED_UNVERIFIED,
    pins.PINNED_INCOMPLETE,
    pins.REFUSED,
    pins.UNPINNED,
)


def receipt_path(region: str) -> str:
    """Where the plan SUGGESTS a region's receipt live — `.detective/receipts/<key>.json` (pure —
    pinned). A suggestion, not a ledger: `receipt -o` takes any path and `verify-rewrite` takes it
    back explicitly; this only makes the two commands the plan prints agree with each other. Not
    under `purge`: a receipt is a deliberate snapshot taken BEFORE a rewrite and cannot be
    regenerated once the source has moved."""
    safe = region.replace("::", "__").replace("/", "_").replace("\\", "_").replace(".", "_")
    return os.path.join(".detective", "receipts", f"{safe}.json")


# The move a region's plan reason calls for (§14.3 — named codes, consumed by BOTH surfaces). The
# CLI spells each as a `detective …` line (`next_command`); the MCP surface spells each as a tool
# call (`mcp_server._plan_call`). Neither re-derives the decision from the reason: a surface that
# did could name a move the other does not, and the two would drift.
DECOMPOSE_APPLY = "decompose_apply"  # funded, gate `decompose …` — the split, applied under proof
RECEIPT_BRACKET = "receipt_bracket"  # funded, gate `receipt …` — receipt, transform, verify-rewrite
CONVERGE = "converge"  # a behaviour-status reason — the ordering law: style waits
JUDGE = "judge"  # escalated — AMBIGUOUS is the driver's; record the answer, or ground it first
AUDIT_PLAN = "audit_plan"  # unpriced — a measured price for what the static instrument could not size


def next_move(reason: str, gate: str) -> str:
    """The ONE move a region's plan reason calls for (§14.3 — pure, pinned), as a named code:

    "funded", gate starting "decompose"   → DECOMPOSE_APPLY
    "funded", gate starting "receipt"     → RECEIPT_BRACKET
    "funded", any other gate              → ""  (the grammar names a gate no surface can spell)
    a behaviour-status reason             → CONVERGE  (unpinned · pinned_stale · pinned_unverified ·
                                                        pinned_incomplete · refused)
    "escalated"                           → JUDGE
    "unpriced"                            → AUDIT_PLAN
    fenced · judged_leave · silent · no_template · no_gate · over_budget · anything else → ""
      (nothing to run; the reason itself is the message)
    """
    if reason == FUNDED:
        if gate.startswith("decompose"):
            return DECOMPOSE_APPLY
        if gate.startswith("receipt"):
            return RECEIPT_BRACKET
        return ""
    if reason in _STATUS_REASONS:
        return CONVERGE
    if reason == "escalated":
        return JUDGE
    if reason == "unpriced":
        return AUDIT_PLAN
    return ""


def next_command(reason: str, region: str, gate: str, move: str) -> str:
    """The ONE next command for a region — the CLI's spelling of `next_move` (§14.3 — pure, pinned).
    Every funded move ends by naming its gate invocation, the way `converge` ends by naming its next
    step; every non-admission names the driver's move — and a verb that does not exist yet is never
    named, because the surface must not point at a command it lacks. "" means nothing to run.

      DECOMPOSE_APPLY   → `decompose … --apply` — the split, applied under proof
      RECEIPT_BRACKET   → `receipt … -o <path>`, then the named transform by hand or model, then
                          `verify-rewrite <path> …` — the bracket
      CONVERGE          → `converge …` — the ordering law: style waits
      JUDGE             → `flag … --style --leave|--proceed` — AMBIGUOUS is the driver's, and the
                          answer is RECORDED (§14.5) so it does not re-escalate; grounding it with
                          `converge` first is named beside it, the one move that is never wrong
      AUDIT_PLAN        → `audit … --plan` — a measured price for what the static instrument could
                          not size
      ""                → "" (nothing to run; the reason itself is the message)
    """
    move_code = next_move(reason, gate)
    if move_code == DECOMPOSE_APPLY:
        return f"detective decompose '{region}' --apply"
    if move_code == RECEIPT_BRACKET:
        path = receipt_path(region)
        return (
            f"detective receipt '{region}' -o {path}"
            f"   # apply the '{move}' transform, then: detective verify-rewrite {path} '{region}'"
        )
    if move_code == CONVERGE:
        return f"detective converge '{region}'"
    if move_code == JUDGE:
        return (
            f"detective flag '{region}' --style --leave --note \"why\""
            f"   # or --proceed; to ground it first: detective converge '{region}'"
        )
    if move_code == AUDIT_PLAN:
        return f"detective audit '{region}' --plan"
    return ""


def plan_exit(regime_conflict: bool, region_missing: bool, nothing_read: bool) -> int:
    """`detective plan`'s exit status (§14.7 — pure, pinned), the shared four-valued contract with the
    advisory layer's own rule: a completed read is ``0`` whatever it found — there is no "gap" on this
    layer, only a residual, and a residual is not a failure — so ``1`` is never returned; ``2`` is a
    PRECONDITION: the regime says no verdict here can be trusted (a `file::fn` target that is shadowed
    or colliding), the named function is not in the file, or there was nothing to read under the path
    (no Python functions — not "clean", not measured). ``3`` belongs to the paired budget read on
    `verify-rewrite --budget` (slice 7), not to this verb."""
    if regime_conflict or region_missing or nothing_read:
        return 2
    return 0


# The closing an AGENT-FACING render ends with (§14.6 / §14.9 slice 8 — pure, pinned). The CLI's
# block lists everything and ends with a banner of counts; a tool result must end with ONE line the
# caller acts on, and WHICH line is a decision, not a rendering choice:
DO_FUNDED = "do_funded"  # a gated move exists — name its gate: the plan's own next call
DO_CONVERGE = "do_converge"  # nothing funded, but regions wait on a contract — the ordering law
YOURS = "yours"  # nothing to fund or converge; AMBIGUOUS regions remain — the driver's decision
DONE = "done"  # nothing funded, nothing waiting, nothing escalated


def plan_closing(funded: int, waiting: int, escalated: int) -> str:
    """Which closing an agent-facing plan render ends with (pure — pinned), in the order the
    epistemics dictate: a FUNDED move first (its gate is the plan's own next call, and only the gate
    writes); else a region WAITING on a behaviour contract (style after behaviour, strictly —
    `converge` is the one move that is never wrong); else the AMBIGUOUS queue handed over as the
    driver's DECISION (the automation boundary: the controller will not decide it, and a tool must
    not render a judgment as a task); else done. Counts in, a code out: the renderer names things."""
    if funded > 0:
        return DO_FUNDED
    if waiting > 0:
        return DO_CONVERGE
    if escalated > 0:
        return YOURS
    return DONE


def queue_order(rows: list[tuple[str, int, float]]) -> list[str]:
    """A driver's queue in the plan's ONE total order (§14.3, pure — pinned): strongest agreement
    first, then cheapest, then name — the same law `controller.plan_moves` funds by. Each row is
    ``(region, agreement, cost)``; the regions come back in the order a driver should take them.

    The funder sorts only what it FUNDS; its exclusions come out in traversal order (the file walk,
    alphabetical). A queue built straight from them named the first file's region as the next move
    while the plan's own strongest case sat lower in the report — measured on this repo
    (2026-09-06, the first `plan Detective/` with nothing funded): `binding.py::classify_target`,
    agreement 2, was named before `engine.py::classify_survivors`, agreement 5. A driver reads a
    queue top-down, so the top must be the plan's strongest case by the plan's own law, or the
    surface says one thing and the law another. Split out over literals so the order is pinnable
    apart from the assembly it serves.
    """
    return [region for region, _, _ in sorted(rows, key=lambda row: (-row[1], row[2], row[0]))]


def _in_plan_order(assembly: PlanAssembly, regions: list[str]) -> tuple[str, ...]:
    """``regions`` (names) as a driver's queue — :func:`queue_order` over the assembly's reads."""
    by_region = {d.read.region: d.read for d in assembly.regions}
    return tuple(queue_order([(r, by_region[r].agreement, by_region[r].cost) for r in regions]))


def converge_first(assembly: PlanAssembly) -> tuple[str, ...]:
    """The regions the ordering law holds back: excluded for a BEHAVIOUR-STATUS reason while the
    banks read CONSTRUCTIVE — or while the driver has already said PROCEED (an answered ambiguity is
    a case for change, and behaviour still comes first). ONE definition, consumed by both surfaces,
    in the plan's order (:func:`queue_order`): the first name is the strongest case."""
    by_region = {d.read.region: d for d in assembly.regions}
    waiting = [
        region
        for region, reason in assembly.plan.excluded
        if reason in _STATUS_REASONS
        and (by_region[region].read.verdict == CONSTRUCTIVE or by_region[region].judgment == PROCEED)
    ]
    return _in_plan_order(assembly, waiting)


def escalated_regions(assembly: PlanAssembly) -> tuple[str, ...]:
    """The AMBIGUOUS queue — every region excluded as `escalated`, in the plan's order."""
    return _in_plan_order(
        assembly, [region for region, reason in assembly.plan.excluded if reason == "escalated"]
    )


def reopened_regions(assembly: PlanAssembly) -> tuple[str, ...]:
    """Every region whose recorded style judgment no longer applies (`reopened_*`), in the plan's order."""
    return _in_plan_order(
        assembly, [d.read.region for d in assembly.regions if d.judgment.startswith("reopened")]
    )


@dataclass(frozen=True)
class PlanSummary:
    """The counts a report is made of — every one a NAMED code's tally, never a score."""

    regions: int
    verdicts: tuple[
        tuple[str, int], ...
    ]  # (verdict, count), fixed order: CONSTRUCTIVE · AMBIGUOUS · DESTRUCTIVE · SILENT
    clean: tuple[tuple[str, int], ...]  # (clean · unread · not_clean, count)
    reasons: tuple[tuple[str, int], ...]  # (exclusion reason, count), most frequent first, then name
    funded: int
    spent: float
    unexamined: tuple[str, ...]  # what this plan did NOT examine, said in words


_VERDICT_ORDER = ("CONSTRUCTIVE", "AMBIGUOUS", "DESTRUCTIVE", SILENT)
_CLEAN_ORDER = (CLEAN, UNREAD, NOT_CLEAN)


def unexamined(fences_note: str, template_count: int) -> tuple[str, ...]:
    """The line every plan report ends its findings with (§14.2 demand 4 — pure, pinned): what
    this plan did NOT propose is UNEXAMINED, not approved. Three standing items and the sentence
    that frames them; a new bank or a grown library changes the items, never the sentence."""
    return (
        "what this plan did not propose is UNEXAMINED, not approved",
        "regime — unread: it needs a live mutation profile this static plan never runs",
        fences_note,
        f"recognizers — {template_count} template(s); a region with no match is a library gap, "
        "not a clean bill",
    )


def summarize(assembly: PlanAssembly) -> PlanSummary:
    """Tally one assembly (pure over its tuples). Counts only — the residual's every reason, the
    verdict distribution, clean / unread / not-clean — so the renderers print codes, never sums."""
    verdicts: dict[str, int] = dict.fromkeys(_VERDICT_ORDER, 0)
    clean: dict[str, int] = dict.fromkeys(_CLEAN_ORDER, 0)
    for d in assembly.regions:
        verdicts[d.read.verdict] = verdicts.get(d.read.verdict, 0) + 1
        clean[d.clean] = clean.get(d.clean, 0) + 1
    reasons: dict[str, int] = {}
    for _region, reason in assembly.plan.excluded:
        reasons[reason] = reasons.get(reason, 0) + 1
    return PlanSummary(
        regions=len(assembly.regions),
        verdicts=tuple((v, verdicts[v]) for v in _VERDICT_ORDER)
        + tuple((v, n) for v, n in verdicts.items() if v not in _VERDICT_ORDER),
        clean=tuple((c, clean[c]) for c in _CLEAN_ORDER),
        reasons=tuple(sorted(reasons.items(), key=lambda kv: (-kv[1], kv[0]))),
        funded=len(assembly.plan.funded),
        spent=assembly.plan.budget_spent,
        unexamined=unexamined(assembly.fences_note, len(TEMPLATE_GRAMMAR)),
    )
