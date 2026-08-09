"""Intent test for the aggregate-wall question (Detective #31, found via ty).

Four sites asked "is the wall gone" and three spellings answered it:

    engine.classify_survivors._cls_exhausted   _b = _cls_budget_ms(); _b is not None and _b <= 0
    converge (loop)                            _deadline_ms is not None and _budget_ms() <= 0.0
    converge (final)                           _deadline_ms is not None and _budget_ms() <= 0.0
    decompose_apply                            _deadline_ms is not None and _budget_ms() <= 0.0

The three outliers guard on a DIFFERENT NAME than the one they read. That is correct only
because `remaining_budget_ms` returns None exactly when the deadline is None — an invariant
living in another variable, which no reader reconstructs at the use site and no checker can
see. `_cls_exhausted` already had the right shape; the other three had drifted from it.

Surfaced by `ty` as `unsupported-operator: None <= float`. Worth recording HOW: a grep for
`_budget_ms` finds two definitions and invites the assumption they are one symbol.
`find_referencing_symbols` shows they are two separate closures AND surfaces a third consumer
under a different spelling (`_cls_budget_ms`) that grep never returns — the one that already
had the fix. Strings found two sites; references found the pattern.
"""

from __future__ import annotations

from Detective._contain import budget_is_exhausted, remaining_budget_ms


def test_no_declared_wall_is_never_exhausted():
    """THE case the type error was pointing at.

    `None` means no deadline was declared, so the answer is False forever. Treating it as
    falsy-therefore-done would cut every unbounded run at its first check — the opposite of
    what an absent budget means.
    """
    assert budget_is_exhausted(None) is False


def test_a_spent_wall_is_exhausted():
    assert budget_is_exhausted(0.0) is True
    assert budget_is_exhausted(-1.0) is True


def test_a_remaining_wall_is_not():
    assert budget_is_exhausted(0.1) is False
    assert budget_is_exhausted(5000.0) is False


def test_it_agrees_with_the_producer_it_consumes():
    """The invariant the three outlier sites relied on, stated where it is used rather than
    inferred across forty lines: `remaining_budget_ms` returns None iff the deadline is None,
    and a deadline already spent clamps to 0.0 — never negative, which by sign would read as
    unbounded."""
    assert remaining_budget_ms(None, 5.0) is None
    assert budget_is_exhausted(remaining_budget_ms(None, 5.0)) is False
    assert remaining_budget_ms(100.0, 500.0) == 0.0
    assert budget_is_exhausted(remaining_budget_ms(100.0, 500.0)) is True
    assert budget_is_exhausted(remaining_budget_ms(1000.0, 1.0)) is False
