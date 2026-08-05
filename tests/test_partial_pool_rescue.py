"""Partial pool-poverty rescue (issue #22).

Field shape: a function over structured objects had SOME survivors proven by
synthetic scalars while the rest filed candidate-equivalent — and the covering
tests were building the distinguishing objects all along. The rescue used to
fire only on TOTAL poverty (no killable at all), so the report asked the user
to hand-transcribe witnesses the suite already contained. It now fires on any
rescuable residual and adopts the retry only when it proves more.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from Detective.converge import converge


def _project(tmp_path: Path) -> Path:
    (tmp_path / "shapes.py").write_text(
        textwrap.dedent(
            """
            def measure(payload, scale):
                if scale == 0:
                    return -1
                return payload["weight"] * scale
            """
        )
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_shapes.py").write_text(
        textwrap.dedent(
            """
            from shapes import measure


            def test_zero_scale():
                assert measure({"weight": 4}, 0) == -1


            def test_scaled_weight():
                assert measure({"weight": 4}, 3) == 12
            """
        )
    )
    return tmp_path


def test_partial_poverty_harvests_the_suites_structured_inputs(tmp_path: Path):
    root = _project(tmp_path)
    result = converge("shapes.py", "measure", str(root), max_iterations=2)

    rep = result.survivor_report
    assert rep is not None
    # The dict-needing dimensions must not file as candidate-equivalent while
    # a covering test passes {"weight": 4}: the harvest feeds the pool in the
    # PARTIAL case now, so the payload line's mutants get real witnesses.
    dict_witnesses = [
        v for v in rep.killable if v.witness is not None and any(isinstance(a, dict) for a in v.witness.args)
    ]
    assert dict_witnesses or result.functionally_complete, (
        "no witness carries the suite-built dict and the run is not complete — "
        f"the partial rescue never fired: equivalents={len(rep.equivalent)}, "
        f"killable={len(rep.killable)}"
    )
