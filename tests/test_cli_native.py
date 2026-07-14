"""Tests for Detective.cli pure helpers (mutation-driven).

``main`` dispatches into the engine (heavy); it is verified by a standalone run,
not here. The arg parsing and formatting helpers are pure and covered to the
ceiling. Plain helpers only (no fixtures).
"""

from __future__ import annotations

import pytest

from Detective.cli import _boundary_hint, _build_parser, _format_scope, _split_target
from Detective.scope import KillQuality, ScopeMap, Specification


# ── _split_target ─────────────────────────────────────────────────
def test_split_target_file_and_function():
    assert _split_target("a/b.py::func") == ("a/b.py", "func")


def test_split_target_dotted_method():
    assert _split_target("m::C.method") == ("m", "C.method")


def test_split_target_rejects_missing_separator():
    with pytest.raises(SystemExit):
        _split_target("nofunc")


def test_split_target_rejects_empty_sides():
    with pytest.raises(SystemExit):
        _split_target("::f")
    with pytest.raises(SystemExit):
        _split_target("f.py::")


# ── _format_scope ─────────────────────────────────────────────────
def _scope(regime="A", surviving=None, warning=None, by_a=6, by_c=2):
    return ScopeMap(
        function="m::f",
        regime=regime,
        surviving_categories=surviving or [],
        specification=Specification(10, 8, 2, 0, 3),
        kill_quality=KillQuality(by_a, by_c, warning),
        behavioral_dof=[],
    )


def test_format_scope_core_lines_exact():
    assert _format_scope(_scope()) == (
        "m::f  [regime A]\n"
        "  10 variants; 8 pinned, 2 unspecified, 0 inert\n"
        "  kill quality: 6 value-assertion, 2 crash\n"
        "  in plain terms:\n"
        "    → 2 behavior(s) no test pins yet — run `converge` to generate tests for them"
    )


def test_format_scope_shows_warning():
    out = _format_scope(_scope(warning="crash-dominated: pins RUNS not returns"))
    assert "⚠ crash-dominated: pins RUNS not returns" in out


def test_format_scope_no_warning_no_marker():
    assert "⚠" not in _format_scope(_scope(warning=None))


def test_format_scope_lists_surviving_categories():
    out = _format_scope(_scope(regime="B", surviving=["VALUE", "TYPE"]))
    assert "surviving categories: VALUE, TYPE" in out


def test_format_scope_omits_categories_when_none():
    assert "surviving categories" not in _format_scope(_scope())


# ── _build_parser ─────────────────────────────────────────────────
def test_parser_diagnose_defaults():
    args = _build_parser().parse_args(["diagnose", "a.py::f"])
    assert args.command == "diagnose" and args.target == "a.py::f"
    assert args.project_root == "." and args.json is False


def test_parser_reports_version():
    with pytest.raises(SystemExit) as exc:
        _build_parser().parse_args(["--version"])
    assert exc.value.code == 0


def test_parser_rejects_removed_certify_command():
    # certify is no longer a CLI command (converge supersedes it); argparse must reject it
    with pytest.raises(SystemExit):
        _build_parser().parse_args(["certify", "a.py::f"])


def test_parser_requires_a_command():
    with pytest.raises(SystemExit):
        _build_parser().parse_args([])


# ── _boundary_hint (BOUNDARY residual: the distinguishing input is the equality edge) ──
def _ds(orig: str, mut: str) -> str:
    """A diff_summary in the '- <whole original>\\n+ <whole mutant>' form the engine emits."""
    return f"- def f(x):\n    {orig}\n+ def f(x):\n    {mut}"


def test_boundary_hint_names_the_equality_edge():
    h = _boundary_hint(_ds("return x > 10", "return x >= 10"))
    assert h == "distinguish at the boundary — supply an input where x == 10"


def test_boundary_hint_handles_lt_to_lte():
    h = _boundary_hint(_ds("return a < b", "return a <= b"))
    assert h is not None and "a == b" in h


def test_boundary_hint_handles_a_ternary():
    h = _boundary_hint(_ds("y = 1 if x > 5 else 0", "y = 1 if x >= 5 else 0"))
    assert h is not None and "x == 5" in h


def test_boundary_hint_none_for_operand_swap_not_a_boundary():
    # a SWAP (operands reordered) is not a strict↔non-strict shift → no boundary hint
    assert _boundary_hint(_ds("return a > b", "return b > a")) is None


def test_boundary_hint_none_for_non_comparison_mutation():
    assert _boundary_hint(_ds("return x + 1", "return x - 1")) is None
