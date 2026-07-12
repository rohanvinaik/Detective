"""The certify loop — the product's front door.

One pass of the workflow: diagnose a function (behavioral-scope map via Wesker),
and for each unspecified degree of freedom (surviving mutant) synthesize a
warrant-classed pytest test. Optionally write the synthesized module to disk.

Driving to the ceiling is the caller's loop: certify -> write -> re-run tests ->
certify again, until ``at_ceiling``.
"""

from __future__ import annotations

import ast
import os
from dataclasses import dataclass

from .decompose import DecompositionPlan, decompose
from .engine import _resolve, profile
from .scope import ScopeMap, scope_from_profiling
from .synthesis.writer import synthesize_test_module


@dataclass(frozen=True)
class CertifyResult:
    """Outcome of one certify pass."""

    function: str
    scope: ScopeMap
    survivors: int
    at_ceiling: bool
    test_source: str  # "" when at the ceiling or nothing is synthesizable
    written_path: str | None
    decomposition: DecompositionPlan | None = None  # set for entangled (regime-B) functions


def certify(
    file: str,
    function: str,
    project_root: str = ".",
    *,
    write_dir: str | None = None,
    call_site_inputs: list[dict] | None = None,
) -> CertifyResult:
    """Diagnose ``function`` and synthesize tests for its surviving mutants."""
    root = os.path.abspath(project_root)
    full = file if os.path.isabs(file) else os.path.join(root, file)
    with open(full, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=full)

    qualname, node = _resolve(tree, function)
    if qualname is None:
        raise LookupError(f"function {function!r} not found in {file}")

    result = profile(file, function, project_root)
    scope = scope_from_profiling(result)
    func_key = f"{os.path.relpath(full, root)}::{qualname}"
    at_ceiling = result.total_survived == 0

    source = ""
    if not at_ceiling:
        source = synthesize_test_module(func_key, node, result.survivor_records, call_site_inputs)

    # Entangled functions get a decomposition plan alongside the synthesized tests.
    plan = None
    if scope.regime == "B":
        plan = decompose(node, qualname, tuple(scope.surviving_categories))

    written = _write(source, write_dir, qualname) if source and write_dir else None
    return CertifyResult(func_key, scope, result.total_survived, at_ceiling, source, written, plan)


def _write(source: str, write_dir: str, qualname: str) -> str:
    """Write synthesized source to ``write_dir/test_<qualname>_synth.py``."""
    os.makedirs(write_dir, exist_ok=True)
    safe = qualname.replace(".", "_")
    path = os.path.join(write_dir, f"test_{safe}_synth.py")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(source)
    return path
