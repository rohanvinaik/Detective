"""Intent tests for the paired budget read on `verify-rewrite --budget` (DETERMINISTIC_SICP §7 /
§14.3 slice 7).

What the read is FOR, stated from intent:

- efficiency is a DETERMINISTIC budget in OPCODES, never wall-clock, and every number says so;
- the two-ledger law holds twice: the preservation verdict owns validity (a rewrite the gate did
  not pass is INADMISSIBLE whatever its counts), and every ladder input is compared arm-to-arm —
  a disagreement there is a distinguishing input the gate missed, reported, never averaged away;
- a shape the instrument cannot ladder honestly — an unannotated parameter, a bare `list`, no
  parameters, a method, an interpreter without sys.monitoring — reads UNMEASURABLE with the reason,
  never a guessed number; and a PRESERVED rewrite whose payoff could not be measured exits 3;
- through the real command path, the `--budget` block rides beneath the verdict and the JSON
  carries the same read.
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap

import pytest

from Detective.budget import (
    LADDER,
    PairedBudgetRead,
    budget_exit,
    ladder_kinds,
    paired_budget_read,
)
from Detective.cli import _format_budget_block, _run_verify_rewrite
from Detective.rewrite import make_receipt, verify_rewrite_exit

HAS_MONITORING = hasattr(sys, "monitoring")

# ---------------------------------------------------------------- ladder_kinds (pure)


@pytest.mark.parametrize(
    "annotations, expected",
    [
        (("list[int]",), ("list[int]",)),
        (("int", "str"), ("int", "str")),
        (("dict[str, int]",), ("dict[str,int]",)),  # spaces are not a different annotation
        (("set[int]", "list[str]"), ("set[int]", "list[str]")),
        (("list",), None),  # a bare list has no element kind — never guessed
        (("Foo",), None),
        (("",), None),  # unannotated
        (("list[int]", ""), None),  # one unannotated parameter refuses the whole ladder
        ((), None),  # nothing to scale
    ],
)
def test_ladder_kinds_exact_or_refuse(annotations, expected) -> None:
    assert ladder_kinds(annotations) == expected


# ---------------------------------------------------------------- budget_exit (pure)


@pytest.mark.parametrize("verify_exit", [0, 1, 2, 3])
@pytest.mark.parametrize("disposition", ["refund", "parity", "regression", "unmeasurable", "inadmissible"])
def test_budget_exit_only_moves_a_preserved_zero_to_three(verify_exit, disposition) -> None:
    expected = 3 if (verify_exit == 0 and disposition == "unmeasurable") else verify_exit
    assert budget_exit(verify_exit, disposition) == expected


def test_budget_exit_never_invents_a_pass_or_a_gap() -> None:
    for disposition in ("refund", "parity", "regression", "inadmissible", "junk"):
        assert budget_exit(0, disposition) == 0
        assert budget_exit(1, disposition) == 1
    assert budget_exit(1, "unmeasurable") == 1  # a determined negative outranks the budget's silence
    assert budget_exit(2, "unmeasurable") == 2


# ---------------------------------------------------------------- paired_budget_read (the instrument)


def _dupes_naive(xs: list) -> list:
    out = []
    for i, a in enumerate(xs):
        for b in xs[i + 1 :]:
            if a == b and a not in out:
                out.append(a)
    return out


def _dupes_seen(xs: list) -> list:
    seen: set = set()
    dup: set = set()
    out = []
    for a in xs:
        if a in seen and a not in dup:
            dup.add(a)
            out.append(a)
        seen.add(a)
    return out


def _dupes_wrong(xs: list) -> list:
    # A different answer on every ladder input with ≥2 duplicates: the same duplicates, reversed.
    # (A first draft used `sorted(set(...))`, which on the ladder's `i % 7` inputs is IDENTICAL to
    # the honest answer — measured while writing this fixture, not assumed.)
    return _dupes_seen(xs)[::-1]


def test_a_known_refund_is_rederived_or_the_counter_declines_honestly() -> None:
    read = paired_budget_read(_dupes_naive, _dupes_seen, ("list[int]",), gate_preserved=True)
    assert read.unit == "opcodes"
    if HAS_MONITORING:
        assert read.sizes == LADDER
        assert (read.incumbent_class, read.candidate_class) == ("quadratic_plus", "linear")
        assert read.verdict == "refund" and read.disposition == "refund" and read.delta_zero
        assert 0 < read.ratio_at_top < 1
    else:
        assert read.sizes == ()
        assert read.disposition == "unmeasurable" and "sys.monitoring" in read.note


def test_the_gate_owns_validity_a_failed_gate_is_inadmissible_whatever_the_counts() -> None:
    read = paired_budget_read(_dupes_naive, _dupes_seen, ("list[int]",), gate_preserved=False)
    assert read.delta_zero is False and read.disposition == "inadmissible"


def test_a_ladder_disagreement_is_reported_not_averaged_away() -> None:
    read = paired_budget_read(_dupes_seen, _dupes_wrong, ("list[int]",), gate_preserved=True)
    if HAS_MONITORING:
        assert read.delta_zero is False and read.disposition == "inadmissible"
        assert "old ≠ new at ladder size" in read.note
    else:
        assert read.disposition in ("inadmissible", "unmeasurable")


def test_no_honest_ladder_reads_unmeasurable_with_the_remedy() -> None:
    read = paired_budget_read(_dupes_naive, _dupes_seen, None, gate_preserved=True)
    assert read.sizes == () and read.disposition == "unmeasurable"
    assert "annotate" in read.note and "--budget" in read.note


def test_the_block_prints_opcodes_never_cost() -> None:
    read = PairedBudgetRead(
        (16, 32), (100, 400), (50, 100), "quadratic_plus", "linear", 0.25, True, "refund", "refund"
    )
    text = _format_budget_block(read)
    assert "opcodes" in text and "cost" not in text.lower()
    assert "refund" in text and "0.250" in text and "quadratic_plus" in text
    unmeasurable = PairedBudgetRead(
        (), (), (), "unmeasurable", "unmeasurable", 0.0, True, "unmeasurable", "unmeasurable", note="why"
    )
    assert "exits 3" in _format_budget_block(unmeasurable) and "why" in _format_budget_block(unmeasurable)


# ---------------------------------------------------------------- through the command path

_NAIVE = textwrap.dedent(
    """
    def dupes(xs: list[int]) -> list:
        out = []
        for i, a in enumerate(xs):
            for b in xs[i + 1:]:
                if a == b and a not in out:
                    out.append(a)
        return out
    """
)
_SEEN = textwrap.dedent(
    """
    def dupes(xs: list[int]) -> list:
        seen = set()
        dup = set()
        out = []
        for a in xs:
            if a in seen and a not in dup:
                dup.add(a)
                out.append(a)
            seen.add(a)
        return out
    """
)


def test_verify_rewrite_budget_rides_beneath_the_verdict(tmp_path, capsys) -> None:
    root = tmp_path
    (root / "calc.py").write_text(_NAIVE, encoding="utf-8")
    receipt = make_receipt("calc.py", "dupes", str(root))
    receipt_path = root / "dupes.receipt.json"
    receipt_path.write_text(receipt.to_json(), encoding="utf-8")
    (root / "calc.py").write_text(_SEEN, encoding="utf-8")

    args = argparse.Namespace(
        receipt_path=str(receipt_path),
        target="calc.py::dupes",
        project_root=str(root),
        json=True,
        learn=False,
        budget=True,
    )
    code = _run_verify_rewrite(args, "calc.py", "dupes")
    payload = json.loads(capsys.readouterr().out)
    assert "budget" in payload and payload["budget"]["unit"] == "opcodes"
    # The exit is the verify verdict's own code, moved to 3 only for PRESERVED + unmeasurable.
    assert (
        payload["exit_code"]
        == code
        == budget_exit(verify_rewrite_exit(payload["verdict"]), payload["budget"]["disposition"])
    )
    if HAS_MONITORING and payload["verdict"] == "PRESERVED":
        assert payload["budget"]["disposition"] == "refund"
        assert (payload["budget"]["incumbent_class"], payload["budget"]["candidate_class"]) == (
            "quadratic_plus",
            "linear",
        )
    if not HAS_MONITORING and payload["verdict"] == "PRESERVED":
        assert payload["exit_code"] == 3 and payload["budget"]["disposition"] == "unmeasurable"


def test_verify_rewrite_budget_on_an_unannotated_function_is_unmeasurable(tmp_path, capsys) -> None:
    root = tmp_path
    (root / "calc.py").write_text(_NAIVE.replace("xs: list[int]", "xs"), encoding="utf-8")
    receipt = make_receipt("calc.py", "dupes", str(root))
    receipt_path = root / "dupes.receipt.json"
    receipt_path.write_text(receipt.to_json(), encoding="utf-8")
    (root / "calc.py").write_text(_SEEN.replace("xs: list[int]", "xs"), encoding="utf-8")
    args = argparse.Namespace(
        receipt_path=str(receipt_path),
        target="calc.py::dupes",
        project_root=str(root),
        json=True,
        learn=False,
        budget=True,
    )
    code = _run_verify_rewrite(args, "calc.py", "dupes")
    payload = json.loads(capsys.readouterr().out)
    # The ladder's absence is always NAMED. The disposition is "unmeasurable" only when the gate
    # passed; under any other verdict the two-ledger law says INADMISSIBLE — the gate owns validity,
    # and a payoff that could not be read is moot beneath a rewrite that did not pass.
    assert "annotate" in payload["budget"]["note"]
    if payload["verdict"] == "PRESERVED":
        assert payload["budget"]["disposition"] == "unmeasurable" and code == 3
    else:
        assert payload["budget"]["disposition"] == "inadmissible"
        assert code == verify_rewrite_exit(payload["verdict"])
