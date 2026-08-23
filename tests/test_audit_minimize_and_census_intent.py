"""X6 — audit minimizes on the ADMISSIBLE basis, and the diagnose census stops flattening.

TEST_BASIS §15.4 / §16 X6 (Part V gap ledger, G6 + G7).

G6: audit computed the line GAP from the admissible view but MINIMIZED (redundant / minimal cover)
on the foreign-stripped RAW union, while converge minimized on the admissible one — the two proposed
different "delete this test" sets for the same suite (the #59 drift, one axis over). The fix strips
foreign tests from the ADMISSIBLE ledger, so audit minimizes on exactly the coverage a certificate
may rest on.

G7 / render: the `· test routing` line rendered `N observed-impossible (M observed)`, which reads as
"N impossible, of which M observed" — backwards, since impossible ⊆ observed by construction, and it
flattened an ORTHOGONAL provenance count into the partition. The fix renders the partition as a
partition and `observed` on its own line.
"""

from __future__ import annotations

from types import SimpleNamespace

from _support import make_pr

from Detective import audit as audit_mod
from Detective.audit import audit_suite
from Detective.cli import _format_scope
from Detective.scope import scope_from_profiling


def _fake_profile_result():
    # t_fail covers line 2 in the RAW union but its coverage is INADMISSIBLE (baseline-failing);
    # only t_good's line-1 coverage is admissible.
    return SimpleNamespace(
        function_key="mod.py::f",
        kill_matrix={},  # isolate the line axis — no kills
        executable_lines=[1, 2],
        line_coverage={"t_good": [1], "t_fail": [2]},
        admissible_line_coverage={"t_good": [1]},
        total_mutants=0,
        total_killed=0,
        value_killed=0,
        value_survived=0,
        total_equivalent=0,
        value_survivor_records=[],
        killed_records=[],
        per_category=[],
        universe_size=0,
        failing_tests=["t_fail"],
        trace_truncated=[],
        served_from_cache=False,
    )


def _trivial_report():
    return SimpleNamespace(
        inputs_expressible=True,
        killable=(),
        manual_equivalent=(),
        authored_fence=(),  # Q8: the real SurvivorReport carries this; the double must too
        equivalent=(),
        unclassified=(),
    )


def test_audit_minimize_rests_on_the_admissible_view_not_the_raw_union(monkeypatch, tmp_path):
    monkeypatch.setattr(audit_mod, "profile", lambda *a, **k: _fake_profile_result())
    monkeypatch.setattr(audit_mod, "classify_survivors", lambda *a, **k: _trivial_report())
    a = audit_suite("mod.py", "f", str(tmp_path))
    # t_fail's only coverage (line 2) is inadmissible, so it earns NO slot in the minimal cover;
    # under the old raw-union basis it would have (sole cover of line 2), inflating the minimize and
    # diverging from converge. Only t_good (admissible line 1) is minimal.
    assert a.line_basis == "admissible"
    assert a.minimal_test_count == 1


def test_diagnose_routing_render_separates_the_partition_from_observed():
    pr = make_pr(
        categories=[{"category": "VALUE", "killed": 1, "survived": 0, "assertion": 1}],
        killed_records=[{"category": "VALUE", "killed_by": "assertion", "test": "t"}],
    )
    pr.test_routing = {"candidate": 2, "unknown": 3, "impossible": 0, "observed": 2}
    pr.tests_discovered = 5
    out = _format_scope(scope_from_profiling(pr))
    # The three route buckets render as ONE partition clause.
    assert "2 candidate · 3 unknown · 0 impossible" in out
    # The backwards inline "N observed-impossible (M observed)" is gone.
    assert "observed-impossible" not in out
    # `observed` renders on its own line — an orthogonal provenance fact, not a fourth bucket.
    assert "2 of these routed from an exact prior trace" in out
