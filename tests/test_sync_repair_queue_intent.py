"""The repair queue's sync records tracker facts, and leaves every judgement to a reader.

On 2026-10-26 ``docs/REPAIR_QUEUE_2026-10-24.json`` (the queue every index issue links to) had drifted
from both trackers. 21 closed issues read ``open``, the ten issues filed after the 2026-10-24 snapshot
had no record, and every rewritten body carried a stale hash. ``scripts/sync_repair_queue.py``
compares the two. Its first version also stamped every completed closure ``accepted_*``, with a
"receipt" that only pointed at whatever comment sat near the close. A tracker closes for many reasons;
an acceptance is a claim about evidence. These tests state what the sync must decide:

- an open issue the queue does not place, or a completed closure with no recorded acceptance, needs
  a reader: exit 3, and nothing is written;
- an acceptance is recorded only from ``--accept`` with a receipt, and a replaced or withdrawn
  receipt moves to ``receipt_history``, never reused;
- a closure that is not a completion (duplicate, not planned) records its reason and claims no
  acceptance;
- drift in check mode is exit 1, never a quiet 0.
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
    ("state", "close_reason", "acceptance_state", "has_record", "mapped", "expected"),
    [
        ("open", "", "", False, False, "unmapped"),
        ("closed", "completed", "", False, False, "untracked"),
        ("open", "", "", False, True, "add"),
        ("closed", "completed", "", False, True, "add"),
        ("closed", "completed", "", True, False, "needs_acceptance"),
        ("closed", "completed", "filed_2026_10_25", True, False, "needs_acceptance"),
        ("closed", "completed", "reopened_2026_10_26", True, False, "needs_acceptance"),
        ("closed", "completed", "accepted_2026_10_25", True, False, "refresh"),
        ("closed", "not_planned", "filed_2026_10_25", True, False, "refresh"),
        ("closed", "duplicate", "", True, False, "refresh"),
        ("open", "", "accepted_2026_10_25", True, False, "reopened"),
        ("open", "", "reopened_2026_10_26", True, False, "refresh"),
        ("open", "", "", True, False, "refresh"),
        ("open", "", "not_reaccepted_by_this_inventory", True, True, "refresh"),
        ("x", "completed", "x", True, False, "refresh"),
    ],
)
def test_each_record_gets_its_named_repair(
    state, close_reason, acceptance_state, has_record, mapped, expected
):
    assert sync.record_disposition(state, close_reason, acceptance_state, has_record, mapped) == expected


def test_arguments_place_issues_and_carry_receipts():
    maps, accepts, write = sync._parse_args(
        ["--map", "Wesker#56=REPAIR:B02,B07", "--write", "--accept", "Detective#9=Closed on abc: 3/3 killed"]
    )
    assert maps == {("Wesker", 56): ("REPAIR", ["B02", "B07"])}
    assert accepts == {("Detective", 9): "Closed on abc: 3/3 killed"}
    assert write is True


@pytest.mark.parametrize("argv", [["--accept", "Detective#9="], ["--map", "Nowhere#1=REPAIR:B01"], ["--map"]])
def test_a_malformed_argument_is_refused(argv):
    with pytest.raises((ValueError, IndexError)):
        sync._parse_args(argv)


def test_the_closing_comment_is_the_one_posted_with_the_close():
    issue = {
        "closedAt": "2026-10-26T09:00:00Z",
        "comments": [
            {"createdAt": "2026-10-25T09:00:00Z", "url": "earlier"},
            {"createdAt": "2026-10-26T09:00:04Z", "url": "closing"},
            {"createdAt": "2026-10-27T09:00:00Z", "url": "later remark"},
        ],
    }
    assert sync._closing_comment(issue) == "closing"


def test_a_close_with_no_comment_near_it_records_no_comment():
    issue = {
        "closedAt": "2026-10-26T09:00:00Z",
        "comments": [{"createdAt": "2026-10-20T09:00:00Z", "url": "old"}],
    }
    assert sync._closing_comment(issue) is None


def test_a_reopen_date_is_the_last_reopened_event_across_slurped_pages(monkeypatch):
    pages = [
        [{"event": "commented", "created_at": "2026-10-19T00:00:00Z"}],
        [{"event": "reopened", "created_at": "2026-10-20T01:00:00Z"}],
        [
            {"event": "closed", "created_at": "2026-10-21T00:00:00Z"},
            {"event": "reopened", "created_at": "2026-10-26T09:00:00Z"},
        ],
    ]
    seen = {}

    def fake_gh(args):
        seen["args"] = args
        return json.dumps(pages)

    monkeypatch.setattr(sync, "_gh", fake_gh)
    assert sync._reopened_on("Detective", 115) == "2026-10-26"
    assert "--paginate" in seen["args"]
    assert "--slurp" in seen["args"]


def _issue(number, state, *, reason=None, closed_at=None, body="b", comments=()):
    return {
        "number": number,
        "title": f"issue {number}",
        "body": body,
        "state": state,
        "stateReason": reason,
        "closedAt": closed_at,
        "createdAt": "2026-10-26T00:00:00Z",
        "url": f"https://example/{number}",
        "comments": list(comments),
    }


def _setup(tmp_path, monkeypatch, records, listing):
    path = tmp_path / "queue.json"
    path.write_text(json.dumps({"issues": records}, indent=2) + "\n")
    monkeypatch.setattr(sync, "QUEUE", path)
    monkeypatch.setattr(sync, "_issues", lambda repo: listing.get(repo, []))
    monkeypatch.setattr(sync, "_reopened_on", lambda repo, number: "2026-10-26")
    return path


def _records(path):
    return {(r["repository"], r["number"]): r for r in json.loads(path.read_text())["issues"]}


def test_an_unmapped_open_issue_needs_a_reader_and_nothing_is_written(tmp_path, monkeypatch, capsys):
    record = {"repository": "Wesker", "number": 1, "acceptance_state": "filed_2026_10_25", "title": "stale"}
    path = _setup(tmp_path, monkeypatch, [record], {"Wesker": [_issue(1, "OPEN"), _issue(2, "OPEN")]})
    before = path.read_text()
    assert sync.main(["--write"]) == 3
    assert path.read_text() == before
    assert "Wesker#2" in capsys.readouterr().out


def test_a_completed_closure_is_never_accepted_by_the_sync(tmp_path, monkeypatch, capsys):
    record = {"repository": "Detective", "number": 5, "acceptance_state": "filed_2026_10_25"}
    closed = _issue(
        5,
        "CLOSED",
        reason="COMPLETED",
        closed_at="2026-10-26T10:00:00Z",
        comments=[{"createdAt": "2026-10-26T10:00:01Z", "url": "c1"}],
    )
    path = _setup(tmp_path, monkeypatch, [record], {"Detective": [closed]})
    before = path.read_text()
    assert sync.main(["--write"]) == 3
    assert path.read_text() == before
    assert "--accept Detective#5" in capsys.readouterr().out


def test_an_acceptance_comes_only_from_a_receipt_and_the_old_one_is_kept(tmp_path, monkeypatch):
    record = {
        "repository": "Detective",
        "number": 5,
        "acceptance_state": "filed_2026_10_25",
        "acceptance_receipt": "an older note",
    }
    closed = _issue(
        5,
        "CLOSED",
        reason="COMPLETED",
        closed_at="2026-10-26T10:00:00Z",
        comments=[{"createdAt": "2026-10-26T10:00:01Z", "url": "c1"}],
    )
    path = _setup(tmp_path, monkeypatch, [record], {"Detective": [closed]})
    assert (
        sync.main(["--accept", "Detective#5=Closed on abc123: 3/3 killed, intent tests 9 passed", "--write"])
        == 0
    )
    rec = _records(path)[("Detective", 5)]
    assert rec["acceptance_state"] == "accepted_2026_10_26"
    assert rec["acceptance_receipt"] == "Closed on abc123: 3/3 killed, intent tests 9 passed"
    assert rec["receipt_history"][0]["receipt"] == "an older note"
    assert rec["closing_comment"] == "c1"
    assert rec["tracker_close_reason"] == "completed"


def test_a_closure_that_is_not_a_completion_claims_no_acceptance(tmp_path, monkeypatch):
    record = {"repository": "Wesker", "number": 7, "acceptance_state": "filed_2026_10_25"}
    dup = _issue(7, "CLOSED", reason="DUPLICATE", closed_at="2026-10-26T10:00:00Z")
    path = _setup(tmp_path, monkeypatch, [record], {"Wesker": [dup]})
    assert sync.main(["--write"]) == 0
    rec = _records(path)[("Wesker", 7)]
    assert rec["acceptance_state"] == "filed_2026_10_25"
    assert rec["tracker_close_reason"] == "duplicate"
    assert "closing_comment" not in rec


def test_a_reopen_withdraws_the_acceptance_and_retires_its_receipt(tmp_path, monkeypatch):
    record = {
        "repository": "Detective",
        "number": 115,
        "acceptance_state": "accepted_2026_10_25",
        "acceptance_receipt": "Closed 2026-10-25 on 2253c2b",
        "latest_state": "closed",
        "tracker_close_reason": "completed",
        "tracker_closed_at": "2026-10-25T08:40:41Z",
    }
    path = _setup(tmp_path, monkeypatch, [record], {"Detective": [_issue(115, "OPEN")]})
    assert sync.main(["--write"]) == 0
    rec = _records(path)[("Detective", 115)]
    assert rec["acceptance_state"] == "reopened_2026_10_26"
    assert "acceptance_receipt" not in rec
    assert rec["receipt_history"][0]["receipt"] == "Closed 2026-10-25 on 2253c2b"
    assert "tracker_close_reason" not in rec
    assert "tracker_closed_at" not in rec


def test_drift_in_check_mode_is_exit_1_and_writes_nothing(tmp_path, monkeypatch):
    record = {"repository": "Wesker", "number": 3, "acceptance_state": "filed_2026_10_25", "title": "old"}
    path = _setup(tmp_path, monkeypatch, [record], {"Wesker": [_issue(3, "OPEN")]})
    before = path.read_text()
    assert sync.main([]) == 1
    assert path.read_text() == before
    assert sync.main(["--write"]) == 0
    assert sync.main([]) == 0


def test_a_record_without_an_acceptance_state_is_refreshed_never_re_added(tmp_path, monkeypatch):
    path = _setup(
        tmp_path,
        monkeypatch,
        [{"repository": "Wesker", "number": 3, "title": "old"}],
        {"Wesker": [_issue(3, "OPEN")]},
    )
    assert sync.main(["--write"]) == 0
    records = json.loads(path.read_text())["issues"]
    assert len(records) == 1
    assert records[0]["title"] == "issue 3"


def test_a_mapped_new_issue_is_added_with_its_placement(tmp_path, monkeypatch):
    path = _setup(tmp_path, monkeypatch, [], {"Wesker": [_issue(9, "OPEN")]})
    assert sync.main(["--map", "Wesker#9=REPAIR:B01", "--write"]) == 0
    rec = _records(path)[("Wesker", 9)]
    assert rec["work_packages"] == ["B01"]
    assert rec["acceptance_state"] == "filed_2026_10_26"


@pytest.mark.parametrize(
    "argv",
    [
        ["--accept", "Wesker#3=receipt for an open issue", "--write"],
        ["--map", "Wesker#3=REPAIR:B01", "--write"],
        ["--accept", "Wesker#99=no such issue", "--write"],
    ],
)
def test_an_argument_that_cannot_apply_is_refused_and_nothing_is_written(tmp_path, monkeypatch, argv):
    record = {"repository": "Wesker", "number": 3, "acceptance_state": "filed_2026_10_25", "title": "old"}
    path = _setup(tmp_path, monkeypatch, [record], {"Wesker": [_issue(3, "OPEN")]})
    before = path.read_text()
    assert sync.main(argv) == 2
    assert path.read_text() == before
