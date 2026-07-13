"""Cognitive complexity (SonarSource model) — how hard code is to understand.

Ported from LintGate's structure-check metric. Unlike cyclomatic complexity, this
counts mental effort: nesting adds incrementally, boolean-operator sequences are
penalized, else/elif/except add. The dependency-clustering decomposer uses it to
keep only extractions that make the residual function measurably simpler.

Pure stdlib ``ast``.
"""

from __future__ import annotations

import ast


def compute_cognitive_complexity(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Cognitive complexity of a function: +1 (plus current nesting) for each
    flow-breaking structure (if/for/while/with/except), +1 per boolean-operator
    sequence, +1 for recursion; nesting compounds as those structures nest."""
    func_name = node.name
    total = 0

    def _walk(body: list[ast.stmt], nesting: int) -> None:
        nonlocal total
        for stmt in body:
            total += _cogc_for_statement(stmt, nesting, func_name)
            for child_body, extra in _nested_bodies(stmt):
                _walk(child_body, nesting + extra)

    _walk(node.body, 0)
    return total


def _cogc_for_statement(stmt: ast.stmt, nesting: int, func_name: str) -> int:
    score = 0
    if isinstance(stmt, (ast.If, ast.For, ast.While, ast.AsyncFor)):
        score += 1 + nesting
    elif isinstance(stmt, ast.Try):
        for _handler in stmt.handlers:
            score += 1 + nesting
    elif isinstance(stmt, (ast.With, ast.AsyncWith)):
        score += 1 + nesting
    if isinstance(stmt, (ast.If, ast.While)):
        score += _count_boolean_operators(stmt.test)
    score += _check_recursion(stmt, func_name)
    return score


def _check_recursion(stmt: ast.stmt, func_name: str) -> int:
    for child in ast.walk(stmt):
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Name) and child.func.id == func_name:
            return 1
    return 0


def _nested_bodies(stmt: ast.stmt) -> list[tuple[list[ast.stmt], int]]:
    """Child bodies of a statement plus how much each increases nesting (elif
    chains do not increase nesting; nested functions reset it)."""
    bodies: list[tuple[list[ast.stmt], int]] = []
    if isinstance(stmt, ast.If):
        bodies.append((stmt.body, 1))
        if stmt.orelse:
            if len(stmt.orelse) == 1 and isinstance(stmt.orelse[0], ast.If):
                bodies.append((stmt.orelse, 0))  # elif
            else:
                bodies.append((stmt.orelse, 1))
    elif isinstance(stmt, (ast.For, ast.While, ast.AsyncFor)):
        bodies.append((stmt.body, 1))
        if stmt.orelse:
            bodies.append((stmt.orelse, 1))
    elif isinstance(stmt, ast.Try):
        bodies.append((stmt.body, 1))
        for handler in stmt.handlers:
            bodies.append((handler.body, 1))
        if stmt.orelse:
            bodies.append((stmt.orelse, 1))
        if stmt.finalbody:
            bodies.append((stmt.finalbody, 1))
    elif isinstance(stmt, (ast.With, ast.AsyncWith)):
        bodies.append((stmt.body, 1))
    elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
        bodies.append((stmt.body, 0))
    return bodies


def _count_boolean_operators(node: ast.expr) -> int:
    """Sequences of boolean operators: ``a and b`` -> 1, ``a and b and c`` -> 1
    (same op), ``a and b or c`` -> 2 (mixed)."""
    if not isinstance(node, ast.BoolOp):
        return 0
    count = 1
    for value in node.values:
        if isinstance(value, ast.BoolOp):
            if not isinstance(value.op, type(node.op)):
                count += 1
            count += _count_boolean_operators(value)
    return count
