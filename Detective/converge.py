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
import os
import sys
from dataclasses import dataclass

from .certify import PytestWiring, _write, wire_pytest
from .engine import _load_original, _resolve, classify_survivors, profile
from .equivalence import SurvivorReport, typed_inputs
from .purity import is_pure
from .synthesis.characterization import capture_golden, corroborate_captures
from .synthesis.oracle_light import ExecutableProperty, generate_executable_property, _import_line
from .synthesis.writer import render_module


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
    killed: int = 0
    remaining: tuple[str, ...] = ()  # e.g. ("2 VALUE", "1 STATE") — the survivors and why
    wiring: PytestWiring | None = None  # how the written suite was wired to run under pytest
    survivor_report: SurvivorReport | None = None  # killable/equivalent/uncertain for leftovers
    functionally_complete: bool = False  # every KILLABLE mutant killed (equivalents may remain)

    @property
    def mutation_score(self) -> float:
        """Fraction of mutants killed (0.0–1.0)."""
        return self.killed / self.total_mutants if self.total_mutants else 1.0


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
    except Exception:
        return False
    finally:
        if added and root in sys.path:
            sys.path.remove(root)


def _type_of(ann) -> str | None:
    """Base type name of an annotation node: ``int``, ``str``, ``list`` (from
    ``list[...]``), or the non-None side of ``X | None`` / ``Optional[X]``. None when
    unannotated or too complex to pick inputs for."""
    if isinstance(ann, ast.Name):
        return ann.id
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


def _ann_name(arg: ast.arg) -> str | None:
    """The annotation's base type name so golden capture picks type-fit inputs."""
    return _type_of(arg.annotation)


def _typed_call_sites(node) -> list[dict]:
    """Call sites for golden capture, using each parameter's ANNOTATION to pick
    type-appropriate literals (a str param gets strings, not ``1``). Integer inputs
    for numeric/unknown params. This is what lets converge generate a real test for a
    string function instead of a false-ceiling crash — surfaced by dogfooding."""
    param_types = [_ann_name(a) for a in node.args.args if a.arg not in ("self", "cls")]
    if not param_types:
        return [{"positional_args": []}]
    return [{"positional_args": [repr(v) for v in combo]} for combo in typed_inputs(param_types)]


def _numeric_inputs(params: list[str]) -> list[dict]:
    """Candidate call sites: ``(1, 2, ..., n)`` — enough to pin most pure numeric
    functions' output. capture_golden also tries zero-arg."""
    if not params:
        return [{"positional_args": []}]
    return [{"positional_args": [str(i) for i in range(1, len(params) + 1)]}]


def _golden_property(func_key: str, capture) -> ExecutableProperty:
    """A golden-capture property: pin the exact return value. Sound by
    construction (asserts the real output) and kills any mutant that changes it."""
    mod, fname = func_key.rsplit("::", 1) if "::" in func_key else ("", func_key)
    args = ", ".join(repr(a) for a in capture.inputs)
    return ExecutableProperty(
        category="VALUE",
        inputs={},
        setup_code=_import_line(mod, fname),
        assertion_code=f"result = {fname}({args})\nassert repr(result) == {capture.output!r}",
        preconditions=["golden capture (pure + deterministic)"],
        confidence=0.9,
        source_lenses=["golden_capture"],
        needs_oracle=False,
    )


def _witness_property(func_key: str, witness) -> ExecutableProperty:
    """A golden test at a distinguishing input the equivalence search found. The
    witness proves original(args) != mutant(args), so pinning the original's real
    output there deterministically kills that mutant — an input the single golden
    capture missed. (Only for value-returning witnesses; a raising original needs a
    pytest.raises form and stays a suggestion.)"""
    mod, fname = func_key.rsplit("::", 1) if "::" in func_key else ("", func_key)
    args = ", ".join(repr(a) for a in witness.args)
    return ExecutableProperty(
        category="VALUE",
        inputs={},
        setup_code=_import_line(mod, fname),
        assertion_code=f"result = {fname}({args})\nassert repr(result) == {witness.original!r}",
        preconditions=["distinguishing witness (equivalence search)"],
        confidence=0.95,
        source_lenses=["witness"],
        needs_oracle=False,
    )


def _golden_properties(
    func_key: str, node, full_path: str, qualname: str
) -> list[ExecutableProperty]:
    """Golden-capture properties for a pure function, or [] if it can't be run
    deterministically on the synthesized inputs."""
    live = _load_original(full_path, qualname)
    if live is None:
        return []
    captures = corroborate_captures(capture_golden(live, _typed_call_sites(node)), is_pure=True)
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
) -> ConvergeResult:
    """Iterate diagnose→synthesize-sound→write→re-profile until ceiling or floor."""
    root = os.path.abspath(project_root)
    full = file if os.path.isabs(file) else os.path.join(root, file)
    with open(full, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=full)
    qualname, node = _resolve(tree, function)
    if qualname is None:
        raise LookupError(f"function {function!r} not found in {file}")
    func_key = f"{os.path.relpath(full, root)}::{qualname}"

    iterations: list[ConvergeIteration] = []
    written_path: str | None = None
    initial: int | None = None
    previous: int | None = None
    hit_max = True
    # Accumulate sound properties ACROSS passes, keyed by assertion (identical
    # assertions are the same test). Each pass re-renders the UNION — never just
    # the current pass — so a later pass cannot overwrite an earlier pass's killers.
    accumulated: dict[str, ExecutableProperty] = {}

    for _ in range(max_iterations):
        result = profile(file, function, project_root)
        survivors = result.total_survived
        if initial is None:
            initial = survivors

        if survivors == 0:
            iterations.append(ConvergeIteration(0, 0))
            hit_max = False
            break

        if previous is not None and not _progressed(previous, survivors):
            iterations.append(ConvergeIteration(survivors, 0))  # no progress -> floor
            hit_max = False
            break
        previous = survivors

        props = [
            generate_executable_property(s, func_key, node, call_site_inputs)
            for s in result.survivor_records
        ]
        # Pure functions also get golden-capture properties, which pin the exact
        # return value and kill the VALUE/ARITHMETIC survivors oracle-light can't.
        if is_pure(node, is_method="." in (qualname or "")):
            props += _golden_properties(func_key, node, full, qualname)
        sound = [
            p for p in props
            if not p.needs_oracle and property_holds(p.setup_code, p.assertion_code, root)
        ]
        new_sound = [p for p in sound if p.assertion_code not in accumulated]
        for p in new_sound:
            accumulated[p.assertion_code] = p
        source = render_module(func_key, list(accumulated.values()))
        if source and write_dir:
            target = write_dir if os.path.isabs(write_dir) else os.path.join(root, write_dir)
            written_path = _write(source, target, qualname)
        iterations.append(ConvergeIteration(survivors, len(new_sound)))

        if not new_sound:  # no NEW sound test this pass -> no further progress possible
            hit_max = False
            break

    # Witness-driven kill pass: the equivalence search tries richer inputs than the
    # single golden capture, so it finds distinguishing inputs that kill survivors the
    # loop left standing. A witness is a PROOF of killability, so the golden test at
    # that input deterministically kills the mutant — auto-write it (auto-apply
    # principle: deterministically-guaranteed-correct → just do it).
    if write_dir:
        pre = classify_survivors(file, function, project_root)
        witnessed = False
        for verdict in pre.killable:
            w = verdict.witness
            if w is None or w.original.startswith("<raised"):
                continue  # a raising original needs a pytest.raises form — left as a suggestion
            prop = _witness_property(func_key, w)
            if prop.assertion_code not in accumulated and property_holds(
                prop.setup_code, prop.assertion_code, root
            ):
                accumulated[prop.assertion_code] = prop
                witnessed = True
        if witnessed:
            source = render_module(func_key, list(accumulated.values()))
            target = write_dir if os.path.isabs(write_dir) else os.path.join(root, write_dir)
            written_path = _write(source, target, qualname)

    # Authoritative final measurement — reflects every written test, including
    # the last pass's, and is the validation of what converge actually achieved.
    final_result = profile(file, function, project_root)
    final = final_result.total_survived
    at_ceiling = final == 0
    # Make the written suite actually runnable in the consumer and state how —
    # Wesker ran the tests by direct call; a real user runs `pytest`.
    wiring = wire_pytest(root, written_path) if written_path else None
    # Classify whatever converge could not kill: killable (a witness = a suggested
    # test), equivalent (retained), or uncertain — so "remaining" is never opaque.
    survivor_report: SurvivorReport | None = None
    if final > 0:
        try:
            survivor_report = classify_survivors(file, function, project_root)
        except Exception:  # noqa: BLE001 — classification is advisory; never fail the run
            survivor_report = None
    # Functionally complete = every KILLABLE mutant killed. Equivalent survivors do
    # not count against it (no test can kill them); an uncertain survivor does, since
    # we can't prove it unkillable.
    functionally_complete = final == 0 or (
        survivor_report is not None
        and not survivor_report.killable
        and not survivor_report.unclassified
    )
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
        remaining=_remaining_summary(final_result.survivor_records),
        wiring=wiring,
        survivor_report=survivor_report,
        functionally_complete=functionally_complete,
    )
