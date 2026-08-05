"""Generated properties, remembered across runs — the accumulator that outlives one converge.

``converge`` accumulates sound properties across its passes "so a later pass cannot overwrite
an earlier pass's killers" (converge.py). That invariant is right and its scope was one run too
short: ``accumulated`` starts EMPTY on every invocation, and the suite file is then re-rendered
wholesale from whatever this run's search happened to reach. Everything the last run pinned and
this one did not re-derive is destroyed before it is ever measured.

Two failures, one cause:

* A target alternates forever. Round A writes the tests for one raise-path, round B overwrites
  them with another's, and each round reports itself Incomplete on the lines the other just
  covered. Following the tool's own instruction never converges, because the instruction is
  answered and then thrown away.
* Re-converging a function silently deletes pins. Observed on Detective's own suite: a run
  rewrote a 5-test file with 1 test and dropped that function from 185/406 killed to 134/406.
  ``✓ wrote 1 test(s)`` reads as "added one", not "replaced five with one".

So the properties are remembered here, and ``accumulated`` is seeded from them.

REGENERATABLE, NOT AUTHORED. Unlike ``inputs.json`` / ``equivalents.json`` — judgments no re-run
can reproduce, which ``purge`` must never touch — this is analysis output, and ``purge`` should
delete it. Losing it costs a cold run, never a decision.

TWO GATES, because one is not enough. The store is keyed by the function's AST, so editing the
target abandons its pins rather than re-asserting stale expectations against new code. That
misses a change OUTSIDE the function that changes its answer (a module-level constant), so every
pin is additionally re-checked with ``property_holds`` on load and dropped if it no longer holds.
The digest is the cheap gate; execution is the correct one.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover — import cycle at runtime, types only
    from .synthesis.oracle_light import ExecutableProperty

_REL_PATH = os.path.join(".detective", "pins.json")

# The fields ``render_module`` and its helpers actually read. ``inputs`` is deliberately absent:
# it is generation scaffolding the renderer never touches, and it holds arbitrary values that do
# not survive JSON. A pin is the TEST, not the search that found it.
_FIELDS = (
    "category",
    "setup_code",
    "assertion_code",
    "preconditions",
    "confidence",
    "source_lenses",
    "needs_oracle",
    "function_key",
    "mutant_id",
    "golden_case",
)


def function_digest(node: ast.AST) -> str:
    """Content identity of the target function, matching ``verdict_cache``'s construction.

    ``ast.dump`` and not the raw text, so reformatting or a comment edit keeps the pins while
    any change to what the function DOES abandons them.
    """
    return hashlib.sha256(ast.dump(node).encode("utf-8")).hexdigest()[:16]


def _entry_key(func_key: str, digest: str) -> str:
    return f"{func_key}::{digest}"


def _store_path(project_root: str) -> str:
    return os.path.join(project_root, _REL_PATH)


def _read(project_root: str) -> dict:
    try:
        with open(_store_path(project_root), encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def load(project_root: str, func_key: str, digest: str, verify=None) -> list[ExecutableProperty]:
    """Pins for this exact function body, each re-checked before it is handed back.

    ``verify`` is ``property_holds``-shaped ``(setup_code, assertion_code, root) -> bool``;
    injected rather than imported to keep this module free of the converge cycle. Passing
    ``None`` skips execution and trusts the digest alone — for callers that only want to know
    what is stored, never for seeding a run.

    Empty on anything unreadable or malformed. A missing memory is simply no memory.
    """
    from .synthesis.oracle_light import ExecutableProperty

    stored = _read(project_root).get(_entry_key(func_key, digest))
    if not isinstance(stored, list):
        return []
    out: list[ExecutableProperty] = []
    for item in stored:
        if not isinstance(item, dict):
            continue
        try:
            prop = ExecutableProperty(inputs={}, **{k: item[k] for k in _FIELDS if k in item})
        except (TypeError, ValueError, KeyError):
            continue  # a malformed entry is skipped, never fatal
        if prop.golden_case is not None:
            # JSON has no tuples; the renderer unpacks this as exactly the (args, expected)
            # pair, so a stored value of any other shape is malformed, not coercible.
            pair = list(prop.golden_case)
            if len(pair) != 2:
                continue
            prop.golden_case = (str(pair[0]), str(pair[1]))
        if verify is not None and not verify(prop.setup_code, prop.assertion_code, project_root):
            continue  # the code around it moved; a pin that no longer holds is not a pin
        out.append(prop)
    return out


def save(project_root: str, func_key: str, digest: str, props: list[ExecutableProperty]) -> None:
    """Remember this run's properties, replacing any older set for the same function body.

    Entries for OTHER digests of the same function are dropped: they describe code that no
    longer exists, and keeping them grows the store without ever being loadable again.
    """
    raw = {
        k: v
        for k, v in _read(project_root).items()
        if not (k.startswith(f"{func_key}::") and k != _entry_key(func_key, digest))
    }
    raw[_entry_key(func_key, digest)] = [
        {f: (list(p.golden_case) if f == "golden_case" and p.golden_case else getattr(p, f)) for f in _FIELDS}
        for p in props
    ]
    path = _store_path(project_root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(raw, fh, indent=2, sort_keys=True)
