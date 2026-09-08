"""The invocation ledger — what the operator did, so the PROCESS axis is decidable.

Design: `docs/INVOCATION_LEDGER.md`. Consumer: `docs/DOCTOR.md`'s red / process axis, which
cannot exist without a record of more than one run.

This module holds the pure decisions FIRST. They are pinned in isolation before the I/O shell
is added, because a decision converged after it is wired into a broadly-called path inflates its
covering set to suite scale (`feedback_converge_before_wiring`).

The ledger records FACTS. Every interpretation of those facts is one of the decisions below, so
the record stays readable by a consumer that is not doctor — the founder has named a second use
(inference over implicit patterns past the boundary of knowability), and a record that embedded
doctor's verdicts would have pre-empted it.
"""

from __future__ import annotations

__all__ = [
    "environment_drift_disposition",
    "order_disposition",
    "spiral_disposition",
]


def spiral_disposition(
    has_prior: bool,
    same_args: bool,
    same_state: bool,
    identical_repeats: int,
) -> str:
    """Did this invocation advance anything, or repeat one that could not (pure — pinned).

    The distinction the CLI cannot draw on its own: a re-run is the NORMAL shape of work, and a
    re-run that cannot change its own outcome is a spiral. Both look identical from inside a
    single run, which is why the process axis needs history rather than cleverness.

    Named codes, because these mean different things and a bool would collapse them:

      * ``no_prior``             — first invocation of this verb+target. Nothing to compare.
      * ``progressed``           — the operator changed the command. Not a finding.
      * ``repeat_state_changed`` — same command, but the source / suite / inputs / equivalents
                                   moved in between. This is ordinary iteration and MUST NOT be
                                   reported: an edit-then-rerun loop is how the tool is used.
      * ``repeat_no_change``     — same command, nothing changed. One repeat. Worth a note, not
                                   an alarm; an operator re-reading a verdict is legitimate.
      * ``spiral``               — two or more identical repeats over unchanged state. The
                                   operator is following an instruction that cannot change the
                                   state it describes. Observed 2026-09-08 on conorheins
                                   ``str2bool``: AUTHOR INPUTS re-emitted byte-identically after
                                   the inputs it asked for were supplied.

    ``identical_repeats`` counts CONSECUTIVE prior invocations matching on args AND state, so a
    spiral is a run of them rather than two that happened to coincide across a session.
    """
    if not has_prior:
        return "no_prior"
    if not same_args:
        return "progressed"
    if not same_state:
        return "repeat_state_changed"
    if identical_repeats >= 2:
        return "spiral"
    return "repeat_no_change"


def order_disposition(
    command_herb: str,
    target_ever_pinned: bool,
    target_has_prior_measurement: bool,
) -> str:
    """Is the taste half being run before the correctness half (pure — pinned).

    The style pass is CONDITIONAL on behaviour being pinned — a seam proposed over an unpinned
    function cannot be proven behaviour-preserving, and a static read taken through a broken
    measurement is reading the breakage. Green and red carry no ordering constraint of this kind,
    so they return ``ok`` unconditionally rather than being excluded by the caller (the decision
    owns its own domain; a caller that has to know which herbs to skip is a second place for the
    rule to drift).

      * ``ok``                       — no ordering finding.
      * ``taste_without_measurement`` — a yellow command on a target nothing has ever measured.
                                        The static read will run and mean less than it appears to.
      * ``taste_before_behaviour``    — measured, but never pinned. The seam is unprovable.
    """
    if command_herb != "yellow":
        return "ok"
    if not target_has_prior_measurement:
        return "taste_without_measurement"
    if not target_ever_pinned:
        return "taste_before_behaviour"
    return "ok"


def environment_drift_disposition(
    has_prior: bool,
    same_interpreter: bool,
    same_engine_paths: bool,
    same_version: bool,
) -> str:
    """Did the ground move between runs (pure — pinned).

    THE motivating case, observed live 2026-09-08: a dependency was installed and landed in a
    different interpreter than the one Detective runs under. The CLI's report — "No module named
    'funcy'" — was literally correct and its premise ("you do not have funcy") was false. Nothing
    inside a single run can see that; two runs can.

    Most-significant first, because these are not independent — a changed interpreter usually
    drags the engine paths with it, and reporting the consequence instead of the cause is how an
    operator ends up fixing the wrong thing:

      * ``interpreter_changed`` — a different python is running Detective than last time.
      * ``engine_changed``      — same interpreter, different Detective/Wesker resolved (the
                                  two-knob fact: PYTHONPATH moved, or an install shadowed a
                                  local checkout).
      * ``version_changed``     — same paths, different reported version.
      * ``stable`` / ``no_prior``
    """
    if not has_prior:
        return "no_prior"
    if not same_interpreter:
        return "interpreter_changed"
    if not same_engine_paths:
        return "engine_changed"
    if not same_version:
        return "version_changed"
    return "stable"
