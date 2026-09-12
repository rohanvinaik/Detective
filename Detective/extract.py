"""`detective extract` — propose the pure decision to pull out of an impure shell (Finding D).

`survey` DETECTS that a function hides a pinnable pure decision behind an impure boundary; `decompose`
will not PERFORM that extraction (its seam criterion is cognitive complexity, and it refuses to apply
any transform it cannot prove behaviour-preserving — which is exactly the impure function converge
cannot pin). So a greenfield author told "extract the pure decision" was left with no tool that acts.

`extract` closes that gap, propose-only: for a survey-flagged function it names the CONCRETE
extraction — a pure function over the PRIMITIVE values the decision reads (the expressible parameters,
plus recognized unshadowed scalar conversions of the inexpressible one, such as its length;
arbitrary element reads, slices, and calls retain an unresolved interface). The proposal guides
hand-extraction followed by `converge` on
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

# Successful calls to these unshadowed builtins produce scalar values. Other calls and
# projections need further evidence; neither slicing nor tuple indexing establishes a type.
_PRIMITIVE_PROJECTIONS = frozenset({"len", "int", "float", "str", "bool"})


def _all_args(func: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.arg]:
    """Candidate interface arguments; receiver reads remain unresolved dependencies."""
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
    func: ast.FunctionDef | ast.AsyncFunctionDef,
    trapped: frozenset[str],
    shadowed: frozenset[str] = frozenset(),
) -> tuple[str, ...]:
    """Recognize only unshadowed builtin scalar conversions of trapped inputs.

    Calls, slices and even ndarray element reads have unknown result types without
    further shape/dtype evidence. An annotation is a declared interface, not a proof.
    """
    found: set[str] = set()
    for stmt in func.body:
        if not isinstance(stmt, ast.Assign) or not isinstance(stmt.value, ast.Call):
            continue
        call = stmt.value
        if not isinstance(call.func, ast.Name):
            continue
        if call.func.id not in _PRIMITIVE_PROJECTIONS or call.func.id in shadowed:
            continue
        if not any(isinstance(n, ast.Name) and n.id in trapped for n in ast.walk(call)):
            continue
        found.update(t.id for t in stmt.targets if isinstance(t, ast.Name))
    writes = [n.id for n in ast.walk(func) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)]
    return tuple(sorted(name for name in found if writes.count(name) == 1))


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
    unresolved_inputs: tuple[str, ...] = ()  # dependencies whose primitive interface is not established


def extract_readiness(
    disposition: str, has_primitive_inputs: bool, has_unresolved_inputs: bool = False
) -> str:
    """Whether a concrete extraction can be PROPOSED for this function (#D, pure — pinned).

    A named code, never a bool, because the two "cannot propose" reasons need different guidance:
      * ``propose``          — a trapped pure decision AND at least one primitive input was identified,
                               so a concrete signature can be offered.
      * ``no_primitive_seam`` — trapped, but no primitive value was found to key the decision on (the
                               body uses the impure object throughout): a hand extraction with no
                               signature `extract` can name — say so rather than propose an empty one.
      * ``unresolved_inputs`` — a dependency's scalar interface is not established.
      * ``move``             — a candidate relocation with no detected unresolved dependency.
                               This bounded static analysis does not prove purity or preservation.
      * ``reachable``        — not trapped (survey would not flag it); nothing to extract.
    """
    if disposition == "reachable":
        return "reachable"
    if has_unresolved_inputs:
        return "unresolved_inputs"
    if disposition == "trapped_by_imports":
        return "move"
    return "propose" if has_primitive_inputs else "no_primitive_seam"


def extraction_target_status(match_count: int) -> str:
    """Resolve one source symbol before making an advisory claim (#D, pure — pinned)."""
    if match_count == 0:
        return "missing"
    if match_count != 1:
        return "ambiguous"
    return "resolved"


def _extraction_target(
    tree: ast.Module, requested: str
) -> tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    """Select an exact qualified target, or a uniquely named bare target."""
    found: list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]] = []

    def matches(qualified: str, bare: str) -> bool:
        """Exact qualified name, or a bare name when the request carried no dots."""
        return qualified == requested or ("." not in requested and bare == requested)

    def visit(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                visit(child, prefix)
                continue
            name = f"{prefix}{child.name}"
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and matches(name, child.name):
                found.append((name, child))
            visit(child, f"{name}.")

    visit(tree, "")
    status = extraction_target_status(len(found))
    if status != "resolved":
        raise LookupError(f"{status} function target: {requested}")
    return found[0]


def _module_bindings(tree: ast.Module) -> set[str]:
    """Every name the MODULE binds — assignments, parameters, defs/classes, import aliases.

    The set a builtin would have to be checked against before it can be called a builtin: if the
    module binds `list` or `id`, the name is not the builtin any more."""
    bound = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    bound.update(n.arg for n in ast.walk(tree) if isinstance(n, ast.arg))
    bound.update(
        n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    )
    bound.update(n.asname or n.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.alias))
    return bound


def _prefix_split(
    func: ast.FunctionDef | ast.AsyncFunctionDef, trapped: tuple[str, ...]
) -> tuple[int, set[str]]:
    """(how many leading statements form the trapped PREFIX, the names it binds).

    The prefix is the docstring plus the run of simple name-assignments whose right-hand side still
    depends on a trapped name — directly, or through an earlier prefix binding. The first statement
    that does not is the seam. Both halves are returned because the caller needs the split to slice
    the tail AND the bound names to decide what the tail's reads are already supplied by."""
    prefix_names: set[str] = set()
    split = 0
    for stmt in func.body:
        if (
            isinstance(stmt, ast.Expr)
            and isinstance(stmt.value, ast.Constant)
            and isinstance(stmt.value.value, str)
        ):
            split += 1
            continue
        if not isinstance(stmt, ast.Assign) or not all(isinstance(t, ast.Name) for t in stmt.targets):
            break
        if not any(
            isinstance(n, ast.Name) and n.id in set(trapped) | prefix_names for n in ast.walk(stmt.value)
        ):
            break
        prefix_names.update(t.id for t in stmt.targets)
        split += 1
    return split, prefix_names


def _extraction_inputs(
    tree: ast.Module, func: ast.FunctionDef | ast.AsyncFunctionDef, trapped: tuple[str, ...]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Describe a bounded prefix-to-decision seam; unresolved dependencies prevent a signature."""
    import builtins

    shadowed = _module_bindings(tree)
    projections = set(_primitive_locals(func, frozenset(trapped), frozenset(shadowed)))
    split, prefix_names = _prefix_split(func, trapped)
    tail = func.body[split:]
    reads = {
        n.id
        for stmt in tail
        for n in ast.walk(stmt)
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
    }
    assigned = {
        n.id
        for stmt in tail
        for n in ast.walk(stmt)
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)
    }
    scalar_args = {
        arg.arg
        for arg in _all_args(func)
        if (
            ast.unparse(arg.annotation)
            if arg.annotation
            else usage_inferred_type(_param_usages(func, arg.arg))
        )
        in {"bool", "int", "float", "str", "bytes"}
    }
    primitive = reads & (scalar_args | (projections & prefix_names))
    known_builtins = set(vars(builtins)) - shadowed
    unresolved = reads - primitive - assigned - known_builtins
    # A later assignment cannot discharge an input read earlier in the residual.
    # In particular, an augmented assignment reads its target before writing it.
    supplied = {arg.arg for arg in _all_args(func)} | prefix_names
    augmented = {
        n.target.id
        for stmt in tail
        for n in ast.walk(stmt)
        if isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Name)
    }
    unresolved |= ((reads | augmented) & supplied) - primitive
    if any(
        isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda))
        for stmt in tail
        for n in ast.walk(stmt)
    ):
        unresolved.add("<nested scope>")
    return tuple(sorted(primitive)), tuple(sorted(unresolved))


def extract_proposal(source: str, qualname: str) -> ExtractionProposal | None:
    """Propose the pure decision to pull out of ``qualname`` — or None when nothing is trapped.

    Pure over the source text (parses, never executes). Mirrors survey's detection so the two agree by
    construction, then adds the concrete primitive-input identification survey does not.
    """
    tree = ast.parse(source)
    resolved, node = _extraction_target(tree, qualname)
    target = node.name
    finding = next((f for f in survey_source(source) if f.qualname == resolved), None)
    if finding is None:
        return None
    trapped = _inexpressible_params(node)
    primitives, unresolved = _extraction_inputs(tree, node, trapped)
    heavy, _bound = _heavy_imports(tree)
    return ExtractionProposal(
        qualname=resolved,
        lineno=node.lineno,
        disposition=finding.disposition,
        trapped_params=trapped,
        proposed_name=f"{target}_decision",
        primitive_inputs=primitives,
        heavy_imports=heavy,
        unresolved_inputs=unresolved,
    )


def render_extract(path: str, proposal: ExtractionProposal | None) -> list[str]:
    """The `detective extract` report — advisory, writes nothing to your project, proves nothing."""
    if proposal is None:
        return [
            f"{path} — extract · nothing trapped   (static advisory)",
            "",
            "  No trap detected within this static scan; reachability is not established.",
        ]
    readiness = extract_readiness(
        proposal.disposition, bool(proposal.primitive_inputs), bool(proposal.unresolved_inputs)
    )
    if readiness == "unresolved_inputs":
        return [
            f"{path} — extract · unresolved input interface (static advisory)",
            f"  Target: {proposal.qualname}",
            f"  Known primitive inputs: {', '.join(proposal.primitive_inputs) or 'none established'}",
            f"  Unresolved dependencies: {', '.join(proposal.unresolved_inputs)}",
            "  Establish these values and dependencies before choosing a complete extraction signature.",
            "  Advisory: writes nothing to your project and proves nothing.",
        ]
    target = proposal.qualname.split(".")[-1]
    if readiness == "move":
        roots = ", ".join(proposal.heavy_imports) or "the heavy stack"
        return [
            f"{path} — extract · a pure function trapped behind heavy module imports   (static advisory)",
            "",
            f"  `{proposal.qualname}` has no unresolved dependency in this bounded scan.",
            f"  Its module imports {roots}; review purity, defaults and annotations before moving it.",
            "",
            "  Proposed move (review the interface and dependencies before relocating):",
            f"      move `{target}` to a leaf module with no heavy imports, then pin it there:",
            f"      detective converge '<leaf_module>.py::{target}'",
            "",
            "  · Advisory       proposes, never performs; writes no project files and proves nothing. The",
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
        "  · Advisory       proposes, never performs; writes nothing to your project and proves nothing. The",
        "                   guarantee comes from converging the EXTRACTED function, not this proposal.",
    ]
    return out
