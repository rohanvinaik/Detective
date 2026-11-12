"""Fault flags are read DIRECTLY, or three-valued - never through a default that means "no problem" (#95).

`docs/theory/COMMUNICATING_DETERMINISM.md` §9 invariant 7: an unmeasured input votes zero, and no
`getattr(obj, name, default)` stands where a renamed field could be absorbed into a silent clean verdict.
`absorption.py` guards the first half (no default read of a name NOTHING declares). This is the second:
a FAULT flag - `budget_exhausted`, `load_failed`, `stale_target`, `trace_truncated`,
`environment_coupled`, ... - whose default is "clean" turns a producer's rename, or an object that never
carried the flag, into a report that goes quietly clean. Founder ruling (§6 item 19): the implementation
that aligns with strict information-theoretic rigour on knowability. So a fault flag is read in one of two
ways, and the guard in `tests/test_absorbed_rename_intent.py` fails any other:

* DIRECT, ``obj.flag``, where the object's type declares it (a `ConvergeResult`, a `SurvivorReport`, a
  `SuiteAudit`): a rename then fails loudly, at the read, and a type checker sees it.
* THREE-VALUED, ``reading(obj, "flag")``, where the object can legitimately lack it (an older Wesker
  result, a duck-typed report, a test double): the answer is present-true, present-false or `ABSENT`, and
  `ABSENT` is a state the consumer names and handles ("could not determine"), never folded into false.
  `validity.normalize_validity` is the precedent: an engine that does not report a field is recorded as
  `absent:<field>` in `capability_flags` rather than read as clean.
"""

from __future__ import annotations

from typing import Any


class _Absent:
    """The type of `ABSENT`: not a bool, not a count, not an empty sequence. Falsy would fold it into
    "no problem", so it is deliberately TRUTHY-ILLEGAL: using it as a condition raises."""

    __slots__ = ()

    def __bool__(self) -> bool:
        raise TypeError("an absent fault flag is neither true nor false; test `is ABSENT` first")

    def __repr__(self) -> str:
        return "ABSENT"


ABSENT = _Absent()

# The fault flags: attributes whose default - False, 0, () or "" - means "no problem". A defaulted read of
# one of these with a clean default is the finding `tests/test_absorbed_rename_intent.py` reports.
FAULT_FLAGS: frozenset[str] = frozenset(
    {
        "budget_exhausted",
        "load_failed",
        "load_failure",
        "stale_target",
        "trace_truncated",
        "environment_coupled",
        "environment_gated",
        "step_budget_divergent",
        "floor_failing_tests",
        "failing_tests",
        "not_consulted",
        "not_consulted_dynamic",
        "collection_conflicts",
        "write_refused_records",
        "unresolved_mutants",
        "unscored_records",
        "shape_hazards",
        "contradicted_flags",
        "redundant_dispositions",
        "cut_reasons",
        "routing_error",
        "authored_fence",
        "missing_line_standings",
    }
)


def fault_read_disposition(is_fault_flag: bool, default_is_absent: bool, registered: bool) -> str:
    """How one defaulted `getattr` stands against the fault-flag rule (#95, pure - pinned). Codes:

    "not_a_fault"   the name is not a fault flag: this rule has nothing to say.
    "three_valued"  a fault flag read with the `ABSENT` sentinel as its default: the absence is a state
                    the consumer must handle, which is the permitted spelling.
    "registered"    a fault flag read with a clean default, still carried in the open registry: a
                    known site not yet converted. The registry counts are exact, so a NEW one fails.
    "clean_default" a fault flag read with a default that means "no problem", and nothing says why:
                    THE finding. A rename of the flag, or an object that never carried it, reads clean.
    """
    if not is_fault_flag:
        return "not_a_fault"
    if default_is_absent:
        return "three_valued"
    return "registered" if registered else "clean_default"


def reading(obj: Any, name: str) -> Any:
    """The attribute `name` of `obj`, or `ABSENT` when `obj` does not carry it.

    The three answers are present (whatever value it holds, including False / 0 / ()), and absent, which
    is `ABSENT` and is never equal to any value. A consumer tests ``value is ABSENT`` and names the
    state; using `ABSENT` as a condition raises rather than reading as false."""
    return getattr(obj, name, ABSENT)
