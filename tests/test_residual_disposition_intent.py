"""residual_disposition types a surviving mutant into its ONE next action (F2).

TEST_BASIS §17 F2 / docs/F2_RESIDUAL_TYPING.md. `candidate_equivalent` conflated two residuals that
need opposite actions: a genuinely-equivalent survivor (flag-safe) and a killable-but-unsynthesized
one on a deep_structural target (a nested/cross-referential input the witness search does not reach —
flagging it equivalent is a FALSE specification claim). `residual_disposition` splits them on the #67
structural gate, and orders the checks so a killer outranks all and a crash-distinguished survivor is
value-unspecified, not "no input found".

Extended (§6, the expressibility boundary; Def. 1.4 RIP) with the two negative-entropy signals the
search already computes and used to discard: ``inputs_expressible`` (False ⇒ a domain-object function,
no ``--input`` differentiates → a ``fixture_residual``, never a flag — the serialize_rule case) and
``reached`` (False ⇒ the mutation never executed, a Reachability failure, so a reaching ``--input``
exists the search did not construct → ``structural_residual``). ``genuine_equivalent`` is now minted
only when the mutation was REACHED over EXPRESSIBLE inputs — the RIP condition a flag-safe equivalence
requires. Defaults are the flag-safe identity, so prior 3-arg callers keep their exact behaviour.
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


def test_inexpressible_inputs_are_a_fixture_residual_outranking_the_structural_gate():
    # §6 door 3 (serialize_rule): a domain-object function (inputs_expressible=False) has NO --input
    # that can differentiate a candidate-equivalent, so it is a `fixture_residual` — a hand-built
    # differential object, never a flag. And it OUTRANKS the deep_structural gate: a nested --input
    # cannot help when the value has no literal form at all.
    assert residual_disposition(False, False, "flat", inputs_expressible=False) == "fixture_residual"
    assert (
        residual_disposition(False, False, "deep_structural", inputs_expressible=False) == "fixture_residual"
    )


def test_unreached_expressible_survivor_is_structural_not_a_flag():
    # RIP-R: a flat, expressible-input survivor whose mutated line was NEVER executed by the tried pool
    # is killable with a reaching --input the search did not construct — `structural_residual`, never a
    # flag. (deep_structural already routes here; this catches the flat-but-unreached branch, e.g. a
    # body behind `if x == 42:` the grid never hit.)
    assert (
        residual_disposition(False, False, "flat", reached=False, inputs_expressible=True)
        == "structural_residual"
    )


def test_genuine_equivalent_requires_reached_and_expressible():
    # The flag-safe verdict is minted ONLY when the mutation was reached over expressible inputs and
    # still no input distinguished it — the RIP condition for a real equivalence. Drop either and it
    # is no longer flag-safe (fixture_residual / structural_residual above).
    assert (
        residual_disposition(False, False, "flat", reached=True, inputs_expressible=True)
        == "genuine_equivalent"
    )


def test_defaults_are_the_flag_safe_identity_preserving_prior_behaviour():
    # A 3-arg caller (deep_structure_caveat, the pre-existing golden) supplies neither new signal and
    # keeps the prior deep_structural/flat behaviour exactly — the change is additive.
    assert residual_disposition(False, False, "deep_structural") == "structural_residual"
    assert residual_disposition(False, False, "flat") == "genuine_equivalent"
    assert residual_disposition(False, False, "") == "genuine_equivalent"
