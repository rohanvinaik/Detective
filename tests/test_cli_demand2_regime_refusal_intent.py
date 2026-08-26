"""CLI Demand 2 — the regime refusal is a first-class output for BOTH channels, on every verb.

Defect A: `_run_live` refused a regime conflict only `and not args.json`, so a --json consumer fell
through into the session and received a verdict measured against the shadowed/colliding target — the
exact number the refusal exists to withhold — while its two sibling refusals (wrong_interpreter,
collection_errors) both emit a typed REFUSED under --json. A now emits the same typed REFUSED / exit 2.

Defect B: `_REGIME_STAGE` was attached to help only for diagnose/converge/decompose/audit, but flag,
flag-line, receipt, and verify-rewrite also carry a target and run the same regime resolution — a
capability that gates them with nothing on their page leading to it. B adds the stage to their help.
"""

from __future__ import annotations

import json as _json
from types import SimpleNamespace

import Detective.cli as cli

_REGIME_MARKER = "resolves the repo's TESTING REGIME"  # a phrase unique to _REGIME_STAGE


def test_regime_conflict_refuses_json_consumers_with_a_typed_refusal(monkeypatch, capsys):
    # A conflicting regime, a ready interpreter, and a deterministic conflict render.
    monkeypatch.setattr(
        "Detective.regime.resolve_regime", lambda *a, **k: SimpleNamespace(conflicts=True, module="pkg.mod")
    )
    monkeypatch.setattr(cli, "_execution_context", lambda: SimpleNamespace(disposition="ready"))
    monkeypatch.setattr(cli, "_format_conflicts", lambda regime, target: "CONFLICT: shadowed by another copy")
    args = SimpleNamespace(command="converge", target="m.py::f", json=True, project_root=".")

    code = cli._run_live(args)
    payload = _json.loads(capsys.readouterr().out)

    assert code == 2  # a precondition, refused — NOT a fall-through into the session
    assert payload["verdict"] == "REFUSED"
    assert payload["reason"] == "regime_conflict"
    assert payload["exit_code"] == 2 and payload["exit_meaning"] == "conflict_or_precondition"


def _subparser_choices():
    parser = cli._build_parser()
    action = next(a for a in parser._actions if getattr(a, "choices", None))
    return action.choices


def test_every_regime_checked_verb_advertises_the_regime_stage():
    choices = _subparser_choices()
    # The four already-covered verbs PLUS the four this fix adds.
    for verb in (
        "diagnose",
        "converge",
        "decompose",
        "audit",
        "flag",
        "flag-line",
        "receipt",
        "verify-rewrite",
    ):
        desc = choices[verb].description or ""
        assert _REGIME_MARKER in desc, f"{verb} runs the regime check but its help does not lead to it"


def test_static_verbs_do_not_falsely_advertise_the_regime_stage():
    # purge / parsimony / censor take a `path`, not a `target` — they run NO regime resolution, so
    # they must not carry the stage (it would promise a refusal that cannot happen).
    choices = _subparser_choices()
    for verb in ("purge", "parsimony", "censor"):
        desc = choices[verb].description or ""
        assert _REGIME_MARKER not in desc, f"{verb} is static and must not advertise the regime stage"
