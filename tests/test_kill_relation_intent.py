"""The redundant set and the cover are functions of the FULL kill relation, never of execution order (#145).

THE DEFECT, measured 2026-10-26 on #104's fixture (`f` with `test_pos`, `test_nonpos`, `test_dup` and the two
rows of `test_more_pos`): `detective audit 'src/calc.py::f'` read a cover of 2 on a cold or a fully warm trace
cache and a cover of 3 (with `test_dup` no longer redundant) on a cache holding only `test_pos` and
`test_nonpos`. Wesker's default kill matrix credits each mutant to the FIRST test that kills it, the order of
the tests follows which were replayed from the trace cache, and the cover was read off that credit.

THE RULING: "which tests kill which mutants" is a relation over (test, mutant) (KNOWABILITY Def. 2.3 / Prop.
7.1 define killing per test). A cover and a redundant set are functions of that relation only. The relation is
measured by the engine in the profile the audit already runs (`profile(full_matrix=True)`, Wesker's
`kill_relation`), read by `audit.kill_relation_of` and judged by `minimize.cover_standing`. Where there is
none the state is named and NO redundant set or cover is claimed; it never falls back to the first-killer
credit. Of several equally good covers the one kept is the one whose test ids sort first.
"""

from __future__ import annotations

import importlib
import itertools
import random
from types import SimpleNamespace

import pytest
from _support import make_pr

from Detective import audit as audit_mod
from Detective.audit import audit_suite, cover_standing_sentence, kill_relation_of
from Detective.engine import function_basis
from Detective.minimize import (
    cover_standing,
    kill_relation_disagreement,
    minimal_cover_2axis,
    redundant_2axis,
)
from Detective.validity import normalize_validity

POS, NONPOS, DUP, ROW3, ROW4 = (
    f"t.py::{n}" for n in ("test_pos", "test_nonpos", "test_dup", "row[3]", "row[4]")
)

# The relation the issue's fixture has: test_pos and test_nonpos pin the boundaries; the three others
# kill what test_pos kills, except the mutant only the exact input 1 distinguishes.
FULL = {
    "m_hi": [DUP, POS, ROW3, ROW4],
    "m_eq": [DUP, POS, ROW3, ROW4],
    "m_one": [POS],
    "m_lo": [NONPOS],
    "m_lo2": [NONPOS, POS],
}
LINES = {POS: [2, 3], NONPOS: [2, 4], DUP: [2, 3], ROW3: [2, 3], ROW4: [2, 3]}

# What Wesker's first-killer credit read under the two cache states the issue measured.
CREDIT_COLD = {"m_hi": [POS], "m_eq": [POS], "m_one": [POS], "m_lo": [NONPOS], "m_lo2": [NONPOS]}
CREDIT_PARTIAL = {"m_hi": [DUP], "m_eq": [DUP], "m_one": [POS], "m_lo": [NONPOS], "m_lo2": [NONPOS]}


def test_the_first_killer_credit_does_move_the_cover_which_is_why_it_is_not_read():
    """The artifact itself, on pure inputs: the same suite read through two creditings gives two covers."""
    cold = minimal_cover_2axis(CREDIT_COLD, LINES)
    partial = minimal_cover_2axis(CREDIT_PARTIAL, LINES)
    assert len(cold) == 2 and len(partial) == 3
    assert redundant_2axis(CREDIT_COLD, LINES) != redundant_2axis(CREDIT_PARTIAL, LINES)


def test_the_full_relation_gives_one_cover_whatever_order_it_is_presented_in():
    expected_cover = minimal_cover_2axis(FULL, LINES)
    expected_redundant = redundant_2axis(FULL, LINES)
    assert expected_cover == {POS, NONPOS}
    assert expected_redundant == {DUP, ROW3, ROW4}
    rng = random.Random(145)
    for _ in range(50):
        mutants = list(FULL)
        rng.shuffle(mutants)
        matrix = {m: rng.sample(FULL[m], len(FULL[m])) for m in mutants}
        lines = {t: LINES[t] for t in rng.sample(list(LINES), len(LINES))}
        assert minimal_cover_2axis(matrix, lines) == expected_cover
        assert redundant_2axis(matrix, lines) == expected_redundant


def test_every_permutation_of_the_test_ids_in_the_matrix_reads_the_same_cover():
    for killers in itertools.permutations([DUP, POS, ROW3]):
        matrix = {"a": list(killers), "b": list(killers)}
        # ties go to the smallest id, never to whichever listing or run order came first
        assert minimal_cover_2axis(matrix, {}) == {min(DUP, POS, ROW3)}


def test_two_tests_with_identical_kill_sets_keep_the_one_whose_id_sorts_first():
    matrix = {"m1": ["t.py::b", "t.py::a"], "m2": ["t.py::a", "t.py::b"]}
    assert minimal_cover_2axis(matrix, {}) == {"t.py::a"}
    assert redundant_2axis(matrix, {}) == {"t.py::b"}
    # ... and the rule is the id, not the listing order
    assert minimal_cover_2axis({"m1": ["t.py::a", "t.py::b"], "m2": ["t.py::b", "t.py::a"]}, {}) == {
        "t.py::a"
    }


def test_a_suite_with_a_single_test_has_that_test_as_its_cover_and_nothing_redundant():
    assert minimal_cover_2axis({"m": [POS]}, {POS: [2]}) == {POS}
    assert redundant_2axis({"m": [POS]}, {POS: [2]}) == set()


def test_a_mutant_no_test_kills_asks_nothing_of_the_cover():
    matrix = {"killed": [POS], "survivor": []}
    assert minimal_cover_2axis(matrix, {}) == {POS}
    assert redundant_2axis(matrix, {}) == set()


def test_a_test_whose_removal_unkills_any_mutant_is_never_redundant():
    """Wesker#49's concern, exhaustively: over every relation of 3 tests x 3 mutants (and every line
    ownership of 2 lines), dropping the whole redundant set leaves every killed mutant killed and every
    covered line covered."""
    tests = ["t.py::a", "t.py::b", "t.py::c"]
    mutants = ["m0", "m1", "m2"]
    checked = 0
    for bits in range(2 ** (len(tests) * len(mutants))):
        matrix = {
            m: [t for ti, t in enumerate(tests) if bits >> (mi * len(tests) + ti) & 1]
            for mi, m in enumerate(mutants)
        }
        for owners in range(4 ** len(tests)):
            lines = {t: [ln for ln in (1, 2) if (owners >> (2 * ti)) & 3 & ln] for ti, t in enumerate(tests)}
            dropped = redundant_2axis(matrix, lines)
            for killers in matrix.values():
                if killers:
                    assert set(killers) - dropped, (matrix, lines, dropped)
            for line in {ln for lns in lines.values() for ln in lns}:
                assert {t for t, lns in lines.items() if line in lns} - dropped
            checked += 1
    assert checked == 512 * 64


def test_a_disagreement_is_a_mutant_killed_in_only_one_of_the_two_measurements():
    assert kill_relation_disagreement(["a", "b"], ["b", "a"]) == 0
    assert kill_relation_disagreement(["a", "b"], ["a"]) == 1
    assert kill_relation_disagreement(["a"], ["a", "c"]) == 1
    assert kill_relation_disagreement([], []) == 0


@pytest.mark.parametrize(
    ("args", "code"),
    [
        ((True, "complete", 0), "full_matrix"),
        ((False, "complete", 0), "main_unresolved"),  # a cut or an unscored mutant in the run
        ((False, "absent", 0), "main_unresolved"),  # the run's refusal outranks every other state
        ((False, "not_requested", 0), "main_unresolved"),
        ((True, "scan_incomplete", 0), "test_unmeasured"),  # a mutant's scan did not settle every test
        ((True, "run_cut", 0), "test_unmeasured"),
        ((True, "row_missing", 0), "test_unmeasured"),  # a killed mutant with no killer in its row
        ((True, "complete", 1), "relation_disagrees"),
        ((True, "scan_incomplete", 1), "test_unmeasured"),  # the engine's own refusal outranks the check
        ((True, "not_requested", 0), "not_requested"),
        ((True, "absent", 0), "engine_lacks_relation"),  # an older Wesker: its own named state
        ((True, "something_new", 0), "test_unmeasured"),  # an unknown engine state is never a claim
    ],
)
def test_the_standing_names_why_the_relation_is_or_is_not_available(args, code):
    assert cover_standing(*args) == code


def test_every_refusal_has_a_sentence_and_an_unknown_one_is_named_not_swallowed():
    codes = (
        "main_unresolved",
        "test_unmeasured",
        "relation_disagrees",
        "not_requested",
        "engine_lacks_relation",
    )
    sentences = {cover_standing_sentence(c) for c in codes}
    assert len(sentences) == len(codes) and all(sentences)
    assert "mystery" in cover_standing_sentence("mystery")


def test_a_result_the_run_cannot_stand_behind_gives_no_relation_and_the_credit_is_never_read():
    relation = kill_relation_of(_result(CREDIT_COLD, LINES, **_asked(FULL)), False)
    assert (relation.standing, relation.matrix) == ("main_unresolved", {})


def test_the_relation_is_the_one_the_engine_measured_in_whatever_order_the_cache_ran_the_tests():
    # the two credits are what the cold and the partial cache wrote into kill_matrix; the relation is not
    # read from them, so the standing and the matrix are the same
    a = kill_relation_of(_result(CREDIT_COLD, LINES, **_asked(FULL)), True)
    b = kill_relation_of(_result(CREDIT_PARTIAL, LINES, **_asked(dict(reversed(FULL.items())))), True)
    assert a.standing == b.standing == "full_matrix"
    assert a.matrix == b.matrix == {m: sorted(ts) for m, ts in sorted(FULL.items())}
    assert redundant_2axis(a.matrix, LINES) == redundant_2axis(b.matrix, LINES) == {DUP, ROW3, ROW4}


def test_a_relation_that_disagrees_with_the_run_about_what_was_killed_is_not_a_relation():
    result = _result({"m_hi": [POS], "m_other": [POS]}, LINES, **_asked({"m_hi": [POS]}))
    relation = kill_relation_of(result, True)
    assert relation.standing == "relation_disagrees" and relation.matrix == {}


@pytest.mark.parametrize("engine", ["run_cut", "scan_incomplete", "row_missing"])
def test_a_relation_the_engine_calls_partial_makes_the_cover_unavailable_not_smaller(engine):
    result = _result(
        {"m": [POS]}, LINES, kill_relation={"m": {POS: "assertion"}}, kill_relation_standing=engine
    )
    relation = kill_relation_of(result, True)
    assert relation.standing == "test_unmeasured" and relation.matrix == {}


def test_a_profile_not_asked_for_the_relation_has_none_even_though_it_has_a_credit():
    result = _result({"m": [POS]}, LINES, kill_relation={}, kill_relation_standing="not_requested")
    relation = kill_relation_of(result, True)
    assert relation.standing == "not_requested" and relation.matrix == {}


def test_an_engine_without_the_field_is_its_own_named_state_not_a_first_killer_fallback():
    result = _result({"m": [POS]}, LINES)  # no kill_relation, no kill_relation_standing
    relation = kill_relation_of(result, True)
    assert relation.standing == "engine_lacks_relation" and relation.matrix == {}


def test_a_single_test_suite_and_an_empty_relation_are_claims_only_when_the_engine_says_whole():
    one = kill_relation_of(_result({"m": [POS]}, {POS: [1]}, **_asked({"m": [POS]})), True)
    assert one.standing == "full_matrix" and one.matrix == {"m": [POS]}
    nothing_killed = kill_relation_of(_result({}, {POS: [1]}, **_asked({})), True)
    assert nothing_killed.standing == "full_matrix" and nothing_killed.matrix == {}


def test_two_tests_with_identical_kill_sets_both_appear_in_the_relation():
    rel = kill_relation_of(_result({"m": ["t.py::a"]}, {}, **_asked({"m": ["t.py::b", "t.py::a"]})), True)
    assert rel.matrix == {"m": ["t.py::a", "t.py::b"]}


# --- the audit, end to end over a stubbed profile --------------------------------------------------------


def _result(kill_matrix, line_coverage, **extra):
    base = {
        "function_key": "m.py::f",
        "kill_matrix": kill_matrix,
        "executable_lines": [1, 2],
        "line_coverage": line_coverage,
        "admissible_line_coverage": line_coverage,
        "total_mutants": len(kill_matrix),
        "total_killed": len(kill_matrix),
        "value_killed": len(kill_matrix),
        "value_survived": 0,
        "total_equivalent": 0,
        "value_survivor_records": [],
        "killed_records": [],
        "per_category": [],
        "universe_size": len(kill_matrix),
        "failing_tests": [],
        "trace_truncated": [],
        "served_from_cache": False,
    }
    base.update(extra)
    return SimpleNamespace(**base)


def _asked(relation):
    """The fields a profile asked for the relation carries when the engine measured it whole."""
    return {
        "kill_relation": {m: {t: "assertion" for t in ts} for m, ts in relation.items()},
        "kill_relation_standing": "complete",
    }


def _trivial_report():
    return SimpleNamespace(
        inputs_expressible=True,
        killable=(),
        manual_equivalent=(),
        authored_fence=(),
        equivalent=(),
        unclassified=(),
    )


def test_an_audit_whose_whole_run_cannot_stand_claims_no_redundant_set_and_runs_no_per_test_profile(
    monkeypatch, tmp_path
):
    calls = []
    asked = []

    def fake_profile(*a, **k):
        calls.append(k.get("tests"))
        asked.append(k.get("full_matrix"))
        # an unscored mutant (a harness error) is a cut reason: the run admits no certificate
        pr = make_pr(
            categories=[{"category": "VALUE", "killed": 1, "survived": 0, "assertion": 1}],
            killed_records=[{"category": "VALUE", "killed_by": "assertion", "test": POS, "mutant_id": "m"}],
        )
        pr.kill_matrix = {"m": [POS, DUP]}
        pr.line_coverage = {POS: [1], DUP: [1]}
        pr.executable_lines = [1]
        pr.per_category[0].unscored = 1
        pr.per_category[0].unscored_by = {"harness_error": 1}
        return pr

    monkeypatch.setattr(audit_mod, "profile", fake_profile)
    monkeypatch.setattr(audit_mod, "classify_survivors", lambda *a, **k: _trivial_report())
    a = audit_suite("m.py", "f", str(tmp_path))
    ran = list(calls)
    asked_in_audit = list(asked)
    assert not normalize_validity(fake_profile()).admits_certificate
    assert a.cover_standing == "main_unresolved"
    assert a.redundant_tests == () and a.minimal_test_count is None and a.bloat is None
    assert ran == [None]  # the one profile only: nothing is re-profiled per test
    assert asked_in_audit == [True]  # ... and that profile is the one asked for the relation
    assert a.function_basis.kill_attribution == "main_unresolved"
    assert all(w.discharged.mutation_dims == () for w in a.function_basis.admitted)


def test_an_audit_with_nothing_killed_has_an_empty_relation_and_a_cover(monkeypatch, tmp_path):
    monkeypatch.setattr(
        audit_mod,
        "profile",
        lambda *a, **k: _result({}, {"t_good": [1]}, executable_lines=[1], **_asked({})),
    )
    monkeypatch.setattr(audit_mod, "classify_survivors", lambda *a, **k: _trivial_report())
    a = audit_suite("m.py", "f", str(tmp_path))
    assert a.cover_standing == "full_matrix" and a.minimal_test_count == 1


def test_an_engine_scan_that_was_not_whole_leaves_the_cover_unestablished_not_first_killer(
    monkeypatch, tmp_path
):
    credit = {"m": [POS]}
    monkeypatch.setattr(
        audit_mod,
        "profile",
        lambda *a, **k: _result(
            credit,
            {POS: [1], DUP: [1]},
            executable_lines=[1],
            kill_relation={"m": {POS: "assertion"}},
            kill_relation_standing="scan_incomplete",
        ),
    )
    monkeypatch.setattr(audit_mod, "classify_survivors", lambda *a, **k: _trivial_report())
    a = audit_suite("m.py", "f", str(tmp_path))
    assert a.cover_standing == "test_unmeasured"
    assert a.redundant_tests == () and a.minimal_test_count is None


def test_the_basis_names_what_a_test_kills_only_from_the_full_relation():
    pr = _result({"mid1: d": [POS]}, {POS: [1], DUP: [1]}, executable_lines=[1])
    pr.killed_records = [{"mutant_id": "mid1"}]
    pr.survivor_records = []
    validity = normalize_validity(pr)
    unmeasured = function_basis(pr, validity, ".")
    assert unmeasured.kill_attribution == "not_measured"
    assert all(w.discharged.mutation_dims == () for w in unmeasured.admitted)  # the credit is not a fact
    measured = function_basis(
        pr, validity, ".", kill_matrix={"mid1: d": [DUP, POS]}, kill_attribution="full_matrix"
    )
    assert {w.test: w.discharged.mutation_dims for w in measured.admitted} == {POS: ("mid1",), DUP: ("mid1",)}
    refused = function_basis(
        pr, validity, ".", kill_matrix={"mid1: d": [DUP, POS]}, kill_attribution="test_unmeasured"
    )
    assert refused.kill_attribution == "test_unmeasured"
    assert all(w.discharged.mutation_dims == () for w in refused.admitted)


# --- converge reads the same relation, from the result it profiled -------------------------------------


def test_converge_asks_every_profile_that_feeds_a_cover_for_the_relation():
    """Every `final_result` converge can end on, and the isolated reproducibility profile that may replace
    it, is profiled with `full_matrix=True`: the cover and redundant set it reports read that result."""
    import inspect

    converge_mod = importlib.import_module("Detective.converge")
    source = inspect.getsource(converge_mod)
    feeding = source.count("final_result = profile(") + source.count("_verify_result = profile(")
    assert feeding == 5
    assert source.count("full_matrix=True") == feeding
    assert not hasattr(converge_mod, "kill_relation_for")  # one derivation: `audit.kill_relation_of`


# --- need, relative to the tests that stay -----------------------------------------------------------------


def test_a_candidate_the_staying_tests_replace_is_not_needed_whatever_its_id_sorts_like():
    from Detective.minimize import needed_candidates

    relation = {"m1": ["legacy:t.py::a", "t.py::b"], "m2": ["legacy:t.py::a", "t.py::b"]}
    lines = {"legacy:t.py::a": [1], "t.py::b": [1]}
    # the cover keeps `legacy:t.py::a` (it sorts first), but it is the candidate: the staying twin carries it
    assert minimal_cover_2axis(relation, lines) == {"legacy:t.py::a"}
    assert needed_candidates(relation, lines, {"legacy:t.py::a"}) == set()
    assert needed_candidates(relation, lines, {"t.py::b"}) == set()


def test_a_candidate_that_is_the_only_one_to_kill_or_cover_something_is_needed():
    from Detective.minimize import needed_candidates

    relation = {"m1": ["t.py::a", "t.py::c"], "m2": ["t.py::c"]}
    lines = {"t.py::a": [1], "t.py::c": [1], "t.py::z": [9]}
    assert needed_candidates(relation, lines, {"t.py::c"}) == {"t.py::c"}  # sole killer of m2
    assert needed_candidates(relation, lines, {"t.py::z"}) == {"t.py::z"}  # sole coverer of line 9
    assert needed_candidates(relation, lines, {"t.py::a"}) == set()


def test_two_candidates_that_replace_each_other_keep_exactly_the_one_whose_id_sorts_first():
    from Detective.minimize import needed_candidates

    relation = {"m": ["t.py::b", "t.py::a"]}
    both = {"t.py::a", "t.py::b"}
    for killers in (["t.py::a", "t.py::b"], ["t.py::b", "t.py::a"]):
        assert needed_candidates({"m": killers}, {}, both) == {"t.py::a"}
    assert needed_candidates(relation, {}, both) == {"t.py::a"}


def test_deleting_every_unneeded_candidate_together_unpins_nothing():
    """Exhaustive over 3 tests x 3 mutants x every candidate subset: what stays plus the needed candidates
    kills every killed mutant and covers every covered line."""
    from Detective.minimize import needed_candidates

    tests = ["t.py::a", "t.py::b", "t.py::c"]
    mutants = ["m0", "m1", "m2"]
    for bits in range(2 ** (len(tests) * len(mutants))):
        matrix = {
            m: [t for ti, t in enumerate(tests) if bits >> (mi * len(tests) + ti) & 1]
            for mi, m in enumerate(mutants)
        }
        lines = {"t.py::a": [1], "t.py::b": [1, 2], "t.py::c": [2]}
        for subset in range(8):
            cands = {t for ti, t in enumerate(tests) if subset >> ti & 1}
            kept = (set(tests) - cands) | needed_candidates(matrix, lines, cands)
            for killers in matrix.values():
                if killers:
                    assert set(killers) & kept, (matrix, cands)
            for line in (1, 2):
                assert {t for t, lns in lines.items() if line in lns} & kept, (matrix, cands, line)
