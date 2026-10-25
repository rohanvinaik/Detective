"""Intent: a measurement with mutants that reached no verdict never passes the strict gate as clean, and the
witness search budgets a mutant the way the engine was calibrated to (#80, Wesker#27).

THE DEFECTS, measured 2026-10-25 on fcd3348 / Wesker 6ba533d:

1. `audit m.py::count_down --check-strict` over a loop whose 4 mutants DIVERGED under the step budget, and
   `audit m.py::settle --check-strict` over a helper whose mutant hit the WALL (`undetermined`): both
   exited 0. The `--json` gate read `"measurement_incomplete": false … "exit": 0` with `exit_meaning:
   "clean"`, while the same page printed `incomplete` and `INCOMPLETE:`. `audit_measurement_incomplete`
   read only unclassified survivors and errored tests, so "could not measure" passed the strict gate as
   "measured no gap" (COMMUNICATING_DETERMINISM §3.1, §4).

2. The witness search budgeted a mutant at `step_cap(orig, factor=10, floor=100)`, its own restatement
   of the engine's calibrated `STEP_BUDGET_FACTOR=32` / `STEP_BUDGET_FLOOR=10_000`. On `bit_length`
   (`while n > 0: n //= 2; count += 1`), the mutant `n //= 2 -> n /= 2` terminates in 0.06 ms, returning
   1075 for n=1, and was filed `step-budget-divergent` at cap 110. The calibration document names exactly
   this case (a `//` -> `/` halving loop running the float-underflow tail) as the reason the floor is
   10,000. converge, under the engine's budget, killed it.

THE RULING (founder, 2026-10-25): the strict gate fails only on a cause the reader can fix. A prevented
write fails it. A step-budget divergence (deterministic, for good) and a wall bound (runner-speed
dependent until Wesker#27's calibrated liveness bound) are named in the gate's payload and never fail it:
nearly every `while` loop has a `while True` mutant, and a gate that reddens for good on it is deleted.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from Detective.audit import audit_measurement_incomplete, unresolved_gate_standing
from Detective.cli import _unmeasured_clause
from Detective.equivalence import _search_witness


def test_a_mutant_with_no_verdict_is_an_unmeasured_mutant_under_the_strict_gate():
    assert audit_measurement_incomplete(0, 0, 4) is True
    assert audit_measurement_incomplete(0, 0, 0) is False
    assert audit_measurement_incomplete(0) is False, "a caller that names no unresolved mutant reports none"
    clause = _unmeasured_clause(0, 0, 4)
    assert (
        clause.startswith("4 mutant(s) reached no verdict")
        and "survivor" not in clause
        and "errored" not in clause
    )


@pytest.mark.parametrize(
    ("reason", "standing"),
    [
        ("write_outside_authority", "repairable"),
        ("diverged", "budget_floor"),
        ("undetermined", "machine_bound"),
        ("a_reason_this_version_does_not_know", "unknown"),
    ],
)
def test_only_a_cause_the_reader_can_fix_fails_the_strict_gate(reason, standing):
    assert unresolved_gate_standing(reason) == standing


def _bit_length(n):
    count = 0
    while n > 0:
        n //= 2
        count += 1
    return count


def _bit_length_true_division(n):  # the mutant: `n //= 2 -> n /= 2`
    count = 0
    while n > 0:
        n /= 2
        count += 1
    return count


def _bit_length_never_halves(n):  # a genuine runaway: `n //= 2 -> pass`
    count = 0
    while n > 0:
        count += 1
    return count


def test_a_terminating_halving_mutant_is_distinguished_never_filed_divergent():
    witness, _crash, _blocked, diverged = _search_witness(_bit_length, _bit_length_true_division, [(1,)])
    assert not diverged, "a mutant that terminates in 1,075 iterations was filed step-budget-divergent"
    assert witness is not None and witness.mutant == "1075"


def test_a_genuine_runaway_still_diverges_under_the_calibrated_budget():
    witness, _crash, _blocked, diverged = _search_witness(_bit_length, _bit_length_never_halves, [(1,)])
    assert witness is None and diverged


def _detective(cwd, *argv):
    return subprocess.run(
        [sys.executable, "-m", "Detective", *argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
        env=dict(os.environ),
    )


def _migrated(tmp_path, files):
    for rel, text in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text)
    migrate = _detective(tmp_path, "regime", "--migrate", "--project-root", str(tmp_path))
    assert migrate.returncode == 0, migrate.stdout + migrate.stderr


def test_a_diverged_mutant_is_named_in_the_gate_and_never_fails_it(tmp_path):
    _migrated(
        tmp_path,
        {
            "m.py": "def count_down(n):\n    while n > 0:\n        n -= 1\n    return n\n",
            "tests/test_m.py": (
                "from m import count_down\n\n\ndef test_count_down():\n    assert count_down(3) == 0\n"
            ),
        },
    )
    strict = _detective(tmp_path, "audit", "m.py::count_down", "--check-strict", "--json")
    payload = json.loads(strict.stdout)
    named = payload["gate"]["unmeasured"]["unresolved_mutants"]
    assert named and all(
        reason == "diverged" and standing == "budget_floor" for _m, reason, standing in named
    )
    assert strict.returncode == 0, "a deterministic budget floor must not redden the gate for good"
    assert payload["gate"]["measurement_incomplete"] is False


# #105's own end-to-end fixture: a SWAP mutant makes the test write outside its authority.
_STORE = (
    "import os\n\n\n"
    "def atomic_write_text(path, text):\n"
    "    staging = f'{path}.tmp-{os.getpid()}'\n"
    "    with open(staging, 'w') as fh:\n"
    "        fh.write(text)\n"
    "    os.replace(staging, path)\n\n\n"
    "def save(path, text):\n"
    "    atomic_write_text(path, text)\n"
    "    return path\n"
)
_TEST = (
    "from store import save\n\n\n"
    "def test_save_writes_the_file(tmp_path):\n"
    "    target = tmp_path / 'store.json'\n"
    "    assert save(str(target), '{\"a\": 1}') == str(target)\n"
    "    assert target.exists()\n"
    "    assert target.read_text() == '{\"a\": 1}'\n"
)


def test_a_prevented_write_fails_the_strict_gate_and_is_warned_as_repairable(tmp_path):
    _migrated(tmp_path, {"store.py": _STORE, "tests/test_store.py": _TEST})
    strict = _detective(tmp_path, "audit", "store.py::save", "--check-strict", "--json")
    payload = json.loads(strict.stdout)
    named = payload["gate"]["unmeasured"]["unresolved_mutants"]
    assert any(
        reason == "write_outside_authority" and standing == "repairable" for _m, reason, standing in named
    )
    assert strict.returncode == 2, "a repairable cause the run could not measure must fail the strict gate"
    plain = _detective(tmp_path, "audit", "store.py::save", "--check")
    assert plain.returncode == 0, "no specification gap, so the plain ratchet stays green: " + plain.stderr
    warning = plain.stderr.split("⚠ measurement incomplete", 1)[-1]
    assert "reached no verdict for a cause you can repair" in warning, plain.stderr
