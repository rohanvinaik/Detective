"""Intent tests for the ledger's ONE call site in `main` (`docs/INVOCATION_LEDGER.md` §6).

Through `main()`, because the thing under test is precisely which EXIT PATHS get recorded — and
that is invisible from inside the handler.

§6's argument, and the reason this is a `finally` rather than the tail block `main` already has:
`main` carries three typed-refusal paths, two of which leave via `raise SystemExit` and one via
`return 1`. A tail append misses all three. And a refusal is a process fact — "you pointed at a
target that does not exist, three times" is exactly a red finding — so the paths that refuse are
the ones that most need recording.
"""

from __future__ import annotations

import json
import os

import pytest

from Detective.cli import _ledger_args, main
from Detective.ledger import ledger_available, ledger_path, read_recent


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "m.py").write_text("def add(a, b):\n    if a > b:\n        return a\n    return b\n")
    return tmp_path


def _rows(root) -> list[dict]:
    return list(read_recent(str(root), limit=50))


# ---------------------------------------------------------------- the ordinary path


def test_a_normal_run_is_recorded_with_what_it_did(repo) -> None:
    main(["survey", "m.py", "--project-root", str(repo)])
    rows = _rows(repo)
    assert len(rows) == 1
    assert rows[0]["verb"] == "survey"
    assert rows[0]["target"] == "m.py"
    assert rows[0]["exit"] == 0
    assert rows[0]["refusal"] is None


def test_the_state_digests_describe_what_a_RE_RUN_would_measure(repo) -> None:
    """§3: `state` is what makes "nothing changed" decidable rather than a guess. Without it,
    `spiral_disposition` would have to take the operator's word for whether they edited anything."""
    main(["survey", "m.py", "--project-root", str(repo)])
    state = _rows(repo)[0]["state"]
    assert state["target_src"].startswith("sha256:"), "the target file's content"
    assert set(state) == {"target_src", "suite", "inputs", "equivalents"}


def test_the_two_knob_fact_is_recorded(repo) -> None:
    """`env.interpreter` selects the target's dependencies; `env.detective`/`env.wesker` select the
    code doing the measuring. Recorded so doctor can eventually say "your last five runs used
    .venv-det; the packages you installed went to ~/miniconda3" — the propagation case answered
    from HISTORY rather than from a live probe."""
    main(["survey", "m.py", "--project-root", str(repo)])
    env = _rows(repo)[0]["env"]
    assert env["interpreter"].endswith(("python", "python3", "python.exe"))
    assert env["detective"].endswith(".py")
    assert env["project_root"] == str(repo)


# ---------------------------------------------------------------- the paths a TAIL would miss


def test_a_typed_refusal_is_recorded_even_though_it_leaves_via_SystemExit(repo) -> None:
    """THE reason for `finally`. `_target_error` raises `SystemExit`, so a tail append never runs —
    and this is the single most process-shaped event there is: an operator pointing at something
    that is not there, repeatedly, is a red finding and nothing else can see it."""
    with pytest.raises(SystemExit):
        main(["diagnose", "m.py::no_such_function", "--project-root", str(repo)])
    rows = _rows(repo)
    assert len(rows) == 1
    assert rows[0]["refusal"] == "target_not_found"


def test_an_unbound_exit_code_is_null_rather_than_invented(repo) -> None:
    """Where the exception path leaves `code` unbound the entry records `exit: null`. A fabricated
    0 or 1 there would be a fact about the run that nobody measured — the shape this whole project
    exists to refuse."""
    with pytest.raises(SystemExit):
        main(["diagnose", "m.py::nope", "--project-root", str(repo)])
    assert _rows(repo)[0]["exit"] is None


def test_the_refusal_and_the_verb_are_both_kept(repo) -> None:
    """A refusal with no verb cannot answer "you ran diagnose three times against a target that
    does not exist" — which is the finding, not "something refused"."""
    with pytest.raises(SystemExit):
        main(["diagnose", "m.py::nope", "--project-root", str(repo)])
    row = _rows(repo)[0]
    assert row["verb"] == "diagnose"
    assert row["target"] == "m.py::nope"


# ---------------------------------------------------------------- what counts as the SAME run


def test_rendering_flags_are_not_part_of_the_invocation(repo) -> None:
    """§3: "two runs differing only in rendering are the same invocation for process purposes". If
    `--json` were keyed, every re-run in a different mode would look like PROGRESS and hide exactly
    the spiral the ledger exists to detect."""
    main(["survey", "m.py", "--project-root", str(repo)])
    main(["survey", "m.py", "--project-root", str(repo), "--json"])
    a, b = _rows(repo)
    assert a["args"] == b["args"], "a rendering flag must not make this look like a new question"


def test_a_measurement_affecting_flag_IS_part_of_it() -> None:
    """The other half, and the reason this is an exclusion list rather than an inclusion one: a new
    flag that changes the measurement is recorded by DEFAULT. An inclusion list would silently drop
    every flag nobody remembered to add, which is how a spiral becomes invisible."""
    from types import SimpleNamespace

    args = SimpleNamespace(command="converge", target="m.py::f", json=True, verbose=True, budget=500)
    keyed = _ledger_args(args)
    assert keyed == {"budget": 500}


def test_absent_and_default_values_are_not_recorded_as_facts() -> None:
    """A flag nobody passed is not a fact about the invocation, and recording `None`/`False` for
    every unset option would make two identical runs differ the moment a new option is added."""
    from types import SimpleNamespace

    args = SimpleNamespace(command="survey", path="m.py", fast=False, deadline=None, inputs=[])
    assert _ledger_args(args) == {}


# ---------------------------------------------------------------- §2.1, at the call site


def test_an_unwritable_project_still_runs_the_command(tmp_path, capsys) -> None:
    """The hard requirement, asserted where it actually matters. The shell swallows its own write
    failure; this pins that the CALL SITE does not reintroduce one — a `finally` that raises would
    replace the command's verdict with the ledger's problem."""
    (tmp_path / "m.py").write_text("def add(a, b):\n    return a + b\n")
    tmp_path.chmod(0o500)
    try:
        assert main(["survey", "m.py", "--project-root", str(tmp_path)]) == 0
    finally:
        tmp_path.chmod(0o700)


def test_a_run_that_records_nothing_still_returns_its_own_verdict(repo, monkeypatch) -> None:
    """Belt and braces on the same property: even if the recorder itself explodes, the verdict is
    the command's. "A run's verdict is unaffected by whether the ledger is watching" (§6)."""
    import Detective.cli as _cli

    monkeypatch.setattr(_cli, "_ledger_env", lambda root: 1 / 0)
    assert main(["survey", "m.py", "--project-root", str(repo)]) == 0


# ---------------------------------------------------------------- outcome, honestly partial


def test_the_outcome_channel_is_recorded_and_currently_only_converge_fills_it(repo) -> None:
    """`outcome` is the NAMED next-action code, which is what makes a repeat finding actionable —
    "you ran `fix_load` three times" rather than "you ran this three times with nothing changed".

    Only `converge` calls `observe` today, so every other verb records []. That is PARTIAL and is
    named as such in the recorder rather than left to look complete; full propagation is its own
    step (§6), and it must not change any command's rendered output or exit code.
    """
    main(["survey", "m.py", "--project-root", str(repo)])
    assert _rows(repo)[0]["outcome"] == [], "survey does not observe yet — recorded empty, not absent"
    assert "outcome" in _rows(repo)[0], "the field is always present, so absent never reads as none"


def test_every_record_carries_the_schema_version(repo) -> None:
    """§3: forward-compat for the inference work the founder named as this artifact's second use."""
    main(["survey", "m.py", "--project-root", str(repo)])
    assert _rows(repo)[0]["v"] == 1


def test_the_ledger_lands_where_the_reader_looks(repo) -> None:
    main(["survey", "m.py", "--project-root", str(repo)])
    assert ledger_available(str(repo))
    assert os.path.isfile(ledger_path(str(repo)))
    with open(ledger_path(str(repo)), encoding="utf-8") as fh:
        json.loads(fh.readline())
