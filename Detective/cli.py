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

from . import __version__


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
    """One-block rendering of a ScopeMap — the raw read, then a plain-language layer
    for a user who doesn't care about the theory (what it means + what to run)."""
    spec, kq = scope.specification, scope.kill_quality
    lines = [
        f"{scope.function}  [regime {scope.regime}]",
        f"  {spec.behavioral_variants} variants; {spec.distinctions_pinned} pinned, "
        f"{spec.unspecified_dof} unspecified, {spec.inert_freedom} inert",
        f"  kill quality: {kq.by_value_assertion} value-assertion, {kq.by_crash} crash"
        + (f"  ⚠ {kq.warning}" if kq.warning else ""),
    ]
    if scope.surviving_categories:
        lines.append(f"  surviving categories: {', '.join(scope.surviving_categories)}")
    # No tests at all: the 0% is "nothing to kill with", not "weak tests". Say so
    # loudly so a fresh user doesn't read an absent suite as a failing one.
    if getattr(scope, "tests_discovered", -1) == 0:
        lines.append(
            "  ⚠ NO tests discovered for this function — the counts above reflect ABSENT "
            "tests, not weak ones; run `converge` to generate them"
        )
    # Learned-weak (opt-in --learn): this project's OWN recurring value-gaps, highest
    # value-survival first. It IS learning from the user's code+tests — surface it plainly.
    priors = getattr(scope, "learned_priors", []) or []
    if priors:
        shown = ", ".join(f"{cat} {prior:.0%}" for cat, prior in priors)
        lines.append(
            f"  learned-weak (this project's history, value-survival): {shown} "
            "— weakest first; fast runs spend budget here first"
        )
    # Plain-language layer: what this means and what to do next.
    lines.append("  in plain terms:")
    if spec.unspecified_dof > 0:
        lines.append(
            f"    → {spec.unspecified_dof} behavior(s) no test pins yet — "
            "run `converge` to generate tests for them"
        )
    else:
        lines.append("    → every behavior this function makes is already pinned by a test")
    if kq.warning:
        lines.append(
            "    → tests mostly check it RUNS, not WHAT it returns — return values may be under-tested"
        )
    # Decompose guidance from TWO independent signals: regime B (behaviorally entangled by
    # the mutation profile) and structural seams (a clean single-exit, small-interface block
    # the deterministic clustering found). Only when BOTH fire is it a genuine decomposition
    # target — flag that loudly; when they disagree, point at the right tool instead of the
    # old blanket "decompose may split it" that contradicted itself on flat-but-untested code.
    seams = getattr(scope, "decompose_seams", 0)
    if scope.regime == "B" and seams >= 1:
        lines.append(
            f"    ★ LOOK HERE FIRST — two independent signals agree this is really >1 thing: "
            f"behaviorally entangled (regime B) AND {seams} clean structural seam(s). "
            "`decompose` proves it's behavior-preserving and splits it."
        )
    elif scope.regime == "B":
        lines.append(
            "    → behaviorally entangled, but structurally one piece (no clean extraction) — "
            "`converge` to pin the interleaved behaviors; `decompose` has no seam to split here."
        )
    elif seams >= 1:
        lines.append(
            f"    → behavior looks cohesive, but a clean structural seam ({seams}) exists — "
            "`decompose` is available and provably safe if you want it simpler."
        )
    return "\n".join(lines)


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
        return "✗ INCOMPLETE"
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
        status = "✗ INCOMPLETE" + (f" · {' · '.join(bits)}" if bits else "")
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
        lines.append(
            f"  DOF: {universe} behavioral degrees of freedom · {mode} · "
            f"{result.killed}/{universe} = {_score(result.killed, universe)} of DOF specified · "
            f"{tail}"
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
        free = f"{_score(result.killed, universe)} resolved by structure for free"
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
    """The default terminal view: a clean, minimal block — a plain-language verdict, the ONE
    quick copy-pasteable action if any, and a pointer to the full report — ending with the
    greppable ``FINAL`` banner. Everything verbose lives in the report file / the test file."""
    fn = result.function
    lines = [f"{fn} — converge", f"  {_plain_terms(result)}"]
    rep = result.survivor_report
    template = _input_template(result.param_names)
    # Lead with the action that makes PROGRESS: supply an input to kill/classify a residual
    # or to cover a line gap. Only when the sole remaining thing is a candidate-equivalent do
    # we surface `flag` — and even then supplying a distinguishing input (a kill) comes first,
    # so the tool never nudges a user to give up on a mutant that a richer input would kill.
    if rep is not None and (rep.killable or rep.unclassified):
        n = len(rep.killable) + len(rep.unclassified)
        lines.append(
            f"  ▶ {n} residual(s) need a real input to kill/classify — supply {template} (details in report)"
        )
    elif result.missing_lines:
        gap = len(result.missing_lines)
        lines.append(f"  ▶ {gap} line(s) uncovered — supply {template} to reach them (details in report)")
    elif rep is not None and rep.equivalent:
        ids = [v.mutant_id for v in rep.equivalent]
        more = f" (+{len(ids) - 1} more in report)" if len(ids) > 1 else ""
        lines.append(
            f"  ▶ {len(ids)} unproven-equivalent — supply a distinguishing input to kill, "
            f"or `detective flag '{fn}' {ids[0]} --note \"why\"`{more}"
        )
    if report_path:
        lines.append(f"  full report → {report_path}")
    lines.append(_final_banner(result))
    return "\n".join(lines)


def _format_decompose(r, applied_mode: bool) -> str:
    """Show what a decomposition did or would do: extractions that preserve the
    SPECIFIED behavior (proven against the target's own MUTATION-complete suite; auto-applied
    under --apply, else marked appliable), extractions not yet provable (the suite is not
    mutation-complete — a killable mutant needs an input synthesis could not reach), and
    blocks skipped as unsafe — with the actual code."""
    lines = [f"{r.function}: decomposition"]
    if not r.applied and not r.proposed and not r.unsafe_blocks:
        return f"{r.function}: no separable blocks — nothing to decompose"
    for ex in r.applied:
        lines.append(
            f"  ✓ APPLIED (specified behavior preserved, auto): {ex.helper_name}"
            f"({', '.join(ex.params)}) -> {', '.join(ex.returns) or 'None'}"
        )
        lines += [f"    │ {line}" for line in ex.new_source.splitlines()[:4]]
        lines.append("    │ …")
    # WHY an extraction is unproven decides what the user should do, so the three causes must
    # not share one message. A suite that IS mutation-complete and still rejects the rewrite has
    # PROVEN it changes behavior — a verdict, not a gap; telling that user to supply an `--input`
    # sends them to close a hole that isn't there.
    proof = getattr(r, "proof", None)
    proof_incomplete = proof is not None and not getattr(proof, "functionally_complete", False)
    for dec in r.proposed:
        ex = dec.extraction
        if dec.validated:
            tag = "appliable — specified behavior preserved — re-run with --apply"
        elif proof is None:
            tag = "can't PROVE preservation — no suite specifies this function yet (run `converge` first)"
        elif proof_incomplete:
            tag = "can't PROVE preservation yet — the proof suite is not mutation-complete (residual below)"
        else:
            tag = "REJECTED — the mutation-complete suite PROVES this extraction changes behavior"
        lines.append(
            f"  → {tag}: {ex.helper_name}({', '.join(ex.params)}) -> {', '.join(ex.returns) or 'None'}"
        )
        lines += [f"    │ {line}" for line in ex.new_source.splitlines()[:6]]
        lines.append("    │ …")
    for block in r.unsafe_blocks:
        lines.append(f"  ✗ not extractable: {block}")
    # The residual hand-back. An unproven extraction means converge could not reach
    # mutation-completeness — a KILLABLE mutant that synthesis could not distinguish, i.e.
    # the "semantic prior the AST needs". Surface the EXACT input to supply (converge already
    # computed it) so the user closes the loop, instead of a dead-end "review it yourself".
    # Only for a genuinely INCOMPLETE proof: a complete suite that rejects the rewrite has
    # nothing for the user to supply.
    unproven = any(not d.validated for d in r.proposed)
    if unproven and proof is not None and proof_incomplete:
        # The blockers are the VALUE-survivors — mutants the suite hasn't pinned. Some are
        # killable-with-a-witness, some couldn't even be classified because the synthesized
        # input crashes the function; either way the fix is the same: supply a valid input.
        blocking = getattr(proof, "final_survivors", 0)
        lines.append(
            f"  ▶ to prove + auto-apply: {blocking} mutant(s) the suite has not pinned — synthesis "
            "could not build a valid distinguishing input for this function's parameters."
        )
        lines += _target_lines(proof.signature)
        lines.append(
            f"      supply:  decompose '{r.function}' --apply {_input_template(proof.param_names)}"
            "   # a valid input for the slot(s); converge then reaches mutation-completeness and the"
        )
        lines.append("               extraction is proven and applied in the same run.")
    if r.applied or any(d.validated for d in r.proposed):
        # The information-conservation frame: the transform adds no new behavior, so it
        # cannot introduce a bug into what is SPECIFIED — and it deliberately does not
        # bake in behavior nothing specifies. That is a feature, not a caveat.
        lines.append(
            "  ℹ preserves every SPECIFIED behavior (information-conservative — introduces no "
            "new behavior); unspecified DOF are not baked in. `converge` the pieces to ground "
            "them — a quick pass that SURFACES latent under-specification instead of preserving it."
        )
    if not applied_mode and any(d.validated for d in r.proposed):
        lines.append("  (run `decompose --apply` to write the extractions)")
    return "\n".join(lines)


def _format_audit(a) -> str:
    """Read-only audit of an existing suite: completeness on both axes, the
    pointless tests to propose removing, and the gaps to propose filling. Nothing
    is written — every action a real run would take is stated, not taken."""
    # Three tiers, not two: a suite that kills every killable mutant and covers every line
    # but leaves UNPROVEN candidate-equivalents is not "incomplete" (no real gaps) — say so,
    # and point at `flag`, instead of a misleading ✗.
    if a.complete_modulo_equivalent:
        verdict = f"✓ complete modulo {a.candidate_equivalent} candidate-equivalent (flag to confirm)"
    elif a.complete:
        verdict = "✓ complete"
    else:
        verdict = "✗ incomplete"
    lines = [
        f"{a.function}: {a.test_count} existing test(s) — {verdict}   [audit reads only — writes nothing]",
        f"  kills: {a.kill_pct}%  |  mutant-complete={a.mutant_complete}  line-complete={a.line_complete}",
        f"  minimal cover: {a.minimal_test_count} test(s)"
        + (f"  (bloat: {a.bloat} redundant)" if a.bloat else "  (no bloat)"),
    ]
    if a.killable_gaps:
        lines.append(f"  ✗ {len(a.killable_gaps)} killable mutant(s) NOT killed — specification gaps:")
        lines += [f"      · {g}" for g in a.killable_gaps[:8]]
        if len(a.killable_gaps) > 8:
            lines.append(f"      … and {len(a.killable_gaps) - 8} more")
    if a.missing_lines:
        lines.append(f"  ✗ {len(a.missing_lines)} uncovered line(s): {list(a.missing_lines)}")
    if a.failing_tests:
        lines.append(
            f"  ⚠ {len(a.failing_tests)} test(s) FAIL on current code — INVESTIGATE "
            f"(wrong assertion OR a real regression; never auto-removed): {', '.join(a.failing_tests)}"
        )
    if a.redundant_tests:
        lines.append(
            f"  PROPOSED removals ({len(a.redundant_tests)}, pointless for BOTH kills and lines "
            f"— confirm to delete, never auto): {', '.join(a.redundant_tests)}"
        )
    if a.candidate_equivalent:
        lines.append(
            f"  · {a.candidate_equivalent} survivor(s) candidate-equivalent — no distinguishing input found "
            "(UNPROVEN: `flag` to confirm equivalent, or add a distinguishing input to kill)"
        )
    if a.unclassified and not a.killable_gaps:
        lines.append(
            f"  ⚠ {a.unclassified} survivor(s) UNCLASSIFIED — the search could not distinguish them; "
            "may be equivalent (prove + `flag`) or need a reaching input (not a confirmed gap)"
        )
    if a.manual_equivalent:
        lines.append(f"  ✓ {a.manual_equivalent} survivor(s) manually-flagged equivalent (oracle — not gaps)")
    if a.complete and not a.redundant_tests:
        lines.append("  nothing to do — suite is complete and minimal")
    # Forward-chain: name the next command for the state we're in (audit itself writes nothing).
    if a.killable_gaps or a.missing_lines:
        lines.append(
            "  ▶ next: `converge` to synthesize the missing tests (WRITES test files + wires conftest)"
        )
    elif a.candidate_equivalent or a.unclassified:
        lines.append(
            "  ▶ next: prove equivalence then `flag <mutant_id>`, or add a "
            "distinguishing input and `converge`"
        )
    elif a.redundant_tests:
        lines.append("  ▶ next: `audit --remove` to delete the redundant tests (confirm — never auto)")
    return "\n".join(lines)


_COMMAND_HELP = {
    "converge": "generate a COMPLETE, minimal pytest suite for a function (the flagship)",
    "audit": "assess an EXISTING suite: complete? minimal? which tests to prune",
    "decompose": "extract entangled blocks into helpers (behavior-preserving; --apply to write)",
    "diagnose": "show a function's behavioral scope + what to run next (read-only)",
}


def _parse_supplied_inputs(raw: list[str]) -> list[tuple]:
    """Parse ``--input`` Python-literal strings into positional-argument tuples — the
    Zone-2 residual a human fills THROUGH the tool when deterministic synthesis provably
    could not exercise a degree of freedom. Each literal is one call's argument tuple; a
    bare non-tuple literal is taken as a single positional argument. ``ast.literal_eval``
    only — no code execution, matching Detective's no-exec discipline."""
    out: list[tuple] = []
    for s in raw:
        try:
            value = ast.literal_eval(s)
        except (ValueError, SyntaxError) as exc:
            raise SystemExit(f"detective: --input is not a valid Python literal: {s!r} ({exc})") from None
        out.append(value if isinstance(value, tuple) else (value,))
    return out


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="detective",
        description="Generate/audit a function's pytest suite from its mutation profile. "
        "Typical use: `detective converge path/to/file.py::function`.",
    )
    parser.add_argument("--version", action="version", version=f"detective {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("converge", "audit", "decompose", "diagnose"):
        p = sub.add_parser(name, help=_COMMAND_HELP[name])
        p.add_argument("target", help="file.py::function")
        p.add_argument("--project-root", default=".", help="project root the target path is relative to")
        p.add_argument("--json", action="store_true", help="emit JSON")
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
                help="supply a residual input as a Python-literal positional-arg tuple — e.g. "
                "\"({'a':['t1'],'b':['t1','t2']}, {})\" — to kill a mutant deterministic synthesis "
                "could not exercise (a Zone-2 residual, filled through the tool). Repeatable; a bare "
                "non-tuple literal is one positional arg.",
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
    purge_p = sub.add_parser("purge", help="delete regeneratable analysis cruft left by old runs")
    purge_p.add_argument("--project-root", default=".")
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
    code = _run(args)
    if not getattr(args, "json", False):
        try:
            from Wesker.memory_guard import telemetry

            sys.stderr.write(f"  [{telemetry()}]\n")
        except Exception:  # noqa: BLE001 — telemetry is advisory, never fatal
            pass
    return code


def _run(args) -> int:
    if args.command == "purge":
        from Wesker.memory_guard import purge_caches

        removed, reclaimed = purge_caches(args.project_root)
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
        print(f"flagged {args.mutant_id} as equivalent — {result.function_key}{suffix}")
        print("  future audit/converge runs will treat it as equivalent (a witness would still override)")
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
            file, function, args.project_root, write=args.apply, supplied_inputs=supplied
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
