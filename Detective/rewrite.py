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

_RECEIPT_SCHEMA = "detective-rewrite-receipt/1"


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
    # (relpath, sha256) of each proof file's CONTENT at receipt time (#37). Freezes the basis so
    # verify-rewrite can refuse when a proof file changed since the receipt — otherwise a
    # post-receipt edit that suppresses a new dimension could help produce a false PRESERVED.
    # Defaulted () for pre-#37 receipts, which read as `unfrozen` (a weaker claim, never PRESERVED).
    proof_digests: tuple[tuple[str, str], ...] = ()
    schema: str = _RECEIPT_SCHEMA

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, default=str)

    @staticmethod
    def from_json(text: str) -> RewriteReceipt:
        """Load a receipt AND validate its integrity at the load boundary (#37).

        The old loader silently *coerced* ``schema`` to the current value and never recomputed the
        source digest, so a foreign or hand-tampered JSON loaded as a trusted receipt. Now the
        schema is read (not forced) and the self-consistent gates (schema + source-digest) run via
        the pinned :func:`receipt_refusal`; an integrity failure raises rather than loading a receipt
        ``verify-rewrite`` would later trust.
        """
        d = json.loads(text)
        schema = d.pop("schema", None)
        d["proof_suite"] = tuple(d.get("proof_suite", ()))
        # JSON stores tuples as lists; restore (path, digest) PAIRS. Absent on a pre-#37 receipt →
        # () → `unfrozen` downstream, never silently trusted as a frozen basis.
        d["proof_digests"] = tuple(tuple(x) for x in d.get("proof_digests", ()))
        rec = RewriteReceipt(**d, schema=schema if isinstance(schema, str) else "")
        # requested_key == receipt.function: identity is trivially satisfied here (we have no target
        # yet), so only the self-contained schema/digest gates can fire at load time.
        reason = receipt_refusal(
            rec.schema, rec.original_source, rec.source_digest, rec.function, rec.function
        )
        if reason is not None:
            raise ValueError(f"invalid rewrite receipt: {reason}")
        return rec


def receipt_refusal(
    schema: str,
    original_source: str,
    source_digest: str,
    receipt_function: str,
    requested_key: str,
) -> str | None:
    """Reasons a receipt must be REFUSED for a target BEFORE any verification runs (#37, pure — pinned).

    A receipt is a claim about exactly ONE function. Nothing bound the receipt to the requested
    target, so a receipt for ``a.py::a`` could be replayed against ``b.py::b`` and reported
    ``PRESERVED`` for ``a.py::a`` — a preservation certificate about a function that was never
    examined. Three self-checking gates close that hole, in order of how fundamental the breach is:

    * ``schema`` — the JSON is not a receipt this version understands (a foreign/newer artifact).
    * ``source_digest`` — the recorded source does not hash to its recorded digest: the receipt is
      corrupt or was hand-edited, so its ``original_source`` (which the old implementation is RUN
      from) cannot be trusted.
    * identity — ``receipt_function`` is not the ``requested_key`` under verification: the receipt
      describes a different function entirely.

    Returns the human-readable reason to refuse, or ``None`` when the receipt is well-formed AND
    bound to exactly this target. Every gate is 'refuse', never 'measure' — absence of a match can
    never become a silent pass.
    """
    if schema != _RECEIPT_SCHEMA:
        return f"unrecognized receipt schema {schema!r} (expected {_RECEIPT_SCHEMA!r})"
    if hashlib.sha256(original_source.encode("utf-8")).hexdigest() != source_digest:
        return "receipt source digest does not match its recorded source — corrupt or tampered receipt"
    if receipt_function != requested_key:
        return (
            f"receipt is for {receipt_function!r}, but verification was requested for "
            f"{requested_key!r} — a receipt binds to exactly one function"
        )
    return None


def receipt_load_refusal(text: str, expected_schema: str) -> str:
    """Why a receipt FILE cannot be loaded at all, "" when it can (#57, pure — pinned).

    :func:`receipt_refusal` gates a receipt that already exists as an object. Everything that
    goes wrong BEFORE that — unparseable JSON, a JSON array where an object belongs, a foreign
    schema, a digest that does not match its own recorded source — reached the CLI as a raised
    exception, so `verify-rewrite` printed a traceback and, under ``--json``, printed NOTHING at
    all. A caller cannot consume a refusal state the tool never emitted, and a traceback is not
    a verdict: the whole point of a typed-outcome contract is that every ending is one of the
    named ones.

    Returns a STABLE CODE, not prose. These are consumed by callers deciding what to do next,
    and a message that reads well is worth nothing if it changes between versions:

    * ``malformed_json``  — not JSON at all.
    * ``not_an_object``   — valid JSON of the wrong shape (a list, a bare string, null).
    * ``missing_schema``  — no ``schema`` key, or one that is not a non-empty string.
    * ``unknown_schema``  — a receipt some other version wrote.
    * ``bad_fields``      — required fields absent or of the wrong type.
    * ``digest_mismatch`` — the recorded source does not hash to its recorded digest, so the
      original implementation this receipt would be REPLAYED from cannot be trusted.

    Ordered from the most fundamental breach outward, because a later check cannot be meaningful
    once an earlier one has failed: there is no schema to read in a file that is not JSON, and no
    digest to compare without a source field to hash.

    ``expected_schema`` is a parameter rather than a module read so the whole contract sits
    inside a literal grammar and can be pinned — the same split as `resolve_test_id` upstream.
    """
    try:
        parsed = json.loads(text)
    except ValueError:
        return "malformed_json"
    if not isinstance(parsed, dict):
        return "not_an_object"
    schema = parsed.get("schema")
    if not isinstance(schema, str) or not schema:
        return "missing_schema"
    if schema != expected_schema:
        return "unknown_schema"
    source = parsed.get("original_source")
    digest = parsed.get("source_digest")
    if not isinstance(source, str) or not isinstance(digest, str):
        return "bad_fields"
    if hashlib.sha256(source.encode("utf-8")).hexdigest() != digest:
        return "digest_mismatch"
    return ""


@dataclass(frozen=True)
class RewriteVerification:
    """The typed outcome of verifying a rewrite against a receipt (#37)."""

    verdict: str  # PRESERVED | CHANGED | UNREVIEWED | ABSTAIN | STALE_RECEIPT | INVALID_RECEIPT
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


def basis_freshness(frozen: dict[str, str], current: dict[str, str]) -> str:
    """Whether the proof basis a receipt froze still describes the files on disk (#37, pure — pinned).

    The receipt's obligations were discharged by a specific proof SUITE. Storing only its file
    PATHS let ``verify-rewrite`` replay whatever those paths contain NOW — so a test added or edited
    AFTER the receipt could suppress a newly introduced dimension and help produce a false
    ``PRESERVED``. Freezing each proof file's content digest lets a consumer refuse when the basis
    has moved out from under the claim.

    Three states, because "the receipt did not freeze the basis", "it froze it and the basis moved",
    and "it froze it and the basis is intact" are different facts a verdict must keep apart:

    * ``unfrozen`` — the receipt carries no digests (a pre-#37 receipt). The basis cannot be
      confirmed unchanged, so a caller must not let it reach PRESERVED — but this is a MISSING
      capability, not a detected change, and is named so rather than conflated with a real move.
    * ``moved`` — a frozen file's current digest differs, or the file is gone. The obligations no
      longer describe what would be replayed; preservation is unprovable against a basis that
      changed.
    * ``fresh`` — every frozen file is present with its recorded digest. The basis a caller is
      about to replay is exactly the one the receipt's obligations were measured against.
    """
    if not frozen:
        return "unfrozen"
    for path, digest in frozen.items():
        if current.get(path) != digest:
            return "moved"
    return "fresh"


def _function_source(file_full: str, function: str) -> tuple[str, Any, str] | None:
    """(source_text, node, qualname) for ``function`` in the file, or None if not found.

    ``qualname`` is the resolver's own name for the target (``Class.method`` for methods) — the same
    string ``converge`` stamps into a receipt's ``function`` key, so a caller can reconstruct that
    key and bind a receipt to exactly this target.
    """
    from .engine import _resolve

    with open(file_full, encoding="utf-8") as fh:
        text = fh.read()
    tree = ast.parse(text, filename=file_full)
    qualname, node = _resolve(tree, function)
    if node is None or qualname is None:
        return None
    seg = ast.get_source_segment(text, node)
    return (seg or "", node, qualname)


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
    original_source, node, _qualname = fs

    conv = converge(file, function, project_root, notify=notify)
    proof: list[str] = []
    if conv.written_path:
        proof.append(os.path.relpath(conv.written_path, root))
    proof.extend(_covering_test_files(root, _kill_matrix(file, function, project_root)))
    proof_paths = tuple(dict.fromkeys(proof))

    def _content_digest(rel: str) -> str:
        try:
            with open(os.path.join(root, rel), "rb") as fh:
                return hashlib.sha256(fh.read()).hexdigest()
        except OSError:
            return ""  # unreadable now -> a digest nothing matches -> `moved` if it reappears

    # Freeze the basis (#37): each proof file's content digest, so verify-rewrite can refuse a
    # basis that changed since the receipt rather than replay whatever the paths hold later.
    proof_digests = tuple((p, _content_digest(p)) for p in proof_paths)
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
        proof_digests=proof_digests,
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
    _new_source, new_node, qualname = fs

    # BIND the receipt to the requested target BEFORE anything is measured (#37, reopened). The
    # requested key is built exactly as ``converge`` builds a receipt's ``function`` (relpath::qualname,
    # see converge.func_key), so a receipt for a DIFFERENT function — or a corrupt/foreign one — is
    # refused here rather than replayed and reported PRESERVED for a function nobody examined. The
    # report is stamped with ``requested_key``, never the receipt's own identity, so it can never
    # mislabel which function was checked.
    requested_key = f"{os.path.relpath(full, root)}::{qualname}"
    refusal = receipt_refusal(
        receipt.schema, receipt.original_source, receipt.source_digest, receipt.function, requested_key
    )
    if refusal is not None:
        say(f"⚠ {refusal}")
        return RewriteVerification("INVALID_RECEIPT", requested_key, "skipped", (), (), (), note=refusal)

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

    # FREEZE GATE (#37): the receipt's obligations were measured against a specific proof suite.
    # If a proof file changed since — a test added or edited that could SUPPRESS a newly introduced
    # dimension — then replaying "the proof suite" replays something else, and preservation is
    # unprovable against a basis that moved. `unfrozen` (a pre-#37 receipt with no digests) is not a
    # detected move but cannot be trusted either, so it is barred from PRESERVED below.
    current_digests: dict[str, str] = {}
    for rel in receipt.proof_suite:
        try:
            with open(os.path.join(root, rel), "rb") as _fh:
                current_digests[rel] = hashlib.sha256(_fh.read()).hexdigest()
        except OSError:
            current_digests[rel] = ""  # gone -> matches no frozen digest -> `moved`
    freshness = basis_freshness(dict(receipt.proof_digests), current_digests)
    if freshness == "moved":
        say("⚠ the proof basis changed since the receipt — preservation cannot be established")
        return RewriteVerification(
            "BASIS_MOVED",
            requested_key,
            "skipped",
            (),
            (),
            (),
            note="a proof file's content differs from the digest the receipt froze",
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
    # A `fresh` frozen basis is now part of a valid baseline (#37): an `unfrozen` receipt cannot
    # ground PRESERVED (its basis may have moved unseen), so it abstains via this gate. A `moved`
    # basis already returned BASIS_MOVED above.
    receipt_valid = (
        receipt.functionally_complete and receipt.proof_status == "passed" and freshness == "fresh"
    )
    if freshness == "unfrozen":
        say("⚠ this older receipt did not freeze its proof basis — cannot establish preservation")
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
