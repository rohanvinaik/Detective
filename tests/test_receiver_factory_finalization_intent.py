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

import textwrap
from pathlib import Path

from Detective.converge import converge

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
        assert not report.unclassified, [d for d in report.unclassified][:3]
