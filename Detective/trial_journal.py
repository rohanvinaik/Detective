"""A trial rewrite of a USER's source file, journaled so no interruption can leave it behind (EP-A1).

`decompose` proves an extraction by writing it into the user's own file, running the proof suite
against it, and reverting unless the extraction is kept. The revert used to be a plain statement
after the suite ran, with no ``try``/``finally`` — so an exception, a Ctrl-C during a suite that takes
minutes, or the hang watchdog's hard exit left the TRIAL in the user's source: possibly a rewrite the
suite had just REJECTED, in dry-run mode too, silently. Three layers, each closing what the one
before cannot reach:

1. :class:`SourceTrial` restores the original on every exit that runs Python — an exception, a
   ``KeyboardInterrupt`` — unless the trial was explicitly kept.
2. The trial and the restore are atomic writes (#63), so neither can leave half a file behind.
3. A write-ahead JOURNAL, written BEFORE the trial touches the source: the path, the original text,
   and both digests, in ``.detective/trials/<digest of the path>.json``. A hard kill skips every
   ``finally``; the next Detective command finds the journal (:func:`recover_interrupted_trials`, run
   before any command reads source) and restores — or, if the file has changed since, touches
   nothing and says where the original is (:func:`trial_recovery_disposition`).

One journal per file, and never two for the same file: a trial on a file whose earlier trial is
unresolved REFUSES (:class:`UnresolvedTrial`), because overwriting that journal would destroy the only
copy of the user's original.

References:
    #63     GitHub issue: atomic writes for every durable store
    EP-A1   docs/ENGINEERING_PASS_2026-09-26.md
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import sys
from types import TracebackType

from .atomic_store import atomic_write_text, read_json_store

TRIALS_REL = os.path.join(".detective", "trials")

TRIAL_RESTORE = "restore"
TRIAL_ALREADY_RESTORED = "already_restored"
TRIAL_DIVERGED = "diverged"


class UnresolvedTrial(RuntimeError):
    """A trial was requested on a file whose earlier interrupted trial is still unresolved."""


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _journal_path(project_root: str, source_path: str) -> str:
    """One journal per source file, named by the file's absolute path so two files never share one."""
    key = hashlib.sha256(os.path.abspath(source_path).encode("utf-8")).hexdigest()[:16]
    return os.path.join(os.path.abspath(project_root), TRIALS_REL, f"{key}.json")


def trial_recovery_disposition(current_digest: str, trial_digest: str, original_digest: str) -> str:
    """What to do with a journal an interrupted trial left behind (EP-A1, pure — pinned).

    already_restored -- the file holds the original: the restore ran and only the journal is left.
                        Checked FIRST, so a trial identical to its original never rewrites anything.
    restore          -- the file still holds the trial: put the original back.
    diverged         -- the file holds neither (someone edited it since, or it is gone, read as
                        ``""``). Touch nothing: the original stays in the journal and the person
                        decides. Restoring over their edit would be this module's own defect again.
    """
    if current_digest and current_digest == original_digest:
        return TRIAL_ALREADY_RESTORED
    if current_digest and current_digest == trial_digest:
        return TRIAL_RESTORE
    return TRIAL_DIVERGED


def _purge_bytecode(path: str) -> None:
    """Retire the restored file's cached bytecode (the engine owns the rule; imported lazily so the
    common path — no journal — never pays for the engine's import graph)."""
    from .engine import _purge_stale_bytecode

    _purge_stale_bytecode(path)


def _recover_one(journal_path: str) -> str:
    journal, _found, _set_aside = read_json_store(journal_path)
    path, original = journal.get("path"), journal.get("original")
    if not isinstance(path, str) or not isinstance(original, str):
        # An unreadable journal was set aside by the reader (or is not ours); nothing to restore from.
        return "unreadable_journal"
    try:
        with open(path, encoding="utf-8") as fh:
            current_digest = _digest(fh.read())
    except OSError:
        current_digest = ""
    code = trial_recovery_disposition(current_digest, str(journal.get("trial_sha256", "")), _digest(original))
    if code == TRIAL_RESTORE:
        atomic_write_text(path, original)
        _purge_bytecode(path)
        os.remove(journal_path)
        sys.stderr.write(f"⚠ restored {path}: an interrupted `decompose` trial had left its rewrite there.\n")
    elif code == TRIAL_ALREADY_RESTORED:
        os.remove(journal_path)
    else:
        sys.stderr.write(
            f"⚠ an interrupted `decompose` trial journal names {path}, which has changed since the trial; "
            f"nothing was restored. The original is in {journal_path}.\n"
        )
    return code


def recover_interrupted_trials(project_root: str) -> dict[str, str]:
    """Restore every user file an interrupted trial left rewritten; ``{journal: disposition}``.

    Run before any command reads source, because a `converge` or `plan` over a file still holding a
    trial measures code the user never wrote. Never raises: recovery must not be what breaks a
    command. The common case — no ``.detective/trials/`` directory — costs one ``stat``.
    """
    trials_dir = os.path.join(os.path.abspath(project_root), TRIALS_REL)
    if not os.path.isdir(trials_dir):
        return {}
    outcomes: dict[str, str] = {}
    for name in sorted(os.listdir(trials_dir)):
        if not name.endswith(".json"):
            continue
        journal_path = os.path.join(trials_dir, name)
        try:
            outcomes[journal_path] = _recover_one(journal_path)
        # BLE001: recovery is a guard on the way in; a failure to recover is reported, never fatal
        except Exception as exc:  # noqa: BLE001
            sys.stderr.write(f"⚠ could not recover the decompose trial journal {journal_path}: {exc}\n")
            outcomes[journal_path] = "error"
    return outcomes


class SourceTrial:
    """Hold ``trial`` in ``path`` for the duration of a ``with`` block, journaled first; restore
    ``original`` on every exit unless :meth:`keep` was called.

    The journal is written BEFORE the trial, so there is no instant at which the source holds the
    trial and no record says so. It is removed only after the restore (or the keep) is complete.
    """

    def __init__(self, project_root: str, path: str, original: str, trial: str) -> None:
        self.path = path
        self.original = original
        self.trial = trial
        self.journal = _journal_path(project_root, path)
        self.kept = False

    def keep(self) -> None:
        """Leave the trial in place on exit: it was proven and applied."""
        self.kept = True

    def __enter__(self) -> SourceTrial:
        if os.path.exists(self.journal):
            raise UnresolvedTrial(
                f"{self.path} has an unresolved earlier trial ({self.journal}); "
                "resolve it before trialling again"
            )
        os.makedirs(os.path.dirname(self.journal), exist_ok=True)
        atomic_write_text(
            self.journal,
            json.dumps(
                {
                    "path": self.path,
                    "original": self.original,
                    "original_sha256": _digest(self.original),
                    "trial_sha256": _digest(self.trial),
                },
                indent=2,
            ),
        )
        atomic_write_text(self.path, self.trial)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        # Returns nothing, so an exception raised inside the trial always propagates after the restore
        # (a context manager suppresses only when __exit__ returns a true value).
        if not self.kept:
            try:
                atomic_write_text(self.path, self.original)
            except OSError:
                # Leave the journal: the next command restores from it. Never mask the original error.
                sys.stderr.write(
                    f"⚠ could not restore {self.path} after a decompose trial; the original is in "
                    f"{self.journal} and the next detective command will restore it.\n"
                )
                return
            # The restore owns the cache retirement, on EVERY exit: the proof suite imported the trial,
            # and a restore in the same second at the same size passes CPython's .pyc check, so the next
            # import would run the trial over the original. The journal recovery retires it the same way.
            _purge_bytecode(self.path)
        with contextlib.suppress(OSError):
            os.remove(self.journal)
