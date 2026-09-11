"""The argument-order budget must be VISIBLE, or a narrowed measurement reads as a complete one.

THE GAP, verified by AST query on 2026-09-11: Wesker's operator census has carried a `withheld`
count since policy 7, and Detective referenced `operator_census` in EXACTLY ZERO places. So a run
where the per-call-site budget declined to ask some argument-order questions produced a certificate
byte-identical to one where every question was asked. That is the project's own named failure —
absence of evidence wearing the costume of evidence of absence — sitting one layer above the engine
that had already measured it correctly.

THE RULE: withheld is neither a gap nor a pass. "Never asked" and "asked, and no distinguishing
input was found" are different states with different remedies, and the report must keep them apart.
Spending the budget changes the recorded evidence state; it never changes what "verified" means.

INTENT tests: a characterization would pin whatever the renderer does today, including saying
nothing. These say what it must do.
"""

from __future__ import annotations

from dataclasses import asdict

import pytest

from Detective.converge import ConvergeResult, _swap_census_counts, swap_budget_disclosure

# ── the pure decision ──────────────────────────────────────────────────────────


def test_nothing_withheld_is_silent():
    """A withholding line on a run that withheld nothing would teach the reader to skip the line
    on the runs that matter."""
    assert swap_budget_disclosure(0, 12) == "not_budgeted"


def test_some_asked_and_some_not_is_partial():
    assert swap_budget_disclosure(5, 11) == "budgeted_partial"


def test_none_asked_at_all_is_its_own_state():
    """Distinct from partial: no argument-order evidence was gathered, so there is nothing to be
    partially confident about. Collapsing the two would let a run that asked NOTHING report the
    same standing as one that asked most."""
    assert swap_budget_disclosure(15, 0) == "budgeted_none"


@pytest.mark.parametrize("withheld", [0, -1, -99])
def test_a_non_positive_withheld_count_never_announces_a_narrowing(withheld):
    """Defensive in the honest direction: an engine that reports a nonsense count must not make
    Detective announce a withholding nobody measured."""
    assert swap_budget_disclosure(withheld, 3) == "not_budgeted"


def test_the_three_states_are_three_distinct_signifiers():
    assert (
        len({swap_budget_disclosure(0, 3), swap_budget_disclosure(2, 3), swap_budget_disclosure(2, 0)}) == 3
    )


def test_no_state_is_a_failure():
    """A withheld question is a question the POLICY declined to ask, not a defect in the suite.
    Nothing here may spell like one, because the CLI branches on these names."""
    for state in ("not_budgeted", "budgeted_partial", "budgeted_none"):
        assert "fail" not in state and "gap" not in state and "incomplete" not in state


# ── reading the engine's census ────────────────────────────────────────────────


class _Cat:
    """Stands in for Wesker's MutationCategory member, which the census is keyed by."""

    def __init__(self, value):
        self.value = value


class _Profile:
    def __init__(self, census):
        self.operator_census = census


def test_the_swap_row_is_read_off_the_census():
    prof = _Profile({_Cat("SWAP"): {"generated": 11, "withheld": 5, "disposition": "generated"}})
    assert _swap_census_counts(prof) == (5, 11)


def test_a_census_without_swap_withholds_nothing():
    prof = _Profile({_Cat("VALUE"): {"generated": 9, "withheld": 0}})
    assert _swap_census_counts(prof) == (0, 0)


def test_an_engine_with_no_census_degrades_to_nothing_withheld():
    """Detective resolves against a FLOOR Wesker. An engine predating the census must not raise,
    and must not be read as having withheld something — that direction claims no narrowing, where
    the opposite would announce one nobody measured."""

    class _Old:
        pass

    assert _swap_census_counts(_Old()) == (0, 0)
    assert _swap_census_counts(_Profile(None)) == (0, 0)


def test_a_census_row_missing_the_withheld_key_is_not_a_crash():
    """A policy-6 engine's census rows have no `withheld` for SWAP."""
    prof = _Profile({_Cat("SWAP"): {"generated": 4}})
    assert _swap_census_counts(prof) == (0, 4)


# ── the decision travels to consumers ──────────────────────────────────────────


def _result(**kw) -> ConvergeResult:
    """A minimally-populated result; only the budget fields matter to these tests."""
    base = dict(
        function="m.py::f",
        converged=True,
        at_ceiling=False,
        initial_survivors=0,
        final_survivors=0,
        iterations=(),
        written_path=None,
    )
    return ConvergeResult(**{**base, **kw})


def test_the_result_carries_the_decision_not_just_the_count():
    """`--json` serializes dataclass fields (`asdict(result)` in `_run_converge`), so the
    CONCLUSION has to be a field. Shipping only the count would hand every consumer the job of
    re-deriving a narrower proxy — the defect class this project names, one layer out."""
    payload = asdict(_result(swap_withheld=5, swap_budget="budgeted_partial"))
    assert payload["swap_withheld"] == 5
    assert payload["swap_budget"] == "budgeted_partial"


def test_the_default_result_claims_no_narrowing():
    """Every construction site that does not set these must read as 'nothing withheld'."""
    r = _result()
    assert (r.swap_withheld, r.swap_budget) == (0, "not_budgeted")


def test_the_renderers_speak_only_when_something_was_withheld():
    """Both the banner and the archived report read the SAME field — one derivation, N renderers.
    A run that withheld nothing prints no line; a run that withheld something prints one on both
    surfaces, so a reader cannot get the complete-looking view by choosing a different one."""
    from Detective.cli import _format_converge, _format_converge_terse

    quiet = _result()
    loud = _result(swap_withheld=5, swap_budget="budgeted_partial")
    for render in (
        lambda r: _format_converge(r),
        lambda r: _format_converge_terse(r, report_path=""),
    ):
        assert "order withheld" not in render(quiet)
        out = render(loud)
        assert "order withheld" in out
        assert "5 argument-order question(s)" in out


def test_asking_none_at_all_reads_differently_from_asking_most():
    """The two budgeted states must not render identically, or the distinct decision is decorative."""
    from Detective.cli import _format_converge_terse

    partial = _format_converge_terse(_result(swap_withheld=5, swap_budget="budgeted_partial"), "")
    none_asked = _format_converge_terse(_result(swap_withheld=15, swap_budget="budgeted_none"), "")
    assert partial != none_asked
