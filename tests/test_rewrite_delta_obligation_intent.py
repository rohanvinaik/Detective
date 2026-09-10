"""Intent tests for the rewrite-as-obligation gate (#37/#15, closing Wesker #11's blind spot).

Authored from INTENT. The generated suites for `Detective/delta.py` are characterizations — they
pin what the code does, so anything wrong today is pinned wrong. These state what it is FOR.

THE DEFECT, measured on the shipped 1.0.0 before this landed. Wesker's live mutation policy
declares `order: 1`, `generation: original-ast`, and in `exclusions`: "kills do not certify
compositions of operators (see the composite-blind-spot witness in issue #11)". That witness::

    def g(a, b, c): return a + 2 * b + 3 * c
    def f(a, b, c): return g(a, b, c)          # rewritten to g(c, b, a)
    def test_f():   assert f(1, 2, 1) == 8

Both adjacent transpositions are killed — g(b,a,c)=7 and g(a,c,b)=9 against 8 — so converge
reported `✓ COMPLETE (operator universe) · 4/4 killed`. Their composite g(c,b,a)=8 agrees at the
tested point and differs at (1,2,3): 14 against 10.

`detective verify-rewrite` returned **✓ PRESERVED**, and printed "matches old-vs-new at every
tested input" — a true sentence about an empty set, because no new dimension meant no witness
meant no comparison ever ran. The policy was honest about the limitation; the verb was not, which
is an injectivity failure between epistemic state and emitted sign.

The fix is not more operators — a first-order universe cannot certify its own closure however
large it grows, and both versions of that call are IDENTICAL syntax (same `Call`, same `Name`
arguments). The fix is that the rewrite itself became an obligation.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from Detective.delta import (
    TRANSFORM_CENSUS,
    census_id,
    delta_disposition,
    semantic_deltas,
    separation_probes,
    separation_verdict,
)
from Detective.rewrite import rewrite_verdict

_OLD = "def f(a, b, c):\n    return g(a, b, c)\n"
_NEW = "def f(a, b, c):\n    return g(c, b, a)\n"


# ── the regression fixture: Wesker #11's witness, permanently ───────────────


def test_the_composite_permutation_is_seen_as_a_delta() -> None:
    """The shipped defect, step 1: the rewrite must be VISIBLE at all.

    Nothing looked at it before. `verify_rewrite` read the new source into a variable named
    `_new_source` — underscore-prefixed, i.e. deliberately discarded — and reasoned only about the
    suite and the new source's mutant profile.
    """
    kinds = semantic_deltas(_OLD, _NEW)
    assert "call_arg_order" in kinds, "an argument permutation must be named as a permutation"
    assert delta_disposition("call_arg_order") == "separable"


def test_a_probe_family_actually_separates_the_composite() -> None:
    """Step 2: the delta must direct a search that FINDS the difference.

    This is the concrete content of "the mutation zoo becomes a basis problem". A permutation is
    invisible exactly when the permuted positions hold equal values — the witness hid behind
    (1, 2, 1), where a == c. So the probe family for an ordering delta is not "more inputs", it is
    inputs whose positions are pairwise DISTINCT.
    """

    def old(a, b, c):
        return a + 2 * b + 3 * c

    def new(a, b, c):
        return c + 2 * b + 3 * a

    probes = separation_probes(3, ["call_arg_order"])
    separating = [p for p in probes if old(*p) != new(*p)]
    assert separating, "no probe separated a provably behaviour-changing permutation"
    assert (1, 2, 3) in probes, "the witness input named in Wesker #11 must be probed"


def test_the_collision_input_is_the_one_that_hid_it() -> None:
    """Why the old suite was complete and still blind: at (1,2,1) the two agree.

    Pinned so nobody 'simplifies' the probe families down to a single tuple that happens to have
    a repeat in it and silently restores the blind spot.
    """

    def old(a, b, c):
        return a + 2 * b + 3 * c

    def new(a, b, c):
        return c + 2 * b + 3 * a

    assert old(1, 2, 1) == new(1, 2, 1) == 8, "the collision input hides the permutation"
    assert old(1, 2, 3) != new(1, 2, 3), "and a distinct-valued input reveals it"


def test_ordering_deltas_get_non_commutative_carriers() -> None:
    """Type variety is load-bearing, not decoration.

    `a + b + c` reversed IS equivalent over numbers and is NOT over strings or lists, where `+`
    does not commute. An int-only probe family would license a wrong PRESERVED on exactly the
    rewrite most likely to be attempted.
    """
    probes = separation_probes(3, ["call_arg_order"])
    assert any(all(isinstance(v, str) for v in p) for p in probes), "no string carrier"
    assert any(all(isinstance(v, list) for v in p) for p in probes), "no list carrier"

    def old(a, b, c):
        return a + b + c

    def new(a, b, c):
        return c + b + a

    assert [p for p in probes if old(*p) != new(*p)], "commutative-over-ints change went unseen"


def test_a_verdict_cannot_be_preserved_when_the_delta_separated() -> None:
    """The gate itself: proof of a behavioural difference outranks a green replay.

    Every other axis is at its most favourable here — valid receipt, classification ran, replay
    green, no new dimension, no abstention — which is the exact state the shipped defect was in.
    """
    assert rewrite_verdict(True, True, True, 0, 0, 0, "changed") == "CHANGED"
    assert rewrite_verdict(True, True, True, 0, 0, 0, "separated_none") == "PRESERVED"


# ── the soundness gate: absence of a look is not a clean look ───────────────


def test_not_searched_and_no_delta_are_different_facts() -> None:
    """The distinction the first implementation of `separation_verdict` collapsed.

    An identity rewrite and an unsearched one both arrive with ``searched=False``. One has nothing
    to look for; the other has something and did not look. Reporting the first as the second would
    be the same absence/negative conflation this whole module exists to close.
    """
    assert separation_verdict(0, False, 0, 0, 0) == "no_delta"
    assert separation_verdict(1, False, 0, 0, 0) == "not_searched"
    assert rewrite_verdict(True, True, True, 0, 0, 0, "not_searched") == "ABSTAIN"
    assert rewrite_verdict(True, True, True, 0, 0, 0, "no_delta") == "PRESERVED"


def test_an_unclassified_delta_kind_can_never_be_silently_benign() -> None:
    """The exhaustiveness guard's teeth. A kind the census never declared is a defect HERE, and it
    must abstain rather than fall through to PRESERVED — fail-safe, not fail-open."""
    assert delta_disposition("a_kind_nobody_declared") == "unclassified"
    assert delta_disposition("") == "unclassified"
    assert separation_verdict(1, True, 0, 0, 1) == "unclassified_delta"
    assert rewrite_verdict(True, True, True, 0, 0, 0, "unclassified_delta") == "ABSTAIN"


def test_an_unmodelled_delta_is_unreviewed_not_preserved() -> None:
    """A named kind with no modelled search is real and unreviewed — the reader must look."""
    assert separation_verdict(0, False, 0, 1, 0) == "unmodelled_delta"
    assert rewrite_verdict(True, True, True, 0, 0, 0, "unmodelled_delta") == "UNREVIEWED"


# ── B: the census, and its criterion ────────────────────────────────────────


def test_every_kind_the_emitter_can_produce_is_declared() -> None:
    """B's exhaustiveness guard, enforced against the emitter's own source.

    Read by AST rather than by grep: a regex cannot tell a real emitted literal from the same text
    inside a docstring, and this test's whole value is that it cannot be fooled. Every string
    handed to ``out.add(...)`` or returned from ``semantic_deltas``/``_shape_kind``, plus every
    value in ``_FIELD_KINDS``, must carry a disposition.

    Adding a kind to the emitter without declaring it here fails this test rather than silently
    producing `unclassified` at runtime — which would abstain correctly but tell nobody why.
    """
    src = Path(__file__).resolve().parent.parent / "Detective" / "delta.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))
    emitted: set[str] = set()
    for node in ast.walk(tree):
        # out.add("kind")
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            emitted.add(node.args[0].value)
        # return "kind" / return ("kind",)
        if isinstance(node, ast.Return):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                emitted.add(node.value.value)
            elif isinstance(node.value, ast.Tuple):
                for el in node.value.elts:
                    if isinstance(el, ast.Constant) and isinstance(el.value, str):
                        emitted.add(el.value)

    # Dispositions and separation codes are returned by the same syntax; only judge kind names.
    non_kinds = {
        "preserving",
        "separable",
        "unsupported",
        "unclassified",
        "changed",
        "no_delta",
        "not_searched",
        "separated_none",
        "unclassified_delta",
        "unmodelled_delta",
    }
    kinds = {k for k in emitted if k not in non_kinds} | set(_FIELD_KIND_VALUES())
    undeclared = sorted(k for k in kinds if k not in TRANSFORM_CENSUS)
    assert not undeclared, f"emitter can produce kinds the census never declared: {undeclared}"


def _FIELD_KIND_VALUES() -> set[str]:
    from Detective.delta import _FIELD_KINDS

    return set(_FIELD_KINDS.values())


def test_the_census_criterion_is_observability_not_structure() -> None:
    """The regression that corrected the census, kept as a test.

    The first version classified every structural edit `unsupported`, which read as conservative
    and was wrong: introducing a local temporary is a statement-count change — the single most
    common benign refactor — and it came back UNREVIEWED. The criterion is whether the delta's
    effect can reach one positional call's return value or raised exception.
    """
    old = "def f(a):\n    return g(a)\n"
    new = "def f(a):\n    result = g(a)\n    return result\n"
    kinds = semantic_deltas(old, new)
    assert all(delta_disposition(k) != "unsupported" for k in kinds), (
        f"a benign temp-variable refactor must stay searchable, got {kinds}"
    )


def test_positionally_invisible_changes_stay_unsupported() -> None:
    """The other side of the criterion. Probes are POSITIONAL, so a parameter rename is invisible
    to them while breaking every keyword caller; a closure/global binding mutates after the call
    returns. A null search over those would be uninformative and must not license PRESERVED."""
    assert delta_disposition("signature") == "unsupported"
    assert delta_disposition("binding_scope") == "unsupported"
    assert delta_disposition("shape_changed") == "unsupported"


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        ("def f(a):\n    return a\n", "def f(a):\n    return a\n", "identity"),
        ("def f(a):\n    return a + 1\n", "def f(a):\n    return a + 2\n", "constant_value"),
        ("def f(a, b):\n    return a + b\n", "def f(a, b):\n    return a - b\n", "operator"),
        ("def f(a, b):\n    return a\n", "def f(a, b):\n    return b\n", "reference"),
        ("def f(a):\n    return g(a)\n", "def f(a):\n    return h(a)\n", "call_target"),
    ],
)
def test_named_delta_kinds(old: str, new: str, expected: str) -> None:
    """Each edit is named as the hypothesis it is, not folded into one 'changed' bit."""
    assert expected in semantic_deltas(old, new)


def test_an_unreadable_target_is_not_an_absent_delta() -> None:
    """ "There is no delta" and "I could not compute the delta" are different facts. An empty tuple
    would read as the first and fall through to PRESERVED."""
    assert semantic_deltas("not python at all {{{", "def f():\n    pass\n") == ("target_unparsable",)
    assert delta_disposition("target_unparsable") == "unsupported"


def test_census_id_is_stable_and_versioned() -> None:
    """A PRESERVED claim is relative to a fixed classification of rewrites, so the classification
    carries an identity — alongside Wesker's policy_id and Detective's transform_class_id."""
    # Bound to a name rather than written as `census_id() == census_id()`: Sonar's S5863 reads the
    # literal repeated expression as a defect, and it is right to — the determinism this checks is
    # real, but the form that states it should not be indistinguishable from an accidental
    # self-comparison. Fixing the expression beats exempting the rule.
    first = census_id()
    assert census_id() == first, "the census identity must not vary between calls"
    assert first.startswith("1."), "the identity carries its version"
