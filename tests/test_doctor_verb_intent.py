"""Intent tests for the `detective doctor` verb (`docs/DOCTOR.md` §1, §3, §6).

Through `main()`, the way a user gets it — not by poking the handler, which is the failure mode the
project records as "poking an internal on a half-built target produces findings that evaporate
under the actual entry point".

What these pin is mostly THE FENCE, because the fence is the part that will erode. Doctor is the
command a confused user runs, so whatever it says will be believed; the moment it emits anything
that reads as a correctness verdict it has inherited the measurement/verdict conflation the project
exists to kill.
"""

from __future__ import annotations

import json
import os

import pytest

from Detective.cli import _STATIC_COMMANDS, main

_CLEAN = "def add(a, b):\n    return a + b\n"
_NEEDS_DEPS = "import funcy\nimport definitely_not_a_real_package_xyz\n\n\ndef f(x):\n    return x\n"


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "m.py").write_text(_CLEAN)
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_m.py").write_text(
        "from m import add\n\n\ndef test_add():\n    assert add(1, 1) == 2\n"
    )
    return tmp_path


def _run(capsys, *args) -> tuple[int, str]:
    code = main(["doctor", *args])
    return code, capsys.readouterr().out


def _ledger(root, entries: dict) -> None:
    """Write a certificate ledger where the real reader looks — beside the suite, not under
    `.detective/`, which is where §14.1 deliberately moved it so a synth and its certificate travel
    together."""
    d = root / "tests" / "detective"
    d.mkdir(parents=True, exist_ok=True)
    (d / "certificates.json").write_text(json.dumps(entries))


# ---------------------------------------------------------------- the verb exists and is static


def test_doctor_is_a_static_command_so_it_never_opens_a_live_session() -> None:
    """§1: cheap. It does not run the target's suite, does not profile mutants, does not import the
    target. `_STATIC_COMMANDS` is the one named set that keeps `_run`'s pre-split dispatch and
    `_run_live`'s session bypass from drifting as verbs are added."""
    assert "doctor" in _STATIC_COMMANDS


def test_it_runs_with_no_target_at_all(repo, capsys) -> None:
    """Repo-scoped is a real mode: "why can I not proceed" is askable before you have a target."""
    code, out = _run(capsys, "--project-root", str(repo))
    assert code == 0
    assert "detective doctor" in out


# ---------------------------------------------------------------- the exit contract


def test_a_clean_read_exits_zero(repo, capsys) -> None:
    code, out = _run(capsys, "--project-root", str(repo))
    assert code == 0
    assert "exit 0" in out


def test_a_live_setup_fault_exits_2_because_your_world_is_wrong(repo, capsys) -> None:
    """Reversing DOCTOR.md §7.2's lean, on the README's own rule: "exit codes are epistemics, not
    pass/fail", and the documented `2 = your world is wrong — fix that, not the code` IS a setup
    fault. Always-0 would make doctor report nothing wrong about a fault it just found."""
    (repo / "needs.py").write_text(_NEEDS_DEPS)
    code, out = _run(capsys, "needs.py", "--project-root", str(repo))
    assert code == 2
    assert "exit 2" in out


def test_it_still_never_gates_a_certificate() -> None:
    """The fence survives the exit code: doctor is not in the completeness chain. If it ever appears
    in the behaviour-status vocabulary or the admission ladder, that is the fence breaking."""
    from Detective import pins
    from Detective.plan import _STATUS_REASONS

    assert "doctor" not in pins.BEHAVIOR_STATUSES
    assert "doctor" not in _STATUS_REASONS


# ---------------------------------------------------------------- the motivating case


def test_the_propagation_case_names_BOTH_interpreters(repo, capsys) -> None:
    """The whole reason doctor exists. A package missing HERE and present THERE is not an install
    problem, and a report that names only the absence sends the operator to install it again —
    away from the fix. The value is in the two paths appearing together."""
    (repo / "needs.py").write_text("import json\nimport definitely_not_a_real_package_xyz\n")
    code, out = _run(capsys, "needs.py", "--project-root", str(repo))
    assert code == 2
    assert "definitely_not_a_real_package_xyz" in out
    assert "This run uses" in out, "the interpreter that cannot see it must be named"


def test_a_package_nobody_has_is_an_install_not_a_propagation(repo, capsys) -> None:
    """The two remedies must not collapse. Sending someone to 'find your other interpreter' when
    the package genuinely does not exist is the same class of wrong advice in the other direction."""
    (repo / "needs.py").write_text("import definitely_not_a_real_package_xyz\n")
    _, out = _run(capsys, "needs.py", "--project-root", str(repo))
    assert "Not found under any interpreter" in out
    assert "PROPAGATION problem" not in out


# ---------------------------------------------------------------- not-read is a REPORTED state


def test_an_unbuilt_axis_says_so_rather_than_rendering_an_empty_section(repo, capsys) -> None:
    """The hard requirement, and it is the project's whole thesis applied to doctor itself:
    swallowing at WRITE time is right, swallowing at READ time is what this exists to prevent. An
    empty process section reads as "nothing wrong", which is the one thing it must not say."""
    _, out = _run(capsys, "--project-root", str(repo))
    assert "RED — process" in out and "not read" in out
    assert "UNAVAILABLE" in out
    assert "YELLOW — taste" in out


def test_a_partial_read_carries_a_banner_saying_it_is_partial(repo, capsys) -> None:
    """§3: `--green` alone is runnable for scoping and must say that an unread axis may invalidate
    what it reports. The full mix is the default because making the operator discover the right
    combination is a puzzle, and a puzzle in a diagnostic tool is the spiral this project bans."""
    _, out = _run(capsys, "--project-root", str(repo), "--green")
    assert "PARTIAL READ" in out
    _, full = _run(capsys, "--project-root", str(repo))
    assert "PARTIAL READ" not in full, "the default mix is not partial"


# ---------------------------------------------------------------- THE FENCE


def test_it_never_emits_a_correctness_verdict(repo, capsys) -> None:
    """§1, the load-bearing constraint. Doctor must never say anything that reads as a claim about
    the CODE — it will be believed, because it is the command a confused user runs, and a
    correctness claim from an advisory surface is the conflation the project exists to kill.

    The forbidden set is VERDICT PHRASINGS, not measurement vocabulary, and the distinction is not
    pedantry — it is the difference between a guard and a false alarm. Doctor legitimately quotes
    `cut_reason_sentence`, and `target_load_failed`'s sentence contains the word "mutant". A test
    banning that word passes on a clean repo (where the branch is unreachable) and fires wrongly the
    moment a real user hits the stale case: agreement over a subspace, which is the exact failure
    §MI, the #60 MCP drift and S10 all turned out to be.
    """
    outs = [_run(capsys, "--project-root", str(repo))[1]]
    _ledger(repo, {"m.py::add": {"cut_reasons": ["target_load_failed"]}})
    outs.append(_run(capsys, "m.py::add", "--project-root", str(repo))[1])
    for out in outs:
        lowered = out.lower()
        for forbidden in (
            "your code is fine",
            "every killable",
            "✓ complete",
            "behaviour is pinned",
            "the suite is complete",
        ):
            assert forbidden not in lowered, f"doctor spoke about the code: {forbidden!r}"


def test_a_recorded_failure_is_found_under_the_ledgers_own_key_form(repo, capsys) -> None:
    """REGRESSION. `_split_target` returns the file ALREADY relative to the project root — which is
    exactly the certificate ledger's key form — and the handler re-relativised it against the CWD,
    producing a `../../..` path that matched nothing. So the whole recorded-failure branch was
    UNREACHABLE and a ledger recording `target_load_failed` rendered `clean`.

    Every unit test passed while that was true, because none of them went near the branch. It was
    caught by driving the real command at it — "validate end-to-end through the real command, not by
    calling the internal function directly", which is the project's own recorded rule.
    """
    _ledger(repo, {"m.py::add": {"standing": "ungateable", "cut_reasons": ["target_load_failed"]}})
    code, out = _run(capsys, "m.py::add", "--project-root", str(repo), "--green")
    assert code == 2
    assert "stale_load_failure" in out
    assert "target_load_failed" in out, "the recorded reason is NAMED, not merely counted"


def test_a_ledger_entry_for_a_DIFFERENT_target_does_not_leak_into_this_ones_read(repo, capsys) -> None:
    """The scoping half of the same bug. A key that matches nothing and a key that matches the wrong
    thing are both wrong; the first was the defect, and this pins that fixing it did not overshoot
    into reporting every target's failures against whichever one you asked about."""
    _ledger(repo, {"other.py::g": {"cut_reasons": ["target_load_failed"]}})
    code, out = _run(capsys, "m.py::add", "--project-root", str(repo), "--green")
    assert code == 0
    assert "stale_load_failure" not in out


def test_a_clean_read_refuses_to_be_a_certificate(repo, capsys) -> None:
    """ "No damage in what was looked at" and "your setup is correct" are different claims, and only
    the first is true. The disclaimer is not politeness — it is the difference between a report and
    a guarantee."""
    _, out = _run(capsys, "--project-root", str(repo))
    assert "not a certificate" in out


def test_it_writes_nothing_to_the_project_it_is_diagnosing(repo, capsys) -> None:
    """Advisory, same class as plan/survey/parsimony/censor: a diagnostic that mutates the project
    it is diagnosing cannot be run safely by someone who does not yet understand the tool.

    NARROWED 2026-09-09, and the narrowing is the finding rather than a relaxation. This asserted
    whole-tree mtime equality, which was a PROXY for the intent above — and it agreed with that
    intent only over the subspace where the invocation ledger did not exist. `main` now records
    every invocation, doctor's included, so the proxy started catching something the intent never
    meant.

    "Writes nothing" is about the PROJECT — your source, your suite, Detective's own artifacts.
    The invocation ledger is a different category: it is the operator's record of having used the
    tool, not a change to what the tool is looking at. Every advisory verb writes it now, and
    doctor must be no exception — "you ran doctor five times" is precisely a process fact, and
    excluding one verb would put a hole in exactly the axis being built to read it.

    So both halves are pinned: nothing in the project moves, and the ledger DOES.
    """

    def _project_files():
        return {
            f: f.stat().st_mtime_ns for f in repo.rglob("*") if f.is_file() and ".detective" not in f.parts
        }

    before = _project_files()
    _run(capsys, "--project-root", str(repo))
    assert _project_files() == before, "doctor wrote to the project it was diagnosing"
    assert not (repo / "tests" / "detective").exists(), "no synths, no certificates"
    assert (repo / ".detective" / "ledger.jsonl").is_file(), "the invocation IS recorded"


def test_it_survives_a_project_that_is_barely_a_project(tmp_path, capsys) -> None:
    """Doctor is what you reach for when things are already broken, so the empty/hostile case is the
    NORMAL case rather than an edge. It must not raise on the way to explaining a failure."""
    code, out = _run(capsys, "--project-root", str(tmp_path))
    assert code in (0, 2)
    assert "detective doctor" in out
    code, out = _run(capsys, "no_such_file.py", "--project-root", str(tmp_path))
    assert code in (0, 2)


def test_a_target_that_will_not_parse_does_not_stop_the_read(repo, capsys) -> None:
    (repo / "broken.py").write_text("def broken(:\n")
    code, out = _run(capsys, "broken.py", "--project-root", str(repo))
    assert code in (0, 2)
    assert "GREEN — setup" in out


def test_the_help_names_the_three_axes_by_their_herb(capsys) -> None:
    """Founder ruling 2026-09-09: the herbs ARE the vocabulary. See DOCTOR.md §2 for why the
    opacity is the feature — a self-describing `--process` invites a model to fire it by
    pattern-match, and a token that carries no meaning cannot lend borrowed meaning to a guess."""
    with pytest.raises(SystemExit):
        main(["doctor", "--help"])
    out = capsys.readouterr().out
    for flag in ("--green", "--red", "--yellow"):
        assert flag in out
    assert "SETUP" in out and "PROCESS" in out and "TASTE" in out


def test_the_target_may_be_a_bare_path_or_a_function(repo, capsys) -> None:
    """Dispatched ABOVE `_split_target` so a bare path does not fall into the separator menu the way
    a required `file::func` verb would."""
    a, _ = _run(capsys, "m.py", "--project-root", str(repo))
    b, _ = _run(capsys, "m.py::add", "--project-root", str(repo))
    assert a == 0 and b == 0
    assert not os.path.exists(os.path.join(str(repo), "tests", "detective"))
