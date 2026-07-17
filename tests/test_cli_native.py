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
def _scope(regime="A", surviving=None, warning=None, by_a=6, by_c=2, inert=0):
    return ScopeMap(
        function="m::f",
        regime=regime,
        surviving_categories=surviving or [],
        specification=Specification(10, 8, 2, inert, 3),
        kill_quality=KillQuality(by_a, by_c, warning),
        behavioral_dof=[],
    )


def test_format_scope_core_lines_exact():
    # Every term carries its own gloss: a first-time reader meets this block BEFORE the
    # "in plain terms" layer, so "regime A", "inert" and "value-assertion" cannot be the
    # only words on offer. `0 inert` is omitted entirely rather than shown as jargon
    # whose value is zero.
    assert _format_scope(_scope()) == (
        "m::f — diagnose · 10 behaviours · 8 pinned · 2 unpinned\n"
        "\n"
        "  ✓ pinned             6 pin the RETURN VALUE · 2 only prove it runs\n"
        "  ✗ unpinned           2 · —\n"
        "  · shape              cohesive and structurally one piece\n"
        "\n"
        "DO THIS:  detective converge 'm::f'\n"
        "          Writes tests for the 2 behaviour(s) nothing pins yet."
    )


def test_format_scope_names_inert_freedom_when_present():
    out = _format_scope(_scope(inert=3))
    assert "3 — no test could ever tell the difference" in out


def test_format_scope_shows_warning():
    out = _format_scope(_scope(warning="crash-dominated: pins RUNS not returns"))
    assert "⚠ crash-dominated: pins RUNS not returns" in out


def test_format_scope_no_warning_no_marker():
    assert "⚠" not in _format_scope(_scope(warning=None))


def test_format_scope_lists_surviving_categories():
    out = _format_scope(_scope(regime="B", surviving=["VALUE", "TYPE"]))
    assert "2 · VALUE, TYPE" in out


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


# ── --version names the ENGINE too ───────────────────────────────────
def test_engine_version_reports_the_installed_engine():
    """A verdict is a joint product: Detective decides what to ask, the ENGINE decides what
    the answer is. `engine.profile` keys its verdict cache on the engine version for exactly
    that reason — so "detective 0.5.4" alone does not identify what produced a report, and two
    installs printing it can legitimately disagree."""
    import Wesker

    from Detective.cli import _engine_version

    assert _engine_version() == f"Wesker {Wesker.__version__}"


def test_engine_version_distinguishes_missing_from_unversioned(monkeypatch):
    """The two causes are not interchangeable. A single catch-all reported `NOT INSTALLED`
    for an engine sitting in site-packages that merely predates `__version__` — the wrong
    cause, stated confidently, in the one string a bug report is meant to be able to trust."""
    import Wesker

    from Detective.cli import _engine_version

    monkeypatch.delattr(Wesker, "__version__", raising=False)
    assert _engine_version() == "Wesker version UNKNOWN"


def test_version_string_never_raises(monkeypatch):
    """`--version` is asked most often when something is already broken; a traceback there is
    a worse answer than naming the breakage."""
    import builtins

    from Detective.cli import _engine_version

    real = builtins.__import__

    def _boom(name, *a, **k):
        if name == "Wesker":
            raise ImportError("gone")
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", _boom)
    assert _engine_version() == "Wesker NOT IMPORTABLE"
