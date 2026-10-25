"""Intent: every printed command carries the run's universe-defining options, or is not printed (#115).

#115's four named surfaces now carry `--two-sign` and FINAL names the policy. Its Expected also asks
that "every printed command carries the run's policy options: --two-sign, and any other option that
changes the measured universe", and the verifier's fixtures (re-measured 2026-10-25) showed those
dropped:

- `converge m.py::scale --two-sign --fast` STOPped with `Re-run detective converge 'm.py::scale'
  --two-sign` (no --fast);
- `converge m.py::expired --clock 1700000000` re-ran without --clock, and its UNVERIFIED FINAL omitted
  the capability set the COMPLETE FINAL names;
- `converge m.py::mode --env MODE=prod` re-ran without --env — a run without the declared variable is
  refused;
- the clock-gated DONE printed `decompose … --apply` and `flag …`, neither of which takes --clock.

The rule, from what the options MEAN: `--two-sign` (the operator universe), `--clock`/`--env` (the world
the function ran in) and `--receiver-factory` (the receiver population) are REQUIRED; `--fast` is a
sampling choice, carried where accepted. A verb that cannot take a required option is not printed —
the page names why. The carried options come from ONE record (`UniverseOptions`) through one decision
(`universe_carry`), checked against each verb's own parser.
"""

from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from Detective.cli import (
    Decision,
    UniverseOptions,
    _audit_commands,
    _build_parser,
    _converge_commands,
    _decision_payload,
    _final_banner_status,
    _verb_options,
    universe_carry,
)

_CONVERGE = [
    "--clock",
    "--env",
    "--fast",
    "--receiver-factory",
    "--two-sign",
    "--input",
    "--project-root",
]
_POLICY_ONLY = ["--two-sign", "--project-root", "--json"]


@pytest.mark.parametrize(
    ("accepted", "two_sign", "fast", "clock", "env", "receiver", "expected"),
    [
        (["--project-root"], True, True, "1700000000.0", ["A=1"], "pkg:make", ("static", ())),
        (
            _CONVERGE,
            True,
            True,
            "1700000000.0",
            ["A=1", "B-"],
            "pkg:make",
            (
                "carry",
                (
                    "--two-sign",
                    "--fast",
                    "--clock",
                    "1700000000.0",
                    "--env",
                    "A=1",
                    "--env",
                    "B-",
                    "--receiver-factory",
                    "pkg:make",
                ),
            ),
        ),
        (_POLICY_ONLY, False, False, "1700000000.0", [], "", ("cannot_reproduce", ("--clock",))),
        (
            _POLICY_ONLY,
            True,
            False,
            "",
            ["MODE=prod"],
            "pkg:make",
            ("cannot_reproduce", ("--env", "--receiver-factory")),
        ),
        (_POLICY_ONLY, True, True, "", [], "", ("carry", ("--two-sign",))),
        (_POLICY_ONLY, False, False, "", [], "", ("carry", ())),
        (_CONVERGE, False, True, "", [], "", ("carry", ("--fast",))),
    ],
)
def test_universe_carry_carries_what_the_verb_accepts_or_names_what_it_lacks(
    accepted, two_sign, fast, clock, env, receiver, expected
):
    assert universe_carry(accepted, two_sign, fast, clock, env, receiver) == expected


def test_each_verb_parser_is_the_authority_on_what_it_carries():
    converge = _verb_options("converge")
    assert {"--two-sign", "--fast", "--clock", "--env", "--receiver-factory"} <= converge
    for verb in ("decompose", "flag", "audit", "diagnose"):
        options = _verb_options(verb)
        assert "--two-sign" in options, verb
        assert "--clock" not in options and "--env" not in options, verb
    assert "--fast" not in _verb_options("audit")
    assert "--two-sign" not in _verb_options("plan"), "plan measures no mutant universe"


_FULL = UniverseOptions(
    two_sign=True, fast=True, clock=1700000000.0, env=("MODE=prod",), receiver_factory="pkg:make"
)


def _parses_to_the_same_universe(argv):
    parsed = _build_parser().parse_args(list(argv))
    assert parsed.command == "converge"
    assert parsed.two_sign is True
    assert parsed.fast is True
    assert parsed.clock == 1700000000.0
    assert parsed.env == ["MODE=prod"]
    assert parsed.receiver_factory == "pkg:make"
    return parsed


@pytest.mark.parametrize(
    ("code", "route", "kind"),
    [
        ("fix_verification", "", "stop"),
        ("fix_load", "", "stop"),
        ("provide_sample", "", "author"),
    ],
)
def test_every_rerun_is_a_command_that_reproduces_the_universe(code, route, kind):
    argv, then = _converge_commands(code, route, kind, "m.py::f", ".", (), None, universe=_FULL)
    assert argv is None
    _parses_to_the_same_universe(then)


def test_the_stale_rerun_and_the_witness_run_carry_the_universe_too():
    argv, _ = _converge_commands("rerun_stale", "", "stop", "m.py::f", ".", (), None, universe=_FULL)
    _parses_to_the_same_universe(argv)
    plan = SimpleNamespace(items=("(1,)",))
    argv, _ = _converge_commands("close_the_gap", "", "run", "m.py::f", ".", (), plan, universe=_FULL)
    parsed = _parses_to_the_same_universe(argv)
    assert parsed.input == ["(1,)"]


def test_without_a_universe_record_the_policy_choice_alone_is_carried():
    argv, then = _converge_commands("fix_verification", "", "stop", "m.py::f", ".", (), None, True)
    assert then == ("converge", "m.py::f", "--two-sign")


def test_audit_carries_its_policy_through_the_same_derivation():
    assert _audit_commands("close_the_gap", "m.py::f", True) == (("converge", "m.py::f", "--two-sign"), None)
    assert _audit_commands("fix_failing_test", "m.py::f", False) == (None, ("audit", "m.py::f"))


def _unverified(**over):
    base = {
        "function": "m.py::expired",
        "stale_target": False,
        "budget_exhausted": False,
        "admits_certificate": True,
        "verification": SimpleNamespace(ok=False, status="tests_failed", passed=1, failed=1, errors=0),
        "capability_identity": None,
        "receiver_identity": None,
    }
    base.update(over)
    return SimpleNamespace(**base)


def test_an_unverified_final_names_the_capability_set_and_receiver_it_was_measured_under():
    line = _final_banner_status(_unverified(capability_identity="clock=1700000000.0"))
    assert "⚠ UNVERIFIED" in line
    assert "under capability set clock=1700000000.0" in line
    line = _final_banner_status(_unverified(receiver_identity="pkg:make()"))
    assert "under receiver pkg:make()" in line
    assert " · under " not in _final_banner_status(_unverified()), "no scope invented for an unscoped run"


def test_the_json_record_carries_the_universe_and_what_was_withheld():
    d = Decision(
        "converge",
        "settled",
        "",
        "done",
        "",
        None,
        None,
        None,
        "",
        None,
        (),
        {},
        universe=UniverseOptions(clock=1700000000.0),
        withheld=(("decompose", ("--clock",)),),
    )
    payload = _decision_payload(d)
    assert payload["universe"] == ["--clock", "1700000000.0"]
    assert payload["withheld"] == [{"verb": "decompose", "missing": ["--clock"]}]
    legacy = Decision("audit", "x", "", "run", "", None, None, None, "", None, (), {}, two_sign=True)
    assert _decision_payload(legacy)["universe"] == ["--two-sign"]


# ---------------------------------------------------------------- through the real command

_PYPROJECT = (
    '[tool.pytest.ini_options]\nmarkers = ["detective: test generated by Detective"]\npythonpath = ["."]\n'
)


def _project(root: Path, source: str, tests: str) -> Path:
    (root / "tests").mkdir(parents=True)
    (root / "m.py").write_text(source)
    (root / "tests" / "test_m.py").write_text(tests)
    (root / "pyproject.toml").write_text(_PYPROJECT)
    return root


def _cli(project: Path, *args: str) -> subprocess.CompletedProcess:
    script = Path(sys.executable).with_name("detective")
    return subprocess.run(
        [str(script), *args, "--project-root", str(project)],
        cwd=str(project),
        capture_output=True,
        text=True,
        timeout=300,
    )


def _skip_if_cut(r):
    if "⚠ CUT" in r.stdout:
        pytest.skip("converge cut under the wall-clock budget — a measurement limit, not a verdict")


def test_a_declared_environment_survives_into_the_rerun_and_the_rerun_runs(tmp_path):
    project = _project(
        tmp_path,
        "import os\n\n\ndef mode():\n    return os.environ.get('MODE', 'dev')\n",
        "from m import mode\n\n\ndef test_known():\n    assert mode() in ('dev', 'prod')\n\n\n"
        "def test_wrong():\n    assert mode() == 'x'\n",
    )
    first = _cli(project, "converge", "m.py::mode", "--env", "MODE=prod")
    _skip_if_cut(first)
    # `test_wrong` reaches `mode` and fails, so since #114 converge stops at the failing floor and
    # prints its re-run as "After fixing" (the STOP block's "Re-run" belongs to other stops).
    label, line = next(
        (label, line)
        for line in first.stdout.splitlines()
        for label in ("Re-run", "After fixing")
        if label in line
    )
    rerun = line.split(label, 1)[1].strip()
    argv = shlex.split(rerun)
    parsed = _build_parser().parse_args(argv[1:])
    assert parsed.env == ["MODE=prod"]
    assert "under capability set" in first.stdout
    again = _cli(project, *argv[1:])
    _skip_if_cut(again)
    assert "under capability set" in again.stdout, "the printed re-run measures the same world"


def test_a_clock_gated_done_prints_no_verb_that_cannot_reproduce_the_clock(tmp_path):
    project = _project(
        tmp_path,
        "import time\n\n\ndef expired(deadline):\n    return time.time() > deadline\n",
        "from m import expired\n\n\ndef test_past():\n    assert expired(0) is True\n",
    )
    r = _cli(project, "converge", "m.py::expired", "--clock", "1700000000")
    _skip_if_cut(r)
    out = r.stdout
    assert "under capability set clock=1700000000.0" in out
    assert "detective decompose" not in out
    assert "detective flag" not in out
    assert "`decompose` is not offered: it takes no --clock" in out
    assert "`flag` is not offered: it takes no --clock" in out
    assert "detective plan 'm.py'" in out, "a static verb measures no universe and is still offered"
