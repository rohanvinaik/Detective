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
