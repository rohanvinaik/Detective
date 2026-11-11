"""Intent: the search tries the sign of what it was given, and the page never asks for an input the suite
already calls (Detective #140, items 5 and 6).

Item 5. `mean(xs)` over floats ended at 19/20 and offered `flag` on the `abs` rewrite of its return:
every input the grid and the covering test supply is positive, so `abs(mean(xs)) == mean(xs)` on all of
them, and `[-2.0, -1.0]` kills it. The search never tried an all-negative list. A residual that a mirrored
input kills is not an equivalence candidate.

Item 6. `evens_upto(n)`, a for-loop generator: the page asked for `--input "(7,)"`, the input the user's own
test already calls. Following it returned `WRITE TEST ... Repeating the command is a proven loop`. The
first run could have said WRITE TEST: the input was already in the suite.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from Detective.engine import _args_among
from Detective.equivalence import mirrored_inputs, sign_mirror


@pytest.mark.parametrize(
    ("value", "mirror"),
    [
        (3, -3),
        (-2.5, 2.5),
        (0, 0),
        (True, True),  # a bool is not a signed number
        ("ab", "ab"),
        (None, None),
        ([1.0, -2.0, 0.0], [-1.0, 2.0, 0.0]),
        ((1, [2, 3]), (-1, [-2, -3])),
        ({"a": 4, "b": "x"}, {"a": -4, "b": "x"}),
        ({1, 2}, {-1, -2}),
    ],
)
def test_the_mirror_flips_every_number_and_nothing_else(value, mirror):
    assert sign_mirror(value) == mirror


def test_nan_has_no_mirror():
    mirrored = sign_mirror(float("nan"))
    assert mirrored != mirrored


def test_a_pool_is_mirrored_only_where_the_mirror_differs_and_can_be_typed():
    pool = [([1.0, 2.0],), (0,), ("s",), (5, "x"), ([1.0, 2.0],)]
    assert mirrored_inputs(pool) == [([-1.0, -2.0],), (-5, "x")]
    assert mirrored_inputs([]) == []
    assert len(mirrored_inputs([(i,) for i in range(1, 100)], limit=5)) == 5


def test_an_input_the_suite_calls_is_recognised_by_equality_and_an_uncomparable_one_is_not():
    assert _args_among((7,), [(1,), (7,)]) is True
    assert _args_among((7,), [(1,), (8,)]) is False
    assert _args_among((7,), []) is False

    class Hostile:
        def __eq__(self, other):
            raise RuntimeError("boom")

        __hash__ = None

    assert _args_among((Hostile(),), [(Hostile(),)]) is False


_MEAN = "def mean(xs):\n    return sum(xs) / len(xs)\n"
_MEAN_TEST = "from stats import mean\n\n\ndef test_mean():\n    assert mean([1.0, 2.0, 3.0]) == 2.0\n"
_GEN = "def evens_upto(n):\n    for i in range(n):\n        if i % 2 == 0:\n            yield i\n"
_GEN_TEST = (
    "from gens import evens_upto\n\n\ndef test_evens():\n    assert list(evens_upto(7)) == [0, 2, 4, 6]\n"
)


def _detective(cwd, *argv):
    return subprocess.run(  # noqa: S603 — the CLI under test
        [sys.executable, "-m", "Detective", *argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
        env=dict(os.environ),
    )


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    (root / "tests").mkdir(parents=True)
    (root / "stats.py").write_text(_MEAN)
    (root / "tests" / "test_stats.py").write_text(_MEAN_TEST)
    (root / "gens.py").write_text(_GEN)
    (root / "tests" / "test_gens.py").write_text(_GEN_TEST)
    assert _detective(root, "regime", "--migrate", "--project-root", str(root)).returncode == 0
    return root


def test_a_killable_abs_is_killed_by_a_mirrored_input_not_offered_to_flag(project):
    record = json.loads(_detective(project, "converge", "stats.py::mean", "--two-sign", "--json").stdout)
    survivors = [v["diff_summary"] for v in record["survivor_report"]["verdicts"]]
    assert not any("abs(" in diff for diff in survivors), survivors


def test_a_generator_whose_witness_input_the_suite_already_calls_is_not_asked_for_that_input(project):
    page = _detective(project, "converge", "gens.py::evens_upto", "--two-sign").stdout
    assert "DO THIS" not in page and '--input "(7,)"' not in page, page
    assert "WRITE TEST:" in page and "your suite already calls this input" in page, page
    assert "a current test already calls it" in page, page
