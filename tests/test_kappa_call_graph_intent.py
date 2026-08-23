"""Q1 intent — κ over the code CALL GRAPH (the §18 Q1 subsystem, first deliverable).

The κ engine is ported VERBATIM from Regenesis ``significance.py`` (pure over an adjacency dict), so
these tests pin the ported behavior against KNOWN small graphs — reachability, marginal coverage,
weakly-connected components, and the bridge predicate §14's crux rests on — plus the ONE code-specific
piece, :func:`build_call_graph` (the adapter): caller→callee edges into package-defined functions only.
"""

from __future__ import annotations

from Detective.kappa import (
    build_call_graph,
    call_graph_shape,
    components,
    coverage,
    is_bridge,
    marginal_coverage,
    reachable,
)


# ─── the ported κ engine, on known graphs ───
def test_reachable_is_the_forward_closure_excluding_the_start():
    g = {"a": {"b"}, "b": {"c"}, "c": set()}
    assert reachable(g, "a") == {"b", "c"}
    assert reachable(g, "c") == set()  # a leaf reaches nothing
    assert reachable({"a": {"b"}, "b": {"a"}}, "a") == {"b"}  # cycle-safe: a↔b terminates


def test_coverage_is_kappa_per_node():
    cov = coverage({"a": {"b"}, "b": {"c"}, "c": set()})
    assert cov["a"] == 2  # reaches b, c
    assert cov["b"] == 1  # reaches c
    assert cov["c"] == 0  # a leaf


def test_marginal_coverage_subtracts_the_already_selected_cover():
    g = {"a": {"b", "d"}, "b": {"c"}, "c": set(), "d": set()}
    assert marginal_coverage(g, "a", []) == 3  # κ(a|∅) = |cover(a)| = {b,c,d}
    # b selected → its cover {b,c} subtracted; a still adds d (which b does not reach)
    assert marginal_coverage(g, "a", ["b"]) == 1


def test_components_are_weakly_connected():
    comps = components({"a": {"b"}, "x": {"y"}})
    assert len(comps) == 2
    assert {"a", "b"} in comps
    assert {"x", "y"} in comps


def test_is_bridge_joins_two_disjoint_components():
    g = {"a": {"b"}, "x": {"y"}}
    assert is_bridge(g, "a", "x") is True  # joins {a,b} and {x,y} — §13's bridge
    assert is_bridge(g, "a", "b") is False  # same component
    assert is_bridge(g, "a", "absent") is False  # a node not in the graph bridges nothing


def test_call_graph_shape_reports_the_fragmentation():
    shape = call_graph_shape({"a": {"b"}, "b": {"c"}, "x": {"y"}})  # a 3-node chain + a 2-node
    assert shape["nodes"] == 5
    assert shape["edges"] == 3
    assert shape["components"] == 2
    assert shape["largest_component"] == 3
    assert shape["max_kappa"] == 2  # `a` reaches b, c


# ─── the adapter: caller→callee edges into package functions only ───
def _pkg(tmp_path):
    (tmp_path / "m.py").write_text(
        "def h():\n    return 1\n\n\n"
        "def g():\n    return h()\n\n\n"
        "def f():\n    print(g())\n"  # `print` is external → dropped; `g` is package → edge f→g
    )
    (tmp_path / "other.py").write_text("def x():\n    return 2\n")
    return str(tmp_path)


def test_build_call_graph_keeps_only_intra_package_edges(tmp_path):
    adj = build_call_graph(_pkg(tmp_path))
    assert adj["f"] == {"g"}  # f calls g (package); print dropped (external)
    assert adj["g"] == {"h"}  # g calls h
    assert adj["h"] == set()  # h calls nothing package-defined
    assert adj["x"] == set()  # unconnected package fn, no calls
    assert call_graph_shape(adj)["components"] == 2  # f→g→h chain + x singleton
