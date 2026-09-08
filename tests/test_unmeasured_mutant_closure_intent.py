"""Ledger B: installation/entry failures remain unmeasured, not a trace-budget problem.

Updated 2026-09-08 for S13. The original intent — an unscored mutant cuts the run and is NOT a
budget problem — is unchanged and still pinned below. What changed is the vocabulary: these were
collapsed into one `mutant_evaluation_failed` reason rendered "the harness failed".

Wesker's `mutant_disposition` distinguishes them deliberately, and its docstring says why:

  * ``harness_error``  — never built. "Says nothing about any test."
  * ``not_installed``  — built, but no call site was rebound. "A survivor here is a patch blind
    spot, not a specification gap" (an lru_cache/partial-wrapped target lands here).
  * ``not_entered``    — installed, but the test never called it. "The classic decorator and
    registry capture: the namespace holds the mutant while the caller holds the original."

Three causes, three remedies — report a defect / unwrap the target / route a test through the
patched name — and one sentence that named only the first. This file's own title distinguished
installation from entry while its assertion merged them, which is how the collapse survived.
"""

from _support import make_pr
from Wesker.engine import CategoryResult, MutationCategory

from Detective.validity import cut_reason_sentence, measurement_cut_reasons, normalize_validity


def test_each_unscored_disposition_has_its_OWN_reason():
    """The S13 repair. A shared reason cannot carry three different remedies."""
    assert measurement_cut_reasons(
        True, False, False, "exhaustive", "contained", False, construction_failed=True
    ) == ("mutant_construction_failed",)
    assert measurement_cut_reasons(
        True, False, False, "exhaustive", "contained", False, not_installed=True
    ) == ("mutant_not_installed",)
    assert measurement_cut_reasons(
        True, False, False, "exhaustive", "contained", False, not_entered=True
    ) == ("mutant_not_entered",)


def test_a_clean_run_still_reports_nothing():
    """Unchanged from the original: the reasons fire on the fact, not on the code path."""
    assert measurement_cut_reasons(True, True, False, "exhaustive", "contained", False) == ()


def test_the_three_do_not_mask_one_another():
    """Plural on purpose. Fixing the construction failure must not reveal the other two as a
    surprise on the next run."""
    got = measurement_cut_reasons(
        True,
        False,
        False,
        "exhaustive",
        "contained",
        False,
        construction_failed=True,
        not_installed=True,
        not_entered=True,
    )
    assert got == ("mutant_construction_failed", "mutant_not_installed", "mutant_not_entered")


def test_only_construction_is_described_as_a_harness_failure():
    """THE defect, stated as a property of the prose. An un-installed mutant means the harness
    built it fine and the patch could not bind it; an un-entered one means both worked and no test
    called it. Telling either operator that "the harness failed" sends them to repair something
    that is not broken."""
    assert "engine" in cut_reason_sentence("mutant_construction_failed")
    for reason in ("mutant_not_installed", "mutant_not_entered"):
        assert "harness" not in cut_reason_sentence(reason), reason


def test_each_sentence_names_a_DIFFERENT_remedy():
    """Three reasons that resolved to the same instruction would be the collapse with extra steps."""
    sentences = {
        r: cut_reason_sentence(r)
        for r in ("mutant_construction_failed", "mutant_not_installed", "mutant_not_entered")
    }
    assert len(set(sentences.values())) == 3
    assert "report" in sentences["mutant_construction_failed"]
    assert "unwrap" in sentences["mutant_not_installed"]
    assert "route a test" in sentences["mutant_not_entered"]


def test_uninstalled_and_unentered_mutants_cannot_empty_the_certificate_universe():
    """The ORIGINAL intent of this file, preserved verbatim in substance: each unscored
    disposition refuses the certificate. Only the reason it carries has become specific."""
    expected = {
        "harness_error": "mutant_construction_failed",
        "not_installed": "mutant_not_installed",
        "not_entered": "mutant_not_entered",
    }
    for disposition, reason in expected.items():
        result = make_pr()
        category = CategoryResult(category=MutationCategory.VALUE)
        category.unscored_by[disposition] = 1
        result.per_category = [category]
        result.is_gateable = False
        result.coverage_depth = "exhaustive"
        validity = normalize_validity(result)
        assert not validity.admits_certificate, disposition
        assert validity.cut_reasons == (reason,), disposition
