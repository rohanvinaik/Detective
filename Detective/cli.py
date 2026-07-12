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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="detective", description="Behavioral-scope diagnosis and test synthesis.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("diagnose", "certify", "converge"):
        p = sub.add_parser(name, help=f"{name} a function")
        p.add_argument("target", help="file.py::function")
        p.add_argument("--project-root", default=".")
        p.add_argument("--json", action="store_true", help="emit JSON")
        if name == "certify":
            p.add_argument("--write-dir", default=None, help="write synthesized tests here")
        if name == "converge":
            p.add_argument("--write-dir", default="tests", help="write synthesized tests here")
            p.add_argument("--max-iterations", type=int, default=3)
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
            print(f"{result.function}: {result.initial_survivors} → {result.final_survivors} survivors")
            print(f"  converged={result.converged}  at_ceiling={result.at_ceiling}")
            for i, it in enumerate(result.iterations):
                print(f"  pass {i}: {it.survivors} survivors, {it.written} sound tests written")
            if result.written_path:
                print(f"  wrote: {result.written_path}")
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
        plan = result.decomposition
        if plan and plan.is_decomposable:
            print(f"  decompose: {plan.rationale}")
            for candidate in plan.candidates:
                print(f"    - {candidate.suggested_name}: {candidate.reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
