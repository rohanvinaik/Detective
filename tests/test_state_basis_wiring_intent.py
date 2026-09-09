"""Intent tests for the digest-basis escalation, WIRED (`docs/INVOCATION_LEDGER.md` §8.1).

The defect these were written against, found 2026-09-09 by asking a question nobody had posed —
"is every pinned pure decision consumed in production?":

    `state_basis` was ✓ COMPLETE 11/11, exported, documented and tested, and had ZERO production
    callers. `"escalate_exact"` appeared nowhere in `Detective/` outside its own definition and
    docstring, and `suite_digest(exact=True)` was never called outside tests. The founder's ruling
    — "cheap with fallback triggered when the situation knowably calls for it" — was half landed:
    the decision existed, the consumer knob existed, and the wire between them did not.

    Driven proof of what that cost, before the repair: three identical `survey` runs produced
    `RED — process  spiral`; a `touch` that moved ZERO bytes (sha identical before and after) made
    the finding vanish. Exactly what `state_basis`'s own docstring predicts — "this is exactly where
    a repeat that changed NOTHING gets excused as normal work."

Why the doc's status line did not catch it: it said "Built: … `state_basis` …", which was true. It
never distinguished *the decision exists* from *the escalation happens* — the project's own "two
conditions that mean different things must not collapse into one truthy check", applied to a status
vocabulary instead of to code.
"""

from __future__ import annotations

import pytest

from Detective.cli import _escalate_suite_digest
from Detective.doctor import red_facts, same_recorded_state
from Detective.ledger import append, suite_digest, suite_state_comparison


@pytest.fixture
def repo(tmp_path):
    d = tmp_path / "tests" / "detective"
    d.mkdir(parents=True)
    (d / "t_synth.py").write_text("def test_a():\n    assert True\n")
    return tmp_path


def _write_dir(root):
    return str(root / "tests" / "detective")


# ------------------------------------------------------- the decision: four facts, not two


def test_the_four_codes_carry_their_BASIS_not_just_their_verdict() -> None:
    """ "The content is unchanged" and "the stat-walk agreed and nobody looked further" are
    different claims. A caller that cannot tell them apart cannot report honestly about either."""
    assert suite_state_comparison(False, True, True) == "unchanged_exact"
    assert suite_state_comparison(False, True, False) == "changed_exact"
    assert suite_state_comparison(True, False, False) == "unchanged_cheap"
    assert suite_state_comparison(False, False, False) == "unknown"


def test_unknown_is_its_own_state_and_never_borrows_another() -> None:
    """The load-bearing one. `unknown` means the cheap digests differ and there is no exact pair to
    check — a touch, a checkout, a copy and a real edit ALL land here. Rendering it as either answer
    is the unknown-versus-established collapse this project exists to police."""
    verdict = suite_state_comparison(False, False, False)
    assert verdict == "unknown"
    assert verdict not in ("unchanged_exact", "unchanged_cheap", "changed_exact")


def test_exact_evidence_outranks_cheap_wherever_both_exist() -> None:
    """§8.1's KNOWN LIMIT — content changed while the mtime was RESTORED — is not reachable from
    the current write side, which is exactly why it is decided here rather than left to fall
    through. A later write-side change must not be able to acquire a wrong answer for free."""
    assert suite_state_comparison(True, True, False) == "changed_exact"


# ------------------------------------------------------- the adapter: no manufactured changes


def test_the_PRESENCE_of_an_escalated_field_is_not_a_state_change() -> None:
    """The hazard that ruled out plain `a == b`. One record escalated and carries `suite_exact`;
    the other did not and carries no such key. Dict equality reads that as the state having moved —
    a change manufactured by the measurement, which is the failure this axis exists to name."""
    escalated = {"target_src": "x", "suite": "s", "suite_exact": "e"}
    plain = {"target_src": "x", "suite": "s"}
    assert escalated != plain, "the precondition: plain dict equality would say CHANGED"
    assert same_recorded_state(escalated, plain) is True


def test_a_non_suite_field_still_decides_on_its_own() -> None:
    """Every other field is a content digest. Only `suite` has two possible bases, so only `suite`
    needs a decision — a source edit must still read as a state change."""
    assert same_recorded_state({"suite": "s", "target_src": "x"}, {"suite": "s", "target_src": "y"}) is False


def test_an_unknown_suite_state_stays_QUIET_rather_than_accusing() -> None:
    """The safe direction §7.1 named, held after the repair. A false spiral accusation is the worse
    error of the two, so a state nobody can establish must not produce one."""
    assert same_recorded_state({"suite": "a"}, {"suite": "b"}) is False


def test_a_proven_identical_suite_reads_as_unchanged_despite_the_cheap_digest() -> None:
    """The whole point of buying the read."""
    assert same_recorded_state({"suite": "a", "suite_exact": "e"}, {"suite": "b", "suite_exact": "e"}) is True


# ------------------------------------------------------- the write side: who pays


def test_a_first_run_never_pays(repo) -> None:
    """ "The healthy path never pays" is §8.1's own property, and it is the reason the ruling beat
    both options the section offered. It has to be pinned or it erodes."""
    state = {"suite": suite_digest(_write_dir(repo))}
    _escalate_suite_digest(str(repo), _write_dir(repo), "survey", "m.py", {}, state)
    assert "suite_exact" not in state


def test_an_unchanged_repeat_never_pays(repo) -> None:
    cheap = suite_digest(_write_dir(repo))
    append(str(repo), {"v": 1, "verb": "survey", "target": "m.py", "args": {}, "state": {"suite": cheap}})
    state = {"suite": cheap}
    _escalate_suite_digest(str(repo), _write_dir(repo), "survey", "m.py", {}, state)
    assert "suite_exact" not in state


def test_a_PROGRESSED_run_never_pays(repo) -> None:
    """Different arguments make the state question moot — it is a different question, not a repeat."""
    append(
        str(repo),
        {"v": 1, "verb": "survey", "target": "m.py", "args": {"a": 1}, "state": {"suite": "stale"}},
    )
    state = {"suite": suite_digest(_write_dir(repo))}
    _escalate_suite_digest(str(repo), _write_dir(repo), "survey", "m.py", {"a": 2}, state)
    assert "suite_exact" not in state


def test_the_ONE_case_that_pays_is_the_one_the_ruling_named(repo) -> None:
    """A same-args repeat whose cheap digest moved. Nothing else buys the read."""
    append(
        str(repo),
        {"v": 1, "verb": "survey", "target": "m.py", "args": {}, "state": {"suite": "moved"}},
    )
    state = {"suite": suite_digest(_write_dir(repo))}
    _escalate_suite_digest(str(repo), _write_dir(repo), "survey", "m.py", {}, state)
    assert state["suite_exact"], "the ruled case must buy the exact digest"
    assert state["suite_exact"] != state["suite"], "two different bases, not the same value twice"


def test_a_different_target_is_a_different_question(repo) -> None:
    """Same scoping red_facts uses. Mixing targets would manufacture repeats out of ordinary work
    across a codebase — the false-positive direction, which is the worse one."""
    append(
        str(repo),
        {"v": 1, "verb": "survey", "target": "other.py", "args": {}, "state": {"suite": "moved"}},
    )
    state = {"suite": suite_digest(_write_dir(repo))}
    _escalate_suite_digest(str(repo), _write_dir(repo), "survey", "m.py", {}, state)
    assert "suite_exact" not in state


def test_the_enrichment_never_costs_the_record(repo) -> None:
    """§2.1 applied one level down: the caller's own guard would have swallowed the whole append, so
    this one is separate. A ledger that cannot be read must cost the FIELD, not the invocation."""
    state = {"suite": "s"}
    _escalate_suite_digest(str(repo / "does" / "not" / "exist"), "/nope", "survey", "m.py", {}, state)
    assert state == {"suite": "s"}, "no exception, and no invented field"


# ------------------------------------------------------- end to end, through red


def test_a_REPEATED_perturbation_is_now_caught(repo) -> None:
    """The acceptance case. Same-args repeats whose suite mtime moves each time but whose bytes
    never do — a CI checkout every run, a `git stash` loop. Before the wiring red went silent here;
    the exact pair is what lets it speak.

    FOUR records, and the count is the LAG made concrete rather than a fixture detail. The first run
    of a series has no prior and so buys nothing, which leaves it uncomparable on the exact basis;
    `spiral` needs two comparable pairs after it, where an unperturbed series needs only two repeats.
    Paying one extra invocation is the cost of the ruled option, which in exchange never taxes a
    healthy repeat."""
    cheap_moves = ["c1", "c2", "c3", "c4"]
    for i, cheap in enumerate(cheap_moves):
        state = {"suite": cheap}
        _escalate_suite_digest(str(repo), _write_dir(repo), "survey", "m.py", {}, state)
        append(str(repo), {"v": 1, "verb": "survey", "target": "m.py", "args": {}, "state": state})
        assert ("suite_exact" in state) is (i > 0), "the first of a run of repeats establishes it"
    assert red_facts(str(repo))["spiral"] == "spiral"


def test_a_ONE_OFF_perturbation_still_stays_quiet(repo) -> None:
    """Stated in the decision's docstring rather than discovered later: an exact pair needs BOTH
    records to have escalated, so a single mtime event yields `unknown` and stays quiet. That is the
    price of the option that never taxes a healthy repeat, and it is the safe direction."""
    for cheap in ("c1", "c1", "c1", "c2"):
        state = {"suite": cheap}
        _escalate_suite_digest(str(repo), _write_dir(repo), "survey", "m.py", {}, state)
        append(str(repo), {"v": 1, "verb": "survey", "target": "m.py", "args": {}, "state": state})
    assert red_facts(str(repo))["spiral"] != "spiral"


def test_plain_identical_repeats_are_UNAFFECTED_by_the_repair(repo) -> None:
    """The non-regression that matters most: the cheap basis is conclusive when it says UNCHANGED,
    so the ordinary spiral must still fire without anyone buying a read."""
    for _ in range(3):
        state = {"suite": "same"}
        _escalate_suite_digest(str(repo), _write_dir(repo), "survey", "m.py", {}, state)
        append(str(repo), {"v": 1, "verb": "survey", "target": "m.py", "args": {}, "state": state})
        assert "suite_exact" not in state, "an unchanged repeat must not pay"
    assert red_facts(str(repo))["spiral"] == "spiral"


def test_a_genuine_edit_is_never_reported_as_a_spiral(repo) -> None:
    """An edit-then-rerun loop IS how the tool is used. The repair must not turn ordinary work into
    an accusation."""
    for cheap in ("c1", "c2", "c3"):
        state = {"suite": cheap, "target_src": cheap}
        _escalate_suite_digest(str(repo), _write_dir(repo), "converge", "m.py::f", {}, state)
        append(str(repo), {"v": 1, "verb": "converge", "target": "m.py::f", "args": {}, "state": state})
    assert red_facts(str(repo))["spiral"] != "spiral"
