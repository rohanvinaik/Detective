"""Intent: a WRITE TEST ask prints every value it asks the reader to pin WHOLE (#125).

The defect: WRITE TEST printed each observed outcome cut to its first 28 characters and each
object's repr to its first 70, with no mark of the cut. Two outcomes sharing their first 28
characters printed identically, so the ask showed no distinction at all to pin, and a driver that
acts only on the printed ask (the SquishOS harness) ended its run `ask_incomplete:cut`. The plan
also deduplicates items by their printed text, so two DIFFERENT witnesses whose outcomes shared a
prefix collapsed into one item and the second distinction vanished from the ask entirely.

COMMUNICATING_DETERMINISM §3: a cut value and a whole value of the same length must never print
the same. A value a printed instruction asks the reader to type is never cut; prose the reader does
not type may be cut only with the cut marked (`marked_cut`).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from Detective.cli import _converge_action, _derive_input_plan, marked_cut
from Detective.equivalence import MutantVerdict, SurvivorReport, Witness

_REAL = "{'kind': 'none', 'command': 'detective converge x.py::f', 'why': 'real'}"
_MUT_A = "{'kind': 'none', 'command': 'detective converge x.py::f', 'why': 'mutant a'}"
_MUT_B = "{'kind': 'none', 'command': 'detective converge x.py::f', 'why': 'mutant b'}"
_INPUT = "('no block here',)"


def _result():
    return SimpleNamespace(
        function="p.py::f",
        functionally_complete=False,
        final_survivors=1,
        missing_lines=(),
        signature="f(text)",
        param_names=("text",),
        environment_gated=(),
        admits_certificate=True,
    )


def _verdict(original, mutant, *, args=("no block here",), mutant_id="VALUE_00000001"):
    return MutantVerdict(
        mutant_id=mutant_id,
        category="VALUE",
        diff_summary="- original + mutant",
        killable=True,
        witness=Witness(args=args, original=original, mutant=mutant),
        searched=1,
    )


@pytest.mark.parametrize(
    ("text", "limit", "expected"),
    [
        ("abc", 5, "abc"),
        ("abcde", 5, "abcde"),
        ("abcdef", 5, "abcde…(+1 chars)"),
        ("ab", 1, "a…(+1 chars)"),
        ("", 3, ""),
        ("abcdef", 0, "abcdef"),
        ("abcdef", -3, "abcdef"),
    ],
)
def test_marked_cut_shows_whole_or_marks_what_it_dropped(text, limit, expected):
    assert marked_cut(text, limit) == expected


def test_a_cut_never_prints_like_a_whole_value_of_the_same_length():
    whole = "x" * 20
    cut = marked_cut("x" * 25, 20)
    assert cut != whole
    assert cut.endswith("…(+5 chars)")


def test_the_repeated_ask_prints_both_outcomes_whole():
    rep = SurvivorReport(verdicts=(_verdict(_REAL, _MUT_A),), unclassified=())
    out = _converge_action(_result(), rep, attempted_inputs=(_INPUT,))
    assert out[0].startswith("WRITE TEST:")
    observed = next(line for line in out if "supplied already" in line)
    assert _REAL in observed
    assert _MUT_A in observed


def test_the_hand_pin_ask_prints_both_raised_outcomes_whole():
    real = "<raised ValueError: the code must be written with decimal digits only, got: x>"
    mutant = "<raised ValueError: the code must be written with decimal digits only, got: y>"
    rep = SurvivorReport(verdicts=(_verdict(real, mutant),), unclassified=())
    out = _converge_action(_result(), rep)
    assert out[0].startswith("WRITE TEST:  hand-write")
    pinned = next(line for line in out if "real <raised" in line)
    assert real in pinned
    assert mutant in pinned


class _LongRepr:
    def __repr__(self) -> str:
        return (
            "Obj(name='a-domain-object-with-a-long-repr', fields=['alpha', 'beta', 'gamma', 'delta'], tail=1)"
        )


def test_the_object_ask_prints_the_whole_repr():
    rep = SurvivorReport(verdicts=(_verdict("'real'", "'mutant'", args=(_LongRepr(),)),), unclassified=())
    out = _converge_action(_result(), rep)
    assert out[0].startswith("WRITE TEST:  call the target")
    assert any(repr(_LongRepr()) in line for line in out)


def test_two_witnesses_sharing_a_long_prefix_stay_two_items():
    rep = SurvivorReport(
        verdicts=(
            _verdict(_REAL, _MUT_A, mutant_id="VALUE_00000001"),
            _verdict(_REAL, _MUT_B, mutant_id="VALUE_00000002"),
        ),
        unclassified=(),
    )
    plan = _derive_input_plan(SimpleNamespace(), rep, attempted_inputs=(_INPUT,))
    assert plan.kind == "repeated"
    assert plan.item_total == 2
    assert {r["mutant"] for r in plan.records} == {_MUT_A, _MUT_B}


def test_every_item_states_the_values_its_typed_record_carries():
    rep = SurvivorReport(verdicts=(_verdict(_REAL, _MUT_A),), unclassified=())
    plan = _derive_input_plan(SimpleNamespace(), rep, attempted_inputs=(_INPUT,))
    item, record = plan.items[0], plan.records[0]
    assert record["original"] in item
    assert record["mutant"] in item


def test_the_unsound_suggestion_marks_the_values_it_abbreviates():
    # The witness branch's aside names what made the suggestion unsound. The reader runs the
    # DO THIS command above it and types nothing from the aside, so it may be cut — never unmarked.
    rep = SurvivorReport(verdicts=(_verdict(_REAL, _MUT_A),), unclassified=())
    out = _converge_action(_result(), rep)
    assert out[0].startswith("DO THIS:")
    aside = next(line for line in out if "unsound (" in line)
    assert aside.count("…(+") == 2
    assert marked_cut(_REAL, 20) in aside


def test_short_values_print_exactly_as_before():
    rep = SurvivorReport(verdicts=(_verdict("'real'", "'mutant'"),), unclassified=())
    plan = _derive_input_plan(SimpleNamespace(), rep, attempted_inputs=(_INPUT,))
    assert plan.items == (f"{_INPUT} — supplied already; real 'real' vs mutant 'mutant'",)
