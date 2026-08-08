"""The converge loop — drive a function toward its mutation ceiling.

Each pass: diagnose → synthesize oracle-light properties → keep only those that
*hold on the unmutated function* (a property that fails on the baseline is a
broken test, never written) → write → re-profile. Stops at the ceiling (0
survivors) or when a pass makes no further progress — the oracle-light-addressable
floor. The needs-oracle survivors that remain are, by definition, the ones that
require an expected value a human or an LLM proposer must supply.
"""

from __future__ import annotations

import ast
import contextlib
import hashlib
import math
import os
import re
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace

from Wesker.ci import relevant_test_files, walk_functions
from Wesker.engine import estimate_universe_size, greedy_coverage_guarantee
from Wesker.filter import filter_categories

from ._contain import contained_stdout, remaining_budget_ms
from .binding import ReceiverFactory, parse_receiver_factory, resolve_execution, wrap_callable
from .capabilities import capability_identity, render_clock_freeze
from .certify import (
    PytestVerification,
    PytestWiring,
    _write,
    run_pytest_verification,
    synth_filename,
    wire_pytest,
)
from .engine import _load_original, _resolve, classify_survivors, profile, representative_site
from .equivalence import SourceExpr, SurvivorReport
from .line_flags import classify_missing_lines
from .minimize import minimal_cover_2axis, missing_lines, redundant_2axis, strip_foreign_evidence
from .purity import environment_reads, is_pure, uncovered_env_reads, world_effects
from .synthesis.characterization import (
    GoldenCapture,
    capture_golden,
    corroborate_captures,
    distinction_pin_lines,
    golden_assert_line,
)
from .synthesis.oracle_light import ExecutableProperty, _import_line, generate_executable_property
from .synthesis.writer import (
    foreign_generated_test_names,
    golden_row_properties,
    individual_test_names,
    render_module,
)
from .verdict_cache import wesker_policy_id

# Fast mode tests this many greedily-selected mutants per category per pass. Greedy
# (1−1/e)-optimal coverage means a small budget kills nearly every killable mutant on the
# first pass, and the multi-pass windows finish the rest. ≤5 is often already exhaustive
# for well-decomposed code (Wesker README); 8 gives margin. Empirically tunable.
_FAST_MAX_PER_CATEGORY = 8


@dataclass(frozen=True)
class ConvergeIteration:
    """One pass: survivors observed, and sound properties written afterward."""

    survivors: int
    written: int


@dataclass(frozen=True)
class ConvergeResult:
    """Outcome of the convergence loop."""

    function: str
    converged: bool
    at_ceiling: bool
    initial_survivors: int
    final_survivors: int
    iterations: tuple[ConvergeIteration, ...]
    written_path: str | None
    total_mutants: int = 0
    killed: int = 0  # TOTAL kills — the standard mutation score (assertion + crash/timeout)
    # Assertion kills only. NOT interchangeable with ``killed``: a crash/timeout kill proves
    # the code RUNS, not what it computes, so it is an unspecified value-DOF. Anything the
    # UI words as "specified" must read this one — "N killed" and "N specified" are
    # different claims and legitimately differ by the crash kills.
    value_killed: int = 0
    remaining: tuple[str, ...] = ()  # e.g. ("2 VALUE", "1 STATE") — the survivors and why
    wiring: PytestWiring | None = None  # how the written suite was wired to run under pytest
    survivor_report: SurvivorReport | None = None  # killable/equivalent/uncertain for leftovers
    functionally_complete: bool = False  # every KILLABLE mutant killed (equivalents may remain)
    # Second completeness axis + minimality (from Wesker's baseline line-coverage pass).
    line_complete: bool = True  # every executable target line covered by some test
    missing_lines: tuple[int, ...] = ()  # executable lines no test covers (the gap)
    # WHICH evidence the line axis rested on (#59): "admissible" when the engine supplied an
    # outcome-qualified view, "observed" when it could not and the weaker union was used. A
    # certificate that cannot say which one it stood on implies the stronger, and the difference
    # is precisely whether a baseline-FAILING test was allowed to close the ledger.
    line_basis: str = "observed"
    manually_unreachable: int = 0  # lines closed by a manual unreachability flag (issue #9)
    contradicted_line_flags: tuple[str, ...] = ()  # flags overridden by observed execution
    # (line, guard) for each uncovered line that sits inside a branch: the condition that must hold to
    # REACH it. Distinct from a mutant's kill requirement — `if total < 0:` yields the boundary mutant's
    # `total == 0` (to KILL it) AND this `total < 0` (to COVER the body); naming only the first left the
    # line gap un-closable by the guidance. Empty for unconditional lines (no branch to satisfy).
    missing_line_guards: tuple[tuple[int, str], ...] = ()
    redundant_tests: tuple[str, ...] = ()  # redundant for BOTH kills and lines -> deletion PROPOSALS
    minimal_test_count: int = 0  # size of the two-axis minimal cover
    universe_size: int = 0  # total possible mutants (behavioral DOF) — completeness denominator
    fast: bool = False  # greedy-sampled per pass (vs comprehensive/exhaustive)
    # A-priori PROVEN lower bound on the fraction of the DOF space the greedy run
    # reaches (Wesker.greedy_coverage_guarantee): exhaustive categories contribute
    # 1.0, sampled ones >= 1-(1/e)**passes. Comprehensive runs = 1.0. The measured
    # kill rate meets or beats it — surfaced as the "statistical guarantee" flex.
    coverage_guarantee: float = 1.0
    # The target's parameter shape — carried so the CLI can emit a PRECISE residual: a
    # copy-pasteable `--input "(…)"` a user fills to reach an un-exercised branch/line
    # (the Zone-2 hand-back), instead of prose. `signature` is for display, `param_names`
    # for building the input template. Both are cheap AST reads (node.args), no execution.
    signature: str = ""  # e.g. "minimal_cover_2axis(kill_matrix: dict, line_coverage: dict)"
    param_names: tuple[str, ...] = ()  # positional param names -> --input slot placeholders
    # No pre-existing test file named this target or any function in its file, so discovery
    # returned the empty suite and every test below is one we synthesized. Reported because
    # the two ways to reach "COMPLETE" are not the same claim: converging a suite the user
    # already had says their tests now pin the behaviour; this one says there were none and
    # here is a first suite to review. Same number, different thing to do next.
    synthesized_only: bool = False
    # The claim's scope (issue #14): "complete" means specified under THIS versioned
    # Wesker mutation policy — never universality beyond it. None = the installed
    # engine predates policy versioning (policy unversioned, not unchanged).
    policy_id: str | None = None
    # Golden captures refused because the invocation opened default-path files
    # (issue #23) — each entry names the call and the touched path(s). The
    # capture would have pinned the ENVIRONMENT, so it was not emitted; these
    # notes are the typed hand-back ("supply inputs or a tmp fixture").
    environment_coupled: tuple[str, ...] = ()
    # The target file changed while the run was measuring it (issue #17). The
    # verdict was computed against the START-of-run snapshot while the suite
    # imported the edited module from disk — an incoherent measurement, not a
    # verdict. Formatters stamp the FINAL line STALE; the CLI exits non-zero;
    # decompose refuses to treat a stale converge as proof. Scope: the TARGET
    # file only — converge legitimately rewrites test files mid-run (its own
    # synth suite), so test-file staleness needs the write ledger to separate
    # our edits from the user's and is deliberately not claimed here.
    stale_target: bool = False
    # Reads of clock / filesystem / process-env / entropy the target performs (issue: the
    # impure-line trap). These gate reachability by STATE A CALLER'S ARGUMENT CANNOT SET, so a
    # line behind one cannot be reached by any `--input` value — the residual is a fixture or a
    # hand-written test, not an input to author. Computed statically from the AST (not empirical
    # like `environment_coupled`, which only fires on lines that actually executed), so it flags
    # the trap even when the impure branch was never reached. Empty for a pure function. The CLI
    # turns a non-empty value + a live line gap into an honest "supply a fixture" hand-back
    # instead of an impossible `--input` ask; the harness reads it to skip these, not spin.
    environment_gated: tuple[str, ...] = ()
    # The aggregate command deadline (issue #31) was exhausted mid-run: some phase
    # was CUT before it finished, so the measurement is PARTIAL. Like ``stale_target``
    # this is an invalid-measurement stamp, not a verdict — the formatter withholds
    # counts, the CLI exits non-zero, ``functionally_complete`` is forced False, and
    # decompose refuses to treat a cut converge as proof. A run that completes inside
    # the wall never sets it. (A per-phase timeout that resets each pass is NOT this;
    # this is one wall drawn down across every phase.)
    budget_exhausted: bool = False
    # Which phase the deadline was exhausted in ("mutant profiling" / "finalization" /
    # "minimization" / "regression-check") — named so the CUT diagnosis says where the
    # budget went, not merely that it ran out.
    cut_phase: str = ""
    # The typed final pytest verification of the target proof basis (issue #38): a certificate
    # requires a GREEN run of the exact generated + hand-written proof suite under real pytest,
    # not just Wesker's direct-call runner. Computed only for an otherwise-complete run (the only
    # case it changes the verdict); None means the run was already incomplete on another axis. A
    # non-``ok`` verification — red, uncollectable, unverified — blocks ``complete`` with its status.
    verification: PytestVerification | None = None
    # Bytes the consumer target emitted to stdout while it was being measured, all
    # contained off the report/JSON channel (issue #31 output contract). Nonzero names
    # an integration/side-effecting target honestly ("N bytes emitted, contained")
    # WITHOUT gating completeness on volume — the deadline and survivor logic decide
    # gateability, this only reports what was silenced.
    stdout_bytes: int = 0
    # Method-target receiver binding (issue #25). ``needs_receiver`` is the NAMED refusal when a
    # method cannot be synthesized without help — a property (needs-fixture) or a constructor that
    # needs arguments (needs-receiver: supply --receiver-factory) — surfaced instead of a silent
    # ``0/N killed``. ``receiver_identity`` scopes an honest certificate to the receiver population
    # explored (``zero-arg:Basket`` / ``class:Basket`` / ``factory:make()``): a COMPLETE on a method
    # holds UNDER that receiver, not for every possible instance state.
    needs_receiver: str | None = None
    receiver_identity: str | None = None
    # Environment capability the certificate is scoped to (issue #24): a ``--clock EPOCH`` makes a
    # wall-clock-reading function pinnable, but its ``✓ COMPLETE`` holds only UNDER that frozen clock,
    # never unconditionally. ``clock=<epoch>`` today; the #24 remainder folds a compound capability
    # set (env / files) into a digest. None when no capability was supplied.
    capability_identity: str | None = None

    @property
    def mutation_score(self) -> float:
        """Fraction of mutants killed (0.0–1.0)."""
        return self.killed / self.total_mutants if self.total_mutants else 1.0

    @property
    def verified(self) -> bool:
        """The proof basis was CONFIRMED green under real pytest (issue #38) — true only when a
        verification ran and passed. Distinct from ``complete``'s gate: this is the positive fact
        for the report, while ``complete`` merely refuses to stand on a FAILED verification."""
        return self.verification is not None and self.verification.ok

    @property
    def complete(self) -> bool:
        """The full acceptance bar: mutant-complete AND line-complete AND not proof-basis-red (#38).

        The verification conjunct stops a red or uncollectable generated suite from printing ✓
        COMPLETE — the mutation score can be perfect while the file Detective wrote does not run
        green in the consumer's own pytest. It gates ONLY when a verification actually RAN: a
        computed-but-non-``ok`` result (tests_failed / collection_failed / runner_missing /
        timed_out / no_tests) blocks; a None verification (not computed — the run was already
        incomplete on another axis, or the result was built without a proof run) falls back to the
        mutation+line axes, so nothing that never had a verification changes meaning. converge sets
        it for every otherwise-complete run — to ``no_tests`` when there is no proof basis at all —
        so an absent basis still refuses."""
        if self.verification is not None and not self.verification.ok:
            return False
        return self.functionally_complete and self.line_complete


def passes_to_complete(trajectory: tuple[int, ...]) -> int:
    """Additional converge passes to drive value-survivors to zero, extrapolated from the
    OBSERVED per-pass decay — a spec-completeness ETA in *passes*, not seconds.

    ``trajectory`` is the value-survivor count at each pass (last = current). Grounded in
    the SSL Semantic Completeness Equation ``dH/dt = -(N + C(H))``: in the greedy bulk each
    pass contracts survivors geometrically (LintGate Thm 3.2 / ``resolution_greedy_decay``),
    so the geometric-mean per-pass survival ratio over the passes already run extrapolates
    how many more reach < 1 survivor.

    Returns 0 when already complete, and -1 when the trajectory has STALLED (no measured
    contraction) — structure is exhausted, so the residual is the I_solve external
    information (supplied inputs), not a pass count.
    """
    seq = tuple(s for s in trajectory if s >= 0)
    if not seq or seq[-1] <= 0:
        return 0
    current = seq[-1]
    positive = tuple(s for s in seq if s > 0)
    if len(positive) < 2 or positive[-1] >= positive[0]:
        return -1  # no contraction observed -> structure exhausted (I_solve residual)
    ratio = (positive[-1] / positive[0]) ** (1.0 / (len(positive) - 1))
    if not 0.0 < ratio < 1.0:
        return -1
    return max(1, math.ceil(math.log(current) / math.log(1.0 / ratio)))


def _signature(
    qualname: str, node: ast.AST, inferred: dict[str, str] | None = None
) -> tuple[str, tuple[str, ...]]:
    """Render the target's parameter shape for precise residual hints.

    Returns ``(display, param_names)`` where ``display`` is ``fn(p1: ann, p2, …)`` (the
    human-readable signature, annotations preserved via ``ast.unparse``) and ``param_names``
    are the positional parameter names (``self`` dropped) used to build the ``--input``
    template. ``inferred`` maps un-annotated parameters to a best-effort type recovered from
    call sites (see ``infer_param_types``); those render as ``p: ~Type`` — the ``~`` marks
    the type as inferred, not declared. A cheap AST read of ``node.args`` — no execution.
    """
    inferred = inferred or {}
    name = qualname.split(".")[-1]
    args = getattr(node, "args", None)
    if args is None:
        return f"{name}()", ()
    display: list[str] = []
    names: list[str] = []
    positional = list(getattr(args, "posonlyargs", [])) + list(args.args)
    for arg in positional:
        if arg.arg == "self":
            continue
        names.append(arg.arg)
        if arg.annotation is not None:
            display.append(f"{arg.arg}: {ast.unparse(arg.annotation)}")
        elif arg.arg in inferred:
            display.append(f"{arg.arg}: ~{inferred[arg.arg]}")
        else:
            display.append(arg.arg)
    return f"{name}({', '.join(display)})", tuple(names)


def _kwargs_names(node: ast.AST, qualname: str) -> tuple[str, ...]:
    """Parameter names a generated call may pass by KEYWORD, or () when it may not.

    ``f(1, 2, 3, 4)`` throws away the one thing that makes a golden test readable — which
    value is which — and the names are already on the node. This decides whether it is
    LEGAL to use them. It is not when the signature has positional-only parameters (a
    keyword call is a TypeError), when it has ``*args`` (values do not map 1:1 to names),
    or for a method (the receiver is not a parameter the call site supplies). In those
    cases the caller keeps the positional form; nothing is guessed.
    """
    args = getattr(node, "args", None)
    if args is None or "." in qualname:
        return ()
    if args.posonlyargs or args.vararg:
        return ()
    return tuple(a.arg for a in args.args if a.arg != "self")


def _render_call(fname: str, values: Sequence, kw_names: Sequence[str] = ()) -> str:
    """``f(weight_kg=1, distance_km=2)`` when the names are usable and cover the values
    exactly, else ``f(1, 2)``. The VALUES are identical either way — the witness that was
    found is the witness that is written; only its presentation changes."""
    if kw_names and len(kw_names) == len(values):
        pairs = zip(kw_names, values, strict=True)  # lengths equal — guarded above
        return f"{fname}({', '.join(f'{n}={v!r}' for n, v in pairs)})"
    return f"{fname}({', '.join(repr(v) for v in values)})"


def _remaining_summary(survivor_records: list[dict]) -> tuple[str, ...]:
    """Group remaining survivors by category, e.g. ('2 VALUE', '1 BOUNDARY')."""
    from collections import Counter

    counts = Counter(r.get("category", "?") for r in survivor_records)
    return tuple(f"{n} {cat}" for cat, n in sorted(counts.items()))


def property_holds(setup_code: str, assertion_code: str, project_root: str) -> bool:
    """True if the property's assertion passes on the unmutated module.

    Executes ``setup_code`` + ``assertion_code`` with the SUITE's import path — not merely
    ``project_root``. The generated setup imports the target the way the rest of the repo does
    (`importable_module`), so on a src-layout it says ``from pkg.mod import f`` while `pkg` lives
    under ``src/``. Root alone cannot resolve that: every property then raised ImportError, was
    judged unsound, and was silently dropped — converge wrote ZERO tests and reported 0/12
    killed, which reads as "this code is unkillable" rather than "the gate could not import it".
    ``_suite_path`` is what pytest itself will use, so a property that passes here passes there.

    Any exception (a failed assertion, or an import that can't resolve) means the
    property does not soundly hold and must not be written.
    """
    from .engine import _suite_path

    root = os.path.abspath(project_root)
    added = [p for p in _suite_path(root) if p not in sys.path]
    sys.path[:0] = added
    try:
        exec(compile(f"{setup_code}\n{assertion_code}", "<verify>", "exec"), {})  # noqa: S102
        return True
    except (KeyboardInterrupt, SystemExit):
        raise  # never swallow interrupt/exit — only property failures are "unsound"
    except BaseException:  # noqa: BLE001 — pytest's Failed inherits BaseException, not Exception
        return False
    finally:
        for p in added:
            if p in sys.path:
                sys.path.remove(p)


def _numeric_inputs(params: list[str]) -> list[dict]:
    """Candidate call sites: ``(1, 2, ..., n)`` — enough to pin most pure numeric
    functions' output. capture_golden also tries zero-arg."""
    if not params:
        return [{"positional_args": []}]
    return [{"positional_args": [str(i) for i in range(1, len(params) + 1)]}]


def _setup_with_imports(
    mod: str, fname: str, args, root: str | None = None, import_stmt: str | None = None
) -> str:
    """The target's import line, plus any imports the arguments need to be *constructed*
    in the test: a ``SourceExpr`` carries its own imports (e.g. ``import ast`` for an
    AST-node input), and a synthesized DATACLASS instance renders (via repr) as
    ``ClassName(...)`` — which NameErrors unless ``ClassName`` is imported. Without these
    a golden or witness test is judged unsound under ``property_holds`` and never written,
    even though it is a valid killing test. Deduped, target import first."""
    # A `--receiver-factory` supplies its OWN import (the factory lives outside the target module),
    # which replaces the default owner import; otherwise `_import_line` derives it from the target.
    lines = [import_stmt if import_stmt is not None else _import_line(mod, fname, root)]
    seen: set[str] = set()
    for arg in args:
        imps: list[str] = []
        if isinstance(arg, SourceExpr):
            imps.extend(arg.imports)
        imps.extend(_dataclass_imports(arg))
        for imp in imps:
            if imp not in seen:
                seen.add(imp)
                lines.append(imp)
    return "\n".join(lines)


def _dataclass_imports(value: object) -> list[str]:
    """Import lines for every dataclass TYPE referenced by ``value`` — recursively through
    lists/tuples/sets/dicts and nested dataclass fields — so a golden test whose args
    contain synthesized dataclass instances can actually construct them from their repr."""
    import dataclasses

    imports: list[str] = []

    def walk(v: object) -> None:
        if isinstance(v, SourceExpr):
            # The transport, not the payload: ``repr`` renders a SourceExpr as its
            # own ``expr`` (the constructor source), so the wrapper TYPE never
            # appears in the emitted test and importing it is not just redundant but
            # wrong — it makes the generated suite depend on Detective, which a
            # target that Detective itself builds on (Wesker) cannot import without
            # inverting the dependency. The imports its source genuinely needs are
            # carried in ``.imports`` and collected by ``_setup_with_imports``.
            return
        if dataclasses.is_dataclass(v) and not isinstance(v, type):
            t = type(v)
            imports.append(f"from {t.__module__} import {t.__name__}")
            for f in dataclasses.fields(v):
                walk(getattr(v, f.name))
        elif isinstance(v, (list, tuple, set, frozenset)):
            for e in v:
                walk(e)
        elif isinstance(v, dict):
            for k, val in v.items():
                walk(k)
                walk(val)

    walk(value)
    return imports


def _golden_property(
    func_key: str,
    capture,
    root: str | None = None,
    kw_names: Sequence[str] = (),
    call_expr: str | None = None,
    import_stmt: str | None = None,
) -> ExecutableProperty:
    """A golden-capture property: pin the exact return value. Sound by
    construction (asserts the real output) and kills any mutant that changes it.

    When the capture was taken under a FROZEN clock (`capture.clock`), the assertion is
    wrapped so ``time.time`` is pinned to that value and restored in a ``finally`` — the same
    self-contained form runs in ``property_holds``'s exec AND in the emitted pytest, with no
    fixture and no leak. Such a property is never folded into a parametrized row (each carries
    its own freeze), so ``golden_case`` is None for it."""
    mod, fname = func_key.rsplit("::", 1) if "::" in func_key else ("", func_key)
    call = _render_call(call_expr or fname, capture.inputs, kw_names)
    assertion = golden_assert_line(capture.output, capture.value)
    frozen = getattr(capture, "clock", None)
    if frozen is not None:
        body = f"result = {call}\n{assertion}"
        indented = "\n".join(f"    {ln}" if ln else "" for ln in body.split("\n"))
        # The whole time-module clock family is frozen + restored in `finally` (#24 increment 1),
        # the SAME plan `apply_clock` used at capture, so the emitted test pins identically with no
        # fixture and no leak.
        assertion_code = render_clock_freeze(frozen, indented)
        preconditions = [f"golden capture (deterministic under a frozen clock == {frozen!r})"]
        golden_case = None  # a freeze-wrapped test is standalone — not a parametrizable row
    else:
        assertion_code = f"result = {call}\n{assertion}"
        preconditions = ["golden capture (pure + deterministic)"]
        # Parametrizable only when the assertion is idiomatic value-equality (a literal
        # output); methods (dotted qualname) need a receiver, so they are not folded.
        golden_case = (
            (repr(tuple(capture.inputs)), capture.output)
            if assertion.startswith("assert result == ") and "." not in fname
            else None
        )
    return ExecutableProperty(
        category="VALUE",
        inputs={},
        setup_code=_setup_with_imports(mod, fname, capture.inputs, root, import_stmt=import_stmt),
        assertion_code=assertion_code,
        preconditions=preconditions,
        confidence=0.9,
        source_lenses=["golden_capture"],
        needs_oracle=False,
        golden_case=golden_case,
    )


def _witness_property(
    func_key: str,
    witness,
    root: str | None = None,
    kw_names: Sequence[str] = (),
    call_expr: str | None = None,
    import_stmt: str | None = None,
) -> ExecutableProperty:
    """A golden test at a distinguishing input the equivalence search found. The
    witness proves original(args) != mutant(args), so pinning the original's real
    output there deterministically kills that mutant — an input the single golden
    capture missed. (For value-returning witnesses; a raising original gets the
    pytest.raises form from :func:`_raises_witness_property`.)

    When the two outcomes are ``==``-equal and differ only in type or repr (``1`` vs
    ``1.0``), the golden ``==`` line cannot kill — ``distinction_pin_lines`` appends the
    ``type()``/``repr`` pins that can, so the witness's kill power survives rendering."""
    mod, fname = func_key.rsplit("::", 1) if "::" in func_key else ("", func_key)
    lines = [
        f"result = {_render_call(call_expr or fname, witness.args, kw_names)}",
        golden_assert_line(witness.original, witness.original_value),
    ]
    pins = distinction_pin_lines(witness.original_value, witness.mutant)
    lines += pins
    preconditions = ["distinguishing witness (equivalence search)"]
    if pins:
        preconditions.append("outcomes ==-equal; distinction pinned by type/repr")
    return ExecutableProperty(
        category="VALUE",
        inputs={},
        setup_code=_setup_with_imports(mod, fname, witness.args, root, import_stmt=import_stmt),
        assertion_code="\n".join(lines),
        preconditions=preconditions,
        confidence=0.95,
        source_lenses=["witness"],
        needs_oracle=False,
    )


def _raises_witness_property(
    func_key: str,
    witness,
    root: str | None = None,
    kw_names: Sequence[str] = (),
    call_expr: str | None = None,
    import_stmt: str | None = None,
) -> ExecutableProperty | None:
    """The killing test for a witness whose ORIGINAL raises: an explicit try/except form.

    The witness proves original(args) != mutant(args) where the original raised
    ``<raised ExcType>``. A mutant can differ in TWO ways, and they need different handling:

    * it RETURNS instead of raising -> the ``else:`` branch fails the test;
    * it raises a DIFFERENT type -> the ``except BaseException`` branch fails the test.

    ``with pytest.raises(ExcType)`` only covers the first. It does not catch the wrong type
    — a mutant swapping ``raise ValueError`` for ``raise TypeError`` lets the TypeError
    propagate out of the test, and the engine reads a propagating exception as a CRASH kill,
    not a value kill. Crash kills are re-listed by ``value_survivor_records`` as unpinned, so
    the mutant returned as a survivor, was re-classified killable off this same witness, and
    the residual asked for an input that would rebuild this same test — a loop with no exit,
    on a mutant that was in fact being killed the whole time.

    Both branches call ``pytest.fail``, so both raise pytest's ``Failed``, which the engine
    classifies ``killed_by="exception"``: a DECLARED failure, a pin, not a crash. Raising IS
    the return behaviour of an error path, and this is the only form that can state it.

    When the witness carries the exception's MESSAGE (`<raised KeyError: unknown slot x>`), the
    handler asserts it rather than passing. That is the only form that kills a mutant which
    raises the RIGHT type with the WRONG message — `raise KeyError("")`, or a deleted guard
    whose fall-through raises `KeyError` on its own. `except KeyError: pass` catches those
    happily and pins nothing. `_outcome` decides whether a message is stable enough to pin; this
    function must honour that decision exactly, because a test that pins less than the witness
    distinguishes cannot kill the mutant the witness was found on — and the survivor comes back
    with the same witness, forever.

    None if the exception type can't be parsed (then it stays a suggestion). The exec-time
    soundness gate still applies: if the original does NOT actually raise ExcType with that
    message, ``property_holds`` rejects it.
    """
    # The message group is optional: `_outcome` omits it when it is empty or carries a memory
    # address. DOTALL because a message may span lines; the trailing `>` anchors the greedy tail.
    match = re.fullmatch(r"<raised (\w+)(?:: (.*))?>", witness.original, re.DOTALL)
    if match is None:
        return None
    exc, message = match.group(1), match.group(2)
    mod, fname = func_key.rsplit("::", 1) if "::" in func_key else ("", func_key)
    setup = _setup_with_imports(mod, fname, witness.args, root, import_stmt=import_stmt) + "\nimport pytest"
    # `_exc`/`_result` are underscore-prefixed so they cannot collide with a parameter name
    # that `_setup_with_imports` bound into the same scope.
    # Pin the message when the witness carries one. `str(_exc)` is the SAME form `_outcome`
    # captured — not `_exc.args` or `repr` — because a test that pins a different form than the
    # witness recorded does not pin the witness (`str(KeyError('x'))` is `"'x'"`, not `x`).
    handler = (
        f"except {exc}:\n    pass\n"
        if message is None
        else f"except {exc} as _exc:\n    assert str(_exc) == {message!r}\n"
    )
    assertion = (
        "try:\n"
        f"    _result = {_render_call(call_expr or fname, witness.args, kw_names)}\n"
        f"{handler}"
        "except BaseException as _exc:\n"
        f'    pytest.fail(f"expected {exc}, got {{type(_exc).__name__}}: {{_exc!r}}")\n'
        "else:\n"
        f'    pytest.fail(f"expected {exc}, but the call returned {{_result!r}}")'
    )
    raises = exc if message is None else f"{exc}: {message}"
    return ExecutableProperty(
        category="VALUE",
        inputs={},
        setup_code=setup,
        assertion_code=assertion,
        preconditions=[f"distinguishing witness (original raises {raises})"],
        confidence=0.95,
        source_lenses=["witness"],
        needs_oracle=False,
    )


def _discovered_sites(qualname: str, project_root: str) -> list[dict]:
    """Real call-sites (from the repo) rendered as golden call-site dicts — positional
    args as repr-strings that eval back at capture time."""
    from .call_sites import discover_call_site_inputs

    return [
        {"positional_args": [repr(v) for v in args]}
        for args in discover_call_site_inputs(qualname, project_root)
    ]


def _golden_properties(
    func_key: str,
    node,
    full_path: str,
    qualname: str,
    project_root: str,
    supplied_inputs: list[tuple] | None = None,
    clock: float | None = None,
    receiver_factory: ReceiverFactory | None = None,
) -> tuple[list[ExecutableProperty], tuple[str, ...]]:
    """Golden-capture properties for a pure function plus the typed refusals
    for captures that touched default-path I/O (issue #23), or ([], ()) if it
    can't be run deterministically. Real call-sites are captured FIRST (they exercise structured /
    unannotated arguments the synthesized single site cannot); a synthesized site that
    crashes on those inputs simply yields no capture and is dropped.

    ``supplied_inputs`` are the Zone-2 residual filled through the CLI (`--input`). They are
    captured golden FIRST — a golden test at a supplied input pins the return value AND
    covers whatever lines that input executes, which is how a supplied input closes a
    *line* residual (not only a kill residual). Rendered into the same golden call-site
    dict form as discovered sites (positional args as reprs that eval back at capture time).
    """
    live_raw = _load_original(full_path, qualname)
    if live_raw is None:
        return [], ()
    # METHOD BINDING (issue #25): `_load_original` returns the UNBOUND method, which the capture
    # path would call with `self` fed a grid value. `resolve_execution` binds a FRESH receiver per
    # call so the existing capture code invokes it exactly like a free function; the arguments stay
    # receiver-free (`representative_site` already skips `self`/`cls`). A property or a constructor
    # that needs arguments is a NAMED refusal (needs-fixture / needs-receiver), surfaced as the
    # refusal note — never the silent `0/N killed` this issue is about.
    exb = resolve_execution(node, qualname, live_raw, factory=receiver_factory)
    if exb.refusal is not None:
        return [], (exb.refusal,)
    live = wrap_callable(exb.underlying, exb.make_receiver)
    # CAPTURABILITY gate (issue #39), BEFORE any sampling. A golden pins the return VALUE, so a
    # return that depends on an uncontrolled environment read (the clock without --clock, the
    # calendar date, the PID, the process env, entropy) is not deterministic — it merely repeats
    # within the sampling interval, then diverges (green at capture, red a second/day/host later).
    # `environment_reads` already names those dependencies; consult it here and DECLINE with the
    # exact reason instead of guessing "now". --clock is the one capability that covers time.time();
    # everything else waits for its fixture (#24). Declining leaves the value survivor un-pinned, so
    # the function reads Incomplete — the honest verdict the README promises, not a false COMPLETE.
    uncovered = uncovered_env_reads(environment_reads(node), clock is not None)
    if uncovered:
        return [], tuple(
            f"golden refused — {reason}; not capturable without an explicit fixture/capability"
            + (" (supply --clock <epoch> to freeze it)" if "time.time()" in reason else "")
            for reason in uncovered
        )
    namespace = getattr(exb.underlying, "__globals__", {}) or {}
    supplied_sites = [{"positional_args": [repr(v) for v in args]} for args in (supplied_inputs or [])]
    sites = supplied_sites + _discovered_sites(qualname, project_root) + representative_site(node, namespace)
    captures = corroborate_captures(capture_golden(live, sites, clock=clock), is_pure=True)
    kw_names = _kwargs_names(node, qualname)
    # A capture that opened a default-path file pinned the ENVIRONMENT, not
    # the function (issue #23): green until the data file legitimately
    # changes, then a phantom regression. Refuse the golden and say exactly
    # why — the static purity gate above let this through because the open()
    # sat behind nested calls, which is why the watch is runtime.
    refusals: list[str] = []
    emitted: list[GoldenCapture] = []
    for c in captures:
        if c.filesystem_writes:
            # The function mutates the tree — transitively, past AST-local purity (issue #30). The
            # write was BLOCKED during capture (no litter); a golden of its return would pin nothing
            # portable regardless. Refuse and name the paths, like the #23 default-path-read case.
            paths = ", ".join(c.filesystem_writes)
            rendered = ", ".join(repr(a) for a in c.inputs)
            refusals.append(
                f"golden at ({rendered}) refused — the function writes the filesystem "
                f"({paths}) transitively; a tmp fixture or explicit sandbox is needed, not a golden"
            )
        elif c.environment_paths:
            rendered = ", ".join(repr(a) for a in c.inputs)
            paths = ", ".join(c.environment_paths)
            refusals.append(
                f"golden at ({rendered}) refused — default-path I/O would pin the "
                f"environment ({paths}); supply inputs or a tmp fixture"
            )
        elif c.deterministic:
            emitted.append(c)
    return [
        _golden_property(
            func_key, c, project_root, kw_names, call_expr=exb.call_expr, import_stmt=exb.import_stmt
        )
        for c in emitted
    ], tuple(refusals)


def _progressed(previous: int, current: int) -> bool:
    """True when the survivor count strictly decreased."""
    return current < previous


def _converged(at_ceiling: bool, hit_max_iterations: bool) -> bool:
    """Converged when the ceiling is reached, or the loop stabilized before the cap."""
    return at_ceiling or not hit_max_iterations


def line_proof_basis(has_admissible: bool, engine_reports_it: bool) -> str:
    """Which evidence the line axis may stand on (#59, pure — pinned).

    Three states, and collapsing any two of them is the defect:

    * ``admissible``    — the engine supplied an outcome-qualified view and it has entries.
      Only baseline-green, contained, non-truncated observations closed the ledger.
    * ``observed``      — the engine does not report the view at all (an older Wesker). The
      weaker union was used, and the certificate must SAY so: silently reverting reproduces the
      original defect while printing the same verdict, which is the unnamed-capability
      assumption Detective #60 forbids.
    * ``none_admissible`` — the engine reports the view and it is EMPTY. Distinct from
      ``observed`` on purpose: this is not a missing capability, it is a measurement saying no
      test's evidence qualifies. Treating it as "absent, fall back" would hand the ledger back
      to exactly the failing tests #59 exists to exclude — the emptiness IS the answer.

    The two booleans are separate because "the engine cannot tell me" and "the engine told me
    nothing qualifies" are different facts that a single truthy check conflates.
    """
    if not engine_reports_it:
        return "observed"
    return "admissible" if has_admissible else "none_admissible"


def _line_guards(func_node: ast.AST, lineno: int) -> list[str]:
    """The branch conditions that must ALL hold to REACH ``lineno`` — the enclosing if/elif/while/for
    tests, outermost first, so an uncovered line names its OWN requirement instead of borrowing a
    mutant's. ``total = 0.0`` inside ``if total < 0:`` -> ``['total < 0']``; an ``elif`` body yields the
    negation of the prior test plus its own. Empty when the line is unconditional (already on the main
    path — 'uncovered' there means a test simply never ran the function, not a missed branch), so the
    caller states nothing rather than a vacuous guard. Best-effort and read-only: any node without line
    spans is skipped, never guessed.
    """

    def _spans(stmts: list, ln: int) -> bool:
        return any(
            getattr(s, "lineno", 1 << 30) <= ln <= getattr(s, "end_lineno", getattr(s, "lineno", -1))
            for s in stmts
        )

    guards: list[tuple[int, str]] = []
    for n in ast.walk(func_node):
        if isinstance(n, ast.If):
            if _spans(n.body, lineno):
                guards.append((n.lineno, ast.unparse(n.test)))
            elif _spans(n.orelse, lineno):
                guards.append((n.lineno, f"not ({ast.unparse(n.test)})"))
        elif isinstance(n, ast.While):
            if _spans(n.body, lineno):
                guards.append((n.lineno, ast.unparse(n.test)))
        elif isinstance(n, ast.For):
            if _spans(n.body, lineno):
                guards.append((n.lineno, f"{ast.unparse(n.target)} in {ast.unparse(n.iter)}"))
    guards.sort()  # outermost (lowest lineno) first — the path condition reads top-down
    return [g for _, g in guards]


def _target_changed(full_path: str, snapshot: str) -> bool:
    """True when the target file no longer matches the start-of-run snapshot —
    including when it can no longer be read at all (deleted or moved is the
    limit case of edited). Two hashes; cheap enough to run on every verdict."""
    try:
        with open(full_path, encoding="utf-8") as fh:
            current = hashlib.sha256(fh.read().encode("utf-8")).hexdigest()
    except OSError:
        return True
    return current != snapshot


def converge(
    file: str,
    function: str,
    project_root: str = ".",
    *,
    write_dir: str | None = "tests/detective",
    max_iterations: int = 3,
    call_site_inputs: list[dict] | None = None,
    supplied_inputs: list[tuple] | None = None,
    clock: float | None = None,
    receiver_factory: str | None = None,
    fast: bool = False,
    deadline_s: float | None = 300.0,
    progress: Callable[[int, int, float], None] | None = None,
    notify: Callable[[str], None] | None = None,
) -> ConvergeResult:
    """Converge, with the consumer target's stdout contained off the report channel.

    A thin shell over :func:`_converge_impl`. The impl re-executes the target throughout
    (every profile, the witness search, golden capture), so a target that prints — or that
    RETURNS a printing object Detective then reprs — would spray the human/JSON channel from
    outside any per-test redirect. One command-level ``sys.stdout`` redirect catches every
    such site (``print`` binds ``sys.stdout`` at call time); the byte count is stamped onto
    the result so the run can name an integration target without gating on volume. stderr —
    the phase narrative — is untouched. This is #31's output contract; ``deadline_s`` (the
    one aggregate wall) is its termination contract, threaded through the impl.
    """
    with contained_stdout() as _sink:
        result = _converge_impl(
            file,
            function,
            project_root,
            write_dir=write_dir,
            max_iterations=max_iterations,
            call_site_inputs=call_site_inputs,
            supplied_inputs=supplied_inputs,
            clock=clock,
            receiver_factory=receiver_factory,
            fast=fast,
            deadline_s=deadline_s,
            progress=progress,
            notify=notify,
        )
    return replace(result, stdout_bytes=_sink.bytes_written) if _sink.bytes_written else result


def _converge_impl(
    file: str,
    function: str,
    project_root: str = ".",
    *,
    write_dir: str | None = "tests/detective",
    max_iterations: int = 3,
    call_site_inputs: list[dict] | None = None,
    supplied_inputs: list[tuple] | None = None,
    clock: float | None = None,
    receiver_factory: str | None = None,
    fast: bool = False,
    deadline_s: float | None = 300.0,
    progress: Callable[[int, int, float], None] | None = None,
    notify: Callable[[str], None] | None = None,
) -> ConvergeResult:
    """Iterate diagnose→synthesize-sound→write→re-profile until ceiling or floor.

    ``fast=True`` samples ``_FAST_MAX_PER_CATEGORY`` greedily-selected ((1−1/e)-optimal)
    mutants per category per pass instead of the full universe — faster, converging over
    passes; the final validation is always comprehensive so the reported kill rate stays
    honest. ``fast=False`` (default) is comprehensive: every mutant, first pass.

    ``notify`` streams a live phase narrative (survivors found, tests written, kills,
    the finalize/classify steps) so a long multi-pass run is legible as it runs, not a
    silent monolith that dumps everything at the end. It is independent of ``progress``
    (per-mutant counts) and fires even in parallel mode, where the long runs are.
    """
    max_per_cat = _FAST_MAX_PER_CATEGORY if fast else 0
    say = notify or (lambda _m: None)
    # The ONE aggregate wall (issue #31). Every profile below draws ``budget_ms`` from the
    # SAME remaining budget — a monotonic clock started here, drawn down, floored at zero by
    # ``remaining_budget_ms`` — so no phase can reset or exceed it. ``deadline_s`` None or
    # <=0 means unbounded (``_deadline_ms`` None), restoring pre-#31 behaviour for a caller
    # that opts out. A blown wall stamps ``budget_cut`` in the phase that hit it; the run is
    # then non-gateable and cannot read COMPLETE.
    _deadline_ms = deadline_s * 1000.0 if deadline_s and deadline_s > 0 else None
    _t0 = time.monotonic()

    def _budget_ms() -> float | None:
        return remaining_budget_ms(_deadline_ms, (time.monotonic() - _t0) * 1000.0)

    def _budget_s() -> float | None:
        _ms = _budget_ms()
        return None if _ms is None else _ms / 1000.0

    budget_cut = False
    cut_phase = ""
    # Typed refusals for goldens that would have pinned the environment
    # (issue #23) — accumulated across passes, deduped, carried on the result.
    environment_coupled: list[str] = []
    root = os.path.abspath(project_root)
    # When write_dir escapes the project tree (an absolute or ../ path), the
    # re-profile's project-tree test discovery cannot see the tests converge writes
    # there, so it would report a false 0% kill for mutants it actually killed. Feed
    # that dir to profile as an extra test root so the kill count reflects the tests
    # we wrote, wherever they landed. In-tree write_dirs need nothing (already scanned).
    extra_test_dirs: tuple[str, ...] = ()
    if write_dir:
        _wd = os.path.abspath(write_dir if os.path.isabs(write_dir) else os.path.join(root, write_dir))
        if _wd != root and not _wd.startswith(root + os.sep):
            extra_test_dirs = (_wd,)
    full = file if os.path.isabs(file) else os.path.join(root, file)
    with open(full, encoding="utf-8") as fh:
        source_text = fh.read()
    # The snapshot every verdict below is ABOUT. If the file changes under the
    # run, the mutants come from this parse while the suite imports the edited
    # module from disk — an incoherent measurement that used to print as a
    # clean verdict (issue #17: an edit mid-run produced `0/26 killed` with
    # line numbers pointing at moved lines). Re-checked at verdict time;
    # a mismatch stamps the result STALE instead of letting it stand.
    source_snapshot = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    tree = ast.parse(source_text, filename=full)
    qualname, node = _resolve(tree, function)
    # Both, though `_resolve` only ever returns them together (`None, None` or a real pair):
    # checking one leaves the other `... | None` for every reader below, and the twelve
    # unnarrowed uses that follow were each a type error a checker reports and a human skips.
    if qualname is None or node is None:
        raise LookupError(f"function {function!r} not found in {file}")
    func_key = f"{os.path.relpath(full, root)}::{qualname}"
    # Read once here, not per witness: every rendered call site in this run names its
    # arguments from the same signature (see `_kwargs_names`).
    kw_names = _kwargs_names(node, qualname)
    # Resolve an explicit --receiver-factory ONCE (issue #25). The parsed callable drives live
    # receiver construction (capture + witness search) and its import/render go into the emitted
    # test; a bad spec fails fast here. `_exec_binding` also carries the certificate-scoping identity
    # (`receiver_identity`) and any named receiver refusal (property / needs-receiver) for the result.
    _rf = parse_receiver_factory(receiver_factory) if receiver_factory else None
    _live_for_binding = _load_original(full, qualname)
    _exec_binding = (
        resolve_execution(node, qualname, _live_for_binding, factory=_rf)
        if _live_for_binding is not None
        else None
    )
    _receiver_identity = _exec_binding.plan.identity if (_exec_binding and _exec_binding.plan) else None
    _receiver_refusal = _exec_binding.refusal if _exec_binding else None
    # Two branches, no third: either test files name this target, or none do. Asked with
    # the SAME predicate discovery scopes by — a banner that decided this independently
    # could contradict the run it is describing. Said while it happens, because otherwise
    # the user watches a baseline of zero tests scroll past with no reason given.
    synthesized_only = not relevant_test_files(root, full, [qn for qn, _ in walk_functions(tree)])
    if synthesized_only:
        say("no existing test reaches this target — synthesizing its suite from scratch…")
    # A supplied input is the ONE thing here a human had to know — the semantic prior
    # synthesis provably could not build. Union it with anything remembered for this
    # function and record it, so it is asked for once, not once per command: `decompose`
    # runs its own converge and used to re-print a residual the user had just filled.
    from . import samples

    recalled = len(samples.load(root, func_key))
    supplied_inputs = samples.merge(root, func_key, supplied_inputs) or None
    if recalled and supplied_inputs:
        say(f"recalled {recalled} supplied input(s) from a previous run")
    # The mutant UNIVERSE (behavioral degrees of freedom) — a cheap AST count, the
    # denominator of specification completeness; reported so the user sees how much of the
    # space was covered. Comprehensive tests all of it; fast samples a greedy subset/pass.
    _cats = filter_categories(node, is_pure(node, is_method="." in (qualname or "")))
    universe_size = estimate_universe_size(node, _cats)

    iterations: list[ConvergeIteration] = []
    written_path: str | None = None
    initial: int | None = None
    previous: int | None = None
    hit_max = True
    # Accumulate sound properties ACROSS passes, keyed by assertion (identical
    # assertions are the same test). Each pass re-renders the UNION — never just
    # the current pass — so a later pass cannot overwrite an earlier pass's killers.
    #
    # ...and across RUNS, for the same reason. This dict starting empty each invocation was
    # the same overwrite one scope up: the suite file is re-rendered wholesale from it, so a
    # pin the previous run wrote and this run's search did not re-derive was destroyed before
    # anything measured it. That is why a target could alternate forever — round A's tests
    # answered, then discarded by round B — and why re-converging silently shrank a suite.
    from . import pins

    fn_digest = pins.function_digest(node)
    accumulated: dict[str, ExecutableProperty] = {
        p.assertion_code: p for p in pins.load(root, func_key, fn_digest, verify=property_holds)
    }
    if accumulated:
        say(f"recalled {len(accumulated)} pinned test(s) from a previous run")

    # COLD START. Pins protect the second run onward; the FIRST run after an upgrade — or any
    # run whose store was purged — still faces a suite file written by an older version, with
    # an accumulator that does not contain it, and re-renders it wholesale. So hold the bytes
    # and what they measured. A run that ends up killing LESS than the file it replaced has
    # not converged anything; it has destroyed evidence, and the honest artifact is the file
    # that was already there.
    prior_suite_source = ""
    prior_suite_path = ""
    if write_dir:
        _wdir = write_dir if os.path.isabs(write_dir) else os.path.join(root, write_dir)
        # Through `synth_filename`, not a second copy of the rule: the guard has to look at the
        # file `_write` will actually replace, and two spellings of "where does it live" drift.
        prior_suite_path = os.path.join(_wdir, synth_filename(func_key))
        with contextlib.suppress(OSError):
            with open(prior_suite_path, encoding="utf-8") as fh:
                prior_suite_source = fh.read()
    baseline_killed: int | None = None

    for _pass in range(max_iterations):
        # Stop STARTING new work once the wall is gone (issue #31): a fresh pass would only
        # re-enter profiling with a zero budget and produce another cut. Break here so the
        # finalize/classify below run on what we have, cut-stamped.
        if _deadline_ms is not None and _budget_ms() <= 0.0:
            budget_cut, cut_phase = True, cut_phase or "mutant profiling"
            say("⚠ aggregate deadline exhausted — cutting the profiling loop")
            break
        result = profile(
            file,
            function,
            project_root,
            budget_ms=_budget_ms(),
            max_per_category=max_per_cat,
            pass_index=_pass,
            extra_test_dirs=extra_test_dirs,
            progress=progress,
        )
        if result.budget_exhausted and not budget_cut:
            budget_cut, cut_phase = True, "mutant profiling"
        if baseline_killed is None:
            # Measured BEFORE this run writes anything: what the suite already on disk kills.
            baseline_killed = result.total_killed
        # Value-survivors: what the suite hasn't pinned the RETURN VALUE of — true
        # survivors plus crash/timeout kills. Converging drives THIS to zero, so a
        # crash-dominated "100%" no longer reads as done.
        survivors = result.value_survived
        if initial is None:
            initial = survivors

        if survivors == 0:
            iterations.append(ConvergeIteration(0, 0))
            hit_max = False
            say(f"pass {_pass}: ✓ every mutant killed")
            break

        if previous is not None and not _progressed(previous, survivors):
            iterations.append(ConvergeIteration(survivors, 0))  # no progress -> floor
            hit_max = False
            say(f"pass {_pass}: {survivors} survivor(s) — no progress, at floor")
            break
        previous = survivors
        say(f"pass {_pass}: {survivors} value-survivor(s) — synthesizing killing tests…")

        props = [
            generate_executable_property(s, func_key, node, call_site_inputs, root)
            for s in result.value_survivor_records
        ]
        # Pure functions also get golden-capture properties, which pin the exact
        # return value and kill the VALUE/ARITHMETIC survivors oracle-light can't.
        #
        # `world_effects` as well as `is_pure`, because `is_pure` answers a different question and
        # was measured saying `shutil.rmtree(p)` is PURE — it looks for observability, and rmtree
        # returns None and mutates nothing in-process. Capture then CALLS the target on a
        # `representative_site`, i.e. a path we invented. `is_pure` alone put "delete this
        # directory tree" one synthesized argument away from running.
        if is_pure(node, is_method="." in (qualname or "")) and not world_effects(node):
            golden_props, refused = _golden_properties(
                func_key,
                node,
                full,
                qualname,
                root,
                supplied_inputs=supplied_inputs,
                clock=clock,
                receiver_factory=_rf,
            )
            props += golden_props
            for note in refused:
                if note not in environment_coupled:
                    environment_coupled.append(note)
                    say(f"⚠ {note}")
        sound = [
            p for p in props if not p.needs_oracle and property_holds(p.setup_code, p.assertion_code, root)
        ]
        new_sound = [p for p in sound if p.assertion_code not in accumulated]
        for p in new_sound:
            accumulated[p.assertion_code] = p
        source = render_module(func_key, list(accumulated.values()))
        if source and write_dir:
            target = write_dir if os.path.isabs(write_dir) else os.path.join(root, write_dir)
            written_path = _write(source, target, func_key, root) or None
        iterations.append(ConvergeIteration(survivors, len(new_sound)))
        if new_sound:
            _wrote = f" [{os.path.basename(written_path)}]" if written_path else ""
            say(f"pass {_pass}: +{len(new_sound)} new killing test(s) written{_wrote}")

        if not new_sound:  # no NEW sound test this pass -> no further progress possible
            hit_max = False
            say(f"pass {_pass}: no new killing test for the remaining survivor(s) — at ceiling")
            break

    # Witness-driven kill pass: the equivalence search tries richer inputs than the
    # single golden capture, so it finds distinguishing inputs that kill survivors the
    # loop left standing. A witness is a PROOF of killability, so the golden test at
    # that input deterministically kills the mutant — auto-write it (auto-apply
    # principle: deterministically-guaranteed-correct → just do it).
    # #39: a return that reads the environment is not value-capturable by the witness pass — its
    # original-vs-mutant search pins the ORIGINAL's clock/pid/env value, green this second and red
    # the next. Unlike the golden-capture pass above, the witness pass CANNOT freeze the clock (it
    # does not thread `--clock` into its search or its emitted row), so even WITH --clock it would
    # emit an unfrozen witness row — violating "every emitted row uses that same value". So it skips
    # value goldens for ANY env-reading function; the `--clock`-aware golden-capture pass is the only
    # path that emits a frozen, deterministic row. Error-path (raises) witnesses stay allowed: a
    # raise is not an env-coupled value. The golden-capture pass already surfaced the reason.
    _capturable = not environment_reads(node)
    # METHOD BINDING (#25): render witness rows for a method as `Owner().method(...)` / `Owner.method(...)`
    # (or `make().method(...)` under an explicit --receiver-factory). The witness `.args` are already
    # receiver-free (classify_survivors bound the receiver to FIND them); only the emitted call + import
    # need the receiver-aware form. Reuses `_exec_binding`; defaults to the function form.
    _render_call_expr = _exec_binding.call_expr if _exec_binding is not None else None
    _render_import_stmt = _exec_binding.import_stmt if _exec_binding is not None else None
    if write_dir:
        say("witness pass: searching richer inputs for a distinguishing kill…")
        pre = classify_survivors(
            file,
            function,
            project_root,
            call_site_inputs=supplied_inputs,
            extra_test_dirs=extra_test_dirs,
            deadline_s=_budget_s(),
            receiver_factory=_rf,
        )
        witnessed = False
        n_witnessed = 0
        for verdict in pre.killable:
            w = verdict.witness
            if w is None:
                continue
            # A raising original gets the pytest.raises form (error-path coverage);
            # a value-returning one gets the golden form. Both are auto-written when
            # they hold on the unmutated function — the raises form closes the line +
            # mutant gap that error paths otherwise leave open.
            is_raises = w.original.startswith("<raised")
            # An env-coupled value golden is declined (#39); the raises form is not a value.
            if not _capturable and not is_raises:
                continue
            prop = (
                _raises_witness_property(
                    func_key, w, root, kw_names, call_expr=_render_call_expr, import_stmt=_render_import_stmt
                )
                if is_raises
                else _witness_property(
                    func_key, w, root, kw_names, call_expr=_render_call_expr, import_stmt=_render_import_stmt
                )
            )
            if prop is None:
                continue
            if prop.assertion_code not in accumulated and property_holds(
                prop.setup_code, prop.assertion_code, root
            ):
                accumulated[prop.assertion_code] = prop
                witnessed = True
                n_witnessed += 1
        # Crash-only survivors the CURRENT suite does not reach: no value-witness exists
        # (the mutant raises rather than returning a different value, so nothing can
        # value-pin it — the accounting stays honest about that), but the search DID find
        # the input where original and mutant part ways. A golden capture of the
        # ORIGINAL's value there is a sound test that fails-by-crash under the mutant: it
        # moves the mutant from "reached by no test at all" to "crash-detected", which is
        # the detection gap the old report papered over with "your suite already detects
        # them". Suite-detected ones are left alone — a test already covers them.
        n_crash_detect = 0
        for verdict in pre.equivalent:
            w = verdict.crash_witness
            # A crash-detection golden also captures the ORIGINAL's value — declined when the
            # return is env-coupled (#39), for the same straddle reason as the value witnesses.
            if w is None or verdict.suite_detected or not _capturable:
                continue
            prop = _witness_property(
                func_key, w, root, kw_names, call_expr=_render_call_expr, import_stmt=_render_import_stmt
            )
            if prop.assertion_code not in accumulated and property_holds(
                prop.setup_code, prop.assertion_code, root
            ):
                accumulated[prop.assertion_code] = prop
                witnessed = True
                n_crash_detect += 1
        if n_crash_detect:
            say(
                f"witness pass: +{n_crash_detect} crash-detection test(s) auto-written "
                "(crash-only survivor reached by no existing test)"
            )
        if witnessed:
            source = render_module(func_key, list(accumulated.values()))
            target = write_dir if os.path.isabs(write_dir) else os.path.join(root, write_dir)
            written_path = _write(source, target, func_key, root) or None
            say(f"witness pass: +{n_witnessed} distinguishing kill test(s) auto-written")

    # Authoritative final measurement — reflects every written test, including
    # the last pass's, and is the validation of what converge actually achieved.
    say("finalizing — re-profiling the full mutant universe against the written suite…")
    final_result = profile(
        file,
        function,
        project_root,
        budget_ms=_budget_ms(),
        extra_test_dirs=extra_test_dirs,
        progress=progress,
    )
    if final_result.budget_exhausted and not budget_cut:
        budget_cut, cut_phase = True, "finalization"
    # Don't SHIP a suite our own minimal-cover immediately flags as non-minimal: drop any test
    # WE generated that is redundant for BOTH kills AND lines (zero marginal contribution), then
    # re-profile so every reported number reflects what is actually on disk. Only individual
    # (non-parametrized) properties are droppable — golden captures fold into one parametrized
    # test and each case is already minimal-cover-selected. This is a NON-generation, not a
    # deletion of a user's own test, so it honors "deletion never auto".
    if written_path and write_dir:
        names = individual_test_names(func_key, list(accumulated.values()))
        # Issue #7: the redundancy decision must not count a SIBLING target's generated
        # tests as evidence — their file is rewritten wholesale on that target's next
        # converge, and a witness dropped on their support silently regresses this
        # target's certificate. User tests and this target's own tests remain evidence.
        own_matrix, own_lines = strip_foreign_evidence(
            final_result.kill_matrix,
            final_result.line_coverage,
            foreign_generated_test_names(root, func_key),
        )
        drop = {names[n].assertion_code for n in redundant_2axis(own_matrix, own_lines) if n in names}
        # Issue #13: parametrized golden ROWS are droppable too. A golden that merely
        # duplicates a stable hand-written test adds zero marginal obligation, and the
        # profile says so — by the row's rendered name (`test_x_golden[args2-…]`). Map
        # the row index back to its property and drop it like any other redundancy;
        # #5's no-AST-surgery posture is untouched because this re-renders Detective's
        # OWN file, it never edits a user's parametrize.
        golden_base, golden_rows = golden_row_properties(func_key, list(accumulated.values()))
        for n in redundant_2axis(own_matrix, own_lines):
            base, _, case = n.partition("[")
            if base != golden_base or not case:
                continue
            row = re.match(r"args(\d+)", case)
            if row and int(row.group(1)) < len(golden_rows):
                drop.add(golden_rows[int(row.group(1))].assertion_code)
        if drop:
            accumulated = {k: v for k, v in accumulated.items() if k not in drop}
            target = write_dir if os.path.isabs(write_dir) else os.path.join(root, write_dir)
            if accumulated:
                source = render_module(func_key, list(accumulated.values()))
                written_path = _write(source, target, func_key, root) or None
            elif written_path:
                # Every generated property was redundant against stable user evidence:
                # the honest artifact is NO file, not an empty shell reporting itself
                # as a written suite. The live session must hear about the delete the
                # same way it hears about every write (see certify._write).
                from Wesker.ci import refresh_live_suite

                with contextlib.suppress(OSError):
                    os.remove(written_path)
                refresh_live_suite(root, written_path)
                written_path = None
            say(f"minimizing — dropped {len(drop)} redundant test(s) our own cover flagged")
            final_result = profile(
                file,
                function,
                project_root,
                budget_ms=_budget_ms(),
                extra_test_dirs=extra_test_dirs,
                progress=progress,
            )
            if final_result.budget_exhausted and not budget_cut:
                budget_cut, cut_phase = True, "minimization"
    # The check the accumulator cannot make on a cold start: is the suite we are about to ship
    # WORSE than the one we replaced? Kill count is the comparison because it is the number
    # this command exists to move; a run that lowers it has destroyed evidence, not converged.
    regressed = (
        bool(prior_suite_source)
        and baseline_killed is not None
        and final_result.total_killed < baseline_killed
    )
    if regressed:
        say(
            f"kept the suite already on disk — this run's would kill {final_result.total_killed} "
            f"where it kills {baseline_killed}"
        )
        with contextlib.suppress(OSError):
            with open(prior_suite_path, "w", encoding="utf-8") as fh:
                fh.write(prior_suite_source)
            from Wesker.ci import refresh_live_suite

            refresh_live_suite(root, prior_suite_path)
        written_path = prior_suite_path
        final_result = profile(
            file,
            function,
            project_root,
            budget_ms=_budget_ms(),
            extra_test_dirs=extra_test_dirs,
            progress=progress,
        )
        if final_result.budget_exhausted and not budget_cut:
            budget_cut, cut_phase = True, "regression-check"

    # Remember what this run pinned, AFTER minimization, so the next run seeds from the suite
    # that actually shipped rather than the pre-minimal set. Saved even when empty: an empty
    # set is the true memory of "everything generated was redundant against your own tests",
    # and resurrecting those next run is the overwrite this store exists to stop.
    #
    # NOT after a restore: `accumulated` then describes the file we just threw away, and the
    # properties of the one we kept are exactly what this run could not recover.
    if not regressed:
        pins.save(root, func_key, fn_digest, list(accumulated.values()))

    final = final_result.value_survived
    at_ceiling = final == 0
    # Make the written suite actually runnable in the consumer and state how —
    # Wesker ran the tests by direct call; a real user runs `pytest`.
    wiring = wire_pytest(root, written_path) if written_path else None
    # Classify whatever converge could not kill: killable (a witness = a suggested
    # test), equivalent (retained), or uncertain — so "remaining" is never opaque.
    survivor_report: SurvivorReport | None = None
    if final > 0:
        say(f"{final} survivor(s) remain — classifying (killable / equivalent / needs-input)…")
        try:
            survivor_report = classify_survivors(
                file,
                function,
                project_root,
                call_site_inputs=supplied_inputs,
                extra_test_dirs=extra_test_dirs,
                deadline_s=_budget_s(),
            )
        except Exception:  # noqa: BLE001 — classification is advisory; never fail the run
            survivor_report = None
    # Functionally complete = every KILLABLE mutant killed. Equivalent survivors do
    # not count against it (no test can kill them); an uncertain survivor does, since
    # we can't prove it unkillable.
    functionally_complete = final == 0 or (
        survivor_report is not None and not survivor_report.killable and not survivor_report.unclassified
    )
    # A CUT run measured only PART of the universe (issue #31): its "every killable mutant
    # killed" is a claim about mutants that never ran. The wall makes the measurement
    # non-gateable, so completeness cannot stand on it — forced False here, which is also
    # what blocks decompose from treating a cut converge as a preservation proof and what
    # keeps ``✓ COMPLETE`` off a partial run. Belt: a final measurement that itself came back
    # budget-exhausted counts as cut even if no earlier phase flagged it.
    if final_result.budget_exhausted and not budget_cut:
        budget_cut, cut_phase = True, cut_phase or "finalization"
    # The wall can also be consumed by the classification phase (advisory, bounded per #31)
    # without any profile flagging it — its survivors come back unclassified, which already
    # blocks COMPLETE, but stamp the run CUT so the verdict SAYS the budget ran out rather
    # than reading as an ordinary "incomplete: N unclassified".
    if _deadline_ms is not None and _budget_ms() <= 0.0 and not budget_cut:
        budget_cut, cut_phase = True, cut_phase or "classification"
    if budget_cut:
        functionally_complete = False
        say(f"⚠ aggregate deadline exhausted during {cut_phase} — result CUT, non-gateable")
    # Second completeness axis + minimality, from Wesker's baseline line-coverage
    # pass on the final suite: which executable lines remain uncovered, the smallest
    # test set that preserves both kills and line coverage, and the tests redundant
    # for BOTH (deletion proposals — never auto-removed).
    # THE PROOF AXIS READS ADMISSIBLE COVERAGE (#59). "A trace observed this line" and "this
    # line is pinned under the certificate regime" are different facts, and completeness was
    # judged from the first. A test that FAILS on the unmutated program is already barred from
    # kill attribution — it cannot distinguish a mutant from correct code — and its coverage
    # still closed the line ledger, so `✓ COMPLETE` could rest on evidence from a test that
    # proves nothing. Wesker #17 exposes the filtered view; this consumes it.
    #
    # The fallback is NAMED, not silent. `admissible_line_coverage` does not exist on older
    # Wesker, and quietly reverting to the observed union would reproduce exactly the defect
    # while reporting the same verdict — the unnamed-capability assumption Detective #60 exists
    # to forbid. `line_basis` travels with the result so a certificate states which evidence it
    # actually rested on rather than implying the stronger one.
    _sentinel = object()
    _admissible = getattr(final_result, "admissible_line_coverage", _sentinel)
    line_basis = line_proof_basis(
        has_admissible=bool(_admissible) and _admissible is not _sentinel,
        engine_reports_it=_admissible is not _sentinel,
    )
    # `none_admissible` keeps the EMPTY admissible map, deliberately. The engine measured and
    # nothing qualified, so the gap is every executable line — falling back to the observed
    # union there would hand the ledger straight back to the failing tests this excludes.
    proof_coverage = final_result.line_coverage if line_basis == "observed" else (_admissible or {})
    missing = missing_lines(final_result.executable_lines, proof_coverage)
    # Issue #9: the line-unreachability oracle closes a flagged statement's residual on the
    # LINE ledger only — reported as "modulo", never silently as covered. A flag contradicted
    # by observed execution is surfaced as overridden; mutation-completeness never reads it.
    # The same basis the gap was computed from. A flag "contradicted by observed execution"
    # must be contradicted by execution that COUNTS: reading the observed union here would let
    # a baseline-failing test override a human's unreachability judgement (#59).
    covered_lines = {ln for lines in proof_coverage.values() for ln in lines}
    missing, manually_unreachable, contradicted_flags = classify_missing_lines(
        root, func_key, node, missing, covered_lines
    )
    # The branch each uncovered line sits behind — its OWN reach requirement, so the line gap is not
    # left to borrow a mutant's kill input (which targets the == edge, not the branch body).
    missing_guards = tuple((ln, " and ".join(g)) for ln in missing if (g := _line_guards(node, ln)))
    redundant = redundant_2axis(final_result.kill_matrix, final_result.line_coverage)
    minimal = minimal_cover_2axis(final_result.kill_matrix, final_result.line_coverage)
    # #38: the certificate's verification axis. COMPLETE requires a GREEN run of the exact target
    # proof basis under REAL pytest — the generated file PLUS the hand-written files that supplied
    # target kills (`_covering_test_files`), not merely Wesker's direct-call runner. Run it only
    # when the run is OTHERWISE complete (the sole case it changes the verdict), so an already-
    # incomplete run never pays for a subprocess; a red / uncollectable / unverified basis then
    # blocks ✓ COMPLETE with its typed status. `basis` records generated-only vs target-complete so
    # verifying just our file is never presented as proof of the larger hand-written basis.
    stale = _target_changed(full, source_snapshot)
    verification: PytestVerification | None = None
    if functionally_complete and not missing and not budget_cut and not stale:
        from .decompose_apply import _covering_test_files

        covering = _covering_test_files(root, final_result.kill_matrix)
        basis_paths = tuple(
            dict.fromkeys(
                ([written_path] if written_path else [])
                + [c if os.path.isabs(c) else os.path.join(root, c) for c in covering]
            )
        )
        if basis_paths:
            # This verification is one phase under the ONE aggregate wall (#31): pass the REMAINING
            # budget so its pytest timeout is clamped to it, never a fresh 120s that overruns the
            # deadline a run finishing mutation with milliseconds left would otherwise blow.
            verification = run_pytest_verification(
                root,
                list(basis_paths),
                basis="target-complete" if covering else "generated-only",
                deadline_s=_budget_s(),
            )
        else:
            # Otherwise-complete but NO proof suite on disk at all — an absent basis is a refusal,
            # not a silent pass (a certificate with nothing to verify is not a certificate).
            verification = PytestVerification("no_tests", None, 0, 0, 0, 0, (), "generated-only")
        if not verification.ok:
            say(f"⚠ proof basis did NOT verify under pytest ({verification.status}) — certificate withheld")
    sig, param_names = _signature(qualname, node)
    # For parameters the source leaves un-annotated, recover a best-effort type from how
    # the function is CALLED across the repo, so the residual's `target:` still names a
    # type to supply. Only walk the repo when there IS an un-annotated param (cost), and
    # only re-render when inference actually recovered something.
    _pos = list(getattr(node.args, "posonlyargs", [])) + list(getattr(node.args, "args", []))
    if any(a.annotation is None for a in _pos if a.arg != "self"):
        from .call_sites import infer_param_types

        inferred = infer_param_types(qualname or function, project_root, list(param_names))
        if inferred:
            sig, param_names = _signature(qualname, node, inferred=inferred)
    return ConvergeResult(
        function=func_key,
        # A cut run has not "converged" anything either — it stopped short, so the
        # ceiling/floor reasoning that ``_converged`` encodes never got to run.
        converged=_converged(at_ceiling, hit_max) and not budget_cut,
        at_ceiling=at_ceiling,
        initial_survivors=initial or 0,
        final_survivors=final,
        iterations=tuple(iterations),
        written_path=written_path,
        total_mutants=final_result.total_mutants,
        killed=final_result.total_killed,
        value_killed=final_result.value_killed,
        remaining=_remaining_summary(final_result.value_survivor_records),
        wiring=wiring,
        survivor_report=survivor_report,
        functionally_complete=functionally_complete,
        line_complete=not missing,
        missing_lines=tuple(missing),
        line_basis=line_basis,
        manually_unreachable=len(manually_unreachable),
        contradicted_line_flags=tuple(f"{f.source} (line {f.line})" for f in contradicted_flags),
        missing_line_guards=missing_guards,
        redundant_tests=tuple(sorted(redundant)),
        minimal_test_count=len(minimal),
        universe_size=universe_size,
        fast=fast,
        coverage_guarantee=greedy_coverage_guarantee(node, _cats, max_per_cat, len(iterations)),
        signature=sig,
        param_names=param_names,
        synthesized_only=synthesized_only,
        policy_id=wesker_policy_id(),
        stale_target=stale,
        environment_coupled=tuple(environment_coupled),
        environment_gated=environment_reads(node),
        budget_exhausted=budget_cut,
        cut_phase=cut_phase,
        verification=verification,
        needs_receiver=_receiver_refusal,
        receiver_identity=_receiver_identity,
        capability_identity=capability_identity(clock),
        # stdout_bytes is stamped by the ``converge`` containment shell, which owns the sink.
    )
