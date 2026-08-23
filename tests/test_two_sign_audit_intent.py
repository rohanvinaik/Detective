"""§16 intent — `audit --two-sign`: the CI-gate view of the negative sign.

Symmetric with diagnose/converge/decompose: under ``two_sign`` the audit profiles under σ(P, μ ∪ μ⁻), so
the μ⁻ OUTPUT perturbations enter the mutant universe and a surviving negative DOF becomes a killable gap
that `audit --two-sign --check` fails on — extending Q8's authored `flag --fence` gate to the negative
degrees of freedom the ENGINE finds. These pin that two_sign widens the universe and that the CLI exposes
the flag off-by-default (a one-sign audit is byte-identical to before).
"""

from __future__ import annotations

from Detective.audit import audit_suite
from Detective.cli import _build_parser

_MOD = "def add(a, b):\n    return a + b\n"
_TEST = "from a2_mod import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"
_PYPROJECT = '[tool.pytest.ini_options]\ntestpaths = ["."]\nmarkers = ["detective: generated"]\n'


def _repo(tmp_path):
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT)
    (tmp_path / "a2_mod.py").write_text(_MOD)
    # Uniquely named so the nested (in-process) audit pytest cannot import-collide with the outer suite.
    (tmp_path / "test_a2_audit_repo.py").write_text(_TEST)
    return str(tmp_path)


def test_audit_two_sign_widens_the_universe_with_mu_minus(tmp_path):
    root = _repo(tmp_path)
    one = audit_suite("a2_mod.py", "add", root)
    two = audit_suite("a2_mod.py", "add", root, two_sign=True)
    # The two-sign audit profiles under σ(P, μ ∪ μ⁻): the μ⁻ OUTPUT perturbations (→None / →const /
    # →identity on the return) enter the universe, so the negative sign is now visible to the CI gate.
    assert two.total_mutants > one.total_mutants


def test_audit_cli_exposes_two_sign_off_by_default():
    assert _build_parser().parse_args(["audit", "a2_mod.py::add", "--two-sign"]).two_sign is True
    # off by default — a one-sign audit is byte-identical to before the flag existed
    assert _build_parser().parse_args(["audit", "a2_mod.py::add"]).two_sign is False
