"""Integration test for #66 (Detective side): a collection ERROR refuses; an empty suite measures.

When a conftest/config fails to LOAD (a missing dependency), tests EXIST but cannot be collected.
Measuring against the zero tests that survived that failure and printing "0 pinned · converge from
scratch" sends a user whose real problem is a missing install off to author a suite. Detective must
REFUSE (exit 2, nothing measured). A genuinely test-less function (empty_collection) is different —
converge-from-scratch is legitimate — so it must still measure.
"""

from __future__ import annotations

from Detective.cli import main


def test_audit_refuses_when_a_conftest_import_failure_blocks_collection(tmp_path, capsys):
    (tmp_path / "m.py").write_text("def f(x):\n    return x + 1\n")
    # a conftest that cannot import -> collection dies before any test is collected
    (tmp_path / "conftest.py").write_text("import a_module_that_surely_does_not_exist_xyz\n")
    (tmp_path / "test_m.py").write_text("from m import f\n\n\ndef test_f():\n    assert f(1) == 2\n")

    code = main(["audit", "m.py::f", "--project-root", str(tmp_path)])
    out = capsys.readouterr()
    combined = out.out + out.err

    assert code == 2  # refused, non-zero for CI/scripts
    assert "REFUSED" in combined
    # the real cause is named, not "check your testpaths"
    assert "ModuleNotFoundError" in combined or "collection failed" in combined
    # and NO hollow "0 test(s)" measurement / "converge from scratch" is presented
    assert "0 test(s)" not in out.out


def test_audit_still_measures_a_function_with_no_tests(tmp_path, capsys):
    # empty_collection (no test at all) is NOT a collection error; it must fall through and measure.
    (tmp_path / "m.py").write_text("def f(x):\n    if x > 0:\n        return 1\n    return 0\n")

    code = main(["audit", "m.py::f", "--project-root", str(tmp_path)])
    out = capsys.readouterr()

    assert code != 2
    assert "REFUSED" not in (out.out + out.err)
    assert "— audit ·" in out.out  # a real measurement was produced
