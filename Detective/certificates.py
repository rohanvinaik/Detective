"""The converge verdict ledger — one recorded terminal verdict per (target, definition) (§14.1).

WHY. The ordering law (style after behavior, STRICTLY) needs one static fact per region: has
converge certified THIS definition complete? Before this ledger the only artifacts a converge left
were the generated suite — absent exactly when the hand-written tests already kill every mutant,
i.e. for the best-tested functions — the pins / verdict caches (regenerable, keyed for other
purposes), and the report file, keyed by BARE qualname so two targets named ``load`` share one
file. A function whose converge said ✓ COMPLETE with zero synth written therefore had no
certificate anyone could read and reported ``unpinned``: an over-refusal that would send the
best-pinned functions to ``converge`` forever, since converging them again writes nothing again.
Measured 2026-09-05 on `behavior_status`, `admission_reason`, `controller_verdict` themselves.

WHAT. ``.detective/certificates.json``: ``{func_key: {"function_digest", "standing", "refusal"}}``.
``standing`` is `converge.certificate_standing`'s code, recorded VERBATIM — one derivation,
consumed, never re-derived here (#17/#38/#60). ``refusal`` names why an incomplete run was a
DECLINE rather than a gap (`certificate_refusal`, pure). No timestamp: determinism is the
product, and a ledger whose bytes change on identical runs is noise, not a record.

REGENERATABLE, NOT AUTHORED. Rebuilt by the next converge; ``purge`` deletes it. It records what
converge SAID and decides nothing — `certify.behavior_status` decides, and consumes this.
"""

from __future__ import annotations

import json
import os

from .atomic_store import atomic_write_text

CERTIFICATES_REL_PATH = os.path.join(".detective", "certificates.json")


def certificate_refusal(needs_receiver: str, environment_gated: tuple[str, ...]) -> str:
    """Why a converge DECLINED the target rather than merely fell short (§14.1 — pure, pinned).

    An ``incomplete`` standing covers two different facts: an honest gap more inputs could close,
    and a decline whose remedy is something no ``--input`` can supply. The status reader must not
    collapse them (``pinned_incomplete`` vs ``refused``), so the decline is named here:

      ""                          no refusal — an incomplete run is an honest gap
      "needs_receiver:<text>"     a method target whose receiver could not be built without help
      "environment_gated:<a,b>"   lines gated by state a caller's argument cannot set (clock,
                                  process env, filesystem, entropy) — a fixture, not an input

    The receiver is checked first: a method that could not be constructed was never measured at
    all, so whatever environment it would have read is moot.
    """
    if needs_receiver:
        return f"needs_receiver:{needs_receiver}"
    if environment_gated:
        return "environment_gated:" + ",".join(environment_gated)
    return ""


def _path(root: str) -> str:
    return os.path.join(os.path.abspath(root), CERTIFICATES_REL_PATH)


def _load_all(root: str) -> dict:
    """Every entry, or ``{}`` — an unreadable or malformed ledger is no ledger, never an error that
    stops a converge or a plan."""
    try:
        with open(_path(root), encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def record_certificate(root: str, func_key: str, function_digest: str, standing: str, refusal: str) -> str:
    """Record ``func_key``'s terminal verdict for the definition ``function_digest`` (the I/O
    shell — unit-guarded, not pinned). Returns the ledger path, or "" when nothing was written.

    Best-effort by design, like the report file: a ledger write must never fail the converge that
    produced the verdict. A result carrying NO identity (``function_digest == ""``: an older caller
    or a directly-built result) is not recorded — a certificate about an unknown definition would
    read as a certificate about every definition, which is the one thing this file must not say.
    Deterministic bytes: sorted keys, fixed indent, no clock.
    """
    if not function_digest:
        return ""
    entries = _load_all(root)
    entries[func_key] = {"function_digest": function_digest, "standing": standing, "refusal": refusal}
    path = _path(root)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        atomic_write_text(path, json.dumps(entries, indent=2, sort_keys=True) + "\n")
    except OSError:
        return ""
    return path


def load_certificate(root: str, func_key: str) -> dict | None:
    """The recorded entry for ``func_key`` — ``{"function_digest", "standing", "refusal"}`` — or
    ``None`` when none was ever recorded (or the ledger is unreadable). The caller compares the
    recorded digest to the current definition; this reader asserts nothing about currency."""
    entry = _load_all(root).get(func_key)
    return entry if isinstance(entry, dict) else None
