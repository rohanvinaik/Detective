"""Intent: verify-rewrite replays the basis its receipt was verified on, never files found by name (#114).

THE DEFECT, a consequence of #114 itself. #114 made converge verify the EXACT proof basis (node ids),
so a receipt over a function whose killer shares a file with a test that is not the function's
business — one that fails before it reaches the function (case iv), or another function's failing
test (case v) — now reads ``passed``. verify-rewrite still replayed ``proof_suite``, the FILES found by
a killer's bare name: it re-ran that other test, and a behaviour-PRESERVING rewrite (``x * 2`` ->
``x + x``) came back ``✗ CHANGED``, exit 1 — a false accusation. On main the same receipt read
``tests_failed`` and verify-rewrite abstained (exit 3): honest, if unhelpful.

THE RULING: replay the receipt's node-ID basis (#58) — its verification's real collection, the basis
its ``passed`` was established on — and fall back to the proof files only for a receipt that froze no
node basis. ``proof_suite`` stays file-level as the freeze gate, where freezing more is conservative.
The replay must still catch a real change, and a receipt over a failing floor must never ground
PRESERVED.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap

import pytest

from Detective.rewrite import replay_selection


@pytest.mark.parametrize(
    ("node_ids", "proof_suite", "selection"),
    [
        (["tests/test_m.py::test_doubles"], ["tests/test_m.py"], "nodes"),
        (["tests/test_m.py::test_doubles"], [], "nodes"),
        ([], ["tests/test_m.py"], "files"),  # a pre-#58 receipt: the file replay it always had
        ([], [], "none"),
    ],
)
def test_the_replay_is_the_frozen_node_basis_whenever_there_is_one(node_ids, proof_suite, selection):
    assert replay_selection(node_ids, proof_suite) == selection


# ------------------------------------------------------------------ receipt -> rewrite -> verify, real CLI

DOUBLES = """

    def test_doubles():
        assert scale(2) == 4
        assert scale(3) == 6
"""
CASES = {
    # (iv) a test in the killer's file fails before it ever reaches the function
    "iv": (
        "def scale(x):\n    return x * 2\n",
        "    from m import scale\n"
        + DOUBLES
        + """

    def test_before_reach():
        assert 1 == 2, "fails before the call"
        scale(1)
""",
    ),
    # (v) another function's failing test shares the killer's file
    "v": (
        "def scale(x):\n    return x * 2\n\n\ndef other():\n    return 1\n",
        "    from m import other, scale\n"
        + DOUBLES
        + """

    def test_other_broken():
        assert other() == 2
""",
    ),
    # (vii) the killer pins every mutant, but a test of the function itself fails: a failing floor
    "vii": (
        "def scale(x):\n    return x * 2\n",
        "    from m import scale\n"
        + DOUBLES
        + """

    def test_wrong():
        assert scale(1) == 3
""",
    ),
}


def _project(tmp_path, case: str):
    module, tests = CASES[case]
    project = tmp_path / "proj"
    (project / "tests").mkdir(parents=True)
    (project / "m.py").write_text(module)
    (project / "tests" / "test_m.py").write_text(textwrap.dedent(tests))
    return project


def _cli(project, *args: str) -> subprocess.CompletedProcess:
    script = os.path.join(os.path.dirname(sys.executable), "detective")
    assert os.path.isfile(script), f"the installed console script is required beside {sys.executable}"
    return subprocess.run(
        [script, *args, "--project-root", str(project)],
        cwd=str(project),
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )


def _receipt_then_verify(project, rewritten: str) -> tuple[dict, subprocess.CompletedProcess]:
    receipt_path = project / "receipt.json"
    receipt = _cli(project, "receipt", "m.py::scale", "-o", str(receipt_path))
    module = project / "m.py"
    module.write_text(module.read_text().replace("return x * 2", rewritten))
    verify = _cli(project, "verify-rewrite", str(receipt_path), "m.py::scale", "--json")
    rec = json.loads(receipt_path.read_text())
    rec["_exit"] = receipt.returncode
    return rec, verify


@pytest.mark.parametrize("case", ["iv", "v"])
def test_a_preserving_rewrite_is_preserved_when_a_neighbour_test_fails(tmp_path, case):
    project = _project(tmp_path, case)
    rec, verify = _receipt_then_verify(project, "return x + x")
    assert rec["proof_status"] == "passed" and rec["_exit"] == 0, rec
    assert rec["node_basis"] and [n for n, _d in rec["node_basis"]] == ["tests/test_m.py::test_doubles"], rec
    out = json.loads(verify.stdout)
    assert out["verdict"] == "PRESERVED" and verify.returncode == 0, verify.stdout + verify.stderr


def test_the_exact_replay_still_catches_a_real_change(tmp_path):
    project = _project(tmp_path, "v")
    _rec, verify = _receipt_then_verify(project, "return x * 3")
    out = json.loads(verify.stdout)
    assert out["verdict"] == "CHANGED" and verify.returncode == 1, verify.stdout + verify.stderr
    assert out["proof_replayed"] == "tests_failed", out


def test_a_receipt_over_a_failing_floor_never_grounds_preserved(tmp_path):
    project = _project(tmp_path, "vii")
    rec, verify = _receipt_then_verify(project, "return x + x")
    assert rec["proof_status"] == "floor_failing" and rec["_exit"] == 3, rec
    out = json.loads(verify.stdout)
    assert out["verdict"] != "PRESERVED" and verify.returncode != 0, verify.stdout + verify.stderr
    # The abstention names its cause on every channel (#114, COMMUNICATING_DETERMINISM §3): re-running
    # cannot repair a failing floor, so it must not share a sign with the ABSTAIN that says "re-run".
    assert out["verdict"] == "ABSTAIN" and out["reason"] == "receipt_floor_failing", out
    page = _cli(project, "verify-rewrite", str(project / "receipt.json"), "m.py::scale")
    assert "NO BASELINE" in page.stdout and "Re-running will not change" in page.stdout, page.stdout
    assert "review by hand" not in page.stdout, page.stdout
    assert page.returncode == verify.returncode, "the page and --json report one exit"
