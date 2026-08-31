"""The computation-shape template library v1 — taste as RECOGNITION (Wave 3 / EXP-DS-004).

Design: ``docs/theory/deterministic_sicp/DETERMINISTIC_SICP.md`` §6. The claim under test: the
performance engineer's skill decomposes into (a) recognition of a bounded library of
computation-shape templates and (b) a deterministic per-template transform grammar — Regime-A
classification plus rules, not open-ended judgment. This module is (a) and the *names* of (b);
the transforms are demonstrated as seeded pairs under the Wave-2 budget harness, and their
AUTO-application is deliberately not v1 (an arc exists only where its gate runs — §8; today the
gates are `receipt`/`verify-rewrite` + the paired budget read, driven by hand).

**Recognizers are conservative by law**: every one abstains on any doubt — a near-miss MUST NOT
match, because a template match invites a transform and a false match invites a wrong one. The
discrimination discipline applies in reverse: a shape the library should recognize and doesn't
is a missing template (grow the library at population level, §4.2 law 3), never a loosened
recognizer. Recognizers walk AST nodes and are therefore the unit-guarded harvest class (the
same classification as parsimony's lens readers — guarded by intent fixtures with adversarial
negatives, not pinned cold).

**The discharge property** (the library's own success criterion, tested per template): applying
a template's transform produces code on which that recognizer NO LONGER fires — a correct
transform discharges its own template — while the Wave-2 paired read pays a refund at behavior
delta exactly 0.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

from .decompose_apply import _names
from .purity import is_pure

# Template → (transform name, the gate that must run before the transform may land).
# The gate column is the §8 actuator law as data: no gate, no arc.
TEMPLATE_GRAMMAR: dict[str, tuple[str, str]] = {
    "memoizable_pure_recursion": ("memoize", "receipt + verify-rewrite + paired budget"),
    "quadratic_membership_scan": ("set_membership", "receipt + verify-rewrite + paired budget"),
    "loop_invariant_recompute": ("hoist_invariant", "receipt + verify-rewrite + paired budget"),
    "accumulator_series": ("closed_form", "receipt + verify-rewrite + paired budget"),
    "manual_index_iteration": ("direct_iteration", "receipt + verify-rewrite + paired budget"),
}


@dataclass(frozen=True)
class TemplateMatch:
    """One recognized shape: which template, where, and the evidence that fired it — the
    five-tuple `path` discipline (a match without its provenance is a verdict without a warrant)."""

    template: str
    line: int
    evidence: str


def _loops(func: ast.FunctionDef | ast.AsyncFunctionDef):
    """Every For loop in the function body (not descending into nested defs)."""
    for node in ast.walk(func):
        if isinstance(node, ast.For):
            yield node


def _loop_target_names(loop: ast.For) -> set[str]:
    return _names(loop.target, ast.Store) | ({loop.target.id} if isinstance(loop.target, ast.Name) else set())


def recognize_memoizable_pure_recursion(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
) -> TemplateMatch | None:
    """A PURE function that calls itself: the memoization shape. Conservative: impure
    self-recursion abstains (memoizing an effectful function changes behavior — the near-miss
    that must not match), and a parameterless recursion abstains (nothing to key a cache on)."""
    if not func.args.args and not func.args.posonlyargs:
        return None
    if not is_pure(func):
        return None
    for node in ast.walk(func):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == func.name:
            return TemplateMatch("memoizable_pure_recursion", node.lineno, f"pure self-call {func.name}(…)")
    return None


def recognize_quadratic_membership_scan(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
) -> TemplateMatch | None:
    """A membership test against a LIST-evidenced name inside a loop: the linear-scan-per-
    iteration shape. List evidence is required (a `[]`/list-literal/listcomp assignment or an
    `.append` call on the name IN THIS FUNCTION) — membership against a set/dict is already
    right and must not match; a name with no local list evidence abstains (its type is not
    knowable here, and a conservative recognizer does not guess)."""
    list_names: set[str] = set()
    for node in ast.walk(func):
        if isinstance(node, ast.Assign) and isinstance(node.value, (ast.List, ast.ListComp)):
            list_names |= {t.id for t in node.targets if isinstance(t, ast.Name)}
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "append"
            and isinstance(node.func.value, ast.Name)
        ):
            list_names.add(node.func.value.id)
    if not list_names:
        return None
    for loop in _loops(func):
        for node in ast.walk(loop):
            if isinstance(node, ast.Compare) and any(isinstance(op, (ast.In, ast.NotIn)) for op in node.ops):
                for comparator in node.comparators:
                    if isinstance(comparator, ast.Name) and comparator.id in list_names:
                        return TemplateMatch(
                            "quadratic_membership_scan",
                            node.lineno,
                            f"`in {comparator.id}` (list-evidenced) inside a loop",
                        )
    return None


def recognize_loop_invariant_recompute(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
) -> TemplateMatch | None:
    """A call inside a loop whose every argument is loop-invariant: the recompute-per-iteration
    shape. Conservative on four axes: the walk covers the loop BODY only (the header's own
    iterator call executes once — `range(n)` firing here was a measured false-positive of the
    first draft, caught by the adversarial corpus); the call must take ≥1 argument (a zero-arg
    call carries no visible invariance evidence); every argument Name must be disjoint from the
    loop targets AND from every name the body assigns (a value the loop writes is not
    invariant); and the callee must be a non-builtin plain Name (hoisting a builtin like
    `print` would move an effect). Residual, stated: a USER callee's purity is not verifiable
    cross-function at v1 granularity — recognition invites, the proof gate decides."""
    import builtins

    builtin_names = set(dir(builtins))
    for loop in _loops(func):
        targets = _loop_target_names(loop)
        body_writes: set[str] = set()
        for stmt in loop.body:
            body_writes |= _names(stmt, ast.Store)
        for node in (n for stmt in loop.body for n in ast.walk(stmt)):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            callee = node.func.id
            if callee in targets or callee in body_writes or callee in builtin_names:
                continue
            arg_names: set[str] = set()
            for arg in node.args:
                arg_names |= _names(arg, ast.Load) | ({arg.id} if isinstance(arg, ast.Name) else set())
            if not node.args or not arg_names:
                continue
            if arg_names & (targets | body_writes):
                continue
            return TemplateMatch(
                "loop_invariant_recompute",
                node.lineno,
                f"{callee}({', '.join(sorted(arg_names))}) — every argument loop-invariant",
            )
    return None


def recognize_accumulator_series(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
) -> TemplateMatch | None:
    """``for i in range(…): acc += i`` — the arithmetic-series shape with a closed form.
    Deliberately narrow: the augmented add must be exactly the loop variable (any other body
    work means the loop is not merely a series and must not match)."""
    for loop in _loops(func):
        if not (
            isinstance(loop.iter, ast.Call)
            and isinstance(loop.iter.func, ast.Name)
            and loop.iter.func.id == "range"
            and isinstance(loop.target, ast.Name)
        ):
            continue
        for stmt in loop.body:
            if (
                isinstance(stmt, ast.AugAssign)
                and isinstance(stmt.op, ast.Add)
                and isinstance(stmt.value, ast.Name)
                and stmt.value.id == loop.target.id
            ):
                return TemplateMatch(
                    "accumulator_series", stmt.lineno, f"acc += {loop.target.id} over range(…)"
                )
    return None


def recognize_manual_index_iteration(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
) -> TemplateMatch | None:
    """``for i in range(len(xs)): … xs[i] …`` — index bookkeeping standing in for direct
    iteration. Requires the subscript to actually appear (a range-len loop that never indexes
    is counting, not iterating, and must not match)."""
    for loop in _loops(func):
        it = loop.iter
        if not (
            isinstance(it, ast.Call)
            and isinstance(it.func, ast.Name)
            and it.func.id == "range"
            and len(it.args) == 1
            and isinstance(it.args[0], ast.Call)
            and isinstance(it.args[0].func, ast.Name)
            and it.args[0].func.id == "len"
            and len(it.args[0].args) == 1
            and isinstance(it.args[0].args[0], ast.Name)
            and isinstance(loop.target, ast.Name)
        ):
            continue
        seq, idx = it.args[0].args[0].id, loop.target.id
        for node in ast.walk(loop):
            if (
                isinstance(node, ast.Subscript)
                and isinstance(node.value, ast.Name)
                and node.value.id == seq
                and isinstance(node.slice, ast.Name)
                and node.slice.id == idx
            ):
                return TemplateMatch(
                    "manual_index_iteration", node.lineno, f"{seq}[{idx}] under range(len({seq}))"
                )
    return None


_RECOGNIZERS = (
    recognize_memoizable_pure_recursion,
    recognize_quadratic_membership_scan,
    recognize_loop_invariant_recompute,
    recognize_accumulator_series,
    recognize_manual_index_iteration,
)


def template_matches(func: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[TemplateMatch, ...]:
    """Every template that fires on this function — a function can host several shapes at
    different lines, and the matches are reported side by side, never collapsed to one. An
    empty tuple is the honest majority verdict: no recognized shape (which is NOT a claim the
    function is optimal — the library is v1 and its gaps are grown at population level)."""
    found = []
    for recognize in _RECOGNIZERS:
        match = recognize(func)
        if match is not None:
            found.append(match)
    return tuple(found)
