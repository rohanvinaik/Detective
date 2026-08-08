"""A COMPLETE must say when its line axis rested on the weaker evidence (issue #59).

`line_basis` recorded which evidence closed the line ledger and NOTHING rendered it. So on a
released engine — one without Wesker #17's outcome-qualified view — `✓ COMPLETE` could rest on
the observed union, including a test that FAILS against the unmutated program, with nothing
telling the user. Recorded-but-unrendered is the same channel split #57 fixed for receipts: a
refusal (or a qualification) that exists only in an object nobody reads is not one.

It belongs on the banner for the same reason `under receiver` and `under capability set` do: the
certificate holds UNDER something, so it has to name what. It is also what keeps the dependency
floor honest — a degradation the user can SEE does not need a floor raise to strand every user
on the published engine (dev/DEPENDENCY_FLOORS.md).
"""

from __future__ import annotations

import dataclasses

from Detective.cli import _final_banner
from Detective.converge import ConvergeResult

_COMPLETE = dict(
    function="x.py::f",
    converged=True,
    at_ceiling=True,
    initial_survivors=0,
    final_survivors=0,
    iterations=(),
    written_path="",
    functionally_complete=True,
    line_complete=True,
    total_mutants=4,
    killed=4,
)


def test_an_observed_basis_is_named_on_the_banner():
    """The defect. Without this the weakening is invisible on the one line people grep."""
    banner = _final_banner(ConvergeResult(**_COMPLETE, line_basis="observed"))
    assert "COMPLETE" in banner
    assert "line axis unqualified" in banner


def test_an_admissible_basis_adds_no_noise():
    """The control. The correct case is the overwhelmingly common one and must read cleanly —
    a qualifier on every run trains the reader to skip it, which is how the next real one gets
    missed."""
    banner = _final_banner(ConvergeResult(**_COMPLETE, line_basis="admissible"))
    assert "COMPLETE" in banner
    assert "unqualified" not in banner


def test_an_incomplete_run_is_not_decorated():
    """An incomplete run already states its residual; adding a basis qualifier there would
    explain the evidence behind a claim that was not made."""
    incomplete = {**_COMPLETE, "functionally_complete": False, "killed": 2}
    banner = _final_banner(ConvergeResult(**incomplete, line_basis="observed"))
    assert "COMPLETE" not in banner
    assert "unqualified" not in banner


def test_the_json_surface_carries_it_too():
    """Both channels or neither. A human-only qualification leaves every programmatic consumer
    reading the same unqualified COMPLETE the field exists to qualify."""
    payload = dataclasses.asdict(ConvergeResult(**_COMPLETE, line_basis="observed"))
    assert payload["line_basis"] == "observed"


def test_the_default_is_the_weaker_basis():
    """A result built without the field must not claim the strong one. Defaults decide what an
    old or hand-built result asserts, and the safe direction is the one that under-claims."""
    assert ConvergeResult(**_COMPLETE).line_basis == "observed"
