#!/usr/bin/env python3
"""Sync ``docs/REPAIR_QUEUE_2026-10-24.json``'s issue records with both GitHub trackers.

The queue is the "complete issue queue" every index issue links to, and ``tasks.md`` 14.3 says each
accepted wave updates it together with the plan and the issue receipts. On 2026-10-26 it had drifted
in three ways at once: 21 closed issues still read ``open``, the issues filed after the 2026-10-24
snapshot had no record at all, and every rewritten body had a stale hash. Nothing failed, because
nothing compared the queue with the trackers. This does.

For every record, ``title``, ``latest_state`` and ``latest_body_sha256`` (sha256 of the raw body,
the convention the records already use) follow GitHub. A record whose issue closed is marked
``accepted_<date>``, with a receipt pointing at the comment posted with the close, unless it
already carries an ``accepted_*`` state. A record whose accepted issue was reopened is marked
``reopened_<date>``. The snapshot's own fields (``scope``, ``work_packages``, ``body_sha256``,
``counts``) are left alone.

Usage::

    python3 scripts/sync_repair_queue.py                      # dry run: print what would change
    python3 scripts/sync_repair_queue.py --write              # rewrite the queue in place
    python3 scripts/sync_repair_queue.py --map Wesker#56=REPAIR:B02,B07 --write

An open issue the queue does not map is not guessed at: placing it in a work package is a judgement,
so the run refuses to write until ``--map`` names its scope and packages.

Exit codes follow the CLI's vocabulary: ``0`` in sync (or written), ``1`` an open issue the queue
does not map (nothing written), ``2`` the question could not be asked (``gh`` failed, no queue).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

QUEUE = Path(__file__).resolve().parent.parent / "docs" / "REPAIR_QUEUE_2026-10-24.json"
REPOS = ("Wesker", "Detective")
_FIELDS = "number,title,body,state,stateReason,closedAt,createdAt,url,comments"
# The comment posted with a close lands within seconds of closedAt; anything further away is a
# later remark, not the closing evidence.
_CLOSING_WINDOW_S = 300


def record_disposition(state: str, acceptance_state: str, has_record: bool, mapped: bool) -> str:
    """What one issue's queue record needs (pure -- pinned).

    ``state`` is GitHub's (``open`` / ``closed``), ``acceptance_state`` the record's current one,
    ``has_record`` whether the queue holds a record for the issue, ``mapped`` whether a ``--map``
    places it. Having a record and having an acceptance state are separate facts: a record without
    a state is still a record, and must never be re-added. Named codes, because an issue the queue
    lacks and an issue whose acceptance a reopen withdrew are different repairs, and a truthy
    "needs work" would merge them.

    ``unmapped``   open, with no record and no ``--map``: a placement only a reader can make
    ``add``        no record, placed by ``--map``
    ``accept``     closed, and the record does not yet carry an acceptance
    ``reopened``   open again although the record says it was accepted
    ``refresh``    anything else: title, state and body hash follow GitHub
    """
    if not has_record:
        if mapped:
            return "add"
        return "unmapped" if state == "open" else "refresh"
    if state == "closed" and not acceptance_state.startswith("accepted_"):
        return "accept"
    if state == "open" and acceptance_state.startswith("accepted_"):
        return "reopened"
    return "refresh"


def _gh_json(args: list[str]) -> Any:
    out = subprocess.run(["gh", *args], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def _closing_comment(issue: dict) -> str:
    """The comment posted with the close, else the issue's own URL."""
    closed = datetime.fromisoformat(issue["closedAt"].replace("Z", "+00:00"))
    best, best_gap = issue["url"], None
    for comment in issue["comments"]:
        posted = datetime.fromisoformat(comment["createdAt"].replace("Z", "+00:00"))
        gap = abs((posted - closed).total_seconds())
        if gap <= _CLOSING_WINDOW_S and (best_gap is None or gap < best_gap):
            best, best_gap = comment["url"], gap
    return best


def _gh_lines(args: list[str]) -> list[str]:
    out = subprocess.run(["gh", *args], capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if line.strip()]


def _reopened_on(repo: str, number: int) -> str:
    """The date of the issue's last reopen. ``--jq`` runs per page, so a timeline longer than one
    page yields lines, never two JSON arrays back to back for ``json.loads`` to reject."""
    dates = _gh_lines(
        [
            "api",
            f"repos/rohanvinaik/{repo}/issues/{number}/timeline",
            "--paginate",
            "--jq",
            '.[] | select(.event == "reopened") | .created_at',
        ]
    )
    return dates[-1][:10] if dates else datetime.now().date().isoformat()


def _parse_maps(argv: list[str]) -> dict[tuple[str, int], tuple[str, list[str]]]:
    maps: dict[tuple[str, int], tuple[str, list[str]]] = {}
    for i, arg in enumerate(argv):
        if arg == "--map":
            spec = argv[i + 1]  # Repo#N=SCOPE:B01,B02
            target, placement = spec.split("=", 1)
            repo, number = target.split("#", 1)
            scope, _, packages = placement.partition(":")
            maps[(repo, int(number))] = (scope, [p for p in packages.split(",") if p])
    return maps


def _sync(queue: dict, maps: dict) -> tuple[list[str], list[str]]:
    records = {(r["repository"], r["number"]): r for r in queue["issues"]}
    changes: list[str] = []
    unmapped: list[str] = []
    for repo in REPOS:
        issues = _gh_json(
            [
                "issue",
                "list",
                "--repo",
                f"rohanvinaik/{repo}",
                "--state",
                "all",
                "--limit",
                "500",
                "--json",
                _FIELDS,
            ]
        )
        for issue in sorted(issues, key=lambda i: i["number"]):
            key = (repo, issue["number"])
            state = issue["state"].lower()
            record = records.get(key)
            code = record_disposition(
                state, (record or {}).get("acceptance_state", ""), record is not None, key in maps
            )
            if code == "unmapped":
                unmapped.append(f"{repo}#{issue['number']} {issue['title'][:80]}")
                continue
            if record is None and code == "refresh":
                continue  # closed before the snapshot and never mapped: not this queue's history
            if code == "add":
                scope, packages = maps[key]
                record = {
                    "repository": repo,
                    "number": issue["number"],
                    "title": issue["title"],
                    "url": issue["url"],
                    "scope": scope,
                    "work_packages": packages,
                    "acceptance_state": f"filed_{issue['createdAt'][:10].replace('-', '_')}",
                }
                queue["issues"].append(record)
                records[key] = record
                changes.append(f"ADD {repo}#{issue['number']} {scope} {packages}")
                code = "accept" if state == "closed" else "refresh"
            if record is None:
                continue
            if code == "accept":
                record["acceptance_state"] = f"accepted_{issue['closedAt'][:10].replace('-', '_')}"
                closing = _closing_comment(issue)
                record.setdefault(
                    "acceptance_receipt",
                    f"Closed {issue['closedAt'][:10]}; the evidence is in the closing comment: {closing}",
                )
                changes.append(f"ACCEPT {repo}#{issue['number']} -> {record['acceptance_state']}")
            elif code == "reopened":
                day = _reopened_on(repo, issue["number"])
                record["acceptance_state"] = f"reopened_{day.replace('-', '_')}"
                changes.append(f"REOPENED {repo}#{issue['number']} (receipt kept; read the reopen comment)")
            digest = hashlib.sha256(issue["body"].encode("utf-8")).hexdigest()
            for field, value in (
                ("title", issue["title"]),
                ("latest_state", state),
                ("latest_body_sha256", digest),
            ):
                if record.get(field) != value:
                    changes.append(f"{field.upper()} {repo}#{issue['number']}")
                    record[field] = value
    return changes, unmapped


def main(argv: list[str]) -> int:
    if not QUEUE.exists():
        print(f"no queue at {QUEUE}", file=sys.stderr)
        return 2
    queue = json.loads(QUEUE.read_text())
    try:
        changes, unmapped = _sync(queue, _parse_maps(argv))
    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"could not ask GitHub: {exc}", file=sys.stderr)
        return 2
    print("\n".join(changes) if changes else "in sync")
    if unmapped:
        print("\nOPEN AND UNMAPPED (place each with --map Repo#N=SCOPE:B01,B02; nothing written):")
        print("\n".join(f"  {line}" for line in unmapped))
        return 1
    if "--write" in argv and changes:
        QUEUE.write_text(json.dumps(queue, indent=2, ensure_ascii=False) + "\n")
        print(f"written ({len(changes)} changes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
