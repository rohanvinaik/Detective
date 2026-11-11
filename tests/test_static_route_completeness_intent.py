"""Static routing finds the tests that reach a function through names it does not itself carry
(Detective #107, #77 items 3 and 5).

The defect: a test that reaches its target only through a helper in its own module (`_call(x)` -> `f(x)`),
an alias (`g = f`, `from m import f as g`), or a module constant (`LENSES[0].vote(...)`) was routed as "no
static path" and NOT consulted, so a fresh audit reported a line that test executes as uncovered, asked
`converge` to write a test over it, and read a different suite size than a warm trace cache did (23 vs 19).
Routing is a cost optimisation over the truth ("which tests execute this function"), so a static miss may
never be read as "no test".

These tests run the real CLI cold (no caches) and warm-sibling (`.detective/` cleared, `.wesker/` kept), on
the issue's own shape and its edge shapes: a helper two levels deep, a helper in another test module, a
re-export through a package `__init__`, a registry built at import, a class-attribute constant, a
`functools.partial`, `getattr` with a literal name (static evidence, consulted), `getattr` with a computed
name (undecidable: NOT consulted, and NAMED — never "uncovered"), and a target with no tests at all.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from Detective.audit import missing_line_standing
from Detective.engine import unconsulted_standing
from Detective.reachability import file_role, module_bindings, reacher_names

_TARGET = """\
def f(x):
    if x > 10:
        return "big"
    return "small"
"""

_PLAIN = """\
def test_small():
    assert f(1) == "small"


def test_small_again():
    assert f(2) == "small"
"""

_HEAD = "from pkg.m import f\n\n"

# name -> (target-module extra source, {test-file name: source}, package __init__ source)
_SHAPES = {
    "helper": (
        "",
        {
            "test_m.py": _HEAD
            + "def _call(x):\n    return f(x)\n\n\ndef test_big():\n    assert _call(50) == 'big'\n"
        },
        "",
    ),
    "helper_two_deep": (
        "",
        {
            "test_m.py": _HEAD
            + "def _inner(x):\n    return f(x)\n\n\ndef _run(x):\n    return _inner(x)\n\n\n"
            + "def test_big():\n    assert _run(50) == 'big'\n"
        },
        "",
    ),
    "helper_in_other_module": (
        "",
        {
            "helpers.py": "from pkg.m import f\n\n\ndef call(x):\n    return f(x)\n",
            "test_m.py": "import helpers\n\n\ndef test_big():\n    assert helpers.call(50) == 'big'\n",
        },
        "",
    ),
    "alias_in_target": (
        "g = f\n",
        {"test_m.py": "from pkg.m import g\n\n\ndef test_big():\n    assert g(50) == 'big'\n"},
        "",
    ),
    "import_as_alias": (
        "",
        {"test_m.py": "from pkg.m import f as g\n\n\ndef test_big():\n    assert g(50) == 'big'\n"},
        "",
    ),
    "reexport_via_init": (
        "",
        {"test_m.py": "from pkg import pf\n\n\ndef test_big():\n    assert pf(50) == 'big'\n"},
        "from .m import f as pf\n",
    ),
    "registry_at_import": (
        "import types\n\nLENSES = (types.SimpleNamespace(vote=f),)\n",
        {
            "test_m.py": "from pkg.m import LENSES\n\n\ndef test_big():\n"
            "    assert LENSES[0].vote(50) == 'big'\n"
        },
        "",
    ),
    "dict_registry": (
        "REGISTRY = {}\nREGISTRY['f'] = f\n",
        {
            "test_m.py": "from pkg.m import REGISTRY\n\n\ndef test_big():\n"
            "    assert REGISTRY['f'](50) == 'big'\n"
        },
        "",
    ),
    "class_attribute": (
        "class Holder:\n    vote = staticmethod(f)\n",
        {"test_m.py": "from pkg.m import Holder\n\n\ndef test_big():\n    assert Holder.vote(50) == 'big'\n"},
        "",
    ),
    "partial": (
        "import functools\n\nbig = functools.partial(f, 50)\n",
        {"test_m.py": "from pkg.m import big\n\n\ndef test_big():\n    assert big() == 'big'\n"},
        "",
    ),
    "getattr_literal": (
        "",
        {"test_m.py": "from pkg import m\n\n\ndef test_big():\n    assert getattr(m, 'f')(50) == 'big'\n"},
        "",
    ),
}

_DYNAMIC = {
    "test_m.py": "from pkg import m\n\n\ndef test_big_by_computed_name():\n"
    "    name = chr(102)\n    assert getattr(m, name)(50) == 'big'\n"
}

_PYPROJECT = '[tool.pytest.ini_options]\npythonpath = ["src", "tests"]\ntestpaths = ["tests"]\n'


def _run(cwd: Path, *argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "Detective", *argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
        env=dict(os.environ),
    )


def _project(tmp_path: Path, extra: str, tests: dict[str, str], init: str, plain: bool = True) -> Path:
    project = tmp_path / "proj"
    (project / "src" / "pkg").mkdir(parents=True)
    (project / "tests").mkdir()
    (project / "pyproject.toml").write_text(_PYPROJECT)
    (project / "src" / "pkg" / "__init__.py").write_text(init)
    (project / "src" / "pkg" / "m.py").write_text(_TARGET + "\n\n" + extra)
    for name, source in tests.items():
        (project / "tests" / name).write_text(source)
    if plain:
        (project / "tests" / "test_plain.py").write_text("from pkg.m import f\n\n\n" + _PLAIN)
    assert _run(project, "regime", "--migrate", "--project-root", str(project)).returncode == 0
    return project


def _audit(project: Path, keep_wesker: bool = True) -> dict:
    cache = project / ".detective"
    for name in ("verdict_cache.json", "pins.json"):
        (cache / name).unlink(missing_ok=True)
    if not keep_wesker:
        (project / ".wesker" / "trace_cache.json").unlink(missing_ok=True)
    done = _run(project, "audit", "src/pkg/m.py::f", "--json")
    return json.loads(done.stdout)


@pytest.mark.parametrize("shape", sorted(_SHAPES))
def test_a_test_reaching_the_target_through_a_name_is_consulted_cold_and_warm(tmp_path, shape):
    extra, tests, init = _SHAPES[shape]
    project = _project(tmp_path, extra, tests, init)
    cold = _audit(project, keep_wesker=False)
    warm = _audit(project)
    again = _audit(project, keep_wesker=False)
    assert cold["missing_lines"] == [], "the big branch is executed by the named-route test"
    assert cold["test_count"] == warm["test_count"] == again["test_count"]
    assert cold["test_count"] >= 3
    assert cold["not_consulted_dynamic"] == []


def test_a_test_dispatching_by_a_computed_name_is_named_not_consulted_never_uncovered(tmp_path):
    project = _project(tmp_path, "", _DYNAMIC, "")
    report = _audit(project, keep_wesker=False)
    assert report["not_consulted_dynamic"], "the undecidable test is NAMED"
    assert report["not_consulted_dynamic"][0].endswith("test_big_by_computed_name")
    standings = dict(map(tuple, report["missing_line_standings"]))
    assert standings.get(3) == "unconsulted", standings
    assert "unexecuted" not in standings.values()
    page = _run(project, "audit", "src/pkg/m.py::f").stdout
    assert "✗ uncovered" not in page
    assert "not consulted" in page and "test_big_by_computed_name" in page


def test_a_target_with_no_test_at_all_still_reads_as_no_test(tmp_path):
    project = _project(tmp_path, "", {}, "", plain=False)
    (project / "tests" / "test_other.py").write_text("def test_unrelated():\n    assert 1 + 1 == 2\n")
    report = _audit(project, keep_wesker=False)
    assert report["not_consulted_dynamic"] == []
    assert report["missing_lines"], "no test reaches the target: its lines stay uncovered"
    assert {s for _, s in report["missing_line_standings"]} == {"unexecuted"}


# ── the pure decisions ────────────────────────────────────────────────────────────────────────────────


def test_module_bindings_separate_code_that_calls_from_names_that_hold():
    got = module_bindings(
        "g = f\nX = f(1)\nP = partial(f, 2)\nL = (Lens(vote=f),)\nREG.update(a=f)\n"
        "import a.b as ab\nfrom m import f as h\n"
        "def helper(x):\n    return f(x)\n"
        "class C:\n    v = f\n"
    )
    refs, defs = got["refs"], got["defs"]
    assert refs["g"] == ["f"] and refs["P"] == ["f"] and "f" in refs["L"]
    assert "X" not in refs or "f" not in refs["X"], "a call's RESULT is not a reference"
    assert "f" in refs["REG"] and refs["h"] == ["f"] and refs["C"] == ["f"] and refs["v"] == ["f"]
    assert "f" in defs["helper"]


def test_unparseable_source_has_no_bindings():
    assert module_bindings("def (:") == {"defs": {}, "refs": {}}


def test_closure_follows_test_side_functions_but_not_other_modules_functions():
    modules = [
        {"role": "support", "defs": {"_run": ["_inner"], "_inner": ["f"]}, "refs": {}},
        {"role": "other", "defs": {"prod_caller": ["f"]}, "refs": {"alias": ["f"]}},
    ]
    assert reacher_names(["f"], modules) == ["_inner", "_run", "alias"]


def test_closure_edge_cases():
    assert reacher_names(["f"], []) == []
    assert reacher_names([], [{"role": "target", "defs": {"a": ["b"]}, "refs": {}}]) == []
    cyc = [{"role": "target", "defs": {"a": ["b"], "b": ["a", "f"]}, "refs": {}}]
    assert reacher_names(["f"], cyc) == ["a", "b"]


def test_file_role(tmp_path):
    t = str(tmp_path / "src" / "m.py")
    assert file_role(t, t, ()) == "target"
    assert file_role(str(tmp_path / "tests" / "conftest.py"), t, ()) == "support"
    assert file_role(str(tmp_path / "tests" / "helpers.py"), t, (str(tmp_path / "tests"),)) == "support"
    assert file_role(str(tmp_path / "pkg" / "x.py"), t, (str(tmp_path / "tests"),)) == "other"


def test_unconsulted_standing_codes():
    assert unconsulted_standing(["getattr"], ["f"], ["m"], ["f"], "m") == "named_by_string"
    assert unconsulted_standing(["getattr"], [], ["m"], ["f"], "m") == "dynamic"
    assert unconsulted_standing(["getattr"], [], ["other"], ["f"], "m") == "no_path"
    assert unconsulted_standing(["x"], [], ["m"], ["f"], "m") == "no_path"


def test_a_line_with_no_runner_is_unconsulted_only_when_dynamic_tests_were_not_consulted():
    assert missing_line_standing(3, {}, [], [], ["t::dyn"]) == "unconsulted"
    assert missing_line_standing(3, {}, [], [], []) == "unexecuted"
    assert missing_line_standing(3, {}, [], []) == "unexecuted"
    assert missing_line_standing(3, {"t": [3]}, ["t"], [], ["t::dyn"]) == "run_by_failing"
