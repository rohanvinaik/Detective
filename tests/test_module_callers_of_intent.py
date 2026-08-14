"""_module_callers_of: the one-hop, same-module backward slice for the caller stratum (#15 B).

INTENT: a test of a public caller (`resolve_roles`) that calls a private target (`_compute_sets`)
reaches the target though it never names it. The slice finds those callers so the router can promote
such a test to a `caller_reaches` widen stratum. Positive-only and conservative: one hop, same
module, the target excluded, unrelated functions never falsely promoted. (`ast.Module` input is not
`--input`-expressible, so this is a hand-written intent characterization, not a converge pin.)
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
