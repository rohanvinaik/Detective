"""The style judgment ledger — the driver's recorded answer to an AMBIGUOUS region (§14.5).

AMBIGUOUS is where taste lives, by the automation boundary: one lens alone, or the two signs
disagreeing, is the driver's call and never the controller's. But a call that is not RECORDED
re-escalates on every run, so the plan's human channel needs a floor: this ledger.

DIVISION — the founder's condition for sharing the `flag` verb with the behavior layer. This is a
DIFFERENT file from the mutant-equivalence ledger (`equivalents.json`), with a different reader and
a different consumer: it is never read by `converge`, `audit`, `decompose` or `certify`; it never
affects ✓ COMPLETE, `audit --check`, or any behavior-layer exit code. The two share a verb because
both mean "a recorded, defeasible human judgment". They share nothing else.

DEFEASIBLE. A judgment is about ONE definition (the function digest) under ONE reading (the
controller verdict at the time). When either moves the judgment is REOPENED — reported as such,
never silently honoured, never silently dropped — and the region is the driver's again.

USER DATA. Like `equivalents.json`, `inputs.json` and `line_flags.json`, this is a human's
irreducible input, not regeneratable analysis: `purge` must never delete it.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass

from .atomic_store import atomic_write_text

JUDGMENTS_REL_PATH = os.path.join(".detective", "judgments.json")

LEAVE = "leave"  # the driver's answer: leave this region alone
PROCEED = "proceed"  # the driver's answer: treat this AMBIGUOUS region as a case for change
DISPOSITIONS = (LEAVE, PROCEED)

REOPENED_DIGEST = "reopened_digest"
REOPENED_VERDICT = "reopened_verdict"
DISPOSITION_UNKNOWN = "disposition_unknown"


@dataclass(frozen=True)
class StyleJudgment:
    """One recorded judgment about one region: the definition it was about (digest), the reading it
    answered (the controller verdict then), the answer, and why."""

    func_key: str
    function_digest: str
    verdict: str
    disposition: str  # leave | proceed
    note: str = ""


def judgment_standing(
    recorded_digest: str,
    current_digest: str,
    recorded_verdict: str,
    current_verdict: str,
    disposition: str,
) -> str:
    """Whether a recorded judgment still speaks for this region (§14.5 — pure, pinned). Named codes,
    because "no judgment", "a judgment about other code", and "a judgment the banks have since
    overtaken" are three different facts with three different renderings:

      ""                     no judgment recorded (``recorded_digest == ""``)
      "reopened_digest"      the definition moved since the judgment — it was about other code
      "reopened_verdict"     the banks now read this definition differently — the question changed
      "disposition_unknown"  a recorded disposition outside the vocabulary — named, never honoured
      "leave" | "proceed"    the judgment stands

    Checked in that order: a judgment about code that no longer exists is reopened whatever it said.
    """
    if not recorded_digest:
        return ""
    if recorded_digest != current_digest:
        return REOPENED_DIGEST
    if recorded_verdict != current_verdict:
        return REOPENED_VERDICT
    if disposition not in DISPOSITIONS:
        return DISPOSITION_UNKNOWN
    return disposition


def style_flag_refusal(has_mutant_id: bool, leave: bool, proceed: bool) -> str:
    """Why a `flag --style` invocation cannot be recorded (§14.5 — pure, pinned). Named codes:

      ""                       well-formed: a region, exactly one disposition
      "mutant_id_with_style"   a mutant id was given — `--style` judges a REGION, not a mutant; the
                               two ledgers must not be addressed in one breath
      "no_disposition"         neither --leave nor --proceed
      "both_dispositions"      both — a judgment is one answer

    The mutant-id collision is checked first: it is the division-blurring mistake, and naming it
    before the disposition keeps the two layers apart in the reader's head as well as on disk.
    """
    if has_mutant_id:
        return "mutant_id_with_style"
    if leave and proceed:
        return "both_dispositions"
    if not (leave or proceed):
        return "no_disposition"
    return ""


def _path(root: str) -> str:
    return os.path.join(os.path.abspath(root), JUDGMENTS_REL_PATH)


def load_judgments(root: str) -> dict[str, StyleJudgment]:
    """Every persisted judgment, keyed by func_key. Empty (never an error) when the ledger is absent
    or unreadable; a malformed entry is skipped, never fatal — a missing oracle is no oracle."""
    try:
        with open(_path(root), encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, StyleJudgment] = {}
    for key, value in raw.items():
        try:
            out[key] = StyleJudgment(**value)
        except (TypeError, ValueError):
            continue
    return out


def save_judgments(root: str, judgments: dict[str, StyleJudgment]) -> None:
    """Persist the ledger atomically (#63): a judgment is irreducible human input; a mid-write crash
    must not clobber the store into an empty file the next load silently accepts."""
    path = _path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {key: asdict(j) for key, j in sorted(judgments.items())}
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def add_judgment(
    root: str, func_key: str, function_digest: str, verdict: str, disposition: str, note: str = ""
) -> StyleJudgment:
    """Record (or replace — one judgment per region) the driver's answer and persist it."""
    judgments = load_judgments(root)
    judgment = StyleJudgment(func_key, function_digest, verdict, disposition, note)
    judgments[func_key] = judgment
    save_judgments(root, judgments)
    return judgment


def judgment_for(root: str, func_key: str) -> StyleJudgment | None:
    """The recorded judgment for ``func_key``, or ``None``. Object handling only; the standing —
    whether it still applies — is :func:`judgment_standing`'s decision."""
    return load_judgments(root).get(func_key)


STYLE_REGIME_CONFLICT = "regime_conflict"
STYLE_NO_SUCH_FUNCTION = "no_such_function"


@dataclass(frozen=True)
class StyleRecording:
    """What one `flag --style` / `flag(style=True)` call did: a typed refusal (nothing written), or
    the judgment as recorded. ONE actuator for both surfaces (§14.5 / §14.9 slice 8), so the CLI and
    the MCP tool cannot drift on what is refused, what the judgment is keyed to, and what is written.

    ``refusal``: "" · mutant_id_with_style · no_disposition · both_dispositions (the three malformed
    shapes, `style_flag_refusal`) · regime_conflict · no_such_function.
    """

    refusal: str
    region: str = ""
    disposition: str = ""
    controller_verdict: str = ""
    function_digest: str = ""
    note: str = ""
    regions_in_file: tuple[str, ...] = ()  # on no_such_function: the file's regions, bare names
    regime: object = None  # on regime_conflict: the surface renders the conflicts in its own idiom


def record_style_judgment(
    project_root: str,
    file: str,
    function: str,
    has_mutant_id: bool,
    leave: bool,
    proceed: bool,
    note: str = "",
) -> StyleRecording:
    """Record the driver's answer to an AMBIGUOUS region — LEAVE or PROCEED — in the style ledger.
    STATIC: no live session, no mutant (a judgment about form never profiles anything). Refuses, in
    order: the three malformed shapes (`style_flag_refusal`); a regime conflict (the same resolver
    the live verbs use — a judgment about the wrong file is about nothing); a function the file does
    not define (the file's regions are named). Otherwise keyed to the CURRENT definition (its digest)
    and the CURRENT reading (the controller verdict now), so an edit or a changed reading reopens it.
    """
    from . import pins
    from .parsimony_map import iter_functions
    from .plan import assemble_plan

    refusal = style_flag_refusal(has_mutant_id, leave, proceed)
    if refusal:
        return StyleRecording(refusal)
    root = os.path.abspath(project_root)
    regime = None
    try:
        from .regime import resolve_regime

        regime = resolve_regime(root, file)
    # BLE001: a guard must never be what breaks the run
    except Exception:  # noqa: BLE001
        regime = None
    if regime is not None and regime.conflicts:
        return StyleRecording(STYLE_REGIME_CONFLICT, regime=regime)
    full = file if os.path.isabs(file) else os.path.join(root, file)
    func_key = f"{os.path.relpath(full, root)}::{function}"
    node = next((n for k, n, _m in iter_functions(full, root) if k == func_key), None)
    assembly = assemble_plan(full, root)
    detail_row = next((d for d in assembly.regions if d.read.region == func_key), None)
    if node is None or detail_row is None:
        return StyleRecording(
            STYLE_NO_SUCH_FUNCTION,
            region=func_key,
            regions_in_file=tuple(d.read.region.split("::", 1)[1] for d in assembly.regions),
        )
    disposition = LEAVE if leave else PROCEED
    judgment = add_judgment(
        root, func_key, pins.function_digest(node), detail_row.read.verdict, disposition, note
    )
    return StyleRecording(
        "",
        region=func_key,
        disposition=disposition,
        controller_verdict=detail_row.read.verdict,
        function_digest=judgment.function_digest,
        note=note,
    )
