"""``detective`` command — a thin dispatcher over the diagnose/certify API.

No compute here: parse args, call the library, format the result. Two commands:

    detective diagnose ./module.py::function [--json]
    detective certify  ./module.py::function [--write-dir tests] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict


def _split_target(target: str) -> tuple[str, str]:
    """Split ``path/to/file.py::function`` into ``(file, function)``."""
    if "::" not in target:
        raise SystemExit(f"target must be 'file.py::function', got {target!r}")
    file, function = target.rsplit("::", 1)
    if not file or not function:
        raise SystemExit(f"target must be 'file.py::function', got {target!r}")
    return file, function


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
    # Plain-language layer: what this means and what to do next.
    lines.append("  in plain terms:")
    if spec.unspecified_dof > 0:
        lines.append(f"    → {spec.unspecified_dof} behavior(s) no test pins yet — run `converge` to generate tests for them")
    else:
        lines.append("    → every behavior this function makes is already pinned by a test")
    if kq.warning:
        lines.append("    → tests mostly check it RUNS, not WHAT it returns — return values may be under-tested")
    if scope.regime == "B":
        lines.append("    → multiple interleaved responsibilities — `decompose` may split it into simpler pieces")
    return "\n".join(lines)


def _score(killed: int, total: int) -> str:
    """Mutation score as a whole-percent string; ``n/a`` when there are no mutants."""
    return f"{round(100 * killed / total)}%" if total else "n/a"


def _format_survivor_report(rep) -> list[str]:
    """Render the grounded disposition of every leftover survivor: equivalent
    (retained), killable (a suggested test, NOT auto-applied), or uncertain."""
    if rep is None:
        return []
    lines: list[str] = []
    if rep.equivalent and not rep.killable and not rep.unclassified:
        lines.append(
            "  ✓ functionally complete — every killable mutant killed; "
            f"{len(rep.equivalent)} equivalent mutant(s) retained (provably no test kills them)"
        )
    if rep.equivalent:
        cats = ", ".join(sorted({v.category for v in rep.equivalent}))
        tried = rep.equivalent[0].searched
        lines.append(
            f"  equivalent — retained, no test can kill ({len(rep.equivalent)}: {cats}); "
            f"no distinguishing input in {tried} tried"
        )
    if rep.manual_equivalent:
        lines.append(
            f"  ✓ {len(rep.manual_equivalent)} survivor(s) manually-flagged equivalent (oracle — not gaps)"
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


def _format_converge(result) -> str:
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
    verdict = "✓ COMPLETE — mutant-complete AND line-complete" if result.complete else "✗ INCOMPLETE"
    lines = [
        f"{result.function}: {verdict}",
        f"  {result.initial_survivors} → {result.final_survivors} survivors; "
        f"score {_score(initial_killed, total)} → {_score(result.killed, total)} "
        f"({result.killed}/{total} killed)",
        f"  mutant-complete={result.functionally_complete}  line-complete={result.line_complete}",
    ]
    for i, it in enumerate(result.iterations):
        lines.append(f"  pass {i}: {it.survivors} survivors, {it.written} sound tests written")
    if result.remaining:
        lines.append(f"  remaining: {', '.join(result.remaining)}")
    lines += _format_survivor_report(result.survivor_report)
    # Second completeness axis + minimality (from the baseline line-coverage pass).
    # Reported only when there is line data (minimal_test_count > 0 or a measured gap).
    if result.missing_lines:
        lines.append(
            f"  ✗ line gap: {len(result.missing_lines)} executable line(s) no test covers: "
            f"{list(result.missing_lines)}"
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
        lines.append(f"  wrote: {result.written_path}")
    if result.wiring:
        lines.append(f"  {result.wiring.message}")
    lines += _show_written(result.written_path)
    return "\n".join(lines)


def _format_decompose(r, applied_mode: bool) -> str:
    """Show what a decomposition did or would do: extractions PROVEN behavior-
    preserving by execution (auto-applied under --apply, else marked appliable),
    unvalidated proposals, and blocks skipped as unsafe — with the actual code."""
    lines = [f"{r.function}: decomposition"]
    if not r.applied and not r.proposed and not r.unsafe_blocks:
        return f"{r.function}: no separable blocks — nothing to decompose"
    for ex in r.applied:
        lines.append(
            f"  ✓ APPLIED (behavior-preserved, auto): {ex.helper_name}"
            f"({', '.join(ex.params)}) -> {', '.join(ex.returns) or 'None'}"
        )
        lines += [f"    │ {line}" for line in ex.new_source.splitlines()[:4]]
        lines.append("    │ …")
    for dec in r.proposed:
        ex = dec.extraction
        tag = "appliable (behavior-preserved) — re-run with --apply" if dec.validated else \
            "PROPOSED — not auto-validated; review before applying"
        lines.append(f"  → {tag}: {ex.helper_name}({', '.join(ex.params)}) -> {', '.join(ex.returns) or 'None'}")
        lines += [f"    │ {line}" for line in ex.new_source.splitlines()[:6]]
        lines.append("    │ …")
    for block in r.unsafe_blocks:
        lines.append(f"  ✗ not extractable: {block}")
    if not applied_mode and any(d.validated for d in r.proposed):
        lines.append("  (run `decompose --apply` to write the behavior-preserved extractions)")
    return "\n".join(lines)


def _format_audit(a) -> str:
    """Read-only audit of an existing suite: completeness on both axes, the
    pointless tests to propose removing, and the gaps to propose filling. Nothing
    is written — every action a real run would take is stated, not taken."""
    verdict = "✓ complete" if a.complete else "✗ incomplete"
    lines = [
        f"{a.function}: {a.test_count} existing test(s) — {verdict}",
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
    if a.manual_equivalent:
        lines.append(f"  ✓ {a.manual_equivalent} survivor(s) manually-flagged equivalent (oracle — not gaps)")
    if a.complete and not a.redundant_tests:
        lines.append("  nothing to do — suite is complete and minimal")
    return "\n".join(lines)


_COMMAND_HELP = {
    "converge": "generate a COMPLETE, minimal pytest suite for a function (the flagship)",
    "audit": "assess an EXISTING suite: complete? minimal? which tests to prune",
    "decompose": "extract entangled blocks into helpers (behavior-preserving; --apply to write)",
    "diagnose": "show a function's behavioral scope + what to run next (read-only)",
    "certify": "one-shot: synthesize tests for current survivors (prefer `converge`)",
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="detective",
        description="Generate/audit a function's pytest suite from its mutation profile. "
        "Typical use: `detective converge path/to/file.py::function`.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("converge", "audit", "decompose", "diagnose", "certify"):
        p = sub.add_parser(name, help=_COMMAND_HELP[name])
        p.add_argument("target", help="file.py::function")
        p.add_argument("--project-root", default=".")
        p.add_argument("--json", action="store_true", help="emit JSON")
        if name == "certify":
            p.add_argument("--write-dir", default=None, help="write synthesized tests here")
        if name == "converge":
            p.add_argument("--write-dir", default="tests", help="write synthesized tests here")
            p.add_argument("--max-iterations", type=int, default=3)
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
    """Run a command, then print a lightweight memory-telemetry footer (human mode).
    The footer is best-effort: monitoring must never fail the actual work."""
    args = _build_parser().parse_args(argv)
    code = _run(args)
    if not getattr(args, "json", False):
        try:
            from Wesker.memory_guard import telemetry

            print(f"  [{telemetry()}]")
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
        rec = next(
            (r for r in result.survivor_records if args.mutant_id in (r.get("mutant_id"), r.get("mutant"))),
            None,
        )
        if rec is None:
            ids = ", ".join(r.get("mutant_id", "?") for r in result.survivor_records) or "none surviving"
            print(f"no surviving mutant '{args.mutant_id}' for {function} — survivors: {ids}")
            return 1
        add_flag(args.project_root, result.function_key, rec.get("diff_summary", ""), note=args.note)
        suffix = f" ({args.note})" if args.note else ""
        print(f"flagged {args.mutant_id} as equivalent — {result.function_key}{suffix}")
        print("  future audit/converge runs will treat it as equivalent (a witness would still override)")
        return 0

    if args.command == "diagnose":
        from .engine import diagnose

        scope = diagnose(file, function, args.project_root)
        print(json.dumps(asdict(scope), indent=2, default=str) if args.json else _format_scope(scope))
        return 0

    if args.command == "converge":
        from .converge import converge

        result = converge(file, function, args.project_root, write_dir=args.write_dir, max_iterations=args.max_iterations)
        if args.json:
            print(json.dumps(asdict(result), indent=2, default=str))
        else:
            print(_format_converge(result))
        return 0

    if args.command == "audit":
        from .audit import audit_suite

        report = audit_suite(file, function, args.project_root)
        print(json.dumps(asdict(report), indent=2, default=str) if args.json else _format_audit(report))
        if args.remove and report.redundant_tests:
            from .suite_edit import apply_removals

            result = apply_removals(file, args.project_root, list(report.redundant_tests))
            print(f"  removed {len(result.removed)}: {', '.join(result.removed)}" if result.removed
                  else "  removed nothing")
            if result.not_found:
                print(f"  could not locate: {', '.join(result.not_found)}")
            if result.removed:
                # Re-audit so the user sees the suite is still complete after pruning.
                after = audit_suite(file, function, args.project_root)
                print(f"  after removal: {after.test_count} test(s), "
                      f"complete={after.complete}, minimal cover={after.minimal_test_count}")
        return 0

    if args.command == "decompose":
        from .decompose_apply import apply_decomposition

        result = apply_decomposition(file, function, args.project_root, write=args.apply)
        print(json.dumps(asdict(result), indent=2, default=str) if args.json else _format_decompose(result, args.apply))
        return 0

    from .certify import certify

    result = certify(file, function, args.project_root, write_dir=args.write_dir)
    if args.json:
        payload = {**asdict(result), "scope": asdict(result.scope)}
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(_format_scope(result.scope))
        status = "at ceiling — nothing to synthesize" if result.at_ceiling else f"{result.survivors} survivor(s)"
        print(f"  certify: {status}")
        if result.written_path:
            print(f"  wrote: {result.written_path}")
        if result.wiring:
            print(f"  {result.wiring.message}")
        for line in _show_written(result.written_path):
            print(line)
        plan = result.decomposition
        if plan and plan.is_decomposable:
            print(f"  decompose: {plan.rationale}")
            for candidate in plan.candidates:
                print(f"    - {candidate.proposed_name}: {candidate.reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
