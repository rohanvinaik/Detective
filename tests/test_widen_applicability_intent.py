"""Intent tests for the APPLICABILITY BOUND on test discovery (founder ruling 2026-09-05).

The defect, verbatim from the diagnosis: the speculative widen's stop rule declares a gap only once
its eligible list is exhausted, and EVERY collected test not statically naming the target was
eligible — so one unkillable survivor turned discovery into a whole-suite trace (1,584 single-test
widen steps for a one-line function whose live partition was 3 candidates and 1,812 tests with no
static path). The witness pass's capture harvest ran the same whole collection with no wall check
anywhere (a 51-minute silent phase, reproduced: `--deadline 60`, still running at 420 s).

What the fix is FOR, stated from intent:

- discovery is an EFFICIENCY device for the floor measurement — find the tests applicable to ONE
  function — never a proof of a negative over the suite; a test with no static path to the target is
  not consulted, and the count is disclosed on every surface (never an opt-in, never a silent drop);
- `file_peer` is dropped: a sibling test's name is no evidence about THIS item;
- the widen and the harvest obey ONE bound (`widen_admission`) through ONE router (`_route_tests`);
- the aggregate wall is a BACKSTOP on the harvest, checked between tests (`harvest_disposition`);
- a missed dynamic reacher under-counts the floor — one redundant generated test — never the ceiling,
  which is why the bound is certificate-safe.

Pins: the two pure decisions are hand truth tables (the in-repo exemption request, §14.9). The
end-to-end runs the REAL command on a fixture with 1,000 no-path tests: before the fix the widen
traced them one at a time and the 60 s wall cut the run; after it the run completes uncut and
reports the 1,000 as not consulted.
"""

from __future__ import annotations

import ast
import json
import os
import textwrap
import time
from pathlib import Path

import pytest

import Detective.engine as engine
from Detective.capture import (
    HARVEST,
    HARVEST_CUT,
    HARVEST_ENOUGH,
    capture_call_inputs,
    harvest_disposition,
)
from Detective.cli import main
from Detective.engine import NOT_CONSULTED, WIDEN, _applicable_harvest_pool, widen_admission

# ---------------------------------------------------------------- widen_admission (pure)

_ROUTE_CODES = (
    "caller_reaches",
    "file_peer",
    "unknown_dynamic",
    "unknown_no_path",
    "candidate_static",
    "candidate_fixture",
    "candidate_observed",
    "impossible_observed",
    "",
    "something_new",
)


@pytest.mark.parametrize("code", _ROUTE_CODES)
def test_only_a_caller_reacher_is_widened(code) -> None:
    expected = WIDEN if code == "caller_reaches" else NOT_CONSULTED
    assert widen_admission(code) == expected


def test_file_peer_is_not_consulted_by_ruling() -> None:
    # A SIBLING test naming the target is no evidence about this item (founder ruling 2026-09-05).
    assert widen_admission("file_peer") == NOT_CONSULTED


# ---------------------------------------------------------------- harvest_disposition (pure)


@pytest.mark.parametrize("have_enough", [False, True])
@pytest.mark.parametrize("deadline_passed", [False, True])
def test_harvest_disposition_enough_outranks_the_wall(have_enough, deadline_passed) -> None:
    expected = HARVEST_ENOUGH if have_enough else HARVEST_CUT if deadline_passed else HARVEST
    assert harvest_disposition(have_enough, deadline_passed) == expected


# ---------------------------------------------------------------- the harvest's wall backstop


def _target(x):
    return x + 1


def test_a_passed_deadline_runs_no_test_and_keeps_what_was_captured() -> None:
    ran: list[str] = []

    def t_a():
        ran.append("a")
        _target(1)

    def t_b():
        ran.append("b")
        _target(2)

    assert capture_call_inputs(_target, [t_a, t_b], deadline=time.monotonic() - 1.0) == []
    assert ran == []  # the wall had passed before the first test: nothing runs
    assert capture_call_inputs(_target, [t_a, t_b], deadline=time.monotonic() + 60.0) == [(1,), (2,)]
    assert capture_call_inputs(_target, [t_a, t_b]) == [(1,), (2,)]  # no wall: unchanged behaviour


def test_the_wall_is_checked_between_tests_not_inside_one() -> None:
    ran: list[str] = []
    deadline = time.monotonic() + 0.05

    def t_slow():
        ran.append("slow")
        time.sleep(0.1)  # crosses the wall INSIDE the test — the test completes, the next never starts
        _target(1)

    def t_next():
        ran.append("next")
        _target(2)

    assert capture_call_inputs(_target, [t_slow, t_next], deadline=deadline) == [(1,)]
    assert ran == ["slow"]


# ---------------------------------------------------------------- the applicable harvest pool

_TARGET_MOD = textwrap.dedent(
    """
    def leaf(x):
        return x * 2

    def caller(x):
        return leaf(x) + 1
    """
)


def _forget_modules(*prefixes: str) -> None:
    """Static discovery IMPORTS a fixture's package into this process's `sys.modules`; a later fixture
    reusing the name would then import the wrong tmp dir. Each fixture here has its own package name
    AND is forgotten after use — the two together keep the tests order-independent."""
    import sys

    for name in list(sys.modules):
        if any(name == p or name.startswith(p + ".") or name.startswith(p + "_") for p in prefixes):
            del sys.modules[name]


def _pool_repo(tmp_path: Path) -> Path:
    (tmp_path / "applic_pkg").mkdir()
    (tmp_path / "applic_pkg" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "applic_pkg" / "mod.py").write_text(_TARGET_MOD, encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\ntestpaths = ['tests']\npythonpath = ['.']\n", encoding="utf-8"
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_applic_names_leaf.py").write_text(
        "from applic_pkg.mod import leaf\n\n\ndef test_leaf():\n    assert leaf(2) == 4\n", encoding="utf-8"
    )
    (tests / "test_applic_names_caller.py").write_text(
        "from applic_pkg.mod import caller\n\n\ndef test_caller():\n    assert caller(2) == 5\n",
        encoding="utf-8",
    )
    (tests / "test_applic_no_path.py").write_text(
        "import applic_pkg.mod\n\n\ndef test_unrelated():\n    assert applic_pkg.mod is not None\n",
        encoding="utf-8",
    )
    return tmp_path


def test_the_harvest_pool_is_candidates_plus_callers_and_the_rest_is_counted(tmp_path) -> None:
    root = _pool_repo(tmp_path)
    full = str(root / "applic_pkg" / "mod.py")
    tree = ast.parse(Path(full).read_text(encoding="utf-8"))
    from Detective.engine import discover_test_callables, walk_functions
    from Detective.regime import resolve_regime

    try:
        names = [qn for qn, _ in walk_functions(tree)]
        tests = discover_test_callables(
            str(root), "applic_pkg/mod.py", names, testpaths=resolve_regime(str(root)).testpaths
        )
        # Outside a live session, static discovery is already function-routed: the no-path test is
        # never even proposed. Inside one, discovery returns the WHOLE collection — so load that test
        # as a real item and hand it to the pool the way the session would.
        assert sorted(t.__name__ for t in tests) == ["test_caller", "test_leaf"]
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "test_applic_no_path", root / "tests" / "test_applic_no_path.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        tests = [*tests, module.test_unrelated]
        leaf_node = next(n for n in tree.body if getattr(n, "name", "") == "leaf")
        exec_lines = set(engine._executable_lines(leaf_node))  # type: ignore[arg-type]
        pool, skipped = _applicable_harvest_pool(tests, str(root), full, tree, "leaf", exec_lines)
        got = sorted(getattr(t, "__name__", "?") for t in pool)
        assert got == ["test_caller", "test_leaf"]  # the candidate and the caller-reacher, nothing else
        assert skipped == 1  # test_unrelated: imports the module, names neither the target nor a caller
    finally:
        _forget_modules("applic_pkg", "test_applic")


# ---------------------------------------------------------------- end to end, through the real command

_FLIP = textwrap.dedent(
    """
    def flip(x: int) -> int:
        # `x < 0` -> `x <= 0` is EQUIVALENT (abs(0) == 0): a survivor no test can kill, so the
        # widen holds an obligation it can never discharge — the shape that exhausted the suite.
        return -x if x < 0 else x
    """
)


def _widen_repo(tmp_path: Path, n_files: int = 100, per_file: int = 10) -> Path:
    (tmp_path / "widenfix").mkdir()
    (tmp_path / "widenfix" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "widenfix" / "target.py").write_text(_FLIP, encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\ntestpaths = ['tests']\npythonpath = ['.']\n", encoding="utf-8"
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_widenfix_target.py").write_text(
        "from widenfix.target import flip\n\n\ndef test_neg():\n    assert flip(-3) == 3\n\n\n"
        "def test_pos():\n    assert flip(4) == 4\n",
        encoding="utf-8",
    )
    # Tests that IMPORT the module (import-graph reachable, so they are collected) but never name the
    # target or a caller: unknown_no_path. Each sleeps, so tracing or harvesting them is measurable —
    # 1,000 × 20 ms is 20 s traced and 20 s harvested, well past a 60 s wall once the profile passes
    # and the trace overhead are added; not consulting them is the only way the run stays uncut.
    for i in range(n_files):
        body = ["import time", "import widenfix.target", ""]
        for j in range(per_file):
            body += [
                f"def test_other_{i}_{j}():",
                "    time.sleep(0.02)",
                "    assert widenfix.target is not None",
                "",
            ]
        (tests / f"test_widenfix_other_{i:03d}.py").write_text("\n".join(body), encoding="utf-8")
    return tmp_path


def _converge_flip(root: Path, *extra: str) -> str:
    """Run the REAL command from the fixture root and return its stdout; forget the fixture's
    modules afterwards (the live session imports them into this process)."""
    import contextlib
    import io

    cwd = os.getcwd()
    buf = io.StringIO()
    try:
        os.chdir(root)
        with contextlib.redirect_stdout(buf):
            main(
                [
                    "converge",
                    "widenfix/target.py::flip",
                    "--project-root",
                    str(root),
                    "--deadline",
                    "60",
                    *extra,
                ]
            )
    finally:
        os.chdir(cwd)
        _forget_modules("widenfix", "test_widenfix")
    return buf.getvalue()


def test_converge_never_traces_the_no_path_tests_and_discloses_the_count(tmp_path) -> None:
    payload = json.loads(_converge_flip(_widen_repo(tmp_path), "--json"))
    # Uncut under a 60 s wall: the 1,000 no-path tests were neither widened nor harvested.
    assert payload["budget_exhausted"] is False and payload["cut_phase"] == "", payload.get("cut_phase")
    assert payload["not_consulted"] == 1000
    # The equivalent survivor is still reported honestly — as a candidate-equivalent, never a kill.
    assert payload["survivor_report"] is not None
    assert payload["functionally_complete"] is True  # complete MODULO the candidate-equivalent
    assert payload["exit_code"] in (0, 3)  # 3 only if the basis did not verify; never 1, never cut


def test_the_disclosure_reaches_the_human_report(tmp_path) -> None:
    out = _converge_flip(_widen_repo(tmp_path, n_files=3, per_file=2), "--full")
    assert "no static path to this function" in out and "6" in out
