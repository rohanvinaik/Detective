"""The budget bank — deterministic cost reads for the efficiency axis (Wave 2 / EXP-DS-003).

Design: ``docs/theory/deterministic_sicp/DETERMINISTIC_SICP.md`` §7. Determinism is the product,
so the efficiency observable is never wall-clock: it is a **countable budget** — here, opcodes
executed at the Python frame level — read on fixed synthesized inputs and along a **size ladder**
whose fitted growth class is the bank's asymptotic read. Every efficiency claim is PAIRED
(candidate vs incumbent on identical inputs) under the two-ledger law: behavior-delta must be
exactly 0 before a budget number may mean anything (`paired_disposition` — the gate owns
validity; the budget is the payoff).

**The counter's stated boundary:** opcode counts measure PYTHON-level work. Work done inside C
(builtins, C-extension methods) executes no Python opcodes and is invisible to this counter —
so a read is comparable only between arms of the same language level, and the detail must say
"opcodes", never "cost". The allocation axis is deferred (recorded in the paper), not folded in.

Pure decisions (`growth_class`, `budget_verdict`, `paired_disposition`, `ladder_value`) are what
Detective pins; `count_opcodes` is the impure instrument shell (installs/restores a trace hook),
guarded by the unit suite — the sanctioned exemption class for instrumentation.
"""

from __future__ import annotations

import math
import sys
from collections.abc import Callable

# The growth-class boundaries — the measurement's stated parameters, not truths. Log-log tail
# slope m maps to a COARSE named band; n·log n sits in "linear" at these widths (stated, not
# hidden — a finer separation needs a wider ladder than this instrument runs).
_SLOPE_CONSTANT = 0.10
_SLOPE_SUBLINEAR = 0.75
_SLOPE_LINEAR = 1.25
_SLOPE_SUPERLINEAR = 1.75

# The paired-read parity band (stated): a same-class count ratio within ±10% is "parity" —
# below it a refund, above it a regression.
_RATIO_REFUND = 0.9
_RATIO_REGRESSION = 1.1


def growth_class(sizes: list[float], counts: list[float]) -> str:
    """The size-ladder asymptotic read (pure — pinned): fit the log-log slope of counts against
    sizes and name the COARSE growth band. Named codes, never a number a caller re-bins:

      "unmeasurable"     fewer than 3 points, mismatched lengths, a non-increasing size, or a
                         non-positive count — cannot-determine, never a fabricated class
      "constant"         tail slope < 0.10   (the size does not buy work)
      "sublinear"        tail slope < 0.75
      "linear"           tail slope < 1.25   (n·log n lands here at this instrument's width — stated)
      "superlinear"      tail slope < 1.75
      "quadratic_plus"   tail slope ≥ 1.75

    The slope is the MEDIAN of consecutive log-log slopes over the ladder's TAIL (the last half,
    at least two slopes) — the asymptotic regime, so small-size warmup noise cannot name the band.
    """
    n = len(sizes)
    if n < 3 or len(counts) != n:
        return "unmeasurable"
    for i in range(n - 1):
        if sizes[i + 1] <= sizes[i]:
            return "unmeasurable"
    if any(c <= 0 for c in counts) or any(s <= 0 for s in sizes):
        return "unmeasurable"
    slopes = [math.log(counts[i + 1] / counts[i]) / math.log(sizes[i + 1] / sizes[i]) for i in range(n - 1)]
    tail = slopes[-max(2, len(slopes) // 2) :]
    m = sorted(tail)[len(tail) // 2]
    if m < _SLOPE_CONSTANT:
        return "constant"
    if m < _SLOPE_SUBLINEAR:
        return "sublinear"
    if m < _SLOPE_LINEAR:
        return "linear"
    if m < _SLOPE_SUPERLINEAR:
        return "superlinear"
    return "quadratic_plus"


_CLASS_ORDER = ("constant", "sublinear", "linear", "superlinear", "quadratic_plus")


def budget_verdict(incumbent_class: str, candidate_class: str, count_ratio_at_max: float) -> str:
    """The paired budget read (pure — pinned): candidate against incumbent. Named codes:

      "unmeasurable"  either growth class is unmeasurable, or the ratio is non-positive
      "refund"        a strictly better growth class — or the same class at a ratio below the
                      parity band (candidate/incumbent ≤ 0.9 at the ladder top)
      "regression"    a strictly worse class, or the same class above the band (≥ 1.1)
      "parity"        the same class inside the band — the honest "no payoff measured"

    Class dominates ratio on purpose: a better asymptotic band at a worse small-n constant is
    still a refund at scale, and the two must not blur into one number.
    """
    if incumbent_class not in _CLASS_ORDER or candidate_class not in _CLASS_ORDER or count_ratio_at_max <= 0:
        return "unmeasurable"
    inc, cand = _CLASS_ORDER.index(incumbent_class), _CLASS_ORDER.index(candidate_class)
    if cand < inc:
        return "refund"
    if cand > inc:
        return "regression"
    if count_ratio_at_max <= _RATIO_REFUND:
        return "refund"
    if count_ratio_at_max >= _RATIO_REGRESSION:
        return "regression"
    return "parity"


def paired_disposition(delta_zero: bool, verdict: str) -> str:
    """The two-ledger law as one pure decision (pinned): a budget verdict may mean something
    ONLY under a behavior-delta of exactly 0. ``delta_zero=False`` → "inadmissible" — an
    optimization that changes behavior is not an optimization, whatever its counts say (the
    proof gate owns validity; the budget is only ever the payoff). Otherwise the verdict passes
    through untouched — this function adds no opinion of its own."""
    return verdict if delta_zero else "inadmissible"


def ladder_value(kind: str, size: int):
    """A sized instance of an expressible input kind (pure — pinned): the size-ladder's input
    builder, deliberately covering only the `--input`-expressible scalar/container kinds (the
    same allowlist boundary the rest of the tool draws; a domain object has no mechanical
    ladder). Deterministic content — no randomness anywhere in a budget read. Returns ``None``
    for an unknown kind or a non-positive size (cannot-determine, never a guessed value).
    Kinds: "int" (magnitude), "str", "list[int]", "list[str]", "set[int]", "dict[str,int]".
    A future wave may consolidate this with the synthesis stack's typed grids; today that stack
    builds single representative values, not sized ladders, so this stays beside its consumer."""
    if size <= 0:
        return None
    if kind == "int":
        return 10**size
    if kind == "str":
        return "ab" * (size // 2) + "a" * (size % 2)
    if kind == "list[int]":
        return [i % 7 for i in range(size)]
    if kind == "list[str]":
        return [f"k{i % 11}" for i in range(size)]
    if kind == "set[int]":
        return set(range(size))
    if kind == "dict[str,int]":
        return {f"k{i}": i for i in range(size)}
    return None


def count_opcodes(fn: Callable, args: tuple) -> int | None:
    """The deterministic operation counter (impure instrument shell — unit-guarded, not pinned):
    the number of Python-level instructions executed while ``fn(*args)`` runs, via
    ``sys.monitoring`` INSTRUCTION events (the 3.12+ API; the legacy ``f_trace_opcodes`` path
    stopped delivering opcode events on 3.14 — measured, which is why this instrument is built
    on the modern surface). Deterministic for deterministic code on fixed inputs — the property
    wall-clock never has — and comparable BETWEEN arms measured by the same interpreter, never
    across Python versions (the instruction stream is an interpreter detail; the read includes
    a small constant enable/disable overhead, identical across arms).

    Honest failure modes, all ``None`` (cannot-determine): an interpreter without
    ``sys.monitoring`` (the API is 3.12+; the package floor is 3.11, so on 3.11 the instrument
    ABSTAINS — never a crash, never a fallback to a counter measured broken), no free monitoring
    tool slot (a debugger/coverage/profiler may hold them all), or the call raising — a crashed
    arm has no budget read, and the caller's delta gate is already red. The slot is released in
    ``finally`` so a surrounding session's own monitoring always survives the instrument."""
    mon = getattr(sys, "monitoring", None)
    if mon is None:
        return None
    tool = None
    for candidate in (5, 4, 3, 2):
        try:
            mon.use_tool_id(candidate, "detective-budget-counter")
            tool = candidate
            break
        except ValueError:
            continue
    if tool is None:
        return None

    count = 0

    def on_instruction(_code, _offset):
        nonlocal count
        count += 1

    mon.register_callback(tool, mon.events.INSTRUCTION, on_instruction)
    mon.set_events(tool, mon.events.INSTRUCTION)
    try:
        fn(*args)
    except Exception:  # noqa: BLE001 — a crashed arm reads None; the delta gate reports it
        return None
    finally:
        mon.set_events(tool, 0)
        mon.register_callback(tool, mon.events.INSTRUCTION, None)
        mon.free_tool_id(tool)
    return count
