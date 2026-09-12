"""`detective survey` — a static, opt-in advisory that finds pure decisions trapped behind an impure
boundary, and names the extraction that would let converge REACH and pin them.

The single highest-leverage move for knowability, done reflexively by a fluent operator and never by
a naive one: pull the pure decision out of an impure shell so `--input` can express it. This pass
turns that tribal reflex into a per-function yes/no. It is STATIC (AST only, no execution), it WRITES
NOTHING, and it PROPOSES never performs — each proposed extraction is then converged in isolation the
normal way. So it honors the sandwich thesis (the unit stays ONE function); it only widens WHERE to
point Detective, never what a pin means.

Surfaced by the follow-graph dogfood (docs/dogfood/pabkit_2026-09-06.md): conorheins `str2bool` (a
pure str->bool decision trapped behind `import jax`), GofL `Game.update_cell` (a pure Conway rule
behind an ndarray param), pabkit's metric decisions buried in torch/IO shells.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

from .call_sites import _param_usages, usage_evidence_class, usage_inferred_type
from .purity import world_effects

# Modules whose mere top-level import makes a file expensive or IMPOSSIBLE to load for a greenfield
# interpreter — the "heavy stack" that traps an otherwise-reachable pure function. Deliberately NOT
# numpy/pandas (too common to be signal); these are the ones that gate reach or fail outright.
_HEAVY_IMPORT_ROOTS = frozenset(
    {"torch", "tensorflow", "jax", "jaxlib", "cv2", "matplotlib", "scipy", "sklearn", "keras"}
)

# Annotation ROOTS that clearly have NO literal `--input` form — a param typed as one of these wraps
# a pure decision converge cannot reach by input synthesis. A DENYLIST, deliberately: an unknown root
# (a project type alias like `Grid`/`Numerical`, an unresolved name) is treated as POSSIBLY
# expressible and NOT flagged, so the survey does not cry wolf on aliased primitive containers.
# Callable is omitted on purpose — a callable param makes a function higher-order, but there is no
# pure sub-decision over primitives to extract from it, so flagging it would be noise.
_INEXPRESSIBLE_ROOTS = frozenset(
    {"ndarray", "Tensor", "DataFrame", "Series", "np", "torch", "jnp", "tf", "pd", "cupy"}
)


def _annotation_root(annotation: str) -> str:
    """The leading identifier of a (possibly subscripted/dotted) annotation string: `tuple[int]`
    -> `tuple`, `np.ndarray` -> `np`, `Optional[int]` -> `Optional`. Empty for no annotation."""
    text = annotation.strip()
    if not text:
        return ""
    head = text.replace("[", " ").replace("(", " ").split()[0]
    return head.split(".")[0]


def _annotation_inexpressible(annotation: str) -> bool:
    """Does this parameter annotation CLEARLY have no literal `--input` form? (#pure — pinned)

    True only for a KNOWN inexpressible data-object root (ndarray/Tensor/DataFrame/Series, or a dotted
    `np.*`/`torch.*`/`jnp.*`). False for everything else — a primitive, a container, an unknown
    project alias (`Grid`, `Numerical`), an EMPTY annotation, a Callable, or a bare `Any`/`object`
    (too broad to be signal — identity/equality would read as extractable when nothing is). A
    conservative denylist: it flags a genuine array/frame param and stays quiet on aliases it cannot
    resolve and on polymorphic params (a recall gap, disclosed in the report, never a clean bill)."""
    return _annotation_root(annotation) in _INEXPRESSIBLE_ROOTS


def survey_disposition(
    any_inexpressible_param: bool,
    has_world_effects: bool,
    module_heavy_imports: bool,
    any_unresolved_param: bool = False,
) -> str:
    """What stands between converge and this function's pure decision (#pure — pinned).

    Returns a NAMED code, most-blocking first (two conditions that mean different extractions must
    not collapse):

      * ``extractable_core``    — a param has no literal form, so the pure sub-decision it wraps is
                                  unreachable. Extract that decision as a total function over
                                  primitives (the highest, hardest block — the param itself).
      * ``impure_body``         — params ARE expressible, but the body is entangled with world
                                  effects (torch/np/open/plt). The decision can be split from the I/O.
      * ``trapped_by_imports``  — the function is pure AND expressible, but its MODULE's top-level
                                  imports are the heavy stack; converge cannot load it cheaply.
                                  Extract it to a leaf module with no heavy imports.
      * ``unresolved_param``    — a param is used in an object-shaped way no supported inference
                                  resolves (a tuple subscript: ndarray or tuple-keyed dict, both
                                  plausible, neither provable from the body). NOT a claim that the
                                  param is inexpressible — a claim that the question is OPEN, which
                                  is why it ranks below every proven block and above silence.
      * ``reachable``           — nothing in the way; converge already reaches it. Not flagged.

    ``unresolved_param`` is R4. v1 inferred ndarray from a tuple subscript, which is unsound (a
    dict takes one); the 2026-09-07 wave correctly stopped, and GofL `Game.update_cell` /
    `count_neighbors` fell from ``extractable_core`` straight to ``reachable`` — the same silence
    as a plain `int`. Removing an unsound CLAIM was right; sending the parameter to silence was the
    regression, because "we cannot resolve this" and "there is nothing here" are different answers
    and only one of them is true.
    """
    if any_inexpressible_param:
        return "extractable_core"
    if has_world_effects:
        return "impure_body"
    if module_heavy_imports:
        return "trapped_by_imports"
    if any_unresolved_param:
        return "unresolved_param"
    return "reachable"


@dataclass(frozen=True)
class SurveyFinding:
    """One function the survey flagged, with the extraction it proposes."""

    qualname: str
    lineno: int
    disposition: str
    detail: str


_EXTRACTION = {
    "extractable_core": "extract the pure decision over primitives so --input can express it",
    "impure_body": "split the pure decision out of the I/O so converge can pin it",
    "trapped_by_imports": "move it to a leaf module with no heavy imports so converge reaches it",
    # Phrased as a QUESTION, not an instruction. The others name a proven block and its extraction;
    # this one reports that the evidence is object-shaped and unresolved, and hands the judgement
    # back — which is the only honest thing to say about a tuple subscript that an ndarray and a
    # tuple-keyed dict both accept.
    "unresolved_param": (
        "an unannotated param is used as an object (a tuple subscript) — an ndarray and a"
        " tuple-keyed dict both fit, so this is unresolved, not clean; annotate it, or check"
        " whether a pure decision is trapped behind it"
    ),
}


def _heavy_imports(tree: ast.Module) -> tuple[tuple[str, ...], frozenset[str]]:
    """Heavy module roots imported at TOP LEVEL, and the NAMES those imports bind into the module.

    The bound names are the load-bearing half: a function that REFERENCES one (jnp, vmap, plt)
    genuinely uses the heavy stack and belongs in this module — it is NOT a trapped pure decision.
    Only a function that touches NONE of them is trapped by an import it does not use. (Top level
    only — a lazy local import does not gate loading the module.)
    """
    roots: list[str] = []
    bound: set[str] = set()
    for node in tree.body:  # top level only
        node_roots, names = _heavy_import_binding(node)
        roots.extend(node_roots)
        bound.update(names)
    return tuple(dict.fromkeys(roots)), frozenset(bound)


def _heavy_import_binding(node: ast.stmt) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """One statement's heavy roots and the names it binds — ((), ()) when it is not a heavy import.

    Split out so the caller is a flat accumulation. The two import FORMS bind names differently
    (`import x.y as z` binds one name per alias, and ONE statement may carry several heavy roots;
    `from x import a, b` has one root and binds every alias), and interleaving that with the
    accumulation put four levels of nesting in a single loop.
    """
    if isinstance(node, ast.Import):
        heavy = [a for a in node.names if a.name.split(".")[0] in _HEAVY_IMPORT_ROOTS]
        return (
            tuple(a.name.split(".")[0] for a in heavy),
            tuple(a.asname or a.name.split(".")[0] for a in heavy),
        )
    if isinstance(node, ast.ImportFrom) and node.module:
        root = node.module.split(".")[0]
        if root in _HEAVY_IMPORT_ROOTS:
            return (root,), tuple(alias.asname or alias.name for alias in node.names)
    return (), ()


def _references_names(func: ast.FunctionDef | ast.AsyncFunctionDef, names: frozenset[str]) -> bool:
    """Does the function body reference any of `names`? (`plt.subplots` reads `plt` as an ast.Name,
    so scanning Name nodes covers attribute access too.)"""
    if not names:
        return False
    return any(
        isinstance(node, ast.Name) and node.id in names
        for statement in func.body
        for node in ast.walk(statement)
    )


def _param_inexpressible(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """True if any parameter CLEARLY has no literal `--input` form — from its ANNOTATION, or, for an
    UNANNOTATED param, from a HIGH-PRECISION usage signal (an array attribute `.shape`/`.dtype`, a
    str method). Reuses the same `_annotation_inexpressible` denylist for both an annotation string
    and an inferred type-name. `self`/`cls` skipped.

    A tuple subscript does NOT reach here. This docstring used to claim it did — "the usage half is
    what closes the recall gap on GofL `Game.update_cell(step, xy)`" — and that stopped being true
    when the 2026-09-07 wave correctly stopped inferring ndarray from `p[i, j]`, since a tuple-keyed
    dict accepts one too. The claim outlived the code by a full wave, which is how the regression
    stayed invisible. That case belongs to `_param_unresolved`: object-shaped use nothing here
    resolves is an OPEN question, and this function reports only PROVEN blocks."""
    args = func.args
    all_args = [*args.posonlyargs, *args.args, *args.kwonlyargs]
    if args.vararg:
        all_args.append(args.vararg)
    if args.kwarg:
        all_args.append(args.kwarg)
    for arg in all_args:
        if arg.arg in ("self", "cls"):
            continue
        annotation = ast.unparse(arg.annotation) if arg.annotation is not None else ""
        recovered = annotation or usage_inferred_type(_param_usages(func, arg.arg))
        if recovered and _annotation_inexpressible(recovered):
            return True
    return False


def _param_unresolved(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """True if an UNANNOTATED parameter is used in an object-shaped way nothing here resolves.

    Deliberately separate from `_param_inexpressible` rather than folded into it. That function
    answers "is this provably without a literal form"; this one answers "is the question open".
    Merging them would put an unproven case behind a proven one's name — the collapse R4 exists to
    undo — and would also risk changing `_param_inexpressible`'s established behaviour, which is
    the half that is currently correct.

    ANNOTATED parameters are skipped entirely: an annotation is an answer, so there is nothing
    unresolved about them whichever way it reads. `self`/`cls` skipped as everywhere else.
    """
    args = func.args
    all_args = [*args.posonlyargs, *args.args, *args.kwonlyargs]
    if args.vararg:
        all_args.append(args.vararg)
    if args.kwarg:
        all_args.append(args.kwarg)
    for arg in all_args:
        if arg.arg in ("self", "cls") or arg.annotation is not None:
            continue
        if usage_evidence_class(_param_usages(func, arg.arg)) == "unresolved_object":
            return True
    return False


def survey_source(source: str) -> list[SurveyFinding]:
    """Walk a module's source and return one finding per function that hides a reachable pure
    decision behind an impure boundary. Pure over the source text (parses, never executes)."""
    tree = ast.parse(source)
    heavy, bound = _heavy_imports(tree)
    module_heavy = bool(heavy)
    findings: list[SurveyFinding] = []

    def _finding(child: ast.FunctionDef | ast.AsyncFunctionDef, qual: str) -> SurveyFinding | None:
        """This function's finding, or None when its pure decision is already reachable.

        Split out so `_walk` is only a traversal. Inline, the DECISION (four inputs, then a detail
        string that varies by disposition) sat three levels deep inside the walk, and the two jobs
        had to be read together to see that the `continue` above is about descent, not verdict.
        """
        # A function that REFERENCES a heavy binding genuinely uses the stack — it belongs in this
        # module, not a trapped pure decision. Only one that uses NONE of them is trapped by an
        # import it does not need.
        if module_heavy and _references_names(child, bound):
            return None
        effects = world_effects(child)
        disp = survey_disposition(
            _param_inexpressible(child), bool(effects), module_heavy, _param_unresolved(child)
        )
        if disp == "reachable":
            return None
        detail = _EXTRACTION[disp]
        if disp == "trapped_by_imports":
            detail = f"{detail} (module imports {', '.join(heavy)})"
        elif disp == "impure_body":
            detail = f"{detail} (body: {', '.join(effects)})"
        return SurveyFinding(qual, child.lineno, disp, detail)

    def _walk(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qual = f"{prefix}{child.name}"
                found = _finding(child, qual)
                if found is not None:
                    findings.append(found)
                _walk(child, f"{qual}.")  # descend regardless: an inner function may differ
            elif isinstance(child, ast.ClassDef):
                _walk(child, f"{prefix}{child.name}.")

    _walk(tree, "")
    return findings


def survey_scan_status(scanned: int, failed: int) -> str:
    """Name what was examined without promoting omission to clean (#D, pure — pinned)."""
    if failed:
        return "incomplete"
    if not scanned:
        return "empty"
    return "observed"


def render_survey(path: str, findings: list[SurveyFinding]) -> list[str]:
    """The `detective survey` report — advisory, writes nothing to your project."""
    total = len(findings)
    if total == 0:
        return [
            f"{path} — survey · 0 trapped pure decisions   (static advisory)",
            "",
            "  No trap detected within this static scan.",
            "  Unresolved types and ambiguous uses are not proved --input-reachable.",
        ]
    by_disp: dict[str, int] = {}
    for f in findings:
        by_disp[f.disposition] = by_disp.get(f.disposition, 0) + 1
    counts = " · ".join(f"{n} {d}" for d, n in by_disp.items())
    # TRAPPED and UNRESOLVED are counted apart, and the headline claims only the first. A
    # `unresolved_param` finding says the evidence is object-shaped and no supported inference
    # settles it — calling that a "trapped pure decision" would assert exactly what it does not
    # know, and would re-introduce the cry-wolf the tuple-subscript inference was removed for.
    # The regression this repair undoes was a false NEGATIVE; the headline must not answer it with
    # a false positive (#R4).
    unresolved = by_disp.get("unresolved_param", 0)
    trapped = total - unresolved
    if trapped and unresolved:
        head = f"{trapped} trapped pure decision(s) · {unresolved} unresolved: {counts}"
    elif unresolved:
        head = f"{unresolved} unresolved param(s): {counts}"
    else:
        head = f"{trapped} trapped pure decision(s): {counts}"
    out = [f"{path} — survey · {head}   (static advisory)", ""]
    if trapped:
        out += [
            "  TRAPPED — these hide a pinnable pure decision behind an impure boundary. Extracting",
            "  each lets converge REACH and pin it. Advisory only — proposes, never performs;",
            "  converge each extracted decision in isolation the normal way.",
            "",
        ]
    if unresolved:
        out += [
            "  UNRESOLVED — an unannotated param is used as an object and no supported inference",
            "  settles WHICH. Not a finding that a decision is trapped, and not a clean bill either:",
            "  the question is open. Annotate the param and re-run, and the survey can answer it.",
            "",
        ]
    for f in findings:
        out.append(f"  {f.lineno:>5}  {f.qualname}")
        out.append(f"         {f.disposition} — {f.detail}")
    out.append("")
    out.append("  · Next           detective extract '<file>::<function>' names the concrete extraction")
    out.append("                   (a pure function over primitives) to pull out, then converge it.")
    out.append("  · Recall bound   a plain subscript, an int index, arithmetic or a comparison is NOT")
    out.append("                   flagged: those are ambiguous with ordinary primitives, so silence")
    out.append("                   there is correct rather than complete.")
    return out
