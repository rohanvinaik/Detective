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
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..equivalence import unwrap


class Provenance(str, Enum):
    """Maturity of a characterization capture."""

    UNCHECKED = "unchecked"
    PROVISIONAL = "provisional"
    CORROBORATED = "corroborated"


@dataclass(frozen=True)
class GoldenCapture:
    """A captured golden value for one function invocation."""

    inputs: tuple[Any, ...]
    kwargs: dict[str, Any] = field(default_factory=dict)
    output: str = ""  # repr of the result
    deterministic: bool = False
    provenance: Provenance = Provenance.PROVISIONAL
    corroborating_lens: str = ""


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


def capture_golden(func: Callable[..., Any], call_site_inputs: list[dict]) -> list[GoldenCapture]:
    """Capture golden values for ``func`` from zero-arg and literal call sites.

    Each candidate invocation is run twice; a stable repr marks the capture
    deterministic. Duplicate argument sets are captured once. Invocations that
    raise are skipped.
    """
    captures: list[GoldenCapture] = []
    seen: set[str] = set()

    for args, kwargs in _candidate_inputs(call_site_inputs):
        key = repr((args, kwargs))
        if key in seen:
            continue
        seen.add(key)
        capture = _try_capture(func, args, kwargs)
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
        lines.append(f"    {golden_assert_line(cap.output)}{tag}")
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


def _try_capture(
    func: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]
) -> GoldenCapture | None:
    """Call ``func`` twice; capture repr + determinism, or None if it raises.

    Arguments are unwrapped for the call so a synthesized ``SourceExpr`` (an AST
    node paired with its source) runs as its live value; the original args — carrier
    intact — are stored on the capture so the emitted test renders as ``repr`` =
    the constructor source, not an opaque object repr."""
    call_args = tuple(unwrap(a) for a in args)
    call_kwargs = {k: unwrap(v) for k, v in kwargs.items()}
    try:
        first = repr(func(*call_args, **call_kwargs))
        second = repr(func(*call_args, **call_kwargs))
    except Exception:
        return None
    return GoldenCapture(inputs=args, kwargs=dict(kwargs), output=first, deterministic=first == second)


def _corroborate(cap: GoldenCapture, lens: str) -> GoldenCapture:
    return GoldenCapture(
        inputs=cap.inputs,
        kwargs=cap.kwargs,
        output=cap.output,
        deterministic=cap.deterministic,
        provenance=Provenance.CORROBORATED,
        corroborating_lens=lens,
    )


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
    stable across processes."""
    if isinstance(value, (set, frozenset)):
        return True
    if isinstance(value, dict):
        return any(_contains_set(k) or _contains_set(v) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return any(_contains_set(v) for v in value)
    return False


def _order_sensitive(output_repr: str) -> bool:
    """True when the captured output is a literal that contains a set/frozenset.

    A ``repr(result) == "<str>"`` assertion is FLAKY for such outputs: set repr
    order depends on the hash seed, which differs between the capture process and
    the process that later runs the test. Non-literal reprs (objects) are treated as
    order-stable — their repr is what it is, and value equality is not available."""
    try:
        return _contains_set(ast.literal_eval(output_repr))
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        return False


def golden_assert_line(output_repr: str) -> str:
    """Pin ``result`` to its captured output with idiomatic VALUE equality
    (``result == <literal>``) — the way a developer actually writes a test. It reads
    cleanly, is order-independent for sets, and loses NO kill power: no mutation operator
    produces a result that is value-equal to the original yet a different type (VALUE
    mutates a constant to a same-type constant; the rest change the value), so ``==``
    catches exactly what the old ``repr(result) == "<str>"`` form did. Falls back to repr
    equality only for a non-literal repr (an object), where value equality is unavailable."""
    try:
        ast.literal_eval(output_repr)
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        return f"assert repr(result) == {output_repr!r}"
    return f"assert result == {output_repr}"
