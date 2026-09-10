"""Intent tests for the per-command signpost (`docs/DOCTOR.md` §4).

A repair system that is not obvious in turn-by-turn output is pointless. The user in the failure
state is BY DEFINITION the one who does not know what is wrong, so they never think to run the
diagnostic — this is Finding A's failure mode generalised, where `decompose` existed all along
marked `Next (optional)` and a greenfield user skipped it every time, as did the founder.

Doctor is MORE exposed to that than decompose was, because nothing about a taste report tells you
its premise might be broken.
"""

from __future__ import annotations

import json

import pytest

from Detective.cli import main
from Detective.doctor import COMMAND_HERB, command_setup_fault

# The fixture's broken environment has to be broken BY CONSTRUCTION. This file previously used
# `import jax`, which quietly made its premise "jax is not installed in whichever interpreter runs
# pytest" — true in the project venv, false anywhere else, and written down nowhere.
#
# Measured 2026-09-09: eight tests in this file passed under `.venv` (3.11) and failed under a
# miniconda 3.11+ carrying jax 0.11.1, because `needs.py` then imported cleanly, no fault existed,
# and the signpost was correct to stay silent. The suite was not wrong about the code — it was
# asserting over a subspace of interpreters without recording that it was a subspace. Which is the
# doctor's own thesis (a true reading against a stale model of the environment) landing on the
# doctor's own tests.
#
# A name no index can serve is a premise no environment can falsify. Same sentinel already used by
# `test_doctor_taste_intent` and `test_doctor_verb_intent`; this conforms to that, rather than
# inventing a third spelling.
_ABSENT = "definitely_not_a_real_package_xyz"

_TRAPPED = f"import {_ABSENT}\n\n\ndef f(x):\n    if x <= 0:\n        return 0\n    return x * 2\n"
_CLEAN = "def add(a, b):\n    if a > b:\n        return a\n    return b\n"


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "clean.py").write_text(_CLEAN)
    (tmp_path / "needs.py").write_text(_TRAPPED)
    return tmp_path


def _run(capsys, *args) -> tuple[int, str]:
    code = main(list(args))
    return code, capsys.readouterr().out


# ---------------------------------------------------------------- the cheap green read


def test_the_free_read_is_a_DIFFERENT_decision_from_the_full_one() -> None:
    """`setup_disposition` with empty probe arguments would return `stale_load_failure` for a load
    failure the CURRENT run just hit — "a prior run recorded this, it may be stale" is the opposite
    of the truth there. Two questions that differ in TENSE are two decisions; collapsing them puts
    the wrong remedy under the right code, which is S13 one layer out."""
    assert command_setup_fault("", True, False) == "target_load_failed"
    assert command_setup_fault("", False, True) == "collection_incomplete"
    assert command_setup_fault("", False, False) == "none"


def test_a_regime_conflict_outranks_a_single_targets_failure() -> None:
    """Same order as `setup_disposition`, same reason: a regime conflict makes EVERY verdict from
    the repo untrustworthy, so it outranks a fault in one target's measurement."""
    assert command_setup_fault("shadowed-target", True, True) == "regime_conflict"


# ---------------------------------------------------------------- when it fires


def test_it_fires_on_a_taste_command_whose_environment_is_broken(repo, capsys) -> None:
    """§3's G+Y product, delivered where it is actually needed. `_run_live` already resolves the
    regime and refuses, and R1/R3 already route a load failure — so the LIVE commands hold their own
    green awareness. The static taste verbs never resolve the regime at all, and emit advice with no
    way of knowing the environment makes it meaningless."""
    _, out = _run(capsys, "survey", "needs.py", "--project-root", str(repo))
    assert "SETUP FAULT" in out
    assert "outranks this yellow verdict" in out


def test_it_names_the_finding_rather_than_just_the_command(repo, capsys) -> None:
    """§4, verbatim: "Run `detective doctor`" is as useless as "Next (optional)". It must say what
    doctor will tell them — the finding is the content, the command is the follow-up."""
    _, out = _run(capsys, "survey", "needs.py", "--project-root", str(repo))
    assert _ABSENT in out, "the missing module is NAMED"
    assert "detective doctor" in out, "…and the full read is offered"
    assert out.index(_ABSENT) < out.index("detective doctor"), "finding first, command second"


def test_it_says_WHY_the_verdict_was_withheld_not_merely_that_it_was(repo, capsys) -> None:
    """A refusal that does not explain itself is the same defect as advice that cannot be acted on.
    The reader has to learn that the read would have measured their ENVIRONMENT rather than their
    code — otherwise "withheld" reads as the tool being broken, which is exactly the conclusion a
    greenfield user draws (U2, the motivating case).

    Reworded when D1 landed: the previous form asserted "RE-DERIVE this read", which described a
    report that no longer arrives."""
    _, out = _run(capsys, "survey", "needs.py", "--project-root", str(repo))
    assert "measured THROUGH" in out
    assert "your ENVIRONMENT rather than of your" in out
    assert "fix the setup, then run this command again" in out


@pytest.mark.parametrize("verb", ["survey", "plan", "parsimony", "censor"])
def test_every_static_taste_verb_gets_it_from_one_site(verb, repo, capsys) -> None:
    """One pre-dispatch site so five verbs cannot drift apart. A per-handler signpost is how you get
    four that fire and one that quietly does not."""
    _, out = _run(capsys, verb, "needs.py", "--project-root", str(repo))
    assert "SETUP FAULT" in out, f"{verb} emitted taste advice with no signpost"


def test_every_verb_it_fires_for_is_declared_yellow() -> None:
    """The trigger is DERIVED from `COMMAND_HERB`, not a hand-kept list of verbs (§4). A verb in the
    dispatch list that is not yellow would be pre-empted by the wrong rank."""
    for verb in ("plan", "survey", "extract", "parsimony", "censor"):
        assert COMMAND_HERB[verb] == "yellow", verb


# ---------------------------------------------------------------- when it must NOT fire


def test_a_RECORDED_fault_fires_the_signpost_too(repo, capsys) -> None:
    """REGRESSION, and it is the second time this exact shape has bitten in one session.

    The branch that formats a NAMED fault (`regime_conflict`, `target_load_failed`) referenced an
    undefined `CUT_REASONS`. Inside the helper's own catch-all, that degraded to SILENCE — so the
    signpost simply never fired for a recorded failure or a regime conflict, and the only path the
    tests exercised was the dependency one, which does not touch that code.

    Found by ruff/ty/pylint all three naming the undefined symbol, not by the suite. A guard that
    swallows its own failure needs a test per BRANCH, because the failure mode is indistinguishable
    from the healthy one — which is exactly what `_skip_if_cache_bypassed` (S10) was written to stop
    happening elsewhere.
    """
    d = repo / "tests" / "detective"
    d.mkdir(parents=True, exist_ok=True)
    (d / "certificates.json").write_text(
        json.dumps({"clean.py::add": {"cut_reasons": ["target_load_failed"]}})
    )
    _, out = _run(capsys, "survey", "clean.py", "--project-root", str(repo))
    assert "SETUP FAULT" in out
    assert "target_load_failed" in out, "the recorded reason is named"
    assert "could not be imported" in out, "…with its own sentence, from the one owner"


def test_it_is_silent_on_a_clean_run(repo, capsys) -> None:
    """The signpost discipline: never on a clean run. A line that always appears is a line nobody
    reads, which is the defect it exists to repair rather than an acceptable cost of repairing it."""
    _, out = _run(capsys, "survey", "clean.py", "--project-root", str(repo))
    assert "SETUP FAULT" not in out


def test_it_is_silent_on_the_machine_channel(repo, capsys) -> None:
    """`--json` is a parsed contract. A human-readable banner printed ahead of it would corrupt the
    document — and a machine consumer gets its green facts from `detective doctor`, which has its
    own structured surface, rather than from prose smuggled into another verb's stdout."""
    _, out = _run(capsys, "survey", "needs.py", "--project-root", str(repo), "--json")
    assert "SETUP FAULT" not in out
    json.loads(out)


def test_it_never_breaks_the_command_it_decorates(tmp_path, capsys) -> None:
    """Advisory about an advisory surface. A signpost that raises has cost a verdict to deliver a
    hint, which is a strictly worse trade than staying quiet — so every failure mode degrades to
    silence."""
    (tmp_path / "broken.py").write_text("def broken(:\n")
    code, out = _run(capsys, "survey", "broken.py", "--project-root", str(tmp_path))
    assert code in (0, 1, 2)
    (tmp_path / "gone").mkdir()
    code, _ = _run(capsys, "survey", "gone", "--project-root", str(tmp_path))
    assert code in (0, 1, 2)


def test_a_preempted_command_WITHHOLDS_its_verdict(repo, capsys) -> None:
    """FOUNDER RULING 2026-09-09 — §4's literal reading, and it reverses what was built first.

    A taste verdict measured THROUGH a live setup fault is a measurement of the ENVIRONMENT. Printing
    it under a warning still leaves the reader free to act on it, which is the unreliability the mix
    exists to NAME rather than decorate. So the report does not arrive at all.

    Exit 2 — the documented "your world is wrong — fix that, not the code" — and the same code
    `doctor` returns for the same finding, so a caller branching on it gets ONE answer from both.
    """
    code, out = _run(capsys, "survey", "needs.py", "--project-root", str(repo))
    assert "SETUP FAULT" in out
    assert "Why withheld" in out
    assert "survey ·" not in out, "the verdict must be WITHHELD, not merely preceded"
    assert code == 2


def test_a_clean_run_still_gets_its_report(repo, capsys) -> None:
    """The other half, and the one that makes withholding safe to ship: nothing is suppressed unless
    a green finding is actually live."""
    code, out = _run(capsys, "survey", "clean.py", "--project-root", str(repo))
    assert "SETUP FAULT" not in out
    assert "survey ·" in out
    assert code == 0


def test_the_machine_channel_is_never_withheld(repo, capsys) -> None:
    """`--json` is a parsed contract. A consumer gets its green facts from `detective doctor`'s
    structured surface, not from a verb silently returning a different shape — so the exemption is
    the same one that keeps the banner off this channel."""
    code, out = _run(capsys, "survey", "needs.py", "--project-root", str(repo), "--json")
    payload = json.loads(out)
    assert payload["kind"] == "survey", "the document still arrives, intact"
    assert code != 2
