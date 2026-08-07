"""Unit guard for `parsimony.statement_cohesion`.

`statement_cohesion` takes an `ast` node — a domain object no input grid synthesises — so it
cannot be converged cold; it is guarded by the unit suite, the sanctioned exemption for
AST/integration functions (ARCHITECTURE §10, §11). The PURE decision `_cohesion_vote` is
Detective-pinned separately in `tests/detective/`.

These cases encode the load-bearing design decision at the output-assembly point: a **single**
returned value/object is a COMBINATION (its producers fuse into one computation); a top-level
**tuple** return is BUNDLING (independent results, kept separate). Without that split a cohesive
struct-builder and a function returning two unrelated values are structurally identical.
"""

import ast

import pytest

from Detective.parsimony import statement_cohesion


def _fn(src: str) -> ast.FunctionDef:
    return ast.parse(src).body[0]  # type: ignore[return-value]


@pytest.mark.parametrize(
    "src, expected",
    [
        # two disjoint producer chains, returned as a tuple -> two responsibilities
        ("def f(a, b):\n x = a + 1\n y = x * 2\n p = b - 1\n q = p / 2\n return y, q\n", 2),
        # one chain feeding the result -> cohesive
        ("def f(a, b):\n x = a + b\n y = x * 2\n z = y - x\n return z\n", 1),
        # three independent producers, tuple return -> three
        ("def f(a, b, c):\n x = a + 1\n p = b - 1\n m = c * 3\n return x, p, m\n", 3),
        # two chains that MERGE at a real producer -> one
        ("def f(a, b):\n x = a + 1\n p = b - 1\n z = x + p\n return z\n", 1),
        # many fields assembled into ONE object -> one computation (the struct-builder case)
        ("def f(a, b):\n x = a + 1\n p = b - 1\n return dict(x=x, p=p)\n", 1),
        # fewer than two producers -> trivial, no opinion
        ("def f(a):\n return a + 1\n", 0),
        # a single side-effect sink combines its consumed producers
        ("def f(a, b):\n x = a + 1\n p = b - 1\n log(x, p)\n", 1),
    ],
)
def test_statement_cohesion_components(src: str, expected: int) -> None:
    assert statement_cohesion(_fn(src)) == expected
