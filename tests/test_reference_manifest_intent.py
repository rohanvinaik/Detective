"""R7: unverified citations stay unverified, including with inline YAML comments.

The checker must reject missing/malformed Boolean evidence instead of treating
nonempty strings as verified. These tests do not update any recorded prior hash.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[1] / "docs/theory/check_reference_manifest.py"
_SPEC = importlib.util.spec_from_file_location("reference_manifest_under_test", _PATH)
assert _SPEC is not None and _SPEC.loader is not None
checker = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(checker)

_MANIFEST = """external_root: /unused
priors:
  - id: local
    path: prior.txt
    root: local
    sha256: unchanged
external_citations:
  - key: remembered
    cite: "An unverified source"
    load_bearing: true # carries a claim
    verified: {value}
"""


@pytest.mark.parametrize(
    ("value", "verified"),
    [("false", False), ("false # not read", False), ("true", True), ("true # source read", True)],
)
def test_verification_is_typed_and_controls_the_real_checker_warning(
    value, verified, tmp_path, monkeypatch, capsys
):
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(_MANIFEST.format(value=value))
    (tmp_path / "prior.txt").write_text("original")
    monkeypatch.setattr(checker, "MANIFEST", manifest)
    monkeypatch.setattr(checker, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(checker, "_sha256", lambda path: "unchanged")
    _, _, citations = checker._parse(manifest.read_text())
    assert citations[0]["verified"] is verified
    assert citations[0]["load_bearing"] is True
    assert checker.main([]) == 0  # publication warning is separate from prior integrity
    output = capsys.readouterr().out
    assert ("1 LOAD-BEARING" in output) is (not verified)
    assert ("remembered" in output) is (not verified)


@pytest.mark.parametrize("value", ['"false"', "maybe", "null", "1", ""])
def test_malformed_verification_is_a_named_manifest_refusal(value, tmp_path, monkeypatch, capsys):
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(_MANIFEST.format(value=value))
    monkeypatch.setattr(checker, "MANIFEST", manifest)
    assert checker.main([]) == 2
    assert "MANIFEST MALFORMED" in capsys.readouterr().err


def test_missing_verification_is_not_silently_assumed(tmp_path, monkeypatch, capsys):
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(_MANIFEST.format(value="false").replace("    verified: false\n", ""))
    monkeypatch.setattr(checker, "MANIFEST", manifest)
    assert checker.main([]) == 2
    assert "verified" in capsys.readouterr().err


def test_a_missing_citation_section_is_not_read_as_verified(tmp_path, monkeypatch, capsys):
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text("priors:\n  - id: local\n    path: prior.txt\n")
    monkeypatch.setattr(checker, "MANIFEST", manifest)
    assert checker.main([]) == 2
    assert "external_citations" in capsys.readouterr().err
