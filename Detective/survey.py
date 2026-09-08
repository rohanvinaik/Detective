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

from .call_sites import _param_usages, usage_inferred_type
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
      * ``reachable``           — nothing in the way; converge already reaches it. Not flagged.
    """
    if any_inexpressible_param:
        return "extractable_core"
    if has_world_effects:
        return "impure_body"
    if module_heavy_imports:
        return "trapped_by_imports"
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
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in _HEAVY_IMPORT_ROOTS:
                    roots.append(root)
                    bound.add(alias.asname or root)
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
            if root in _HEAVY_IMPORT_ROOTS:
                roots.append(root)
                for alias in node.names:
                    bound.add(alias.asname or alias.name)
    return tuple(dict.fromkeys(roots)), frozenset(bound)


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
    """True if any parameter clearly has no literal `--input` form — from its ANNOTATION, or, for an
    UNANNOTATED param, from USAGE inference (how the body uses it: a tuple subscript -> ndarray). The
    usage half is what closes the recall gap on GofL `Game.update_cell(step, xy)`: `step` is
    unannotated, but `step[xy[0], xy[1]]` types it. Reuses the same `_annotation_inexpressible`
    denylist for both an annotation string and an inferred type-name. `self`/`cls` skipped."""
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


def survey_source(source: str) -> list[SurveyFinding]:
    """Walk a module's source and return one finding per function that hides a reachable pure
    decision behind an impure boundary. Pure over the source text (parses, never executes)."""
    tree = ast.parse(source)
    heavy, bound = _heavy_imports(tree)
    module_heavy = bool(heavy)
    findings: list[SurveyFinding] = []

    def _walk(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qual = f"{prefix}{child.name}"
                # A function that REFERENCES a heavy binding genuinely uses the stack — it belongs in
                # this module, not a trapped pure decision. Only a function that uses NONE of them is
                # trapped by an import it does not need. (Still descend: an inner may differ.)
                if module_heavy and _references_names(child, bound):
                    _walk(child, f"{qual}.")
                    continue
                any_inexpressible = _param_inexpressible(child)
                effects = world_effects(child)
                disp = survey_disposition(any_inexpressible, bool(effects), module_heavy)
                if disp != "reachable":
                    detail = _EXTRACTION[disp]
                    if disp == "trapped_by_imports":
                        detail = f"{detail} (module imports {', '.join(heavy)})"
                    elif disp == "impure_body":
                        detail = f"{detail} (body: {', '.join(effects)})"
                    findings.append(SurveyFinding(qual, child.lineno, disp, detail))
                _walk(child, f"{qual}.")
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
    """The `detective survey` report — advisory, writes nothing."""
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
    out = [
        f"{path} — survey · {total} trapped pure decision(s): {counts}   (static advisory)",
        "",
        "  These functions hide a pinnable pure decision behind an impure boundary. Extracting each",
        "  lets converge REACH and pin it. Advisory only — proposes, never performs; converge each",
        "  extracted decision in isolation the normal way.",
        "",
    ]
    for f in findings:
        out.append(f"  {f.lineno:>5}  {f.qualname}")
        out.append(f"         {f.disposition} — {f.detail}")
    out.append("")
    out.append("  · Next           detective extract '<file>::<function>' names the concrete extraction")
    out.append("                   (a pure function over primitives) to pull out, then converge it.")
    out.append("  · Recall bound   an unannotated param with AMBIGUOUS usage (a plain subscript or")
    out.append("                   arithmetic) is not flagged — only high-confidence usage is inferred.")
    return out
