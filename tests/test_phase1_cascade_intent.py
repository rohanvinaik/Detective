from __future__ import annotations

import copy
import time

from Detective.equivalence import (
    _OUTCOME_DIVERGED,
    _OUTCOME_TIMEOUT,
    _OUTCOME_WALL_UNDETERMINED,
    _outcome,
    _search_witness,
)
from Detective.synthesis.writer import _ruff_format


def test_outcome_argument_mutation_isolation() -> None:
    """Mutating arguments in-place inside the target must not alter the candidate args tuple

    or subsequent executions (#127).
    """

    def in_place_append(items: list[int]) -> int:
        items.append(42)
        return len(items)

    def mutant_in_place_append(items: list[int]) -> int:
        items.append(999)
        return len(items) * 2

    raw_args = ([1, 2, 3],)
    candidate_tuple = copy.deepcopy(raw_args)

    out1 = _outcome(in_place_append, candidate_tuple)
    assert out1 == "4"
    assert candidate_tuple[0] == [1, 2, 3], f"candidate_tuple was mutated in-place: {candidate_tuple}"

    out2 = _outcome(mutant_in_place_append, candidate_tuple)
    assert out2 == "8"
    assert candidate_tuple[0] == [1, 2, 3], f"candidate_tuple was mutated on second call: {candidate_tuple}"

    # Search witness should find the difference and emit pristine Witness.args
    witness, crash_witness, blocked, *rest = _search_witness(
        in_place_append, mutant_in_place_append, [candidate_tuple]
    )
    assert witness is not None
    assert witness.args[0] == [1, 2, 3], f"Witness.args captured mutated object: {witness.args}"
    assert witness.original == "4"
    assert witness.mutant == "8"


def test_outcome_timeout_and_recovery() -> None:
    """_outcome cleanly times out on non-terminating mutants and subsequent evaluations succeed."""

    def inc(x: int) -> int:
        return x + 1

    res1 = _outcome(inc, (5,))
    assert res1 == "6"

    # Timeout causes abandonment
    def runaway() -> None:
        while True:
            pass

    t0 = time.monotonic()
    div_res = _outcome(runaway, (), timeout_s=0.1, cap=5000)
    assert div_res == _OUTCOME_DIVERGED
    assert time.monotonic() - t0 < 0.1

    # With cap=None, wall-timeout path is exercised
    timeout_res = _outcome(runaway, (), timeout_s=0.1, cap=None)
    assert timeout_res in (_OUTCOME_TIMEOUT, _OUTCOME_WALL_UNDETERMINED)
    assert time.monotonic() - t0 < 1.0

    # Next evaluation succeeds normally
    res2 = _outcome(inc, (20,))
    assert res2 == "21"


def test_ruff_format_native_execution() -> None:
    """_ruff_format formats source code using direct binary when present (#131)."""
    unformatted = "def foo(   x,y   ):\n    return x+y\n"
    formatted = _ruff_format(unformatted)
    assert "def foo(x, y):" in formatted
