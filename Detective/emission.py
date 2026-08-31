"""Warranted cross-language emission — the `rewrite-in-<lang>` gate (Wave 5 / EXP-DS-006).

Design: ``docs/theory/deterministic_sicp/DETERMINISTIC_SICP.md`` §8 and §11 Q6, on the LeanExpr
precedent (an emission carries its source, its ENVIRONMENT PIN, and its warrant; it compiles
relative to a named toolchain, and the external oracle verifies). The receipt (`rewrite.py`)
carries the runnable OLD source and the frozen proof basis — not (args, expected) pairs — so a
cross-language replay cannot ride the pytest suite. The gate therefore transports
`verify-rewrite`'s own differential step across the bridge: derive an **obligation ledger** by
running the receipt's old implementation over a STATED deterministic input family, and replay
it against the emission. The certificate names its observing set (the §8/Cor-8.3 discipline):
`PRESERVED` here always means *over the stated family, at the stated codec* — never more.

**The portability boundary is the L boundary, found rather than chosen (Q6's answer at v1):**
the values that can cross the bridge are exactly the `--input`-expressible kinds, minus the
target's numeric-model edges — Python's bigint beyond the target's i64, non-finite floats. A
container is codec-v2 (named, deferred). Float comparison is EXACT by design: a legitimate
IEEE divergence (e.g. contraction differences) reads CHANGED, because the conservative
direction is a false CHANGED, never a false PRESERVED.

Pure decisions (`value_portability`, `emission_disposition`, `c_literal`) are pinned; the
compile-and-run bridge is the impure instrument shell (toolchain abstention on a missing
compiler — the `count_opcodes` pattern), unit-guarded.
"""

from __future__ import annotations

import math
import os
import subprocess
from dataclasses import dataclass

_I64_MIN, _I64_MAX = -(2**63), 2**63 - 1


def value_portability(value) -> str:
    """Can this recorded obligation value cross the C bridge (pure — pinned)? Named codes:

      "portable"            bool · i64-range int · finite float · str — rides the v1 codec
      "numeric_model_risk"  an int beyond the target's i64, or a non-finite float — REAL in
                            Python, unrepresentable-or-hazardous in the target's numeric model;
                            skipped and COUNTED (the modulo qualifier), never silently dropped
      "inexpressible"       containers, None, objects — codec v2 territory, named and deferred

    ``bool`` is checked before ``int`` on purpose (bool is an int subclass, and the two render
    differently at the codec); the split mirrors the L boundary the whole tool draws — the
    portable values ARE the expressible ones, minus the numeric edges."""
    if isinstance(value, bool):
        return "portable"
    if isinstance(value, int):
        return "portable" if _I64_MIN <= value <= _I64_MAX else "numeric_model_risk"
    if isinstance(value, float):
        return "portable" if math.isfinite(value) else "numeric_model_risk"
    if isinstance(value, str):
        return "portable"
    return "inexpressible"


def emission_disposition(
    compiled: bool, ran: bool, mismatches: int, portable_count: int, skipped_count: int
) -> str:
    """The gate verdict (pure — pinned). Named codes, and the order encodes the epistemics:

    "INVALID_MEASUREMENT"          it did not compile or did not run — the exit-3 class:
                                   re-measure, no claim about the code either way
    "CHANGED"                      a portable obligation disagreed — the old and new
                                   implementations are different functions; determined-false
    "VACUOUS"                      zero portable obligations ran — a certificate over an
                                   empty observing set must NOT read preserved (the vacuity
                                   discipline: passing while constraining nothing)
    "PRESERVED_MODULO_UNPORTABLE"  every portable obligation agreed, but some could not ride
                                   the codec — preserved, observing set named as partial
    "PRESERVED_PORTABLE"           every obligation rode and agreed — preserved over the full
                                   stated family (still family-relative, never absolute)
    """
    if not compiled or not ran:
        return "INVALID_MEASUREMENT"
    if mismatches > 0:
        return "CHANGED"
    if portable_count == 0:
        return "VACUOUS"
    if skipped_count > 0:
        return "PRESERVED_MODULO_UNPORTABLE"
    return "PRESERVED_PORTABLE"


def c_literal(value) -> str | None:
    """Render a portable value as a C literal (pure — pinned): the codec's write half. ``None``
    for anything `value_portability` does not call portable — the codec never guesses. Strings
    escape backslash, quote, and newline (the v1 escape set; a string outside it still renders,
    byte-for-byte through the three escapes)."""
    if value_portability(value) != "portable":
        return None
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return f"{value}LL"
    if isinstance(value, float):
        return f"{value!r}"
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


@dataclass(frozen=True)
class CrossLangEmission:
    """The emission object — the LeanExpr homology for this domain: the target-language source,
    the entrypoint it exposes, the ENVIRONMENT it compiles against (recorded on every gate
    result; a compile is only ever relative to a toolchain), and the warrant tying it back to
    the receipt it claims to preserve."""

    language: str  # v1: "c"
    source: str  # the emitted implementation (the transform's output — hand-driven at v1)
    entrypoint: str  # the function the harness calls
    environment: str  # the toolchain pin (e.g. `cc --version` line 1) — recorded, never inferred
    warrant: str  # function key + receipt source digest — which specification this claims


def c_harness(emission: CrossLangEmission, obligations: list[tuple[tuple, object]]) -> str | None:
    """The replay harness generator: a C ``main`` calling the entrypoint once per PORTABLE
    obligation and printing one result per line (ints %lld · floats %.17g — round-trip exact
    for IEEE doubles · bools as 0/1 · strings %s). Returns ``None`` when any obligation's args
    fail the codec — the caller decides to skip-and-count, this function never partially
    renders a ledger it was handed whole."""
    calls = []
    for args, _expected in obligations:
        rendered: list[str] = []
        for a in args:
            lit = c_literal(a)
            if lit is None:
                return None
            rendered.append(lit)
        calls.append(f"    print_result({emission.entrypoint}({', '.join(rendered)}));")
    body = "\n".join(calls)
    return (
        "#include <stdio.h>\n#include <string.h>\n\n"
        + emission.source
        + '\n\nstatic void print_result(long long v) { printf("%lld\\n", v); }\n\n'
        + "int main(void) {\n"
        + body
        + "\n    return 0;\n}\n"
    )


def toolchain_pin() -> str | None:
    """The environment pin (impure shell): the first line of ``cc --version``, or ``None`` when
    no toolchain exists — the gate then ABSTAINS (INVALID_MEASUREMENT), never guesses."""
    import shutil

    cc = shutil.which("cc")
    if cc is None:
        return None
    try:
        out = subprocess.run([cc, "--version"], capture_output=True, text=True, timeout=30)
        return out.stdout.splitlines()[0] if out.stdout else None
    except (OSError, subprocess.SubprocessError):
        return None


def run_c_gate(emission: CrossLangEmission, obligations: list[tuple[tuple, object]], workdir: str) -> dict:
    """The bridge shell (impure — unit-guarded): compile the harness under the pinned toolchain
    and replay the PORTABLE obligations, comparing exactly. Returns the full result record —
    disposition, per-arm counts, the environment pin, and every mismatch with its input (the
    residual explains itself). v1 codec: integer-valued obligations end-to-end (the harness's
    print channel is %lld); wider return codecs arrive with codec v2, and an obligation whose
    expected value is not an i64-range int is skipped-and-counted, never coerced."""
    import shutil

    portable, skipped = [], 0
    for args, expected in obligations:
        arg_ok = all(value_portability(a) == "portable" for a in args)
        ret_ok = (
            not isinstance(expected, bool)
            and isinstance(expected, int)
            and value_portability(expected) == "portable"
        )
        if arg_ok and ret_ok:
            portable.append((args, expected))
        else:
            skipped += 1

    pin = toolchain_pin()
    cc = shutil.which("cc")
    if pin is None or cc is None or not portable:
        disposition = emission_disposition(
            compiled=pin is not None,
            ran=False,
            mismatches=0,
            portable_count=len(portable),
            skipped_count=skipped,
        )
        if pin is not None and not portable:
            disposition = emission_disposition(True, True, 0, 0, skipped)  # ran vacuously
        return {
            "disposition": disposition,
            "environment": pin,
            "mismatches": [],
            "portable": len(portable),
            "skipped": skipped,
        }

    src = c_harness(emission, portable)
    if src is None:
        return {
            "disposition": "INVALID_MEASUREMENT",
            "environment": pin,
            "mismatches": [],
            "portable": len(portable),
            "skipped": skipped,
        }
    c_path = os.path.join(workdir, "emission_gate.c")
    bin_path = os.path.join(workdir, "emission_gate")
    with open(c_path, "w", encoding="utf-8") as fh:
        fh.write(src)
    build = subprocess.run([cc, "-O0", "-o", bin_path, c_path], capture_output=True, text=True, timeout=120)
    if build.returncode != 0:
        return {
            "disposition": emission_disposition(False, False, 0, len(portable), skipped),
            "environment": pin,
            "mismatches": [],
            "portable": len(portable),
            "skipped": skipped,
            "compile_error": build.stderr[-500:],
        }
    run = subprocess.run([bin_path], capture_output=True, text=True, timeout=120)
    if run.returncode != 0:
        return {
            "disposition": emission_disposition(True, False, 0, len(portable), skipped),
            "environment": pin,
            "mismatches": [],
            "portable": len(portable),
            "skipped": skipped,
        }
    lines = run.stdout.splitlines()
    mismatches = []
    if len(lines) != len(portable):
        return {
            "disposition": emission_disposition(True, False, 0, len(portable), skipped),
            "environment": pin,
            "mismatches": [],
            "portable": len(portable),
            "skipped": skipped,
        }
    for (args, expected), line in zip(portable, lines, strict=True):
        if int(line) != expected:
            mismatches.append({"args": list(args), "expected": expected, "got": int(line)})
    return {
        "disposition": emission_disposition(True, True, len(mismatches), len(portable), skipped),
        "environment": pin,
        "mismatches": mismatches,
        "portable": len(portable),
        "skipped": skipped,
    }
