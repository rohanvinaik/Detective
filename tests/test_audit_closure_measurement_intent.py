"""Audit findings 1–2 / ledger B / #60: a verification refusal is absorbing.

Fresh isolated observation must replace replayed shared-state evidence. A failed,
cut, cached or differently identified verification never supports COMPLETE.
"""

import json
import subprocess
import sys

import pytest

from Detective.converge import verification_disposition


@pytest.mark.parametrize(
    ("valid", "cached", "known", "equal", "survivors", "universe", "expected"),
    [
        (True, False, True, True, True, True, "reproducible"),
        (False, False, True, True, True, True, "invalid_verification"),
        (True, True, True, True, True, True, "cached_verification"),
        (True, False, False, True, True, True, "unknown_verification_basis"),
        (True, False, True, False, True, True, "verification_basis_changed"),
        (True, False, True, True, False, True, "nonreproducible"),
        (True, False, True, True, True, False, "verification_universe_changed"),
    ],
)
def test_verification_requires_positive_evidence(valid, cached, known, equal, survivors, universe, expected):
    assert verification_disposition(valid, cached, known, equal, survivors, universe) == expected


@pytest.mark.parametrize(
    "fault", ["none", "budget", "collection", "cached", "identity", "exception", "universe"]
)
def test_cli_preserves_the_verification_result(tmp_path, fault):
    name = f"closure_{fault}"
    (tmp_path / f"{name}.py").write_text("def f(x: int) -> int:\n    return x + 0\n")
    (tmp_path / f"test_{name}.py").write_text(
        f"from {name} import f\ndef test_f():\n    assert f(1) == 1\n    assert f(-1) == -1\n"
    )
    (tmp_path / "pyproject.toml").write_text('[tool.pytest.ini_options]\npythonpath=["."]\n')
    script = r"""
import contextlib, importlib, io, json, sys
from Detective.cli import main
fault, root, name = sys.argv[1:]
module = importlib.import_module("Detective.converge")
real = module.profile
observations = []
def observe(*args, **kwargs):
    result = real(*args, **kwargs)
    if kwargs.get("isolated"):
        observations.append([kwargs.get("use_cache"), result.execution_mode])
        if fault == "exception":
            raise RuntimeError("verification unavailable")
        if fault == "budget":
            result.budget_exhausted = True
        elif fault == "collection":
            result.collection_errors = ("unavailable_test.py",)
        elif fault == "cached":
            result.served_from_cache = True
        elif fault == "identity":
            result.measurement_basis = "different"
        elif fault == "universe":
            assert result.killed_records
            result.killed_records = []
    return result
module.profile = observe
output = io.StringIO()
with contextlib.redirect_stdout(output):
    code = main(["converge", name + ".py::f", "--project-root", root, "--json", "--deadline", "30"])
print(json.dumps({"code": code, "observations": observations, "result": json.loads(output.getvalue())}))
"""
    run = subprocess.run(
        [sys.executable, "-c", script, fault, str(tmp_path), name],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    payload = json.loads(run.stdout)
    code, observations, result = payload["code"], payload["observations"], payload["result"]
    assert observations == [[False, "isolated"]]
    if fault == "none":
        assert code == 0
        assert result["functionally_complete"] is True
        assert result["validity"]["execution_mode"] == "isolated"
    else:
        assert code == 3
        assert result["functionally_complete"] is False
        assert result["cut_reasons"]
        assert result["verification"] is None
        if fault == "budget":
            assert result["budget_exhausted"] is True
        if fault == "collection":
            assert "collection_incomplete" in result["cut_reasons"]
