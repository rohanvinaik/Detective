"""#115 (reopened): `diagnose --two-sign` printed `detective converge 'm.py::scale'` — a command that, run as
printed, measures the one-sign universe. The same drop was in decompose's residual/blocked/ready/no-suite
endings, `audit --remove`'s re-measure line, `audit --plan`'s `then` line and `flag --line`'s Next line.

Rule under test: every printed command of a verb that measures a mutant universe carries the run's
universe (`UniverseOptions`), and FINAL names the policy under both policies."""

from types import SimpleNamespace

from Detective.cli import (
    UniverseOptions,
    _diagnose_action,
    _final_banner,
    _format_audit_plan,
    _removal_lines,
    _residual_action,
)

TWO = UniverseOptions(two_sign=True)
ONE = UniverseOptions()


def _spec(dof=3):
    return SimpleNamespace(unspecified_dof=dof)


def _scope():
    return SimpleNamespace(function="m.py::scale", load_failure="")


def _text(lines):
    return "\n".join(lines)


def test_diagnose_converge_carries_two_sign():
    page = _text(_diagnose_action(_scope(), _spec(3), False, 0, TWO))
    assert "detective converge 'm.py::scale' --two-sign" in page


def test_diagnose_decompose_first_carries_two_sign():
    page = _text(_diagnose_action(_scope(), _spec(3), True, 2, TWO))
    assert "detective decompose 'm.py::scale' --apply --two-sign" in page


def test_diagnose_done_audit_carries_two_sign():
    page = _text(_diagnose_action(_scope(), _spec(0), False, 0, TWO))
    assert "detective audit 'm.py::scale' --two-sign" in page


def test_diagnose_one_sign_unchanged():
    page = _text(_diagnose_action(_scope(), _spec(3), False, 0, ONE))
    assert "detective converge 'm.py::scale'\n" in page + "\n"
    assert "--two-sign" not in page


def test_diagnose_default_universe_is_one_sign():
    assert "--two-sign" not in _text(_diagnose_action(_scope(), _spec(3), False, 0))


def test_decompose_unclassified_residual_carries_two_sign():
    proof = SimpleNamespace(final_survivors=2)
    page = _text(_residual_action(None, proof, None, "m.py::scale", ".", TWO))
    assert "detective converge 'm.py::scale' --full --two-sign" in page


def test_removal_remeasure_carries_two_sign():
    record = {"outcomes": [], "removed": [], "target": "m.py::scale", "gate": "refused", "target_state": "x"}
    assert "detective audit 'm.py::scale' --two-sign" in _text(_removal_lines(record, TWO))
    assert "--two-sign" not in _text(_removal_lines(record))


def test_removal_confirm_lines_carry_two_sign():
    record = {
        "outcomes": [],
        "removed": ["t::a"],
        "target": "m.py::scale",
        "gate": "proceed",
        "after": {
            "reading": "gap_new",
            "newly_open": 1,
            "test_count": 1,
            "value_killed": 1,
            "total_mutants": 2,
        },
    }
    assert "detective audit 'm.py::scale' --two-sign" in _text(_removal_lines(record, TWO))


def test_audit_plan_then_carries_two_sign():
    tier1 = SimpleNamespace(
        tests_reaching=1, tests_total=1, covered_lines=1, executable_lines=1, mutant_count=3, two_sign=True
    )
    page = _format_audit_plan("m.py::scale", "", tier1, 1.0, TWO)
    assert "detective audit 'm.py::scale' --two-sign" in page


def test_final_names_policy_and_differs_per_policy():
    base = dict(
        function="m.py::scale", stale_target=True, budget_exhausted=False, written_path="", complete=False
    )
    one = _final_banner(SimpleNamespace(policy_id="P1", **base))
    two = _final_banner(SimpleNamespace(policy_id="P2+neg", **base))
    assert one.endswith("policy P1") and two.endswith("policy P2+neg")
    assert "policy" in _final_banner(SimpleNamespace(**base))
