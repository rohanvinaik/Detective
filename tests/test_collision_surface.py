"""A collision refusal reaches BOTH surfaces, never as a traceback (issue #61).

`_write` refuses a destination occupied by a file this target does not own — the guard that
stopped it destroying user tests. The refusal then escaped `main` as a Python traceback, which
is the one shape a caller cannot tell from a crash. It is the opposite of a crash: nothing was
written precisely because the guard worked.

Under `--json` it was worse than ugly. The exception propagated before anything was printed, so
stdout was EMPTY and a programmatic consumer had no refusal to read at all — exactly the channel
split #57 fixed for receipts, in a second place.

`main` already had this shape for bad targets (LookupError / FileNotFoundError / SyntaxError ->
one clean line, no traceback); this joins that boundary rather than inventing a parallel one.
"""

from __future__ import annotations

import json

import pytest

from Detective.certify import GeneratedSuiteCollision
from Detective.cli import main


def _raise_collision(*_a, **_k):
    raise GeneratedSuiteCollision("dest.py is owned by 'other.py::g', not 'a.py::f'")


def test_the_human_surface_gets_one_clean_line(tmp_path, monkeypatch, capsys):
    """A traceback gives a caller nothing to route on. The message names the conflict."""
    monkeypatch.setattr("Detective.cli._run_live", _raise_collision)
    (tmp_path / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")

    with pytest.raises(SystemExit) as excinfo:
        main(["converge", "a.py::f", "--project-root", str(tmp_path)])

    message = str(excinfo.value)
    assert "detective:" in message
    assert "other.py::g" in message
    assert "Traceback" not in message


def test_the_json_surface_carries_a_typed_refusal(tmp_path, monkeypatch, capsys):
    """Previously stdout was empty here — the exception escaped before anything printed."""
    monkeypatch.setattr("Detective.cli._run_live", _raise_collision)
    (tmp_path / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")

    code = main(["converge", "a.py::f", "--project-root", str(tmp_path), "--json"])

    payload = json.loads(capsys.readouterr().out)  # raises if stdout is empty
    assert payload["verdict"] == "REFUSED"
    assert payload["reason"] == "generated_suite_collision"
    assert "other.py::g" in payload["detail"]
    assert code != 0


def test_the_json_surface_does_not_also_raise(tmp_path, monkeypatch):
    """Returning a code rather than raising is what lets the JSON object be the whole output.
    A SystemExit alongside it would put prose on stderr and make the exit path differ between
    channels for the same refusal."""
    monkeypatch.setattr("Detective.cli._run_live", _raise_collision)
    (tmp_path / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")

    assert main(["converge", "a.py::f", "--project-root", str(tmp_path), "--json"]) == 1


def test_an_ordinary_run_is_unaffected(tmp_path, monkeypatch):
    """The control: the new except clause must not swallow or alter a normal exit code."""
    monkeypatch.setattr("Detective.cli._run_live", lambda _a: 0)
    (tmp_path / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")

    assert main(["converge", "a.py::f", "--project-root", str(tmp_path)]) == 0
