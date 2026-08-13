"""An extracted helper must declare the PEP 695 type-params its threaded annotations use.

Defect (#28 follow-on): ``extract_candidate`` threads the parent's parameter annotations onto
the helper (issue #28) but the helper is spliced at MODULE scope. When the parent is generic —
``def transform[E, R](items: list[E], ...)`` — a threaded ``x: list[E]`` lands ``E`` on a helper
that never declared it, so ``E`` is an undefined name: ruff F821 and a ty unresolved-reference on
every applied split over a generic function. A behaviour-preserving split that reds the target's
own lint is not mergeable, which was the whole point of threading annotations (#28) in the first
place.

Intent: the helper redeclares EXACTLY the subset of the parent's type-params its emitted
annotations reference (transitively closed over bounds/defaults, in parent declaration order),
and nothing when the parent is non-generic. These are written from intent, not captured — the
generated ``*_synth`` golden pins what the code does; only these can catch a wrong implementation
pinned wrong.
"""

from __future__ import annotations

import ast
import sys
from types import SimpleNamespace

import pytest

from Detective.decompose_apply import extract_candidate, helper_generic_clause

# PEP 695 generic syntax (`def f[E, R](...)`) and `ast.FunctionDef.type_params` are Python 3.12+.
# On 3.11 the feature is a no-op (`extract_candidate` reads `getattr(func, "type_params", [])` → []),
# so there is nothing to exercise — and the source strings below cannot even parse. Skip the module.
pytestmark = pytest.mark.skipif(sys.version_info < (3, 12), reason="PEP 695 generics require Python 3.12+")


def _cand(**kw):
    return SimpleNamespace(**kw)


def _helper_def(new_source: str, name: str) -> ast.FunctionDef:
    tree = ast.parse(new_source)
    return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)


def _typeparam_names(node: ast.FunctionDef) -> list[str]:
    return [tp.name for tp in node.type_params]


def _names_in_annotations(node: ast.FunctionDef) -> set[str]:
    out: set[str] = set()
    for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]:
        if arg.annotation is not None:
            out |= {n.id for n in ast.walk(arg.annotation) if isinstance(n, ast.Name)}
    return out


# ─────────────────────────── end-to-end, through extract_candidate ───────────────────────────


def test_reported_flat_case_declares_the_typevar_it_uses():
    # The exact reported shape: def f[E, R], extract a block whose only param is annotated list[E].
    src = (
        "def transform[E, R](items: list[E], make: R) -> list[R]:\n"
        "    seen: list[E] = []\n"
        "    for x in items:\n"
        "        seen.append(x)\n"
        "    out: list[R] = [make for _ in seen]\n"
        "    return out\n"
    )
    ext = extract_candidate(
        src,
        "transform",
        _cand(start_line=2, end_line=4, proposed_name="_collect_seen", inputs=("items",), outputs=("seen",)),
    )
    assert ext is not None
    helper = _helper_def(ext.new_source, "_collect_seen")
    # E is USED (via list[E]) and therefore DECLARED; R is neither used by the helper nor declared.
    assert "E" in _names_in_annotations(helper)
    assert _typeparam_names(helper) == ["E"]


def test_no_parent_typevar_leaks_undeclared_across_shapes():
    # The general property the fix guarantees: for any generic parent, every parent type-param a
    # helper's annotations reference is one the helper itself declares — never an undefined name.
    src = (
        "def build[E, R: list[E]](rows: R, key: E) -> None:\n"
        "    acc: R = rows\n"
        "    acc.append(key)\n"
        "    print(acc)\n"
    )
    ext = extract_candidate(
        src,
        "build",
        _cand(start_line=2, end_line=3, proposed_name="_extend", inputs=("rows", "key"), outputs=("acc",)),
    )
    assert ext is not None
    helper = _helper_def(ext.new_source, "_extend")
    parent_typevars = {"E", "R"}
    referenced_parent_tvs = _names_in_annotations(helper) & parent_typevars
    declared = set(_typeparam_names(helper))
    # No leak: everything referenced is declared. (R via `rows: R`, and R's bound list[E] drags E in.)
    assert referenced_parent_tvs <= declared
    assert declared == {"E", "R"}


def test_non_generic_parent_yields_a_helper_with_no_type_params():
    src = "def plain(a: int, b: int) -> int:\n    s = a + b\n    t = s * 2\n    return t\n"
    ext = extract_candidate(
        src,
        "plain",
        _cand(start_line=2, end_line=2, proposed_name="_sum", inputs=("a", "b"), outputs=("s",)),
    )
    assert ext is not None
    helper = _helper_def(ext.new_source, "_sum")
    assert helper.type_params == []
    assert "[" not in ext.new_source.split("def _sum")[1].split("(")[0]  # no generic clause


# ─────────────────────────── the pure decision, from intent ───────────────────────────


def test_clause_is_the_referenced_subset_in_parent_order():
    tps = [["E", "E", []], ["R", "R", []], ["S", "S", []]]
    # Reference S then E (out of order); output must follow PARENT order E..R..S, R dropped.
    assert helper_generic_clause(tps, ["S", "E"]) == "[E, S]"


def test_clause_closes_transitively_over_a_bound():
    # R's bound names E; referencing only R must still pull E in, so the bound stays defined.
    tps = [["E", "E", []], ["R", "R: list[E]", ["E"]]]
    assert helper_generic_clause(tps, ["R"]) == "[E, R: list[E]]"


def test_clause_is_empty_when_no_typeparam_is_referenced():
    tps = [["E", "E", []], ["R", "R", []]]
    assert helper_generic_clause(tps, ["X", "items"]) == ""


def test_clause_is_empty_for_a_non_generic_parent():
    assert helper_generic_clause([], ["anything"]) == ""


def test_a_referenced_name_that_is_not_a_typeparam_is_ignored():
    # `X` is not one of the parent's type-params, so it contributes nothing to the clause.
    assert helper_generic_clause([["E", "E", []]], ["E", "X"]) == "[E]"
