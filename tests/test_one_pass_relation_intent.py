"""The per-test kill relation is a product of the profile the audit already runs, not a profile per test
(#145, second part).

THE DEFECT (measured 2026-11-11, cold). The first fix of #145 made the redundant set and the cover a function
of the full kill relation, and bought the relation by profiling the function once per test, each test alone:
`audit 'src/calc.py::f'` went 0.93 s -> 3.6 s, and `audit 'Detective/suite_edit.py::nodeid_parts'` (18 tests,
45 mutants) 27.0 s -> 109.2 s. It did so because Wesker's full-matrix switch did not reach the path Detective
profiles through. It now does (`run_function_profiling(full_matrix=True)`, Wesker, both execution modes), and
`engine.profile(full_matrix=True)` passes it on.

THE RULING. One derivation of one fact: the relation is what the engine measured in the profile whose
verdict the cover, the redundant set, the per-test discharge, `--remove`'s need and converge's redundancy drop
rest on. Where the profile has none the state is NAMED and no cover is claimed, never a fall-back to the
first-killer credit: no relation asked for, an engine too old to offer the mode, a scan the engine itself
calls partial. The same fact names the tests of a proof basis (every killer, not the one the run order
credited) and the test a page says detects a mutant (one name, `legacy:` namespace stripped, whichever
surface prints it).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from Detective import engine as engine_mod
from Detective.audit import _removal_needs, kill_relation_of
from Detective.decompose_apply import exact_proof_basis
from Detective.engine import _detecting_test, result_killers
from Detective.minimize import detecting_test_name, display_test_id, known_killers
from Detective.verdict_cache import cache_key


def test_the_per_test_reprofiling_path_is_gone():
    from Detective import audit, converge

    for name in ("measure_per_test_kills", "_baseline_of_one", "PerTestKills", "assemble_kill_relation"):
        assert not hasattr(audit, name), name
    assert not hasattr(converge, "kill_relation_for")
    assert not hasattr(audit, "measure_kill_relation")


# --- the pure decisions ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("test_id", "shown"),
    [
        ("legacy:tests/t.py::test_a", "tests/t.py::test_a"),
        ("tests/t.py::test_a[1-x]", "tests/t.py::test_a[1-x]"),
        ("legacy:legacy:t.py::a", "legacy:t.py::a"),  # one namespace, once
        ("", ""),
        ("test_bare", "test_bare"),
    ],
)
def test_a_test_is_shown_without_the_engines_routing_namespace(test_id, shown):
    assert display_test_id(test_id) == shown


def test_the_named_detecting_test_is_the_smallest_displayed_id_of_all_killers_in_any_order():
    killers = ["tests/t.py::test_b", "legacy:tests/t.py::test_a", "tests/t.py::test_c"]
    assert detecting_test_name(killers) == "tests/t.py::test_a"
    assert detecting_test_name(list(reversed(killers))) == "tests/t.py::test_a"
    # one test spelled both ways is one test
    assert detecting_test_name(["legacy:t.py::a", "t.py::a"]) == "t.py::a"
    assert detecting_test_name([]) == "" and detecting_test_name([""]) == ""


def test_known_killers_is_the_union_of_the_credit_and_the_relation_sorted():
    credit = {"m1": ["t::b"], "m2": ["t::z"]}
    relation = {"m1": ["t::a", "t::b"], "m3": ["t::c"]}
    assert known_killers(credit, relation) == {"m1": ["t::a", "t::b"], "m2": ["t::z"], "m3": ["t::c"]}
    assert known_killers(credit, {}) == {"m1": ["t::b"], "m2": ["t::z"]}  # a lower bound, named as such
    assert known_killers({}, {}) == {}
    # no order anywhere
    assert known_killers({"m": ["t::b", "t::a"]}, {}) == known_killers({"m": ["t::a", "t::b"]}, {})


def test_a_whole_relation_contains_the_credit_so_the_union_is_the_relation():
    relation = {"m": ["t::a", "t::b"]}
    for credit in ({"m": ["t::a"]}, {"m": ["t::b"]}):
        assert known_killers(credit, relation) == relation


# --- what reads the relation -----------------------------------------------------------------------------


def _profile_double(credit, rows=None, standing=None):
    fields = {"kill_matrix": credit}
    if rows is not None:
        fields["kill_relation"] = rows
    if standing is not None:
        fields["kill_relation_standing"] = standing
    return SimpleNamespace(**fields)


def test_result_killers_reads_the_relation_where_the_engine_measured_one():
    result = _profile_double({"m": ["t::b"]}, {"m": {"t::a": "assertion", "t::b": "crash"}}, "complete")
    assert result_killers(result) == {"m": ["t::a", "t::b"]}
    assert result_killers(_profile_double({"m": ["t::b"]})) == {"m": ["t::b"]}  # an engine without it


def test_a_proof_basis_names_every_killer_not_the_one_the_run_order_credited():
    credit_warm = {"m": ["tests/t.py::test_b"]}
    credit_cold = {"m": ["tests/t.py::test_a"]}
    rows = {"m": {"tests/t.py::test_a": "assertion", "tests/t.py::test_b": "assertion"}}
    a = exact_proof_basis("/r", result_killers(_profile_double(credit_warm, rows, "complete")))
    b = exact_proof_basis("/r", result_killers(_profile_double(credit_cold, rows, "complete")))
    assert a == b == ("tests/t.py::test_a", "tests/t.py::test_b")


def test_two_surfaces_name_one_test_one_way_whatever_spelling_each_profile_used():
    rec = {"mutant": "SWAP_1: x", "mutant_id": "SWAP_1"}
    converge_side = result_killers(_profile_double({"SWAP_1: x": ["legacy:tests/t.py::test_interval"]}))
    flag_side = result_killers(
        _profile_double(
            {"SWAP_1: x": ["tests/t.py::test_other"]},
            {"SWAP_1: x": {"tests/t.py::test_interval": "crash", "tests/t.py::test_other": "crash"}},
            "complete",
        )
    )
    assert (
        _detecting_test(converge_side, rec) == _detecting_test(flag_side, rec) == "tests/t.py::test_interval"
    )
    assert "legacy:" not in _detecting_test(converge_side, rec)


def _real_profile(credit, rows, standing, lines):
    from _support import make_pr

    pr = make_pr(function_key="m.py::g")
    pr.kill_matrix = credit
    pr.line_coverage = lines
    pr.kill_relation = rows
    pr.kill_relation_standing = standing
    return pr


def test_removal_needs_reads_the_relation_the_profile_carries():
    lines = {"tests/t.py::test_pos": [1], "tests/t.py::test_dup": [1]}
    both = {"m": {"tests/t.py::test_pos": "assertion", "tests/t.py::test_dup": "assertion"}}
    credit = {"m": ["tests/t.py::test_pos"]}
    # test_dup kills what test_pos kills and covers what it covers: not needed, whichever was credited
    redundant = _removal_needs(_real_profile(credit, both, "complete", lines), {"tests/t.py::test_dup"}, "/r")
    assert redundant.state == "redundant" and redundant.needed == frozenset()
    # the credit alone would have called the OTHER test the necessary one
    flipped = _real_profile({"m": ["tests/t.py::test_dup"]}, both, "complete", lines)
    assert _removal_needs(flipped, {"tests/t.py::test_dup"}, "/r").state == "redundant"
    # the sole killer of a mutant is needed
    sole = {"m": {"tests/t.py::test_dup": "assertion"}}
    needed = _removal_needs(_real_profile(credit, sole, "complete", lines), {"tests/t.py::test_dup"}, "/r")
    assert needed.state == "needed" and needed.needed == frozenset({"tests/t.py::test_dup"})


@pytest.mark.parametrize("standing", ["not_requested", "scan_incomplete", "run_cut", "row_missing"])
def test_removal_keeps_a_candidate_whose_need_has_no_whole_relation_behind_it(standing):
    lines = {"tests/t.py::test_pos": [1], "tests/t.py::test_dup": [1]}
    both = {"m": {"tests/t.py::test_pos": "assertion", "tests/t.py::test_dup": "assertion"}}
    evidence = _removal_needs(
        _real_profile({"m": ["tests/t.py::test_pos"]}, both, standing, lines), {"tests/t.py::test_dup"}, "/r"
    )
    assert evidence.state == "unverified"
    assert evidence.cut_reasons == ("test_unmeasured" if standing != "not_requested" else "not_requested",)


def test_asking_for_the_relation_changes_the_verdict_cache_key_and_not_asking_leaves_it_alone():
    args = ("f.py::g", "src", [], 0, 0)
    plain = cache_key(*args)
    assert cache_key(*args, full_matrix=False) == plain
    assert cache_key(*args, full_matrix=True) != plain
    # the two coexist in the cache: same field count, different question (see `verdict_cache.put`)
    from Detective.verdict_cache import key_prefix, key_question

    assert cache_key(*args, full_matrix=True).count(":") == plain.count(":")
    prefix = key_prefix("f.py::g")
    assert key_question(cache_key(*args, full_matrix=True), prefix) != key_question(plain, prefix)


def test_the_plain_and_the_relation_bearing_verdict_do_not_evict_each_other(tmp_path):
    """The defect this guards: with a trailing marker field each `put` evicted the other's row, so a
    converge pass 0 and its relation-bearing final measurement (and the next session's) never hit."""
    from Wesker.engine import ProfilingResult

    from Detective import verdict_cache

    args = ("f.py::g", "src", [], 0, 0)
    plain, asked = cache_key(*args), cache_key(*args, full_matrix=True)
    prefix = verdict_cache.key_prefix("f.py::g")
    verdict_cache.put(str(tmp_path), plain, prefix, ProfilingResult(function_key="f.py::g"))
    verdict_cache.put(str(tmp_path), asked, prefix, ProfilingResult(function_key="f.py::g"))
    assert verdict_cache.get(str(tmp_path), plain) is not None
    assert verdict_cache.get(str(tmp_path), asked) is not None


def test_an_engine_that_cannot_offer_the_mode_is_a_named_standing_not_a_first_killer_fallback(monkeypatch):
    monkeypatch.setattr(engine_mod, "_WESKER_FULL_MATRIX", False)
    result = _profile_double({"m": ["t::a"]}, {}, "absent")
    relation = kill_relation_of(result, True)
    assert relation.standing == "engine_lacks_relation" and relation.matrix == {}


# --- the real thing, on #145's fixture ---------------------------------------------------------------------

_PYPROJECT = '[tool.pytest.ini_options]\npythonpath = ["src"]\ntestpaths = ["tests"]\n'
_CALC = 'def f(x):\n    if x > 0:\n        return "pos"\n    return "nonpos"\n'
_TESTS = (
    "import pytest\nfrom calc import f\n\n\n"
    'def test_pos():\n    assert f(1) == "pos"\n\n\n'
    'def test_nonpos():\n    assert f(0) == "nonpos"\n\n\n'
    'def test_dup():\n    assert f(5) == "pos"\n\n\n'
    '@pytest.mark.parametrize("x", [3, 4])\n'
    'def test_more_pos(x):\n    assert f(x) == "pos"\n'
)
_SCRIPT = """
import json, sys
from Detective import engine
isolated = sys.argv[1] == "isolated"
out = {}
for asked in (False, True):
    r = engine.profile("src/calc.py", "f", ".", use_cache=False, isolated=isolated, full_matrix=asked)
    out[str(asked)] = {
        "relation": getattr(r, "kill_relation", None),
        "standing": getattr(r, "kill_relation_standing", None),
        "credit": r.kill_matrix,
        "killed": sorted((x["mutant_id"], x["killed_by"], x["test"]) for x in r.killed_records),
        "survived": sorted(x["mutant_id"] for x in r.survivor_records),
        "unscored": sorted(x["mutant_id"] for x in r.unscored_records),
        "gateable": r.is_gateable,
    }
print(json.dumps(out))
"""


def _run(cwd: Path, *argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
        env=dict(os.environ),
    )


@pytest.fixture(scope="module")
def measured(tmp_path_factory):
    project = tmp_path_factory.mktemp("onepass") / "proj"
    (project / "src").mkdir(parents=True)
    (project / "tests").mkdir()
    (project / "pyproject.toml").write_text(_PYPROJECT)
    (project / "src" / "calc.py").write_text(_CALC)
    (project / "tests" / "test_calc.py").write_text(_TESTS)
    assert (
        _run(project, "-m", "Detective", "regime", "--migrate", "--project-root", str(project)).returncode
        == 0
    )
    (project / "run.py").write_text(_SCRIPT)
    out = {}
    for mode in ("in_process", "isolated"):
        done = _run(project, "run.py", mode)
        assert done.returncode == 0, done.stdout + done.stderr
        out[mode] = json.loads(done.stdout.strip().splitlines()[-1])
    return out


def test_one_profile_carries_the_relation_in_both_modes_and_the_modes_agree(measured):
    inproc, iso = measured["in_process"]["True"], measured["isolated"]["True"]
    assert inproc["standing"] == iso["standing"] == "complete"
    names = {t.removeprefix("legacy:") for row in inproc["relation"].values() for t in row}
    assert names == {
        f"tests/test_calc.py::{n}"
        for n in ("test_pos", "test_nonpos", "test_dup", "test_more_pos[3]", "test_more_pos[4]")
    }
    assert inproc["relation"] == iso["relation"]


def test_asking_for_the_relation_changes_no_verdict_in_either_mode(measured):
    for mode in ("in_process", "isolated"):
        plain, asked = measured[mode]["False"], measured[mode]["True"]
        for field in ("credit", "killed", "survived", "unscored", "gateable"):
            assert plain[field] == asked[field], (mode, field)
        assert plain["standing"] == "not_requested" and plain["relation"] == {}


def test_the_credit_is_inside_the_relation_which_is_the_point_of_having_both(measured):
    asked = measured["isolated"]["True"]
    for mutant, tests in asked["credit"].items():
        assert set(tests) <= set(asked["relation"][mutant])
    assert any(len(row) > 1 for row in asked["relation"].values())
