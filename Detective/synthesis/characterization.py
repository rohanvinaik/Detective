"""Characterization-backed golden captures.

Run a deterministic function on inferred inputs, capture the result, and emit a
pytest test that pins it. A capture is PROVISIONAL until corroborated by another
lens (purity + determinism, or a VALUE-mutation kill) — otherwise it fossilizes
whatever the code currently does, bugs included.

Clean-room port of LintGate's characterization. The seam is improved: capture
takes a *live callable* (the caller resolves it) rather than importing the module
itself, so the logic is pure and directly testable.
"""

from __future__ import annotations

import ast
import contextlib
import os
import sys
import tempfile
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass, field, is_dataclass, replace
from dataclasses import fields as dataclass_fields
from enum import StrEnum
from typing import Any

from ..capabilities import apply_clock, apply_env, restore_clock, restore_env
from ..equivalence import unwrap


class Provenance(StrEnum):
    """Maturity of a characterization capture.

    ``StrEnum``, not ``(str, Enum)``: they differ only in what ``str()``/``format()`` return
    (the value vs ``Provenance.NAME``), and this enum is only ever compared or read via
    ``.value`` — so the swap is behaviour-preserving here, and would NOT be if a member were
    ever interpolated directly.
    """

    UNCHECKED = "unchecked"
    PROVISIONAL = "provisional"
    CORROBORATED = "corroborated"


@dataclass(frozen=True)
class GoldenCapture:
    """A captured golden value for one function invocation."""

    inputs: tuple[Any, ...]
    kwargs: dict[str, Any] = field(default_factory=dict)
    output: str = ""  # repr of the result
    # The result ITSELF. The repr alone cannot answer "is this an unordered container",
    # and that question decides whether repr-equality is a sound assertion or a flaky one
    # (`golden_assert_line`). Carried, never rendered; ``compare=False`` because ``output``
    # already summarises it for identity, and a live value may not compare cleanly.
    value: Any = field(default=None, compare=False)
    deterministic: bool = False
    provenance: Provenance = Provenance.PROVISIONAL
    corroborating_lens: str = ""
    # Filesystem paths the invocation opened that are NOT derived from its own
    # arguments (issue #23). Non-empty means the capture pinned the ENVIRONMENT
    # — a default-path data file — not the function: green until the data file
    # legitimately changes, then a phantom regression. Consumers refuse to emit
    # such a capture as a golden and say why instead.
    environment_paths: tuple[str, ...] = ()
    # Filesystem paths the invocation WROTE (mkdir / write / rename / delete), at any call depth
    # (issue #30). Non-empty means the function mutates the tree — transitively, past AST-local
    # purity — so no golden of its return is portable, and the write was BLOCKED during capture so
    # it did not litter. Consumers refuse such a capture and name the writes. Distinct from
    # ``environment_paths`` (default-path READS, #23): a read pins the environment, a write changes it.
    filesystem_writes: tuple[str, ...] = ()
    # Environment VARIABLE names the invocation read (issue #23, environment half). Non-empty means
    # the captured value is a function of this machine's environment, so pinning it by equality
    # produces a test that is green here and red on CI. Distinct from ``environment_paths``, which
    # records default-path FILE reads: same refusal, different channel into the same environment.
    environment_reads: tuple[str, ...] = ()
    # Whether the captured value MOVED when the same call was replayed under a different frozen
    # clock, with no freeze planned for the emitted test. Probed rather than read off the source, so
    # it holds for a clock reached through a helper the static scan never looks at. When ``clock``
    # below is set the emitted test freezes the clock itself, and movement is pinned rather than
    # refused — so this is only ever consulted for an unfrozen capture.
    clock_dependent: bool = False
    # The wall-clock value `time.time()` was FROZEN to for this capture (the `--clock` residual
    # for a time-gated function), or None if the clock ran free. A frozen clock is what makes a
    # `time.time()`-reading function DETERMINISTIC — hence capturable and pinnable — and the
    # emitted test restores `time.time` in a `finally` so the freeze never leaks to another test.
    clock: float | None = None
    # The declared ENVIRONMENT this capture was taken under (#48): ``(name, value)`` pairs, ``value``
    # None meaning declared-absent. Set by ``--env``, applied live during capture so a branch behind
    # an ``os.environ[NAME]`` read is reachable, and rendered into the emitted test (``render_env``) so
    # it re-applies and restores the same environment. A certificate is scoped to this exact set.
    env: tuple[tuple[str, str | None], ...] = ()


def eval_call_site(site: dict) -> tuple[tuple[Any, ...], dict[str, Any]] | None:
    """Evaluate a call site's args as Python literals.

    Returns ``(args, kwargs)`` or None if any argument is a non-literal (a name
    or expression that cannot be captured deterministically). Accepts both
    ``positional_args``/``keyword_args`` and legacy ``args``/``kwargs`` keys.
    """
    args: list[Any] = []
    for a in site.get("positional_args") or site.get("args") or []:
        literal = _as_literal(a)
        if literal is _UNSET:
            return None
        args.append(literal)

    kwargs: dict[str, Any] = {}
    for key, value in (site.get("keyword_args") or site.get("kwargs") or {}).items():
        literal = _as_literal(value)
        if literal is _UNSET:
            return None
        kwargs[key] = literal

    return tuple(args), kwargs


def capture_golden(
    func: Callable[..., Any],
    call_site_inputs: list[dict],
    clock: float | None = None,
    env: tuple[tuple[str, str | None], ...] = (),
    namespace: dict[str, object] | None = None,
) -> list[GoldenCapture]:
    """Capture golden values for ``func`` from zero-arg and literal call sites.

    Each candidate invocation is run twice; a stable repr marks the capture
    deterministic. Duplicate argument sets are captured once. Invocations that
    raise are skipped.

    ``clock`` (the `--clock` residual) FREEZES ``time.time()`` to a fixed value for the
    duration of each call. A function whose output depends on the wall clock is
    non-deterministic and would be abstained; with the clock frozen the two calls agree, the
    capture is deterministic, and the emitted test re-freezes the clock so it stays true.
    """
    captures: list[GoldenCapture] = []
    seen: set[str] = set()

    for args, kwargs in _candidate_inputs(call_site_inputs):
        key = repr((args, kwargs))
        if key in seen:
            continue
        seen.add(key)
        capture = _try_capture(func, args, kwargs, clock=clock, env=env, namespace=namespace)
        if capture is not None:
            captures.append(capture)

    return captures


def corroborate_captures(
    captures: list[GoldenCapture],
    *,
    is_pure: bool = False,
    value_mutation_killed: bool = False,
) -> list[GoldenCapture]:
    """Upgrade PROVISIONAL captures to CORROBORATED where evidence supports it.

    A deterministic capture of a pure function is corroborated by
    ``pure_deterministic``; any capture is corroborated by ``mutation_value_killed``
    when a VALUE mutation of the function was killed (the golden value
    discriminates correct from mutant). Non-PROVISIONAL captures pass through.
    """
    upgraded: list[GoldenCapture] = []
    for cap in captures:
        if cap.provenance != Provenance.PROVISIONAL:
            upgraded.append(cap)
        elif cap.deterministic and is_pure:
            upgraded.append(_corroborate(cap, "pure_deterministic"))
        elif value_mutation_killed:
            upgraded.append(_corroborate(cap, "mutation_value_killed"))
        else:
            upgraded.append(cap)
    return upgraded


def generate_golden_test(func_key: str, captures: list[GoldenCapture]) -> str:
    """Emit pytest source pinning each deterministic golden capture.

    A deterministic capture becomes an exact ``repr(result) == <golden>``
    assertion; a non-deterministic one is abstained on (no vacuous
    ``assert result is not None`` skeleton — that fossilizes nothing and only
    dilutes the suite). Returns "" when nothing is pinnable.
    """
    mod, fname = func_key.rsplit("::", 1) if "::" in func_key else ("", func_key)
    pinnable = [c for c in captures if c.deterministic]
    if not pinnable:
        return ""

    lines: list[str] = []
    if mod:
        lines += [f"from {mod} import {fname}", ""]

    for i, cap in enumerate(pinnable):
        suffix = f"_{i}" if len(pinnable) > 1 else ""
        lines.append(f"def test_{fname}_golden{suffix}():")
        lines.append(f"    {_docstring(cap)}")
        lines.append(f"    result = {fname}({_call_args(cap)})")
        tag = "" if cap.provenance == Provenance.CORROBORATED else f"  # {cap.provenance.value}"
        lines.append(f"    {golden_assert_line(cap.output, cap.value)}{tag}")
        lines.append("")

    return "\n".join(lines)


# ── Internals ─────────────────────────────────────────────────────

_UNSET = object()


def _as_literal(value: Any) -> Any:
    """A literal value, evaluating strings via ast.literal_eval; _UNSET if not."""
    if not isinstance(value, str):
        return value
    try:
        return ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return _UNSET


def _candidate_inputs(call_site_inputs: list[dict]) -> list[tuple[tuple[Any, ...], dict[str, Any]]]:
    """Zero-arg first, then each literal-evaluable call site."""
    candidates: list[tuple[tuple[Any, ...], dict[str, Any]]] = [((), {})]
    for site in call_site_inputs:
        parsed = eval_call_site(site)
        if parsed is not None:
            candidates.append(parsed)
    return candidates


# ── Environment-coupling watch (issue #23) ─────────────────────────────
#
# An audit hook is PERMANENT once installed (sys.addaudithook has no remove),
# so there is exactly one, installed lazily, gated by a ContextVar that is
# None except during a capture invocation. Static purity analysis missed the
# field case (open() reached through nested calls), which is why this is a
# RUNTIME watch: the audit event fires for io.open however deep the call.


@dataclass
class _EffectSink:
    """What a speculative capture invocation touched, and whether to PREVENT its writes.

    ``opened`` — every fs-effect path (reads included), for the #23 default-path-I/O refusal.
    ``writes`` — the MUTATING subset (a golden of a function that writes pins nothing portable, #30).
    ``block`` — when True the hook RAISES on a write, so a transitive/default-path write is prevented
    before it litters the tree, not merely observed after (#30: 'observing a write after it has
    littered the tree is not a safety gate'). Blocking is scoped to this capture by the ContextVar,
    so the consumer's own tests and Wesker's profiling — where the sink is None — write freely.
    """

    opened: list[str] = field(default_factory=list)
    writes: list[str] = field(default_factory=list)
    # Environment VARIABLE names read during the capture. Same refusal shape as ``opened``: a value
    # derived from ``$APP_MODE`` belongs to the environment, not the function. Recorded by proxying
    # ``os.environ`` rather than by the audit hook — CPython emits NO audit event for an environment
    # read, so the hook that powers the two lists above structurally cannot cover this one.
    env_reads: list[str] = field(default_factory=list)
    block: bool = False


class _CaptureWriteBlocked(BaseException):
    """A filesystem write attempted during speculative golden capture was prevented (#30).

    Raised INSIDE the audit hook, so it unwinds the target mid-write: the effect never lands, and
    the capture is reported as a filesystem-writing refusal.

    Subclasses ``BaseException``, NOT ``Exception``, on purpose. A target that wraps its own write in
    ``try: … except Exception:`` (a fallback, a "best effort" logger) would otherwise CATCH the guard,
    swallow the unwind, and return normally — and Detective would pin a golden of that fallback branch
    while reporting zero writes, even though the same function writes the file when run for real. Sitting
    above ``Exception`` (like ``KeyboardInterrupt``/``SystemExit``) makes the guard unswallowable by
    ordinary handlers; only Detective's own call sites, which name it explicitly, may catch it."""


_OPEN_WATCH: ContextVar[_EffectSink | None] = ContextVar("detective_open_watch", default=None)
_watch_installed = False


# Filesystem-effect audit events whose FIRST arg is the path touched. `open` covers
# `write_text`/`read_text` and plain I/O; the `os.*` events cover writes that never open a file
# (a helper that only `mkdir`s a default dir, renames, or deletes). Watching all of them makes a
# TRANSITIVE effect — one the target reaches only through a callee — visible regardless of call
# depth, which AST-local purity cannot see (#30). `os.makedirs`/`Path.mkdir`/`Path.write_text`
# decompose into these primitives, so they are covered without being named.
_FS_EFFECT_EVENTS = frozenset(
    {"open", "os.mkdir", "os.rename", "os.replace", "os.remove", "os.rmdir", "os.unlink", "os.symlink"}
)
# The events that ALWAYS mutate the filesystem — `open` is the exception (it reads OR writes,
# decided by mode/flags via `open_is_write`). Everything else here only ever changes the tree.
_MUTATING_EFFECT_EVENTS = _FS_EFFECT_EVENTS - {"open"}


def open_is_write(mode: object, flags: object) -> bool:
    """Whether an ``open`` audit event is a WRITE (issue #30, pure — Detective-pinned).

    The audit event carries ``(path, mode, flags)``. A text mode string writes when it names any of
    ``w a x +`` (``r``/``rb`` are pure reads); when mode is absent (``os.open`` with integer flags)
    the flags decide — any of ``O_WRONLY O_RDWR O_CREAT O_APPEND O_TRUNC`` is a write. Unknown shapes
    are treated as READS, so the block never aborts a legitimate read the #23 path already handles.
    """
    if isinstance(mode, str):
        return any(ch in mode for ch in "wax+")
    if isinstance(flags, int):
        write_flags = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC
        return bool(flags & write_flags)
    return False


def _open_watch_hook(event: str, args: tuple) -> None:
    if event not in _FS_EFFECT_EVENTS:
        return
    sink = _OPEN_WATCH.get()
    if sink is None:
        return
    target = args[0]
    path: str | None = None
    if isinstance(target, (str, bytes, os.PathLike)):
        with contextlib.suppress(TypeError, UnicodeDecodeError):
            path = os.fsdecode(target)
    if path is not None:
        sink.opened.append(path)
    is_write = event in _MUTATING_EFFECT_EVENTS or (
        event == "open" and open_is_write(args[1] if len(args) > 1 else None, args[2] if len(args) > 2 else 0)
    )
    if is_write:
        if path is not None:
            sink.writes.append(path)
        if sink.block:
            # Prevent the write BEFORE it lands (#30). The raise unwinds the target; the caller
            # records the attempt and refuses the golden.
            raise _CaptureWriteBlocked(path or event)


# The epoch the perturbation probe re-runs a capture under (2033-05-18). Far from both "now" and
# from `1_000_000_000.0`, the value `--clock` and the test fixtures use, so a match cannot be
# coincidence.
_PERTURBED_EPOCH = 2_000_000_000.0


class _RecordingEnviron(type(os.environ)):  # type: ignore[misc]  # ty: ignore[unsupported-base]
    """``os.environ``, recording which variable names were read (#23, environment half).

    Subclasses the REAL ``os._Environ`` rather than wrapping a dict, and that is load-bearing:
    the real class is what keeps ``putenv``/``unsetenv`` in step with the process environment,
    so a captured function that sets a variable and then spawns a subprocess still behaves
    correctly. Measured — a dict proxy silently breaks subprocess inheritance, and nothing in
    the suite would have caught it.

    EVERY SPELLING IS CAUGHT, including ``from os import getenv``, because ``getenv`` resolves
    ``os.environ`` at CALL time rather than at import time. That is what makes this alias- and
    indirection-proof, and it is precisely the property a static scan of the source cannot have.

    Reads reached through iteration (``dict(os.environ)``, ``os.environ.keys()``) are NOT
    recorded: they name no single variable, and expanding them to "every variable" would refuse
    over the whole environment. A documented remainder, not a silent one.
    """

    def __init__(self, real: Any, sink: _EffectSink) -> None:
        super().__init__(real._data, real.encodekey, real.decodekey, real.encodevalue, real.decodevalue)
        self._sink = sink

    def _record(self, key: Any) -> None:
        # `get` delegates to `__getitem__`, so one read arrives twice; and a bytes key (`os.environb`)
        # must not read as a different variable from its str spelling. Normalising both here is what
        # lets the refusal name each variable ONCE, in the spelling a human would write.
        with contextlib.suppress(TypeError, UnicodeDecodeError):
            name = os.fsdecode(key) if isinstance(key, (str, bytes)) else str(key)
            if name not in self._sink.env_reads:
                self._sink.env_reads.append(name)

    def __getitem__(self, key: Any) -> Any:
        self._record(key)
        return super().__getitem__(key)

    def get(self, key: Any, default: Any = None) -> Any:
        self._record(key)
        return super().get(key, default)

    def __contains__(self, key: Any) -> bool:
        # A membership test that decides the return value is environment dependence just as much
        # as a lookup is: `"CI" in os.environ` branching two ways pins whichever way this machine went.
        self._record(key)
        return super().__contains__(key)


def _install_open_watch() -> None:
    global _watch_installed
    if not _watch_installed:
        sys.addaudithook(_open_watch_hook)
        _watch_installed = True


@contextlib.contextmanager
def block_fs_writes():
    """Run a block of SPECULATIVE target execution with filesystem writes prevented (issue #30).

    Detective runs the consumer's function on inputs IT invented — golden capture, the witness
    search's original-vs-mutant comparison — and a transitive write there litters the consumer's
    tree for a run that was only ever measuring. Inside this context the audit hook raises on a
    write, so the effect never lands; the call unwinds and the caller treats it as a raise. Scoped
    by the ContextVar to the wrapped block and its thread, so the consumer's OWN tests and Wesker's
    profiling — where no sink is set — still write freely. Yields the sink (its ``writes`` lists what
    was prevented). NOT a general sandbox: it blocks writes, not reads, and only where installed.
    """
    _install_open_watch()
    sink = _EffectSink(block=True)
    token = _OPEN_WATCH.set(sink)
    try:
        yield sink
    finally:
        _OPEN_WATCH.reset(token)


def _environment_paths(opened: list[str], args: tuple[Any, ...], kwargs: dict[str, Any]) -> tuple[str, ...]:
    """The opened paths that are NOT explained by the invocation itself:
    code loading (imports open .py/.pyc) is not data, and a path derived from
    an argument (the arg itself, or a join on an arg directory) is the
    function doing its job. What remains is default-path I/O — the
    environment, which a golden must not pin."""
    arg_strings = [
        os.fspath(v)
        for v in (*args, *kwargs.values())
        if isinstance(v, (str, bytes, os.PathLike))
        and not isinstance(v, bytes)  # byte-paths: rare, and substring math lies
    ]
    out: list[str] = []
    for path in opened:
        if path.endswith((".py", ".pyc", ".pyi")) or "__pycache__" in path:
            continue
        if any(a and a in path for a in arg_strings):
            continue
        out.append(path)
    return tuple(sorted(set(out)))


def golden_capture_disposition(
    filesystem_writes: tuple[str, ...],
    environment_paths: tuple[str, ...],
    environment_reads: tuple[str, ...],
    machine_probe: str,
    clock_dependent: bool,
    deterministic: bool,
) -> str:
    """Whether a captured value may be pinned by equality, and if not, WHICH way it is unpinnable.

    (#23/#30, pure — pinned.) Split out of the ``if/elif`` chain in ``_golden_properties`` that
    used to hold it inline. That chain reads capture OBJECTS, so input synthesis could not
    construct a call and none of it was reachable by ``--input``; taking the six facts directly
    puts the whole decision inside the literal grammar. The caller keeps the message wording and
    holds no decision of its own.

    A NAMED CODE PER REASON, not a bool, because the reasons are not interchangeable: a write
    means "no golden of this return is portable at all", a default-path read means "supply a
    fixture", an environment read means "this is CI-dependent", a machine path means "this string
    is about my checkout". Collapsing them into one falsy result is what let three different
    defects share a single silent drop.

    Order is by how fundamental the objection is, and it decides only which message a
    multiply-unpinnable capture gets — every branch below refuses either way.

    ``drop_nondeterministic`` is deliberately distinct from the refusals: an unstable value is
    dropped without a message today, and preserving that as its own code keeps "we said why" and
    "we said nothing" from reading alike.
    """
    if filesystem_writes:
        return "refuse_writes"
    if environment_paths:
        return "refuse_default_path_read"
    if environment_reads:
        return "refuse_environment_read"
    if machine_probe:
        return "refuse_machine_path"
    if clock_dependent:
        return "refuse_clock_dependent"
    if not deterministic:
        return "drop_nondeterministic"
    return "pin"


def value_capture_coupling(disposition: str) -> str:
    """Whether a refusal reason disqualifies the FUNCTION's value goldens, or only this one value.

    (#39, pure — pinned.) The witness pass runs a second, independent search for distinguishing
    inputs and emits its own goldens, so a reason established during capture has to be told to it
    or it re-derives nothing and ships the same unpinnable value. Measured: with the capture-side
    refusals in place and this link absent, `converge` printed "2 golden(s) refused —
    environment-dependent" and wrote `assert result == "STAGING"` in the same run.

    ``function_coupled`` — the objection is to the function: it reads the environment, moves with
    the clock, opens a default path, or writes. NO value it returns is portable, at any input the
    witness search might find, so the whole value-golden pass is declined for it.

    ``value_local`` — the objection is to this particular VALUE, not the function. The machine-path
    case is the one: `golden_assert_line` already declines such a value wherever it is rendered, so
    the witness pass is correctly left open rather than shut for a reason already handled per-value.

    ``none`` — no objection, or a non-refusal (an unstable value is dropped, which says nothing
    about whether some other input is capturable).
    """
    if disposition in (
        "refuse_environment_read",
        "refuse_clock_dependent",
        "refuse_default_path_read",
        "refuse_writes",
    ):
        return "function_coupled"
    if disposition == "refuse_machine_path":
        return "value_local"
    return "none"


def _try_capture(
    func: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    clock: float | None = None,
    env: tuple[tuple[str, str | None], ...] = (),
    namespace: dict[str, object] | None = None,
) -> GoldenCapture | None:
    """Call ``func`` twice; capture repr + determinism, or None if it raises.

    Arguments are unwrapped for the call so a synthesized ``SourceExpr`` (an AST
    node paired with its source) runs as its live value; the original args — carrier
    intact — are stored on the capture so the emitted test renders as ``repr`` =
    the constructor source, not an opaque object repr.

    ``clock`` freezes the whole ``time``-module clock family (``time`` / ``monotonic`` /
    ``perf_counter`` and the ``_ns`` forms; see :func:`capabilities.apply_clock`) to a fixed value
    across both calls (restored in ``finally``, so no leak). This is what turns a wall-clock reader
    deterministic: without it the two calls disagree and the capture is dropped. ``date.today()``
    DOES follow the freeze — measured, against this docstring's own earlier claim that it did not —
    because it derives from the frozen ``time.time``; only ``datetime.now()`` stays out of reach
    (a builtin-type method this slice cannot ``setattr`` — the #24 remainder). Reaches a function
    that calls the clock on the module (``import time; time.time()``); a ``from time import time``
    local binding keeps its own reference and is a documented miss.

    TWO CALLS IN ONE ENVIRONMENT CANNOT SEE ENVIRONMENT DEPENDENCE — they agree precisely because
    nothing varied. So the capture also PERTURBS: ``os.environ`` is proxied to record which
    variables were read, and an unfrozen capture is replayed under a different epoch to see whether
    the value moves. Both observe the running function rather than its source, which is what makes
    them hold for a read reached through an alias or a helper.

    ``deterministic`` asks whether the VALUE is stable, and compares reprs to decide. Both
    calls share one process, so this cannot observe hash-seed effects — which is correct,
    not a gap: a set's repr ORDER varies across processes while its value does not, so it
    belongs to assertion rendering (`golden_assert_line` emits an order-independent form),
    not here. What the two calls DO catch is genuine instability, including an id-bearing
    repr (``<Foo object at 0x…>``), where two calls build two objects and disagree."""
    call_args = tuple(unwrap(a) for a in args)
    call_kwargs = {k: unwrap(v) for k, v in kwargs.items()}
    _install_open_watch()
    # block=True: a transitive/default-path WRITE is prevented, not just recorded — so a speculative
    # capture of a tree-mutating function (issue #30) cannot litter the consumer's checkout.
    sink = _EffectSink(block=True)
    token = _OPEN_WATCH.set(sink)
    # Freeze the whole time-module clock family (#24 increment 1), not only `time.time`, so a function
    # reading `monotonic()`/`perf_counter()` for a TTL/elapsed check is deterministic too — the same
    # plan `render_clock_freeze` emits into the test.
    _clock_saved = apply_clock(clock, namespace) if clock is not None else None
    # Apply the declared environment (#48) BEFORE the recording proxy wraps os.environ, so the
    # captured function reads the DECLARED values and those reads are still recorded; restored in
    # `finally` after the proxy is off, so a declared var never leaks into a later capture.
    _env_applied = apply_env(env) if env else None
    # Proxy `os.environ` for the duration of the call so a read is observed at whatever depth and
    # under whatever spelling it happens. Restored in `finally` alongside the clock: leaving the
    # proxy installed would make every later capture record the previous one's reads.
    _env_saved = os.environ
    # noqa B003: the rule warns that this does not CLEAR the process environment — which is
    # exactly the requirement. The proxy is a recording VIEW over the same `_data`, so the
    # captured function sees the real environment and `putenv` stays in step.
    os.environ = _RecordingEnviron(_env_saved, sink)  # type: ignore[assignment] # noqa: B003
    blocked_write = False
    clock_dependent = False
    try:
        result = func(*call_args, **call_kwargs)
        first = repr(result)
        second = repr(func(*call_args, **call_kwargs))
        if clock is None:
            # No freeze is planned for the emitted test, so any clock dependence is unpinnable —
            # `date.today()` one helper down pinned today's date and the suite began failing the
            # next morning. Replaying under a distant epoch OBSERVES that: the two calls above
            # cannot, because both ran at the same moment. When `clock` IS set the emitted test
            # freezes the clock itself, so movement is pinned rather than refused, and this is skipped.
            with contextlib.suppress(Exception):
                _probe_saved = apply_clock(_PERTURBED_EPOCH, namespace)
                try:
                    clock_dependent = repr(func(*call_args, **call_kwargs)) != first
                finally:
                    restore_clock(_probe_saved)
    except _CaptureWriteBlocked:
        blocked_write = True
    except Exception:
        return None
    finally:
        os.environ = _env_saved  # type: ignore[assignment] # noqa: B003
        if _clock_saved is not None:
            restore_clock(_clock_saved)  # restore — the freeze must never outlive the capture
        if _env_applied is not None:
            restore_env(_env_applied)  # restore the real env exactly, now the proxy is off
        _OPEN_WATCH.reset(token)
    if blocked_write:
        # A tree-mutating function is not golden-capturable; the write was prevented (no litter),
        # and the attempt is surfaced so the refusal names it rather than reading as a bare drop.
        return GoldenCapture(
            inputs=args,
            kwargs=dict(kwargs),
            deterministic=False,
            filesystem_writes=tuple(dict.fromkeys(sink.writes)),
            clock=clock,
            env=env,
        )
    return GoldenCapture(
        inputs=args,
        kwargs=dict(kwargs),
        output=first,
        value=result,
        deterministic=first == second,
        environment_paths=_environment_paths(sink.opened, call_args, call_kwargs),
        # A DECLARED env var (via ``--env``, #48) is COVERED: the emitted test re-applies it, so its
        # read is not the CI-dependence #23 refuses over — drop it from the reads the disposition
        # gates on. An UNDECLARED read stays, and is still refused, which is the sound abstain: a
        # certificate must not silently depend on a var the capability set does not name.
        environment_reads=tuple(
            n for n in dict.fromkeys(sink.env_reads) if n not in {name for name, _ in env}
        ),
        clock_dependent=clock_dependent,
        clock=clock,
        env=env,
    )


def _corroborate(cap: GoldenCapture, lens: str) -> GoldenCapture:
    """Re-stamp provenance, carrying every other field. ``replace`` rather than a
    field-by-field rebuild: the rebuild silently dropped whatever it did not enumerate, so
    a field added to GoldenCapture arrived as None here — for ``value`` that meant the
    assertion renderer could not tell a set from an object and shipped a flaky repr
    assertion for every CORROBORATED capture."""
    return replace(cap, provenance=Provenance.CORROBORATED, corroborating_lens=lens)


def _docstring(cap: GoldenCapture) -> str:
    if cap.provenance == Provenance.CORROBORATED:
        return f'"""Golden capture — corroborated via {cap.corroborating_lens}."""'
    if cap.provenance == Provenance.PROVISIONAL:
        return '"""Golden capture — PROVISIONAL (may fossilize bugs)."""'
    return '"""Golden capture — unchecked."""'


def _call_args(cap: GoldenCapture) -> str:
    parts = [repr(a) for a in cap.inputs]
    parts += [f"{k}={v!r}" for k, v in cap.kwargs.items()]
    return ", ".join(parts)


def _contains_set(value: Any) -> bool:
    """True if ``value`` is, or nests, a set/frozenset — whose repr order is not
    stable across processes. Dataclass instances nest their field values: a repr
    like ``_Flow(uses=frozenset({...}))`` embeds the set's unstable order."""
    if isinstance(value, (set, frozenset)):
        return True
    if isinstance(value, dict):
        return any(_contains_set(k) or _contains_set(v) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return any(_contains_set(v) for v in value)
    if is_dataclass(value) and not isinstance(value, type):
        return any(_contains_set(getattr(value, f.name)) for f in dataclass_fields(value))
    return False


def machine_specific_probe_hit(text: str, probes: tuple[str, ...]) -> str:
    """The first probe substring that makes ``text`` specific to ONE machine, or "" (#30, pure).

    Split from ``_is_machine_specific`` so the decision can be pinned at all: that function reads
    ``os.getcwd()`` / ``expanduser("~")`` / ``sys.prefix`` / the temp dir at call time, so its
    answer depends on the environment it runs in and no ``--input`` can state it. Taking the
    probes as an argument moves the whole rule inside a literal grammar; the accessor below
    supplies today's environment and holds no decision of its own.

    Returns the OFFENDING PROBE rather than a bool, so a refusal can name what made the value
    unportable ("contains /Users/<you>") instead of asserting unportability without evidence.
    "" is the portable answer.

    The length floor is not a nicety. A probe of "/" or "" is a substring of nearly every path,
    and with one in the list every captured string on earth becomes machine-specific and the
    golden path refuses everything — a guard that fires always is as useless as one that never
    fires, and strictly more annoying. Substrings of the REAL environment are what is checked,
    never a path SHAPE: `/etc/hosts` is identical on every machine and stays pinnable.
    """
    for probe in probes:
        if probe and len(probe) > 3 and probe in text:
            return probe
    return ""


def _is_machine_specific(text: str) -> bool:
    """True when a captured string carries a value specific to THIS machine/checkout — it contains
    the current working directory, the user home, the interpreter prefix, or the temp dir. A golden
    pinned to such a value (a `Path.resolve()` / `os.getcwd()` / `__file__` result baked into a
    return) is green on this checkout and red on any other, INDEPENDENT of whether any I/O happened
    — the door #23's default-path-I/O guard does not cover. Substrings of the real environment, not
    a path SHAPE: a stable absolute path that is identical on every machine (`/etc/hosts`) is fine
    to pin; only paths that differ per machine are refused, so the guard never false-flags data."""
    return bool(machine_specific_probe_hit(text, machine_probes()))


def machine_probes() -> tuple[str, ...]:
    """This machine's identifying path prefixes, as the substrings a capture might carry."""
    return (
        os.getcwd(),
        os.path.expanduser("~"),
        sys.prefix,
        tempfile.gettempdir(),
    )


def _stable_expr(value: Any) -> str | None:
    """A Python expression that reconstructs ``value`` with order-STABLE source text,
    or None when no such expression exists (a non-literal element). Sets are the one
    order-unstable repr; render them from SORTED element expressions so the emitted
    text cannot depend on the hash seed. Everything else round-trips through
    ``literal_eval`` or abstains — an expression this cannot build is a value this
    must not pin."""
    if isinstance(value, (set, frozenset)):
        elems = [_stable_expr(v) for v in value]
        if any(e is None for e in elems):
            return None
        if not elems:
            return "frozenset()" if isinstance(value, frozenset) else "set()"
        inner = "{" + ", ".join(sorted(e for e in elems if e is not None)) + "}"
        return f"frozenset({inner})" if isinstance(value, frozenset) else inner
    if isinstance(value, tuple):
        elems = [_stable_expr(v) for v in value]
        if any(e is None for e in elems):
            return None
        return "(" + ", ".join(e for e in elems if e is not None) + ("," if len(elems) == 1 else "") + ")"
    if isinstance(value, list):
        elems = [_stable_expr(v) for v in value]
        if any(e is None for e in elems):
            return None
        return "[" + ", ".join(e for e in elems if e is not None) + "]"
    if isinstance(value, dict):
        items = [(_stable_expr(k), _stable_expr(v)) for k, v in value.items()]
        if any(k is None or v is None for k, v in items):
            return None
        return "{" + ", ".join(f"{k}: {v}" for k, v in items) + "}"
    if isinstance(value, str) and _is_machine_specific(value):
        return None  # a golden pinned to this machine's paths is green here, red elsewhere (#30)
    rendered = repr(value)
    try:
        round_tripped = ast.literal_eval(rendered)
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        return None
    # equality, not identity: a repr that parses but does not reproduce the value
    # (nan) is as unusable as one that does not parse
    return rendered if round_tripped == value else None


def golden_assert_line(output_repr: str, value: Any = None) -> str | None:
    """Pin ``result`` to its captured output with idiomatic VALUE equality
    (``result == <literal>``) — the way a developer actually writes a test. It reads
    cleanly and is order-independent for sets. It is TYPE-BLIND where repr is not
    (``1 == 1.0``, ``True == 1``): call-unwrap (``int(x)`` -> ``x``) and TYPE operators DO
    produce value-equal, repr-distinct outcomes, so a witness whose only distinction is
    the type needs the companion pins from :func:`distinction_pin_lines` — the ``==``
    line alone would be written, kill nothing, and be minimized away forever.

    The three singletons take ``is``: ``== True`` / ``== False`` / ``== None`` are ruff
    E712/E711, and a consumer that lints the tests we write (this project does) would
    reject a suite we emitted. ``is`` is also the stricter pin — identity with the
    singleton, not merely equality with it (``1 == True``).

    A NON-literal repr (an object) has no value-equality form, and repr-equality is sound
    for it — EXCEPT for a set, whose repr order follows element hashes and so differs
    between the capture process and the process that later runs the test. That case is
    neither literal nor order-stable, and pinning it by repr ships a test that passes or
    fails on the hash seed. Comparing the SORTED element reprs is order-independent and
    needs no constructor source for the elements. ``value`` is the result itself: the repr
    string alone cannot answer "is this a set", which is why it is threaded here.
    """
    # THE ONE PLACE that decides whether a captured value may be pinned by equality at all.
    # None means "not pinnable", and every producer must handle it — which is the point of
    # putting it here rather than in each of them. There are two producers (a capture, and a
    # distinguishing witness from the equivalence search) and they both funnel through this
    # function; a guard bolted onto one of them is how a machine-specific golden shipped from
    # the other while the capture path was correctly refusing it (#30).
    #
    # A value carrying THIS checkout's paths is green here and red everywhere else, and no I/O
    # need have happened for that to be true — `Path(x).resolve()` in a returned string is
    # enough. `_is_machine_specific` existed for exactly this but was reachable only from
    # `_stable_expr`, which the branch below consults ONLY for non-literal reprs; a plain
    # string is a literal, so it took the fast path and never met the guard.
    if machine_specific_probe_hit(output_repr, machine_probes()):
        return None

    try:
        ast.literal_eval(output_repr)
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        # Elements that themselves nest a set have unstable reprs of their own, so sorting
        # them does not recover stability — leave those on the repr form rather than emit a
        # different flaky assertion dressed as a fix.
        if isinstance(value, (set, frozenset)) and not any(_contains_set(v) for v in value):
            return f"assert sorted(map(repr, result)) == {sorted(map(repr, value))!r}"
        if _contains_set(value):
            # The repr embeds a set's unstable order somewhere INSIDE a non-literal
            # shell — a dataclass with frozenset fields, a list of frozensets. Pin by
            # value equality against an order-stable reconstruction; for a dataclass,
            # field access reaches the values without needing its constructor imported.
            if is_dataclass(value) and not isinstance(value, type):
                dc_fields = dataclass_fields(value)
                exprs = [_stable_expr(getattr(value, f.name)) for f in dc_fields]
                if dc_fields and all(e is not None for e in exprs):
                    names = ", ".join(f"result.{f.name}" for f in dc_fields)
                    vals = ", ".join(e for e in exprs if e is not None)
                    if len(dc_fields) == 1:
                        return f"assert {names} == {vals}"
                    return f"assert ({names}) == ({vals})"
            stable = _stable_expr(value)
            if stable is not None:
                return f"assert result == {stable}"
        return f"assert repr(result) == {output_repr!r}"
    if output_repr in ("True", "False", "None"):
        return f"assert result is {output_repr}"
    return f"assert result == {output_repr}"


def distinction_pin_lines(original_value: Any, mutant_repr: str) -> list[str]:
    """Assertion lines pinning a distinction ``==`` cannot see — type first, repr second.

    The classifier's distinguishability relation is repr-based (``_outcome``); the golden
    assertion is ``==``-based. A mutant whose outcome is ``==``-equal to the original's yet
    repr-distinct — ``1`` vs ``1.0`` from call-unwrap, ``True`` vs ``1``, ``-0.0`` vs ``0.0`` —
    is killable by witness but unpinnable by ``==``: the witness test is written, kills
    nothing, is minimized away as zero-marginal, and the survivor is re-witnessed forever.
    These lines restore the invariant that every distinction the classifier can observe,
    the writer can assert.

    Returns pins ONLY when the two outcomes compare equal overall (otherwise the golden
    ``==`` line already kills), walking containers to each distinguishing leaf: a type
    difference pins ``type(<leaf>) is <T>`` (``type() is``, not ``isinstance`` — ``True``
    would satisfy ``isinstance(_, int)``); a same-type repr difference pins the leaf's
    ``repr``. Empty when the mutant outcome is not a parseable literal (a raised-marker,
    an object repr) — those paths have their own forms and owe nothing here.
    """
    try:
        mutant_value = ast.literal_eval(mutant_repr)
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        return []
    try:
        if original_value != mutant_value:
            return []
    except Exception:  # noqa: BLE001 — un-comparable values cannot loop the == path either
        return []
    pins: list[str] = []
    _walk_distinction(original_value, mutant_value, "result", pins)
    return pins


def _walk_distinction(orig: Any, mut: Any, path: str, pins: list[str]) -> None:
    """Descend ``==``-equal structures; pin each leaf where type or repr still differs."""
    if type(orig) is not type(mut):
        pins.append(f"assert type({path}) is {type(orig).__name__}")
        return
    if isinstance(orig, dict):
        for key in orig:
            if key in mut:
                _walk_distinction(orig[key], mut[key], f"{path}[{key!r}]", pins)
        return
    if isinstance(orig, (list, tuple)):
        for i, (a, b) in enumerate(zip(orig, mut, strict=False)):  # == already proved equal length
            _walk_distinction(a, b, f"{path}[{i}]", pins)
        return
    if repr(orig) != repr(mut):
        pins.append(f"assert repr({path}) == {repr(orig)!r}")
