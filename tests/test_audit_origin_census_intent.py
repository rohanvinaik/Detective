"""audit reports the ℋ ⊎ 𝒢 origin census — which half of the Sandwich the suite is (#E1 §2.3, D5).

ℋ hand-written tests are intent evidence; 𝒢 generated tests are characterization — they pin what the
code DOES, which may already be wrong. The split is read from each test file's Detective header (a
RECORDED authorship fact), never a path glob, and the three counts sum to test_count.
"""

from __future__ import annotations

import importlib

from Detective.audit import audit_suite

_cm = importlib.import_module("Detective.certify")


def _repo(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[tool.pytest.ini_options]\ntestpaths = ["tests"]\n')
    (tmp_path / "mod.py").write_text("def f(n):\n    return n + 1\n")
    tdir = tmp_path / "tests"
    tdir.mkdir()
    # ℋ — a human's test, no Detective header.
    (tdir / "test_hand.py").write_text("from mod import f\n\n\ndef test_h():\n    assert f(1) == 2\n")
    # 𝒢 — a Detective-generated file whose header claims this target.
    (tdir / "test_gen.py").write_text(
        f'"""{_cm._HEADER_PREFIX}mod.py::f.\n\ngenerated"""\n'
        "from mod import f\n\n\ndef test_g():\n    assert f(2) == 3\n"
    )


def test_audit_attributes_each_discharging_test_to_its_half(tmp_path):
    _repo(tmp_path)
    a = audit_suite("mod.py", "f", str(tmp_path))
    assert a.intent_tests == 1, "the header-less hand test is intent (ℋ)"
    assert a.characterized_tests == 1, "the Detective-headered test is characterization (𝒢)"
    assert a.unattributed_tests == 0
    # The census partitions the obligation-discharging suite exactly.
    assert a.intent_tests + a.characterized_tests + a.unattributed_tests == a.test_count
