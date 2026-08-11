"""The durable stores replace-or-preserve, never truncate-then-fill (#63, increment 1).

Every durable JSON store — the pin store, the line-flag and equivalent-mutant USER oracles, the
verdict cache — now writes through `atomic_store.atomic_write_text`. The property that matters is
NOT "the happy write works" (the old code did too); it is that an INTERRUPTED write leaves the
prior file intact. The old `open(path, "w")` truncated first, so a crash between truncation and
`json.dump` left an empty file the next load read as empty and the next save overwrote — silently
destroying a human's declared equivalence/line judgement. These are durability tests (pure I/O, no
mutation pin): a failed replace must leave the original byte-for-byte.
"""

from __future__ import annotations

import os

import pytest

from Detective.atomic_store import atomic_write_text


def _boom(_src, _dst):
    raise OSError("simulated crash mid-replace")


def test_writes_content_and_leaves_no_staging_file(tmp_path):
    """The happy path: the content lands and the same-directory temp file is gone."""
    p = tmp_path / "sub" / "store.json"
    p.parent.mkdir()
    atomic_write_text(p, '{"a": 1}')
    assert p.read_text(encoding="utf-8") == '{"a": 1}'
    assert list(p.parent.glob("*.tmp-*")) == []


def test_overwrites_an_existing_file_wholly(tmp_path):
    """A shorter new payload fully replaces a longer old one — no trailing stale bytes, which a
    seek-and-write (rather than replace) would leave."""
    p = tmp_path / "s.json"
    p.write_text("a much longer stale payload that must not bleed through", encoding="utf-8")
    atomic_write_text(p, "x")
    assert p.read_text(encoding="utf-8") == "x"


def test_a_failed_replace_leaves_the_original_intact(tmp_path, monkeypatch):
    """THE durability guarantee: if the replace step fails (full disk, killed process), the prior
    file is untouched and the staging temp is cleaned up — never a half-written or empty file."""
    p = tmp_path / "store.json"
    p.write_text('{"human": "declared truth"}', encoding="utf-8")
    monkeypatch.setattr(os, "replace", _boom)
    with pytest.raises(OSError):
        atomic_write_text(p, '{"new": "payload"}')
    assert p.read_text(encoding="utf-8") == '{"human": "declared truth"}'
    assert list(tmp_path.glob("*.tmp-*")) == []


def test_a_durable_oracle_survives_a_crashed_write(tmp_path, monkeypatch):
    """End-to-end through a real store: an equivalence oracle already on disk is NOT clobbered when
    a later `save_flags` is interrupted. The old truncate-then-fill path would have emptied it."""
    from Detective import equivalents
    from Detective.equivalents import _store_path

    root = str(tmp_path)
    path = _store_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write('{"m0::t": {"reason": "hand-declared equivalent"}}')

    monkeypatch.setattr(os, "replace", _boom)
    with pytest.raises(OSError):
        equivalents.save_flags(root, {})
    assert open(path, encoding="utf-8").read() == '{"m0::t": {"reason": "hand-declared equivalent"}}'
