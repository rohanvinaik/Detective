"""C8 / §15 intent — decompose's preservation proof is over the TWO-SIGN σ-witness under --two-sign.

Thm 15.4 transported: a consolidation is safe iff it preserves σ(P, μ ∪ μ⁻) — the value pins AND the
negative fences. By Thm 5.2 two value-≡ implementations can differ in the negative channel, so a one-sign
preservation proof can certify a rewrite that crossed a μ⁻ fence. Under ``two_sign`` decompose's proof
converge runs under the two-sign policy, so a green before/after trial certifies both signs. These pin
that the proof policy IS the two-sign one (a distinct id) and that the CLI exposes the flag.
"""

from __future__ import annotations

from Detective.cli import _build_parser
from Detective.decompose_apply import apply_decomposition

_MOD = "def add(a, b):\n    return a + b\n"
_TEST = (
    "from c8_mod import add\n\n\n"
    "def test_add():\n    assert add(1, 2) == 3\n    assert add(0, 0) == 0\n    assert add(-1, 1) == 0\n"
)
_PYPROJECT = '[tool.pytest.ini_options]\ntestpaths = ["."]\nmarkers = ["detective: generated"]\n'


def _repo(tmp_path):
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT)
    (tmp_path / "c8_mod.py").write_text(_MOD)
    # Uniquely named so the nested (in-process) proof pytest cannot import-collide with the outer suite.
    (tmp_path / "test_c8_decompose_repo.py").write_text(_TEST)
    return str(tmp_path)


def test_decompose_proof_runs_under_the_two_sign_policy(tmp_path):
    root = _repo(tmp_path)
    one = apply_decomposition("c8_mod.py", "add", root, write=False, two_sign=False)
    two = apply_decomposition("c8_mod.py", "add", root, write=False, two_sign=True)
    # The proof converge ran under σ(P, μ ∪ μ⁻) → a DISTINCT policy id from the one-sign proof, so a green
    # before/after trial certifies preservation of the negative fences too, not the value pins alone.
    assert two.policy_id != one.policy_id
    assert "+neg." in two.policy_id  # Wesker's two-sign policy id is `<version>+neg.<digest>`
    assert "+neg." not in one.policy_id  # the one-sign proof is unchanged (byte-identical policy)


def test_decompose_cli_exposes_two_sign_off_by_default():
    assert _build_parser().parse_args(["decompose", "c8_mod.py::add", "--two-sign"]).two_sign is True
    # off by default — a one-sign decompose is byte-identical to before the flag existed
    assert _build_parser().parse_args(["decompose", "c8_mod.py::add"]).two_sign is False
