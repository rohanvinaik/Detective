"""Preservation is compared by obligation SET, not by count (issue #62).

The cold-start guard kept the suite already on disk when a run's kill TOTAL dropped. Equal
totals passed, and they should not:

    before: {mutant_A, mutant_B}   count = 2
    after:  {mutant_B, mutant_C}   count = 2

`mutant_A` regressed and the guard saw nothing, because a scalar cannot express WHICH
behaviours are pinned — only how many. Shipping that suite trades one obligation for another
and reports convergence.

The invariant is containment: for an unchanged target, policy, capability set and pytest
manifest, `old admissible obligations ⊆ new`. That is strictly stronger than the count rule and
subsumes it, since containment forbids a drop in size.

`mutant_id` is what makes the comparison meaningful across two profiles: `_content_mutant_id`
hashes the mutated AST dump, so it is invocation-stable and survives regeneration. An ordinal or
a rendered description would compare positions, not behaviours.
"""

from __future__ import annotations

from Detective.converge import regressed_obligations


def test_a_swap_at_equal_count_is_caught():
    """THE defect, in one line. This is precisely what the count comparison could not see."""
    assert regressed_obligations(["A", "B"], ["B", "C"]) == ["A"]


def test_a_strict_superset_is_not_a_regression():
    """Convergence ADDS obligations. A guard that fired here would refuse every successful run,
    which is worse than the bug it replaces."""
    assert regressed_obligations(["A", "B"], ["A", "B", "C"]) == []


def test_an_identical_set_is_not_a_regression():
    assert regressed_obligations(["A", "B"], ["B", "A"]) == []


def test_a_dropped_obligation_is_caught_even_when_the_count_grows():
    """The case that most embarrasses a count rule: the total went UP and evidence was still
    destroyed. No magnitude comparison in any direction detects this."""
    assert regressed_obligations(["A", "B"], ["B", "C", "D", "E"]) == ["A"]


def test_every_lost_obligation_is_named():
    """Returning a bool would send the reader to diff two suites by hand. Sorted, so two
    identical runs cannot report differently."""
    assert regressed_obligations(["z", "a", "m"], []) == ["a", "m", "z"]


def test_an_empty_baseline_cannot_regress():
    """A cold start with nothing pinned has nothing to lose — the guard must not block the
    first run that ever writes a suite."""
    assert regressed_obligations([], ["A", "B"]) == []


def test_duplicate_ids_do_not_manufacture_a_regression():
    """Records are per kill EVENT, so one obligation can appear more than once. Comparing
    multisets would report a phantom loss when a mutant was simply killed by fewer tests."""
    assert regressed_obligations(["A", "A", "B"], ["A", "B"]) == []


# ── #62: the OTHER obligation classes — contract, line, arc — compared apart ──────


def test_a_value_pin_downgraded_to_a_crash_kill_is_caught():
    """THE contract-class defect. A mutant still KILLED but now only by CRASH has lost its value pin;
    its id stays in the killed set both runs, so the kill comparison sees nothing — only comparing
    the declared-CONTRACT set (assertion/exception kills) apart catches the regression."""
    from Detective.converge import _contract_obligation_ids

    before = [
        {"mutant_id": "A", "killed_by": "assertion"},
        {"mutant_id": "B", "killed_by": "crash"},
    ]
    after = [
        {"mutant_id": "A", "killed_by": "crash"},  # A's value pin lost, but A is still killed
        {"mutant_id": "B", "killed_by": "crash"},
    ]
    # The killed SET is identical — {A, B} both runs — so the kill comparison is blind:
    assert regressed_obligations(["A", "B"], ["A", "B"]) == []
    # The contract set is not: A was contract-killed, now only crash-killed.
    assert _contract_obligation_ids(before) == ["A"]
    assert _contract_obligation_ids(after) == []
    assert regressed_obligations(_contract_obligation_ids(before), _contract_obligation_ids(after)) == ["A"]


def test_a_missing_killed_by_contributes_no_contract_obligation():
    """An engine (or record) that does not report `killed_by` has not said the kill was by contract,
    so it owns no contract obligation — never invented, never a phantom regression."""
    from Detective.converge import _contract_obligation_ids

    assert _contract_obligation_ids([{"mutant_id": "A"}, {"mutant_id": "B", "killed_by": None}]) == []
    assert _contract_obligation_ids(None) == []


def test_line_and_arc_obligation_ids_are_stable_and_named():
    """Line and arc losses are named by stable id (sorted), so a dropped proof line or branch edge is
    reported, not counted. Arcs absent (no capture) is a sound no-op, never a manufactured loss."""
    from Detective.converge import _arc_obligation_ids, _line_obligation_ids

    assert _line_obligation_ids({"m.py": [3, 1, 2]}) == [
        "line:m.py:1",
        "line:m.py:2",
        "line:m.py:3",
    ]
    assert _arc_obligation_ids({(2, 3), (1, 2)}) == ["arc:1-2", "arc:2-3"]
    assert _arc_obligation_ids(()) == [] and _arc_obligation_ids(None) == []
    # A dropped admissible line is caught; an added one is not a regression.
    assert regressed_obligations(
        _line_obligation_ids({"m.py": [1, 2]}), _line_obligation_ids({"m.py": [2]})
    ) == ["line:m.py:1"]


def test_line_obligation_is_keyed_by_target_line_not_the_owning_test():
    """A regenerated suite that covers the SAME target lines under DIFFERENT test names is NOT a
    regression — the obligation is the covered LINE, never its owner.

    The false-revert bug: `admissible_proof_coverage` keys by test nodeid, and feeding that into
    `_line_obligation_ids` made the id `line:{test}:{L}`. So the SECOND converge of an incomplete
    function (bare, then again after supplying `--input`) regenerated the suite with new test
    names, every prior `line:{old_test}:{L}` "vanished", the containment guard reported a mass
    regression, and it reverted a suite that had reached ✓ every-mutant-killed to the incomplete
    one it improved on. The obligation must be owner-independent.
    """
    from types import SimpleNamespace

    from Detective.converge import _self_owned_obligation_ids

    def _fake(function_key: str, coverage: dict[str, list[int]]) -> SimpleNamespace:
        # Only the attributes `_self_owned_obligation_ids` + `admissible_proof_coverage` read.
        return SimpleNamespace(
            function_key=function_key,
            admissible_line_coverage=coverage,  # {test_nodeid: [target_lines]}
            line_coverage=coverage,
            kill_matrix={},
            killed_records=[],
            trace_evidence=[],
        )

    # SAME target lines {10, 11}, covered under DIFFERENT owning tests across two runs.
    _, line_a, _, _ = _self_owned_obligation_ids(_fake("m.py::f", {"tests/t.py::test_a_0": [10, 11]}), set())
    _, line_b, _, _ = _self_owned_obligation_ids(_fake("m.py::f", {"tests/t.py::test_b_9": [10, 11]}), set())
    assert line_a == line_b == ["line:m.py:10", "line:m.py:11"]
    assert regressed_obligations(line_a, line_b) == []  # a rename is NOT a regression

    # A genuinely dropped line is STILL caught, whatever the owner.
    _, line_c, _, _ = _self_owned_obligation_ids(_fake("m.py::f", {"tests/t.py::test_c_0": [10]}), set())
    assert regressed_obligations(line_a, line_c) == ["line:m.py:11"]
