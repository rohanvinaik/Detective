"""The receiver axis reaches the classification whose report becomes the verdict (#25, reopened
2026-09-06 by the dogfood sweep's first Tier-1 region, `purity._SideEffectVisitor.visit_Call`).

The defect: `_converge_impl` classifies survivors twice — once in the witness pass (with the
explicit `--receiver-factory`) and once at finalization, "N survivor(s) remain — classifying", whose
`SurvivorReport` is the one the run reports. The second call did not pass the factory. So a method
target whose class needs constructor arguments, converged WITH a factory, still ended
"needs-receiver — <Owner>() could not be constructed without arguments", every survivor unclassified
— while the emitted test happily imported and called that very factory. Two calls doing the same
job; the axis was wired into one.

Pinned from intent, end to end through `converge`: a method on a class with a required constructor
argument, a zero-arg factory in the tmp repo, and the run's own verdict must carry NO receiver
refusal and must classify (and kill) rather than abstain on every survivor.
"""

from __future__ import annotations

import importlib
import textwrap
from pathlib import Path

import pytest

from Detective.converge import converge
from Detective.equivalence import SurvivorReport

convergence = importlib.import_module("Detective.converge")

_BASKET = """
class Basket:
    def __init__(self, tier: str) -> None:
        self.tier = tier

    def total(self, prices: list[int]) -> int:
        base = sum(prices)
        if self.tier == "gold":
            return base - base // 10
        return base
"""

_FACTORY = """
from basket import Basket


def make_gold_basket() -> Basket:
    return Basket("gold")
"""


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "basket.py").write_text(textwrap.dedent(_BASKET), encoding="utf-8")
    (tmp_path / "basket_factories.py").write_text(textwrap.dedent(_FACTORY), encoding="utf-8")
    return tmp_path


def test_every_classification_call_is_handed_the_receiver_factory(tmp_path, monkeypatch) -> None:
    """Forwarding, on its own (#138): a spy at the `classify_survivors` call boundary.

    The end-to-end test below can pass only on a VALID measurement, so it cannot be the only check
    that the finalization call passes the factory: an invalid measurement would hide a dropped
    factory, or a dropped factory would be blamed on the measurement. Here the classification is a
    stub, so nothing it measures matters, and the wall is unbounded (`deadline_s=None`), so no
    clock can cut the run before the finalization call is reached. What is pinned is only the
    argument the call receives.
    """
    root = _repo(tmp_path)
    monkeypatch.syspath_prepend(str(root))
    calls: list[dict] = []

    def spy(file, function, project_root, **kwargs):
        calls.append(kwargs)
        return SurvivorReport((), ())

    monkeypatch.setattr(convergence, "classify_survivors", spy)
    result = converge(
        "basket.py",
        "Basket.total",
        str(root),
        receiver_factory="basket_factories:make_gold_basket",
        max_iterations=1,
        write_dir="tests/detective",
        deadline_s=None,
    )
    # The precondition, stated: the finalization classification is the call made over the run's own
    # final profile, and it is only made when survivors remain and the floor passes.
    finalization = [kw for kw in calls if kw.get("profile_result") is not None]
    assert calls and finalization, {
        "the finalization classification was never reached": True,
        "final_survivors": result.final_survivors,
        "cut_reasons": result.cut_reasons,
        "budget_exhausted": result.budget_exhausted,
        "cut_phase": result.cut_phase,
        "calls": len(calls),
    }
    for kwargs in calls:
        factory = kwargs.get("receiver_factory")
        assert factory is not None, "a classification call was made WITHOUT the receiver factory"
        assert factory.render == "make_gold_basket()"
        assert factory.import_stmt == "from basket_factories import make_gold_basket"
    # The two calls (witness pass, finalization) are handed the same resolved axis.
    assert len({id(kw["receiver_factory"]) for kw in calls}) == 1


def _require_valid_measurement(result) -> None:
    """The end-to-end test's PRECONDITION, stated (#138): a valid measurement.

    A run whose measurement is invalid (a wall cut, an uncontained worker, an unresolved mutant)
    classifies nothing by design; that is a refusal, not a forwarding defect, and must be reported
    as the cut it is, naming it, never as a bare "unclassified" assertion.
    """
    report = result.survivor_report
    invalid = (
        not result.measurement_gateable
        or bool(result.cut_reasons)
        or result.budget_exhausted
        or (report is not None and not report.measurement_valid)
    )
    if invalid:
        pytest.fail(
            "INVALID MEASUREMENT, not a receiver-factory result: "
            + repr(
                {
                    "measurement_gateable": result.measurement_gateable,
                    "cut_reasons": result.cut_reasons,
                    "budget_exhausted": result.budget_exhausted,
                    "cut_phase": result.cut_phase,
                    "report_measurement_valid": getattr(report, "measurement_valid", None),
                    "report_note": getattr(report, "note", None),
                }
            )
        )


def test_an_invalid_measurement_fails_naming_the_cut_not_as_unclassified() -> None:
    """The precondition helper reports the validity cut it saw (#138), whatever kind it is."""
    from types import SimpleNamespace

    report = SimpleNamespace(measurement_valid=False, note="the profile was cut", unclassified=("m1",))
    cut = SimpleNamespace(
        measurement_gateable=False,
        cut_reasons=("budget_exhausted",),
        budget_exhausted=True,
        cut_phase="finalization",
        survivor_report=report,
    )
    with pytest.raises(pytest.fail.Exception) as raised:
        _require_valid_measurement(cut)
    message = str(raised.value)
    assert message.startswith("INVALID MEASUREMENT")
    assert "budget_exhausted" in message and "finalization" in message and "the profile was cut" in message
    # Only the report invalid (an uncontained harvest carries no run-level cut reason): still named.
    quiet = SimpleNamespace(
        measurement_gateable=True,
        cut_reasons=(),
        budget_exhausted=False,
        cut_phase="",
        survivor_report=report,
    )
    with pytest.raises(pytest.fail.Exception, match="INVALID MEASUREMENT"):
        _require_valid_measurement(quiet)
    # A valid measurement, or one with no report at all, passes the precondition.
    ok = SimpleNamespace(
        measurement_gateable=True,
        cut_reasons=(),
        budget_exhausted=False,
        cut_phase="",
        survivor_report=SimpleNamespace(measurement_valid=True, note=None),
    )
    _require_valid_measurement(ok)
    _require_valid_measurement(SimpleNamespace(**{**vars(ok), "survivor_report": None}))


def test_the_final_classification_uses_the_receiver_factory_too(tmp_path, monkeypatch) -> None:
    root = _repo(tmp_path)
    # The factory is IMPORTED by name; under the CLI the live pytest session puts the repo on
    # sys.path, here the library call is made directly, so the test does what the regime does.
    monkeypatch.syspath_prepend(str(root))
    result = converge(
        "basket.py",
        "Basket.total",
        str(root),
        receiver_factory="basket_factories:make_gold_basket",
        max_iterations=1,
        write_dir="tests/detective",
    )
    _require_valid_measurement(result)
    assert not result.needs_receiver, (
        f"the factory was supplied; the verdict still refused: {result.needs_receiver!r}"
    )
    report = result.survivor_report
    note = (report.note or "") if report is not None else ""
    assert "needs-receiver" not in note, note
    # With a receiver the search actually exercises the method: at least one mutant is KILLED, and
    # no survivor is filed "unclassified — the search could not run".
    assert result.killed > 0, "the receiver axis must let the search run"
    if report is not None:
        assert not report.unclassified, {
            "measurement_valid": report.measurement_valid,
            "note": note,
            "unclassified": report.unclassified[:3],
        }
