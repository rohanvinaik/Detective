"""The #67 detector: a survivor on a nested/worklist-shaped target must not be mistaken for equivalent.

Defect this guards against: Detective's witness search does not synthesize nested / cyclic /
value-cross-referential inputs, so on a target whose distinguishing inputs have that shape a
KILLABLE mutant surfaces as a residual survivor — presented identically to a genuinely equivalent
one. The guidance "flag if truly equivalent" then invites a false `flag`, which is a certificate
overclaim. (Measured: `helper_generic_clause` left 8 such survivors; all 8 were killable under
hand-authored structural witnesses, none equivalent.)

Intent: `structural_input_difficulty` names that shape ("deep_structural") from three structural
facts, `structural_shape` reads those facts off the AST, and the CLI appends a caution to the
survivor advisory — but ONLY when the shape is deep_structural AND there are flag-eligible
survivors. These are written from intent; the generated `*_synth` golden only pins what the code
does today.
"""

from __future__ import annotations

import ast

from Detective.cli import _format_survivor_report
from Detective.equivalence import (
    MutantVerdict,
    SurvivorReport,
    Witness,
    structural_input_difficulty,
    structural_shape,
)

_CAVEAT = "deep-structure caveat"


def _func(src: str, name: str) -> ast.FunctionDef:
    return next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == name)


# ───────────────────────────── the detector, from intent ─────────────────────────────

_WORKLIST = """
def close(type_params, referenced):
    by_name = {tp[0]: tp for tp in type_params}
    need = {n for n in referenced if n in by_name}
    frontier = list(need)
    while frontier:
        for dep in by_name[frontier.pop()][2]:
            if dep not in need:
                need.add(dep)
                frontier.append(dep)
    return [tp[1] for tp in type_params if tp[0] in need]
"""

_FLAT = """
def score(values, window, threshold):
    s = sum(values) / len(values)
    return round(s, 4) if s > threshold else 0.0
"""

_NESTED_NO_LOOP = """
def flatten(rows: list[list[int]]) -> list[int]:
    out = []
    for r in rows:
        for x in r:
            out.append(x)
    return out
"""

_ACCUMULATOR_WHILE = """
def collatz(n: int) -> list[int]:
    seq = []
    while n != 1:
        seq.append(n)
        n = n // 2 if n % 2 == 0 else 3 * n + 1
    return seq
"""


def test_a_worklist_loop_indexing_into_elements_is_deep_structural():
    # A fixpoint over values pulled out of collection elements — the shape the witness search
    # cannot reach with a scalar grid.
    assert structural_input_difficulty(**structural_shape(_func(_WORKLIST, "close"))) == "deep_structural"


def test_a_straight_line_function_is_flat():
    assert structural_input_difficulty(**structural_shape(_func(_FLAT, "score"))) == "flat"


def test_a_nested_container_param_iterated_flatly_stays_flat():
    # list[list[int]] but NO worklist: flat iteration is within synthesis's reach, so the detector
    # must stay quiet (conservative — a false caveat is noise on every such function).
    assert structural_input_difficulty(**structural_shape(_func(_NESTED_NO_LOOP, "flatten"))) == "flat"


def test_an_append_only_while_is_not_a_worklist():
    # `while` that grows a list but never pops it is an accumulator, not a fixpoint — no recursive
    # reachability, so not deep_structural.
    assert structural_input_difficulty(**structural_shape(_func(_ACCUMULATOR_WHILE, "collatz"))) == "flat"


def test_the_worklist_is_required_for_deep_structural():
    # Pure decision: neither element-indexing nor a nested param counts WITHOUT the worklist loop.
    assert structural_input_difficulty(False, True, True) == "flat"
    assert structural_input_difficulty(True, True, False) == "deep_structural"
    assert structural_input_difficulty(True, False, True) == "deep_structural"
    assert structural_input_difficulty(True, False, False) == "flat"


# ───────────────────────────── the CLI advisory, from intent ─────────────────────────────


def _crash_only(mid: str) -> MutantVerdict:
    return MutantVerdict(
        mutant_id=mid,
        category=mid.split("_")[0],
        diff_summary="- a and b + a or b",
        killable=False,
        witness=None,
        searched=5,
        crash_only=True,
        crash_witness=Witness(args=([["E", "E", []]], ["E"]), original="[E]", mutant="<raise>"),
        suite_detected=True,
    )


def _candidate_equivalent(mid: str) -> MutantVerdict:
    return MutantVerdict(
        mutant_id=mid,
        category=mid.split("_")[0],
        diff_summary="- tp[0] + tp[1]",
        killable=False,
        witness=None,
        searched=5,
    )


def _killable(mid: str) -> MutantVerdict:
    return MutantVerdict(
        mutant_id=mid,
        category=mid.split("_")[0],
        diff_summary="- x + y",
        killable=True,
        witness=Witness(args=(1,), original=1, mutant="<other>"),
        searched=5,
    )


def test_deep_structural_survivors_get_the_flag_caveat():
    rep = SurvivorReport(
        verdicts=(_crash_only("BOUNDARY_a1"), _candidate_equivalent("VALUE_b2")), unclassified=()
    )
    out = "\n".join(_format_survivor_report(rep, structural_difficulty="deep_structural"))
    assert _CAVEAT in out
    assert "differential check" in out


def test_a_flat_target_gets_no_caveat_on_the_same_survivors():
    rep = SurvivorReport(verdicts=(_crash_only("BOUNDARY_a1"),), unclassified=())
    out = "\n".join(_format_survivor_report(rep, structural_difficulty="flat"))
    assert _CAVEAT not in out


def test_no_flag_eligible_survivors_no_caveat_even_when_deep_structural():
    # A fully-killed deep_structural target has nothing to mis-flag — the caveat must not fire.
    rep = SurvivorReport(verdicts=(_killable("VALUE_a1"),), unclassified=())
    out = "\n".join(_format_survivor_report(rep, structural_difficulty="deep_structural"))
    assert _CAVEAT not in out


def test_the_caveat_omitted_by_default_is_backward_compatible():
    # Callers that do not pass structural_difficulty (older call sites, tests) never see the caveat.
    rep = SurvivorReport(verdicts=(_crash_only("BOUNDARY_a1"),), unclassified=())
    out = "\n".join(_format_survivor_report(rep))
    assert _CAVEAT not in out
