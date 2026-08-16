"""residual_disposition types a surviving mutant into its ONE next action (F2).

TEST_BASIS §17 F2 / docs/F2_RESIDUAL_TYPING.md. `candidate_equivalent` conflated two residuals that
need opposite actions: a genuinely-equivalent survivor (flag-safe) and a killable-but-unsynthesized
one on a deep_structural target (a nested/cross-referential input the witness search does not reach —
flagging it equivalent is a FALSE specification claim). `residual_disposition` splits them on the #67
structural gate, and orders the checks so a killer outranks all and a crash-distinguished survivor is
value-unspecified, not "no input found".
"""

from __future__ import annotations

from Detective.equivalence import residual_disposition, structural_residual_handback


def test_a_killer_outranks_everything():
    # A witness exists → it is not a residual at all, regardless of shape or crash flag.
    assert residual_disposition(True, False, "deep_structural") == "killer_ready"
    assert residual_disposition(True, True, "flat") == "killer_ready"


def test_crash_only_is_value_residual_before_the_structural_gate():
    # A crash input DOES distinguish it (value-unspecified, not "no input found"), so it never reads
    # as a structural residual even on a deep_structural target.
    assert residual_disposition(False, True, "deep_structural") == "value_residual"
    assert residual_disposition(False, True, "flat") == "value_residual"


def test_a_true_candidate_equivalent_splits_only_on_the_structural_gate():
    # No input found: deep_structural ⇒ likely killable (structural_residual, never flag); flat ⇒
    # flag-safe (genuine_equivalent). An unknown/absent shape is treated as flag-safe, not structural.
    assert residual_disposition(False, False, "deep_structural") == "structural_residual"
    assert residual_disposition(False, False, "flat") == "genuine_equivalent"
    assert residual_disposition(False, False, "") == "genuine_equivalent"


def test_structural_residual_handback_never_asks_for_an_inexpressible_input():
    # The escalation dispatch: an expressible structural input → `--input`/differential; a
    # non-expressible one → a fixture / real object, NEVER the broken `--input` ask.
    assert structural_residual_handback(True) == "structural_input"
    assert structural_residual_handback(False) == "structural_fixture"
