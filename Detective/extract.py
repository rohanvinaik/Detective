"""`detective extract` — propose the pure decision to pull out of an impure shell (Finding D).

`survey` DETECTS that a function hides a pinnable pure decision behind an impure boundary; `decompose`
will not PERFORM that extraction (its seam criterion is cognitive complexity, and it refuses to apply
any transform it cannot prove behaviour-preserving — which is exactly the impure function converge
cannot pin). So a greenfield author told "extract the pure decision" was left with no tool that acts.

`extract` closes that gap, propose-only: for a survey-flagged function it names the CONCRETE
extraction — a pure function over the PRIMITIVE values the decision reads (the expressible parameters,
plus the scalars projected out of the inexpressible one: a cell read `grid[i, j]`, a length, a
neighbour count) — so the operator's move becomes a mechanical hand-extraction plus a `converge` on
the result. It WRITES NOTHING and PROVES NOTHING: the guarantee comes afterward, from converging the
extracted pure function in isolation (which CAN be pinned), never from this proposal. It honours the
sandwich thesis exactly as survey does — it widens WHERE to point Detective, never what a pin means.

The safety model follows the founder's ruling on the in-process efficiency hack (Finding B): a
transform that cannot be proven is PROPOSED for human review, never auto-applied on a green rerun
(the same `apply_disposition` gate decompose uses). `extract` therefore has no ``--apply``.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

from .call_sites import _param_usages, usage_inferred_type
from .survey import _annotation_inexpressible, _heavy_imports, survey_source

# Attribute/method calls on the inexpressible param that yield a PRIMITIVE the decision can take as a
# plain argument — a scalar element read, a length, a shape component. Deliberately small: only reads
# whose result is near-certainly a primitive, so a proposed input is one converge can actually express.
_PRIMITIVE_PROJECTIONS = frozenset({"len", "sum", "count", "size", "min", "max", "index"})


def _all_args(func: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.arg]:
    """Every parameter arg node, ``self``/``cls`` dropped (they carry no decision)."""
    a = func.args
    args = [*a.posonlyargs, *a.args, *a.kwonlyargs]
    if a.vararg:
        args.append(a.vararg)
    if a.kwarg:
        args.append(a.kwarg)
    return [arg for arg in args if arg.arg not in ("self", "cls")]


def _inexpressible_params(func: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[str, ...]:
    """The parameters with no literal `--input` form — the boundary the decision is trapped behind.

    Per-arg mirror of survey's `_param_inexpressible`: the annotation root, or (for an unannotated
    param) the type inferred from how the body USES it — decided over survey's same denylist, so
    `extract` and `survey` flag the identical params."""
    out: list[str] = []
    for arg in _all_args(func):
        annotation = ast.unparse(arg.annotation) if arg.annotation is not None else ""
        recovered = annotation or usage_inferred_type(_param_usages(func, arg.arg))
        if recovered and _annotation_inexpressible(recovered):
            out.append(arg.arg)
    return tuple(out)


def _primitive_locals(
    func: ast.FunctionDef | ast.AsyncFunctionDef, trapped: frozenset[str]
) -> tuple[str, ...]:
    """Local names assigned a PRIMITIVE projected out of a trapped param — the decision's real inputs.

    ``alive = grid[i, j]`` (a subscript of an ndarray yields a scalar), ``n = len(cells)``,
    ``s = neighbours(grid, i, j)`` (a call whose args touch the trapped param). Each is a plain value
    the extracted pure function can take as an argument, so naming them turns "extract the decision"
    into a concrete signature. Sorted + deduped; a name bound more than once is reported once.
    """
    found: list[str] = []

    def _touches_trapped(node: ast.AST) -> bool:
        return any(isinstance(n, ast.Name) and n.id in trapped for n in ast.walk(node))

    for stmt in ast.walk(func):
        if not isinstance(stmt, ast.Assign) or not isinstance(stmt.value, (ast.Subscript, ast.Call)):
            continue
        value = stmt.value
        is_primitive_read = (
            isinstance(value, ast.Subscript)
            and _touches_trapped(value)
            or (
                isinstance(value, ast.Call)
                and (
                    (isinstance(value.func, ast.Name) and value.func.id in _PRIMITIVE_PROJECTIONS)
                    or _touches_trapped(value)
                )
            )
        )
        if not is_primitive_read:
            continue
        for tgt in stmt.targets:
            if isinstance(tgt, ast.Name) and tgt.id not in found:
                found.append(tgt.id)
    return tuple(sorted(found))


@dataclass(frozen=True)
class ExtractionProposal:
    """The concrete pure decision `extract` proposes pulling out — advisory, never applied."""

    qualname: str
    lineno: int
    disposition: str  # survey's disposition — why the decision is trapped
    trapped_params: tuple[str, ...]  # the impure boundary
    proposed_name: str  # the pure function to create
    primitive_inputs: tuple[str, ...]  # its arguments — the primitives the decision reads
    heavy_imports: tuple[str, ...] = ()  # for trapped_by_imports: the module roots that block reach


def extract_readiness(disposition: str, has_primitive_inputs: bool) -> str:
    """Whether a concrete extraction can be PROPOSED for this function (#D, pure — pinned).

    A named code, never a bool, because the two "cannot propose" reasons need different guidance:
      * ``propose``          — a trapped pure decision AND at least one primitive input was identified,
                               so a concrete signature can be offered.
      * ``no_primitive_seam`` — trapped, but no primitive value was found to key the decision on (the
                               body uses the impure object throughout): a hand extraction with no
                               signature `extract` can name — say so rather than propose an empty one.
      * ``move``             — trapped_by_imports: the function is already pure and expressible, stranded
                               only by its MODULE's heavy top-level imports. The move is to relocate it
                               verbatim to a leaf module, not to extract a sub-decision.
      * ``reachable``        — not trapped (survey would not flag it); nothing to extract.
    """
    if disposition == "reachable":
        return "reachable"
    if disposition == "trapped_by_imports":
        return "move"
    return "propose" if has_primitive_inputs else "no_primitive_seam"


def extract_proposal(source: str, qualname: str) -> ExtractionProposal | None:
    """Propose the pure decision to pull out of ``qualname`` — or None when nothing is trapped.

    Pure over the source text (parses, never executes). Mirrors survey's detection so the two agree by
    construction, then adds the concrete primitive-input identification survey does not.
    """
    target = qualname.split(".")[-1]
    # Take the DISPOSITION from survey itself, so `extract` and `survey` flag the identical functions
    # (the whole point of Finding D — they must not disagree). Prefer an exact qualname match; fall
    # back to the unique last-segment match for a bare `func` target.
    findings = survey_source(source)
    finding = next((f for f in findings if f.qualname == qualname), None) or next(
        (f for f in findings if f.qualname.split(".")[-1] == target), None
    )
    if finding is None:
        return None
    tree = ast.parse(source)
    node = next(
        (
            n
            for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == target
        ),
        None,
    )
    trapped = _inexpressible_params(node) if node is not None else ()
    primitives = _primitive_locals(node, frozenset(trapped)) if node is not None else ()
    heavy, _bound = _heavy_imports(tree)
    return ExtractionProposal(
        qualname=qualname,
        lineno=finding.lineno,
        disposition=finding.disposition,
        trapped_params=trapped,
        proposed_name=f"{target}_decision",
        primitive_inputs=primitives,
        heavy_imports=heavy,
    )


def render_extract(path: str, proposal: ExtractionProposal | None) -> list[str]:
    """The `detective extract` report — advisory, writes nothing, proves nothing."""
    if proposal is None:
        return [
            f"{path} — extract · nothing trapped   (static advisory)",
            "",
            "  ✓ no pure decision is trapped here — converge already reaches this function.",
        ]
    readiness = extract_readiness(proposal.disposition, bool(proposal.primitive_inputs))
    target = proposal.qualname.split(".")[-1]
    if readiness == "move":
        roots = ", ".join(proposal.heavy_imports) or "the heavy stack"
        return [
            f"{path} — extract · a pure function trapped behind heavy module imports   (static advisory)",
            "",
            f"  `{proposal.qualname}` is already pure and --input-expressible — only its MODULE's",
            f"  top-level imports ({roots}) stop converge from loading it cheaply.",
            "",
            "  Proposed move (no sub-decision to extract — relocate the function verbatim):",
            f"      move `{target}` to a leaf module with no heavy imports, then pin it there:",
            f"      detective converge '<leaf_module>.py::{target}'",
            "",
            "  · Advisory       proposes, never performs; writes nothing and proves nothing. The",
            "                   guarantee comes from converging the MOVED function, not this proposal.",
        ]
    boundary = ", ".join(proposal.trapped_params) or "an impure body"
    out = [
        f"{path} — extract · a pure decision is trapped behind `{boundary}`   (static advisory)",
        "",
    ]
    if readiness == "propose":
        sig = ", ".join(f"{p}: <primitive>" for p in proposal.primitive_inputs)
        out += [
            "  Proposed extraction (pure — converge can pin it in isolation once you apply it by hand):",
            f"      def {proposal.proposed_name}({sig}) -> <return>:",
            "          # the decision, over the primitive values the function computes from the",
            f"          # trapped {boundary} — moved out verbatim, then called from the original.",
            "",
            f"  · Reads          {', '.join(proposal.primitive_inputs)}",
            "  · Then           move the decision body into it (a module-level pure function),",
            "                   replace it with a call, and pin it in isolation:",
            f"                   detective converge '{path}::{proposal.proposed_name}'",
        ]
    else:  # no_primitive_seam
        out += [
            "  A pure decision is trapped, but no PRIMITIVE value was found to key it on — the body",
            "  uses the impure object throughout. This is a hand extraction with no signature to",
            "  propose: pull the scalar decision out over plain values yourself, then converge it.",
        ]
    out += [
        "",
        "  · Advisory       proposes, never performs; writes nothing and proves nothing. The",
        "                   guarantee comes from converging the EXTRACTED function, not this proposal.",
    ]
    return out
