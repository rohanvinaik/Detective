"""Durability tests for the invocation ledger's persistence shell (`docs/INVOCATION_LEDGER.md`).

Pure I/O, so hand-written tests only. Every one of them is about a hard requirement rather than a
happy path, because the shell's whole contract is what it does when things go wrong:

    §2.1  It must never fail a run. A correctness tool does not acquire a new failure source for an
          advisory artifact.
    §2.2  But the ABSENCE is disclosed where it matters. Swallowing at write time is right;
          swallowing at read time is the thing this project exists to prevent.
    §2.3  It records FACTS, never verdicts. Every interpretation is a separate pure decision over
          it, so the record stays reusable by a consumer that is not doctor.
    §2.4  It is not cache.
"""

from __future__ import annotations

import json
import os
import time

import pytest

from Detective.ledger import (
    LEDGER_CAP_BYTES,
    LEDGER_REL,
    append,
    file_digest,
    ledger_available,
    ledger_path,
    read_recent,
    state_basis,
    suite_digest,
)

# ---------------------------------------------------------------- §2.1 it never fails a run


def test_a_first_append_creates_the_directory_it_needs(tmp_path) -> None:
    assert append(str(tmp_path), {"v": 1, "verb": "converge"}) is True
    assert os.path.isfile(ledger_path(str(tmp_path)))


def test_an_unwritable_project_costs_the_record_and_not_the_run(tmp_path) -> None:
    """The load-bearing one. A read-only checkout, a container with no write mount, a
    permissions mistake — none of them may take down the converge that was actually asked for."""
    d = tmp_path / "ro"
    d.mkdir()
    d.chmod(0o500)
    try:
        assert append(str(d), {"v": 1, "verb": "converge"}) is False
    finally:
        d.chmod(0o700)


def test_an_unserialisable_record_is_refused_rather_than_raised(tmp_path) -> None:
    """A caller that hands the ledger something JSON cannot hold has a bug, and the ledger is not
    the place to discover it loudly — it is advisory."""
    assert append(str(tmp_path), {"v": 1, "bad": object()}) is False


def test_reading_a_project_that_has_none_is_not_an_error(tmp_path) -> None:
    assert read_recent(str(tmp_path)) == ()
    assert ledger_available(str(tmp_path)) is False


# ---------------------------------------------------------------- §2.2 absence is DISCLOSED


def test_no_ledger_and_an_empty_ledger_are_different_facts(tmp_path) -> None:
    """`read_recent` returns () for both, which is why `ledger_available` exists. "We have no
    history" and "you have run nothing" are different claims about the OPERATOR, and rendering the
    first as the second would let a missing ledger read as a clean process report — the single
    thing this surface must never do."""
    assert ledger_available(str(tmp_path)) is False
    open(ledger_path(str(tmp_path)) if os.path.isdir(tmp_path / ".detective") else os.devnull, "a").close()
    os.makedirs(os.path.dirname(ledger_path(str(tmp_path))), exist_ok=True)
    open(ledger_path(str(tmp_path)), "a").close()
    assert ledger_available(str(tmp_path)) is True
    assert read_recent(str(tmp_path)) == ()


# ---------------------------------------------------------------- JSONL's actual argument


def test_a_truncated_final_line_costs_ONE_record_not_the_file(tmp_path) -> None:
    """The whole reason for JSONL over a single document. An interrupted write — Ctrl-C, a killed
    container — must not lose the history that was already durable."""
    append(str(tmp_path), {"v": 1, "verb": "converge"})
    append(str(tmp_path), {"v": 1, "verb": "audit"})
    with open(ledger_path(str(tmp_path)), "a", encoding="utf-8") as fh:
        fh.write('{"v":1,"verb":"interrup')
    assert [r["verb"] for r in read_recent(str(tmp_path))] == ["converge", "audit"]


def test_concurrent_appends_do_not_lose_each_other(tmp_path) -> None:
    """One `open(..., "a")` plus one newline-terminated `write()` needs no read-modify-write, which
    is what makes this true. A read-modify-write over the whole map would lose entries here."""
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda i: append(str(tmp_path), {"v": 1, "verb": "converge", "n": i}), range(40)))
    assert len(read_recent(str(tmp_path), limit=100)) == 40


def test_records_come_back_oldest_first_and_limited(tmp_path) -> None:
    for i in range(10):
        append(str(tmp_path), {"v": 1, "n": i})
    rows = read_recent(str(tmp_path), limit=3)
    assert [r["n"] for r in rows] == [7, 8, 9], "the most recent, in the order they happened"


# ---------------------------------------------------------------- pruning is not purging


def test_eviction_is_recorded_in_band_so_a_pruned_head_is_not_mistaken_for_the_start(tmp_path) -> None:
    """Unbounded growth is real and pruning is not purging. A reader that cannot tell a pruned head
    from the beginning of history would conclude the operator had done nothing before the cap."""
    path = ledger_path(str(tmp_path))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(('{"v":1,"pad":"' + "x" * 900 + '"}\n') * 7000)
    assert os.path.getsize(path) > LEDGER_CAP_BYTES
    append(str(tmp_path), {"v": 1, "verb": "converge"})
    assert os.path.getsize(path) <= LEDGER_CAP_BYTES
    with open(path, encoding="utf-8") as fh:
        first = json.loads(fh.readline())
    assert "evicted" in first and first["evicted"] > 0


def test_the_eviction_marker_is_never_returned_as_an_invocation(tmp_path) -> None:
    """It is bookkeeping about the FILE, not a fact about the operator. A consumer counting repeats
    must not see it as one."""
    path = ledger_path(str(tmp_path))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write('{"v":1,"evicted":12}\n')
        fh.write('{"v":1,"verb":"converge"}\n')
    rows = read_recent(str(tmp_path))
    assert len(rows) == 1 and rows[0]["verb"] == "converge"


def test_purge_leaves_the_ledger_alone(tmp_path) -> None:
    """HISTORY IS NOT REGENERATABLE BY RE-RUNNING, which is purge's own stated criterion — a re-run
    produces a NEW entry and cannot reproduce the one that recorded what you did an hour ago.

    It needed no new rule: `verdict_cache.purge` works from an explicit ALLOWLIST (the cache file
    plus `.detective/reports/*`) rather than sweeping `.detective/`, so the ledger survives by
    construction. This pins that, because a future purge that switched to a sweep would silently
    destroy evidence while reporting a clean state.
    """
    from Detective import verdict_cache

    append(str(tmp_path), {"v": 1, "verb": "converge"})
    verdict_cache.purge(str(tmp_path))
    assert ledger_available(str(tmp_path)) is True
    assert len(read_recent(str(tmp_path))) == 1


def test_it_lives_where_the_design_says(tmp_path) -> None:
    """Per-project (founder ruling 2026-09-09: project scope, no machine-level index) and under
    `.detective/`, which is gitignored — correct, because this is YOUR invocation history rather
    than a fact about the project, and it must not travel with a clone."""
    assert LEDGER_REL == os.path.join(".detective", "ledger.jsonl")


# ---------------------------------------------------------------- the digests


def test_the_cheap_digest_moves_on_a_touch_and_the_exact_one_does_not(tmp_path) -> None:
    """The measured basis for `state_basis`. `touch`, a checkout, a copy and a stash round-trip all
    move mtime without moving a byte — which is the direction the cheap basis gets wrong, and the
    only direction it gets wrong."""
    d = tmp_path / "suite"
    d.mkdir()
    (d / "test_a_synth.py").write_text("x = 1\n")
    cheap_before, exact_before = suite_digest(str(d)), suite_digest(str(d), exact=True)
    time.sleep(0.01)
    os.utime(d / "test_a_synth.py", None)
    assert suite_digest(str(d)) != cheap_before, "mtime moved, so the stat-walk sees a change"
    assert suite_digest(str(d), exact=True) == exact_before, "…and no byte moved"


def test_both_bases_move_when_the_content_really_moves(tmp_path) -> None:
    """A digest that never changes is not a digest. The guard against writing a test that passes
    because both sides are constant."""
    d = tmp_path / "suite"
    d.mkdir()
    (d / "test_a_synth.py").write_text("x = 1\n")
    cheap_before, exact_before = suite_digest(str(d)), suite_digest(str(d), exact=True)
    (d / "test_a_synth.py").write_text("x = 2\n")
    assert suite_digest(str(d)) != cheap_before
    assert suite_digest(str(d), exact=True) != exact_before


def test_a_missing_suite_directory_digests_to_the_empty_string(tmp_path) -> None:
    assert suite_digest(str(tmp_path / "nope")) == ""
    assert file_digest(str(tmp_path / "nope.py")) == ""


def test_an_unreadable_file_is_unknown_rather_than_a_digest(tmp_path) -> None:
    """ "" is a REPORTED absence, not a value. Two runs that both failed to read the target must not
    compare EQUAL on it and conclude nothing changed — which is how a spiral gets manufactured out
    of a permissions problem."""
    assert file_digest(str(tmp_path)) == "", "a directory is not a readable file"


# ---------------------------------------------------------------- the escalation decision


@pytest.mark.parametrize(
    ("has_prior", "same_args", "cheap_changed", "expected"),
    [
        (False, True, True, "cheap"),
        (True, False, True, "cheap"),
        (True, True, False, "cheap"),
        (True, True, True, "escalate_exact"),
    ],
)
def test_only_a_same_args_repeat_that_LOOKS_changed_buys_the_full_read(
    has_prior, same_args, cheap_changed, expected
) -> None:
    """The healthy path never pays. A first run, a progressed run and an unchanged run all take the
    stat-walk; only the one case where the cheap basis can hide a spiral buys the read."""
    assert state_basis(has_prior, same_args, cheap_changed) == expected
