"""Design-warranted tests for Detective.decompose, mutation-driven to the ceiling.

Plain module-level helpers only (no fixtures).
"""

from __future__ import annotations

import ast

from Detective.decompose import (
    DecompositionPlan,
    ExtractionCandidate,
    _body_size,
    _is_extractable,
    _suggested_name,
    decompose,
)

_TWO_BLOCK = """
def process(data):
    for item in data:
        x = item + 1
        results.append(x)
    if data:
        total = sum(data)
        report(total)
    return results
"""


def _fn(src: str) -> ast.FunctionDef:
    node = ast.parse(src).body[0]
    assert isinstance(node, ast.FunctionDef)
    return node


# ── decompose ─────────────────────────────────────────────────────
def test_two_blocks_are_decomposable():
    plan = decompose(_fn(_TWO_BLOCK), "process", ("VALUE", "LOGICAL"))
    assert isinstance(plan, DecompositionPlan)
    assert plan.is_decomposable is True
    assert len(plan.candidates) == 2
    assert [c.kind for c in plan.candidates] == ["for", "if"]


def test_single_block_not_decomposable():
    plan = decompose(_fn("def f(x):\n if x:\n  a = 1\n  return a\n return 0"), "f")
    assert plan.is_decomposable is False and len(plan.candidates) == 1


def test_no_blocks_not_decomposable():
    plan = decompose(_fn("def f(a, b):\n return a + b"), "f")
    assert plan.candidates == () and plan.is_decomposable is False


def test_small_blocks_not_extractable():
    # each compound block owns a single statement -> not worth extracting
    plan = decompose(_fn("def f(x):\n if x:\n  return 1\n for y in x:\n  return 2"), "f")
    assert plan.candidates == ()


# ── candidate details ─────────────────────────────────────────────
def test_for_candidate_full():
    plan = decompose(_fn("def f(data):\n for item in data:\n  a = item\n  b = a + 1\n  results.append(b)"), "f")
    c = plan.candidates[0]
    assert c == ExtractionCandidate(
        kind="for",
        lineno=2,
        statement_count=3,
        suggested_name="process_item",
        reason="for block with 3 statements — a separable concern",
    )


def test_for_tuple_target_falls_back_to_items():
    plan = decompose(_fn("def f(pairs):\n for a, b in pairs:\n  x = a\n  y = b"), "f")
    assert plan.candidates[0].suggested_name == "process_items"


def test_if_and_generic_names():
    plan = decompose(_fn("def f(x):\n while x:\n  a = 1\n  x = a\n with x as fh:\n  d = fh\n  e = d"), "f")
    names = [c.suggested_name for c in plan.candidates]
    assert any(n.startswith("extract_while_line_") for n in names)
    assert any(n.startswith("extract_with_line_") for n in names)


def test_if_name():
    plan = decompose(_fn("def f(x):\n if x:\n  a = 1\n  b = 2\n return 0"), "f")
    assert plan.candidates[0].suggested_name.startswith("handle_case_line_")


# ── _body_size ────────────────────────────────────────────────────
def test_body_size_counts_orelse():
    assert _is_extractable(_fn("def f(x):\n if x:\n  a = 1\n else:\n  b = 2").body[0]) is True


def test_body_size_counts_handlers_and_finally():
    plan = decompose(_fn("def f():\n try:\n  a = 1\n except ValueError:\n  b = 2\n finally:\n  c = 3"), "f")
    assert len(plan.candidates) == 1
    assert plan.candidates[0].kind == "try" and plan.candidates[0].statement_count == 3


def test_body_size_direct():
    node = _fn("def f(x):\n for y in x:\n  a = 1\n  b = 2\n  c = 3")
    assert _body_size(node.body[0]) == 3


# ── _suggested_name / _is_extractable ─────────────────────────────
def test_suggested_name_for_while_with():
    while_stmt = _fn("def f(x):\n while x:\n  a = 1").body[0]
    assert _suggested_name("while", while_stmt) == "extract_while_line_2"


def test_is_extractable_rejects_simple_statement():
    assert _is_extractable(_fn("def f():\n return 1").body[0]) is False


# ── rationale ─────────────────────────────────────────────────────
def test_rationale_decomposable_with_categories():
    plan = decompose(_fn(_TWO_BLOCK), "process", ("VALUE", "LOGICAL"))
    assert plan.rationale == (
        "2 separable concerns (2 entangled categories: VALUE, LOGICAL) — "
        "extract each into a helper, then re-profile"
    )


def test_rationale_decomposable_without_categories():
    plan = decompose(_fn(_TWO_BLOCK), "process")
    assert plan.rationale == "2 separable concerns — extract each into a helper, then re-profile"


def test_rationale_not_decomposable():
    plan = decompose(_fn("def f(a):\n return a"), "f")
    assert plan.rationale == "fewer than 2 separable blocks — decomposition is unlikely to help"
