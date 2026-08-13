"""The import-graph walk never descends into a virtualenv (Slice 0 of Fix B; the 34s ARC pre-parse).

Defect: `_build_graph` walks the whole repo root and `ast.parse`s every `.py` it finds, pruning
only by name (`_SKIP_DIRS`/`norecursedirs`). An installed dependency's sources under `.venv312/`
(or any non-`.venv` venv name) were therefore OPENED and parsed before their tests were rejected —
measured on ARC as 34s across two reachability calls, a cost paid before pytest even starts.

Intent: a directory holding `pyvenv.cfg` is authoritatively a Python virtualenv (PEP 405), whatever
its name. The walk prunes that subtree without parsing anything inside it — the authoritative-
boundary principle applied to the walk, so no name list is needed and no dependency source is read.
"""

from __future__ import annotations

from Detective.reachability import _build_graph, is_virtualenv_root


def test_is_virtualenv_root_keys_on_the_pep405_marker():
    assert is_virtualenv_root(["pyvenv.cfg", "bin", "lib"]) is True
    assert is_virtualenv_root(["setup.py", "src"]) is False
    assert is_virtualenv_root([]) is False


def _repo(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "mod.py").write_text("def target(x):\n    return x + 1\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_mod.py").write_text(
        "from src.mod import target\n\ndef test_t():\n    assert target(1) == 2\n"
    )
    # A virtualenv under a NON-.venv name, with a dependency source + test inside it.
    venv = tmp_path / ".venv312"
    (venv / "lib" / "python3.12" / "site-packages" / "dep").mkdir(parents=True)
    (venv / "pyvenv.cfg").write_text("home = /usr/bin\nversion = 3.12.0\n")
    (venv / "lib" / "python3.12" / "site-packages" / "dep" / "big.py").write_text(
        "x = 1\n" * 5000  # a heavy source the walk must NOT open
    )
    (venv / "lib" / "python3.12" / "site-packages" / "dep" / "test_dep.py").write_text(
        "def test_dep():\n    assert True\n"
    )
    return str(tmp_path)


def test_build_graph_does_not_parse_anything_under_a_virtualenv(tmp_path):
    root = _repo(tmp_path)
    graph, paths, opaque = _build_graph(root, (root,))
    # The real tree is parsed into the graph...
    assert "src.mod" in paths
    assert "tests.test_mod" in paths
    # ...and NOTHING under the .venv312 subtree is (name-agnostic: keyed on pyvenv.cfg).
    assert not any(".venv312" in p for p in paths.values())
