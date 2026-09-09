"""The class-wide consumption fence — every pinned decision either has a consumer or a REASON.

THE DEFECT THIS EXISTS FOR, found twice on 2026-09-09:

    `ledger.state_basis` — ✓ COMPLETE 11/11, exported, documented, tested, and with ZERO production
    callers, so the founder's ruling it implemented could never fire.
    `converge.reproducibility_verdict` — pinned, and its intent guard asserted a property against a
    function production never called, so the inline expression that DID run was unguarded.

Neither appeared in any open-items index, and no index was wrong: an index lists what somebody
thought to file, and nobody had posed the question. A pin proves a decision does what it says; it
says nothing about whether anything asks it.

FOUNDER RULING 2026-09-09, on making this class-wide: *"I'm okay with class-wide, so long as it's
properly documented and fully mutant pinned. The solution isn't to hide from the dark, it's to throw
some light on it."*

So the registries below take a REASON, never a bare name. An entry has to say what actually consumes
the decision, or what it would take to wire it — which makes the list auditable by READING rather
than by trusting. And they are split in two on purpose:

    BY_DESIGN  a decision that is genuinely not meant to be reached from the CLI.
    OPEN       a decision that SHOULD be wired and is not. A real gap, carried in the open.

One list would have let a defect sit among the design decisions and read as one of them, which is
the hiding the reason requirement exists to prevent. Two lists mean `len(OPEN)` is a number that
changes visibly.

WHAT THIS IS NOT. It does not judge whether a decision is meaningful, correct or well named — it
answers one question with a countable answer and hands everything else to a person. That is what
separates it from a mechanical gate on meaning, which this project has rejected for good reasons.
"""

from __future__ import annotations

import pytest

from Detective.consumption import (
    call_counts,
    consumption_disposition,
    declared_decisions,
    declares_pinned_decision,
)

# Not reachable from the CLI, and correctly so. Each reason names what DOES consume it.
BY_DESIGN: dict[str, str] = {
    "consumption.consumption_disposition": (
        "This guard's own decision. `Detective/consumption.py` is deliberately not wired to any "
        "verb — it is a repo-discipline instrument, and its consumer is this test."
    ),
    "controller.interference_isolation_cost": (
        "Deterministic-SICP Wave-4 measurement instrument (EXP-DS-005). Consumed by "
        "dev/exp_ds_005_controller.py. `controller.py`'s module docstring frames the whole module "
        "as the estimator's instrument, not as CLI machinery."
    ),
    "norms.norm_disposition": (
        "EXP-DS-002 norms mining. Consumed by dev/exp_ds_002_norms_knee.py. `norms.py`'s module "
        "docstring states the split outright: 'This module holds only the PURE decisions of that "
        "discipline — the corpus walking and the call-graph read live with their callers.'"
    ),
    "norms.split_of": (
        "EXP-DS-002 norms mining — consumed by dev/exp_ds_002_norms_knee.py. "
        "See norms.norm_disposition for the module-level split."
    ),
    "norms.verdict_isolation_cost": (
        "EXP-DS-002 — the σ_form read-cost whose corpus distribution locates the bulk/tail knee. "
        "Consumed by dev/exp_ds_002_norms_knee.py."
    ),
    "norms.weighted_median": (
        "EXP-DS-002 norms mining — the κ-weighted corpus zero. Consumed by "
        "dev/exp_ds_002_norms_knee.py. See norms.norm_disposition for the module-level split."
    ),
}

# Real gaps. Carried here so they are VISIBLE rather than absent, and so the count is a number.
OPEN: dict[str, str] = {
    "equivalence.structural_residual_handback": (
        "W5 — the CONSUMER was never built. `residual_disposition` IS wired (via "
        "`cli.candidate_equivalent_caveat`, which maps its code to a caveat inline); this decides "
        "the NEXT question — whether an honest hand-back is `--input` or a hand-built fixture — and "
        "nothing asks it. Design: docs/F2_RESIDUAL_TYPING.md."
    ),
    "session_manifest.module_identity_conflicts": (
        "W6 — built for #58, which is CLOSED, and never wired. `session_manifest.py` contains this "
        "function and nothing else, so the entire module is unconsumed. Its own docstring says 'a "
        "caller has to say which one' — that caller does not exist."
    ),
}


@pytest.fixture(scope="module")
def sweep():
    """One AST pass over the package, its tests and the research harnesses."""
    decls = declared_decisions("Detective")
    names = frozenset(q.split(".", 1)[1] for q in decls)
    production = call_counts(("Detective",), names)
    elsewhere = call_counts(("tests", "dev"), names)
    return decls, production, elsewhere


# ---------------------------------------------------------------- the fence


def test_every_pinned_decision_is_consumed_or_carries_a_reason(sweep) -> None:
    """THE guard. A decision that nothing calls, with nothing on record saying why, is the
    `state_basis` shape — and it will pass every other check in this repo."""
    decls, production, elsewhere = sweep
    orphans = [
        qual
        for qual in decls
        if consumption_disposition(production[qual.split(".", 1)[1]], elsewhere[qual.split(".", 1)[1]], "")
        in ("pinned_unconsumed", "unreferenced")
        and qual not in BY_DESIGN
        and qual not in OPEN
    ]
    assert not orphans, (
        "pinned decision(s) with no production consumer and no declared reason:\n  "
        + "\n  ".join(f"{q}  ({decls[q]})" for q in orphans)
        + "\n\nWire it, or add it to BY_DESIGN/OPEN with a reason that says what consumes it."
    )


def test_the_population_is_not_silently_shrinking(sweep) -> None:
    """A false NEGATIVE in the declaration predicate drops a decision out of the population this
    guard claims to cover — the failure the guard exists to close, reproduced inside it. The count
    is pinned loosely: it moves when decisions are added, and a COLLAPSE is what this catches."""
    decls, _, _ = sweep
    assert len(decls) > 120, f"only {len(decls)} declared decisions found — the predicate likely broke"


# ---------------------------------------------------------------- the registries cannot rot


def test_no_registry_entry_names_a_decision_that_is_now_consumed(sweep) -> None:
    """`exemption_stale`. A registry that accumulates entries nobody re-checks becomes exactly the
    hiding place the reason requirement exists to prevent, so an exemption that outlived its reason
    is a finding rather than a tidy no-op."""
    _, production, _elsewhere = sweep
    stale = [
        qual
        for qual, reason in {**BY_DESIGN, **OPEN}.items()
        if consumption_disposition(production.get(qual.split(".", 1)[1], 0), 0, reason) == "exemption_stale"
    ]
    assert not stale, f"these are consumed now — delete their registry entries: {stale}"


def test_no_registry_entry_names_a_decision_that_no_longer_EXISTS(sweep) -> None:
    """The other way a registry rots: the function was renamed or deleted and its excuse outlived
    it, silently covering nothing."""
    decls, _, _ = sweep
    ghosts = [q for q in {**BY_DESIGN, **OPEN} if q not in decls]
    assert not ghosts, f"registry names decisions that are not declared any more: {ghosts}"


def test_every_reason_actually_says_something() -> None:
    """An empty or token reason is not a reason. This is the rule the disposition encodes, asserted
    against the registry that has to satisfy it."""
    for qual, reason in {**BY_DESIGN, **OPEN}.items():
        assert len(reason.strip()) > 40, f"{qual}: a reason has to name what consumes it, or what it needs"


def test_the_open_gaps_are_exactly_the_two_we_know_about() -> None:
    """`len(OPEN)` is the number this whole instrument exists to make visible. It should go DOWN.
    If it goes up, that is a finding arriving — which is the guard working, not failing."""
    assert set(OPEN) == {
        "equivalence.structural_residual_handback",
        "session_manifest.module_identity_conflicts",
    }


def test_a_decision_is_never_in_both_registries() -> None:
    """The split is the point: a real gap must not be able to read as a design decision."""
    assert not (set(BY_DESIGN) & set(OPEN))


# ---------------------------------------------------------------- the gathering layer (impure)


def test_a_docstring_mentioning_its_IMPURE_caller_is_not_a_declaration() -> None:
    """The house convention for extracting a decision says to place it beside the impure function it
    serves — so `"pure" in text` matched "impure" and admitted 7 false positives, one of which had
    been carried in a hand-written finding list. Word boundary, in order, close together."""
    assert (
        declares_pinned_decision("Sits beside the impure shell it serves; the pinned one is elsewhere.")
        is False
    )
    assert declares_pinned_decision("Whether this holds (pure — pinned).") is True
    assert declares_pinned_decision("(F2 — pure, pinned)") is True
    assert declares_pinned_decision("pinned first, then pure") is False, "order carries meaning"
    assert declares_pinned_decision("") is False


def test_declared_decisions_finds_module_level_functions_only(tmp_path) -> None:
    """Nested and method-bound decisions are outside the population this guard claims to cover, and
    claiming more than it checks is the failure it is here to prevent."""
    (tmp_path / "m.py").write_text(
        'def top():\n    """A decision (pure — pinned)."""\n\n\n'
        'class C:\n    def meth(self):\n        """Also (pure — pinned)."""\n'
    )
    found = declared_decisions(str(tmp_path))
    assert "m.top" in found
    assert not any(k.endswith(".meth") for k in found)


def test_call_counts_counts_CALLS_not_mentions(tmp_path) -> None:
    """Why this cannot be a text search: the docstrings here name sibling decisions constantly, and
    every one of them would read as a consumer."""
    (tmp_path / "a.py").write_text(
        '"""Mentions target() in prose."""\n\n\n# target() in a comment\ndef f():\n    return 1\n'
    )
    (tmp_path / "b.py").write_text("from x import target\n\n\ndef g():\n    return target(1)\n")
    counts = call_counts((str(tmp_path),), frozenset({"target"}))
    assert counts["target"] == 1


def test_call_counts_sees_a_module_alias_call(tmp_path) -> None:
    """The house style reaches decisions both ways — `state_basis(...)` and `_L.state_basis(...)`."""
    (tmp_path / "c.py").write_text("from . import ledger as _L\n\n\ndef g():\n    return _L.target(1)\n")
    assert call_counts((str(tmp_path),), frozenset({"target"}))["target"] == 1


def test_a_missing_root_is_not_an_error() -> None:
    """`dev/` is not present in every checkout."""
    assert call_counts(("no_such_dir_anywhere",), frozenset({"target"})) == {"target": 0}
