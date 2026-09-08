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
    "observe",
    "order_disposition",
    "outcome_disposition",
    "reset_observations",
    "spiral_disposition",
    "take_observations",
]


def outcome_disposition(
    matching_count: int,
    other_count: int,
    matching_are_identical: bool,
) -> str:
    """Which recorded outcome, if any, is THIS invocation's (pure — pinned).

    One process can record more than one next-action code: `decompose` converges its target
    first, so a `decompose` run observes a converge outcome too. Writing "the last code wins"
    into the collector would bury that choice where nothing can pin it, and would silently
    attribute a nested command's verdict to the one the operator actually ran.

    The caller partitions what it gathered — codes recorded BY the invoked verb, and codes
    recorded by anything else — and this decides what that partition warrants. The code itself
    is the caller's to read; this returns only the disposition, so a decision and a payload never
    travel as one value.

      * ``unobserved``    — nothing recorded. The verb has no routing decision (``purge``), or it
                            refused before reaching one. NOT an error, and not ``stable``-shaped:
                            an absent observation must never read as a benign one.
      * ``authoritative`` — the invoked verb recorded exactly one distinct code. Use it.
      * ``nested_only``   — only an inner command recorded anything. Attributing it to the outer
                            verb would tell the operator that `decompose` said `close_the_gap`,
                            which it did not.
      * ``ambiguous``     — the invoked verb recorded two or more DIFFERENT codes in one run.
                            A single invocation has one next action; two means the render path
                            was reached twice with different state, and recording either would
                            be a guess.
    """
    if matching_count == 0:
        return "nested_only" if other_count > 0 else "unobserved"
    if matching_count > 1 and not matching_are_identical:
        return "ambiguous"
    return "authoritative"


# ---------------------------------------------------------------------------------------------
# The gathering layer.
#
# Primitive facts, collected where they occur, with NO interpretation applied. Every means of
# combination — the dispositions above, and doctor's cross-axis precedence above those — is a
# separate layer reading this record. That ordering is the point: a collector that decided
# anything would pre-empt the layers built on it, and the founder has named a second consumer
# (inference over implicit patterns) that must not inherit doctor's opinions.
#
# Process-scoped: one invocation is one process, so this needs no key and no lifetime management
# beyond the drain. It is deliberately NOT the persisted file — the shell that writes
# `.detective/ledger.jsonl` reads this and is the only thing that touches disk.
# ---------------------------------------------------------------------------------------------

_OBSERVED: list[tuple[str, str, str]] = []


def observe(kind: str, verb: str, code: str) -> None:
    """Record ONE fact about the running invocation. NEVER raises.

    Called from render paths that already computed something worth keeping — the next-action
    code they routed on, which is otherwise consumed and discarded. An observation channel, not
    a return value: threading this up through five rendering layers would change ~12 pinned test
    call sites to carry a value none of them are about (founder call, 2026-09-08).

    The no-raise guarantee is absolute. A correctness tool does not acquire a new failure mode
    for an advisory record, and a caller must never need a try/except around observing.
    """
    try:
        _OBSERVED.append((str(kind), str(verb), str(code)))
    # BLE001: observation is advisory and never fatal
    except Exception:  # noqa: BLE001
        pass


def take_observations() -> tuple[tuple[str, str, str], ...]:
    """Drain what this process gathered. NEVER raises; empty is a valid answer.

    Draining rather than reading keeps the record honest under an in-process test session, where
    the same interpreter may run many logical invocations: whatever is left behind would
    otherwise be attributed to whoever asks next.
    """
    try:
        gathered = tuple(_OBSERVED)
        _OBSERVED.clear()
        return gathered
    # BLE001: observation is advisory and never fatal
    except Exception:  # noqa: BLE001
        return ()


def reset_observations() -> None:
    """Discard without reading — for a test that must start from a known-empty channel."""
    try:
        _OBSERVED.clear()
    # BLE001: observation is advisory and never fatal
    except Exception:  # noqa: BLE001
        pass


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
