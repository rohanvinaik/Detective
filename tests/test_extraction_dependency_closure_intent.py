"""Audit D: moving a helper must preserve imported and read-before-write dependencies."""

from Detective.extract import extract_proposal, render_extract


def test_a_move_does_not_lose_the_exception_constructor_import():
    source = (
        "import jax\nimport argparse\n"
        "def parse(v: str):\n"
        "    if v == 'yes':\n        return True\n"
        "    raise argparse.ArgumentTypeError('bad')\n"
    )
    proposal = extract_proposal(source, "parse")
    assert proposal is not None
    assert proposal.unresolved_inputs == ("argparse",)
    assert "unresolved input interface" in "\n".join(render_extract("m.py", proposal))


def test_a_later_assignment_does_not_hide_a_nonprimitive_input_read():
    source = "def f(grid: ndarray, item):\n    n = len(grid)\n    n += item\n    item = 1\n    return n\n"
    proposal = extract_proposal(source, "f")
    assert proposal is not None
    assert "item" in proposal.unresolved_inputs


def test_nested_scope_is_an_explicit_analysis_boundary():
    source = (
        "def f(grid: ndarray):\n    n = len(grid)\n    def inner():\n        return n\n    return inner()\n"
    )
    proposal = extract_proposal(source, "f")
    assert proposal is not None
    assert "<nested scope>" in proposal.unresolved_inputs
