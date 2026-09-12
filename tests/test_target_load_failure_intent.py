"""Intent tests for R1 — a target that never imported cannot support a certificate.

Design: `docs/CORRECTNESS_REPAIRS_2026-09-08.md` §R1.

The defect, observed 2026-09-08 on conorheins `jax_backend/src/utils.py::str2bool` with
funcy/jax/matplotlib absent: the module could not be imported, so no mutant was ever evaluated —
`0/27 killed`, `0 pinned`, `27 unclassified — the search could not run on them` — and converge
answered with `AUTHOR INPUTS`, justified by "Every killable mutant is already dead", at **exit 0**.
Supplying the requested inputs returned byte-identical output. A spiral whose printed instruction
could not change the state it described.

The cause was not a missing signal. `measurement_cut_reasons` had no load-failure parameter, so a
load-failed run produced NO cut reason, `admits_certificate` stayed True, `certificate_standing`
read clean, and all three standing guards passed. `audit` had the fact and ANDed a local
`not _load_failed` into its own completeness — correct for audit, invisible to everyone else, and
exactly the "re-derive a narrower proxy" shape this module exists to end.

These pin the repair from intent:

1. The refusal is CARRIED, not re-derived — one validity object, every consumer reads it.
2. The refusal is TYPED. An anonymous `admits_certificate=False` beside no reason is the "empty
   reason list beside a refusal" state `measurement_cut_reasons` was written to prevent.
3. It does not MASK other reasons, and it does not get masked BY them.
4. A caller that cannot supply it is byte-for-byte unchanged (#60).
"""

from __future__ import annotations

from Detective.validity import (
    CUT_REASONS,
    cut_reason_sentence,
    measurement_cut_reasons,
    normalize_validity,
)


class _Result:
    """A Wesker profiling result that is clean on every axis the engine reports.

    The point of the fixture: the PROFILE genuinely succeeds. Mutants are generated from the AST,
    which needs no import, so nothing Wesker reports is wrong. The load failure is Detective's own
    later discovery, which is why it arrives as a caller-supplied fact.
    """

    def __init__(self, **kw):
        self.is_gateable = True
        self.budget_exhausted = False
        self.coverage_depth = "exhaustive"
        self.all_contained = True
        self.collection_conflicts = ()
        self.collection_errors = ()
        self.execution_mode = "isolated"
        self.per_category = ()
        self.__dict__.update(kw)


def test_a_target_that_never_imported_cannot_admit_a_certificate():
    """THE defect. Every engine-reported axis is clean, because the profile really did succeed —
    and the run still measured nothing."""
    v = normalize_validity(_Result(), load_failed=True)
    assert v.admits_certificate is False


def test_the_refusal_carries_a_typed_reason_not_an_anonymous_false():
    """An `admits_certificate=False` with an empty reason list reads as 'no problems found' — the
    exact shape this vocabulary exists to prevent, and how a refusal gets talked past."""
    v = normalize_validity(_Result(), load_failed=True)
    assert "target_load_failed" in v.cut_reasons
    assert "target_load_failed" in CUT_REASONS


def test_a_loading_target_is_unaffected():
    """The reason must fire on the fact, not on the code path. A clean run stays clean."""
    v = normalize_validity(_Result(), load_failed=False)
    assert "target_load_failed" not in v.cut_reasons
    assert v.admits_certificate is True


def test_a_caller_that_cannot_supply_the_fact_is_unchanged():
    """#60, the unnamed-capability contract, in the direction that matters here: `classify_survivors`
    and `profile` call this BEFORE the load is attempted and legitimately cannot know. They must
    not be refused for asking early."""
    assert normalize_validity(_Result()).admits_certificate is True
    assert normalize_validity(_Result()).cut_reasons == ()


def test_the_load_failure_is_named_first():
    """Nothing downstream of a failed import is meaningful — every other count on the run describes
    an empty observation — so a reader scanning the reasons must meet the cause before its
    consequences."""
    reasons = measurement_cut_reasons(
        reported_gateable=True,
        gateable=False,
        budget_exhausted=True,
        coverage_depth="cut",
        containment="uncontained",
        identity_ambiguous=True,
        collection_incomplete=True,
        construction_failed=True,
        not_installed=True,
        not_entered=True,
        target_load_failed=True,
    )
    assert reasons[0] == "target_load_failed"


def test_it_neither_masks_other_reasons_nor_is_masked_by_them():
    """Plural on purpose. Reporting only the first makes the second invisible to whoever fixes the
    first — they re-run, hit the next refusal, and cannot tell it was always there."""
    reasons = measurement_cut_reasons(
        reported_gateable=True,
        gateable=False,
        budget_exhausted=True,
        coverage_depth="unreported",
        containment="contained",
        identity_ambiguous=False,
        collection_incomplete=True,
        target_load_failed=True,
    )
    assert set(reasons) >= {"target_load_failed", "budget_exhausted", "collection_incomplete"}


def test_it_does_not_trigger_the_unspecified_fallback():
    """`engine_refused_unspecified` fires only when a refusal has no explanation. A load failure IS
    the explanation, so producing both would report one refusal as two."""
    reasons = measurement_cut_reasons(
        reported_gateable=True,
        gateable=False,
        budget_exhausted=False,
        coverage_depth="unreported",
        containment="contained",
        identity_ambiguous=False,
        target_load_failed=True,
    )
    assert reasons == ("target_load_failed",)


def test_the_sentence_rules_out_the_three_remedies_that_spiralled():
    """The operator followed `--input` and it changed nothing; the older routing offered
    `regime --migrate` and `--trace-budget`, neither of which can fix an import. The sentence must
    close those doors explicitly, or the next reader tries them again."""
    s = cut_reason_sentence("target_load_failed")
    assert "could not be imported" in s
    assert "--input" in s
    assert "--deadline" in s
    assert "regime" in s
    assert "dependencies" in s


def test_a_load_failed_run_with_nothing_outstanding_is_still_refused():
    """The LATENT case, worse than the observed one and reachable by inspection: converge's
    `settled` fires on `not (has_killable or has_line_gap)`, which is satisfiable by a load-failed
    target that has no static line gap — DONE over a run that measured nothing. `settled` is only
    reachable once the standing guards pass, so the refusal has to live here."""
    v = normalize_validity(_Result(), load_failed=True)
    assert v.admits_certificate is False, "a run that measured nothing must never reach settled"
