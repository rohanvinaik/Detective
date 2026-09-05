"""Intent tests for the style judgment ledger (DETERMINISTIC_SICP §14.5, slice 6).

What the ledger is FOR, stated from intent:

- the driver's answer to an AMBIGUOUS region is RECORDED, so it does not re-escalate every run;
- it is DEFEASIBLE: a moved definition or a changed reading REOPENS it — reported as such, never
  silently honoured and never silently dropped;
- the division holds at the file: a separate ledger from the mutant-equivalence flags, and USER
  DATA that `purge` never deletes;
- the vocabulary is closed and unknown dispositions are named, never honoured.
"""

from __future__ import annotations

import json

import pytest

from Detective.judgments import (
    DISPOSITION_UNKNOWN,
    JUDGMENTS_REL_PATH,
    LEAVE,
    PROCEED,
    REOPENED_DIGEST,
    REOPENED_VERDICT,
    StyleJudgment,
    add_judgment,
    judgment_for,
    judgment_standing,
    load_judgments,
    style_flag_refusal,
)
from Detective.verdict_cache import purge

# ---------------------------------------------------------------- judgment_standing (pure)


@pytest.mark.parametrize(
    "recorded_digest, current_digest, recorded_verdict, current_verdict, disposition, expected",
    [
        ("", "d1", "AMBIGUOUS", "AMBIGUOUS", LEAVE, ""),  # no judgment at all
        ("", "d1", "AMBIGUOUS", "AMBIGUOUS", "junk", ""),  # …whatever the other fields say
        ("d0", "d1", "AMBIGUOUS", "AMBIGUOUS", LEAVE, REOPENED_DIGEST),  # the code moved
        ("d0", "d1", "AMBIGUOUS", "CONSTRUCTIVE", PROCEED, REOPENED_DIGEST),  # digest outranks verdict
        ("d1", "d1", "AMBIGUOUS", "CONSTRUCTIVE", LEAVE, REOPENED_VERDICT),  # the reading changed
        ("d1", "d1", "AMBIGUOUS", "AMBIGUOUS", "junk", DISPOSITION_UNKNOWN),  # never honoured
        ("d1", "d1", "AMBIGUOUS", "AMBIGUOUS", "", DISPOSITION_UNKNOWN),
        ("d1", "d1", "AMBIGUOUS", "AMBIGUOUS", LEAVE, LEAVE),
        ("d1", "d1", "AMBIGUOUS", "AMBIGUOUS", PROCEED, PROCEED),
        (
            "d1",
            "d1",
            "CONSTRUCTIVE",
            "CONSTRUCTIVE",
            LEAVE,
            LEAVE,
        ),  # a leave on a constructive region stands too
    ],
)
def test_judgment_standing(
    recorded_digest, current_digest, recorded_verdict, current_verdict, disposition, expected
):
    assert (
        judgment_standing(recorded_digest, current_digest, recorded_verdict, current_verdict, disposition)
        == expected
    )


@pytest.mark.parametrize(
    "has_id, leave, proceed, expected",
    [
        (False, True, False, ""),
        (False, False, True, ""),
        (False, False, False, "no_disposition"),
        (False, True, True, "both_dispositions"),
        (True, True, False, "mutant_id_with_style"),
        (True, False, False, "mutant_id_with_style"),  # the division-blurring mistake is named first
        (True, True, True, "mutant_id_with_style"),
        (True, False, True, "mutant_id_with_style"),
    ],
)
def test_style_flag_refusal_truth_table(has_id, leave, proceed, expected) -> None:
    assert style_flag_refusal(has_id, leave, proceed) == expected


def test_reopened_is_never_silently_a_disposition() -> None:
    for standing in (REOPENED_DIGEST, REOPENED_VERDICT, DISPOSITION_UNKNOWN, ""):
        assert standing not in (LEAVE, PROCEED)


# ---------------------------------------------------------------- the ledger (I/O shell)


def test_record_then_read_round_trips(tmp_path) -> None:
    j = add_judgment(str(tmp_path), "m.py::f", "d1", "AMBIGUOUS", LEAVE, "one lens; fine as it is")
    assert j == StyleJudgment("m.py::f", "d1", "AMBIGUOUS", LEAVE, "one lens; fine as it is")
    assert judgment_for(str(tmp_path), "m.py::f") == j
    assert judgment_for(str(tmp_path), "m.py::g") is None


def test_one_judgment_per_region_and_others_survive(tmp_path) -> None:
    add_judgment(str(tmp_path), "m.py::f", "d1", "AMBIGUOUS", LEAVE)
    add_judgment(str(tmp_path), "m.py::g", "d2", "AMBIGUOUS", PROCEED)
    add_judgment(str(tmp_path), "m.py::f", "d1", "AMBIGUOUS", PROCEED, "changed my mind")
    assert judgment_for(str(tmp_path), "m.py::f").disposition == PROCEED
    assert judgment_for(str(tmp_path), "m.py::g").disposition == PROCEED
    assert set(load_judgments(str(tmp_path))) == {"m.py::f", "m.py::g"}


def test_ledger_is_deterministic_bytes(tmp_path) -> None:
    add_judgment(str(tmp_path), "m.py::g", "d2", "AMBIGUOUS", PROCEED)
    add_judgment(str(tmp_path), "m.py::f", "d1", "AMBIGUOUS", LEAVE)
    first = (tmp_path / JUDGMENTS_REL_PATH).read_bytes()
    add_judgment(str(tmp_path), "m.py::f", "d1", "AMBIGUOUS", LEAVE)
    add_judgment(str(tmp_path), "m.py::g", "d2", "AMBIGUOUS", PROCEED)
    assert (tmp_path / JUDGMENTS_REL_PATH).read_bytes() == first
    assert list(json.loads(first)) == ["m.py::f", "m.py::g"]


def test_malformed_entries_are_skipped_and_a_corrupt_ledger_is_no_ledger(tmp_path) -> None:
    ledger = tmp_path / JUDGMENTS_REL_PATH
    ledger.parent.mkdir(parents=True)
    ledger.write_text(
        json.dumps(
            {
                "m.py::f": {
                    "func_key": "m.py::f",
                    "function_digest": "d1",
                    "verdict": "AMBIGUOUS",
                    "disposition": "leave",
                },
                "bad": {"nope": 1},
            }
        ),
        encoding="utf-8",
    )
    assert set(load_judgments(str(tmp_path))) == {"m.py::f"}
    ledger.write_text("{not json", encoding="utf-8")
    assert load_judgments(str(tmp_path)) == {}
    assert judgment_for(str(tmp_path), "m.py::f") is None


def test_judgments_are_user_data_purge_never_deletes_them(tmp_path) -> None:
    add_judgment(str(tmp_path), "m.py::f", "d1", "AMBIGUOUS", LEAVE)
    removed, _ = purge(str(tmp_path))
    assert str(tmp_path / JUDGMENTS_REL_PATH) not in removed
    assert (tmp_path / JUDGMENTS_REL_PATH).exists()


def test_the_ledger_is_not_the_equivalence_ledger(tmp_path) -> None:
    add_judgment(str(tmp_path), "m.py::f", "d1", "AMBIGUOUS", LEAVE)
    assert not (tmp_path / ".detective" / "equivalents.json").exists()
