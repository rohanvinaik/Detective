"""Tests for Detective.equivalence — killable vs equivalent-candidate by execution.

Pure functions (they only call the callables handed to them), mutation-driven to
value-assertion ceilings. Plain module-level helper callables, no fixtures.
"""

from __future__ import annotations

from Detective.equivalence import (
    MutantVerdict,
    SurvivorReport,
    Witness,
    _grid_for,
    _outcome,
    _search_witness,
    candidate_inputs,
    classify_survivor,
    find_witness,
    typed_inputs,
)


# ── _grid_for / typed_inputs ──────────────────────────────────────
def test_grid_for_known_types():
    assert _grid_for("str") == ["", "a", "abc"]
    assert _grid_for("bool") == [False, True]


def test_grid_for_unknown_or_none_falls_back_to_ints():
    assert _grid_for(None) == [-1, 0, 1, 2, 3]
    assert _grid_for("SomeClass") == [-1, 0, 1, 2, 3]


def test_typed_inputs_empty_is_single_empty_tuple():
    assert typed_inputs([]) == [()]


def test_typed_inputs_str_param_yields_strings():
    assert typed_inputs(["str"]) == [("",), ("a",), ("abc",)]


def test_typed_inputs_small_signature_is_full_product():
    assert typed_inputs(["bool", "bool"]) == [
        (False, False),
        (False, True),
        (True, False),
        (True, True),
    ]


def test_typed_inputs_large_signature_is_zipped_rows():
    # 5^3 = 125 > cap -> positionally-zipped diagonals (5 rows)
    assert typed_inputs(["int", "int", "int"]) == [
        (-1, -1, -1),
        (0, 0, 0),
        (1, 1, 1),
        (2, 2, 2),
        (3, 3, 3),
    ]


def _verdict(killable: bool) -> MutantVerdict:
    w = Witness((1,), "1", "2") if killable else None
    return MutantVerdict("M", "VALUE", "", killable, w, 3)


# ── SurvivorReport ────────────────────────────────────────────────
def test_survivor_report_splits_killable_from_equivalent():
    rep = SurvivorReport((_verdict(True), _verdict(False), _verdict(False)), (), None)
    assert len(rep.killable) == 1
    assert len(rep.equivalent) == 2


def test_survivor_report_carries_unclassified_and_note():
    rep = SurvivorReport((), ("- a\n+ b",), note="inputs don't exercise this function")
    assert rep.killable == () and rep.equivalent == ()
    assert rep.unclassified == ("- a\n+ b",)
    assert rep.note == "inputs don't exercise this function"


# ── candidate_inputs ──────────────────────────────────────────────
def test_candidate_inputs_arity_zero_is_single_empty_tuple():
    assert candidate_inputs(0) == [()]


def test_candidate_inputs_arity_one_is_the_base_grid():
    assert candidate_inputs(1) == [(-1,), (0,), (1,), (2,), (3,)]


def test_candidate_inputs_arity_two_is_full_product_including_boundaries():
    got = candidate_inputs(2)
    assert len(got) == 25
    assert (0, 0) in got and (-1, 2) in got


def test_candidate_inputs_wide_signature_stays_bounded():
    got = candidate_inputs(3)
    assert len(got) == 8  # 5 diagonals + 3 varied
    assert (1, 2, 3) in got and (3, 2, 1) in got


def test_candidate_inputs_arity_three_is_pinned_verbatim():
    # pin the exact grid so the range/modulo arithmetic in the varied tuples is
    # specified, not just counted
    assert candidate_inputs(3) == [
        (-1, -1, -1),
        (0, 0, 0),
        (1, 1, 1),
        (2, 2, 2),
        (3, 3, 3),
        (1, 2, 3),
        (3, 2, 1),
        (0, 1, 2),
    ]


def _double(x):
    return x * 2


def _plus_two(x):
    return x + 2


def _gt0(x):
    return x > 0


def _ge0(x):
    return x >= 0


def _boom():
    raise ValueError("nope")


# ── _outcome ──────────────────────────────────────────────────────
def test_outcome_reprs_the_value():
    assert _outcome(lambda: 42, ()) == "42"


def test_outcome_marks_a_raise_as_an_observable_outcome():
    assert _outcome(_boom, ()) == "<raised ValueError: nope>"


def test_outcome_carries_the_message_so_same_type_different_message_is_visible():
    # THE reason the marker is not type-only. Two mutants that keep the type and change the
    # message compared EQUAL to the original under a type-only marker, so `find_witness` skipped
    # them and they were filed candidate-equivalent — killable mutants, reported unkillable, and
    # no input could ever have fixed it because the distinction was never in the input.
    assert _outcome(_boom, ()) != _outcome(lambda: (_ for _ in ()).throw(ValueError("other")), ())


def test_outcome_keeps_the_type_when_the_message_is_empty():
    assert _outcome(lambda: (_ for _ in ()).throw(ValueError("")), ()) == "<raised ValueError>"


def test_outcome_drops_a_message_carrying_a_memory_address():
    # An address differs every run: pinning it writes a test that fails tomorrow, and comparing
    # two invents a difference. Coarse beats unstable — the type-level kill still stands.
    class Thing:
        pass

    def raises_with_an_address():
        raise ValueError(f"bad: {Thing()!r}")

    assert _outcome(raises_with_an_address, ()) == "<raised ValueError>"


def test_outcome_keeps_a_message_that_merely_contains_hex_like_text():
    # The guard must catch addresses, not any hex-ish word, or it silently coarsens real messages.
    assert _outcome(lambda: (_ for _ in ()).throw(ValueError("deadbeef")), ()) == (
        "<raised ValueError: deadbeef>"
    )


# ── find_witness ──────────────────────────────────────────────────
def test_find_witness_returns_first_distinguishing_input():
    w = find_witness(_double, _plus_two, [(3,)])
    assert w == Witness((3,), "6", "5")


def test_find_witness_none_when_indistinguishable():
    # x*1 vs x agree everywhere tried -> no witness (NOT a proof of equivalence)
    assert find_witness(lambda x: x * 1, lambda x: x, [(3,), (0,), (-4,)]) is None


def test_find_witness_needs_the_boundary_input():
    # differ only at x==0: without (0,) no witness; with it, the boundary is caught
    assert find_witness(_gt0, _ge0, [(1,), (5,)]) is None
    assert find_witness(_gt0, _ge0, [(1,), (0,)]) == Witness((0,), "False", "True")


def test_find_witness_empty_inputs_is_none():
    assert find_witness(_double, _plus_two, []) is None


# ── _search_witness (the crash-only fact `find_witness` drops) ─────
def _raises_on_anything(x):
    raise ValueError("boom")


def test_search_witness_reports_crash_only_when_only_the_mutant_raises():
    # Original returns, mutant raises: an input DOES distinguish them, but no value assertion
    # can pin a value the mutant never returns. `find_witness` skips it and returns None --
    # identical to "nothing distinguishes it". Reporting them the same is what let a renderer
    # say "no input distinguishes them" about a mutant an input plainly does.
    witness, crash_only = _search_witness(_double, _raises_on_anything, [(3,)])
    assert witness is None
    assert crash_only is True


def test_search_witness_not_crash_only_when_the_ORIGINAL_raises():
    # The mirror image: the original raises and the mutant returns. `pytest.raises` pins the
    # original's behaviour, so this IS a value-witness -- and must not be filed as crash-only.
    witness, crash_only = _search_witness(_raises_on_anything, _double, [(3,)])
    assert witness is not None
    assert crash_only is False


def test_search_witness_prefers_a_value_witness_over_an_earlier_crash_only_input():
    # (3,) is crash-only, (0,) is a real value difference. The value-witness must win: a mutant
    # that is genuinely killable must never be reported as merely crash-only.
    def mutant(x):
        if x == 3:
            raise ValueError("boom")
        return x + 1

    witness, crash_only = _search_witness(_double, mutant, [(3,), (0,)])
    assert witness == Witness((0,), "0", "1")
    assert crash_only is False


def test_search_witness_no_difference_at_all_is_neither_witness_nor_crash_only():
    witness, crash_only = _search_witness(_double, lambda x: x * 2, [(3,), (0,)])
    assert witness is None
    assert crash_only is False


def test_find_witness_still_hides_the_crash_only_input_from_its_callers():
    # The public API is unchanged: a crash-only difference is still not a witness.
    assert find_witness(_double, _raises_on_anything, [(3,)]) is None


# ── classify_survivor ─────────────────────────────────────────────
def test_classify_killable_carries_witness_and_label():
    v = classify_survivor("M0", "ARITHMETIC", "- a*2\n+ a+2", _double, _plus_two, [(3,)])
    assert v.killable is True
    assert v.witness == Witness((3,), "6", "5")
    assert v.label == "killable"
    assert v.searched == 1


def test_classify_equivalent_candidate_has_no_witness():
    v = classify_survivor("M1", "VALUE", "- x*1\n+ x", lambda x: x * 1, lambda x: x, [(3,), (0,)])
    assert v.killable is False
    assert v.witness is None
    assert v.label == "equivalent-candidate"
    assert v.searched == 2
    assert v.crash_only is False


def test_classify_carries_crash_only_through_to_the_verdict():
    # The verdict is what every renderer reads. If the fact stops at the search, each surface
    # re-derives it or (as they all did) states the false claim instead.
    v = classify_survivor("M2", "BOUNDARY", "- <=\n+ >=", _double, _raises_on_anything, [(3,)])
    assert v.killable is False
    assert v.witness is None
    assert v.crash_only is True


def test_crash_only_verdict_says_what_it_actually_is():
    v = classify_survivor("M3", "BOUNDARY", "- <=\n+ >=", _double, _raises_on_anything, [(3,)])
    # Not "equivalent-candidate": an input DOES distinguish it, by crash. The word has to carry
    # that, because the word is what a reader acts on.
    assert v.label == "value-equivalent (crash-only-distinguishable)"


def test_a_killable_mutant_is_never_labelled_crash_only():
    v = classify_survivor("M4", "ARITHMETIC", "- a*2\n+ a+2", _double, _plus_two, [(3,)])
    assert v.crash_only is False
    assert v.label == "killable"
