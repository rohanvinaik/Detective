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

from .certify import _write
from .engine import _load_original, _resolve, profile
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


def _golden_properties(
    func_key: str, node, full_path: str, qualname: str
) -> list[ExecutableProperty]:
    """Golden-capture properties for a pure function, or [] if it can't be run
    deterministically on the synthesized inputs."""
    live = _load_original(full_path, qualname)
    if live is None:
        return []
    params = [a.arg for a in node.args.args if a.arg not in ("self", "cls")]
    captures = corroborate_captures(capture_golden(live, _numeric_inputs(params)), is_pure=True)
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
        source = render_module(func_key, sound)
        if source and write_dir:
            target = write_dir if os.path.isabs(write_dir) else os.path.join(root, write_dir)
            written_path = _write(source, target, qualname)
        iterations.append(ConvergeIteration(survivors, len(sound)))

        if not sound:  # nothing sound to add -> no further progress possible
            hit_max = False
            break

    final = iterations[-1].survivors if iterations else 0
    return ConvergeResult(
        function=func_key,
        converged=_converged(final == 0, hit_max),
        at_ceiling=final == 0,
        initial_survivors=initial or 0,
        final_survivors=final,
        iterations=tuple(iterations),
        written_path=written_path,
    )
