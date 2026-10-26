"""Intent: a page never asks for an input a function cannot take, and never calls a crash "detected"
when no test runs it (D#140, items 2 and 4).

THE DEFECTS, measured 2026-10-25 on fcd3348 and again on 157510e:

Item 2. `version()` takes no arguments. Its two surviving μ⁻ mutants (`'1.0'.swapcase()`, a no-op on
that literal, and a stale on a constant) were told to:
- "supply an input reaching a mutated branch";
- "confirm over a nested / cross-referential `--input`";
- "supply the distinguishing value(s) with --input".
The DONE block said it "probed this signature's boundaries". No input exists to supply, and there is
no boundary to probe.

Item 4. `tag(n) -> str | None` returns None if `n < 0`. Its only test asserts `tag(3) == "#3"`. Audit
printed

    · crash-only-equiv   4 survivor(s) — detected by crash; no value pins them

for the four str rewrites of the never-executed `return None`, with `value_killed` 12 of 27: no
test crash-killed them. The crash was the witness search's own observation. The split that tells
the two apart (`crash_only_status`) already existed, and the full report used it. The terse rows,
the verdict line and the DONE sentence ("They are detected, not equivalent") did not.

THE RULING:
- Classification establishes whether the function takes any argument, a method's receiver included
  (`SurvivorReport.takes_arguments`), once. The receiver counts: a receiver factory and the
  receiver-state search both vary it. Both verbs read it:
  - no structural or fixture caveat (`candidate_equivalent_caveat`);
  - no --input ask (`rescue_disposition` → `no_input`);
  - a DONE residual of its own (`residual_done_basis` → `single_call`), which still offers `flag`,
    because the one call is every input there is.
- Every surface that says "detected by crash" splits the crash-only bucket by whether a current test
  reaches each one (`_crash_only_rows`, `crash_only_unreached`).

NOT HERE: item 1's history-dependent class (a stale needs a second call), item 3's unbuilt operators,
item 5's all-negative probe and item 6's generator loop. Judging a Form B mutant's reach by entry
instead of by its def line belongs with item 1's class. Alone, it would drop the only caution a
killable stale on a parameterised function gets.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from Detective.cli import (
    _crash_only_rows,
    candidate_equivalent_caveat,
    residual_done_basis,
    residual_done_why,
)
from Detective.engine import rescue_disposition


def test_a_function_that_takes_no_argument_is_never_asked_for_an_input():
    assert rescue_disposition(True, True, False, takes_arguments=False) == "no_input"
    assert rescue_disposition(True, True, False, takes_arguments=True) == "skip_ask_input"
    assert rescue_disposition(True, False, False, takes_arguments=False) == "nothing"


def test_a_function_that_takes_no_argument_gets_no_caveat_that_sends_the_reader_after_one():
    assert candidate_equivalent_caveat("", True, True, True, takes_arguments=False) == "none"
    assert candidate_equivalent_caveat("", False, True, False, takes_arguments=False) == "none"
    assert candidate_equivalent_caveat("", True, True, True, takes_arguments=True) == "structural"


@pytest.mark.parametrize(
    ("args", "basis"),
    [
        ((2, 0, "run", 0, False), "single_call"),
        ((2, 0, "skip_effects", 0, False), "single_call"),
        ((2, 0, "run", 0, True), "probed"),
        ((0, 4, "", 4, True), "crash_only_unreached"),
        ((0, 4, "", 0, True), "crash_only"),
        ((1, 4, "run", 4, True), "probed"),  # a candidate-equivalent outranks the crash-only residue
        ((0, 0, "", 0, False), "none"),
    ],
)
def test_the_done_residual_says_what_was_established(args, basis):
    assert residual_done_basis(*args) == basis


def test_the_residual_sentences_claim_only_what_holds():
    single = residual_done_why("single_call")
    assert "takes no arguments" in single and "--input" not in single and "boundar" not in single
    unreached = residual_done_why("crash_only_unreached")
    assert "They are detected" not in unreached and "NO\ncurrent test reaches" in unreached


def test_a_crash_no_test_runs_is_never_called_detected():
    rows = "\n".join(_crash_only_rows(0, 4))
    assert "4 — an input crashes them, but no current test runs it" in rows
    assert "detected by crash" not in rows
    both = "\n".join(_crash_only_rows(3, 1))
    assert "3 — detected by crash" in both and "1 — an input crashes them" in both


# ── end to end ──────────────────────────────────────────────────────────────────────────────────

_BASKET = (
    "class Basket:\n"
    "    def __init__(self, items=None):\n"
    "        self.items = list(items or [])\n\n"
    "    def total(self):\n"
    "        if not self.items:\n"
    "            return 0\n"
    "        return sum(self.items)\n"
)
_BASKET_TEST = (
    "from basket import Basket\n\n\n"
    "def test_total_adds_the_items():\n"
    "    assert Basket([2, 3]).total() == 5\n"
)
_TAG = 'def tag(n: int) -> str | None:\n    if n < 0:\n        return None\n    return f"#{n}"\n'
_TAG_TEST = 'from tagging import tag\n\n\ndef test_tag_formats_a_count():\n    assert tag(3) == "#3"\n'
_VERSION = 'def version():\n    return "1.0"\n'
_VERSION_TEST = (
    'from versioning import version\n\n\ndef test_version_is_the_release():\n    assert version() == "1.0"\n'
)


def _detective(cwd, *argv):
    return subprocess.run(  # noqa: S603 — the CLI under test
        [sys.executable, "-m", "Detective", *argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
        env=dict(os.environ),
    )


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    (root / "tests").mkdir(parents=True)
    (root / "tagging.py").write_text(_TAG)
    (root / "versioning.py").write_text(_VERSION)
    (root / "tests" / "test_tagging.py").write_text(_TAG_TEST)
    (root / "tests" / "test_versioning.py").write_text(_VERSION_TEST)
    (root / "basket.py").write_text(_BASKET)
    (root / "tests" / "test_basket.py").write_text(_BASKET_TEST)
    assert _detective(root, "regime", "--migrate", "--project-root", str(root)).returncode == 0
    return root


def test_audit_never_calls_the_rewrites_of_an_unexecuted_line_detected(project):
    page = _detective(project, "audit", "tagging.py::tag", "--two-sign").stdout
    assert "4 — an input crashes them, but no current test runs it" in page, page
    assert "survivor(s) — detected by crash" not in page, page
    record = json.loads(_detective(project, "audit", "tagging.py::tag", "--two-sign", "--json").stdout)
    assert record["crash_only_equivalent"] == 4 and record["crash_only_undetected"] == 4


def test_converge_never_asks_a_function_with_no_argument_for_an_input(project):
    converge = _detective(project, "converge", "versioning.py::version", "--two-sign")
    assert converge.returncode == 0, converge.stdout + converge.stderr
    page = converge.stdout
    assert "it takes no arguments" in page and "⚠ structural" not in page, page
    assert "boundaries" not in page, page
    report = (project / ".detective" / "reports" / "converge_version.txt").read_text()
    assert "none can be supplied" in report and "template:" not in report, report
    assert "supply the distinguishing value(s) with --input" not in report, report
    assert "or add a distinguishing input" not in report, report


def test_a_methods_receiver_is_an_input_so_its_one_call_is_never_every_input(project):
    # The correction: `Basket.total(self)` read "it takes no arguments, so its one call is every input
    # there is" over survivors a different receiver reaches, and was offered `flag` for them.
    converge = _detective(project, "converge", "basket.py::Basket.total", "--two-sign")
    assert converge.returncode == 0, converge.stdout + converge.stderr
    assert "takes no arguments" not in converge.stdout, converge.stdout
