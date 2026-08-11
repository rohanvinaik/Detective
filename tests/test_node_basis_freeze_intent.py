"""verify-rewrite freezes on the runner's node-ID basis, at node granularity (issue #58).

The #37 freeze gate stores each proof FILE's content digest, but the file set it freezes is
`proof_suite` = the kill-matrix-covering files — which OMITS a test that owns only a line or arc
obligation. #58 additionally freezes the runner's OWN node-ID basis (every collected item as
`(node_id, content digest)`, from the final verification's real collection), so a rewrite that edits
such a line/arc-only owner — invisible to the file gate — is still caught by test IDENTITY.

`basis_freshness` is the same pinned #37 decision (a dict of key→digest → unfrozen/moved/fresh); it
is generic over the key, so node IDs reuse it exactly. `_node_file_digest` recomputes a frozen node's
current file digest the SAME way Wesker captured it (realpath + a 16-char sha256 of content), so the
comparison is normalization-consistent and cannot drift into a false verdict.
"""

from __future__ import annotations

from Detective.rewrite import _node_file_digest, basis_freshness


def test_an_intact_node_basis_is_fresh(tmp_path):
    """The stable case: the target was rewritten but the proof tests were not, so every frozen node's
    file still hashes to what the receipt froze — the basis is intact and preservation may proceed."""
    (tmp_path / "t_line_owner.py").write_text("def test_x():\n    assert True\n")
    root = str(tmp_path)
    nid = "t_line_owner.py::test_x"
    frozen = {nid: _node_file_digest(root, nid)}
    assert frozen[nid], "a readable proof file must produce a non-empty digest"
    assert basis_freshness(frozen, {nid: _node_file_digest(root, nid)}) == "fresh"


def test_an_edited_proof_test_file_is_moved_by_identity(tmp_path):
    """THE defect this closes: a proof test that owns only a line/arc obligation is absent from the
    file-level `proof_digests`, so editing it slips the #37 gate. Frozen by node identity, the change
    to its file is caught — `moved`, and verify-rewrite refuses PRESERVED against a basis that shifted."""
    p = tmp_path / "t_line_owner.py"
    p.write_text("def test_x():\n    assert True\n")
    root = str(tmp_path)
    nid = "t_line_owner.py::test_x"
    frozen = {nid: _node_file_digest(root, nid)}
    p.write_text("def test_x():\n    assert True  # edited after the receipt\n")
    assert basis_freshness(frozen, {nid: _node_file_digest(root, nid)}) == "moved"


def test_a_deleted_proof_test_file_is_moved_not_silently_fresh(tmp_path):
    """A gone owner must READ as moved, never vanish into `fresh`. `_node_file_digest` returns "" for
    an unreadable file, which matches no frozen digest — the same convention the file gate uses."""
    p = tmp_path / "t_line_owner.py"
    p.write_text("def test_x():\n    assert True\n")
    root = str(tmp_path)
    nid = "t_line_owner.py::test_x"
    frozen = {nid: _node_file_digest(root, nid)}
    p.unlink()
    assert _node_file_digest(root, nid) == ""
    assert basis_freshness(frozen, {nid: _node_file_digest(root, nid)}) == "moved"


def test_a_pre_58_receipt_with_no_node_basis_reads_as_unfrozen(tmp_path):
    """An empty node basis (a receipt taken before #58, or a run with no green verification to collect
    under) is a MISSING capability, not a detected move — named `unfrozen`, and the file gate stands."""
    assert basis_freshness({}, {"whatever.py::t": "x"}) == "unfrozen"
