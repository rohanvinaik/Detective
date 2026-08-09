"""Structural ban: no internal issue tag (#NN) may reach a user-facing CLI string.

The CLI is the product's surface — a precise, functional tool, not a place for developer
bookkeeping. A flag's help, a subcommand description, or a printed line carrying "(#37)" leaks an
issue tracker the user does not have and has no reason to see. Stripping the instances that leaked
is not enough: the next subcommand or the next printed message would reintroduce it, and it would
ship. So the class is banned STRUCTURALLY, in two independent ways that a new leak cannot slip
past both of:

1. Build the REAL parser and render every subcommand's ``--help``; assert none contains an issue
   tag. This is exactly the text a user sees, so the check cannot drift from the surface.
2. AST-scan the source of both shipped packages for issue tags inside the string arguments of
   ``say(...)`` / ``print(...)`` — the runtime messages rendered help cannot show. Docstrings,
   comments, and internal reference constants are deliberately untouched: they are not the CLI.

The banned pattern is ``#`` followed by digits — the issue-tag signature. If a genuine CLI string
ever needs a literal ``#123``, that is a deliberate decision to make here, not a silent default.
"""

from __future__ import annotations

import argparse
import ast
import os
import re

import Wesker

import Detective
from Detective.cli import _build_parser

_TAG = re.compile(r"#\d+")
_PRINTERS = {"say", "print"}
_PACKAGE_DIRS = [
    os.path.dirname(os.path.abspath(Detective.__file__)),
    os.path.dirname(os.path.abspath(Wesker.__file__)),
]


def _all_parsers(
    parser: argparse.ArgumentParser,
    seen: list[argparse.ArgumentParser] | None = None,
) -> list[argparse.ArgumentParser]:
    """The top parser and every subparser reachable from it, deduplicated by identity."""
    seen = seen if seen is not None else []
    if any(parser is s for s in seen):
        return seen
    seen.append(parser)
    for action in parser._actions:  # noqa: SLF001 — introspecting argparse is the point
        if isinstance(action, argparse._SubParsersAction):
            for sub in action.choices.values():
                _all_parsers(sub, seen)
    return seen


def test_no_issue_tag_in_any_rendered_cli_help() -> None:
    offenders: list[str] = []
    for parser in _all_parsers(_build_parser()):
        rendered = parser.format_help()
        for match in _TAG.finditer(rendered):
            offenders.append(f"{getattr(parser, 'prog', '?')}: {match.group(0)}")
    assert not offenders, (
        "Issue tags leaked into rendered CLI help — the CLI is inviolate:\n  " + "\n  ".join(offenders)
    )


def _tagged_strings_in_call(call: ast.Call) -> list[str]:
    """Issue-tagged string literals passed positionally to ``call``, f-string parts included."""
    found: list[str] = []

    def _scan(node: ast.AST) -> None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and _TAG.search(node.value):
            found.append(node.value)
        elif isinstance(node, ast.JoinedStr):
            for value in node.values:
                _scan(value)

    for arg in call.args:
        _scan(arg)
    return found


def test_no_issue_tag_in_any_printed_message() -> None:
    offenders: list[str] = []
    for pkg_dir in _PACKAGE_DIRS:
        for dirpath, _dirs, files in os.walk(pkg_dir):
            for filename in files:
                if not filename.endswith(".py"):
                    continue
                path = os.path.join(dirpath, filename)
                with open(path, encoding="utf-8") as handle:
                    tree = ast.parse(handle.read(), filename=path)
                for node in ast.walk(tree):
                    if not isinstance(node, ast.Call):
                        continue
                    func = node.func
                    name = (
                        func.id
                        if isinstance(func, ast.Name)
                        else func.attr
                        if isinstance(func, ast.Attribute)
                        else None
                    )
                    if name in _PRINTERS:
                        for text in _tagged_strings_in_call(node):
                            offenders.append(f"{os.path.basename(path)}:{node.lineno}  {text[:70]!r}")
    assert not offenders, (
        "Issue tags leaked into printed CLI messages — the CLI is inviolate:\n  " + "\n  ".join(offenders)
    )
