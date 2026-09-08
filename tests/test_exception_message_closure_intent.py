"""Pabkit ledger exception-message lead: preserve the message in a multi-test proof basis.

The external checkout is unavailable. This reconstructs the reported helper/message
mechanism and checks the actual CLI, including a second pass after its generated trim.
"""

import json
import subprocess
import sys


def test_shared_guard_message_is_pinned_through_convergence_and_minimization(tmp_path):
    (tmp_path / "message_leaf.py").write_text(
        "def _require_same_length(a, b, pair):\n"
        "    if len(a) != len(b):\n"
        "        raise ValueError(f'{pair} must be the same length')\n"
        "def metric(a: list, b: list):\n"
        "    _require_same_length(a, b, 'train and test loss trajectories')\n"
        "    return len(a) + len(b)\n"
    )
    (tmp_path / "test_message_leaf.py").write_text(
        "import pytest\nfrom message_leaf import metric\n"
        "def test_equal():\n    assert metric([.5], [.6]) == 2\n"
        "def test_duplicate():\n    assert metric([.5], [.6]) == 2\n"
        "def test_empty():\n    assert metric([], []) == 0\n"
        "def test_message():\n"
        "    with pytest.raises(ValueError, "
        "match='^train and test loss trajectories must be the same length$'):\n"
        "        metric([.5, .4], [.6])\n"
    )
    (tmp_path / "pyproject.toml").write_text('[tool.pytest.ini_options]\npythonpath=["."]\n')
    for _ in range(2):
        run = subprocess.run(
            [
                sys.executable,
                "-m",
                "Detective",
                "converge",
                "message_leaf.py::metric",
                "--project-root",
                str(tmp_path),
                "--isolated",
                "--json",
                "--deadline",
                "35",
                "--input",
                "([.5, .4], [.6])",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert run.stdout, run.stderr
        report = json.loads(run.stdout)
        assert run.returncode == 0, report
        assert report["functionally_complete"], report
    verify = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert verify.returncode == 0, verify.stdout + verify.stderr
