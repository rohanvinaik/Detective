#!/usr/bin/env python3
"""Verify docs/theory/REFERENCE_MANIFEST.yaml against the files it claims.

    python docs/theory/check_reference_manifest.py [--json]

WHY this exists. The theory documents in this repo make claims that rest on
priors held in another repo. A prior changing under a claim that cites it must
FAIL LOUDLY, not silently invalidate the claim -- so every prior is recorded with
a sha256 and this script is the gate.

Exit codes:
    0  every prior resolved and hashed as recorded
    1  a DRIFT or MISSING prior -- a cited source is not what the claim was built on
    2  the manifest itself is unreadable/malformed

An UNRESOLVED external root is reported and exits 1, never 0: a check that could
not run is not a check that passed. (Same shape as the ARC_AGI_3 Law-3 discipline:
a vacuous pass is a failure.)

Load-bearing external citations with `verified: false` are reported as WARNINGS,
not failures -- they are memories, not sources, and the manifest says so on
purpose. They gate publication, not the build.

No third-party dependencies: the manifest subset used here is parsed directly so
this runs anywhere the repo does.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

MANIFEST = Path(__file__).resolve().parent / "REFERENCE_MANIFEST.yaml"
REPO_ROOT = Path(__file__).resolve().parents[2]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _parse(text: str) -> tuple[str, list[dict], list[dict]]:
    """Extract external_root, priors, and external_citations.

    A deliberately small reader over the exact shape this manifest uses -- keys we
    care about are flat scalars inside `- ` list items. Anything it cannot read it
    reports rather than guessing, so a manifest edit that outgrows it fails at (2)
    instead of silently checking nothing.
    """
    root_match = re.search(r"^external_root:\s*(\S+)", text, re.M)
    external_root = root_match.group(1) if root_match else ""

    def items(section: str, keys: tuple[str, ...]) -> list[dict]:
        start = re.search(rf"^{section}:\s*$", text, re.M)
        if not start:
            return []
        body = text[start.end() :]
        nxt = re.search(r"^[a-z_]+:\s*$", body, re.M)
        if nxt:
            body = body[: nxt.start()]
        out: list[dict] = []
        for block in re.split(r"^\s{2}-\s", body, flags=re.M)[1:]:
            rec: dict = {}
            for key in keys:
                m = re.search(rf"^\s*{key}:\s*(.+?)\s*$", block, re.M)
                if m:
                    val = m.group(1).strip().strip('"')
                    if val in ("true", "false"):
                        rec[key] = val == "true"
                    elif val not in (">", "|"):
                        rec[key] = val
            if rec:
                out.append(rec)
        return out

    priors = items("priors", ("id", "path", "root", "sha256"))
    citations = items("external_citations", ("key", "cite", "load_bearing", "verified"))
    return external_root, priors, citations


def main(argv: list[str]) -> int:
    as_json = "--json" in argv
    try:
        text = MANIFEST.read_text(encoding="utf-8")
        external_root, priors, citations = _parse(text)
    except OSError as exc:
        print(f"MANIFEST UNREADABLE: {exc}", file=sys.stderr)
        return 2
    if not priors:
        print("MANIFEST MALFORMED: no priors parsed", file=sys.stderr)
        return 2

    ext_root = Path(os.path.expanduser(external_root)) if external_root else None
    ext_ok = bool(ext_root and ext_root.is_dir())

    results: list[dict] = []
    for p in priors:
        pid, rel, which = p.get("id", "?"), p.get("path", ""), p.get("root", "local")
        recorded = p.get("sha256", "")
        base = REPO_ROOT if which == "local" else ext_root
        if base is None or (which == "external" and not ext_ok):
            results.append(
                {
                    "id": pid,
                    "status": "UNRESOLVED",
                    "detail": f"external_root {external_root!r} not a directory",
                }
            )
            continue
        target = base / rel
        if not target.is_file():
            results.append({"id": pid, "status": "MISSING", "detail": str(target)})
            continue
        actual = _sha256(target)
        if actual != recorded:
            results.append(
                {
                    "id": pid,
                    "status": "DRIFT",
                    "detail": str(target),
                    "recorded": recorded[:16],
                    "actual": actual[:16],
                }
            )
        else:
            results.append({"id": pid, "status": "OK", "detail": str(target)})

    unverified = [c for c in citations if c.get("load_bearing") and not c.get("verified")]
    bad = [r for r in results if r["status"] != "OK"]

    if as_json:
        print(
            json.dumps(
                {
                    "priors": results,
                    "load_bearing_unverified": [c.get("key") for c in unverified],
                    "ok": not bad,
                },
                indent=2,
            )
        )
        return 1 if bad else 0

    width = max(len(r["id"]) for r in results)
    for r in results:
        mark = {"OK": "  ok  ", "DRIFT": " DRIFT", "MISSING": " MISS ", "UNRESOLVED": " ???? "}[r["status"]]
        line = f"[{mark}] {r['id']:<{width}}  {r['detail']}"
        if r["status"] == "DRIFT":
            line += f"\n            recorded {r['recorded']}…  actual {r['actual']}…"
        print(line)

    print(f"\n{len(results) - len(bad)}/{len(results)} priors verified")

    if unverified:
        print(
            f"\nWARNING — {len(unverified)} LOAD-BEARING external citation(s) still "
            f"recalled-not-verified. Do not quote publicly until checked:"
        )
        for c in unverified:
            print(f"  · {c.get('key')}: {c.get('cite', '')}")
        print("  (These do not fail the check. They gate publication.)")

    if bad:
        print("\nFAIL — a cited prior is not what the claim was built on.")
        print("Either the prior moved/changed (re-read the claim, then re-hash), or")
        print("external_root is wrong for this machine. Do NOT re-hash to silence it")
        print("without re-reading what changed: the hash is the claim's footing.")
        return 1

    print("\nPASS — every cited prior is byte-identical to what the claims were built on.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
