"""Ledger B: installation/entry failures remain unmeasured, not a trace-budget problem."""

from _support import make_pr
from Wesker.engine import CategoryResult, MutationCategory

from Detective.validity import measurement_cut_reasons, normalize_validity


def test_failed_evaluation_has_its_own_reason():
    assert measurement_cut_reasons(True, False, False, "exhaustive", "contained", False, False, True) == (
        "mutant_evaluation_failed",
    )
    assert measurement_cut_reasons(True, True, False, "exhaustive", "contained", False, False, False) == ()


def test_uninstalled_and_unentered_mutants_cannot_empty_the_certificate_universe():
    for reason in ("harness_error", "not_installed", "not_entered"):
        result = make_pr()
        category = CategoryResult(category=MutationCategory.VALUE)
        category.unscored_by[reason] = 1
        result.per_category = [category]
        result.is_gateable = False
        result.coverage_depth = "exhaustive"
        validity = normalize_validity(result)
        assert not validity.admits_certificate
        assert validity.cut_reasons == ("mutant_evaluation_failed",)
