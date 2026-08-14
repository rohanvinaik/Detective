"""FunctionBasis terminal state + obligation-open semantics, from the engine's validity (#D2 §1.3).

Written from intent, not current output. Two conflations this file guards, both recorded defects:
  * a TRUNCATED search is never a `gap` — only an EXHAUSTED one may conclude a specification gap
    (#16, 303289b). A cut is `unresolved`, open obligations or not.
  * a candidate-equivalent mutant is NOT an open obligation — it is the undischargeable residue U_t
    ("modulo N unproven-equivalent"), resolved by `detective flag`, never by grinding.
The generated *_synth goldens are characterization; this file pins the meaning.
"""

from __future__ import annotations

from Detective.engine import basis_action, has_open_obligations


def test_gateable_and_all_discharged_is_complete():
    assert basis_action(admits_certificate=True, has_open_obligations=False) == "complete"


def test_gateable_but_an_obligation_open_is_a_gap():
    # A gap is a VALID gateable conclusion: the search exhausted, the spec simply does not pin this.
    assert basis_action(admits_certificate=True, has_open_obligations=True) == "gap"


def test_a_cut_search_is_unresolved_never_a_gap():
    # #16 (303289b): a truncated / ungateable search earns no negative conclusion.
    assert basis_action(admits_certificate=False, has_open_obligations=True) == "unresolved"
    assert basis_action(admits_certificate=False, has_open_obligations=False) == "unresolved"


def test_a_killable_survivor_is_an_open_obligation():
    assert has_open_obligations(surviving_mutants=1, candidate_equivalents=0, uncovered_lines=0) is True


def test_an_uncovered_line_is_an_open_obligation():
    assert has_open_obligations(surviving_mutants=0, candidate_equivalents=0, uncovered_lines=1) is True


def test_a_candidate_equivalent_is_not_an_open_obligation():
    # survived == equivalent: the only survivors are undecidable equivalents — NOT a gap.
    assert has_open_obligations(surviving_mutants=3, candidate_equivalents=3, uncovered_lines=0) is False


def test_more_survivors_than_equivalents_is_open_the_extra_is_killable():
    assert has_open_obligations(surviving_mutants=4, candidate_equivalents=3, uncovered_lines=0) is True


def test_nothing_open_is_false():
    assert has_open_obligations(surviving_mutants=0, candidate_equivalents=0, uncovered_lines=0) is False
