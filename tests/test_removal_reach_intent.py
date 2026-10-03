"""Intent tests for #103: `audit --remove` deleted a test another function needed, under a false label.

The founder's rule for this issue: "make sure the removals were WRONG, not just aggressive. We can
re-label aggressiveness that is correct, but we must fix removals that are wrong." Both cases were
measured through the real CLI on 2026-10-02.

**WRONG: deleted a needed test.** ``h`` calls ``g``, which calls ``f``, each in its own module.
``test_mixed`` asserts ``f(3) == 6`` (a duplicate) and ``h(200) == 400``, and is the only test that
reaches ``h``'s ``x > 100`` branch. ``audit f --remove`` deleted it as redundant; ``h`` fell from
12/14 value-pinned to 5/14, with line 6 uncovered, while the report said ``complete=True``. Two
causes, both fixed here:
- the evidence boundary was one hop (``f``'s file plus its direct callers and callees), and ``h`` is
  two hops away;
- inside the CLI's live session, the shared baseline is traced only for the target's file, so a
  profile of ANY function in another file came back empty and VALID: 0 kills, no coverage. Even the
  one-hop bridge check measured nothing.

**CORRECT, mislabelled.** With ``tests/test_f.py`` and ``tests/test_other.py`` both testing ``f``,
``--remove`` deleted the redundant tests in both files, and ``f`` stayed complete. The deletions were
right; the sentence beside them ("never a cross-file test") was false. It is re-labelled here, never
restricted.

Pinned: the pure decisions, stated from intent; identity and editing over real files; and the two
measured cases through the installed console script.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import textwrap
from pathlib import Path
from unittest.mock import patch

from Detective.audit import (
    module_safe_removals,
    probe_reach_status,
    reach_consultation_plan,
    removal_after_reading,
    removal_gate,
    removal_safety,
)
from Detective.engine import session_baseline_scope
from Detective.suite_edit import (
    apply_removals,
    nodeid_parts,
    removal_disposition,
    removal_outcome_why,
    removal_summary,
    remove_definition_from_source,
)

# --------------------------------------------------------------------------------------
# The decisions, from intent
# --------------------------------------------------------------------------------------


def test_removal_acts_only_on_a_target_measurement_that_admits_a_certificate():
    """The redundant set is read off the target's own kill matrix, and nothing re-checks the target
    itself: an unresolved measurement (a truncated search, mutants that could not be built) leaves
    "redundant here" unestablished. A gap is still a valid measurement; an unknown state is refused."""
    assert removal_gate("complete") == "proceed"
    assert removal_gate("gap") == "proceed"
    for state in ("unresolved", "trace_next", "", "something_new"):
        assert removal_gate(state) == "refuse_unresolved"


def test_a_gap_after_removal_is_blamed_on_it_only_when_something_newly_opened():
    """A target that had a gap before still has it after: that is not the removal's doing. Anything open
    after that was not before means the removal broke something, and is never reported as done."""
    assert removal_after_reading("complete", "complete", 0) == "complete"
    assert removal_after_reading("gap", "complete", 0) == "complete"
    assert removal_after_reading("gap", "gap", 0) == "gap_kept"
    assert removal_after_reading("gap", "gap", 2) == "gap_new"
    assert removal_after_reading("complete", "gap", 0) == "gap_new"
    for after in ("unresolved", "", "something_new"):
        assert removal_after_reading("complete", after, 0) == "unmeasured"
        assert removal_after_reading("gap", after, 3) == "unmeasured"


def test_a_measured_need_outranks_everything():
    assert removal_safety("src/hmod.py::h", "known", 0, 0) == "retained_for"
    assert removal_safety("src/hmod.py::h", "skipped", 3, 2) == "retained_for"


def test_an_unobserved_reach_is_never_read_as_an_empty_one():
    """A candidate no collected test answers to never ran; one that did not pass by itself ran only part
    of what the measured run did. Each keeps the test, under its own code, since the remedies differ."""
    assert removal_safety("", "not_collected", 0, 0) == "reach_unobserved"
    assert removal_safety("   ", "not_collected", 0, 0) == "reach_unobserved"
    for status in ("raised", "skipped", "failed", "error", "xfailed", "something_new"):
        assert removal_safety("", status, 0, 0) == "reach_not_reproduced"


def test_a_function_without_a_valid_measurement_outranks_the_budget():
    """Raising the budget cannot fix an invalid measurement, so that cause is the one named."""
    assert removal_safety("", "known", 1, 0) == "reach_unmeasured"
    assert removal_safety("", "known", 1, 4) == "reach_unmeasured"


def test_a_reach_the_budget_left_unchecked_keeps_the_candidate():
    assert removal_safety("", "known", 0, 1) == "reach_over_budget"


def test_redundant_everywhere_it_runs_is_removable_however_far_away():
    assert removal_safety("", "known", 0, 0) == "removable"


def test_a_probe_counts_only_a_run_that_passed_as_the_measured_one_did():
    assert probe_reach_status(False, "passed") == "known"
    assert probe_reach_status(False, "unobserved") == "known"  # a plain function that returned
    assert probe_reach_status(False, "") == "known"


def test_a_skipped_or_failing_rerun_is_never_read_as_its_reach():
    """The live wrapper returns normally for a skip: what ran before the skip is a PARTIAL reach."""
    for category in ("skipped", "xfailed", "failed", "error", "something_new"):
        assert probe_reach_status(False, category) == category
        assert probe_reach_status(True, category) == category


def test_a_rerun_that_raised_without_a_category_is_named_raised():
    """pytest's `Failed`/`Skipped` derive from BaseException; a plain callable has no category."""
    assert probe_reach_status(True, "unobserved") == "raised"
    assert probe_reach_status(True, "passed") == "raised"


def test_the_budget_decides_whole_candidates_smallest_reach_first():
    """One test reaching many functions must not starve the tests reaching few: a candidate is decided
    only when everything it runs is consulted, so a half-consulted candidate is budget wasted."""
    unchecked = {"t_big": ["a.py::f", "b.py::g", "c.py::h"], "t_small": ["a.py::f"], "t_none": []}
    assert reach_consultation_plan(unchecked, 2) == {
        "t_none": "covered",
        "t_small": "consult",
        "t_big": "over_budget",
    }
    # `a.py::f` is already paid for by t_small, so t_big costs two more, and three is enough.
    assert reach_consultation_plan(unchecked, 3) == {
        "t_none": "covered",
        "t_small": "consult",
        "t_big": "consult",
    }


def test_no_budget_consults_nothing_yet_still_decides_what_needs_nothing():
    unchecked = {"t1": ["a.py::f"], "t2": []}
    assert reach_consultation_plan(unchecked, 0) == {"t1": "over_budget", "t2": "covered"}
    assert reach_consultation_plan(unchecked, -5) == {"t1": "over_budget", "t2": "covered"}


def test_equal_reach_breaks_by_id_so_the_same_run_reads_the_same():
    assert reach_consultation_plan({"t_b": ["x.py::f"], "t_a": ["y.py::g"]}, 1) == {
        "t_a": "consult",
        "t_b": "over_budget",
    }


def test_the_live_baseline_answers_only_for_the_files_it_traced():
    traced = ["/r/src/fmod.py"]
    assert session_baseline_scope(False, traced, "/r/src/fmod.py") == "no_session"
    assert session_baseline_scope(True, [], "/r/src/gmod.py") == "undeclared"
    assert session_baseline_scope(True, traced, "/r/src/fmod.py") == "covers"
    assert session_baseline_scope(True, traced, "/r/src/gmod.py") == "foreign_file"


def test_a_session_holder_from_an_older_wesker_reads_undeclared_never_a_crash():
    """CI installs the uv.lock-pinned Wesker; a holder that predates `target_files` must leave every
    profile in the session working as before, not raise inside it."""
    from Wesker.engine import _SESSION_BASELINE

    from Detective.engine import _session_baseline_scope_for

    token = _SESSION_BASELINE.set(object())  # type: ignore[arg-type]  # a holder without the attribute
    try:
        assert _session_baseline_scope_for("/r/src/fmod.py") == "undeclared"
    finally:
        _SESSION_BASELINE.reset(token)


def test_a_row_is_never_edited_and_one_definition_is_the_only_edit():
    assert removal_disposition("parametrized_case", 1, "function") == "parametrized_row"
    assert removal_disposition("qualified", 0, "") == "not_located"
    assert removal_disposition("empty", 0, "") == "not_located"
    assert removal_disposition("bare", 2, "function") == "ambiguous"
    assert removal_disposition("qualified", 1, "unsupported") == "unsupported_shape"
    assert removal_disposition("qualified", 1, "function") == "remove"
    assert removal_disposition("qualified", 1, "method") == "remove"


def test_a_class_method_id_names_its_file_not_its_class():
    """Before #103 the file was everything before the LAST `::`, so this named `tests/t.py::TestC`."""
    assert nodeid_parts("tests/t.py::TestC::test_m[x-1]") == ("tests/t.py", "TestC.test_m", "x-1")
    assert nodeid_parts("tests/t.py::TestA::TestB::test_m") == ("tests/t.py", "TestA.TestB.test_m", "")
    assert nodeid_parts("legacy:?::test_x") == ("", "test_x", "")
    assert nodeid_parts("legacy:a.py::base#shown[c]") == ("a.py", "base", "c")
    assert nodeid_parts("test_x") == ("", "test_x", "")


_CODES = (
    "removed",
    "retained_for",
    "target_unresolved",
    "reach_unobserved",
    "reach_not_reproduced",
    "reach_unmeasured",
    "reach_over_budget",
    "parametrized_row",
    "not_located",
    "ambiguous",
    "unsupported_shape",
    "stale_collection",
    "shadowed",
)


def test_every_outcome_has_its_own_sentence_and_an_unknown_one_is_named():
    sentences = {code: removal_outcome_why(code, "src/x.py::k") for code in _CODES}
    assert len(set(sentences.values())) == len(_CODES)
    assert "src/x.py::k" in sentences["retained_for"]
    assert "never-seen" in removal_outcome_why("never-seen")


def test_an_empty_run_says_why_and_counts_by_cause():
    assert removal_summary([]) == "no candidate was safely removable"
    summary = removal_summary(["retained_for", "retained_for", "parametrized_row", "brand_new"])
    assert summary.startswith("2 still needed by another function")
    assert "1 parametrized row(s)" in summary
    assert "1 brand_new" in summary


# --------------------------------------------------------------------------------------
# Editing one definition exactly
# --------------------------------------------------------------------------------------

_CLASS_SOURCE = textwrap.dedent(
    """
    class TestC:
        def test_a(self):
            assert True

        def test_b(self):
            assert True


    class TestOnly:
        def test_lone(self):
            assert True
    """
)


def test_a_method_is_removed_and_its_class_keeps_the_rest():
    code, edited = remove_definition_from_source(_CLASS_SOURCE, "TestC.test_a")
    assert code == "removed"
    tree = ast.parse(edited)
    test_c = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "TestC")
    assert [n.name for n in test_c.body if isinstance(n, ast.FunctionDef)] == ["test_b"]


def test_removing_a_class_s_only_method_leaves_a_class_that_parses():
    code, edited = remove_definition_from_source(_CLASS_SOURCE, "TestOnly.test_lone")
    assert code == "removed"
    ast.parse(edited)
    assert "def test_lone" not in edited


def test_a_name_bound_twice_is_refused_never_half_removed():
    """Python keeps the LAST binding; the function this replaced removed the FIRST (the dead copy)."""
    source = "def test_x():\n    assert 1\n\n\ndef test_x():\n    assert 2\n"
    assert remove_definition_from_source(source, "test_x") == ("shadowed", source)


def test_a_method_of_a_class_that_is_not_there_is_missing_and_the_source_is_untouched():
    source = "def test_x():\n    pass\n"
    assert remove_definition_from_source(source, "TestC.test_x") == ("missing", source)


def test_a_method_of_a_class_bound_twice_is_refused_as_shadowed():
    """Python keeps the LAST class binding, so editing either copy changes which tests run."""
    source = (
        "class TestC:\n    def test_x(self):\n        pass\n\n\n"
        "class TestC:\n    def test_x(self):\n        pass\n"
    )
    assert remove_definition_from_source(source, "TestC.test_x") == ("shadowed", source)


def test_a_definition_that_is_not_there_is_missing_and_the_source_is_untouched():
    assert remove_definition_from_source("def test_y():\n    pass\n", "test_x") == (
        "missing",
        "def test_y():\n    pass\n",
    )
    assert remove_definition_from_source("def broken(:\n", "test_x") == ("missing", "def broken(:\n")


def test_a_source_the_parser_cannot_read_is_missing_never_a_crash():
    """The parser raises more than SyntaxError on a str (measured on 3.14: a lone surrogate raises
    UnicodeEncodeError, a deep expression overflows its stack as MemoryError). The function this
    replaced caught SyntaxError alone, so a decision documented as total crashed on these."""
    source = "def test_x():\n    return '\ud800'\n"
    assert remove_definition_from_source(source, "test_x") == ("missing", source)


# --------------------------------------------------------------------------------------
# Identity over real files, through Wesker's discovery
# --------------------------------------------------------------------------------------


def _write(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body))
    return path


def _two_definitions(tmp_path: Path) -> tuple[Path, Path]:
    uniq = abs(hash(str(tmp_path))) % 10**8
    _write(tmp_path / "src" / f"m{uniq}.py", "def f(x):\n    return x + 1\n")
    a = _write(
        tmp_path / "tests" / f"test_a{uniq}.py",
        f"from m{uniq} import f\n\n\ndef test_dup():\n    assert f(1) == 2\n",
    )
    b = _write(
        tmp_path / "tests" / f"test_b{uniq}.py",
        f"from m{uniq} import f\n\n\ndef test_dup():\n    assert f(2) == 3\n",
    )
    (tmp_path / "pyproject.toml").write_text('[tool.pytest.ini_options]\ntestpaths = ["tests"]\n')
    return a, b


def test_a_file_less_id_with_two_definitions_deletes_nothing(tmp_path, monkeypatch):
    """The function this replaced deleted EVERY in-root definition of a bare name."""
    a, b = _two_definitions(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path / "src"))
    before = (a.read_text(), b.read_text())
    src = str(next((tmp_path / "src").glob("m*.py")).relative_to(tmp_path))
    report = apply_removals(src, str(tmp_path), ["test_dup"])
    assert dict(report.outcomes) == {"test_dup": "ambiguous"}
    assert report.removed == ()
    assert (a.read_text(), b.read_text()) == before


def test_a_qualified_id_edits_only_its_own_file_and_is_the_only_one_reported(tmp_path, monkeypatch):
    """Accounting was by bare name, so the other file's `test_dup` read as removed too."""
    a, b = _two_definitions(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path / "src"))
    src = str(next((tmp_path / "src").glob("m*.py")).relative_to(tmp_path))
    wanted = f"tests/{a.name}::test_dup"
    report = apply_removals(src, str(tmp_path), [wanted])
    assert report.removed == (wanted,)
    assert "def test_dup" not in a.read_text()
    assert "def test_dup" in b.read_text()


# --------------------------------------------------------------------------------------
# The reach probe and its budget
# --------------------------------------------------------------------------------------


def _lone_function_module(tmp_path: Path) -> Path:
    """A target with no siblings and candidates with no test file, so only the reach step decides."""
    return _write(tmp_path / "m.py", "def f(x):\n    return x + 1\n")


def test_a_reach_the_budget_cannot_cover_is_kept_and_named(tmp_path):
    _lone_function_module(tmp_path)
    reach = {"test_far": ("known", frozenset({("src/x.py", "k")})), "test_here": ("known", frozenset())}
    with patch("Detective.audit.candidate_reach", return_value=(reach, {})):
        safe, retained, unverified = module_safe_removals("m.py", "f", str(tmp_path), list(reach), 0)
    assert safe == ("test_here",)
    assert retained == {}
    assert unverified == {"test_far": ("reach_over_budget", "src/x.py::k")}


def test_a_rerun_that_did_not_pass_or_was_never_collected_keeps_the_candidate_under_its_cause(tmp_path):
    _lone_function_module(tmp_path)
    reach = {
        "test_skips": ("skipped", frozenset({("m.py", "f")})),
        "test_gone": ("not_collected", frozenset()),
    }
    with patch("Detective.audit.candidate_reach", return_value=(reach, {})):
        safe, _retained, unverified = module_safe_removals("m.py", "f", str(tmp_path), list(reach))
    assert safe == ()
    assert unverified == {
        "test_skips": ("reach_not_reproduced", "skipped"),
        "test_gone": ("reach_unobserved", ""),
    }


def test_the_probe_reads_a_live_rerun_that_skipped_or_failed_as_not_reproduced(tmp_path, monkeypatch):
    """Through Wesker's live session. The item wrapper returns NORMALLY for a skip, having run only what
    preceded it, and re-raises pytest's `Failed` (a BaseException, not an Exception) for pytest.fail.
    Neither run's reach may stand for the measured run, and neither may escape the probe."""
    from Wesker.ci import run_with_live_suite

    from Detective.audit import candidate_reach

    mod = f"mprobe{abs(hash(str(tmp_path))) % 10**8}"
    project = tmp_path / "proj"
    _write(project / f"{mod}.py", "def f(x):\n    return x + 1\n")
    (project / f"test_{mod}.py").write_text(
        "import pytest\n"
        f"from {mod} import f\n\n\n"
        "def test_passes():\n    assert f(1) == 2\n\n\n"
        "def test_skips():\n    pytest.skip('does not run by itself')\n\n\n"
        "def test_fails():\n    pytest.fail('does not pass by itself')\n"
    )
    (project / "pyproject.toml").write_text('[tool.pytest.ini_options]\ntestpaths = ["."]\n')
    monkeypatch.chdir(project)
    monkeypatch.syspath_prepend(str(project))
    ids = [f"test_{mod}.py::{name}" for name in ("test_passes", "test_skips", "test_fails")]
    seen: dict = {}

    def _probe():
        seen["reach"], _live = candidate_reach(str(project), f"{mod}.py", "f", ids)

    try:
        run_with_live_suite(str(project), _probe, target_files=[f"{mod}.py"])
    finally:
        for name in (mod, f"test_{mod}"):
            sys.modules.pop(name, None)
    reach = seen["reach"]
    assert reach[ids[0]] == ("known", frozenset({(f"{mod}.py", "f")}))
    assert reach[ids[1]][0] == "skipped"
    assert reach[ids[2]][0] == "failed"


def test_an_unresolved_target_measurement_deletes_nothing_and_never_consults_further(tmp_path):
    """The gate, wired: the redundant set of a measurement that admits no certificate is not acted on."""
    from types import SimpleNamespace

    from Detective.cli import _audit_remove, _removal_lines

    report = SimpleNamespace(
        function="src/m.py::f",
        redundant_tests=("tests/t.py::test_b", "tests/t.py::test_a"),
        function_basis=SimpleNamespace(action="unresolved"),
    )
    with patch("Detective.audit.module_safe_removals", side_effect=AssertionError("consulted")):
        record = _audit_remove("src/m.py", "f", str(tmp_path), report, two_sign=False)
    assert (record["gate"], record["target_state"], record["removed"]) == (
        "refuse_unresolved",
        "unresolved",
        [],
    )
    assert {r["code"] for r in record["outcomes"]} == {"target_unresolved"}
    lines = _removal_lines(record)
    assert lines[-2].startswith(
        "STOP:  --remove refused — src/m.py::f's own measurement admits no certificate"
    )
    assert lines[-1] == "       Re-measure it first: detective audit 'src/m.py::f'"


def test_a_recheck_that_could_not_measure_is_named_never_printed_as_a_gap():
    from Detective.cli import _removal_lines

    record = {
        "target": "src/m.py::f",
        "gate": "proceed",
        "outcomes": [{"test": "tests/t.py::test_x", "code": "removed", "subject": "", "why": "deleted"}],
        "removed": ["tests/t.py::test_x"],
        "after": {
            "test_count": 3,
            "state": "unresolved",
            "reading": "unmeasured",
            "newly_open": 0,
            "cover": 2,
        },
    }
    lines = _removal_lines(record)
    assert "  after removal: not re-measured — the in-process re-check admits no certificate" in lines
    assert lines[-1] == "DONE:  removed 1 test(s). Confirm in a fresh run: detective audit 'src/m.py::f'"
    record["after"].update(state="complete", reading="complete")
    assert _removal_lines(record)[-2:] == [
        "  after removal: 3 test(s), complete, greedy cover=2",
        "DONE:  removed 1 test(s); the suite above is what remains.",
    ]
    record["after"].update(state="gap", reading="gap_kept")
    assert _removal_lines(record)[-2:] == [
        "  after removal: 3 test(s); the gap named above, and nothing new",
        "DONE:  removed 1 test(s); the suite above is what remains.",
    ]


def test_a_recheck_that_finds_something_newly_open_stops_and_names_the_restore():
    """By construction a removal opens nothing; if the re-check says otherwise, that is a STOP, not DONE."""
    from Detective.cli import _removal_lines

    record = {
        "target": "src/m.py::f",
        "gate": "proceed",
        "outcomes": [{"test": "tests/t.py::test_x", "code": "removed", "subject": "", "why": "deleted"}],
        "removed": ["tests/t.py::test_x"],
        "after": {"test_count": 3, "state": "gap", "reading": "gap_new", "newly_open": 2, "cover": 2},
    }
    assert _removal_lines(record)[-3:] == [
        "  after removal: 3 test(s), and 2 obligation(s) open that were not before",
        "STOP:  a removal may have broken src/m.py::f. Confirm in a fresh run: detective audit 'src/m.py::f'",
        "       If it agrees, restore the removed tests listed above (git checkout).",
    ]


# --------------------------------------------------------------------------------------
# The two measured cases, through the installed console script
# --------------------------------------------------------------------------------------


def _console_script() -> Path:
    name = "detective.exe" if sys.platform == "win32" else "detective"
    script = Path(sys.executable).with_name(name)
    assert script.is_file(), f"installed-boundary test requires the console script beside {sys.executable}"
    return script


def _cli(project: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(_console_script()), *args, "--project-root", str(project)],
        cwd=str(project),
        capture_output=True,
        text=True,
        timeout=600,
    )


def _two_hop(root: Path) -> Path:
    _write(root / "src" / "fmod.py", "def f(x):\n    return x * 2\n")
    _write(root / "src" / "gmod.py", "from fmod import f\n\n\ndef g(x):\n    return f(x) + 1\n")
    _write(
        root / "src" / "hmod.py",
        "from gmod import g\n\n\ndef h(x):\n    if x > 100:\n        return g(x) - 1\n    return g(x)\n",
    )
    _write(
        root / "tests" / "test_f.py",
        "from fmod import f\n\n\n"
        "def test_f():\n    assert f(3) == 6\n\n\n"
        "def test_f_zero():\n    assert f(0) == 0\n",
    )
    _write(root / "tests" / "test_g.py", "from gmod import g\n\n\ndef test_g():\n    assert g(3) == 7\n")
    _write(
        root / "tests" / "test_h.py", "from hmod import h\n\n\ndef test_h_small():\n    assert h(1) == 3\n"
    )
    _write(
        root / "tests" / "test_mixed.py",
        "from fmod import f\nfrom hmod import h\n\n\n"
        "def test_mixed():\n    assert f(3) == 6\n    assert h(200) == 400\n",
    )
    (root / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\ntestpaths = ["tests"]\npythonpath = ["src"]\n'
    )
    return root


def _value_pinned(audit_text: str) -> str:
    """The `N/M value-pinned` figure from an audit header (the reader's own number, not a re-derivation)."""
    return next(part.strip() for part in audit_text.split("·") if "value-pinned" in part)


def test_a_test_needed_two_hops_away_is_kept(tmp_path):
    """THE regression: `test_mixed` is redundant for `f` and its neighbour `g`, and h's only pin."""
    root = _two_hop(tmp_path)
    before = _cli(root, "audit", "src/hmod.py::h")
    removal = _cli(root, "audit", "src/fmod.py::f", "--remove")
    assert removal.returncode == 0, removal.stdout + removal.stderr
    assert "tests/test_mixed.py::test_mixed — kept: src/hmod.py::h still needs it" in removal.stdout
    assert (root / "tests" / "test_mixed.py").read_text().count("def test_mixed") == 1
    assert "def test_f_zero" not in (root / "tests" / "test_f.py").read_text(), (
        "the correct removal still happens"
    )
    after = _cli(root, "audit", "src/hmod.py::h")
    assert _value_pinned(after.stdout) == _value_pinned(before.stdout)


def test_correct_cross_file_removals_still_happen_under_a_true_sentence(tmp_path):
    _write(tmp_path / "src" / "m.py", 'def f(x):\n    if x > 0:\n        return "pos"\n    return "nonpos"\n')
    _write(
        tmp_path / "tests" / "test_f.py",
        'from m import f\n\n\ndef test_pos():\n    assert f(1) == "pos"\n\n\n'
        'def test_nonpos():\n    assert f(0) == "nonpos"\n\n\ndef test_dup():\n    assert f(5) == "pos"\n',
    )
    _write(
        tmp_path / "tests" / "test_other.py",
        'from m import f\n\n\ndef test_dup():\n    assert f(7) == "pos"\n',
    )
    (tmp_path / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\ntestpaths = ["tests"]\npythonpath = ["src"]\n'
    )
    proposal = _cli(tmp_path, "audit", "src/m.py::f")
    assert "never a cross-file test" not in proposal.stdout
    assert "deletes the rest from whichever test file defines them" in proposal.stdout
    removal = _cli(tmp_path, "audit", "src/m.py::f", "--remove")
    assert removal.returncode == 0, removal.stdout + removal.stderr
    assert "def test_dup" not in (tmp_path / "tests" / "test_other.py").read_text()
    assert "after removal: 2 test(s), complete, greedy cover=2" in removal.stdout


def test_json_remove_prints_one_document_carrying_every_outcome(tmp_path):
    """Printed before the removal ran, the JSON never said what was deleted."""
    root = _two_hop(tmp_path)
    run = _cli(root, "audit", "src/fmod.py::f", "--remove", "--json")
    assert run.returncode == 0, run.stdout + run.stderr
    payload = json.loads(run.stdout)
    outcomes = {row["test"]: (row["code"], row["why"]) for row in payload["removal"]["outcomes"]}
    assert outcomes["tests/test_mixed.py::test_mixed"][0] == "retained_for"
    assert outcomes["tests/test_f.py::test_f_zero"][0] == "removed"
    assert all(why for _code, why in outcomes.values())
    assert payload["removal"]["reach_budget"] == 32


def test_a_class_method_is_removed_and_a_correct_removal_is_never_labelled_a_gap(tmp_path):
    """Through the CLI: the class-method candidate is deleted from its class, which keeps its other
    member; the rows stay rows. The edit sits mid-file, the shape measured to leave the in-process
    re-check unable to build the mutant universe (2 of 11), which the old report printed as
    `complete=False`. A fresh audit is the confirmation, and it reads complete."""
    _write(
        tmp_path / "src" / "calc.py", 'def f(x):\n    if x > 0:\n        return "pos"\n    return "nonpos"\n'
    )
    test_file = _write(
        tmp_path / "tests" / "test_calc.py",
        "import pytest\nfrom calc import f\n\n\n"
        'def test_pos():\n    assert f(1) == "pos"\n\n\n'
        'def test_nonpos():\n    assert f(0) == "nonpos"\n\n\n'
        "class TestDup:\n    value = 5\n\n"
        '    def test_dup_method(self):\n        assert f(self.value) == "pos"\n\n\n'
        '@pytest.mark.parametrize("x", [2, -4])\n'
        'def test_rows(x):\n    assert f(x) == ("pos" if x > 0 else "nonpos")\n',
    )
    (tmp_path / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\ntestpaths = ["tests"]\npythonpath = ["src"]\n'
    )
    removal = _cli(tmp_path, "audit", "src/calc.py::f", "--remove")
    assert removal.returncode == 0, removal.stdout + removal.stderr
    assert "removed 1: tests/test_calc.py::TestDup::test_dup_method" in removal.stdout
    assert "tests/test_calc.py::test_rows[2] — kept: a row of a live parametrized test" in removal.stdout
    assert "complete=False" not in removal.stdout and "GAP" not in removal.stdout
    if "not re-measured" in removal.stdout:
        assert "Confirm in a fresh run: detective audit 'src/calc.py::f'" in removal.stdout
    tree = ast.parse(test_file.read_text())
    dup = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "TestDup")
    assert not [n for n in dup.body if isinstance(n, ast.FunctionDef)] and len(dup.body) == 1
    fresh = _cli(tmp_path, "audit", "src/calc.py::f")
    assert "11/11 value-pinned" in fresh.stdout and "· complete" in fresh.stdout


def test_a_reach_past_the_budget_is_kept_under_its_own_code_through_the_cli(tmp_path):
    """--reach-budget 0: `h` lies beyond `f`'s file and its neighbour `g`, so `test_mixed` cannot be
    cleared and is kept, naming `h`; `test_f_zero` runs only `f` and is still removed."""
    root = _two_hop(tmp_path)
    run = _cli(root, "audit", "src/fmod.py::f", "--remove", "--reach-budget", "0", "--json")
    assert run.returncode == 0, run.stdout + run.stderr
    payload = json.loads(run.stdout)
    assert payload["removal"]["reach_budget"] == 0
    rows = {row["test"]: row for row in payload["removal"]["outcomes"]}
    assert (
        rows["tests/test_mixed.py::test_mixed"]["code"],
        rows["tests/test_mixed.py::test_mixed"]["subject"],
    ) == (
        "reach_over_budget",
        "src/hmod.py::h",
    )
    assert rows["tests/test_f.py::test_f_zero"]["code"] == "removed"
    assert (root / "tests" / "test_mixed.py").read_text().count("def test_mixed") == 1
