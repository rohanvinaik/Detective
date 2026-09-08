"""Optional MCP surface — Detective, rendered for an LLM caller.

Requires the ``mcp`` extra (``uv pip install 'detective-spec[mcp]'``); ``mcp`` is imported
lazily so the core package stays Wesker + stdlib only. No compute here — each tool calls
the library and renders the result.

    detective-mcp        # or: python -m Detective.mcp_server

WHY THIS FILE DOES NOT RETURN ``asdict(result)``
------------------------------------------------
It used to. ``asdict(ConvergeResult)`` is ``killed``, ``value_killed``, ``universe_size``,
``final_survivors``, ``minimal_test_count`` — ratios, with no stated next action anywhere
in the payload. Handed that, an LLM does the only thing that payload affords: it treats the
ratio as a dial, and turns it. There is no instruction in a dataclass saying *stop, the
remaining work is not yours to compute*, so the caller invents a plan and grinds. That
failure mode is not hypothetical and it is not cheap.

WHY IT DOES NOT RELAY THE CLI's TEXT EITHER
-------------------------------------------
``cli.py`` already renders every one of these results correctly and completely, for a human.
Relaying that text through MCP was tried and it is not the fix: the identical bytes went to
an LLM's stdout, in full, and were piped to ``tail -3`` unread. Same bytes, different
transport, same outcome. The CLI's rendering is a *theorem* — every clause is exactly as
true as the engine can make it. This file's output is a *prompt*. A theorem is true or
false; a prompt is effective or ineffective. They are different objects with different
correctness criteria, and this one is authored against the second.

So the text below deliberately says things the CLI would not say, and the author of the CLI
would call several of them wrong. They stay. Specifically:

* **No score in the default view.** A ratio is the single most reliable way to make an LLM
  caller reach outside the tool. The numbers are real and they are correct; they are behind
  ``full=True``, where reading them is a deliberate act rather than an ambient temptation.
* **The mutant diffs ARE in the default view.** The engagement problem is symmetrical: too
  terse and the task reads as scut work to be shortcut, too loud and the signal is lost. The
  specific behavioral distinctions are the interesting part and the honest part. Show those.
* **One next action, stated as an imperative, never a menu.** Not because the world is
  unambiguous — an equivalent-mutant fork is genuinely undecidable — but because the
  *caller's legal move set* is singular even when the epistemics are not.
* **Flat prohibitions on the moves that are not in the protocol.** "More passes will not
  help." "There is nothing here to derive." Strictly these overclaim. They are the load-
  bearing sentences.

The engine's epistemics are untouched. Nothing here re-decides a verdict, softens an
UNPROVEN, or spends a crash kill to flatter a number. This file chooses what a caller sees
first and what it is told to do next. That is the whole of its remit.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from .cli import _reachable_paths

# ── rendering ────────────────────────────────────────────────────────────────────────
# One rule: every response closes every circle. After reading it there is no question left
# whose answer is "go look." Either the caller is told the exact next call, or it is done.


def _input_template(param_names: tuple[str, ...]) -> str:
    """The ``inputs=[...]`` skeleton shaped to the target's parameters."""
    if not param_names:
        return '"(<value>,)"'
    slots = ", ".join(f"<{p}>" for p in param_names)
    tail = "," if len(param_names) == 1 else ""
    return f'"({slots}{tail})"'


def _ask_for_input(
    tool: str,
    file: str,
    function: str,
    param_names: tuple[str, ...],
    why: str,
    expressible: bool | None = True,
    root: str = ".",
    rep: Any = None,
    proof: Any = None,
    apply: bool = False,
) -> list[str]:
    """The hand-back: every input Detective DERIVED, batched into ONE call.

    The DERIVATION comes from `cli._derive_inputs` — shared, because it must never drift. The
    RENDERING is this surface's own, because a caller here makes a CALL: `inputs=["(...)"]`,
    `apply=True`. Reusing the CLI's rendered text put `--input` — a flag that does not exist
    here — into a tool caller's instructions, which is worse than a duplicate: it is a command
    that cannot be run, in the register the caller trusts most.

    Phrased as a request for knowledge, not a deficiency to close by effort. The distinction is
    the whole ballgame: a caller told "30 residuals remain" optimizes; a caller told "here is
    the call, pass it" does that and stops.
    """
    from .cli import _derive_inputs

    kind, items, total = _derive_inputs(proof, rep) if proof is not None else ("author", [], 0)
    tmpl = _input_template(param_names)
    tail = ", apply=True" if apply else ""

    if kind == "witness":
        inputs = ", ".join(f'"{a}"' for a in items)
        out = [
            "",
            f"DO THIS: {tool}(file={file!r}, function={function!r}, inputs=[{inputs}]{tail})",
            "",
            f"  {why}",
            f"  Detective RAN each of those {len(items)} call(s) and watched a mutant differ. They are",
            "  SUGGESTED, not written for you: the engine could not verify the tests sound, and",
            "  it does not write what it cannot prove. Pass them and it derives the rest.",
        ]
        if total > len(items):
            out.append(f"  ({total - len(items)} more are in the full report — full=True.)")
        return out

    if kind == "hand_pin":
        # The crash-only sibling of `witness` (#44): an input can NOT close these — the two outcomes
        # differ only by exception type/message (or share a repr), so passing them as `inputs=[...]`
        # recalls the same pin and the number never moves. The action that TERMINATES is a
        # hand-written assertion, so this surface must NOT hand back an `inputs=[...]` call that loops.
        out = [
            "",
            f"DO THIS: write a test pinning the exact outcome of the {total} call(s), then re-run {tool}.",
            "",
            f"  {why}",
            "  Detective RAN each and watched a mutant differ — but the difference is an exception",
            "  type/message (or identical reprs), which no == on a return value separates. Passing",
            "  these as inputs cannot close them; assert the exact outcome by hand (pytest.raises).",
        ]
        out += [f"    {i}. {d}" for i, d in enumerate(items, start=1)]
        if total > len(items):
            out.append(f"    ({total - len(items)} more in the full report — full=True.)")
        return out

    if kind == "test":
        out = [
            "",
            f"DO THIS: write a test that calls {function} with the object(s) below, then re-run {tool}.",
            "",
            f"  {why}",
            f"  Detective RAN each of these {total} object(s) and watched a mutant differ — but none",
            "  can be passed as an input string: they are objects only a test can build.",
        ]
        out += [f"    {i}. {d}" for i, d in enumerate(items, start=1)]
        if total > len(items):
            out.append(f"    ({total - len(items)} more in the full report — full=True.)")
        return out

    if kind == "fixture" or (kind == "author" and expressible is False):
        return [
            "",
            f"WRITE TEST: build the domain objects in a fixture, call {function}, then re-run {tool}.",
            f"  {why}",
            "  These inputs are outside the literal grammar. "
            "A primitive decision extraction is another option.",
            *(f"  {item}" for item in items),
        ]

    if kind == "lines":
        return [
            "",
            f"AUTHOR INPUTS: supply calls to {function} that reach these lines, then re-run {tool}.",
            *(f"  {item}" for item in items),
        ]

    if kind == "boundary":
        inputs = ", ".join([tmpl] * len(items))
        out = [
            "",
            f"DO THIS: {tool}(file={file!r}, function={function!r}, inputs=[{inputs}]{tail})",
            "",
            f"  {why}",
            f"  Author {len(items)} call(s) to {function}{_sig_tail(proof)}, one per requirement:",
        ]
        out += [f"    {i}. {rel}" for i, rel in enumerate(items, start=1)]
        if total > len(items):
            out.append(f"    (+{total - len(items)} more in the full report — full=True.)")
        out += [
            "  Each relation is DERIVED from your code — two orderings differ exactly at the",
            "  equality edge — not guessed. Detective derives every test from the calls you pass.",
        ]
        return out

    if kind == "internal":
        out = [
            "",
            f"DO THIS: {tool}(file={file!r}, function={function!r}, inputs=[{tmpl}]{tail})",
            "",
            f"  {why}",
            "  The surviving distinction sits behind an INTERNAL condition — a derived local,",
            "  not a parameter — so no direct input constraint exists. That is the verified",
            "  finding, not a missing derivation:",
        ]
        out += [f"    {i}. {cond}" for i, cond in enumerate(items, start=1)]
        if total > len(items):
            out.append(f"    (+{total - len(items)} more in the full report — full=True.)")
        out += [
            f"  Author one real call to {function}{_sig_tail(proof)} whose execution drives the",
            "  condition(s) above. Detective derives every test from the call you pass.",
        ]
        return out

    return [
        "",
        f"DO THIS: {tool}(file={file!r}, function={function!r}, inputs=[{tmpl}]{tail})",
        "",
        f"  {why}",
        f"  Author one real call to {function}{_sig_tail(proof)}. Any call that RUNS will do —",
        "  Detective derives every test from it. The argument values are the one thing it",
        "  cannot supply: it will not invent a value whose meaning is not in the code.",
        "  A class from the module under test goes in as its constructor, e.g. Account('gold').",
        "  More passes will not help. The information is absent, and you are its only source.",
    ]


def _sig_tail(proof: Any) -> str:
    """`(a, b, c)` from the target's signature, or '' — so the ask names the real parameters."""
    sig = getattr(proof, "signature", "") or ""
    return sig[sig.index("(") :] if "(" in sig else ""


def _render_diagnose(scope: Any, file: str, function: str) -> str:
    """diagnose is read-only. It always terminates in exactly one recommended call."""
    out = [f"{scope.function}  [regime {scope.regime}]"]

    # The mutant IDs are stable identities for `flag`, and useless to read: twelve lines of
    # "off-by-one comparison" is a flood, not a finding. Group by what the edit DOES. The
    # exact per-mutant diffs (`- if total < 0:` / `+ if total <= 0:`) are the genuinely
    # interesting artefact and they do not live on ScopeMap — converge's survivor report
    # carries them. Do not imply they are here.
    unspec = list(scope.unspecified_behaviors)
    # `unspec` is a SAMPLE (hard-capped at scope._MAX_UNSPECIFIED); `total` is the fact.
    # Nothing below may branch on or count the sample — that is how a cap becomes a claim.
    total = scope.specification.unspecified_dof
    no_tests = scope.tests_discovered == 0
    # A truncated trace UNDER-COUNTS coverage, and an under-counted line is indistinguishable
    # from an uncovered one in the numbers. Everything below rests on that measurement, so this
    # goes FIRST and is not optional: `ScopeMap.trace_truncated` exists precisely because "a
    # completeness verdict that quietly rests on a truncated measurement is the one failure this
    # tool cannot afford", and a surface that drops it commits exactly that failure while looking
    # tidier for it. On Regenesis this was 152 of 240 tests.
    cut = list(scope.trace_truncated)
    if cut:
        # A hit traced nothing, so the present tense would describe a measurement this call never
        # made. Name the run that was actually cut — otherwise the reader tunes budgets against a
        # recording, which is an hour that buys nothing.
        cached = getattr(scope, "served_from_cache", False)
        out.append("")
        if cached:
            out.append(f"⚠ This verdict is REPLAYED FROM CACHE, and {len(cut)} test(s) were CUT by")
            out.append("  the trace budget WHEN IT WAS MEASURED. This call traced nothing. The")
            out.append("  budgets are wall-clock, so the machine load that cut it is gone and is")
            out.append("  not reproducible — the cut is a fact about that run, not about your")
            out.append("  code. Those tests' line coverage is")
        else:
            out.append(f"⚠ {len(cut)} test(s) were CUT by the trace budget, so their line coverage is")
        out.append("  UNDER-COUNTED. Anything below may be the budget rather than a real hole.")
        out.append("  This is a measurement limit, not a finding — do not act on it as one.")
        out.append("  Re-run with trace_session_budget=0 AND trace_budget=0 (0 = unbounded).")
        out.append("  The SESSION budget is what cuts: it caps the WHOLE pass, so raising the")
        out.append("  per-test trace_budget alone changes nothing (measured: identical cut).")
        if cached:
            out.append("  Those budgets are a DIFFERENT cache row, so that re-run re-measures")
            out.append("  rather than serving this same row back to you.")
    if unspec:
        kinds: dict[str, int] = {}
        for b in unspec:
            kinds[b.split(": ", 1)[-1]] = kinds.get(b.split(": ", 1)[-1], 0) + 1
        out.append("")
        # The COUNT is `unspecified_dof`; `unspecified_behaviors` is a SAMPLE, hard-capped at
        # `scope._MAX_UNSPECIFIED` (20). Rendering `len()` of the sample as the total stated a
        # number 3.5x too small on a 71-DOF function — and a caller cannot see a cap, so it
        # reads as the whole list. It closes "all 20", reports done, and 51 unpinned
        # behaviours are gone. A bound that is not named is a silent truncation wearing a
        # finding's clothes. The CLI never had this: it renders `unspecified_dof` and does not
        # touch this field.
        out.append(f"{total} behaviour(s) nothing distinguishes:")
        out += [f"  {n} × {desc}" for desc, n in sorted(kinds.items(), key=lambda kv: -kv[1])]
        if total > len(unspec):
            out.append(f"  (kinds above are a sample of {len(unspec)}; the count is all {total})")
        out.append("")
        if no_tests:
            # A 0 here means "nothing to kill with", NOT "weak tests". Those are different
            # situations with identical numbers, and reading the second for the first is the
            # fastest way to conclude the tool is broken.
            out.append("  ⚠ There are NO tests for this function. That count is ABSENT tests,")
            out.append("    not weak ones. Nothing is wrong; nothing has been written yet.")
        else:
            out.append("  Each is a real edit to the function that every existing test passes.")

    seams = scope.decompose_seams
    entangled = scope.regime == "B"

    out.append("")
    if entangled and seams:
        # apply=True, matching the CLI's `--apply`. Without it the caller does exactly what it
        # was told, gets a dry run, and has to be told a second time — and the safety is not the
        # flag anyway, it is the proof: apply=True writes NOTHING it cannot prove.
        out.append(f"DO THIS: decompose(file={file!r}, function={function!r}, apply=True)")
        out.append("")
        out.append("  Two independent signals agree this is more than one function: it is")
        out.append(f"  behaviourally entangled AND has {seams} clean structural seam(s).")
        out.append("  apply=True is safe here: decompose writes a proof suite FIRST and applies")
        out.append("  nothing it cannot prove. If it cannot, it tells you what it needs and")
        out.append("  leaves your source untouched.")
    elif total:
        out.append(f"DO THIS: converge(file={file!r}, function={function!r})")
        out.append("")
        out.append("  Nothing pins those behaviours yet. converge writes the tests that do.")
        if entangled:
            out.append("  (Entangled, but structurally one piece — decompose has no seam here.)")
    else:
        out.append("DONE: every behaviour this engine can enumerate is already pinned.")
        out.append("  Nothing to run. Nothing to derive.")

    return "\n".join(out)


def _render_converge(result: Any, file: str, function: str, full_text: str | None) -> str:
    """converge's terse view. The score is deliberately absent — see the module docstring."""
    if full_text is not None:
        return full_text

    out = [f"{result.function} — converge"]
    if result.written_path:
        from .cli import _rel_path

        out.append(f"  wrote: {_rel_path(result.written_path)}  (ordinary pytest; `pytest -m detective`)")
    # The applicability bound's boundary, stated (`engine.widen_admission`): collected tests with no
    # static path to this function were not traced. Not a knob — there is no opt-in — and not a gap:
    # a missed dynamic reacher under-counts the floor (one redundant generated test), never the ceiling.
    if skipped := getattr(result, "not_consulted", 0):
        out.append(
            f"  not consulted: {skipped} collected test(s) have no static path to this function and were not"
        )
        out.append(
            "  traced. A missed dynamic reacher costs one redundant generated test, never a certificate."
        )

    # DIRECT attribute access, never `getattr(rep, name, default)`. A default silently absorbs a
    # wrong field name, and this file did exactly that: it asked for `candidate_equivalent`,
    # which `SurvivorReport` does not have — the field is `equivalent` — so the lookup returned
    # the default `()` on every run, the branch below never fired, and the tool reported "the
    # suite is complete, nothing to derive" over NINE unproven survivors. The engine had
    # classified them honestly; the renderer promoted UNPROVEN to done. A wrong name must break
    # here loudly instead of quietly overclaiming.
    rep = result.survivor_report
    killable = len(rep.killable) if rep else 0
    params = tuple(result.param_names or ())

    # STANDING BEFORE FINDINGS (#17/#38). Every branch below describes a MEASUREMENT — "every
    # killable mutant is killed", "N survivors remain" — and each is a claim about the source that
    # was measured. If the target changed under the run, or the proof basis did not come back green
    # under real pytest, those sentences are about something that no longer exists or does not run.
    # This surface consulted NEITHER signal and went straight to "DONE: every killable mutant is
    # killed", which is the measurement/decision gap in its purest form: the engine computed the
    # fact, the CLI consumed it, and the renderer re-derived a narrower proxy that could not see it.
    # Read through `certificate_standing` rather than testing the fields here, so this surface
    # cannot drift from the property and the CLI the way it already had.
    from .converge import certificate_standing

    standing = certificate_standing(
        result.functionally_complete,
        result.line_complete,
        result.stale_target,
        result.verification is not None,
        result.verification is not None and result.verification.ok,
        getattr(result, "measurement_gateable", True),
    )
    if standing == "ungateable":
        out.append("")
        out.append("STOP. This is NOT a verdict. Wesker declared the measurement UNGATEABLE —")
        out.append("  the profile was cut, or a timed-out worker could not be contained and may")
        out.append("  still be running. The counts below are a FLOOR, not a result. Re-run on a")
        out.append("  settled machine, or with a larger budget, before reporting anything.")
        return "\n".join(out)
    if standing == "stale":
        out.append("")
        out.append("STOP. This is NOT a verdict. The target file CHANGED while the run was")
        out.append("  measuring it, so the kill-count and the line numbers below describe a")
        out.append("  source that no longer exists. They are not small — they are meaningless.")
        out.append("  Do not act on them, and do not report them. Re-run on the settled file.")
        return "\n".join(out)
    if standing == "unverified":
        status = getattr(result.verification, "status", "unverified")
        out.append("")
        out.append(f"STOP. The proof basis did NOT verify under real pytest ({status}).")
        out.append("  The mutation score can be perfect while the tests Detective wrote do not")
        out.append("  run green in your own pytest — a certificate over a suite that does not")
        out.append("  run is not a certificate. Fix the basis, then re-run.")
        return "\n".join(out)

    if killable or not result.line_complete:
        why = "Synthesis is exhausted. What is left needs a value only you can supply."
        # `rep.inputs_expressible` decides WHICH hand-back. None (nothing exercised the
        # function at all) is the case that most needs a test, so it must not read as True.
        out += _ask_for_input("converge", file, function, params, why, rep=rep, proof=result)
        return "\n".join(out)

    cand = list(rep.equivalent) if rep else []
    manual = list(rep.manual_equivalent) if rep else []
    unclassified = list(rep.unclassified) if rep else []
    if unclassified:
        # Honest uncertainty: the mutant could not be built or the search could not run. It is
        # NOT an equivalent and NOT a gap, and collapsing it into either would be a claim the
        # engine declined to make.
        out.append("")
        out.append(f"DONE: every killable mutant is killed. {len(unclassified)} survivor(s) could")
        out.append("  not be classified at all — the search could not run on them. Not gaps, not")
        out.append("  equivalents, just unknown. Ask the user if it matters; do not guess.")
        return "\n".join(out)
    if cand:
        out.append("")
        out.append(f"DONE: every killable mutant is killed. {len(cand)} survivor(s) remain that")
        out.append("  no VALUE assertion could pin. Whether they are truly equivalent is UNDECIDABLE")
        out.append("  in general — the engine will not claim it, and neither should you.")
        out.append("  Leave them by default. They are not a gap.")
        # Name the crash-only class outright. This used to read "no input could distinguish",
        # which is FALSE of them — an input does, by crash — and a caller who believes it goes
        # looking for the input that would, which cannot exist. There is nothing to supply here.
        if n_crash := sum(1 for v in cand if v.crash_only):
            out.append("")
            out.append(f"  {n_crash} of them are crash-only-distinguishable: your suite ALREADY detects")
            out.append("  them (the mutant raises where the original returns). What is missing is a")
            out.append("  value to pin, not an input — supplying inputs cannot move them.")
        out.append("")
        # `flag` IS a tool now. This branch used to end "ask the user; do not decide it
        # yourself", which was written when it was not — and would have gone on saying so.
        # The judgement is available to you, but the bar is a PROOF, not an impression.
        out.append("  If you can PROVE one cannot change behaviour — an argument from the code")
        out.append('  that holds for EVERY input ("the cap is 0.60 and the branches above sum to')
        out.append('  at most 0.50, so it never fires"), not "looks equivalent" — record it:')
        out.append(f"    flag(file={file!r}, function={function!r}, mutant_id=<id>, why=<your proof>)")
        out.append("  The ids are in full=True. If you have no such argument, say so and stop:")
        out.append("  an UNPROVEN survivor is an honest result and costs nothing.")
        if manual:
            out.append(f"  ({len(manual)} more were already flagged equivalent by a human.)")
        return "\n".join(out)

    out.append("")
    out.append("DONE: the suite is complete. Nothing to run. Nothing to derive.")
    return "\n".join(out)


def _render_audit(a: Any, file: str, function: str) -> str:
    """audit, for a caller. Read-only, always; deletions are proposals a human confirms.

    It had NO renderer here — it relayed the CLI's report under a header saying "ignore its
    instructions", which is a header telling the caller to disobey a `DO THIS:` while it reads
    one. That is not a rule anything follows. Every action audit can suggest is a real tool on
    this surface, so name the tool.
    """
    out = [f"{a.function} — audit · {a.test_count} test(s) · {a.kill_pct}% killed"]

    if a.failing_tests:
        # Outranks everything: the suite contradicts the code RIGHT NOW, so every other number
        # here was measured against a suite that does not pass.
        out.append("")
        out.append(f"⚠ {len(a.failing_tests)} test(s) FAIL on the current code:")
        out += [f"    {t}" for t in a.failing_tests[:6]]
        out.append("")
        out.append("STOP. Do not delete them and do not 'fix' them to green. A test failing on")
        out.append("  correct code is either a wrong expectation or a real regression, and which")
        out.append("  one it is decides whether the CODE or the TEST is wrong. You cannot tell")
        out.append("  from here. Ask the user. Nothing else in this report means anything until")
        out.append("  that is settled.")
        return "\n".join(out)

    if a.killable_gaps or a.missing_lines:
        out.append("")
        if a.killable_gaps:
            out.append(f"{len(a.killable_gaps)} real gap(s) — killable behaviour no test pins:")
            out += [f"    {g}" for g in a.killable_gaps[:6]]
            if len(a.killable_gaps) > 6:
                out.append(f"    (+{len(a.killable_gaps) - 6} more; this is a sample, the count is above)")
        if a.missing_lines:
            out.append(f"{len(a.missing_lines)} line(s) no test covers: {list(a.missing_lines)[:8]}")
        out.append("")
        out.append(f"DO THIS: converge(file={file!r}, function={function!r})")
        out.append("")
        out.append("  That writes the tests. audit only reads — it has told you what is missing")
        out.append("  and that is the whole of what it can do.")
        return "\n".join(out)

    if a.redundant_tests:
        out.append("")
        out.append(f"{len(a.redundant_tests)} test(s) are pointless for THIS FUNCTION's kills and lines:")
        out += [f"    {t}" for t in a.redundant_tests[:6]]
        out.append("")
        out.append("DONE: no gaps. The tests above earn nothing HERE — every mutant of this")
        out.append("  function they kill and every line they cover is already covered by another")
        out.append("  test. That is single-function evidence: one of them can still be the only")
        out.append("  killer of a SIBLING function's mutant, so do NOT delete on this report")
        out.append("  alone. Deleting is a PROPOSAL and it is the user's call, not yours: ask.")
        out.append("  `audit --remove` is the terminal form (it re-checks every sibling in the")
        out.append("  file before deleting) and is not a tool here, deliberately — deleting")
        out.append("  someone's tests on your own judgement is not a move this surface offers.")
        return "\n".join(out)

    if a.candidate_equivalent and a.candidate_equivalent_ids:
        first = a.candidate_equivalent_ids[0]
        out.append("")
        out.append("DONE: every killable behaviour is pinned and every line covered.")
        out.append(f"  {a.candidate_equivalent} survivor(s) remain that no input Detective found can")
        out.append("  distinguish. Whether they are TRULY equivalent is undecidable in general —")
        out.append("  the engine will not claim it, and neither should you by default.")
        out.append("")
        out.append("  If you can PROVE one cannot change behaviour — an argument from the code that")
        out.append("  holds for every input, not 'looks fine' — that is what flag is for:")
        out.append(f"    flag(file={file!r}, function={function!r}, mutant_id={first!r}, why=<your proof>)")
        if a.candidate_equivalent > 1:
            out.append(f"  ({a.candidate_equivalent - 1} more ids in the full report.)")
        out.append("  If you cannot, leave them. An UNPROVEN survivor is an honest result.")
        return "\n".join(out)

    if a.unclassified:
        out.append("")
        out.append(f"DONE: no gaps found. {a.unclassified} survivor(s) could not be classified at all —")
        out.append("  the search could not run on them. Not gaps, not equivalents: unknown. Do not")
        out.append("  flag them; you have no argument, only an absence.")
        return "\n".join(out)

    out.append("")
    out.append("DONE: the suite is complete and minimal. Nothing to run. Nothing to derive.")
    return "\n".join(out)


def _render_decompose(r: Any, file: str, function: str, wrote: bool) -> str:
    """The three outcomes the engine never blurs: applied / rejected / unproven."""

    def _sig(ex: Any) -> str:
        return f"{ex.helper_name}({', '.join(ex.params)}) -> {', '.join(ex.returns) or 'None'}"

    out = [f"{r.function} — decompose"]

    if not r.applied and not r.proposed and not r.unsafe_blocks:
        out.append("")
        out.append("DONE: no separable block. There is no seam here to split.")
        out.append("  Nothing to run. Nothing to derive.")
        return "\n".join(out)

    for ex in r.applied:
        out.append(f"  ✓ APPLIED — proven behaviour-preserving: {_sig(ex)}")

    # Direct access — see `_render_converge` for what a `getattr` default cost here. `proof` is
    # genuinely Optional (no suite yet); the fields ON it are not.
    proof = r.proof
    proof_incomplete = proof is not None and not proof.functionally_complete
    validated = [d for d in r.proposed if d.validated]
    unproven = [d for d in r.proposed if not d.validated]

    if r.applied:
        out.append("")
        out.append("DONE: your source is rewritten. The suite ran green before AND after.")
        out.append("  The extraction was trial-written and re-verified; nothing reached the file")
        out.append("  that the suite did not clear. Unspecified behaviour was not baked in —")
        out.append("  converge the new helper(s) if you want them pinned too.")
        return "\n".join(out)

    if validated and not wrote:
        for d in validated:
            out.append(f"  proven behaviour-preserving, not written: {_sig(d.extraction)}")
        out.append("")
        out.append(f"DO THIS: decompose(file={file!r}, function={function!r}, apply=True)")
        out.append("")
        out.append("  The proof already passed. apply=True writes it. Nothing else is needed.")
        return "\n".join(out)

    # The four causes of "unproven" are NOT interchangeable, and the CLI is right to keep them
    # apart. Collapsing them is how a caller gets told to supply an input for a hole that does
    # not exist — and then goes looking for why its input "didn't work".
    if unproven and proof is not None and not proof_incomplete:
        for d in unproven:
            out.append(f"  ✗ REJECTED: {_sig(d.extraction)}")
        out.append("")
        out.append("STOP. This is a verdict, not a gap. The suite is mutation-complete and it")
        out.append("  PROVES this extraction changes behaviour. Your source was not touched.")
        out.append("  There is no input to supply and nothing to retry. The answer is no.")
        return "\n".join(out)

    if unproven and proof is None:
        out.append("")
        out.append(f"DO THIS: converge(file={file!r}, function={function!r})")
        out.append("")
        out.append("  No suite specifies this function yet, so there is nothing to prove against.")
        out.append("  Your source was not touched. converge first, then come back.")
        return "\n".join(out)

    # `proof is not None` is carried by `proof_incomplete`, but only a reader knows that — the
    # correlation dies in the bool, and every `proof.` below reads as an attribute on None.
    if unproven and proof is not None and proof_incomplete:
        # Count what the GATE reads, not every survivor. `functionally_complete` (converge.py) is
        # `not killable and not unclassified` — a candidate-equivalent does not block. Reporting
        # `final_survivors` here fused all three populations into one number and then asked for an
        # input to close ALL of them, which is impossible for the equivalents by definition: no
        # input distinguishes one, that is what the classification MEANS. The number therefore did
        # not move when an input WAS supplied, and this renderer re-emitted the identical demand —
        # an agent reading it supplies input after input, sees the same line, and concludes the
        # tool ignores it. Same family as the bug named above: the engine classified honestly and
        # the renderer threw the classification away at the last inch.
        rep = proof.survivor_report
        params = tuple(proof.param_names or ())
        if rep is None:
            why = (
                f"{proof.final_survivors} survivor(s) are unpinned, but the classification did not "
                "run, so WHICH of them block is unknown. Your source was NOT touched."
            )
        else:
            n_kill, n_unc, n_eq = len(rep.killable), len(rep.unclassified), len(rep.equivalent)
            part = f"{n_kill} killable" if n_kill else ""
            part += (", " if part and n_unc else "") + (f"{n_unc} unclassified" if n_unc else "")
            # Name the non-blockers, or the agent reads the total as its backlog and chases
            # mutants no input can ever kill.
            # "no input will ever move them" is true of both classes only in the VALUE sense —
            # say that, rather than a flat "no input", which reads as "unreachable" and is what
            # sends a caller hunting for an input to reach them with.
            # Detection is claimed per mutant, never for the bucket: `crash_only_status`
            # splits by the profile's own kill records, and the old single sentence
            # ("your suite already detects them") was false for the undetected ones.
            from .equivalence import crash_only_status

            n_det, n_undet = crash_only_status([v for v in rep.equivalent if v.crash_only])
            crash_note = ""
            if n_det:
                crash_note += (
                    f" ({n_det} of them your suite already detects by crash — the mutant raises "
                    "where the original returns; what is missing is a value to pin, not an input.)"
                )
            if n_undet:
                crash_note += (
                    f" ({n_undet} crash-only survivor(s) are reached by NO current test; converge "
                    "writes a golden capture at each crash witness so they become crash-detected.)"
                )
            spare = (
                f" The other {n_eq} survivor(s) are candidate-equivalent: they do NOT block, no "
                f"input will ever pin them with a VALUE, and they are not your work.{crash_note}"
                if n_eq
                else ""
            )
            why = (
                f"{n_kill + n_unc} behaviour(s) block the proof ({part}), so the suite is not "
                f"mutation-complete.{spare} Your source was NOT touched."
            )
        out += _ask_for_input("decompose", file, function, params, why, rep=rep, proof=proof, apply=True)
        out.append("")
        out.append("  apply=True is already on the call above. The gate is not the flag — it is the")
        out.append("  proof: apply=True without one still writes nothing.")
        return "\n".join(out)

    for block in r.unsafe_blocks:
        out.append(f"  ✗ not extractable: {block}")
    out.append("")
    out.append("DONE: nothing here can be safely extracted. Nothing to derive.")
    return "\n".join(out)


def _plan_call(move_code: str, region: str, project_root: str, move: str = "") -> str:
    """One region's next move, spelled in THIS surface's call syntax — the MCP twin of the CLI's
    `plan.next_command`. Both consume `plan.next_move`; neither re-derives it. A move whose gate has
    no tool here (the receipt → verify-rewrite bracket; `audit --plan`) is NOT paraphrased into a
    tool that does not exist: the caller is told to hand the user the terminal command, verbatim."""
    from .plan import AUDIT_PLAN, CONVERGE, DECOMPOSE_APPLY, JUDGE, RECEIPT_BRACKET, receipt_path

    file, function = region.rsplit("::", 1) if "::" in region else (region, "")
    args = f"file={file!r}, function={function!r}, project_root={project_root!r}"
    if move_code == DECOMPOSE_APPLY:
        return f"decompose({args}, apply=True)"
    if move_code == CONVERGE:
        return f"converge({args})"
    if move_code == JUDGE:
        return f"flag({args}, style=True, leave=True, why=<why it stays>)   # or proceed=True"
    if move_code == RECEIPT_BRACKET:
        path = receipt_path(region)
        return (
            "hand the user this bracket — it runs in a TERMINAL (no receipt / verify-rewrite tool here):\n"
            f"      detective receipt '{region}' -o {path}\n"
            f"      # apply the '{move}' transform (that edit may be yours), then:\n"
            f"      detective verify-rewrite {path} '{region}'"
        )
    if move_code == AUDIT_PLAN:
        return f"hand the user: detective audit '{region}' --plan   (a TERMINAL command; not a tool here)"
    return ""


def _render_plan(assembly: Any, project_root: str, top: int = 5, report_path: str = "") -> str:
    """plan, for a caller (§14.6 / §14.9 slice 8). STATIC and advisory — no mutant ran, nothing is
    proven, nothing was written but the report file. The same tallies as the CLI (`plan.summarize`),
    the same three queues (`plan.converge_first` · `escalated_regions` · `reopened_regions`), the same
    next move per region (`plan.next_move`) spelled in this surface's syntax — and it closes the way
    every tool here closes, with ONE line, chosen by `plan.plan_closing`: the first funded gate; else
    the first region the ordering law says to converge; else the AMBIGUOUS queue handed to the driver
    as ITS decision (YOURS — a judgment is never rendered as a task); else done."""
    from .cli import _plan_move
    from .plan import (
        CONVERGE,
        DO_CONVERGE,
        DO_FUNDED,
        FUNDED,
        YOURS,
        converge_first,
        escalated_regions,
        next_move,
        plan_closing,
        reopened_regions,
        summarize,
    )

    s = summarize(assembly)
    v, c = dict(s.verdicts), dict(s.clean)
    by_region = {d.read.region: d for d in assembly.regions}
    out = [
        f"{assembly.scope} — plan · {s.regions} region(s) · {v.get('CONSTRUCTIVE', 0)} constructive · "
        f"{v.get('AMBIGUOUS', 0)} ambiguous · {v.get('DESTRUCTIVE', 0)} destructive · "
        f"{v.get('SILENT', 0)} silent (clean {c.get('clean', 0)} · unread {c.get('unread', 0)})",
        "  advisory — STATIC: no mutant ran, nothing here is proven, nothing was written but the report.",
        "  Every count is a named code's tally; none of them is a number to move.",
        "",
        f"funded {s.funded} · budget {assembly.budget:g} DOF-proxy · spent {s.spent:g}",
    ]
    funded = list(assembly.plan.funded)
    for r in funded[:top]:
        d = by_region[r.region]
        out.append(
            f"  {r.region}   agreement {r.agreement} · {r.template} → {_plan_move(d)} · "
            f"cost {r.cost:g} ({r.cost_provenance})"
        )
        out.append(
            f"    gate: {_plan_call(next_move(FUNDED, d.gate), r.region, project_root, _plan_move(d))}"
        )
    if len(funded) > top:
        out.append(f"  … {len(funded) - top} more funded — all in the report")
    if not funded:
        out.append("  nothing funded — every constructive region is excluded below, by name")

    out.append("")
    named = " · ".join(f"{reason} {n}" for reason, n in s.reasons) or "none"
    out.append(f"residual — every exclusion named: {named}")
    waiting = converge_first(assembly)
    escalated = escalated_regions(assembly)
    reopened = reopened_regions(assembly)

    def _some(regions: tuple[str, ...]) -> str:
        more = f"  (+{len(regions) - 3} more in the report)" if len(regions) > 3 else ""
        return ", ".join(regions[:3]) + more

    if waiting:
        out.append(
            f"  converge first: {len(waiting)} region(s) have no current behaviour contract — style WAITS "
            f"for behaviour: {_some(waiting)}"
        )
    if escalated:
        out.append(
            f"  yours: {len(escalated)} AMBIGUOUS — one lens each, or the two signs disagree; the controller "
            f"will not decide them: {_some(escalated)}"
        )
    if reopened:
        out.append(
            f"  reopened: {len(reopened)} style judgment(s) no longer apply — the code or its reading moved: "
            f"{_some(reopened)}"
        )
    out.append("")
    out.append(f"unexamined: {s.unexamined[0]}")
    out += [f"  {item}" for item in s.unexamined[1:]]
    if report_path:
        out.append(f"full report: {report_path}")

    out.append("")
    closing = plan_closing(len(funded), len(waiting), len(escalated))
    if closing == DO_FUNDED:
        r = funded[0]
        d = by_region[r.region]
        out.append(f"DO THIS: {_plan_call(next_move(FUNDED, d.gate), r.region, project_root, _plan_move(d))}")
        out.append("")
        out.append("  Funded is not applied. The gate proves the move behaviour-preserving or refuses it,")
        out.append("  and only the gate writes. A refusal there is the tool working, not an obstacle.")
    elif closing == DO_CONVERGE:
        out.append(f"DO THIS: {_plan_call(CONVERGE, waiting[0], project_root)}")
        out.append("")
        out.append(f"  {len(waiting)} region(s) this plan would consider have no current behaviour contract.")
        out.append("  Style AFTER behaviour, strictly: a refactor for form under an unpinned function can")
        out.append("  break what nothing pins. converge pins it. Then call plan again.")
    elif closing == YOURS:
        file, function = escalated[0].rsplit("::", 1)
        args = f"file={file!r}, function={function!r}, project_root={project_root!r}, style=True"
        out.append(
            f"YOURS: {len(escalated)} AMBIGUOUS region(s) — the controller will not decide them; you do."
        )
        out.append("  Read the region. Then record ONE answer per region, with your reason as `why`:")
        out.append(f"    flag({args}, leave=True, why=<why it stays as it is>)")
        out.append(f"    flag({args}, proceed=True, why=<why it is a case for change>)")
        out.append("  LEAVE excludes it by your decision; PROCEED sends it down the gate chain — behaviour")
        out.append("  still first, so an unpinned region then asks for converge. Unanswered, it re-escalates")
        out.append("  unchanged on every run: that is the question standing, not a fault.")
    else:
        out.append("DONE: nothing funded, nothing waiting on a contract, nothing escalated.")
        silent, clean, unread = v.get("SILENT", 0), c.get("clean", 0), c.get("unread", 0)
        out.append(
            f"  {silent} silent region(s) (clean {clean} · unread {unread}) — clean is measured, unread is"
        )
        out.append("  not-measured, and neither is approval. Nothing to run. Nothing to derive.")
    return "\n".join(out)


def _render_flag_style(rec: Any, file: str, function: str, project_root: str) -> str:
    """`flag(style=True)`, for a caller: a typed refusal (nothing recorded) or the recorded judgment,
    with `plan` as the one next call. Same refusal codes as the CLI (`judgments.record_style_judgment`
    is the shared actuator); the wording is this surface's."""
    head = f"{file}::{function} — flag · style"
    if rec.refusal == "mutant_id_with_style":
        return "\n".join(
            [
                head,
                "",
                "STOP. style=True judges a REGION, not a mutant — drop mutant_id. The two ledgers are",
                "  never addressed in one call. Nothing was recorded.",
            ]
        )
    if rec.refusal == "no_disposition":
        return "\n".join(
            [
                head,
                "",
                "STOP. style=True needs exactly one of leave=True / proceed=True. Nothing was recorded.",
            ]
        )
    if rec.refusal == "both_dispositions":
        return "\n".join(
            [
                head,
                "",
                "STOP. leave=True and proceed=True together is not an answer — a judgment is ONE answer.",
                "  Nothing was recorded.",
            ]
        )
    if rec.refusal == "regime_conflict":
        from .cli import _format_conflicts

        return "\n".join(
            [
                head,
                "",
                "STOP. The testing regime says no verdict about this file can be trusted, so a judgment",
                "  about it would be about nothing. Nothing was recorded.",
                "",
                _format_conflicts(rec.regime, f"{file}::{function}").rstrip(),
            ]
        )
    if rec.refusal == "no_such_function":
        names = ", ".join(rec.regions_in_file) or "none"
        return "\n".join(
            [
                head,
                "",
                f"STOP. No function {function!r} in {file} — regions in that file: {names}.",
                "  Nothing was recorded.",
            ]
        )
    suffix = f" ({rec.note})" if rec.note else ""
    out = [
        head,
        "",
        f"  recorded: style judgment — {rec.disposition}{suffix}",
        f"  keyed to this exact definition and its current reading ({rec.controller_verdict}) — an edit, or",
        "  a changed reading, REOPENS it; a fence outranks it. It never touches the behaviour layer.",
        "",
    ]
    if rec.disposition == "leave":
        out.append("DONE: plan excludes this region by your decision (judged_leave) until the code or its")
        out.append("  reading moves.")
    else:
        out.append("DONE: plan treats this AMBIGUOUS region as a case for change — down the gate chain,")
        out.append(
            "  behaviour first (an unpinned region asks for converge before any style move is funded)."
        )
    out.append(f"  Next: plan(target={rec.region!r}, project_root={project_root!r})")
    return "\n".join(out)


# ── the live session ─────────────────────────────────────────────────────────────────


def _budget_kwargs(trace_budget: float | None, trace_session_budget: float | None) -> dict[str, Any]:
    """MCP budget params -> ``run_with_live_suite`` kwargs. THREE states, not two.

    The seam distinguishes: omitted (use the engine's default), ``None`` (explicitly unbounded),
    a number (that budget). Collapsing "the caller said nothing" into ``None`` would read as
    "unbounded" and silently remove the only bound on the baseline pass — the pass that makes a
    large suite finite. So an unspecified budget is not forwarded AT ALL.

    ``0`` means unbounded, matching ``cli._trace_budget``'s documented convention exactly rather
    than inventing a second one for this surface. One tool, one meaning for the same number.
    """
    out: dict[str, Any] = {}
    if trace_budget is not None:
        out["trace_budget_s"] = None if trace_budget <= 0 else float(trace_budget)
    if trace_session_budget is not None:
        out["trace_session_budget_s"] = None if trace_session_budget <= 0 else float(trace_session_budget)
    return out


def _in_session(
    root: str,
    file: str | None,
    fn: Callable[[], Any],
    trace_budget: float | None = None,
    trace_session_budget: float | None = None,
) -> tuple[Any, str | None]:
    """Run ``fn()`` inside a LIVE pytest session. Returns ``(result, warning_or_None)``.

    NOT an optimisation — a correctness requirement, and the single most important line in this
    file. Wesker's fallback discovery collects with ``--collect-only``, which tears the session
    down immediately, so every fixture-taking test is SKIPPED. A mutant only such a test could
    kill is then reported as a surviving behavioural gap: the tool says a dimension is unspecified
    when the suite already pins it, and `converge` writes a test for behaviour that was never
    unspecified. On a fixture-heavy target that is nearly the whole suite (measured on Prism: 0 of
    445 tests bound the old way, 445 the new way). The CLI has wrapped its entry point in this
    since day one; this surface called the library directly and therefore never had it — every
    verdict it returned on a fixture-driven repo was wrong in the tool's least honest direction,
    reporting MORE unspecified behaviour than exists.

    Scoping rides along for free — it belongs to this same seam, so collection is narrowed to
    the files that could execute the target's lines before anything is imported.

    The trace budgets ride along TOO, and they did not always. This surface used to skip them on
    the reasoning that "a caller who needs to change them wants the CLI" — while its own output
    told that caller, in the same breath, to fix an under-counted measurement with
    ``--trace-budget 0``. A remedy that only exists on a surface you are not using is not a
    remedy; it is the tool describing an escape it does not offer. That is the same defect this
    release removed from three other places (budget flags that reached only the path a live
    session never uses; a purge that could not see its own cache; a cache key blind to the budget
    that produced it): a documented opt-out that cannot reach the thing it opts out of.

    A missing session is returned as a WARNING, never swallowed: degrading quietly to a weaker
    test set is what makes a well-specified suite look under-specified, and a caller that cannot
    tell the difference will act on the wrong number.

    ``project_root`` is REQUIRED on every tool of this surface, and has no default, because there
    is no honest one. It used to default to ``"."`` — which for a STDIO server does not mean "the
    project", it means "wherever the client happened to launch this process", fixed for the
    process's whole life and never updated when the caller moves to another repo. Analyse a
    project that is not that directory and every write lands somewhere else: the verdict cache
    lives at ``<project_root>/.detective/``, so a wrong root does not fail — it silently gets its
    own cache file and is therefore COLD ON EVERY CALL, forever. Cold is minutes on a large suite,
    and a tool call that outlives the client's timeout takes the whole server down with it. A
    default that is right only when the client's cwd happens to be the target is not a default;
    it is a coin flip with a slow, silent, self-inflicted failure on one face. Make the caller say
    it.

    (Not the cache KEY — that is cwd-independent: the seam chdirs to ``project_root`` before
    anything is collected, and two cwds with the same absolute root produce byte-identical keys.
    Measured. The path is the whole story.)
    """
    try:
        from Wesker.ci import run_with_live_suite
    except ImportError:
        return fn(), None

    targets = [file] if file else None
    paths = _reachable_paths(root, targets).paths
    diagnostic: dict[str, Any] = {}
    try:
        result = run_with_live_suite(
            root,
            fn,
            target_files=targets,
            paths=paths,
            diagnostic=diagnostic,
            **_budget_kwargs(trace_budget, trace_session_budget),
        )
    except TypeError:  # older Wesker without the `diagnostic` param
        result = run_with_live_suite(
            root, fn, target_files=targets, paths=paths, **_budget_kwargs(trace_budget, trace_session_budget)
        )
    if result is None:
        # `None` means exactly one thing here: no live session could be started. Re-run without
        # one so the caller still gets an answer, but SAY the answer is weaker — and NAME the
        # reason. The old generic "pytest missing, or collection failed" sent users to reinstall
        # pytest for problems that were actually duplicate-conftest ImportPathMismatchErrors in
        # mutants/ shadow trees. `diagnostic["reason"]` distinguishes the four cases and, for
        # collection errors, hands back the first failing nodeids and the standard fix hint.
        return fn(), _format_session_warning_mcp(diagnostic)
    return result, None


def _format_session_warning_mcp(diagnostic: dict[str, Any]) -> str:
    """MCP-surface twin of the CLI's `_format_session_warning`.

    Same reason discrimination, formatted for the MCP tool-result view (leading
    `⚠` glyph, tighter margins). Kept separate from the CLI version so each
    surface can evolve its own idiom without the other one drifting; both read
    the same ``diagnostic["reason"]`` contract from ``Wesker.run_in_session``.
    """
    reason = diagnostic.get("reason", "unknown")
    if reason == "pytest_missing":
        return (
            "⚠ pytest is not importable in the interpreter that runs the live suite.\n"
            "  Install it (e.g. `pip install pytest`) or run Detective from an interpreter\n"
            "  that has it. Counts below are collect-only UPPER BOUNDS, not findings."
        )
    if reason == "collection_errors":
        errors = diagnostic.get("errors", [])
        header = (
            f"⚠ pytest collection failed with {len(errors)} error(s). The live suite could not\n"
            "  start; fixture-taking tests could not run, so counts below are UPPER BOUNDS.\n"
            "  First failures:\n"
        )
        lines = []
        for nodeid, detail in errors[:3]:
            first_line = detail.strip().splitlines()[0][:200] if detail.strip() else "(no detail)"
            lines.append(f"    · {nodeid}: {first_line}\n")
        tail = ""
        if len(errors) > 3:
            tail = f"    ... and {len(errors) - 3} more.\n"
        hint = (
            '  Common fix: set `[tool.pytest.ini_options] testpaths = ["tests"]` in\n'
            "  pyproject.toml to exclude generated / mutants / shadow trees from discovery."
        )
        return header + "".join(lines) + tail + hint
    if reason == "empty_collection":
        return (
            "⚠ pytest collected no tests — the live suite has nothing to run.\n"
            "  Check `testpaths` / conftest / discovery patterns. Counts below are\n"
            "  collect-only UPPER BOUNDS, not findings."
        )
    if reason == "pytest_crashed":
        return (
            "⚠ pytest raised an unexpected exception during collection. Falling back to\n"
            "  collect-only discovery; fixture-taking tests cannot run."
        )
    # Older Wesker without diagnostic support falls here — keep the legacy message.
    return (
        "⚠ NO live pytest session (pytest missing, or collection failed). Fixture-taking\n"
        "  tests could not run, so behaviour below may read as unspecified when a test does\n"
        "  pin it. Treat these counts as an UPPER BOUND, not a finding."
    )


# Prepended to any CLI-rendered report handed back through this surface. That text is written
# for a human at a terminal and says so in its own idiom — `--input "(...)"`, `decompose 'fn'
# --apply`, `detective flag 'f::g' MUTANT_ID`. None are calls a tool caller can make, so a
# caller reading the full report is handed instructions it cannot follow, in a register that
# invites it to shell out and improvise. The report is correct and worth reading; only the
# imperatives are addressed to someone else. Say so at the door rather than rewrite the
# engine's own honest rendering.
#
# The CLI now writes its actions as `DO THIS:` — the same marker this surface uses for a REAL
# call — so the collision has to be named explicitly. "Ignore the instructions" is too vague
# against a line that looks exactly like the one the caller is supposed to obey; the tell is
# the shape, and the shape is `detective <verb>` vs `<verb>(...)`.
#
# And `flag` IS a tool here now. It used to be withheld as a human judgement, which was wrong:
# deciding a mutant is unreachable is symbolic reasoning about the code ("the cap is 0.60 and
# the branches above sum to at most 0.50"), and the required `why` is what makes the claim
# auditable and therefore repairable. This text said the opposite for as long as that was true
# and would have kept saying it — a header describing a surface it no longer describes.
_CLI_REPORT_HEADER = (
    "ℹ This is the CLI's full report, rendered for a human. Read it for the detail — every\n"
    "  survivor, its exact diff, the scores. Its `DO THIS:` lines are NOT for you: a line\n"
    "  starting `detective <verb>` is terminal syntax. Do not run it, and do not shell out\n"
    "  to it — every action it names is a tool here, bar the two named below.\n"
    '  `detective converge \'f::g\'` is converge(file="f", function="g"); `--input "(...)"` is\n'
    "  inputs=[\"(...)\"]; `--apply` is apply=True; `detective flag 'f::g' ID` is\n"
    '  flag(..., mutant_id="ID", why=<your proof>); `detective plan <path>` is plan(target=<path>);\n'
    "  `detective flag 'f::g' --style --leave|--proceed` is flag(..., style=True, leave=True |\n"
    "  proceed=True). Translate, never execute. The two exceptions: `detective receipt …` and\n"
    "  `detective verify-rewrite …` — a plan's rewrite bracket — have NO tool here. Hand those\n"
    "  two, and only those, to the user to run in a terminal.\n"
)


def _rendered(
    root: str,
    file: str | None,
    produce: Callable[[], str],
    trace_budget: float | None = None,
    trace_session_budget: float | None = None,
) -> str:
    """``produce()`` inside a live session, with any session warning prepended to its text."""
    text, warning = _in_session(root, file, produce, trace_budget, trace_session_budget)
    return f"{warning}\n\n{text}" if warning else text


# Every tool takes these, because every tool traces. Documented once here and APPLIED to each by
# `_with_budget_doc` below, so the surface cannot drift back into recommending a knob it does not
# have. It drifted anyway, and the reason is worth keeping: this block existed, said the right
# thing, and was never referenced by anything — a constant defined and dropped. So every tool
# published these two parameters with NO description at all, the only guidance a caller ever saw
# was a CUT warning that named the per-test knob, and the knob it named is not the one that cuts.
# A documentation mechanism that nothing applies documents nothing; wiring it is the fix.
_BUDGET_DOC = """
        trace_budget: seconds to spend tracing EACH test in the baseline. Omitted = the engine's
            default. ``0`` = unbounded (exact, slower). This bounds ONE pathological test; it is
            rarely what cut you.
        trace_session_budget: seconds for the WHOLE baseline pass. Omitted = the engine's
            default. ``0`` = unbounded. A per-test cap times N tests is still unbounded in
            aggregate; only this bounds the phase — so THIS is almost always the knob that cut
            you, and the one to raise when a response says tests were CUT. Measured on a real
            2000-test repo: (50, 300) and (unbounded, 300) cut an identical 152 tests, i.e.
            raising the per-test knob alone changed nothing at all. Set both to ``0`` to be sure.
            A CUT warning is not cosmetic: a cut test's coverage is under-counted, so tests that
            DO pin a behaviour cannot be credited, and the report calls already-specified
            behaviour unpinned (measured: 0 of 45 reported, 22 of 45 true). Re-measure, then act."""


def _with_budget_doc(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Append `_BUDGET_DOC` to ``fn``'s docstring. Applied UNDER ``@server.tool()`` so the
    decorator below it sees the finished text — FastMCP reads ``__doc__`` when it registers the
    tool, so appending after registration would publish the original and silently change nothing.
    """
    fn.__doc__ = (fn.__doc__ or "") + _BUDGET_DOC
    return fn


# ── server ───────────────────────────────────────────────────────────────────────────


def build_server() -> Any:
    """Construct the FastMCP server.

    Tool descriptions are the part of this file most likely to actually be read, since they
    are in the caller's context at the moment it decides what to do. They carry the protocol,
    not just the signature.
    """
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("Detective")

    @server.tool()
    @_with_budget_doc
    def diagnose(
        file: str,
        function: str,
        project_root: str,
        full: bool = False,
        trace_budget: float | None = None,
        trace_session_budget: float | None = None,
    ) -> str:
        """START HERE for any function you are about to change. Writes nothing.

        Reports every behavioural distinction the function makes and which ones no test
        pins, then names the single next call. Read the whole response; it is the product,
        not a log. Do not grep the source to check its findings — it ran the mutants and
        you did not.

        FIRST RUN ON A BIG SUITE IS SLOW. Before answering anything, the engine traces the
        target's suite once — minutes on a large repo, seconds after for THAT EXACT QUESTION.
        Warm means one question, not one repo: what persists is a single function's profile under
        a single set of budgets. The trace is never persisted, so a different function — or the
        same one under different budgets — misses and re-pays it in full. Your client's tool
        timeout may be shorter than that, and a timeout here kills the whole server, discards
        the trace, and leaves the next call just as cold. If this call dies: run
        `detective diagnose file.py::function` in a terminal ONCE to warm the cache, then come
        back — same budgets, same cache key, so the terminal run genuinely warms this one.
        Nothing is wrong with the tool; the work simply outlives the call.

        Profiling MANY functions? Do it from the CLI in ONE process: the trace amortises across
        functions within a session, and one tool call is a session of exactly one function — so
        N functions here cost N traces.
        """
        from .cli import _format_scope
        from .engine import diagnose as _diagnose

        def _go() -> str:
            scope = _diagnose(file, function, project_root)
            if full:
                return _CLI_REPORT_HEADER + "\n" + _format_scope(scope)
            return _render_diagnose(scope, file, function)

        return _rendered(project_root, file, _go, trace_budget, trace_session_budget)

    @server.tool()
    @_with_budget_doc
    def converge(
        file: str,
        function: str,
        project_root: str,
        inputs: list[str] | None = None,
        full: bool = False,
        verbose: bool = False,
        trace_budget: float | None = None,
        trace_session_budget: float | None = None,
    ) -> str:
        """Write the minimal pytest suite that pins this function's behaviour. WRITES FILES.

        ``inputs`` are real calls to the target, as strings: ``["(2.0, 600, True)"]``. Supply
        one whenever the response asks for it — that is the only thing this engine cannot
        derive for itself, and re-running without one cannot make progress.

        ``verbose=True`` (only meaningful with ``full=True``) lists every surviving mutant's id
        and diff; by default they group by the statement they mutated. Ask for it when you need
        a specific id to pass to `flag` — on a large function the ungrouped list is mostly
        repetition of the same few branches, and reading it costs you context you will want.

        Calling this repeatedly with no new ``inputs`` is inert. If the answer did not change,
        that is not a bug and not a reason to look inside .detective/ — it means the engine
        already told you what it needs and is still waiting for it.

        COLD FIRST RUN OUTLIVES A TOOL CALL. The engine traces the target's suite before it can
        answer — minutes on a large repo, seconds thereafter for THAT EXACT QUESTION. Warm means
        one question, not one repo: what persists is a single function's profile under a single set
        of budgets. The trace itself is never persisted, so a different function — or the same one
        under different budgets — misses and re-pays the whole trace. If this call dies with a
        transport error, the server died with it and the trace was discarded, so retrying is
        identically cold. Warm it once from a terminal (`detective converge file.py::function`), or raise your
        client's tool timeout. Pass project_root as an ABSOLUTE path: the cache lives under it,
        and a relative "." resolves against THIS SERVER's cwd — which is the client's, not
        necessarily the project's, so a wrong root silently means a permanently cold cache.
        """
        from .cli import _format_converge, _parse_supplied_inputs
        from .converge import converge as _converge

        def _go() -> str:
            supplied = _parse_supplied_inputs(inputs) if inputs else None
            result = _converge(file, function, project_root, supplied_inputs=supplied)
            full_text = (
                _CLI_REPORT_HEADER + "\n" + _format_converge(result, show_tests=True, verbose=verbose)
                if full
                else None
            )
            return _render_converge(result, file, function, full_text)

        return _rendered(project_root, file, _go, trace_budget, trace_session_budget)

    @server.tool()
    @_with_budget_doc
    def decompose(
        file: str,
        function: str,
        project_root: str,
        apply: bool = False,
        inputs: list[str] | None = None,
        full: bool = False,
        trace_budget: float | None = None,
        trace_session_budget: float | None = None,
    ) -> str:
        """Split a tangled function into helpers. Applied ONLY when proven behaviour-preserving.

        ``apply=True`` is not "do it" — it is "do it if proven". It converges a suite, runs it
        against the unchanged function for a baseline, trial-writes each extraction, re-runs,
        and keeps it only if green. An unproven extraction is never written, with or without
        the flag. A refusal here is the tool working, not an obstacle to route around.

        COLD FIRST RUN OUTLIVES A TOOL CALL. The engine traces the target's suite before it can
        answer — minutes on a large repo, seconds thereafter for THAT EXACT QUESTION. Warm means
        one question, not one repo: what persists is a single function's profile under a single set
        of budgets. The trace itself is never persisted, so a different function — or the same one
        under different budgets — misses and re-pays the whole trace. If this call dies with a
        transport error, the server died with it and the trace was discarded, so retrying is
        identically cold. Warm it once from a terminal (`detective decompose file.py::function`),
        or raise your client's tool timeout. Pass project_root as an ABSOLUTE path: the cache lives under it,
        and a relative "." resolves against THIS SERVER's cwd — which is the client's, not
        necessarily the project's, so a wrong root silently means a permanently cold cache.
        """
        from .cli import _format_decompose, _parse_supplied_inputs
        from .decompose_apply import apply_decomposition

        def _go() -> str:
            supplied = _parse_supplied_inputs(inputs) if inputs else None
            result = apply_decomposition(file, function, project_root, write=apply, supplied_inputs=supplied)
            if full:
                return _CLI_REPORT_HEADER + "\n" + _format_decompose(result, apply)
            return _render_decompose(result, file, function, apply)

        return _rendered(project_root, file, _go, trace_budget, trace_session_budget)

    @server.tool()
    @_with_budget_doc
    def audit(
        file: str,
        function: str,
        project_root: str,
        full: bool = False,
        trace_budget: float | None = None,
        trace_session_budget: float | None = None,
    ) -> str:
        """Assess the suite that already exists: complete? minimal? what is safe to delete?

        Writes nothing, ever. Deletions are proposals; the user confirms them — `--remove` is
        deliberately not a tool here, because deleting someone's tests on your own judgement is
        not a move this surface offers.

        `full=True` returns the CLI's human report — every survivor, its diff, the scores. Its
        `DO THIS:` lines are for a terminal, not for you; translate them to tools.

        COLD FIRST RUN OUTLIVES A TOOL CALL. The engine traces the target's suite before it can
        answer — minutes on a large repo, seconds thereafter for THAT EXACT QUESTION. Warm means
        one question, not one repo: what persists is a single function's profile under a single set
        of budgets. The trace itself is never persisted, so a different function — or the same one
        under different budgets — misses and re-pays the whole trace. If this call dies with a
        transport error, the server died with it and the trace was discarded, so retrying is
        identically cold. Warm it once from a terminal (`detective audit file.py::function`), or raise your
        client's tool timeout. Pass project_root as an ABSOLUTE path: the cache lives under it,
        and a relative "." resolves against THIS SERVER's cwd — which is the client's, not
        necessarily the project's, so a wrong root silently means a permanently cold cache.
        """
        from .audit import audit_suite
        from .cli import _format_audit

        def _go() -> str:
            a = audit_suite(file, function, project_root)
            if full:
                return _CLI_REPORT_HEADER + "\n" + _format_audit(a)
            return _render_audit(a, file, function)

        return _rendered(
            project_root,
            file,
            _go,
            trace_budget,
            trace_session_budget,
        )

    @server.tool()
    def plan(
        target: str,
        project_root: str,
        budget: float = 500.0,
        top: int = 5,
        full: bool = False,
    ) -> str:
        """START HERE for STYLE — and only AFTER behaviour. Writes nothing but a report file.

        STATIC: no mutant runs, no session opens, nothing is proven. Reads every function under
        ``target`` — a path (a tree) or ``file.py::function`` (one region) — through the parsimony
        banks, prices each region, checks its BEHAVIOUR STATUS against the certificate ledger, and
        returns: the moves it can fund (each with its gate), the residual with EVERY exclusion
        named, the AMBIGUOUS queue that is yours to decide, and the line naming what it could not
        examine. Then ONE closing line: the first funded gate; else the first region the ordering
        law says to converge (style waits for behaviour — a refactor for form under an unpinned
        function can break what nothing pins); else the AMBIGUOUS queue, handed to you; else done.

        Funded is NOT applied. The gate proves a move behaviour-preserving or refuses it, and only
        the gate writes. Some gates (`receipt`, then `verify-rewrite`) have no tool here — the
        response says so and hands you the terminal bracket for the user. Do not improvise the
        edit without the receipt taken first: without it the rewrite cannot be verified.

        There is no score here and nothing to optimise: every count is a named code's tally;
        `clean` is measured (a region every bank passed), `unread` is not-measured, and neither is
        approval. ``full=True`` returns the CLI's archive — every region, every lens that voted,
        every reason. ``budget`` is in DOF-proxy units (static mutant-universe size), not time.
        Pass project_root as an ABSOLUTE path; the report lands under it.
        """
        from .cli import _format_conflicts, _format_plan_full, _write_converge_report
        from .plan import REGIME_CONFLICT, resolve_plan

        if "::" in target and not all(target.rsplit("::", 1)):
            return (
                f"STOP. target must be a path, or 'file.py::function' with both halves — got {target!r}. "
                "Nothing was read."
            )
        res = resolve_plan(target, project_root, budget)
        if res.refusal == REGIME_CONFLICT:
            return "\n".join(
                [
                    f"{target} — plan",
                    "",
                    "STOP. The testing regime says no verdict about this file can be trusted, so a plan",
                    "  over it would be a finding about nothing. Nothing was read.",
                    "",
                    _format_conflicts(res.regime, target).rstrip(),
                ]
            )
        if res.refusal or res.assembly is None:
            return f"{target} — plan\n\nSTOP. {res.detail}. Nothing was read."
        assembly = res.assembly
        root = os.path.abspath(project_root)
        report_path = _write_converge_report(root, assembly.scope, _format_plan_full(assembly), prefix="plan")
        if full:
            return _CLI_REPORT_HEADER + "\n" + _format_plan_full(assembly, report_path)
        return _render_plan(assembly, project_root, top, report_path)

    @server.tool()
    def flag(
        file: str,
        function: str,
        project_root: str,
        mutant_id: str = "",
        why: str = "",
        style: bool = False,
        leave: bool = False,
        proceed: bool = False,
    ) -> str:
        """Record that a surviving mutant is TRULY EQUIVALENT — it cannot change behaviour, so
        no test could ever kill it. Use when you can PROVE that, not when you want the number down.

        This is the one tool here that moves a verdict without evidence. Everything else reports
        what the engine measured; this records what YOU concluded. `audit` goes from "complete,
        modulo 17 unproven-equivalent" to "complete" because you said so. So the bar is a proof,
        and `why` is where you write it.

        WHAT QUALIFIES. An argument from the code that holds for EVERY input:
          · unreachable — "the cap is 0.60 and the branches above sum to at most 0.50, so it
            never fires" (a real one; the mutants on that branch are equivalent for that reason)
          · commutative/idempotent — "max(a, b) == max(b, a)"
          · dominated — "the value is overwritten on every path before it is read"
        Name the constraint. If your `why` would be "looks equivalent", "probably fine", "the
        test suite passes", or a restatement of the diff, you have not proven it — say so to the
        user and leave the survivor alone. An UNPROVEN survivor is an honest result and costs
        nothing.

        A stated argument is the whole point: it makes the claim auditable, and therefore
        REPAIRABLE if it is wrong. Someone can read "the cap never fires because the branches
        sum to at most 0.50", check it, and delete the flag if it does not hold. That is why
        `why` is required rather than optional here — not to slow you down, but because a flag
        without an argument is a conclusion no one can check, and an unreviewable claim is the
        only kind that stays wrong.

        WHAT DOES NOT QUALIFY: that it blocks you. It does not. Candidate-equivalents do NOT
        block `functionally_complete` — decompose and converge close with them outstanding. If
        you are reaching for this to make something proceed, it is the wrong tool and the thing
        actually blocking you is a killable mutant, which needs an input or a test.

        Two things outrank you, by design: a real distinguishing witness found later kills the
        mutant and your flag with it (proof beats judgement), and the flag is keyed to this exact
        code, so editing the function drops it. Neither is a bug.

        Returns the recorded flag, or an error naming the survivors if `mutant_id` is not one —
        ids come from `audit`/`converge`. Pass project_root as an ABSOLUTE path.

        TWO LEDGERS, ONE VERB. ``style=True`` records a DIFFERENT kind of judgment: your answer to
        a region `plan` marked AMBIGUOUS — ``leave=True`` (it stays as it is) or ``proceed=True``
        (treat it as a case for change) — in `.detective/judgments.json`. That is a judgment about
        FORM, not a verdict about a mutant: no ``mutant_id`` (giving one is refused), no session
        opens, nothing is profiled, and it never affects converge, audit, decompose, or any
        behaviour-layer verdict. It is keyed to the definition and its current reading — an edit,
        or a changed reading, REOPENS it — and ``why`` is your reason, kept beside it. A style
        judgment needs no proof, only a reason: it is the driver's call by design, and `plan`
        re-asks it, unchanged, until one is recorded.
        """
        from .engine import profile
        from .equivalents import add_flag

        if style:
            # STATIC — outside `_rendered`: a judgment about form never opens a live session.
            from .judgments import record_style_judgment

            rec = record_style_judgment(
                project_root, file, function, bool(mutant_id), leave, proceed, why.strip()
            )
            return _render_flag_style(rec, file, function, project_root)
        if not mutant_id:
            return (
                "STOP. flag needs a surviving mutant id (from audit / converge) — or style=True to judge "
                "the REGION's form. Nothing was recorded."
            )

        def _go() -> str:
            reason = why.strip()
            if not reason:
                return "STOP. `why` is the proof. An unjustified flag is a deleted behaviour."
            result = profile(file, function, project_root)
            # Value-survivors — the SAME set audit/converge report, so a crash-killed mutant
            # they list is flaggable. `survivor_records` would miss those and answer "none".
            rec = next(
                (
                    r
                    for r in result.value_survivor_records
                    if mutant_id in (r.get("mutant_id"), r.get("mutant"))
                ),
                None,
            )
            if rec is None:
                ids = ", ".join(r.get("mutant_id", "?") for r in result.value_survivor_records)
                return (
                    f"STOP. '{mutant_id}' is not a surviving mutant of {function}. Your flag was "
                    f"NOT recorded.\n  Surviving: {ids or 'none — nothing to flag'}"
                )
            add_flag(project_root, result.function_key, rec.get("diff_summary", ""), note=reason)
            return "\n".join(
                [
                    f"{result.function_key} — flag · {mutant_id}",
                    "",
                    f"  recorded equivalent: {reason}",
                    "",
                    "DONE: audit and converge now treat it as equivalent, not a gap. Your source",
                    "  and tests are untouched. A distinguishing witness found later still kills",
                    "  it — proof outranks this. Editing the function drops the flag.",
                ]
            )

        return _rendered(project_root, file, _go)

    @server.tool()
    @_with_budget_doc
    def deep_context(
        file: str,
        function: str,
        project_root: str,
        trace_budget: float | None = None,
        trace_session_budget: float | None = None,
    ) -> str:
        """The full analysis: every survivor, its exact diff, the scores, the written tests.

        Call this when you are curious, or when the user asks for the numbers. You do not need
        it to act — the other tools already told you the next call. This is a door, not a step.

        COLD FIRST RUN OUTLIVES A TOOL CALL. The engine traces the target's suite before it can
        answer — minutes on a large repo, seconds thereafter for THAT EXACT QUESTION. Warm means
        one question, not one repo: what persists is a single function's profile under a single set
        of budgets. The trace itself is never persisted, so a different function — or the same one
        under different budgets — misses and re-pays the whole trace. If this call dies with a
        transport error, the server died with it and the trace was discarded, so retrying is
        identically cold. Warm it once from a terminal (`detective diagnose file.py::function`), or raise your
        client's tool timeout. Pass project_root as an ABSOLUTE path: the cache lives under it,
        and a relative "." resolves against THIS SERVER's cwd — which is the client's, not
        necessarily the project's, so a wrong root silently means a permanently cold cache.
        """
        from .cli import _format_converge
        from .converge import converge as _converge

        return _rendered(
            project_root,
            file,
            lambda: (
                _CLI_REPORT_HEADER
                + "\n"
                # Grouped, like the CLI's --full: this relays a whole converge report into a model's
                # context, so the per-mutant list is the most expensive and least load-bearing part
                # of it. The ids live in the written report for anyone who needs one.
                + _format_converge(
                    _converge(file, function, project_root, write_dir=None), show_tests=True, verbose=False
                )
            ),
            trace_budget,
            trace_session_budget,
        )

    return server


def main() -> None:
    """Entry point for the ``detective-mcp`` console script.

    The script is installed unconditionally — a wheel cannot make a console script
    depend on an extra — so on a plain ``detective-spec`` install it is present but its
    dependency is not. Left alone, it dies on a raw ModuleNotFoundError traceback and
    reads like a broken package. Say what is missing and how to get it instead.
    """
    try:
        server = build_server()
    except ModuleNotFoundError as exc:  # pragma: no cover — depends on the extra being absent
        if exc.name != "mcp" and not str(exc).startswith("No module named 'mcp"):
            raise
        raise SystemExit(
            "detective-mcp: the optional MCP server dependency is not installed.\n"
            "  install it with:  uv pip install 'detective-spec[mcp]'\n"
            "  (the `detective` CLI itself needs nothing extra — this is only for the MCP surface)"
        ) from None
    server.run()


if __name__ == "__main__":
    main()
