"""Structural invariant: every ``--json`` verdict carries a self-describing exit field (#16).

`_EXIT_CODES` promises "CI branches on the code, --json on the field" — but a field a consumer is told
to branch on has to actually be EMITTED, in every verb, or the promise is a lie for whichever verb
forgot it. Stripping the instances that lacked it is not enough: the next verb would ship without it.
So the class is enforced STRUCTURALLY — the same discipline as the issue-tag ban.

Two independent checks a new leak cannot slip past both of:

1. AST: no ``_run_<verb>`` handler may call ``json.dumps`` / ``.to_json`` DIRECTLY. Every JSON verdict
   must go through the one funnel, ``_emit_json``, which injects ``exit_code`` + ``exit_meaning`` and
   returns the code — so the payload and its status are minted at one point and cannot disagree.
2. Behavioural: drive real verbs with ``--json`` and assert the emitted object carries both fields, and
   that ``exit_code`` equals the process exit status. This is the surface a consumer sees, so it cannot
   drift from the contract.

``exit_code_meaning`` (the pure label map) is converge-pinned in its own synth suite; this fixes the
wiring the pin cannot: that every verb consumes it.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys

import Detective
from Detective.cli import exit_code_meaning

_CLI = ast.parse(open(Detective.cli.__file__).read())  # type: ignore[attr-defined]  # noqa: SIM115


def _wraps_with_exit(call: ast.Call) -> bool:
    """A json.dumps(...) whose payload (first positional arg) is a `_with_exit(...)` call carries
    the field; anything else is a raw verdict that would ship without it."""
    a = call.args
    return (
        bool(a)
        and isinstance(a[0], ast.Call)
        and isinstance(a[0].func, ast.Name)
        and a[0].func.id == "_with_exit"
    )


def _emits_raw_json(fn: ast.FunctionDef) -> list[str]:
    bad = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "dumps" and not _wraps_with_exit(node):
                bad.append(f"{fn.name}:{node.lineno} json.dumps(...) not wrapped in _with_exit")
            elif node.func.attr == "to_json":
                bad.append(
                    f"{fn.name}:{node.lineno} .to_json() — use json.dumps(_with_exit(asdict(x), code))"
                )
    return bad


def test_no_run_handler_emits_raw_json() -> None:
    """Every per-verb handler routes its --json through _emit_json, never a raw dumps/to_json."""
    # `_run_receipt` is exempt: its --json emits the RECEIPT ARTIFACT (the RewriteReceipt schema
    # verify-rewrite later consumes), not a verdict envelope — an exit_code field would corrupt it.
    exempt = {"_run_receipt"}
    offenders: list[str] = []
    for node in ast.walk(_CLI):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("_run_") and node.name not in exempt:
            offenders.extend(_emits_raw_json(node))
    assert not offenders, (
        "A --json verdict bypassed the _emit_json funnel — it will ship without exit_code/exit_meaning:\n  "
        + "\n  ".join(offenders)
    )


def test_exit_code_meaning_is_total_over_the_contract() -> None:
    # the four codes _EXIT_CODES documents, plus the named fallback
    assert exit_code_meaning(0) == "clean"
    assert exit_code_meaning(1) == "gap_or_refusal"
    assert exit_code_meaning(2) == "conflict_or_precondition"
    assert exit_code_meaning(3) == "invalid_measurement_rerun"
    assert exit_code_meaning(99) == "unknown"


def _run_cli(args: list[str], root: str) -> tuple[int, dict]:
    proc = subprocess.run(
        [sys.executable, "-m", "Detective", *args, "--project-root", root, "--json"],
        capture_output=True,
        text=True,
        cwd=root,
    )
    return proc.returncode, json.loads(proc.stdout)


def test_real_verbs_emit_exit_code_matching_the_process_status(tmp_path) -> None:
    """Drive real verbs end-to-end: the --json object carries exit_code == the process exit status."""
    (tmp_path / "m.py").write_text("def f(x):\n    return x + 1\n")
    root = str(tmp_path)
    for args in (["regime"], ["parsimony", "m.py"], ["diagnose", "m.py::f"], ["audit", "m.py::f"]):
        code, payload = _run_cli(args, root)
        assert "exit_code" in payload, f"{args[0]} --json lacks exit_code"
        assert "exit_meaning" in payload, f"{args[0]} --json lacks exit_meaning"
        assert payload["exit_code"] == code, (
            f"{args[0]}: json exit_code {payload['exit_code']} != status {code}"
        )
        assert payload["exit_meaning"] == exit_code_meaning(code)
