"""Adversarial adequacy benchmark for the supported decomposition transform Τ_Detective (#15).

Issue #16 makes the extraction's interface contract EXPLICIT and marks the non-value dimensions
(``alias_mutation``, ``effect_order``) as ``witnessed`` — believed-preserved and exercised by a
green rerun, but not proven. This module FALSIFIES that belief. It drives an extraction to a green
PROVEN state, injects a fault into the transform's OUTPUT (a τ′ a buggy transformer could emit),
reruns the SAME mutation-complete proof suite, and asks whether the suite REJECTS the fault. The
adequacy claim under test:

    τ ∈ Τ_Detective  ∧  τ(P) ≠ P   ⇒   the μ-complete proof suite rejects τ(P)

A behavior-changing fault the suite fails to reject (``undetected``) is a dimension whose
``witnessed`` status is too strong — the finding that should downgrade it to ``unsupported`` in
#16's model, turning a silent auto-apply into an honest proposal. A result is keyed by
``(policy_id, transform_class_id)``: adequacy is a claim about ONE rewrite model under ONE
mutation policy, and a bump to either invalidates it — the same two ids a PROVEN claim carries.

Milestone-1 fault families (issue #15's own first list): helper-signature omission, return
packing, call-site unpacking order, ordered-effect deletion. Eval-order, exception-region, and
async/generator are the declared next families. The harness does not assert equivalence of an
``undetected`` fault — it surfaces it for review, because a green suite there is EITHER a genuine
no-op OR an inadequacy, and a differential old-vs-new oracle (issue #37's territory) is what
separates them.
"""

from __future__ import annotations

import ast
from collections.abc import Callable
from dataclasses import dataclass

# ── the classification decision (the one named code the driver consumes) ────


def adequacy_bucket(produced: bool, import_broke: bool, suite_passed: bool) -> str:
    """Classify one adversarial fault's outcome against the proof suite (#15, pure — pinned).

    A named code, never a bool — the four cases mean different things and must not collapse:

    * ``not_applicable`` — the fault family does not apply to this extraction (e.g. a return-swap
      on a helper with fewer than two returns). Nothing was tested; not evidence either way.
    * ``structurally_impossible`` — the fault produced source the runner could not even import.
      A τ′ that will not load is not one Τ_Detective could emit, so it does not bear on adequacy.
    * ``detected`` — the fault produced a loadable τ′ and the proof suite went RED. The adequacy
      claim HOLDS for this fault: a distinguishable rewrite was rejected.
    * ``undetected`` — the fault produced a loadable τ′ and the suite stayed GREEN. This is the
      finding: the μ-complete suite did not reject it. Surfaced for review (genuine no-op vs a
      real inadequacy), keyed by policy and transform class."""
    if not produced:
        return "not_applicable"
    if import_broke:
        return "structurally_impossible"
    return "detected" if not suite_passed else "undetected"


def bucket_is_finding(bucket: str) -> bool:
    """Whether an adequacy bucket is a REPORTABLE gap (#15, pure — pinned). Only ``undetected`` is:
    a fault the suite failed to reject. ``not_applicable`` and ``structurally_impossible`` are
    non-events, and ``detected`` is the claim holding — none of them is a gap."""
    return bucket == "undetected"


# ── the fault families: a buggy transformer's τ′, injected into the output ──


def _helper_def(tree: ast.Module, helper_name: str) -> ast.FunctionDef | None:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == helper_name:
            return node
    return None


def _last_return_tuple(fn: ast.FunctionDef) -> ast.Return | None:
    """The helper's ``return a, b`` statement, if its value is a tuple of ≥2 elements."""
    for node in ast.walk(fn):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Tuple) and len(node.value.elts) >= 2:
            return node
    return None


def drop_helper_param(source: str, helper_name: str) -> str | None:
    """Fault: emit the helper missing its LAST parameter, call site unchanged. A dropped param is
    one the finder proved the block reads, so the call now passes an argument the signature will
    not accept (or the body reads an unbound name) — a τ′ that must be rejected."""
    tree = ast.parse(source)
    fn = _helper_def(tree, helper_name)
    if fn is None or not fn.args.args:
        return None
    fn.args.args = fn.args.args[:-1]
    return ast.unparse(tree)


def swap_helper_returns(source: str, helper_name: str) -> str | None:
    """Fault: reverse the order of the helper's returned tuple. The call site unpacks positionally,
    so each output binds a sibling's value — a behavior change whenever the outputs are not
    interchangeable. Not applicable to a single-return helper."""
    tree = ast.parse(source)
    fn = _helper_def(tree, helper_name)
    if fn is None:
        return None
    ret = _last_return_tuple(fn)
    if ret is None or not isinstance(ret.value, ast.Tuple):
        return None
    ret.value.elts = list(reversed(ret.value.elts))
    return ast.unparse(tree)


def swap_call_unpacking(source: str, helper_name: str) -> str | None:
    """Fault: reverse the LHS tuple of the call-site assignment ``x, y = helper(...)`` → ``y, x``.
    Same distinguishing power as a return swap, injected at the OTHER end of the interface. Not
    applicable unless the call assigns to a tuple of ≥2 targets."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1):
            continue
        call, target = node.value, node.targets[0]
        if (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id == helper_name
            and isinstance(target, ast.Tuple)
            and len(target.elts) >= 2
        ):
            target.elts = list(reversed(target.elts))
            return ast.unparse(tree)
    return None


def drop_ordered_effect(source: str, helper_name: str) -> str | None:
    """Fault: delete an ordered side-effect statement (a bare call ``log(x)``) from the helper body.
    If any test observes the effect, the suite must reject its removal. Not applicable to a helper
    with no discarded-call statement."""
    tree = ast.parse(source)
    fn = _helper_def(tree, helper_name)
    if fn is None:
        return None
    for i, stmt in enumerate(fn.body):
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            del fn.body[i]
            if not fn.body:  # a helper cannot have an empty body
                return None
            return ast.unparse(tree)
    return None


# The registry the driver iterates. Each entry: (family name, injector). Order is stable so a
# report is byte-reproducible; the family name is what a finding is keyed and reported under.
FAULT_FAMILIES: tuple[tuple[str, Callable[[str, str], str | None]], ...] = (
    ("drop_helper_param", drop_helper_param),
    ("swap_helper_returns", swap_helper_returns),
    ("swap_call_unpacking", swap_call_unpacking),
    ("drop_ordered_effect", drop_ordered_effect),
)


# ── the report ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class FaultOutcome:
    """One fault family's result against one proven extraction."""

    family: str
    helper_name: str
    bucket: str  # not_applicable | structurally_impossible | detected | undetected


@dataclass(frozen=True)
class AdequacyReport:
    """The adequacy of ONE function's proof suite against every fault family, keyed by the two ids
    a PROVEN claim carries — a result minted under one rewrite model or policy is not another's."""

    function: str
    policy_id: str | None
    transform_class_id: str | None
    outcomes: tuple[FaultOutcome, ...]
    abstain_reason: str = ""

    @property
    def findings(self) -> tuple[FaultOutcome, ...]:
        """The undetected faults — dimensions the μ-complete suite failed to reject."""
        return tuple(o for o in self.outcomes if bucket_is_finding(o.bucket))

    @property
    def adequate(self) -> bool:
        """The suite is adequate for the tested families when it ran and produced no finding. An
        abstention (no proven extraction, no generated proof suite) is NOT adequacy — it is the
        benchmark declining to make a claim, so it reads False and names why."""
        return not self.abstain_reason and not self.findings


def run_adequacy(file: str, function: str, project_root: str = ".") -> AdequacyReport:
    """Drive ``function`` to a PROVEN extraction, then falsify each fault family against its
    mutation-complete proof suite (#15).

    Abstains — rather than claiming adequacy — when there is no proven extraction to attack or no
    Detective-generated proof suite to rerun (the pre-existing-suite case is a declared gap: this
    milestone reruns ``written_path`` only). The target file is written with each faulted source to
    run the real consumer pytest, then RESTORED in a finally, exactly as the trial loop does."""
    import os

    from .certify import run_pytest_verification
    from .decompose_apply import apply_decomposition
    from .engine import _purge_stale_bytecode

    root = os.path.abspath(project_root)
    full = file if os.path.isabs(file) else os.path.join(root, file)

    result = apply_decomposition(file, function, project_root, write=False)
    proof = result.proof
    proof_suite = proof.written_path if proof is not None else None
    proven = [d.extraction for d in result.proposed if d.validated]

    if not proven:
        reason = "no proven extraction to attack"
    elif not proof_suite:
        reason = "no generated proof suite (pre-existing-suite case not yet covered — milestone 1)"
    else:
        reason = ""
    if reason:
        return AdequacyReport(
            function,
            result.policy_id,
            result.transform_class_id,
            (),
            abstain_reason=reason,
        )

    # The two abstain branches above return whenever proof_suite is falsy, so it is a non-None str
    # here. Stated rather than relied upon, so a later edit to the guard cannot silently feed None
    # into the runner (the invariant is three branches up, not adjacent).
    assert proof_suite is not None

    with open(full, encoding="utf-8") as fh:
        original = fh.read()

    outcomes: list[FaultOutcome] = []
    try:
        for extraction in proven:
            for family, inject in FAULT_FAMILIES:
                faulted = inject(extraction.new_source, extraction.helper_name)
                if faulted is None:
                    outcomes.append(FaultOutcome(family, extraction.helper_name, "not_applicable"))
                    continue
                with open(full, "w", encoding="utf-8") as fh:
                    fh.write(faulted)
                _purge_stale_bytecode(full)
                v = run_pytest_verification(root, proof_suite)
                import_broke = v.status == "collection_failed"
                bucket = adequacy_bucket(
                    produced=True, import_broke=import_broke, suite_passed=v.status == "passed"
                )
                outcomes.append(FaultOutcome(family, extraction.helper_name, bucket))
    finally:
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(original)
        _purge_stale_bytecode(full)

    return AdequacyReport(function, result.policy_id, result.transform_class_id, tuple(outcomes))
