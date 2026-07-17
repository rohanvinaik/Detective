"""``detective`` command — a thin dispatcher over the library API.

No compute here: parse args, call the library, format the result. Example:

    detective converge ./module.py::function [--json]
"""

from __future__ import annotations

import argparse
import ast
import difflib
import json
import sys
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


def _parallel_mode(args) -> bool | None:
    """Resolve the tri-state parallelism choice: ``--parallel`` → True (force fan-out),
    ``--serial`` → False (force serial), neither → None (adaptive auto — the default)."""
    if getattr(args, "parallel", False):
        return True
    if getattr(args, "serial", False):
        return False
    return None


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
    lines = [head, ""]

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
    priors = getattr(scope, "learned_priors", []) or []
    if priors:
        shown = ", ".join(f"{cat} {prior:.0%}" for cat, prior in priors)
        lines.append(_row("· learned-weak", f"{shown} — this project's own history"))
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
    """Diagnose's ONE next action.

    Priority, and the priority IS the judgement: split before you pin. When both signals
    agree the function is more than one thing, `decompose` is the move even though behaviour
    is unpinned — it converges internally, and pinning the pieces afterwards is cheaper and
    clearer than pinning the tangle first and then splitting a suite you have to re-derive.
    Otherwise `converge`. The old report printed both and let the reader choose; two actions
    is a choice the reader has no basis to make.
    """
    fn = scope.function
    if entangled and seams >= 1:
        return [
            f"DO THIS:  detective decompose '{fn}' --apply",
            f"          Two signals agree this is >{1} thing. --apply only writes if a generated",
            "          suite PROVES behaviour survived; otherwise it tells you what it needs.",
        ]
    if spec.unspecified_dof:
        return [
            f"DO THIS:  detective converge '{fn}'",
            f"          Writes tests for the {spec.unspecified_dof} behaviour(s) nothing pins yet.",
        ]
    return [
        "DONE:  every behaviour this function makes is already pinned by a test.",
        f"       Next (optional): detective audit '{fn}'   # is the suite minimal?",
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
            if op not in _ORDERING_OPS:
                continue
            for m_left, m_op, m_right in m_cmps:
                if m_left == left and m_right == right and m_op in _ORDERING_OPS and m_op is not op:
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
    import os

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
    import os

    prior = _read_per_mutant_ms()
    value = observed_ms if prior is None else 0.7 * prior + 0.3 * observed_ms
    path = _telemetry_cache_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"per_mutant_ms": round(value, 3)}, fh)
    except OSError:
        pass


def _format_survivor_report(rep, signature: str = "", param_names: tuple[str, ...] = ()) -> list[str]:
    """Render the grounded disposition of every leftover survivor: equivalent
    (retained), killable (a suggested test, NOT auto-applied), or uncertain.

    For candidate-equivalent survivors — the Zone-2 residual — emit a PRECISE,
    copy-pasteable hand-back: the surviving mutant id + category + what it changed, the
    target's signature, and the exact ``--input`` skeleton to supply to reach the branch
    and kill it. A user should never have to guess the input from prose.
    """
    if rep is None:
        return []
    lines: list[str] = []
    if rep.equivalent and not rep.killable and not rep.unclassified:
        lines.append(
            "  ✓ every killable mutant killed — remaining survivors have no distinguishing "
            "input (candidate-equivalent, NOT proven)"
        )
    if rep.equivalent:
        cats = ", ".join(sorted({v.category for v in rep.equivalent}))
        tried = rep.equivalent[0].searched
        lines.append(
            f"  candidate-equivalent — retained, UNPROVEN ({len(rep.equivalent)}: {cats}); "
            f"no distinguishing input in {tried} tried. To KILL: supply an input reaching a "
            "mutated branch below (or `flag` if truly equivalent):"
        )
        for v in rep.equivalent:
            lines.append(f"    → mutant {v.mutant_id} [{v.category}]: {_concise_diff(v.diff_summary)}")
            if v.category == "BOUNDARY":
                hint = _boundary_hint(v.diff_summary)
                if hint:
                    lines.append(f"        ↳ {hint}")
        lines += _target_lines(signature)
        lines.append(
            f"      supply:  {_input_template(param_names)}   "
            "# fill the slots to reach a branch above, then re-run converge"
        )
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
    import os

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
    tests = f" · {result.minimal_test_count} test(s)" if result.minimal_test_count else ""
    arrow = f" → {_rel_path(result.written_path)}" if result.written_path else ""
    return f"FINAL {result.function}: {status} · {result.killed}/{total} killed{tests}{arrow}"


def _format_converge(result, show_tests: bool = False) -> str:
    """Validation report: what converge measured and what it left standing.

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
    lines += _format_survivor_report(result.survivor_report, result.signature, result.param_names)
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
    import os

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


def _format_converge_terse(result, report_path: str) -> str:
    """The converge report: what got written, what is left, the ONE next action — then the
    greppable ``FINAL`` banner, which stays LAST.

    ``FINAL`` last is a downstream contract, not a layout choice: tooling tails this output to
    find the result, so the human action sits above it rather than after it. Everything
    verbose lives in the report file, which is always written regardless of `--full`.
    """
    fn = result.function
    rep = result.survivor_report
    lines = [f"{fn} — converge{_headline_counts(result, rep)}", ""]

    if result.written_path:
        # `_rel_path`, like the banner: converge stores ABSOLUTE paths, and a 90-character
        # /private/tmp/... string in a fixed-width column wraps and destroys the report.
        lines.append(
            _row("✓ wrote", f"{result.minimal_test_count} test(s) → {_rel_path(result.written_path)}")
        )
    if rep is not None and rep.killable:
        lines.append(_row("✗ still killable", f"{len(rep.killable)} — a witness exists for each"))
    if rep is not None and rep.unclassified:
        lines.append(_row("⚠ unclassified", f"{len(rep.unclassified)} — the search could not run on them"))
    if result.missing_lines:
        gap = list(result.missing_lines)
        lines.append(_row("✗ uncovered", f"{len(gap)} line(s): {gap[:8]}"))
    if rep is not None and rep.equivalent:
        lines.append(_row("· unproven-equiv", f"{len(rep.equivalent)} — no input distinguishes them"))
    if report_path:
        lines.append(_row("· full report", report_path))
    lines.append("")
    lines += _converge_action(result, rep)
    lines.append("")
    lines.append(_final_banner(result))
    return "\n".join(lines)


def _converge_action(result, rep) -> list[str]:
    """Converge's ONE next action.

    Same rule as decompose's residual, for the same reason: `--input` parses an allowlist, so
    for a function taking a domain object there is no string that satisfies it and printing
    the template hands the reader a command that always errors. `inputs_expressible` decides.

    `flag` comes LAST and only when nothing else is outstanding. It is the one irreversible
    claim a human makes here — asserting a mutant is truly equivalent — and suggesting it
    while a real gap is open invites someone to flag their way to a green board.
    """
    fn = result.function
    blocked = rep is not None and (rep.killable or rep.unclassified)
    if blocked or result.missing_lines:
        # TRUTHY, not `is False`. `None` means nothing exercised the function AT ALL — the
        # case that most needs a test — and `is False` let it fall through to the `--input`
        # branch, printing the exact dead-end command this check exists to prevent.
        if rep is None or not rep.inputs_expressible:
            sig = result.signature or f"{fn}(...)"
            return [
                f"DO THIS:  add ONE test that calls {sig} with real arguments.",
                "          Detective captures them from your test and pins the rest.",
                "          (its arguments have no literal form, so --input cannot carry them.)",
            ]
        return [
            # `_input_template` already carries the `--input` flag; naming it again emitted
            # `--input --input "(...)"`.
            f"DO THIS:  detective converge '{fn}' {_input_template(result.param_names)}",
            "          Fill the slots with one real call, to reach what synthesis could not.",
        ]
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


def _residual_action(r, proof, rep) -> list[str]:
    """The next action when the proof is incomplete — the one line that has to be right.

    Three states, three DIFFERENT actions, because `--input` cannot express every parameter:

    * nothing exercised the function (`inputs_expressible is None`) -> a test is the only way
      in; the engine's `note` already says so and names each parameter's type.
    * something exercised it but has no literal form (False) -> the working input came from
      CAPTURE (a real object out of the user's own tests). `--input` would reject the only
      value that works, so ask for the test that produces more of them.
    * everything is typeable (True) -> `--input` is real, and is the fastest path.

    Collapsing these into one `supply --input` line is what made the tool look broken on any
    function taking a domain object: the reader did exactly what it said and got back
    `--input only [ast] are available — 'Account' is not`.
    """
    out: list[str] = []
    if rep is None:
        out.append(_row(f"{proof.final_survivors} unpinned", "the classification did not run, so which"))
        out.append(_row("", "mutants block is unknown. Source NOT touched."))
        out.append("")
        out.append(f"DO THIS:  detective converge '{r.function}' --full     # then re-run decompose")
        return out

    n_kill, n_unc, n_eq = len(rep.killable), len(rep.unclassified), len(rep.equivalent)
    # The cause has to agree with the action below it. "an input can kill them" next to
    # "--input cannot carry it" is two true sentences that read as a contradiction, and a
    # reader resolves that by distrusting both.
    if not n_kill:
        why = "synthesis never reached them."
    elif rep.inputs_expressible:
        why = "a witness exists — an input can kill them."
    else:
        why = "a witness exists, but only a real object reaches it."
    out.append(_row(f"{n_kill + n_unc} block the proof", why))
    if n_eq:
        out.append(_row("", f"{n_eq} candidate-equivalent do NOT block."))
    out.append(_row("", "Your source was NOT touched."))
    out.append("")

    sig = proof.signature or f"{r.function}(...)"
    if rep.inputs_expressible:
        slots = _input_template(proof.param_names)
        out.append(f"DO THIS:  detective decompose '{r.function}' --apply {slots}")
        out.append("          Fill the slots with one real call. That kills the blockers, the")
        out.append("          proof completes, and the extraction applies in the same run.")
    else:
        # No literal form exists for at least one parameter, so naming `--input` here would
        # be printing a command that cannot be run.
        first = (proof.param_names or ("it",))[0]
        out.append(f"DO THIS:  add ONE test that calls {sig} with real arguments.")
        out.append("          Detective captures them from your test and proves the rest.")
        out += _target_line(rep)
        out.append(f"          (`{first}` has no literal form, so --input cannot carry it.)")
    return out


def _target_line(rep) -> list[str]:
    """Name the LINE a blocking mutant sits on, so "add a test" is aimed.

    Without it the instruction is identical every round and the reader is guessing which
    branch to reach — the number moves, so they are converging, but by luck. The engine
    already holds the answer: a killable verdict carries the mutation, and `_concise_diff`
    reduces it to the changed line. Telling someone to write a test without saying what it
    must reach is the difference between an instruction and a chore.
    """
    target = next(iter(rep.killable), None)
    if target is None:
        return []
    changed = _concise_diff(target.diff_summary).strip().splitlines()
    return [f"          Aim it at:  {changed[0].strip()}"] if changed else []


def _format_decompose(r, applied_mode: bool) -> str:
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
    lines: list[str] = []
    if not r.applied and not r.proposed and not r.unsafe_blocks:
        return f"{r.function} — decompose\n\nDONE:  no separable block. There is no seam here to split."

    proof = r.proof
    proof_incomplete = proof is not None and not proof.functionally_complete
    rep = proof.survivor_report if proof is not None else None
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
        if proof is not None:
            lines.append(f"       Next (optional): converge '{r.function}' on the new helper(s).")
        return "\n".join(lines)

    validated = [d for d in r.proposed if d.validated]
    if validated and not applied_mode:
        lines.append(f"DO THIS:  detective decompose '{r.function}' --apply")
        lines.append("          The proof already passed. --apply writes it. Nothing else is needed.")
        return "\n".join(lines)

    if proof is None:
        lines.append(f"DO THIS:  detective converge '{r.function}'")
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

    lines += _residual_action(r, proof, rep)
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
    if a.candidate_equivalent:
        lines.append(
            _row("· unproven-equiv", f"{a.candidate_equivalent} survivor(s) — no input distinguishes them")
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
    """Audit's ONE next action, in priority order — the order is the judgement.

    A failing test outranks everything: the suite contradicts the code, so every other number
    here was measured against a suite that does not pass, and acting on them first is acting
    on sand. Then real gaps (converge writes them), then bloat, then the equivalents — last,
    because `flag` is the only irreversible-ish claim a human makes here and it should never
    be suggested while a real gap is outstanding.
    """
    if a.failing_tests:
        return [
            "DO THIS:  fix or delete the failing test(s) above, then re-run audit.",
            "          Detective will NOT touch them: a test failing on current code is either",
            "          a wrong expectation or a real regression, and only you can tell which.",
        ]
    if a.killable_gaps or a.missing_lines:
        return [
            f"DO THIS:  detective converge '{a.function}'",
            "          Writes the missing tests and wires them into pytest.",
        ]
    if a.redundant_tests:
        return [
            f"DO THIS:  detective audit '{a.function}' --remove",
            f"          Deletes the {len(a.redundant_tests)} redundant test(s). Nothing else changes.",
        ]
    if a.candidate_equivalent and a.candidate_equivalent_ids:
        first = a.candidate_equivalent_ids[0]
        more = (
            f"  ({len(a.candidate_equivalent_ids) - 1} more in the report)"
            if a.candidate_equivalent > 1
            else ""
        )
        return [
            "DONE:  every killable behaviour is pinned and every line covered. What remains",
            "       cannot be distinguished by any input Detective found — whether it is truly",
            "       equivalent is UNDECIDABLE in general, so the engine will not claim it.",
            f"       If you can prove one is: detective flag '{a.function}' {first} --note \"why\"{more}",
        ]
    if a.unclassified:
        return [
            "DONE:  no gaps found. Some survivors could not be classified at all — the search",
            "       could not run on them. Not gaps, not equivalents: unknown.",
        ]
    return ["DONE:  the suite is complete and minimal. Nothing to do."]


_COMMAND_HELP = {
    "diagnose": "START HERE — what does this function actually do, and what to run next (read-only)",
    "converge": "write a complete, minimal pytest suite for a function (the flagship; writes files)",
    "decompose": "split a tangled function into helpers — applied only when PROVEN behavior-preserving",
    "audit": "assess an EXISTING suite: complete? minimal? which tests to prune",
}


def _parse_supplied_inputs(raw: list[str]) -> list[tuple]:
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
            out.append(parse_input_expression(s))
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
        description="Read what a function actually does, pin it with tests, and split it "
        "SAFELY — every rewrite is applied only when a generated suite proves behavior "
        "survived. Start read-only: `detective diagnose path/to/file.py::function`.",
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
        p = sub.add_parser(name, help=_COMMAND_HELP[name])
        p.add_argument("target", help="file.py::function")
        p.add_argument("--project-root", default=".", help="project root the target path is relative to")
        p.add_argument("--json", action="store_true", help="emit JSON")
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
        if name in ("converge", "audit", "diagnose"):
            # Default is ADAPTIVE auto: a small serial probe measures this function's real
            # per-mutant cost, then it fans out across CPU cores only when the remaining work
            # justifies it (so small/fast functions never pay the spawn tax). Memory-bounded by
            # construction (workers × per-worker budget ≤ RAM fraction); verdicts identical to
            # serial. ``--parallel`` forces the whole run parallel; ``--serial`` forces serial.
            p.add_argument(
                "--parallel",
                action="store_true",
                help="force fan-out across CPU cores for the whole run (skip the adaptive "
                "probe). Per-mutant progress streaming is disabled in parallel.",
            )
            p.add_argument(
                "--serial",
                action="store_true",
                help="force serial — disable the adaptive auto-parallelization (debugging, or "
                "a machine where process spawn is constrained).",
            )
        if name == "diagnose":
            p.add_argument(
                "--learn",
                action="store_true",
                help="fold this run's per-category value-survival into the project's "
                ".wesker/mutation_report.json and show the learned-weak priors — which "
                "mutation categories THIS project recurrently leaves value-unspecified",
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
    flag_p = sub.add_parser("flag", help="mark a surviving mutant as truly equivalent (manual oracle)")
    flag_p.add_argument("target", help="file.py::function")
    flag_p.add_argument("mutant_id", help="the surviving mutant id (from `audit`/`diagnose`)")
    flag_p.add_argument("--note", default="", help="why it is equivalent")
    flag_p.add_argument("--project-root", default=".")
    flag_p.add_argument("--json", action="store_true", help="emit JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run a command, then emit a lightweight memory-telemetry footer (human mode).
    The footer is best-effort: monitoring must never fail the actual work. It goes to
    STDERR — advisory monitoring, like progress — so STDOUT ends on the result banner and
    stays clean for piping."""
    args = _build_parser().parse_args(argv)
    code = _run_live(args)
    if not getattr(args, "json", False):
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
    if getattr(args, "command", None) == "purge" or not root:
        return _run(args)
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
    return code


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

        _par = _parallel_mode(args)
        scope = diagnose(
            file,
            function,
            args.project_root,
            learn=getattr(args, "learn", False),
            use_parallel=_par,
            progress=None if _par else _stream_progress(function),
            # The traced baseline runs in THIS process even when the mutation loop fans out, so
            # the trace reporter is wired regardless of `_par` — it is the phase that was silent.
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

        supplied = _parse_supplied_inputs(args.input) if getattr(args, "input", None) else None
        _par = _parallel_mode(args)
        result = converge(
            file,
            function,
            args.project_root,
            write_dir=args.write_dir,
            max_iterations=args.max_iterations,
            supplied_inputs=supplied,
            fast=args.fast,
            use_parallel=_par,
            progress=None if _par else _stream_progress(function),
            notify=_notify_stderr,
        )
        if args.json:
            print(json.dumps(asdict(result), indent=2, default=str))
            return 0
        # The full report always goes to a readable file; the terminal stays minimal
        # (a banner + the one quick action) unless --full is asked for.
        full = _format_converge(result, show_tests=True)
        qn = result.function.split("::")[-1]
        report_path = _write_converge_report(os.path.abspath(args.project_root), qn, full)
        print(full if args.full else _format_converge_terse(result, report_path))
        return 0

    if args.command == "audit":
        from .audit import audit_suite

        _par = _parallel_mode(args)
        report = audit_suite(
            file,
            function,
            args.project_root,
            use_parallel=_par,
            progress=None if _par else _stream_progress(function),
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

        supplied = _parse_supplied_inputs(args.input) if getattr(args, "input", None) else None
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
            else _format_decompose(result, args.apply)
        )
        return 0

    # Unreachable: argparse (required subparsers) guarantees args.command is one of the
    # registered commands, each handled above. Kept as a defensive guard.
    raise SystemExit(f"detective: unknown command {args.command!r}")


if __name__ == "__main__":
    sys.exit(main())
