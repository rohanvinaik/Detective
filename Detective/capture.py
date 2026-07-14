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
from collections.abc import Callable
from typing import Any


def capture_call_inputs(
    original: Callable[..., Any],
    tests: list[Callable[..., Any]],
    *,
    max_samples: int = 12,
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
        except Exception:  # noqa: BLE001 — an unrepr-able/odd arg is simply not harvested
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
                if len(captured) >= max_samples:
                    break
                try:
                    t()
                except BaseException:  # noqa: BLE001 — harvest inputs, not the verdict
                    pass
        finally:
            sys.setprofile(prev)
    return captured[:max_samples]
