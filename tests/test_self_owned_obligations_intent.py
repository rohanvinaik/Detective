"""A self-contained receipt cannot rest SOLELY on a sibling target's generated test (issue #62, mechanism-2).

Mechanism-1 (`regressed_obligations` + the four projections) made the preservation guard compare
obligation SETS across kills / contracts / lines / arcs. But it built those sets from the RAW
profile: a foreign Detective-generated test — one owned by ANOTHER target's converge, discovered in
the same tree — could be the sole evidence discharging one of THIS target's obligations. That file is
rewritten wholesale on the sibling's next converge, so the certificate silently depended on a mutable
artifact this target does not own. Closed #7 stopped a foreign test from making an OWNED witness look
removable; this is the other half — a foreign test must not COUNT as owned evidence in the receipt.

The decided policy (2026-08-09) is **policy 1, self-contained receipts**: foreign generated evidence
MAY accelerate a run but may NEVER be the sole owner of an obligation; if it is the only thing pinning
one, the principled self-contained path re-derives it locally. `owned_obligation_disposition` is that
decision; `_self_owned_obligation_ids` applies it to every obligation class.

These are written from INTENT, not characterization: the generated `_synth` golden pins what the pure
decision DOES; this file states what mechanism-2 must GUARANTEE, and reproduces the gap it closes.
"""

from __future__ import annotations

from types import SimpleNamespace

from Detective.converge import (
    _contract_obligation_ids,
    _self_owned_obligation_ids,
    owned_obligation_disposition,
)

# A foreign generated test (owned by a sibling target) and an owned/user test, as the profile keys
# them: `legacy:<path>::<name>`. `foreign` holds the BARE names, the grammar foreign_generated_test_names
# returns and strip_foreign_evidence matches on.
FOREIGN_TID = "legacy:/proj/tests/detective/test_sibling_synth.py::test_sibling_value_0"
OWNED_TID = "legacy:/proj/tests/test_user.py::test_user_pins"
FOREIGN = {"test_sibling_value_0"}


def _te(test_id: str, arcs: list[tuple[int, int]]):
    """A stand-in TraceEvidence: the accessor reads .test_id, .admissible, .arcs (Wesker #17)."""
    return SimpleNamespace(test_id=test_id, admissible=True, arcs=arcs)


def _result():
    return SimpleNamespace(
        # M_foreign is killed ONLY by the sibling's test; M_owned only by the user's; M_mixed by both;
        # M_unattributed is killed but has no recorded killer.
        kill_matrix={
            "M_owned": [OWNED_TID],
            "M_foreign": [FOREIGN_TID],
            "M_mixed": [FOREIGN_TID, OWNED_TID],
        },
        killed_records=[
            {"mutant_id": "M_owned", "killed_by": "assertion"},
            {"mutant_id": "M_foreign", "killed_by": "assertion"},
            {"mutant_id": "M_mixed", "killed_by": "assertion"},
            {"mutant_id": "M_unattributed", "killed_by": "assertion"},
        ],
        # Admissible line coverage is keyed by test id; line 12 is covered ONLY by the foreign test.
        admissible_line_coverage={OWNED_TID: [10, 11], FOREIGN_TID: [12]},
        line_coverage={},
        trace_evidence=[_te(OWNED_TID, [(1, 2)]), _te(FOREIGN_TID, [(3, 4)])],
    )


# ── the pure decision (policy 1), from intent ──────────────────────────────────────────


def test_a_non_foreign_discharger_makes_the_obligation_self_owned():
    """The payoff. One owned test is enough — foreign evidence may ride along and accelerate."""
    assert owned_obligation_disposition([False]) == "owned"
    assert owned_obligation_disposition([True, False]) == "owned"


def test_an_all_foreign_obligation_is_refused_not_owned():
    """THE defect this closes: an obligation whose every discharger is a sibling's generated test."""
    assert owned_obligation_disposition([True]) == "foreign_only"
    assert owned_obligation_disposition([True, True]) == "foreign_only"


def test_foreign_only_and_unwitnessed_are_different_facts():
    """Load-bearing: a refused foreign dependency is not the same as no evidence at all. Collapsing
    them into one falsy check would either drop an owned kill or silently keep a foreign-owned one."""
    assert owned_obligation_disposition([]) == "unwitnessed"
    assert owned_obligation_disposition([True]) == "foreign_only"
    assert owned_obligation_disposition([]) != owned_obligation_disposition([True])


# ── the accessor: every obligation class, foreign-stripped ──────────────────────────────


def test_a_foreign_sole_kill_does_not_enter_the_receipt():
    """The gap, reproduced and closed. The RAW killed set (what mechanism-1 built) contains M_foreign;
    the self-owned set does not, while M_owned and M_mixed survive."""
    result = _result()
    raw_killed = [r["mutant_id"] for r in result.killed_records]
    assert "M_foreign" in raw_killed  # the defect: a foreign-sole kill was in the compared set

    killed_ids, _, _, _ = _self_owned_obligation_ids(result, FOREIGN)
    assert "M_foreign" not in killed_ids
    assert "M_owned" in killed_ids and "M_mixed" in killed_ids


def test_a_kill_with_no_recorded_killer_is_kept_not_mistaken_for_foreign():
    """`unwitnessed` (killed, unattributed) must be KEPT — it is this target's kill, not a foreign
    dependency. Dropping it for missing attribution would lose a real owned obligation."""
    killed_ids, _, _, _ = _self_owned_obligation_ids(_result(), FOREIGN)
    assert "M_unattributed" in killed_ids


def test_a_foreign_sole_line_and_arc_are_stripped():
    """Line 12 is covered only by the foreign test; arc (3,4) is executed only by it. Neither may be
    a proof obligation this certificate rests on; the owned line/arc survive."""
    _, line_ids, arc_ids, _ = _self_owned_obligation_ids(_result(), FOREIGN)
    assert any("test_user_pins" in x for x in line_ids)  # owned lines kept
    assert not any("test_sibling_value_0" in x for x in line_ids)  # foreign line stripped
    assert "arc:1-2" in arc_ids and "arc:3-4" not in arc_ids


def test_the_contract_set_drops_a_foreign_sole_mutant():
    """A value-pin (assertion kill) owned solely by the sibling's test leaves the declared-contract
    set too. (The narrow residue #62 names: a mutant ALSO owned-crash-killed keeps its contract id,
    because Wesker reports an aggregate `killed_by`, not a per-test kill reason.)"""
    _, _, _, contract_ids = _self_owned_obligation_ids(_result(), FOREIGN)
    assert "M_foreign" not in contract_ids
    assert "M_owned" in contract_ids and "M_mixed" in contract_ids
    # Control: without foreign-stripping, M_foreign's contract obligation was present.
    assert "M_foreign" in _contract_obligation_ids(_result().killed_records)


def test_no_foreign_names_is_a_no_op():
    """With nothing foreign, every obligation is owned — the guarantee never removes a real one."""
    killed_ids, line_ids, arc_ids, contract_ids = _self_owned_obligation_ids(_result(), set())
    assert {"M_owned", "M_foreign", "M_mixed", "M_unattributed"} <= set(killed_ids)
    assert "arc:3-4" in arc_ids and "arc:1-2" in arc_ids
