"""An interrupted write must not destroy the cache, and a corrupt file must not be erased (#63).

Two defects that COMPOUND, which is why either alone looked survivable:

* `put` wrote with a plain `write_text` — truncate, then fill. A crash, a full disk or a killed
  process between those leaves a half-written file.
* `load` returned `{}` on ANY failure, including a parse error. So the half-written file read as
  empty, and the next `put` — a read-modify-write over the WHOLE map — wrote one entry over the
  remains.

The non-atomic write CREATES the corruption that the empty-fallback converts into total loss.
An interruption that touched one row destroyed every row, on the next ordinary run, silently.

Unreadable and unparseable are deliberately not the same. A file that cannot be read right now
may be perfectly good; renaming it would turn a transient condition into a permanent one.
"""

from __future__ import annotations

import contextlib
import json
import os

from Detective import verdict_cache as vc


def _cache_file(root):
    return vc._cache_path(str(root))


def test_a_corrupt_cache_is_quarantined_not_silently_emptied(tmp_path):
    """The defect. Reporting empty is what lets the next write destroy recoverable state — so
    the file is moved aside, which both frees the next write AND keeps the evidence."""
    path = _cache_file(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"a": {"trunc', encoding="utf-8")

    assert vc.load(str(tmp_path)) == {}
    assert path.with_name(path.name + ".corrupt").exists(), "the corrupt file was destroyed"


def test_an_unreadable_cache_is_not_quarantined(tmp_path, monkeypatch):
    """A permission blip, a lock, a transient mount — the contents may be fine. Renaming here
    would convert a temporary failure into a permanent one."""
    path = _cache_file(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"a": 1}', encoding="utf-8")

    def _boom(*_a, **_k):
        raise OSError("locked")

    monkeypatch.setattr(type(path), "read_text", _boom)
    assert vc.load(str(tmp_path)) == {}
    assert not path.with_name(path.name + ".corrupt").exists()


def test_a_write_leaves_no_partial_file_behind(tmp_path):
    """The staging file is same-directory (so `os.replace` is atomic) and must not survive."""
    path = _cache_file(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    vc._atomic_write(path, json.dumps({"k": 1}))

    assert json.loads(path.read_text()) == {"k": 1}
    leftovers = [p.name for p in path.parent.iterdir() if ".tmp-" in p.name]
    assert leftovers == [], f"staging files left behind: {leftovers}"


def test_a_failed_write_does_not_truncate_the_existing_file(tmp_path, monkeypatch):
    """THE guarantee. Truncate-then-fill loses the old contents the moment it begins; replace
    leaves them untouched until the new file is complete."""
    path = _cache_file(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"original": 1}), encoding="utf-8")

    def _boom(*_a, **_k):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", _boom)
    with contextlib.suppress(OSError):
        vc._atomic_write(path, json.dumps({"new": 2}))

    assert json.loads(path.read_text()) == {"original": 1}, "the prior cache was destroyed"


def test_a_quarantined_cache_lets_the_next_write_start_clean(tmp_path):
    """End to end: corruption must cost the cache, not the file — and the run after it must
    behave like a cold start rather than inheriting the damage."""
    path = _cache_file(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("}{ not json", encoding="utf-8")

    assert vc.load(str(tmp_path)) == {}
    vc._atomic_write(path, json.dumps({"fresh": 1}))
    assert vc.load(str(tmp_path)) == {"fresh": 1}
