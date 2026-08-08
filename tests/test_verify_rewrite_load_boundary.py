"""`verify-rewrite` must refuse a bad receipt in its own vocabulary (issue #57).

Commit 97e2a569 added an `INVALID_RECEIPT` verdict and correctly refuses an in-memory receipt
whose schema, digest or target identity is wrong. The LOAD boundary did not preserve that
contract: `RewriteReceipt.from_json` raises on unknown schema or stale digest, `json.loads`
raises on garbage, and `open` raises on an unreadable path — none of which the CLI caught. So a
corrupt or foreign receipt escaped as a Python traceback, and under `--json` stdout carried
NOTHING, leaving a caller with no refusal to consume at all.

A refusal is an outcome. Every ending of this command has to be one of the named ones, on both
surfaces, with a non-zero exit — which is what these pin.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from Detective.cli import main
from Detective.rewrite import _RECEIPT_SCHEMA


def _write(tmp_path, text: str):
    path = tmp_path / "receipt.json"
    path.write_text(text, encoding="utf-8")
    (tmp_path / "a.py").write_text("def a(n):\n    return n + 1\n", encoding="utf-8")
    return path


def _run(tmp_path, receipt_path, *, as_json: bool):
    argv = [
        "verify-rewrite",
        str(receipt_path),
        "a.py::a",
        "--project-root",
        str(tmp_path),
    ]
    if as_json:
        argv.append("--json")
    return main(argv)


_CASES = {
    "malformed_json": "this is not json {",
    "not_an_object": "[1, 2, 3]",
    "missing_schema": "{}",
    "unknown_schema": json.dumps({"schema": "some-other-tool/v9"}),
    "digest_mismatch": json.dumps(
        {
            "schema": _RECEIPT_SCHEMA,
            "original_source": "def a(n):\n    return n + 1\n",
            "source_digest": "0" * 64,
        }
    ),
}


@pytest.mark.parametrize("expected_reason,text", sorted(_CASES.items()))
def test_a_bad_receipt_is_typed_json_not_a_traceback(tmp_path, capsys, expected_reason, text):
    """The `--json` contract: exactly one JSON object on stdout, carrying the verdict AND a
    machine-readable reason. Previously stdout was empty and the exception escaped."""
    code = _run(tmp_path, _write(tmp_path, text), as_json=True)
    out = capsys.readouterr().out
    payload = json.loads(out)  # raises if stdout is empty or not one object
    assert payload["verdict"] == "INVALID_RECEIPT"
    assert expected_reason in payload["note"]
    assert code != 0


@pytest.mark.parametrize("expected_reason,text", sorted(_CASES.items()))
def test_the_human_surface_refuses_with_the_same_reason(tmp_path, capsys, expected_reason, text):
    """Both surfaces must agree. A refusal a human sees and a caller cannot parse — or the
    reverse — is the channel split this issue is about."""
    code = _run(tmp_path, _write(tmp_path, text), as_json=False)
    out = capsys.readouterr().out
    assert "INVALID_RECEIPT" in out
    assert "Traceback" not in out
    assert code != 0


def test_an_unreadable_receipt_is_also_typed(tmp_path, capsys):
    """`open` raises before any parsing can happen, so this path could never have been covered
    by a JSON-level check — it needs the boundary to start at the file, not the text."""
    (tmp_path / "a.py").write_text("def a(n):\n    return n + 1\n", encoding="utf-8")
    code = _run(tmp_path, tmp_path / "no_such_receipt.json", as_json=True)
    payload = json.loads(capsys.readouterr().out)
    assert payload["verdict"] == "INVALID_RECEIPT"
    assert "unreadable_receipt" in payload["note"]
    assert code != 0


def test_a_well_formed_receipt_still_loads(tmp_path, capsys):
    """The control. A boundary that refused everything would satisfy every test above while
    destroying the command — this is the one input that must get PAST the load gate."""
    src = "def a(n):\n    return n + 1\n"
    text = json.dumps(
        {
            "schema": _RECEIPT_SCHEMA,
            "function": "a.py::a",
            "original_source": src,
            "source_digest": hashlib.sha256(src.encode("utf-8")).hexdigest(),
        }
    )
    _run(tmp_path, _write(tmp_path, text), as_json=True)
    payload = json.loads(capsys.readouterr().out)
    # It may well refuse for a LATER reason (an incomplete baseline abstains); what it must not
    # do is refuse at the LOAD boundary, which is the only thing under test here.
    assert "malformed_json" not in payload.get("note", "")
    assert "unknown_schema" not in payload.get("note", "")
    assert "digest_mismatch" not in payload.get("note", "")
