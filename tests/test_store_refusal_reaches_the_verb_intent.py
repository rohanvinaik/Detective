"""A refused store write reaches the verb that asked for it (EP-A3c — docs/ENGINEERING_PASS_2026-09-26.md).

EP-A3 made every durable store refuse a write over bytes it could not read safely, and say so on
stderr. The savers then dropped the refusal, so the verbs whose whole product is that write carried
on: `flag-line` printed "✓ recorded … DONE" and exited 0, and so did `flag`, `flag --style` and
`censor --promote`, over a write that had just been refused. That is a sign for a state the tool had
measured as false, the failure COMMUNICATING_DETERMINISM §3 calls the worst one: the reader forms a
definite belief and acts on it.

Pinned here from intent, through the real CLI: over an unreadable store each of those verbs records
NOTHING, prints no RECORDED/DONE block, names the store, the refusal and its remedy, and exits 2 —
the world is wrong, fix the file (§4). The two refusal codes get two remedies. The store's bytes are
untouched. `--learn` keeps its verdict's exit code but must not announce learning that never happened.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from Detective import equivalents, judgments, line_flags, promotion_ledger
from Detective.atomic_store import StoreRefused
from Detective.cli import main

pytestmark = pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0, reason="root reads through a 000 mode"
)

_MODULE = "def f(x):\n    if x > 0:\n        return 1\n    return 0\n"


def _project(tmp_path: Path) -> str:
    (tmp_path / "m.py").write_text(_MODULE, encoding="utf-8")
    return str(tmp_path)


class _Unreadable:
    """A store file that exists and holds real entries, made unreadable for the duration."""

    def __init__(self, path: str, content: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(content, encoding="utf-8")
        self.before = self.path.read_bytes()

    def __enter__(self):
        self.path.chmod(0)
        return self

    def __exit__(self, *exc):
        self.path.chmod(0o644)
        assert self.path.read_bytes() == self.before, "a refused write must leave the store's bytes whole"


def _assert_refused(capsys, code: int, which: str = "refuse_unreadable") -> str:
    out, err = capsys.readouterr()
    assert code == 2
    assert "DONE" not in out and "recorded" not in out
    assert "nothing was recorded" in err and f"could not be used safely ({which})" in err
    return err


def test_flag_line_over_an_unreadable_store_records_nothing_and_says_so(tmp_path, capsys):
    root = _project(tmp_path)
    with _Unreadable(line_flags._store_path(root), '{"earlier": "judgment"}'):
        code = main(["flag-line", "m.py::f", "3", "--project-root", root])
    err = _assert_refused(capsys, code)
    assert "make the file readable" in err


def test_flag_line_remove_and_clean_over_an_unreadable_store_exit_2(tmp_path, capsys):
    root = _project(tmp_path)
    assert main(["flag-line", "m.py::f", "3", "--project-root", root]) == 0  # a real record to act on
    capsys.readouterr()
    store = line_flags._store_path(root)
    with _Unreadable(store, Path(store).read_text(encoding="utf-8")):
        code = main(["flag-line", "m.py::f", "3", "--remove", "--project-root", root])
    _assert_refused(capsys, code)


@pytest.mark.parametrize("verb", [["--list"], ["--clean"]])
def test_listing_or_cleaning_an_unreadable_store_is_a_refusal_not_an_empty_answer(tmp_path, capsys, verb):
    """The read half (EP-A3c): "(none)" or "0 orphaned records removed" would be a claim about bytes
    nobody read. Absence and emptiness never render identically (§9 invariant 5)."""
    root = _project(tmp_path)
    assert main(["flag-line", "m.py::f", "3", "--project-root", root]) == 0
    capsys.readouterr()
    store = line_flags._store_path(root)
    with _Unreadable(store, Path(store).read_text(encoding="utf-8")):
        code = main(["flag-line", "m.py::f", *verb, "--project-root", root])
    out, err = capsys.readouterr()
    assert code == 2
    assert "(none)" not in out and "removed" not in out
    assert "could not be used safely (refuse_unreadable)" in err


def test_a_verdict_consumer_is_told_when_it_proceeds_without_a_store(tmp_path, capsys):
    """The lenient read the verdict paths keep ("a missing oracle is no oracle") is announced, never
    silent (EP-A3d): a run measured without the human's flags must not read as one measured with them."""
    root = str(tmp_path)
    equivalents.add_flag(root, "m.py::f", "diff one")
    capsys.readouterr()
    store = equivalents._store_path(root)
    with _Unreadable(store, Path(store).read_text(encoding="utf-8")):
        assert equivalents.load_flags(root) == {}
    err = capsys.readouterr().err
    assert "exists but could not be read" in err and "proceeding WITHOUT it" in err


def test_flag_style_over_an_unreadable_ledger_refuses_in_json_too(tmp_path, capsys):
    root = _project(tmp_path)
    with _Unreadable(judgments._path(root), "{}"):
        code = main(["flag", "m.py::f", "--style", "--leave", "--json", "--project-root", root])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert code == 2
    assert payload["verdict"] == "REFUSED" and payload["reason"] == "refuse_unreadable"
    assert payload["store"] == judgments._path(root)


def test_flag_over_an_unreadable_store_exits_2(tmp_path, capsys, monkeypatch):
    """The mutant flag. The profile is stood in for: the refusal is about the store, not the run."""

    class _Profiled:
        function_key = "m.py::f"
        value_survivor_records = [{"mutant_id": "BOUNDARY_x", "diff_summary": "x > 0 -> x >= 0"}]

    monkeypatch.setattr("Detective.engine.profile", lambda *a, **k: _Profiled())
    root = _project(tmp_path)
    with _Unreadable(equivalents._store_path(root), "{}"):
        code = main(["flag", "m.py::f", "BOUNDARY_x", "--project-root", root])
    _assert_refused(capsys, code)


@pytest.mark.parametrize("verb", ["--promote", "--list"])
def test_censor_over_an_unreadable_ledger_exits_2(tmp_path, capsys, verb):
    root = _project(tmp_path)
    with _Unreadable(promotion_ledger._store_path(root), "{}"):
        code = main(["censor", str(tmp_path), verb, "--project-root", root])
    _assert_refused(capsys, code)


def test_a_corrupt_store_that_cannot_be_moved_aside_names_the_other_remedy(tmp_path, capsys):
    """`refuse_unmoved`: the bytes read, but they are not a JSON object, and the directory will not
    let them be set aside. A different state, so a different remedy — never one "could not save"."""
    root = _project(tmp_path)
    store = Path(line_flags._store_path(root))
    store.parent.mkdir(parents=True)
    store.write_text("{not json", encoding="utf-8")
    store.parent.chmod(0o555)
    try:
        code = main(["flag-line", "m.py::f", "3", "--project-root", root])
    finally:
        store.parent.chmod(0o755)
    err = _assert_refused(capsys, code, "refuse_unmoved")
    assert "move it aside by hand" in err
    assert store.read_text(encoding="utf-8") == "{not json"


def test_the_saver_raises_with_the_path_and_the_code(tmp_path):
    """The library half: the refusal leaves the saver as an exception carrying what the verb names."""
    root = str(tmp_path)
    equivalents.add_flag(root, "m.py::f", "diff one")
    with _Unreadable(equivalents._store_path(root), Path(equivalents._store_path(root)).read_text()):
        with pytest.raises(StoreRefused) as info:
            equivalents.add_flag(root, "m.py::f", "diff two")
    assert info.value.code == "refuse_unreadable"
    assert info.value.path == equivalents._store_path(root)
    assert isinstance(info.value, OSError), "a caller that treats I/O failure as 'not written' still does"


def test_a_readable_store_still_records(tmp_path, capsys):
    """The control: nothing about the ordinary path changed."""
    root = _project(tmp_path)
    assert main(["flag-line", "m.py::f", "3", "--project-root", root]) == 0
    assert "✓ recorded" in capsys.readouterr().out
