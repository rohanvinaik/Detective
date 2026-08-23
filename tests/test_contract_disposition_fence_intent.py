"""Q8 intent — the two-sign contract's `fence` disposition must never collapse into `equivalent`.

`is_flagged_equivalent` was verdict-BLIND: ANY flag suppressed a survivor into the equivalent
bucket (`manual_equivalent`). A two-sign `fence` is an authored MUST-NOT (Def. 12.1 `invalid`): its
survival is a BUG — an UNENFORCED negative degree of freedom. Collapsing fence→equivalent silently
marks a must-not as valid — the Def. 9.5 soundness inversion. These tests pin the split from INTENT,
so a re-merge of the two verdicts (which a generated characterization cannot catch when it is
wrong-but-consistent) fails here.

`audit_partition_sums` is pinned by HAND on purpose: it is WIRED into `audit_suite`, so `converge`
cannot isolate it (its covering set inflates to codebase scale — the converge-before-wiring hazard),
and its `total == sum` arithmetic is exhaustively pinnable from intent.
"""

from __future__ import annotations

from Detective.audit import audit_partition_sums
from Detective.engine import classify_survivors, profile
from Detective.equivalents import add_flag, contract_disposition, flag_verdict, load_flags


# ── the pure decision: a fence is NEVER an equivalent ────────────────────────
def test_a_fence_flag_reports_a_fence_never_an_equivalent():
    # A no-witness survivor flagged `fence` reports as a fence (a gap), NEVER as `equivalent`
    # (suppressed/valid). The two codes are distinct — the split is real, not cosmetic.
    assert contract_disposition(True, False, False, "fence") == "fence"
    assert contract_disposition(True, False, False, "equivalent") == "equivalent"
    assert contract_disposition(True, False, False, "fence") != contract_disposition(
        True, False, False, "equivalent"
    )


def test_proof_outranks_any_flag():
    # A distinguishing witness (killable) outranks BOTH flags — a real kill is proof, not opinion.
    assert contract_disposition(True, True, False, "fence") == "killable"
    assert contract_disposition(True, True, False, "equivalent") == "killable"


def test_an_unbuildable_fence_is_still_a_fence_and_an_unflagged_survivor_is_unclassified():
    # No execution verdict (un-buildable): the authored fence still holds; no flag → unclassified.
    assert contract_disposition(False, False, False, "fence") == "fence"
    assert contract_disposition(False, False, False, "equivalent") == "equivalent"
    assert contract_disposition(False, False, False, "") == "unclassified"


def test_a_blocked_search_is_unclassified_not_a_false_equivalent():
    # A timed-out witness search is honest uncertainty; an unflagged reached survivor is a candidate.
    assert contract_disposition(True, False, True, "") == "unclassified"
    assert contract_disposition(True, False, False, "") == "candidate"


# ── persistence + accessor: the verdict round-trips ──────────────────────────
def test_add_flag_persists_and_flag_verdict_reads_the_recorded_verdict(tmp_path):
    root = str(tmp_path)
    add_flag(root, "m.py::f", "some-diff", verdict="fence")
    add_flag(root, "m.py::g", "other-diff")  # default verdict stays "equivalent"
    flags = load_flags(root)
    assert flag_verdict(flags, "m.py::f", "some-diff") == "fence"
    assert flag_verdict(flags, "m.py::g", "other-diff") == "equivalent"
    assert flag_verdict(flags, "m.py::f", "never-flagged") == ""


# ── the pure arithmetic decision audit_suite gates on (WIRED — hand-pinned) ──
def test_audit_partition_sums_is_exact_and_fence_is_a_load_bearing_term():
    # True exactly when total == the six-way partition. Perturb EACH term by 1 → the sum no longer
    # reconciles, proving every term (including `fence`) is counted; drop `fence` and an authored
    # must-not would fall out of the accounting silently.
    assert audit_partition_sums(10, 3, 2, 1, 1, 1, 2) is True  # 3+2+1+1+1+2 == 10
    assert audit_partition_sums(0, 0, 0, 0, 0, 0, 0) is True
    assert audit_partition_sums(10, 4, 2, 1, 1, 1, 2) is False  # value_killed
    assert audit_partition_sums(10, 3, 3, 1, 1, 1, 2) is False  # killable
    assert audit_partition_sums(10, 3, 2, 2, 1, 1, 2) is False  # candidate_equivalent
    assert audit_partition_sums(10, 3, 2, 1, 2, 1, 2) is False  # manual
    assert audit_partition_sums(10, 3, 2, 1, 1, 2, 2) is False  # fence
    assert audit_partition_sums(10, 3, 2, 1, 1, 1, 3) is False  # unclassified


# ── end-to-end: a fenced survivor lands in authored_fence, never manual_equivalent ──
def _repo_with_value_dead_branch(tmp_path):
    # The condition is value-DEAD (both branches return abs(x)), so its mutants are candidate-
    # equivalent — no input distinguishes them — exactly the survivor a human fences as a must-not.
    (tmp_path / "pyproject.toml").write_text('[tool.pytest.ini_options]\ntestpaths = ["tests"]\n')
    (tmp_path / "m.py").write_text("def f(x):\n    return abs(x) if x < 0 else abs(x)\n")
    tdir = tmp_path / "tests"
    tdir.mkdir()
    (tdir / "test_m.py").write_text(
        "from m import f\n\n\ndef test_f():\n    assert f(-3) == 3\n    assert f(3) == 3\n"
    )
    return str(tmp_path)


def test_a_fenced_survivor_is_reported_never_suppressed_as_equivalent(tmp_path):
    root = _repo_with_value_dead_branch(tmp_path)
    r = profile("m.py", "f", root, use_cache=False)
    diffs = [rec.get("diff_summary", "") for rec in r.value_survivor_records if rec.get("diff_summary")]
    assert diffs, "the value-dead branch must leave at least one value-survivor to fence"
    for d in diffs:
        add_flag(root, r.function_key, d, verdict="fence")
    report = classify_survivors("m.py", "f", root, profile_result=r)
    # THE INVERSION, closed: not one fenced survivor is suppressed into the equivalent bucket.
    assert not report.manual_equivalent
    # The non-killable fences are REPORTED as unenforced must-nots, never silently dropped.
    assert report.authored_fence


def test_an_equivalent_flag_still_suppresses_into_manual_equivalent(tmp_path):
    # The other verdict is unchanged and symmetric: an `equivalent` flag routes to manual_equivalent
    # and NEVER to authored_fence — the split is not a fence-only special case.
    root = _repo_with_value_dead_branch(tmp_path)
    r = profile("m.py", "f", root, use_cache=False)
    diffs = [rec.get("diff_summary", "") for rec in r.value_survivor_records if rec.get("diff_summary")]
    for d in diffs:
        add_flag(root, r.function_key, d, verdict="equivalent")
    report = classify_survivors("m.py", "f", root, profile_result=r)
    assert not report.authored_fence
    assert report.manual_equivalent
