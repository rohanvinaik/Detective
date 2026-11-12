"""Intent: a suggested test is satisfiable and names the mutant it is for (Detective #76).

THE DEFECT (spread_ratio, 2026-09-17; the renderer still printed it on 2026-10-26):
`→ assert f(0.0, -0.5) == nan   (mutant gives -0.0)`. `nan != nan`, so the assertion can never pass; the
synthesized test files already pin a NaN as `assert repr(result) == "nan"` (#78). A lone suggestion also
named no mutant, so the one line a reader acts on could not be checked against the mutant it was for. And
the FINAL banner read `Incomplete: 1 killable · 14/14 killed`, two numbers about two populations under one
word.

THE RULING: the suggestion is built by `suggested_assertion` (a non-literal repr is compared by repr; a
literal keeps `==`; a `<…>` observation stays as observed), every suggestion names the mutants it kills,
and the banner's `killable` says it is a value gap.
"""

from __future__ import annotations

import ast

import pytest

from Detective.cli import _format_survivor_report, suggested_assertion
from Detective.equivalence import MutantVerdict, SurvivorReport, Witness


@pytest.mark.parametrize(
    ("original", "expected"),
    [
        ("nan", "assert repr(f(0.0, -0.5)) == 'nan'"),
        ("inf", "assert repr(f(0.0, -0.5)) == 'inf'"),
        ("[nan, 1.0]", "assert repr(f(0.0, -0.5)) == '[nan, 1.0]'"),
        ("-0.0", "assert f(0.0, -0.5) == -0.0"),
        ("7", "assert f(0.0, -0.5) == 7"),
        ("'a'", "assert f(0.0, -0.5) == 'a'"),
        ("None", "assert f(0.0, -0.5) == None"),
        ("<raised KeyError: 'x'>", "assert f(0.0, -0.5) == <raised KeyError: 'x'>"),
        ("", "assert repr(f(0.0, -0.5)) == ''"),
    ],
)
def test_the_suggested_assertion_is_satisfiable_for_what_it_observed(original, expected):
    assert suggested_assertion("f(0.0, -0.5)", original) == expected


def test_a_nan_suggestion_is_valid_python_that_holds_for_nan():
    line = suggested_assertion("f()", "nan")
    f = lambda: float("nan")  # noqa: E731
    exec(compile(ast.parse(line), "<s>", "exec"), {"f": f})  # noqa: S102 — asserting the suggestion


def _verdict(mutant_id, original):
    return MutantVerdict(
        mutant_id=mutant_id,
        category="VALUE",
        diff_summary="- x + y",
        killable=True,
        witness=Witness(args=(0.0, -0.5), original=original, mutant="-0.0"),
        searched=3,
    )


def test_the_report_never_prints_the_unsatisfiable_nan_assertion_and_names_a_lone_mutant():
    rep = SurvivorReport(verdicts=(_verdict("VALUE_aaaa1111", "nan"),), unclassified=())
    out = "\n".join(_format_survivor_report(rep, verbose=False))
    assert "== nan" not in out, out
    assert "assert repr(f(0.0, -0.5)) == 'nan'" in out, out
    assert "(kills 1: VALUE_aaaa1111)" in out, out
