"""A green line-ONLY owner enters the certificate's proof basis; a failing one never does (#59).

The open half of #59: `_covering_test_files` derived the proof suite from the kill matrix ALONE, so a
test that covers an admissible target line but kills no mutant — a line-only owner — was omitted from
the final verification and the receipt basis. A green line obligation then rested on a test the
certificate never reran. The fix threads the admissible line owners (`ConvergeResult.line_owner_ids`,
gated by `admissible_line_owners`) into `_covering_test_files`, so a line-only owner's file joins the
proof basis — and through #58's verification plugin, the node-ID basis — automatically.

The gate is load-bearing and the reason it returns NAMED codes upstream: on an `observed` basis the
owner map is the raw union keyed by every test INCLUDING the baseline-failing ones #59 exists to
exclude, so only the `admissible` basis may contribute owners. These tests pin both halves from intent,
not from what the code happens to do.
"""

from __future__ import annotations

from Detective.converge import admissible_line_owners
from Detective.decompose_apply import _covering_test_files


def _write_suite(root):
    # test_k defines a KILL owner (in the kill matrix); test_l defines a LINE-only owner (not in it).
    (root / "test_k.py").write_text("def test_k():\n    assert True\n")
    (root / "test_l.py").write_text("def test_l():\n    assert True\n")


def test_a_line_only_owner_file_is_absent_without_the_owner_ids(tmp_path):
    """Baseline: with the kill matrix alone, the line-only owner's file is NOT in the proof basis —
    this is the exact omission #59 names, reproduced so the fix is proven against a live defect."""
    _write_suite(tmp_path)
    km = {"m0": ["test_k.py::test_k"]}
    covering = _covering_test_files(str(tmp_path), km)
    assert covering == ("test_k.py",)
    assert "test_l.py" not in covering


def test_a_line_only_owner_file_enters_the_basis_when_admitted(tmp_path):
    """THE fix: pass the admissible line owner and its file joins the proof basis, so a green
    line-only test is rerun by the final verification even though it killed no mutant."""
    _write_suite(tmp_path)
    km = {"m0": ["test_k.py::test_k"]}
    covering = _covering_test_files(str(tmp_path), km, ("test_l.py::test_l",))
    assert covering == ("test_k.py", "test_l.py")


def test_the_gate_admits_owners_only_on_the_admissible_basis(tmp_path):
    """The gate a caller relies on: `admissible_line_owners` yields owners ONLY on `admissible`.
    On `observed` the map is the raw union carrying baseline-failing owners, so it must yield none —
    and a caller passing that empty result to `_covering_test_files` keeps the line-only file OUT."""
    owners = ["test_l.py::test_l"]
    assert admissible_line_owners(owners, "admissible") == ("test_l.py::test_l",)
    for refusing in ("observed", "none_admissible", "malformed"):
        assert admissible_line_owners(owners, refusing) == ()

    _write_suite(tmp_path)
    km = {"m0": ["test_k.py::test_k"]}
    on_observed = admissible_line_owners(owners, "observed")
    assert _covering_test_files(str(tmp_path), km, on_observed) == ("test_k.py",)


def test_owners_are_deduplicated_and_ordered(tmp_path):
    """A stable proof basis: duplicate owners collapse and the result is ordered, so the frozen
    basis and its #58 node digests do not churn with the map's iteration order."""
    assert admissible_line_owners(["b::t", "a::t", "b::t"], "admissible") == ("a::t", "b::t")
