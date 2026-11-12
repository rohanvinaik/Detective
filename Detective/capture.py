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
    STEP_PROBE_CAP,
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
    "harvest_stop_status",
]


HARVEST = "harvest"  # run the next test
HARVEST_ENOUGH = "enough"  # the pool is full — a completed harvest, whatever the wall says
HARVEST_CUT = "cut"  # the aggregate wall has passed — stop, keep what was captured

# Verdicts computed before this contract omitted None and accepted cut harvests.
# The cache consumes this identity; a package release number cannot identify it.
RETURN_OBSERVATION_POLICY = "owned-complete-types-v3-deadline"


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
    #: The tests the loop budget could not bound (Detective#80): each ran past `STEP_PROBE_CAP` inside the
    #: target, so the count could not decide it and it ran AGAIN, unarmed, under the calibrated wall alone;
    #: the harvest is taken from that run. A fact for the full report and ``--json``, not a cut: it makes
    #: nothing partial.
    unarmed: tuple[str, ...] = ()

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
                and self.unarmed == other.unarmed
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


class EffectRefused(ObservationIncomplete):
    """A speculative call attempted process effects, each refused before it ran (D#141).

    ``effects`` names them as their audit events (``subprocess.Popen``, ``resource.setrlimit``), so the
    page can say what the function does rather than borrow "writes files", which would be false."""

    def __init__(self, effects: tuple[str, ...]):
        self.effects = effects
        super().__init__(
            "process_effect_blocked", "speculative process effects were refused: " + ", ".join(effects)
        )


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
    step_stopped: bool = False


HARVEST_UNCONTAINED = "uncontained"


def harvest_stop_status(base: str, contained: bool, timed_out: bool) -> str:
    """The status a harvest ends with once its tests have run (Detective#80, pure — pinned).

    ``base`` is the status the loop reached on its own (``empty`` / ``complete`` / ``enough`` / ``cut``
    for a spent aggregate wall). The facts that void or qualify it, strongest first:

    * ``uncontained`` — a worker could not be stopped: nothing measured after it is trustworthy.
    * ``cut``         — a per-test wall fired: a liveness bound, so the harvest is partial.
    * otherwise ``base`` stands.

    A loop budget is not among them. A test the count stopped is run again unarmed (see
    `capture_call_inputs`), so only the wall can cut it, and a test that merely loops long is complete.
    """
    if not contained:
        return HARVEST_UNCONTAINED
    if timed_out:
        return "cut"
    return base


def _stretched_timeout(seconds: float) -> float:
    """A reference-time per-test wall, stretched by this machine's calibrated slowdown (Detective#80).

    The harvest's wall is a liveness bound, so it follows the same calibration Wesker's walls do
    (`Wesker.monitoring.machine_slowdown`): a slow machine gets a proportionally longer wall and the
    same test reaches the same status. Never a shrink."""
    from Wesker.monitoring import machine_slowdown

    return seconds * max(machine_slowdown()[0], 1.0)


def _remaining(per_test_timeout: float, deadline: float | None) -> float:
    """A test's wall: its own, clipped to what the aggregate deadline has left."""
    if deadline is None:
        return per_test_timeout
    return min(per_test_timeout, max(0.0, deadline - time.monotonic()))


def _test_label(test: Callable[..., Any]) -> str:
    """The name a test is reported by in `HarvestResult.unarmed`."""
    return getattr(test, "__qualname__", None) or getattr(test, "__name__", None) or repr(test)


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
    deadline: float | None = None,
    step_cap: int | None = None,
) -> _HarvestExecution:
    """Run one discovered test for its SIDE EFFECTS on the active monitoring hook.

    Each test owns a fresh token and subscription. The worker object is known
    before start, so ownership has neither an ident-binding race nor ident reuse.
    The parent retires and closes the subscription on every exit.
    An absolute deadline includes setup/startup and rejects observations even
    when a finished worker wins the race with its waiting parent.
    """
    interrupt_exc: BaseException | None = None
    observation_errors: list[MonitoringUnavailable] = []
    step_stopped: list[bool] = []

    def _run_test() -> None:
        # The loop budget bounds the TARGET's own iterations inside this test (Detective#80): the same
        # deterministic stop the mutant observations have, so a test that loops in the function does not
        # have to wait out a wall that is a different answer on every machine. Budgets do not nest: a
        # test that opened its own is left to it.
        if step_cap is None or code is None or is_budget_active():
            test()
            return
        with step_budget([code], cap=step_cap) as count:
            try:
                test()
            finally:
                if count.stopped:
                    step_stopped.append(True)

    def _safe_run() -> None:
        nonlocal interrupt_exc
        try:
            if deadline is not None and time.monotonic() >= deadline:
                return
            _run_test()
        except (KeyboardInterrupt, SystemExit) as exc:
            interrupt_exc = exc
        except StepBudgetExceeded:
            pass  # recorded in `step_stopped` by `_run_test`
        except Abandoned:
            pass
        except MonitoringUnavailable as exc:
            observation_errors.append(exc)
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

    def observe_within_deadline(*args: Any, **kwargs: Any) -> None:
        if deadline is None or time.monotonic() < deadline:
            observer(*args, **kwargs)

    try:
        handle = subscribe(
            [code] if code is not None else [],
            event,
            observe_within_deadline if deadline is not None else observer,
            run_token=token,
            thread_filter=owns_thread,
            selectors=selectors,
        )
    except BaseException:
        retire_run_token(token)
        raise
    timed_out, contained = True, True
    joined = False
    try:
        if deadline is None or time.monotonic() < deadline:
            worker.start()
            remaining = (
                min(timeout_s, max(0.0, deadline - time.monotonic())) if deadline is not None else timeout_s
            )
            timed_out, contained = bounded_join(worker, remaining, unwind_s=0.05)
            joined = True
    finally:
        retire_run_token(token)
        try:
            # Startup or remaining-budget calculation can be interrupted after
            # the worker starts but before bounded_join takes ownership.
            if not joined and worker.is_alive():
                bounded_join(worker, 0.0, unwind_s=0.05)
        finally:
            handle.close()
    try:
        handle.check()
    except MonitoringObservationFailed as exc:
        raise ObservationIncomplete(exc.code, str(exc), contained=contained) from exc
    if interrupt_exc is not None:
        raise interrupt_exc
    if worker.refusal:
        raise ObservationIncomplete("execution_refused", worker.refusal, contained=contained)
    if observation_errors:
        raise observation_errors[0]
    incomplete_thread = include_children and any(
        thread not in alive_before and thread is not worker for thread in threading.enumerate()
    )
    timed_out = timed_out or (deadline is not None and time.monotonic() >= deadline)
    return _HarvestExecution(timed_out, contained, incomplete_thread, bool(step_stopped))


def capture_call_inputs(
    original: Callable[..., Any],
    tests: list[Callable[..., Any]],
    *,
    max_samples: int = 12,
    deadline: float | None = None,
    per_test_timeout: float = 5.0,
    step_cap: int | None = STEP_PROBE_CAP,
) -> HarvestResult:
    """Independent entry snapshots of positional arguments passed to ``original`` while
    ``tests`` run, deduplicated by value and capped at ``max_samples``.

    Keyed on the function's *code object* via owned ``sys.monitoring`` subscription on ``PY_START``.
    Receives authentic target frame from the broker without stack guessing.
    Binds thread ownership inside the worker and freezes evidence via retired run tokens.

    Each test runs under a loop budget of ``step_cap`` iterations of the target (default Wesker's
    ``STEP_PROBE_CAP``, the budget an original gets where no test fixed a count) and a wall of
    ``per_test_timeout`` reference seconds stretched by this machine's calibrated slowdown. A test the
    budget stops is UNARMED, the engine's rule for an original that does not finish inside the probe
    cap: the count cannot decide it, so it runs again under the wall alone and the harvest is taken from
    that run (what the stopped run captured is dropped). Only the wall can then cut it (``cut``); the
    test is named on ``HarvestResult.unarmed``.
    """
    code = getattr(original, "__code__", None)
    if code is None or not tests:
        return HarvestResult((), status="empty", contained=True)
    per_test_timeout = _stretched_timeout(per_test_timeout)

    names = code.co_varnames[: code.co_argcount]
    tool_id()
    captured: list[tuple] = []
    seen: set[str] = set()
    snapshot_errors: list[tuple[str, str]] = []
    all_contained = True
    any_timed_out = False
    unarmed: list[str] = []

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
        if deadline is not None and time.monotonic() >= deadline:
            return
        try:
            key = repr(args)
        except Exception as exc:  # noqa: BLE001
            snapshot_errors.append(("input_snapshot_unrepresentable", type(exc).__name__))
            return
        if deadline is not None and time.monotonic() >= deadline:
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
            captured_before = len(captured)
            seen_before = set(seen)
            run = _run_for_effects(
                t,
                timeout_s=timeout_s,
                code=code,
                event=sys.monitoring.events.PY_START,
                observer=_on_start,
                deadline=deadline,
                step_cap=step_cap,
            )
            if run.step_stopped and run.contained:
                # The count cannot decide this test (it loops past the probe cap in the target): it is
                # UNARMED, so it runs once more under the wall alone and the harvest is taken from that
                # run. Whatever the stopped run captured is dropped first, so the result is one run's.
                del captured[captured_before:]
                seen.clear()
                seen.update(seen_before)
                snapshot_errors.clear()
                unarmed.append(_test_label(t))
                run = _run_for_effects(
                    t,
                    timeout_s=_remaining(per_test_timeout, deadline),
                    code=code,
                    event=sys.monitoring.events.PY_START,
                    observer=_on_start,
                    deadline=deadline,
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

    status = harvest_stop_status(status, all_contained, any_timed_out)

    deadline_passed = deadline is not None and time.monotonic() >= deadline
    return HarvestResult(
        tuple(captured[:max_samples]),
        contained=all_contained,
        status=status,
        deadline_passed=deadline_passed,
        unarmed=tuple(unarmed),
    )


def capture_return_types(
    original: Callable[..., Any] | None,
    tests: list[Callable[..., Any]],
    *,
    max_samples: int = 24,
    per_test_timeout: float = 5.0,
    deadline: float | None = None,
    step_cap: int | None = STEP_PROBE_CAP,
    unarmed: list[str] | None = None,
) -> frozenset[str]:
    """The set of type NAMES of values the target RETURNS while ``tests`` run — the observed
    codomain for μ⁻ Fork 2 (the two-sign contract's type-conditional output perturbations).

    Keyed on the target's code object via owned ``sys.monitoring`` subscription on ``PY_RETURN``.
    """
    code = getattr(original, "__code__", None)
    if code is None or not tests:
        return frozenset()
    per_test_timeout = _stretched_timeout(per_test_timeout)

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
        name = type(retval).__name__
        if deadline is None or time.monotonic() < deadline:
            names.add(name)

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
            names_before = set(names)
            run = _run_for_effects(
                t,
                timeout_s=timeout_s,
                code=code,
                event=sys.monitoring.events.PY_RETURN,
                observer=_on_return,
                deadline=deadline,
                step_cap=step_cap,
            )
            if run.step_stopped and run.contained:
                # Unarmed, as in `capture_call_inputs`: the stopped run's types are dropped and the test
                # runs again under the wall alone; the codomain is taken from that run.
                names.clear()
                names.update(names_before)
                if unarmed is not None:
                    unarmed.append(_test_label(t))
                run = _run_for_effects(
                    t,
                    timeout_s=_remaining(per_test_timeout, deadline),
                    code=code,
                    event=sys.monitoring.events.PY_RETURN,
                    observer=_on_return,
                    deadline=deadline,
                )
            stop = harvest_stop_status("complete", run.contained, run.timed_out)
            if stop != "complete":
                # Partial types are diagnostic only: a codomain missing what a stopped test would have
                # returned is not the observed codomain, and the status says which bound stopped it.
                raise HarvestIncomplete(
                    HarvestResult(
                        codomain=frozenset(names),
                        contained=run.contained,
                        status=stop,
                        deadline_passed=deadline is not None and time.monotonic() >= deadline,
                    )
                )

    return frozenset(names)
