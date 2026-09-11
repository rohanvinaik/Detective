"""A baseline's UNASKED argument-order questions must reach the preservation verdict.

THE DEFECT, reproduced through the real CLI on 2026-09-11. A six-argument wrapper converges
`✓ COMPLETE · 12/12 killed` and discloses `5 argument-order question(s) were not asked`. Take a
receipt, transpose the first and last arguments — a pair the budget withheld — and `verify-rewrite`
answers `✓ PRESERVED`, exit 0, for a rewrite that computes 66 where the original computes 91.

Traced with Serena: the budget signal lived only in `converge.py` and `cli.py` and appeared NOWHERE
in `rewrite.py`. `RewriteReceipt` had no field for it, so `make_receipt` never recorded it and
`rewrite_verdict` could not see it. A render-only leaf — the project's own "trace the signal to the
decision" failure, one field over from where the same class of hole was closed for `policy_id`.

Worse than a known gap: whether such a rewrite is caught at all depends on whether some unrelated
test's input happens to separate those positions. The FIRST attempt at this reproduction returned
CHANGED for exactly that reason — a synthesized golden of (1,2,3,4,5,6) incidentally distinguished
the pair. So the verdict was decided by luck, and recorded that nowhere.

THE RULE: withheld questions withhold PRESERVED — the "unverified but not failing" grade — and they
do so BELOW the CHANGED branch, so a directly observed difference is never hidden behind an
abstention about what the baseline failed to ask.
"""

from __future__ import annotations

import pytest

from Detective.rewrite import RewriteReceipt, order_evidence_standing, rewrite_verdict

# ── the pure decision ──────────────────────────────────────────────────────────


def test_a_fully_asked_baseline_is_clear():
    assert order_evidence_standing("not_budgeted") == "clear"


@pytest.mark.parametrize("state", ["budgeted_partial", "budgeted_none"])
def test_a_budgeted_baseline_is_withheld(state):
    """The measured case: the engine asked some pairs and declined others."""
    assert order_evidence_standing(state) == "baseline_order_withheld"


def test_an_unreportable_census_is_its_own_cause():
    """Distinct from withholding: nobody established whether anything was withheld. The remedy is a
    newer engine, not a distinguishing input, so it cannot share a code."""
    assert order_evidence_standing("unavailable") == "order_census_unavailable"


def test_a_receipt_predating_the_field_is_unrecorded_not_clear():
    """THE SERIALIZATION BOUNDARY. A pre-policy-7 receipt has no budget field. Reading `None` as
    "nothing withheld" would rebuild the missing-census blur one layer out — at load time, where it
    is even harder to see."""
    assert order_evidence_standing(None) == "unrecorded"


def test_the_four_causes_are_four_distinct_signifiers():
    seen = {order_evidence_standing(s) for s in ("not_budgeted", "budgeted_partial", "unavailable", None)}
    assert seen == {"clear", "baseline_order_withheld", "order_census_unavailable", "unrecorded"}


def test_only_clear_permits_preservation():
    for state in ("budgeted_partial", "budgeted_none", "unavailable", None):
        assert order_evidence_standing(state) != "clear"


# ── the receipt carries it, and an absent field stays UNKNOWN ──────────────────


def _receipt(**kw) -> RewriteReceipt:
    import ast
    import hashlib

    from Detective import pins

    src = "def f(x):\n    return x + 1\n"
    node = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef))
    base = dict(
        function="m.py::f",
        original_source=src,
        source_digest=hashlib.sha256(src.encode()).hexdigest(),
        function_digest=pins.function_digest(node),
        policy_id="7.test",
        universe_size=1,
        proof_suite=(),
        proof_status="passed",
        functionally_complete=True,
    )
    return RewriteReceipt(**{**base, **kw})


def test_an_old_receipt_round_trips_as_unknown_never_as_clear():
    """A receipt serialized before the field existed must come back UNKNOWN. Defaulting the count
    to 0 here is what the reviewer caught: it would reproduce the census blur at the load boundary,
    where a pre-policy-7 receipt would silently assert that nothing was withheld."""
    rec = _receipt()
    assert rec.swap_budget is None and rec.swap_withheld is None
    back = RewriteReceipt.from_json(rec.to_json())
    assert back.swap_budget is None
    assert order_evidence_standing(back.swap_budget) == "unrecorded"


def test_a_recorded_budget_survives_the_round_trip():
    back = RewriteReceipt.from_json(_receipt(swap_budget="budgeted_partial", swap_withheld=5).to_json())
    assert (back.swap_budget, back.swap_withheld) == ("budgeted_partial", 5)
    assert order_evidence_standing(back.swap_budget) == "baseline_order_withheld"


# ── the verdict: withheld withholds PRESERVED, but never outranks CHANGED ──────

_SOUND = dict(receipt_valid=True, classification_ran=True, proof_replayed_ok=True)


def test_a_clear_baseline_can_still_be_preserved():
    """The gate must not become a wall: a fully-measured, matching baseline still certifies."""
    assert rewrite_verdict(**_SOUND, new_dimensions=0, differences=0, abstentions=0) == "PRESERVED"
    assert (
        rewrite_verdict(**_SOUND, new_dimensions=0, differences=0, abstentions=0, order_clear=True)
        == "PRESERVED"
    )


def test_a_withheld_baseline_cannot_be_preserved():
    """The defect, as a unit: everything else discharged, and PRESERVED is still unavailable."""
    assert (
        rewrite_verdict(**_SOUND, new_dimensions=0, differences=0, abstentions=0, order_clear=False)
        == "ABSTAIN"
    )


def test_an_observed_difference_still_reads_CHANGED_when_order_is_withheld():
    """THE PRECEDENCE RULE, and the most dangerous part of this fix. A difference is a DIRECT
    OBSERVATION — both implementations executed at a concrete input — not an inference from the
    baseline. Folding the withheld gate in above the CHANGED branch would report ABSTAIN for a
    rewrite that provably broke something, hiding the very difference a supplied input was
    requested to expose. That would be worse than the hole this closes."""
    assert (
        rewrite_verdict(**_SOUND, new_dimensions=0, differences=1, abstentions=0, order_clear=False)
        == "CHANGED"
    )
    # Same, via a failing replay rather than a witness.
    assert (
        rewrite_verdict(
            receipt_valid=True,
            classification_ran=True,
            proof_replayed_ok=False,
            new_dimensions=0,
            differences=0,
            abstentions=0,
            order_clear=False,
        )
        == "CHANGED"
    )


def test_a_new_dimension_still_reads_UNREVIEWED_when_order_is_withheld():
    """UNREVIEWED means the REWRITE added a dimension; withheld means the ORIGINAL never asked one.
    Different facts, and the more specific one keeps its name."""
    assert (
        rewrite_verdict(**_SOUND, new_dimensions=1, differences=0, abstentions=0, order_clear=False)
        == "UNREVIEWED"
    )


def test_the_default_keeps_every_existing_caller_unchanged():
    """`order_clear` defaults True so the pinned behaviour of every call that predates it is
    byte-identical — this fix adds a gate, it does not re-decide old ones."""
    for diffs, dims, abst in ((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)):
        assert rewrite_verdict(
            **_SOUND, new_dimensions=dims, differences=diffs, abstentions=abst
        ) == rewrite_verdict(
            **_SOUND, new_dimensions=dims, differences=diffs, abstentions=abst, order_clear=True
        )


@pytest.mark.xfail(
    reason="OPEN QUESTION, recorded not fixed: the same argument — a directly observed difference "
    "outranks a weak baseline — applies to the EXISTING receipt_valid causes, which are checked "
    "above CHANGED. Founder's call was to leave that pinned ordering alone in this change.",
    strict=True,
)
def test_an_observed_difference_outranks_an_invalid_baseline_too():
    assert (
        rewrite_verdict(
            receipt_valid=False,
            classification_ran=True,
            proof_replayed_ok=True,
            new_dimensions=0,
            differences=1,
            abstentions=0,
        )
        == "CHANGED"
    )
