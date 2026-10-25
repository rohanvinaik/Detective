"""D#129 — a module whose relative imports need a package is named, loaded and routed by that package.

THE DEFECT (reproduced 2026-10-25 on Detective 5723410, Wesker 1addf57). A namespace layout — no
``__init__.py`` in ``tools/`` or ``tools/voice/`` — with ``pythonpath = ["src", "tools/voice"]`` and a
module ``tools/voice/references.py`` that does ``from .metrics import …``. Every one of Detective's
derivations of a file's dotted name produced the bare ``references``: ``regime`` reported
``module: "references"`` and called the setup clean, while ``diagnose`` STOPped with "the live original
could not be loaded: ImportError: attempted relative import with no known parent package" and told the
reader to install a missing dependency. Under ``references`` the module can never load: its relative
imports have no parent package.

THE CONTRACT. One override, applied by every consumer to its own name (``module_identity``): a file
with no relative imports, or a name deep enough for them, keeps the name it has today. A file whose
relative imports need a deeper package takes the namespace name under the deepest import root that
gives them one (``tools.voice.references``) — routing's own deepest-root rule. Regime, the generated
tests' import line, routing and the loader all agree, and the loaded module's ``__package__`` lets a
FUNCTION-level relative import run too (Wesker #46's shape).

The override is advisory and must never be the thing that fails: a source it cannot read or parse,
for any reason, leaves the consumer's own name standing, and the load reports the real failure.
"""

from __future__ import annotations

import os
import sys
import textwrap

import pytest

from Detective.module_identity import (
    loader_identity,
    module_identity_name,
    namespace_candidates,
    project_identity,
    relative_import_level,
)

NS = ["tools", "voice", "references"]
ROOTS = ["", "src", "tools/voice"]


# ── the decision ─────────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("current", ["references", "pkg.mod", "a.b.c"])
def test_without_relative_imports_every_name_stands(current):
    assert module_identity_name(current, NS, ROOTS, 0) == ("current", current, "")


def test_a_regular_package_deep_enough_keeps_its_name():
    # tools/voice/ has __init__.py, tools/ does not: the walk gives voice.references, deep enough.
    assert module_identity_name("voice.references", NS, ROOTS, 1) == ("current", "voice.references", "")


def test_a_namespace_module_takes_the_name_its_relative_imports_need():
    assert module_identity_name("references", NS, ROOTS, 1) == ("namespace", "tools.voice.references", "")


def test_a_two_level_relative_import_needs_a_grandparent():
    assert module_identity_name("voice.references", NS, ROOTS, 2) == (
        "namespace",
        "tools.voice.references",
        "",
    )


def test_no_root_gives_a_parent_so_the_name_stands_and_says_why():
    # A top-level script with `from . import x`: nothing anywhere can load it as a package member.
    assert module_identity_name("script", ["script"], [""], 1) == ("no_package_context", "script", "")


def test_of_two_valid_names_the_deepest_root_wins():
    # src/tools/voice/references.py under roots "" and "src": both `tools.voice.references` and
    # `src.tools.voice.references` give `from .x` a parent. Routing names a file from its deepest
    # root, so the override does too — and never reads the suite to break the tie (§11).
    parts = ["src", "tools", "voice", "references"]
    assert module_identity_name("references", parts, ["", "src"], 1) == (
        "namespace",
        "tools.voice.references",
        "src",
    )
    assert module_identity_name("references", parts, ["src", ""], 1)[1] == "tools.voice.references"


@pytest.mark.parametrize("current", ["pkg", "pkg.__init__"])
def test_a_package_init_is_judged_as_the_package_it_names(current):
    # Routing strips `__init__` ("pkg"), the loader keeps it ("pkg.__init__"); both are deep enough
    # for `from . import x` inside the package itself.
    assert module_identity_name(current, ["pkg", "__init__"], [""], 1)[0] == "current"


def test_candidates_are_ordered_deepest_root_first_and_filtered_by_depth():
    assert namespace_candidates(NS, ROOTS, 1) == [["tools.voice.references", ""]]
    assert namespace_candidates(NS, ROOTS, 0) == [
        ["references", "tools/voice"],
        ["tools.voice.references", ""],
    ]
    assert namespace_candidates(["elsewhere", "x"], ["src"], 0) == []
    # A package's own name is the directory: `a/b/__init__.py` is `a.b`, and a bare `__init__`
    # at a root names no package at all.
    assert namespace_candidates(["a", "b", "__init__"], [""], 1) == [["a.b", ""]]
    assert namespace_candidates(["__init__"], [""], 1) == []
    # Inside a package's `__init__`, `from .. import x` needs only the package's own parent: `a.b`
    # (two components) satisfies level 2, where a MODULE `a/b.py` would need three.
    assert namespace_candidates(["a", "b", "__init__"], [""], 2) == [["a.b", ""]]
    assert namespace_candidates(["a", "b"], [""], 2) == []
    assert namespace_candidates(["a", "b", "__init__"], [""], 3) == []


@pytest.mark.parametrize(
    ("source", "level"),
    [
        ("", 0),
        ("x = 1\n", 0),
        ("import os\nfrom os import path\n", 0),
        ("from . import a\n", 1),
        ("from ..b import c\n", 2),
        ("def f():\n    from .m import n\n    return n\n", 1),
        ("from . import a\ndef f():\n    from ...deep import x\n", 3),
    ],
)
def test_the_relative_import_level_counts_function_level_imports_too(source, level):
    assert relative_import_level(source) == level


@pytest.mark.parametrize(
    "source",
    [
        pytest.param("def broken(:\n", id="syntax-error"),
        pytest.param("x = 1\x00\n", id="null-byte"),
        # CPython's parser reports these as MemoryError ("Parser stack overflowed") and
        # RecursionError ("Stack overflow during compilation"), not SyntaxError.
        pytest.param("-" * 100_000 + "1", id="too-deep-for-the-parser"),
        pytest.param("1+" * 200_000 + "1", id="too-deep-for-the-compiler"),
    ],
)
def test_an_unparsable_source_has_level_zero_and_never_raises(source):
    assert relative_import_level(source) == 0


# ── the consumers, on a real tree ────────────────────────────────────────────────────────────────


def _namespace_project(tmp_path, with_routed_test=True):
    (tmp_path / "src").mkdir()
    voice = tmp_path / "tools" / "voice"
    voice.mkdir(parents=True)
    (voice / "metrics.py").write_text(
        "METRICS_VERSION = 3\n\n\ndef number(text):\n    return len(text.split())\n"
    )
    (voice / "references.py").write_text(
        textwrap.dedent(
            """
            from .metrics import METRICS_VERSION, number


            def partition_verdict(text, limit):
                if not text:
                    return "empty"
                if number(text) > limit:
                    return "long"
                return "short"


            def versioned(text):
                from .metrics import number as count

                return f"v{METRICS_VERSION}:{count(text)}"
            """
        )
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    if with_routed_test:
        (tests / "test_references.py").write_text(
            "from tools.voice.references import partition_verdict\n\n\n"
            "def test_verdict():\n    assert partition_verdict('a b', 2) == 'short'\n"
        )
    (tests / "test_metrics.py").write_text(
        "from metrics import number\n\n\ndef test_number():\n    assert number('a b c') == 3\n"
    )
    (tmp_path / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\npythonpath = ["src", "tools/voice"]\ntestpaths = ["tests"]\n'
    )
    return tmp_path


def test_project_identity_names_the_namespace_module_under_the_project_root(tmp_path):
    root = _namespace_project(tmp_path)
    ident = project_identity(str(root), "tools/voice/references.py", "references")
    assert (ident.code, ident.name, ident.import_root) == ("namespace", "tools.voice.references", str(root))
    # A sibling with no relative imports keeps its name.
    assert project_identity(str(root), "tools/voice/metrics.py", "metrics").name == "metrics"


def test_the_import_roots_come_from_the_config_pytest_actually_reads(tmp_path):
    # pytest.ini outranks pyproject.toml, and its pythonpath is one whitespace-split string. Read
    # through regime's single config reader: a pyproject-only re-read would see neither.
    pkg = tmp_path / "lib" / "ns"
    pkg.mkdir(parents=True)
    (pkg / "helper.py").write_text("X = 1\n")
    (pkg / "mod.py").write_text("from .helper import X\n")
    (tmp_path / "pytest.ini").write_text("[pytest]\npythonpath = lib\n")
    (tmp_path / "pyproject.toml").write_text('[tool.pytest.ini_options]\npythonpath = ["elsewhere"]\n')
    ident = project_identity(str(tmp_path), "lib/ns/mod.py", "mod")
    assert (ident.name, ident.import_root) == ("ns.mod", os.path.join(str(tmp_path), "lib"))


def test_a_src_layout_package_keeps_its_name(tmp_path):
    pkg = tmp_path / "src" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "helper.py").write_text("X = 1\n")
    (pkg / "mod.py").write_text("from .helper import X\n\n\ndef f():\n    return X\n")
    (tmp_path / "pyproject.toml").write_text('[tool.pytest.ini_options]\npythonpath = ["src"]\n')

    from Detective.reachability import module_name
    from Detective.synthesis.oracle_light import importable_module

    assert importable_module("src/pkg/mod.py", str(tmp_path)) == "pkg.mod"
    assert module_name(str(tmp_path), str(pkg / "mod.py"), (str(tmp_path / "src"),)) == "pkg.mod"


def test_a_source_in_a_declared_encoding_is_read_and_an_undecodable_one_never_raises(tmp_path):
    voice = tmp_path / "tools" / "voice"
    voice.mkdir(parents=True)
    (voice / "latin.py").write_bytes(
        b"# -*- coding: latin-1 -*-\nfrom .metrics import number\nNAME = '\xe9t\xe9'\n"
    )
    (voice / "broken.py").write_bytes(b"from .metrics import number\nNAME = '\xff\xfe'\n")
    (voice / "bogus.py").write_bytes(b"# -*- coding: no-such-codec -*-\nfrom . import x\n")
    root = str(tmp_path)
    assert project_identity(root, "tools/voice/latin.py", "latin").name == "tools.voice.latin"
    # Undecodable as UTF-8, or an unknown codec: no level can be read, so the name stands.
    assert project_identity(root, "tools/voice/broken.py", "broken").code == "current"
    assert project_identity(root, "tools/voice/bogus.py", "bogus").code == "current"


def test_regime_and_the_generated_import_line_use_the_namespace_name(tmp_path):
    root = _namespace_project(tmp_path)
    from Detective.regime import resolve_regime
    from Detective.synthesis.oracle_light import _import_line, importable_module

    assert resolve_regime(str(root), "tools/voice/references.py").module == "tools.voice.references"
    assert importable_module("tools/voice/references.py", str(root)) == "tools.voice.references"
    assert (
        _import_line("tools/voice/references.py", "partition_verdict", str(root))
        == "from tools.voice.references import partition_verdict"
    )
    # Unchanged where nothing needed a package.
    assert importable_module("tools/voice/metrics.py", str(root)) == "metrics"


def test_a_conftest_keeps_the_name_pytest_gives_it(tmp_path):
    # pytest imports a conftest ITSELF, by the `__init__` walk, and never applies the namespace
    # override: a conftest in a non-package directory is `conftest`, relative import or not, and the
    # regime's collision check must predict pytest's name, not the one generated tests would use.
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "conftest.py").write_text("from . import helpers\n")
    from Detective.regime import _conftest_module
    from Detective.synthesis.oracle_light import importable_module

    assert _conftest_module(str(tmp_path), str(tmp_path / "tests" / "conftest.py")) == "conftest"
    assert importable_module("tests/conftest.py", str(tmp_path)) == "tests.conftest"


def test_routing_reaches_the_namespace_module_and_keeps_the_sibling_edge(tmp_path):
    root = _namespace_project(tmp_path)
    from Detective.reachability import module_name, reachable_test_paths

    roots = (str(root / "src"), str(root / "tools" / "voice"))
    target = str(root / "tools" / "voice" / "references.py")
    assert module_name(str(root), target, roots) == "tools.voice.references"
    kept = reachable_test_paths(str(root), target, import_roots=roots, testpaths=("tests",)) or []
    assert any(p.endswith("test_references.py") for p in kept)
    # metrics.py is reached by test_references.py THROUGH references' relative import, spelled
    # `tools.voice.metrics` there and keyed `metrics` in the graph: the edge must survive.
    metrics = str(root / "tools" / "voice" / "metrics.py")
    kept_m = reachable_test_paths(str(root), metrics, import_roots=roots, testpaths=("tests",)) or []
    assert any(p.endswith("test_references.py") for p in kept_m)
    assert any(p.endswith("test_metrics.py") for p in kept_m)


@pytest.fixture
def isolated_import_state():
    path_before = list(sys.path)
    modules_before = set(sys.modules)
    yield
    sys.path[:] = path_before
    for name in set(sys.modules) - modules_before:
        sys.modules.pop(name, None)


def test_the_loader_imports_the_namespace_module_with_a_real_package(tmp_path, isolated_import_state):
    root = _namespace_project(tmp_path, with_routed_test=False)
    from Detective.engine import _load_failure_reason, _load_original

    # The live session puts the project root on sys.path; the loader reads what it can import.
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "tools" / "voice"))
    fn = _load_original(str(root / "tools" / "voice" / "references.py"), "partition_verdict")
    assert fn is not None, "the namespace module could not be loaded"
    assert fn.__globals__["__name__"] == "tools.voice.references"
    assert fn.__globals__["__package__"] == "tools.voice"
    assert fn("a b c", 2) == "long"
    # W#46's shape: a FUNCTION-level relative import runs once the package context is right.
    versioned = _load_original(str(root / "tools" / "voice" / "references.py"), "versioned")
    assert versioned("a b") == "v3:2"
    # The failure-reason probe imports by the same name, so it finds nothing to report.
    assert _load_failure_reason(str(root / "tools" / "voice" / "references.py")) is None


def test_the_loader_matches_a_symlinked_path_entry_and_keeps_its_spelling(tmp_path, isolated_import_state):
    (tmp_path / "real").mkdir()
    real_root = _namespace_project(tmp_path / "real", with_routed_test=False)
    link = tmp_path / "link"
    link.symlink_to(real_root, target_is_directory=True)
    target = str(real_root / "tools" / "voice" / "references.py")
    # sys.path names the root through the link; the target is named by its real path.
    ident = loader_identity(target, "references", [str(link)])
    assert (ident.code, ident.name, ident.import_root) == ("namespace", "tools.voice.references", str(link))

    from Detective.engine import _load_original

    sys.path.insert(0, str(link))
    fn = _load_original(target, "versioned")
    assert fn is not None and fn("a b c") == "v3:3"
    assert sys.path.count(str(link)) == 1, "the root was re-added under another spelling"


def test_a_namespace_name_that_resolves_to_another_file_is_never_measured(tmp_path, isolated_import_state):
    # Two portions of one namespace package: `other/tools/voice/references.py` precedes the project on
    # sys.path, so `tools.voice.references` imports THAT file. Measuring it would measure another
    # program; the loader must refuse it rather than return its function.
    (tmp_path / "proj").mkdir()
    root = _namespace_project(tmp_path / "proj", with_routed_test=False)
    other = tmp_path / "other" / "tools" / "voice"
    other.mkdir(parents=True)
    (other / "references.py").write_text("def partition_verdict(text, limit):\n    return 'IMPOSTOR'\n")
    from Detective.engine import _load_original

    target = str(root / "tools" / "voice" / "references.py")
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(tmp_path / "other"))
    fn = _load_original(target, "partition_verdict")
    assert fn is None or os.path.samefile(fn.__code__.co_filename, target)


def test_a_module_that_needs_no_package_still_loads_by_its_old_route(tmp_path, isolated_import_state):
    (tmp_path / "flat_mod.py").write_text("def f(x):\n    return x + 1\n")
    from Detective.engine import _load_original

    fn = _load_original(str(tmp_path / "flat_mod.py"), "f")
    assert fn is not None and fn(1) == 2


def test_the_loader_reads_an_empty_path_entry_as_the_working_directory(tmp_path, monkeypatch):
    root = _namespace_project(tmp_path, with_routed_test=False)
    monkeypatch.chdir(root)
    target = str(root / "tools" / "voice" / "references.py")
    ident = loader_identity(target, "references", ["", b"/not/a/str", 42])
    assert (ident.code, ident.name) == ("namespace", "tools.voice.references")
    assert os.path.realpath(ident.import_root) == os.path.realpath(str(root))
