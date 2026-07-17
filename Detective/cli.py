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
import sys
import textwrap
from dataclasses import asdict
from typing import Any

# Imported, never restated: the engine owns this number, and a second copy would drift silently.
from Wesker.engine import DEFAULT_TRACE_BUDGET_S as _WESKER_DEFAULT_TRACE_BUDGET_S
from Wesker.engine import (
    DEFAULT_TRACE_SESSION_BUDGET_S as _DEFAULT_TRACE_SESSION_BUDGET_S,
)

from . import __version__


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


def _reachable_paths(root: str, targets: list[str] | None) -> list[str] | None:
    """pytest collection paths scoped to the target, or None to collect everything.

    Wrapped so the scoping can NEVER be the thing that breaks a run: any failure in the
    static analysis degrades to None, i.e. exactly today's full collection. A speedup that
    can turn a verdict wrong is not a speedup, and this one is only ever allowed to make the
    tool faster or leave it alone.
    """
    if not targets or len(targets) != 1:
        return None
    try:
        from .reachability import reachable_test_paths

        return reachable_test_paths(root, targets[0])
    except Exception:  # noqa: BLE001 — scoping is an optimisation; never fail the run for it
        return None


def _split_target(target: str) -> tuple[str, str]:
    """Split ``path/to/file.py::function`` into ``(file, function)``."""
    if "::" not in target:
        raise SystemExit(f"target must be 'file.py::function', got {target!r}")
    file, function = target.rsplit("::", 1)
    if not file or not function:
        raise SystemExit(f"target must be 'file.py::function', got {target!r}")
    return file, function


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
    lines.append(
        _row("✓ pinned", f"{kq.by_value_assertion} pin the RETURN VALUE · {kq.by_crash} only prove it runs")
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


def _input_template(param_names: tuple[str, ...]) -> str:
    """A copy-pasteable ``--input`` skeleton shaped to the target's parameters.

    The user replaces each ``<name>`` slot with a literal to exercise the residual; the
    CLI parses it (``ast.literal_eval``) and the AST builds the test. This is the Zone-2
    hand-back made concrete — the tool states the exact input shape to supply, so a user
    never has to reverse-engineer it from prose.
    """
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


def _survivor_lines(verdicts, verbose: bool) -> list[str]:
    """One survivor block — per-mutant under `verbose`, grouped by mutated statement otherwise.

    The grouped form keeps the BOUNDARY hints (the only actionable part) and drops the ids and
    diffs, which is what makes a 200-line function's residual readable. The ids are never lost:
    the written report always renders verbose, and `--verbose` reproduces it on the terminal.
    """
    out: list[str] = []
    if verbose:
        for v in verdicts:
            out.append(f"    → mutant {v.mutant_id} [{v.category}]: {_concise_diff(v.diff_summary)}")
            if v.category == "BOUNDARY" and (hint := _boundary_hint(v.diff_summary)):
                out.append(f"        ↳ {hint}")
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
        for v in vs:
            if v.category == "BOUNDARY" and (h := _boundary_hint(v.diff_summary)):
                if (rel := _hint_relation(h)) not in hints:
                    hints.append(rel)
        out += [f"        ↳ distinguish at the boundary — supply an input {r}" for r in hints]
    out.append("    (--verbose for each mutant's id and diff)")
    return out


def _boundary_hint(diff_summary: str) -> str | None:
    """For a BOUNDARY mutant — a strict↔non-strict comparison shift (`>`↔`>=`, `<`↔`<=`) — name
    the ONE distinguishing input: the EQUALITY edge. Two ordering comparisons differ EXACTLY when
    their operands are equal, so `left == right` is the valid relation WITH its precondition, not
    a generic template (BOUNDARY is oracle-light, not oracle-free). Recovers the real operands by
    matching the comparison whose operator changed between original and mutant; None if none found.
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
                if m_left == left and m_right == right and _differs_at_eq(op, m_op):
                    return f"distinguish at the boundary — supply an input where {left} == {right}"
    return None


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

    state = {"last_ms": -1e9}

    def cb(done: int, total: int, elapsed_ms: float) -> None:
        if 0 < done < total and elapsed_ms - state["last_ms"] < 200.0:
            return  # ~5 updates/sec, but always emit the last
        state["last_ms"] = elapsed_ms
        secs = elapsed_ms / 1000.0
        if done >= total:
            sys.stderr.write(f"\r  … {label}: baseline traced · {total} tests · {secs:.1f}s          \n")
        else:
            eta = (total - done) * (elapsed_ms / done) / 1000.0 if done else 0.0
            sys.stderr.write(f"\r  … {label}: tracing baseline {done}/{total} tests · ETA {eta:.0f}s   ")
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

    prior_ms = _read_per_mutant_ms()
    state = {"last_ms": -1e9, "started": False}

    def cb(done: int, total: int, elapsed_ms: float) -> None:
        if not state["started"]:
            state["started"] = True
            if prior_ms and total:
                est = total * prior_ms / 1000.0
                sys.stderr.write(
                    f"\r  … {label}: 0/{total} mutants · est ~{est:.1f}s (this machine's recent rate)   "
                )
            else:
                sys.stderr.write(f"\r  … {label}: 0/{total} mutants · calibrating this machine…   ")
            sys.stderr.flush()
            if done == 0:
                return
        if 0 < done < total and elapsed_ms - state["last_ms"] < 200.0:
            return  # throttle to ~5 updates/sec, but always emit first + last
        state["last_ms"] = elapsed_ms
        secs = elapsed_ms / 1000.0
        rate = done / secs if secs > 0 else 0.0
        if done >= total:
            if total:
                _update_per_mutant_ms(elapsed_ms / total)  # learn this machine's throughput
            sys.stderr.write(f"\r  … {label}: {done}/{total} mutants · {rate:.0f}/s · done in {secs:.1f}s\n")
        else:
            eta = (total - done) * (elapsed_ms / done) / 1000.0 if done else 0.0
            sys.stderr.write(f"\r  … {label}: {done}/{total} mutants · {rate:.0f}/s · ETA {eta:.1f}s   ")
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
    rep, signature: str = "", param_names: tuple[str, ...] = (), verbose: bool = True
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
        lines += _survivor_lines(unproven, verbose)
        lines += _target_lines(signature)
        lines.append(
            f"      supply:  {_input_template(param_names)}   "
            "# fill the slots to reach a branch above, then re-run converge"
        )
    if crash_only:
        cats = ", ".join(sorted({v.category for v in crash_only}))
        lines.append(
            f"  value-equivalent, crash-only-distinguishable ({len(crash_only)}: {cats}) — an input "
            "DOES distinguish these: the mutant RAISES where the original returns, so your suite "
            "already detects them. No value assertion can pin them (the mutant never returns a "
            "value to compare), so there is NO input to supply. `flag` if truly equivalent:"
        )
        lines += _survivor_lines(crash_only, verbose)
    if rep.manual_equivalent:
        lines.append(
            f"  ✓ {len(rep.manual_equivalent)} survivor(s) flagged equivalent (oracle — PROVEN, not gaps)"
        )
    if rep.killable:
        lines.append(f"  killable — SUGGESTED tests (not auto-applied, {len(rep.killable)}):")
        for v in rep.killable:
            w = v.witness
            args = ", ".join(repr(a) for a in w.args)
            lines.append(f"    → assert f({args}) == {w.original}   (mutant gives {w.mutant})")
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
    if not result.complete:
        # Not "✗": the residual is stated on the lines that follow, and marking a run that
        # pinned every killable behavior as a failure misreads the tool's own result.
        return "Incomplete"
    rep = result.survivor_report
    candidate = len(rep.equivalent) if rep is not None else 0
    if candidate == 0:
        return "✓ COMPLETE — every mutant killed or oracle-proven-equivalent, line-complete"
    return (
        f"✓ every killable mutant killed + line-complete — {candidate} survivor(s) "
        "candidate-equivalent (UNPROVEN: `flag` if truly equivalent, or add a distinguishing input)"
    )


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
    cand = len(rep.equivalent) if rep is not None else 0
    killable = len(rep.killable) if rep is not None else 0
    uncertain = len(rep.unclassified) if rep is not None else 0
    gap = len(result.missing_lines)
    if result.complete and cand == 0:
        return "the suite pins every behavior a test can — nothing killable remains, every line covered"
    parts = []
    if killable:
        parts.append(f"{killable} behavior(s) still killable — supply the input(s) below")
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
    total = result.total_mutants
    rep = result.survivor_report
    cand = len(rep.equivalent) if rep is not None else 0
    killable = len(rep.killable) if rep is not None else 0
    gap = len(result.missing_lines)
    if result.complete and cand == 0:
        status = "✓ COMPLETE"
    elif result.complete:
        status = f"✓ COMPLETE (modulo {cand} unproven-equivalent)"
    else:
        bits = []
        if killable:
            bits.append(f"{killable} killable")
        if gap:
            bits.append(f"{gap}-line gap")
        # "✗ INCOMPLETE" reads as FAILURE, and the common case it labels is not one: every
        # killable mutant pinned with a couple of lines left over is the tool working. The
        # ✗ made a good result look like a broken run. State the residual plainly instead —
        # what is missing is already named in `bits`.
        status = "Incomplete" + (f": {' · '.join(bits)}" if bits else "")
    # Next to the arrow, this slot READS as "wrote N tests → here", so it has to BE that.
    # `minimal_test_count` is a different quantity — the two-axis minimal cover over the WHOLE
    # suite, ours and the consumer's together — and printing it beside our own path credits us
    # with the consumer's tests. See `_written_count`.
    written = _written_count(result)
    count = written if result.written_path else (result.minimal_test_count or None)
    tests = f" · {count} test(s)" if count else ""
    arrow = f" → {_rel_path(result.written_path)}" if result.written_path else ""
    return f"FINAL {result.function}: {status} · {result.killed}/{total} killed{tests}{arrow}"


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
        # meets or beats. Comprehensive is exhaustive (100% guaranteed); fast shows
        # the (1−1/e)-per-pass guarantee, so the speed/certainty trade is explicit.
        if result.fast:
            tail = (
                f"greedy floor ≥ {result.coverage_guarantee:.0%} of coverable DOF (proven, (1−1/e) per pass)"
            )
        else:
            tail = "exhaustive — 100% guaranteed"
        # SPECIFIED reads value_killed, not killed: a crash/timeout kill proves the code runs,
        # not what it computes (§0), so crediting it here would overstate the specification —
        # and disagree with `diagnose`, which counts value-pins. This number is therefore
        # allowed to sit below the "N killed" above it; they are different claims.
        lines.append(
            f"  DOF: {universe} behavioral degrees of freedom · {mode} · "
            f"{result.value_killed}/{universe} = {_score(result.value_killed, universe)} "
            f"of DOF specified · {tail}"
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
        killable = (
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
        elif killable > 0:
            # Stalled with real killable residuals: the I_solve external facts.
            lines.append(
                f"  spec-completeness: {free} · structure exhausted — {killable} killable "
                "residual(s) = I_solve (supply --input below to finish)"
            )
        # else: complete-modulo-equivalent — the verdict + survivor lines already say so.
    if result.remaining:
        lines.append(f"  remaining: {', '.join(result.remaining)}")
    lines += _format_survivor_report(
        result.survivor_report, result.signature, result.param_names, verbose=verbose
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
        lines.append(
            f"      supply:  {_input_template(result.param_names)}   "
            f"# fill the slots to execute line(s) {gap}, then re-run converge"
        )
    elif result.minimal_test_count:
        lines.append("  ✓ line-complete — every executable line is covered by a test")
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


def _write_converge_report(root: str, qualname: str, text: str) -> str:
    """Persist the FULL report to a readable file so the terminal can stay minimal.
    The complete detail — DOF, per-pass, every survivor, the generated test source — is
    one `cat` away. Returns a short path relative to root, or '' on failure (best-effort)."""

    safe = qualname.replace("::", "__").replace("/", "_").replace(".", "_")
    d = os.path.join(root, ".detective", "reports")
    try:
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, f"converge_{safe}.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    except OSError:
        return ""
    return os.path.relpath(path, root)


def _format_converge_terse(result, report_path: str, root: str = ".") -> str:
    """The converge report: what got written, what is left, the ONE next action — then the
    greppable ``FINAL`` banner, which stays LAST.

    ``FINAL`` last is a downstream contract, not a layout choice: tooling tails this output to
    find the result, so the human action sits above it rather than after it. Everything
    verbose lives in the report file, which is always written regardless of `--full`.
    """
    fn = result.function
    rep = result.survivor_report
    lines = [_RULE, f"{fn} — converge{_headline_counts(result, rep)}", ""]

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
    if result.missing_lines:
        gap = list(result.missing_lines)
        lines.append(_row("✗ uncovered", f"{len(gap)} line(s): {gap[:8]}"))
    if rep is not None and rep.equivalent:
        # Two rows, not one: "no input distinguishes them" is FALSE of a crash-only survivor —
        # an input does, by crash — and it was that false claim that sent a reader hunting for
        # the input. Each row states the one true thing about its own class.
        if unproven := [v for v in rep.equivalent if not v.crash_only]:
            lines.append(_row("· unproven-equiv", f"{len(unproven)} — no input distinguishes them"))
        if crash_only := [v for v in rep.equivalent if v.crash_only]:
            lines.append(
                _row("· crash-only-equiv", f"{len(crash_only)} — detected by crash; no value pins them")
            )
    if report_path:
        lines.append(_row("· full report", report_path))
    lines.append("")
    lines += _converge_action(result, rep, root, report_path)
    lines.append("")
    lines.append(_final_banner(result))
    return "\n".join(lines)


def _converge_action(result, rep, root: str = ".", report_path: str = "") -> list[str]:
    """Converge's ONE next action — the DERIVED input, same as decompose's residual and from
    the same machinery (`_derived_input`). A witness is a call the engine RAN; a boundary hint
    is a relation it PROVED; only with neither is the reader asked for the value, which is the
    documented interface and not a fallback for work the tool skipped.

    `flag` comes LAST and only when nothing else is outstanding. It is the one claim a human
    makes against the engine, and offering it while a real gap is open invites someone to flag
    their way to a green board.
    """
    fn = result.function
    blocked = rep is not None and (rep.killable or rep.unclassified)
    if blocked or result.missing_lines:
        return _derived_input(None, result, rep, fn, verb=f"detective converge '{fn}'", report=report_path)
    if rep is not None and rep.equivalent:
        ids = [v.mutant_id for v in rep.equivalent]
        more = f"  ({len(ids) - 1} more in the report)" if len(ids) > 1 else ""
        return [
            "DONE:  every killable behaviour is pinned. What remains cannot be distinguished",
            "       by any input Detective found — whether it is truly equivalent is UNDECIDABLE",
            "       in general, so the engine will not claim it. Leave them; they are not a gap.",
            f"       If you can prove one is: detective flag '{fn}' {ids[0]} --note \"why\"{more}",
        ]
    return [
        "DONE:  the suite pins every behaviour this function makes.",
        f"       Next (optional): detective decompose '{fn}' --apply   # if it does too much",
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
    if rep is not None and rep.equivalent:
        parts.append(f"{len(rep.equivalent)} candidate-equivalent")
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


def _hint_relation(hint: str) -> str:
    """The bare relation out of a boundary hint — "where amt == 0"."""
    tail = hint.split("—", 1)[-1].strip()
    # Lower-case: the caller opens the sentence ("That reaches the branch: where amt == 0.").
    return tail[len("supply an input ") :] if tail.startswith("supply an input ") else tail


def _witness_args(w) -> str:
    """A witness's args as a tuple literal. `(1)` is not a tuple, it is `1` — a one-argument
    call needs the trailing comma or the command does not parse as what it claims to be."""
    return ", ".join(repr(a) for a in w.args) + ("," if len(w.args) == 1 else "")


def _derive_inputs(proof, rep) -> tuple[str, list[str], int]:
    """What the engine DERIVED about the inputs it still needs — as data, for any surface.

    Returns ``(kind, items, total)``:

    * ``("witness", ['(1,)', "(0, 'gold')"], n)`` — each item is a real call the engine RAN and
      saw a mutant differ on. Paste it. SUGGESTED, not applied: `property_holds` could not
      verify the test sound, and that gap is the abstention.
    * ``("boundary", ['where qty == 0'], n)`` — each item is a relation the engine PROVED: two
      orderings differ exactly at the equality edge, recovered from the comparison whose
      operator shifted. Author a call satisfying it.
    * ``("author", [], 0)`` — nothing derived. The caller supplies the value outright, which is
      the documented interface ("You supply what only you know"), not a fallback.

    ``total`` is how many exist; ``items`` is capped at `_MAX_BATCH`. The gap between them MUST
    be disclosed by the caller — a bound that is not named reads as "this is all of them", which
    is how 65 requirements looked like 1.

    DATA, not text, because the two surfaces render different commands: a human runs
    `--input "(...)"`, a tool caller passes `inputs=["(...)"]`. Sharing the rendered STRING put
    terminal syntax into an MCP response — telling a caller to use a flag that does not exist
    there. Sharing the derivation cannot do that, and it is the part that must never drift.
    """
    witnesses = [v for v in (rep.killable if rep is not None else ()) if v.witness]
    if witnesses:
        return "witness", [f"({_witness_args(v.witness)})" for v in witnesses[:_MAX_BATCH]], len(witnesses)
    hints: list[str] = []
    # Skip crash-only survivors: an input already distinguishes them and no value assertion can
    # pin them, so any input we ask for here is one the caller can supply and still see NO
    # progress — the same forever-loop `find_witness` skips them to avoid.
    for v in (v for v in (rep.equivalent if rep is not None else ()) if not v.crash_only):
        h = _boundary_hint(v.diff_summary)
        if h and (rel := _hint_relation(h)) not in hints:
            hints.append(rel)
    if hints:
        return "boundary", hints[:_MAX_BATCH], len(hints)
    return "author", [], 0


def _derived_input(r, proof, rep, target: str, verb: str = "", report: str = "") -> list[str]:
    """The CLI's `DO THIS:` block — `derive_inputs`' data rendered as terminal syntax.

    A thin renderer on purpose. The DERIVATION is shared with the MCP (`derive_inputs`); the
    COMMAND is not, because a human runs `--input "(...)"` and a tool caller passes
    `inputs=["(...)"]`. Sharing the rendered string put terminal syntax into an MCP response.

    Batched: `--input` is repeatable, each call kills what it reaches, and the repetition is the
    signal for how many calls to author. The remainder is always named — a bound that is not
    disclosed reads as "this is all of them".
    """
    cmd = verb or f"detective decompose '{target}' --apply"
    sig = proof.signature or ""
    tmpl = _input_template(proof.param_names)
    kind, items, total = _derive_inputs(proof, rep)
    where = report or "the full report"

    if kind == "witness":
        flags = " ".join(f'--input "{a}"' for a in items)
        out = [f"DO THIS:  {cmd} {flags}"]
        out.append("")
        out.append(_row("· Why these", f"Detective RAN each: the {len(items)} call(s) above each"))
        out.append(_row("", "make a mutant differ from your real function."))
        out.append(_row("", "SUGGESTED — not written for you, because the engine"))
        out.append(_row("", "could not verify the tests sound."))
        if total > len(items):
            out.append(_row("", f"({total - len(items)} more in {where})"))
        return out

    if kind == "boundary":
        out = [f"DO THIS:  {cmd} " + " ".join([tmpl] * len(items))]
        out.append("")
        out.append(_row("· Signature", sig))
        out.append("")
        out.append(_row("· Task", f"Author {len(items)} call(s), one per requirement, each as"))
        out.append(_row("", "its own --input. Detective derives every test from them."))
        out.append(_row("· Requirements", f"1. {items[0]}"))
        for i, rel in enumerate(items[1:], start=2):
            out.append(_row("", f"{i}. {rel}"))
        if total > len(items):
            out.append(_row("", f"(+{total - len(items)} more in {where})"))
        out.append(_row("", "Derived from your code: two orderings differ exactly"))
        out.append(_row("", "at the equality edge."))
        return out

    return [
        f"DO THIS:  {cmd} {tmpl}",
        "",
        _row("· Signature", sig),
        "",
        _row("· Task", "Author one real call and pass it as --input."),
        _row("· Requirement", "It must run. Detective derives every test from it."),
        _row("", "Values are yours to choose — it will not invent one whose"),
        _row("", "meaning is not in the code. A class from the module goes"),
        _row("", "in as its constructor. Repeatable for another branch."),
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
    if not r.applied and not r.proposed and not r.unsafe_blocks:
        return f"{r.function} — decompose\n\nDONE:  no separable block. There is no seam here to split."

    proof = r.proof
    proof_incomplete = proof is not None and not proof.functionally_complete
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

    if not proof_incomplete:
        # A complete suite that rejects the rewrite has PROVEN behaviour changed. There is no
        # input to supply and nothing to retry; offering one sends the reader to close a hole
        # that does not exist.
        lines.append("STOP.  This is a verdict, not a gap. The suite is mutation-complete and it")
        lines.append("       proves this extraction changes behaviour. Your source was NOT touched.")
        return "\n".join(lines)

    lines += _residual_action(r, proof, rep, tgt, root)
    return "\n".join(lines)


def _format_audit(a) -> str:
    """Read-only audit of an existing suite, in the report shape: what is true, then the ONE
    next action, and audit itself never writes.

    Three tiers, not two: a suite that kills every killable mutant and covers every line but
    leaves UNPROVEN candidate-equivalents has no real gaps and is not "incomplete" — calling
    it that sends someone to write tests for behaviour that is already pinned.

    The action names a REAL mutant id. It used to read ``flag <mutant_id>`` — a placeholder,
    with the ids sitting one field away in the classifier — so the one command the report
    offered could not be pasted, and the reader had to go hunting to do what it asked.
    """
    if a.complete_modulo_equivalent:
        verdict = f"complete, modulo {a.candidate_equivalent} unproven-equivalent"
    elif a.complete:
        verdict = "complete"
    else:
        # Not "✗": the gaps are itemised below, and a suite that pins every killable behaviour
        # but leaves a line uncovered is not a failed run.
        verdict = "incomplete"
    lines = [
        _RULE,
        f"{a.function} — audit · {a.test_count} test(s) · {a.kill_pct}% killed · {verdict}",
        "",
    ]
    if a.failing_tests:
        # First, always: a failing test means the suite disagrees with the code RIGHT NOW.
        # Nothing else in this report matters until that is resolved, and it is never ours
        # to delete — it is either a wrong expectation or a real regression.
        lines.append(_row("⚠ FAILING NOW", f"{len(a.failing_tests)} test(s) fail on current code:"))
        lines.append(_row("", ", ".join(a.failing_tests[:4])))
    if a.killable_gaps:
        lines.append(_row("✗ real gaps", f"{len(a.killable_gaps)} killable mutant(s) no test kills"))
    if a.missing_lines:
        lines.append(_row("✗ uncovered", f"{len(a.missing_lines)} line(s): {list(a.missing_lines)[:8]}"))
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
        lines.append(_row("", ", ".join(a.redundant_tests[:4])))
    lines.append("")
    lines += _audit_action(a)
    return "\n".join(lines)


def _audit_action(a) -> list[str]:
    """Audit's ONE next action, in the report's row style. Priority order — the order IS the
    judgement.

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
        return [
            f"DO THIS:  detective audit '{a.function}' --remove",
            "",
            _row("· Why", f"{len(a.redundant_tests)} test(s) kill no mutant AND cover no line"),
            _row("", "that another test does not already. Nothing else changes."),
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
        if name == "converge":
            p.add_argument("--write-dir", default="tests", help="write synthesized tests here")
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
        if name == "audit":
            p.add_argument(
                "--remove",
                action="store_true",
                help="CONFIRM deletion of the proposed pointless tests (removes them from your files)",
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
    flag_p = sub.add_parser("flag", help="mark a surviving mutant as truly equivalent (manual oracle)")
    flag_p.add_argument("target", help="file.py::function")
    flag_p.add_argument("mutant_id", help="the surviving mutant id (from `audit`/`diagnose`)")
    flag_p.add_argument("--note", default="", help="why it is equivalent")
    flag_p.add_argument("--project-root", default=".")
    flag_p.add_argument("--json", action="store_true", help="emit JSON")
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
    names: list[str] = []
    try:
        import ast as _ast

        from Wesker.ci import walk_functions

        file = _split_target(target)[0]
        root = os.path.abspath(getattr(args, "project_root", ".") or ".")
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
    args = _build_parser().parse_args(argv)
    try:
        code = _run_live(args)
    except (LookupError, FileNotFoundError) as exc:
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
    if getattr(args, "command", None) in ("purge", "regime") or not root:
        return _run(args)
    # Resolve the testing regime BEFORE the session — the session is the expensive part, and
    # tracing a suite that cannot reach the target is the longest possible way to learn nothing.
    # Refuse rather than warn: a warning above a plausible report is read as a footnote, and the
    # report underneath says "0 tests cover this", which is exactly the sentence that sends
    # someone off to write a suite against a copy nobody runs.
    if (target_arg := getattr(args, "target", None)) and not getattr(args, "json", False):
        try:
            from .regime import resolve_regime

            regime = resolve_regime(root, _split_target(target_arg)[0])
            if regime.conflicts:
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
    target_arg = getattr(args, "target", None)
    if target_arg:
        try:
            targets = [_split_target(target_arg)[0]]
        except Exception:  # noqa: BLE001 — a command whose target isn't file::function
            targets = None

    # The suite-global baseline is traced HERE, before `_run` — so this callback, not the one
    # `diagnose` gets, is what makes the first (and on a large suite, longest) phase visible.
    # Without it the live path is silent at 100% CPU until the first mutant, which is the whole
    # "looks hung" failure one layer further up than it looked.
    label = _split_target(target_arg)[1] if target_arg else "baseline"

    # Collect only the test files that could execute the target's lines. The session baseline
    # traces EVERYTHING it collects, before a single mutant runs, so an unscoped collection
    # makes the cost scale with the SUITE rather than the function: measured on Regenesis,
    # 2134 test functions traced for one 13-line function, of which 1928 are in modules that
    # cannot import the target even transitively. `paths` is pytest's own collection argument,
    # so the scoping happens before anything is imported, not after everything is traced.
    # `None` (analysis unsure, or no target) collects everything — byte-identical to before.
    paths = _reachable_paths(root, targets)
    # `--trace-budget` / `--trace-session-budget` bound the pass that traces the whole suite, and
    # on the live path that pass runs HERE — inside the seam — not in `profile`. Sent only to
    # `profile`, they reached the per-function baseline the live path never uses, so raising them
    # changed nothing and the phase stayed capped at the engine's default: a documented opt-out
    # that could not reach the thing it opts out of.
    diagnostic: dict[str, Any] = {}
    try:
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
    except TypeError:  # older Wesker: seam without diagnostic (or the older progress/paths)
        try:
            code = run_with_live_suite(
                root,
                lambda: _run(args),
                target_files=targets,
                paths=paths,
                trace_progress=_stream_trace_progress(label),
                trace_budget_s=_trace_budget(args),
                trace_session_budget_s=_trace_session_budget(args),
            )
        except TypeError:
            code = run_with_live_suite(root, lambda: _run(args), target_files=targets)
    if code is None:
        sys.stderr.write(_format_session_warning(diagnostic))
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


def _format_session_warning(diagnostic: dict[str, Any]) -> str:
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
        return (
            "WARNING: pytest is not importable in the interpreter that runs the live suite.\n"
            "         Install it (e.g. `pip install pytest`) in that environment, or run\n"
            "         Detective from an interpreter that has it.\n"
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


def _run(args) -> int:
    if args.command == "regime":
        from dataclasses import asdict as _asdict

        from .regime import apply_migration, plan_migration, resolve_regime

        target_file = _split_target(args.target)[0] if args.target else None
        regime = resolve_regime(args.project_root, target_file)
        plan = plan_migration(regime)
        applied = apply_migration(plan) if args.migrate else ()
        if args.migrate:
            # Re-read: the report must describe the tree as it IS now, not as it was before we
            # wrote to it. Reporting the pre-migration regime after migrating is how a tool
            # tells you it fixed something and shows you the evidence that it did not.
            regime = resolve_regime(args.project_root, target_file)
            plan = plan_migration(regime)
        if args.json:
            print(json.dumps({"regime": _asdict(regime), "applied": list(applied)}, indent=2, default=str))
        else:
            print(_format_regime(regime, plan, applied, args.target))
        # A conflict is the answer, not a crash: exit 2 so a script can gate on it, the same
        # code every other command returns when it refuses for the same reason.
        return 2 if regime.conflicts else 0

    if args.command == "purge":
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
            print(json.dumps({"removed": list(removed), "reclaimed_bytes": reclaimed}))
        elif removed:
            print(f"purged {len(removed)} cache file(s), reclaimed {reclaimed // 1024} KB:")
            for path in removed:
                print(f"  - {path}")
        else:
            print("nothing to purge — no cached analysis found (a clean state)")
        return 0

    file, function = _split_target(args.target)

    if args.command == "flag":
        from .engine import profile
        from .equivalents import add_flag

        result = profile(file, function, args.project_root)
        # Match against value-survivors — the SAME set audit/classify report from — so a
        # crash/timeout-killed mutant surfaced by `audit` is flaggable (it is a value-
        # survivor). Using survivor_records here would miss those and read "none surviving".
        rec = next(
            (
                r
                for r in result.value_survivor_records
                if args.mutant_id in (r.get("mutant_id"), r.get("mutant"))
            ),
            None,
        )
        if rec is None:
            ids = (
                ", ".join(r.get("mutant_id", "?") for r in result.value_survivor_records) or "none surviving"
            )
            print(f"no surviving mutant '{args.mutant_id}' for {function} — survivors: {ids}")
            return 1
        add_flag(args.project_root, result.function_key, rec.get("diff_summary", ""), note=args.note)
        suffix = f" ({args.note})" if args.note else ""
        print(f"{result.function_key} — flag · {args.mutant_id}")
        print("")
        print(_row("✓ recorded", f"equivalent{suffix}"))
        print(_row("", "keyed to this exact code — an edit un-flags it."))
        print("")
        # A flag is a CLAIM, and the one place a human overrides the engine. Say what it does
        # and what still outranks it: a real distinguishing witness. Otherwise it reads as a
        # way to silence a survivor, which is how a green board gets flagged into existence.
        print("DONE:  future audit/converge runs treat it as equivalent — unless a witness")
        print("       is found, which outranks your flag. Proof beats judgement.")
        # `function_key`, not `function`: the bare name does not resolve as a target, so the
        # one command this line offers would fail for anyone who pasted it.
        print(f"       Next: detective audit '{result.function_key}'   # it is no longer a gap")
        return 0

    if args.command == "diagnose":
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
        )
        print(json.dumps(asdict(scope), indent=2, default=str) if args.json else _format_scope(scope))
        return 0

    if args.command == "converge":
        import os

        from .converge import converge

        supplied = (
            _parse_supplied_inputs(args.input, _target_ns(file, function, args.project_root))
            if getattr(args, "input", None)
            else None
        )
        result = converge(
            file,
            function,
            args.project_root,
            write_dir=args.write_dir,
            max_iterations=args.max_iterations,
            supplied_inputs=supplied,
            fast=args.fast,
            progress=_stream_progress(function),
            notify=_notify_stderr,
        )
        if args.json:
            print(json.dumps(asdict(result), indent=2, default=str))
            return 0
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
            print(_format_converge_terse(result, report_path, args.project_root))
        return 0

    if args.command == "audit":
        from .audit import audit_suite

        report = audit_suite(
            file,
            function,
            args.project_root,
            progress=_stream_progress(function),
        )
        print(json.dumps(asdict(report), indent=2, default=str) if args.json else _format_audit(report))
        if args.remove and report.redundant_tests:
            from .suite_edit import apply_removals

            result = apply_removals(file, args.project_root, list(report.redundant_tests))
            print(
                f"  removed {len(result.removed)}: {', '.join(result.removed)}"
                if result.removed
                else "  removed nothing"
            )
            if result.not_found:
                print(f"  could not locate: {', '.join(result.not_found)}")
            if result.removed:
                # Re-audit so the user sees the suite is still complete after pruning.
                after = audit_suite(file, function, args.project_root)
                print(
                    f"  after removal: {after.test_count} test(s), "
                    f"complete={after.complete}, minimal cover={after.minimal_test_count}"
                )
        return 0

    if args.command == "decompose":
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
            # decompose's work IS a converge plus a trial-apply per candidate — the slowest
            # command in the CLI, and until now the only one that printed nothing while it ran.
            notify=None if args.json else _notify_stderr,
        )
        print(
            json.dumps(asdict(result), indent=2, default=str)
            if args.json
            else _format_decompose(result, args.apply, args.target, args.project_root)
        )
        return 0

    # Unreachable: argparse (required subparsers) guarantees args.command is one of the
    # registered commands, each handled above. Kept as a defensive guard.
    raise SystemExit(f"detective: unknown command {args.command!r}")


if __name__ == "__main__":
    sys.exit(main())
