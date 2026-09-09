"""Intent tests for doctor's precedence lattice — written from `docs/DOCTOR.md` §3/§4, not the code.

The lattice is the one derivation behind three surfaces (doctor's combined report, the per-command
signpost, the ordered-remediation section). Every repair in
`docs/CORRECTNESS_REPAIRS_2026-09-08.md` turned out to be an instance of the same failure — a second
reader of the same facts drifting from the first — so this one exists to be CONSUMED, and these
tests pin the contract that makes consuming it safe.

The paired generated suite is a characterization: it pins what the code does. This pins what it is
FOR, which is the only thing that can catch a wrong implementation pinned wrong.
"""

from __future__ import annotations

import pytest

from Detective.doctor import COMMAND_HERB, HERBS, signpost_disposition

# ------------------------------------------------------------------ the load-bearing rule


@pytest.mark.parametrize("herb", HERBS)
def test_a_command_is_never_preempted_by_its_own_axis(herb) -> None:
    """A red command with a red finding IS the process statement — that is what it exists to say.
    Pre-empting it would silence the command in exactly the case it was built for.

    This is why the parameter is the command's HERB and not "is any finding live": the question is
    ranking, and own-axis is not a higher rank.
    """
    only_own = {"green": (True, False, False), "red": (False, True, False), "yellow": (False, False, True)}[
        herb
    ]
    assert not signpost_disposition(herb, *only_own).startswith("preempted")


def test_green_is_preempted_by_nothing() -> None:
    """Green is the top of the ranking, so no finding can outrank it. It may still gain a NOTE."""
    for red, yellow in ((False, False), (True, False), (False, True), (True, True)):
        assert not signpost_disposition("green", True, red, yellow).startswith("preempted")


# ------------------------------------------------------------------ the mix that motivated this


def test_a_setup_fault_preempts_a_process_verdict_which_is_the_converge_spiral() -> None:
    """G+R, the general form of the observed spiral: converge (red) emitted "author these inputs"
    while a green fault — funcy absent from THIS interpreter — was live and pre-emptive. The inputs
    could never have helped, so following the instruction moved the operator away from the fix.
    Neither axis alone catches it; that is the argument for the mix being the default."""
    assert signpost_disposition("red", True, False, False) == "preempted_by_setup"
    assert signpost_disposition("red", True, True, True) == "preempted_by_setup"


def test_a_taste_command_waits_for_both_halves_above_it() -> None:
    """R+Y is the ORDERING product: running the taste half before behaviour is pinned. G+Y is
    UNRELIABILITY: a taste finding measured through a broken environment must be re-derived after
    the fix, not acted on."""
    assert signpost_disposition("yellow", False, True, False) == "preempted_by_process"
    assert signpost_disposition("yellow", True, False, False) == "preempted_by_setup"


def test_setup_outranks_process_when_both_are_live() -> None:
    """The precedence is total, not a tie. A yellow command under both findings must be sent to the
    green one FIRST — fixing the process issue while the environment is broken re-derives a finding
    that was measured through the fault."""
    assert signpost_disposition("yellow", True, True, False) == "preempted_by_setup"


# ------------------------------------------------------------------ emit vs emit_with_note


def test_a_clean_run_gains_no_line() -> None:
    """The signpost discipline: never on a clean run. A line that always appears is a line nobody
    reads — Finding A's failure mode, where `decompose` sat marked `Next (optional)` and a
    greenfield user skipped it every time."""
    assert signpost_disposition("green", False, False, False) == "emit"
    assert signpost_disposition("red", False, False, False) == "emit"
    assert signpost_disposition("yellow", False, False, False) == "emit"


def test_a_lower_ranked_finding_is_named_without_silencing_the_verdict() -> None:
    """`emit_with_note` is a different fact from `emit` — the difference is a visible line — and a
    different fact from the pre-emptions, because the verdict is still VALID: it was not measured
    through the finding. Collapsing it into either would either hide a live finding or suppress a
    sound verdict."""
    assert signpost_disposition("green", False, True, False) == "emit_with_note"
    assert signpost_disposition("green", False, False, True) == "emit_with_note"
    assert signpost_disposition("red", False, False, True) == "emit_with_note"


def test_a_yellow_command_has_nothing_below_it_to_note() -> None:
    """Yellow is the bottom of the ranking, so a yellow command that is not pre-empted has no
    lower-ranked finding by construction. `emit_with_note` here would be unreachable — and an
    unreachable state in a named-code vocabulary is a state that means nothing."""
    for green, red in ((False, False),):
        assert signpost_disposition("yellow", green, red, True) == "emit"


# ------------------------------------------------------------------ the vocabulary boundary


def test_an_undeclared_command_is_named_never_admitted_by_fallthrough() -> None:
    """A command whose herb nobody declared must not silently acquire permission to speak. Same
    rule `controller.admission_reason` applies with `status_unknown`, and the same reason: a
    fall-through grants the strongest outcome to the least understood input."""
    assert signpost_disposition("", True, True, True) == "unknown_herb"
    assert signpost_disposition("purple", False, False, False) == "unknown_herb"
    assert signpost_disposition("GREEN", False, False, False) == "unknown_herb", "codes are exact"


def test_every_declared_command_maps_to_a_real_herb() -> None:
    """`COMMAND_HERB` is what makes the signpost trigger DERIVED rather than a heuristic (§4). A
    verb mapped to a herb outside the vocabulary would route to `unknown_herb` at runtime and read
    as a missing declaration rather than a typo."""
    assert set(COMMAND_HERB.values()) <= set(HERBS)
    for verb, herb in COMMAND_HERB.items():
        assert signpost_disposition(herb, False, False, False) == "emit", verb


def test_the_commands_that_gate_correctness_are_red_and_the_taste_half_is_yellow() -> None:
    """The assignment is the design, not bookkeeping: `converge`/`audit` gate behaviour, so they are
    process; `plan`/`survey`/`decompose` are the taste half, so they wait on it; `regime` answers
    'can a verdict here even be trusted', which is setup."""
    assert COMMAND_HERB["regime"] == "green"
    for verb in ("converge", "audit", "diagnose", "receipt", "verify-rewrite"):
        assert COMMAND_HERB[verb] == "red", verb
    for verb in ("plan", "survey", "extract", "decompose", "parsimony", "censor"):
        assert COMMAND_HERB[verb] == "yellow", verb
