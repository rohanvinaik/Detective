"""Apply a decomposition — extract a compound block into a helper function.

:mod:`Detective.decompose` proposes which blocks are separable; this module turns
a proposal into real code and, when it can PROVE the rewrite is behavior-preserving,
applies it. Proof is by EXECUTION, not by trusting the transform: the decomposed
function is run against the original over witness inputs, and only an exact match on
every input earns an auto-apply (Detective's stochastic-proposer / deterministic-
checker model). Anything unvalidated is proposed — shown, never written.

The extraction itself is scope-based: a block's PARAMS are the names it reads that
were defined before it, its RETURNS are the names it writes that are read after it,
and a block that escapes its own control flow (return / yield / a free break) is not
extractable at all.
"""

from __future__ import annotations

import ast
import textwrap
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .converge import ConvergeResult


def _kill_matrix(file: str, function: str, project_root: str) -> dict[str, list[str]]:
    """The target's ``mutant -> tests that killed it`` map. Served from the content-hashed
    verdict cache whenever the function and its tests are unchanged, so this costs ~nothing
    right after converge profiled the same target."""
    from .engine import profile

    try:
        return profile(file, function, project_root).kill_matrix
    except Exception:  # noqa: BLE001 — no profile -> no proof suite -> propose, never apply
        return {}


def _wanted_test_names(kill_matrix: dict[str, list[str]]) -> set[str]:
    """The test names that killed a mutant OF THIS TARGET, as the names their ``def``s
    carry: a parametrize id is stripped, since ``t[case-a]`` is defined by ``def t``.

    ``kill_matrix`` maps mutant -> the tests that killed it, so every name here provably
    exercises the target. That is what "covers the target specifically" means, and it is
    why the whole discovered suite must NOT be used instead — ``discover_test_callables``
    returns every test in the project, which would let an unrelated passing test stand in
    for the proof.
    """
    return {t.split("[", 1)[0] for tests in kill_matrix.values() for t in tests}


def _test_names_in_source(source: str) -> set[str]:
    """The function names a test module's source DEFINES. Source that does not parse
    defines nothing — a malformed file specifies no behavior, so it is not proof."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    return {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)}


def _covering_test_files(root: str, kill_matrix: dict[str, list[str]]) -> tuple[str, ...]:
    """The PRE-EXISTING test files that provably specify this target — the proof suite
    when converge wrote nothing because the hand-written suite was already complete.

    The walk is deliberately thin; the decisions live in the two pure helpers above.
    Names resolve to files by reading the source, never ``inspect.getfile``: Wesker binds
    parametrized cases through a wrapper, so a callable's file is its wrapper's file.
    """
    import os

    wanted = _wanted_test_names(kill_matrix)
    if not wanted:
        return ()

    files: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith((".", "__")) and d != "node_modules"]
        for name in filenames:
            if not (name.startswith("test_") and name.endswith(".py")):
                continue
            full = os.path.join(dirpath, name)
            try:
                with open(full, encoding="utf-8") as fh:
                    source = fh.read()
            except OSError:
                continue
            if _test_names_in_source(source) & wanted:
                files.add(os.path.relpath(full, root))
    return tuple(sorted(files))


def _names(node: ast.AST, ctx: type | tuple[type, ...]) -> set[str]:
    """The ``Name`` ids used with the given context (Load / Store) anywhere in
    ``node``, not descending into nested function scopes (their locals are theirs)."""
    found: set[str] = set()
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.Name) and isinstance(child.ctx, ctx):
            found.add(child.id)
        if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            found |= _names(child, ctx)
    return found


def _aug_targets(node: ast.AST) -> set[str]:
    """Names that are augmented-assignment targets (``x += 1``): read AND written,
    so they must be passed IN as well as returned OUT."""
    return {
        a.target.id for a in ast.walk(node) if isinstance(a, ast.AugAssign) and isinstance(a.target, ast.Name)
    }


def _target_names(target: ast.AST) -> set[str]:
    """The Name ids bound by an assignment/loop target (handles tuple unpacking)."""
    return {n.id for n in ast.walk(target) if isinstance(n, ast.Name)}


def structural_bindings(node: ast.AST) -> set[str]:
    """Names a block binds structurally BEFORE any use — loop variables, ``with … as``
    targets, ``except … as`` names, comprehension targets. Such a name is the block's
    own local (its read is of the value the block itself just bound), so it is NOT an
    external read and must never become a parameter — the loop-variable leak that a
    plain reads∩defined-before test gets wrong when an earlier loop left the same
    name bound in the enclosing scope."""
    bound: set[str] = set()
    for n in ast.walk(node):
        if isinstance(n, (ast.For, ast.AsyncFor)):
            bound |= _target_names(n.target)
        elif isinstance(n, ast.comprehension):
            bound |= _target_names(n.target)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            bound.add(n.name)
        elif isinstance(n, ast.withitem) and n.optional_vars is not None:
            bound |= _target_names(n.optional_vars)
    return bound


def _has_free_break(node: ast.AST, in_loop: bool) -> bool:
    """True if ``node`` contains a ``break``/``continue`` NOT enclosed by a loop
    within ``node`` — such a jump targets an OUTER loop and cannot move into a
    helper. Nested function scopes are ignored (they cannot break the outer loop)."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.Break, ast.Continue)) and not in_loop:
            return True
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        child_in_loop = in_loop or isinstance(child, (ast.For, ast.While, ast.AsyncFor))
        if _has_free_break(child, child_in_loop):
            return True
    return False


def control_escapes(stmt: ast.stmt) -> bool:
    """True if extracting ``stmt`` into a helper would change control flow: it
    contains a ``return``/``yield``, a ``nonlocal``/``global`` declaration, or a
    ``break``/``continue`` that targets a loop outside the block."""
    for node in ast.walk(stmt):
        if isinstance(node, (ast.Return, ast.Yield, ast.YieldFrom, ast.Nonlocal, ast.Global)):
            return True
    started_in_loop = isinstance(stmt, (ast.For, ast.While, ast.AsyncFor))
    return _has_free_break(stmt, in_loop=started_in_loop)


@dataclass(frozen=True)
class BlockInterface:
    """The data-flow interface of an extractable block: what it needs in and hands
    out. ``params`` come in as arguments, ``returns`` go out as the helper's return."""

    params: tuple[str, ...]
    returns: tuple[str, ...]


def block_interface(func_node: ast.FunctionDef | ast.AsyncFunctionDef, index: int) -> BlockInterface:
    """Params and returns for extracting ``func_node.body[index]``.

    A param is a name the block READS that was defined before it (a function
    parameter, or something assigned in an earlier statement) — a loop variable or
    other block-local read is NOT a param. A return is a name the block WRITES that
    is READ by a later statement — anything written only for the block's own use
    stays inside the helper. Both are sorted for a deterministic signature.
    """
    block = func_node.body[index]
    arg_names = {a.arg for a in func_node.args.args}
    arg_names |= {a.arg for a in getattr(func_node.args, "posonlyargs", [])}
    arg_names |= {a.arg for a in func_node.args.kwonlyargs}
    if func_node.args.vararg:
        arg_names.add(func_node.args.vararg.arg)
    if func_node.args.kwarg:
        arg_names.add(func_node.args.kwarg.arg)

    defined_before = set(arg_names)
    for earlier in func_node.body[:index]:
        defined_before |= _names(earlier, ast.Store)

    reads = _names(block, ast.Load) | _aug_targets(block)
    # Exclude names the block binds for itself (loop vars etc.): their read is of the
    # block's own binding, not an external value, even if an earlier statement left
    # the same name in scope.
    params = (reads & defined_before) - structural_bindings(block)

    writes = _names(block, ast.Store) | _aug_targets(block)
    read_after: set[str] = set()
    for later in func_node.body[index + 1 :]:
        read_after |= _names(later, ast.Load)
    returns = writes & read_after

    return BlockInterface(tuple(sorted(params)), tuple(sorted(returns)))


def _resolve(tree: ast.Module, function: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    """The FunctionDef named ``function`` (last path segment for a method)."""
    target = function.split(".")[-1]
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == target:
            return node
    return None


@dataclass(frozen=True)
class Extraction:
    """A generated (not-yet-validated) extraction: the helper's interface and the
    full rewritten source with the helper spliced in and the block replaced by a
    call."""

    helper_name: str
    params: tuple[str, ...]
    returns: tuple[str, ...]
    new_source: str


def extract_block(source: str, function: str, index: int) -> Extraction | None:
    """Rewrite ``source`` extracting ``function``'s ``index``-th body statement into
    a helper, or None if that statement is not safely extractable (it escapes its
    control flow) or cannot be located.

    Surgical, not a full reparse: only the block's lines become a call and the
    helper is spliced in above the function, so every comment and the formatting of
    the rest of the file survive. Behavior preservation is NOT asserted here — the
    caller validates by execution before applying."""
    tree = ast.parse(source)
    func = _resolve(tree, function)
    if func is None or index < 0 or index >= len(func.body):
        return None
    block = func.body[index]
    if control_escapes(block):
        return None
    iface = block_interface(func, index)

    lines = source.splitlines(keepends=True)
    end = block.end_lineno or block.lineno
    block_text = "".join(lines[block.lineno - 1 : end])
    first = lines[block.lineno - 1]
    base_indent = first[: len(first) - len(first.lstrip())]

    helper_name = f"_{function.split('.')[-1]}_{type(block).__name__.lower()}_{block.lineno}"
    body = textwrap.indent(textwrap.dedent(block_text), "    ")
    if not body.endswith("\n"):
        body += "\n"
    helper = f"def {helper_name}({', '.join(iface.params)}):\n{body}"
    if iface.returns:
        helper += f"    return {', '.join(iface.returns)}\n"
    helper += "\n\n"

    call = base_indent + (f"{', '.join(iface.returns)} = " if iface.returns else "")
    call += f"{helper_name}({', '.join(iface.params)})\n"

    func_start = min([func.lineno, *(d.lineno for d in func.decorator_list)]) - 1
    rewritten = lines[: block.lineno - 1] + [call] + lines[end:]
    new_source = "".join(rewritten[:func_start]) + helper + "".join(rewritten[func_start:])
    return Extraction(helper_name, iface.params, iface.returns, new_source)


def extract_candidate(source: str, function: str, candidate) -> Extraction | None:
    """Extract the finder's contiguous block (``candidate.start_line..end_line``)
    into ``candidate.proposed_name``, using the def-use interface the deterministic
    finder already computed (``inputs``/``outputs``). Surgical: only those lines
    become a call and the helper is spliced above the function, so the rest of the
    file is untouched."""
    tree = ast.parse(source)
    func = _resolve(tree, function)
    if func is None:
        return None
    lines = source.splitlines(keepends=True)
    start, end = candidate.start_line, candidate.end_line
    if start < 1 or end > len(lines) or start > end:
        return None
    block_text = "".join(lines[start - 1 : end])
    first = lines[start - 1]
    base_indent = first[: len(first) - len(first.lstrip())]
    body = textwrap.indent(textwrap.dedent(block_text), "    ")
    if not body.endswith("\n"):
        body += "\n"
    params = ", ".join(candidate.inputs)
    returns = ", ".join(candidate.outputs)
    helper = f"def {candidate.proposed_name}({params}):\n{body}"
    if candidate.outputs:
        helper += f"    return {returns}\n"
    helper += "\n\n"
    call = base_indent + (f"{returns} = " if candidate.outputs else "")
    call += f"{candidate.proposed_name}({params})\n"
    func_start = min([func.lineno, *(d.lineno for d in func.decorator_list)]) - 1
    rewritten = lines[: start - 1] + [call] + lines[end:]
    new_source = "".join(rewritten[:func_start]) + helper + "".join(rewritten[func_start:])
    return Extraction(candidate.proposed_name, candidate.inputs, candidate.outputs, new_source)


@dataclass(frozen=True)
class Decomposition:
    """One candidate's outcome: the generated extraction and whether execution
    proved it behavior-preserving (hence auto-appliable)."""

    extraction: Extraction
    validated: bool  # True -> safe to auto-apply; False -> propose only


@dataclass(frozen=True)
class DecompositionApply:
    """Result of decomposing a function: what was applied (validated + written) and
    what is only proposed (generated but unvalidated, or written=False)."""

    function: str
    applied: tuple[Extraction, ...]
    proposed: tuple[Decomposition, ...]
    unsafe_blocks: tuple[str, ...]
    # The converge run used as the proof attempt. When it is not ``functionally_complete``
    # (a KILLABLE mutant synthesis could not reach), the extraction cannot be proven — and
    # this carries the exact residual (signature, param shape, killable survivors) so the CLI
    # can hand the user the ``--input`` to supply, instead of a dead-end "review it yourself".
    proof: ConvergeResult | None = None  # blocks skipped as non-extractable (control escape)


def apply_decomposition(
    file: str,
    function: str,
    project_root: str = ".",
    *,
    write: bool = False,
    max_extractions: int = 8,
    supplied_inputs: list[tuple] | None = None,
    notify: Callable[[str], None] | None = None,
) -> DecompositionApply:
    """The full decomposition loop — a decomposition is applied only when PROVED
    behavior-preserving by a mutant-complete test suite.

        1. converge → generate a functional, mutant-complete test suite (the
           behavioral spec: it kills every killable mutant, so passing it means every
           behavioral degree of freedom is preserved).
        2. decompose (deterministic dependency clustering, gated on entanglement) →
           propose contiguous-block extractions.
        3. PROVE: trial-apply each extraction and re-run the suite. Green → proven
           behavior-preserving; red → reject and revert.

    A validated extraction is kept only when ``write`` is True; otherwise the trial
    is reverted and the extraction reported as (validated) proposed."""
    import os

    from .certify import verify_under_pytest
    from .converge import converge
    from .decompose import decompose

    root = os.path.abspath(project_root)
    full = file if os.path.isabs(file) else os.path.join(root, file)
    # decompose's cost IS the converge below (mutating + running the suite), so without this
    # the slowest command is also the only silent one — it looks hung while doing the most.
    say = notify or (lambda _m: None)

    # STEP 1 — the mutant-complete suite is both the spec and the proof.
    surviving_categories: tuple[str, ...] = ()
    try:
        # ``supplied_inputs`` are the Zone-2 residual filled through the CLI (`decompose
        # --input`): the exact inputs deterministic synthesis could not exercise. They flow
        # into the proof suite so a function whose line-/mutant-completeness needs a human
        # sample can still reach the `line_complete` gate below — otherwise it could never
        # be proven decomposable from the CLI.
        say("proving: converging the target to a mutation-complete suite (the proof)…")
        conv = converge(
            file,
            function,
            project_root,
            write_dir="tests",
            supplied_inputs=supplied_inputs,
            notify=notify,
        )
        report = conv.survivor_report
        if report is not None:
            surviving_categories = tuple(sorted({v.category for v in report.verdicts}))
    except Exception:  # noqa: BLE001 — no suite -> no proof possible
        conv = None
    if not surviving_categories:
        from .engine import profile

        try:
            _prof = profile(file, function, project_root)
            surviving_categories = tuple(
                sorted({r.get("category", "") for r in _prof.value_survivor_records})
            )
        except Exception:  # noqa: BLE001
            surviving_categories = ()

    # The proof suite is the TARGET's own MUTATION-complete suite. The behavior-preservation
    # proof is mutation-completeness (every KILLABLE mutant killed → every pin-able behavioral
    # degree of freedom is pinned, so a decomposition that changes any of them fails a test).
    # LINE-completeness is orthogonal and NOT required: a line whose mutants are all killed is
    # fully specified whether or not a test "covers" it in the coverage sense, and a covered
    # line whose mutants survive proves nothing. Gating on ``functionally_complete`` (not
    # ``line_complete``) is what lets a branchy function be proven+auto-applied without the
    # user hand-feeding boundary ``--input``s just to satisfy a coverage metric that does not
    # bear on preservation. (A genuine residual — a KILLABLE mutant synthesis could not reach —
    # correctly leaves ``functionally_complete`` False, and THAT is the real case to surface an
    # ``--input`` for.) The suite must still exist and cover the target specifically, so an
    # unrelated passing test can never stand in for the proof.
    # The suite that proves preservation is whichever one is mutation-complete — Detective
    # does not have to be its author. When converge wrote nothing BECAUSE the pre-existing
    # hand-written suite already killed every killable mutant (``written_path`` None with
    # ``functionally_complete`` True — the BEST case, a function already fully specified),
    # the proof is those hand-written files. Gating on ``written_path`` alone rejected
    # exactly that case, and misreported the cause as "not mutation-complete".
    proof_suite: str | tuple[str, ...] | None = None
    if conv is not None and conv.functionally_complete:
        if conv.written_path:
            proof_suite = conv.written_path
        else:
            proof_suite = _covering_test_files(root, _kill_matrix(file, function, project_root)) or None

    def _suite_green() -> bool:
        if proof_suite is None:
            return False
        ok, count = verify_under_pytest(root, proof_suite)
        return ok and count > 0

    if proof_suite is None:
        say("no proof suite — nothing can be proven; extractions will be proposed only")
    else:
        say("baseline: running the proof suite against the UNCHANGED function…")
    baseline_green = _suite_green()

    applied: list[Extraction] = []
    proposed: list[Decomposition] = []
    unsafe: list[str] = []
    for _ in range(max_extractions):
        with open(full, encoding="utf-8") as fh:
            source = fh.read()
        tree = ast.parse(source)
        func = _resolve(tree, function)
        if func is None:
            break
        plan = decompose(func, function, surviving_categories)
        progressed = False
        for candidate in plan.candidates:
            extraction = extract_candidate(source, function, candidate)
            if extraction is None:
                unsafe.append(f"block lines {candidate.start_line}-{candidate.end_line}")
                continue
            # Trial-apply on disk, PROVE against the mutant-complete suite, then either
            # keep (write mode) or revert (dry run / rejected).
            say(
                f"trialling: {extraction.helper_name}"
                f"({', '.join(extraction.params)}) -> {', '.join(extraction.returns) or 'None'} "
                "— re-running the proof suite against the rewrite…"
            )
            with open(full, "w", encoding="utf-8") as fh:
                fh.write(extraction.new_source)
            proven = baseline_green and _suite_green()
            # Three outcomes, never two: with no proof suite nothing was REJECTED, it was
            # never tried. Collapsing "could not prove" into "behavior changed" accuses a
            # rewrite the tool never actually tested.
            if proven:
                verdict = "PROVEN — behavior preserved"
            elif proof_suite is None:
                verdict = "unproven — no suite to prove against; proposed, not applied"
            else:
                verdict = "rejected — the suite says behavior changed"
            say(f"{verdict}: {extraction.helper_name}")
            if proven and write:
                applied.append(extraction)
                progressed = True
                break  # keep it; re-read and re-plan against the rewritten file
            with open(full, "w", encoding="utf-8") as fh:
                fh.write(source)  # revert the trial
            proposed.append(Decomposition(extraction, validated=proven))
        if not (write and progressed):
            break
    return DecompositionApply(
        function=function,
        applied=tuple(applied),
        proposed=tuple(proposed),
        unsafe_blocks=tuple(dict.fromkeys(unsafe)),
        proof=conv,
    )
