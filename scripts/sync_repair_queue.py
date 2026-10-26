#!/usr/bin/env python3
"""Keep ``docs/REPAIR_QUEUE_2026-10-24.json``'s issue records equal to what both GitHub trackers say.

The queue is the "complete issue queue" every index issue links to, and ``tasks.md`` 14.3 says each
accepted wave updates it together with the plan and the issue receipts. On 2026-10-26 it had drifted
in three ways at once: 21 closed issues still read ``open``, the issues filed after the 2026-10-24
snapshot had no record at all, and every rewritten body had a stale hash. Nothing failed, because
nothing compared the queue with the trackers. This does, and claims no more than it can check.

What it maintains are tracker FACTS:
- ``title``, ``latest_state`` and ``latest_body_sha256``. The hash is sha256 of the raw body, the
  convention the records already use.
- For a closed issue: ``tracker_close_reason`` (GitHub's state reason: completed, not_planned,
  duplicate), ``tracker_closed_at`` and ``closing_comment``. That last is the comment posted within
  five minutes of the close: a pointer, not a reading of what it says.

What it never does is decide that a closure was an ACCEPTANCE. A tracker closes for many reasons,
and ``accepted_<date>`` is a claim about evidence that only a reader who checked the evidence can
make::

    --accept Repo#N="<receipt: the sha, the pinned decision, the measurement>"

- A previous receipt moves to ``receipt_history``; it is never silently reused.
- A reopen withdraws the acceptance (``reopened_<date>``) and moves the receipt there too, so a
  re-close asks for a receipt again.
- Placement is a reader's call as well. An open issue the queue does not map waits for
  ``--map Repo#N=SCOPE:B01,B02``.
- The snapshot's own fields (``scope``, ``work_packages``, ``body_sha256``, ``counts``) are left
  alone.

Exit codes follow the CLI's epistemic vocabulary:

``0``  in sync, or ``--write`` applied and nothing awaits a reader
``1``  drift: the queue's facts differ from the trackers (check mode); ``--write`` repairs it
``2``  the question could not be asked (``gh`` failed, no queue, a malformed argument)
``3``  a reader is needed: an open issue the queue does not place, or a completed closure with no
       recorded acceptance. Nothing is written while any remains.
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
# later remark, not the comment that accompanied the close.
_CLOSING_WINDOW_S = 300
_TRACKER_FIELDS = ("tracker_close_reason", "tracker_closed_at", "closing_comment")


def record_disposition(
    state: str, close_reason: str, acceptance_state: str, has_record: bool, mapped: bool
) -> str:
    """What one issue's queue record needs (pure -- pinned).

    ``state`` is GitHub's (``open`` / ``closed``), ``close_reason`` its state reason for a closed
    issue, ``acceptance_state`` the record's own, ``has_record`` whether the queue holds a record,
    ``mapped`` whether a ``--map`` places it. Named codes, because each one is a different repair
    with a different owner. A truthy "needs work" would merge a reader's judgement into a
    mechanical refresh, which is how the first version came to stamp closures "accepted".

    ``untracked``         closed, and never in this queue: not its history
    ``unmapped``          open, with no record and no ``--map``: a placement only a reader can make
    ``add``               no record, placed by ``--map``
    ``needs_acceptance``  closed as completed, with no acceptance recorded: a receipt only a reader
                          who checked the evidence can give
    ``reopened``          open again although the record says it was accepted
    ``refresh``           anything else; the tracker facts follow GitHub
    """
    if not has_record:
        if mapped:
            return "add"
        return "unmapped" if state == "open" else "untracked"
    accepted = acceptance_state.startswith("accepted_")
    if state == "closed" and close_reason == "completed" and not accepted:
        return "needs_acceptance"
    if state == "open" and accepted:
        return "reopened"
    return "refresh"


def _gh(args: list[str]) -> str:
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=True).stdout


def _issues(repo: str) -> list[dict[str, Any]]:
    return json.loads(
        _gh(
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
    )


def _closing_comment(issue: dict[str, Any]) -> str | None:
    """The comment posted with the close, if one was; otherwise ``None``."""
    closed = datetime.fromisoformat(issue["closedAt"].replace("Z", "+00:00"))
    best, best_gap = None, None
    for comment in issue["comments"]:
        posted = datetime.fromisoformat(comment["createdAt"].replace("Z", "+00:00"))
        gap = abs((posted - closed).total_seconds())
        if gap <= _CLOSING_WINDOW_S and (best_gap is None or gap < best_gap):
            best, best_gap = comment["url"], gap
    return best


def _reopened_on(repo: str, number: int) -> str:
    """The date of the issue's last reopen. ``--slurp`` wraps every page in one JSON array."""
    pages = json.loads(
        _gh(["api", f"repos/rohanvinaik/{repo}/issues/{number}/timeline", "--paginate", "--slurp"])
    )
    dates = [event["created_at"] for page in pages for event in page if event.get("event") == "reopened"]
    return dates[-1][:10] if dates else datetime.now().date().isoformat()


def _parse_args(argv: list[str]) -> tuple[dict, dict, bool]:
    """``--map Repo#N=SCOPE:B01,B02`` and ``--accept Repo#N=receipt``; raises ValueError if malformed."""
    maps: dict[tuple[str, int], tuple[str, list[str]]] = {}
    accepts: dict[tuple[str, int], str] = {}
    for i, arg in enumerate(argv):
        if arg not in ("--map", "--accept"):
            continue
        target, value = argv[i + 1].split("=", 1)
        repo, number = target.split("#", 1)
        key = (repo, int(number))
        if repo not in REPOS:
            raise ValueError(f"unknown repository in {argv[i + 1]!r}")
        if arg == "--map":
            scope, _, packages = value.partition(":")
            maps[key] = (scope, [p for p in packages.split(",") if p])
        elif value.strip():
            accepts[key] = value.strip()
        else:
            raise ValueError(f"--accept {target} needs a receipt")
    return maps, accepts, "--write" in argv


def _refresh_facts(record: dict, issue: dict, state: str) -> list[str]:
    facts: dict[str, Any] = {
        "title": issue["title"],
        "latest_state": state,
        "latest_body_sha256": hashlib.sha256(issue["body"].encode("utf-8")).hexdigest(),
    }
    if state == "closed":
        facts["tracker_close_reason"] = (issue.get("stateReason") or "completed").lower()
        facts["tracker_closed_at"] = issue["closedAt"]
        facts["closing_comment"] = _closing_comment(issue)
    changed = []
    for field, value in facts.items():
        if value is None:
            if field in record:
                del record[field]
                changed.append(field)
        elif record.get(field) != value:
            record[field] = value
            changed.append(field)
    if state == "open":
        for field in _TRACKER_FIELDS:
            if field in record:
                del record[field]
                changed.append(field)
    return changed


def _retire_receipt(record: dict, why: str) -> None:
    if "acceptance_receipt" in record:
        history = record.setdefault("receipt_history", [])
        history.append(
            {
                "acceptance_state": record.get("acceptance_state", ""),
                "receipt": record.pop("acceptance_receipt"),
                "retired": why,
            }
        )


def _sync(queue: dict, maps: dict, accepts: dict) -> tuple[list[str], list[str]]:
    """Apply facts, placements and receipts to ``queue`` in place; return (changes, needs_reader)."""
    records = {(r["repository"], r["number"]): r for r in queue["issues"]}
    changes: list[str] = []
    needs_reader: list[str] = []
    consumed: set[tuple[str, int]] = set()
    for repo in REPOS:
        for issue in sorted(_issues(repo), key=lambda i: i["number"]):
            key = (repo, issue["number"])
            name = f"{repo}#{issue['number']}"
            state = issue["state"].lower()
            reason = (issue.get("stateReason") or "completed").lower() if state == "closed" else ""
            record = records.get(key)
            code = record_disposition(
                state, reason, (record or {}).get("acceptance_state", ""), record is not None, key in maps
            )
            if code == "untracked":
                continue
            if code == "unmapped":
                needs_reader.append(
                    f"{name} open, not in the queue: place it with --map {name}=SCOPE:B01,B02"
                )
                continue
            if code == "add":
                consumed.add(key)
                scope, packages = maps[key]
                record = {
                    "repository": repo,
                    "number": issue["number"],
                    "url": issue["url"],
                    "scope": scope,
                    "work_packages": packages,
                    "acceptance_state": f"filed_{issue['createdAt'][:10].replace('-', '_')}",
                }
                queue["issues"].append(record)
                records[key] = record
                changes.append(f"ADD {name} {scope} {packages}")
                code = record_disposition(state, reason, record["acceptance_state"], True, True)
            assert record is not None
            if code == "reopened":
                record["acceptance_state"] = (
                    f"reopened_{_reopened_on(repo, issue['number']).replace('-', '_')}"
                )
                _retire_receipt(record, "the issue was reopened")
                changes.append(f"REOPENED {name}: acceptance withdrawn, receipt moved to receipt_history")
            if key in accepts:
                if state != "closed":
                    raise ValueError(f"--accept {name}: the issue is open")
                consumed.add(key)
                _retire_receipt(record, "replaced by a new --accept")
                record["acceptance_state"] = f"accepted_{issue['closedAt'][:10].replace('-', '_')}"
                record["acceptance_receipt"] = accepts[key]
                changes.append(f"ACCEPT {name}")
            elif code == "needs_acceptance":
                needs_reader.append(
                    f"{name} closed as completed with no acceptance recorded: "
                    f'read its evidence, then --accept {name}="<receipt>"'
                )
            changes += [f"{field.upper()} {name}" for field in _refresh_facts(record, issue, state)]
    unused = sorted((set(maps) | set(accepts)) - consumed)
    if unused:
        names = ", ".join(f"{repo}#{number}" for repo, number in unused)
        raise ValueError(
            f"--map/--accept named an issue it could not apply to (already placed, or not found): {names}"
        )
    return changes, needs_reader


def main(argv: list[str]) -> int:
    if not QUEUE.exists():
        print(f"no queue at {QUEUE}", file=sys.stderr)
        return 2
    queue = json.loads(QUEUE.read_text())
    try:
        maps, accepts, write = _parse_args(argv)
        changes, needs_reader = _sync(queue, maps, accepts)
    except (ValueError, IndexError) as exc:
        print(f"malformed argument: {exc}", file=sys.stderr)
        return 2
    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"could not ask GitHub: {exc}", file=sys.stderr)
        return 2
    print("\n".join(changes) if changes else "no fact differs from the trackers")
    if needs_reader:
        print("\nA READER IS NEEDED (nothing written):")
        print("\n".join(f"  {line}" for line in needs_reader))
        return 3
    if not changes:
        print("in sync")
        return 0
    if not write:
        print(f"\ndrift: {len(changes)} change(s); --write applies them")
        return 1
    QUEUE.write_text(json.dumps(queue, indent=2, ensure_ascii=False) + "\n")
    print(f"written ({len(changes)} change(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
