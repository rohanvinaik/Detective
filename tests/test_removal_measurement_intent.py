"""#112: refusal protects tests without claiming a kill or line that was never measured.

The impure boundary gets controlled profiles and observed reach; the pure decision is pinned
separately. All three consultation paths must consume the same evidence states.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from _support import make_pr

from Detective.audit import module_safe_removals, removal_measurement_state


def test_a_refusal_is_unverified_even_when_it_claims_needed_tests():
    assert removal_measurement_state(False, 1) == "unverified"


def test_admissible_empty_evidence_is_redundant():
    assert removal_measurement_state(True, 0) == "redundant"


def test_admissible_nonempty_evidence_is_needed():
    assert removal_measurement_state(True, 1) == "needed"


def _invalid():
    result = make_pr()
    result.is_gateable = False
    result.collection_errors = ("test_broken.py",)
    # A cut result must not publish even this apparent unique contribution as proof.
    result.kill_matrix = {"M": ["test_candidate"]}
    result.line_coverage = {"test_candidate": [2]}
    return result


@pytest.mark.parametrize("reaches_sibling", [False, True])
@pytest.mark.parametrize("two_sign", [False, True])
def test_an_invalid_sibling_is_named_only_for_tests_that_reach_it(tmp_path, reaches_sibling, two_sign):
    (tmp_path / "m.py").write_text("def f():\n    return 1\n\ndef broken():\n    return 2\n")
    reached = frozenset({("m.py", "broken")}) if reaches_sibling else frozenset()
    with (
        patch("Detective.audit.profile", return_value=_invalid()) as measured,
        patch("Detective.audit.candidate_reach", return_value=({"test_candidate": ("known", reached)}, {})),
    ):
        safe, retained, unverified = module_safe_removals(
            "m.py", "f", str(tmp_path), ["test_candidate"], two_sign=two_sign
        )
    assert measured.call_count
    assert all(call.kwargs["two_sign"] is two_sign for call in measured.call_args_list)
    assert not retained  # no measured evidence of unique need
    if reaches_sibling:
        assert not safe
        code, subject = unverified["test_candidate"]
        assert code == "reach_unmeasured"
        assert "m.py::broken" in subject
        assert "collection_incomplete" in subject
    else:
        assert safe == ("test_candidate",)
        assert not unverified


def test_an_invalid_sibling_never_turns_unknown_reach_into_permission_to_delete(tmp_path):
    (tmp_path / "m.py").write_text("def f():\n    return 1\n\ndef broken():\n    return 2\n")
    with (
        patch("Detective.audit.profile", return_value=_invalid()),
        patch(
            "Detective.audit.candidate_reach",
            return_value=({"test_candidate": ("not_collected", frozenset())}, {}),
        ),
    ):
        safe, retained, unverified = module_safe_removals("m.py", "f", str(tmp_path), ["test_candidate"])
    assert not safe
    assert not retained
    assert unverified["test_candidate"][0] != "retained_for"


@pytest.mark.parametrize("path", ["neighbor", "observed_reach"])
@pytest.mark.parametrize("two_sign", [False, True])
def test_a_refused_cross_file_measurement_stays_unverified_with_its_cause(tmp_path, path, two_sign):
    (tmp_path / "m.py").write_text("def f():\n    return 1\n")
    test_file = tmp_path / "test_m.py"
    test_file.write_text("def test_candidate():\n    pass\n")
    candidate = f"legacy:{test_file}::test_candidate"
    reached = frozenset({("other.py", "broken")})
    with (
        patch("Detective.audit.profile", return_value=_invalid()) as measured,
        patch("Detective.audit.candidate_reach", return_value=({candidate: ("known", reached)}, {})),
        patch("Wesker.ci.load_test_callables", return_value=[lambda: None]),
        patch("Wesker.ci.discover_test_callables", return_value=[]),
        patch("Detective.kappa.build_call_graph", return_value={}),
        patch("Detective.kappa.function_locations", return_value={"broken": [("other.py", "broken")]}),
        patch(
            "Detective.kappa.call_graph_neighbors", return_value={"broken"} if path == "neighbor" else set()
        ),
    ):
        safe, retained, unverified = module_safe_removals(
            "m.py", "f", str(tmp_path), [candidate], two_sign=two_sign
        )
    assert measured.call_count
    assert all(call.kwargs["two_sign"] is two_sign for call in measured.call_args_list)
    assert not safe
    assert not retained
    code, subject = unverified[candidate]
    assert code == "reach_unmeasured"
    assert "other.py::broken" in subject
    assert "collection_incomplete" in subject


def test_remove_handoff_forwards_the_two_sign_policy(tmp_path):
    from Detective.cli import _audit_remove

    report = SimpleNamespace(
        function="m.py::f",
        redundant_tests=("test_candidate",),
        function_basis=SimpleNamespace(action="complete"),
    )
    with (
        patch(
            "Detective.audit.module_safe_removals",
            return_value=((), {}, {"test_candidate": ("reach_not_reproduced", "unknown")}),
        ) as preflight,
        patch(
            "Detective.suite_edit.apply_removals",
            return_value=SimpleNamespace(removed=(), outcomes=(), files_changed=()),
        ),
    ):
        result = _audit_remove("m.py", "f", str(tmp_path), report, two_sign=True)
    assert preflight.call_args.kwargs["two_sign"] is True
    assert not result["removed"]
