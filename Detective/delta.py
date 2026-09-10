"""The rewrite itself as a proof obligation — the differential old-vs-new oracle (#37/#15).

WHY THIS EXISTS, and it is a measured defect rather than a theoretical one.

``verify-rewrite`` used to establish ``PRESERVED`` from three facts: the frozen proof suite
replays green, the new source adds no behavioural dimension the receipt never covered, and old
and new agree at every witness the survivor classification happened to produce. Each is true.
Together they are not enough, and the gap has a name in this repo already: Wesker's live policy
declares ``order: 1`` and ``generation: original-ast``, and its ``exclusions`` say outright that
"kills do not certify compositions of operators (see the composite-blind-spot witness in issue
#11)".

Wesker #11's witness, run against the shipped 1.0.0 stack::

    def g(a, b, c): return a + 2 * b + 3 * c
    def f(a, b, c): return g(a, b, c)      # rewritten to g(c, b, a)
    def test_f():   assert f(1, 2, 1) == 8

Both adjacent transpositions are killed -- ``g(b,a,c)``=7 and ``g(a,c,b)``=9 against 8 -- so the
suite is ``COMPLETE, 4/4 killed``. Their composite ``g(c,b,a)``=8 agrees at the tested point and
differs at ``(1,2,3)``: 14 against 10. ``verify-rewrite`` returned **PRESERVED**, and said
"matches old-vs-new at every tested input" -- a true sentence about an empty set, because no new
dimension meant no witness meant no comparison ever ran.

That is this project's own meta-pattern landing on its headline verb: a claim that holds over the
subspace where it was checked, with nothing recording that the subspace was a subspace.

THE FIX IS NOT MORE OPERATORS. A first-order universe cannot certify its own closure however
large it grows, and the census in this module would classify BOTH versions of that call as
identical syntax -- same ``Call``, same ``Name`` arguments, every field already covered. The
missing step is upstream of mutation entirely: **nobody was looking at the rewrite**. The delta
between old and new was never computed, so it could never be discharged.

So the actual transformation becomes a first-class hypothesis. Given old ``P`` and new ``P'``:

1. compute the semantic delta -- what structurally changed;
2. classify every delta against a VERSIONED census of transformation kinds;
3. direct a separation search at those kinds, and require the search to have RUN.

An unclassified delta kind cannot produce ``PRESERVED``. That is the point of the census being a
census rather than a list: a kind nobody named is not silently benign, it is a refusal. Same
discipline as :data:`Detective.decompose.OBLIGATION_EVIDENCE`, where an ``unsupported`` obligation
already forces proposal-only instead of riding a green rerun.

WHAT THIS DOES NOT CLAIM. A separation search that finds nothing is not a proof of equivalence --
it is the same epistemic object the rest of the tool trades in, a failed search, and it is
reported as such. What changes is that the search is now DIRECTED BY THE DELTA and is a
precondition of the verdict, so "we did not look" can no longer render as "we looked and found
nothing". Those are different facts and they must not print the same.
"""

from __future__ import annotations

import ast
import hashlib

# ── B: the transformation census ────────────────────────────────────────────
#
# Every delta kind this module can emit carries exactly one disposition. A kind absent from
# this table is `unclassified`, which forbids PRESERVED -- the exhaustiveness guard. Adding a
# kind to the emitter without adding it here is therefore fail-safe rather than fail-open.
#
#   preserving  -- provably cannot change observable behaviour (no separation search needed)
#   separable   -- if this delta changed behaviour, the change lands in the channel the probe
#                  observes, so a null search is meaningful evidence
#   unsupported -- the delta's effect can live OUTSIDE that channel; a null search would be
#                  uninformative, so it must not license PRESERVED
#
# THE CRITERION IS OBSERVABILITY, NOT STRUCTURE, and getting that wrong is a measured mistake
# rather than a hypothetical one. The first version of this table classified every structural
# edit as `unsupported`, which read as conservative and was simply incorrect: introducing a local
# temporary (`result = g(...); return result`) is a statement-count change, the single most common
# benign refactor there is, and it came back UNREVIEWED. The effect of that edit is entirely in the
# return value, which is exactly what the probe reads.
#
# So the question a kind must answer is not "is this structural?" but "if this delta changed
# behaviour, would `_outcome(fn, args)` — one positional call's return value or raised exception —
# be able to differ?" Statements, control flow, comprehensions and exception regions all resolve
# into that channel. A closure cell mutated after the call, a keyword parameter's NAME (probes are
# positional, so a rename is invisible to them while breaking every keyword caller), and an
# unnamed node-type mismatch do not.
#
# Note what `separable` still does NOT claim: that the probes WILL find a difference if one exists.
# Every kind here shares that limit — a constant change may only matter on inputs nobody probed.
# It is a failed search, reported as one, which is the epistemics the whole tool trades in.
TRANSFORM_CENSUS: dict[str, str] = {
    # nothing changed
    "identity": "preserving",
    # the effect of these resolves into one call's return value or raised exception
    "constant_value": "separable",
    "operator": "separable",
    "reference": "separable",
    "call_target": "separable",
    "call_keyword": "separable",
    "call_arg_order": "separable",
    "sequence_order": "separable",
    "sequence_length": "separable",
    "control_shape": "separable",
    "comprehension_shape": "separable",
    "exception_region": "separable",
    "expression_shape": "separable",
    "statement_shape": "separable",
    # the effect can live outside what a positional probe observes
    "signature": "unsupported",  # a parameter RENAME is invisible positionally, fatal to callers
    "binding_scope": "unsupported",  # closure cells / global bindings mutate after the call returns
    "shape_changed": "unsupported",  # an unnamed node-type mismatch: we do not know what it is
    # the target itself could not be read
    "target_unparsable": "unsupported",
    "target_missing": "unsupported",
}

CENSUS_VERSION = 1
"""Bump on any semantic change to the census or the emitter's kind vocabulary.

Carried alongside Wesker's ``policy_id`` and Detective's ``transform_class_id`` for the same
reason those exist: a PRESERVED claim is relative to a fixed classification of rewrites, and a
change to that classification invalidates the claim rather than silently re-grading it.
"""


def census_id() -> str:
    """A stable identity for the census contents, as ``<version>.<digest>``."""
    body = ";".join(f"{k}={v}" for k, v in sorted(TRANSFORM_CENSUS.items()))
    return f"{CENSUS_VERSION}.{hashlib.sha256(body.encode()).hexdigest()[:12]}"


def delta_disposition(kind: str) -> str:
    """What one delta kind means for the verdict (#37, pure -- pinned).

    A named code, never a bool: ``preserving`` needs no search, ``separable`` needs one that
    RAN, and ``unsupported``/``unclassified`` forbid PRESERVED for different reasons that must
    stay distinguishable in the report. ``unsupported`` is "we named this and model no search";
    ``unclassified`` is "the emitter produced a kind the census never declared", which is a
    defect in this module rather than in the user's rewrite and should read that way.
    """
    if not kind:
        return "unclassified"
    return TRANSFORM_CENSUS.get(kind, "unclassified")


# ── A: the semantic delta ───────────────────────────────────────────────────

# Primitive-field edits, keyed by (node type, field). Anything unlisted becomes `shape_changed`
# rather than being dropped -- silence here would reopen exactly the hole this module closes.
_FIELD_KINDS: dict[tuple[str, str], str] = {
    ("Constant", "value"): "constant_value",
    ("Constant", "kind"): "constant_value",
    ("Name", "id"): "reference",
    ("Attribute", "attr"): "reference",
    ("arg", "arg"): "signature",
    ("FunctionDef", "name"): "signature",
    ("AsyncFunctionDef", "name"): "signature",
    ("keyword", "arg"): "call_keyword",
    ("Global", "names"): "binding_scope",
    ("Nonlocal", "names"): "binding_scope",
    ("alias", "name"): "reference",
    ("alias", "asname"): "reference",
    ("ExceptHandler", "name"): "exception_region",
}

# Node types whose mere presence/shape change is a control or scope edit rather than a value one.
_CONTROL_NODES = frozenset(
    {"If", "For", "AsyncFor", "While", "Break", "Continue", "Return", "Pass", "Match", "match_case"}
)
_EXCEPTION_NODES = frozenset({"Try", "TryStar", "ExceptHandler", "Raise", "Assert", "With", "AsyncWith"})
_COMPREHENSION_NODES = frozenset({"ListComp", "SetComp", "DictComp", "GeneratorExp", "comprehension"})
_SCOPE_NODES = frozenset({"Lambda", "Global", "Nonlocal", "FunctionDef", "AsyncFunctionDef", "ClassDef"})


def _shape_kind(a: ast.AST, b: ast.AST) -> str:
    """Name a node-type mismatch by the semantic surface it sits on.

    The final two branches apply the census's observability criterion rather than dumping every
    unrecognised mismatch into ``shape_changed``. Replacing an expression with another expression
    (``g(x)`` becoming ``g(x) + 1``) resolves entirely into the return value, and so does swapping
    one statement for another; both are as observable as a changed constant. Only a mismatch that
    is neither — a node pair we cannot even place on the expression/statement surface — stays
    ``shape_changed``, which is `unsupported` precisely because we do not know what it is.
    """
    both = {type(a).__name__, type(b).__name__}
    if both & _EXCEPTION_NODES:
        return "exception_region"
    if both & _COMPREHENSION_NODES:
        return "comprehension_shape"
    if both & _SCOPE_NODES:
        return "binding_scope"
    if both & _CONTROL_NODES:
        return "control_shape"
    if isinstance(a, ast.expr) and isinstance(b, ast.expr):
        return "expression_shape"
    if isinstance(a, ast.stmt) and isinstance(b, ast.stmt):
        return "statement_shape"
    return "shape_changed"


def _is_op(node: ast.AST) -> bool:
    return isinstance(node, (ast.operator, ast.unaryop, ast.boolop, ast.cmpop))


def _fingerprint(node: object) -> str:
    """Order-insensitive identity of a subtree, for detecting a pure reordering.

    ``ast.dump`` without attributes is exactly the right granularity: it ignores line/column
    (a moved element is not thereby a changed one) and keeps every semantic field.
    """
    if isinstance(node, ast.AST):
        return ast.dump(node, annotate_fields=True, include_attributes=False)
    return repr(node)


def _walk_nodes(a: ast.AST, b: ast.AST, parent: str, field: str, out: set[str]) -> None:
    """Two aligned AST nodes."""
    if type(a) is not type(b):
        out.add("operator" if _is_op(a) and _is_op(b) else _shape_kind(a, b))
        return
    if parent == "Call" and field == "func" and _fingerprint(a) != _fingerprint(b):
        # WHICH callable is invoked is a different hypothesis from which value is passed to it,
        # and the finer `reference` edit below is emitted too. Both are true and both are
        # `separable`, so the extra kind costs a report line and buys a named hypothesis.
        out.add("call_target")
    node_name = type(a).__name__
    for f in a._fields:
        _walk(getattr(a, f, None), getattr(b, f, None), node_name, f, out)


def _walk_sequences(a: list, b: list, parent: str, field: str, out: set[str]) -> None:
    """Two aligned child lists — where the composite blind spot actually lives."""
    if len(a) != len(b):
        out.add("sequence_length")
        return
    fa = [_fingerprint(x) for x in a]
    fb = [_fingerprint(x) for x in b]
    if fa != fb and sorted(fa) == sorted(fb):
        # Same elements, different positions: a pure reordering. Named separately from the
        # per-element reference edits it also produces, because the PERMUTATION is the
        # hypothesis -- this is Wesker #11's shape, and the reason this module exists.
        out.add("call_arg_order" if parent == "Call" and field == "args" else "sequence_order")
    for x, y in zip(a, b, strict=True):  # lengths compared above; strict pins that invariant
        _walk(x, y, parent, field, out)


def _walk(a: object, b: object, parent: str, field: str, out: set[str]) -> None:
    """Accumulate delta kinds for two aligned positions in the old and new trees.

    Three cases, each its own function. Kept split rather than inlined because a parallel tree
    walk with node/sequence/leaf branches folded together measured cognitive complexity 28, and
    the sequence branch in particular is the one carrying the reordering detection this whole
    module was built for -- it should be readable on its own.
    """
    if isinstance(a, ast.AST) and isinstance(b, ast.AST):
        _walk_nodes(a, b, parent, field, out)
        return

    if isinstance(a, list) and isinstance(b, list):
        _walk_sequences(a, b, parent, field, out)
        return

    if a == b:
        return
    out.add(_FIELD_KINDS.get((parent, field), "shape_changed"))


def _function_def(source: str) -> ast.AST | None:
    """Parse one function's source to its def node, tolerating leading indentation."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        try:
            tree = ast.parse(_dedent(source))
        except SyntaxError:
            return None
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return node
    return None


def _dedent(source: str) -> str:
    lines = [ln for ln in source.splitlines() if ln.strip()]
    if not lines:
        return source
    pad = min(len(ln) - len(ln.lstrip()) for ln in lines)
    return "\n".join(ln[pad:] if len(ln) >= pad else ln for ln in source.splitlines())


def semantic_deltas(old_source: str, new_source: str) -> tuple[str, ...]:
    """Every way the rewrite differs from the original, as sorted census kinds (#37, pure -- pinned).

    Takes SOURCE rather than AST so the decision is expressible as ``--input`` and can be pinned
    in isolation; the receipt already carries ``original_source``, and the new source is read
    from disk by the caller.

    Returns ``("identity",)`` when the two parse to the same tree modulo position -- which is the
    only result that needs no separation search. An unparsable or absent target returns its own
    kind rather than an empty tuple: "there is no delta" and "I could not compute the delta" are
    different facts, and an empty tuple would read as the first.
    """
    old_def, new_def = _function_def(old_source), _function_def(new_source)
    if old_def is None or new_def is None:
        return ("target_unparsable",) if (old_source and new_source) else ("target_missing",)
    if _fingerprint(old_def) == _fingerprint(new_def):
        return ("identity",)
    out: set[str] = set()
    _walk(old_def, new_def, "", "", out)
    return tuple(sorted(out)) if out else ("identity",)


# ── the delta-directed separation search ────────────────────────────────────
#
# A permutation is invisible exactly when the permuted positions hold EQUAL values: the shipped
# counterexample hid behind `(1, 2, 1)`, where a == c. So the probe family for an ordering delta
# is not "more inputs" but "inputs whose positions are pairwise DISTINCT" -- the symmetry the
# delta could hide behind, deliberately broken.
#
# Type variety matters for the same reason and is not decoration. `a + b + c` reversed IS
# equivalent over numbers and is NOT over strings or lists, where `+` does not commute. Probing
# ints alone would license a wrong PRESERVED on exactly the rewrite most likely to be attempted.


def separation_probes(arity: int, kinds: list[str]) -> tuple[tuple[object, ...], ...]:
    """Candidate argument tuples aimed at the symmetries ``kinds`` could hide behind (pure -- pinned).

    Ordering deltas get pairwise-distinct families across several types, because commutativity is
    type-dependent. Value deltas get magnitude and sign variety. Returns an empty tuple for a
    non-positive arity: a nullary function has no argument symmetry to break, and fabricating a
    probe for one would be inventing a distinction the code cannot make.
    """
    if arity <= 0:
        return ()
    ordering = any(k in ("call_arg_order", "sequence_order") for k in kinds)
    families: list[tuple[object, ...]] = [
        tuple(range(1, arity + 1)),
        tuple(range(arity, 0, -1)),
        tuple((2, 3, 5, 7, 11, 13, 17, 19, 23, 29)[i % 10] for i in range(arity)),
        tuple((-1) ** i * (i + 1) for i in range(arity)),
        tuple(10**i for i in range(arity)),
    ]
    if ordering:
        # Non-commutative carriers: these separate an ordering change that arithmetic hides.
        families.append(tuple(chr(ord("a") + (i % 26)) for i in range(arity)))
        families.append(tuple([i + 1] for i in range(arity)))
        families.append(tuple(float(i + 1) / 2 for i in range(arity)))
    return tuple(families)


def separation_verdict(
    separable: int, searched: bool, distinguished: int, unsupported: int, unclassified: int
) -> str:
    """What the delta analysis warrants, before the suite evidence is folded in (pure -- pinned).

    Named codes, and the order is the severity order:

    * ``unclassified_delta`` -- the emitter produced a kind the census never declared. A defect
      here, not in the rewrite; it must never be silently benign.
    * ``changed`` -- a probe separated old from new. This is PROOF of a behaviour change and
      outranks everything below it.
    * ``unmodelled_delta`` -- some delta kind is declared ``unsupported``: real, named, and with
      no search this version can run. Forbids PRESERVED.
    * ``not_searched`` -- a ``separable`` delta exists and no search ran. "We did not look" is
      never "we looked and found nothing"; this is the soundness gate.
    * ``separated_none`` -- every delta was searched and none separated. The strongest thing this
      module can say, and still a failed search rather than a proof.
    * ``no_delta`` -- nothing separable to discharge (an identity rewrite, or one whose every
      delta is ``preserving``).

    ``separable`` is a parameter rather than an inference from ``searched`` because an identity
    rewrite and an unsearched one both arrive with ``searched=False``, and they are opposite
    facts: the first has nothing to look for, the second has something and did not look. An
    earlier revision of this function omitted the parameter and reported the first as the second
    -- the same absence/negative conflation the module exists to close, one level down.
    """
    if unclassified > 0:
        return "unclassified_delta"
    if distinguished > 0:
        return "changed"
    if unsupported > 0:
        return "unmodelled_delta"
    if separable <= 0:
        return "no_delta"
    if not searched:
        return "not_searched"
    return "separated_none"
