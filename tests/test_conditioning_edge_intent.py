"""#67: the conditioning-edge extractor recovers inter-parameter coupling as a dataflow fact.

Defect this closes: a worklist over records whose KEYS come from a second parameter
(`by_name = {e[0]: e for e in A}` … `B`'s values used as `by_name[·]`) is only reachable by
inputs that tie the two parameters together — the referencing parameter must name into the
collection's key field. Independent-sampling synthesis never constructs that, so the coupled
survivor reads as an unreached candidate-equivalent. `conditioning_edge` extracts the coupling
(collection, key-field, referencing-parameter) so a coupling-aware search can build the tie.

Intent: the extraction is a bounded, decidable dataflow match — general over the shape, not the
signature — so it must fire on BOTH real targets (`transitive_close`, `helper_generic_clause`) and
stay silent (conservative) when the grammar is absent or the lookup is self-referential.
"""

from __future__ import annotations

import ast

from Detective.equivalence import conditioning_edge


def _func(src: str) -> ast.FunctionDef:
    return next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef))


# The two real targets, reduced to their coupling shape. Both: a dict keyed on the collection's
# field 0, a second parameter whose values are the keys.

_TRANSITIVE = """
def close(items, seeds):
    by_name = {it[0]: it for it in items}
    reached = set()
    frontier = list(seeds)
    while frontier:
        n = frontier.pop()
        if n in reached or n not in by_name:
            continue
        reached.add(n)
        for d in by_name[n][2]:
            frontier.append(d)
    return sorted(reached)
"""

_HELPER = """
def clause(type_params, referenced):
    by_name = {tp[0]: tp for tp in type_params}
    need = {name for name in referenced if name in by_name}
    frontier = list(need)
    while frontier:
        for dep in by_name[frontier.pop()][2]:
            if dep in by_name and dep not in need:
                need.add(dep)
                frontier.append(dep)
    return [tp[1] for tp in type_params if tp[0] in need]
"""


def test_transitive_close_edge_is_collection0_keyfield0_ref1():
    # items is the keyed collection (field 0), seeds the referencing parameter, via list()/pop().
    assert conditioning_edge(_func(_TRANSITIVE)) == (0, 0, 1)


def test_helper_generic_clause_edge_same_shape_via_setcomp_and_membership():
    # type_params keyed on field 0; `referenced` reaches the keys through a set comprehension
    # (`{name for name in referenced ...}`), list(), and `by_name[frontier.pop()]` — the extractor
    # must trace all three binding forms.
    assert conditioning_edge(_func(_HELPER)) == (0, 0, 1)


def test_no_dict_comprehension_no_edge():
    assert conditioning_edge(_func("def f(a, b):\n    return a + b")) is None


def test_single_parameter_no_edge():
    # Coupling is BETWEEN parameters; a one-parameter function cannot have one.
    src = "def f(items):\n    by_name = {e[0]: e for e in items}\n    return by_name.get(items[0][0])"
    assert conditioning_edge(_func(src)) is None


def test_self_referential_lookup_is_not_a_cross_parameter_edge():
    # The key comes from the SAME collection (`for k in items`), not a second parameter — no coupling.
    src = (
        "def f(items, other):\n"
        "    by_name = {e[0]: e for e in items}\n"
        "    return [by_name[k[0]] for k in items if k[0] in by_name]\n"
    )
    assert conditioning_edge(_func(src)) is None


def test_keyed_dict_but_second_parameter_never_references_it():
    # A dict is keyed from `items`, but `other` is never used as a key into it — nothing to couple.
    src = "def f(items, other):\n    by_name = {e[0]: e for e in items}\n    return len(by_name) + other"
    assert conditioning_edge(_func(src)) is None
