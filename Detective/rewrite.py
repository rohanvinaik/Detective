"""Old-vs-new preservation gate for ARBITRARY rewrites (issue #37).

Detective's ``decompose`` transform has a built-in old-vs-new proof: converge the original, trial-
write the extraction, rerun the target-specific proof suite. An arbitrary external/model rewrite has
no such gate — converging the rewritten source characterizes what it NOW does, never whether that
matches the original, and the pre-existing pytest file stays green precisely because no witness
exercised the newly introduced predicate. This module closes that gap with a two-step protocol:

  1. ``receipt`` records the ORIGINAL — its proof basis, its source (so the old implementation can be
     RUN), its policy and operator-universe size — into a JSON file, before the rewrite.
  2. ``verify-rewrite`` checks a rewrite against that receipt: it replays the old obligations on the
     new source, profiles the new source for dimensions the old proof never covered, and for each new
     distinguishing input evaluates OLD and NEW at the same value — reporting equality / difference /
     abstention rather than silently learning the new behaviour.

The verdict never upgrades "no witness found" to "preserved": a new dimension or an old/new
difference refuses automatic preservation, and replacing the receipt requires explicit acceptance.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class RewriteReceipt:
    """A signed-in-spirit snapshot of a function's specification BEFORE an arbitrary rewrite (#37).

    Carries the original SOURCE — not just a digest — so ``verify-rewrite`` can execute the old
    implementation and compare it to the new one at a distinguishing input. Everything else binds the
    claim: which proof suite discharged the obligations, under which Wesker policy, over how large an
    operator universe, and whether that basis actually verified green when the receipt was taken.
    """

    function: str  # "file.py::fn", relative to project root
    original_source: str  # the function's exact source text — the OLD implementation, runnable
    source_digest: str  # sha256 of original_source — detects an unchanged/again-rewritten target
    function_digest: str  # AST digest (pins.function_digest) — position-independent identity
    policy_id: str | None  # Wesker mutation policy the obligations were measured under
    universe_size: int  # operator-universe size the original spanned
    proof_suite: tuple[str, ...]  # proof-basis paths (relative) that discharged the obligations
    proof_status: str  # the verification status when recorded (should be "passed")
    functionally_complete: bool  # was the original mutation-complete when the receipt was taken
    schema: str = "detective-rewrite-receipt/1"

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, default=str)

    @staticmethod
    def from_json(text: str) -> RewriteReceipt:
        d = json.loads(text)
        d.pop("schema", None)
        d["proof_suite"] = tuple(d.get("proof_suite", ()))
        return RewriteReceipt(**d, schema="detective-rewrite-receipt/1")


@dataclass(frozen=True)
class RewriteVerification:
    """The typed outcome of verifying a rewrite against a receipt (#37)."""

    verdict: str  # PRESERVED | CHANGED | UNREVIEWED | ABSTAIN | STALE_RECEIPT
    function: str
    proof_replayed: str  # the pytest status of replaying the old proof suite on the NEW source
    new_dimensions: tuple[str, ...]  # killable mutants the old proof does not kill on the new source
    differences: tuple[str, ...]  # inputs where OLD and NEW implementations produced different results
    abstentions: tuple[str, ...]  # inputs where old-vs-new could not be safely compared
    note: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, default=str)


def rewrite_verdict(
    receipt_valid: bool,
    classification_ran: bool,
    proof_replayed_ok: bool,
    new_dimensions: int,
    differences: int,
    abstentions: int,
) -> str:
    """The rewrite-preservation verdict (issue #37, pure — Detective-pinned).

    PRESERVED is the STRONGEST claim and the hardest to earn: it requires POSITIVE evidence on EVERY
    axis, so absence of evidence can never masquerade as it. In order of severity —

    * ABSTAIN when the check could not be MADE: the receipt is not a valid baseline (the original was
      not itself a complete, green-verified proof, so replaying its obligations proves nothing), OR
      survivor classification could not run (a raised/None report is 'we did not look', never 'we
      looked and found zero new dimensions'). This is the soundness gate: no measurement, no verdict.
    * CHANGED when a difference is PROVEN: the old proof suite fails on the new source, or old and new
      disagree at a distinguishing input.
    * UNREVIEWED when the new source added a behavioural dimension the receipt never covered.
    * ABSTAIN again for any residual that could not be compared (unclassified / candidate-equivalent
      survivors fold into ``abstentions``).
    * PRESERVED only when ALL hold: valid baseline, classification ran, proof replays green, no new
      dimension, no difference, no abstention.
    """
    if not receipt_valid or not classification_ran:
        return "ABSTAIN"
    if not proof_replayed_ok or differences > 0:
        return "CHANGED"
    if new_dimensions > 0:
        return "UNREVIEWED"
    if abstentions > 0:
        return "ABSTAIN"
    return "PRESERVED"


def _function_source(file_full: str, function: str) -> tuple[str, Any] | None:
    """(source_text, node) for ``function`` in the file, or None if not found."""
    from .engine import _resolve

    with open(file_full, encoding="utf-8") as fh:
        text = fh.read()
    tree = ast.parse(text, filename=file_full)
    qualname, node = _resolve(tree, function)
    if node is None:
        return None
    seg = ast.get_source_segment(text, node)
    return (seg or "", node)


def make_receipt(
    file: str, function: str, project_root: str = ".", *, notify: Callable[[str], None] | None = None
) -> RewriteReceipt:
    """Record the CURRENT function as the baseline a later rewrite is checked against (#37).

    Converges the target first, so the receipt's proof basis is the mutation-complete suite (the same
    obligations ``decompose`` would prove against) and the verification status is real, not assumed.
    """
    from . import pins
    from .converge import converge
    from .decompose_apply import _covering_test_files, _kill_matrix

    root = os.path.abspath(project_root)
    full = file if os.path.isabs(file) else os.path.join(root, file)
    fs = _function_source(full, function)
    if fs is None:
        raise LookupError(f"function {function!r} not found in {file}")
    original_source, node = fs

    conv = converge(file, function, project_root, notify=notify)
    proof: list[str] = []
    if conv.written_path:
        proof.append(os.path.relpath(conv.written_path, root))
    proof.extend(_covering_test_files(root, _kill_matrix(file, function, project_root)))
    proof_paths = tuple(dict.fromkeys(proof))
    ver = conv.verification
    return RewriteReceipt(
        function=conv.function,
        original_source=original_source,
        source_digest=hashlib.sha256(original_source.encode("utf-8")).hexdigest(),
        function_digest=pins.function_digest(node),
        policy_id=conv.policy_id,
        universe_size=conv.universe_size,
        proof_suite=proof_paths,
        proof_status=(
            ver.status if ver is not None else ("passed" if conv.functionally_complete else "unverified")
        ),
        functionally_complete=conv.functionally_complete,
    )


def _load_old_callable(
    receipt: RewriteReceipt, new_globals: dict[str, Any], function: str
) -> Callable[..., Any] | None:
    """Exec the receipt's original source in a namespace seeded from the NEW module's globals, so the
    old implementation's free names (imports, module helpers) resolve. Returns the old callable."""
    name = function.split(".")[-1]
    ns: dict[str, Any] = dict(new_globals)
    try:
        exec(compile(receipt.original_source, "<receipt-original>", "exec"), ns)  # noqa: S102 — the receipt's own recorded source, under the user's control
    except Exception:  # noqa: BLE001
        return None
    fn = ns.get(name)
    return fn if callable(fn) else None


def verify_rewrite(
    receipt: RewriteReceipt,
    file: str,
    function: str,
    project_root: str = ".",
    *,
    notify: Callable[[str], None] | None = None,
) -> RewriteVerification:
    """Check a rewrite against its receipt (issue #37) — replay, new-dimension scan, old-vs-new compare.

    Reports rather than learns: a distinguishing input is EVALUATED against both implementations and
    surfaced as equal / different / abstained, never captured as the new golden.
    """
    from . import pins
    from .certify import run_pytest_verification
    from .engine import _load_original, classify_survivors
    from .equivalence import _outcome

    say = notify or (lambda _m: None)
    root = os.path.abspath(project_root)
    full = file if os.path.isabs(file) else os.path.join(root, file)

    fs = _function_source(full, function)
    if fs is None:
        raise LookupError(f"function {function!r} not found in {file}")
    _new_source, new_node = fs
    # A receipt whose recorded source equals the current source is not describing a REWRITE — there is
    # nothing to verify, and "PRESERVED" would be a vacuous pass. Say so distinctly.
    if pins.function_digest(new_node) == receipt.function_digest:
        return RewriteVerification(
            "STALE_RECEIPT",
            receipt.function,
            "skipped",
            (),
            (),
            (),
            note="the current source is identical to the receipt's original — nothing was rewritten",
        )

    # 1. REPLAY the original obligations on the new source.
    say("replaying the original proof suite against the rewritten source…")
    abspaths = [p if os.path.isabs(p) else os.path.join(root, p) for p in receipt.proof_suite]
    replay = run_pytest_verification(root, abspaths, basis="target-complete") if abspaths else None
    proof_replayed = replay.status if replay is not None else "no_tests"
    proof_ok = replay is not None and replay.ok

    # 2. NEW DIMENSIONS + witnesses: classify the new source's survivors against the old proof basis.
    #    A killable survivor is a behaviour the new source has and the old proof never pinned.
    say("profiling the rewritten source for behaviours the original proof never covered…")
    new_dimensions: list[str] = []
    differences: list[str] = []
    abstentions: list[str] = []
    try:
        report = classify_survivors(file, function, project_root, deadline_s=120.0)
    except Exception:  # noqa: BLE001
        report = None

    new_fn = _load_original(full, function)
    old_fn = (
        _load_old_callable(receipt, getattr(new_fn, "__globals__", {}) or {}, function) if new_fn else None
    )

    if report is not None:
        for verdict in report.killable:
            new_dimensions.append(verdict.diff_summary or verdict.mutant_id)
            # 3. OLD-vs-NEW at the witness input: does the rewrite actually change behaviour there?
            w = verdict.witness
            if w is None or old_fn is None or new_fn is None:
                abstentions.append(verdict.mutant_id)
                continue
            old_out = _outcome(old_fn, w.args)
            new_out = _outcome(new_fn, w.args)
            if old_out.startswith("<classifier-timeout") or new_out.startswith("<classifier-timeout"):
                abstentions.append(f"{verdict.mutant_id} @ {w.args!r}")
            elif old_out != new_out:
                differences.append(f"{w.args!r}: old={old_out} new={new_out}")
        # Survivors the search could not classify, and mutants no input distinguished, are behaviours
        # the old proof did not pin and this run could not resolve — they must forbid PRESERVED, not
        # be silently ignored (they were). Fold both into abstentions (absence of a resolving witness).
        abstentions.extend(f"unclassified:{u}" for u in report.unclassified)
        abstentions.extend(f"candidate-equivalent:{v.mutant_id}" for v in report.candidate_equivalent)

    # SOUNDNESS GATES (issue #37, reopened): PRESERVED is impossible unless the baseline itself was a
    # complete, green-verified proof (else replaying its obligations proves nothing), and unless the
    # classification actually ran (a None report is 'we did not look'). Both feed the pure verdict.
    receipt_valid = receipt.functionally_complete and receipt.proof_status == "passed"
    classification_ran = report is not None
    if not receipt_valid:
        say("⚠ the receipt is not a complete, verified baseline — preservation cannot be established")
    if not classification_ran:
        say("⚠ survivor classification could not run on the rewritten source — abstaining")
    verdict_str = rewrite_verdict(
        receipt_valid, classification_ran, proof_ok, len(new_dimensions), len(differences), len(abstentions)
    )
    return RewriteVerification(
        verdict=verdict_str,
        function=receipt.function,
        proof_replayed=proof_replayed,
        new_dimensions=tuple(dict.fromkeys(new_dimensions)),
        differences=tuple(dict.fromkeys(differences)),  # many mutants share one witness input
        abstentions=tuple(dict.fromkeys(abstentions)),
    )
