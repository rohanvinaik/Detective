"""One atomic writer for every durable JSON store (#63).

Detective persists several kinds of durable state as JSON — the pin store, the line-flag and
equivalent-mutant USER oracles, the verdict cache. Each was written with a plain
``open(path, "w"); json.dump(...)``, which TRUNCATES the file and then fills it. A crash, a full
disk, or a killed process between those two steps leaves a HALF-WRITTEN file; a half-written JSON
file does not parse, so the next load treats it as empty and the next save writes one entry over
the remains. For a cache that is a lost optimization; for a human's equivalence/line judgements it
is irrecoverable declared truth, silently gone from an interruption that never meant to touch it.

This is the single writer #63 asks every store to share. It replaces the contents in ONE step
(``os.replace``) or leaves the original untouched:

* the temp file lives in the SAME directory on purpose — ``os.replace`` is atomic only within a
  filesystem, and the system temp dir is routinely a different one;
* the pid suffix keeps two concurrent processes from colliding on the same staging path.

It does NOT make the surrounding read-modify-write itself safe against concurrent writers — that
wants the advisory project lock #63 also asks for, a separate increment. What it closes is the
truncate/clobber-on-interruption hole, uniformly, for every durable store rather than the cache
alone.

THE READER (EP-A3). An atomic writer protects the bytes only until the next READ decides what they
mean. Every store's loader used to answer "absent", "unreadable" and "corrupt" with the same ``{}``,
and every writer then saved that ``{}`` plus its one new entry — so a hand edit with a stray comma, a
merge-conflict marker, or a permission blip ended as a store holding one entry, silently. The only
store that set a bad file aside was the verdict cache: the one store a re-run can rebuild.
:func:`read_json_store` and :func:`write_json_store` are the reader and the guarded writer every
store now shares, so the four states are named once and handled once:
:func:`store_read_disposition` and :func:`store_write_disposition` are the decisions, pinned.

References:
    #63            GitHub issue: one atomic writer for every durable store
    EP-A2, EP-A3   docs/ENGINEERING_PASS_2026-09-26.md
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

STORE_ABSENT = "absent"
STORE_READABLE = "readable"
STORE_CORRUPT = "corrupt"
STORE_UNREADABLE = "unreadable"


def atomic_write_text(path: str | os.PathLike[str], text: str) -> None:
    """Replace ``path``'s contents with ``text`` atomically, or not at all (#63).

    The caller is responsible for ensuring the parent directory exists (the same-directory temp
    file cannot be staged otherwise); every store already does its own ``os.makedirs`` first.
    """
    p = Path(path)
    tmp = p.with_name(f"{p.name}.tmp-{os.getpid()}")
    try:
        try:
            fh = open(tmp, "w", encoding="utf-8")  # noqa: SIM115 — closed by the `with fh:` below
        except OSError as exc:
            # The staging file is an implementation detail with this process's pid in its name. An
            # error about it must read as an error about the file the CALLER named: a message saying
            # `pyproject.toml.tmp-60747` differs per process, so no caller, test or golden could rely
            # on it — and it changed what the old truncate-then-fill write said (`pyproject.toml`).
            # Caught by a generated characterization of `regime.apply_migration` (EP-A4).
            raise type(exc)(exc.errno, exc.strerror, os.fspath(path)) from exc
        with fh:
            fh.write(text)
            fh.flush()
            # EP-A5: the bytes reach the device before the rename makes them the store — the
            # guarantee Wesker's trace-cache writer already gives, so the pair's two atomic writers
            # promise one thing rather than two.
            os.fsync(fh.fileno())
        os.replace(tmp, p)
    finally:
        with contextlib.suppress(OSError):
            tmp.unlink()


def store_read_disposition(exists: bool, read_ok: bool, parsed: bool, is_mapping: bool) -> str:
    """What a durable store's file IS, as one named code (EP-A3, pure — pinned).

    Four facts with four different remedies, which every loader used to collapse into ``{}``:

      absent     -- no file. An empty store; a write creates it.
      unreadable -- the OS refused the read (a permission, a lock, a cloud file not on disk). The
                    bytes may be perfectly good, so they are neither set aside nor overwritten: a
                    read sees an empty store and a write REFUSES rather than replace what it could
                    not see.
      corrupt    -- read, but not a JSON object (unparseable, or valid JSON of the wrong shape).
                    Set aside before anything is written, because the next write would replace it,
                    and for a human store those bytes are irreplaceable.
      readable   -- a JSON object: the store's contents.

    Split out of :func:`read_json_store` because a decision over a filesystem is not expressible as
    a literal and this one is: the shell gathers the four facts, this names what they add up to.
    """
    if not exists:
        return STORE_ABSENT
    if not read_ok:
        return STORE_UNREADABLE
    if not (parsed and is_mapping):
        return STORE_CORRUPT
    return STORE_READABLE


def store_write_disposition(found: str, set_aside: bool) -> str:
    """May a write replace a store whose file was ``found`` in that state (EP-A3, pure — pinned)?

    write             -- absent or readable, or corrupt and its bytes were set aside first.
    refuse_unmoved    -- corrupt, and the move aside FAILED: replacing it now is exactly the loss
                         the quarantine exists to prevent.
    refuse_unreadable -- the current bytes could not be read at all. Also the answer for any code
                         this function does not know: an unknown state is not permission to write.
    """
    if found in (STORE_ABSENT, STORE_READABLE):
        return "write"
    if found == STORE_CORRUPT:
        return "write" if set_aside else "refuse_unmoved"
    return "refuse_unreadable"


def _set_aside(path: Path) -> Path | None:
    """Move a corrupt store beside itself as ``<name>.corrupt-<utc>-<pid>``; None when the move failed.

    Every copy is kept. The verdict cache keeps ONE ``.corrupt`` and overwrites it on recurrence,
    which is right for bytes a re-run rebuilds and wrong for these: two separate corruptions of a
    human store are two sets of judgments, and the second must not erase the first.
    """
    stamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
    base = f"{path.name}.corrupt-{stamp}-{os.getpid()}"
    # `os.replace` overwrites without asking, so a second corruption in the same second would land on
    # the first quarantine and erase it: probe for a free name first. The pid already separates
    # processes; the counter separates repeats within one.
    target = path.with_name(base)
    n = 1
    while target.exists():
        target = path.with_name(f"{base}-{n}")
        n += 1
    try:
        os.replace(path, target)
    except OSError:
        return None
    return target


def read_json_store(path: str | os.PathLike[str]) -> tuple[dict[str, Any], str, bool]:
    """A durable store's top-level object, the state its file was found in, and whether a corrupt
    file was set aside. Never raises; the object is ``{}`` for every state but ``readable``.

    A corrupt file is moved aside (:func:`_set_aside`) and named on stderr, so the next write starts
    clean AND the bytes survive. Named rather than silent because this is the one moment the loss can
    still be undone by the person reading the line.
    """
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}, store_read_disposition(False, False, False, False), False
    except OSError as exc:
        # Announced, never silent (EP-A3d): every caller reads this as EMPTY, and a run that proceeds
        # without the store must say so, or a verdict measured without the human's judgments reads as
        # one measured with them.
        sys.stderr.write(
            f"⚠ {p} exists but could not be read ({exc.strerror}); proceeding WITHOUT it. "
            "It will not be overwritten.\n"
        )
        return {}, store_read_disposition(True, False, False, False), False
    try:
        raw = json.loads(text)
        parsed = True
    except ValueError:
        raw, parsed = None, False
    found = store_read_disposition(True, True, parsed, isinstance(raw, dict))
    # `readable` already implies a dict, but only through the decision above; stated here so the
    # narrowing is checked where the value is returned rather than reconstructed by a reader (ty).
    if found == STORE_READABLE and isinstance(raw, dict):
        return raw, found, False
    target = _set_aside(p)
    if target is None:
        sys.stderr.write(
            f"⚠ {p} is not a readable JSON object and could not be moved aside; it will not be overwritten.\n"
        )
        return {}, found, False
    sys.stderr.write(
        f"⚠ {p} is not a readable JSON object; moved aside to {target.name} so no write can destroy it.\n"
    )
    return {}, found, True


def write_json_store(
    path: str | os.PathLike[str],
    payload: dict[str, Any],
    *,
    dumps: Callable[[dict[str, Any]], str],
    parses: Callable[[Any], bool] | None = None,
) -> str:
    """Replace a durable store with ``dumps(payload)`` atomically, unless its CURRENT bytes could not
    be read (or were corrupt and could not be set aside): then refuse, say so on stderr, and return
    :func:`store_write_disposition`'s code. ``write`` means the bytes were replaced.

    It probes the file as it is NOW rather than trusting the caller's earlier load, so a store that
    became unreadable, or was hand-edited into a syntax error, between load and save is protected too.

    ``parses`` (EP-A3b) is the store's own entry schema. When given, every on-disk entry it rejects
    — a malformed entry, or one written by a newer Detective with a field this one does not know —
    is carried through untouched unless ``payload`` now holds that key. The loaders skip such an entry
    ("never fatal"), and a save built from what they returned used to delete it: the entry-level
    copy of the file-level loss above.
    """
    p = Path(path)
    on_disk, found, set_aside = read_json_store(p)
    code = store_write_disposition(found, set_aside)
    if code != "write":
        sys.stderr.write(f"⚠ {p} was NOT written ({code}): its current bytes could not be read safely.\n")
        return code
    if parses is not None:
        carried = {key: value for key, value in on_disk.items() if key not in payload and not parses(value)}
        payload = {**carried, **payload}
    p.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(p, dumps(payload))
    return code


def parsed_entry[T](value: object, build: Callable[[dict[str, Any]], T]) -> T | None:
    """One stored entry through the store's own ``build``, or None when this version cannot read it
    (EP-A3b) — the ONE per-entry contract every durable store shares, as :func:`read_json_store` is the
    one file-level one. Four stores each kept a copy and they had already begun to differ.

    Not a JSON object, or rejected by ``build`` — an unknown or missing field (``TypeError``), a value
    the type refuses (``ValueError``), a required nested key absent (``KeyError``, the ledger's
    ``censor``) — all mean the same thing: this version cannot read the entry. Its loader skips it, and
    :func:`write_json_store` (``parses=``) carries it through the next write untouched rather than
    deleting it.
    """
    if not isinstance(value, dict):
        return None
    try:
        return build(value)
    except (TypeError, ValueError, KeyError):
        return None


class StoreRefused(OSError):
    """A durable store could not be used safely, so it was left exactly as it is (EP-A3c).

    `write_json_store` refuses to write over a store whose current bytes could not be read safely,
    and returns :func:`store_write_disposition`'s code. The savers used to drop that code, so `flag`,
    `flag-line` and `flag --style` printed "RECORDED" and exited 0 over a write that never happened:
    a sign for a state the tool had just measured as false. The read side had the same shape: a verb
    that reports ON a store (`flag-line --list`, `--remove`, `--clean`, `censor --list`) read an
    unreadable one as empty, and answered "(none)" or "no flag recorded at line N".

    Raised by :func:`require_usable` wherever the store IS the product, it carries the path and the
    code up to the verb, which names the refusal and its remedy and exits on it. An `OSError`, so a
    caller that already treats an I/O failure as "nothing done" keeps doing so."""

    def __init__(self, path: str | os.PathLike[str], code: str):
        super().__init__(f"{path} could not be used safely ({code})")
        self.path = os.fspath(path)
        self.code = code


def require_usable(path: str | os.PathLike[str], code: str) -> None:
    """Raise :class:`StoreRefused` unless ``code`` is :func:`store_write_disposition`'s ``write`` (EP-A3c).

    The same decision serves both directions, because "may this store be written over" and "may its
    content be reported as the whole truth" fail in exactly the same states: unreadable bytes, and
    corrupt bytes that could not be set aside."""
    if code != "write":
        raise StoreRefused(path, code)
