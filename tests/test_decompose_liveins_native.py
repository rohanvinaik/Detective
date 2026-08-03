"""Native tests for Detective.decompose — the read-before-write live-in invariant (issue #6).

``_compute_block_variables`` takes ``_StmtInfo`` lists built from an ``ast.FunctionDef``,
which converge cannot synthesize as ``--input``, so this engine-core behavior is guarded
by a unit suite — the sanctioned exemption to the converge-generate discipline (mirrors
test_decompose_native.py). The invariant pinned here, from the issue's regression matrix:
a name whose pre-block value is consumed before its first definition inside the block is a
live-in and MUST appear in the helper interface. The old set arithmetic
``(reads & pre) - writes`` erased exactly those (``x += 1``, ``x = x + 1``), producing
trial helpers with unbound locals.
"""

from __future__ import annotations

import ast
import textwrap

from Detective.decompose import (
    _analyze_statement,
    _compute_block_variables,
    _get_param_names,
    decompose,
    find_extraction_candidates,
)
from Detective.decompose_apply import extract_candidate


def _funcdef(src: str) -> ast.FunctionDef:
    node = ast.parse(textwrap.dedent(src)).body[0]
    assert isinstance(node, ast.FunctionDef)
    return node


def _block_vars(src: str, start: int, end: int) -> tuple[set[str], set[str]]:
    fn = _funcdef(src)
    infos = [_analyze_statement(i, s) for i, s in enumerate(fn.body)]
    result = _compute_block_variables(infos, start, end, _get_param_names(fn))
    assert result is not None
    return result


def test_aug_assign_target_is_a_live_in():
    # x += 1 loads the pre-block x: it is an input, not erased by its own write
    inputs, _ = _block_vars(
        """
        def f(a):
            x = a
            x += 1
            y = x * 2
            z = y + 1
            return z
        """,
        1,
        4,
    )
    assert "x" in inputs


def test_plain_rebind_is_a_live_in():
    # x = x + 1 consumes the pre-block x on the RHS before storing
    inputs, _ = _block_vars(
        """
        def f(a):
            x = a
            x = x + 1
            y = x * 2
            z = y + 1
            return z
        """,
        1,
        4,
    )
    assert "x" in inputs


def test_both_branches_define_means_not_required_afterward():
    # y is must-defined by the if/else, so the later read is NOT upward-exposed
    inputs, _ = _block_vars(
        """
        def f(a):
            y = 0
            if a > 0:
                y = 1
            else:
                y = 2
            z = y + 1
            return z
        """,
        1,
        3,
    )
    assert "y" not in inputs
    assert "a" in inputs


def test_one_branch_only_is_not_a_must_def():
    # without an else, the pre-block y can flow through: it stays a live-in
    inputs, _ = _block_vars(
        """
        def f(a):
            y = 0
            if a > 0:
                y = 1
            z = y + 1
            return z
        """,
        1,
        3,
    )
    assert "y" in inputs


def test_loop_only_definition_is_not_assumed_after_zero_iterations():
    # a for-body assignment is a may-def: the pre-block y survives an empty loop
    inputs, _ = _block_vars(
        """
        def f(items):
            y = 0
            for it in items:
                y = it
            z = y + 1
            return z
        """,
        1,
        3,
    )
    assert "y" in inputs


def test_nested_scope_free_variables_are_live_ins():
    # Review finding 2 (supersedes the issue's rule-6 reading): a nested def closes
    # over `hidden` and a class body reads it at definition time — both make it a
    # live-in of any block carrying the definition. Omitting it shipped helpers
    # that raised NameError.
    inputs, _ = _block_vars(
        """
        def f(a):
            hidden = a * 3
            def g():
                return hidden
            class C:
                attr = hidden
            c = a + 1
            d = c + 2
            return d
        """,
        1,
        5,
    )
    assert "hidden" in inputs
    assert "a" in inputs


def test_nested_scope_locals_still_do_not_leak():
    # the nested scope's OWN names (params, locals) stay private to it
    inputs, _ = _block_vars(
        """
        def f(a):
            outer = a * 3
            def g(inner_param):
                inner_local = inner_param + outer
                return inner_local
            c = a + g(1)
            d = c + 2
            return d
        """,
        1,
        4,
    )
    assert "outer" in inputs
    assert "inner_param" not in inputs
    assert "inner_local" not in inputs


def test_subscript_store_reads_its_container():
    # d[k] = v mutates an existing dict: d and k are live-ins, and d is not a def
    inputs, _ = _block_vars(
        """
        def f(d, k):
            v = 1
            d[k] = v
            w = v + 1
            x = w + 1
            return x
        """,
        1,
        4,
    )
    assert "d" in inputs
    assert "k" in inputs


_SHIP_SRC = """\
def f(rows):
    shipping = 10.0
    handling = 2.0
    total = 0.0
    for r in rows:
        if r > 0:
            total += r
    if total > 100:
        shipping *= 1.2
        handling += 4
    fee = shipping + handling
    return total + fee
"""


def test_issue_fixture_augmented_locals_are_in_the_interface():
    # the block covering `shipping *= 1.2` / `handling += 4` must carry both as inputs
    inputs, outputs = _block_vars(_SHIP_SRC, 3, 6)
    assert {"shipping", "handling", "total", "rows"} <= inputs
    assert outputs == {"total", "fee"}


def test_every_extracted_helper_runs_green():
    # the "done when": no generated helper reads a local that is neither a parameter
    # nor definitely defined before that read — proven by executing every candidate
    ns_orig: dict = {}
    exec(compile(_SHIP_SRC, "<orig>", "exec"), ns_orig)
    cases = [[50, 60, -3], [1, 2], [], [200]]
    expected = [ns_orig["f"](rows) for rows in cases]
    candidates = find_extraction_candidates(_funcdef(_SHIP_SRC))
    assert candidates  # the fixture must keep producing at least one seam
    for cand in candidates:
        ex = extract_candidate(_SHIP_SRC, "f", cand)
        if ex is None:
            continue
        ns: dict = {}
        exec(compile(ex.new_source, "<rewritten>", "exec"), ns)
        got = [ns["f"](rows) for rows in cases]
        assert got == expected, f"candidate {cand.proposed_name} changed behavior"


# ── issue #11: nonlocal closures pin their lexical cell to this frame ───────────


def test_nonlocal_closure_block_is_rejected():
    # relocating the def would close over the HELPER's cell; the caller's copy
    # diverges on the next invocation — no candidate may carry it
    src = """
    def f(a, x):
        hidden = a
        def g():
            nonlocal hidden
            hidden += 1
        if x > 0:
            g()
        if hidden > 10:
            hidden = 10
        out = hidden + x
        return out
    """
    for cand in find_extraction_candidates(_funcdef(src)):
        assert not (cand.start_line <= 4 <= cand.end_line), (
            f"candidate {cand.proposed_name} relocates a nonlocal closure"
        )


def test_read_only_closure_stays_eligible():
    # a closure that only READS a free variable is a value dependency: valid seam
    src = """
    def f(a, x):
        base = a * 2
        def g(v):
            return base + v
        total = 0
        for i in range(x):
            if i % 2:
                total += g(i)
        out = total + base
        return out
    """
    cands = find_extraction_candidates(_funcdef(src))
    covering = [c for c in cands if c.start_line <= 4 <= c.end_line]
    assert covering  # the def itself is relocatable
    # g's free variable is satisfied either way: the block contains base's
    # definition (line 3) or must carry base as an input
    assert all("base" in c.inputs or c.start_line <= 3 for c in covering)


def test_cell_obstruction_is_named_not_silent():
    src = """
    def f(a):
        count = 0
        def bump():
            nonlocal count
            count += 1
        bump()
        bump()
        return count
    """
    plan = decompose(_funcdef(src), "f")
    if not plan.is_decomposable:
        assert "nonlocal" in plan.rationale
        assert "no clean extraction" not in plan.rationale
