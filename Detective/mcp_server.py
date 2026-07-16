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


def _ask_for_input(tool: str, file: str, function: str, param_names: tuple[str, ...], why: str) -> list[str]:
    """The hand-back. This is the only thing the caller is ever asked to produce, and it is
    the one thing it can produce that the engine cannot: a real call to the target.

    Phrased as a request for knowledge, not as a deficiency to be closed by effort. The
    distinction is the whole ballgame — a caller told "30 residuals remain" optimizes; a
    caller told "supply one real call" answers and stops.
    """
    tmpl = _input_template(param_names)
    return [
        "",
        f"DO THIS: {tool}(file={file!r}, function={function!r}, inputs=[{tmpl}])",
        "",
        f"  {why}",
        "  Detective will not invent a value whose meaning is not in the code. You know what",
        f"  a real call to {function} looks like. It does not. That is the entire division of",
        "  labour here, and supplying one is the whole of your job.",
        "  More passes will not help. This is not a matter of effort or cleverness — the",
        "  information is absent, and you are the only source of it.",
    ]


def _render_diagnose(scope: Any, file: str, function: str) -> str:
    """diagnose is read-only. It always terminates in exactly one recommended call."""
    out = [f"{scope.function}  [regime {scope.regime}]"]

    # The mutant IDs are stable identities for `flag`, and useless to read: twelve lines of
    # "off-by-one comparison" is a flood, not a finding. Group by what the edit DOES. The
    # exact per-mutant diffs (`- if total < 0:` / `+ if total <= 0:`) are the genuinely
    # interesting artefact and they do not live on ScopeMap — converge's survivor report
    # carries them. Do not imply they are here.
    unspec = list(scope.unspecified_behaviors)
    no_tests = scope.tests_discovered == 0
    # A truncated trace UNDER-COUNTS coverage, and an under-counted line is indistinguishable
    # from an uncovered one in the numbers. Everything below rests on that measurement, so this
    # goes FIRST and is not optional: `ScopeMap.trace_truncated` exists precisely because "a
    # completeness verdict that quietly rests on a truncated measurement is the one failure this
    # tool cannot afford", and a surface that drops it commits exactly that failure while looking
    # tidier for it. On Regenesis this was 152 of 240 tests.
    cut = list(scope.trace_truncated)
    if cut:
        out.append("")
        out.append(f"⚠ {len(cut)} test(s) were CUT by the trace budget, so their line coverage is")
        out.append("  UNDER-COUNTED. Anything below may be the budget rather than a real hole.")
        out.append("  This is a measurement limit, not a finding — do not act on it as one.")
        out.append("  Raise it from the CLI (`--trace-budget 0` = unbounded) if it matters.")
    if unspec:
        kinds: dict[str, int] = {}
        for b in unspec:
            kinds[b.split(": ", 1)[-1]] = kinds.get(b.split(": ", 1)[-1], 0) + 1
        out.append("")
        out.append(f"{len(unspec)} behaviour(s) nothing distinguishes:")
        out += [f"  {n} × {desc}" for desc, n in sorted(kinds.items(), key=lambda kv: -kv[1])]
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
        out.append(f"DO THIS: decompose(file={file!r}, function={function!r})")
        out.append("")
        out.append("  Two independent signals agree this is more than one function: it is")
        out.append(f"  behaviourally entangled AND has {seams} clean structural seam(s).")
        out.append("  decompose writes a proof suite first and applies nothing it cannot prove.")
    elif unspec:
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

    if killable or not result.line_complete:
        why = "Synthesis is exhausted. What is left needs a value only you can supply."
        out += _ask_for_input("converge", file, function, params, why)
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
        out.append("  no input could distinguish. Whether they are truly equivalent is UNDECIDABLE")
        out.append("  in general — the engine will not claim it, and neither should you.")
        out.append("  Leave them. They are not a gap and not your work.")
        out.append("  (If you have positive reason one is equivalent, that is a human judgement:")
        out.append("   ask the user. Do not decide it yourself.)")
        if manual:
            out.append(f"  ({len(manual)} more were already flagged equivalent by a human.)")
        return "\n".join(out)

    out.append("")
    out.append("DONE: the suite is complete. Nothing to run. Nothing to derive.")
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

    if unproven and proof_incomplete:
        blocking = proof.final_survivors
        params = tuple(proof.param_names or ())
        why = (
            f"{blocking} behaviour(s) are unpinned, so the proof suite is not mutation-complete, "
            "so nothing can be proven. Your source was NOT touched."
        )
        out += _ask_for_input("decompose", file, function, params, why)
        out.append("")
        out.append("  Pass apply=True alongside the input. The gate is not the flag — the gate is")
        out.append("  the proof. apply=True without a proof still writes nothing.")
        return "\n".join(out)

    for block in r.unsafe_blocks:
        out.append(f"  ✗ not extractable: {block}")
    out.append("")
    out.append("DONE: nothing here can be safely extracted. Nothing to derive.")
    return "\n".join(out)


# ── the live session ─────────────────────────────────────────────────────────────────


def _in_session(root: str, file: str | None, fn: Callable[[], Any]) -> tuple[Any, str | None]:
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
    the files that could execute the target's lines before anything is imported. The trace
    budgets are deliberately NOT passed: this surface exposes no knob for them, so they take the
    engine's defaults, and forwarding `None` here would read as "unbounded" and remove the only
    bound on the baseline pass. A caller who needs to change them wants the CLI.

    A missing session is returned as a WARNING, never swallowed: degrading quietly to a weaker
    test set is what makes a well-specified suite look under-specified, and a caller that cannot
    tell the difference will act on the wrong number.
    """
    try:
        from Wesker.ci import run_with_live_suite
    except ImportError:
        return fn(), None

    targets = [file] if file else None
    paths = _reachable_paths(root, targets)
    result = run_with_live_suite(root, fn, target_files=targets, paths=paths)
    if result is None:
        # `None` means exactly one thing here: no live session could be started. Re-run without
        # one so the caller still gets an answer, but SAY the answer is weaker.
        return fn(), (
            "⚠ NO live pytest session (pytest missing, or collection failed). Fixture-taking\n"
            "  tests could not run, so behaviour below may read as unspecified when a test does\n"
            "  pin it. Treat these counts as an UPPER BOUND, not a finding."
        )
    return result, None


# Prepended to any CLI-rendered report handed back through this surface. That text is written
# for a human at a terminal and says so in its own idiom: `--input "(...)"`, `decompose 'fn'
# --apply`, `detective flag 'f::g' MUTANT_ID`. None of those are calls a tool caller can make,
# and `flag` is not exposed here AT ALL — so a caller reading the full report is being handed
# instructions it cannot follow, in a register that invites it to shell out and improvise. The
# report itself is correct and worth reading; only the imperatives are addressed to someone
# else. Say so at the door rather than rewrite the engine's own honest rendering.
_CLI_REPORT_HEADER = (
    "ℹ This is the CLI's full report, rendered for a human. Read it for the detail — every\n"
    '  survivor, its exact diff, the scores. IGNORE its instructions: `--input "(...)"`,\n'
    "  `--apply` and `detective flag ...` are terminal syntax, not calls you can make.\n"
    "  The equivalents fork it offers is a HUMAN judgement and is deliberately not a tool\n"
    "  here — if a survivor looks truly equivalent, ask the user; do not decide it.\n"
    '  To act, use the terse view: converge(..., inputs=["(<real call>)"]).\n'
)


def _rendered(root: str, file: str | None, produce: Callable[[], str]) -> str:
    """``produce()`` inside a live session, with any session warning prepended to its text."""
    text, warning = _in_session(root, file, produce)
    return f"{warning}\n\n{text}" if warning else text


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
    def diagnose(file: str, function: str, project_root: str = ".", full: bool = False) -> str:
        """START HERE for any function you are about to change. Writes nothing.

        Reports every behavioural distinction the function makes and which ones no test
        pins, then names the single next call. Read the whole response; it is the product,
        not a log. Do not grep the source to check its findings — it ran the mutants and
        you did not.
        """
        from .cli import _format_scope
        from .engine import diagnose as _diagnose

        def _go() -> str:
            scope = _diagnose(file, function, project_root)
            if full:
                return _CLI_REPORT_HEADER + "\n" + _format_scope(scope)
            return _render_diagnose(scope, file, function)

        return _rendered(project_root, file, _go)

    @server.tool()
    def converge(
        file: str,
        function: str,
        project_root: str = ".",
        inputs: list[str] | None = None,
        full: bool = False,
    ) -> str:
        """Write the minimal pytest suite that pins this function's behaviour. WRITES FILES.

        ``inputs`` are real calls to the target, as strings: ``["(2.0, 600, True)"]``. Supply
        one whenever the response asks for it — that is the only thing this engine cannot
        derive for itself, and re-running without one cannot make progress.

        Calling this repeatedly with no new ``inputs`` is inert. If the answer did not change,
        that is not a bug and not a reason to look inside .detective/ — it means the engine
        already told you what it needs and is still waiting for it.
        """
        from .cli import _format_converge, _parse_supplied_inputs
        from .converge import converge as _converge

        def _go() -> str:
            supplied = _parse_supplied_inputs(inputs) if inputs else None
            result = _converge(file, function, project_root, supplied_inputs=supplied)
            full_text = (
                _CLI_REPORT_HEADER + "\n" + _format_converge(result, show_tests=True) if full else None
            )
            return _render_converge(result, file, function, full_text)

        return _rendered(project_root, file, _go)

    @server.tool()
    def decompose(
        file: str,
        function: str,
        project_root: str = ".",
        apply: bool = False,
        inputs: list[str] | None = None,
        full: bool = False,
    ) -> str:
        """Split a tangled function into helpers. Applied ONLY when proven behaviour-preserving.

        ``apply=True`` is not "do it" — it is "do it if proven". It converges a suite, runs it
        against the unchanged function for a baseline, trial-writes each extraction, re-runs,
        and keeps it only if green. An unproven extraction is never written, with or without
        the flag. A refusal here is the tool working, not an obstacle to route around.
        """
        from .cli import _format_decompose, _parse_supplied_inputs
        from .decompose_apply import apply_decomposition

        def _go() -> str:
            supplied = _parse_supplied_inputs(inputs) if inputs else None
            result = apply_decomposition(file, function, project_root, write=apply, supplied_inputs=supplied)
            if full:
                return _CLI_REPORT_HEADER + "\n" + _format_decompose(result, apply)
            return _render_decompose(result, file, function, apply)

        return _rendered(project_root, file, _go)

    @server.tool()
    def audit(file: str, function: str, project_root: str = ".") -> str:
        """Assess the suite that already exists: complete? minimal? what is safe to delete?

        Writes nothing, ever. Deletions are proposals; the user confirms them.
        """
        from .audit import audit_suite
        from .cli import _format_audit

        return _rendered(
            project_root,
            file,
            lambda: _CLI_REPORT_HEADER + "\n" + _format_audit(audit_suite(file, function, project_root)),
        )

    @server.tool()
    def deep_context(file: str, function: str, project_root: str = ".") -> str:
        """The full analysis: every survivor, its exact diff, the scores, the written tests.

        Call this when you are curious, or when the user asks for the numbers. You do not need
        it to act — the other tools already told you the next call. This is a door, not a step.
        """
        from .cli import _format_converge
        from .converge import converge as _converge

        return _rendered(
            project_root,
            file,
            lambda: _CLI_REPORT_HEADER
            + "\n"
            + _format_converge(_converge(file, function, project_root, write_dir=None), show_tests=True),
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
