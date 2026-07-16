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
import math
import os
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass

from Wesker.engine import estimate_universe_size, greedy_coverage_guarantee
from Wesker.filter import filter_categories

from .certify import PytestWiring, _write, wire_pytest
from .engine import _load_original, _resolve, classify_survivors, profile, representative_site
from .equivalence import SourceExpr, SurvivorReport
from .minimize import minimal_cover_2axis, missing_lines, redundant_2axis
from .purity import is_pure
from .synthesis.characterization import capture_golden, corroborate_captures, golden_assert_line
from .synthesis.oracle_light import ExecutableProperty, _import_line, generate_executable_property
from .synthesis.writer import individual_test_names, render_module

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

    @property
    def mutation_score(self) -> float:
        """Fraction of mutants killed (0.0–1.0)."""
        return self.killed / self.total_mutants if self.total_mutants else 1.0

    @property
    def complete(self) -> bool:
        """The full acceptance bar: mutant-complete AND line-complete."""
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


def _remaining_summary(survivor_records: list[dict]) -> tuple[str, ...]:
    """Group remaining survivors by category, e.g. ('2 VALUE', '1 BOUNDARY')."""
    from collections import Counter

    counts = Counter(r.get("category", "?") for r in survivor_records)
    return tuple(f"{n} {cat}" for cat, n in sorted(counts.items()))


def property_holds(setup_code: str, assertion_code: str, project_root: str) -> bool:
    """True if the property's assertion passes on the unmutated module.

    Executes ``setup_code`` + ``assertion_code`` with ``project_root`` on the path.
    Any exception (a failed assertion, or an import that can't resolve) means the
    property does not soundly hold and must not be written.
    """
    root = os.path.abspath(project_root)
    added = root not in sys.path
    if added:
        sys.path.insert(0, root)
    try:
        exec(compile(f"{setup_code}\n{assertion_code}", "<verify>", "exec"), {})  # noqa: S102
        return True
    except (KeyboardInterrupt, SystemExit):
        raise  # never swallow interrupt/exit — only property failures are "unsound"
    except BaseException:  # noqa: BLE001 — pytest's Failed inherits BaseException, not Exception
        return False
    finally:
        if added and root in sys.path:
            sys.path.remove(root)


def _numeric_inputs(params: list[str]) -> list[dict]:
    """Candidate call sites: ``(1, 2, ..., n)`` — enough to pin most pure numeric
    functions' output. capture_golden also tries zero-arg."""
    if not params:
        return [{"positional_args": []}]
    return [{"positional_args": [str(i) for i in range(1, len(params) + 1)]}]


def _setup_with_imports(mod: str, fname: str, args) -> str:
    """The target's import line, plus any imports the arguments need to be *constructed*
    in the test: a ``SourceExpr`` carries its own imports (e.g. ``import ast`` for an
    AST-node input), and a synthesized DATACLASS instance renders (via repr) as
    ``ClassName(...)`` — which NameErrors unless ``ClassName`` is imported. Without these
    a golden or witness test is judged unsound under ``property_holds`` and never written,
    even though it is a valid killing test. Deduped, target import first."""
    lines = [_import_line(mod, fname)]
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


def _golden_property(func_key: str, capture) -> ExecutableProperty:
    """A golden-capture property: pin the exact return value. Sound by
    construction (asserts the real output) and kills any mutant that changes it."""
    mod, fname = func_key.rsplit("::", 1) if "::" in func_key else ("", func_key)
    args = ", ".join(repr(a) for a in capture.inputs)
    assertion = golden_assert_line(capture.output, capture.value)
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
        setup_code=_setup_with_imports(mod, fname, capture.inputs),
        assertion_code=f"result = {fname}({args})\n{assertion}",
        preconditions=["golden capture (pure + deterministic)"],
        confidence=0.9,
        source_lenses=["golden_capture"],
        needs_oracle=False,
        golden_case=golden_case,
    )


def _witness_property(func_key: str, witness) -> ExecutableProperty:
    """A golden test at a distinguishing input the equivalence search found. The
    witness proves original(args) != mutant(args), so pinning the original's real
    output there deterministically kills that mutant — an input the single golden
    capture missed. (For value-returning witnesses; a raising original gets the
    pytest.raises form from :func:`_raises_witness_property`.)"""
    mod, fname = func_key.rsplit("::", 1) if "::" in func_key else ("", func_key)
    args = ", ".join(repr(a) for a in witness.args)
    return ExecutableProperty(
        category="VALUE",
        inputs={},
        setup_code=_setup_with_imports(mod, fname, witness.args),
        assertion_code=(
            f"result = {fname}({args})\n{golden_assert_line(witness.original, witness.original_value)}"
        ),
        preconditions=["distinguishing witness (equivalence search)"],
        confidence=0.95,
        source_lenses=["witness"],
        needs_oracle=False,
    )


def _raises_witness_property(func_key: str, witness) -> ExecutableProperty | None:
    """The killing test for a witness whose ORIGINAL raises: a ``pytest.raises`` form.

    The witness proves original(args) != mutant(args) where the original raised
    ``<raised ExcType>``; a mutant that returns a value (or raises differently) fails
    ``with pytest.raises(ExcType): f(args)``, so the form kills it — the error-path
    coverage a value-assertion can't express. None if the exception type can't be
    parsed (then it stays a suggestion). The exec-time soundness gate still applies:
    if the original does NOT actually raise ExcType, ``property_holds`` rejects it."""
    match = re.fullmatch(r"<raised (\w+)>", witness.original)
    if match is None:
        return None
    exc = match.group(1)
    mod, fname = func_key.rsplit("::", 1) if "::" in func_key else ("", func_key)
    args = ", ".join(repr(a) for a in witness.args)
    setup = _setup_with_imports(mod, fname, witness.args) + "\nimport pytest"
    return ExecutableProperty(
        category="VALUE",
        inputs={},
        setup_code=setup,
        assertion_code=f"with pytest.raises({exc}):\n    {fname}({args})",
        preconditions=[f"distinguishing witness (original raises {exc})"],
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
) -> list[ExecutableProperty]:
    """Golden-capture properties for a pure function, or [] if it can't be run
    deterministically. Real call-sites are captured FIRST (they exercise structured /
    unannotated arguments the synthesized single site cannot); a synthesized site that
    crashes on those inputs simply yields no capture and is dropped.

    ``supplied_inputs`` are the Zone-2 residual filled through the CLI (`--input`). They are
    captured golden FIRST — a golden test at a supplied input pins the return value AND
    covers whatever lines that input executes, which is how a supplied input closes a
    *line* residual (not only a kill residual). Rendered into the same golden call-site
    dict form as discovered sites (positional args as reprs that eval back at capture time).
    """
    live = _load_original(full_path, qualname)
    if live is None:
        return []
    namespace = getattr(live, "__globals__", {}) or {}
    supplied_sites = [{"positional_args": [repr(v) for v in args]} for args in (supplied_inputs or [])]
    sites = supplied_sites + _discovered_sites(qualname, project_root) + representative_site(node, namespace)
    captures = corroborate_captures(capture_golden(live, sites), is_pure=True)
    return [_golden_property(func_key, c) for c in captures if c.deterministic]


def _progressed(previous: int, current: int) -> bool:
    """True when the survivor count strictly decreased."""
    return current < previous


def _converged(at_ceiling: bool, hit_max_iterations: bool) -> bool:
    """Converged when the ceiling is reached, or the loop stabilized before the cap."""
    return at_ceiling or not hit_max_iterations


def converge(
    file: str,
    function: str,
    project_root: str = ".",
    *,
    write_dir: str | None = "tests",
    max_iterations: int = 3,
    call_site_inputs: list[dict] | None = None,
    supplied_inputs: list[tuple] | None = None,
    fast: bool = False,
    use_parallel: bool | None = None,
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
        tree = ast.parse(fh.read(), filename=full)
    qualname, node = _resolve(tree, function)
    if qualname is None:
        raise LookupError(f"function {function!r} not found in {file}")
    func_key = f"{os.path.relpath(full, root)}::{qualname}"
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
    accumulated: dict[str, ExecutableProperty] = {}

    for _pass in range(max_iterations):
        result = profile(
            file,
            function,
            project_root,
            max_per_category=max_per_cat,
            pass_index=_pass,
            extra_test_dirs=extra_test_dirs,
            progress=progress,
            use_parallel=use_parallel,
        )
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
            generate_executable_property(s, func_key, node, call_site_inputs)
            for s in result.value_survivor_records
        ]
        # Pure functions also get golden-capture properties, which pin the exact
        # return value and kill the VALUE/ARITHMETIC survivors oracle-light can't.
        if is_pure(node, is_method="." in (qualname or "")):
            props += _golden_properties(func_key, node, full, qualname, root, supplied_inputs=supplied_inputs)
        sound = [
            p for p in props if not p.needs_oracle and property_holds(p.setup_code, p.assertion_code, root)
        ]
        new_sound = [p for p in sound if p.assertion_code not in accumulated]
        for p in new_sound:
            accumulated[p.assertion_code] = p
        source = render_module(func_key, list(accumulated.values()))
        if source and write_dir:
            target = write_dir if os.path.isabs(write_dir) else os.path.join(root, write_dir)
            written_path = _write(source, target, qualname, root) or None
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
    if write_dir:
        say("witness pass: searching richer inputs for a distinguishing kill…")
        pre = classify_survivors(
            file,
            function,
            project_root,
            call_site_inputs=supplied_inputs,
            extra_test_dirs=extra_test_dirs,
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
            prop = (
                _raises_witness_property(func_key, w)
                if w.original.startswith("<raised")
                else _witness_property(func_key, w)
            )
            if prop is None:
                continue
            if prop.assertion_code not in accumulated and property_holds(
                prop.setup_code, prop.assertion_code, root
            ):
                accumulated[prop.assertion_code] = prop
                witnessed = True
                n_witnessed += 1
        if witnessed:
            source = render_module(func_key, list(accumulated.values()))
            target = write_dir if os.path.isabs(write_dir) else os.path.join(root, write_dir)
            written_path = _write(source, target, qualname, root) or None
            say(f"witness pass: +{n_witnessed} distinguishing kill test(s) auto-written")

    # Authoritative final measurement — reflects every written test, including
    # the last pass's, and is the validation of what converge actually achieved.
    say("finalizing — re-profiling the full mutant universe against the written suite…")
    final_result = profile(
        file,
        function,
        project_root,
        extra_test_dirs=extra_test_dirs,
        progress=progress,
        use_parallel=use_parallel,
    )
    # Don't SHIP a suite our own minimal-cover immediately flags as non-minimal: drop any test
    # WE generated that is redundant for BOTH kills AND lines (zero marginal contribution), then
    # re-profile so every reported number reflects what is actually on disk. Only individual
    # (non-parametrized) properties are droppable — golden captures fold into one parametrized
    # test and each case is already minimal-cover-selected. This is a NON-generation, not a
    # deletion of a user's own test, so it honors "deletion never auto".
    if written_path and write_dir:
        names = individual_test_names(func_key, list(accumulated.values()))
        drop = {
            names[n].assertion_code
            for n in redundant_2axis(final_result.kill_matrix, final_result.line_coverage)
            if n in names
        }
        if drop:
            accumulated = {k: v for k, v in accumulated.items() if k not in drop}
            source = render_module(func_key, list(accumulated.values()))
            target = write_dir if os.path.isabs(write_dir) else os.path.join(root, write_dir)
            written_path = _write(source, target, qualname, root) or None
            say(f"minimizing — dropped {len(drop)} redundant test(s) our own cover flagged")
            final_result = profile(
                file,
                function,
                project_root,
                extra_test_dirs=extra_test_dirs,
                progress=progress,
                use_parallel=use_parallel,
            )
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
            )
        except Exception:  # noqa: BLE001 — classification is advisory; never fail the run
            survivor_report = None
    # Functionally complete = every KILLABLE mutant killed. Equivalent survivors do
    # not count against it (no test can kill them); an uncertain survivor does, since
    # we can't prove it unkillable.
    functionally_complete = final == 0 or (
        survivor_report is not None and not survivor_report.killable and not survivor_report.unclassified
    )
    # Second completeness axis + minimality, from Wesker's baseline line-coverage
    # pass on the final suite: which executable lines remain uncovered, the smallest
    # test set that preserves both kills and line coverage, and the tests redundant
    # for BOTH (deletion proposals — never auto-removed).
    missing = missing_lines(final_result.executable_lines, final_result.line_coverage)
    redundant = redundant_2axis(final_result.kill_matrix, final_result.line_coverage)
    minimal = minimal_cover_2axis(final_result.kill_matrix, final_result.line_coverage)
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
        converged=_converged(at_ceiling, hit_max),
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
        redundant_tests=tuple(sorted(redundant)),
        minimal_test_count=len(minimal),
        universe_size=universe_size,
        fast=fast,
        coverage_guarantee=greedy_coverage_guarantee(node, _cats, max_per_cat, len(iterations)),
        signature=sig,
        param_names=param_names,
    )
