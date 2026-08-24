"""``detective`` command — a thin dispatcher over the library API.

No compute here: parse args, call the library, format the result. Example:

    detective converge ./module.py::function [--json]
"""

from __future__ import annotations

import argparse
import ast
import difflib
import json
import os
import shlex
import sys
import textwrap
from dataclasses import asdict, dataclass
from typing import Any

# Imported, never restated: the engine owns this number, and a second copy would drift silently.
from Wesker.engine import DEFAULT_TRACE_BUDGET_S as _WESKER_DEFAULT_TRACE_BUDGET_S
from Wesker.engine import (
    DEFAULT_TRACE_SESSION_BUDGET_S as _DEFAULT_TRACE_SESSION_BUDGET_S,
)

from Detective.validity import cut_reason_sentence

from . import __version__
from .equivalence import crash_only_status


def _trace_budget(args) -> float | None:
    """The CLI's `--trace-budget SECONDS` → the engine's `trace_budget_s`. 0 (or negative) means
    the user explicitly wants the historical UNBOUNDED pass, which the engine spells `None` — so
    the opt-out is one documented value on the CLI rather than a sentinel a caller has to know."""
    v = getattr(args, "trace_budget", _WESKER_DEFAULT_TRACE_BUDGET_S)
    return None if v is not None and v <= 0 else v


def _trace_session_budget(args) -> float | None:
    """The CLI's `--trace-session-budget SECONDS` → the engine's `trace_session_budget_s`. Same
    0 = unbounded convention as `--trace-budget`. Separate from it because they bound DIFFERENT
    things: per-test caps the worst single test, this caps the whole baseline. A suite of 2000
    tests under a 50s per-test cap is still a day of tracing — only this makes the phase finite."""
    v = getattr(args, "trace_session_budget", _DEFAULT_TRACE_SESSION_BUDGET_S)
    return None if v is not None and v <= 0 else v


@dataclass(frozen=True)
class ExecutionContext:
    """The interpreter boundary every live-suite decision is measured under."""

    executable: str
    prefix: str
    active_environment: str | None
    disposition: str


def execution_disposition(active_environment: str | None, interpreter_prefix: str) -> str:
    """Name whether the active project environment owns this interpreter (#58, pure — pinned).

    ``PYTHONPATH`` can redirect imports but cannot change a console script's shebang.  Keeping the
    two states named prevents a foreign launcher from falling through to pytest, where the same
    mismatch is reconstructed later as a missing target package or plugin.
    """
    if not active_environment:
        return "ready"
    return "ready" if active_environment == interpreter_prefix else "wrong_interpreter"


def _execution_context() -> ExecutionContext:
    """Capture the process/environment identity once, before pytest is allowed to start."""
    active = os.environ.get("VIRTUAL_ENV")
    # CONDA_PREFIX often survives when an explicit uv/venv interpreter is launched from a Conda
    # shell.  In that state it describes the parent shell, not the project environment.  Accept it
    # only when it actually contains this interpreter; unlike VIRTUAL_ENV it cannot safely prove a
    # mismatch on its own.
    conda = os.environ.get("CONDA_PREFIX")
    if not active and conda:
        prefix = os.path.normcase(os.path.realpath(sys.prefix))
        conda_real = os.path.normcase(os.path.realpath(conda))
        if prefix == conda_real:
            active = conda
    active_real = os.path.normcase(os.path.realpath(active)) if active else None
    prefix_real = os.path.normcase(os.path.realpath(sys.prefix))
    return ExecutionContext(
        executable=os.path.realpath(sys.executable),
        prefix=prefix_real,
        active_environment=active_real,
        disposition=execution_disposition(active_real, prefix_real),
    )


def _format_execution_refusal(context: ExecutionContext) -> str:
    """An exact recovery for a console script bound to a foreign interpreter."""
    active = context.active_environment or ""
    bindir = "Scripts" if os.name == "nt" else "bin"
    python = os.path.join(active, bindir, "python")
    detective = os.path.join(active, bindir, "detective")
    install = shlex.join(["uv", "pip", "install", "--python", python, "detective-spec"])
    rerun = shlex.join([detective, *sys.argv[1:]])
    return (
        "REFUSED: Detective is running under a different interpreter than the active project environment.\n"
        f"  active environment: {active}\n"
        f"  Detective Python:   {context.executable}\n"
        "  Install Detective into the active environment, then invoke that environment's launcher:\n"
        f"    {install}\n"
        f"    {rerun}\n"
    )


def reachable_disposition(n_targets: int, raised: bool, scoped_count: int | None) -> str:
    """Why `_reachable_paths` chose its collection scope — a named disposition, not the old
    `list | None` (B2, pure — pinned).

    The old wrapper collapsed THREE unrelated outcomes into one `None`: no single target, a
    CRASHED analysis, and a deliberate "collect everything". The ARC measurement (TEST_BASIS §13)
    cannot tell "declined" from "narrowed" through that, and a blanket crash-swallow of exactly
    this shape has hidden a real defect before (bd6f24e). Each state means something different, so
    each gets its own code — never a bool:

      "declined_multi"  0 or >1 targets — no analysis was attempted
      "declined_error"  the static analysis RAISED — degrade to full collection, but say so
      "roots"           analysis ran and did not narrow — the configured floor / full tree
      "scoped"          analysis narrowed to `scoped_count` target-relevant paths
    """
    if n_targets != 1:
        return "declined_multi"
    if raised:
        return "declined_error"
    if scoped_count is None:
        return "roots"
    return "scoped"


@dataclass(frozen=True)
class PathScope:
    """The pytest collection scope AND why it is that scope (B2).

    ``paths`` is pytest's own collection argument — a scoped list, or ``None`` to collect
    everything. ``disposition`` is :func:`reachable_disposition`'s code, so a decline (no single
    target, or a CRASHED analysis) is never the same value as a deliberate "collect everything".
    Consumers read ``.paths`` today; the ARC measurement (TEST_BASIS C1) reads ``.disposition`` to
    tell "declined" from "narrowed".
    """

    paths: list[str] | None
    disposition: str


def _reachable_paths(
    root: str,
    targets: list[str] | None,
    target_module: str | None = None,
    import_roots: tuple[str, ...] = (),
    testpaths: tuple[str, ...] = (),
) -> PathScope:
    """pytest collection scope for the target, carrying WHY — a PathScope, not a bare list | None.

    Wrapped so the scoping can NEVER be the thing that breaks a run: any failure in the static
    analysis degrades to full collection (``paths=None``), i.e. exactly today's behaviour — but now
    as ``disposition='declined_error'`` rather than a silent ``None`` indistinguishable from the two
    other reasons ``paths`` can be ``None`` (the §14 conflation that once hid a real defect).

    ``testpaths`` is the regime's declared pytest ``testpaths``: it bounds the collection to the
    project's own suite so an installed dependency's ``test_*.py`` (which a repo-walk reaches under
    ``.venv*/``) is never traced, and it is the collection FLOOR when reachability cannot narrow.
    """
    n_targets = len(targets) if targets else 0
    if not targets or n_targets != 1:  # `not targets` also narrows `targets` to non-None below
        return PathScope(None, reachable_disposition(n_targets, raised=False, scoped_count=None))
    try:
        from .reachability import reachable_test_paths

        paths = reachable_test_paths(
            root,
            targets[0],
            target_module=target_module,
            import_roots=import_roots,
            testpaths=testpaths,
        )
    except Exception:  # noqa: BLE001 — scoping is an optimisation; degrade to full, but NAME it
        return PathScope(None, reachable_disposition(1, raised=True, scoped_count=None))
    scoped_count = len(paths) if paths is not None else None
    return PathScope(paths, reachable_disposition(1, raised=False, scoped_count=scoped_count))


def _split_target(target: str, project_root: str | None = None) -> tuple[str, str]:
    """Split ``path/to/file.py::function`` into ``(file, function)``.

    Issue #1: the most likely first-run mistake — forgetting ``::`` — used to be the ONE
    bad target that got no menu, even though at that point we hold a path to a real file
    and could list its functions exactly as the wrong-name path does. When the ``::``-less
    target names an existing ``.py`` file, hand back that same menu, same ``detective:``
    prefix; when it names nothing, the bare format message stands.
    """
    if "::" not in target:
        raise SystemExit(_no_separator_message(target, project_root))
    file, function = target.rsplit("::", 1)
    if not file or not function:
        raise SystemExit(f"detective: target must be 'file.py::function', got {target!r}")
    return file, function


def _no_separator_message(target: str, project_root: str | None) -> str:
    """The error for a ``::``-less target — with the file's own function menu when the
    target IS a real .py file. Never raises: this runs on the error path."""
    base = f"detective: target must be 'file.py::function', got {target!r}"
    names: list[str] = []
    try:
        from Wesker.ci import walk_functions

        root = os.path.abspath(project_root or ".")
        full = target if os.path.isabs(target) else os.path.join(root, target)
        if target.endswith(".py") and os.path.isfile(full):
            with open(full, encoding="utf-8") as fh:
                names = [qn for qn, _ in walk_functions(ast.parse(fh.read(), filename=full))]
    except Exception:  # noqa: BLE001 — a formatter that throws replaces the message with a traceback
        names = []
    if not names:
        return base
    shown = ", ".join(names[:12]) + (f", … (+{len(names) - 12} more)" if len(names) > 12 else "")
    return f"{base}\n  functions in that file: {shown}\n  e.g.: '{target}::{names[0]}'"


def _format_scope(scope) -> str:
    """The diagnose report: what this function does, and the ONE thing to run next.

    This is the entry point — the first thing anyone sees, and often the only thing a reader
    without the vocabulary will get through. So no term appears without its gloss, and the
    run ends in exactly one command.

    The warnings above the fold are not decoration. A cut trace UNDER-counts line coverage,
    and an under-counted line is indistinguishable from an uncovered one in the numbers right
    below it — so a completeness verdict resting on a truncated measurement is the one failure
    this tool cannot afford, and it says which knob to turn. "No tests discovered" is the same
    hazard wearing a different face: 0 pinned means "nothing to kill with", not "weak tests",
    and a reader who confuses the two goes off to fix a suite that does not exist.
    """
    spec, kq = scope.specification, scope.kill_quality
    seams = getattr(scope, "decompose_seams", 0)
    entangled = scope.regime == "B"
    head = f"{scope.function} — diagnose · {spec.behavioral_variants} behaviours"
    head += f" · {spec.distinctions_pinned} pinned · {spec.unspecified_dof} unpinned"
    lines = [_RULE, head, ""]

    if getattr(scope, "tests_discovered", -1) == 0:
        lines.append(_row("⚠ NO tests", "nothing pins this function yet — the counts above"))
        lines.append(_row("", "reflect ABSENT tests, not weak ones."))
    for row in _trace_cut_rows(scope):
        lines.append(row)
    routing = getattr(scope, "test_routing", {}) or {}
    if routing:
        # The PARTITION of discovered tests — candidate + unknown + impossible = every discovered
        # test. Rendered as the partition it is.
        lines.append(
            _row(
                "· test routing",
                (
                    f"{routing.get('candidate', 0)} candidate · "
                    f"{routing.get('unknown', 0)} unknown · "
                    f"{routing.get('impossible', 0)} impossible"
                ),
            )
        )
        # `observed` is ORTHOGONAL to that partition — a provenance count, not a fourth bucket: how
        # many routes came from an exact prior POSITIVE trace rather than a static positive prior.
        # Rendered on its own line so it is never read as "of which N impossible": the old inline
        # `(N observed)` after impossible was backwards, since impossible ⊆ observed by construction
        # (G6/§15.4). ``impossible`` is 0 on a normal run since X1 (a replayed negative never excludes).
        observed = routing.get("observed", 0)
        if observed:
            lines.append(_row("", f"{observed} of these routed from an exact prior trace"))
        # Also orthogonal: shape-hazardous unknowns DEFERRED from the speculative widen (shaped-defer),
        # disclosed so a residual is never silently attributed to the code. Only present when non-zero.
        deferred = routing.get("deferred_shaped", 0)
        if deferred:
            lines.append(
                _row(
                    "",
                    f"{deferred} isolation-hazardous test(s) held out of the widen — "
                    "re-run --include-shaped to trace them",
                )
            )
    # #40: two rows, never one. A crash/timeout kill proves the code RUNS, not what it returns, so
    # it must not sit under the checked "pinned" gutter — a scanning reader reads everything beside
    # ✓ as specified. value-pinned is the checked population; run-only is its own unchecked row.
    lines.append(_row("✓ value-pinned", f"{kq.by_value_assertion} pin the RETURN VALUE"))
    if kq.by_crash:
        lines.append(
            _row("· run-only", f"{kq.by_crash} crash/timeout detection(s) — return value still unspecified")
        )
    if kq.warning:
        # The ENGINE's sentence, verbatim. Substituting a generic one here throws away the
        # specific thing it measured and says something adjacent instead — the same defect as
        # every other renderer bug in this file, committed while fixing them.
        lines.append(_row("", f"⚠ {kq.warning}"))
    if spec.unspecified_dof:
        kinds = ", ".join(scope.surviving_categories) if scope.surviving_categories else "—"
        lines.append(_row("✗ unpinned", f"{spec.unspecified_dof} · {kinds}"))
    if spec.inert_freedom:
        lines.append(_row("· inert", f"{spec.inert_freedom} — no test could ever tell the difference"))
    lines.append(_row("· shape", _shape_phrase(entangled, seams)))
    lines += _parsimony_rows(scope)
    lines.append("")
    lines += _diagnose_action(scope, spec, entangled, seams)
    return "\n".join(lines)


def _shape_phrase(entangled: bool, seams: int) -> str:
    """One phrase for the two INDEPENDENT signals — behavioural entanglement (from the
    mutation profile) and structural seams (from the deterministic clustering). They can
    disagree, and when they do the honest read is "this is one thing that does a lot",
    not the blanket "decompose may split it" that used to contradict itself on flat code."""
    if entangled and seams >= 1:
        return f"entangled AND {seams} clean seam(s) — two signals agree it is >1 thing"
    if entangled:
        return "entangled, but structurally one piece — no seam to split"
    if seams >= 1:
        return f"cohesive, but {seams} clean seam(s) exist — splitting is optional"
    return "cohesive and structurally one piece"


def _parsimony_rows(scope) -> list[str]:
    """The SICP parsimony advisory row — shown ONLY when ≥2 lenses agree a function reads heavy.

    Advisory, stylistic, NOT a proof: it points where a human or large model driving Detective
    might look, and it deliberately never touches the ``DO THIS`` action, which stays the one
    provable next step. Absent read or no flag → nothing, so a clean function adds no noise (the
    same "show only what matters" rule the rest of the report follows). The lenses are already in
    priority order, so the first named IS the dominant one — attribution, not a bare number.
    """
    par = getattr(scope, "parsimony", None)
    if par is None or not par.flagged:
        return []
    smells = " · ".join(f"{lens.name} ({lens.detail})" for lens in par.lenses if lens.vote == -1)
    return [
        _row("· parsimony", f"⚠ advisory — {par.agreement} lenses agree, stylistic (not a proof)"),
        _row("", smells),
        _row("", "a human/model call — any split still goes through decompose's proof gate"),
    ]


def _format_parsimony_map(score, top: int = 10) -> str:
    """The `detective parsimony <path>` report: a repo/module/class SICP map, worst-first.

    Static and ADVISORY — it runs no mutant and writes nothing, and every line here says so, the
    same way `_format_scope` never lets the per-function advisory touch the DO THIS action. A scope
    lists only its FLAGGED members (the report's "show what matters" rule); a fully clean tree gets
    one line, not a wall of green.
    """
    lines = [
        _RULE,
        f"{score.name} — parsimony · {score.functions} functions · {score.flagged} flagged "
        f"· {score.clean_pct}% clean   (static advisory)",
        "",
    ]
    modules = sorted(
        (c for c in score.children if c.kind == "module" and c.flagged),
        key=lambda m: (m.clean_pct, -m.flagged),
    )
    classes = sorted(
        (cc for c in score.children for cc in c.children if cc.flagged),
        key=lambda cc: (cc.clean_pct, -cc.flagged),
    )
    offenders = sorted((r for r in score.reads if r.flagged), key=lambda r: (-r.smells, r.qualname))

    if modules:
        lines.append(_row("worst modules", "clean% · flagged/total"))
        for m in modules[:top]:
            lines.append(_row("", f"{m.clean_pct:>3}%  {m.flagged:>2}/{m.functions:<3}  {m.name}"))
        lines.append("")
    if classes:
        lines.append(_row("worst classes", "clean% · flagged/total"))
        for c in classes[:top]:
            lines.append(_row("", f"{c.clean_pct:>3}%  {c.flagged:>2}/{c.functions:<3}  {c.name}"))
        lines.append("")
    if offenders:
        lines.append(_row("worst functions", f"{len(offenders)} flagged · {min(top, len(offenders))} shown"))
        for r in offenders[:top]:
            lines.append(_row("", f"{r.smells}⚠  {r.qualname}"))
            lines.append(_row("", f"    {r.detail}"))
        lines.append("")
    else:
        lines.append(_row("✓ clean", "no function trips ≥2 static lenses — nothing to flag"))
        lines.append("")
    lines.append(_row("· advisory", "a STATIC read (complexity · cohesion · interface · seam) — guidance,"))
    lines.append(_row("", "NOT a proof, and it writes nothing. For the behavioural lenses (overload,"))
    lines.append(_row("", "regime) and the PROOF: detective diagnose <file>::<function>"))
    return "\n".join(lines)


def _format_parsimony_plan(score, top: int = 10) -> str:
    """The `parsimony --plan` WORK QUEUE (issue #51): flagged functions grouped by module — one
    baseline trace per group — worst-first, each line a paste-able target. It SCHEDULES work; it
    ranks no quality and proves nothing, and the header says so."""
    from .parsimony_map import parsimony_plan

    plan = parsimony_plan(score)
    lines = [
        _RULE,
        f"{score.name} — parsimony --plan · {score.functions} functions · {score.flagged} flagged "
        f"· {len(plan)} trace group(s) · a schedule, not a finding (advisory)",
        "",
    ]
    if not plan:
        lines.append(_row("", "nothing scored heavy — no work queued."))
        return "\n".join(lines)
    for module, reads in plan[:top]:
        lines.append(f"  ▸ {module}  —  one baseline trace · {len(reads)} flagged, worst-first")
        for r in reads:
            lines.append(_row("", f"{r.qualname}   {r.smells}⚠  {r.detail}"))
    if len(plan) > top:
        lines.append(_row("", f"… {len(plan) - top} more group(s) — raise --top"))
    return "\n".join(lines)


def _format_censor_proposal(rows: list, total: int, top: int) -> str:
    """The ranked censor PROPOSAL render (read-only): each near-miss with its marginal-κ and the
    per-censor disposition (propose / abstain_low_kappa / refuse_inadmissible). Advisory — nothing
    written; a censor is UNVERIFIED until promoted or triaged (Def. 9.5)."""
    lines = [
        f"censor — {total} proposed near-miss(es), ranked by marginal-κ over the call graph",
        "        (advisory · static · nothing written)",
        "",
    ]
    if not rows:
        lines.append("  (none — no observed near-miss across the call-site population)")
        return "\n".join(lines)
    for _key, censor, kappa, disp in rows[:top]:
        k = kappa if kappa is not None else "?"
        lines.append(f"  κ={k:<4} {disp:<18} {censor.func_key} · {censor.subject} ({censor.source})")
    if total > top:
        lines.append(f"  … and {total - top} more (raise --top)")
    lines += [
        "",
        "DONE:  proposals only — a censor is UNVERIFIED until promoted or triaged (Def. 9.5).",
        "       Re-run with --promote to adopt the admissible, high-κ ones into the ledger.",
    ]
    return "\n".join(lines)


def _format_censor_promote(result: dict, proposed: int) -> str:
    """The --promote render: the corpus fixpoint's promotions, demotions, and L_ind (§16.5). Conservative-
    empty on clean data is the honest outcome ('the spine is the bottleneck'), not a failure."""
    promoted = result["promoted"]
    lines = [
        f"censor --promote — corpus fixpoint reached in {result['generations']} generation(s)",
        f"        {proposed} proposed · {len(promoted)} promoted · {result['n_demoted']} demoted "
        f"· L_ind={result['self_teaching']:.2f}",
        "",
    ]
    if not promoted:
        lines += [
            "  (nothing promoted — conservative-empty on this corpus)",
            "  A censor promotes only when it is spine-sourced, admissible, AND adds real κ (bridges",
            "  otherwise-disjoint call clusters). The honest 'the spine is the bottleneck' (§15).",
        ]
        return "\n".join(lines)
    for e in promoted:
        lines.append(
            f"  κ={e.kappa} gen{e.generation}  {e.censor.func_key} · {e.censor.subject} ({e.censor.source})"
        )
    lines += [
        "",
        "DONE:  the promoted censors are persisted to .detective/censors.json (--list to review).",
        "       They are proposals for human triage, never a gate — proof/triage disposes (Def. 9.5).",
    ]
    return "\n".join(lines)


def _format_censor_list(entries: dict) -> str:
    """The --list render of the persisted ledger (.detective/censors.json), state-annotated."""
    lines = [f"censor --list — {len(entries)} persisted entry(ies) in .detective/censors.json", ""]
    if not entries:
        lines.append("  (empty — run `detective censor <path> --promote` to populate it)")
        return "\n".join(lines)
    for e in entries.values():
        k = e.kappa if e.kappa is not None else "?"
        lines.append(
            f"  [{e.state:<8}] κ={k} gen{e.generation}  {e.censor.func_key} · "
            f"{e.censor.subject} ({e.censor.source})"
        )
    return "\n".join(lines)


def _trace_cut_rows(scope) -> list[str]:
    """The cut-trace warning, or nothing.

    Tense is a claim. A cache hit traced NOTHING this run, so "were CUT" would describe a
    measurement that did not happen, under a machine load that is gone and unreproducible
    (the budgets are wall-clock). Saying WHICH run got cut is the difference between a
    re-run that re-measures and an hour spent tuning budgets against a recording.
    """
    cut = getattr(scope, "trace_truncated", []) or []
    if not cut:
        return []
    cached = getattr(scope, "served_from_cache", False)
    when = "when this verdict was measured (replayed from cache)" if cached else "on this run"
    return [
        _row("⚠ trace CUT", f"{len(cut)} test(s) hit the budget {when} —"),
        _row("", "line coverage is UNDER-counted, so a gap below may be"),
        _row("", "the budget, not a hole. Re-measure exactly with:"),
        _row("", "--trace-session-budget 0 --trace-budget 0   (0 = unbounded)"),
    ]


def _diagnose_action(scope, spec, entangled: bool, seams: int) -> list[str]:
    """Diagnose's ONE next action, in the report's row style.

    Priority IS the judgement: split before you pin. When both signals agree the function is
    more than one thing, `decompose` is the move even though behaviour is unpinned — it
    converges internally, and pinning the pieces afterwards is cheaper than pinning the tangle
    first and then splitting a suite you have to re-derive. Otherwise `converge`. The old report
    printed both and let the reader choose; two actions is a choice they have no basis to make.

    No derived input here, and that is not an omission: diagnose is read-only and works from a
    `ScopeMap`, which carries no witnesses — so there is nothing to batch. The command IS the
    whole action.
    """
    fn = scope.function
    if entangled and seams >= 1:
        return [
            f"DO THIS:  detective decompose '{fn}' --apply",
            "",
            _row("· Why", "Two signals agree this is more than one function."),
            _row("· Safety", "--apply writes ONLY if a generated suite proves the"),
            _row("", "behaviour survived. If it cannot, it says what it needs"),
            _row("", "and leaves your source untouched."),
        ]
    if spec.unspecified_dof:
        return [
            f"DO THIS:  detective converge '{fn}'",
            "",
            _row("· Why", f"{spec.unspecified_dof} behaviour(s) have no test pinning them."),
            _row("· Writes", "test files, and wires them into pytest for you."),
        ]
    return [
        "DONE:  every behaviour this function makes is already pinned by a test.",
        "",
        _row("· Optional next", f"detective audit '{fn}'   # is the suite minimal?"),
    ]


def _score(killed: int, total: int) -> str:
    """Mutation score as a whole-percent string; ``n/a`` when there are no mutants."""
    return f"{round(100 * killed / total)}%" if total else "n/a"


def _input_template(param_names: tuple[str, ...] | None) -> str:
    """A visibly non-executable ``--input`` template shaped to the target's parameters.

    The user replaces each ``<name>`` slot with a literal to exercise the residual; the
    CLI parses the completed value and the AST builds the test.  Angle-bracket slots are a
    drafting aid, never a ``DO THIS`` command: only parser-validated concrete values may be
    rendered as executable guidance.

    A zero-parameter target gets NO skeleton (#8). Measured, `status()` — which accepts nothing
    — was handed ``--input "(<value>,)"`` two lines below a report printing ``Signature
    status()``. There is no literal that reaches a residual in a function with no inputs, so a
    pasteable recipe is a false hand-back: the reader supplies it, the parse fails or the value
    goes nowhere, and the residual is unchanged. Abstaining is the honest answer, and the caller
    renders the bare command.

    ``None`` still yields the generic placeholder: not-supplied is not the same fact as
    no-parameters, and only the latter licenses the abstention.
    """
    if parameter_scope(param_names) == "none":
        return ""
    if not param_names:
        return '--input "(<value>,)"'
    slots = ", ".join(f"<{n}>" for n in param_names)
    tail = "," if len(param_names) == 1 else ""
    return f'--input "({slots}{tail})"'


def _concise_diff(diff_summary: str) -> str:
    """Reduce a mutant's full before/after ``diff_summary`` to just the changed line(s).

    ``diff_summary`` is ``"- <whole original source>\\n+ <whole mutant source>"`` — its
    stable identity for `flag`, but a wall of text in a residual. Line-diff the two blocks
    and emit only the lines that actually differ, so the residual names the EXACT mutated
    branch the user must reach — not the entire function.
    """
    marker = "\n+ "
    if diff_summary.startswith("- ") and marker in diff_summary:
        idx = diff_summary.index(marker)
        orig_lines = diff_summary[2:idx].splitlines()
        mut_lines = diff_summary[idx + len(marker) :].splitlines()
        changed: list[str] = []
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=orig_lines, b=mut_lines).get_opcodes():
            if tag == "equal":
                continue
            changed += [f"- {ln.strip()}" for ln in orig_lines[i1:i2]]
            changed += [f"+ {ln.strip()}" for ln in mut_lines[j1:j2]]
        if changed:
            return "  ".join(changed)
    # Fallback: no parseable before/after — show the first non-empty line, truncated.
    first = next((ln.strip() for ln in diff_summary.splitlines() if ln.strip()), "")
    return f"{first[:100]}…" if len(first) > 100 else first


def _comparisons(src: str) -> list[tuple[str, type, str]]:
    """(left_src, op_class, right_src) for each single-operator comparison in a diff line,
    normalizing statement headers (`if …:` / `elif …:`) so the fragment parses on its own."""
    s = src.strip()
    if s.startswith("elif "):
        s = "if " + s[len("elif ") :]
    if s.endswith(":"):
        s += "\n    pass"
    try:
        tree = ast.parse(s)
    except SyntaxError:
        return []
    out: list[tuple[str, type, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            out.append((ast.unparse(node.left), type(node.ops[0]), ast.unparse(node.comparators[0])))
    return out


_ORDERING_OPS = (ast.Lt, ast.LtE, ast.Gt, ast.GtE)
# The ordering ops that hold when the operands are EQUAL. Two ordering comparisons differ at the
# equality edge iff exactly one of them is in here — i.e. iff the shift is strict↔non-strict.
# `<=`↔`>=` is a direction flip, not an edge shift: both are True at `==`, so they AGREE there and
# `left == right` is the one input that CANNOT distinguish them. Emitting the hint anyway asked
# for that input, got no progress, and re-derived the same ask from the same survivor — forever.
_HOLDS_AT_EQ = (ast.LtE, ast.GtE)


def _differs_at_eq(op: type, m_op: type) -> bool:
    """Do these two ordering comparisons disagree when their operands are EQUAL?

    THE rule behind every boundary hint, named so it can be tested and covered on its own. True
    iff exactly one side holds at the edge — i.e. iff the shift is strict↔non-strict. `<`→`<=`
    qualifies; `<=`→`>=` does NOT (both True at `==`), and neither does `<`→`>` (both False).
    """
    return op in _ORDERING_OPS and m_op in _ORDERING_OPS and (op in _HOLDS_AT_EQ) != (m_op in _HOLDS_AT_EQ)


def _difference_region(op: type, m_op: type, left: str, right: str) -> str | None:
    """The relation an input must satisfy for the original and mutated comparison to DISAGREE —
    the region a distinguishing witness must land in, else None when no rule names it.

    `_differs_at_eq` covers the strict↔non-strict shifts, where the region is exactly the
    equality edge. It is NOT the whole table: a non-strict ordering collapsed to bare equality
    (`>=` → `==`) AGREES at the edge — both hold — and differs exactly on the strict side the
    mutation cut off, so `quantity >= 50` vs `quantity == 50` is distinguished only where
    `quantity > 50`. Hinting the edge there (or hinting nothing, the prior behavior) sent the
    search to the one region that cannot answer, and the mutant read "candidate-equivalent"
    while a one-past-the-edge input kills it.
    """
    if _differs_at_eq(op, m_op):
        return f"{left} == {right}"
    pair = {op, m_op}
    if pair == {ast.GtE, ast.Eq}:
        return f"{left} > {right}"
    if pair == {ast.LtE, ast.Eq}:
        return f"{left} < {right}"
    # A STRICT ordering against bare equality (`>` ↔ `==`) disagrees AT the edge: the strict
    # form is False there, the equality True.
    if pair in ({ast.Gt, ast.Eq}, {ast.Lt, ast.Eq}):
        return f"{left} == {right}"
    return None


# Column width for a grouped survivor's mutated statement. Sized so the count and category
# breakdown still land inside the 78-col rule the report is ruled to.
_STMT_W = 46


def _mutated_stmt(diff_summary: str) -> str:
    """The ORIGINAL statement a mutant changed — the grouping key for a survivor list.

    Survivors cluster hard by statement (one guard clause spawns a dozen), so this is the axis
    that turns a per-mutant wall into a per-branch summary. Falls back to `_concise_diff` when
    the mutation is a pure insertion with no original line to name.
    """
    marker = "\n+ "
    if diff_summary.startswith("- ") and marker in diff_summary:
        idx = diff_summary.index(marker)
        orig_lines = diff_summary[2:idx].splitlines()
        mut_lines = diff_summary[idx + len(marker) :].splitlines()
        changed: list[str] = []
        for tag, i1, i2, _j1, _j2 in difflib.SequenceMatcher(a=orig_lines, b=mut_lines).get_opcodes():
            if tag != "equal":
                changed += [ln.strip() for ln in orig_lines[i1:i2]]
        if changed:
            return "  ".join(changed)
    return _concise_diff(diff_summary)


def _survivor_lines(verdicts, verbose: bool, param_names: tuple[str, ...] | None = None) -> list[str]:
    """One survivor block — per-mutant under `verbose`, grouped by mutated statement otherwise.

    The grouped form keeps the BOUNDARY hints (the only actionable part) and drops the ids and
    diffs, which is what makes a 200-line function's residual readable. The ids are never lost:
    the written report always renders verbose, and `--verbose` reproduces it on the terminal.
    """
    out: list[str] = []
    if verbose:
        for v in verdicts:
            out.append(f"    → mutant {v.mutant_id} [{v.category}]: {_concise_diff(v.diff_summary)}")
            if v.category == "BOUNDARY" and (hint := _boundary_hint(v.diff_summary, param_names)):
                out.append(f"        ↳ {hint}")
            if v.crash_only and not v.suite_detected and v.crash_witness is not None:
                # The fact that decides the next action: this survivor is invisible to the
                # current suite, and here is the input that exposes it.
                args = ", ".join(repr(a) for a in v.crash_witness.args)
                out.append(f"        ↳ reached by no current test — crash witness: f({args})")
        return out
    groups: dict[str, list] = {}
    for v in verdicts:
        groups.setdefault(_mutated_stmt(v.diff_summary), []).append(v)
    for stmt, vs in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        counts: dict[str, int] = {}
        for v in vs:
            counts[v.category] = counts.get(v.category, 0) + 1
        cats = ", ".join(f"{n} {c}" for c, n in sorted(counts.items()))
        shown = stmt if len(stmt) <= _STMT_W else stmt[: _STMT_W - 1] + "…"
        out.append(f"    {shown:<{_STMT_W}}  {len(vs):>3}   ({cats})")
        hints: list[str] = []
        internal: list[str] = []
        for v in vs:
            if v.category == "BOUNDARY" and (h := _boundary_hint(v.diff_summary, param_names)):
                if _is_internal_hint(h):
                    if h not in internal:
                        internal.append(h)
                elif (rel := _hint_relation(h)) not in hints:
                    hints.append(rel)
        out += [f"        ↳ distinguish at the boundary — supply an input {r}" for r in hints]
        out += [f"        ↳ {h}" for h in internal]
    out.append("    (--verbose for each mutant's id and diff)")
    return out


def parameter_scope(param_names: tuple[str, ...] | None) -> str:
    """Whether a parameter list can classify a name at all (#8, pure — pinned).

    ``None`` AND ``()`` MEAN OPPOSITE THINGS HERE and three call sites fused them with
    ``param_names or None``. An empty tuple is a FACT — this function takes no parameters — and
    it is the strongest possible evidence that a comparison over named locals is an internal
    condition, because there is no parameter it could be. ``or None`` turned that fact into "not
    supplied", which is the one value that skips both #8 guards and restores the pre-#8
    rendering. So the case where abstention is most certainly correct was the case that got the
    confident answer: "supply an input where risk > 4" for a function that accepts no input.

    This is the cannot-determine / determined-false conflation, and truthiness is what hides it:
    `()` and `None` are both falsy, so the collapse reads as a harmless normalisation.

    ``unknown`` — not supplied; no classification is possible and the historical rendering stands.
    ``none``    — the function has no parameters; no predicate over parameters can exist, so a
                  named comparison is necessarily internal.
    ``known``   — at least one parameter; the operands can be classified against it.
    """
    if param_names is None:
        return "unknown"
    if not param_names:
        return "none"
    return "known"


def _boundary_hint(diff_summary: str, param_names: tuple[str, ...] | None = None) -> str | None:
    """For a BOUNDARY mutant — an operator shift on a comparison — name the region a
    distinguishing input must land in: the equality edge for strict↔non-strict shifts, the
    cut-off strict side for non-strict→`==` collapses (see `_difference_region` for the table).
    The relation comes WITH its real operands, not as a generic template (BOUNDARY is
    oracle-light, not oracle-free). Recovers the operands by matching the comparison whose
    operator changed between original and mutant; None if no rule names the region.

    Issue #8 — the residual's TYPE must survive to the reader. When ``param_names`` is given
    and the comparison reads a name that is NOT a parameter (``risk > 4`` over a derived
    local), the region is an INTERNAL condition: presenting it as a direct input requirement
    hands the reader a predicate no call satisfies literally, with the dominating path
    conditions silently dropped. Those render as an explicit internal-condition line — the
    certified abstention — instead of ``supply an input where …``. With ``param_names=None``
    the classification is unavailable and the historical rendering stands.
    """
    # diff_summary is '- <whole original>\n+ <whole mutant>'; block-diff it (as _concise_diff
    # does) to isolate the lines that actually changed, then find the comparison whose operator
    # shifted — not the def line the raw prefixes would otherwise pick up.
    marker = "\n+ "
    if not (diff_summary.startswith("- ") and marker in diff_summary):
        return None
    idx = diff_summary.index(marker)
    orig_lines = diff_summary[2:idx].splitlines()
    mut_lines = diff_summary[idx + len(marker) :].splitlines()
    o_changed: list[str] = []
    m_changed: list[str] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=orig_lines, b=mut_lines).get_opcodes():
        if tag == "equal":
            continue
        o_changed += orig_lines[i1:i2]
        m_changed += mut_lines[j1:j2]
    m_cmps = [c for ln in m_changed for c in _comparisons(ln)]
    for ln in o_changed:
        for left, op, right in _comparisons(ln):
            for m_left, m_op, m_right in m_cmps:
                if (
                    m_left == left
                    and m_right == right
                    and (region := _difference_region(op, m_op, left, right))
                ):
                    _scope = parameter_scope(param_names)
                    # `none` short-circuits: with no parameters there is nothing for
                    # `_params_only` to match, and saying so directly keeps the reason legible.
                    if _scope == "none" or (
                        _scope == "known" and not _params_only(left, right, param_names or ())
                    ):
                        return (
                            f"internal condition `{region}` decides this — not a direct input "
                            "constraint; Detective could not derive a verified call from the "
                            "parameters"
                        )
                    # Review finding 3: operands being parameters does not make the
                    # region path-complete — `weight == 10` beneath `if enabled:` is a
                    # recipe that silently omits `enabled`. Until control-dependence is
                    # derived, a dominated comparison abstains; only one this analysis
                    # PROVES unconditionally evaluated keeps the actionable form.
                    if _scope == "known" and not _always_evaluated("\n".join(orig_lines), left, op, right):
                        return (
                            f"internal condition `{region}` sits behind enclosing control "
                            "flow — the relation alone is not path-complete; supply a call "
                            "that reaches this comparison and lands on the edge"
                        )
                    return f"distinguish at the boundary — supply an input where {region}"
    return None


def _always_evaluated(orig_src: str, left: str, op: type, right: str) -> bool:
    """True only when the matched comparison PROVABLY evaluates on every call — no
    enclosing branch, loop body, short-circuit position, ternary arm, try, match, or
    nested scope decides whether it runs, and no SEQUENTIAL PREDECESSOR can divert
    control before it (issue #8, second round: an earlier ``if enabled: return False``
    is a control-flow predecessor, not an ancestor, and an ancestors-only check called
    the final ``return weight > 10`` unconditional). Anything unparseable or
    unlocatable is False: the promotable form is a claim, and a claim this cannot
    verify abstains."""
    try:
        tree = ast.parse(textwrap.dedent(orig_src))
    except SyntaxError:
        return False
    if not tree.body or not isinstance(tree.body[0], (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    fn = tree.body[0]
    target: ast.Compare | None = None
    for node in ast.walk(fn):
        if (
            isinstance(node, ast.Compare)
            and len(node.ops) == 1
            and type(node.ops[0]) is op
            and ast.unparse(node.left) == left
            and ast.unparse(node.comparators[0]) == right
        ):
            target = node
            break
    if target is None:
        return False

    def path_to(node: ast.AST) -> list[ast.AST] | None:
        if node is target:
            return [node]
        for child in ast.iter_child_nodes(node):
            sub = path_to(child)
            if sub is not None:
                return [node, *sub]
        return None

    path = path_to(fn)
    if path is None:
        return False
    for parent, child in zip(path, path[1:], strict=False):
        if isinstance(child, ast.stmt) and not _predecessors_fall_through(parent, child):
            return False
        if parent is fn:
            continue
        if isinstance(parent, (ast.If, ast.While)):
            if child is not parent.test:
                return False
        elif isinstance(parent, (ast.For, ast.AsyncFor)):
            if child is not parent.iter:
                return False
        elif isinstance(parent, ast.IfExp):
            if child is not parent.test:
                return False
        elif isinstance(parent, ast.BoolOp):
            if child is not parent.values[0]:  # only the first operand always evaluates
                return False
        elif isinstance(
            parent,
            (
                ast.Try,
                ast.ExceptHandler,
                ast.Match,
                ast.ListComp,
                ast.SetComp,
                ast.DictComp,
                ast.GeneratorExp,
                ast.Lambda,
                ast.FunctionDef,
                ast.AsyncFunctionDef,
                ast.ClassDef,
            ),
        ):
            return False
    return True


def _predecessors_fall_through(parent: ast.AST, child: ast.stmt) -> bool:
    """True when every statement BEFORE ``child`` in its suite provably falls through
    to it. A predecessor that contains a return/raise anywhere (a conditional early
    exit included), an unbounded ``while``, or control routing this analysis does not
    model (``try``/``match``) may prevent the comparison from ever running — the
    promoted recipe would then name an input the function never tests."""
    for field in ("body", "orelse", "finalbody"):
        suite = getattr(parent, field, None)
        if isinstance(suite, list) and child in suite:
            return all(not _may_divert(prior) for prior in suite[: suite.index(child)])
    return True  # child is not in a statement suite of parent (it is a test/iter expr)


def _may_divert(node: ast.AST) -> bool:
    """Can executing ``node`` route control away from the statement after it?
    Return/raise anywhere within (a CONDITIONAL early exit counts — "may", not
    "must"), an unbounded ``while``, or ``try``/``match`` routing this analysis does
    not model. Nested function/class/lambda scopes are not descended: their
    ``return`` belongs to them, not to the enclosing flow."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
        return False
    if isinstance(node, (ast.Return, ast.Raise, ast.Break, ast.Continue, ast.While, ast.Try, ast.Match)):
        return True
    if hasattr(ast, "TryStar") and isinstance(node, ast.TryStar):
        return True
    return any(_may_divert(child) for child in ast.iter_child_nodes(node))


def _params_only(left: str, right: str, param_names: tuple[str, ...]) -> bool:
    """True when every name the comparison reads is a function parameter — the one case
    where ``supply an input where {region}`` is literally satisfiable by a call. A derived
    local in either operand makes the region an internal condition instead."""
    for src in (left, right):
        try:
            tree = ast.parse(src, mode="eval")
        except SyntaxError:
            return False
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id not in param_names:
                return False
    return True


def _is_internal_hint(hint: str) -> bool:
    """Classify a rendered `_boundary_hint` line without re-deriving it."""
    return hint.startswith("internal condition ")


def _target_lines(signature: str) -> list[str]:
    """The residual's ``target:`` signature line, plus a one-line legend when any
    parameter type was inferred from call sites (rendered ``p: ~Type``) rather than
    declared — so the ``~`` marker is never unexplained."""
    if not signature:
        return []
    lines = [f"      target:  {signature}"]
    if "~" in signature:
        lines.append("      note:    ~Type = inferred from call sites (param un-annotated), approximate")
    return lines


def _interactive_stderr() -> bool:
    """True when stderr is a terminal a ``\\r`` can redraw.

    Both progress reporters below overwrite ONE line in place. That is right at a terminal
    and wrong everywhere else: a pipe, a CI log, or an agent capturing the run keeps every
    carriage return, so a long profile arrives as one multi-kilobyte line with `\\r` buried
    in it and no way to read the phases apart. It reads as a run that printed nothing —
    which is exactly the "looks hung" failure these reporters exist to fix, reintroduced one
    layer down. Off-terminal they keep the same INFORMATION and drop only the redraw: one
    complete line per phase, in order, greppable.

    Anything other than a real terminal answers False, including a stderr that has been
    replaced or closed — a progress indicator must never be the thing that ends a run.
    """
    import sys

    try:
        return bool(sys.stderr.isatty())
    except Exception:  # noqa: BLE001 — detached//closed/substituted stderr is simply not a tty
        return False


def eta_seconds(done: int, total: int, elapsed_ms: float, anchor_done: int, anchor_ms: float) -> float | None:
    """Seconds remaining, computed from the rate SINCE an anchor — or None when too few to be honest.

    The naive ``elapsed / done`` extrapolates the FIXED warm-up (import, harness setup, the cold first
    mutant) across the whole run, so mutant #1 quoted a 23× overshoot (issue #53). The anchor is the
    first observed frame with ``done >= 1``; measuring the rate from there excludes that warm-up. Fewer
    than 2 samples PAST the anchor (i.e. < ~3 mutants seen) returns None so the caller prints
    ``estimating…`` rather than a wild number — the estimate lands only once it is grounded."""
    past = done - anchor_done
    if past < 2 or done >= total:
        return None
    per_ms = (elapsed_ms - anchor_ms) / past
    return max(0.0, (total - done) * per_ms / 1000.0)


def rate_label(done: int, elapsed_ms: float) -> str:
    """A legible throughput label. Below 1/s, ``done/secs`` rounds to a useless ``0/s`` (issue #53) —
    a 28-mutant run in 422s is ``0/s`` but ``15.1s/mutant``. So flip the unit under 1/s to the one
    that carries the number; at or above 1/s the per-second rate reads fine."""
    secs = elapsed_ms / 1000.0
    if secs <= 0 or done <= 0:
        return "…"
    rate = done / secs
    return f"{rate:.1f}/s" if rate >= 1.0 else f"{secs / done:.1f}s/mutant"


def _print_tier0_static(file: str, function: str, project_root: str) -> None:
    """Stream TIER 0 — the AST-only static read — the instant the file parses (issue #52).

    audit's cost is tiered (static ~0s · traced · mutation) but only the final tier was ever shown, so
    a first-time user faced a dead terminal for minutes. This prints the cheapest tier immediately: the
    same parsimony lenses `parsimony`/`--plan` use, carrying their own warrant (``static · proves
    nothing``) so it can never be mistaken for the mutation verdict below. Best-effort, to stderr (the
    result/--json owns stdout); a courtesy that must never fail the audit."""
    import sys

    try:
        from .engine import _resolve
        from .parsimony_map import read_function

        root = os.path.abspath(project_root)
        full = file if os.path.isabs(file) else os.path.join(root, file)
        with open(full, encoding="utf-8") as fh:
            _qn, node = _resolve(ast.parse(fh.read()), function)
        if node is None:
            return
        read = read_function(node, function)
        detail = read.detail if read.detail else "no static smell"
        sys.stderr.write(f"  … {function}: static · {detail} · proves nothing (advisory)\n")
        sys.stderr.flush()
    except Exception:  # noqa: BLE001 — tier 0 is a courtesy; the audit stands without it
        return


@dataclass
class _ProgressState:
    """Mutable frame state for the two streaming progress reporters.

    Both reporters kept this as a dict literal, and the dicts were heterogeneous — `int`, `float`
    and `bool` under one inferred value type — so `anchor_done` typed as `int | float` and every
    read of it was an untyped bag lookup. `ty` caught it where the bag met a signature
    (`eta_seconds(..., anchor_done: int, ...)`); nothing else could, because a dict lookup answers
    every question you ask it.

    Shared rather than duplicated because THE TWO REPORTERS ARE NOT THE SAME FUNCTION and looked
    like it — one spelled the opener flag `opened`, the other `started`, for the identical concept.
    That is the lookalike-closure shape this repo has already paid for once: two definitions that
    read as one, diverging silently. One declared shape makes the sameness checkable instead of
    apparent.
    """

    last_ms: float = -1e9
    anchor_done: int = 0
    anchor_ms: float = 0.0
    opened: bool = False


def _stream_trace_progress(label: str):
    """Live progress for the TRACED BASELINE pass — the phase that runs BEFORE the first mutant.

    `_stream_progress` below already fixed "looks hung" for the mutation loop; this is the same
    fix one phase earlier, and it is the phase that actually dominates a big suite's wall clock
    (89% of it, measured — see Wesker's `trace_suite`). Because it runs first, a silent trace means
    the mutation reporter has not printed even once, so the whole run looks dead from the outside:
    zero output at 99% CPU, indistinguishable from a crash. Same stderr + in-place + throttle as
    the mutation reporter, so the two phases read as one continuous stream.
    """
    import sys

    live = _interactive_stderr()
    lead = "\r  … " if live else "  … "
    pad = "   " if live else ""
    state = _ProgressState()

    def cb(done: int, total: int, elapsed_ms: float) -> None:
        if not state.opened:
            # Say the wait is coming BEFORE it happens: on a big suite the trace dominates the wall
            # clock and used to print nothing until it finished, indistinguishable from a hang (#53).
            state.opened = True
            sys.stderr.write(f"{lead}{label}: tracing {total} function-routed tests{pad}\n")
            sys.stderr.flush()
        if done >= 1 and state.anchor_done == 0:
            state.anchor_done, state.anchor_ms = done, elapsed_ms  # exclude warm-up from the ETA
        if 0 < done < total:
            # Off-terminal there is no line to redraw, so intermediate frames are noise the
            # final line already summarises. On one, throttle to ~5 updates/sec.
            if not live or elapsed_ms - state.last_ms < 200.0:
                return
        state.last_ms = elapsed_ms
        secs = elapsed_ms / 1000.0
        if done >= total:
            sys.stderr.write(f"{lead}{label}: baseline traced · {total} tests · {secs:.1f}s{pad}\n")
            # A target-first run may invoke the SAME callback for a candidate seed and, only if a
            # gap remains, a widened unknown batch. Reset at the phase boundary so the second batch
            # gets its own opener/ETA instead of following a mutant "done" line in silence.
            state.opened = False
            state.anchor_done = 0
            state.anchor_ms = 0.0
            state.last_ms = -1e9
        else:
            eta = eta_seconds(done, total, elapsed_ms, state.anchor_done, state.anchor_ms)
            eta_str = f"~{eta:.0f}s" if eta is not None else "estimating…"
            sys.stderr.write(f"{lead}{label}: tracing baseline {done}/{total} tests · ETA {eta_str}{pad}")
        sys.stderr.flush()

    return cb


def _stream_progress(label: str):
    """A throttled progress callback that streams live mutation progress to STDERR, in
    place — so a long profile never 'looks hung' (fix for the whole-file audit that ran
    5 min with zero output). stderr keeps stdout clean for the result / --json.

    Telemetry sources, stated honestly:
      * live ETA/rate = MEASURED this run — remaining × mean-per-mutant-time-so-far — so it
        reflects the ACTUAL machine (cores, load), self-calibrating within ~1s. No hardware
        model, no a-priori assumption.
      * upfront estimate = this machine's OWN recent per-mutant throughput (a rolling EMA
        cached in ~/.detective/telemetry.json), so before the first mutant you see a grounded
        ``est ~Xs (this machine)``. First-ever run says 'calibrating' (no prior data — honest).
      * final line = the reported post-process telemetry (total mutants, elapsed) and updates
        the cache.
    """
    import sys

    live = _interactive_stderr()
    lead = "\r  … " if live else "  … "
    pad = "   " if live else ""
    prior_ms = _read_per_mutant_ms()
    state = _ProgressState()

    def cb(done: int, total: int, elapsed_ms: float) -> None:
        if not state.opened:
            state.opened = True
            # The opener exists to say "something is happening" before the first mutant
            # lands. Off-terminal nothing is waiting on it and the completion line carries
            # the same numbers, so it is a duplicate rather than reassurance.
            if live:
                if prior_ms and total:
                    est = total * prior_ms / 1000.0
                    rate_note = "(this machine's recent rate)"
                    sys.stderr.write(f"{lead}{label}: 0/{total} mutants · est ~{est:.1f}s {rate_note}{pad}")
                else:
                    sys.stderr.write(f"{lead}{label}: 0/{total} mutants · calibrating this machine…{pad}")
                sys.stderr.flush()
        # EVERY pass, not just the first. This guard used to sit inside the `started` block, so
        # it protected the opening pass and nothing after it: converge reuses ONE callback across
        # its re-profiles, and from the second pass on a `done=0` frame fell through to the ETA
        # branch below. On a terminal `\r` hid it; off one there is no line to redraw, so it
        # printed `0/207 mutants · 0/s · ETA 0.0s` immediately followed by the completion line —
        # two frames welded into one, which is what every CI log of a converge looked like.
        if done == 0:
            return
        if 0 < done < total:
            if live:
                if elapsed_ms - state.last_ms < 200.0:
                    return  # throttle to ~5 updates/sec on a terminal
            # Off-terminal there is no line to redraw, so this used to be
            # first + last ONLY — a 20-minute mutant loop on a heavy-import
            # target wrote NOTHING to a tee'd log, and "running" vs "hung"
            # was decidable only by ps (issue #19). Emit a newline-terminated
            # heartbeat instead, throttled hard so CI logs stay bounded.
            elif elapsed_ms - state.last_ms < 15_000.0:
                return
        if state.anchor_done == 0:
            state.anchor_done, state.anchor_ms = done, elapsed_ms  # exclude warm-up from the ETA
        state.last_ms = elapsed_ms
        secs = elapsed_ms / 1000.0
        rate_str = rate_label(done, elapsed_ms)  # legible below 1/s (s/mutant), not a rounded 0/s
        if done >= total:
            if total:
                _update_per_mutant_ms(elapsed_ms / total)  # learn this machine's throughput
            sys.stderr.write(f"{lead}{label}: {done}/{total} mutants · {rate_str} · done in {secs:.1f}s\n")
        else:
            eta = eta_seconds(done, total, elapsed_ms, state.anchor_done, state.anchor_ms)
            eta_str = f"~{eta:.0f}s" if eta is not None else "estimating…"
            tail = f"{pad}" if live else " (heartbeat)\n"
            sys.stderr.write(f"{lead}{label}: {done}/{total} mutants · {rate_str} · ETA {eta_str}{tail}")
        sys.stderr.flush()

    return cb


def _notify_stderr(msg: str) -> None:
    """Stream converge's live phase narrative — one clean line per phase (survivors
    found, tests written, kills, finalize/classify) — to STDERR, so a long multi-pass
    run is legible as it runs instead of a silent monolith. STDERR keeps STDOUT clean
    for the result / --json; the line is newline-terminated so it never clobbers the
    in-place per-mutant progress line (which finalizes each pass with a newline)."""
    import sys

    sys.stderr.write(f"  ▸ {msg}\n")
    sys.stderr.flush()


def _telemetry_cache_path() -> str:
    return os.path.join(os.path.expanduser("~"), ".detective", "telemetry.json")


def _read_per_mutant_ms() -> float | None:
    """This machine's recent per-mutant evaluation cost (ms), or None if never measured.
    Machine-local (throughput depends on the box, not the project), so it lives under ~/."""
    import json

    try:
        with open(_telemetry_cache_path(), encoding="utf-8") as fh:
            val = float(json.load(fh).get("per_mutant_ms", 0.0))
        return val or None
    except (OSError, ValueError, TypeError, KeyError):
        return None


def _update_per_mutant_ms(observed_ms: float) -> None:
    """Fold this run's measured per-mutant cost into a rolling EMA, so the upfront estimate
    tracks the machine's throughput without one anomalous run dominating. Best-effort."""
    import json

    prior = _read_per_mutant_ms()
    value = observed_ms if prior is None else 0.7 * prior + 0.3 * observed_ms
    path = _telemetry_cache_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"per_mutant_ms": round(value, 3)}, fh)
    except OSError:
        pass


def _format_survivor_report(
    rep,
    signature: str = "",
    param_names: tuple[str, ...] = (),
    verbose: bool = True,
    structural_difficulty: str = "",
) -> list[str]:
    """Render the grounded disposition of every leftover survivor: equivalent
    (retained), killable (a suggested test, NOT auto-applied), or uncertain.

    For candidate-equivalent survivors — the Zone-2 residual — emit a PRECISE,
    copy-pasteable hand-back: the surviving mutant id + category + what it changed, the
    target's signature, and the exact ``--input`` skeleton to supply to reach the branch
    and kill it. A user should never have to guess the input from prose.

    ``verbose`` renders every mutant's id and diff; without it the survivors group by mutated
    statement. The written report always passes True — a file has no scrolling cost, and the ids
    `flag` needs must stay somewhere stable.

    Crash-only-distinguishable survivors render as their OWN class with no ``--input`` ask: an
    input already distinguishes them, so asking for one is unsatisfiable by construction.
    """
    if rep is None:
        return []
    lines: list[str] = []
    # Two classes, because they take different actions and only one of them is a request.
    crash_only = [v for v in rep.equivalent if v.crash_only]
    unproven = [v for v in rep.equivalent if not v.crash_only]
    if unproven and not rep.killable and not rep.unclassified:
        lines.append(
            "  ✓ every killable mutant killed — remaining survivors have no distinguishing "
            "input (candidate-equivalent, NOT proven)"
        )
    if unproven:
        cats = ", ".join(sorted({v.category for v in unproven}))
        tried = unproven[0].searched
        lines.append(
            f"  candidate-equivalent — retained, UNPROVEN ({len(unproven)}: {cats}); "
            f"no distinguishing input in {tried} tried. To KILL: supply an input reaching a "
            "mutated branch below (or `flag` if truly equivalent):"
        )
        # NOT `param_names or None` (#8): an empty tuple means 'no parameters', a fact that makes
        # abstention certain — collapsing it to None restored the unguarded rendering.
        lines += _survivor_lines(unproven, verbose, param_names)
        lines += _target_lines(signature)
        # A zero-parameter target has no slots to fill, so "supply:" would head an empty
        # recipe and instruct the reader to do something impossible (#8).
        if _tmpl := _input_template(param_names):
            lines.append(f"      template: {_tmpl}   # replace every <...> slot before running")
    if crash_only:
        cats = ", ".join(sorted({v.category for v in crash_only}))
        n_det, n_undet = crash_only_status(crash_only)
        head = (
            f"  value-equivalent, crash-only-distinguishable ({len(crash_only)}: {cats}) — the "
            "mutant RAISES where the original returns, so no return-value assertion can pin it."
        )
        # The detection claim is made per mutant, from the profile — not assumed for the
        # bucket. The old single sentence said "your suite already detects them" for ALL of
        # these, which was false exactly for the ones no test reaches.
        if n_det and not n_undet:
            # "Detection is complete" and "a sharper witness exists" are different
            # claims — the old "nothing to supply" flatly contradicted the ↳ hint
            # lines below, which DO name an input worth supplying.
            head += (
                " Your suite already detects every one by crash — no input is owed for "
                "detection; a ↳ line below, where present, names the boundary input that "
                "would make the distinction explicit."
            )
        elif n_undet:
            head += (
                f" Your suite crash-detects {n_det} of them; the other {n_undet} are reached by "
                "NO current test — converge writes a golden capture at each crash witness "
                "(↳ below) so they are at least crash-detected."
            )
        head += " `flag` if truly equivalent:"
        lines.append(head)
        lines += _survivor_lines(crash_only, verbose, param_names)
    # #67 detector: when the target has the nested / worklist-driven shape whose distinguishing
    # inputs deterministic synthesis does not reach, a leftover survivor may be killable with a
    # harder (nested / cross-referential) input rather than equivalent — so caution against a
    # false `flag` here. Only when there ARE flag-eligible survivors (candidate-equivalent or
    # crash-only); a fully killed target needs no caveat.
    if deep_structure_caveat(structural_difficulty, bool(unproven)):
        from .equivalence import structural_residual_handback

        # F2 dispatch: never send the reader to `--input` for a residual whose distinguishing input
        # has no literal form — that is the broken ask `converge_next_action` also refuses.
        _how = (
            "a nested / cross-referential `--input`"
            if structural_residual_handback(bool(rep.inputs_expressible)) == "structural_input"
            else "a hand-built object (a real value — no `--input` expresses this shape)"
        )
        lines.append(
            "  ⚠ deep-structure caveat: this target indexes into collection elements and drives a "
            "worklist/fixpoint loop — a shape whose distinguishing inputs the witness search does "
            "NOT synthesize. A survivor above may be KILLABLE, not equivalent. Confirm with a "
            f"differential check (original vs mutant over {_how}) BEFORE you `flag`."
        )
    if rep.manual_equivalent:
        lines.append(
            f"  ✓ {len(rep.manual_equivalent)} survivor(s) flagged equivalent (oracle — PROVEN, not gaps)"
        )
    if rep.killable:
        lines.append(f"  killable — SUGGESTED tests (not auto-applied, {len(rep.killable)}):")
        # One witness often kills many mutants — the field case printed the
        # SAME 800-char assert twelve times (issue #18). Group by the rendered
        # (input, expected) pair and say the useful fact instead: one pin
        # closes N degrees of freedom. Insertion-ordered, so the first
        # appearance keeps its place in the report.
        grouped: dict[tuple[str, str], list] = {}
        for v in rep.killable:
            w = v.witness
            args = ", ".join(repr(a) for a in w.args)
            grouped.setdefault((args, str(w.original)), []).append(v)
        for (args, original), verdicts in grouped.items():
            w = verdicts[0].witness
            if len(verdicts) == 1:
                kills = ""
            else:
                ids = ", ".join(v.mutant_id for v in verdicts)
                kills = f"   (kills {len(verdicts)}: {ids})"
            if _witness_input(w) is not None:
                lines.append(f"    → assert f({args}) == {original}   (mutant gives {w.mutant}){kills}")
            else:
                objects = ", ".join(type(a).__name__ for a in w.args) or "test-built object"
                lines.append(
                    f"    → hand-write a test using {objects}; observed {original} "
                    f"(mutant gives {w.mutant}){kills}"
                )
    if rep.unclassified:
        tail = f": {rep.note}" if rep.note else ""
        lines.append(f"  uncertain — {len(rep.unclassified)} survivor(s) not classified{tail}")
    elif rep.note:
        lines.append(f"  uncertain — {rep.note}")
    return lines


def _show_written(path: str | None) -> list[str]:
    """Echo the code Detective actually wrote to disk, so the user sees exactly
    what was auto-applied — not just a path. Empty when nothing was written."""
    if not path:
        return []
    try:
        with open(path, encoding="utf-8") as fh:
            body = fh.read()
    except OSError:
        return []
    lines = ["  ── written to disk (auto-applied) ──"]
    lines += [f"  │ {ln}" if ln else "  │" for ln in body.rstrip("\n").split("\n")]
    return lines


def _completeness_verdict(result) -> str:
    """The honest headline. 'COMPLETE' is claimed ONLY when nothing killable remains AND
    no survivor is merely *candidate*-equivalent (an unproven 'no distinguishing input
    found' — automated search never proves equivalence; only a manual `flag` or a killing
    input resolves it). When candidate-equivalents remain, we killed every mutant we could
    distinguish but cannot claim completeness, and we say exactly that."""
    # A CUT run (issue #31) never measured the full universe; its headline is the CUT, not a
    # completeness claim (``result.complete`` is already False, but say WHY, not just "Incomplete").
    if getattr(result, "budget_exhausted", False):
        phase = getattr(result, "cut_phase", "") or "a profiling phase"
        return f"⚠ CUT — aggregate deadline exhausted during {phase}; measurement partial"
    # A proof basis that ran red/uncollectable (issue #38): name the verification status, not just
    # "Incomplete" — the mutants are all killed; what failed is the suite running green.
    _ver = getattr(result, "verification", None)
    if _ver is not None and not _ver.ok:
        return f"⚠ UNVERIFIED — proof basis {_ver.status} under real pytest; certificate withheld"
    if not result.complete:
        # Not "✗": the residual is stated on the lines that follow, and marking a run that
        # pinned every killable behavior as a failure misreads the tool's own result.
        return "Incomplete"
    rep = result.survivor_report
    # #36: name the two residual classes separately — a crash-only mutant HAS a distinguishing
    # input (by crash), so it is not "candidate-equivalent / no input distinguishes it".
    candidate = len(rep.candidate_equivalent) if rep is not None else 0
    crash_only = len(rep.crash_only) if rep is not None else 0
    if candidate == 0 and crash_only == 0:
        return "✓ COMPLETE — every mutant killed or oracle-proven-equivalent, line-complete"
    bits = []
    if candidate:
        bits.append(
            f"{candidate} candidate-equivalent (UNPROVEN: `flag` if truly equivalent, "
            "or add a distinguishing input)"
        )
    if crash_only:
        bits.append(f"{crash_only} crash-only value gap(s) — detected by crash; no value pins them")
    return "✓ every killable mutant killed + line-complete — " + "; ".join(bits)


def _rel_path(path: str) -> str:
    """Display a written path relative to cwd when possible — converge stores absolute
    paths, but a banner reads far cleaner as `tests/foo.py` than a long /tmp/... string."""

    try:
        rel = os.path.relpath(path, os.getcwd())
    except ValueError:  # different drive (Windows)
        return path
    return rel if not rel.startswith("..") else path


def _plain_terms(result) -> str:
    """The verdict in plain language — mirrors diagnose's strongest section, so converge's
    headline doesn't lean on jargon (every-killable-killed, DOF) to be read.

    Names EVERY remaining disposition — killable, uncertain, candidate-equivalent, and a
    line gap — so INCOMPLETE is never opaque. Candidate-equivalents lead with 'supply an
    input' (they are usually killable with a richer input), not 'flag' (which is giving up)."""
    rep = result.survivor_report
    # #36: this row leads candidate-equivalents with "supply an input" (usually killable with a
    # richer one) — TRUE of candidate-equivalent, FALSE of crash-only (no value can pin them), so
    # count only the former here.
    cand = len(rep.candidate_equivalent) if rep is not None else 0
    killable = len(rep.killable) if rep is not None else 0
    unresolved = result.final_survivors if rep is None and not result.functionally_complete else 0
    uncertain = len(rep.unclassified) if rep is not None else 0
    gap = len(result.missing_lines)
    if result.complete and cand == 0:
        return "the suite pins every behavior a test can — nothing killable remains, every line covered"
    parts = []
    if killable:
        parts.append(f"{killable} behavior(s) still killable — supply the input(s) below")
    if unresolved:
        parts.append(f"{unresolved} behavior(s) unresolved — classification produced no survivor report")
    if uncertain:
        parts.append(f"{uncertain} survivor(s) need a real sample input to classify")
    if cand:
        parts.append(
            f"{cand} survivor(s) LOOK equivalent but UNPROVEN — supply a distinguishing input, "
            "or `flag` if truly equivalent"
        )
    if gap:
        parts.append(f"{gap} line(s) no test covers — supply an input that reaches them")
    return "; ".join(parts) if parts else "more passes or supplied inputs needed to finish"


def _final_banner(result) -> str:
    """A stable, greppable, ALWAYS-LAST line — so `tail`/scroll-to-bottom always lands
    on the result, never in a generated-test body. Survives truncation by construction."""
    # A verdict computed against a file that changed under the run is NOT a
    # verdict (issue #17): the mutants came from the start-of-run parse while
    # the suite imported the edited module from disk. Stamp it before any
    # status wording — STALE overrides COMPLETE and Incomplete alike, because
    # both would be claims about a measurement that did not happen.
    if getattr(result, "stale_target", False):
        return (
            f"FINAL {result.function}: ⚠ STALE — target changed during run; "
            "measurement invalid, re-run required"
        )
    # A CUT run (issue #31) is likewise a non-verdict — the wall stopped it before the
    # universe was measured — so CUT overrides COMPLETE/Incomplete for the same reason
    # STALE does: both would claim a measurement that did not finish.
    if getattr(result, "budget_exhausted", False):
        phase = getattr(result, "cut_phase", "") or "a profiling phase"
        return (
            f"FINAL {result.function}: ⚠ CUT — aggregate deadline exhausted during {phase}; "
            "measurement partial, re-run with a larger --deadline"
        )
    # A measurement Wesker itself declared UNGATEABLE (#60/#19) is a non-verdict for the same
    # reason: a cut or uncontained profile — a traced worker still running because an async
    # exception could not land in `time.sleep`/a C call — measured something other than this
    # suite against this code. Named here rather than folded into "Incomplete", because
    # "11/11 killed · Incomplete" with no reason reads as a gap to close and is not one.
    if not getattr(result, "measurement_gateable", True):
        # Name the ACTUAL reason. A shadowed collection (#58) finished cleanly and may have exact
        # counts — attributing it to a timeout sends the reader to raise a budget that was never
        # the problem.
        # CONSUME the normalized reasons (#60) rather than re-deriving them from raw fields.
        # Every reason is named, not just the first: a run cut for two causes that reports one
        # sends the reader to fix it, re-run, and meet the second with no way to know it was
        # always there. `cut_reason_sentence` is the single owner of the wording, so --json,
        # MCP and receipts render the identical vocabulary.
        _reasons = tuple(getattr(result, "cut_reasons", ()) or ())
        if _reasons:
            _why = "; ".join(cut_reason_sentence(r) for r in _reasons)
            return f"FINAL {result.function}: ⚠ UNGATEABLE — {_why}; counts are a floor, not a verdict"
        _conflicts = tuple(getattr(result, "collection_conflicts", ()) or ())
        if _conflicts:
            return (
                f"FINAL {result.function}: ⚠ UNGATEABLE — the live collection resolved "
                f"{', '.join(_conflicts)} to more than one file; the measurement is about an "
                "ambiguous copy of the code, so its counts specify nothing"
            )
        _depth = getattr(result, "coverage_depth", "") or "cut"
        return (
            f"FINAL {result.function}: ⚠ UNGATEABLE — the profile is {_depth} (a timed-out worker "
            "could not be contained, or the universe was not fully measured); counts are a floor, "
            "not a verdict"
        )
    # A proof basis that RAN and did not pass (issue #38) is not a certificate either — the
    # mutation score can be perfect while the written suite is red or uncollectable under real
    # pytest. Named before COMPLETE, like STALE/CUT, because it too disowns the verdict.
    _ver = getattr(result, "verification", None)
    if _ver is not None and not _ver.ok:
        return (
            f"FINAL {result.function}: ⚠ UNVERIFIED — proof basis {_ver.status} under pytest "
            f"({_ver.passed} passed / {_ver.failed} failed / {_ver.errors} error); certificate withheld"
        )
    total = result.total_mutants
    rep = result.survivor_report
    # #36: candidate-equivalent (no input distinguishes it) and crash-only (a crash input DOES) are
    # different residual classes; the banner must not fuse them into "N unproven-equivalent". Consume
    # the named partitions, never len(rep.equivalent) which is their union.
    cand = len(rep.candidate_equivalent) if rep is not None else 0
    crash_only = len(rep.crash_only) if rep is not None else 0
    killable = len(rep.killable) if rep is not None else 0
    unresolved = result.final_survivors if rep is None and not result.functionally_complete else 0
    gap = len(result.missing_lines)
    # "COMPLETE" is a claim about the OPERATOR UNIVERSE — every mutant the engine can
    # construct — never about all possible edits (a float threshold shifted by an
    # arbitrary amount is outside any finite family). The report body already carries
    # the qualifier ("every operator-universe mutant tested"); the banner is where
    # over-trust actually happens, so the banner says it too.
    if result.complete and cand == 0 and crash_only == 0:
        status = "✓ COMPLETE (operator universe)"
    elif result.complete:
        modulo = []
        if cand:
            modulo.append(f"{cand} unproven-equivalent")
        if crash_only:
            modulo.append(f"{crash_only} crash-only value gap{'s' if crash_only != 1 else ''}")
        status = f"✓ COMPLETE (operator universe · modulo {' · '.join(modulo)})"
    else:
        bits = []
        if killable:
            bits.append(f"{killable} killable")
        if unresolved:
            bits.append(f"{unresolved} unresolved")
        if gap:
            bits.append(f"{gap}-line gap")
        # "✗ INCOMPLETE" reads as FAILURE, and the common case it labels is not one: every
        # killable mutant pinned with a couple of lines left over is the tool working. The
        # ✗ made a good result look like a broken run. State the residual plainly instead —
        # what is missing is already named in `bits`.
        status = "Incomplete" + (f": {' · '.join(bits)}" if bits else "")
    # A method target's certificate is scoped to the RECEIVER population explored (issue #25): a
    # COMPLETE holds UNDER this receiver (a single `Basket()`, its class for a classmethod, or a
    # `--receiver-factory`), not for every possible instance state. Name it so the claim is honest.
    if result.complete and result.receiver_identity:
        status += f" · under receiver {result.receiver_identity}"
    # An environment capability (a `--clock` freeze) makes a function whose result depends on external
    # state pinnable — but its COMPLETE holds only UNDER that capability set, never unconditionally
    # (issue #24). Name it, the same honesty as the receiver scope above.
    if result.complete and getattr(result, "capability_identity", None):
        status += f" · under capability set {result.capability_identity}"
    # A COMPLETE whose LINE axis rested on the observed union is a weaker claim than one that
    # rested on admissible evidence (issue #59), and for the same reason the two lines above
    # exist: the certificate holds UNDER something, so it has to say what. The engine reports an
    # outcome-qualified view only from Wesker's #17 onward; below that a baseline-FAILING test's
    # coverage still closes the ledger, which is the defect #59 removes. `line_basis` recorded
    # that on the result and nothing rendered it — so on a released engine the weakening was
    # invisible, which is precisely the channel split #57 fixed for receipts. Naming it here is
    # also what keeps the dependency floor honest: a degradation the user can SEE does not need
    # a floor raise to strand them, per dev/DEPENDENCY_FLOORS.md.
    if result.complete and getattr(result, "line_basis", "admissible") == "observed":
        status += " · line axis unqualified (engine reports no admissible coverage)"
    # Next to the arrow, this slot READS as "wrote N tests → here", so it has to BE that.
    # `minimal_test_count` is a different quantity — the two-axis minimal cover over the WHOLE
    # suite, ours and the consumer's together — and printing it beside our own path credits us
    # with the consumer's tests. See `_written_count`.
    written = _written_count(result)
    if result.written_path:
        tests = f" · {written} test(s)" if written else ""
        arrow = f" → {_rel_path(result.written_path)}"
    else:
        # Nothing of OURS on disk this run — every generated property was redundant against
        # tests that already existed. The minimal cover is still the useful number, but it
        # cannot go in the bare slot: `· 10 test(s)` with no arrow reads as "wrote 10 tests,
        # location unknown", and sends the reader hunting for a file that was never written.
        # It is the same conflation the comment above guards for the with-path case.
        tests = f" · minimal cover {result.minimal_test_count} test(s)" if result.minimal_test_count else ""
        arrow = ""
    # Two routes reach the same number and they are NOT the same claim. Converging a suite
    # the user already had says their tests now pin the behaviour. Reaching it with no
    # pre-existing test says the behaviour is pinned to what the code does TODAY, by tests
    # nobody has read yet — a characterization baseline, not a review. The banner is the
    # line people grep and quote, so the distinction belongs on it, not only in the body.
    origin = (
        " · synthesized — no pre-existing test reached it"
        if getattr(result, "synthesized_only", False)
        else ""
    )
    return f"FINAL {result.function}: {status}{origin} · {result.killed}/{total} killed{tests}{arrow}"


def _written_count(result) -> int | None:
    """How many tests Detective actually WROTE — measured by running them, never inferred.

    `minimal_test_count` was standing in for this, and it answers a different question: the size
    of the two-axis minimal cover across the ENTIRE suite for this function, the consumer's
    hand-written tests included. Reported as "✓ wrote N test(s) → <our file>", it claims their
    tests as our product. Measured on TailChasingFixer: `wrote 3 test(s)` for a file containing
    exactly ONE test function — the 3 were the repo's own `is_valid_for` tests, which the minimal
    cover had (correctly) selected. It went unnoticed because the two numbers COINCIDE whenever
    the function had no tests before, which is every function the dogfood harness converges.

    `wiring.passed` is the count from actually running the written file under real pytest
    (`certify.verify_under_pytest`), so it counts what a user's own `pytest` will count —
    parametrized cases included, which a `def test_` grep would miss. It is set exactly when
    `written_path` is, so there is no case where we wrote a file and cannot say how much.
    """
    return result.wiring.passed if result.wiring is not None else None


def _format_converge(result, show_tests: bool = False, verbose: bool = True) -> str:
    """Validation report: what converge measured and what it left standing.

    ``verbose`` passes through to the survivor block: True (the default, and what the written
    report uses) renders every mutant id and diff; False groups them by mutated statement.

    The score line reports initial→final kill percentage (over the same fixed
    mutant set, since the function body is untouched) and the killed/total count.
    A non-empty ``remaining`` names the survivors converge could not kill without
    an oracle — the exact specification work a human or LLM must still supply.
    """
    total = result.total_mutants
    initial_killed = total - result.initial_survivors
    # Lead with the plain verdict a user actually wants — COMPLETE means both axes
    # hold (kills every killable mutant AND covers every line). "converged" is loop
    # state, not a completeness claim, so it no longer headlines.
    verdict = _completeness_verdict(result)
    lines = [
        f"{result.function}: {verdict}",
        f"  {result.initial_survivors} → {result.final_survivors} survivors; "
        f"score {_score(initial_killed, total)} → {_score(result.killed, total)} "
        f"({result.killed}/{total} killed)",
        f"  every-killable-killed={result.functionally_complete}  line-complete={result.line_complete}",
    ]
    # STATS FLEX: make "mutant-complete" concrete. universe_size is the count of
    # behavioral degrees of freedom (total possible mutants); killed/universe is the
    # fraction of that DOF space converge actually pinned down. Fast mode greedily
    # samples a (1−1/e)-optimal subset per category per pass, so its DOF fraction
    # exposes the speed/completeness trade honestly rather than hiding it.
    universe = result.universe_size or total
    if universe:
        if result.fast:
            from .converge import _FAST_MAX_PER_CATEGORY

            passes = len(result.iterations)
            mode = (
                f"fast — greedy ≤{_FAST_MAX_PER_CATEGORY}/category × "
                f"{passes} pass{'es' if passes != 1 else ''}"
            )
        else:
            mode = "comprehensive — full mutant universe"
        # STATS FLEX tail: the PROVEN greedy coverage floor (Wesker's
        # greedy_coverage_guarantee) — an a-priori lower bound the measured rate
        # meets or beats. Comprehensive tests every mutant the operators generate;
        # fast shows the (1−1/e)-per-pass guarantee, so the speed/certainty trade
        # is explicit. Both claims are RELATIVE TO THE OPERATOR UNIVERSE — a
        # semantic edit no operator expresses is outside them, and the tail must
        # not read as "no human edit can slip through" (one did: round ndigits,
        # before VALUE:int~off1 existed).
        if result.fast:
            tail = (
                f"greedy floor ≥ {result.coverage_guarantee:.0%} of coverable DOF (proven, (1−1/e) per pass)"
            )
        else:
            tail = "exhaustive — every operator-universe mutant tested"
        # SPECIFIED reads value_killed, not killed: a crash/timeout kill proves the code runs,
        # not what it computes (§0), so crediting it here would overstate the specification —
        # and disagree with `diagnose`, which counts value-pins. This number is therefore
        # allowed to sit below the "N killed" above it; they are different claims.
        # "complete" is a claim under a VERSIONED mutation policy (issues #8/#14),
        # and the report is where that scope belongs in human-readable form — the
        # id is what a receipt or a re-run months later is compared against. An
        # engine from before policy versioning prints nothing here (unversioned,
        # not unchanged).
        policy = f" · policy {result.policy_id}" if getattr(result, "policy_id", None) else ""
        lines.append(
            f"  DOF: {universe} behavioral degrees of freedom · {mode} · "
            f"{result.value_killed}/{universe} = {_score(result.value_killed, universe)} "
            f"of DOF specified · {tail}{policy}"
        )
    for i, it in enumerate(result.iterations):
        lines.append(f"  pass {i}: {it.survivors} survivors, {it.written} sound tests written")
    # Spec-completeness ETA in PASSES, not seconds (the SSL Semantic Completeness Equation):
    # converge's tests are the free structural resolution; killable residuals are the
    # I_solve external facts. When still contracting → "≈N more passes"; when the trajectory
    # has stalled → structure is exhausted and the residual needs supplied inputs.
    if not result.complete and universe:
        from .converge import passes_to_complete

        traj = tuple(it.survivors for it in result.iterations) + (result.final_survivors,)
        pr = passes_to_complete(traj)
        unresolved = (
            len(result.survivor_report.killable)
            if result.survivor_report is not None
            else result.final_survivors
        )
        # Also a specification claim (what deterministic synthesis pinned without a human), so
        # value_killed — a crash kill resolved nothing about the value.
        free = f"{_score(result.value_killed, universe)} resolved by structure for free"
        # A pass that wrote 0 new sound tests is the tail: structure is exhausted, so the
        # residual is I_solve (supplied inputs), NOT more passes — no matter how fast the
        # bulk contracted. Only extrapolate passes while the last pass still made progress.
        stalled = (not result.iterations) or result.iterations[-1].written == 0
        if not stalled and pr > 0:
            lines.append(
                f"  spec-completeness: {free} · ≈{pr} more pass{'es' if pr != 1 else ''} "
                "to complete (greedy bulk decay)"
            )
        elif unresolved > 0:
            # Stalled with real killable residuals: the I_solve external facts.
            lines.append(
                f"  spec-completeness: {free} · structure exhausted — {unresolved} unresolved "
                "residual(s) = I_solve (supply input/evidence below to finish)"
            )
        # else: complete-modulo-equivalent — the verdict + survivor lines already say so.
    if result.remaining:
        lines.append(f"  remaining: {', '.join(result.remaining)}")
    lines += _format_survivor_report(
        result.survivor_report,
        result.signature,
        result.param_names,
        verbose=verbose,
        structural_difficulty=result.structural_difficulty,
    )
    # Make the equivalent-mutant escape hatch discoverable: a new user should never have
    # to read --help to learn `flag`, nor loop forever chasing an unkillable mutant. Emit
    # the EXACT copy-pasteable command with the mutant id already filled in.
    _eq = result.survivor_report.equivalent if result.survivor_report is not None else ()
    if _eq:
        _ids = [v.mutant_id for v in _eq]
        lines.append(
            f"  ▶ if truly equivalent, accept it (stops the unkillable-mutant chase): "
            f"`detective flag '{result.function}' {_ids[0]} --note \"why-equivalent\"`"
            + (f"   (repeat for: {', '.join(_ids[1:])})" if len(_ids) > 1 else "")
        )
    # Second completeness axis + minimality (from the baseline line-coverage pass).
    # Reported only when there is line data (minimal_test_count > 0 or a measured gap).
    if result.missing_lines:
        gap = list(result.missing_lines)
        lines.append(f"  ✗ line gap: {len(result.missing_lines)} executable line(s) no test covers: {gap}")
        lines += _target_lines(result.signature)
        if _tmpl := _input_template(result.param_names):
            lines.append(f"      template: {_tmpl}   # replace every <...> slot to execute line(s) {gap}")
    elif result.minimal_test_count:
        lines.append("  ✓ line-complete — every executable line is covered by a test")
    if result.manually_unreachable:
        # Issue #9: closed by the human oracle, and SAID so — "modulo", never silently covered.
        lines.append(
            f"  · line ledger modulo {result.manually_unreachable} statement(s) manually "
            "classified unreachable (flag-line)"
        )
    for stale in result.contradicted_line_flags:
        lines.append(f"  ⚠ line flag OVERRIDDEN by execution: {stale} — the line was reached; flag ignored")
    # Issue #23: goldens refused because the invocation read default-path
    # files — the capture would have pinned the environment, not the function.
    for refusal in getattr(result, "environment_coupled", ()):
        lines.append(f"  ⚠ {refusal}")
    if result.minimal_test_count:
        lines.append(f"  minimal suite: {result.minimal_test_count} test(s) cover all kills + lines")
    if result.redundant_tests:
        lines.append(
            f"  PROPOSED removals ({len(result.redundant_tests)}, redundant for BOTH kills and "
            f"lines — confirm to delete, never auto): {', '.join(result.redundant_tests)}"
        )
    if result.written_path:
        lines.append(f"  wrote: {_rel_path(result.written_path)}")
    if result.wiring:
        lines.append(f"  {result.wiring.message}")
    if result.written_path:
        lines.append(
            "  ▶ to run these tests: `pytest`   (only the generated ones: `pytest -m detective`; "
            'only your own: `pytest -m "not detective"`)'
        )
    # The generated test source is dumped only into the FILE report (show_tests) — never
    # to the terminal by default, where it buried the verdict. The tests live on disk.
    if show_tests:
        lines += _show_written(result.written_path)
    # The stable banner is ALWAYS the last line, so `tail`/scroll lands on the result.
    lines.append(_final_banner(result))
    return "\n".join(lines)


def _write_converge_report(root: str, qualname: str, text: str, prefix: str = "converge") -> str:
    """Persist the FULL report to a readable file so the terminal can stay minimal.
    The complete detail — DOF, per-pass, every survivor, the generated test source — is
    one `cat` away. Returns a short path relative to root, or '' on failure (best-effort).

    ``prefix`` names the command that produced the text (``converge_f.txt``,
    ``decompose_f.txt``): a decompose that REFUSES used to leave no artifact at all,
    so the refusal could only be re-diagnosed by re-running it."""

    safe = qualname.replace("::", "__").replace("/", "_").replace(".", "_")
    d = os.path.join(root, ".detective", "reports")
    try:
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, f"{prefix}_{safe}.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    except OSError:
        return ""
    return os.path.relpath(path, root)


def _format_converge_terse(
    result,
    report_path: str,
    root: str = ".",
    session_reason: str = "",
    attempted_inputs: tuple[str, ...] = (),
) -> str:
    """The converge report: what got written, what is left, the ONE next action — then the
    greppable ``FINAL`` banner, which stays LAST.

    ``FINAL`` last is a downstream contract, not a layout choice: tooling tails this output to
    find the result, so the human action sits above it rather than after it. Everything
    verbose lives in the report file, which is always written regardless of `--full`.
    """
    fn = result.function
    rep = result.survivor_report
    # A stale headline must not carry counts either — "26 behaviours · 0
    # pinned" is the invalid measurement wearing the headline's authority.
    stale = getattr(result, "stale_target", False)
    counts = "" if stale else _headline_counts(result, rep)
    lines = [_RULE, f"{fn} — converge{counts}", ""]

    # A stale run's rows would describe an invalid measurement — survivor
    # counts and line gaps computed against a file that changed under the run
    # (issue #17). The staleness story is the WHOLE report: what happened, the
    # one action, the stamped banner. Anything more is advice from a reading
    # the instrument itself has disowned.
    if stale:
        lines.append(_row("⚠ stale", "the target file changed while the run was measuring it"))
        if report_path:
            lines.append(_row("· full report", f"{report_path} (measurement invalid)"))
        lines.append("")
        lines.append("DO THIS:  re-run the same converge on the now-stable file — nothing")
        lines.append("       below the edit was measured; this run's numbers describe a")
        lines.append("       function that no longer exists.")
        lines.append("")
        lines.append(_final_banner(result))
        return "\n".join(lines)

    # A CUT run (issue #31) is the same class of story as stale: the measurement is PARTIAL,
    # so counts would misrepresent a half-run universe. Name the phase the wall ran out in,
    # the integration signal if the target flooded, and the one action — re-run with more
    # budget — then the banner. Non-gateable: no COMPLETE can appear below this.
    if getattr(result, "budget_exhausted", False):
        phase = getattr(result, "cut_phase", "") or "a profiling phase"
        lines.append(_row("⚠ CUT", f"the aggregate deadline ran out during {phase}"))
        contained = getattr(result, "stdout_bytes", 0)
        if contained:
            lines.append(
                _row(
                    "· contained",
                    f"{contained:,} bytes the target printed to stdout — "
                    "integration/side-effecting; kept off this report",
                )
            )
        if report_path:
            lines.append(_row("· full report", f"{report_path} (measurement partial)"))
        lines.append("")
        lines.append("DO THIS:  re-run with a larger wall, e.g. --deadline 900 — or 0 to")
        lines.append("       disable it — on a target that genuinely needs longer. If the")
        lines.append("       target prints megabytes above, it is an integration function")
        lines.append("       that cannot be isolated in-process; that is the real finding.")
        lines.append("")
        lines.append(_final_banner(result))
        return "\n".join(lines)

    if result.written_path:
        # `_rel_path`, like the banner: converge stores ABSOLUTE paths, and a 90-character
        # /private/tmp/... string in a fixed-width column wraps and destroys the report.
        # The count of what WE wrote, not the minimal cover of everything covering this
        # function — see `_written_count`. This row names our file; the number beside it must
        # describe our file.
        written = _written_count(result)
        lines.append(
            _row(
                "✓ wrote",
                f"{written} test(s) → {_rel_path(result.written_path)}"
                if written is not None
                else _rel_path(result.written_path),
            )
        )
    if rep is not None and rep.killable:
        lines.append(_row("✗ still killable", f"{len(rep.killable)} — a witness exists for each"))
    if rep is not None and rep.unclassified:
        lines.append(_row("⚠ unclassified", f"{len(rep.unclassified)} — the search could not run on them"))
    if rep is None and not result.functionally_complete:
        lines.append(
            _row("✗ unresolved", f"{result.final_survivors} — classification produced no survivor report")
        )
    if result.missing_lines:
        gap = list(result.missing_lines)
        lines.append(_row("✗ uncovered", f"{len(gap)} line(s): {gap[:8]}"))
        # Name each uncovered line's OWN reach requirement (the branch it sits behind), so it is not
        # conflated with a mutant's kill input — the boundary mutant on `if x < 0` wants `x == 0`, but
        # the body is reached only when `x < 0`. Capped so the block stays inside its line budget.
        guards = result.missing_line_guards
        for ln, guard in guards[:3]:
            lines.append(_row("", f"line {ln} runs only when: {guard}"))
        # Disclose the cap, by this report's own rule — a bound that is not named reads as
        # "this is all of them". Three of seven printed silently, and the action block below
        # names every one, so the reader had no way to tell the row was a sample.
        if len(guards) > 3:
            lines.append(_row("", f"(+{len(guards) - 3} more — all named in the action below)"))
    if result.manually_unreachable:
        lines.append(
            _row("· line oracle", f"{result.manually_unreachable} statement(s) flagged unreachable (modulo)")
        )
    for stale in result.contradicted_line_flags:
        lines.append(_row("⚠ flag overridden", f"executed: {stale} — execution outranks the flag"))
    if rep is not None and rep.equivalent:
        # Two rows, not one (#36): "no input distinguishes them" is FALSE of a crash-only survivor —
        # an input does, by crash — and it was that false claim that sent a reader hunting for
        # the input. Each row states the one true thing about its own class, from the named
        # partitions the banner and verdict also consume (single source).
        if unproven := rep.candidate_equivalent:
            lines.append(_row("· unproven-equiv", f"{len(unproven)} — no input distinguishes them"))
        if crash_only := rep.crash_only:
            lines.append(
                _row("· crash-only-equiv", f"{len(crash_only)} — detected by crash; no value pins them")
            )
        # F2: the deep-structure caveat must reach the DEFAULT surface too, not only the verbose
        # report — this is the surface that invites a `flag`, and a `deep_structural` survivor above
        # may be killable-with-harder-input, not equivalent. The SAME decision the verbose path uses,
        # so the two cannot drift on when to caution.
        if deep_structure_caveat(
            getattr(result, "structural_difficulty", ""), bool(rep.candidate_equivalent)
        ):
            from .equivalence import structural_residual_handback

            _how = (
                "a nested/cross-referential --input"
                if structural_residual_handback(bool(rep.inputs_expressible)) == "structural_input"
                else "a hand-built object (no --input expresses it)"
            )
            lines.append(
                _row(
                    "⚠ deep-structure",
                    f"a survivor above may be KILLABLE, not equivalent — confirm over {_how} before "
                    "you `flag` (full report)",
                )
            )
    # The target printed to stdout while being measured, all contained off this channel
    # (issue #31). Named on EVERY run that produced output — not just cut ones — because a
    # function that traces/prints is side-effecting whether or not its return also pinned:
    # the row is the honest "this is an integration target" signal, sized so a 4KB debug
    # print reads differently from a multi-MB tracing flood.
    if contained := getattr(result, "stdout_bytes", 0):
        lines.append(
            _row(
                "· contained",
                f"{contained:,} bytes the target printed to stdout — "
                "integration/side-effecting; kept off this report",
            )
        )
    # Refused goldens are a residual the USER can act on (supply inputs or a
    # tmp fixture), so they earn a terse row like every other residual class;
    # the full report names each call and touched path (issue #23).
    if coupled := getattr(result, "environment_coupled", ()):
        lines.append(
            _row(
                "· env-coupled",
                f"{len(coupled)} golden(s) refused — environment-dependent (clock / process / "
                "default-path I/O / transitive write); see report for the exact reason per capture",
            )
        )
    # Static environment-read gating on a live line gap: a distinct residual class from the
    # golden-refusal row above — those lines cannot be reached by ANY --input, so they are a
    # fixture/manual hand-back, not an input to author.
    if (gated := getattr(result, "environment_gated", ())) and result.missing_lines:
        lines.append(
            _row("· env-gated", f"{len(gated)} read(s) gate uncovered line(s) — fixture/manual, not --input")
        )
    # Shape-hazardous tests held out of the speculative search (shaped-defer): a NAMED disclosure so a
    # residual is never silently attributed to the code when a deferred test might have killed it.
    if deferred := getattr(result, "deferred_shaped", 0):
        lines.append(
            _row(
                "· deferred-shaped",
                f"{deferred} isolation-hazardous test(s) held out of the widen search "
                "(subprocess/thread/signal/custom-collector) — a residual MAY be killable by one; "
                "re-run with --include-shaped to trace them",
            )
        )
    if report_path:
        lines.append(_row("· full report", report_path))
    lines.append("")
    lines += _converge_action(result, rep, root, report_path, session_reason, attempted_inputs)
    lines.append("")
    lines.append(_final_banner(result))
    return "\n".join(lines)


def deep_structure_caveat(structural_difficulty: str, has_candidate_equivalent: bool) -> bool:
    """Whether to warn that a CANDIDATE-EQUIVALENT survivor may be KILLABLE, not equivalent (F2 — pinned).

    A ``deep_structural`` target (it indexes into collection elements and drives a worklist/fixpoint
    loop) has distinguishing inputs the witness search does NOT synthesize, so a survivor it left
    ``candidate-equivalent`` may be killable with a hand-built structural input, not a genuine
    equivalent. The caution must reach EVERY surface that invites a ``flag`` — the terse default AND
    the verbose report — or the default invites the flag while the caution lives only in the verbose
    one (the F2 measurement/decision gap). So the decision is made ONCE here and both consume it.

    The gate is CANDIDATE-EQUIVALENT presence specifically, NOT any flag-eligible survivor. A
    crash-only survivor is a ``value_residual`` (a crash input DOES distinguish it), never a
    ``structural_residual``, so a result with only crash-only survivors must NOT receive the
    structural-input warning — passing the merged "candidate-equivalent OR crash-only" flag was the
    bug that let it. DERIVED from the canonical `residual_disposition` typing so the caveat and the
    typed residual cannot disagree: only a candidate-equivalent on a deep_structural target is a
    ``structural_residual``, which is exactly what this caveat names.
    """
    from .equivalence import residual_disposition

    return (
        has_candidate_equivalent
        and residual_disposition(False, False, structural_difficulty) == "structural_residual"
    )


def converge_next_action(
    standing: str,
    session_reason: str,
    has_killable: bool,
    has_line_gap: bool,
) -> str:
    """Converge's ONE next action, given whether the SUITE ITSELF ran (pure — pinned).

    The defect this exists to stop, reproduced in a directory with no pytest config:

        WARNING: pytest collected no tests — the live suite has nothing to run.
        ...
        DO THIS:  detective converge 'spine.py::spine' --input "(3,)" --input "(2,)" --input "(4,)"

    Running that advice literally produced byte-identical output — still ``0/11 killed``. The
    warning at the top had already NAMED the cause; the action block re-derived a narrower proxy
    (uncovered lines exist ⇒ ask for inputs) and sent the reader into a loop that cannot close.
    Adding a pytest config took the same target to ``✓ COMPLETE · 11/11``, and ``detective regime``
    already prints the correct remedy — so every part of the answer existed and none of it
    reached the decision.

    The signal was MEASURED and the decision did not CONSUME it: `_run_live` fills a
    `diagnostic` dict, writes the warning, and then falls back to `_run(args)` with the dict
    left behind as a local. Nothing downstream could see it, and `synthesized_only` is True in
    BOTH the healthy case (a real suite, no test reaches this function) and the broken one
    (no suite at all), so the renderer had no way to tell them apart.

    The certificate STANDING is consumed FIRST (`stale` / `ungateable` / `unverified`), so this
    renderer cannot drift from `ConvergeResult.complete` and the MCP surface the way it once did —
    a run whose target moved, or whose written suite did not verify, printed DONE because this path
    re-derived a narrower proxy that could not see either. The states, ordered by what outranks what:

    ``rerun_stale`` — the target changed while converge measured it. The counts describe a source
      that no longer exists, so they are meaningless, not small; no `--input` closes a moved gap.
    ``repair_measurement`` — the measurement is ungateable (cut / uncontained worker). Not a verdict.
    ``fix_verification`` — the generated suite did not run green under real pytest. A perfect score
      over a suite that does not run is not a certificate.
    ``settled`` — NOTHING OUTSTANDING, and this outranks every reason. `session_reason` describes
      the collection at the START of the run, and converge can finish a run that began with no
      collectable suite: it synthesizes tests, writes them, and re-profiles. Ranking the reason
      first would print "fix your regime" directly above a green certificate.
    ``install_pytest`` — pytest is not importable. Nothing runs; no input is relevant.
    ``fix_collection`` — pytest ran and collected nothing, errored, or crashed, AND a residual is
      still open. THE ORDER IS THE POINT: this outranks a line gap, because with no suite the gap
      is not closable by any argument the reader can supply. Ranking the gap first is the
      originally observed bug.
    ``close_the_gap`` — the suite runs and a real residual remains. Witnesses and `--input` are
      the documented interface, and here they actually work.

    `session_reason` is empty whenever the live suite DID run, so the healthy path is the
    default and an older Wesker that reports no reason degrades to exactly the previous
    behaviour rather than to a spurious refusal.
    """
    # `standing` is `certificate_standing`'s resolved code — one value, consumed not re-derived —
    # so these checks are order-independent and read the SAME bar as `complete` and the MCP surface.
    if standing == "stale":
        return "rerun_stale"
    if standing == "ungateable":
        return "repair_measurement"
    if standing == "unverified":
        return "fix_verification"
    if not (has_killable or has_line_gap):
        return "settled"
    if session_reason == "pytest_missing":
        return "install_pytest"
    if session_reason:
        return "fix_collection"
    return "close_the_gap"


def _dead_suite_action(kind: str, fn: str, root: str, session_reason: str) -> list[str]:
    """The action block for a suite that could not run. Names the remedy, not the symptom."""
    if kind == "install_pytest":
        return [
            "DO THIS:  install pytest in the interpreter that runs the suite, then re-run.",
            "",
            _row("· Why not --input", "no input can help: nothing can execute a test here."),
        ]
    where = f" --project-root '{root}'" if root and root != "." else ""
    named = {
        "empty_collection": "pytest collected NO tests, so nothing can run the pins.",
        "collection_errors": "pytest failed to collect, so the suite never started.",
        "pytest_crashed": "pytest raised during collection, so the suite never started.",
    }.get(session_reason, "the live suite did not run.")
    return [
        f"DO THIS:  detective regime --migrate '{fn}'{where}",
        "",
        _row("· Why not --input", named),
        _row("", "An --input closes a GAP; it cannot supply a suite. Following the"),
        _row("", "input ask here re-runs to the identical result."),
        _row("· Then", f"detective converge '{fn}'{where}   # the gap ask lands once tests collect"),
    ]


def _converge_action(
    result,
    rep,
    root: str = ".",
    report_path: str = "",
    session_reason: str = "",
    attempted_inputs: tuple[str, ...] = (),
) -> list[str]:
    """Converge's ONE next action — the DERIVED input, same as decompose's residual and from
    the same machinery (`_derived_input`). A witness is a call the engine RAN; a boundary hint
    is a relation it PROVED; only with neither is the reader asked for the value, which is the
    documented interface and not a fallback for work the tool skipped.

    `flag` comes LAST and only when nothing else is outstanding. It is the one claim a human
    makes against the engine, and offering it while a real gap is open invites someone to flag
    their way to a green board.

    `session_reason` defaults to empty — "the live suite ran" — so every existing caller and any
    older Wesker that reports no reason keeps exactly the previous behaviour.
    """
    fn = result.function
    # `functionally_complete` is the authoritative engine decision. A missing survivor report does
    # not turn residual survivors into DONE — that was the exact measurement/decision split this
    # function exists to prevent, and it produced "DONE" above `FINAL ... Incomplete` on a live run.
    blocked = (not result.functionally_complete) or bool(
        rep is not None and (rep.killable or rep.unclassified)
    )
    # A dead suite OUTRANKS the gap. See `converge_next_action`: the gap ask was reached by
    # re-deriving "uncovered lines exist" while the measured cause sat unread one layer up.
    # Read the certificate STANDING through `certificate_standing` — the same call `complete` and
    # the MCP renderer make — so this surface cannot keep printing DONE over a stale target or a
    # written suite that did not verify. getattr defaults keep a duck-typed / older result answering.
    from .converge import certificate_standing

    _ver = getattr(result, "verification", None)
    standing = certificate_standing(
        bool(result.functionally_complete),
        bool(getattr(result, "line_complete", not result.missing_lines)),
        bool(getattr(result, "stale_target", False)),
        _ver is not None,
        _ver is not None and bool(getattr(_ver, "ok", False)),
        bool(getattr(result, "admits_certificate", True)),
    )
    kind = converge_next_action(
        standing,
        session_reason,
        bool(blocked),
        bool(result.missing_lines),
    )
    if kind == "repair_measurement":
        flags = " ".join(_shell_input_flag(raw) for raw in attempted_inputs)
        if getattr(result, "collection_conflicts", ()):
            command = f"detective regime '{fn}'"
            why = "the live session resolved the target to conflicting module origins"
        elif getattr(result, "budget_exhausted", False):
            command = f"detective converge '{fn}' {flags} --deadline 0".replace("  ", " ")
            why = "the aggregate command deadline expired before proof completed"
        else:
            command = (
                f"detective converge '{fn}' {flags} --trace-budget 0 --trace-session-budget 0"
            ).replace("  ", " ")
            why = "the profile was cut before the mutant universe was measured"
        return [
            f"DO THIS:  {command}",
            "",
            _row("· Why first", why),
            _row("", "An invalid measurement cannot justify an input/test action."),
        ]
    if kind == "rerun_stale":
        return [
            "STOP:  the target changed while converge measured it — this is NOT a verdict.",
            "",
            _row("· Why first", "The kill-count and line numbers below describe a source that no"),
            _row("", "longer exists — meaningless, not small. Re-run on the settled file:"),
            _row("· Re-run", f"detective converge '{fn}'"),
        ]
    if kind == "fix_verification":
        _status = getattr(getattr(result, "verification", None), "status", "unverified")
        return [
            f"STOP:  the written suite did not verify under real pytest ({_status}) — NOT a certificate.",
            "",
            _row("· Why first", "A perfect mutation score over a suite that does not run green is"),
            _row("", "not a certificate. Fix the proof basis, then re-run:"),
            _row("· Re-run", f"detective converge '{fn}'"),
        ]
    if kind in ("install_pytest", "fix_collection"):
        return _dead_suite_action(kind, fn, root, session_reason)
    if blocked or result.missing_lines:
        action = _derived_input(
            None,
            result,
            rep,
            fn,
            verb=f"detective converge '{fn}'",
            report=report_path,
            attempted_inputs=attempted_inputs,
        )
        # An environment-gated line gap earns the honest decline FIRST: some uncovered lines sit
        # behind a read of the clock/filesystem/env, which no `--input` value reaches, so the ask
        # below is impossible for them. Saying so up front is the difference between a driver that
        # supplies a fixture and one that loops forever on inputs that never land.
        if result.missing_lines and getattr(result, "environment_gated", ()):
            return _environment_gated_caveat(result.environment_gated) + action
        return action
    # A synthesized suite has never been read by anyone. "Every behaviour pinned" is true of
    # it and is NOT "reviewed": with no pre-existing test, the pins record what the code does
    # TODAY — a bug included is a bug frozen, and the next `converge` will defend it. That is
    # a different next step from the converged-a-real-suite case, and it outranks the others,
    # so it goes last where the eye lands.
    review = (
        [
            "",
            "       NOTE: no pre-existing test reached this function, so the suite above is",
            "       entirely synthesized — a CHARACTERIZATION of current behaviour, not a",
            "       review of intended behaviour. Read the assertions before trusting them:",
            "       anything wrong today is now pinned wrong.",
        ]
        if getattr(result, "synthesized_only", False)
        else []
    )
    if rep is not None and rep.equivalent:
        ids = [v.mutant_id for v in rep.equivalent]
        more = f"  ({len(ids) - 1} more in the report)" if len(ids) > 1 else ""
        return [
            "DONE:  every killable behaviour is pinned. What remains cannot be distinguished",
            "       by any input Detective found — whether it is truly equivalent is UNDECIDABLE",
            "       in general, so the engine will not claim it. Leave them; they are not a gap.",
            f"       If you can prove one is: detective flag '{fn}' {ids[0]} --note \"why\"{more}",
            *review,
        ]
    return [
        "DONE:  the suite pins every behaviour this function makes.",
        f"       Next (optional): detective decompose '{fn}' --apply   # if it does too much",
        *review,
    ]


def _environment_gated_caveat(reads: tuple[str, ...]) -> list[str]:
    """The honest decline for an environment-gated line gap. Some uncovered lines sit behind a
    read the caller's ARGUMENT cannot set — the clock, the filesystem, the process env — so no
    `--input` value reaches them. Name the reads, point at the two ways in (a fixture or a
    hand-written test), and keep the `--input` ask that follows for any ARGUMENT-gated line.
    Without this, the tool asks for an input that provably cannot close the gap (the impure-line
    trap): `get_cached_model(model_id)` returns early unless `<id>/meta.json` exists, so its body
    is unreachable by any `model_id` string, yet the tool kept asking for one."""
    shown = "; ".join(reads[:3]) + (f" (+{len(reads) - 3} more)" if len(reads) > 3 else "")
    return [
        _row("⚠ environment-gated", "some uncovered lines sit behind external state, not arguments:"),
        _row("", f"  {shown}"),
        _row("", "  no --input value reaches a branch gated by the clock / filesystem / env."),
        _row("", "  supply a fixture (tmp file, monkeypatched clock) or write those lines by hand;"),
        _row("", "  the --input ask below still applies to any ARGUMENT-gated line."),
        "",
    ]


# One label column for the whole report, so every line hangs off the same gutter. Hand-counted
# padding drifts the moment any label changes length, and a report whose columns do not line up
# reads as unmaintained no matter how correct the words are.
_LABEL_W = 21

# The barrier between the live `▸` stream and the printed report. The stream is progress on a
# run that can take minutes; the report is the product. Without a rule they are one wall of
# text, and a reader cannot tell which lines they are meant to act on — the progress narration
# reads as findings. Rendered wide enough to survive a wrapped terminal.
_RULE = "─" * 78

# How many derived requirements one command carries. `--input` is repeatable and each call kills
# whatever it reaches, so the interface imposes no ceiling — this is only a wall-of-text guard.
# Set high on purpose: a reader who can close ten requirements in one command should not be made
# to run ten commands, and the repetition of the template IS the signal for how many calls to
# author. Whatever is left over is NAMED with a pointer to the report; a bound that is not
# disclosed reads as "this is all of them", which is how 65 requirements looked like 1.
_MAX_BATCH = 10


def _row(label: str, text: str) -> str:
    """`  label...  text` on the report's single gutter."""
    return f"  {label:<{_LABEL_W}}{text}"


def _helper_sig(ex) -> str:
    """`name(params) -> returns` — the extraction's interface on one line."""
    return f"{ex.helper_name}({', '.join(ex.params)}) -> {', '.join(ex.returns) or 'None'}"


def _helper_preview(ex, n: int = 3) -> list[str]:
    """The first `n` lines OF THE HELPER, found by name in the rewritten module.

    Not `new_source[:n]`. `new_source` is the whole rewritten FILE, so slicing its head
    printed whatever happens to sit at line 1 — for a module beginning `class Account:` the
    report named `_compute_rate` and then showed the class. It only ever looked right when
    the helper landed at the top, which is why it survived: the demo file always did.
    """
    src = ex.new_source.splitlines()
    start = next((i for i, ln in enumerate(src) if ln.startswith(f"def {ex.helper_name}(")), None)
    if start is None:  # spliced under a decorator/class, or renamed — show nothing, never a lie
        return []
    gutter = " " * (_LABEL_W + 2)
    return [f"{gutter}│ {ln}" for ln in src[start : start + n]] + [f"{gutter}│ …"]


def _headline_counts(proof, rep) -> str:
    """`· 139 behaviours · 11 pinned · 128 candidate-equivalent` — the scoreboard, or ''."""
    if proof is None:
        return ""
    parts = [f"{proof.total_mutants} behaviours", f"{proof.value_killed} pinned"]
    # #36: name the two residual classes, never the union labelled "candidate-equivalent" — a
    # crash-only mutant has a distinguishing input and is not an unproven equivalence.
    if rep is not None:
        if rep.candidate_equivalent:
            parts.append(f"{len(rep.candidate_equivalent)} candidate-equivalent")
        if rep.crash_only:
            parts.append(f"{len(rep.crash_only)} crash-only")
    return " · " + " · ".join(parts)


def _residual_action(r, proof, rep, target: str, root: str = ".") -> list[str]:
    """The next action when the proof is incomplete: the DERIVED input, never an invented one
    and never a slot for the reader to author.

    The engine already computes what the input must satisfy, and it is neither a guess nor a
    template:

    * a witness IS a real call — the equivalence search ran it and saw the mutant differ, so
      `assert f(args) == original` is a literal fact about this code. It is SUGGESTED, not
      applied, because `property_holds` could not verify it sound; that gap is the abstention,
      not an excuse to say less.
    * a BOUNDARY mutant's distinguishing input is the EQUALITY edge, and `_boundary_hint`
      derives it from the comparison whose operator shifted: "supply an input where qty == 0"
      is the valid relation WITH its precondition (oracle-LIGHT, not oracle-free).

    Printing `--input "(<account>, <charges>)"` and "fill the slots with ONE real call" throws
    all of that away and hands the reader the derivation the pipeline exists to do. It also is
    not pasteable — `<account>` is not Python — so the one line the report is judged on fails
    the only test that matters.
    """
    out: list[str] = []
    if rep is None:
        out.append(_row(f"{proof.final_survivors} unpinned", "the classification did not run, so which"))
        out.append(_row("", "mutants block is unknown. Source NOT touched."))
        out.append("")
        out.append(f"DO THIS:  detective converge '{target}' --full     # then re-run decompose")
        return out

    n_kill, n_unc, n_eq = len(rep.killable), len(rep.unclassified), len(rep.equivalent)
    unit = "behaviour(s)" if (n_kill + n_unc) != 1 else "behaviour"
    why = "a real input distinguishes them" if n_kill else "no input Detective built reaches them"
    out.append(_row(f"{n_kill + n_unc} {unit}", f"block the proof — {why}."))
    if n_eq:
        out.append(_row("", f"{n_eq} more look equivalent and do NOT block."))
    out.append(_row("", "Your source was NOT touched."))
    out.append("")
    out += _derived_input(r, proof, rep, target)
    return out


def _blocked_action(rep, target: str) -> list[str]:
    """The terminal when the proof suite is mutation-complete but the extraction could NOT be
    proven because candidate-equivalent / crash-only survivors remain (#decompose-banner).

    This is NOT a rejection — no trial ran against a sufficient suite, so the tool never
    observed a behaviour change. `apply_decomposition` withholds the proof suite while unproven
    survivors stand (a green trial would prove only the pinned behaviours), and `trial_verdict`
    returns ``unproven``. The honest next action is to resolve those survivors — `flag` the
    truly-equivalent, or supply the ``--input`` that kills a killable one — never a claim, from
    a run that tested nothing, that the rewrite changes behaviour. The distinction is the whole
    reason the banner reads the trial code instead of ``functionally_complete``.
    """
    n = len(rep.equivalent) if rep is not None else 0
    out = [
        "STOP.  Not a rejection — this rewrite was never tested. The proof suite kills every",
        "       KILLABLE mutant but keeps unproven survivor(s), so a green trial would prove",
        "       only the pinned behaviours. The extraction is proposed, not proven, and your",
        "       source was NOT touched.",
        "",
    ]
    if n:
        out.append(_row("· blocked by", f"{n} candidate-equivalent / crash-only survivor(s)"))
    out.append(_row("· to prove it", "flag the survivor(s) truly equivalent, or supply --input to"))
    out.append(_row("", f"kill them, then  detective decompose '{target}' --apply"))
    return out


def _hint_relation(hint: str) -> str:
    """The bare relation out of a boundary hint — "where amt == 0"."""
    tail = hint.split("—", 1)[-1].strip()
    # Lower-case: the caller opens the sentence ("That reaches the branch: where amt == 0.").
    return tail[len("supply an input ") :] if tail.startswith("supply an input ") else tail


def _witness_args(w) -> str:
    """A witness's args as a tuple literal. `(1)` is not a tuple, it is `1` — a one-argument
    call needs the trailing comma or the command does not parse as what it claims to be."""
    return ", ".join(repr(a) for a in w.args) + ("," if len(w.args) == 1 else "")


@dataclass(frozen=True)
class InputPlan:
    """One next-action decision, before any human or MCP surface renders it."""

    kind: str
    items: tuple[str, ...]
    item_total: int
    obligation_total: int


def _input_plan(kind: str, items: list[str], obligation_total: int) -> InputPlan:
    """Keep distinct inputs separate from the obligations those inputs discharge."""
    distinct = tuple(dict.fromkeys(items))
    return InputPlan(kind, distinct[:_MAX_BATCH], len(distinct), obligation_total)


def _witness_input(witness) -> str | None:
    """The exact ``--input`` payload iff Detective's own parser accepts it (#58)."""
    rendered = f"({_witness_args(witness)})"
    try:
        _parse_supplied_inputs([rendered])
    except SystemExit:
        return None
    return rendered


def _shell_input_flag(rendered: str) -> str:
    """Quote one parser-validated input without making ordinary literals noisy."""
    if not any(ch in rendered for ch in ('"', "$", "`", "\\", "\n")):
        return f'--input "{rendered}"'
    return f"--input {shlex.quote(rendered)}"


def _derive_input_plan(proof, rep, attempted_inputs: tuple[str, ...] = ()) -> InputPlan:
    """What the engine DERIVED about the inputs it still needs — as typed action data.

    Returns ``(kind, items, total)``:

    * ``("witness", ['(1,)', "(0, 'gold')"], n)`` — each item is a real call the engine RAN and
      saw a mutant differ on. Paste it. SUGGESTED, not applied: `property_holds` could not
      verify the test sound, and that gap is the abstention.
    * ``("boundary", ['where qty == 0'], n)`` — each item is a relation the engine PROVED: two
      orderings differ exactly at the equality edge, recovered from the comparison whose
      operator shifted. Author a call satisfying it.
    * ``("author", [], 0)`` — nothing derived. The caller supplies the value outright, which is
      the documented interface ("You supply what only you know"), not a fallback.

    ``item_total`` counts distinct calls/objects/requirements. ``obligation_total`` counts the
    mutants or lines they discharge.  They are deliberately separate: one domain object can kill
    31 mutants, and calling that "31 objects" sends the user looking for data that does not exist.

    DATA, not text, because the two surfaces render different commands: a human runs
    `--input "(...)"`, a tool caller passes `inputs=["(...)"]`. Sharing the rendered STRING put
    terminal syntax into an MCP response — telling a caller to use a flag that does not exist
    there. Sharing the derivation cannot do that, and it is the part that must never drift.
    """
    witnesses = [v for v in (rep.killable if rep is not None else ()) if v.witness]
    # The parser, not a parallel type predicate, decides whether a witness is a COMMAND. This
    # round-trip is the load-bearing invariant: anything printed after `DO THIS` has already been
    # accepted by the exact parser that will receive it.
    commandable = [(v, rendered) for v in witnesses if (rendered := _witness_input(v.witness))]
    # ...AND only if an `--input`-derived test can actually CLOSE it. A witness whose two OUTCOMES
    # differ only by exception type/message (or share a repr) cannot be pinned by `==` on a return
    # value, so re-running `--input` recalls the same pin and the number never moves — the exact
    # forever-loop the equivalent branch below already skips crash-only survivors to avoid, and the
    # action invariant of #44: an input is offered only for a population an input can resolve. Those
    # witnesses route to `hand_pin` (write the exception/exact-value assertion by hand) instead of a
    # command that loops. Value witnesses are unaffected — `_outcome_needs_hand_pin` is False for two
    # plainly different return values, where `==` is exactly what separates them.
    input_closes = [
        (v, rendered)
        for v, rendered in commandable
        if not _outcome_needs_hand_pin(v.witness.original, v.witness.mutant)
    ]
    attempted = set(attempted_inputs)
    fresh_inputs = [(v, rendered) for v, rendered in input_closes if rendered not in attempted]
    if fresh_inputs:
        return _input_plan("witness", [rendered for _, rendered in fresh_inputs], len(fresh_inputs))
    # The exact input was accepted, executed, and returned as the same residual. Offering it again
    # is a proven loop, not guidance. Route to the existing terminating hand-pin action.
    repeated_inputs = [(v, rendered) for v, rendered in input_closes if rendered in attempted]
    if repeated_inputs:
        items = [
            f"{rendered} — supplied already; real {v.witness.original[:28]} vs mutant {v.witness.mutant[:28]}"
            for v, rendered in repeated_inputs
        ]
        return _input_plan("repeated", items, len(repeated_inputs))
    hand_pin = [v for v, _ in commandable if _outcome_needs_hand_pin(v.witness.original, v.witness.mutant)]
    if hand_pin:
        items = [
            f"({_witness_args(v.witness)}) — real {v.witness.original[:28]} vs mutant {v.witness.mutant[:28]}"
            for v in hand_pin
        ]
        return _input_plan("hand_pin", items, len(hand_pin))
    if witnesses:
        descs: list[str] = []
        for v in witnesses:
            d = ", ".join(f"a {type(a).__name__}: {repr(a)[:70]}" for a in v.witness.args)
            if d not in descs:
                descs.append(d)
        return _input_plan("test", descs, len(witnesses))
    hints: list[str] = []
    internal: list[str] = []
    # Skip crash-only survivors: an input already distinguishes them and no value assertion can
    # pin them, so any input we ask for here is one the caller can supply and still see NO
    # progress — the same forever-loop `find_witness` skips them to avoid.
    for v in (v for v in (rep.equivalent if rep is not None else ()) if not v.crash_only):
        h = _boundary_hint(
            v.diff_summary,
            tuple(proof.param_names) if proof.param_names is not None else None,
        )
        if not h:
            continue
        if _is_internal_hint(h):
            if h not in internal:
                internal.append(h)
        elif (rel := _hint_relation(h)) not in hints:
            hints.append(rel)
    # A DARK LINE OUTRANKS AN EQUIVALENT'S EDGE. `hints`/`internal` are read off
    # CANDIDATE-EQUIVALENT survivors — by construction nothing killable is left, so the only
    # progress still available is executing a line no test reaches. Asking for the edge first
    # asks for the wrong thing and cannot move the number: the reader supplies `billable == 1`,
    # every killable mutant is already dead, and the run returns byte-identical with the same
    # request. `missing_line_guards` is already computed for exactly this (converge.py) and was
    # reaching only the informational row; a mutant on a line that never runs can never die, so
    # coverage is a PRECONDITION for the kill axis, not a parallel one.
    if gaps := _line_gap_items(proof):
        return _input_plan("lines", gaps, len(gaps))
    if hints:
        return _input_plan("boundary", hints, len(hints))
    if internal:
        # Issue #8: the region exists but reads a derived local — no direct input
        # constraint is derivable, and saying so IS the result (certified abstention).
        return _input_plan("internal", internal, len(internal))
    return _input_plan("author", [], 0)


def _derive_inputs(proof, rep) -> tuple[str, list[str], int]:
    """Backward-compatible data adapter; new renderers consume :class:`InputPlan` directly."""
    plan = _derive_input_plan(proof, rep)
    return plan.kind, list(plan.items), plan.obligation_total


def _line_gap_items(proof) -> list[str]:
    """Uncovered lines as REACH requirements — "line 30: service == 'overnight' and zone >= 5".

    Guards are per-line and may be absent (an unconditional line sits behind no branch); such a
    line is still named, because "line 47" with no condition is actionable and silence is not.
    Only the converge surface carries these fields, so a decompose `proof` yields nothing here
    and the derivation is unchanged for it.
    """
    guards = dict(getattr(proof, "missing_line_guards", ()) or ())
    return [
        f"line {ln} — reached only when: {guards[ln]}" if ln in guards else f"line {ln} — reach it"
        for ln in (getattr(proof, "missing_lines", ()) or ())
    ]


def _outcome_needs_hand_pin(original: str, mutant: str) -> bool:
    """Whether a witness's two outcomes are beyond an ``==`` on the return value.

    True when either side is an exception (``<raised …>`` — the engine's own encoding, see
    ``equivalence``) or the reprs are identical. False for two plainly different values, where
    ``==`` is exactly the thing that separates them and advice to pin a repr is a non-sequitur
    printed under evidence that contradicts it.
    """
    return original.startswith("<raised") or mutant.startswith("<raised") or original == mutant


def _derived_input(
    r,
    proof,
    rep,
    target: str,
    verb: str = "",
    report: str = "",
    attempted_inputs: tuple[str, ...] = (),
) -> list[str]:
    """The CLI's `DO THIS:` block — `derive_inputs`' data rendered as terminal syntax.

    A thin renderer on purpose. The DERIVATION is shared with the MCP (`derive_inputs`); the
    COMMAND is not, because a human runs `--input "(...)"` and a tool caller passes
    `inputs=["(...)"]`. Sharing the rendered string put terminal syntax into an MCP response.

    Batched: `--input` is repeatable and each call kills what it reaches, so N requirements
    close in ONE command. The COUNT is a sentence, not argv — that was the earlier design and it
    cost the line without buying anything: an unfilled template repeated N times is the same
    string N times (and the reader edits each anyway), and an identical witness repeated N times
    kills exactly what one kills. Ten of either rendered ~600 characters of command, which is not
    a thing anyone pastes. DISTINCT witnesses still all appear; only duplicates collapse, and what
    they cover is stated. The remainder is always named — a bound that is not disclosed reads as
    "this is all of them".
    """
    cmd = verb or f"detective decompose '{target}' --apply"
    sig = proof.signature or ""
    tmpl = _input_template(proof.param_names)
    plan = _derive_input_plan(proof, rep, attempted_inputs)
    kind = plan.kind
    items = list(plan.items)
    where = report or "the full report"

    if kind == "witness":
        # DISTINCT calls. `--input` is a set in effect — passing the same tuple five times kills
        # exactly what passing it once kills — so the repetition bought nothing and cost the one
        # thing this line is for: at 10 shared witnesses it rendered a ~600-character command,
        # which is not a thing anyone pastes. The mutant count is what the repetition was
        # actually carrying, so it is stated as a count instead of spelled out in argv.
        distinct = items
        flags = " ".join(_shell_input_flag(a) for a in distinct)
        out = [f"DO THIS:  {cmd} {flags}"]
        out.append("")
        out.append(_row("· Why these", f"Detective RAN each: the {len(distinct)} call(s) above each"))
        out.append(_row("", "make a mutant differ from your real function."))
        if plan.obligation_total != plan.item_total:
            out.append(
                _row(
                    "",
                    f"({plan.item_total} distinct call(s) cover "
                    f"{plan.obligation_total} mutant obligation(s))",
                )
            )
        # The reason is data the engine already holds — show ONE observed pair inside the
        # same two budgeted lines, so a dead-end reads as a diagnosis, not a loop.
        # A representative VALUE pair. Witnesses whose outcome needs hand-pinning are routed to the
        # `hand_pin` kind below, so the pair shown here is always one an `--input` actually closes —
        # the old code fished the FIRST killable witness, which could be an exception pair, and then
        # printed "pin by hand" under a `--input` headline that contradicted it.
        pair = (
            next(
                (
                    v.witness
                    for v in rep.killable
                    if v.witness
                    and _witness_input(v.witness) is not None
                    and not _outcome_needs_hand_pin(v.witness.original, v.witness.mutant)
                ),
                None,
            )
            if rep is not None
            else None
        )
        if pair is not None:
            seen = f"{pair.original[:20]} vs {pair.mutant[:20]}"
            out.append(_row("", f"SUGGESTED — not written: unsound ({seen} observed)."))
        else:
            out.append(_row("", "SUGGESTED — not written for you, because the engine"))
            out.append(_row("", "could not verify the tests sound."))
        if plan.item_total > len(items):
            out.append(_row("", f"({plan.item_total - len(items)} more distinct calls in {where})"))
        return out

    if kind == "hand_pin":
        # #44 action invariant, the crash-only sibling of the witness branch: an `--input` can NOT
        # close these — the two outcomes differ only by exception type/message (or share a repr), so
        # no `==` on a return value separates them. Re-running `--input` recalls the same pin and the
        # number never moves. The next action that TERMINATES is to hand-write the assertion, so the
        # headline is that — never a `--input` command that loops.
        out = ["WRITE TEST:  hand-write a test pinning the exact outcome below (no --input closes these)"]
        out.append("")
        out.append(_row("· Why", f"Detective RAN each: the {len(items)} call(s) differ from your"))
        out.append(_row("", "function only by exception type/message (or identical"))
        out.append(_row("", "reprs) — no == on a return value separates them, so an"))
        out.append(_row("", "--input cannot close them and re-running it loops."))
        out.append(_row("· Pin by hand", f"1. {items[0]}"))
        for i, d in enumerate(items[1:], start=2):
            out.append(_row("", f"{i}. {d}"))
        out.append(_row("", "e.g. assert the exception via pytest.raises(<Type>)."))
        if plan.item_total > len(items):
            out.append(_row("", f"({plan.item_total - len(items)} more distinct calls in {where})"))
        out.append("")
        out.append(f"THEN RUN:  {cmd}")
        return out

    if kind == "repeated":
        out = ["WRITE TEST:  pin the observed distinction below; the supplied --input did not close it"]
        out.append("")
        out.append(_row("· Why", "Detective accepted and ran this exact input, then returned"))
        out.append(_row("", "the same residual. Repeating the command is a proven loop."))
        out.append(_row("· Observed", f"1. {items[0]}"))
        for i, d in enumerate(items[1:], start=2):
            out.append(_row("", f"{i}. {d}"))
        if plan.item_total > len(items):
            out.append(_row("", f"({plan.item_total - len(items)} more distinct calls in {where})"))
        out.append("")
        out.append(f"THEN RUN:  {cmd}")
        return out

    if kind == "test":
        out = ["WRITE TEST:  call the target with the object/call below"]
        out.append("")
        out.append(_row("· Why", "Detective RAN each — a mutant differs on it — but none"))
        out.append(_row("", "can be typed as --input: they are objects only a test builds."))
        out.append(
            _row(
                "· Coverage",
                f"{plan.item_total} distinct object/call(s) cover "
                f"{plan.obligation_total} mutant obligation(s)",
            )
        )
        out.append(_row("· Object/call(s)", f"1. {items[0]}"))
        for i, d in enumerate(items[1:], start=2):
            out.append(_row("", f"{i}. {d}"))
        if plan.item_total > len(items):
            out.append(_row("", f"({plan.item_total - len(items)} more distinct calls in {where})"))
        out.append("")
        out.append(f"THEN RUN:  {cmd}")
        return out

    if kind == "lines":
        # ONE slot, not N identical ones. Every copy is the same unfilled template, so repeating
        # it says nothing the Task line does not, and at seven uncovered lines it produced a
        # command that was 90% the same string. How many to author is a sentence; it is not argv.
        out = ["AUTHOR INPUTS:  write the calls that reach the uncovered lines below"]
        out.append("")
        out.append(_row("· Signature", sig))
        if tmpl:
            out.append(_row("· Template", f"{tmpl}  (replace every <...> slot before running)"))
        out.append("")
        out.append(_row("· Task", f"Author {len(items)} call(s) — one per line below — each as"))
        out.append(_row("", "its own --input. Detective derives every test from them."))
        out.append(_row("· Why", "Every killable mutant is already dead. What is left is"))
        out.append(_row("", "lines no test executes; a mutant on a line that never"))
        out.append(_row("", "runs cannot be killed, so reach these first."))
        out.append(_row("· Uncovered", f"1. {items[0]}"))
        for i, gap in enumerate(items[1:], start=2):
            out.append(_row("", f"{i}. {gap}"))
        if plan.item_total > len(items):
            out.append(_row("", f"(+{plan.item_total - len(items)} more in {where})"))
        out.append("")
        out.append(f"THEN RUN:  {cmd}")
        return out

    if kind == "boundary":
        # One slot — see the `lines` branch above; the count is in the Task line.
        out = ["AUTHOR INPUTS:  write the boundary calls described below"]
        out.append("")
        out.append(_row("· Signature", sig))
        if tmpl:
            out.append(_row("· Template", f"{tmpl}  (replace every <...> slot before running)"))
        out.append("")
        out.append(_row("· Task", f"Author {len(items)} call(s), one per requirement, each as"))
        out.append(_row("", "its own --input. Detective derives every test from them."))
        out.append(_row("· Requirements", f"1. {items[0]}"))
        for i, rel in enumerate(items[1:], start=2):
            out.append(_row("", f"{i}. {rel}"))
        if plan.item_total > len(items):
            out.append(_row("", f"(+{plan.item_total - len(items)} more in {where})"))
        out.append(_row("", "Derived from your code: two orderings differ exactly"))
        out.append(_row("", "at the equality edge."))
        out.append("")
        out.append(f"THEN RUN:  {cmd}")
        return out

    if kind == "internal":
        out = ["AUTHOR INPUTS:  write a call that drives the internal condition below"]
        out.append("")
        out.append(_row("· Signature", sig))
        if tmpl:
            out.append(_row("· Template", f"{tmpl}  (replace every <...> slot before running)"))
        out.append("")
        out.append(_row("· Status", "The surviving distinction sits behind an INTERNAL"))
        out.append(_row("", "condition — a derived local, not a parameter — so no"))
        out.append(_row("", "direct input constraint is derivable. That is a finding,"))
        out.append(_row("", "not a gap in your report:"))
        out.append(_row("· Condition(s)", f"1. {items[0]}"))
        for i, cond in enumerate(items[1:], start=2):
            out.append(_row("", f"{i}. {cond}"))
        if plan.item_total > len(items):
            out.append(_row("", f"(+{plan.item_total - len(items)} more in {where})"))
        out.append(_row("· Task", "Author one real call whose execution drives the"))
        out.append(_row("", "condition(s) above, and pass it as --input."))
        out.append("")
        out.append(f"THEN RUN:  {cmd}")
        return out

    return [
        "AUTHOR INPUTS:  write one real call for the target below",
        "",
        _row("· Signature", sig),
        _row("· Template", f"{tmpl}  (replace every <...> slot before running)" if tmpl else "(none)"),
        "",
        _row("· Task", "Author one real call and pass it as --input."),
        _row("· Requirement", "It must run. Detective derives every test from it."),
        _row("", "Values are yours to choose — it will not invent one whose"),
        _row("", "meaning is not in the code. A class from the module goes"),
        _row("", "in as its constructor. Repeatable for another branch."),
        "",
        f"THEN RUN:  {cmd}",
    ]


def _aim_at(rep) -> str:
    """Name the LINE a blocking mutant sits on, so "add a test" is aimed.

    Without it the instruction is identical every round and the reader is guessing which
    branch to reach — the number moves, so they are converging, but by luck. The engine
    already holds the answer: a killable verdict carries the mutation, and `_concise_diff`
    reduces it to the changed line. Telling someone to write a test without saying what it
    must reach is the difference between an instruction and a chore.
    """
    target = next(iter(rep.killable), None) if rep is not None else None
    if target is None:
        return ""
    changed = _concise_diff(target.diff_summary).strip().splitlines()
    return changed[0].strip() if changed else ""


def _format_decompose(r, applied_mode: bool, target: str | None = None, root: str = ".") -> str:
    """The decompose report: what happened, and the ONE next action, in a fixed shape.

    Two rules hold this together.

    ONE ACTION, AND IT MUST RUN. Every terminal state ends in exactly one `DO THIS:` /
    `DONE:` / `STOP.` line, and the command on it is one the tool will accept. That is not a
    style preference — `--input` parses an allowlist (literals + `ast.*`), so for a function
    taking a domain object NO string satisfies `--input "(<account>, ...)"`, and printing it
    hands the reader a command that always errors. `inputs_expressible` (equivalence.py) is
    the engine's answer to "can a human type this?", computed from the input that actually
    exercised the function, and it decides which action is printed. The reader should never
    have to know that; they should be able to paste the line.

    SAY WHAT HAPPENED, NOT WHAT WAS COMPUTED. The counts name the three populations by their
    CONSEQUENCE (blocks / does not block), because a single fused total is what made this
    report unreadable: it counted 22 blockers where 5 blocked and asked for an input for all
    of them.
    """
    # `r.function` is the BARE name ("settle"), unlike SuiteAudit.function which is the full
    # key. Every command this renderer printed used it, so every one was unrunnable:
    # `detective decompose 'settle' --apply` -> "target must be 'file.py::function'". It went
    # unnoticed for the whole build because it was only ever tested by someone typing the full
    # target from memory — the reader this report exists for cannot do that.
    tgt = target or r.function
    lines: list[str] = []
    # A CUT decompose (issue #31) never got a completed proof, so it can neither apply nor
    # honestly say "no seam". Name the cut, the integration signal if the target flooded, and
    # the action — this is the original wrap_trace regression's user-visible landing.
    if getattr(r, "budget_exhausted", False):
        phase = getattr(r, "cut_phase", "") or "the proof converge"
        out = [
            _RULE,
            f"{r.function} — decompose",
            "",
            _row("⚠ CUT", f"the aggregate deadline ran out during {phase} — nothing proven, nothing applied"),
        ]
        contained = getattr(r, "stdout_bytes", 0)
        if contained:
            out.append(
                _row(
                    "· contained",
                    f"{contained:,} bytes the target printed to stdout — "
                    "an integration/tracing function that cannot be isolated in-process",
                )
            )
        out += [
            "",
            "DO THIS:  re-run with a larger wall, e.g. --deadline 900 (or 0 to disable). If",
            "       the target floods stdout above, that IS the finding — it is not a pure",
            "       function a suite can pin; decompose safely declined to rewrite it.",
        ]
        return "\n".join(out)
    if not r.applied and not r.proposed and not r.unsafe_blocks:
        return f"{r.function} — decompose\n\nDONE:  no separable block. There is no seam here to split."

    proof = r.proof
    rep = proof.survivor_report if proof is not None else None
    lines.append(_RULE)
    lines.append(f"{r.function} — decompose{_headline_counts(proof, rep)}")
    lines.append("")

    for ex in r.applied:
        lines.append(_row("✓ APPLIED", _helper_sig(ex)))
        lines += _helper_preview(ex)
    for dec in r.proposed:
        lines.append(_row("✓ proven" if dec.validated else "✗ can't prove yet", _helper_sig(dec.extraction)))
        lines += _helper_preview(dec.extraction)
    for block in r.unsafe_blocks:
        lines.append(_row("✗ not extractable", block))
    lines.append("")

    if r.applied:
        lines.append("DONE:  your source is rewritten. The suite ran green before AND after, and")
        lines.append("       unspecified behaviour was not baked in.")
        # NAME the helpers. "converge 'quote' on the new helper(s)" is not a command — it is a
        # command with the operand described instead of supplied, and the operand is the only
        # part the reader does not already have. The extraction is right there.
        file_part = tgt.rsplit("::", 1)[0] if "::" in tgt else ""
        for ex in r.applied:
            target = f"{file_part}::{ex.helper_name}" if file_part else ex.helper_name
            lines.append(f"       Next (optional):  detective converge '{target}'")
        return "\n".join(lines)

    validated = [d for d in r.proposed if d.validated]
    if validated and not applied_mode:
        lines.append(f"DO THIS:  detective decompose '{tgt}' --apply")
        lines.append("          The proof already passed. --apply writes it. Nothing else is needed.")
        return "\n".join(lines)

    if proof is None:
        lines.append(f"DO THIS:  detective converge '{tgt}'")
        lines.append("          No suite specifies this function yet, so there is nothing to prove")
        lines.append("          against. Your source was NOT touched.")
        return "\n".join(lines)

    # The last three verdicts are the ones that were conflated. Read the trial outcome the
    # engine computed (`Decomposition.trial`), never re-derive "rejected" from
    # `functionally_complete`: a mutation-complete suite that still retains candidate-equivalent
    # survivors withheld its proof suite, so the trial was `unproven` (blocked), NOT `rejected`
    # (#decompose-banner). The pure decision is pinned; here we only dispatch on it.
    from .decompose import decompose_terminal

    code = decompose_terminal(
        any_applied=bool(r.applied),
        has_validated=bool(validated),
        applied_mode=applied_mode,
        proof_present=proof is not None,
        proof_complete=proof is not None and proof.functionally_complete,
        any_rejected=any(d.trial == "rejected" for d in r.proposed),
    )
    if code == "rejected":
        # A trial ran against a SUFFICIENT (mutation-complete, unblocked) suite and went red:
        # the rewrite genuinely changes behaviour. There is no input to supply and nothing to
        # retry; offering one sends the reader to close a hole that does not exist.
        lines.append("STOP.  This is a verdict, not a gap. The suite is mutation-complete and it")
        lines.append("       proves this extraction changes behaviour. Your source was NOT touched.")
        return "\n".join(lines)
    if code == "blocked":
        # Mutation-complete-modulo-equivalent: the rewrite was never tested, so this is NOT a
        # disproof. Name the real blocker instead of accusing a change the tool never observed.
        lines += _blocked_action(rep, tgt)
        return "\n".join(lines)

    lines += _residual_action(r, proof, rep, tgt, root)
    return "\n".join(lines)


def _first_n(items, n: int) -> str:
    """``a, b, c`` — and ``a, b, c … (+4 more)`` when the list was cut.

    A list that stops at N with no marker reads as the WHOLE list, and the reader then acts
    on a count the report never showed them: the redundant line said "7 test(s)" and named
    four, so three of the deletions being proposed were invisible. Converge already says
    "(N more in the report)" about its survivors; this is that courtesy everywhere else.
    """
    seq = list(items)
    shown = seq[:n]
    extra = len(seq) - len(shown)
    return ", ".join(str(s) for s in shown) + (f" … (+{extra} more)" if extra else "")


def _format_audit_plan(function: str, static_detail: str, tier1, est_s: float | None) -> str:
    """`audit --plan` — the mutation-budget decision WITHOUT paying for it (issue #52): tier 0 static,
    tier 1 fan-in + coverage, a measured tier-2 estimate, no verdict. A schedule, not a finding."""
    est = (
        f"~{est_s:.0f}s to mutate {tier1.mutant_count} mutant(s) (this machine's recent rate)"
        if est_s is not None
        else f"{tier1.mutant_count} mutant(s) — no prior rate yet to estimate from (first run here)"
    )
    return "\n".join(
        [
            _RULE,
            f"{function} — audit --plan · a schedule, not a finding (no mutation run)",
            "",
            _row("· tier 0 static", static_detail or "no static smell — proves nothing (advisory)"),
            _row(
                "· tier 1 traced",
                f"{tier1.tests_reaching} of {tier1.tests_total} test(s) reach it · "
                f"{tier1.covered_lines}/{tier1.executable_lines} line(s) covered",
            ),
            _row("· tier 2 est", est),
            "",
            _row("· then", f"detective audit '{function}'   # pay tier 2 for the specification verdict"),
        ]
    )


def audit_headline_verdict(
    complete: bool,
    complete_modulo_equivalent: bool,
    candidate_equivalent: int,
    crash_only_equivalent: int,
    total_mutants: int = 1,
) -> str:
    """Which verdict shape the audit headline may claim (#36, pure — pinned).

    CANDIDATE-EQUIVALENT AND CRASH-ONLY ARE DIFFERENT RESIDUALS and the headline fused them.
    Measured on a target whose survivors were ALL crash-only, in one session:

        converge: ✓ COMPLETE (operator universe · modulo 3 crash-only value gaps)
        audit:    complete, modulo 3 unproven-equivalent
                  · crash-only-equiv   3 survivor(s) — detected by crash; no value pins them

    Zero were unproven-equivalent, and the headline contradicted the itemised body two lines
    below it. converge's banner had already been taught the distinction; audit's had not, so the
    same tool said two different things about one measurement depending on which command you ran.

    The counts are NOT two populations: `crash_only_equivalent` is a SUB-COUNT of
    `candidate_equivalent` (audit.py), so the truly-unproven residual is their difference. That
    arithmetic is the entire reason this is worth extracting — it is easy to state wrongly, and
    stating it wrongly is invisible whenever the two happen to be equal.

    Codes, not a rendered string, so the wording stays in the renderer and the DECISION is what
    gets pinned: ``incomplete``, ``complete``, ``complete_modulo_unproven``,
    ``complete_modulo_crash_only``, ``complete_modulo_both``.

    ``inconsistent`` names the state where crash-only exceeds its own parent count. That cannot
    happen while the sub-count invariant holds — which is exactly why it is worth a name rather
    than an unchecked subtraction: if the invariant ever breaks, the alternative is a headline
    reading "modulo -2 unproven-equivalent", which no reader can act on.
    """
    if not (complete or complete_modulo_equivalent):
        return "incomplete"
    # AN EMPTY UNIVERSE CERTIFIES NOTHING (W#13). With no mutants, `mutant_complete` is
    # vacuously true and `kill_pct` is an explicit `else 100.0`, so a function with no mutable
    # behaviour read `0/0 value-pinned · 100.0% killed · complete` — the strongest headline the
    # tool emits, over a measurement that never happened. converge is honest about the same
    # target ("0 behaviours · 0 pinned", certificate withheld); audit was not.
    #
    # Ranked BELOW `incomplete` on purpose: a zero-mutant function can still have an uncovered
    # line, and that is a real gap on a different axis which must keep its own name.
    if total_mutants <= 0:
        return "nothing_measured"
    unproven = candidate_equivalent - crash_only_equivalent
    if unproven < 0:
        return "inconsistent"
    if unproven and crash_only_equivalent:
        return "complete_modulo_both"
    if unproven:
        return "complete_modulo_unproven"
    if crash_only_equivalent:
        return "complete_modulo_crash_only"
    return "complete"


def _format_audit(a, removing: bool = False) -> str:
    """Read-only audit of an existing suite, in the report shape: what is true, then the ONE
    next action, and audit itself never writes.

    Three tiers, not two: a suite that kills every killable mutant and covers every line but
    leaves UNPROVEN candidate-equivalents has no real gaps and is not "incomplete" — calling
    it that sends someone to write tests for behaviour that is already pinned.

    The action names a REAL mutant id. It used to read ``flag <mutant_id>`` — a placeholder,
    with the ids sitting one field away in the classifier — so the one command the report
    offered could not be pasted, and the reader had to go hunting to do what it asked.
    """
    _crash_only = getattr(a, "crash_only_equivalent", 0)
    _unproven = a.candidate_equivalent - _crash_only
    _shape = audit_headline_verdict(
        a.complete,
        a.complete_modulo_equivalent,
        a.candidate_equivalent,
        _crash_only,
        a.total_mutants,
    )
    if _shape == "complete_modulo_both":
        verdict = (
            f"complete, modulo {_unproven} unproven-equivalent "
            f"and {_crash_only} crash-only value gap{'s' if _crash_only != 1 else ''}"
        )
    elif _shape == "complete_modulo_unproven":
        verdict = f"complete, modulo {_unproven} unproven-equivalent"
    elif _shape == "complete_modulo_crash_only":
        # NOT "unproven-equivalent": an input DOES distinguish these, by crash. Calling them
        # unproven sends the reader hunting for an input that already exists.
        verdict = f"complete, modulo {_crash_only} crash-only value gap{'s' if _crash_only != 1 else ''}"
    elif _shape == "nothing_measured":
        verdict = "nothing measured — no mutants in this function's universe; no certificate"
    elif _shape == "inconsistent":
        verdict = "complete, modulo an inconsistent survivor count (please report)"
    elif _shape == "complete":
        verdict = "complete"
    else:
        # Not "✗": the gaps are itemised below, and a suite that pins every killable behaviour
        # but leaves a line uncovered is not a failed run.
        verdict = "incomplete"
    # Name BOTH lenses so the headline reconciles with the classification below (issue #55): the
    # value-pinned count (the completeness the classification partitions) AND the detection rate
    # (`kill_pct`, which counts crash kills too). Blurring them into one "% killed" is the very thing
    # the README says the tool does not do.
    # A RATE OVER AN EMPTY UNIVERSE IS NOT A RATE. `kill_pct` is an explicit `else 100.0` when
    # `total_mutants` is 0, so a function with no mutable behaviour printed "100.0% killed" — a
    # number that reads as the best possible outcome and is a division artifact. Omit it rather
    # than render it: the verdict beside it already says nothing was measured.
    _rate = "" if a.total_mutants <= 0 else f"· {a.kill_pct}% killed (value+crash) "
    lines = [
        _RULE,
        f"{a.function} — audit · {a.test_count} test(s) · {a.value_killed}/{a.total_mutants} value-pinned "
        f"{_rate}· {verdict}",
        "",
    ]
    # FAN-IN, led with (issue #54): how many tests REACH this function vs how many PIN it. A wide
    # gap (79 reach · 5 pin) is the most decision-useful line the run produces — high fan-in + thin
    # contract is exactly where a rewrite is dangerous and converging pays off most. It also reframes
    # the "redundant" count below: most of those tests are not junk, they traverse this function en
    # route to their own — the number says "write tests here", not "delete tests".
    if a.minimal_test_count and a.test_count > a.minimal_test_count:
        ratio = a.test_count / a.minimal_test_count
        flag = " — high fan-in, thin contract: converge here" if ratio >= 3 else ""
        # The minimal cover is BASIS-RELATIVE (§1.4): computed over THIS run's traced, admissible,
        # own-suite evidence (own_matrix + admissible own_lines), not a suite-wide claim — a different
        # `.wesker/` trace state yields a different B_t, so the count is minimal *for what was traced*.
        lines.append(
            _row(
                "· fan-in",
                f"{a.test_count} reach this function · {a.minimal_test_count} in the basis-relative "
                f"minimal cover ({ratio:.0f}:1){flag}",
            )
        )
    # ℋ ⊎ 𝒢 origin census (§2.3, D5): which half of the Sandwich the suite's evidence is. A suite that
    # is fully pinned but 0 intent-grounded is CHARACTERIZED and un-reviewed — generated tests pin what
    # the code DOES, not what it should. Surfacing that is the whole point of typing the two halves.
    _origin_bits = [
        f"{n} {label}"
        for n, label in (
            (a.intent_tests, "intent-grounded"),
            (a.characterized_tests, "characterized"),
            (a.unattributed_tests, "unattributed"),
        )
        if n
    ]
    if _origin_bits:
        _note = " — characterization only, UNREVIEWED" if a.characterized_tests and not a.intent_tests else ""
        lines.append(_row("· origin (ℋ⊎𝒢)", " · ".join(_origin_bits) + _note))
    if a.failing_tests:
        # First, always: a failing test means the suite disagrees with the code RIGHT NOW.
        # Nothing else in this report matters until that is resolved, and it is never ours
        # to delete — it is either a wrong expectation or a real regression.
        lines.append(_row("⚠ FAILING NOW", f"{len(a.failing_tests)} test(s) fail on current code:"))
        lines.append(_row("", _first_n(a.failing_tests, 4)))
    if a.killable_gaps:
        lines.append(_row("✗ real gaps", f"{len(a.killable_gaps)} killable mutant(s) no test kills"))
    if a.missing_lines:
        lines.append(_row("✗ uncovered", f"{len(a.missing_lines)} line(s): {_first_n(a.missing_lines, 8)}"))
    if getattr(a, "authored_fence", 0):
        # A FENCE is a GAP, not an equivalent (Q8): an authored must-not the suite does not enforce.
        # Shown with the ✗ gaps and above the flagged-equivalent line so the two are never conflated.
        lines.append(
            _row("✗ authored fence", f"{a.authored_fence} must-not(s) you flagged that no test enforces")
        )
    if a.manually_unreachable:
        lines.append(
            _row("· line oracle", f"{a.manually_unreachable} statement(s) flagged unreachable (modulo)")
        )
    for stale in a.contradicted_line_flags:
        lines.append(_row("⚠ flag overridden", f"executed: {stale} — execution outranks the flag"))
    # Split the breakdown out: "no input distinguishes them" is false of the crash-only class.
    if unproven_eq := a.candidate_equivalent - a.crash_only_equivalent:
        lines.append(_row("· unproven-equiv", f"{unproven_eq} survivor(s) — no input distinguishes them"))
    if a.crash_only_equivalent:
        lines.append(
            _row(
                "· crash-only-equiv",
                f"{a.crash_only_equivalent} survivor(s) — detected by crash; no value pins them",
            )
        )
    if a.unclassified:
        lines.append(_row("⚠ unclassified", f"{a.unclassified} — the search could not run on them"))
    if a.manual_equivalent:
        lines.append(_row("✓ flagged equivalent", f"{a.manual_equivalent} (your oracle — not gaps)"))
    if a.redundant_tests:
        lines.append(_row("· redundant", f"{len(a.redundant_tests)} test(s) pointless for kills AND lines"))
        lines.append(_row("", _first_n(a.redundant_tests, 4)))
    lines.append("")
    lines += _audit_action(a, removing)
    return "\n".join(lines)


def _audit_action(a, removing: bool = False) -> list[str]:
    """Audit's ONE next action, in the report's row style. Priority order — the order IS the
    judgement.

    Issue #10: ``removing`` means ``--remove`` is EXECUTING right now — recommending
    ``audit --remove`` mid-``audit --remove`` is a stale self-instruction computed for the
    pre-action state. The measurement stays; the recommendation yields to the removal
    result the caller prints next.

    A failing test outranks everything: the suite contradicts the code, so every other number
    here was measured against a suite that does not pass, and acting on them first is acting on
    sand. Then real gaps (converge writes them), then bloat, then the equivalents — last,
    because `flag` is the one claim a human makes against the engine and it must never be
    suggested while a real gap is open.
    """
    if a.failing_tests:
        # The one branch with no single command, and legitimately so: the next move is a
        # decision only a human has standing to make (is the CODE wrong, or the TEST?), and
        # either answer is a different edit. The mechanical parts are still commands.
        first = a.failing_tests[0]
        return [
            f"DO THIS:  pytest -k {first!r}",
            "",
            _row("· Then decide", "is the TEST's expectation wrong, or is the CODE broken?"),
            _row("", "Detective will not touch it — that call is yours alone."),
            _row("· After fixing", f"detective audit '{a.function}'"),
        ]
    if a.killable_gaps or a.missing_lines:
        gaps = len(a.killable_gaps)
        lines = len(a.missing_lines)
        why = ", ".join(
            p
            for p in (
                f"{gaps} killable mutant(s)" if gaps else "",
                f"{lines} uncovered line(s)" if lines else "",
            )
            if p
        )
        return [
            f"DO THIS:  detective converge '{a.function}'",
            "",
            _row("· Why", f"{why} — real gaps, not equivalents."),
            _row("· Writes", "the missing tests, and wires them into pytest."),
        ]
    if a.redundant_tests:
        if removing:
            return [
                _row("· Removing", f"{len(a.redundant_tests)} candidate(s), safety-checked below —"),
                _row("", "a test pointless here can still be a sibling's only pin."),
            ]
        return [
            f"DO THIS:  detective audit '{a.function}' --remove",
            "",
            _row("· Why", f"{len(a.redundant_tests)} test(s) kill no mutant AND cover no line"),
            _row("", "OF THIS FUNCTION that another test does not already. --remove"),
            _row("", "re-checks every sibling in the file, keeps any a candidate still contributes"),
            _row("", "to, and edits only this function's own test file — never a cross-file test."),
        ]
    if a.candidate_equivalent and a.candidate_equivalent_ids:
        first = a.candidate_equivalent_ids[0]
        more = f"   ({a.candidate_equivalent - 1} more in the report)" if a.candidate_equivalent > 1 else ""
        return [
            "DONE:  every killable behaviour is pinned and every line covered.",
            "",
            _row("· What remains", f"{a.candidate_equivalent} survivor(s) no VALUE assertion pins."),
            _row("", "Whether they are truly equivalent is UNDECIDABLE in"),
            _row("", "general — the engine will not claim it. Leave them."),
            _row("· If you can PROVE", f"detective flag '{a.function}' {first} --note \"why\"{more}"),
        ]
    if a.unclassified:
        return [
            "DONE:  no gaps found.",
            "",
            _row("· Unknown", f"{a.unclassified} survivor(s) could not be classified — the"),
            _row("", "search could not run on them. Not gaps, not equivalents."),
        ]
    return ["DONE:  the suite is complete and minimal. Nothing to do."]


_COMMAND_HELP = {
    "diagnose": "START HERE for a FUNCTION — what does it actually do, and what to run next (read-only)",
    "converge": "write a complete, minimal pytest suite for a function (the flagship; writes files)",
    "decompose": "split a tangled function into helpers — applied only when PROVEN behavior-preserving",
    "audit": "assess an EXISTING suite: complete? minimal? which tests to prune",
}


def _headline(help_text: str) -> str:
    """A command's one-liner, as the first line of its `--help` description.

    Sentence-cased with `s[0].upper() + s[1:]`, NEVER `.capitalize()` — which lower-cases
    everything after the first character and silently ate the emphasis these strings carry on
    purpose: "an EXISTING suite" became "an existing suite", "PROVEN behavior-preserving" became
    "proven". The shouted words are the claim.

    Wrapped here because these pages use RawDescriptionHelpFormatter — argparse wraps `help=` but
    never a `description`, so the same string that fits in the command list ran to 89 columns on
    its own page.
    """
    text = f"{help_text[0].upper()}{help_text[1:]}."
    return "\n".join(textwrap.wrap(text, 78))


# Stated on EVERY command that runs it, because a reader who hits the refusal reads THAT
# command's --help, not the root's. Four commands resolve this stage and one used to mention it,
# which is the same discoverability failure as the tool having no `regime` command at all: the
# capability existed and nothing led you to it. Worth the repetition — an agent that has never
# seen Detective needs to learn the word `regime` from whatever page it happens to land on.
_REGIME_STAGE = (
    "BEFORE this runs, Detective resolves the repo's TESTING REGIME: the name that\n"
    "imports your target, the sys.path your SUITE gets, and whether that name means\n"
    "the file you pointed at. If anything makes a verdict untrustworthy — the target\n"
    "is SHADOWED by another copy of itself, or two conftests share one module name\n"
    "and kill the live pytest session — it REFUSES and prints the exact fix, rather\n"
    "than reporting a number measured against the wrong file.\n"
    "\n"
    "    detective regime            # see it, and why a run refused\n"
    "    detective regime --migrate  # fix the part that is Detective's to fix"
)


# converge is the one command that WRITES, and WHEN it writes is a first-order instruction, not
# a nicety. Converge a function in ISOLATION right after writing it, BEFORE wiring it into a
# property / to_dict / any broadly-called path: a wired target's covering set is every test that
# reaches its callers, so tracing inflates to suite scale and the run can hang (the covering set
# was never meant to scale with the suite — the unit is ONE function's tests). Converged in
# isolation the covering set is just this function's own tests, and the complete suite lands while
# the code is still fresh in hand. Shown on converge's own --help page (epilog).
_CONVERGE_WORKFLOW = (
    "WORKFLOW — converge at WRITE TIME, in isolation:\n"
    "    Write the function, converge it, THEN wire it in. Converging a function that\n"
    "    is already wired into a property / to_dict / a broadly-called path traces\n"
    "    every test reaching those callers, so its covering set balloons to suite\n"
    "    scale and the run can hang. In isolation the covering set is just this\n"
    "    function's own tests — the complete, minimal suite lands while the code is\n"
    "    still fresh in hand."
)


def _target_ns(file: str, function: str, root: str) -> dict:
    """The target module's namespace, for `--input`.

    This is what makes the README's promise true — it says `--input` carries "a plan name, a
    lookup key, a valid domain object", and a domain object needs its CLASS in scope to be
    written down. The same namespace the engine already seeds every mutant from; nothing new
    is reachable that the caller's own tests do not already import.

    `__name__` is OVERRIDDEN with the module name derived from the FILE PATH, and that is not
    cosmetic. `_load_original` imports the target under a synthetic name (`_detective_uut_x`)
    when it is not already in `sys.modules`, so the live `__name__` is an implementation
    detail of this loader. A generated test that inherits it reads
    `from _detective_uut_billing import Account`, fails collection, takes the whole proof
    suite red with it — and decompose then reports `REJECTED: the suite PROVES this extraction
    changes behaviour` for an extraction that is perfectly sound. A false verdict, sourced from
    an import line. `_import_line` derives the name a reader would actually type; use that.

    Returns {} on any failure: a target that cannot be loaded still has a literal `--input`
    path, and refusing to parse `(1, 2)` because a module import failed would be worse than
    the gap this closes.
    """
    import os as _os

    from .engine import _load_original

    try:
        full = file if _os.path.isabs(file) else _os.path.join(_os.path.abspath(root), file)
        obj = _load_original(full, function)
        ns = dict(getattr(obj, "__globals__", {}) or {})
        rel = _os.path.relpath(full, _os.path.abspath(root))
        mod = rel.replace(_os.sep, ".").replace("/", ".")
        ns["__name__"] = mod[:-3] if mod.endswith(".py") else mod
        return ns
    except Exception:  # noqa: BLE001 — an input parser must not be what breaks the run
        return {}


def _parse_supplied_inputs(raw: list[str], ns: dict | None = None) -> list[tuple]:
    """Parse ``--input`` strings into positional-argument tuples — the Zone-2 residual a
    human fills THROUGH the tool when deterministic synthesis provably could not exercise
    a degree of freedom. Each string is one call's argument tuple; a bare non-tuple value
    is taken as a single positional argument.

    A LITERAL is the fast path. Beyond that an argument may be a CONSTRUCTOR EXPRESSION
    over an allowlisted module — ``ast.parse('def f(): ...').body[0]``. Without it the
    residual is unfillable for precisely the parameters that most need it: an
    ``ast.FunctionDef`` has no literal form, so a literal-only parser rejects every input
    a human could offer, and the tool ends up printing ``supply --input "(<func_node>,)"``
    for a slot no ``--input`` could ever fill. Measured on Wesker's
    ``_deletable_stmt_ids``: 23 behaviors proven killable, not one of them expressible.

    The grammar, the allowlist and the safety boundary live in
    :func:`equivalence.parse_input_expression` — ONE definition, shared with
    ``samples.load``, so what a human may supply and what the store may recall cannot
    drift apart. Errors become a usage message here; the library raises rather than
    exiting, so it stays usable off the CLI.
    """
    from .equivalence import InputExpressionError, parse_input_expression

    out: list[tuple] = []
    for s in raw:
        try:
            out.append(parse_input_expression(s, ns))
        except InputExpressionError as exc:
            raise SystemExit(f"detective: --input {exc}") from None
    return out


def _engine_version() -> str:
    """`Wesker X.Y.Z` — the engine actually imported, for `--version`.

    Read off the live module, not the dependency floor in our metadata: the floor is what we
    ASKED for; a report is produced by what is INSTALLED. Those differ routinely — an editable
    checkout, a sibling on PYTHONPATH, a stale venv — and that difference is exactly what a bug
    report needs to state and what this session spent hours failing to see.

    The two failure modes are DIFFERENT and are not collapsed. "Not importable" is close to
    unreachable in practice (this package imports the engine at module scope, so `--version`
    could not have run) but is honest if it ever happens; "no `__version__`" means an engine
    IS installed and simply predates the attribute. A single catch-all here reported
    `Wesker NOT INSTALLED` for an engine sitting right there in site-packages — the wrong
    cause, stated confidently, in a string whose whole job is to be trusted in a bug report.
    """
    try:
        import Wesker
    except Exception:  # noqa: BLE001 — a version string must never be the thing that crashes
        return "Wesker NOT IMPORTABLE"
    version = getattr(Wesker, "__version__", None)
    return f"Wesker {version}" if version else "Wesker version UNKNOWN"


# The path-based / advisory verbs: each carries `path` or no target (never `target::function`), runs a
# STATIC pass (no mutant, no live pytest session), and is dispatched in `_run` ABOVE `_split_target`. One
# named set so `_run_live`'s session bypass and `_run`'s pre-split dispatch cannot silently drift as verbs
# are added (the dispatch-ordering fragility of the flat `_run` ladder — patched by naming the contract).
_STATIC_COMMANDS = ("purge", "regime", "parsimony", "censor")

# The exit-code contract, one place. Each verb's result IS its exit status (CI branches on the code, a
# `--json` consumer on the field) — this consolidates the per-handler semantics into one discoverable map.
_EXIT_CODES = (
    "EXIT CODES (a verdict is also the exit status — CI branches on the code, --json on the field):\n"
    "  0  clean / success\n"
    "  1  a real gap or typed REFUSAL — audit --check spec gap; verify-rewrite not PRESERVED; a\n"
    "     collision/accounting refusal; flag: no such surviving mutant\n"
    "  2  a conflict / precondition — regime conflict, wrong interpreter, a bad --env, or\n"
    "     audit --check-strict measurement-incomplete\n"
    "  3  INVALID MEASUREMENT, re-run — converge/decompose CUT or stale target; a weak receipt baseline"
)


def exit_code_meaning(code: int) -> str:
    """The self-describing label for an exit code (#16, pure — pinned). Every ``--json`` verdict carries
    ``{exit_code, exit_meaning}`` so a machine consumer branches on the FIELD — not the process status it
    may not even see, nor the human epilog `_EXIT_CODES` it would have to parse. One map, the four codes
    of that contract; an out-of-range code is NAMED ``unknown``, never silently dropped or mislabelled as
    one of the four."""
    return {
        0: "clean",
        1: "gap_or_refusal",
        2: "conflict_or_precondition",
        3: "invalid_measurement_rerun",
    }.get(code, "unknown")


def _with_exit(payload: dict, code: int) -> dict:
    """Enrich a ``--json`` verdict with its self-describing exit field (#16): ``exit_code`` +
    ``exit_meaning``, so a consumer branches on the FIELD, never the process status it may not see nor
    the human `_EXIT_CODES` epilog it would have to parse. Wrap a payload where it is already
    ``json.dumps``-ed — ``json.dumps(_with_exit(payload, code), …)`` — so the field rides along without
    disturbing the payload's own (possibly nested) shape."""
    return {**payload, "exit_code": code, "exit_meaning": exit_code_meaning(code)}


def _emit_json(payload: dict, code: int) -> int:
    """The print+return funnel for a ``--json`` verdict (#16): enrich, print, and RETURN the code — so a
    verb's `--json` ending is `return _emit_json(payload, code)`, the payload and its exit status minted
    at one point and unable to disagree. A structural test asserts every verdict emission carries the
    field, whether via this funnel or a ``json.dumps(_with_exit(...))`` wrap where the dumps already sits."""
    print(json.dumps(_with_exit(payload, code), indent=2, default=str))
    return code


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="detective",
        # RawDescription: argparse's default formatter re-wraps and would collapse the two
        # commands below into prose, which is the one thing they must not be — they are the
        # first things a reader runs. Every line here is hand-wrapped to fit a terminal.
        description=(
            "Read what a function actually does, pin it with tests, and split it SAFELY —\n"
            "every rewrite is applied only when a generated suite proves behavior survived.\n"
            "\n"
            "NEW REPO? START HERE:\n"
            "    detective regime            # how does this repo import its code and run\n"
            "                                # its tests — and is anything making every\n"
            "                                # verdict untrustworthy?\n"
            "    detective regime --migrate  # fix the part that is Detective's to fix\n"
            "\n"
            "  Every command below resolves that same regime first and REFUSES on a conflict.\n"
            "  A number measured against the wrong file is worse than no number: it reads as\n"
            "  a finding. If a run refuses, `detective regime` is where the reason is.\n"
            "\n"
            "THEN, read-only:\n"
            "    detective diagnose path/to/file.py::function"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=_EXIT_CODES,
    )
    # BOTH versions, because a verdict is a joint product. Detective decides what to ask; the
    # ENGINE decides what the answer is — a kill it classifies `crash` rather than `exception`
    # changes what counts as specified — and `engine.profile` keys its verdict cache on the
    # engine version precisely because the same question yields a different answer across
    # engines. So "detective 0.5.4" alone does not identify the thing that produced your
    # report: two installs printing it can disagree, and the string gives you no way to know.
    # Read from the INSTALLED module, never restated: this must describe the engine actually
    # imported, not the one the metadata floor asked for.
    parser.add_argument(
        "--version", action="version", version=f"detective {__version__} ({_engine_version()})"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    # diagnose leads: it is the only read-only entry point, and the previous order
    # recommended `converge` first — which WRITES test files into someone's repo before they
    # have any idea what the tool does. Earning that comes after showing the map.
    for name in ("diagnose", "converge", "decompose", "audit"):
        p = sub.add_parser(
            name,
            help=_COMMAND_HELP[name],
            description=f"{_headline(_COMMAND_HELP[name])}\n\n{_REGIME_STAGE}",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        p.add_argument("target", help="file.py::function")
        p.add_argument("--project-root", default=".", help="project root the target path is relative to")
        p.add_argument("--json", action="store_true", help="emit JSON")
        # GLOBAL, not converge-only. It was added for converge's mutant list and that revived a
        # telemetry footer whose reader had sat behind `args.verbose` since before any command
        # defined the flag — dead code, waiting. Its comment says "behind --verbose, where
        # someone chasing memory will look for it", and someone chasing memory is debugging
        # `diagnose` as often as `converge`. One flag, one meaning: MORE DETAIL. What that
        # yields differs per command, which is what a detail flag is for.
        p.add_argument(
            "--verbose",
            action="store_true",
            help="more detail: the memory-telemetry footer (stderr) on any command, and — with "
            "--full on converge — every surviving mutant's id and diff instead of grouping them "
            "by the statement they mutated. Use it when you need an id to pass to `flag`, or "
            "when you are debugging the run itself",
        )
        # The traced baseline runs BEFORE any mutant, and tracing costs a callback per executed
        # line — so a computationally heavy test in the suite used to present as a hang with no
        # output at all. Bounded by default; 0 restores the old unbounded pass. Cut tests are
        # always named, never dropped quietly.
        p.add_argument(
            "--trace-budget",
            type=float,
            default=_WESKER_DEFAULT_TRACE_BUDGET_S,
            metavar="SECONDS",
            help=(
                f"per-test cap on the traced baseline pass (default {_WESKER_DEFAULT_TRACE_BUDGET_S:g}s; "
                "0 = unbounded). Bounds ONE pathological test; rarely what cut you — see "
                "--trace-session-budget. A cut test's line coverage is under-counted, is reported "
                "by name, and makes already-pinned behaviour read as unpinned."
            ),
        )
        p.add_argument(
            "--trace-session-budget",
            type=float,
            default=_DEFAULT_TRACE_SESSION_BUDGET_S,
            metavar="SECONDS",
            help=(
                f"cap on the WHOLE traced baseline pass (default {_DEFAULT_TRACE_SESSION_BUDGET_S:g}s; "
                "0 = unbounded). Bounds the aggregate, which the per-test cap cannot: tests not "
                "reached are reported by name. THIS is almost always the knob that cut you — "
                "raise it first, or set both to 0 for an exact measurement."
            ),
        )
        if name in ("diagnose", "converge"):
            # The two commands that run the speculative widen/capture search. By DEFAULT a
            # shape-hazardous test is DEFERRED from that search (it forces the expensive isolation
            # path and is almost never the minimal witness for a unit mutant); the count is disclosed
            # so a residual is never silently attributed to the code when a deferred test might kill it.
            p.add_argument(
                "--include-shaped",
                action="store_true",
                help="include shape-hazardous tests (subprocess/thread/signal/custom-collector) in the "
                "speculative widen search. By DEFAULT these are DEFERRED — one such test forces the "
                "expensive isolation path (a subprocess per mutant, e.g. a 50s live-game system test per "
                "widen step) and is almost never the minimal distinguishing witness for a unit-level "
                "mutant, so the widen skips them and the report discloses how many. Pass this when a "
                "residual may be killable ONLY by such a test and you want to pay to trace them.",
            )
        if name in ("diagnose", "converge", "decompose", "audit"):
            # μ⁻ (negative specification). Opt into the two-sign contract σ(P, μ ∪ μ⁻): add the
            # codomain operator that perturbs the RETURN VALUE, so a surviving perturbation is a
            # NEGATIVE degree of freedom — an output invariant no test pins. diagnose reports them;
            # converge writes tests that pin them, under the two-sign policy id. Off by default; the
            # one-sign universe and its policy id are unchanged when this is absent.
            p.add_argument(
                "--two-sign",
                action="store_true",
                help="opt into the two-sign contract σ(P, μ ∪ μ⁻): also run the codomain operator "
                "μ⁻, which perturbs the RETURN VALUE. A surviving μ⁻ perturbation is a negative "
                "degree of freedom — an output invariant your suite does not pin (→None: the "
                "output must exist; →const: it must depend on the input; →identity: it must "
                "transform its input). On `audit`, such a survivor is a killable gap, so `audit "
                "--two-sign --check` gates CI on an engine-found negative DOF (extending the authored "
                "`flag --fence`). On `decompose`, the preservation proof is then over σ(P, μ ∪ "
                "μ⁻), so an applied extraction is certified to have preserved the value pins AND the "
                "negative fences (Thm 15.4). Off by default.",
            )
        if name == "converge":
            # The workflow note renders after the options on `converge --help` (this loop set
            # RawDescriptionHelpFormatter, so the epilog is shown verbatim).
            p.epilog = _CONVERGE_WORKFLOW
            p.add_argument(
                "--write-dir",
                default="tests/detective",
                # The generated-tests home (issue #21): certificates separate
                # from hand-written specs at a glance. A file this target left
                # at the old tests/ root default is migrated on next write.
                help="write synthesized tests here (default: tests/detective)",
            )
            p.add_argument(
                "--max-iterations",
                type=int,
                default=3,
                help="max converge passes before stopping (default 3)",
            )
            p.add_argument(
                "--fast",
                action="store_true",
                help="greedy-sample a (1−1/e)-optimal subset of mutants per category per pass "
                "instead of the full universe — faster, converging over passes (default: comprehensive)",
            )
            p.add_argument(
                "--full",
                action="store_true",
                help="print the full report to the terminal (default: a minimal banner + the one "
                "quick action; the full report is always written to .detective/reports/ regardless)",
            )
            p.add_argument(
                "--input",
                action="append",
                metavar="TUPLE",
                help="one real call's positional arguments, as a Python literal tuple — e.g. "
                "\"([{'qty': 5, 'price': 2.0}], 0.08, 'gold', None)\" — to reach behaviour "
                "synthesis could not. Repeatable; a bare non-tuple literal is one argument. "
                "LITERALS ONLY (plus `ast.*`): this parses an allowlist, which is what makes "
                '"no arbitrary code execution" checkable rather than hoped-for — so it CANNOT '
                "carry your own classes (`Account(...)` is rejected). For a function taking a "
                "domain object, do not use this flag: write ONE test that calls the function "
                "with a real object and Detective captures the arguments from it. The report "
                "tells you which of the two applies; it never asks for an --input it will refuse.",
            )
            p.add_argument(
                "--clock",
                type=float,
                metavar="EPOCH",
                default=None,
                help="freeze time.time() to this UNIX-epoch value while pinning — for a function "
                "whose output reads the wall clock (a TTL/expiry check), which is otherwise "
                "non-deterministic and cannot be pinned. The emitted test re-freezes and restores "
                "the clock, so the pin holds. v1 freezes time.time() only; the report flags "
                "time-gated lines under `env-gated`.",
            )
            p.add_argument(
                "--env",
                action="append",
                metavar="NAME=value",
                default=None,
                help="declare an environment variable while pinning — NAME=value sets it, NAME- "
                "declares it ABSENT — for a function whose result reads os.environ / os.getenv, which "
                "is otherwise CI-dependent and refused. Repeatable. The emitted test re-applies and "
                "restores the same environment (stdlib only), so the pin holds with no fixture. A "
                "variable the function reads but you do not declare stays refused (an undeclared "
                "dependency must not ride a certificate).",
            )
            p.add_argument(
                "--receiver-factory",
                metavar="MODULE:CALLABLE",
                default=None,
                help="for a METHOD target whose class cannot be constructed with no arguments "
                "(``Basket()`` fails), name a zero-argument factory that returns a receiver — e.g. "
                "``package.factories:make_basket``. The factory builds a FRESH receiver for every "
                "capture and witness call (so no mutable state leaks between checks), and the emitted "
                "test imports and calls it. The receiver is a separate proof axis from ``--input`` "
                "(which parses literals only and cannot carry a constructed object); a ``✓ COMPLETE`` "
                "on a method holds UNDER the receiver population this explores, not every instance "
                "state. Without it, such a target is a named ``needs-receiver`` refusal, never 0 kills.",
            )
            p.add_argument(
                "--deadline",
                type=float,
                metavar="SECONDS",
                default=300.0,
                help="ONE aggregate wall for the whole command (default 300s; 0 = unbounded). "
                "Every phase — profiling, witness search, minimization, finalization — draws "
                "from the SAME remaining budget, so a runaway or a flooding integration target "
                "is CUT with a named diagnosis instead of hanging. A cut run is non-gateable: "
                "no `✓ COMPLETE`, and decompose will not treat it as a preservation proof.",
            )
        if name == "audit":
            p.add_argument(
                "--remove",
                action="store_true",
                help="CONFIRM deletion of the proposed pointless tests (removes them from your files)",
            )
            p.add_argument(
                "--check",
                action="store_true",
                help="CI mode: exit 1 when the suite has a real SPECIFICATION gap — a killable mutant "
                "it does not kill, a reachable uncovered line, or a failing test. An UNCLASSIFIED "
                "survivor is a MEASUREMENT limit (the search could not evaluate it), NOT a code gap, so "
                "it does NOT fail the gate — it is surfaced instead; use --check-strict to "
                "gate on it. Candidate-equivalent / crash-only survivors do NOT fail either (unproven-"
                "equivalent, resolved by `flag`). Combine with --json for a machine-readable artifact "
                "carrying the same exit status. This is the surface a CI ratchet gates on: it fails "
                "only when the CODE got worse, never when the measurement got shorter.",
            )
            p.add_argument(
                "--check-strict",
                action="store_true",
                help="Like --check, but ALSO exit non-zero (code 2, distinct from a spec gap's 1) when "
                "the measurement was incomplete — an unclassified survivor the equivalence search could "
                "not evaluate. For a pipeline that genuinely wants 'fail unless fully measured'; opt-in, "
                "so the documented --check default stays a claim about the code alone.",
            )
            p.add_argument(
                "--plan",
                action="store_true",
                help="the 'should I spend the mutation budget on this?' answer, WITHOUT paying for it: "
                "tier 0 (static read) + tier 1 (fan-in — how many tests reach it — and line coverage) + "
                "a MEASURED estimate of the tier-2 mutation cost, then exit before mutating. Composes "
                "with `parsimony --plan` (which picks the functions); this sizes one. Pair with --json.",
            )
        if name == "decompose":
            p.add_argument(
                "--apply",
                action="store_true",
                help="APPLY the behavior-preserving extractions (rewrites the file); else propose only",
            )
            p.add_argument(
                "--input",
                action="append",
                metavar="TUPLE",
                help="supply a residual input (Python-literal positional-arg tuple) to the proof suite, "
                "so a function whose completeness needs a human sample can still reach the "
                "behavior-preservation gate. Same form as `converge --input`. Repeatable.",
            )
            p.add_argument(
                "--deadline",
                type=float,
                metavar="SECONDS",
                default=300.0,
                help="ONE aggregate wall for the whole decompose — the proof converge AND every "
                "trial-apply draw from the same remaining budget (default 300s; 0 = unbounded). "
                "A cut proof is never auto-applied: the source is rewritten only on a COMPLETE, "
                "non-cut proof.",
            )
    purge_p = sub.add_parser(
        "purge",
        help="delete regeneratable analysis caches (.detective/ + .wesker/) — never your tests",
        description=(
            "Delete the analysis caches BOTH packages leave behind: Detective's `.detective/` "
            "verdict cache and reports, and Wesker's `.wesker/`. Everything removed is "
            "regeneratable by re-running — the next run is just cold.\n\n"
            "NEVER deleted: your test files, and the two things you AUTHORED — "
            "`.detective/inputs.json` (the --input samples you supplied) and "
            "`.detective/equivalents.json` (the mutants you flagged equivalent). Those are "
            "judgements no re-run can reproduce, so purge does not treat them as cache."
        ),
    )
    purge_p.add_argument("--project-root", default=".", help="project root to purge caches under")
    purge_p.add_argument("--json", action="store_true", help="emit JSON")
    regime_p = sub.add_parser(
        "regime",
        help="read how this repo imports its code and runs its tests — the stage every command runs",
        description=(
            "Resolve the testing regime and report it: the layout, the sys.path the SUITE gets, "
            "the conftests pytest loads, whether the `detective` marker is declared, and — with "
            "a target — the dotted name the rest of the repo imports it by and whether that name "
            "means THIS file.\n\n"
            "Read-only. Every other command resolves the same regime before it runs and refuses "
            "on a conflict; this prints it. Use it when a run refuses, or before pointing "
            "Detective at an unfamiliar repo."
        ),
    )
    regime_p.add_argument(
        "target", nargs="?", help="optional file.py::function — adds the target-specific facts"
    )
    regime_p.add_argument("--project-root", default=".", help="project root to read")
    regime_p.add_argument(
        "--migrate",
        action="store_true",
        help="APPLY the clean setup: declare the `detective` marker (and pythonpath, if a "
        "conftest WE wrote was supplying it) in pyproject, then remove that conftest. Only ever "
        "replaces Detective's own artifacts with their declarative equivalent — never edits or "
        "deletes a file you wrote. Without this flag the plan is printed and nothing changes",
    )
    regime_p.add_argument("--json", action="store_true", help="emit JSON")
    flag_p = sub.add_parser(
        "flag", help="mark a surviving mutant equivalent (default) or a FENCE — an authored must-not"
    )
    flag_p.add_argument("target", help="file.py::function")
    flag_p.add_argument("mutant_id", help="the surviving mutant id (from `audit`/`diagnose`)")
    flag_p.add_argument("--note", default="", help="why it is equivalent, or why it must not survive")
    flag_p.add_argument(
        "--fence",
        action="store_true",
        help="record a FENCE, not an equivalent: this survival is a BUG — an authored MUST-NOT (a "
        "two-sign negative degree of freedom) the suite does not yet enforce. Reported as an "
        "unenforced gap that fails `audit --check` and blocks ✓COMPLETE, never suppressed as valid.",
    )
    flag_p.add_argument("--project-root", default=".")
    flag_p.add_argument("--json", action="store_true", help="emit JSON")

    flag_line_p = sub.add_parser(
        "flag-line",
        help="mark an uncovered source line as unreachable (manual oracle — line ledger only)",
    )
    flag_line_p.add_argument("target", help="file.py::function")
    flag_line_p.add_argument(
        "line", type=int, nargs="?", help="the uncovered line number (from `audit`/`converge`)"
    )
    flag_line_p.add_argument("--note", default="", help="why it is unreachable")
    flag_line_p.add_argument(
        "--list", action="store_true", help="show this function's flags with current/orphaned status"
    )
    flag_line_p.add_argument(
        "--remove", action="store_true", help="delete the flag at LINE (exact record; never bulk)"
    )
    flag_line_p.add_argument(
        "--clean", action="store_true", help="delete only CONFIRMED-orphaned records for this function"
    )
    flag_line_p.add_argument("--project-root", default=".")
    flag_line_p.add_argument("--json", action="store_true", help="emit JSON")

    parsimony_p = sub.add_parser(
        "parsimony",
        help="STATIC repo/module/class SICP map (advisory) — no mutation, no proof",
        description=(
            "Roll up the AST-only parsimony lenses (complexity, cohesion, interface width, "
            "structural seam) over a file or directory and report the shape of its parsimony: a "
            "clean-percent score per module and class, and the worst-offending functions.\n\n"
            "ADVISORY, not a proof. It runs no mutant and writes nothing — the one repo-scale "
            "surface, and it says so. There is no repo-scale PROOF: the behavioural lenses "
            "(overload, regime), the per-function detail, and any proof stay in "
            "`detective diagnose`/`converge`, one function at a time."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parsimony_p.add_argument("path", help="a .py file or a directory to scan")
    parsimony_p.add_argument("--project-root", default=".", help="project root the path is relative to")
    parsimony_p.add_argument("--top", type=int, default=10, help="worst offenders to show (default 10)")
    parsimony_p.add_argument(
        "--plan",
        action="store_true",
        help="emit an ordered WORK QUEUE instead of the map: the flagged functions grouped by module "
        "(one baseline trace per group) and ordered worst-first, so a driver spends a finite mutation "
        "budget where it pays off first. Schedules work; ranks no quality, proves nothing, writes "
        "nothing. Pair with --json for an agent/MCP-consumable queue; --top bounds the groups shown.",
    )
    parsimony_p.add_argument("--json", action="store_true", help="emit JSON")

    censor_p = sub.add_parser(
        "censor",
        help="propose population-derived CENSORS (forbidden I/O regions) ranked by κ — the §14 corpus loop",
        description=(
            "Harvest population-derived censors across a corpus. A censor is a forbidden input/output "
            'region ("no correct implementation produces (x, y)") carved from an OBSERVED near-miss '
            "across the call-site population, NEVER from one function alone (Def. 9.1, Rem. 9.2); v1 "
            "fences the systematically-absent None. Rank them by marginal coverage κ over the call graph "
            "and report the promotion PRIORITY.\n\n"
            "ADVISORY / static — an AST call-site + call-graph pass, no mutant. Read-only by default "
            "(proposes, prints, writes nothing). --promote runs the κ→0 corpus fixpoint and PERSISTS the "
            "promoted censors to .detective/censors.json; --list shows that ledger. On clean data the loop "
            "is conservative-empty by construction — the honest 'the spine is the bottleneck' outcome, a "
            "censor is UNVERIFIED until promoted or triaged (Def. 9.5), never a gate."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    censor_p.add_argument("path", help="a .py file or a directory to scan for near-misses")
    censor_p.add_argument("--project-root", default=".", help="project root the path is relative to")
    censor_p.add_argument("--top", type=int, default=20, help="ranked censors to show (default 20)")
    censor_p.add_argument(
        "--promote",
        action="store_true",
        help="run the corpus fixpoint and PERSIST the promoted censors to .detective/censors.json "
        "(default: propose + rank only, writing nothing)",
    )
    censor_p.add_argument(
        "--list", action="store_true", help="show the persisted censor ledger (.detective/censors.json)"
    )
    censor_p.add_argument("--json", action="store_true", help="emit JSON")

    # Arbitrary-rewrite old-vs-new preservation gate (issue #37). `decompose` proves its OWN
    # transform; these two commands bracket an EXTERNAL/model rewrite: snapshot before, verify after.
    receipt_p = sub.add_parser(
        "receipt",
        help="snapshot a function's specification BEFORE an arbitrary rewrite, for verify-rewrite",
        description=(
            "Record a baseline receipt of a function: its source (so the OLD implementation can be run), "
            "its mutation-complete proof suite, its policy and operator universe. Take this BEFORE you "
            "let a model (or anyone) rewrite the function; `verify-rewrite` then proves the rewrite did "
            "not change behaviour against this receipt. Converges the target first, so the recorded "
            "proof basis is real."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    receipt_p.add_argument("target", help="file.py::function to snapshot")
    receipt_p.add_argument("--project-root", default=".", help="project root the target is relative to")
    receipt_p.add_argument("-o", "--out", default=None, help="write the receipt JSON here (default: stdout)")
    receipt_p.add_argument(
        "--json", action="store_true", help="the receipt is always JSON; accepted for uniformity"
    )

    verify_p = sub.add_parser(
        "verify-rewrite",
        help="prove an arbitrary/model rewrite preserved behaviour, against a receipt",
        description=(
            "Check a rewritten function against the receipt taken before the rewrite. Replays the "
            "original proof suite on the new source, profiles the new source for behaviours the old "
            "proof never covered, and evaluates the OLD and NEW implementations at each distinguishing "
            "input — reporting equal / different / abstained rather than silently learning the new "
            "behaviour. PRESERVED only when all three hold; exits non-zero otherwise."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    verify_p.add_argument(
        "receipt_path", metavar="receipt.json", help="the baseline from `detective receipt`"
    )
    verify_p.add_argument("target", help="file.py::function — the rewritten source to check")
    verify_p.add_argument("--project-root", default=".", help="project root the target is relative to")
    verify_p.add_argument("--json", action="store_true", help="emit the verification as JSON")
    verify_p.add_argument(
        "--learn",
        action="store_true",
        help="on a CHANGED verdict, SOURCE censors from the rejected rewrite (§9's second spine "
        "source): each input where the old (correct) and new (bad) implementations differed is "
        "a near-miss whose new output is forbidden. The candidates are κ-scored over the call graph "
        "and the promoted ones persisted to .detective/censors.json (`censor --list` shows them). "
        "Off by default — verify-rewrite stays a pure verdict command and writes nothing.",
    )
    return parser


def _shadow_root(shadow) -> str:
    """The `--project-root` that would put the analysis on the tree Python ACTUALLY imports.

    Strip the module's own parts off the imported file to get its source root, then strip a
    trailing `src` — the tests live beside it, not under it, and the root has to see both.
    """
    depth = len(shadow.module.split("."))
    root = shadow.imported
    for _ in range(depth):
        root = os.path.dirname(root)
    return os.path.dirname(root) if os.path.basename(root) == "src" else root


def _format_regime(regime, plan=None, applied: tuple[str, ...] = (), target: str | None = None) -> str:
    """The testing regime, as read — what imports what, and whether anything is in conflict.

    This is the stage every other command runs silently. Printing it exists because the four
    bugs it prevents were all invisible: each produced a plausible number rather than an error,
    and the only way to see the cause was to already suspect it.

    ``plan``/``applied`` are what migration WOULD do and what it just DID. Both are rendered
    against the regime as re-read afterwards, so the report is the tree as it stands.
    """
    lines = [
        _RULE,
        f"{_rel_path(regime.root)} — testing regime",
        "",
        _row("· layout", regime.layout),
        _row("· suite imports via", ", ".join(_rel_path(p) for p in regime.suite_path) or "(nothing)"),
    ]
    if regime.testpaths:
        lines.append(_row("· testpaths", ", ".join(regime.testpaths)))
    lines.append(_row("· conftest", ", ".join(regime.conftests) if regime.conftests else "(none)"))
    lines.append(
        # Name the FILE. "declared in pyproject" was hardcoded, and on a repo whose `pytest.ini`
        # outranks pyproject that sentence described a file pytest ignores — the report agreeing
        # with the bug instead of exposing it.
        _row(
            "· detective marker",
            f"declared in {regime.config_file or 'config'}" if regime.marker_declared else "not declared",
        )
    )
    if regime.module:
        lines.append(_row("· target imports as", regime.module))
    if regime.shadow is not None:
        lines.append(_row("✗ but that name is", _rel_path(regime.shadow.imported)))
    if regime.colliding_conftests:
        lines.append(_row("✗ same module name", ", ".join(regime.colliding_conftests)))
    if applied:
        lines.append("")
        lines.append("  MIGRATED:")
        lines += [_row("", f"✓ {what}") for what in applied]
    lines.append("")
    lines += _regime_action(regime, plan, applied, target)
    lines.append("")
    return "\n".join(lines) + "\n"


def _regime_action(regime, plan, applied, target: str | None = None) -> list[str]:
    """The one thing to do next. Migration first — it is the only step that is ours to take."""
    if plan is not None and plan.blocked:
        # Say what migration CANNOT fix before offering to run it. A tool that tidies the config
        # and stays quiet about the target resolving to another checkout has made the repo look
        # healthier without making a single verdict truer.
        out = ["DO THIS:  migration cannot fix this — it needs a decision only you can make:", ""]
        out += [_row("", f"· {why}") for why in plan.blocked]
        return out
    if plan is not None and plan.needed:
        where = f" --project-root '{regime.root}'" if regime.root else ""
        # Carry the TARGET, because half of what this command can fix is only VISIBLE with one.
        # `resolve_regime` runs the shadow check per file, so a targetless re-run cannot see the
        # shadow that produced this very line — and `plan_migration` then finds nothing to do.
        # Printed without it, the command answered "this regime resolves cleanly · nothing to
        # migrate" about the problem it had just diagnosed one line above, and wrote nothing.
        # A caller following the action verbatim (which is the contract) loops forever on it.
        aim = f" '{target}'" if target else ""
        return [
            f"DO THIS:  detective regime --migrate{aim}{where}",
            "",
            _row("· writes", "the marker (and pythonpath, if a conftest WE wrote was"),
            _row("", "supplying it) into pyproject — then removes that conftest."),
            _row("· never touches", "a file you wrote."),
        ]
    if regime.conflicts:
        return [
            "DO THIS:  resolve the conflict — every verdict here is untrustworthy until",
            "          you do. Run the command you wanted; it refuses with the exact fix.",
        ]
    if applied:
        return [
            "DONE:  migration applied; the re-read regime now resolves cleanly. Run",
            "       `detective audit`, `converge`, or `decompose` on a target in it.",
        ]
    # `DONE:`, not `DO THIS: nothing`. Every other command already draws this line — `DONE: no
    # separable block`, `DONE: every killable behaviour is pinned` — and the split is the whole
    # contract for a caller that is not a person: `DO THIS:` is a command to RUN, `DONE:` is a
    # stop. `DO THIS: nothing — this regime resolves cleanly` hands a parser prose where the
    # grammar promises a command, in the one command the banner tells a new repo to run FIRST.
    return [
        "DONE:  this regime resolves cleanly — nothing to migrate. Run `detective audit`,",
        "       `converge`, or `decompose` on a target in it.",
    ]


def _format_shadowed(shadow, target: str, root: str) -> str:
    """Refuse, and say which two files disagree.

    The paths ARE the message: every cause of shadowing (a stale copy, a non-editable install,
    a `.pth` aimed at another checkout) looks the same from here, and naming a cause we did not
    verify would be a guess. Naming both files is a fact, and it is the fact that ends the
    confusion — "0 tests cover this" is what a shadow looks like when nobody says the word.
    """
    lines = [
        _RULE,
        f"{target} — REFUSED · shadowed target",
        "",
        _row("✗ your tests import", shadow.module),
        _row("✗ which is this file", _rel_path(shadow.imported)),
        _row("✗ but you pointed me", _rel_path(shadow.target)),
        _row("", "— a different file, so the suite never runs the code"),
        _row("", "you asked about. Any verdict would measure the wrong"),
        _row("", 'program. "0 tests cover this" would be TRUE, and useless.'),
        "",
        "DO THIS:  pick the tree you meant, then re-run —",
        "",
        _row("· that tree", f"--project-root '{_shadow_root(shadow)}'"),
        _row("· or THIS tree", f"cd '{os.path.abspath(root)}' && pip install -e ."),
        _row("", f"which re-points `import {shadow.module.split('.')[0]}` here."),
        "",
    ]
    return "\n".join(lines) + "\n"


def _format_collision(regime, target: str) -> str:
    """Refuse on two conftests that share one importable name.

    Not cosmetic. Both are the module `conftest`; the second import in one process raises
    `import file mismatch`, which kills the live pytest session. Discovery then falls back to
    collect-only, where every FIXTURE-TAKING test is skipped — so the run does not fail, it
    quietly measures a smaller suite and reports the gaps that absence creates. The damage lands
    on exactly the repos careful enough to use fixtures, and Detective did this to itself, in its
    own repo, with a conftest it generated.
    """
    a, b = regime.colliding_conftests[0], regime.colliding_conftests[1]
    ours = [c for c in regime.colliding_conftests if c in regime.generated_conftests]
    lines = [
        _RULE,
        f"{target} — REFUSED · conflicting test setup",
        "",
        _row("✗ two conftests", f"{a}"),
        _row("", f"{b}"),
        _row("✗ one module name", "both import as `conftest` — their directories are not"),
        _row("", "packages, so pytest gives them the SAME name and the"),
        _row("", "second raises `import file mismatch`."),
        _row("✗ what that costs", "the live pytest session cannot start, so every"),
        _row("", "FIXTURE-taking test is silently skipped and the gaps"),
        _row("", "they cover are reported as unspecified behaviour."),
        "",
    ]
    if ours:
        # The only exact, verified fix — and the common case, because Detective wrote the second
        # conftest itself. Everything that file did now lives in pyproject, so removing it costs
        # nothing. Measured on this repo: the live session starts, the suite stays green.
        lines += [
            "DO THIS:  delete the one DETECTIVE wrote — everything it did now lives in",
            "          pyproject, so it costs nothing —",
            "",
            _row("· run", f"rm '{ours[0]}'"),
            _row("", "then re-run. Your own conftest is untouched."),
            "",
        ]
    else:
        # Both are the user's. Do NOT reach for `touch tests/__init__.py`: it ends the collision
        # and breaks any suite whose tests import a sibling helper by bare name (`from _support
        # import ...` — which only resolves while `tests/` is NOT a package). Measured on this
        # repo: 5 tests -> 0, `ModuleNotFoundError: No module named '_support'`. So name the
        # constraint and let the person who knows these files choose.
        lines += [
            "DO THIS:  give them different module names — either one works, and only you",
            "          can say which is right for these two files —",
            "",
            _row("· delete one", "if either is doing nothing."),
            _row("· or make a package", f"touch '{os.path.join(os.path.dirname(b) or '.', '__init__.py')}'"),
            _row("", "CAVEAT: that breaks tests that import a sibling helper"),
            _row("", "by bare name (`from _support import …`), which only"),
            _row("", "resolves while that directory is NOT a package."),
            "",
        ]
    return "\n".join(lines) + "\n"


def _format_conflicts(regime, target: str) -> str:
    """The regime said no verdict here can be trusted. Say which one, and how to end it.

    One refusal per conflict, most-blocking first: a shadowed target means the suite is not
    about this code at all, which outranks a suite that merely cannot start.
    """
    if regime.shadow is not None:
        return _format_shadowed(regime.shadow, target, regime.root)
    return _format_collision(regime, target)


def _target_error(exc: Exception, args) -> str:
    """A bad target, said in one line, with the names that WOULD have worked.

    "not found" is a dead end; the file's own function list is the fix, and it is one cheap AST
    read away. Wrong-name is the common miss (a stale qualname after a rename, `Class.method`
    written bare, a typo), and every one of those is answered by showing what is actually there.

    Never raises: this runs on the error path, and a formatter that throws replaces a bad-target
    message with a traceback about the bad-target message.
    """
    target = getattr(args, "target", None) or "?"
    if isinstance(exc, FileNotFoundError):
        return f"detective: no such file: {target} — the path is relative to --project-root"
    if isinstance(exc, SyntaxError):
        # An unparseable TARGET is the same class of user error as a misspelled one, and was
        # the last one still arriving as a raw traceback: Python's own SyntaxError render
        # (caret line included) reads as Detective crashing on itself. Name the file and the
        # line, and say plainly that nothing was measured — a partial number here would be
        # worse than none.
        where = f":{exc.lineno}" if exc.lineno else ""
        shown = exc.filename or _split_target(target, getattr(args, "project_root", None))[0]
        # Repo-relative, like every other path this CLI prints. `relpath` can raise across
        # drives, and this is the error path — fall back to what the exception carried.
        try:
            shown = os.path.relpath(shown, os.path.abspath(getattr(args, "project_root", ".") or "."))
        except (OSError, ValueError):
            pass
        return (
            f"detective: cannot parse {shown}{where} — {exc.msg or 'invalid syntax'}\n"
            "  nothing was measured; fix the file and re-run"
        )
    names: list[str] = []
    try:
        import ast as _ast

        from Wesker.ci import walk_functions

        root = os.path.abspath(getattr(args, "project_root", ".") or ".")
        file = _split_target(target, root)[0]
        full = file if os.path.isabs(file) else os.path.join(root, file)
        with open(full, encoding="utf-8") as fh:
            names = [qn for qn, _ in walk_functions(_ast.parse(fh.read(), filename=full))]
    except Exception:  # noqa: BLE001 — see "never raises" above
        names = []
    if not names:
        return f"detective: {exc}"
    shown = ", ".join(names[:12]) + (f", … (+{len(names) - 12} more)" if len(names) > 12 else "")
    return f"detective: {exc}\n  functions in that file: {shown}"


def main(argv: list[str] | None = None) -> int:
    """Run a command, then emit a lightweight memory-telemetry footer (human mode).
    The footer is best-effort: monitoring must never fail the actual work. It goes to
    STDERR — advisory monitoring, like progress — so STDOUT ends on the result banner and
    stays clean for piping."""
    # Local, like every other `certify` import here: the CLI defers that module so `--help`
    # and a bad target never pay for the engine's import graph.
    from .audit import AuditAccountingError
    from .certify import GeneratedSuiteCollision

    args = _build_parser().parse_args(argv)
    try:
        code = _run_live(args)
    except GeneratedSuiteCollision as exc:
        # A destination occupied by a file this target does not own (#61). It reached the
        # terminal as a traceback, which is the one shape a caller cannot distinguish from a
        # crash — and the refusal is the OPPOSITE of a crash: nothing was written precisely
        # because the guard worked. Both channels carry it, for the reason #57 gives: a
        # refusal only the human surface can see leaves every programmatic consumer with an
        # empty stdout and an exception it has to parse from stderr.
        if getattr(args, "json", False):
            print(
                json.dumps(
                    {
                        "verdict": "REFUSED",
                        "reason": "generated_suite_collision",
                        "detail": str(exc),
                    },
                    indent=2,
                )
            )
            return 1
        raise SystemExit(f"detective: {exc}") from exc
    except AuditAccountingError as exc:
        # An internal accounting inconsistency (#65) — the audit's value partition did not reconcile
        # with its classification. NOT a fact about the user's suite, and with the single-profile
        # reuse it should be unreachable; if it ever fires it is a Detective bug to report. Render a
        # clean typed refusal on both channels rather than leaking a raw traceback (the #65 UX).
        if getattr(args, "json", False):
            print(
                json.dumps(
                    {"verdict": "REFUSED", "reason": "audit_accounting_inconsistency", "detail": str(exc)},
                    indent=2,
                )
            )
            return 1
        raise SystemExit(f"detective: internal accounting inconsistency — please report this: {exc}") from exc
    except (LookupError, FileNotFoundError, SyntaxError) as exc:
        # A target that does not exist is a USER error, and it was reaching the terminal as a
        # 36-line Python traceback — the one shape a caller cannot tell from a crash. Every other
        # bad input here already exits clean (`_split_target`: "target must be 'file.py::function'"),
        # so these two were the gap, not the rule. The consumer that matters is a small model
        # driving refactors from this output: a traceback gives it nothing to route on, while
        # "not found · here are the names that ARE in the file" is the next action itself.
        raise SystemExit(_target_error(exc, args)) from exc
    # Telemetry is for a run you are DEBUGGING, not every run. It answered a question nobody
    # asked ("41 MB of a 2048 MB budget") on every invocation, and — being unbuffered stderr
    # written after a buffered stdout report — it surfaced ABOVE the result it postdates,
    # reading as a header. Behind --verbose, where someone chasing memory will look for it.
    if getattr(args, "verbose", False) and not getattr(args, "json", False):
        try:
            from Wesker.memory_guard import telemetry

            sys.stderr.write(f"  [{telemetry()}]\n")
        except Exception:  # noqa: BLE001 — telemetry is advisory, never fatal
            pass
    return code


def hang_watchdog_seconds(session_budget_s: float | None) -> float:
    """The preemptive-backstop deadline for a whole live-session run (#hang — pure, pinned).

    NOT a budget — a DEADLOCK catcher. The cooperative trace/per-test budgets cannot fire while the
    main thread is blocked OUTSIDE the interpreter (a test in a subprocess / socket / C-extension that
    ``interrupt.abandon`` cannot stop — see the converge-hang investigation), so a WALL-CLOCK backstop
    is the only thing that can end an infinite hang. Sized to NEVER fire on a legitimate run: twice the
    session trace budget plus a fixed margin for mutant evaluation and synthesis. An unbounded (None or
    ``<= 0``) session budget has no proportional bound, so it degrades to a large fixed backstop.
    """
    if session_budget_s and session_budget_s > 0:
        return session_budget_s * 2.0 + 600.0
    return 3600.0


class _hang_watchdog:
    """Arm a PREEMPTIVE wall-clock backstop around a live-session run (#hang).

    ``faulthandler.dump_traceback_later`` runs a C-level timer thread that fires even when the Python
    main thread is DEADLOCKED — unlike any cooperative budget, which can only be checked between steps
    the stuck thread never reaches. On expiry it dumps EVERY thread's stack to stderr (the diagnosis of
    WHERE it hung) and hard-exits, turning an infinite hang into a bounded, debuggable failure.
    Cancelled on normal completion, so a fast run leaves no timer armed. The deadline is
    :func:`hang_watchdog_seconds` — a backstop sized never to fire on a legitimate run.
    """

    def __init__(self, seconds: float) -> None:
        self._seconds = seconds
        self._armed = False

    def __enter__(self) -> _hang_watchdog:
        # `dump_traceback_later` writes to a file that must have a real ``fileno()``. Under pytest
        # capture (or any redirected stderr) it does not, so arming would raise — and a BACKSTOP must
        # never break the run it guards. Arm only when stderr is a real stream: the watchdog matters
        # in production (a terminal/pipe with an fd), not under a harness whose runs cannot hang.
        try:
            import faulthandler
            import sys

            sys.stderr.fileno()
            faulthandler.dump_traceback_later(self._seconds, exit=True)
            self._armed = True
        except Exception:  # noqa: BLE001 — a backstop degrades silently; it never fails the run
            self._armed = False
        return self

    def __exit__(self, *exc: object) -> bool:
        if self._armed:
            import faulthandler

            faulthandler.cancel_dump_traceback_later()
        return False


def _run_live(args) -> int:
    """Run the command inside a LIVE pytest session, so profiling sees the REAL suite.

    Wesker's default discovery collects with ``--collect-only``, which tears the session
    down immediately — every fixture-taking test is then SKIPPED because its fixtures can
    no longer be supplied. For Detective that is not a speed issue but a correctness one:
    a mutant that only a fixture-taking test could kill is reported as a surviving
    behavioral gap, so the diagnosis claims a dimension is unspecified when the suite
    already pins it, and a warrant-classed test gets synthesised for behavior that was
    never unspecified. On a fixture-heavy target that is most of the suite (measured on
    Prism: 0 of 445 tests bound the old way, 445 the new way).

    ONE wrap upgrades everything underneath: ``Wesker.ci.run_with_live_suite`` publishes
    the live suite to Wesker's own discovery, so ``profile_function`` and ``suite_edit``
    keep calling ``discover_test_callables`` with unchanged signatures and simply receive
    real, runnable tests. The inversion of control is pytest's — the loop cannot be handed
    out and left open — which is exactly why it is wrapped here once rather than
    re-derived at each call site.

    ``purge`` runs no tests, so it never pays for a session. Degrading is LOUD: silently
    falling back to the weaker discovery is what makes a well-tested suite look
    under-specified.
    """
    root = getattr(args, "project_root", None)
    # `purge` runs no tests; `regime` READS the setup and must answer even when that setup is
    # what is broken — opening a live session to report that a live session cannot open would
    # be the one command guaranteed to fail exactly when it is needed.
    if getattr(args, "command", None) in _STATIC_COMMANDS or not root:
        return _run(args)
    context = _execution_context()
    if context.disposition == "wrong_interpreter":
        detail = _format_execution_refusal(context)
        if getattr(args, "json", False):
            return _emit_json(
                {
                    "verdict": "REFUSED",
                    "reason": "wrong_interpreter",
                    "active_environment": context.active_environment,
                    "executable": context.executable,
                    "detail": detail.strip(),
                },
                2,
            )
        sys.stderr.write(detail)
        return 2
    # Resolve the testing regime BEFORE the session — the session is the expensive part, and
    # tracing a suite that cannot reach the target is the longest possible way to learn nothing.
    # Refuse rather than warn: a warning above a plausible report is read as a footnote, and the
    # report underneath says "0 tests cover this", which is exactly the sentence that sends
    # someone off to write a suite against a copy nobody runs.
    target_arg = getattr(args, "target", None)
    regime = None
    if target_arg:
        try:
            from .regime import resolve_regime

            regime = resolve_regime(root, _split_target(target_arg, root)[0])
            if regime.conflicts and not getattr(args, "json", False):
                sys.stdout.write(_format_conflicts(regime, target_arg))
                return 2
        except SystemExit:
            raise
        except Exception:  # noqa: BLE001 — a guard must never be what breaks the run
            pass
    try:
        from Wesker.ci import run_with_live_suite
    except ImportError:  # older Wesker without the live-session seam
        return _run(args)

    # The file under analysis, so the suite-global baseline is traced once for it
    # rather than re-derived per profiled function.
    targets: list[str] | None = None
    if target_arg:
        try:
            targets = [_split_target(target_arg, root)[0]]
        except Exception:  # noqa: BLE001 — a command whose target isn't file::function
            targets = None

    # The suite-global baseline is traced HERE, before `_run` — so this callback, not the one
    # `diagnose` gets, is what makes the first (and on a large suite, longest) phase visible.
    # Without it the live path is silent at 100% CPU until the first mutant, which is the whole
    # "looks hung" failure one layer further up than it looked.
    label = _split_target(target_arg, root)[1] if target_arg else "baseline"

    # Collect only the test files that could execute the target's lines. The session baseline
    # traces EVERYTHING it collects, before a single mutant runs, so an unscoped collection
    # makes the cost scale with the SUITE rather than the function: measured on Regenesis,
    # 2134 test functions traced for one 13-line function, of which 1928 are in modules that
    # cannot import the target even transitively. `paths` is pytest's own collection argument,
    # so the scoping happens before anything is imported, not after everything is traced.
    # `None` (analysis unsure, or no target) collects everything — byte-identical to before.
    paths = _reachable_paths(
        root,
        targets,
        target_module=regime.module if regime is not None else None,
        import_roots=regime.suite_path if regime is not None else (),
        # Bound the collection to pytest's declared testpaths: the authoritative fix for a repo-walk
        # admitting an installed dependency's suite (ARC: 736 `.venv312` test_*.py). Empty when
        # undeclared, which leaves today's whole-tree behaviour untouched.
        testpaths=regime.testpaths if regime is not None else (),
    ).paths
    # `--trace-budget` / `--trace-session-budget` bound the pass that traces the whole suite, and
    # on the live path that pass runs HERE — inside the seam — not in `profile`. Sent only to
    # `profile`, they reached the per-function baseline the live path never uses, so raising them
    # changed nothing and the phase stayed capped at the engine's default: a documented opt-out
    # that could not reach the thing it opts out of.
    diagnostic: dict[str, Any] = {}
    # Call the seam ONCE. The previous `except TypeError` ladder feature-detected an older Wesker
    # by RE-RUNNING the body — but `_run(args)` writes tests, and an ordinary TypeError raised
    # INSIDE it (not a signature mismatch) was indistinguishable from an old signature, so the
    # body replayed up to three times, repeating its writes. The published Detective/Wesker pair is
    # version-pinned to a matched seam (pyproject floor + uv.lock), so a signature mismatch is a
    # broken install that must fail LOUDLY here rather than be silently retried; the `ImportError`
    # above still degrades a MISSING seam. An internal TypeError now propagates on the first call.
    # Preemptive backstop: the in-process live session runs arbitrary consumer tests, and one that
    # blocks OUTSIDE the interpreter cannot be stopped by the cooperative trace budgets (they check
    # between steps the stuck main thread never reaches). The wall-clock watchdog fires regardless and
    # dumps stacks, so a deadlock fails LOUD and bounded instead of hanging (see the converge-hang
    # investigation). Sized never to fire on a real run.
    with _hang_watchdog(hang_watchdog_seconds(_trace_session_budget(args))):
        code = run_with_live_suite(
            root,
            lambda: _run(args),
            target_files=targets,
            paths=paths,
            trace_progress=_stream_trace_progress(label),
            trace_budget_s=_trace_budget(args),
            trace_session_budget_s=_trace_session_budget(args),
            diagnostic=diagnostic,
        )
    if code is None:
        sys.stderr.write(_format_session_warning(diagnostic, project_root=root))
        reason = str(diagnostic.get("reason", "") or "")
        # REFUSE the legacy fallback on a collection ERROR (#66). `empty_collection` — the project
        # genuinely has no test for this target — legitimately falls through to a from-scratch
        # measurement; converge exists for exactly that. But `collection_errors` means tests EXIST
        # and could not be collected: a conftest/config that failed to LOAD, typically a missing
        # dependency named in the warning above. Measuring against the zero tests that survived that
        # failure and printing "0 pinned · converge from scratch" is the misdirection this issue
        # closes — the fix is to repair the environment, not to author a suite. So nothing is
        # measured and the command exits non-zero, and a `--json` caller gets a typed refusal.
        if reason == "collection_errors":
            if getattr(args, "json", False):
                return _emit_json(
                    {
                        "verdict": "REFUSED",
                        "reason": "collection_errors",
                        "detail": "suite could not be collected — nothing measured; fix and re-run",
                    },
                    2,
                )
            sys.stderr.write(
                "  REFUSED: the suite could not be collected, so nothing was measured — "
                "fix the error above and re-run.\n"
            )
            return 2
        # CARRY THE REASON PAST THE FALLBACK. This warning used to be the only trace that the
        # suite never ran: `diagnostic` is a local, `_run` takes only `args`, and the renderer
        # far below therefore re-derived a narrower proxy and told the reader to pass `--input`
        # into a suite that collects nothing. `args` is the thread that already reaches every
        # command, so the measured cause travels with it instead of dying at this line.
        args.session_reason = reason
        return _run(args)
    sys.stderr.write(_format_uncollected(diagnostic, paths, root))
    return code


def _format_uncollected(diagnostic: dict[str, Any], paths: list[str] | None, root: str) -> str:
    """Name the reachable test files that never collected — "" when none did.

    The session SURVIVING a collection error is what `--continue-on-collection-errors` bought,
    and unreported it is a downgrade dressed as a fix: one broken import used to zero the
    collection and fire a loud warning, and now 41 of 44 files bind while the 3 holding the
    target's tests are dropped in silence, under a confident `0 pinned`. Measured on
    TailChasingFixer, whose 11 stale imports are an ordinary amount of drift. A file that never
    collected contributes no tests, so every mutant its tests would have killed reads as an
    unpinned behaviour — and a caller acting on that writes tests for behaviour already pinned.

    REACHABLE errors only, which is the whole reason this is Detective's job and not Wesker's.
    Most collection errors are in files that could never execute the target: real, and noise
    here. `_reachable_paths` already computed the set that could, and an error inside THAT set is
    the only kind that can cost a kill. Warning about the rest would train a reader to ignore the
    warning — which is how the loud-degrade discipline dies.

    Advisory, on stderr, and NOT a refusal: unlike a shadowed target, the measurement is still
    honest about what it measured, and a partial floor is the normal state of a drifted repo. It
    reads as a footnote to a number, which is exactly its weight — the number may be low because
    of this. Silence would let it read as a finding.
    """
    errors = diagnostic.get("errors") or []
    if not errors:
        return ""
    reachable = {os.path.abspath(p) for p in paths} if paths else None
    hits = [
        nodeid
        for nodeid, _ in errors
        # nodeid for a module-level collection failure IS the rootdir-relative path. `paths=None`
        # means the analysis declined to scope, so every collected file was reachable-by-default
        # and every error is a candidate — the same "any doubt, include it" rule that produced it.
        if reachable is None or os.path.abspath(os.path.join(root, str(nodeid).split("::")[0])) in reachable
    ]
    if not hits:
        return ""
    shown = "\n".join(f"           {n}" for n in hits[:3])
    more = f"\n           … and {len(hits) - 3} more" if len(hits) > 3 else ""
    return (
        f"WARNING: {len(hits)} test file(s) that could reach this target FAILED TO COLLECT, so\n"
        f"         their tests never ran. Behaviour they pin will read as unpinned below.\n"
        f"{shown}{more}\n"
        f"         Fix the import(s), or re-run once they collect, before trusting a gap.\n"
    )


# Config-option / import signatures that name the pytest PLUGIN a `--strict-config` repo needs. Such
# a repo carries the plugin's ini option (`asyncio_default_fixture_loop_scope`) or marker, and pytest
# refuses the WHOLE config when the plugin is absent — so NOTHING collects and "install the
# dependencies" is too vague to act on. Conservative: only unambiguous signatures. Found dogfooding
# structlog (needs pytest-asyncio for its config to load at all).
_PLUGIN_SIGNATURES: tuple[tuple[str, str], ...] = (
    ("asyncio", "pytest-asyncio"),
    ("django_settings", "pytest-django"),
    ("django settings", "pytest-django"),
    ("trio", "pytest-trio"),
    ("tornado", "pytest-tornado"),
    ("twisted", "pytest-twisted"),
    ("codspeed", "pytest-codspeed"),
    ("benchmark", "pytest-benchmark"),
    ("playwright", "pytest-playwright"),
)


def plugin_hint(blob: str) -> str:
    """The specific package a pytest config/collection error says is missing (#, pure — pinned).

    ``no module named 'X'`` names X directly (the general case); otherwise a known config-option or
    marker signature names its plugin (`asyncio_*` -> ``pytest-asyncio``). ``""`` when nothing is
    recognised, so the caller keeps the generic "install the project's dependencies" guidance rather
    than guess. A ``--strict-config`` repo refuses its WHOLE config when a plugin it declares an ini
    option for is absent, so this is what turns "install something" into "install THIS".
    """
    low = blob.lower()
    marker = "no module named "
    if marker in low:
        rest = low.split(marker, 1)[1].lstrip(" '\"")
        mod = ""
        for ch in rest:
            if ch.isalnum() or ch in "._-":
                mod += ch
            else:
                break
        if mod:
            return mod.split(".")[0].replace("_", "-")
    for needle, plugin in _PLUGIN_SIGNATURES:
        if needle in low:
            return plugin
    return ""


def install_extra_target(extras: list[str]) -> str:
    """Which ``.[extra]`` a missing-dependency install command should name (pure — pinned).

    The advice installs the project into the interpreter that runs the suite, so the extra it
    names must be DECLARED in that project or the copied command errors — a project with a
    ``dev`` extra but no ``test`` extra (the common case, e.g. ARC_AGI_3) breaks on a guessed
    ``.[test]``. Chosen from what the pyproject ACTUALLY declares, not from a convention:

      a test-ish extra ('test'/'tests'/'testing') is declared -> ".[<that exact name>]"
      else a dev-ish extra ('dev'/'develop'/'development')     -> ".[<that exact name>]"
      else (no test/dev extra, or none declared)               -> "."  (bare — core deps only)
    """
    by_lower = {e.lower(): e for e in extras}
    for cand in ("test", "tests", "testing"):
        if cand in by_lower:
            return f".[{by_lower[cand]}]"
    for cand in ("dev", "develop", "development"):
        if cand in by_lower:
            return f".[{by_lower[cand]}]"
    return "."


def _declared_extras(project_root: str | None) -> list[str]:
    """The ``[project.optional-dependencies]`` extra names in the project's pyproject.toml, or
    ``[]`` when there is no readable/parseable pyproject — the advice then falls back to a bare
    ``-e .`` rather than naming an extra that may not exist.
    """
    if not project_root:
        return []
    try:
        import tomllib

        with open(os.path.join(project_root, "pyproject.toml"), "rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError):
        return []
    project = data.get("project", {})
    opt = project.get("optional-dependencies", {}) if isinstance(project, dict) else {}
    return list(opt) if isinstance(opt, dict) else []


def _ready_venv(project_root: str | None, module: str) -> str | None:
    """A sibling virtualenv under ``project_root`` that can ALREADY run detective's live suite for
    this target — it has the missing ``module``, pytest, AND a ``detective`` console script — or
    ``None``.

    Requiring all three is the point. A runtime-only venv that has the module but not pytest or
    detective CANNOT run the suite, so recommending it would send the user in a circle — the exact
    bug the ARC_AGI_3 end-to-end run caught: ``.venv`` had ``arc_agi`` but no pytest/detective, while
    ``.venv312`` had all three. This lets the advice say "run detective from ``.venv312`` — the deps
    are already there" instead of telling the user to install into detective's OWN interpreter (the
    accurate fix when detective was invoked from outside the project's environment). Filesystem check
    only, never a subprocess, so it cannot hang a session that is already failing.
    """
    if not project_root or not module:
        return None
    import glob

    mod_dir = module.replace("-", "_").split(".")[0]
    candidates = glob.glob(os.path.join(project_root, ".venv*")) + glob.glob(
        os.path.join(project_root, "venv")
    )
    for venv in sorted(candidates):
        if not os.path.isfile(os.path.join(venv, "bin", "python")):
            continue
        if not os.path.isfile(os.path.join(venv, "bin", "detective")):
            continue  # we recommend `<venv>/bin/detective` — it must actually be runnable there
        for site in glob.glob(os.path.join(venv, "lib", "python*", "site-packages")):
            has_module = os.path.isdir(os.path.join(site, mod_dir)) or os.path.isfile(
                os.path.join(site, mod_dir + ".py")
            )
            if has_module and os.path.isdir(os.path.join(site, "pytest")):
                return venv
    return None


def _format_session_warning(diagnostic: dict[str, Any], project_root: str | None = None) -> str:
    """Render the "no live pytest session" fallback warning with the actual reason.

    Wesker's ``run_in_session`` populates ``diagnostic["reason"]`` with one of
    ``pytest_missing`` / ``collection_errors`` / ``empty_collection`` /
    ``pytest_crashed`` (or leaves it empty on older Wesker). The old catch-all
    "pytest missing, or collection failed" sent users chasing the wrong fix
    for hours when the true cause was a duplicate ``conftest`` importable name
    in a ``mutants/`` shadow tree. This surfaces the actual reason and, for
    collection errors, shows the first three failing nodeids with the fix hint.
    """
    reason = diagnostic.get("reason", "unknown")
    if reason == "pytest_missing":
        have_venv = _ready_venv(project_root, "pytest")
        if have_venv:
            return (
                "WARNING: pytest is not importable in the interpreter that runs the live suite,\n"
                f"         but it IS installed in `{have_venv}`. Run detective from THAT environment\n"
                f"         (e.g. `{have_venv}/bin/detective …`) rather than this interpreter.\n"
            )
        install = shlex.join(["uv", "pip", "install", "--python", sys.executable, "pytest"])
        return (
            "WARNING: pytest is not importable in the interpreter that runs the live suite.\n"
            f"         Install it in that exact interpreter: `{install}`.\n"
        )
    if reason == "collection_errors":
        errors = diagnostic.get("errors", [])
        header = (
            f"WARNING: pytest collection failed with {len(errors)} error(s); the live suite\n"
            "         could not start. Fixture-taking tests cannot run, so surviving DOF\n"
            "         may be overstated. First failures:\n"
        )
        lines = []
        for nodeid, detail in errors[:3]:
            first_line = detail.strip().splitlines()[0][:200] if detail.strip() else "(no detail)"
            lines.append(f"           · {nodeid}: {first_line}\n")
        tail = ""
        if len(errors) > 3:
            tail = f"           ... and {len(errors) - 3} more.\n"
        # A conftest/config that failed to IMPORT (a missing dependency) is fixed by INSTALLING the
        # project, not by pruning testpaths — pointing there sends the user chasing the wrong thing
        # for hours (#66). Detect the import signature and give the accurate remedy.
        blob = " ".join(f"{n} {d}" for n, d in errors).lower()
        pkg = plugin_hint(blob)
        is_import = any(s in blob for s in ("modulenotfound", "importerror", "no module named"))
        if is_import:
            # (usability, ARC_AGI_3 repro) If the missing module ALREADY lives in a sibling venv,
            # the fix is to run detective from THAT interpreter, not to install into this one — the
            # accurate remedy when detective was invoked from outside the project's environment.
            have_venv = _ready_venv(project_root, pkg) if pkg else None
            if have_venv:
                hint = (
                    "         This is an IMPORT failure loading a conftest/config. The missing\n"
                    f"         module is ALREADY installed in `{have_venv}`, but detective is running\n"
                    "         under a DIFFERENT interpreter. Re-run detective from that environment\n"
                    f"         (e.g. `{have_venv}/bin/detective …`) — nothing needs installing.\n"
                )
            else:
                # Name the project's ACTUAL declared extra, not a guessed `.[test]` that may not
                # exist (a project with a `dev` extra but no `test` extra breaks the copied command).
                target = install_extra_target(_declared_extras(project_root))
                install_project = shlex.join(
                    ["uv", "pip", "install", "--python", sys.executable, "-e", target]
                )
                hint = (
                    "         This is an IMPORT failure loading a conftest/config, not a discovery\n"
                    "         problem: install the project's dependencies in this exact interpreter\n"
                    f"         (`{install_project}`), then re-run. Adjusting `testpaths` will not\n"
                    "         fix it.\n"
                )
                # Turn "install something" into "install THIS": a --strict-config repo refuses its
                # whole config when a plugin it declares an ini option for is absent, so name it.
                if pkg:
                    install_plugin = shlex.join(["uv", "pip", "install", "--python", sys.executable, pkg])
                    hint += (
                        f"         Likely missing: `{pkg}` — `{install_plugin}` (or install the\n"
                        "         project's declared extra), then re-run.\n"
                    )
        elif pkg:
            install_plugin = shlex.join(["uv", "pip", "install", "--python", sys.executable, pkg])
            hint = (
                f"         Pytest rejected a config/marker owned by `{pkg}`. Install that plugin\n"
                f"         in this exact interpreter: `{install_plugin}`, then re-run.\n"
            )
        else:
            hint = (
                '         Common fix: set `[tool.pytest.ini_options] testpaths = ["tests"]`\n'
                "         in pyproject.toml to exclude generated / mutants / shadow trees.\n"
            )
        return header + "".join(lines) + tail + hint
    if reason == "empty_collection":
        return (
            "WARNING: pytest collected no tests — the live suite has nothing to run.\n"
            "         Check `testpaths` / conftest / discovery patterns.\n"
        )
    if reason == "pytest_crashed":
        return (
            "WARNING: pytest raised an unexpected exception during collection.\n"
            "         Falling back to collect-only discovery; fixture-taking tests cannot run.\n"
        )
    # `unknown` covers older Wesker without diagnostic support: keep the original
    # legacy message so the fallback still tells the user what happened.
    return (
        "WARNING: no live pytest session (pytest missing, or collection failed /\n"
        "         collected nothing). Falling back to collect-only discovery:\n"
        "         fixture-taking tests cannot run, so surviving DOF may be overstated.\n"
    )


def _format_rewrite(r) -> str:
    """The rewrite-verification report (issue #37): verdict first, then the evidence behind it."""
    icon = {
        "PRESERVED": "✓",
        "CHANGED": "✗",
        "UNREVIEWED": "⚠",
        "ABSTAIN": "⚠",
        "STALE_RECEIPT": "·",
        "INVALID_RECEIPT": "✗",
    }
    lines = [_RULE, f"{r.function} — verify-rewrite: {icon.get(r.verdict, '·')} {r.verdict}", ""]
    lines.append(_row("· proof replay", f"the original suite ran {r.proof_replayed} on the rewritten source"))
    if r.new_dimensions:
        lines.append(
            _row("⚠ new dimensions", f"{len(r.new_dimensions)} behaviour(s) the original proof never covered")
        )
    # The old-vs-new differences are the load-bearing evidence — a proven behaviour change at a
    # concrete input, not "no witness found". Show them (deduped, capped); full set in --json.
    if r.differences:
        lines.append(_row("✗ old ≠ new", f"{len(r.differences)} input(s) where the implementations disagree"))
        for d in r.differences[:6]:
            lines.append(_row("", d))
        if len(r.differences) > 6:
            lines.append(_row("", f"(+{len(r.differences) - 6} more — all in --json)"))
    if r.abstentions:
        lines.append(_row("· abstained", f"{len(r.abstentions)} input(s) could not be safely compared"))
    lines.append("")
    verdict_msg = {
        "PRESERVED": (
            "DONE:  behaviour preserved — the rewrite passes the original obligations, adds no new\n"
            "       dimension, and matches old-vs-new at every tested input."
        ),
        "CHANGED": (
            "STOP.  behaviour CHANGED — an original obligation failed, or old and new disagree at\n"
            "       some input. This is not a behaviour-preserving rewrite."
        ),
        "UNREVIEWED": (
            "STOP.  the rewrite adds behaviour the original proof never reviewed. Converge and review\n"
            "       the new dimension(s), or narrow the rewrite — do not assume preservation."
        ),
        "ABSTAIN": (
            "STOP.  old vs new could not be compared at every point — treat as unproven; review by hand."
        ),
        "STALE_RECEIPT": (
            "DONE:  nothing was rewritten — the current source is identical to the receipt's original."
        ),
        "INVALID_RECEIPT": (
            "STOP.  this receipt does not apply to the requested target — wrong function, or a\n"
            "       corrupt/foreign receipt. No preservation claim was made; see the reason below."
        ),
    }
    lines.append(verdict_msg.get(r.verdict, ""))
    if r.note:
        lines.append(f"       {r.note}")
    return "\n".join(lines)


def _run_decompose(args, file, function) -> int:
    from .decompose_apply import apply_decomposition

    supplied = (
        _parse_supplied_inputs(args.input, _target_ns(file, function, args.project_root))
        if getattr(args, "input", None)
        else None
    )
    result = apply_decomposition(
        file,
        function,
        args.project_root,
        write=args.apply,
        supplied_inputs=supplied,
        deadline_s=args.deadline,
        two_sign=getattr(args, "two_sign", False),
        # decompose's work IS a converge plus a trial-apply per candidate — the slowest
        # command in the CLI, and until now the only one that printed nothing while it ran.
        notify=None if args.json else _notify_stderr,
    )
    if args.json:
        return _emit_json(asdict(result), 3 if getattr(result, "budget_exhausted", False) else 0)
    text = _format_decompose(result, args.apply, args.target, args.project_root)
    # Persist the full outcome — especially a REFUSAL, which otherwise leaves no
    # artifact and can only be re-diagnosed by re-running the slowest command here.
    #
    # The FILE is the full artifact and the terminal stays minimal — the split
    # converge already makes (`_format_converge_terse` to the screen, the complete
    # `_format_converge` to disk). Decompose printed and persisted the SAME string,
    # so "full report" named a byte-identical copy of what the reader had just
    # scrolled past, and the one command that promises more delivered less. The
    # proof run is where the detail lives: per-pass, every survivor, the generated
    # source. Absent on a refusal that never got to converge, and then the outcome
    # text is genuinely all there is.
    detail = text
    if getattr(result, "proof", None) is not None:
        detail = "\n".join(
            [
                text,
                "",
                _RULE,
                "PROOF RUN — the converge this decomposition was validated against",
                _RULE,
                _format_converge(result.proof, show_tests=True),
            ]
        )
    rel = _write_converge_report(args.project_root, function, detail, prefix="decompose")
    if rel:
        _notify_stderr(f"full report: {rel}")
    print(text)
    # 3 on a CUT proof (issue #31), mirroring converge: the run did not complete its
    # proof within the wall, so CI must tell it apart from a clean "nothing to decompose".
    return 3 if getattr(result, "budget_exhausted", False) else 0


def _run_audit(args, file, function) -> int:
    from .audit import audit_suite

    if getattr(args, "plan", False):
        # The mutation-budget decision WITHOUT paying for it (issue #52): tier 0 static + tier 1
        # trace (fan-in, coverage) + a MEASURED tier-2 estimate, then exit before mutating.
        from .audit import mutation_estimate_seconds
        from .engine import _resolve, trace_tier
        from .parsimony_map import read_function

        _root = os.path.abspath(args.project_root)
        _full = file if os.path.isabs(file) else os.path.join(_root, file)
        try:
            with open(_full, encoding="utf-8") as _fh:
                _qn, _node = _resolve(ast.parse(_fh.read()), function)
            _static = read_function(_node, function).detail if _node is not None else ""
        except (OSError, SyntaxError):
            _static = ""
        tier1 = trace_tier(file, function, args.project_root, trace_progress=_stream_trace_progress(function))
        est_s = mutation_estimate_seconds(tier1.mutant_count, _read_per_mutant_ms())
        if args.json:
            return _emit_json(
                {
                    "kind": "audit-plan",
                    "note": "schedule (advisory) — tiers 0-1 measured, tier 2 estimated, not mutated",
                    "function": tier1.function,
                    "tier0_static": _static or None,
                    "tier1": {
                        "tests_reaching": tier1.tests_reaching,
                        "tests_total": tier1.tests_total,
                        "covered_lines": tier1.covered_lines,
                        "executable_lines": tier1.executable_lines,
                    },
                    "tier2": {"mutant_count": tier1.mutant_count, "estimate_seconds": est_s},
                },
                0,
            )
        print(_format_audit_plan(function, _static, tier1, est_s))
        return 0

    # Tier 0 first (issue #52): the ~0s static read, streamed the instant the file parses, so
    # audit shows a grounded first line immediately instead of a dead terminal — then the trace
    # (tier 1) and mutation (tier 2) heartbeats follow, each carrying its own warrant.
    _print_tier0_static(file, function, args.project_root)
    report = audit_suite(
        file,
        function,
        args.project_root,
        progress=_stream_progress(function),
        trace_progress=_stream_trace_progress(function),
        two_sign=getattr(args, "two_sign", False),
    )
    # CI ratchet (issues #35, #50): --check makes a SPECIFICATION gap an enforceable process
    # result (exit 1), but a MEASUREMENT limit (an unclassified survivor the search could not
    # evaluate) is surfaced, never fatal by default — only --check-strict gates on it (exit 2).
    # The gate is embedded in --json so a pipeline branches on the field, not the exit code alone.
    check = getattr(args, "check", False) or getattr(args, "check_strict", False)
    strict = getattr(args, "check_strict", False)
    payload = asdict(report)
    if check:
        from .audit import audit_check_failed, audit_gate_exit, audit_measurement_incomplete

        spec_gap = audit_check_failed(
            len(report.killable_gaps),
            len(report.missing_lines),
            len(report.failing_tests),
            getattr(report, "authored_fence", 0),  # Q8: an unenforced must-not is a spec gap
        )
        meas_incomplete = audit_measurement_incomplete(report.unclassified)
        gate_exit = audit_gate_exit(spec_gap, meas_incomplete, strict)
        payload["gate"] = {
            "spec_gap": spec_gap,
            "measurement_incomplete": meas_incomplete,
            "unmeasured": {"unclassified": report.unclassified},
            "strict": strict,
            "exit": gate_exit,
        }
    print(
        json.dumps(_with_exit(payload, gate_exit if check else 0), indent=2, default=str)
        if args.json
        else _format_audit(report, removing=bool(args.remove and report.redundant_tests))
    )
    if check:
        if meas_incomplete and not spec_gap:
            # Surfaced always; fatal only under --check-strict (audit_gate_exit). A shorter search
            # is a measurement limit, not a finding — the default gate stays a claim about the code.
            print(
                f"  ⚠ measurement incomplete — {report.unclassified} survivor(s) the equivalence "
                "search could not classify; NOT a specification gap. Use --check-strict to gate on it.",
                file=sys.stderr,
            )
        return gate_exit
    if args.remove and report.redundant_tests:
        from .audit import module_safe_removals
        from .suite_edit import apply_removals

        # The redundant set is single-function evidence; deletion is a
        # module-level act. Filter against every sibling in the file first —
        # a test pointless for THIS function can be the only killer of a
        # sibling's mutant (the post-decompose wrapper case).
        safe, retained = module_safe_removals(file, function, args.project_root, list(report.redundant_tests))
        for name, sibling in sorted(retained.items()):
            # Honest about WHAT the sibling check verified (issue #54): it confirms the test still
            # contributes a kill/line to `sibling` — NOT that `sibling` is itself specified. If
            # `sibling` is far from complete, "still contributes" is a weaker guarantee than "pins".
            print(
                f"  retained {name} — still contributes kills/lines to {sibling} "
                f"({sibling}'s own completeness unknown)"
            )
        result = apply_removals(file, args.project_root, list(safe))
        if result.removed:
            print(f"  removed {len(result.removed)}: {', '.join(result.removed)}")
        if result.not_found:
            # An explicit scope RULE, not a shrug (issue #54): --remove edits only tests Detective
            # can attribute to this function's own file. A candidate elsewhere (a test of another
            # function that traverses this one) is out of scope — never a deletion candidate,
            # regardless of file layout, so it was protected by policy, not by accident.
            print(
                f"  skipped {len(result.not_found)} — outside this function's editable test scope "
                "(--remove edits only its own test file, never a cross-file test): "
                f"{', '.join(result.not_found)}"
            )
        if result.parametrized:
            print(
                f"  parametrized case(s) — rows of a live test, not removable as "
                f"functions; prune the @parametrize row(s) yourself: "
                f"{', '.join(result.parametrized)}"
            )
        if result.removed:
            # Re-audit so the user sees the suite is still complete after pruning.
            after = audit_suite(file, function, args.project_root, two_sign=getattr(args, "two_sign", False))
            print(
                f"  after removal: {after.test_count} test(s), "
                f"complete={after.complete}, minimal cover={after.minimal_test_count}"
            )
            print(f"DONE:  removed {len(result.removed)} test(s); the suite above is what remains.")
        else:
            # Issue #10: the requested action RAN and retained everything — say why and
            # stop. Repeating `audit --remove` here instructs the user to re-run a
            # command that just proved itself a no-op.
            why = (
                ", ".join(
                    p
                    for p in (
                        f"{len(retained)} still contribute to a sibling" if retained else "",
                        f"{len(result.parametrized)} are parametrized rows (report-only)"
                        if result.parametrized
                        else "",
                        f"{len(result.not_found)} outside this function's editable test scope"
                        if result.not_found
                        else "",
                    )
                    if p
                )
                or "no candidate was safely removable"
            )
            print(f"DONE:  removed nothing — {why}. Every test is retained; the suite stands.")
    return 0


def _run_converge(args, file, function) -> int:
    from .converge import converge

    supplied = (
        _parse_supplied_inputs(args.input, _target_ns(file, function, args.project_root))
        if getattr(args, "input", None)
        else None
    )
    from .capabilities import parse_env

    try:
        _env = parse_env(getattr(args, "env", None) or [])
    except ValueError as exc:
        print(f"detective: {exc}", file=sys.stderr)
        return 2
    result = converge(
        file,
        function,
        args.project_root,
        write_dir=args.write_dir,
        max_iterations=args.max_iterations,
        supplied_inputs=supplied,
        clock=args.clock,
        env=_env,
        receiver_factory=getattr(args, "receiver_factory", None),
        fast=args.fast,
        deadline_s=args.deadline,
        include_shaped=args.include_shaped,
        two_sign=args.two_sign,
        progress=_stream_progress(function),
        notify=_notify_stderr,
    )
    if args.json:
        # 3 for either invalid-measurement stamp: a stale target (issue #17) or a
        # deadline CUT (issue #31) both mean "this run's numbers are partial — re-run".
        return _emit_json(
            asdict(result),
            3
            if result.stale_target
            or result.budget_exhausted
            or (result.verification is not None and not result.verification.ok)
            else 0,
        )
    # The full report always goes to a readable file; the terminal stays minimal
    # (a banner + the one quick action) unless --full is asked for. The FILE is always
    # verbose — it is the archive `flag` reads mutant ids out of, and a file has no
    # scrolling cost. The terminal groups unless --verbose, so the two are rendered
    # separately rather than sharing one string.
    qn = result.function.split("::")[-1]
    report_path = _write_converge_report(
        os.path.abspath(args.project_root), qn, _format_converge(result, show_tests=True, verbose=True)
    )
    if args.full:
        print(_format_converge(result, show_tests=True, verbose=args.verbose))
    else:
        print(
            _format_converge_terse(
                result,
                report_path,
                args.project_root,
                getattr(args, "session_reason", ""),
                tuple(getattr(args, "input", ()) or ()),
            )
        )
    # 3, not 1: "the measurement is invalid, re-run" is a different failure
    # from "the run errored", and CI that gates on converge needs to tell
    # them apart (issue #17). A deadline CUT (issue #31) is the same class of
    # invalid-measurement signal — partial evidence, re-run with more budget.
    return (
        3
        if result.stale_target
        or result.budget_exhausted
        or (result.verification is not None and not result.verification.ok)
        else 0
    )


def _run_flag_line(args, file, function) -> int:
    from Wesker.ci import walk_functions as _walk

    from .line_flags import add_line_flag, clean_orphaned_flags, flag_statuses, remove_line_flag

    root_abs = os.path.abspath(args.project_root)
    full = file if os.path.isabs(file) else os.path.join(root_abs, file)
    try:
        with open(full, encoding="utf-8") as fh:
            node = next((n for qn, n in _walk(ast.parse(fh.read())) if qn == function), None)
    except (OSError, SyntaxError) as exc:
        print(f"detective: cannot read {file}: {exc}")
        return 1
    if node is None:
        print(f"detective: function '{function}' not found in {file}")
        return 1
    # THE ledger identity — issue #9 round 2: audit/converge key on the
    # root-relative path, so `./pkg/mod.py`, an absolute path, and `pkg/mod.py`
    # must all land on one record, not three.
    func_key = f"{os.path.relpath(full, root_abs)}::{function}"

    if args.list or args.clean:
        if args.list:
            statuses = flag_statuses(args.project_root, func_key, node)
            if args.json:
                return _emit_json(
                    {
                        "action": "list",
                        "function": func_key,
                        "flags": [{**asdict(f), "status": s} for f, s in statuses],
                    },
                    0,
                )
            print(f"{func_key} — flag-line · {len(statuses)} record(s)")
            for f, status in statuses:
                note = f"  ({f.note})" if f.note else ""
                print(f"  [{status}] line {f.line}: {f.source}{note}")
            if not statuses:
                print("  (none)")
            return 0
        removed = clean_orphaned_flags(args.project_root, func_key, node)
        if args.json:
            return _emit_json(
                {"action": "clean", "function": func_key, "removed": [asdict(f) for f in removed]},
                0,
            )
        print(f"{func_key} — flag-line --clean")
        for f in removed:
            print(f"  removed orphaned record: line {f.line}: {f.source}")
        print(f"DONE:  {len(removed)} orphaned record(s) removed; current judgments untouched.")
        return 0

    if args.line is None:
        print("detective: flag-line needs a LINE (or --list / --clean)")
        return 1

    if args.remove:
        removed_flag = remove_line_flag(args.project_root, func_key, node, args.line)
        if args.json:
            return _emit_json(
                {
                    "action": "remove",
                    "function": func_key,
                    "removed": asdict(removed_flag) if removed_flag else None,
                },
                0 if removed_flag else 1,
            )
        if removed_flag is None:
            print(f"detective: no flag recorded at line {args.line} for {func_key}")
            return 1
        print(f"{func_key} — flag-line --remove · line {args.line}")
        print(_row("✓ removed", f"{removed_flag.source}"))
        print("DONE:  the line counts as a residual again on the next audit/converge.")
        return 0

    flag = add_line_flag(args.project_root, func_key, node, args.line, note=args.note)
    if flag is None:
        span = f"{node.lineno}-{node.end_lineno}"
        if args.json:
            return _emit_json(
                {
                    "action": "add",
                    "function": func_key,
                    "line": args.line,
                    "error": f"not a statement of {function} (lines {span})",
                },
                1,
            )
        print(f"detective: line {args.line} is not a statement of {function} (lines {span})")
        return 1
    if args.json:
        return _emit_json({"action": "add", "function": func_key, **asdict(flag)}, 0)
    suffix = f" ({args.note})" if args.note else ""
    print(f"{func_key} — flag-line · line {args.line}")
    print("")
    print(_row("✓ recorded", f"unreachable{suffix}: {flag.source}"))
    print(_row("", "keyed to this exact statement — an edit un-flags it."))
    print("")
    # The two ledgers stay orthogonal: this closes a LINE residual and nothing else.
    # Say what still outranks it — observed execution is proof of reachability.
    print("DONE:  line reports read 'line-complete modulo N flagged unreachable'. The flag")
    print("       kills no mutant and never gates decompose. If a test ever EXECUTES the")
    print("       line, execution overrides your flag. Proof beats judgement.")
    print(f"       Next: detective audit '{func_key}'   # the line is no longer a gap")
    return 0


def _run_flag(args, file, function) -> int:
    from .engine import profile
    from .equivalents import add_flag

    result = profile(file, function, args.project_root)
    # Match against value-survivors — the SAME set audit/classify report from — so a
    # crash/timeout-killed mutant surfaced by `audit` is flaggable (it is a value-
    # survivor). Using survivor_records here would miss those and read "none surviving".
    rec = next(
        (r for r in result.value_survivor_records if args.mutant_id in (r.get("mutant_id"), r.get("mutant"))),
        None,
    )
    if rec is None:
        ids = ", ".join(r.get("mutant_id", "?") for r in result.value_survivor_records) or "none surviving"
        print(f"no surviving mutant '{args.mutant_id}' for {function} — survivors: {ids}")
        return 1
    _verdict = "fence" if args.fence else "equivalent"
    add_flag(
        args.project_root,
        result.function_key,
        rec.get("diff_summary", ""),
        note=args.note,
        verdict=_verdict,
    )
    suffix = f" ({args.note})" if args.note else ""
    print(f"{result.function_key} — flag · {args.mutant_id}")
    print("")
    if args.fence:
        # A FENCE is the OPPOSITE claim to equivalent: this survival is a BUG, an authored
        # must-not the suite does not enforce. It is a GAP (fails `audit --check`, blocks
        # ✓COMPLETE), never suppressed — so a witness that KILLS it SATISFIES the fence, it does
        # not override a mistaken judgement.
        print(_row("✓ recorded", f"fence — an unenforced must-not{suffix}"))
        print(_row("", "keyed to this exact code — an edit un-flags it."))
        print("")
        print("DONE:  future audit/converge runs report it as an UNENFORCED must-not — a gap")
        print("       that fails `audit --check` and blocks ✓COMPLETE until a test kills it.")
        print(f"       Next: detective converge '{result.function_key}'   # write the test it needs")
        return 0
    # A flag is a CLAIM, and the one place a human overrides the engine. Say what it does
    # and what still outranks it: a real distinguishing witness. Otherwise it reads as a
    # way to silence a survivor, which is how a green board gets flagged into existence.
    print(_row("✓ recorded", f"equivalent{suffix}"))
    print(_row("", "keyed to this exact code — an edit un-flags it."))
    print("")
    print("DONE:  future audit/converge runs treat it as equivalent — unless a witness")
    print("       is found, which outranks your flag. Proof beats judgement.")
    # `function_key`, not `function`: the bare name does not resolve as a target, so the
    # one command this line offers would fail for anyone who pasted it.
    print(f"       Next: detective audit '{result.function_key}'   # it is no longer a gap")
    return 0


def _run_verify_rewrite(args, file, function) -> int:
    from .rewrite import (
        _RECEIPT_SCHEMA,
        RewriteReceipt,
        RewriteVerification,
        receipt_load_refusal,
        verify_rewrite,
    )

    def _invalid(reason: str) -> int:
        """Emit INVALID_RECEIPT through the SAME channel a real verdict uses (#57).

        The load boundary raised, so a corrupt or foreign receipt reached the user as a
        Python traceback — and under ``--json`` as NOTHING AT ALL, since the exception
        escaped before anything was printed. A caller cannot consume a refusal the tool
        never emitted. Every ending of this command is a `RewriteVerification`, including
        the ones where no verification could begin.
        """
        res = RewriteVerification(
            verdict="INVALID_RECEIPT",
            function=f"{file}::{function}",
            proof_replayed="",
            new_dimensions=(),
            differences=(),
            abstentions=(),
            note=reason,
        )
        if args.json:
            return _emit_json(asdict(res), 1)
        print(_format_rewrite(res))
        return 1

    try:
        with open(args.receipt_path, encoding="utf-8") as fh:
            _text = fh.read()
    except OSError as exc:
        return _invalid(f"unreadable_receipt: {exc}")
    _reason = receipt_load_refusal(_text, _RECEIPT_SCHEMA)
    if _reason:
        return _invalid(_reason)
    try:
        receipt = RewriteReceipt.from_json(_text)
    except (TypeError, ValueError) as exc:
        # Residual. `receipt_load_refusal` names every failure derivable from the TEXT, but
        # construction can still reject a shape it does not model — an unexpected key, a
        # field whose type it does not inspect. Catching here keeps the promise that no
        # input reaches the user as a traceback, instead of assuming that list is total.
        return _invalid(f"bad_fields: {exc}")
    result = verify_rewrite(
        receipt, file, function, args.project_root, notify=None if args.json else _notify_stderr
    )
    if args.json:
        # WRAP, not early-return: the --learn persistence below runs under --json too.
        print(
            json.dumps(
                _with_exit(asdict(result), 0 if result.verdict == "PRESERVED" else 1),
                indent=2,
                default=str,
            )
        )
    else:
        print(_format_rewrite(result))
    # --learn (#17): a CHANGED rewrite is §9's SECOND spine source. `learn_disposition` is the
    # pure gate (flag off → skip_disabled; not CHANGED → skip_unchanged); only "learn" harvests
    # the near-misses, κ-scores them over the call graph via the SAME corpus fixpoint `censor
    # --promote` uses, and persists the promoted ones. Reported on stderr so the --json verdict
    # on stdout stays a clean RewriteVerification.
    from .censor import learn_disposition

    if learn_disposition(result.verdict, args.learn) == "learn":
        from .censor import censors_from_verification
        from .promotion_ledger import corpus_fixpoint, ledger_key, load_ledger, save_ledger

        censors = censors_from_verification(f"{file}::{function}", result)
        promoted = corpus_fixpoint(args.project_root, censors)["promoted"] if censors else []
        store = load_ledger(args.project_root)
        for e in promoted:
            store[ledger_key(e.censor)] = e
        save_ledger(args.project_root, store)
        if not args.json:
            _notify_stderr(
                f"learned {len(promoted)} censor(s) from the rejected rewrite "
                f"({len(censors)} near-miss candidate(s)) → .detective/censors.json"
            )
    # Only PRESERVED is a pass; every other verdict (CHANGED / UNREVIEWED / ABSTAIN / STALE) is a
    # refusal CI must catch, so it exits non-zero.
    return 0 if result.verdict == "PRESERVED" else 1


def _run_receipt(args, file, function) -> int:
    from .rewrite import make_receipt

    rec = make_receipt(file, function, args.project_root, notify=_notify_stderr)
    text = rec.to_json()
    if getattr(args, "out", None):
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        _notify_stderr(f"receipt written: {args.out}  (proof status: {rec.proof_status})")
    else:
        print(text)
    # A valid baseline receipt needs BOTH a mutation-complete proof AND a green verification of it
    # (issue #37): either alone is a weak baseline verify-rewrite must not treat as sound, so this
    # is AND, not OR. A weak receipt exits 3 so it is caught at creation, not silently trusted later.
    return 0 if (rec.proof_status == "passed" and rec.functionally_complete) else 3


def _run_diagnose(args, file, function) -> int:
    from .engine import diagnose

    scope = diagnose(
        file,
        function,
        args.project_root,
        progress=_stream_progress(function),
        trace_progress=_stream_trace_progress(function),
        # BOTH budgets, always. `--trace-budget` used to stop here while its session sibling
        # went through, so the per-test cap silently stayed at the default however the user
        # set it. It also has to arrive for the verdict cache to be keyed honestly: the key
        # identifies the budget regime a result was measured under, and a flag that reaches
        # the seam but not this call would change the answer without changing the key.
        trace_budget_s=_trace_budget(args),
        trace_session_budget_s=_trace_session_budget(args),
        include_shaped=args.include_shaped,
        two_sign=args.two_sign,
    )
    if args.json:
        return _emit_json(asdict(scope), 0)
    print(_format_scope(scope))
    return 0


def _run_censor(args) -> int:
    # Path-based + static (an AST call-site + call-graph pass), so it lands with the other advisory
    # verbs ABOVE _split_target — it carries `path`, not `target`, and never opens a live session.
    from .censor import harvest_corpus_censors, score_censor
    from .promotion_ledger import (
        build_ledger,
        corpus_fixpoint,
        ledger_key,
        load_ledger,
        save_ledger,
    )

    if args.list:
        entries = load_ledger(args.project_root)
        if args.json:
            return _emit_json(
                {
                    "kind": "censor-ledger",
                    "count": len(entries),
                    "entries": {
                        k: {
                            "censor": asdict(e.censor),
                            "kappa": e.kappa,
                            "state": e.state,
                            "generation": e.generation,
                        }
                        for k, e in entries.items()
                    },
                },
                0,
            )
        print(_format_censor_list(entries))
        return 0

    censors = harvest_corpus_censors(args.project_root, args.path)
    if args.promote:
        result = corpus_fixpoint(args.project_root, censors)
        # Persist the promoted censors into the ledger (merge with any existing entries).
        store = load_ledger(args.project_root)
        for e in result["promoted"]:
            store[ledger_key(e.censor)] = e
        save_ledger(args.project_root, store)
        if args.json:
            return _emit_json(
                {
                    "kind": "censor-promote",
                    "proposed": len(censors),
                    "generations": result["generations"],
                    "n_demoted": result["n_demoted"],
                    "self_teaching": result["self_teaching"],
                    "promoted": [
                        {
                            "key": ledger_key(e.censor),
                            "censor": asdict(e.censor),
                            "kappa": e.kappa,
                            "generation": e.generation,
                        }
                        for e in result["promoted"]
                    ],
                },
                0,
            )
        print(_format_censor_promote(result, len(censors)))
        return 0

    ledger = build_ledger(args.project_root, censors)
    # Per-censor disposition at the conservative σ̂ default (retains plurality): propose / abstain /
    # refuse — the same score_censor the fixpoint gates on, shown so a reader sees WHY each ranks.
    rows = [
        (ledger_key(e.censor), e.censor, e.kappa, score_censor(e.censor, e.kappa or 0, 1)) for e in ledger
    ]
    if args.json:
        return _emit_json(
            {
                "kind": "censor-proposal",
                "proposed": len(censors),
                "censors": [
                    {
                        "key": k,
                        "func_key": c.func_key,
                        "kind": c.kind,
                        "subject": c.subject,
                        "source": c.source,
                        "kappa": kap,
                        "disposition": disp,
                    }
                    for k, c, kap, disp in rows[: args.top]
                ],
            },
            0,
        )
    print(_format_censor_proposal(rows, total=len(censors), top=args.top))
    return 0


def _run_parsimony(args) -> int:
    from .parsimony_map import parsimony_plan, score_path

    score = score_path(args.path, args.project_root)
    if getattr(args, "plan", False):
        # A work QUEUE, not the map (issue #51): flagged functions grouped by module (one trace
        # per group), worst-first, so a driver spends a finite budget where it pays off first.
        if args.json:
            groups = parsimony_plan(score)
            return _emit_json(
                {
                    "kind": "parsimony-plan",
                    "note": "schedule (advisory) — ranks no quality, proves nothing, writes nothing",
                    "functions": score.functions,
                    "flagged": score.flagged,
                    "trace_groups": len(groups),
                    "groups": [
                        {
                            "module": module,
                            "one_baseline_trace": True,
                            "targets": [
                                {"target": r.qualname, "smells": r.smells, "detail": r.detail} for r in reads
                            ],
                        }
                        for module, reads in groups[: args.top]
                    ],
                },
                0,
            )
        print(_format_parsimony_plan(score, top=args.top))
        return 0
    if args.json:
        print(json.dumps(_with_exit(asdict(score), 0), indent=2, default=str))
    else:
        print(_format_parsimony_map(score, top=args.top))
    return 0


def _run_regime(args) -> int:
    from dataclasses import asdict as _asdict

    from .regime import apply_migration, plan_migration, resolve_regime

    target_file = _split_target(args.target, args.project_root)[0] if args.target else None
    regime = resolve_regime(args.project_root, target_file)
    plan = plan_migration(regime)
    applied: tuple[str, ...] = ()
    if args.migrate:
        # por qué no los dos: cross-check the static precedence mirror (regime.config_file)
        # against the config file pytest ITSELF reports. Agreement is the standard case;
        # divergence means a non-standard/version-specific config — register into pytest's own
        # file and WARN, rather than silently declaring into one pytest ignores.
        from .regime import _resolved_for_file, pytest_configfile_live, reconcile_config_file

        _root = os.path.abspath(args.project_root)
        _chosen, _divergence = reconcile_config_file(regime.config_file, pytest_configfile_live(_root))
        _override = _resolved_for_file(_root, _chosen) if _divergence else None
        applied = apply_migration(plan, _override)
        if _divergence:
            print(f"  ⚠ {_divergence}", file=sys.stderr)
        # Re-read: the report must describe the tree as it IS now, not as it was before we
        # wrote to it. Reporting the pre-migration regime after migrating is how a tool
        # tells you it fixed something and shows you the evidence that it did not.
        regime = resolve_regime(args.project_root, target_file)
        plan = plan_migration(regime)
    if args.json:
        return _emit_json({"regime": _asdict(regime), "applied": list(applied)}, 2 if regime.conflicts else 0)
    print(_format_regime(regime, plan, applied, args.target))
    # A conflict is the answer, not a crash: exit 2 so a script can gate on it, the same
    # code every other command returns when it refuses for the same reason.
    return 2 if regime.conflicts else 0


def _run_purge(args) -> int:
    from Wesker.memory_guard import purge_caches

    from . import verdict_cache as _vc

    # BOTH packages. Wesker's purge knows `.wesker/`; ours knows `.detective/`. Neither can
    # know the other's, and a command that purges one of two caches while announcing "a clean
    # state" is worse than one that purges neither — the user acts on the claim.
    w_removed, w_reclaimed = purge_caches(args.project_root)
    d_removed, d_reclaimed = _vc.purge(args.project_root)
    removed = tuple(w_removed) + tuple(d_removed)
    reclaimed = w_reclaimed + d_reclaimed
    if args.json:
        return _emit_json({"removed": list(removed), "reclaimed_bytes": reclaimed}, 0)
    if removed:
        print(f"purged {len(removed)} cache file(s), reclaimed {reclaimed // 1024} KB:")
        for path in removed:
            print(f"  - {path}")
    else:
        print("nothing to purge — no cached analysis found (a clean state)")
    return 0


def _run(args) -> int:
    if args.command == "regime":
        return _run_regime(args)

    if args.command == "purge":
        return _run_purge(args)

    if args.command == "parsimony":
        return _run_parsimony(args)

    if args.command == "censor":
        return _run_censor(args)

    file, function = _split_target(args.target, getattr(args, "project_root", None))

    if args.command == "receipt":
        return _run_receipt(args, file, function)

    if args.command == "verify-rewrite":
        return _run_verify_rewrite(args, file, function)

    if args.command == "flag":
        return _run_flag(args, file, function)

    if args.command == "flag-line":
        return _run_flag_line(args, file, function)

    if args.command == "diagnose":
        return _run_diagnose(args, file, function)

    if args.command == "converge":
        return _run_converge(args, file, function)

    if args.command == "audit":
        return _run_audit(args, file, function)

    if args.command == "decompose":
        return _run_decompose(args, file, function)

    # Unreachable: argparse (required subparsers) guarantees args.command is one of the
    # registered commands, each handled above. Kept as a defensive guard.
    raise SystemExit(f"detective: unknown command {args.command!r}")


if __name__ == "__main__":
    sys.exit(main())
