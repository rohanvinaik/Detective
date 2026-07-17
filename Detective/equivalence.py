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
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


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


# Modules an input EXPRESSION may reference. An allowlist, not a sandbox: it is what makes
# "no arbitrary code execution" a checkable property rather than a hope. ``ast`` is here
# because AST nodes are the inputs with no literal form — the reason the expression path
# exists at all. Add a module only when its constructors are the only way to express some
# parameter, and never one that touches the filesystem, network, or process table.
INPUT_MODULES: dict[str, Any] = {"ast": ast}

# The node types an input expression may contain. A WHITELIST, because a blacklist of
# "dangerous" forms is unbounded and this is not.
_INPUT_SAFE_NODES: tuple[type, ...] = (
    ast.Expression,
    ast.Call,
    ast.Attribute,
    ast.Subscript,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.Tuple,
    ast.List,
    ast.Dict,
    ast.Set,
    ast.Slice,
    ast.keyword,
    ast.Starred,
    ast.UnaryOp,
    ast.USub,
    ast.UAdd,
)


class InputExpressionError(ValueError):
    """An input expression that is not a permitted constructor over :data:`INPUT_MODULES`."""


def reject_unsafe_expression(node: ast.AST, src: str, names: dict[str, Any] | None = None) -> None:
    """Raise :class:`InputExpressionError` unless ``node`` is a plain constructor call.

    EMPTYING ``__builtins__`` IS NOT A SANDBOX, and treating it as one is the bug this
    exists to prevent. Python's object graph is reachable from any literal:
    ``().__class__.__mro__[1].__subclasses__()`` walks tuple -> type -> object -> every
    loaded class, ``subprocess.Popen`` among them. No name lookup is involved, so no
    namespace restriction can see it coming — it is ordinary attribute access. Verified:
    with builtins emptied and only ``ast`` in scope, that expression still evaluated.

    So the GRAMMAR is restricted, not just the namespace: every node must be in
    ``_INPUT_SAFE_NODES`` (no lambda, comprehension, walrus, f-string, await); every free
    name must be allowlisted; and no dunder attribute may be touched, which is what severs
    the escape above. Both layers are load-bearing; neither suffices alone.

    ``names`` is the TARGET MODULE's own namespace, and it is what makes the residual
    fillable for a domain object. Without it the allowlist is ``{ast}``, so ``Account(...)``
    is rejected — and the tool then prints ``supply --input "(<account>, ...)"`` for a slot
    no ``--input`` could ever fill, which is precisely the dead end this function's sibling
    docstring already names for ``ast.FunctionDef``. Nothing is loosened that matters: the
    class comes from the module under test, the same module the caller's own tests import
    and the same one the engine already seeds every mutant's namespace from. The grammar
    gate and the dunder ban are untouched, and they are the two that sever the escape —
    the name layer never could.

    This is a usage gate for a developer's own inputs, not a defence against someone who
    already has shell access to the same machine — but it does make "an input cannot run
    arbitrary code" a property that is CHECKED rather than asserted.
    """
    allowed = {**INPUT_MODULES, **(names or {})}
    for sub in ast.walk(node):
        if not isinstance(sub, _INPUT_SAFE_NODES):
            raise InputExpressionError(
                f"only constructor expressions and literals are allowed — "
                f"{type(sub).__name__} is not permitted in {src!r}"
            )
        if isinstance(sub, ast.Attribute) and sub.attr.startswith("__"):
            raise InputExpressionError(
                f"dunder attributes may not be touched ({sub.attr!r} in {src!r}) — "
                "that is the object-graph escape, not an input"
            )
        if isinstance(sub, ast.Name) and sub.id not in allowed:
            raise InputExpressionError(
                f"{sub.id!r} is not available in {src!r} — use a literal, `ast.*`, or a name "
                f"defined in the module under test ({', '.join(sorted(allowed)) or 'none'})"
            )


def parse_input_expression(s: str, ns: dict[str, Any] | None = None) -> tuple:
    """One positional-argument tuple from a literal OR a constructor expression.

    THE SINGLE DEFINITION OF WHAT AN INPUT MAY BE. Both ends of the input lifecycle must
    agree, or the store becomes write-only: ``samples.remember`` records ``repr(args)`` —
    for a non-literal that is its CONSTRUCTOR SOURCE — and a literal-only reader then
    drops on reload exactly what the writer just saved, so a supplied ``--input`` works
    once and silently evaporates on the next run. Parsing lives here, imported by the CLI
    (which accepts inputs) and by ``samples`` (which reloads them), so the two cannot
    drift apart on what is expressible.

    ``ns`` is the TARGET MODULE's namespace, and it is what makes the documented interface
    true. The README promises ``--input`` carries "a plan name, a lookup key, a valid domain
    object" — but with the allowlist at ``{ast}`` a domain object was rejected, so the tool
    printed ``supply --input "(<account>, ...)"`` for a slot no input could fill: the exact
    dead end this docstring already describes for ``ast.FunctionDef``, one type wider.
    Passing the module under test closes it, and nothing weakens: the class is from the same
    module the caller's own tests import and the engine already seeds every mutant from, while
    the grammar gate and dunder ban — the two layers that actually sever the object-graph
    escape — are untouched.

    Non-literal arguments come back as :class:`SourceExpr`, carrying both the live value
    and the source that rebuilds it, so a generated test reads ``Account('gold', 500.0, [])``
    and not an un-round-trippable ``<billing.Account object at 0x...>``.

    Raises :class:`InputExpressionError` for anything unparseable or not permitted; see
    :func:`reject_unsafe_expression` for the boundary and what it is not.
    """
    try:
        return _literal_tuple(ast.literal_eval(s))
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        pass
    try:
        tree = ast.parse(s, mode="eval")
    except SyntaxError as exc:
        raise InputExpressionError(f"not a valid literal or expression: {s!r} ({exc})") from None

    target_ns = {k: v for k, v in (ns or {}).items() if not k.startswith("_")}
    module = (ns or {}).get("__name__", "")
    elements = tree.body.elts if isinstance(tree.body, ast.Tuple) else [tree.body]
    args: list[Any] = []
    for elt in elements:
        src = ast.unparse(elt)
        reject_unsafe_expression(elt, src, target_ns)
        try:
            # Grammar checked above, builtins emptied here: BOTH are required.
            value = eval(  # noqa: S307 — grammar-checked, allowlisted, no builtins
                compile(ast.Expression(body=elt), "<input>", "eval"),
                {"__builtins__": {}, **INPUT_MODULES, **target_ns},
            )
        except Exception as exc:  # noqa: BLE001 — a bad input is a usage error, not a crash
            raise InputExpressionError(f"failed to evaluate {src!r}: {exc}") from None
        try:
            ast.literal_eval(elt)
            args.append(value)  # a literal needs no carrier
        except (ValueError, SyntaxError):
            imports = [f"import {m}" for m in sorted(INPUT_MODULES) if f"{m}." in src]
            # A target-module name needs `from <module> import <Name>`, or the generated test
            # renders `Account(...)` and NameErrors — which `property_holds` then rejects, and
            # the killing test silently never gets written.
            names = sorted({n.id for n in ast.walk(elt) if isinstance(n, ast.Name) and n.id in target_ns})
            if module and names:
                imports.append(f"from {module} import {', '.join(names)}")
            args.append(SourceExpr(value=value, expr=src, imports=tuple(imports)))
    return tuple(args)


def _literal_tuple(value: Any) -> tuple:
    """A parsed literal as an argument tuple; a bare value is one positional argument."""
    return value if isinstance(value, tuple) else (value,)


# The representative source for an AST-typed parameter: a snippet to parse and the
# accessor onto the node the annotation names. Keyed by the dotted type name from
# ``_type_of``. The value is built by eval-ing the very expr that will be rendered,
# so the live input and its emitted source are guaranteed identical.
# The FunctionDef sample must be RICH, not minimal. A consumer of an ``ast.FunctionDef``
# is almost always looking FOR something — an assignment, a comparison, a call, a raise —
# and ``def _f(x): return x`` contains none of them. Against that input the interesting
# branches are unreachable, every mutant in them survives, and converge reports them as
# "look equivalent but UNPROVEN": not because the code is unspecified, but because no
# input ever reached it. Measured on Wesker's ``_deletable_stmt_ids``: 64 of 68 behaviors
# unreachable against the trivial sample, and the one golden capture that could be pinned
# asserted ``== set()``.
#
# So the sample carries one of each construct the AST-analysis functions dispatch on:
# arithmetic, a REBINDING (bound name reassigned), a comparison, a raise, a call, string
# and numeric constants, and a return value. Bigger is not better — every extra statement
# widens the rendered source in each generated test — but reachable beats small.
_RICH_FUNC = (
    "def _f(x, y):\n"
    "    total = x + y\n"
    "    total = abs(total)\n"
    "    if total > 10:\n"
    "        raise ValueError('big')\n"
    "    return round(total, 2)"
)

_AST_SAMPLE: dict[str, tuple[str, str]] = {
    "ast.FunctionDef": (_RICH_FUNC, "body[0]"),
    "ast.AsyncFunctionDef": ("async def _f(x, y):\n" + _RICH_FUNC.split("\n", 1)[1], "body[0]"),
    "ast.Module": (_RICH_FUNC, ""),
    "ast.stmt": ("total = abs(total)", "body[0]"),
    "ast.expr": ("1 + 1", "body[0].value"),
    "ast.AST": (_RICH_FUNC, "body[0]"),
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


# A GRID of AST inputs, not one sample. ``_AST_SAMPLE`` answers "give me a
# representative" (for a golden capture); this answers "give me inputs that DISTINGUISH"
# (for the witness search), and those are different jobs. One input can never separate a
# mutant from its original unless that input happens to reach the mutated line — so a
# lone sample proves nothing about the mutants it does not reach, and they are reported
# "equivalent but UNPROVEN". The grid spans the constructs AST-analysis functions
# dispatch on, so a mutant of any one branch has an input that reaches it.
#
# Ordered cheap-to-rich: ``bounded_product`` truncates at ``cap``, so the first entries
# must be the ones most likely to separate. Kept small for the same reason — the product
# across several AST params grows fast, and every entry costs a full mutant evaluation.
_AST_GRID: dict[str, list[tuple[str, str]]] = {
    "ast.FunctionDef": [
        (_RICH_FUNC, "body[0]"),
        # No statements to delete, nothing to compare, nothing raised: the "empty"
        # end of every analysis, which is where off-by-one and always-true bugs show.
        ("def _f():\n    pass", "body[0]"),
        # Aliased argument mutation + a discarded-value call: the STMT/purity surface.
        ("def _f(items, x):\n    items.append(x)\n    return len(items)", "body[0]"),
        # Exception handling: the try/except surface, with a non-trivial handler body.
        (
            "def _f(x):\n    try:\n        return int(x)\n    except ValueError:\n        return 0",
            "body[0]",
        ),
        # A method: exercises is_method / self-state paths that a bare function cannot.
        ("class C:\n    def _f(self, v):\n        self.v = v\n        return self.v", "body[0].body[0]"),
        # Assignment TARGET shapes: tuple unpack, starred, annotated. An analyser that
        # walks targets branches on each of these, and a Name-only sample reaches none of
        # them — the branches are then unreachable, so their mutants survive and get
        # reported "equivalent but UNPROVEN".
        (
            "def _f(xs, n):\n    a, b = 1, 2\n    a, b = b, a\n    *rest, last = xs\n"
            "    c: int = n\n    c: int = n + 1\n    return (a, b, rest, last, c)",
            "body[0]",
        ),
        # Nested blocks: else / finally / handler bodies are separate statement lists, and
        # a function that only walks `body` silently skips all three.
        (
            "def _f(x):\n    try:\n        y = int(x)\n    except (TypeError, ValueError):\n"
            "        y = 0\n    else:\n        y = y + 1\n    finally:\n        pass\n"
            "    for i in range(2):\n        y = y + i\n    else:\n        y = y * 2\n"
            "    while y > 100:\n        y = y - 1\n    return y",
            "body[0]",
        ),
        # Parameter KINDS: positional-only, defaults, *args, keyword-only, **kwargs. A
        # signature reader that only walks `args.args` misses posonlyargs/vararg/kwarg.
        (
            "def _f(p, /, q=1, *args, r=2, **kwargs):\n    q = abs(q)\n    return (p, q, args, r, kwargs)",
            "body[0]",
        ),
    ],
    "ast.AsyncFunctionDef": [
        ("async def _f(x, y):\n" + _RICH_FUNC.split("\n", 1)[1], "body[0]"),
        ("async def _f():\n    pass", "body[0]"),
    ],
    "ast.Module": [(_RICH_FUNC, ""), ("x = 1", "")],
    "ast.stmt": [
        ("total = abs(total)", "body[0]"),  # rebinding
        ("items.append(x)", "body[0]"),  # discarded-value call
        ("cfg[k] = v", "body[0]"),  # aliased write
        ("return x", "body[0]"),
    ],
    "ast.expr": [("1 + 1", "body[0].value"), ("a < b", "body[0].value"), ("f(x)", "body[0].value")],
}


def _ast_source_expr(snippet: str, accessor: str) -> SourceExpr:
    """Build one AST input paired with the source that rebuilds it.

    The value is produced by eval-ing the very expression that will be rendered, so the
    live input and its emitted source cannot disagree.
    """
    expr = f"ast.parse({snippet!r})" + (f".{accessor}" if accessor else "")
    value = eval(expr, {"ast": ast})  # noqa: S307 — Detective-synthesized expr, not user input
    return SourceExpr(value=value, expr=expr, imports=("import ast",))


def ast_grid(type_name: str | None) -> list[SourceExpr]:
    """Candidate inputs for an ``ast.*``-typed parameter — the witness search's grid.

    Falls back to the ``ast.AST`` entry for an AST type with no explicit grid, so a new
    node type degrades to "a few real nodes" rather than to the integer grid.
    """
    if not type_name or not type_name.startswith("ast."):
        return []
    entries = _AST_GRID.get(type_name) or _AST_GRID["ast.FunctionDef"]
    out: list[SourceExpr] = []
    for snippet, accessor in entries:
        try:
            out.append(_ast_source_expr(snippet, accessor))
        except Exception:  # noqa: BLE001,S112 — a bad entry must not sink the whole grid
            continue
    return out


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
    """Candidate values for a parameter of the given annotation.

    AST-typed parameters get the AST grid (see :func:`ast_grid`). Everything else falls
    back to the integer grid, which is right for unannotated numeric code and WRONG for
    any type the grid does not know: the witness search then feeds ``-1`` to a function
    expecting a node, every candidate dies on AttributeError, no witness is ever found,
    and every survivor is reported "equivalent but UNPROVEN" — a claim about the
    synthesizer wearing the costume of a claim about the code. Measured on Wesker's
    ``_deletable_stmt_ids`` (one ``ast.FunctionDef`` param): 64 of 68 behaviors
    unprovable, purely because the grid handed it integers.
    """
    if type_name and type_name.startswith("ast."):
        return list(ast_grid(type_name))
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
    # The original's outcome ITSELF (None when it raised — the raises-witness path pins
    # that instead). A repr cannot answer "is this a set", and that question decides
    # whether pinning the outcome by repr is sound or hash-seed flaky
    # (`characterization.golden_assert_line`). Carried, never rendered.
    #
    # ``compare=False``: a witness IS (args, original repr, mutant repr) — the live value is
    # a payload for rendering, not identity, and it is already summarised by ``original``.
    # Including it would also hand __eq__ a value that may not compare cleanly (an array).
    original_value: Any = field(default=None, compare=False)


def _outcome(fn: Callable[..., Any], args: tuple) -> str:
    """The repr of ``fn(*args)``, or a raised-marker — so a mutant that starts
    raising (or stops raising) counts as an observable difference, not a crash.

    Arguments are unwrapped so a synthesized non-literal input (a ``SourceExpr``
    wrapping an AST node) runs as its live value, not as the carrier."""
    try:
        return repr(fn(*(unwrap(a) for a in args)))
    except Exception as exc:  # noqa: BLE001 — a raised exception IS an observable outcome
        return f"<raised {type(exc).__name__}>"


def _outcome_value(fn: Callable[..., Any], args: tuple) -> Any:
    """The LIVE outcome of ``fn(*args)``, or None if it raised.

    Companion to ``_outcome``, which yields only a repr — and a repr cannot answer "is
    this a set", the question that decides whether pinning the outcome by repr is sound or
    hash-seed flaky. Called once, when a witness is actually constructed, not for every
    candidate input."""
    try:
        return fn(*(unwrap(a) for a in args))
    except Exception:  # noqa: BLE001 — a raise carries no value; `_outcome` already marked it
        return None


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
        return Witness(tuple(args), original_outcome, mutant_outcome, _outcome_value(original, args))
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


# Types `--input` can actually carry. Deliberately mirrors `_INPUT_SAFE_NODES`/`INPUT_MODULES`
# above rather than restating a guess: an input is expressible iff the parser would accept the
# source you'd have to type for it.
_LITERAL_TYPES: tuple[type, ...] = (bool, int, float, complex, str, bytes, type(None))


def is_expressible(value: Any) -> bool:
    """Could a user TYPE this value into `--input`?

    Answered against the real value, not inferred from the signature, because the signature
    is frequently unannotated — the case this matters most for. A container is expressible
    only if everything inside it is, so `[{'id': 'a', 'amount': 1.0}]` passes and
    `[Account(...)]` does not.

    A `SourceExpr` is NOT expressible even though it renders as source: it is how synthesis
    builds a domain object (a dataclass constructor), and that constructor names a class the
    `--input` allowlist refuses. Answering True there is the failure this exists to prevent —
    a next action that looks typed-out and correct and is rejected the moment it is run.
    """
    if isinstance(value, SourceExpr):
        return False
    if isinstance(value, ast.AST):  # the reason the expression path exists at all
        return True
    if isinstance(value, _LITERAL_TYPES):
        return True
    if isinstance(value, (list, tuple, set, frozenset)):
        return all(is_expressible(v) for v in value)
    if isinstance(value, dict):
        return all(is_expressible(k) and is_expressible(v) for k, v in value.items())
    return False


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
    # Can a HUMAN type the input that exercises this function, as `--input`?
    #
    # This is the difference between a next action that works and one that cannot. `--input`
    # parses an allowlisted expression — literals plus `ast.*` — which is what makes "no
    # arbitrary code execution" checkable rather than hoped-for. So for a function taking a
    # domain object there is no string the user can pass, and telling them to `supply --input
    # "(<account>, ...)"` sends them to a command that rejects `Account(...)` by design. They
    # then reasonably conclude the tool is broken. The real move is the other one the engine
    # already supports: write ONE test that calls the function with a real object, and the
    # arguments are captured from it.
    #
    # False means exactly that: something in the exercising input has no literal form. None
    # means nothing exercised the function at all (see ``note``).
    inputs_expressible: bool | None = None

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
