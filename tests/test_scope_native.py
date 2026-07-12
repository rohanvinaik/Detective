"""Design-warranted tests for Detective.scope.scope_from_profiling.

These pin behavioral degrees of freedom the oracle-warranted conformance corpus
does not force. Each case's docstring states its warrant (the documented native
semantics) and the mutation survivor it kills, surfaced by profiling the port
with the Detective tool.
"""

from __future__ import annotations

from _support import make_pr

from Detective.scope import scope_from_profiling


def test_single_survivor_makes_category_surviving():
    """A category with *exactly one* surviving mutant IS a surviving category
    (``unspecified > 0``).

    Warrant: the boundary is strictly ``> 0``, not ``> 1`` — one unspecified DOF
    already makes a category under-specified. The oracle corpus has no
    unspecified==1 category, so it cannot distinguish ``> 0`` from an off-by-one.
    Kills VALUE_6 (replace the ``0`` constant with a boundary value).
    """
    pr = make_pr(
        categories=[{"category": "VALUE", "killed": 2, "survived": 1, "assertion": 2}],
        killed_records=[{"category": "VALUE", "killed_by": "assertion", "test": "t"} for _ in range(2)],
        survivor_records=[{"mutant": "VALUE_x: replace constant"}],
    )
    scope = scope_from_profiling(pr)
    assert scope.surviving_categories == ["VALUE"]
    assert scope.behavioral_dof[0].unspecified == 1


def test_only_string_test_names_enter_teaching_set():
    """Only string test names contribute to the σ-proxy teaching set; a killed
    record with a null test name is excluded.

    Warrant: the load-bearing test set is the distinct *named* tests that pin
    behavior — a record without a test name teaches nothing. The oracle corpus
    has no null-test record, so it cannot force the ``isinstance(t, str)`` filter.
    Kills TYPE_0 (replace isinstance with True), which would admit the null name.
    """
    pr = make_pr(
        categories=[{"category": "VALUE", "killed": 2, "survived": 0, "assertion": 1, "crash": 1}],
        killed_records=[
            {"category": "VALUE", "killed_by": "assertion", "test": "real_test"},
            {"category": "VALUE", "killed_by": "crash", "test": None},
        ],
    )
    scope = scope_from_profiling(pr)
    assert scope.load_bearing_tests == ["real_test"]
    assert scope.specification.sigma_proxy_teaching_set == 1
