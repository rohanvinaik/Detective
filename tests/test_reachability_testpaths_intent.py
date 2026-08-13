"""Collection is bounded to pytest's declared testpaths (Fix A for the ARC .venv312 leak).

Defect: `reachable_test_paths` builds its test universe by walking the whole repo root and
calling any `test_*.py` a test. `_SKIP_DIRS` lists `.venv` but no name-based list can enumerate
every virtualenv dir (`.venv312`, `.venv-3.12`, …), and an installed dependency's suite is often
OPAQUE (imports importlib / plugins), so `_reaches` returns True and admits it. On ARC that put
736 `.venv312` `test_*.py` into the traced baseline for a 13-line function — the suite-global
trace scaling with the whole machine, not the function.

Intent: consume pytest's authoritative boundary. A `test_*.py` outside every declared testpath is
FOREIGN and never collected; when reachability cannot narrow, the collection FLOOR is the declared
testpaths (pytest's own suite), never the whole repo; and a project that declares NO testpaths is
byte-identical to before. Written from intent — the `*_synth` golden only pins current behaviour.
"""

from __future__ import annotations

import os

from Detective.reachability import reachable_test_paths, within_declared_testpaths


def test_within_declared_testpaths_names_three_states():
    assert within_declared_testpaths("tests/test_x.py", []) == "unrestricted"  # nothing declared
    assert within_declared_testpaths("tests/test_x.py", ["tests"]) == "within"
    assert within_declared_testpaths("tests", ["tests"]) == "within"  # exact dir match
    assert within_declared_testpaths(".venv312/lib/test_y.py", ["tests"]) == "foreign"
    # No false prefix: 'testsuite' is not under 'tests'.
    assert within_declared_testpaths("testsuite/test_x.py", ["tests"]) == "foreign"


def _arc_repo(tmp_path):
    """An ARC-shaped tree: real src+tests, plus an OPAQUE installed-dependency suite under .venv312."""
    (tmp_path / "src" / "story").mkdir(parents=True)
    (tmp_path / "src" / "story" / "__init__.py").write_text("")
    (tmp_path / "src" / "story" / "hypothesis.py").write_text("def hypothesis(x):\n    return x + 1\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_story.py").write_text(
        "from src.story.hypothesis import hypothesis\n\ndef test_h():\n    assert hypothesis(1) == 2\n"
    )
    # opaque local test (imports importlib) — must still be KEPT: it is within testpaths.
    (tmp_path / "tests" / "test_opaque.py").write_text(
        "import importlib\n"
        "from src.story.hypothesis import hypothesis\n\n"
        "def test_h2():\n    assert hypothesis(2) == 3\n"
    )
    venv = tmp_path / ".venv312" / "lib" / "python3.12" / "site-packages" / "foolib"
    venv.mkdir(parents=True)
    for i in range(3):
        # OPAQUE (importlib) so pre-fix reachability admits them, as ARC's dependency tests were.
        (venv / f"test_foo{i}.py").write_text("import importlib\n\ndef test_dep():\n    assert True\n")
    return str(tmp_path)


def _rels(root, paths):
    return sorted(os.path.relpath(p, root) for p in paths) if paths is not None else None


def test_foreign_opaque_dependency_tests_are_admitted_without_testpaths_and_excluded_with():
    # Regression guard: proves the leak exists (BEFORE) and the fix closes it (AFTER), in one test.
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = _arc_repo(__import__("pathlib").Path(td))
        common = dict(target_module="src.story.hypothesis", import_roots=(root,))
        before = reachable_test_paths(root, "src/story/hypothesis.py", **common)
        after = reachable_test_paths(root, "src/story/hypothesis.py", testpaths=("tests",), **common)
        assert sum(".venv312" in p for p in before) == 3  # the leak: 3 foreign tests admitted
        assert not any(".venv312" in p for p in after)  # fix: none admitted
        # Both real tests (including the opaque local one) survive — narrowing, not over-pruning.
        assert _rels(root, after) == ["tests/test_opaque.py", "tests/test_story.py"]


def test_floor_is_testpaths_when_reachability_cannot_narrow():
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = _arc_repo(__import__("pathlib").Path(td))
        # A target not in the graph would return None (whole-repo) without a floor; with testpaths
        # declared it returns the declared dirs — pytest's own suite, never the whole tree.
        floored = reachable_test_paths(
            root,
            "src/story/missing.py",
            target_module="src.story.missing",
            import_roots=(root,),
            testpaths=("tests",),
        )
        assert _rels(root, floored) == ["tests"]


def test_no_declared_testpaths_is_byte_identical_none_fallback():
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = _arc_repo(__import__("pathlib").Path(td))
        # Undetermined target, NO testpaths declared -> None (collect everything), exactly as before.
        assert (
            reachable_test_paths(
                root, "src/story/missing.py", target_module="src.story.missing", import_roots=(root,)
            )
            is None
        )
