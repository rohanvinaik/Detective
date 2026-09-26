"""The durable stores' READ side (EP-A2, EP-A3, EP-A3b — docs/ENGINEERING_PASS_2026-09-26.md).

#63 gave every durable JSON store one atomic writer, which protects the bytes DURING a write. It did
not protect them from the next READ: every loader answered "absent", "unreadable" and "corrupt" with
the same ``{}``, and every save then wrote that ``{}`` plus its one new entry. Pinned here from
intent, not from the implementation:

* EP-A2 — ``.detective/inputs.json`` (a person's supplied inputs, never purged) was also written
  truncate-then-fill, and on a parse failure ``remember`` wrote back ONLY the current function's entry:
  one interrupted write plus one later ``--input`` erased every other function's inputs.
* EP-A3 — a store that does not parse is SET ASIDE (every copy kept), never read as empty and then
  overwritten; a store the OS will not let us read is never replaced.
* EP-A3b — one entry this version cannot parse (malformed, or written by a newer schema) is carried
  through a save of the others; the loaders skip such an entry, and a save built from what they
  returned used to delete it.

The verdict cache keeps its own policy (one ``.corrupt`` copy — it can be rebuilt) and is not covered.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from Detective import atomic_store as st
from Detective import equivalents, judgments, line_flags, promotion_ledger, samples

# ── the two decisions ────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("exists", "read_ok", "parsed", "is_mapping", "expected"),
    [
        (False, False, False, False, "absent"),
        (True, False, False, False, "unreadable"),
        (True, True, False, False, "corrupt"),  # the bytes do not parse
        (True, True, True, False, "corrupt"),  # they parse, but a list or a string is not a store
        (True, True, True, True, "readable"),
    ],
)
def test_the_read_disposition_names_four_states(exists, read_ok, parsed, is_mapping, expected):
    assert st.store_read_disposition(exists, read_ok, parsed, is_mapping) == expected


@pytest.mark.parametrize(
    ("found", "set_aside", "expected"),
    [
        ("absent", False, "write"),
        ("readable", False, "write"),
        ("corrupt", True, "write"),  # its bytes are safe beside it
        ("corrupt", False, "refuse_unmoved"),  # replacing them now is the loss the move prevents
        ("unreadable", False, "refuse_unreadable"),  # never replace bytes nobody could read
        ("a-state-nobody-named", True, "refuse_unreadable"),  # unknown is not permission to write
    ],
)
def test_the_write_disposition_refuses_what_it_could_not_see(found, set_aside, expected):
    assert st.store_write_disposition(found, set_aside) == expected


# ── EP-A2: the supplied-inputs store ─────────────────────────────────────────────────────────────


def test_an_interrupted_inputs_write_leaves_the_prior_store_intact(tmp_path, monkeypatch):
    root = str(tmp_path)
    samples.remember(root, "a.py::f", [(1, 2)])
    path = Path(samples._path(root))
    before = path.read_bytes()

    def boom(_src, _dst):
        raise OSError("simulated crash mid-replace")

    monkeypatch.setattr(os, "replace", boom)
    samples.remember(root, "b.py::g", [("x",)])  # best-effort by contract: it must not raise
    assert path.read_bytes() == before


def test_a_half_written_inputs_store_is_set_aside_not_overwritten(tmp_path, capsys):
    """The EP-A2 repro. Before: the half document read as {} and the next ``--input`` wrote a store
    holding only ``b.py::g`` — ``a.py::f``'s inputs gone with no trace. After: the bytes are beside it."""
    root = str(tmp_path)
    samples.remember(root, "a.py::f", [(1, 2)])
    path = Path(samples._path(root))
    whole = path.read_bytes()
    path.write_bytes(whole[: len(whole) // 2])
    half = path.read_bytes()

    samples.remember(root, "b.py::g", [("x",)])

    kept = list(path.parent.glob("inputs.json.corrupt-*"))
    assert len(kept) == 1
    assert kept[0].read_bytes() == half
    assert json.loads(path.read_text(encoding="utf-8")) == {"b.py::g": ["('x',)"]}
    assert "moved aside" in capsys.readouterr().err


# ── EP-A3: file level ───────────────────────────────────────────────────────────────────────────


@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root reads through a 000 mode")
def test_an_unreadable_store_is_never_overwritten(tmp_path, capsys):
    """``os.replace`` needs only the DIRECTORY to be writable, so the old writer replaced a file it
    could not read — and a flag added while a permission was wrong erased every earlier flag."""
    root = str(tmp_path)
    equivalents.add_flag(root, "m.py::f", "diff one", note="first")
    path = Path(equivalents._store_path(root))
    before = path.read_bytes()
    path.chmod(0)
    try:
        equivalents.add_flag(root, "m.py::f", "diff two", note="second")
    finally:
        path.chmod(0o644)
    assert path.read_bytes() == before
    assert "NOT written (refuse_unreadable)" in capsys.readouterr().err


def test_valid_json_of_the_wrong_shape_is_corrupt_not_empty(tmp_path):
    root = str(tmp_path)
    path = Path(line_flags._store_path(root))
    path.parent.mkdir(parents=True)
    path.write_text("[1, 2, 3]", encoding="utf-8")
    assert line_flags.load_line_flags(root) == {}
    assert not path.exists()  # moved, so no later save can land on it
    assert [p.read_text(encoding="utf-8") for p in path.parent.glob("*.corrupt-*")] == ["[1, 2, 3]"]


def test_two_corruptions_in_the_same_second_keep_two_copies(tmp_path):
    """A human store's quarantine keeps every copy: two corruptions are two sets of judgments."""
    root = str(tmp_path)
    path = Path(judgments._path(root))
    path.parent.mkdir(parents=True)
    path.write_text("{ first corruption", encoding="utf-8")
    assert judgments.load_judgments(root) == {}
    path.write_text("{ second corruption", encoding="utf-8")
    assert judgments.load_judgments(root) == {}
    kept = sorted(p.read_text(encoding="utf-8") for p in path.parent.glob("*.corrupt-*"))
    assert kept == ["{ first corruption", "{ second corruption"]


def test_an_absent_store_is_empty_and_leaves_no_trace(tmp_path, capsys):
    data, found, set_aside = st.read_json_store(tmp_path / "nothing.json")
    assert (data, found, set_aside) == ({}, "absent", False)
    assert list(tmp_path.iterdir()) == []
    assert capsys.readouterr().err == ""


# ── EP-A3b: entry level ──────────────────────────────────────────────────────────────────────────

_FLAG = {"func_key": "m.py::f", "diff": "d", "verdict": "equivalent", "note": ""}
_LINE = {"func_key": "m.py::f", "stmt_hash": "h", "line": 3, "source": "x = 1", "note": ""}
_JUDGMENT = {
    "func_key": "m.py::f",
    "function_digest": "abc",
    "verdict": "AMBIGUOUS",
    "disposition": "leave",
    "note": "",
}
_CENSOR = {
    "func_key": "m.py::f",
    "kind": "input_absent",
    "subject": "0",
    "source": "call_site_absence",
    "note": "",
}
_LEDGER = {"censor": _CENSOR, "kappa": 2, "state": "proposed", "generation": 0}

_STORES = [
    (
        "equivalents",
        equivalents._store_path,
        equivalents.load_flags,
        equivalents.save_flags,
        _FLAG,
        {**_FLAG, "field_from_a_newer_release": True},
    ),
    (
        "line_flags",
        line_flags._store_path,
        line_flags.load_line_flags,
        line_flags.save_line_flags,
        _LINE,
        {**_LINE, "field_from_a_newer_release": True},
    ),
    (
        "judgments",
        judgments._path,
        judgments.load_judgments,
        judgments.save_judgments,
        _JUDGMENT,
        {**_JUDGMENT, "field_from_a_newer_release": True},
    ),
    (
        "promotion_ledger",
        promotion_ledger._store_path,
        promotion_ledger.load_ledger,
        promotion_ledger.save_ledger,
        _LEDGER,
        {**_LEDGER, "censor": {**_CENSOR, "field_from_a_newer_release": True}},
    ),
]


@pytest.mark.parametrize(
    ("name", "path_of", "load", "save", "valid", "unreadable_entry"), _STORES, ids=[s[0] for s in _STORES]
)
def test_an_entry_this_version_cannot_parse_survives_a_save_of_the_others(
    tmp_path, name, path_of, load, save, valid, unreadable_entry
):
    root = str(tmp_path)
    path = Path(path_of(root))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"valid-key": valid, "newer-key": unreadable_entry}), encoding="utf-8")

    loaded = load(root)
    assert set(loaded) == {"valid-key"}, f"{name}: the loader must skip what it cannot read"
    save(root, loaded)
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["newer-key"] == unreadable_entry, f"{name}: the save must carry it, not drop it"
    assert "valid-key" in on_disk
