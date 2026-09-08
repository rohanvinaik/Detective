"""Ledger Step 3: bounded array synthesis must preserve input identity and trial independence.

Tuple indexing alone is not array evidence. Serialization must preserve the actual
numeric value, dtype and shape, including empty dimensions, without accepting objects.
"""

import ast
import json
import subprocess
import sys

import pytest

from Detective.array_inputs import array_grid, array_source, array_source_disposition
from Detective.equivalence import unwrap


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        ((1, 1, "i", True, True), "render"),
        ((2, 16, "f", True, True), "render"),
        ((1, 0, "b", True, True), "render"),
        ((1, 2, "u", True, True), "render"),
        ((0, 1, "i", True, True), "outside_bound"),
        ((3, 1, "i", True, True), "outside_bound"),
        ((1, -1, "i", True, True), "outside_bound"),
        ((1, 17, "i", True, True), "outside_bound"),
        ((1, 1, "O", True, True), "unsupported_dtype"),
        ((1, 1, "f", False, True), "nonfinite"),
        ((1, 1, "i", True, False), "unsupported_type"),
    ],
)
def test_array_serialization_has_an_explicit_domain(args, expected):
    assert array_source_disposition(*args) == expected


def test_array_roundtrip_and_each_trial_start_from_the_same_input():
    numpy = pytest.importorskip("numpy")
    for value in (numpy.array([[1, 2]], dtype=">i2"), numpy.empty((0, 2)), numpy.array([True])):
        source = array_source(value)
        assert source is not None
        rebuilt = eval(source.expr, {"numpy": numpy})
        assert rebuilt.dtype == value.dtype
        assert rebuilt.shape == value.shape
        numpy.testing.assert_array_equal(rebuilt, value)
        first = unwrap(source)
        first[...] = 0
        numpy.testing.assert_array_equal(unwrap(source), value)
    assert array_source(numpy.array([object()])) is None
    assert array_source(numpy.array([float("inf")])) is None
    assert array_source(numpy.zeros((17,))) is None


def test_only_a_real_numpy_type_binding_establishes_array_candidates():
    numpy = pytest.importorskip("numpy")
    assert array_grid(ast.parse("np.ndarray", mode="eval").body, {"np": numpy})
    assert array_grid(ast.Name(id="Array"), {"Array": numpy.ndarray})
    assert array_grid(ast.Name(id="ndarray"), {"ndarray": dict}) is None
    assert array_grid(None, {"np": numpy}) is None
    assert array_grid(ast.parse("np.ndarray()", mode="eval").body, {"np": numpy}) is None


def test_cli_pins_a_real_array_cell_without_a_literal_array_input(tmp_path):
    pytest.importorskip("numpy")
    (tmp_path / "array_leaf.py").write_text(
        "import numpy as np\ndef cell(grid: np.ndarray, x: int, y: int):\n    return int(grid[x, y]) + 1\n"
    )
    (tmp_path / "pyproject.toml").write_text('[tool.pytest.ini_options]\npythonpath=["."]\n')
    run = subprocess.run(
        [
            sys.executable,
            "-m",
            "Detective",
            "converge",
            "array_leaf.py::cell",
            "--project-root",
            str(tmp_path),
            "--json",
            "--deadline",
            "45",
        ],
        text=True,
        capture_output=True,
        timeout=75,
    )
    assert run.stdout, run.stderr
    report = json.loads(run.stdout)
    assert run.returncode == 0, report
    assert report["functionally_complete"], report
    proof = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert proof.returncode == 0, proof.stdout + proof.stderr
