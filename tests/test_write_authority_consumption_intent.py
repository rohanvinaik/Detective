"""Intent: a mutant whose test run was prevented from writing outside its authority is named (#105).

THE DEFECT, measured 2026-10-04 dogfooding `audit --remove` on Detective and reproduced 2026-10-25 in a
disposable clone of ed5efd8 (13 untracked files from one run of
`audit 'Detective/suite_edit.py::remove_definition_from_source' --remove`). Mutant evaluation runs in
the project root; a SWAP mutant of ``atomic_write_text(path, source)`` wrote files NAMED by a test's
source text there, and staging files such as ``pyproject.toml.tmp-<pid>`` landed beside the real
``pyproject.toml``. On the minimal fixture below (a `save` that writes through an atomic helper, one
test keeping its paths under ``tmp_path``) the same mutant left ``{"a": 1}`` in the project root AND
scored a crash kill — the test's ``read_text`` of the file it expected raised.

Wesker now arms an audit-hook write authority for every test run against a mutant (the session's
pytest basetemp, entries the process created exclusively in the temporary directory, devices) and
names the mutant ``write_outside_authority`` — neither killed nor survived. What Detective must do with
that disposition, and what these pin:

* it is a per-mutant reason with its own name and sentence (validity schema 8), distinct from the
  speculative-capture refusal ``filesystem_write_blocked``: that one aborts an observation, this one
  leaves one mutant without a verdict;
* the other survivors are still classified; the certificate is withheld;
* converge and audit name the mutant in the ``⚠ no verdict`` row, the universe line says a mutant
  reached no verdict, the repair route is ``write_authority`` (its remedy is in the test — no
  budget, isolation or input changes it), and ``flag`` refuses the id by name;
* nothing lands in the project root.
"""

from __future__ import annotations

import ast
import importlib.util
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

from Detective.cli import (
    _no_verdict_text,
    _unscored_flag_refusal,
    converge_step,
    repair_measurement_route,
    universe_tail,
)
from Detective.validity import (
    CUT_REASONS,
    MEASUREMENT_VALIDITY_SCHEMA,
    PER_MUTANT_REASONS,
    UNSCORED_DISPOSITION_REASONS,
    classification_standing,
    cut_reason_sentence,
    measurement_cut_reasons,
    normalize_validity,
    unresolved_mutant_records,
)

REASON = "write_outside_authority"

# ── the vocabulary ──────────────────────────────────────────────────────────────────────────────


def test_the_disposition_has_its_own_per_mutant_reason():
    assert UNSCORED_DISPOSITION_REASONS[REASON] == REASON
    assert REASON in CUT_REASONS
    assert REASON in PER_MUTANT_REASONS
    assert MEASUREMENT_VALIDITY_SCHEMA >= 8, "a changed reason vocabulary bumps the schema"


def test_it_is_not_the_speculative_capture_refusal():
    """Two different facts: `filesystem_write_blocked` aborts a speculative OBSERVATION (golden capture,
    a witness search); this one leaves one mutant of an existing test's run without a verdict."""
    assert "filesystem_write_blocked" not in CUT_REASONS
    assert "filesystem_write_blocked" not in UNSCORED_DISPOSITION_REASONS


def test_the_sentence_names_the_remedy_in_the_test():
    sentence = cut_reason_sentence(REASON)
    assert "write authority" in sentence
    assert "prevented" in sentence
    assert "tmp_path" in sentence
    assert "unrecognised" not in sentence


def test_the_cut_reason_is_reported_in_declaration_order():
    reasons = measurement_cut_reasons(
        True,
        False,
        False,
        "profiled",
        "contained",
        False,
        mutant_wall_undetermined=True,
        write_outside_authority=True,
    )
    assert reasons == ("mutant_wall_undetermined", REASON)
    assert list(reasons) == [r for r in CUT_REASONS if r in reasons]
    assert measurement_cut_reasons(True, True, False, "profiled", "contained", False) == ()


# ── the decisions ───────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("reasons", "standing"),
    [
        ([REASON], "classify_beside_unresolved"),
        ([REASON, "mutant_wall_undetermined"], "classify_beside_unresolved"),
        ([REASON, "coverage_truncated"], "blocked"),
        ([REASON, "nested_measurement"], "blocked"),
    ],
)
def test_the_other_survivors_are_still_classified(reasons, standing):
    assert classification_standing(reasons) == standing


def test_the_universe_line_says_a_mutant_reached_no_verdict():
    assert universe_tail(False, [REASON]) == "exhaustive_unresolved"
    assert universe_tail(False, [REASON, "budget_exhausted"]) == "truncated"
    assert universe_tail(True, [REASON]) == "greedy_floor"


@pytest.mark.parametrize(
    ("reasons", "route"),
    [
        ((REASON,), "write_authority"),
        ((REASON, "mutant_wall_undetermined"), "write_authority"),
        ((REASON, "step_budget_exceeded"), "write_authority"),
        # Run-level reasons outrank it: their remedies act on the whole measurement.
        ((REASON, "nested_measurement"), "isolate"),
        ((REASON, "collection_incomplete"), "fix_collection"),
        ((REASON, "mutant_not_entered"), "mutant_phase"),
        (("mutant_wall_undetermined",), "execution_budget"),
    ],
)
def test_the_repair_route_is_its_own(reasons, route):
    assert repair_measurement_route(reasons) == route


def test_the_route_is_a_stop_that_runs_nothing():
    """No re-run fixes it: the same test under the same mutant is prevented the same way."""
    assert converge_step("repair_measurement", "write_authority", "", False, "", "") == (
        "stop",
        "write_authority",
    )


def test_the_no_verdict_rows_carry_it():
    records = [
        {"mutant_id": "SWAP_a", "disposition": REASON, "test": "t.py::t", "blocked_writes": ["/p/x"]},
        {"mutant_id": "STMT_b", "disposition": "undetermined"},
        {"mutant_id": "STMT_c", "disposition": "not_entered"},
    ]
    pairs = unresolved_mutant_records(records)
    assert pairs == (("SWAP_a", REASON), ("STMT_b", "undetermined"))
    assert _no_verdict_text(pairs).startswith(f"2 — SWAP_a ({REASON}), STMT_b (undetermined)")


# ── the adapter ─────────────────────────────────────────────────────────────────────────────────


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


def test_the_adapter_names_it_and_withholds_the_certificate():
    validity = normalize_validity(_result({REASON: 1}))
    assert validity.cut_reasons == (REASON,), "named, never engine_refused_unspecified"
    assert not validity.admits_certificate
    assert classification_standing(list(validity.cut_reasons)) == "classify_beside_unresolved"


def test_an_engine_that_never_reports_it_reads_as_before():
    validity = normalize_validity(_result({}))
    assert REASON not in validity.cut_reasons


# ── through the REAL engine (Wesker's direct-call profiling path) ───────────────────────────────

_STORE = (
    "import os\n\n\n"
    "def atomic_write_text(path, text):\n"
    "    staging = f'{path}.tmp-{os.getpid()}'\n"
    "    with open(staging, 'w') as fh:\n"
    "        fh.write(text)\n"
    "    os.replace(staging, path)\n\n\n"
    "def save(path, text):\n"
    "    atomic_write_text(path, text)\n"
    "    return path\n"
)


@pytest.fixture
def swap_profile(tmp_path, monkeypatch):
    """D#105's shape: the test keeps its path inside its authority; the SWAP mutant swaps it out into
    the working directory, which is the project root."""
    from Wesker.engine import MutationCategory, run_function_profiling
    from Wesker.write_authority import declared_roots

    project, authority = tmp_path / "project", tmp_path / "authority"
    project.mkdir()
    authority.mkdir()
    path = project / "wa_det_store.py"
    path.write_text(_STORE)
    spec = importlib.util.spec_from_file_location("wa_det_store", str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["wa_det_store"] = mod
    spec.loader.exec_module(mod)
    node = next(n for n in ast.parse(_STORE).body if getattr(n, "name", "") == "save")

    def test_saves():
        target = authority / "store.json"
        assert mod.save(str(target), '{"a": 1}') == str(target)
        assert target.exists()

    monkeypatch.chdir(project)
    before = {p.name for p in project.iterdir()}
    try:
        with declared_roots([str(authority)]):
            result = run_function_profiling(
                node,
                "wa_det_store.py::save",
                {MutationCategory.SWAP, MutationCategory.OUTPUT},
                [test_saves],
                mod.save,
                max_per_category=0,
            )
        yield result, project, before
    finally:
        sys.modules.pop("wa_det_store", None)


def test_the_real_disposition_reaches_its_reason(swap_profile):
    result, project, before = swap_profile
    assert {p.name for p in project.iterdir()} == before, "a mutant wrote into the project"
    validity = normalize_validity(result)
    assert REASON in validity.cut_reasons, validity.cut_reasons
    assert "engine_refused_unspecified" not in validity.cut_reasons
    assert classification_standing(list(validity.cut_reasons)) == "classify_beside_unresolved"
    assert unresolved_mutant_records(result.unscored_records) == tuple(
        (r["mutant_id"], REASON) for r in result.unscored_records if r["disposition"] == REASON
    )
    killed = {k["mutant_id"] for k in result.killed_records}
    assert all(r["mutant_id"] not in killed for r in result.unscored_records), "a prevented write scored"


def test_flag_refuses_it_by_name(swap_profile, capsys):
    result, _, _ = swap_profile
    mid = next(r["mutant_id"] for r in result.unscored_records if r["disposition"] == REASON)
    args = types.SimpleNamespace(mutant_id=mid, json=False, target="wa_det_store.py::save")
    assert _unscored_flag_refusal(args, result) == 1
    err = capsys.readouterr().err
    assert f"reached no verdict ({REASON})" in err
    assert "write authority" in err


# ── end to end: the minimal D#105 fixture through the real CLI ──────────────────────────────────

_TEST = (
    "from store import save\n\n\n"
    "def test_save_writes_the_file(tmp_path):\n"
    "    target = tmp_path / 'store.json'\n"
    "    assert save(str(target), '{\"a\": 1}') == str(target)\n"
    "    assert target.exists()\n"
    "    assert target.read_text() == '{\"a\": 1}'\n"
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


def _user_entries(root: Path) -> set[str]:
    """The project root's entries, without the tools' own state and bytecode."""
    return {p.name for p in root.iterdir()} - {".detective", ".wesker", "__pycache__"}


def test_the_fixture_names_the_swap_mutant_and_leaves_the_project_root_untouched(tmp_path):
    (tmp_path / "store.py").write_text(_STORE)
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_store.py").write_text(_TEST)
    migrate = _detective(tmp_path, "regime", "--migrate", "--project-root", str(tmp_path))
    assert migrate.returncode == 0, migrate.stdout + migrate.stderr
    before = _user_entries(tmp_path)

    run = _detective(tmp_path, "converge", "store.py::save")
    out = run.stdout
    assert _user_entries(tmp_path) == before, "a mutant wrote into the project root"
    rows = [ln for ln in out.splitlines() if "⚠ no verdict" in ln]
    assert len(rows) == 1, out
    assert "SWAP_" in rows[0] and f"({REASON})" in rows[0], rows[0]
    assert "INCOMPLETE:" in out and "write authority" in out, out
    assert "keep the test's writes inside its temporary directory" in out
    final = [ln for ln in out.splitlines() if ln.startswith("FINAL ")]
    assert final and "✓ COMPLETE" not in final[-1], "a run with a prevented write claimed a certificate"
    assert "AUTHOR INPUTS" not in out and "WRITE TEST" not in out
    report = (tmp_path / ".detective" / "reports" / "converge_save.txt").read_text()
    assert "every operator-universe mutant tested — 1 reached no verdict" in report

    audit = _detective(tmp_path, "audit", "store.py::save")
    assert f"({REASON})" in audit.stdout, audit.stdout + audit.stderr
    mid = next(tok for tok in rows[0].split() if tok.startswith("SWAP_"))
    refused = _detective(tmp_path, "flag", "store.py::save", mid, "--note", "never")
    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert f"reached no verdict ({REASON})" in refused.stderr
    assert _user_entries(tmp_path) == before
