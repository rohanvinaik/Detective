"""Intent: a mutant with no verdict is a per-mutant fact, never a run-level cut (Detective #80, #126).

The defects, reproduced on 2026-10-25 against D#80's own fixture — a six-line `while` loop with one
test — through `detective converge`:

- Two mutants (`i += 1 -> pass`, `i += 1 -> i += 0`) never terminate on the test's input and reach
  the wall-clock bound. Wesker folded that per-mutant outcome into `coverage_depth="cut"`, so the
  report said both "exhaustive — every operator-universe mutant tested" and "the profile was cut
  before the universe was measured" for one run.
- `classify_survivors` refused EVERY survivor whenever the measurement did not admit a certificate,
  for any reason, so the ten unrelated survivors read "unclassified — the search could not run on
  them" (7/17 pinned, UNGATEABLE), and `audit` agreed.
- `flag` answered an id with no verdict "no surviving mutant", naming nothing.
- `nested_measurement` (Wesker #28's refusal) had no reason of its own and read
  `engine_refused_unspecified`; a nondeterministic baseline, or a disposition this version does not
  know, vanished entirely whenever a per-mutant reason stood beside it.

Intent: a run-level refusal still blocks every witness; a reason naming only SOME mutants does not —
the other survivors are classified, the no-verdict mutants are named by id in both verbs, never
asked for an input and never flaggable, and the certificate stays withheld. The universe line and
the cut reasons derive from the same facts.
"""

from __future__ import annotations

import ast
import importlib.util
import os
import subprocess
import sys
import types

import pytest

from Detective.cli import _no_verdict_text, _unscored_flag_refusal, universe_tail
from Detective.validity import (
    classification_standing,
    cut_reason_sentence,
    normalize_validity,
    unresolved_mutant_records,
)

# ── the decisions ───────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("reasons", "standing"),
    [
        ([], "classify"),
        (["mutant_wall_undetermined"], "classify_beside_unresolved"),
        (["step_budget_exceeded"], "classify_beside_unresolved"),
        (["mutant_wall_undetermined", "step_budget_exceeded"], "classify_beside_unresolved"),
        (["mutant_wall_undetermined", "coverage_truncated"], "blocked"),
        (["budget_exhausted"], "blocked"),
        (["target_load_failed"], "blocked"),
        (["nested_measurement"], "blocked"),
        (["nondeterministic_baseline", "mutant_wall_undetermined"], "blocked"),
        (["engine_refused_unspecified"], "blocked"),
        (["a_reason_from_the_future"], "blocked"),
    ],
)
def test_only_reasons_that_name_some_mutants_let_classification_run(reasons, standing):
    assert classification_standing(reasons) == standing


@pytest.mark.parametrize(
    ("fast", "reasons", "tail"),
    [
        (False, [], "exhaustive"),
        (False, ["mutant_wall_undetermined"], "exhaustive_unresolved"),
        (False, ["step_budget_exceeded"], "exhaustive_unresolved"),
        (False, ["coverage_truncated"], "truncated"),
        (False, ["budget_exhausted", "mutant_wall_undetermined"], "truncated"),
        (True, [], "greedy_floor"),
        (True, ["mutant_wall_undetermined"], "greedy_floor"),
        (True, ["coverage_truncated"], "truncated"),
    ],
)
def test_the_universe_tail_reads_the_reasons_the_verdict_rests_on(fast, reasons, tail):
    assert universe_tail(fast, reasons) == tail


def test_the_no_verdict_mutants_are_read_by_id_and_disposition():
    records = [
        {"mutant_id": "STMT_a", "disposition": "undetermined"},
        {"mutant_id": "VALUE_b", "disposition": "diverged"},
        {"mutant_id": "STMT_c", "disposition": "nested_measurement"},
        {"mutant_id": "STMT_d", "disposition": "not_entered"},
        "not a record",
    ]
    assert unresolved_mutant_records(records) == (("STMT_a", "undetermined"), ("VALUE_b", "diverged"))
    assert unresolved_mutant_records([]) == ()
    # A foreign record is read defensively: ids are always text, a missing id is named "?", and a
    # malformed disposition (unhashable, or no per-mutant meaning) is skipped, never a crash.
    assert unresolved_mutant_records([{"mutant_id": 5, "disposition": "undetermined"}]) == (
        ("5", "undetermined"),
    )
    assert unresolved_mutant_records([{"disposition": "diverged"}]) == (("?", "diverged"),)
    assert unresolved_mutant_records([{"mutant_id": "x", "disposition": ["undetermined"]}]) == ()
    assert unresolved_mutant_records([{"mutant_id": "x"}]) == ()
    text = _no_verdict_text((("STMT_a", "undetermined"), ("VALUE_b", "diverged")))
    assert text.startswith("2 — STMT_a (undetermined), VALUE_b (diverged)")
    assert "no input or flag applies" in text


# ── the adapter: reasons named, never masked ────────────────────────────────────────────────────


def _result(unscored_by: dict, **fields):
    category = types.SimpleNamespace(unscored_by=unscored_by)
    base = {
        "is_gateable": not unscored_by,
        "coverage_depth": "profiled",
        "collection_conflicts": [],
        "all_contained": True,
        "collection_errors": [],
        "execution_mode": "in_process",
        "budget_exhausted": False,
        "per_category": [category],
    }
    base.update(fields)
    return types.SimpleNamespace(**base)


def test_a_wall_bound_alone_classifies_beside_its_named_mutants():
    validity = normalize_validity(_result({"undetermined": 2}))
    assert validity.cut_reasons == ("mutant_wall_undetermined",)
    assert not validity.admits_certificate, "a no-verdict mutant must never let a certificate stand"
    assert classification_standing(list(validity.cut_reasons)) == "classify_beside_unresolved"


def test_an_older_engine_that_still_cuts_the_depth_keeps_classification_blocked():
    validity = normalize_validity(_result({"undetermined": 2}, coverage_depth="cut"))
    assert "coverage_truncated" in validity.cut_reasons
    assert classification_standing(list(validity.cut_reasons)) == "blocked"


def test_a_nondeterministic_baseline_is_named_and_not_hidden_behind_a_wall_bound():
    validity = normalize_validity(_result({"undetermined": 1}, determinism="nondeterministic"))
    assert "nondeterministic_baseline" in validity.cut_reasons
    assert classification_standing(list(validity.cut_reasons)) == "blocked"


def test_an_unknown_disposition_beside_a_known_one_is_still_named():
    validity = normalize_validity(_result({"undetermined": 1, "a_future_disposition": 1}))
    assert "engine_refused_unspecified" in validity.cut_reasons
    assert classification_standing(list(validity.cut_reasons)) == "blocked"


def test_a_genuine_budget_truncation_still_blocks_every_witness():
    validity = normalize_validity(_result({"undetermined": 1}, budget_exhausted=True, coverage_depth="cut"))
    assert {"budget_exhausted", "coverage_truncated"} <= set(validity.cut_reasons)
    assert classification_standing(list(validity.cut_reasons)) == "blocked"
    assert universe_tail(False, list(validity.cut_reasons)) == "truncated"


# ── nested_measurement through the REAL engine (Wesker's direct-call profiling path) ────────────

_SRC = "def compute(n):\n    return n * 2\n"


@pytest.fixture
def nested_profile(tmp_path):
    """A profile whose only test drives the engine before it reaches the target — the shape Wesker's
    own `test_nested_measurement_intent` builds. Every mutant is refused as `nested_measurement`."""
    from Wesker.engine import evaluate_mutant, generate_mutants, run_function_profiling
    from Wesker.filter import filter_categories

    path = tmp_path / "nested_det_mod.py"
    path.write_text(_SRC)
    spec = importlib.util.spec_from_file_location("nested_det_mod", str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["nested_det_mod"] = mod
    spec.loader.exec_module(mod)
    node = ast.parse(_SRC).body[0]
    inner = generate_mutants(node, filter_categories(node, True), max_per_category=0, pass_index=0)[1]

    def plain():
        assert mod.compute(2) == 4

    def test_runs_the_engine():
        evaluate_mutant(inner, [plain], mod.compute, qualname="compute", source_path=str(path))
        assert mod.compute(1) == 2

    try:
        yield run_function_profiling(
            node,
            "nested_det_mod.py::compute",
            filter_categories(node, True),
            [test_runs_the_engine],
            mod.compute,
            max_per_category=0,
        )
    finally:
        sys.modules.pop("nested_det_mod", None)


def test_a_nested_measurement_has_its_own_reason_and_remedy(nested_profile):
    validity = normalize_validity(nested_profile)
    assert "nested_measurement" in validity.cut_reasons, validity.cut_reasons
    assert "engine_refused_unspecified" not in validity.cut_reasons, validity.cut_reasons
    assert "--isolated" in cut_reason_sentence("nested_measurement")
    assert classification_standing(list(validity.cut_reasons)) == "blocked"


def test_flag_refuses_a_mutant_that_reached_no_verdict_by_name(nested_profile, capsys):
    mid = next(r["mutant_id"] for r in nested_profile.unscored_records)
    args = types.SimpleNamespace(mutant_id=mid, json=False, target="nested_det_mod.py::compute")
    assert _unscored_flag_refusal(args, nested_profile) == 1
    err = capsys.readouterr().err
    assert "reached no verdict (nested_measurement)" in err
    assert "--isolated" in err
    survivor = types.SimpleNamespace(mutant_id="NOT_UNSCORED", json=False, target="t")
    assert _unscored_flag_refusal(survivor, nested_profile) is None, "only a no-verdict id is refused here"


# ── end to end: D#80's own fixture through the real CLI ─────────────────────────────────────────

_LOOP = (
    "def first_false(flags: list, start: int) -> int:\n"
    '    """The index of the first False at or after start, or the end of the list."""\n'
    "    i = max(start, 0)\n"
    "    while i < len(flags) and flags[i]:\n"
    "        i += 1\n"
    "    return i\n"
)
_LOOP_TEST = (
    "from skipmod import first_false\n\n\ndef test_first_false():\n"
    "    assert first_false([True, True, False], 0) == 2\n"
)


def _detective(cwd, *argv):
    return subprocess.run(
        [sys.executable, "-m", "Detective", *argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
        env=dict(os.environ),
    )


def test_the_loop_fixture_classifies_beside_its_named_no_verdict_mutants(tmp_path):
    (tmp_path / "skipmod.py").write_text(_LOOP)
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_skipmod.py").write_text(_LOOP_TEST)
    migrate = _detective(tmp_path, "regime", "--migrate", "--project-root", str(tmp_path))
    assert migrate.returncode == 0, migrate.stdout + migrate.stderr
    run = _detective(tmp_path, "converge", "skipmod.py::first_false")
    out = run.stdout
    rows = [ln for ln in out.splitlines() if "⚠ no verdict" in ln]
    assert len(rows) == 1, out
    named = [tok for tok in rows[0].split() if tok.startswith(("STMT_", "VALUE_"))]
    assert len(named) == 2, rows[0]
    # `undetermined` today; `diverged` once a deterministic step budget decides these mutants (#27).
    assert rows[0].count("(undetermined)") + rows[0].count("(diverged)") == 2, rows[0]
    assert "unclassified" not in out, "survivors unrelated to the no-verdict mutants went unclassified"
    assert "cut before the universe" not in out, "a per-mutant outcome was reported as a truncation"
    final = [ln for ln in out.splitlines() if ln.startswith("FINAL ")]
    assert final and "✓ COMPLETE" not in final[-1], "a run with no-verdict mutants claimed a certificate"
    assert "AUTHOR INPUTS" not in out and "WRITE TEST" not in out
    report = (tmp_path / ".detective" / "reports" / "converge_first_false.txt").read_text()
    assert "every operator-universe mutant tested — 2 reached no verdict" in report
    assert "exhaustive — every operator-universe mutant tested" not in report
    refused = _detective(tmp_path, "flag", "skipmod.py::first_false", named[0], "--note", "never")
    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert "reached no verdict" in refused.stderr
