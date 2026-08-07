"""Tests for Detective.cli pure helpers (mutation-driven).

``main`` dispatches into the engine (heavy); it is verified by a standalone run,
not here. The arg parsing and formatting helpers are pure and covered to the
ceiling. Plain helpers only (no fixtures).
"""

from __future__ import annotations

import ast

import pytest

from Detective.audit import SuiteAudit
from Detective.cli import (
    _boundary_hint,
    _build_parser,
    _differs_at_eq,
    _format_audit,
    _format_scope,
    _headline,
    _mutated_stmt,
    _split_target,
    _survivor_lines,
)
from Detective.equivalence import MutantVerdict
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
        # The rule is the BARRIER between the live `▸` progress stream and the report. Without
        # it they are one wall and the narration reads as findings.
        "─" * 78 + "\n"
        "m::f — diagnose · 10 behaviours · 8 pinned · 2 unpinned\n"
        "\n"
        # #40: value-pinned and run-only are TWO rows — a crash/timeout kill proves the code runs,
        # not what it returns, so it never sits under the checked "pinned" gutter.
        "  ✓ value-pinned       6 pin the RETURN VALUE\n"
        "  · run-only           2 crash/timeout detection(s) — return value still unspecified\n"
        "  ✗ unpinned           2 · —\n"
        "  · shape              cohesive and structurally one piece\n"
        "\n"
        # ONE action, and it is a command you can paste — never a description of a task.
        "DO THIS:  detective converge 'm::f'\n"
        "\n"
        "  · Why                2 behaviour(s) have no test pinning them.\n"
        "  · Writes             test files, and wires them into pytest for you."
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


def test_boundary_hint_none_for_a_direction_flip_that_agrees_at_the_edge():
    # `<=` → `>=` is a DIRECTION flip, not an edge shift: both are True at `x == 0`, so the
    # equality edge is the one input that CANNOT distinguish them. Emitting the hint anyway
    # asked for that exact input, made no progress, and re-derived the same ask forever.
    assert _boundary_hint(_ds("return x <= 0", "return x >= 0")) is None


def test_boundary_hint_none_when_both_operators_are_strict():
    # `<` → `>`: both False at the edge — they agree there too.
    assert _boundary_hint(_ds("return x < 0", "return x > 0")) is None


def test_boundary_hint_fires_for_a_flip_that_does_differ_at_the_edge():
    # `<=` → `>`: True vs False at `x == 0`. A direction flip, but exactly one side holds at
    # the edge, so the edge really does distinguish them — the rule is about equality, not
    # about direction.
    h = _boundary_hint(_ds("return x <= 0", "return x > 0"))
    assert h is not None and "x == 0" in h


# ── _differs_at_eq (THE rule every boundary hint rests on) ────────
@pytest.mark.parametrize(
    "op, m_op, expected",
    [
        (ast.LtE, ast.Lt, True),  # strict↔non-strict: the real edge shift
        (ast.Gt, ast.GtE, True),
        (ast.LtE, ast.Gt, True),  # flips still count when one side holds at ==
        (ast.LtE, ast.GtE, False),  # both hold at == → agree there
        (ast.Lt, ast.Gt, False),  # neither holds at == → agree there
        (ast.LtE, ast.LtE, False),  # same operator cannot differ anywhere
        (ast.Eq, ast.LtE, False),  # not an ordering comparison at all
    ],
)
def test_differs_at_eq_is_exactly_the_strict_vs_non_strict_split(op, m_op, expected):
    assert _differs_at_eq(op, m_op) is expected


def test_differs_at_eq_is_symmetric():
    # The caller matches original→mutant, but the relation is about the PAIR.
    assert _differs_at_eq(ast.LtE, ast.Lt) == _differs_at_eq(ast.Lt, ast.LtE)


# ── _mutated_stmt / _survivor_lines (the grouped survivor block) ──
def _v(mid: str, cat: str, orig: str, mut: str) -> MutantVerdict:
    return MutantVerdict(mid, cat, _ds(orig, mut), killable=False, witness=None, searched=14)


def test_mutated_stmt_names_the_ORIGINAL_line_so_survivors_group_by_branch():
    assert _mutated_stmt(_ds("if x <= 0: pass", "if x < 0: pass")) == "if x <= 0: pass"


def test_survivor_lines_verbose_keeps_every_id():
    # `flag` takes an id, so the verbose form must never drop one.
    vs = [_v("M1", "BOUNDARY", "if x <= 0: pass", "if x < 0: pass")]
    out = "\n".join(_survivor_lines(vs, verbose=True))
    assert "M1" in out and "BOUNDARY" in out


def test_survivor_lines_grouped_collapses_one_branch_into_one_row():
    # Three mutants of the SAME statement is the shape that makes a real function's residual a
    # wall: one row, one count, not three near-identical diffs.
    vs = [
        _v("M1", "BOUNDARY", "if x <= 0: pass", "if x < 0: pass"),
        _v("M2", "BOUNDARY", "if x <= 0: pass", "if x == 0: pass"),
        _v("M3", "VALUE", "if x <= 0: pass", "if x <= 1: pass"),
    ]
    out = _survivor_lines(vs, verbose=False)
    rows = [ln for ln in out if "if x <= 0" in ln]
    assert len(rows) == 1
    assert "3" in rows[0]  # the count
    assert "2 BOUNDARY" in rows[0] and "1 VALUE" in rows[0]


def test_survivor_lines_grouped_drops_the_ids_but_says_where_they_went():
    vs = [_v("M1", "BOUNDARY", "if x <= 0: pass", "if x < 0: pass")]
    out = "\n".join(_survivor_lines(vs, verbose=False))
    assert "M1" not in out
    assert "--verbose" in out  # a dropped id must be recoverable, and say so


def test_survivor_lines_grouped_keeps_the_boundary_hint():
    # The hint is the only ACTIONABLE part of the block; grouping may cost ids, never actions.
    vs = [_v("M1", "BOUNDARY", "if x <= 0: pass", "if x < 0: pass")]
    out = "\n".join(_survivor_lines(vs, verbose=False))
    assert "x == 0" in out


def test_survivor_lines_grouped_orders_the_biggest_cluster_first():
    vs = [
        _v("M1", "VALUE", "return x + 1", "return x + 2"),
        _v("M2", "BOUNDARY", "if x <= 0: pass", "if x < 0: pass"),
        _v("M3", "BOUNDARY", "if x <= 0: pass", "if x == 0: pass"),
    ]
    rows = [ln for ln in _survivor_lines(vs, verbose=False) if ln.startswith("    ") and "↳" not in ln]
    assert "if x <= 0" in rows[0]  # 2 mutants beats 1 — the worst branch leads


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


# ── the import line a generated test inherits ────────────────────────
def test_target_ns_names_the_module_a_reader_would_type(tmp_path):
    """`_load_original` imports the target under a SYNTHETIC name (`_detective_uut_x`) when it
    is not already in sys.modules, so the live `__name__` is an artifact of that loader. A
    generated test that inherits it reads `from _detective_uut_billing import Account`, fails
    collection, takes the whole proof suite red — and decompose then reports `REJECTED: the
    suite PROVES this extraction changes behaviour` for an extraction that is perfectly sound.
    A false verdict, sourced from an import line."""
    from Detective.cli import _target_ns

    (tmp_path / "billing.py").write_text(
        "class Account:\n    def __init__(self, tier):\n        self.tier = tier\n\n\n"
        "def settle(account):\n    return account.tier\n"
    )
    ns = _target_ns("billing.py", "settle", str(tmp_path))
    assert "Account" in ns  # the class is in scope, so --input can name it
    assert ns["__name__"] == "billing"  # NOT _detective_uut_billing
    assert not ns["__name__"].startswith("_detective_uut")


# ── _headline (a command's one-liner, as its --help description) ──
def test_headline_preserves_the_emphasis_the_string_carries():
    # THE regression. `.capitalize()` lower-cases everything after the first character, so
    # "an EXISTING suite" became "an existing suite" and "PROVEN behavior-preserving" became
    # "proven" — the shouted words ARE the claim, and they were silently eaten.
    #
    # The grid cannot find this: it offers "", "a", "abc", and `.capitalize()` agrees with
    # `s[0].upper() + s[1:]` on every string that has no interior capital. So the distinguishing
    # input is the one thing Detective asked for and could not invent.
    assert _headline("assess an EXISTING suite") == "Assess an EXISTING suite."
    assert _headline("split it — applied only when PROVEN safe") == (
        "Split it — applied only when PROVEN safe."
    )


def test_headline_sentence_cases_the_first_character():
    assert _headline("write a suite") == "Write a suite."


def test_headline_wraps_to_the_terminal():
    # These pages use RawDescriptionHelpFormatter, which wraps `help=` but never a
    # `description` — so the same string that fits in the command list ran to 89 columns on its
    # own page. Every line must fit.
    long = "start here for a FUNCTION — what does it actually do, and what to run next (read-only)"
    assert all(len(line) <= 78 for line in _headline(long).splitlines())
    assert "FUNCTION" in _headline(long)  # wrapping must not cost the emphasis either


# ── _difference_region (the full boundary table, not just strict↔non-strict) ──
def test_boundary_hint_gte_collapsed_to_eq_names_the_strict_side():
    # `>=` → `==` AGREES at the edge (both True), so the edge hint would send the search to
    # the one region that cannot answer. They differ exactly on the strict side the mutation
    # cut off — one past the boundary.
    h = _boundary_hint(_ds("if x >= 10: pass", "if x == 10: pass"))
    assert h == "distinguish at the boundary — supply an input where x > 10"


def test_boundary_hint_lte_collapsed_to_eq_names_the_strict_side():
    h = _boundary_hint(_ds("if x <= 10: pass", "if x == 10: pass"))
    assert h is not None and "x < 10" in h


def test_boundary_hint_strict_vs_eq_is_the_edge():
    # `>` → `==` DISAGREES at the edge (False vs True), so the edge hint stands there.
    h = _boundary_hint(_ds("if x > 10: pass", "if x == 10: pass"))
    assert h is not None and "x == 10" in h


# ── crash-only rendering: detection claimed per mutant, never for the bucket ──
def test_survivor_lines_verbose_names_the_crash_witness_when_no_test_reaches_it():
    from Detective.equivalence import Witness

    v = MutantVerdict(
        "M1",
        "BOUNDARY",
        _ds("if x < 0: raise ValueError('neg')", "if x <= 0: raise ValueError('neg')"),
        killable=False,
        witness=None,
        searched=14,
        crash_only=True,
        crash_witness=Witness((0,), "5.99", "<raised ValueError: neg>"),
        suite_detected=False,
    )
    out = "\n".join(_survivor_lines([v], verbose=True))
    assert "reached by no current test" in out
    assert "f(0)" in out


def test_survivor_lines_verbose_no_witness_line_when_the_suite_already_detects():
    from Detective.equivalence import Witness

    v = MutantVerdict(
        "M1",
        "BOUNDARY",
        _ds("if x < 0: raise ValueError('neg')", "if True: raise ValueError('neg')"),
        killable=False,
        witness=None,
        searched=14,
        crash_only=True,
        crash_witness=Witness((0,), "5.99", "<raised ValueError: neg>"),
        suite_detected=True,
    )
    out = "\n".join(_survivor_lines([v], verbose=True))
    assert "reached by no current test" not in out


# ── issue #8: the residual's TYPE survives to the reader ────────────────────────
# `risk > 4` over a derived local is an INTERNAL condition; presenting it as a
# direct input requirement hands the reader a predicate no call satisfies
# literally. Parameter-only comparisons keep the actionable form; everything
# else renders as certified abstention. param_names=None keeps history exact.


def test_boundary_hint_param_only_comparison_stays_actionable():
    h = _boundary_hint(_ds("return x > 10", "return x >= 10"), param_names=("x",))
    assert h == "distinguish at the boundary — supply an input where x == 10"


def test_boundary_hint_derived_local_becomes_internal_condition():
    h = _boundary_hint(_ds("if risk > 4: pass", "if risk >= 4: pass"), param_names=("weight", "tax"))
    assert h is not None
    assert h.startswith("internal condition `risk == 4`")
    assert "supply an input where" not in h


def test_boundary_hint_mixed_operands_are_internal():
    # one side a parameter, the other a local: still not directly satisfiable
    h = _boundary_hint(_ds("if total > cap: pass", "if total >= cap: pass"), param_names=("cap",))
    assert h is not None and h.startswith("internal condition ")


def test_boundary_hint_without_param_names_is_byte_identical_history():
    with_none = _boundary_hint(_ds("if risk > 4: pass", "if risk >= 4: pass"))
    assert with_none == "distinguish at the boundary — supply an input where risk == 4"


def test_boundary_hint_constant_only_comparison_is_param_scope():
    # no names at all: vacuously parameter-only, keeps the actionable form
    h = _boundary_hint(_ds("if 3 > 2: pass", "if 3 >= 2: pass"), param_names=("x",))
    assert h is not None and h.startswith("distinguish at the boundary")


# ── issue #1: the least-informed target mistake gets the most help ──────────────


def test_missing_separator_on_a_real_file_hands_back_the_menu(tmp_path):
    (tmp_path / "spine.py").write_text("def sections():\n    pass\n\ndef role_spine():\n    pass\n")
    with pytest.raises(SystemExit) as exc:
        _split_target("spine.py", str(tmp_path))
    msg = str(exc.value)
    assert msg.startswith("detective: target must be 'file.py::function'")
    assert "functions in that file: sections, role_spine" in msg
    assert "'spine.py::sections'" in msg


def test_missing_separator_on_nothing_keeps_the_bare_format_message(tmp_path):
    with pytest.raises(SystemExit) as exc:
        _split_target("spien.py", str(tmp_path))
    msg = str(exc.value)
    assert msg == "detective: target must be 'file.py::function', got 'spien.py'"


# ── issue #10: audit --remove must not recommend itself ─────────────────────────


def _audit_report(**over) -> SuiteAudit:
    base = dict(
        function="p.py::f",
        test_count=4,
        kill_pct=100.0,
        mutant_complete=True,
        line_complete=True,
        redundant_tests=("test_f_extra",),
        failing_tests=(),
        killable_gaps=(),
        missing_lines=(),
        minimal_test_count=3,
    )
    base.update(over)
    return SuiteAudit(**base)


def test_plain_audit_still_recommends_remove():
    out = _format_audit(_audit_report())
    assert "DO THIS:  detective audit 'p.py::f' --remove" in out


def test_audit_remove_mode_does_not_recommend_itself():
    out = _format_audit(_audit_report(), removing=True)
    assert "--remove" not in out.split("· Removing")[0] or "DO THIS" not in out
    assert "DO THIS:  detective audit" not in out
    assert "· Removing" in out  # the measurement still says what is happening


# ── review finding 3: parameter operands alone do not make a region path-complete ──


def test_boundary_hint_dominated_param_comparison_abstains():
    # `weight == 10` beneath `if enabled:` omits `enabled` from the recipe — abstain
    orig = "def f(enabled, weight):\n    if enabled:\n        if weight > 10:\n            pass"
    mut = "def f(enabled, weight):\n    if enabled:\n        if weight >= 10:\n            pass"
    h = _boundary_hint(f"- {orig}\n+ {mut}", param_names=("enabled", "weight"))
    assert h is not None and h.startswith("internal condition `weight == 10` sits behind")
    assert "supply an input where" not in h


def test_boundary_hint_top_level_param_comparison_still_promotes():
    h = _boundary_hint(_ds("return x > 10", "return x >= 10"), param_names=("x",))
    assert h == "distinguish at the boundary — supply an input where x == 10"


def test_boundary_hint_short_circuit_position_abstains():
    # the second operand of `and` evaluates conditionally
    h = _boundary_hint(_ds("return x and y > 5", "return x and y >= 5"), param_names=("x", "y"))
    assert h is not None and "sits behind enclosing control flow" in h


def test_boundary_hint_first_boolop_operand_still_promotes():
    h = _boundary_hint(_ds("return y > 5 and x", "return y >= 5 and x"), param_names=("x", "y"))
    assert h is not None and h.startswith("distinguish at the boundary")


# ── issue #8 round 2: sequential predecessors are control flow too ──────────────


def test_boundary_hint_abstains_when_a_predecessor_may_return():
    # `if enabled: return False` before the comparison: the recipe must not read
    # as sufficient without enabled=False
    orig = "def f(enabled, weight):\n    if enabled:\n        return False\n    return weight > 10"
    mut = "def f(enabled, weight):\n    if enabled:\n        return False\n    return weight >= 10"
    h = _boundary_hint(f"- {orig}\n+ {mut}", param_names=("enabled", "weight"))
    assert h is not None and "sits behind enclosing control flow" in h
    assert "supply an input where" not in h


def test_boundary_hint_unconditional_predecessor_assignment_still_promotes():
    orig = "def f(weight):\n    unit = 1\n    return weight > 10"
    mut = "def f(weight):\n    unit = 1\n    return weight >= 10"
    h = _boundary_hint(f"- {orig}\n+ {mut}", param_names=("weight",))
    assert h is not None and h.startswith("distinguish at the boundary")


def test_boundary_hint_predecessor_raise_blocks_promotion():
    orig = "def f(weight):\n    if weight is None:\n        raise ValueError\n    return weight > 10"
    mut = "def f(weight):\n    if weight is None:\n        raise ValueError\n    return weight >= 10"
    h = _boundary_hint(f"- {orig}\n+ {mut}", param_names=("weight",))
    assert h is not None and "sits behind enclosing control flow" in h
