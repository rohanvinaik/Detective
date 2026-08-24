"""B3 — the captured-instance differential closes the CROSS-FIELD-INVARIANT domain object (#67).

B2 (`test_domain_object_differential_b2_intent`) varies a from-SCRATCH synthesized dataclass. That fails
for an object whose fields are COUPLED by an invariant the code enforces: a `Rel` whose `args` must all
be declared (`x in KNOWN`). `_synth_value` builds `Rel(tag=1, args=[1])`, the invariant rejects it, the
function RAISES, and no witness is found — the synth cannot even reach the body. Worse, an `else`-branch
scalar (`render(-1) == 0`) makes the target look `expressible`, so the pool-poverty rescue that would
harvest the real object is skipped, and the residual is mislabeled "supply an --input" for an object no
--input can express.

B3 supplies the missing negative-entropy signal that was there all along: the covering tests BUILT a
VALID instance (they satisfy the invariant by construction), and the function itself is the invariant
oracle. `_captured_domain_variant_inputs` harvests those real instances and varies ONE field each
(`distinct_field_value`) — the invariant is preserved by LOCALITY (the other fields are the test's own
valid values), so a fixed-point mutant behind the invariant (`r.tag**2`, which every exponent mutation
agrees on at the sample `tag=1`) becomes a KILL rendered as a constructor `Rel(tag=2, args=['a'])`. A
variant that DOES break the invariant makes the original raise and is dropped — positive-only, never a
false COMPLETE. What stays a fixture hand-back after B3 is the genuinely representation-bound core: a
NON-introspectable object (no `dataclasses.fields`, so no field to vary and no constructor `repr`).

These tests are GENERAL — a synthetic `Rel`/KNOWN invariant, not idiomatic to `serialize_rule`.
"""

from __future__ import annotations

import dataclasses

import Detective.engine as engine
from Detective.engine import _captured_domain_variant_inputs, classify_survivors
from Detective.equivalence import SourceExpr


@dataclasses.dataclass
class _Rel:
    tag: int
    args: list


# ── _captured_domain_variant_inputs: vary a captured VALID instance one field at a time ──────────────
def test_captured_domain_variant_inputs_varies_a_captured_dataclass_instance():
    # A captured valid base — the tests' own instance. B3 varies one field per candidate (and keeps the
    # base), each carried as a constructor SourceExpr so the kill renders.
    rows = _captured_domain_variant_inputs([(_Rel(tag=1, args=["a"]),)])
    values = [row[0].value for row in rows]
    assert _Rel(tag=1, args=["a"]) in values  # the base captured instance is included…
    assert _Rel(tag=2, args=["a"]) in values  # …plus tag varied (distinct_field_value(1) == 2)…
    assert _Rel(tag=1, args=[]) in values  # …plus args varied (distinct_field_value(["a"]) == [])
    assert all(isinstance(row[0], SourceExpr) for row in rows)  # every variant renders as a constructor


def test_captured_domain_variant_inputs_is_empty_without_a_dataclass_instance():
    # A non-introspectable / scalar captured value has no field to vary and no constructor to render —
    # the honest limit, an empty pool (that residual stays a fixture hand-back).
    assert _captured_domain_variant_inputs([(1,), ("a", 2)]) == []


def test_captured_domain_variant_inputs_varies_only_the_dataclass_slot():
    # A multi-arg call: only the dataclass slot is varied; the other positional args are held at their
    # captured values (so a variant is still a valid call).
    rows = _captured_domain_variant_inputs([(_Rel(tag=1, args=["a"]), 7)])
    assert rows, "expected variants for the dataclass slot"
    assert all(row[1] == 7 for row in rows)  # the second arg is never perturbed
    assert any(row[0].value == _Rel(tag=2, args=["a"]) for row in rows)


# ── end-to-end: B3 kills a cross-field-invariant survivor B2's synth cannot reach ────────────────────
_REL = (
    "from dataclasses import dataclass\n\n"
    "KNOWN = {'a', 'b', 'c', 'd'}\n\n\n"
    "@dataclass\n"
    "class Rel:\n"
    "    tag: int\n"
    "    args: list\n\n\n"
    "def render(r):\n"
    "    if isinstance(r, Rel):\n"
    "        if not all(x in KNOWN for x in r.args):\n"
    "            raise ValueError('undeclared')\n"
    "        return r.tag**2\n"
    "    return 0\n"
)


def _write_rel(tmp_path) -> str:
    (tmp_path / "rel.py").write_text(_REL)
    tdir = tmp_path / "tests"
    tdir.mkdir()
    # A VALID instance at the fixed point tag=1 (1**n == 1), args declared — never distinguishes an
    # exponent mutation, and its from-scratch synth (args=[1]) would violate the KNOWN invariant.
    (tdir / "test_rel.py").write_text(
        "from rel import Rel, render\n\n\n"
        "def test_render():\n    assert render(Rel(tag=1, args=['a'])) == 1\n"
    )
    return str(tmp_path)


def _invariant_exponent_killed(rep) -> bool:
    # A survivor killed with a witness that renders as a VALID varied Rel constructor (tag != 1).
    for v in rep.verdicts:
        if v.killable and v.witness is not None:
            (arg,) = v.witness.args
            if repr(arg).startswith("Rel(tag=2"):
                return True
    return False


def test_b3_kills_a_cross_field_invariant_survivor(tmp_path):
    # The exponent mutants sit behind BOTH the isinstance guard AND the KNOWN invariant; a synth Rel is
    # invalid (raises), so B2 cannot reach them. B3 varies the tests' VALID captured Rel(tag=1, args=['a'])
    # to Rel(tag=2, args=['a']) — invariant intact, 2**2 != 2**3 — a real KILL, rendered as a constructor.
    rep = classify_survivors("rel.py", "render", _write_rel(tmp_path), deadline_s=None)
    assert _invariant_exponent_killed(rep), "B3 should kill the invariant-guarded exponent survivor"


def test_b2_synth_alone_cannot_reach_the_invariant_object(tmp_path, monkeypatch):
    # Isolate B3 from B2: disable ONLY the captured-instance stage (leave B2's from-scratch synth on).
    # B2's synth builds an invariant-violating Rel that raises, so the exponent survivor persists —
    # proving it is B3, not B2, that reaches a cross-field-invariant object.
    monkeypatch.setattr(engine, "_captured_domain_variant_inputs", lambda *a, **k: [])
    rep = classify_survivors("rel.py", "render", _write_rel(tmp_path), deadline_s=None)
    assert not _invariant_exponent_killed(rep), (
        "without B3 the invariant-guarded exponent survivor must remain"
    )
