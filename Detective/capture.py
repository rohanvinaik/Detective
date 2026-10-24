"""Runtime harvest of REAL argument tuples from the tests that already cover a
function — the honest input source when a parameter is a domain object that no
deterministic synthesis can fabricate.

Detective never *guesses* a structured input (that would undercut the abstention,
which is a feature: a fabricated input can only ever produce a spurious verdict).
Instead, when synthesis provably can't build a valid input, it reuses one the
covering tests genuinely pass: a ``sys.monitoring`` hook records the bound
positional arguments at every entry to the target's code object while the
discovered test callables run, and those real tuples feed the witness search.
Discovery proposes; the soundness gate in ``classify_survivors`` disposes (an
input that doesn't fit just raises and is dropped).

References: Fork 1 / Fork 2 = docs/theory/NEGATIVE_SPECIFICATION.md §11, Definition 11.10
"""

from __future__ import annotations

import contextlib
import copy
import io
import sys
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from Wesker.interrupt import Abandoned, JoinedWorker, bounded_join
from Wesker.monitoring import (
    MonitoringObservationFailed,
    MonitoringUnavailable,
    StepBudgetExceeded,
    allocate_run_token,
    is_budget_active,
    registered_thread,
    retire_run_token,
    step_budget,
    subscribe,
    tool_id,
)

__all__ = [
    "HARVEST",
    "HARVEST_CUT",
    "HARVEST_ENOUGH",
    "HOOK_FOREIGN_UNRESTORABLE",
    "HOOK_INSTALL",
    "HOOK_INSTALL_AND_RESTORE",
    "HarvestResult",
    "HarvestIncomplete",
    "ObservationIncomplete",
    "MonitoringUnavailable",
    "StepBudgetExceeded",
    "capture_call_inputs",
    "capture_return_types",
    "harvest_disposition",
    "is_budget_active",
    "profile_hook_disposition",
    "step_budget",
]


HARVEST = "harvest"  # run the next test
HARVEST_ENOUGH = "enough"  # the pool is full — a completed harvest, whatever the wall says
HARVEST_CUT = "cut"  # the aggregate wall has passed — stop, keep what was captured

# Verdicts computed before this contract omitted None and accepted cut harvests.
# The cache consumes this identity; a package release number cannot identify it.
RETURN_OBSERVATION_POLICY = "owned-complete-types-v2"


@dataclass(frozen=True)
class HarvestResult(Sequence[tuple]):
    """Typed result of an input or return type harvest (W#32).

    Behaves as a sequence of sample tuples for backwards compatibility while
    exposing explicit containment standing, execution status, and codomain types.
    """

    samples: tuple[tuple, ...] = ()
    codomain: frozenset[str] = frozenset()
    contained: bool = True
    status: str = "empty"  # "complete", "enough", "empty", "cut", "sample_limit", "uncontained"
    deadline_passed: bool = False

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: Any) -> Any:
        return self.samples[index]

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, HarvestResult):
            return (
                self.samples == other.samples
                and self.codomain == other.codomain
                and self.contained == other.contained
                and self.status == other.status
                and self.deadline_passed == other.deadline_passed
            )
        if isinstance(other, (list, tuple)):
            return list(self.samples) == list(other)
        return False

    def __add__(self, other: Any) -> list:
        if isinstance(other, (list, tuple)):
            return list(self.samples) + list(other)
        return NotImplemented

    def __radd__(self, other: Any) -> list:
        if isinstance(other, (list, tuple)):
            return list(other) + list(self.samples)
        return NotImplemented


class ObservationIncomplete(MonitoringUnavailable):
    """Execution supplied no admissible observation; its named reason reaches the CLI gate."""

    def __init__(self, code: str, detail: str, *, contained: bool = True):
        self.code = code
        self.contained = contained
        super().__init__(f"{code}: {detail}")


class HarvestIncomplete(ObservationIncomplete):
    """A codomain harvest did not finish admissibly; partial types are diagnostic only."""

    def __init__(self, result: HarvestResult):
        self.result = result
        super().__init__(
            f"harvest_{result.status}",
            "codomain observation did not complete admissibly",
            contained=result.contained,
        )


@dataclass(frozen=True)
class _HarvestExecution:
    timed_out: bool
    contained: bool
    incomplete_thread: bool = False


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
    inputs.
    """
    if have_enough:
        return HARVEST_ENOUGH
    if deadline_passed:
        return HARVEST_CUT
    return HARVEST


HOOK_INSTALL = "install"
HOOK_INSTALL_AND_RESTORE = "install_and_restore"
HOOK_FOREIGN_UNRESTORABLE = "foreign_unrestorable"


def profile_hook_disposition(prev_is_none: bool, prev_is_callable: bool) -> str:
    """Legacy profile hook disposition (pure — pinned). Kept for interface stability."""
    if prev_is_none:
        return HOOK_INSTALL
    if prev_is_callable:
        return HOOK_INSTALL_AND_RESTORE
    return HOOK_FOREIGN_UNRESTORABLE


def _run_for_effects(
    test: Callable[..., Any],
    timeout_s: float = 5.0,
    *,
    code: Any = None,
    event: int,
    observer: Callable[..., None],
    selectors: Sequence[str] | None = None,
    include_children: bool = False,
) -> _HarvestExecution:
    """Run one discovered test for its SIDE EFFECTS on the active monitoring hook.

    Each test owns a fresh token and subscription. The worker object is known
    before start, so ownership has neither an ident-binding race nor ident reuse.
    The parent retires and closes the subscription on every exit.
    """
    interrupt_exc: BaseException | None = None

    def _safe_run() -> None:
        nonlocal interrupt_exc
        try:
            test()
        except (KeyboardInterrupt, SystemExit) as exc:
            interrupt_exc = exc
        except Abandoned:
            pass
        # BLE001: the harvest swallows a test's verdict and never the operator's interrupt
        except BaseException:  # noqa: BLE001
            pass

    alive_before = set(threading.enumerate()) if include_children else set()
    worker = JoinedWorker(target=_safe_run, daemon=True)
    token = allocate_run_token()

    def owns_thread(tid: int) -> bool:
        if worker.ident == tid:
            return True
        if not include_children:
            return False
        registered = registered_thread(tid)
        return registered is not None and registered not in alive_before

    try:
        handle = subscribe(
            [code] if code is not None else [],
            event,
            observer,
            run_token=token,
            thread_filter=owns_thread,
            selectors=selectors,
        )
    except BaseException:
        retire_run_token(token)
        raise
    try:
        worker.start()
        timed_out, contained = bounded_join(worker, timeout_s, unwind_s=0.05)
    finally:
        retire_run_token(token)
        handle.close()
    try:
        handle.check()
    except MonitoringObservationFailed as exc:
        raise ObservationIncomplete(exc.code, str(exc), contained=contained) from exc
    if interrupt_exc is not None:
        raise interrupt_exc
    if worker.refusal:
        raise ObservationIncomplete("execution_refused", worker.refusal, contained=contained)
    incomplete_thread = include_children and any(
        thread not in alive_before and thread is not worker for thread in threading.enumerate()
    )
    return _HarvestExecution(timed_out, contained, incomplete_thread)


def capture_call_inputs(
    original: Callable[..., Any],
    tests: list[Callable[..., Any]],
    *,
    max_samples: int = 12,
    deadline: float | None = None,
    per_test_timeout: float = 5.0,
) -> HarvestResult:
    """Independent entry snapshots of positional arguments passed to ``original`` while
    ``tests`` run, deduplicated by value and capped at ``max_samples``.

    Keyed on the function's *code object* via owned ``sys.monitoring`` subscription on ``PY_START``.
    Receives authentic target frame from the broker without stack guessing.
    Binds thread ownership inside the worker and freezes evidence via retired run tokens.
    """
    code = getattr(original, "__code__", None)
    if code is None or not tests:
        return HarvestResult((), status="empty", contained=True)

    names = code.co_varnames[: code.co_argcount]
    tool_id()
    captured: list[tuple] = []
    seen: set[str] = set()
    snapshot_errors: list[tuple[str, str]] = []
    all_contained = True
    any_timed_out = False

    def _on_start(
        frame_code: Any,
        _offset: int,
        frame: Any = None,
        run_token: int | None = None,
    ) -> None:
        if frame_code is not code or frame is None or len(captured) >= max_samples or snapshot_errors:
            return
        try:
            loc = frame.f_locals
            # One copy of the whole row preserves its aliases while severing
            # references to the test's live arguments before the target runs.
            args = copy.deepcopy(tuple(loc[n] for n in names))
        except Exception as exc:  # noqa: BLE001
            # Report after the worker retires: an observation failure must not
            # become an exception thrown into the target under observation.
            snapshot_errors.append(("input_snapshot_failed", type(exc).__name__))
            return
        try:
            key = repr(args)
        except Exception as exc:  # noqa: BLE001
            snapshot_errors.append(("input_snapshot_unrepresentable", type(exc).__name__))
            return
        if key in seen:
            return
        seen.add(key)
        captured.append(args)

    status = "empty"
    deadline_passed = False
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        for t in tests:
            deadline_passed = deadline is not None and time.monotonic() >= deadline
            action = harvest_disposition(len(captured) >= max_samples, deadline_passed)
            if action != HARVEST:
                status = action
                break
            timeout_s = (
                min(per_test_timeout, max(0.0, deadline - time.monotonic()))
                if deadline is not None
                else per_test_timeout
            )
            run = _run_for_effects(
                t, timeout_s=timeout_s, code=code, event=sys.monitoring.events.PY_START, observer=_on_start
            )
            if snapshot_errors:
                reason, error_type = snapshot_errors[0]
                raise ObservationIncomplete(
                    reason,
                    f"entry arguments could not be retained independently ({error_type})",
                    contained=run.contained,
                )
            any_timed_out = any_timed_out or run.timed_out
            if not run.contained:
                all_contained = False
                break
        if status == "empty" and captured:
            status = "enough" if len(captured) >= max_samples else "complete"

    if not all_contained:
        status = "uncontained"
    elif any_timed_out:
        status = "cut"

    return HarvestResult(
        tuple(captured[:max_samples]),
        contained=all_contained,
        status=status,
        deadline_passed=deadline_passed,
    )


def capture_return_types(
    original: Callable[..., Any] | None,
    tests: list[Callable[..., Any]],
    *,
    max_samples: int = 24,
    per_test_timeout: float = 5.0,
    deadline: float | None = None,
) -> frozenset[str]:
    """The set of type NAMES of values the target RETURNS while ``tests`` run — the observed
    codomain for μ⁻ Fork 2 (the two-sign contract's type-conditional output perturbations).

    Keyed on the target's code object via owned ``sys.monitoring`` subscription on ``PY_RETURN``.
    """
    code = getattr(original, "__code__", None)
    if code is None or not tests:
        return frozenset()

    names: set[str] = set()
    tool_id()

    def _on_return(
        frame_code: Any,
        _offset: int,
        retval: Any,
        frame: Any = None,
        run_token: int | None = None,
    ) -> None:
        if frame_code is not code:
            return
        names.add(type(retval).__name__)

    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        for t in tests:
            deadline_passed = deadline is not None and time.monotonic() >= deadline
            action = harvest_disposition(len(names) >= max_samples, deadline_passed)
            if action == HARVEST_ENOUGH:
                raise HarvestIncomplete(HarvestResult(codomain=frozenset(names), status="sample_limit"))
            if action == HARVEST_CUT:
                raise HarvestIncomplete(
                    HarvestResult(codomain=frozenset(names), status="cut", deadline_passed=True)
                )
            timeout_s = (
                min(per_test_timeout, max(0.0, deadline - time.monotonic()))
                if deadline is not None
                else per_test_timeout
            )
            run = _run_for_effects(
                t, timeout_s=timeout_s, code=code, event=sys.monitoring.events.PY_RETURN, observer=_on_return
            )
            if run.timed_out or not run.contained:
                raise HarvestIncomplete(
                    HarvestResult(
                        codomain=frozenset(names),
                        contained=run.contained,
                        status="uncontained" if not run.contained else "cut",
                        deadline_passed=deadline is not None and time.monotonic() >= deadline,
                    )
                )

    return frozenset(names)
