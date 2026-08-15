"""_module_callers_of: the same-module backward slice for the caller stratum (#15 B, F1 multi-hop).

INTENT: a test of a public caller (`resolve_roles`) that calls a private target (`_compute_sets`)
reaches the target though it never names it. The slice finds those callers — now TRANSITIVELY (F1:
`pub` → `mid` → `_compute_sets`) — so the router can promote such a test to a `caller_reaches` widen
stratum, traced before the weak signals. Positive-only and conservative: SAME module only (never a
cross-module repo scan — the sandwich thesis), the target excluded, cycles terminate, unrelated
functions never falsely promoted. (`ast.Module` input is not `--input`-expressible, so this is a
hand-written intent characterization, not a converge pin.)
"""

from __future__ import annotations

import ast

from Detective.engine import _module_callers_of


def test_a_public_caller_of_a_private_target_is_found():
    """The idiomatic case: `resolve_roles` calls `_compute_sets`, so a test of `resolve_roles`
    reaches the target — `resolve_roles` is the caller. `unrelated` never touches it."""
    src = (
        "def _compute_sets(x):\n    return x\n"
        "def resolve_roles(x):\n    return _compute_sets(x) + 1\n"
        "def unrelated(x):\n    return x * 2\n"
    )
    assert _module_callers_of(ast.parse(src), "_compute_sets") == {"resolve_roles"}


def test_an_attribute_call_counts_and_the_target_excludes_itself():
    """`self._compute_sets(...)` is an Attribute reach (the same two-form match the router uses); the
    target naming a DIFFERENT helper does not make the target its own caller."""
    src = (
        "class C:\n"
        "    def _compute_sets(self, x):\n"
        "        return _compute_sets_helper(x)\n"
        "    def resolve(self, x):\n"
        "        return self._compute_sets(x)\n"
    )
    assert _module_callers_of(ast.parse(src), "_compute_sets") == {"resolve"}


def test_no_caller_yields_the_empty_set_never_a_false_promotion():
    """Positive-only: with no production function reaching the target, the slice is empty — it never
    invents a caller, so no test is falsely promoted out of `unknown`."""
    src = "def a(x):\n    return x\ndef b(x):\n    return x + 1\n"
    assert _module_callers_of(ast.parse(src), "_compute_sets") == set()


def test_a_multi_hop_same_module_chain_is_transitively_reached():
    """F1: `pub` calls `mid` calls `_compute_sets`. A test of `pub` reaches the target in TWO hops,
    so `pub` AND `mid` are both callers — the multi-hop promotion the one-hop slice missed. The
    unrelated function is never pulled in."""
    src = (
        "def _compute_sets(x):\n    return x\n"
        "def mid(x):\n    return _compute_sets(x) + 1\n"
        "def pub(x):\n    return mid(x) * 2\n"
        "def unrelated(x):\n    return x\n"
    )
    assert _module_callers_of(ast.parse(src), "_compute_sets") == {"mid", "pub"}


def test_a_cycle_among_reachers_terminates():
    """`a` calls `b`, `b` calls `a` AND `_t`. `b` reaches `_t` directly, `a` through `b`; the a↔b
    cycle must not loop the BFS. Both are callers, computed once."""
    src = "def _t(x):\n    return x\ndef a(x):\n    return b(x)\ndef b(x):\n    return a(x) + _t(x)\n"
    assert _module_callers_of(ast.parse(src), "_t") == {"a", "b"}


def test_cross_module_chains_are_not_followed():
    """Sandwich-safe: a caller reaching the target only through a name NOT defined in this module
    (an imported helper) is not resolved here — the slice stays bounded to this module's functions,
    never a repo scan. `local` reaches `_t` directly and is found; `via_import` reaches it only
    through `ext_helper` (undefined here), so it is not transitively promoted by this module alone."""
    src = (
        "from other import ext_helper\n"
        "def _t(x):\n    return x\n"
        "def local(x):\n    return _t(x)\n"
        "def via_import(x):\n    return ext_helper(x)\n"
    )
    got = _module_callers_of(ast.parse(src), "_t")
    assert "local" in got
    assert "via_import" not in got
