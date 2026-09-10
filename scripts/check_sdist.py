#!/usr/bin/env python3
"""Fail if a built sdist carries a file git does not track.

The sdist exclude list in ``pyproject.toml`` is a DENYLIST, and a denylist is a claim about
what you remembered to name. This checks that claim instead of trusting it.

1.0.0 was one command away from publishing a 38 MB sdist whose bulk was
``docs/theory/operator_completeness/proofs/.lake`` -- vendored Lean packages, untracked,
gitignored, and swept in anyway. The size was the symptom. The defect is that an sdist
containing untracked build output is a function of the BUILDER's working tree rather than of
the commit, so two people running ``uv build`` on the same sha ship different tarballs and
neither has any way to notice.

The rule enforced here: an sdist member is either tracked by git, or synthesised by the build
backend (``PKG-INFO``). There is no third category.

Usage::

    python3 scripts/check_sdist.py [dist/<name>-<version>.tar.gz]

Exit codes follow the CLI's vocabulary rather than pass/fail: ``0`` reproducible from the
commit, ``1`` a measured defect, ``2`` the question could not be asked (no sdist built, not a
git checkout) -- a refusal is not a pass.
"""

from __future__ import annotations

import subprocess
import sys
import tarfile
from pathlib import Path

# Members the build backend synthesises rather than copying out of the tree. Anything else in
# the sdist that git does not track came from the builder's working directory.
GENERATED = frozenset({"PKG-INFO"})


def _stem(name: str) -> str:
    """Strip the ``<name>-<version>/`` prefix every sdist member carries."""
    return name.split("/", 1)[1] if "/" in name else name


def sdist_verdict(members: list[str], tracked: list[str], generated: list[str]) -> str:
    """Classify an sdist against the repo's tracked set (pure -- pinned).

    Split out from the I/O so the judgement is expressible as ``--input``: opening the tar and
    shelling out to ``git ls-files`` are inexpressible, deciding the verdict is not. Returns a
    named code rather than a bool because "no members at all" and "members the commit does not
    contain" are different facts with different remedies, and a truthy check would collapse
    them into one -- an empty archive would have read as a clean bill of health.

    ``reproducible``      every member is tracked or build-generated
    ``carries_untracked`` at least one member came from the builder's working tree
    ``empty``             the archive listed no files to judge

    PIN RECEIPT. Converged in ISOLATION (a scratch copy outside the repo), because an in-repo
    target pays a whole-suite baseline trace here -- 27.2 s/mutant against 13 mutants, versus
    the same 13 in 0.0s once the covering set is empty. Generated suite: ✓ COMPLETE, 12/13
    killed, modulo 1 unproven-equivalent and 2 crash-only.

    The generated suite is NOT in the tree, and the reason is measured rather than assumed.
    Audited against ``tests/test_sdist_guard_intent.py`` alone, the hand-written suite scores
    11/13 value-pinned, 100% killed (value+crash), complete modulo only the 2 crash-only gaps
    -- strictly stronger than the characterization, which left an unproven-equivalent behind.
    So the intent tests are the pin; adding the generated file would add a weaker duplicate
    that has to be regenerated every time this function changes.

    ``audit`` calls 6 of those intent tests redundant -- they kill no mutant and cover no line
    another does not. That is a true measurement and the wrong action. They exist to state the
    tradeoffs (the check is one-directional; the generated allowlist is a parameter, not a
    hardcode; a malformed member fails toward the alarm) so a later simplification has to argue
    with a named intent rather than notice nothing. Kill count is not the only thing a test is
    for, which is the distinction this whole tool is built on.
    """
    if not members:
        return "empty"
    known = set(tracked) | set(generated)
    for name in members:
        if _stem(name) not in known:
            return "carries_untracked"
    return "reproducible"


def main(argv: list[str]) -> int:
    root = Path(__file__).resolve().parent.parent
    archives = [Path(argv[0])] if argv else sorted((root / "dist").glob("*.tar.gz"))
    if not archives:
        print("check_sdist: no sdist found -- build one first (`uv build`)", file=sys.stderr)
        return 2

    try:
        listed = subprocess.run(
            ["git", "ls-files"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"check_sdist: cannot read the tracked set: {exc}", file=sys.stderr)
        return 2
    tracked = sorted(set(listed.split("\n")) - {""})

    failed = False
    for archive in archives:
        with tarfile.open(archive) as tar:
            files = [m for m in tar.getmembers() if m.isfile()]
        members = [m.name for m in files]
        size = sum(m.size for m in files)
        verdict = sdist_verdict(members, tracked, sorted(GENERATED))
        if verdict == "reproducible":
            print(f"OK  {archive.name}: {len(members)} files, {size / 1e6:.2f} MB, all tracked")
            continue
        failed = True
        if verdict == "empty":
            print(f"FAIL {archive.name}: contains no files", file=sys.stderr)
            continue
        known = set(tracked) | GENERATED
        extra = sorted(n for n in members if _stem(n) not in known)
        print(
            f"FAIL {archive.name}: {len(extra)} of {len(members)} files are not tracked by git.\n"
            "  This sdist is a function of the builder's working tree, not of the commit.\n"
            "  Add the offending path to [tool.hatch.build.targets.sdist].exclude:",
            file=sys.stderr,
        )
        for name in extra[:20]:
            print(f"    {name}", file=sys.stderr)
        if len(extra) > 20:
            print(f"    ... and {len(extra) - 20} more", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
