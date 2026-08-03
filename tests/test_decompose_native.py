"""Native tests for Detective.decompose — the docstring-preservation invariant.

``find_extraction_candidates`` takes an ``ast.FunctionDef``, which converge cannot
synthesize as ``--input`` (an AST node is not literal-eval'able), so this engine-core
behavior is guarded by a unit suite — the sanctioned exemption to the converge-generate
discipline (mirrors test_capture_native.py). The invariant pinned here: a function's
leading docstring belongs to the FUNCTION and is never swept into an extracted helper
(which would both mis-describe the helper and strip the parent of its own docstring).
"""

from __future__ import annotations

import ast

import pytest

from Detective.decompose import find_extraction_candidates
from Detective.decompose_apply import extract_candidate

_SRC = '''\
def f(a, b, c):
    """A function docstring that must stay with f."""
    base = a * 2
    if a > 10:
        x = 1
    elif a > 5:
        x = 2
    else:
        x = 3
    if b:
        x += c
    total = x + base
    return total
'''


def _funcdef(src: str) -> ast.FunctionDef:
    node = ast.parse(src).body[0]
    assert isinstance(node, ast.FunctionDef)
    return node


def test_no_candidate_block_starts_at_the_docstring():
    cands = find_extraction_candidates(_funcdef(_SRC))
    assert cands  # there is a genuinely extractable block
    # the docstring is line 2; a block must never begin there (or earlier)
    assert all(c.start_line > 2 for c in cands)


def test_extraction_leaves_docstring_with_parent_not_helper():
    cands = find_extraction_candidates(_funcdef(_SRC))
    ex = extract_candidate(_SRC, "f", cands[0])
    assert ex is not None
    ns = ex.new_source
    # the docstring survives exactly once, and belongs to f (which is spliced AFTER the
    # helper), never to the helper that comes first in the rewritten source
    assert ns.count('"""A function docstring') == 1
    assert ns.index('"""A function docstring') > ns.index("def f(")
    helper_part = ns[: ns.index("def f(")]
    assert '"""' not in helper_part


def test_docstringless_function_still_decomposes():
    # the docstring-skip path must not regress ordinary extraction
    src = _SRC.replace('    """A function docstring that must stay with f."""\n', "")
    assert find_extraction_candidates(_funcdef(src))


# ── issue #2 / #3: seam placement and helper naming ─────────────────────────────
# Black-box finding: on this fixture the boundary landed one statement past the
# real seam, swallowing `out = []` — the helper returned a freshly-constructed
# empty container — and was named `_compute_name` after a loop-local it does not
# return. The seam is the aggregation; the initializer belongs to its consumer.

_TALLY_SRC = """\
def summarize(rows):
    totals = {}
    for r in rows:
        name = r.get("name") or "unknown"
        v = r.get("value", 0)
        if v < 0:
            v = 0
        totals[name] = totals.get(name, 0) + v

    out = []
    for key in sorted(totals):
        t = totals[key]
        if t == 0:
            continue
        label = key.upper() if t > 100 else key
        out.append(f"{label}={t}")
    return ", ".join(out)
"""


def test_trailing_empty_initializer_is_retracted_not_swallowed():
    cands = find_extraction_candidates(_funcdef(_TALLY_SRC))
    assert cands  # the aggregation seam must survive retraction
    top = cands[0]
    # the block stops at the aggregation loop; `out = []` (line 10) stays with its consumer
    assert top.end_line < 10
    assert top.outputs == ("totals",)
    assert "out" not in top.outputs


def test_helper_is_named_after_what_it_returns():
    cands = find_extraction_candidates(_funcdef(_TALLY_SRC))
    assert cands[0].proposed_name == "_compute_totals"


def test_retracted_extraction_runs_green():
    ns_orig: dict = {}
    exec(compile(_TALLY_SRC, "<orig>", "exec"), ns_orig)
    cases = [
        [{"name": "a", "value": 5}],
        [{"name": "b", "value": 150}],
        [{"name": "c", "value": -3}],
        [],
    ]
    expected = [ns_orig["summarize"](rows) for rows in cases]
    for cand in find_extraction_candidates(_funcdef(_TALLY_SRC)):
        ex = extract_candidate(_TALLY_SRC, "summarize", cand)
        if ex is None:
            continue
        ns: dict = {}
        exec(compile(ex.new_source, "<rewritten>", "exec"), ns)
        assert [ns["summarize"](rows) for rows in cases] == expected


@pytest.mark.parametrize(
    "src, expected",
    [
        ("x = []", True),
        ("x = {}", True),
        ("x = ()", True),
        ("x = set()", True),
        ("x = frozenset()", True),
        ("x = list()", True),
        ("x = dict()", True),
        ("x = tuple()", True),
        ("x = ''", True),
        ("x = 0", True),
        ("x = 0.0", True),
        ("x = b''", True),
        ("x = False", False),  # a bool is a flag, not an empty accumulator
        ("x = [1]", False),
        ("x = {'k': 1}", False),
        ("x = set(rows)", False),
        ("x = 'a'", False),
        ("x = 1", False),
        ("x, y = [], []", False),  # multi-target: not the observed initializer shape
        ("x[0] = []", False),  # subscript store mutates, binds nothing
        ("x += []", False),
        ("x = f()", False),
    ],
)
def test_empty_initializer_grid(src, expected):
    stmt = ast.parse(src).body[0]
    from Detective.decompose import _is_empty_initializer

    assert _is_empty_initializer(stmt) is expected


def test_two_statement_seam_is_enumerated_by_default():
    # Review finding 5: an initializer + accumulator loop is a real seam at width 2
    src = """\
def f(rows):
    total = 0
    for r in rows:
        if r > 0:
            total += r
    label = "big" if total > 100 else "small"
    return f"{label}:{total}"
"""
    cands = find_extraction_candidates(_funcdef(src))
    assert any(c.start_line == 2 and c.end_line == 5 for c in cands)


def test_helper_name_never_collides_with_module_symbols():
    # Review finding 5: an existing module-level `_compute_totals` must be reserved
    src = "def _compute_totals():\n    return 1\n\n\n" + _TALLY_SRC
    summarize = ast.parse(src).body[1]
    assert isinstance(summarize, ast.FunctionDef)
    cands = find_extraction_candidates(summarize)
    assert cands and cands[0].proposed_name == "_compute_totals"
    ex = extract_candidate(src, "summarize", cands[0])
    assert ex is not None
    assert ex.helper_name == "_compute_totals_2"
    ns: dict = {}
    exec(compile(ex.new_source, "<rewritten>", "exec"), ns)
    assert ns["_compute_totals"]() == 1  # the pre-existing symbol is untouched
    assert ns["summarize"]([{"name": "a", "value": 5}]) == "a=5"
