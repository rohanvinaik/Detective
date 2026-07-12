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
    """Human-readable one-block rendering of a ScopeMap."""
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
    lines = [
        f"{result.function}: {result.initial_survivors} → {result.final_survivors} survivors",
        f"  mutation score: {_score(initial_killed, total)} → {_score(result.killed, total)}"
        f"  ({result.killed}/{total} killed)",
        f"  converged={result.converged}  at_ceiling={result.at_ceiling}"
        + ("  functionally_complete=True" if result.functionally_complete and not result.at_ceiling else ""),
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
    if a.complete and not a.redundant_tests:
        lines.append("  nothing to do — suite is complete and minimal")
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="detective", description="Behavioral-scope diagnosis and test synthesis.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("diagnose", "certify", "converge", "audit"):
        p = sub.add_parser(name, help=f"{name} a function")
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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    file, function = _split_target(args.target)

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
                print(f"    - {candidate.suggested_name}: {candidate.reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
