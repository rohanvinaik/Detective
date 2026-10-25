"""The preemptive hang watchdog aborts a deadlocked live-session run instead of hanging (#hang).

The converge-hang investigation found that a test blocked OUTSIDE the interpreter cannot be stopped
(``interrupt.abandon`` returns False) and that Wesker has NO preemptive watchdog, so the cooperative
trace budgets never fire while the main thread is stuck — an infinite hang. This wraps every
live-session command (`_run_live`) in a wall-clock backstop that fires regardless of the main
thread's state, dumps stacks, and hard-exits.

The two behavioural tests run in a SUBPROCESS on purpose: the watchdog's whole job is to hard-exit
the process, which would kill the test runner if exercised in-process.
"""

from __future__ import annotations

import subprocess
import sys

from Detective.cli import hang_watchdog_seconds


def test_hang_watchdog_seconds_is_a_backstop_not_a_budget():
    # Twice the session budget plus a fixed margin — always strictly larger than the budget it guards,
    # so the cooperative budget is what shapes a real run and the watchdog only catches a true deadlock.
    assert hang_watchdog_seconds(1800.0) == 1800.0 * 2 + 600.0
    assert hang_watchdog_seconds(300.0) > 300.0
    # An unbounded (None / 0 / negative) session budget has no proportional bound -> fixed backstop.
    assert hang_watchdog_seconds(None) == 3600.0
    assert hang_watchdog_seconds(0) == 3600.0
    assert hang_watchdog_seconds(-5.0) == 3600.0


def test_the_watchdog_aborts_a_hung_run_with_a_stack_dump():
    # A run that blocks forever must be KILLED by the watchdog, not hang. 1.5s deadline; the outer
    # timeout is generous so a FAILURE here is "the watchdog did not fire", never a flaky slow box.
    script = (
        "import threading\n"
        "from Detective.cli import _hang_watchdog\n"
        "with _hang_watchdog(1.5):\n"
        "    threading.Event().wait()\n"  # block forever, outside anything the tracer could bound
    )
    proc = subprocess.run([sys.executable, "-c", script], capture_output=True, timeout=30)
    assert proc.returncode != 0, "a hung run must be aborted, never exit 0"
    err = proc.stderr.decode(errors="replace")
    assert "Timeout" in err, f"expected a faulthandler stack dump, got: {err[:400]}"


def test_the_dump_survives_a_hung_test_that_holds_fd_level_capture():
    # Measured 2026-10-25 through `detective converge`: the live session captures at the `sys` level,
    # so a hang in an ordinary test printed every thread's stack — but the same hang inside a test
    # using pytest's `capfd` fixture exited 1 with ZERO bytes on stderr. `capfd` points fd 2 at a
    # temporary file for the test's duration; a dump written to fd 2 lands there and `exit=True`
    # discards it. The dump must reach the stderr the run STARTED with, whoever holds fd 2 when it
    # fires.
    script = (
        "import os, threading\n"
        "from Detective.cli import _hang_watchdog\n"
        "with _hang_watchdog(1.5):\n"
        "    os.dup2(os.open(os.devnull, os.O_WRONLY), 2)\n"  # what fd-level capture does to fd 2
        "    threading.Event().wait()\n"
    )
    proc = subprocess.run([sys.executable, "-c", script], capture_output=True, timeout=30)
    assert proc.returncode != 0, "a hung run must be aborted, never exit 0"
    err = proc.stderr.decode(errors="replace")
    assert "Timeout" in err, f"the stack dump was lost with fd 2: {err[:400]!r}"
    assert "most recent call first" in err


def test_the_watchdog_cancels_on_normal_completion():
    # After the `with` exits, the timer must be disarmed — a later sleep PAST the deadline must NOT
    # abort. If cancel were broken, the process would die during the sleep and never print SURVIVED.
    script = (
        "import time\n"
        "from Detective.cli import _hang_watchdog\n"
        "with _hang_watchdog(0.5):\n"
        "    pass\n"
        "time.sleep(1.5)\n"
        "print('SURVIVED')\n"
    )
    proc = subprocess.run([sys.executable, "-c", script], capture_output=True, timeout=30)
    assert proc.returncode == 0, proc.stderr.decode(errors="replace")
    assert b"SURVIVED" in proc.stdout
