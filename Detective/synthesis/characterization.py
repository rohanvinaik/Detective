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
import time
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass, field, is_dataclass, replace
from dataclasses import fields as dataclass_fields
from enum import StrEnum
from typing import Any

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
    # The wall-clock value `time.time()` was FROZEN to for this capture (the `--clock` residual
    # for a time-gated function), or None if the clock ran free. A frozen clock is what makes a
    # `time.time()`-reading function DETERMINISTIC — hence capturable and pinnable — and the
    # emitted test restores `time.time` in a `finally` so the freeze never leaks to another test.
    clock: float | None = None


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
    func: Callable[..., Any], call_site_inputs: list[dict], clock: float | None = None
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
        capture = _try_capture(func, args, kwargs, clock=clock)
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

_OPEN_WATCH: ContextVar[list[str] | None] = ContextVar("detective_open_watch", default=None)
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


def _open_watch_hook(event: str, args: tuple) -> None:
    if event not in _FS_EFFECT_EVENTS:
        return
    sink = _OPEN_WATCH.get()
    if sink is None:
        return
    target = args[0]
    if isinstance(target, (str, bytes, os.PathLike)):
        with contextlib.suppress(TypeError, UnicodeDecodeError):
            sink.append(os.fsdecode(target))


def _install_open_watch() -> None:
    global _watch_installed
    if not _watch_installed:
        sys.addaudithook(_open_watch_hook)
        _watch_installed = True


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


def _try_capture(
    func: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any], clock: float | None = None
) -> GoldenCapture | None:
    """Call ``func`` twice; capture repr + determinism, or None if it raises.

    Arguments are unwrapped for the call so a synthesized ``SourceExpr`` (an AST
    node paired with its source) runs as its live value; the original args — carrier
    intact — are stored on the capture so the emitted test renders as ``repr`` =
    the constructor source, not an opaque object repr.

    ``clock`` freezes ``time.time`` to a fixed value across both calls (restored in ``finally``,
    so no leak). This is what turns a wall-clock reader deterministic: without it the two calls
    disagree and the capture is dropped. Only ``time.time`` is frozen (v1 of the `--clock`
    residual); ``time.monotonic`` / ``datetime.now`` are follow-ups. Reaches a function that calls
    ``time.time()`` on the module (``import time; time.time()``); a ``from time import time`` local
    binding keeps its own reference and is a documented miss.

    ``deterministic`` asks whether the VALUE is stable, and compares reprs to decide. Both
    calls share one process, so this cannot observe hash-seed effects — which is correct,
    not a gap: a set's repr ORDER varies across processes while its value does not, so it
    belongs to assertion rendering (`golden_assert_line` emits an order-independent form),
    not here. What the two calls DO catch is genuine instability, including an id-bearing
    repr (``<Foo object at 0x…>``), where two calls build two objects and disagree."""
    call_args = tuple(unwrap(a) for a in args)
    call_kwargs = {k: unwrap(v) for k, v in kwargs.items()}
    _install_open_watch()
    opened: list[str] = []
    token = _OPEN_WATCH.set(opened)
    saved_time = time.time if clock is not None else None
    try:
        if clock is not None:
            time.time = lambda: clock  # freeze the wall clock -> the function is now deterministic
        result = func(*call_args, **call_kwargs)
        first = repr(result)
        second = repr(func(*call_args, **call_kwargs))
    except Exception:
        return None
    finally:
        if saved_time is not None:
            time.time = saved_time  # restore — the freeze must never outlive the capture
        _OPEN_WATCH.reset(token)
    return GoldenCapture(
        inputs=args,
        kwargs=dict(kwargs),
        output=first,
        value=result,
        deterministic=first == second,
        environment_paths=_environment_paths(opened, call_args, call_kwargs),
        clock=clock,
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


def _is_machine_specific(text: str) -> bool:
    """True when a captured string carries a value specific to THIS machine/checkout — it contains
    the current working directory, the user home, the interpreter prefix, or the temp dir. A golden
    pinned to such a value (a `Path.resolve()` / `os.getcwd()` / `__file__` result baked into a
    return) is green on this checkout and red on any other, INDEPENDENT of whether any I/O happened
    — the door #23's default-path-I/O guard does not cover. Substrings of the real environment, not
    a path SHAPE: a stable absolute path that is identical on every machine (`/etc/hosts`) is fine
    to pin; only paths that differ per machine are refused, so the guard never false-flags data."""
    for probe in (os.getcwd(), os.path.expanduser("~"), sys.prefix, tempfile.gettempdir()):
        if probe and len(probe) > 3 and probe in text:
            return True
    return False


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


def golden_assert_line(output_repr: str, value: Any = None) -> str:
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
