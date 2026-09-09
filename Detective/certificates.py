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

WHAT. ``<write-dir>/certificates.json`` — beside the generated suites, ``tests/detective/`` by
default: ``{func_key: {"function_digest", "standing", "refusal", "cut_reasons"}}``. ``standing`` is
`converge.certificate_standing`'s code, recorded VERBATIM — one derivation, consumed, never
re-derived here (#17/#38/#60). ``refusal`` names why an incomplete run was a DECLINE rather than a
gap (`certificate_refusal`, pure) — it is scoped to ``incomplete`` and says nothing about the other
standings. ``cut_reasons`` names why an ``ungateable`` run could not support a certificate at all
(`certificate_cut_reasons`, pure), in `validity.CUT_REASONS`' vocabulary: added because this ledger
predates that vocabulary, so an invalid measurement was recorded as a category with no remedy.
No timestamp: determinism is the product, and a ledger whose bytes change on identical runs is
noise, not a record.

VERSIONED WITH THE SUITE IT CERTIFIES — NOT A CACHE, NOT PURGED (founder ruling 2026-09-06: "the
synths and the certificates should be synced properly"). This ledger first lived under
``.detective/`` as regenerable analysis output — which it is — but ``.detective/`` is ignored, so
the one static fact the ordering law reads existed only on the machine that ran converge: the
first `plan Detective/` over a fresh reading found every region unpinned but the fifteen certified
that morning. A synth and its certificate are two halves of one artifact — the suite pins, the
certificate says converge SAW it pin — and halves kept in different directories part at the first
clone. So the ledger lives where the synths live, travels with them, and `purge` leaves it alone.
The next converge rebuilds an entry, and a re-run that changes nothing changes no bytes.
"""

from __future__ import annotations

import json
import os

from .atomic_store import atomic_write_text

DEFAULT_WRITE_DIR = os.path.join("tests", "detective")  # converge's default suite location
CERTIFICATES_FILENAME = "certificates.json"
# The default location — the ledger's path under the default write-dir.
CERTIFICATES_REL_PATH = os.path.join(DEFAULT_WRITE_DIR, CERTIFICATES_FILENAME)


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


def certificate_cut_reasons(standing: str, cut_reasons: tuple[str, ...]) -> tuple[str, ...]:
    """WHICH invalidity an ``ungateable`` certificate rests on (§14.1 — pure, pinned).

    ``standing`` already says the measurement could not support a certificate; this says which of
    `validity.CUT_REASONS` refused it, so the record names a remedy instead of a category. The
    ledger predates that vocabulary: S13 split one `mutant_evaluation_failed` flag into three
    reasons with three different fixes (report an engine defect / unwrap the target / route a test
    through the patched name), and a reader of this file could see only that something was wrong.

    Carried for EVERY standing, not just the invalid one. A tuple that is empty because nothing was
    cut is itself a fact, and folding it into "absent" would make "recorded, none" and "recorded
    before this field existed" the same bytes — the distinction an absent-sentinel exists for.

    ``reason_unrecorded`` is the load-bearing state, and it is the move `measurement_cut_reasons`
    already makes with ``engine_refused_unspecified`` one layer up: an empty reason list beside a
    refusal reads as "no problems found", which is how a refusal gets talked past. Through
    `normalize_validity` it cannot arise — an engine that does not report ``is_gateable`` cannot
    refuse, so ``gateable`` defaults True — but ``ConvergeResult.admits_certificate`` deliberately
    falls back to the flattened fields for a result built without a live measurement, and
    ``measurement_gateable=False`` with no reasons is constructible there. Measured: 6 of
    `measurement_cut_reasons`' 7680 input combinations refuse with an empty tuple, all of them
    ``reported_gateable=False``. Named here rather than persisted as an empty list.
    """
    if standing != "ungateable":
        return cut_reasons
    return cut_reasons or ("reason_unrecorded",)


def _path(root: str, write_dir: str) -> str:
    """The ledger beside the suite: ``write_dir`` absolute as given, else under ``root`` — the same
    resolution `certify.read_behavior_status` applies to the synths, so the two cannot part."""
    target = write_dir if os.path.isabs(write_dir) else os.path.join(os.path.abspath(root), write_dir)
    return os.path.join(target, CERTIFICATES_FILENAME)


def _load_all(root: str, write_dir: str) -> dict:
    """Every entry, or ``{}`` — an unreadable or malformed ledger is no ledger, never an error that
    stops a converge or a plan."""
    try:
        with open(_path(root, write_dir), encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def record_certificate(
    root: str,
    func_key: str,
    function_digest: str,
    standing: str,
    refusal: str,
    write_dir: str = DEFAULT_WRITE_DIR,
    cut_reasons: tuple[str, ...] = (),
) -> str:
    """Record ``func_key``'s terminal verdict for the definition ``function_digest`` (the I/O
    shell — unit-guarded, not pinned). Returns the ledger path, or "" when nothing was written.

    ``write_dir`` is the suite's location — the ledger lives beside the synths it certifies, so a
    converge that writes its suite elsewhere records its certificate there too.

    Best-effort by design, like the report file: a ledger write must never fail the converge that
    produced the verdict. A result carrying NO identity (``function_digest == ""``: an older caller
    or a directly-built result) is not recorded — a certificate about an unknown definition would
    read as a certificate about every definition, which is the one thing this file must not say.
    Deterministic bytes: sorted keys, fixed indent, no clock.
    """
    if not function_digest:
        return ""
    entries = _load_all(root, write_dir)
    entries[func_key] = {
        "function_digest": function_digest,
        "standing": standing,
        "refusal": refusal,
        # A LIST, and always written: `[]` means "recorded, nothing cut", while a MISSING key means
        # "written before this field existed". A reader that cannot tell those apart re-acquires
        # the ambiguity the field was added to remove.
        "cut_reasons": list(cut_reasons),
    }
    path = _path(root, write_dir)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        atomic_write_text(path, json.dumps(entries, indent=2, sort_keys=True) + "\n")
    except OSError:
        return ""
    return path


def load_certificate(root: str, func_key: str, write_dir: str = DEFAULT_WRITE_DIR) -> dict | None:
    """The recorded entry for ``func_key`` — ``{"function_digest", "standing", "refusal"}`` — or
    ``None`` when none was ever recorded (or the ledger is unreadable). Read from the suite's
    location, ``write_dir``. The caller compares the recorded digest to the current definition;
    this reader asserts nothing about currency."""
    entry = _load_all(root, write_dir).get(func_key)
    return entry if isinstance(entry, dict) else None
