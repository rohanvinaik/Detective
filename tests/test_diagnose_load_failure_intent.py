"""Intent tests: diagnose is R3's fourth renderer, and it was never wired.

THE DEFECT, measured 2026-09-09 by driving the real command on a module whose import fails:

    diagnose reported `0 pinned`, attributed it to "⚠ NO tests — the counts above reflect ABSENT
    tests, not weak ones", routed to `DO THIS: detective converge`, and exited 0. Converge on the
    SAME target exits 3 naming the missing dependency. A reader who starts at diagnose — the command
    the README tells them to start at — is sent to write tests for a module no test can run.

R3 named the shared route and listed its renderers: `_audit_action` (correct), `converge_next_action`
(fixed there), `verify_rewrite` (no call site). Diagnose was in none of the three columns, and
`diagnose_next_action` had no load-failure parameter at all — R1's exact shape ("there is no
load-failure parameter") in a function written this same session.

WHY THE SIGNAL WAS MISSING rather than ignored: `normalize_validity`'s docstring says `load_failed`
"is not a Wesker fact… the import failure is only discovered later, by Detective's own
`classify_survivors`". Converge and audit run that; `engine.diagnose` does not. And `ScopeMap` had
no field to carry it — the same "a renderer cannot consume a field the type does not define" defect
R3 found on `RewriteVerification` and, before it, on `SuiteAudit`. Third instance of one shape.

The repair consumes the EXISTING derivations at every layer rather than adding any: `_load_failure_
reason` (the same probe `classify_survivors` uses), `measurement_block_route` (the same shared
route audit delegates to), and audit's own wording for the STOP block.
"""

from __future__ import annotations

from Detective.cli import _format_scope, diagnose_next_action, no_tests_attribution
from Detective.scope import KillQuality, ScopeMap, Specification


def _scope(*, load_failure: str = "", tests_discovered: int = 0, dof: int = 2) -> ScopeMap:
    return ScopeMap(
        function="m.py::f",
        regime="A",
        surviving_categories=[],
        specification=Specification(10, 0, dof, 0, 0),
        kill_quality=KillQuality(0, 0, None),
        behavioral_dof=[],
        tests_discovered=tests_discovered,
        load_failure=load_failure,
    )


# ---------------------------------------------------------------- the shared route, delegated


def test_a_measurement_that_could_not_RUN_outranks_every_structural_signal() -> None:
    """The rule R3 installed for audit and converge, now held by diagnose. Nothing below a blocked
    measurement means anything, so nothing below it may be the instruction."""
    assert diagnose_next_action("fix_load", True, 3, 7) == "fix_load"
    assert diagnose_next_action("fix_load", False, 0, 0) == "fix_load"


def test_the_block_is_DELEGATED_not_restated() -> None:
    """`audit_next_action`'s own discipline: its first branch passes the shared route's code
    through rather than re-deciding it. A second reading of the same facts is the sibling drift
    every repair in CORRECTNESS_REPAIRS turned out to be an instance of, so any code the shared
    route can return must survive this function unchanged."""
    for code in ("fix_load", "close_the_gap", "provide_sample"):
        assert diagnose_next_action(code, True, 3, 7) == code


def test_an_unblocked_run_keeps_the_ladder_it_had() -> None:
    """An INSERTION, not a reordering. Every pre-existing route must be untouched when nothing
    blocks — otherwise the repair bought a regression."""
    assert diagnose_next_action("", True, 1, 2) == "decompose_first"
    assert diagnose_next_action("", False, 0, 1) == "close_the_gap"
    assert diagnose_next_action("", False, 0, 0) == "settled"


# ---------------------------------------------------------------- the cause the row may claim


def test_the_row_states_the_FACT_but_defers_a_cause_it_does_not_own() -> None:
    """R2a one renderer further along. The count (zero tests) is true either way; the CAUSE is not.
    Asserting "ABSENT tests" over an unimportable module put two contradicting lines in one report
    eight lines apart, and left the reader no basis to choose between them."""
    assert no_tests_attribution(0, load_failed=True) == "cause_below"
    assert no_tests_attribution(0, load_failed=False) == "absent_tests"
    assert no_tests_attribution(5, load_failed=True) == "silent"


def test_cause_below_is_not_silence() -> None:
    """Suppressing the row entirely would drop a TRUE observation. "We did not say" and "there is
    nothing to say" are different, which is this project's whole subject."""
    assert no_tests_attribution(0, load_failed=True) != "silent"


# ---------------------------------------------------------------- what the report actually says


def test_a_load_failure_is_NAMED_with_its_reason() -> None:
    """A refusal that cannot name its cause sends the reader to look at the whole world. The
    interpreter's own exception text is the one thing that points at the fix."""
    out = _format_scope(_scope(load_failure="ModuleNotFoundError: No module named 'funcy'"))
    assert "STOP:" in out
    assert "No module named 'funcy'" in out


def test_the_report_never_contradicts_itself_about_WHY() -> None:
    """The defect in one assertion: the ABSENT-tests claim and the STOP block cannot both appear."""
    out = _format_scope(_scope(load_failure="ImportError: boom"))
    assert "reflect ABSENT tests" not in out
    assert "not a measurement at all" in out


def test_it_does_not_send_the_reader_to_converge() -> None:
    """The spiral this closes: diagnose said `converge`, and converge on the same target refuses for
    the import. Naming the failure without withdrawing the instruction would leave the loop intact."""
    out = _format_scope(_scope(load_failure="ImportError: boom"))
    assert "DO THIS:  detective converge" not in out
    assert "Not converge" in out


def test_a_HEALTHY_module_with_no_tests_is_unaffected() -> None:
    """The non-regression that matters: "you have no tests" is a useful thing to say, and it is what
    stops a reader reading 0-pinned as weak tests. The repair must only fire when a load failure
    makes that attribution false."""
    out = _format_scope(_scope(load_failure="", tests_discovered=0))
    assert "reflect ABSENT tests, not weak ones." in out
    assert "STOP:" not in out
    assert "DO THIS:  detective converge" in out
