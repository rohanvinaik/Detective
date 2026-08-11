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
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path


def atomic_write_text(path: str | os.PathLike[str], text: str) -> None:
    """Replace ``path``'s contents with ``text`` atomically, or not at all (#63).

    The caller is responsible for ensuring the parent directory exists (the same-directory temp
    file cannot be staged otherwise); every store already does its own ``os.makedirs`` first.
    """
    p = Path(path)
    tmp = p.with_name(f"{p.name}.tmp-{os.getpid()}")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, p)
    finally:
        with contextlib.suppress(OSError):
            tmp.unlink()
