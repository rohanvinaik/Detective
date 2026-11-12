"""Intent: Detective#80 — the witness search names WHY it could not classify a mutant.

The defect, verbatim from the issue: "`blocked` renders as `wall-undetermined`, but an uncopyable input,
a refused write or effect, an equal truncated iterator and a missing payload also set it." Six causes
with six different remedies shared one code and one page sentence: a person told a wall had fired went
looking for a slow machine when the input could not be copied. A cause is now a named code on the pair,
the search, the verdict, the survivor report, the decision record and the page.

And the original's own cap: the search ran the ORIGINAL with `cap=None`, so a 5 s wall decided whether
it finished, which is a different answer on every machine. It now runs under Wesker's probe cap
(`STEP_PROBE_CAP`), and an original that cannot finish inside it is `original-step-budget`: no evidence
either way, and the mutant is not run against nothing.

`terminated-distinct` / `terminated-same` were considered and not added: they are renames of `witness`
and `same`, which already mean exactly "both sides terminated and the outcomes differ / agree".
"""

from __future__ import annotations

import pytest
from Wesker.monitoring import STEP_PROBE_CAP

from Detective.cli import _blocked_cause_rows, blocked_cause_groups
from Detective.equivalence import (
    _OUTCOME_DIVERGED,
    _OUTCOME_EFFECT_REFUSED,
    _OUTCOME_TIMEOUT,
    _OUTCOME_UNCOPYABLE,
    _OUTCOME_WRITE_REFUSED,
    BLOCKED_CAUSES,
    MutantVerdict,
    _observe_pair,
    _pair_disposition,
    _search_witness_detail,
    blocked_cause,
    dominant_blocked_cause,
)

TRUNC = "<iter~trunc map ['1']>"


@pytest.mark.parametrize(
    ("original", "mutant", "payload", "cause"),
    [
        (_OUTCOME_TIMEOUT, "1", True, "wall-undetermined"),
        ("1", _OUTCOME_TIMEOUT, True, "wall-undetermined"),
        (_OUTCOME_UNCOPYABLE, "1", True, "uncopyable-input"),
        ("1", _OUTCOME_UNCOPYABLE, True, "uncopyable-input"),
        (_OUTCOME_WRITE_REFUSED, "1", True, "write-refused"),
        ("1", _OUTCOME_EFFECT_REFUSED, True, "effect-refused"),
        (TRUNC, TRUNC, True, "truncated-iterator"),
        ("1", "2", False, "payload-missing"),
        # the ORIGINAL exceeding its probe budget is its own cause
        (_OUTCOME_DIVERGED, "1", True, "original-step-budget"),
        (_OUTCOME_DIVERGED, _OUTCOME_TIMEOUT, True, "original-step-budget"),
        # the original is read first, as the pair always was
        (_OUTCOME_TIMEOUT, _OUTCOME_UNCOPYABLE, True, "wall-undetermined"),
        # not blocked
        ("1", "1", True, ""),
        ("1", "2", True, ""),
        ("1", _OUTCOME_DIVERGED, True, ""),  # the MUTANT diverging is a finding, not a block
        ("1", "1", False, ""),  # equal outcomes need no payload
        ("1", "<raised ValueError>", True, ""),
    ],
)
def test_the_cause_of_a_blocked_pair_is_named(original, mutant, payload, cause):
    assert blocked_cause(original, mutant, payload) == cause


def test_blocked_cause_and_pair_disposition_agree_on_what_is_blocked():
    outcomes = [
        "1",
        "2",
        "<raised E>",
        TRUNC,
        _OUTCOME_TIMEOUT,
        _OUTCOME_UNCOPYABLE,
        _OUTCOME_WRITE_REFUSED,
        _OUTCOME_EFFECT_REFUSED,
        _OUTCOME_DIVERGED,
    ]
    for original in outcomes:
        for mutant in outcomes:
            blocked = _pair_disposition(original, mutant) == "blocked"
            assert blocked == bool(blocked_cause(original, mutant, True)), (original, mutant)


def test_every_named_cause_has_a_sentence_and_no_two_share_one():
    from Detective.cli import _BLOCKED_CAUSE_SENTENCES

    # write and effect refusals have their own rows; every other cause is worded here, differently
    worded = [c for c in BLOCKED_CAUSES if c not in ("write-refused", "effect-refused")]
    assert set(worded) == set(_BLOCKED_CAUSE_SENTENCES)
    assert len(set(_BLOCKED_CAUSE_SENTENCES.values())) == len(_BLOCKED_CAUSE_SENTENCES)


def test_one_cause_is_reported_when_several_blocked_a_search():
    assert dominant_blocked_cause([]) == ""
    assert dominant_blocked_cause(["deadline-exhausted", "wall-undetermined"]) == "wall-undetermined"
    assert dominant_blocked_cause(["payload-missing", "uncopyable-input"]) == "uncopyable-input"
    # an unnamed cause is still reported, after every named one
    assert dominant_blocked_cause(["mystery"]) == "mystery"
    assert dominant_blocked_cause(["mystery", "deadline-exhausted"]) == "deadline-exhausted"


def _same(x):
    return x


def _plus_one(x):
    return x + 1


def test_a_search_blocked_by_an_uncopyable_input_says_so():
    class Once:
        def __deepcopy__(self, memo):
            raise TypeError("single use")

    search = _search_witness_detail(_same, _plus_one, [(Once(),)])
    assert search.blocked and search.witness is None
    assert search.blocked_cause == "uncopyable-input"


def test_a_search_with_no_blocking_names_no_cause():
    search = _search_witness_detail(_same, _plus_one, [(1,)])
    assert not search.blocked and search.witness is not None
    assert search.blocked_cause == ""


def test_a_spent_deadline_is_its_own_cause():
    search = _search_witness_detail(_same, _plus_one, [(1,), (2,)], deadline=0.0)
    assert search.blocked and search.blocked_cause == "deadline-exhausted"


def test_the_verdict_carries_the_cause_and_its_label_is_the_cause():
    base = dict(
        mutant_id="m",
        category="VALUE",
        diff_summary="",
        killable=False,
        witness=None,
        searched=1,
    )
    assert MutantVerdict(**base, blocked=True, blocked_cause="uncopyable-input").label == "uncopyable-input"
    assert MutantVerdict(**base, blocked=True, blocked_cause="wall-undetermined").label == "wall-undetermined"
    # a blocked verdict built with no cause is not dressed as a wall
    assert MutantVerdict(**base, blocked=True).label == "unclassified"


# ── the original's own cap ──────────────────────────────────────────────────────


def _unbounded_loop(n):
    i = 0
    while i < n:
        i += 1
    return i


def test_an_original_that_cannot_finish_its_probe_budget_is_named_and_the_mutant_is_not_run():
    ran: list[str] = []

    def mutant(n):
        ran.append("mutant")
        return 0

    pair = _observe_pair(_unbounded_loop, mutant, (STEP_PROBE_CAP * 10,), None)
    assert (pair.disposition, pair.cause) == ("blocked", "original-step-budget")
    assert ran == [], "a mutant is not run against an original that produced nothing"


def test_the_budget_is_the_count_not_the_clock():
    # Well inside the 5 s wall, far past the cap: the count decides, so the answer does not depend on
    # how fast the machine is.
    pair = _observe_pair(_unbounded_loop, _unbounded_loop, (STEP_PROBE_CAP + 100,), None)
    assert pair.cause == "original-step-budget"
    ok = _observe_pair(_unbounded_loop, _unbounded_loop, (STEP_PROBE_CAP - 10,), None)
    assert (ok.disposition, ok.cause) == ("same", "")


# ── the page ────────────────────────────────────────────────────────────────────


def test_causes_are_grouped_in_order_and_refusals_are_left_to_their_own_rows():
    causes = (
        ("M1", "deadline-exhausted"),
        ("M2", "uncopyable-input"),
        ("M3", "write-refused"),
        ("M4", "uncopyable-input"),
        ("M5", "effect-refused"),
        ("M6", "mystery"),
    )
    assert blocked_cause_groups(causes) == (
        ("uncopyable-input", ("M2", "M4")),
        ("deadline-exhausted", ("M1",)),
        ("mystery", ("M6",)),
    )


def test_the_page_says_a_different_thing_for_each_cause():
    rows = _blocked_cause_rows(
        (("M1", "wall-undetermined"), ("M2", "uncopyable-input"), ("M3", "original-step-budget"))
    )
    text = "\n".join(rows)
    assert "wall-undetermined" in text and "wall-clock bound" in text
    assert "uncopyable-input" in text and "built fresh" in text
    assert "original-step-budget" in text and "probe budget" in text
    assert _blocked_cause_rows(()) == []
