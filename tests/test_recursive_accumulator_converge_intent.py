"""Intent: `converge` on a recursive accumulator finishes inside its deadline, and no witness it writes
rests on a mutated input (#108).

THE DEFECT (Detective #108, SquishOS `tools/voice/probe.py::_statuses`): a recursive walk that appends to
an `out` accumulator and returns it. A captured input was a tuple of LIVE references, so every row from
one test call shared one `out` list, each trial grew it, and the original disagreed with itself on the
same row. Nearly every survivor then had a bogus "distinguishing witness", and the witness-writing loop
rendered and re-executed each of them unbounded: 66 minutes at ~16 GiB, past `--deadline 300`.

The repairs (`1ca0202` entry snapshots, `219a062` a private copy per trial, `02d96d2` the writing loop under
the wall, `e5f7c98`/`bf3f87b` the harvest deadline) each have a unit test. What had none was the whole
path: the real CLI, in a fresh project, on this shape. This is that test. It asserts the three things the
issue's acceptance names for `def walk(node, out): out.append(...); ...; return out`:
  * converge finishes inside its deadline, with no cut;
  * no witness it writes rests on a mutated input: an accumulator that already holds the node's own
    contribution is the post-call state of a call, not an entry state;
  * the FINAL line is the one line, and says what `--json` says.
"""

from __future__ import annotations

import ast
import copy
import json
import os
import subprocess
import sys
import time
from pathlib import Path

_TARGET = """\
def walk(node, out):
    if isinstance(node, list):
        for item in node:
            walk(item, out)
        return out
    if isinstance(node, dict):
        for key in sorted(node):
            out.append(key)
            walk(node[key], out)
        return out
    out.append(node)
    return out
"""
_TEST = """\
from m import walk


def test_walk_flattens_nested_structure():
    tree = {"a": [1, {"b": 2}], "c": 3}
    assert walk(tree, []) == ["a", 1, "b", 2, "c", 3]
"""
_DEADLINE = 60


def walk(node, out):  # the target, as the test below judges witnesses against it
    namespace: dict = {}
    exec(_TARGET, namespace)  # noqa: S102 (a fixed literal defined above, never input)
    return namespace["walk"](node, out)


def _detective(cwd: Path, home: Path, *argv: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.pop("PYTHONUNBUFFERED", None)
    env["HOME"] = str(home)
    return subprocess.run(
        [sys.executable, "-m", "Detective", *argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
        env=env,
    )


def _rests_on_a_mutated_input(node, out) -> bool:
    """Whether ``out`` is the POST-call state of a walk over ``node``: it ends with what walking ``node``
    alone contributes. An entry snapshot of a recursive call holds only what came before the node."""
    if not isinstance(out, list):
        return False
    contribution = walk(copy.deepcopy(node), [])
    return bool(contribution) and out[-len(contribution) :] == contribution


def test_converge_on_a_recursive_accumulator_finishes_in_its_deadline_on_entry_state_witnesses(tmp_path):
    project, home = tmp_path / "proj", tmp_path / "home"
    (project / "tests").mkdir(parents=True)
    home.mkdir()
    (project / "m.py").write_text(_TARGET)
    (project / "tests" / "test_m.py").write_text(_TEST)
    (project / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\npythonpath = ['.']\nmarkers = ['detective: generated']\n"
    )
    assert _detective(project, home, "regime", "--migrate", "--project-root", str(project)).returncode == 0

    started = time.monotonic()
    page = _detective(project, home, "converge", "m.py::walk", "--deadline", str(_DEADLINE))
    elapsed = time.monotonic() - started
    assert page.returncode == 0, page.stdout + page.stderr
    assert elapsed < _DEADLINE, f"converge took {elapsed:.1f}s against a {_DEADLINE}s deadline"

    record = json.loads(
        _detective(project, home, "converge", "m.py::walk", "--deadline", str(_DEADLINE), "--json").stdout
    )
    assert record["budget_exhausted"] is False and record["cut_phase"] == "", record["cut_phase"]
    assert record["measurement_gateable"] is True

    # no written witness rests on a mutated input
    written = sorted((project / "tests" / "detective").glob("*_synth.py"))
    assert written, "converge wrote no witness test, so there is nothing to judge"
    judged = 0
    for path in written:
        for call in (n for n in ast.walk(ast.parse(path.read_text())) if isinstance(n, ast.Call)):
            if getattr(call.func, "id", "") != "walk":
                continue
            args = {kw.arg: ast.literal_eval(kw.value) for kw in call.keywords}
            judged += 1
            assert not _rests_on_a_mutated_input(args["node"], args["out"]), (path.name, args)
    assert judged, "no walk(...) call was found in the written tests"
    # …and the same for every witness the search kept in the record
    for verdict in record["survivor_report"]["verdicts"]:
        witness = verdict.get("witness")
        if witness and len(witness["args"]) == 2:
            node, out = witness["args"]
            assert not _rests_on_a_mutated_input(node, out), (verdict["mutant_id"], witness["args"])

    # the FINAL line is one line and says what the record says
    final = [line for line in page.stdout.splitlines() if line.startswith("FINAL ")]
    assert len(final) == 1 and final[0].startswith("FINAL m.py::walk: "), page.stdout
    assert ("✓ COMPLETE" in final[0]) == bool(record["functionally_complete"] and record["line_complete"])
    assert ("Incomplete" in final[0]) == (not record["functionally_complete"] or not record["line_complete"])
