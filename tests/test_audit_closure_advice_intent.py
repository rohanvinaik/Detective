"""Audit D/E/F: advisory uncertainty is not a reachability or preservation proof.

The regression cases come from audit findings 3–11 and the ledger's impossible
line-input route. They assert intended boundaries independently of generated pins.
"""

import json
from types import SimpleNamespace

import pytest

from Detective.cli import _derive_input_plan, _derived_input, main, residual_input_route
from Detective.engine import _load_failure_reason
from Detective.extract import extract_proposal, extraction_target_status, render_extract
from Detective.mcp_server import _ask_for_input
from Detective.rewrite import rewrite_classification_status
from Detective.survey import survey_scan_status, survey_source


@pytest.mark.parametrize(
    "expressible,gaps,expected",
    [
        (True, True, "lines"),
        (True, False, "author"),
        (False, True, "fixture"),
        (False, False, "fixture"),
    ],
)
def test_residual_input_route_respects_the_literal_boundary(expressible, gaps, expected):
    assert residual_input_route(expressible, gaps) == expected


def test_both_surfaces_keep_inexpressible_line_gaps_out_of_input_commands():
    proof = SimpleNamespace(
        param_names=("grid",),
        signature="f(grid)",
        inputs_expressible=False,
        missing_lines=(8,),
        missing_line_guards=((8, "grid.shape[0] > 0"),),
    )
    assert _derive_input_plan(proof, None).kind == "fixture"
    cli = "\n".join(_derived_input(None, proof, None, "m.py::f"))
    mcp = "\n".join(_ask_for_input("converge", "m.py", "f", ("grid",), "gap", proof=proof))
    for output in (cli, mcp):
        assert "WRITE TEST" in output and "line 8" in output
        assert "--input" not in output and "inputs=[" not in output


@pytest.mark.parametrize(
    "present,failed,valid,expected",
    [
        (False, False, False, "unavailable"),
        (True, True, True, "load_failed"),
        (True, False, False, "invalid_measurement"),
        (True, False, True, "observed"),
    ],
)
def test_rewrite_classification_requires_measured_evidence(present, failed, valid, expected):
    assert rewrite_classification_status(present, failed, valid) == expected


def test_import_diagnostic_reports_the_dependency_after_a_postponed_dataclass(tmp_path):
    import sys

    target = tmp_path / "missing_dep.py"
    target.write_text(
        "from __future__ import annotations\nfrom dataclasses import dataclass\n"
        "@dataclass\nclass Box:\n    x: int\nimport closure_nonexistent_dependency\n"
    )
    prior = sys.modules.get("_detective_probe")
    reason = _load_failure_reason(str(target), "f")
    assert reason == "ModuleNotFoundError: No module named 'closure_nonexistent_dependency'"
    assert sys.modules.get("_detective_probe") is prior


@pytest.mark.parametrize("count,expected", [(0, "missing"), (1, "resolved"), (2, "ambiguous")])
def test_extraction_target_must_resolve_once(count, expected):
    assert extraction_target_status(count) == expected


def test_exact_qualified_target_keeps_its_own_body_and_scalar_inputs():
    source = (
        "class A:\n    def decide(self, grid: ndarray):\n        a = len(grid)\n        return a\n"
        "class B:\n    def decide(self, grid: ndarray, k: int):\n"
        "        n = len(grid)\n        return n + k\n"
    )
    proposal = extract_proposal(source, "B.decide")
    assert proposal.qualname == "B.decide"
    assert proposal.primitive_inputs == ("k", "n")
    assert proposal.unresolved_inputs == ()
    with pytest.raises(LookupError, match="ambiguous"):
        extract_proposal(source, "decide")
    with pytest.raises(LookupError, match="missing"):
        extract_proposal(source, "Missing.decide")


@pytest.mark.parametrize("projection", ["grid[:]", "grid.copy()", "grid[0, 0]", "helper(grid)"])
def test_unknown_projection_does_not_become_a_primitive_signature(projection):
    source = f"def f(grid: ndarray, k: int):\n    n = {projection}\n    return n + k\n"
    proposal = extract_proposal(source, "f")
    assert proposal.primitive_inputs == ("k",)
    assert "n" in proposal.unresolved_inputs
    assert "def f_decision(" not in "\n".join(render_extract("m.py", proposal))


def test_reassignment_and_shadowing_invalidate_primitive_projection_evidence():
    for source in (
        "def f(grid: ndarray):\n    n = len(grid)\n    n = grid.copy()\n    return n\n",
        "def len(x):\n    return x\ndef f(grid: ndarray):\n    n = len(grid)\n    return n\n",
    ):
        proposal = extract_proposal(source, "f")
        assert "n" not in proposal.primitive_inputs
        assert "n" in proposal.unresolved_inputs


def test_tensor_annotation_is_not_a_heavy_library_body_use():
    findings = survey_source("import torch\ndef f(x: torch.Tensor):\n    return len(x) > 0\n")
    assert [(f.qualname, f.disposition) for f in findings] == [("f", "extractable_core")]


@pytest.mark.parametrize(
    "scanned,failed,expected", [(1, 0, "observed"), (0, 0, "empty"), (1, 1, "incomplete")]
)
def test_survey_status_preserves_omissions(scanned, failed, expected):
    assert survey_scan_status(scanned, failed) == expected


def test_survey_resolves_requested_root_and_reports_parse_failures(tmp_path, capsys):
    (tmp_path / "module.py").write_text("def f(x: Alien):\n    return x\n")
    assert main(["survey", "module.py", "--project-root", str(tmp_path), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["scan_status"] == "observed" and report["files"]
    (tmp_path / "module.py").write_text("def broken(")
    assert main(["survey", "module.py", "--project-root", str(tmp_path), "--json"]) == 2
    report = json.loads(capsys.readouterr().out)
    assert report["scan_status"] == "incomplete" and report["unexamined"]


def test_missing_extraction_target_is_a_precondition_error(tmp_path, capsys):
    (tmp_path / "module.py").write_text("def f(x: int):\n    return x\n")
    assert main(["extract", "module.py::absent", "--project-root", str(tmp_path), "--json"]) == 2
    assert "missing function target" in json.loads(capsys.readouterr().out)["error"]
