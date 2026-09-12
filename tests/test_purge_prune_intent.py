"""Intent tests for `purge --prune` (`docs/INVOCATION_LEDGER.md` §4, §8.2).

The one destructive thing in the tool, and the only one that asks.

Everything ordinary `purge` removes is regeneratable by re-running — that is its stated criterion
and why it needs no confirmation. History fails that criterion: a re-run appends a NEW entry and
cannot reproduce the one that recorded what you did an hour ago. Founder ruling 2026-09-09: the
escape exists and it asks, because the history "should only be removed if there's no possible way
for a mistake in operation, which is obviously far away".
"""

from __future__ import annotations

import json

import pytest

from Detective.cli import main
from Detective.ledger import append, ledger_available, ledger_path, prune, read_recent


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "m.py").write_text("def add(a, b):\n    return a + b\n")
    for i in range(3):
        append(str(tmp_path), {"v": 1, "verb": "audit", "target": "m.py::add", "n": i})
    return tmp_path


# ---------------------------------------------------------------- the default is to SPARE it


def test_an_ordinary_purge_leaves_the_history_alone(repo, capsys) -> None:
    """The distinction the whole feature rests on. It needed no new rule to be true —
    `verdict_cache.purge` works from an allowlist — and this pins that `--prune`'s arrival did not
    quietly change the default."""
    main(["purge", "--project-root", str(repo)])
    capsys.readouterr()
    assert ledger_available(str(repo))
    assert len(read_recent(str(repo))) >= 3


# ---------------------------------------------------------------- it asks


def test_a_non_interactive_prune_answers_NO(repo, capsys, monkeypatch) -> None:
    """The SAFE direction. A pipe, a CI job or a closed stdin must not be read as consent to
    destroy the one artifact no re-run can reproduce."""
    monkeypatch.setattr("builtins.input", lambda *_: (_ for _ in ()).throw(EOFError()))
    main(["purge", "--prune", "--project-root", str(repo)])
    out = capsys.readouterr().out
    assert "left the invocation history alone" in out
    assert ledger_available(str(repo))


def test_anything_that_is_not_yes_is_no(repo, capsys, monkeypatch) -> None:
    for reply in ("", "n", "no", "maybe", "Y E S", "1"):
        monkeypatch.setattr("builtins.input", lambda *_, r=reply: r)
        main(["purge", "--prune", "--project-root", str(repo)])
        capsys.readouterr()
        assert ledger_available(str(repo)), f"{reply!r} was treated as consent"


@pytest.mark.parametrize("reply", ["y", "Y", "yes", "YES", " yes "])
def test_an_explicit_yes_deletes_it(repo, capsys, monkeypatch, reply) -> None:
    monkeypatch.setattr("builtins.input", lambda *_: reply)
    main(["purge", "--prune", "--project-root", str(repo)])
    capsys.readouterr()
    assert len(read_recent(str(repo))) == 1, "only this run's own record remains"


def test_yes_skips_the_prompt_for_scripts(repo, capsys, monkeypatch) -> None:
    """`--yes` exists so the scripted case that genuinely wants this can have it without the
    prompt — which is also why a closed stdin must NOT be read as yes."""
    monkeypatch.setattr("builtins.input", lambda *_: (_ for _ in ()).throw(AssertionError("prompted")))
    main(["purge", "--prune", "--yes", "--project-root", str(repo)])
    capsys.readouterr()
    assert len(read_recent(str(repo))) == 1


# ---------------------------------------------------------------- what it reports


def test_the_history_is_reported_APART_from_the_cache_count(repo, capsys) -> None:
    """History is not cache — which is exactly why it survives an ordinary purge — and folding it
    into that number would undo the distinction at the one surface where the user can see it."""
    main(["purge", "--prune", "--yes", "--project-root", str(repo)])
    out = capsys.readouterr().out
    assert "pruned the invocation history" in out
    assert "there is no undo" in out


def test_the_run_that_pruned_becomes_the_first_entry(repo, capsys) -> None:
    """Not a leak: the prune IS a process fact, and a history whose first entry says how it started
    is self-documenting — the same reasoning as the in-band eviction marker. The output says so
    rather than leaving the reader to discover a file they asked to be gone."""
    main(["purge", "--prune", "--yes", "--project-root", str(repo)])
    assert "this run is now its first entry" in capsys.readouterr().out
    rows = read_recent(str(repo))
    assert len(rows) == 1
    assert rows[0]["verb"] == "purge"


def test_the_json_channel_carries_it_as_its_own_field(repo, capsys) -> None:
    main(["purge", "--prune", "--yes", "--project-root", str(repo), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert "pruned_history" in payload
    assert payload["pruned_history"]["path"] == ledger_path(str(repo))


def test_pruning_nothing_says_so(tmp_path, capsys) -> None:
    main(["purge", "--prune", "--yes", "--project-root", str(tmp_path)])
    assert "no invocation history to prune" in capsys.readouterr().out


# ---------------------------------------------------------------- the library half


def test_prune_returns_what_it_removed_and_never_raises(tmp_path) -> None:
    """The caller owns the confirmation — a library function that prompts cannot be used by anything
    that is not a terminal."""
    assert prune(str(tmp_path)) == ("", 0), "nothing to remove is not an error"
    append(str(tmp_path), {"v": 1, "verb": "audit"})
    path, size = prune(str(tmp_path))
    assert path == ledger_path(str(tmp_path))
    assert size > 0
    assert prune(str(tmp_path)) == ("", 0), "and it is gone"
