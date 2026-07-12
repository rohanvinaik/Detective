"""Classify a surviving mutant as *killable* or *equivalent-candidate* — by
EXECUTION, never inference.

A survivor is a mutant no current test distinguishes. Two very different things
hide behind that: a mutant a *better test would kill* (killable), and a mutant
*no test can kill* because it computes the same thing (equivalent). Detective must
not conflate them — a killable survivor is a specification gap; an equivalent one
is noise to document and retain.

General mutant equivalence is undecidable, so the classification is asymmetric and
honest:
  * a **distinguishing input** — one where the original and the mutant observably
    differ — is a *proof of killability*: it is a concrete test that kills it.
  * **no distinguishing input found** across the witness search is *evidence* of
    equivalence, documented as "no distinguishing input in N tried", never claimed
    as proof.

This module is input-agnostic: the caller supplies the candidate inputs (which
should include boundary values from the mutation diff, since that is exactly where
a killable-but-surviving mutant hides).
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Any, Callable


def candidate_inputs(arity: int, max_int: int = 3) -> list[tuple]:
    """Candidate positional-arg tuples for the witness search.

    Richer inputs distinguish more killable-but-surviving mutants (fewer false
    'equivalent' verdicts), so for ≤2 params take the full small-integer product
    (boundary values like 0 and -1 included); for wider signatures fall back to
    diagonals plus a few varied orderings to stay bounded.
    """
    if arity <= 0:
        return [()]
    base = [-1, 0, 1, 2, max_int]
    if arity <= 2:
        return [tuple(combo) for combo in itertools.product(base, repeat=arity)]
    diagonals = [tuple([v] * arity) for v in base]
    varied = [
        tuple(range(1, arity + 1)),
        tuple(range(arity, 0, -1)),
        tuple(i % 3 for i in range(arity)),
    ]
    return diagonals + varied


@dataclass(frozen=True)
class Witness:
    """A concrete input on which the original and the mutant observably differ."""

    args: tuple
    original: str  # repr of the original's outcome
    mutant: str  # repr of the mutant's outcome


def _outcome(fn: Callable[..., Any], args: tuple) -> str:
    """The repr of ``fn(*args)``, or a raised-marker — so a mutant that starts
    raising (or stops raising) counts as an observable difference, not a crash."""
    try:
        return repr(fn(*args))
    except Exception as exc:  # noqa: BLE001 — a raised exception IS an observable outcome
        return f"<raised {type(exc).__name__}>"


def find_witness(
    original: Callable[..., Any], mutant: Callable[..., Any], candidate_inputs: list[tuple]
) -> Witness | None:
    """The first input on which original and mutant differ, or None if none does.

    None does not prove equivalence — it means the search did not distinguish them.
    """
    for args in candidate_inputs:
        original_outcome, mutant_outcome = _outcome(original, args), _outcome(mutant, args)
        if original_outcome != mutant_outcome:
            return Witness(tuple(args), original_outcome, mutant_outcome)
    return None


@dataclass(frozen=True)
class MutantVerdict:
    """The classification of one surviving mutant."""

    mutant_id: str
    category: str
    diff_summary: str
    killable: bool  # True iff a distinguishing input was found
    witness: Witness | None  # the distinguishing input, present iff killable
    searched: int  # how many candidate inputs were tried (context for 'equivalent')

    @property
    def label(self) -> str:
        """One-word disposition for reports."""
        return "killable" if self.killable else "equivalent-candidate"


@dataclass(frozen=True)
class SurvivorReport:
    """Per-function classification of every surviving mutant — three grounded
    dispositions plus an optional function-level reason.

    * ``killable``     — a witness exists; the witness *is* a suggested killing test.
    * ``equivalent``   — no distinguishing input found; retained and documented.
    * ``unclassified`` — the mutant could not be built or the search could not run;
      honest uncertainty, named per mutant, never silently dropped.
    """

    verdicts: tuple[MutantVerdict, ...]
    unclassified: tuple[str, ...]  # survivor descriptions with no verdict
    note: str | None = None  # function-level reason when the search could not run at all

    @property
    def killable(self) -> tuple[MutantVerdict, ...]:
        return tuple(v for v in self.verdicts if v.killable)

    @property
    def equivalent(self) -> tuple[MutantVerdict, ...]:
        return tuple(v for v in self.verdicts if not v.killable)


def classify_survivor(
    mutant_id: str,
    category: str,
    diff_summary: str,
    original: Callable[..., Any],
    mutant: Callable[..., Any],
    candidate_inputs: list[tuple],
) -> MutantVerdict:
    """Killable (with a witness) if any input distinguishes the mutant, else an
    equivalent-candidate documented with how many inputs were tried."""
    witness = find_witness(original, mutant, candidate_inputs)
    return MutantVerdict(
        mutant_id=mutant_id,
        category=category,
        diff_summary=diff_summary,
        killable=witness is not None,
        witness=witness,
        searched=len(candidate_inputs),
    )
