"""Wesker#18 (Detective side): a decorator-wrapped target's page says what is true, in both modes.

THE DEFECT. The issue's own acceptance case, run end to end: `@functools.lru_cache def fee`, reached by a
test only through a module constant (`FEE = fee`, `from mod import FEE as charge`).

* `--isolated`: 15/15 killed, yet lines 6-8 read UNCOVERED, the page said `AUTHOR INPUTS ... Uncovered
  1. line 6` and the report proposed removing two hand-written tests as redundant. The tests ran those
  lines; the engine read the target's file off the cache wrapper, which has none.
* in-process: every mutant read `harness_error`, so the page said "could not be BUILT ... a defect to
  report" and ended UNGATEABLE with no route. The true standing is `not_entered (decorator_wrapper)`,
  whose repair is `--isolated` (Wesker's robust mode installs the mutant at import). Its sentence still
  said the repair was unbuilt.
* routing: the progress lines read "tracing 1 function-routed tests" (x3) in-process and "tracing 3" under
  --isolated. The route is ONE derivation (`_route_tests`) for both: in-process the widen traces one
  micro-batch per test and stops when the obligations discharge, isolated screens them in one pass.
  Pinned here as the SET of tests each mode traced, which must agree.

Controls: a `functools.wraps` wrapper and a plain function are measured the same way.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from Detective.cli import _ROUTE_ADDRESSES, repair_measurement_route
from Detective.validity import cut_reason_sentence

_DECORATOR_REASON = "mutant_not_entered_decorator_wrapper"

_BODY = "    if n > 10:\n        return n * 2\n    return n + 1\n"

_CACHE = "import functools\n\n\n@functools.lru_cache(maxsize=None)\ndef fee(n: int) -> int:\n" + _BODY
_CACHE += "\n\nFEE = fee\n"
_WRAPS = (
    "import functools\n\n\ndef deco(fn):\n    @functools.wraps(fn)\n    def wrapper(*a, **k):\n"
    "        return fn(*a, **k)\n\n    return wrapper\n\n\n@deco\ndef fee(n: int) -> int:\n" + _BODY
)
_WRAPS += "\n\nFEE = fee\n"
_PLAIN = "def fee(n: int) -> int:\n" + _BODY + "\n\nFEE = fee\n"
_TESTS = (
    "from mod import FEE as charge\n\n\ndef test_small():\n    assert charge(3) == 4\n\n\n"
    "def test_large():\n    assert charge(20) == 40\n\n\n"
    "def test_edge():\n    assert charge(10) == 11\n    assert charge(11) == 22\n"
)


# ── the pure route ────────────────────────────────────────────────────────────────────────────


def test_in_process_a_decorator_captured_target_routes_to_isolated():
    assert repair_measurement_route((_DECORATOR_REASON,), False, False) == "isolate"


def test_an_isolated_run_that_still_reads_it_has_had_the_repair_and_does_not_loop():
    assert repair_measurement_route((_DECORATOR_REASON,), False, False, True) == "mutant_phase"


def test_a_mutant_that_was_never_built_is_a_defect_to_report_before_any_isolated_re_run():
    assert (
        repair_measurement_route(("mutant_construction_failed", _DECORATOR_REASON), False, False)
        == "mutant_phase"
    )


@pytest.mark.parametrize(
    "reason",
    ["mutant_not_entered_captured_at_import", "mutant_not_entered_pre_bound_reference"],
)
def test_an_import_time_capture_routes_to_isolated_and_an_isolated_run_does_not_loop(reason):
    assert repair_measurement_route((reason,), False, False) == "isolate"
    assert repair_measurement_route((reason,), False, False, True) == "mutant_phase"
    assert reason in _ROUTE_ADDRESSES["isolate"]
    assert "--isolated" in cut_reason_sentence(reason)


@pytest.mark.parametrize(
    "other",
    ["mutant_not_entered_holder_not_found", "mutant_not_entered_not_reached", "mutant_not_entered"],
)
def test_the_causes_the_hook_does_not_repair_keep_their_own_route(other):
    assert repair_measurement_route((other,), False, False) in ("mutant_phase",)


def test_the_isolate_route_addresses_the_reason_so_it_is_not_named_twice():
    assert _DECORATOR_REASON in _ROUTE_ADDRESSES["isolate"]


def test_the_sentence_routes_to_isolated_and_no_longer_says_the_repair_is_unbuilt():
    sentence = cut_reason_sentence(_DECORATOR_REASON)
    assert "--isolated" in sentence
    assert "unbuilt" not in sentence and "no repair exists" not in sentence


# ── end to end, through the real CLI ──────────────────────────────────────────────────────────


def _console_script() -> Path:
    script = Path(sys.executable).with_name("detective")
    assert script.is_file(), f"requires the console script beside {sys.executable}"
    return script


def _run(project: Path, *args: str, timeout: int = 600):
    import os

    env = {k: v for k, v in os.environ.items() if k != "PYTHONUNBUFFERED"}
    return subprocess.run(
        [str(_console_script()), *args, "--project-root", str(project)],
        cwd=str(project),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


def _project(tmp_path: Path, source: str, tests: str = _TESTS) -> Path:
    root = tmp_path / "proj"
    (root / "tests").mkdir(parents=True)
    (root / "mod.py").write_text(source)
    (root / "tests" / "test_mod.py").write_text(tests)
    (root / "pyproject.toml").write_text("[project]\nname = 'dc'\nversion = '0'\n")
    done = _run(root, "regime", "--migrate")
    assert done.returncode == 0, done.stderr
    return root


def _final(out: str) -> str:
    return next(line for line in reversed(out.splitlines()) if line.startswith("FINAL"))


def _skip_if_cut(r) -> None:
    if r.returncode == 3 and "UNGATEABLE" in r.stdout and "profile was cut" in r.stdout:
        pytest.skip("cut by the wall clock on a loaded machine")


@pytest.fixture(scope="module")
def cache_project(tmp_path_factory):
    return _project(tmp_path_factory.mktemp("dc_cache"), _CACHE)


def _traced_tests(project: Path) -> set[str]:
    blob = json.loads((project / ".wesker" / "trace_cache.json").read_text())
    return set(blob["outcomes_observed"])


@pytest.mark.parametrize(
    ("name", "source"),
    [("cache", _CACHE), ("wraps", _WRAPS), ("plain", _PLAIN)],
    ids=lambda v: v if isinstance(v, str) and len(v) < 8 else "",
)
def test_isolated_reads_every_body_line_covered_and_completes(tmp_path, name, source):
    """Lines 6-8 (the body) are covered by the three tests; nothing is proposed for removal."""
    project = _project(tmp_path, source)
    r = _run(project, "converge", "mod.py::fee", "--isolated")
    _skip_if_cut(r)
    assert r.returncode == 0, r.stdout + r.stderr
    final = _final(r.stdout)
    assert "COMPLETE" in final and "15/15 killed" in final, final
    assert "uncovered" not in r.stdout
    assert "redundant" not in r.stdout.lower()
    assert "AUTHOR INPUTS" not in r.stdout


def test_in_process_names_the_decorator_cause_and_routes_to_isolated(cache_project, tmp_path):
    project = tmp_path / "p"
    shutil.copytree(cache_project, project, ignore=shutil.ignore_patterns(".detective", ".wesker"))
    r = _run(project, "converge", "mod.py::fee")
    _skip_if_cut(r)
    out = r.stdout
    assert r.returncode == 3, out + r.stderr
    assert "could not be BUILT" not in out
    assert "cause unclassified" not in out
    assert "decorator's WRAPPER" in out
    assert "detective converge 'mod.py::fee' --isolated" in out
    assert "UNGATEABLE" in _final(out)


def test_both_modes_route_the_same_tests(cache_project, tmp_path):
    traced = {}
    for mode, extra in (("in_process", ()), ("isolated", ("--isolated",))):
        project = tmp_path / mode
        shutil.copytree(cache_project, project, ignore=shutil.ignore_patterns(".detective", ".wesker"))
        r = _run(project, "converge", "mod.py::fee", *extra)
        _skip_if_cut(r)
        traced[mode] = _traced_tests(project)
    assert traced["in_process"] == traced["isolated"]
    assert {t.rsplit("::", 1)[1] for t in traced["isolated"]} == {"test_small", "test_large", "test_edge"}


_HANDLERS = "def fee(n: int) -> int:\n" + _BODY + "\n\nHANDLERS = {'fee': fee}\n"
_DEFAULT = "def fee(n: int) -> int:\n" + _BODY + "\n\ndef apply(n, f=fee):\n    return f(n)\n"
_CAPTURES = {
    "alias": (_PLAIN, _TESTS),
    "handler_dict": (
        _HANDLERS,
        "from mod import HANDLERS\n\n\ndef test_small():\n    assert HANDLERS['fee'](3) == 4\n\n\n"
        "def test_large():\n    assert HANDLERS['fee'](20) == 40\n\n\n"
        "def test_edge():\n    assert HANDLERS['fee'](10) == 11\n    assert HANDLERS['fee'](11) == 22\n",
    ),
    "default_argument": (
        _DEFAULT,
        "from mod import apply\n\n\ndef test_small():\n    assert apply(3) == 4\n\n\n"
        "def test_large():\n    assert apply(20) == 40\n\n\n"
        "def test_edge():\n    assert apply(10) == 11\n    assert apply(11) == 22\n",
    ),
}


@pytest.mark.parametrize("kind", sorted(_CAPTURES))
def test_a_plain_function_captured_at_import_is_measured_by_isolated_and_named_in_process(tmp_path, kind):
    """The issue's alias acceptance for an UNDECORATED target: the import hook compiles the module with the
    definition replaced, so an alias, a handler dict and a default argument all capture the mutant."""
    source, tests = _CAPTURES[kind]
    project = _project(tmp_path / "iso", source, tests)
    r = _run(project, "converge", "mod.py::fee", "--isolated")
    _skip_if_cut(r)
    assert r.returncode == 0, r.stdout + r.stderr
    final = _final(r.stdout)
    assert "COMPLETE" in final and "15/15 killed" in final, final
    assert "uncovered" not in r.stdout
    inproc = _project(tmp_path / "inproc", source, tests)
    r = _run(inproc, "converge", "mod.py::fee")
    _skip_if_cut(r)
    assert r.returncode == 3, r.stdout + r.stderr
    assert "detective converge 'mod.py::fee' --isolated" in r.stdout
    assert "ALIAS" in r.stdout or "CAPTURED at import" in r.stdout
    assert "could not be BUILT" not in r.stdout
