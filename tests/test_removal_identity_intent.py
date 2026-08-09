"""Intent tests for test-identity resolution in `audit --remove` (Detective #54).

`audit --remove` could not remove anything it proposed, and reported that as a SAFETY POLICY.

    DO THIS:  detective audit 'src/g.py::grade' --remove
    …
    skipped 15 — outside this function's editable test scope
                 (--remove edits only its own test file, never a cross-file test):
                 tests/detective/test_src_g_grade_60f85dc0a5_synth.py::test_grade_boundary_0, …

Every one of those was in the target's OWN generated file — the file converge had written
moments earlier. The sentence describes a deliberate scope rule; the cause was a string format
miss. `apply_removals` matched identifiers against a callable's `__name__`, while the audit
passes pytest nodeids (Wesker #16 made the nodeid the identity) and Wesker's explicitly
namespaced `legacy:<origin>::<base>[<case>]` fallback where collection yielded none.

MEASURED, the whole defect in two lines:

    apply_removals(..., ["tests/…::test_grade_boundary_0"])  -> removed=()      not_found=1
    apply_removals(..., ["test_grade_boundary_0"])           -> removed=(...)   not_found=0

THE WORST PART IS NOT THE NO-OP. A user reading "protected by policy" concludes the safety
check ran and held. It never ran. A failure that reports itself as a guarantee is strictly
worse than one that reports itself as an error, and it is why this file tests the REPORTED
REASON, not just the count.

`test_a_name_defined_in_another_file_is_still_refused` is the load-bearing one: the fix must
make removal work WITHOUT making it match more loosely. Resolving to a bare name alone would
delete whichever definition discovery happened to yield first.
"""

from __future__ import annotations

import shutil

import pytest

from Detective.suite_edit import (
    apply_removals,
    nodeid_file_hint,
    nodeid_function_name,
    nodeid_kind,
)

NODEID = "tests/detective/test_g_synth.py::test_boundary_0"
LEGACY = "legacy:tests/detective/test_g_synth.py::test_boundary_0"


# --------------------------------------------------------------------------------------
# The grammar, stated from what each spelling MEANS
# --------------------------------------------------------------------------------------


def test_every_spelling_resolves_to_the_same_function():
    """Five spellings, one function. Matching only the last of them was the defect."""
    for ident in (NODEID, LEGACY, "test_boundary_0", f"{NODEID}[case]", f"{LEGACY}[case]"):
        assert nodeid_function_name(ident) == "test_boundary_0", ident


def test_a_parametrized_row_is_not_a_function():
    """The function is alive — its other rows earn their keep — so it must never be deleted
    to get at one row."""
    assert nodeid_kind(f"{NODEID}[args6-F]") == "parametrized_case"
    assert nodeid_kind(NODEID) == "qualified"
    assert nodeid_kind("test_boundary_0") == "bare"
    assert nodeid_kind("") == "empty"


def test_a_qualified_identifier_names_its_file():
    assert nodeid_file_hint(NODEID) == "tests/detective/test_g_synth.py"
    assert nodeid_file_hint(LEGACY) == "tests/detective/test_g_synth.py"


def test_an_unqualified_identifier_names_no_file():
    """`?` is Wesker's explicit unknown-origin placeholder — it names no file, and treating it
    as one would look for a directory called '?'."""
    assert nodeid_file_hint("test_boundary_0") == ""
    assert nodeid_file_hint("legacy:?::test_boundary_0") == ""


# --------------------------------------------------------------------------------------
# Removal, end to end over a real file
# --------------------------------------------------------------------------------------


@pytest.fixture
def project(tmp_path, request, monkeypatch):
    """A project whose tests both IMPORT and EXERCISE the target.

    Both constraints are load-bearing, and each one failing looks exactly like the defect:

    * discovery finds tests that REACH the target, so a self-contained test file yields zero
      callables — nothing to locate, nothing removed;
    * discovery IMPORTS the test module, so the source must be importable, and the module names
      must be unique per test or `sys.modules` serves the previous test's tmp directory back.

    A fixture that satisfies neither produces `removed=()`, which is the exact symptom under
    test. That is how a green suite would certify a broken fix.
    """
    uniq = abs(hash(request.node.name)) % 10**8
    mod, stem = f"m{uniq}", f"test_s{uniq}"
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / f"{mod}.py").write_text(
        "def grade(score: int) -> str:\n    if score >= 90:\n        return 'A'\n    return 'F'\n"
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / f"{stem}.py").write_text(
        f"from {mod} import grade\n\n\n"
        "def test_boundary_0():\n    assert grade(90) == 'A'\n\n\n"
        "def test_keep():\n    assert grade(0) == 'F'\n"
    )
    (tmp_path / "pyproject.toml").write_text('[tool.pytest.ini_options]\ntestpaths = ["tests"]\n')
    monkeypatch.syspath_prepend(str(tmp_path / "src"))
    return tmp_path, mod, stem


def _run(bundle, names):
    root, mod, stem = bundle
    target = root / "tests" / f"{stem}.py"
    shutil.copy(target, root / "orig.py")
    try:
        return apply_removals(f"src/{mod}.py", str(root), [n.replace("__STEM__", stem) for n in names])
    finally:
        shutil.copy(root / "orig.py", target)


def _nodeid(bundle, suffix=""):
    return f"tests/{bundle[2]}.py::test_boundary_0{suffix}"


def test_a_nodeid_removes_the_test_it_names(project):
    """The exact regression."""
    report = _run(project, ["tests/__STEM__.py::test_boundary_0"])
    assert report.removed == (_nodeid(project),)
    assert report.not_found == ()


def test_the_legacy_namespaced_form_removes_it_too(project):
    report = _run(project, ["legacy:tests/__STEM__.py::test_boundary_0"])
    assert len(report.removed) == 1
    assert report.not_found == ()


def test_a_bare_name_still_works(project):
    """The one spelling that worked before must keep working."""
    report = _run(project, ["test_boundary_0"])
    assert report.removed == ("test_boundary_0",)


def test_a_name_defined_in_another_file_is_still_refused(project):
    """THE load-bearing test: making removal WORK must not make it match LOOSELY.

    The identifier names `tests/other.py`, which defines nothing here. Resolving to the bare
    name would find the real definition and delete a test the caller never asked about —
    deleting the wrong test is the one mistake this module must never make.
    """
    report = _run(project, ["tests/other.py::test_boundary_0"])
    assert report.removed == ()
    assert report.not_found == ("tests/other.py::test_boundary_0",)


def test_a_parametrized_row_is_set_aside_not_deleted(project):
    report = _run(project, ["tests/__STEM__.py::test_boundary_0[case]"])
    assert report.removed == ()
    assert report.parametrized == (_nodeid(project, "[case]"),)
    assert report.not_found == ()


def test_the_report_answers_in_the_spelling_it_was_asked_in(project):
    """The user was shown nodeids. A report naming bare functions reads as a different set of
    tests than the one they approved."""
    report = _run(project, ["tests/__STEM__.py::test_boundary_0"])
    assert report.removed == (_nodeid(project),)


# --------------------------------------------------------------------------------------
# One grammar, four consumers (Detective #13, #7, #54)
# --------------------------------------------------------------------------------------


def test_every_consumer_of_the_grammar_resolves_identically():
    """Four places compare a profile identifier against a bare `def` name, and all four had
    their own ad-hoc normalisation — or none:

      converge minimization   `n in names`              (raw nodeid vs rendered name)
      strip_foreign_evidence  `test.split("[")[0]`      (#7's guard — always False)
      _wanted_test_names      `t.split("[", 1)[0]`      (proof basis — no covering files)
      apply_removals          `call.__name__`           (#54 — --remove was a no-op)

    Two of them masked each other: the minimization never fired, so #7's inert guard never
    mattered, and the empty proof basis never showed because a generated file was always
    present. Fixing one at a time switches the others on. This asserts they share one
    derivation rather than four.
    """
    from Detective.decompose_apply import _wanted_test_names
    from Detective.minimize import strip_foreign_evidence

    ident = "tests/detective/test_x_synth.py::test_foo[args0-A]"
    assert nodeid_function_name(ident) == "test_foo"
    assert _wanted_test_names({"MUT_1": [ident]}) == {"test_foo"}
    matrix, lines = strip_foreign_evidence({"MUT_1": [ident]}, {ident: [1, 2]}, {"test_foo"})
    assert matrix == {"MUT_1": []}, "a foreign nodeid must be stripped, not silently kept"
    assert lines == {}


def test_a_row_suffix_alone_is_not_resolution():
    """The old normalisation stripped `[case]` and stopped, leaving `path::t` — which matches
    no `def` anywhere. Stripping the suffix is necessary and nowhere near sufficient."""
    ident = "tests/t.py::test_foo[case]"
    assert ident.split("[", 1)[0] != "test_foo"
    assert nodeid_function_name(ident) == "test_foo"
