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
