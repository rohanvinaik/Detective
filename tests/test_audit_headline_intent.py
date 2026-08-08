"""Intent tests for the audit headline's residual accounting (Detective #36).

The defect, reproduced in ONE session with both surfaces side by side on the same target:

    converge: ✓ COMPLETE (operator universe · modulo 3 crash-only value gaps)
    audit:    complete, modulo 3 unproven-equivalent
              · crash-only-equiv   3 survivor(s) — detected by crash; no value pins them

Zero of them were unproven-equivalent. The audit headline contradicted the itemised body two
lines beneath it, and contradicted converge's banner on the identical measurement — because
converge's banner had been taught the distinction and audit's had not.

WHY THE DISTINCTION IS LOAD-BEARING, not vocabulary. "Unproven-equivalent" means NO input
distinguishes the mutant, so there is nothing to go find and `detective flag` is the right
next action. "Crash-only" means an input DOES distinguish it, by crash — it is a value-
specification gap with a concrete witness. Labelling the second as the first sends the reader
hunting for an input that already exists, and tells them to flag a mutant that is not equivalent.

THE ARITHMETIC IS THE TRAP. `crash_only_equivalent` is a SUB-COUNT of `candidate_equivalent`,
not a sibling population, so the truly-unproven residual is their DIFFERENCE. Every test below
that uses unequal counts exists because the bug is invisible whenever the two happen to be equal
— which is exactly the case the field report caught it on.
"""

from __future__ import annotations

from Detective.cli import audit_headline_verdict


def test_all_survivors_crash_only_is_never_called_unproven():
    """The exact field case: candidate_equivalent == crash_only_equivalent == 3."""
    assert audit_headline_verdict(False, True, 3, 3) == "complete_modulo_crash_only"


def test_all_survivors_unproven_keeps_the_original_wording():
    """The fix must not overcorrect: a genuinely unproven residual is still unproven."""
    assert audit_headline_verdict(False, True, 3, 0) == "complete_modulo_unproven"


def test_a_mixed_population_names_both():
    """The case that proves the counts are subtracted rather than compared.

    5 candidate-equivalent of which 2 are crash-only means 3 unproven AND 2 crash-only. Code
    that tested `crash_only == candidate_equivalent` would call this pure-unproven and lose the
    crash-only entirely.
    """
    assert audit_headline_verdict(False, True, 5, 2) == "complete_modulo_both"


def test_no_survivors_is_plainly_complete():
    assert audit_headline_verdict(True, False, 0, 0) == "complete"


def test_an_incomplete_suite_is_incomplete_whatever_the_residuals():
    """Residual accounting must not promote a suite with real gaps."""
    assert audit_headline_verdict(False, False, 0, 0) == "incomplete"
    assert audit_headline_verdict(False, False, 5, 2) == "incomplete"


def test_a_crash_only_count_exceeding_its_parent_is_named_not_rendered():
    """A sub-count larger than its parent breaks the invariant it belongs to.

    Unchecked, the subtraction yields a negative and the headline reads "modulo -2
    unproven-equivalent" — a number no reader can act on and no gate can interpret. Naming the
    state is what keeps a broken invariant from being rendered as a quantity.
    """
    assert audit_headline_verdict(False, True, 1, 3) == "inconsistent"


def test_each_shape_stays_distinguishable():
    """Six meanings, six codes. Collapsing any two puts the wrong next action in the report."""
    shapes = {
        audit_headline_verdict(False, False, 0, 0),
        audit_headline_verdict(True, False, 0, 0),
        audit_headline_verdict(False, True, 3, 0),
        audit_headline_verdict(False, True, 3, 3),
        audit_headline_verdict(False, True, 5, 2),
        audit_headline_verdict(False, True, 1, 3),
    }
    assert len(shapes) == 6
