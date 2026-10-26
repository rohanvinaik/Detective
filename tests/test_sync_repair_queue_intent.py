"""The repair queue's sync names each record's repair, and never guesses where a new issue belongs.

On 2026-10-26 ``docs/REPAIR_QUEUE_2026-10-24.json`` (the queue every index issue links to) had drifted
from both trackers. 21 closed issues read ``open``, the ten issues filed after the 2026-10-24 snapshot
had no record, and every rewritten body carried a stale hash. Nothing failed, because nothing compared
the two. ``scripts/sync_repair_queue.py`` does, and these tests state what it must decide:

- an open issue the queue does not place is refused, never put in a work package by guess;
- a close is accepted once, and an existing acceptance is never rewritten;
- a reopen withdraws an acceptance;
- everything else only follows GitHub.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "sync_repair_queue.py"
_NAME = "sync_repair_queue"


def _load():
    """Import the script by path, under the name the regime binds it to (``sync_repair_queue``).

    It is deliberately not a package member. A private module name would give these tests a copy that
    no installed mutant ever enters (converge stops on exactly that: ``holder_not_found``), so the
    script is registered once under its bound name and shared.
    """
    existing = sys.modules.get(_NAME)
    if existing is not None and getattr(existing, "__file__", None) == str(_SCRIPT):
        return existing
    spec = importlib.util.spec_from_file_location(_NAME, _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[_NAME] = module
    spec.loader.exec_module(module)
    return module


sync = _load()


@pytest.mark.parametrize(
    ("state", "acceptance_state", "has_record", "mapped", "expected"),
    [
        ("open", "", False, False, "unmapped"),
        ("closed", "", False, False, "refresh"),
        ("open", "", False, True, "add"),
        ("closed", "", False, True, "add"),
        # A record without an acceptance state is still a record: never re-added (a KeyError once).
        ("open", "", True, False, "refresh"),
        ("closed", "", True, False, "accept"),
        ("closed", "filed_2026_10_25", True, False, "accept"),
        ("closed", "not_reaccepted_by_this_inventory", True, False, "accept"),
        ("closed", "a", True, True, "accept"),
        ("open", "accepted_2026_10_25", True, False, "reopened"),
        ("closed", "accepted_2026_10_25", True, False, "refresh"),
        ("open", "not_reaccepted_by_this_inventory", True, False, "refresh"),
        ("open", "reopened_2026_10_26", True, False, "refresh"),
        ("open", "a", True, False, "refresh"),
        ("x", "x", True, True, "refresh"),
    ],
)
def test_each_record_gets_its_named_repair(state, acceptance_state, has_record, mapped, expected):
    assert sync.record_disposition(state, acceptance_state, has_record, mapped) == expected


def test_a_map_names_scope_and_packages_and_may_name_none():
    maps = sync._parse_maps(["--map", "Wesker#56=REPAIR:B02,B07", "--write", "--map", "Detective#146=MIXED:"])
    assert maps == {("Wesker", 56): ("REPAIR", ["B02", "B07"]), ("Detective", 146): ("MIXED", [])}


def test_the_receipt_is_the_comment_posted_with_the_close_not_the_last_one():
    issue = {
        "url": "https://example/issues/1",
        "closedAt": "2026-10-26T09:00:00Z",
        "comments": [
            {"createdAt": "2026-10-25T09:00:00Z", "url": "earlier"},
            {"createdAt": "2026-10-26T09:00:04Z", "url": "closing"},
            {"createdAt": "2026-10-27T09:00:00Z", "url": "later remark"},
        ],
    }
    assert sync._closing_comment(issue) == "closing"


def test_a_close_with_no_comment_near_it_points_at_the_issue():
    issue = {
        "url": "https://example/issues/1",
        "closedAt": "2026-10-26T09:00:00Z",
        "comments": [{"createdAt": "2026-10-20T09:00:00Z", "url": "old"}],
    }
    assert sync._closing_comment(issue) == "https://example/issues/1"


def _issue(number, state, body="b", closed_at=None):
    return {
        "number": number,
        "title": f"issue {number}",
        "body": body,
        "state": state,
        "stateReason": None,
        "closedAt": closed_at,
        "createdAt": "2026-10-26T00:00:00Z",
        "url": f"https://example/{number}",
        "comments": [],
    }


def _queue(tmp_path, records):
    path = tmp_path / "queue.json"
    path.write_text(json.dumps({"issues": records}, indent=2) + "\n")
    return path


def test_an_unmapped_open_issue_refuses_and_writes_nothing(tmp_path, monkeypatch, capsys):
    record = {"repository": "Wesker", "number": 1, "acceptance_state": "filed_2026_10_25", "title": "issue 1"}
    path = _queue(tmp_path, [record])
    before = path.read_text()
    listing = {"Wesker": [_issue(1, "OPEN"), _issue(2, "OPEN")], "Detective": []}
    monkeypatch.setattr(sync, "QUEUE", path)
    monkeypatch.setattr(sync, "_gh_json", lambda args: listing[args[3].split("/")[1]])
    assert sync.main(["--write"]) == 1
    assert path.read_text() == before
    assert "Wesker#2" in capsys.readouterr().out


def test_a_mapped_new_issue_is_added_and_a_close_is_accepted(tmp_path, monkeypatch):
    record = {
        "repository": "Detective",
        "number": 5,
        "acceptance_state": "filed_2026_10_25",
        "title": "old title",
    }
    path = _queue(tmp_path, [record])
    listing = {
        "Wesker": [_issue(9, "OPEN")],
        "Detective": [_issue(5, "CLOSED", closed_at="2026-10-26T10:00:00Z")],
    }
    monkeypatch.setattr(sync, "QUEUE", path)
    monkeypatch.setattr(sync, "_gh_json", lambda args: listing[args[3].split("/")[1]])
    assert sync.main(["--map", "Wesker#9=REPAIR:B01", "--write"]) == 0
    records = {(r["repository"], r["number"]): r for r in json.loads(path.read_text())["issues"]}
    assert records[("Wesker", 9)]["work_packages"] == ["B01"]
    assert records[("Wesker", 9)]["acceptance_state"] == "filed_2026_10_26"
    assert records[("Detective", 5)]["acceptance_state"] == "accepted_2026_10_26"
    assert records[("Detective", 5)]["latest_state"] == "closed"
    assert records[("Detective", 5)]["title"] == "issue 5"


def test_an_existing_acceptance_receipt_is_never_rewritten(tmp_path, monkeypatch):
    record = {
        "repository": "Detective",
        "number": 5,
        "acceptance_state": "accepted_2026_10_25",
        "acceptance_receipt": "Closed 2026-10-25 on 6e10cf8: the measured receipt",
    }
    path = _queue(tmp_path, [record])
    listing = {"Wesker": [], "Detective": [_issue(5, "CLOSED", closed_at="2026-10-25T10:00:00Z")]}
    monkeypatch.setattr(sync, "QUEUE", path)
    monkeypatch.setattr(sync, "_gh_json", lambda args: listing[args[3].split("/")[1]])
    assert sync.main(["--write"]) == 0
    kept = json.loads(path.read_text())["issues"][0]
    assert kept["acceptance_receipt"] == "Closed 2026-10-25 on 6e10cf8: the measured receipt"
    assert kept["acceptance_state"] == "accepted_2026_10_25"


def test_a_record_without_an_acceptance_state_is_refreshed_not_re_added(tmp_path, monkeypatch):
    path = _queue(tmp_path, [{"repository": "Wesker", "number": 3, "title": "old"}])
    listing = {"Wesker": [_issue(3, "OPEN")], "Detective": []}
    monkeypatch.setattr(sync, "QUEUE", path)
    monkeypatch.setattr(sync, "_gh_json", lambda args: listing[args[3].split("/")[1]])
    assert sync.main(["--write"]) == 0
    records = json.loads(path.read_text())["issues"]
    assert len(records) == 1
    assert records[0]["title"] == "issue 3"
    assert "acceptance_state" not in records[0]


def test_a_reopen_date_is_the_last_reopened_event_across_pages(monkeypatch):
    seen = {}

    def fake_lines(args):
        seen["args"] = args
        return ["2026-10-20T01:00:00Z", "2026-10-26T09:00:00Z"]

    monkeypatch.setattr(sync, "_gh_lines", fake_lines)
    assert sync._reopened_on("Detective", 115) == "2026-10-26"
    assert "--paginate" in seen["args"]
    assert "--jq" in seen["args"]
