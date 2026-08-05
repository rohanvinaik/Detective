"""Tests for the cross-run property store.

Hand-written native, same sanctioned exemption as the other ``*_native`` files: ``load``
reads a JSON store off disk and takes a callable ``verify``, and neither a filesystem
state nor a function satisfies any ``--input`` string.

The contract this file defends is the one whose absence caused two bugs. ``converge``
re-renders its suite file WHOLESALE from an accumulator that started empty every run, so
whatever the previous run pinned and this run did not re-derive was deleted before anything
measured it. That is why a target could alternate forever (round A's tests answered, then
overwritten by round B's) and why re-converging a function silently shrank its suite from
five tests to one. Seeding the accumulator from here is the fix, so these are the properties
that make the seeding safe: a pin survives an unrelated run, and NEVER survives the code
moving out from under it.
"""

from __future__ import annotations

import json
import os
from dataclasses import replace

from Detective import pins
from Detective.synthesis.oracle_light import ExecutableProperty

_KEY = "m.py::f"
_DIGEST = "0123456789abcdef"


def _prop(assertion: str = "assert f(1) == 2", **over) -> ExecutableProperty:
    # `replace`, not a dict splatted into the constructor: the dict form widens every value to
    # the union of its members, so a checker cannot tell `confidence=0.9` from `category=...`
    # and reports one error per field. Same fixture, typed.
    base = ExecutableProperty(
        category="VALUE",
        inputs={},
        setup_code="from m import f",
        assertion_code=assertion,
        preconditions=[],
        confidence=0.9,
        function_key=_KEY,
        mutant_id="V0",
    )
    return replace(base, **over) if over else base


def _always(*_a, **_k) -> bool:
    return True


def _never(*_a, **_k) -> bool:
    return False


def test_a_saved_pin_is_returned_on_the_next_run(tmp_path):
    """The whole point: a property survives to the next converge instead of being
    re-derived-or-lost."""
    pins.save(str(tmp_path), _KEY, _DIGEST, [_prop()])
    out = pins.load(str(tmp_path), _KEY, _DIGEST, verify=_always)

    assert [p.assertion_code for p in out] == ["assert f(1) == 2"]
    assert out[0].setup_code == "from m import f"
    assert out[0].category == "VALUE" and out[0].mutant_id == "V0"


def test_an_edited_function_abandons_its_pins(tmp_path):
    """The cheap gate. The store is keyed by the target's AST, so pins never re-assert a
    previous body's expectations against a new one — a stale golden would otherwise fail
    loudly on code the user just intentionally changed."""
    pins.save(str(tmp_path), _KEY, _DIGEST, [_prop()])
    assert pins.load(str(tmp_path), _KEY, "ffffffffffffffff", verify=_always) == []


def test_a_pin_that_no_longer_holds_is_dropped(tmp_path):
    """The correct gate. The digest covers the FUNCTION; a module-level constant it reads can
    change without touching it, and the pinned value is then wrong. Execution decides, so a
    property that fails is not returned — never carried forward to be re-rendered."""
    pins.save(str(tmp_path), _KEY, _DIGEST, [_prop()])
    assert pins.load(str(tmp_path), _KEY, _DIGEST, verify=_never) == []


def test_no_store_is_no_memory_not_an_error(tmp_path):
    assert pins.load(str(tmp_path), _KEY, _DIGEST, verify=_always) == []


def test_a_malformed_entry_is_skipped_and_the_rest_survive(tmp_path):
    """A half-written store must cost the entries it corrupted, not the run. Same posture as
    the equivalence-flag store: unreadable is empty, never fatal."""
    pins.save(str(tmp_path), _KEY, _DIGEST, [_prop()])
    path = os.path.join(str(tmp_path), ".detective", "pins.json")
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    key = next(iter(raw))
    raw[key] = ["not-a-dict", {"category": "VALUE"}, *raw[key]]  # junk + missing fields + the good one
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(raw, fh)

    out = pins.load(str(tmp_path), _KEY, _DIGEST, verify=_always)
    assert [p.assertion_code for p in out] == ["assert f(1) == 2"]


def test_unreadable_json_is_empty_not_an_exception(tmp_path):
    path = os.path.join(str(tmp_path), ".detective", "pins.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("{ this is not json")
    assert pins.load(str(tmp_path), _KEY, _DIGEST, verify=_always) == []


def test_a_golden_case_returns_as_the_pair_the_renderer_unpacks(tmp_path):
    """JSON has no tuples. ``render_module`` folds 2+ goldens into one parametrize by
    unpacking ``golden_case`` as (args, expected); a list round-tripped back would change the
    rendered file's shape, so the pair is restored as a pair."""
    pins.save(str(tmp_path), _KEY, _DIGEST, [_prop(golden_case=("(1,)", "2"))])
    out = pins.load(str(tmp_path), _KEY, _DIGEST, verify=_always)

    assert out[0].golden_case == ("(1,)", "2")
    assert isinstance(out[0].golden_case, tuple)


def test_a_golden_case_of_the_wrong_shape_is_skipped(tmp_path):
    """Only a 2-tuple is a golden case. Anything else is malformed, not coercible — the
    renderer would unpack it and raise inside the write."""
    pins.save(str(tmp_path), _KEY, _DIGEST, [_prop()])
    path = os.path.join(str(tmp_path), ".detective", "pins.json")
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    key = next(iter(raw))
    raw[key][0]["golden_case"] = ["only-one"]
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(raw, fh)

    assert pins.load(str(tmp_path), _KEY, _DIGEST, verify=_always) == []


def test_saving_a_new_body_drops_the_previous_bodys_entry(tmp_path):
    """Entries for a digest that no longer exists can never be loaded again; keeping them
    grows the store forever. A DIFFERENT function's pins are untouched."""
    other = "m.py::g"
    pins.save(str(tmp_path), _KEY, _DIGEST, [_prop()])
    pins.save(str(tmp_path), other, _DIGEST, [_prop(function_key=other)])
    pins.save(str(tmp_path), _KEY, "ffffffffffffffff", [_prop("assert f(1) == 3")])

    with open(os.path.join(str(tmp_path), ".detective", "pins.json"), encoding="utf-8") as fh:
        raw = json.load(fh)

    assert pins._entry_key(_KEY, _DIGEST) not in raw
    assert pins._entry_key(_KEY, "ffffffffffffffff") in raw
    assert pins._entry_key(other, _DIGEST) in raw  # a sibling target is not collateral


def test_saving_empty_is_a_real_memory_not_a_no_op(tmp_path):
    """ "Everything generated was redundant against your own tests" is a fact worth
    remembering. If empty were skipped, the previous run's pins would load again and be
    re-rendered — resurrecting exactly the file the minimizer just decided not to ship."""
    pins.save(str(tmp_path), _KEY, _DIGEST, [_prop()])
    pins.save(str(tmp_path), _KEY, _DIGEST, [])
    assert pins.load(str(tmp_path), _KEY, _DIGEST, verify=_always) == []


def test_verify_is_optional_for_readers_that_only_want_the_store(tmp_path):
    """``None`` trusts the digest alone. Seeding a run must always pass a verifier; a caller
    merely inspecting what is stored should not have to execute it."""
    pins.save(str(tmp_path), _KEY, _DIGEST, [_prop()])
    assert len(pins.load(str(tmp_path), _KEY, _DIGEST)) == 1


def test_the_digest_tracks_behaviour_not_formatting():
    """``ast.dump``, not raw text: reformatting or a comment edit must keep the pins, and any
    change to what the function DOES must abandon them."""
    import ast

    same = pins.function_digest(ast.parse("def f(x):\n    return x + 1\n").body[0])
    commented = pins.function_digest(ast.parse("def f(x):\n    # a note\n    return x + 1\n").body[0])
    changed = pins.function_digest(ast.parse("def f(x):\n    return x + 2\n").body[0])

    assert same == commented
    assert same != changed
