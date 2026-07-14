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

import ast
import itertools
from dataclasses import dataclass
from typing import Any, Callable


def _type_of(ann) -> str | None:
    """Base type name of an annotation node: ``int``, ``str``, ``list`` (from
    ``list[...]``), a dotted ``ast.FunctionDef`` (from an ``Attribute``), or the
    non-None side of ``X | None`` / ``Optional[X]``. None when unannotated or too
    complex to pick inputs for."""
    if isinstance(ann, ast.Name):
        return ann.id
    if isinstance(ann, ast.Attribute) and isinstance(ann.value, ast.Name):
        return f"{ann.value.id}.{ann.attr}"  # ast.FunctionDef, typing.Any, …
    if isinstance(ann, ast.Subscript) and isinstance(ann.value, ast.Name):
        if ann.value.id == "Optional":  # Optional[X] -> X
            return _type_of(ann.slice)
        return ann.value.id  # list[...], dict[...] -> the container
    if isinstance(ann, ast.BinOp) and isinstance(ann.op, ast.BitOr):
        for side in (ann.left, ann.right):  # X | None -> X
            name = _type_of(side)
            if name and name != "None":
                return name
    return None


@dataclass(frozen=True, repr=False)
class SourceExpr:
    """A synthesized input that is NOT a plain literal (an AST node, a constructed
    object): it carries the source that reconstructs it *and* the live value.

    The pipeline is literal-only by default — inputs round-trip through ``repr`` and
    ``ast.literal_eval``. A ``SourceExpr`` bridges the non-literal case in one type:
      * ``repr(self)`` IS the constructor source, so every render seam that already
        does ``repr(arg)`` emits round-trippable code with no change;
      * ``value`` is the pre-built live object, so call sites run the real input via
        :func:`unwrap` (no ``eval`` in the hot path);
      * ``imports`` are the module imports that source needs, surfaced so the
        generated test header can include them.
    """

    value: Any
    expr: str
    imports: tuple[str, ...] = ()

    def __repr__(self) -> str:  # the source seam: repr(arg) -> constructor code
        return self.expr


def unwrap(arg: Any) -> Any:
    """The live value of an argument — a :class:`SourceExpr`'s built object, or the
    argument itself. Applied at call sites so a synthesized non-literal input runs
    as its real value while still rendering as source."""
    return arg.value if isinstance(arg, SourceExpr) else arg


# The representative source for an AST-typed parameter: a snippet to parse and the
# accessor onto the node the annotation names. Keyed by the dotted type name from
# ``_type_of``. The value is built by eval-ing the very expr that will be rendered,
# so the live input and its emitted source are guaranteed identical.
_AST_SAMPLE: dict[str, tuple[str, str]] = {
    "ast.FunctionDef": ("def _f(x):\n    return x", "body[0]"),
    "ast.AsyncFunctionDef": ("async def _f(x):\n    return x", "body[0]"),
    "ast.Module": ("x = 1", ""),
    "ast.stmt": ("x = 1", "body[0]"),
    "ast.expr": ("1 + 1", "body[0].value"),
    "ast.AST": ("def _f(x):\n    return x", "body[0]"),
}


def synth_ast_input(type_name: str | None) -> SourceExpr | None:
    """A representative input for an ``ast.*``-typed parameter, or None if the type
    is not an AST node type. Constructs the node by parsing a small snippet — the
    natural synthesizer for AST inputs — and pairs it with the source that rebuilds
    it so the generated test reads ``ast.parse('def _f(x): ...').body[0]``, not an
    opaque ``<ast.FunctionDef object>`` repr that cannot round-trip."""
    if not type_name or not type_name.startswith("ast."):
        return None
    snippet, accessor = _AST_SAMPLE.get(type_name, _AST_SAMPLE["ast.AST"])
    expr = f"ast.parse({snippet!r})" + (f".{accessor}" if accessor else "")
    value = eval(expr, {"ast": ast})  # noqa: S307 — Detective-synthesized expr, not user input
    return SourceExpr(value=value, expr=expr, imports=("import ast",))


def param_type_names(node) -> list[str | None]:
    """The base type name of each positional parameter (excluding self/cls), from
    its annotation — the shared bridge from a function's AST to typed inputs."""
    return [_type_of(a.annotation) for a in node.args.args if a.arg not in ("self", "cls")]


_TYPE_GRID: dict[str, list] = {
    "int": [-1, 0, 1, 2, 3],
    "float": [-1.0, 0.0, 1.0, 2.5],
    "bool": [False, True],
    "str": ["", "a", "abc"],
}


def _grid_for(type_name: str | None) -> list:
    """Candidate values for a parameter of the given annotation; unknown/unannotated
    falls back to the integer grid (the most common numeric case)."""
    return _TYPE_GRID.get(type_name or "", _TYPE_GRID["int"])


def is_scalar_type(type_name: str | None) -> bool:
    """True when the type has a built-in value grid (so it needs no synthesis)."""
    return type_name in _TYPE_GRID


def bounded_product(grids: list[list], cap: int = 32) -> list[tuple]:
    """Candidate arg tuples from per-parameter value lists: full cartesian product
    when small, else positionally-zipped rows so wide signatures stay bounded."""
    if not grids:
        return [()]
    total = 1
    for grid in grids:
        total *= max(1, len(grid))
    if total <= cap:
        return [tuple(combo) for combo in itertools.product(*grids)]
    longest = max(len(grid) for grid in grids)
    return [tuple(grid[i % len(grid)] for grid in grids) for i in range(longest)]


def typed_inputs(param_types: list[str | None], cap: int = 32) -> list[tuple]:
    """Type-appropriate candidate arg tuples from parameter annotations, so the
    witness search exercises non-numeric functions (a str function gets strings,
    not ints)."""
    if not param_types:
        return [()]
    return bounded_product([_grid_for(t) for t in param_types], cap)


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
    raising (or stops raising) counts as an observable difference, not a crash.

    Arguments are unwrapped so a synthesized non-literal input (a ``SourceExpr``
    wrapping an AST node) runs as its live value, not as the carrier."""
    try:
        return repr(fn(*(unwrap(a) for a in args)))
    except Exception as exc:  # noqa: BLE001 — a raised exception IS an observable outcome
        return f"<raised {type(exc).__name__}>"


def find_witness(
    original: Callable[..., Any], mutant: Callable[..., Any], candidate_inputs: list[tuple]
) -> Witness | None:
    """The first input on which original and mutant differ by a VALUE-killable
    outcome, or None if none does.

    A witness must ground a test that pins the return VALUE (crash-as-spec): a
    value-difference (``assert f(x) == v``) or an original-raises difference
    (``pytest.raises`` pins the original's raising behaviour). A difference that
    exists ONLY because the mutant *newly raises* while the original returns is
    skipped: killing via the mutant's crash is a crash-kill, which the
    value-specification accounting does not credit — suggesting it would write a
    value-assertion the mutant never reaches and loop forever. If every
    difference is of that crash-only kind, the mutant is value-equivalent
    (crash-only-distinguishable) and None is returned.

    None does not prove equivalence — it means no value-killable input was found.
    """
    for args in candidate_inputs:
        original_outcome, mutant_outcome = _outcome(original, args), _outcome(mutant, args)
        if original_outcome == mutant_outcome:
            continue
        if mutant_outcome.startswith("<raised ") and not original_outcome.startswith("<raised "):
            continue  # crash-only kill — not a value-witness (see crash-as-spec)
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
    manual_equivalent: tuple[str, ...] = ()  # mutations manually flagged equivalent (the oracle)

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
