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

import hashlib
import json
import os

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


# ─────────────────────────────────────────────────────────────────────────────
# The persistence shell (impure — hand-tested for durability, never converge-pinned).
#
# JSONL rather than one JSON document because a single `open(..., "a")` plus one newline-terminated
# `write()` needs no read-modify-write: concurrent runs cannot lose each other's entries, and a
# truncated final line costs ONE record instead of the file.
#
# HARD REQUIREMENT: it must never fail a run. A correctness tool does not acquire a new failure
# source for an advisory artifact, so every write is wrapped and swallowed. But the absence is
# DISCLOSED at read time — swallowing at write time is right; swallowing at read time is the thing
# this project exists to prevent, and an empty process section reads as "nothing wrong".
#
# NOT PURGED, and this needed no new rule: `verdict_cache.purge` works from an explicit ALLOWLIST
# (the cache file plus `.detective/reports/*`), not a sweep of `.detective/`, so history survives by
# construction. It also fails purge's own stated criterion — "everything removed is regeneratable by
# re-running" — because a re-run produces a NEW entry and cannot reproduce the one that recorded
# what you did an hour ago.
# ─────────────────────────────────────────────────────────────────────────────

LEDGER_REL = os.path.join(".detective", "ledger.jsonl")
LEDGER_SCHEMA = 1
# 5 MB, oldest-evicted. At this schema that is on the order of 10^4 entries — far more than any
# process question needs, and deliberately generous because the founder named this as a data source
# for later inference work. PRUNING IS NOT PURGING: eviction is logged in-band so a reader never
# mistakes a pruned head for the beginning of history.
LEDGER_CAP_BYTES = 5 * 1024 * 1024


def _sha(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:32]


def ledger_path(root: str) -> str:
    return os.path.join(os.path.abspath(root), LEDGER_REL)


def file_digest(path: str) -> str:
    """Content digest of one file, or "" when it cannot be read (never raises).

    "" is a REPORTED absence, not a value: two runs that both could not read the target must not
    compare equal on it, which is why the readers treat "" as unknown rather than as a digest.
    """
    try:
        with open(path, "rb") as fh:
            return "sha256:" + hashlib.sha256(fh.read()).hexdigest()[:32]
    except OSError:
        return ""


def suite_digest(write_dir: str, exact: bool = False) -> str:
    """Digest of the generated suite directory (never raises).

    Cheap by default — sorted ``(name, size, mtime_ns)``, one stat-walk, no reads. ``exact=True``
    content-hashes each file instead, and is paid for only where `state_basis` says the cheap basis
    can lie. See that function for which situation that is and why it is the only one.
    """
    try:
        names = sorted(n for n in os.listdir(write_dir) if n.endswith(".py"))
    except OSError:
        return ""
    parts: list[str] = []
    for name in names:
        full = os.path.join(write_dir, name)
        try:
            if exact:
                parts.append(f"{name}:{file_digest(full)}")
            else:
                st = os.stat(full)
                parts.append(f"{name}:{st.st_size}:{st.st_mtime_ns}")
        except OSError:
            parts.append(f"{name}:?")
    return _sha("\n".join(parts))


def append(root: str, record: dict) -> bool:
    """Append one record. Returns whether it landed; NEVER raises.

    One `open(..., "a")` and one `write()` of a newline-terminated line — no read-modify-write, so
    two concurrent runs cannot lose each other's entries. Eviction is checked BEFORE the write and
    only pays the rewrite when the cap is actually exceeded, so the common path is one stat.
    """
    path = ledger_path(root)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        _evict_if_over_cap(path)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
        return True
    except (OSError, TypeError, ValueError):
        return False


def _evict_if_over_cap(path: str) -> None:
    """Drop the oldest records until the file is under the cap, recording that it happened."""
    try:
        if os.path.getsize(path) <= LEDGER_CAP_BYTES:
            return
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError:
        return
    keep = lines[len(lines) // 2 :]
    dropped = len(lines) - len(keep)
    marker = json.dumps({"v": LEDGER_SCHEMA, "evicted": dropped}, sort_keys=True) + "\n"
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(marker)
            fh.writelines(keep)
        os.replace(tmp, path)
    except OSError:
        return


def read_recent(root: str, limit: int = 50) -> tuple[dict, ...]:
    """The most recent records, oldest-first, or () when there is no readable ledger.

    () is AMBIGUOUS on purpose at this layer — no file, unreadable file, empty file — and the
    caller must not render it as "nothing happened". `ledger_available` answers that separately,
    because "we have no history" and "you have run nothing" are different facts and only one of
    them is a finding about the operator.

    A truncated final line (an interrupted write) is skipped rather than fatal: JSONL's whole
    argument is that a bad tail costs one record.
    """
    try:
        with open(ledger_path(root), encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError:
        return ()
    out: list[dict] = []
    for line in lines[-max(limit, 1) * 2 :]:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and "evicted" not in row:
            out.append(row)
    return tuple(out[-limit:])


def ledger_available(root: str) -> bool:
    """Whether a ledger EXISTS to be read — the fact `read_recent`'s empty tuple cannot carry.

    Doctor's red axis reports "process findings are UNAVAILABLE" on False and "no prior
    invocations" on True-with-no-rows. Collapsing them would let a missing ledger render as a clean
    process read, which is the one thing this surface must never do.
    """
    return os.path.isfile(ledger_path(root))


def prune(root: str) -> tuple[str, int]:
    """DELETE the invocation history. Returns ``(path, bytes)``, or ``("", 0)`` if there was none.

    Deliberately NOT part of ordinary `purge`, and it is the one destructive thing in the tool.
    Everything `purge` removes is regeneratable by re-running — that is its stated criterion and why
    it needs no confirmation. History fails that criterion: a re-run appends a NEW entry and cannot
    reproduce the one that recorded what you did an hour ago.

    Founder ruling 2026-09-09, kept because it is an argument about when a safety rail comes OFF
    rather than when it goes on: the history "was very useful during debugging/building, and should
    only be removed if there's no possible way for a mistake in operation, which is obviously far
    away. Theoretically possible, but not today."

    The CALLER owns the confirmation. A library function that prompts cannot be used by anything
    that is not a terminal, and this one is also the thing a future automated consumer would want.
    """
    path = ledger_path(root)
    try:
        size = os.path.getsize(path)
        os.remove(path)
    except OSError:
        return "", 0
    return path, size


def state_basis(has_prior: bool, same_args: bool, cheap_says_changed: bool) -> str:
    """Which digest basis this comparison needs — cheap by default, exact where cheap can LIE
    (pure — pinned; founder ruling 2026-09-09: "cheap with fallback triggered when the situation
    knowably calls for it").

    `state.suite` is a hash over sorted ``(name, size, mtime_ns)``. That is one stat-walk and no
    reads, and it is EXACT in one direction and not the other:

      cheap says UNCHANGED  →  content is unchanged, barring deliberate mtime restoration
      cheap says CHANGED    →  content may be identical. A `touch`, a checkout, a copy, a
                               `git stash` round-trip all move mtime without moving a byte.

    The second is the one that matters, and only in one situation. If the operator re-ran the SAME
    command with the SAME arguments and the cheap digest says the state moved, then either they
    genuinely edited something — normal work, nothing to report — or the mtimes shifted underneath
    them and this is a SPIRAL the cheap basis is about to hide. Those two are worth one full read
    to tell apart, and nothing else is.

      "cheap"           the stat-walk is conclusive here. No prior to compare against, or the
                        arguments moved (so the state question is moot), or cheap already says
                        unchanged — which is the direction it cannot get wrong.
      "escalate_exact"  same command, same arguments, cheap reports a change. Content-hash the
                        suite before believing it, because this is exactly where a repeat that
                        changed NOTHING gets excused as normal work.

    THE HEALTHY PATH NEVER PAYS. A first run, a progressed run, and an unchanged run all take the
    stat-walk. Only a same-args repeat that appears to have moved buys the read, which is the
    smallest set that closes the hole.

    KNOWN LIMIT, stated rather than papered over: the other direction — content changed while mtime
    was RESTORED — would let cheap report `unchanged` and produce a false spiral accusation, which
    is the worse error. It is not escalated because catching it costs a full read on every repeat,
    including every healthy one, and its precondition is deliberate mtime restoration rather than
    anything an operator does by accident.
    """
    if not has_prior:
        return "cheap"
    if not same_args:
        return "cheap"
    if not cheap_says_changed:
        return "cheap"
    return "escalate_exact"


def suite_state_comparison(cheap_same: bool, both_exact: bool, exact_same: bool) -> str:
    """Did the generated suite actually move between two records — and on WHAT basis (pure — pinned).

    The READ half of the founder's ruling in `docs/INVOCATION_LEDGER.md` §8.1. `state_basis` decides
    at WRITE time whether a run buys the exact digest; this decides what the two records being
    compared are entitled to conclude. They are separate decisions because they answer questions in
    different TENSES over different data, and folding them into one would be the sibling drift every
    repair in `CORRECTNESS_REPAIRS_2026-09-08.md` turned out to be an instance of.

    The names carry the BASIS as well as the verdict, because "the content is unchanged" and "the
    stat-walk agreed and nobody looked further" are different claims:

      "unchanged_exact"  both records content-hashed the suite and the hashes match. THE case the
                         escalation exists for: the mtime moved and no byte did.
      "changed_exact"    both content-hashed and they differ — a genuine edit, established.
      "unchanged_cheap"  no exact pair, and the cheap digests agree. Still conclusive: the cheap
                         basis is exact in THAT direction (§8.1's table). Only "changed" can lie.
      "unknown"          the cheap digests differ and there is no exact pair to check. The one that
                         must not be rendered as either answer — a `touch`, a checkout, a copy and a
                         real edit all land here, and the caller treats it as changed (quiet), which
                         is the safe direction §7.1 named.

    Exact evidence outranks cheap wherever both exist — including the combination the write side
    cannot currently produce (cheap agreeing while exact disagrees, §8.1's KNOWN LIMIT: content
    changed with the mtime restored). Deciding it here costs one branch and means a later write-side
    change cannot silently acquire a wrong answer by fall-through.

    THE LAG, stated rather than left to be discovered. An exact pair needs BOTH records to have
    escalated, and a run escalates only when it is a same-args repeat whose cheap digest moved. So a
    ONE-OFF perturbation yields `unknown` and stays quiet, while a REPEATED one — a CI checkout each
    run, a `git stash` loop — is caught from its second occurrence. That is the price of the ruled
    option, which in exchange never taxes a healthy repeat.
    """
    if both_exact:
        return "unchanged_exact" if exact_same else "changed_exact"
    if cheap_same:
        return "unchanged_cheap"
    return "unknown"


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
