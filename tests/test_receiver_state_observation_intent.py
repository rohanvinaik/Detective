"""Receiver-state observation — the #25 fallback that pins a method whose mutation changes only
`self` (founder ruling 2026-09-06, "fallback only"), found by the dogfood sweep on
`purity._SideEffectVisitor.visit_Call`.

The gap: `_outcome` observed only the RETURN value, so a visitor that appends to `self.reasons` and
returns None was identical to every mutant of it — 7/47 killed, the rest "unclassified, the search
could not run", because no return observation can distinguish a state-only change. The fallback:
when the value search finds no witness AND the target is receiver-bound, observe the receiver's
POST-CALL state and retry; a differing attribute whose value round-trips as a literal becomes a
`recv = Owner(); recv.m(args); assert recv.attr == <lit>` test. "Fallback only" — a method whose
RETURN the mutation changes never pays for the second pass.

Pinned from intent (the pure decisions hand-pinned, not converge-pinned: `state_witness_attrs` lives
in the huge equivalence.py, whose test surface inflates an isolated converge — the recorded
exemption). The end-to-end behaviour is pinned through the real `converge` on a tmp repo.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from Detective.converge import converge
from Detective.equivalence import _observe_receiver_state, _renderable_repr, state_witness_attrs

# ---------------------------------------------------------------- state_witness_attrs (pure)


def test_no_difference_yields_no_attrs():
    post = {"reasons": "[]", "seen": "set()"}
    assert state_witness_attrs(post, dict(post)) == ()


def test_a_differing_attribute_is_named():
    original = {"reasons": "['calls impure builtin print']", "seen": "set()"}
    mutant = {"reasons": "[]", "seen": "set()"}
    assert state_witness_attrs(original, mutant) == ("reasons",)


def test_multiple_differences_come_back_sorted():
    original = {"b": "2", "a": "1", "c": "3"}
    mutant = {"b": "9", "a": "1", "c": "9"}
    assert state_witness_attrs(original, mutant) == ("b", "c")


def test_an_attribute_present_on_one_side_only_counts_as_differing():
    assert state_witness_attrs({"x": "1"}, {}) == ("x",)
    assert state_witness_attrs({}, {"y": "2"}) == ("y",)


# ---------------------------------------------------------------- _renderable_repr (pure)


@pytest.mark.parametrize("value", [[], ["a", "b"], "s", 3, 3.5, True, None, {"k": 1}, (1, 2), {1, 2}])
def test_a_literal_value_round_trips(value):
    assert _renderable_repr(value) == repr(value)


def test_an_object_valued_attribute_is_not_renderable():
    import ast

    assert _renderable_repr(ast.parse("x").body[0]) is None
    assert _renderable_repr(object()) is None


# ---------------------------------------------------------------- _observe_receiver_state (shape)


def test_observe_receiver_state_is_sorted_and_address_free():
    class R:
        def __init__(self):
            self.b = [1]
            self.a = "x"

    obs = _observe_receiver_state(R())
    assert obs == "{'a': 'x', 'b': [1]}"  # sorted keys, value reprs, no address


def test_a_slotted_receiver_has_no_observable_state():
    class S:
        __slots__ = ()

    assert _observe_receiver_state(S()) == "<no __dict__>"


# ---------------------------------------------------------------- end to end, through converge

_VISITOR = """
class Recorder:
    def __init__(self) -> None:
        self.hits: list[str] = []

    def note(self, name: str) -> None:
        if name.startswith("_"):
            self.hits.append("private")
        else:
            self.hits.append("public")
"""

_FACTORY = """
from rec import Recorder


def make_recorder() -> Recorder:
    return Recorder()
"""


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "rec.py").write_text(textwrap.dedent(_VISITOR), encoding="utf-8")
    (tmp_path / "rec_factories.py").write_text(textwrap.dedent(_FACTORY), encoding="utf-8")
    return tmp_path


def test_a_void_method_is_pinned_by_its_receiver_state(tmp_path, monkeypatch) -> None:
    root = _repo(tmp_path)
    # The factory is imported by name; under the CLI the live pytest session puts the repo on
    # sys.path — do the same for this direct library call.
    monkeypatch.syspath_prepend(str(root))
    result = converge(
        "rec.py",
        "Recorder.note",
        str(root),
        receiver_factory="rec_factories:make_recorder",
        supplied_inputs=[("_x",), ("y",)],
        max_iterations=2,
        write_dir="tests/detective",
    )
    assert not result.needs_receiver, result.needs_receiver
    # The method returns None; without state observation the branch mutants (append "private" vs
    # "public", or nothing) are indistinguishable and survive. With it, they are killed and a state
    # test is written that asserts on `recv.hits`, not on the (always-None) return.
    assert result.written_path is not None, "a receiver-state test should have been written"
    emitted = Path(result.written_path).read_text(encoding="utf-8")
    assert "recv = make_recorder()" in emitted, emitted
    assert "recv.note(" in emitted, emitted
    assert "assert recv.hits ==" in emitted, emitted
    # Every mutant is killed — the whole point: a void method reaches ✓ COMPLETE via receiver state.
    assert result.converged, result
    assert result.killed == result.total_mutants, (result.killed, result.total_mutants)
