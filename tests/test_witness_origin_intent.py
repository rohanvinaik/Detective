"""Witness origin — which half of the Sandwich a test's evidence is, from a RECORDED fact (#D5 §2.3).

ℋ (hand-written) is INTENT evidence; 𝒢 (generated) is CHARACTERIZATION — it faithfully pins behaviour
that may already be wrong. The split is read from the file's Detective header (`generated_owner`),
NEVER a path glob: `tests/detective/` and `@pytest.mark.detective` are an authorship proxy that breaks
both ways (a hand-written test dropped in the dir, a generated golden a human edits). "We did not
measure this" (unattributed) must never render as either half.
"""

from __future__ import annotations

import importlib

from Detective.certify import witness_origin, witness_origin_of

_cm = importlib.import_module("Detective.certify")


def test_witness_origin_names_the_three_halves():
    assert witness_origin("generated", edited=False) == "characterization"
    assert witness_origin("generated", edited=True) == "intent"  # a human took it over → ℋ
    assert witness_origin("hand_written", edited=False) == "intent"
    assert witness_origin("hand_written", edited=True) == "intent"  # `edited` is moot when not ours
    assert witness_origin("unreadable", edited=False) == "unattributed"
    assert witness_origin("unreadable", edited=True) == "unattributed"


def test_a_generated_file_is_characterization(tmp_path):
    p = tmp_path / "gen.py"
    p.write_text(f'"""{_cm._HEADER_PREFIX}f.py::g.\n\nbody"""\nx = 1\n')
    assert witness_origin_of(str(p)) == "characterization"


def test_a_headerless_readable_file_is_intent(tmp_path):
    p = tmp_path / "hand.py"
    p.write_text('"""a human test."""\n\n\ndef test_x():\n    assert True\n')
    assert witness_origin_of(str(p)) == "intent"


def test_an_unreadable_or_missing_file_is_unattributed(tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text("def (( not python\n")
    assert witness_origin_of(str(bad)) == "unattributed"
    assert witness_origin_of(str(tmp_path / "nope.py")) == "unattributed"
