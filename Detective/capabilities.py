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


def env_covers(reason: str) -> bool:
    """Whether a declared ``--env`` set covers this ``environment_reads`` reason (pure — #48).

    ``--env`` applies process-environment variables, so it covers a ``reads process env via …``
    dependency (``os.environ`` / ``os.getenv``). It does NOT cover the clock, the PID, the calendar
    date, entropy, or filesystem reads — each waits for its OWN capability, exactly as ``--clock``
    covers only ``time.``-rooted reads. Per-variable admissibility (was THIS var declared) is decided
    at capture time, where the read's name is known; this static gate only asks "is the env CLASS
    covered at all", and defers the precise per-var refusal to the capture disposition.
    """
    return "process env" in reason


def env_token_disposition(token: str) -> str:
    """Classify one ``--env`` token (#48, pure — pinned): how a NAME=value / NAME- spelling reads.

    * ``set``       — ``NAME=value`` with a non-empty NAME. An empty VALUE is allowed and means the
      variable is present-and-empty, which is a DISTINCT state from absent (a ``getenv`` returns
      ``""`` vs ``None``), so the two must not collapse.
    * ``absent``    — ``NAME-`` (a trailing dash, no ``=``): the variable is declared explicitly
      UNSET, making a ``KeyError`` / ``os.getenv(...) is None`` branch reachable and pinnable.
    * ``malformed`` — neither form, or an empty NAME (``=value`` / ``-`` / ``""``). Named rather than
      folded into ``absent`` so the CLI refuses it loudly instead of silently unsetting a nameless
      variable — the same "absent is not malformed" distinction the value case draws above.
    """
    if "=" in token:
        return "set" if token.split("=", 1)[0] else "malformed"
    if token.endswith("-") and len(token) > 1:
        return "absent"
    return "malformed"


def parse_env(tokens: list[str]) -> tuple[tuple[str, str | None], ...]:
    """Parse ``--env`` tokens into ``(name, value)`` pairs, ``value=None`` meaning declared ABSENT.

    Thin over the pinned :func:`env_token_disposition`: a ``malformed`` token RAISES rather than being
    silently dropped — a capability the user asked for that cannot be parsed must stop the run, not
    scope a certificate to a set that quietly omits it.
    """
    spec: list[tuple[str, str | None]] = []
    for tok in tokens:
        disposition = env_token_disposition(tok)
        if disposition == "set":
            name, value = tok.split("=", 1)
            spec.append((name, value))
        elif disposition == "absent":
            spec.append((tok[:-1], None))
        else:
            raise ValueError(f"malformed --env {tok!r}: expected NAME=value, or NAME- for absent")
    return tuple(spec)


def apply_env(spec: tuple[tuple[str, str | None], ...]) -> list[tuple[str, str | None]]:
    """Apply the declared environment live; return the saved originals to restore (#48).

    ``value=None`` DELETES the variable (declared absent); otherwise it is set. Each saved entry keeps
    the prior value, or ``None`` if the variable was itself absent — so :func:`restore_env` can put the
    environment back exactly, including restoring a variable to *absent*. The caller MUST restore in a
    ``finally`` — a declared environment that outlived the capture would leak into later captures and
    the consumer's own tests running in the same process.
    """
    import os

    saved: list[tuple[str, str | None]] = []
    for name, value in spec:
        saved.append((name, os.environ.get(name)))
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
    return saved


def restore_env(saved: list[tuple[str, str | None]]) -> None:
    """Undo :func:`apply_env`, innermost first — restoring each variable to its prior value, or to
    ABSENT when it had none, so the process environment is byte-for-byte what it was."""
    import os

    for name, original in reversed(saved):
        if original is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = original


def render_env(spec: tuple[tuple[str, str | None], ...], body_indented: str) -> str:
    """Emit ``body_indented`` wrapped so the declared environment is applied and restored in a
    ``finally``, using only the stdlib (mirrors :func:`render_clock_freeze`; no Detective at runtime).

    ``body_indented`` is already indented one level (it runs inside the ``try``). A declared-absent
    variable is ``pop``-ed; the saved originals restore to the prior value or to absent.
    """
    names = [name for name, _ in spec]
    saves = ", ".join(f"{n!r}: _dtv_env.environ.get({n!r})" for n in names)
    applies = "\n".join(
        (f"_dtv_env.environ.pop({n!r}, None)" if v is None else f"_dtv_env.environ[{n!r}] = {v!r}")
        for n, v in spec
    )
    return (
        "import os as _dtv_env\n"
        f"_dtv_env_saved = {{{saves}}}\n"
        f"{applies}\n"
        "try:\n"
        f"{body_indented}\n"
        "finally:\n"
        "    for _dtv_n, _dtv_v in _dtv_env_saved.items():\n"
        "        _dtv_env.environ.pop(_dtv_n, None) if _dtv_v is None else "
        "_dtv_env.environ.__setitem__(_dtv_n, _dtv_v)"
    )


def apply_clock(clock: float, namespace: dict[str, object] | None = None) -> list[tuple]:
    """Freeze the ``time``-module clocks live to ``clock``; return the saved originals to restore.

    The caller MUST restore in a ``finally`` (see :func:`restore_clock`) — a freeze that outlived the
    capture would leak a frozen clock into the consumer's own tests running in the same process.

    ``namespace`` is the TARGET module's globals (#48-E). ``from time import time`` binds the clock
    FUNCTION directly into that namespace, so patching the ``time`` module attribute below never
    reaches it — the free clock is read anyway, and the perturbed-epoch probe that exists to catch it
    misses it too, so a free clock reads as deterministic. Every namespace binding that IS one of the
    original clock functions is therefore frozen BY IDENTITY as well. ``import time as t`` needs
    nothing here: ``t`` is the module object, so the module-attribute patch already covers ``t.time()``.
    """
    freezes = clock_freezes(clock)
    originals = {attr: getattr(time, attr) for attr, _ in freezes}
    saved: list[tuple] = [("module", attr, originals[attr]) for attr, _ in freezes]
    for attr, value in freezes:
        setattr(time, attr, (lambda v=value: v))
    if namespace is not None:
        by_id = {id(originals[attr]): value for attr, value in freezes}
        for name, obj in list(namespace.items()):
            frozen = by_id.get(id(obj))
            if frozen is not None:
                saved.append(("ns", namespace, name, obj))
                namespace[name] = lambda v=frozen: v
    return saved


def restore_clock(saved: list[tuple]) -> None:
    """Restore the clocks saved by :func:`apply_clock` — module attributes AND any target-namespace
    from-import bindings (#48-E) — so the freeze never leaks."""
    for entry in saved:
        if entry[0] == "module":
            setattr(time, entry[1], entry[2])
        else:  # ("ns", namespace, name, original)
            entry[1][entry[2]] = entry[3]


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


def capability_identity(clock: float | None, env: tuple[tuple[str, str | None], ...] = ()) -> str | None:
    """A readable identity for the declared capability set, for the honest ``✓ COMPLETE under
    capability set <id>`` banner (#24 increment 2) — never an unconditional certificate for a
    function whose result depends on external state. None when no capability was supplied. A single
    clock reads as ``clock=<epoch>``; the #24 remainder folds multiple capabilities into a digest."""
    parts: list[str] = []
    if clock is not None:
        parts.append(f"clock={clock!r}")
    if env:
        rendered = ",".join(f"{n}={v!r}" if v is not None else f"{n}-" for n, v in env)
        parts.append(f"env={rendered}")
    return " ".join(parts) if parts else None
