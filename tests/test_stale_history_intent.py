"""Intent: a surviving stale (μ⁻ Form B ``return_stale``) is a class of its own, killed by a SECOND call
(Detective #140, item 1).

THE DEFECT, measured 2026-10-25 and again after Wesker #49: a stale mutant answers each call with the
previous call's result, within one test. Wesker's mutant memory now ends with each test, so only a test
that calls the function twice and sees two results detects it. Detective's search and its generated tests
call once per input, so under ``--two-sign`` every surviving stale printed:

- "candidate-equivalent ... supply an input reaching a mutated branch" and an offer of `flag`;
- the structural caveat "a branch no tried input reached", because Wesker files a Form B mutant on the
  def line, which no call executes (``reached: false``);
- or, when the pool held two inputs with different results, a "killable" ONE-call witness
  (``assert f('') == 'hello '  (mutant gives 'hello bob')``) that a one-call test never kills: converge
  wrote it, the stale survived, and the page asked for the same input again.

THE RULING:
- ``form_b_mode`` reads the mode from the structured dimension (``OUTPUT:<mode>:<line>``), never the
  diff's prose.
- ``history_standing`` names four states: "" / single_valued (flag is honest) / second_call_pair (converge
  writes ONE two-call test) / needs_second_call (supply two inputs with different results; no flag).
- A Form B mutant's reach is its function's ENTRY, not its def line.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys

import pytest

from Detective.equivalence import (
    classify_survivor,
    entry_statement_line,
    form_b_mode,
    history_standing,
    returned_value_outcome,
    returns_one_constant,
)

# ── pure decisions ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("dimension", "mode"),
    [
        ("OUTPUT:return_stale:12", "return_stale"),
        ("OUTPUT:raise_swallow:3", "raise_swallow"),
        ("OUTPUT:yield_empty:7", "yield_empty"),
        ("OUTPUT:return_none", ""),  # Form A: a return-site rewrite, no line
        ("OUTPUT:return_stale", ""),  # no def line: not Wesker's Form B dimension
        ("OUTPUT:return_stale:x", ""),
        ("ARITHMETIC:Add", ""),
        ("", ""),
        (None, ""),
    ],
)
def test_the_mode_is_read_from_the_structured_dimension(dimension, mode):
    assert form_b_mode(dimension) == mode


@pytest.mark.parametrize(
    ("args", "code"),
    [
        (("return_stale", True, False, True), "second_call_pair"),
        (("return_stale", True, False, False), "needs_second_call"),
        (("return_stale", False, False, False), "single_valued"),  # takes no argument
        (("return_stale", True, True, False), "single_valued"),  # a constant return
        (("return_stale", False, False, True), "single_valued"),
        (("raise_swallow", True, False, True), ""),
        (("yield_empty", True, False, True), ""),
        (("", True, False, True), ""),
    ],
)
def test_history_standing_names_each_state(args, code):
    assert history_standing(*args) == code


@pytest.mark.parametrize(
    ("source", "one"),
    [
        ("def f(x):\n    return 1\n", True),
        ("def f(x):\n    if x:\n        return None\n    return None\n", True),
        ("def f(x):\n    pass\n", True),
        ("def f(x):\n    return\n", True),
        ("def f(x):\n    if x:\n        return 1\n    return 2\n", False),
        ("def f(x):\n    return x\n", False),
        ("def f(x):\n    if x:\n        return 1\n", False),  # falls off the end: 1 or None
        ("def f(x):\n    yield 1\n", False),
        ("def f(x):\n    def g():\n        return x\n    return 1\n", True),
        ("def f(x):\n    return 1\n    return True\n", False),  # 1 and True are different values
    ],
)
def test_a_provably_single_valued_return_is_syntactic_and_conservative(source, one):
    assert returns_one_constant(ast.parse(source).body[0]) is one


def test_the_entry_line_is_the_first_statement_a_call_runs():
    fn = ast.parse('def f(x):\n    """doc"""\n    y = x\n    return y\n').body[0]
    assert entry_statement_line(fn) == 3
    only_doc = ast.parse('def f(x):\n    """doc"""\n').body[0]
    assert entry_statement_line(only_doc) == 2
    assert entry_statement_line(ast.parse("x = 1").body[0]) is None


@pytest.mark.parametrize(
    ("outcome", "value"),
    [
        ("'hello'", True),
        ("None", True),
        ("<raised TypeError: boom>", False),
        ("<classifier-timeout>", False),
        ("<step-budget-divergent>", False),
        ("<iter~trunc [1, 2]>", False),
        ("<Foo object at 0x10a3f2b50>", False),
        ("", False),
    ],
)
def test_only_a_returned_value_can_be_the_previous_calls_result(outcome, value):
    assert returned_value_outcome(outcome) is value


# ── the classifier ──────────────────────────────────────────────────────────────────────────────


def _greet(name):
    return "hello " + name


def test_a_stale_mutant_is_never_killable_by_one_input():
    verdict = classify_survivor(
        "m",
        "OUTPUT",
        "stale",
        _greet,
        _greet,  # the mutant callable must not be consulted: a per-input search cannot see history
        [("bob",), ("",)],
        form_b="return_stale",
    )
    assert verdict.killable is False and verdict.witness is None
    assert verdict.history == "second_call_pair"
    first, second = verdict.history_pair
    assert (first.args, first.original) == (("bob",), "'hello bob'")
    assert (second.args, second.original) == (("",), "'hello '")


def test_a_pool_without_two_different_results_needs_a_second_call():
    only_one_result = classify_survivor(
        "m", "OUTPUT", "s", _greet, _greet, [("bob",), ("bob",)], form_b="return_stale"
    )
    assert only_one_result.history == "needs_second_call" and only_one_result.history_pair is None
    raising = classify_survivor("m", "OUTPUT", "s", _greet, _greet, [(1,), (2,)], form_b="return_stale")
    assert raising.history == "needs_second_call"
    empty = classify_survivor("m", "OUTPUT", "s", _greet, _greet, [], form_b="return_stale")
    assert empty.history == "needs_second_call"


def test_a_function_known_to_return_one_value_keeps_the_flag_offer():
    assert (
        classify_survivor(
            "m", "OUTPUT", "s", _greet, _greet, [("a",)], form_b="return_stale", takes_arguments=False
        ).history
        == "single_valued"
    )
    assert (
        classify_survivor(
            "m", "OUTPUT", "s", _greet, _greet, [("a",), ("b",)], form_b="return_stale", constant_return=True
        ).history
        == "single_valued"
    )


def test_another_form_b_mode_takes_the_ordinary_search():
    verdict = classify_survivor("m", "OUTPUT", "s", _greet, lambda n: "x", [("bob",)], form_b="raise_swallow")
    assert verdict.history == "" and verdict.killable is True


# ── end to end, through the real CLI ────────────────────────────────────────────────────────────

_ANNOTATED = 'def greet(name: str) -> str:\n    return "hello " + name\n'
_ANNOTATED_TEST = 'from grs import greet\n\n\ndef test_greet():\n    assert greet("bob") == "hello bob"\n'
_UNANNOTATED = 'def greet(name):\n    return "hello " + name\n'
_UNANNOTATED_TEST = (
    'from greeting import greet\n\n\ndef test_greet():\n    assert greet("bob") == "hello bob"\n'
)
_CONSTANT = 'def version():\n    return "1.0"\n'
_CONSTANT_TEST = 'from versioning import version\n\n\ndef test_version():\n    assert version() == "1.0"\n'


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
    for name, source, test in (
        ("grs", _ANNOTATED, _ANNOTATED_TEST),
        ("greeting", _UNANNOTATED, _UNANNOTATED_TEST),
        ("versioning", _CONSTANT, _CONSTANT_TEST),
    ):
        (root / f"{name}.py").write_text(source)
        (root / "tests" / f"test_{name}.py").write_text(test)
    assert _detective(root, "regime", "--migrate", "--project-root", str(root)).returncode == 0
    return root


def _history_mutants(root, function):
    record = json.loads(_detective(root, "converge", function, "--two-sign", "--json").stdout)
    return [v for v in record["survivor_report"]["verdicts"] if v["history"]], record


def test_converge_writes_one_two_call_test_that_kills_the_stale_mutant(project):
    page = _detective(project, "converge", "grs.py::greet", "--two-sign")
    assert page.returncode == 0, page.stdout + page.stderr
    assert "13/13 killed" in page.stdout, page.stdout
    assert "history-dep" not in page.stdout and "detective flag" not in page.stdout, page.stdout
    written = next((project / "tests" / "detective").glob("test_grs_greet_*_synth.py")).read_text()
    # ONE test, two calls, two results asserted: neither call alone distinguishes a stale mutant.
    assert written.count("greet(name=") == 2 and written.count("assert result ==") == 2, written


def test_a_stale_that_needs_a_second_call_is_its_own_row_and_never_offered_to_flag(project):
    page = _detective(project, "converge", "greeting.py::greet", "--two-sign").stdout
    assert "· history-dep" in page and "second call" in page, page
    assert "· unproven-equiv" not in page and "⚠ structural" not in page, page
    assert "detective flag" not in page, page
    report = (project / ".detective" / "reports" / "converge_greet.txt").read_text()
    assert "history-dependent — retained, NOT a candidate for `flag`" in report, report
    assert "supply two inputs whose results differ" in report, report
    assert "candidate-equivalent — retained, UNPROVEN" not in report, report
    stale, record = _history_mutants(project, "greeting.py::greet")
    assert [v["history"] for v in stale] == ["needs_second_call"]
    assert stale[0]["killable"] is False and stale[0]["reached"] is True


def test_two_supplied_inputs_with_different_results_kill_it(project):
    page = _detective(
        project, "converge", "greeting.py::greet", "--two-sign", "--input", "('a',)", "--input", "('bb',)"
    ).stdout
    assert "13/13 killed" in page, page
    assert "history-dep" not in page, page


def test_a_constant_function_keeps_the_flag_and_no_second_call_is_asked(project):
    page = _detective(project, "converge", "versioning.py::version", "--two-sign").stdout
    assert "history-dep" not in page and "second call" not in page, page
