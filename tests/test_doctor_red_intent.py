"""Intent tests for doctor's RED axis and the superadditive products (`docs/DOCTOR.md` §2, §3).

Red does nothing alone and COMPLETES green — that is the mechanic, not a metaphor. Knowing what the
operator was TRYING to do turns "your venv lacks funcy" into "…and that is why your converge
reported 0 kills and asked you for inputs; fix the import first, then re-run — do not author
inputs." Neither axis alone can say that sentence.
"""

from __future__ import annotations

import pytest

from Detective.cli import main
from Detective.doctor import mix_product, process_disposition, red_facts
from Detective.ledger import append

_SRC = "def add(a, b):\n    if a > b:\n        return a\n    return b\n"


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "m.py").write_text(_SRC)
    return tmp_path


def _row(root, **over) -> dict:
    base = {
        "v": 1,
        "verb": "audit",
        "target": "m.py::add",
        "args": {},
        "exit": 0,
        "refusal": None,
        "env": {"interpreter": "/py", "detective": "/d.py", "wesker": "/w.py", "version": "1"},
        "state": {"target_src": "sha256:aaa", "suite": "sha256:bbb", "inputs": "", "equivalents": ""},
        "outcome": [["outcome", "audit", "close_the_gap"]],
    }
    base.update(over)
    append(str(root), base)
    return base


# ---------------------------------------------------------------- the ranking


def test_moved_ground_outranks_everything_because_it_invalidates_the_comparison() -> None:
    """Not a taste ranking. EVERY other red finding is a comparison BETWEEN runs, and a comparison
    across changed ground compares different things. A "spiral" computed across an interpreter
    change is not a spiral — it is two measurements of two environments, and reporting it as a
    repeat sends the operator to stop doing the one thing that was actually varying."""
    for drift in ("interpreter_changed", "engine_changed", "version_changed"):
        assert process_disposition(drift, "spiral", "taste_before_behaviour") == "ground_moved"


def test_a_spiral_outranks_an_ordering_finding() -> None:
    assert process_disposition("stable", "spiral", "taste_before_behaviour") == "spiral"


def test_one_repeat_is_named_but_is_not_a_spiral() -> None:
    """Two identical runs is how anyone checks a result. The remedy differs — there is none — so
    collapsing it into `spiral` would cry wolf on ordinary use."""
    assert process_disposition("stable", "repeat_no_change", "ok") == "repeat_no_change"
    assert process_disposition("stable", "spiral", "ok") == "spiral"


def test_ordinary_iteration_never_becomes_a_finding() -> None:
    """An edit-then-rerun loop IS how the tool is used. A process axis that flagged it would be
    noise on the one surface whose credibility is the product."""
    for spiral in ("no_prior", "progressed", "repeat_state_changed"):
        assert process_disposition("stable", spiral, "ok") == "clear"


# ---------------------------------------------------------------- the products (§3)


@pytest.mark.parametrize(
    ("live", "expected"),
    [
        ((True, True, False), "suppression"),
        ((True, False, True), "unreliability"),
        ((False, True, True), "ordering"),
        ((True, True, True), "ordered_remediation"),
        ((True, False, False), "none"),
        ((False, True, False), "none"),
        ((False, False, True), "none"),
        ((False, False, False), "none"),
    ],
)
def test_each_combination_yields_a_verdict_no_single_axis_produces(live, expected) -> None:
    assert mix_product(*live) == expected


def test_a_product_needs_two_axes_to_multiply() -> None:
    """A mix line over a single finding is the line that always appears — the defect the signpost
    discipline exists to prevent, reproduced inside doctor itself."""
    assert mix_product(True, False, False) == "none"


# ---------------------------------------------------------------- reading the history


def test_no_ledger_is_UNAVAILABLE_not_clear(repo) -> None:
    """The §2.2 requirement, at the surface that consumes it. "We cannot read your history" and
    "your history is clean" are different claims about the operator, and rendering the first as the
    second is the single thing this axis must never do."""
    facts = red_facts(str(repo))
    assert facts["available"] is False


def test_history_that_records_only_doctor_has_no_subject(repo) -> None:
    """Doctor is the command you just ran. "You ran doctor twice" is not the finding anyone came
    for, so doctor is excluded from the subject search — and an empty result after that exclusion
    is honest rather than clean."""
    _row(repo, verb="doctor", target=None)
    _row(repo, verb="doctor", target=None)
    facts = red_facts(str(repo))
    assert facts["available"] is True
    assert facts["subject"] is None


def test_the_same_command_repeated_with_nothing_changed_is_a_spiral(repo) -> None:
    for _ in range(3):
        _row(repo)
    assert red_facts(str(repo))["spiral"] == "spiral"


def test_an_edit_between_runs_is_iteration_not_a_spiral(repo) -> None:
    """`state` is what makes this decidable rather than a guess — without it the axis would have to
    take the operator's word for whether they changed anything."""
    _row(repo)
    _row(repo, state={"target_src": "sha256:MOVED", "suite": "sha256:bbb", "inputs": "", "equivalents": ""})
    assert red_facts(str(repo))["spiral"] == "repeat_state_changed"


def test_a_different_target_does_not_manufacture_a_repeat(repo) -> None:
    """A different target is a different QUESTION. Mixing them would turn ordinary work across a
    codebase into a spiral accusation — the false-positive direction, which is the worse one."""
    _row(repo, target="m.py::add")
    _row(repo, target="m.py::other")
    _row(repo, target="m.py::add")
    assert red_facts(str(repo))["spiral"] != "spiral"


def test_a_changed_interpreter_is_reported_as_drift(repo) -> None:
    """THE motivating case's history half: a dependency installed into a different interpreter than
    the one Detective runs under. Nothing inside a single run can see it; two runs can."""
    _row(repo)
    _row(repo, env={"interpreter": "/other", "detective": "/d.py", "wesker": "/w.py", "version": "1"})
    assert red_facts(str(repo))["drift"] == "interpreter_changed"


def test_the_recorded_outcome_code_is_carried_so_the_finding_can_name_it(repo) -> None:
    """The whole point of `outcome` propagation. "You ran `fix_load` three times" names what to stop
    doing; "you ran this three times" does not."""
    for _ in range(3):
        _row(repo, outcome=[["outcome", "audit", "fix_load"]])
    facts = red_facts(str(repo))
    assert facts["spiral"] == "spiral"
    assert facts["outcome_code"] == "fix_load"


# ---------------------------------------------------------------- through the real command


def test_the_spiral_render_names_the_command_and_the_code(repo, capsys) -> None:
    for _ in range(3):
        _row(repo, outcome=[["outcome", "audit", "fix_load"]])
    main(["doctor", "--project-root", str(repo), "--red"])
    out = capsys.readouterr().out
    assert "spiral" in out
    assert "audit m.py::add" in out, "the command is named"
    assert "fix_load" in out, "…and so is the instruction it kept giving"


def test_an_unreadable_history_says_UNAVAILABLE_in_the_report(repo, capsys) -> None:
    main(["doctor", "--project-root", str(repo), "--red"])
    out = capsys.readouterr().out
    assert "not read" in out and "UNAVAILABLE" in out
    assert "NOT the same as absent" in out


def test_red_alone_never_changes_the_exit_code(repo, capsys) -> None:
    """Only a GREEN finding earns exit 2 — "your world is wrong". A process finding is about what
    you did, not about the environment being broken, and conflating them would make the exit code
    stop meaning what the documented table says."""
    for _ in range(3):
        _row(repo)
    code = main(["doctor", "--project-root", str(repo), "--red"])
    capsys.readouterr()
    assert code == 0


def test_red_never_speaks_about_the_code(repo, capsys) -> None:
    """The fence, on red's side. Every row is about what the OPERATOR did; none of it is a claim
    about the function under test."""
    for _ in range(3):
        _row(repo)
    main(["doctor", "--project-root", str(repo), "--red"])
    lowered = capsys.readouterr().out.lower()
    for forbidden in ("your code is fine", "every killable", "✓ complete", "the suite is complete"):
        assert forbidden not in lowered


def test_reading_red_does_not_disturb_the_history_it_reads(repo, capsys) -> None:
    """Doctor's own invocation IS recorded (it is a process fact), but the subject search excludes
    it — so reading twice must not change what the second read reports."""
    for _ in range(3):
        _row(repo)
    main(["doctor", "--project-root", str(repo), "--red"])
    first = capsys.readouterr().out
    main(["doctor", "--project-root", str(repo), "--red"])
    assert "spiral" in capsys.readouterr().out and "spiral" in first
