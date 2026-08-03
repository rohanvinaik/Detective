"""Native tests for Detective.line_flags — the line-unreachability oracle (issue #9).

The store's regression contract, from the issue: a flag closes ONLY its line residual;
mutation-completeness is byte-for-byte unchanged by it; observed execution overrides it;
editing the statement (or moving it to another function) orphans it; identical statements
in different functions never alias; decompose still requires its mutation-completeness
proof (the proof gate never reads this store — pinned by construction: `decompose_apply`
imports nothing from `line_flags`).
"""

from __future__ import annotations

import ast
import textwrap

from Detective.line_flags import (
    add_line_flag,
    classify_missing_lines,
    clean_orphaned_flags,
    flag_statuses,
    load_line_flags,
    remove_line_flag,
    resolve_statement,
    stmt_identity,
)

_SRC = """\
def clamp(values):
    total = 0
    for v in values:
        total += max(v, 0)
    if total < 0:
        total = -1
    return total
"""


def _node(src: str = _SRC) -> ast.FunctionDef:
    fn = ast.parse(textwrap.dedent(src)).body[0]
    assert isinstance(fn, ast.FunctionDef)
    return fn


def test_flag_closes_only_its_line_residual(tmp_path):
    node = _node()
    add_line_flag(str(tmp_path), "c.py::clamp", node, 6, note="total is never negative")
    still, manual, contradicted = classify_missing_lines(
        str(tmp_path), "c.py::clamp", node, [6, 7], covered=set()
    )
    assert still == [7]
    assert manual == [6]
    assert contradicted == []


def test_execution_overrides_the_flag(tmp_path):
    node = _node()
    add_line_flag(str(tmp_path), "c.py::clamp", node, 6)
    still, manual, contradicted = classify_missing_lines(str(tmp_path), "c.py::clamp", node, [], covered={6})
    assert manual == []
    assert len(contradicted) == 1
    assert contradicted[0].line == 6


def test_editing_the_statement_orphans_the_flag(tmp_path):
    node = _node()
    add_line_flag(str(tmp_path), "c.py::clamp", node, 6)
    edited = _node(_SRC.replace("total = -1", "total = 0"))
    still, manual, _ = classify_missing_lines(str(tmp_path), "c.py::clamp", edited, [6], covered=set())
    assert still == [6]  # the record no longer matches: it must NOT silently apply
    assert manual == []


def test_identical_statements_in_different_functions_do_not_alias():
    node_a = _node()
    node_b = _node(_SRC.replace("def clamp", "def other"))
    stmt_a, ord_a, ctx_a = resolve_statement(node_a, 6)
    stmt_b, ord_b, ctx_b = resolve_statement(node_b, 6)
    assert ast.dump(stmt_a) == ast.dump(stmt_b)
    assert stmt_identity("c.py::clamp", stmt_a, ord_a, ctx_a) != stmt_identity(
        "c.py::other", stmt_b, ord_b, ctx_b
    )


def test_identical_statements_in_one_function_get_distinct_ordinals():
    src = """\
def f(a):
    x = 0
    if a:
        x = 0
    return x
"""
    node = _node(src)
    _, ord_first, _ = resolve_statement(node, 2)
    _, ord_second, _ = resolve_statement(node, 4)
    assert ord_first != ord_second


def test_flag_outside_the_function_is_refused(tmp_path):
    node = _node()
    assert add_line_flag(str(tmp_path), "c.py::clamp", node, 999) is None
    assert load_line_flags(str(tmp_path)) == {}


def test_pure_movement_keeps_the_flag_alive(tmp_path):
    # a line added ABOVE the function shifts every lineno; the identity is position-free
    node = _node()
    add_line_flag(str(tmp_path), "c.py::clamp", node, 6)
    shifted_src = "# a comment\n\n" + _SRC
    shifted = ast.parse(shifted_src).body[0]
    assert isinstance(shifted, ast.FunctionDef)
    still, manual, _ = classify_missing_lines(str(tmp_path), "c.py::clamp", shifted, [8], covered=set())
    assert manual == [8]
    assert still == []


def test_editing_the_controlling_condition_orphans_the_flag(tmp_path):
    # Review finding 1: the unreachability judgment is a claim about the GUARD.
    # `if total < 0` -> `if total < 100` makes the body newly reachable; a flag
    # hashed on the body alone would keep closing the residual over it.
    node = _node()
    add_line_flag(str(tmp_path), "c.py::clamp", node, 6)
    reguarded = _node(_SRC.replace("if total < 0:", "if total < 100:"))
    still, manual, _ = classify_missing_lines(str(tmp_path), "c.py::clamp", reguarded, [6], covered=set())
    assert still == [6]
    assert manual == []


def test_flag_statuses_current_vs_orphaned(tmp_path):
    node = _node()
    add_line_flag(str(tmp_path), "c.py::clamp", node, 6, note="guarded")
    edited = _node(_SRC.replace("if total < 0:", "if total < 100:"))
    statuses = flag_statuses(str(tmp_path), "c.py::clamp", edited)
    assert [s for _, s in statuses] == ["orphaned"]
    statuses_same = flag_statuses(str(tmp_path), "c.py::clamp", node)
    assert [s for _, s in statuses_same] == ["current"]


def test_remove_line_flag_deletes_exactly_one(tmp_path):
    node = _node()
    add_line_flag(str(tmp_path), "c.py::clamp", node, 4)
    add_line_flag(str(tmp_path), "c.py::clamp", node, 6)
    removed = remove_line_flag(str(tmp_path), "c.py::clamp", node, 6)
    assert removed is not None and removed.line == 6
    assert len(load_line_flags(str(tmp_path))) == 1
    assert remove_line_flag(str(tmp_path), "c.py::clamp", node, 6) is None


def test_clean_orphaned_removes_only_orphans(tmp_path):
    node = _node()
    add_line_flag(str(tmp_path), "c.py::clamp", node, 4)
    add_line_flag(str(tmp_path), "c.py::clamp", node, 6)
    edited = _node(_SRC.replace("if total < 0:", "if total < 100:"))  # orphans line 6's flag
    removed = clean_orphaned_flags(str(tmp_path), "c.py::clamp", edited)
    assert [f.line for f in removed] == [6]
    remaining = list(load_line_flags(str(tmp_path)).values())
    assert [f.line for f in remaining] == [4]
