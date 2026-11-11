"""#142 (routing items): (1) an `ObservationIncomplete` ended in ONE line with no next command even when the
remedy is known — a `*_timeout` code has the CUT ending's `--deadline` re-run; (3) the decision record named a
divergent residual's ids `flaggable_ids`, though its page says nothing is flaggable; (4) under a step-budget
floor the uncovered row said "all named in the action below" and the action named none."""

from types import SimpleNamespace

import pytest

import Detective.cli as cli
from Detective.capture import ObservationIncomplete
from Detective.cli import (
    _decision_payload,
    _open_work_rows,
    _with_option,
    guards_pointer,
    observation_incomplete_remedy,
    residual_ids_key,
)


@pytest.mark.parametrize(
    ("code", "deadline", "dl", "expected"),
    [
        ("property_timeout", 300.0, True, "raise_deadline"),
        ("property_timeout", None, True, "raise_deadline"),
        ("witness_render_timeout", 899.0, True, "raise_deadline"),
        ("property_timeout", 900.0, True, "disable_deadline"),
        ("property_timeout", 0.0, True, "unbounded_timeout"),
        ("property_timeout", 300.0, False, "none"),
        ("property_uncontained", 300.0, True, "none"),
        ("execution_refused", 300.0, True, "none"),
        ("process_effect_blocked", 300.0, True, "none"),
        ("", 300.0, True, "none"),
    ],
)
def test_observation_incomplete_remedy(code, deadline, dl, expected):
    assert observation_incomplete_remedy(code, deadline, dl) == expected


def test_with_option_replaces_both_spellings_and_appends():
    assert _with_option(["converge", "f.py::g"], "--deadline", "900") == [
        "converge",
        "f.py::g",
        "--deadline",
        "900",
    ]
    assert _with_option(["converge", "t", "--deadline", "300", "--fast"], "--deadline", "0") == [
        "converge",
        "t",
        "--fast",
        "--deadline",
        "0",
    ]
    assert _with_option(["converge", "t", "--deadline=300"], "--deadline", "900")[-2:] == [
        "--deadline",
        "900",
    ]
    assert _with_option(["converge", "t"], "--isolated", None) == ["converge", "t", "--isolated"]


def _main_raising(monkeypatch, capsys, code, argv):
    def boom(_args):
        raise ObservationIncomplete(code, "the remaining execution deadline is exhausted")

    monkeypatch.setattr(cli, "_run_live", boom)
    monkeypatch.setattr(cli, "recover_interrupted_trials", lambda *_a, **_k: None, raising=False)
    status = cli.main(argv)
    return status, capsys.readouterr().out


def test_timeout_names_the_deadline_rerun(monkeypatch, capsys, tmp_path):
    argv = ["converge", "m.py::f", "--project-root", str(tmp_path)]
    status, out = _main_raising(monkeypatch, capsys, "property_timeout", argv)
    assert status == 3
    assert out.splitlines()[0].startswith("INCOMPLETE:  property_timeout:")
    do_this = next(line for line in out.splitlines() if line.startswith("DO THIS:"))
    assert do_this.endswith("--deadline 900")
    assert "converge m.py::f" in do_this or "converge 'm.py::f'" in do_this


def test_timeout_after_900_goes_to_zero_not_900_again(monkeypatch, capsys, tmp_path):
    argv = ["converge", "m.py::f", "--project-root", str(tmp_path), "--deadline", "900"]
    _status, out = _main_raising(monkeypatch, capsys, "property_timeout", argv)
    do_this = next(line for line in out.splitlines() if line.startswith("DO THIS:"))
    assert do_this.endswith("--deadline 0") and "--deadline 900" not in do_this


def test_other_codes_keep_the_one_line_form_and_the_json_says_none(monkeypatch, capsys, tmp_path):
    import json

    argv = ["converge", "m.py::f", "--project-root", str(tmp_path)]
    _status, out = _main_raising(monkeypatch, capsys, "execution_refused", argv)
    assert "DO THIS" not in out and len(out.strip().splitlines()) == 1
    _status, out = _main_raising(monkeypatch, capsys, "execution_refused", [*argv, "--json"])
    assert json.loads(out)["next"] == {"remedy": "none", "command": None}


def test_json_carries_the_remedy(monkeypatch, capsys, tmp_path):
    import json

    argv = ["converge", "m.py::f", "--project-root", str(tmp_path), "--json"]
    _status, out = _main_raising(monkeypatch, capsys, "property_timeout", argv)
    payload = json.loads(out)
    assert payload["next"]["remedy"] == "raise_deadline"
    assert payload["next"]["command"].endswith("--deadline 900")


def test_divergent_residual_is_not_recorded_as_flaggable():
    assert residual_ids_key("step_budget_divergent") == "divergent_ids"
    assert residual_ids_key("unprobed") == "flaggable_ids"
    assert residual_ids_key("") == "flaggable_ids"
    record = SimpleNamespace(
        verb="converge",
        code="step_budget_divergent",
        route="",
        kind="hand_back",
        argv=None,
        then=None,
        remedy="divergent",
        plan=None,
        residual=("step_budget_divergent", ("M1",)),
        optional=(),
        state={},
        final=None,
        two_sign=False,
        run_universe=cli.UniverseOptions(),
        withheld=(),
        note="",
        supplied=(),
    )
    residual = _decision_payload(record)["residual"]
    assert residual == {"basis": "step_budget_divergent", "divergent_ids": ["M1"]}


def test_guards_pointer_points_at_the_action_only_when_it_names_the_lines():
    assert guards_pointer("close_the_gap") == "action"
    for code in ("repair_measurement", "step_budget_divergent", "fix_failing_test", "fix_collection", ""):
        assert guards_pointer(code) == "report"


def test_the_step_budget_block_names_the_other_open_work():
    verdict = SimpleNamespace(crash_only=False)
    result = SimpleNamespace(missing_lines=[11, 12, 13])
    rows = "\n".join(_open_work_rows(result, SimpleNamespace(equivalent=[verdict, verdict])))
    assert "3 uncovered line(s) · 2 unproven-equivalent" in rows
    assert _open_work_rows(SimpleNamespace(missing_lines=[]), SimpleNamespace(equivalent=[])) == []
    assert _open_work_rows(SimpleNamespace(missing_lines=[]), None) == []
