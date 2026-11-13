"""Intent tests for the converge certificate ledger (§14.1, slice 1b — founder ruling 2026-09-05).

The defect: a converge that finds the hand-written suite already complete writes NO synth, and the
only other artifacts — the pins/verdict caches (keyed for other purposes) and the report file (keyed
by BARE qualname) — cannot serve as a per-target certificate. So the best-tested functions read
`unpinned` under the ordering law, forever. The fix, chosen over receipts-as-certificate: converge
records its terminal verdict per (func_key, function digest) in the ledger.

WHERE the ledger lives (founder ruling 2026-09-06: "the synths and the certificates should be
synced properly"): beside the suite it certifies — `<write-dir>/certificates.json`,
`tests/detective/` by default — versioned with the synths, never purged. It first lived under the
ignored `.detective/`, and the first `plan Detective/` over a fresh reading found every region
unpinned but the fifteen certified that morning: a certificate that exists only on the machine that
ran converge makes the ordering law non-reproducible from the repo.

What this pins from intent:

- the ledger records `certificate_standing`'s code VERBATIM — the one derivation, consumed;
- a result with no identity (empty digest) is never recorded — a certificate about an unknown
  definition would read as one about every definition;
- the bytes are deterministic: no clock, sorted keys — identical runs, identical file;
- a refusal is named apart from an honest gap, receiver before environment;
- the ledger lives beside the synths (the default write-dir), a custom write-dir carries its own,
  and the status reader follows the write-dir it was given;
- `purge` SPARES the ledger — it is part of the suite, not a cache — and the user-data ledgers;
- END TO END through the real command path: `converge` on a tmp repo writes the entry for the
  target at its current digest with the standing the result itself claims, and the status reader
  then sees the certificate — with no synth file involved in the decision.
"""

from __future__ import annotations

import ast
import json
import os
import textwrap
from pathlib import Path

import pytest

from Detective import pins
from Detective.certificates import (
    CERTIFICATES_REL_PATH,
    certificate_refusal,
    load_certificate,
    record_certificate,
)
from Detective.certify import read_behavior_status
from Detective.converge import converge
from Detective.verdict_cache import purge

# ---------------------------------------------------------------- certificate_refusal (pure)


@pytest.mark.parametrize(
    "receiver, gated, expected",
    [
        ("", (), ""),
        ("zero-arg:Basket fails", (), "needs_receiver:zero-arg:Basket fails"),
        ("", ("time.time",), "environment_gated:time.time"),
        ("", ("time.time", "os.environ"), "environment_gated:time.time,os.environ"),
        ("zero-arg:Basket fails", ("time.time",), "needs_receiver:zero-arg:Basket fails"),
    ],
)
def test_certificate_refusal_names_the_decline(receiver, gated, expected) -> None:
    assert certificate_refusal(receiver, gated) == expected


def test_receiver_outranks_environment() -> None:
    # A method that could not be constructed was never measured; its environment reads are moot.
    assert certificate_refusal("r", ("e",)).startswith("needs_receiver:")


# ---------------------------------------------------------------- record / load (the I/O shell)


def test_record_then_load_round_trips(tmp_path) -> None:
    path = record_certificate(str(tmp_path), "m.py::f", "abc123", "complete", "")
    assert path.endswith(CERTIFICATES_REL_PATH)
    assert load_certificate(str(tmp_path), "m.py::f") == {
        "function_digest": "abc123",
        "standing": "complete",
        "refusal": "",
        # Written even when empty: `[]` is "recorded, nothing cut" and a missing key is "written
        # before the field existed". Exact-equality on purpose — the shape is the contract.
        "cut_reasons": [],
    }


def test_entries_for_other_targets_survive_and_same_target_is_replaced(tmp_path) -> None:
    record_certificate(str(tmp_path), "m.py::f", "d1", "incomplete", "")
    record_certificate(str(tmp_path), "m.py::g", "d2", "complete", "")
    record_certificate(str(tmp_path), "m.py::f", "d3", "complete", "")
    assert load_certificate(str(tmp_path), "m.py::f") == {
        "function_digest": "d3",
        "standing": "complete",
        "refusal": "",
        "cut_reasons": [],
    }
    assert load_certificate(str(tmp_path), "m.py::g") == {
        "function_digest": "d2",
        "standing": "complete",
        "refusal": "",
        "cut_reasons": [],
    }


def test_an_identity_less_result_is_never_recorded(tmp_path) -> None:
    assert record_certificate(str(tmp_path), "m.py::f", "", "complete", "") == ""
    assert load_certificate(str(tmp_path), "m.py::f") is None
    assert not (tmp_path / CERTIFICATES_REL_PATH).exists()


def test_the_ledger_bytes_are_deterministic(tmp_path) -> None:
    record_certificate(str(tmp_path), "m.py::g", "d2", "complete", "")
    record_certificate(str(tmp_path), "m.py::f", "d1", "incomplete", "environment_gated:time.time")
    first = (tmp_path / CERTIFICATES_REL_PATH).read_bytes()
    record_certificate(str(tmp_path), "m.py::f", "d1", "incomplete", "environment_gated:time.time")
    record_certificate(str(tmp_path), "m.py::g", "d2", "complete", "")
    assert (tmp_path / CERTIFICATES_REL_PATH).read_bytes() == first
    assert list(json.loads(first)) == ["m.py::f", "m.py::g"]  # sorted keys


def test_a_corrupt_ledger_is_no_ledger(tmp_path) -> None:
    ledger = tmp_path / CERTIFICATES_REL_PATH
    ledger.parent.mkdir(parents=True)
    ledger.write_text("{not json", encoding="utf-8")
    assert load_certificate(str(tmp_path), "m.py::f") is None
    # …and recording over it recovers, rather than raising.
    assert record_certificate(str(tmp_path), "m.py::f", "d1", "complete", "")
    assert load_certificate(str(tmp_path), "m.py::f") is not None


def test_missing_ledger_loads_none(tmp_path) -> None:
    assert load_certificate(str(tmp_path), "m.py::f") is None


def test_the_ledger_lives_beside_the_synths_and_never_under_the_ignored_cache_dir(tmp_path) -> None:
    path = record_certificate(str(tmp_path), "m.py::f", "d1", "complete", "")
    assert path == str(tmp_path / "tests" / "detective" / "certificates.json")
    assert not (tmp_path / ".detective").exists()


def test_a_custom_write_dir_carries_its_own_ledger_and_the_reader_follows_it(tmp_path) -> None:
    node = ast.parse("def f(x):\n    return x + 1\n").body[0]
    record_certificate(
        str(tmp_path), "m.py::f", pins.function_digest(node), "complete", "", write_dir="suite"
    )
    assert (tmp_path / "suite" / "certificates.json").exists()
    assert load_certificate(str(tmp_path), "m.py::f", write_dir="suite")["standing"] == "complete"
    # The default location is a DIFFERENT suite: nothing was certified there.
    assert load_certificate(str(tmp_path), "m.py::f") is None
    assert read_behavior_status(str(tmp_path), "suite", "m.py::f", node) == "pinned"
    assert (
        read_behavior_status(str(tmp_path), os.path.join("tests", "detective"), "m.py::f", node) == "unpinned"
    )


def test_purge_spares_the_ledger_it_is_part_of_the_suite_and_spares_user_data(tmp_path) -> None:
    record_certificate(str(tmp_path), "m.py::f", "d1", "complete", "")
    user_data = tmp_path / ".detective" / "inputs.json"
    user_data.parent.mkdir(parents=True, exist_ok=True)
    user_data.write_text("{}", encoding="utf-8")
    (tmp_path / ".detective" / "verdict_cache.json").write_text("{}", encoding="utf-8")
    removed, _ = purge(str(tmp_path))
    assert str(tmp_path / CERTIFICATES_REL_PATH) not in removed
    assert (tmp_path / CERTIFICATES_REL_PATH).exists()
    assert user_data.exists()
    assert any(p.endswith("verdict_cache.json") for p in removed), "the cache is still what purge is for"


# ---------------------------------------------------------------- end to end, through `converge`


def _project(tmp_path: Path) -> Path:
    (tmp_path / "calc.py").write_text(
        textwrap.dedent(
            """
            def add(a, b):
                return a + b
            """
        )
    )
    return tmp_path


def test_converge_records_the_certificate_and_the_reader_sees_it(tmp_path) -> None:
    root = _project(tmp_path)
    result = converge("calc.py", "add", str(root), max_iterations=1)
    node = ast.parse((root / "calc.py").read_text()).body[0]

    assert result.function_digest == pins.function_digest(node)
    entry = load_certificate(str(root), "calc.py::add")
    assert entry is not None
    assert entry["function_digest"] == result.function_digest
    assert entry["standing"] == result.standing  # recorded verbatim, never re-derived
    assert entry["refusal"] == ""

    status = read_behavior_status(str(root), os.path.join("tests", "detective"), "calc.py::add", node)
    expected = {"complete": "pinned", "incomplete": "pinned_incomplete", "unverified": "pinned_incomplete"}
    if result.standing in expected:
        assert status == expected[result.standing]
    else:  # an invalid measurement on this machine is not this test's subject; it must still be honest
        assert status in ("unpinned", "pinned_unverified")
