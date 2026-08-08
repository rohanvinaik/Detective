"""Environment CAPABILITIES — a declared precondition Detective applies during capture AND renders
into the emitted test, so an environment-gated branch is PINNED instead of declined (issue #24).

The discipline is the one that makes ``--input`` sound: the human/model states the precondition
explicitly; deterministic code applies it and writes the test. No guessing at the environment.

Increment 1 ships the CLOCK capability. ``--clock EPOCH`` freezes the process's ``time``-module
clocks (``time`` / ``monotonic`` / ``perf_counter`` and their ``_ns`` forms) to a fixed value, so a
wall-clock-reading function is deterministic and pinnable. ONE plan, TWO interpreters:

* :func:`apply_clock` / :func:`restore_clock` freeze the clocks LIVE — the same sites capture,
  witness search, and profiling exercise the target;
* :func:`render_clock_freeze` emits the identical freeze + restore-in-``finally`` using only the
  stdlib, so the generated test needs no Detective at runtime.

Deferred to the #24 remainder (they need module-binding / import-alias work beyond this slice — a
builtin ``datetime.datetime.now`` cannot be ``setattr``'d, and ``from time import time`` keeps its
own binding): the ``datetime`` / ``date`` clocks, and the ``--env`` (process env) and ``--fixture``
(``tmp_path``) capabilities. Those stay the honest-decline path until built.
"""

from __future__ import annotations

import time


def clock_freezes(clock: float) -> list[tuple[str, object]]:
    """The ``(time-module attribute, frozen value)`` pairs the clock capability pins (pure — #24).

    The ``_ns`` clocks return integer nanoseconds; the rest return the float epoch. Freezing the whole
    ``time``-module family — not only ``time.time`` — means a function reading ``monotonic()`` /
    ``perf_counter()`` for a duration or TTL check is pinnable too, and to the SAME instant, so an
    intra-call elapsed reads as exactly 0 rather than a flaky small delta. Detective-pinned."""
    ns = int(clock * 1_000_000_000)
    return [
        ("time", clock),
        ("monotonic", clock),
        ("perf_counter", clock),
        ("time_ns", ns),
        ("monotonic_ns", ns),
    ]


def clock_covers(reason: str) -> bool:
    """Whether a ``--clock`` freeze covers this ``environment_reads`` reason (pure — #24).

    A reason names its symbol (``reads the clock via time.monotonic()``). ``--clock`` freezes the
    ``time`` module, so it covers every ``time.``-rooted clock read — but NOT ``datetime.now()`` /
    ``date.today()``, which read builtin-type methods this slice cannot freeze (the #24 remainder). A
    date golden under today's ``--clock`` would pass today and fail tomorrow, so it stays declined."""
    return "reads the clock via time." in reason


def apply_clock(clock: float) -> list[tuple[str, object]]:
    """Freeze the ``time``-module clocks live to ``clock``; return the saved originals to restore.

    The caller MUST restore in a ``finally`` (see :func:`restore_clock`) — a freeze that outlived the
    capture would leak a frozen clock into the consumer's own tests running in the same process."""
    saved = [(attr, getattr(time, attr)) for attr, _ in clock_freezes(clock)]
    for attr, value in clock_freezes(clock):
        setattr(time, attr, (lambda v=value: v))
    return saved


def restore_clock(saved: list[tuple[str, object]]) -> None:
    """Restore the ``time``-module clocks saved by :func:`apply_clock` — the freeze never leaks."""
    for attr, original in saved:
        setattr(time, attr, original)


def render_clock_freeze(clock: float, body_indented: str) -> str:
    """Emit ``body_indented`` wrapped so the ``time`` clocks are frozen to ``clock`` and restored in a
    ``finally``, using only the stdlib (mirrors the shipped ``--clock`` render; no Detective at
    runtime). ``body_indented`` is already indented one level (it runs inside the ``try``)."""
    freezes = clock_freezes(clock)
    attrs = ", ".join(f"_dtv_clock.{a}" for a, _ in freezes)
    sets = "\n".join(f"_dtv_clock.{a} = lambda: {v!r}" for a, v in freezes)
    return (
        "import time as _dtv_clock\n"
        f"_dtv_clock_saved = ({attrs})\n"
        f"{sets}\n"
        "try:\n"
        f"{body_indented}\n"
        "finally:\n"
        f"    ({attrs}) = _dtv_clock_saved"
    )


def capability_identity(clock: float | None) -> str | None:
    """A readable identity for the declared capability set, for the honest ``✓ COMPLETE under
    capability set <id>`` banner (#24 increment 2) — never an unconditional certificate for a
    function whose result depends on external state. None when no capability was supplied. A single
    clock reads as ``clock=<epoch>``; the #24 remainder folds multiple capabilities into a digest."""
    return None if clock is None else f"clock={clock!r}"
