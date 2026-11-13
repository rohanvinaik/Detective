"""A target inside the engine that measures it is measured isolated, and the page says so (no issue number;
Wesker #28 records the class).

THE DEFECT: `detective converge` measures in-process by default. When the target belongs to a module the
measuring engine itself imports and runs, the mutant is installed into the engine's own code while the
engine is using it, and the measurement is unsound without saying so. Pinning Wesker's
`Wesker/monitoring.py::harness_slowdown` in-process left mutant STATE_d0f81e8c (`return (ratio, 'slower')`
-> `return None`) a survivor whose page asked for an assertion the suite already had; `converge --isolated`
on the same target was `COMPLETE 48/50 killed` with no new test.

`engine_ownership` is the pure decision (a target file against the engine packages' directories);
`profile` consumes it and forces the isolated measurement; the page, `--json` and the decision record carry
the code.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from Detective.engine import engine_owned_notice, engine_ownership

ENGINE = "/site/Wesker"
DETECTIVE = "/site/Detective"


@pytest.mark.parametrize(
    ("target", "dirs", "expected"),
    [
        ("/site/Wesker/monitoring.py", [DETECTIVE, ENGINE], "engine_owned"),
        ("/site/Detective/sub/deep.py", [DETECTIVE, ENGINE], "engine_owned"),
        ("/site/Wesker/../Wesker/x.py", [ENGINE], "engine_owned"),
        ("/site/Wesker/monitoring.py", [ENGINE + "/"], "engine_owned"),
        # a renamed dogfood copy at a different path stays ordinary
        ("/scratch/DetectiveUUT/engine.py", [DETECTIVE, ENGINE], "ordinary"),
        # a sibling whose name merely shares the prefix is not inside the package
        ("/site/Wesker_extra/x.py", [ENGINE], "ordinary"),
        ("/site/Wesker.py", [ENGINE], "ordinary"),
        ("/proj/mod.py", [DETECTIVE, ENGINE], "ordinary"),
        # the directory itself is not a file inside it
        ("/site/Wesker", [ENGINE], "ordinary"),
        # absence is not "ordinary"
        ("", [ENGINE], "unresolved"),
        ("relative/mod.py", [ENGINE], "unresolved"),
        ("/site/Wesker/x.py", [], "unresolved"),
        ("/site/Wesker/x.py", ["", "relative"], "unresolved"),
    ],
)
def test_ownership_table(target, dirs, expected):
    assert engine_ownership(target, dirs) == expected


def test_only_the_engine_owned_code_has_a_notice():
    assert "engine doing the measuring" in engine_owned_notice("engine_owned")
    for code in ("ordinary", "unresolved", ""):
        assert engine_owned_notice(code) == ""


_SCRIPT = r"""
import contextlib, importlib, io, json, os, sys
from Detective.cli import main
mode, root, name, as_json = sys.argv[1:]
engine = importlib.import_module("Detective.engine")
real_run = engine.run_function_profiling
isolated_calls = []
def spy(*args, **kwargs):
    isolated_calls.append(bool(kwargs.get("isolated")))
    return real_run(*args, **kwargs)
engine.run_function_profiling = spy
if mode == "owned":
    engine.target_engine_ownership = lambda full: engine.engine_ownership(
        os.path.realpath(full), [os.path.realpath(root)]
    )
else:
    engine.target_engine_ownership = lambda full: engine.engine_ownership(
        os.path.realpath(full), ["/nonexistent/engine"]
    )
argv = ["converge", name + ".py::f", "--project-root", root, "--deadline", "60"]
if as_json == "1":
    argv.append("--json")
output = io.StringIO()
with contextlib.redirect_stdout(output):
    code = main(argv)
print(json.dumps({"code": code, "isolated_calls": isolated_calls, "out": output.getvalue()}))
"""


def _run(tmp_path, mode, as_json):
    name = f"owned_{mode}_{as_json}"
    (tmp_path / f"{name}.py").write_text("def f(x: int) -> int:\n    return x + 0\n")
    (tmp_path / f"test_{name}.py").write_text(
        f"from {name} import f\ndef test_f():\n    assert f(1) == 1\n    assert f(-1) == -1\n"
    )
    (tmp_path / "pyproject.toml").write_text('[tool.pytest.ini_options]\npythonpath=["."]\n')
    env = {k: v for k, v in os.environ.items() if k != "PYTHONUNBUFFERED"}
    run = subprocess.run(
        [sys.executable, "-c", _SCRIPT, mode, str(tmp_path), name, as_json],
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
        env=env,
    )
    return json.loads(run.stdout)


def test_engine_owned_target_is_measured_isolated_and_says_so(tmp_path):
    payload = _run(tmp_path, "owned", "0")
    assert payload["isolated_calls"] and all(payload["isolated_calls"])
    assert "measured isolated: the target is part of the engine doing the measuring" in payload["out"]


def test_engine_owned_code_rides_json_and_the_decision_record(tmp_path):
    payload = _run(tmp_path, "owned", "1")
    assert all(payload["isolated_calls"])
    body = json.loads(payload["out"])
    assert body["engine_ownership"] == "engine_owned"
    assert body["decision"]["state"]["engine_ownership"] == "engine_owned"
    assert body["validity"]["execution_mode"] == "isolated"


def test_ordinary_target_is_unchanged(tmp_path):
    payload = _run(tmp_path, "ordinary", "0")
    assert "measured isolated" not in payload["out"]
    # the first measurement is the in-process default; only the later reproducibility check is isolated
    assert payload["isolated_calls"][0] is False
    body = json.loads(_run(tmp_path, "ordinary", "1")["out"])
    assert body["engine_ownership"] == "ordinary"
