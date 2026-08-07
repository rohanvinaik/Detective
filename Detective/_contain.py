"""Command-level output containment and the aggregate-deadline arithmetic (issue #31).

A converge/decompose command runs the CONSUMER's code — its tests, and the target
function itself — throughout: every ``profile`` re-executes it under mutation, the
witness search calls original and mutant directly, golden capture invokes it on a
representative site. A target that PRINTS (a tracing wrapper, a debug ``print``) will
therefore spray stdout not only from inside a per-test redirect but from Detective's
OWN machinery — when the target *returns* a printing object (``boltons.wrap_trace``
returns an instance whose ``__getattribute__`` prints on every access) and Detective
then reprs or compares that value outside any redirect. ``print`` binds ``sys.stdout``
at call time, so one command-level redirect catches every one of those sites; a
per-test redirect structurally cannot. That is the output half of #31's contract:
consumer output must never corrupt the human report or the JSON stream.

The sink DISCARDS (never buffers) so a 14-million-line flood costs O(1) memory, and
COUNTS so the run can name the integration boundary honestly ("N bytes emitted to
stdout during measurement — contained") without gating behaviour on an arbitrary
volume threshold. Termination and gateability are decided by the aggregate deadline
and the existing survivor logic, not by how loud the target was.
"""

from __future__ import annotations

import contextlib
import io
import sys
import threading
from collections.abc import Iterator


class _CountingSink(io.TextIOBase):
    """A writable text stream that throws every write away and tallies its length.

    Thread-safe on the counter because Wesker runs tests on worker threads whose
    ``print`` resolves this same ``sys.stdout`` — the flood is genuinely concurrent,
    and a torn ``+=`` would under-report the very number the CUT diagnosis cites.
    """

    def __init__(self) -> None:
        self._bytes = 0
        self._lock = threading.Lock()

    @property
    def bytes_written(self) -> int:
        return self._bytes

    def writable(self) -> bool:
        return True

    def write(self, s: str) -> int:  # type: ignore[override]
        n = len(s)
        with self._lock:
            self._bytes += n
        return n


@contextlib.contextmanager
def contained_stdout() -> Iterator[_CountingSink]:
    """Redirect ``sys.stdout`` to a discarding, counting sink for the block's duration.

    stderr — where the phase narrative and the per-mutant heartbeat go — is left
    untouched, so a contained run is still legible as it runs. Yields the sink so the
    caller can read ``bytes_written`` and stamp it onto the result.
    """
    sink = _CountingSink()
    with contextlib.redirect_stdout(sink):
        yield sink


def remaining_budget_ms(deadline_ms: float | None, elapsed_ms: float) -> float | None:
    """The aggregate deadline every phase draws from, expressed as the ms still available.

    ``None`` (no wall declared) passes straight through as unbounded. A wall that has
    already elapsed clamps to ``0.0`` — NEVER a negative number, because a negative
    ``budget_ms`` handed to the engine would read as "unbounded" by sign and silently
    grant an exhausted run the full per-mutant allowance again. That clamp is the whole
    point of #31's "no command phase can reset or exceed the remaining deadline": one
    monotonic wall, drawn down, floored at zero.
    """
    if deadline_ms is None:
        return None
    return max(0.0, deadline_ms - elapsed_ms)
