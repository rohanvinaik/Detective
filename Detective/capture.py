"""Runtime harvest of REAL argument tuples from the tests that already cover a
function — the honest input source when a parameter is a domain object that no
deterministic synthesis can fabricate.

Detective never *guesses* a structured input (that would undercut the abstention,
which is a feature: a fabricated input can only ever produce a spurious verdict).
Instead, when synthesis provably can't build a valid input, it reuses one the
covering tests genuinely pass: a ``sys.setprofile`` hook records the bound
positional arguments at every entry to the target's code object while the
discovered test callables run, and those real tuples feed the witness search.
Discovery proposes; the soundness gate in ``classify_survivors`` disposes (an
input that doesn't fit just raises and is dropped).
"""

from __future__ import annotations

import contextlib
import io
import sys
import time
from collections.abc import Callable
from typing import Any

HARVEST = "harvest"  # run the next test
HARVEST_ENOUGH = "enough"  # the pool is full — a completed harvest, whatever the wall says
HARVEST_CUT = "cut"  # the aggregate wall has passed — stop, keep what was captured


def harvest_disposition(have_enough: bool, deadline_passed: bool) -> str:
    """Whether the capture harvest runs the NEXT test (pure — pinned). Named codes:

      "enough"   — ``max_samples`` distinct inputs are already captured: stop; the pool is full and a
                   full pool is a completed harvest, checked FIRST so a late wall never voids it
      "cut"      — the aggregate command wall (an absolute monotonic deadline) has passed: stop and
                   keep what was captured — a partial harvest is honest, an overrun is not
      "harvest"  — run it

    Checked BETWEEN tests, never inside one. The wall is a BACKSTOP on the sequence; the BOUND on the
    sequence is applicability (`engine._applicable_harvest_pool`): only tests with a static path to
    the target are handed here at all, because only a test that reaches the function can capture its
    inputs. Before this, the harvest ran every collected test with no check anywhere — a 51-minute
    silent witness pass on a four-parameter function (2026-09-05), the wall it was under long gone.
    """
    if have_enough:
        return HARVEST_ENOUGH
    if deadline_passed:
        return HARVEST_CUT
    return HARVEST


def _run_for_effects(test: Callable[..., Any]) -> None:
    """Run one discovered test for its SIDE EFFECTS on the active profile hook — the harvest wants
    the calls it makes, never its verdict. A failing, erroring or skipped test is swallowed
    (pytest's ``Skipped``/``Failed`` derive from ``BaseException``, so ``Exception`` is too narrow);
    the operator's interrupt is the one thing that is never swallowed.
    """
    try:
        test()
    except (KeyboardInterrupt, SystemExit):
        raise
    # BLE001: the harvest swallows a test's verdict and never the operator's interrupt
    except BaseException:  # noqa: BLE001
        pass


def capture_call_inputs(
    original: Callable[..., Any],
    tests: list[Callable[..., Any]],
    *,
    max_samples: int = 12,
    deadline: float | None = None,
) -> list[tuple]:
    """Real positional-argument tuples observed at every call to ``original`` while
    ``tests`` run, deduplicated by value and capped at ``max_samples``.

    Keyed on the function's *code object* via ``sys.setprofile``, so a call is
    captured regardless of how the test imported the target (``import mod`` then
    ``mod.fn(...)`` vs ``from mod import fn``): the frame's bound parameters at
    entry are the ground truth, not a re-derived reference. Only the positional
    parameters (``co_varnames[:co_argcount]``, which includes ``self`` for a
    method) are read, matching how the witness search splats a tuple.

    Empty when the tests never reach the function — in which case the caller keeps
    abstaining, the honest Zone-3 'provide a sample'. A failing or erroring test is
    swallowed: we want the *inputs* it passes, not its pass/fail verdict.

    ``deadline`` (absolute monotonic seconds, the caller's aggregate wall) is checked BETWEEN tests
    by :func:`harvest_disposition`: once it has passed no further test is run and what was captured
    is returned. It is the backstop; the caller bounds ``tests`` to the applicable set first.
    """
    code = getattr(original, "__code__", None)
    if code is None or not tests:
        return []
    names = code.co_varnames[: code.co_argcount]
    captured: list[tuple] = []
    seen: set[str] = set()

    def _hook(frame: Any, event: str, _arg: Any) -> None:
        # Fires for every Python call while active; cheap-reject everything that is
        # not an entry to the exact target code object.
        if event != "call" or frame.f_code is not code:
            return
        loc = frame.f_locals
        try:
            args = tuple(loc[n] for n in names)
            key = repr(args)
        # BLE001: an unrepr-able/odd arg is simply not harvested
        except Exception:  # noqa: BLE001
            return
        if key in seen:
            return
        seen.add(key)
        captured.append(args)

    prev = sys.getprofile()
    # Isolate the discovered tests' own stdout/stderr the way Wesker's runner does,
    # so a consumer test's prints/banners never pollute Detective's report.
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        sys.setprofile(_hook)
        try:
            for t in tests:
                if (
                    harvest_disposition(
                        len(captured) >= max_samples,
                        deadline is not None and time.monotonic() >= deadline,
                    )
                    != HARVEST
                ):
                    break
                _run_for_effects(t)
        finally:
            sys.setprofile(prev)
    return captured[:max_samples]


def capture_return_types(
    original: Callable[..., Any],
    tests: list[Callable[..., Any]],
    *,
    max_samples: int = 24,
) -> frozenset[str]:
    """The set of type NAMES of values the target RETURNS while ``tests`` run — the observed
    codomain for μ⁻ Fork 2 (the two-sign contract's type-conditional output perturbations).

    Sibling of :func:`capture_call_inputs`: the same ``sys.setprofile`` hook keyed on the target's
    code object, but harvesting on the ``return`` event, where the hook's ``arg`` is the returned
    object. Keying on the exact ``type(x).__name__`` is deliberate — a ``bool`` return reads as
    ``"bool"``, not ``"int"``, so a numeric perturbation (``-x``) is never emitted for it (the
    silent-coercion hole Fork 1 could not close, closed here by observation).

    Empty when the tests never reach the function or it only ever returns ``None`` — the honest
    'codomain unobserved', in which case only the always-applicable Fork-1 perturbations apply and
    the type-conditional dimensions are simply not generated.
    """
    code = getattr(original, "__code__", None)
    if code is None or not tests:
        return frozenset()
    names: set[str] = set()

    def _hook(frame: Any, event: str, arg: Any) -> None:
        # `arg` is the returned value on a 'return' event; a raise or a bare `return` gives None,
        # which carries no codomain type to condition on (existence is Fork 1's return_none).
        if event != "return" or frame.f_code is not code or arg is None:
            return
        names.add(type(arg).__name__)

    prev = sys.getprofile()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        sys.setprofile(_hook)
        try:
            for t in tests:
                if len(names) >= max_samples:
                    break
                _run_for_effects(t)
        finally:
            sys.setprofile(prev)
    return frozenset(names)
