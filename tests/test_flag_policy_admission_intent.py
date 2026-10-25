"""Intent: `flag` names the POLICY when an id exists only under the other one (#128).

The defect: a two-sign converge prescribed `detective flag … OUTPUT_<id>`, and `flag` — then
without `--two-sign` — profiled the one-sign universe and answered "no surviving mutant", so a
correct equivalence proof was refused as if the mutant were dead. `flag --two-sign` and the policy
carried on every printed flag command have since landed; what remained, reproduced 2026-10-25 on
current code, was the refusal itself: an OUTPUT id under the one-sign policy still read "no
surviving mutant 'OUTPUT_…' … survivors: …" (exit 1, after a full profile of the wrong universe),
and an empty id read "no surviving mutant ''" instead of the missing-id refusal.

An OUTPUT (μ⁻) mutant exists only in σ(P, μ ∪ μ⁻) — the one-sign policy never generates one — so
the id's category alone decides the refusal, before any profile runs.
"""

from __future__ import annotations

import pytest

from Detective.cli import flag_id_admission


@pytest.mark.parametrize(
    ("mutant_id", "two_sign", "expected"),
    [
        (None, False, "no_mutant_id"),
        (None, True, "no_mutant_id"),
        ("", False, "no_mutant_id"),
        ("   ", True, "no_mutant_id"),
        ("OUTPUT_09171603", False, "needs_two_sign"),
        (" OUTPUT_09171603 ", False, "needs_two_sign"),
        ("OUTPUT_09171603", True, "look_up"),
        ("STATE_bde50f1f", False, "look_up"),
        ("STATE_bde50f1f", True, "look_up"),
        ("output_09171603", False, "look_up"),
        ("VALUE_OUTPUT_1", False, "look_up"),
    ],
)
def test_the_admission_names_missing_id_wrong_policy_and_lookup_apart(mutant_id, two_sign, expected):
    assert flag_id_admission(mutant_id, two_sign) == expected


def _run(argv, monkeypatch, tmp_path):
    import json as _json
    import shlex
    from types import SimpleNamespace

    from Detective import cli, engine, equivalents

    profiled = []

    def measured(*a, **kwargs):
        profiled.append(kwargs.get("two_sign"))
        return SimpleNamespace(
            function_key="m.py::scale",
            value_survivor_records=[{"mutant_id": "STATE_bde50f1f", "diff_summary": "return None -> pass"}],
        )

    monkeypatch.setattr(engine, "profile", measured)
    monkeypatch.setattr(equivalents, "add_flag", lambda *a, **kw: None)
    args = cli._build_parser().parse_args([*argv, "--project-root", str(tmp_path)])
    code = cli._run_flag(args, "m.py", "scale")
    return SimpleNamespace(code=code, profiled=profiled, json=_json, shlex=shlex, cli=cli)


def test_an_output_id_under_one_sign_is_refused_by_policy_before_any_profile(monkeypatch, tmp_path, capsys):
    run = _run(
        ["flag", "m.py::scale", "OUTPUT_09171603", "--note", "NoneType() is None"], monkeypatch, tmp_path
    )
    err = capsys.readouterr().err
    assert run.code == 2  # conflict_or_precondition: the command cannot succeed as given
    assert run.profiled == [], "the wrong universe must not be profiled to say so"
    assert "OUTPUT mutants exist only under the two-sign policy" in err
    assert "no surviving mutant" not in err
    # The repair is the same command under the policy that holds the id, and it round-trips.
    repair = err.split("Re-run: ", 1)[1].strip()
    argv = run.shlex.split(repair)
    assert argv[0] == "detective"
    parsed = run.cli._build_parser().parse_args(argv[1:])
    assert parsed.command == "flag"
    assert parsed.two_sign is True
    assert parsed.mutant_id == "OUTPUT_09171603"
    assert parsed.note == "NoneType() is None"
    assert parsed.project_root == str(tmp_path)


def test_the_policy_refusal_is_typed_in_json(monkeypatch, tmp_path, capsys):
    run = _run(["flag", "m.py::scale", "OUTPUT_09171603", "--fence", "--json"], monkeypatch, tmp_path)
    payload = run.json.loads(capsys.readouterr().out)
    assert run.code == 2
    assert payload["reason"] == "needs_two_sign"
    assert payload["exit_meaning"] == "conflict_or_precondition"
    assert "--two-sign" in payload["argv"]
    assert "--fence" in payload["argv"]
    assert "--json" in payload["argv"]


def test_an_empty_id_is_the_missing_id_refusal_not_a_lookup(monkeypatch, tmp_path, capsys):
    run = _run(["flag", "m.py::scale", "  "], monkeypatch, tmp_path)
    err = capsys.readouterr().err
    assert run.code == 2
    assert run.profiled == []
    assert "flag needs a surviving mutant id" in err


def test_an_output_id_under_two_sign_is_looked_up_in_that_universe(monkeypatch, tmp_path, capsys):
    run = _run(["flag", "m.py::scale", "OUTPUT_09171603", "--two-sign"], monkeypatch, tmp_path)
    out = capsys.readouterr().out
    assert run.profiled == [True]
    assert run.code == 1  # looked up, and genuinely not among this stub's survivors
    assert "no surviving mutant 'OUTPUT_09171603'" in out


def test_a_one_sign_id_is_still_looked_up_and_flagged(monkeypatch, tmp_path, capsys):
    run = _run(["flag", "m.py::scale", "STATE_bde50f1f", "--note", "proof"], monkeypatch, tmp_path)
    assert run.profiled == [False]
    assert run.code == 0
    assert "flag · STATE_bde50f1f" in capsys.readouterr().out
