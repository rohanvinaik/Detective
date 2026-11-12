"""Intent: Detective#80 — the witness search names WHY it could not classify a mutant.

The defect, verbatim from the issue: "`blocked` renders as `wall-undetermined`, but an uncopyable input,
a refused write or effect, an equal truncated iterator and a missing payload also set it." Six causes
with six different remedies shared one code and one page sentence: a person told a wall had fired went
looking for a slow machine when the input could not be copied. A cause is now a named code on the pair,
the search, the verdict, the survivor report, the decision record and the page.

And the original's own cap: the search runs the ORIGINAL under Wesker's probe cap (`STEP_PROBE_CAP`). An
original that runs past it is NOT refused: the count cannot decide that input, so the comparison is
UNARMED, as the engine leaves an observation whose original did not finish inside the cap. The original
runs again under the wall alone, the mutant uncapped by count, and only `wall-undetermined` can block it.

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
        # an ORIGINAL the count stopped and nobody re-ran unarmed: only the wall can bound it
        (_OUTCOME_DIVERGED, "1", True, "wall-undetermined"),
        (_OUTCOME_DIVERGED, _OUTCOME_TIMEOUT, True, "wall-undetermined"),
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


def test_an_original_past_the_probe_cap_is_compared_unarmed_not_refused():
    # 300,000 iterations of the ORIGINAL, past the cap: the count cannot decide it, the wall bounds it.
    differs = lambda n: -1  # noqa: E731
    pair = _observe_pair(_unbounded_loop, differs, (STEP_PROBE_CAP + 100_000,), None)
    assert (pair.disposition, pair.cause) == ("witness", "")
    same = _observe_pair(_unbounded_loop, _unbounded_loop, (STEP_PROBE_CAP + 100_000,), None)
    assert (same.disposition, same.cause) == ("same", "")


def test_the_mutant_is_uncapped_by_count_where_there_is_no_original_count():
    # The mutant does as much work as the original (past the cap); with no original count to scale from
    # it is not stopped by one.
    pair = _observe_pair(_unbounded_loop, _longer_loop, (STEP_PROBE_CAP + 100_000,), None)
    assert pair.disposition == "witness" and pair.cause == ""


def test_where_the_original_finished_the_mutants_count_cap_is_unchanged():
    def forever(n):
        while True:
            pass

    pair = _observe_pair(_unbounded_loop, forever, (50,), None)
    assert pair.disposition == "step-budget-divergent"


def test_a_search_over_an_original_that_loops_300000_times_still_classifies():
    search = _search_witness_detail(_unbounded_loop, _longer_loop, [(300_000,)])
    assert search.witness is not None and not search.blocked and search.blocked_cause == ""


def _longer_loop(n):
    i = 0
    while i < n:
        i += 1
    return i + 1


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
    rows = _blocked_cause_rows((("M1", "wall-undetermined"), ("M2", "uncopyable-input")))
    text = "\n".join(rows)
    assert "wall-undetermined" in text and "wall-clock bound" in text
    assert "uncopyable-input" in text and "built fresh" in text
    assert "original-step-budget" not in text
    assert _blocked_cause_rows(()) == []


# ── the per-call wall follows the machine ───────────────────────────────────────


def test_the_classifier_wall_is_stretched_by_the_calibrated_slowdown(monkeypatch):
    import time

    from Wesker import monitoring

    from Detective.equivalence import _CLASSIFY_TIMEOUT_S, _outcome_budget_s

    monkeypatch.setattr(monitoring, "machine_slowdown", lambda refresh=False: (4.0, "slower"))
    assert _outcome_budget_s(None) == _CLASSIFY_TIMEOUT_S * 4.0
    # a real aggregate deadline is never stretched
    assert _outcome_budget_s(time.monotonic() + 1.0) <= 1.0
    monkeypatch.setattr(monitoring, "machine_slowdown", lambda refresh=False: (1.0, "reference"))
    assert _outcome_budget_s(None) == _CLASSIFY_TIMEOUT_S
    monkeypatch.setattr(monitoring, "machine_slowdown", lambda refresh=False: (0.2, "reference"))
    assert _outcome_budget_s(None) == _CLASSIFY_TIMEOUT_S
