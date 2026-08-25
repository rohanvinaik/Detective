"""B2 — the differential domain-object search closes the last #67 door with a SYNTHESIZED fixture (#67).

Grounding the wiring (post-§6) showed the "differential domain-object" gap the paper (§18 Q10) framed as
one research-grade problem is NOT monolithic. Synthesis ALREADY reaches a dataclass parameter
(``_synth_value``/``_synth_from_ann`` build a ``Relation``), and ``_dataclass_field_variants`` already
produces a DIFFERENTIAL grid over it — but only for bool (flipped) and Optional (→None) fields. A
mutation that reads a VALUE-bearing field (str / int / list content) — the ``serialize_rule`` case — is
never distinguished, so its survivor files candidate-equivalent and routes to a hand-built ``fixture``.

B2 closes the tractable half: ``distinct_field_value`` varies a value-bearing field so the mutation
manifests (§6 band-2, the differential ``p_field`` of Def. 11.8(vi)), carried as a ``SourceExpr``
constructor so the kill renders as ``Cls(field=...)`` — never an ``--input`` literal (a constructor is
outside the allowlist), never a flag. It is the generalization of B0 (nested-int topologies) and B1
(scalar guards) to a dataclass field. Positive-only (adopt only a NEW kill), so it can never manufacture
a false COMPLETE. The GENUINELY open residual it does NOT close — a cross-field-invariant object (a blind
field variant builds an invalid instance the function rejects) or a non-introspectable object (no
``dataclasses.fields``) — stays a fixture hand-back, exactly as B0/B1 left their harder frontiers.

These tests are GENERAL (a synthetic ``Cfg`` whose fixed-point sample hides an exponent mutant), not
idiomatic to ``serialize_rule`` — the fix must hold for arbitrary code.
"""

from __future__ import annotations

import dataclasses

import Detective.engine as engine
from Detective.engine import (
    _as_domain_source,
    _domain_constructor_imports,
    _domain_variants,
    classify_survivors,
    distinct_field_value,
    domain_import_disposition,
    domain_variant_retry_gate,
)
from Detective.equivalence import SourceExpr


# ── distinct_field_value: the pinned differential value chooser (isolation ✓ COMPLETE 36/38) ─────────
def test_distinct_field_value_is_bool_before_int():
    # bool is an int subclass; the two mean different fences (a flipped flag vs a boundary step) and
    # must not collapse — a flipped bool, never `True + 1 == 2`.
    assert distinct_field_value(True) is False
    assert distinct_field_value(False) is True


def test_distinct_field_value_varies_every_value_bearing_type_distinctly():
    # The contract is DISTINCTNESS from `current` (the down-payment B0/B1 also make): each returned
    # value differs, of a compatible shape, so a mutation reading the field can manifest.
    assert distinct_field_value(1) == 2
    assert distinct_field_value(1.5) == 2.5
    assert distinct_field_value("x") == "xx"
    assert distinct_field_value("") == "x"  # distinct even from the empty string
    assert distinct_field_value([1, 2]) == [2]  # length-distinct
    assert distinct_field_value([]) == ["x"]  # empty → nonempty
    assert distinct_field_value((1, 2)) == (2,)
    assert distinct_field_value(()) == ("x",)
    for v in (1, 1.5, "x", "", [1, 2], [], (1, 2), ()):
        assert distinct_field_value(v) != v


def test_distinct_field_value_is_none_at_the_honest_limit():
    # A dict / set field, or a None current (the Optional path already covers None), yields no
    # value-only variant — such a residual stays a fixture hand-back, never a fabricated object.
    assert distinct_field_value({}) is None
    assert distinct_field_value({1, 2}) is None
    assert distinct_field_value(None) is None
    assert distinct_field_value(object()) is None


# ── domain_variant_retry_gate: the pinned B2 gate (its own symbol, so B2 is independently disablable) ─
def test_domain_variant_retry_gate_runs_only_when_safe():
    assert domain_variant_retry_gate(True, False, False) == "run"
    assert domain_variant_retry_gate(False, False, False) == "skip"  # nothing to upgrade
    assert domain_variant_retry_gate(True, True, False) == "skip"  # effectful — a variant CALLS the target
    assert domain_variant_retry_gate(True, False, True) == "skip"  # wall gone (#31)


# ── _as_domain_source / _domain_variants: the SourceExpr constructor renderer + differential grid ────
@dataclasses.dataclass
class _Flat:
    name: str
    weight: int


@dataclasses.dataclass
class _Nested:
    child: _Flat


class _Opaque:  # not a dataclass — no fields to vary, no constructor repr (the #68b core)
    pass


@dataclasses.dataclass
class _HasOpaque:
    x: object


@dataclasses.dataclass
class _Rec:  # a self-nesting dataclass, to exceed the depth cap
    child: object = None


@dataclasses.dataclass
class _DupX:
    v: int


@dataclasses.dataclass
class _DupY:
    v: int


# Force an import-name collision: two DISTINCT classes whose repr both emits the bare name `_Dup`
# from different modules — `from mod_x import _Dup` and `from mod_y import _Dup` cannot coexist.
_DupX.__qualname__ = _DupY.__qualname__ = "_Dup"
_DupX.__module__, _DupY.__module__ = "mod_x", "mod_y"


@dataclasses.dataclass
class _Holder:
    a: object
    b: object


def test_as_domain_source_renders_a_flat_dataclass_as_a_constructor_sourceexpr():
    se = _as_domain_source(_Flat(name="a", weight=1))
    assert isinstance(se, SourceExpr)
    assert se.expr == "_Flat(name='a', weight=1)"  # dataclass repr IS its constructor source
    assert se.imports == (f"from {_Flat.__module__} import _Flat",)
    assert se.value == _Flat(name="a", weight=1)  # the LIVE value rides alongside the source


def test_domain_import_disposition_flags_only_a_genuine_name_collision():
    # The pure #68a gate (hand-pinned — converge inflates on engine.py's module-scale test surface,
    # not a property of this function). A NAMED code, never a bool: only two DISTINCT sources binding
    # the same imported name is a collision; identical imports (the same class reached twice) are not.
    assert domain_import_disposition(()) == "ok"
    assert domain_import_disposition(("from a import C",)) == "ok"
    assert domain_import_disposition(("from a import C", "from b import D")) == "ok"  # distinct names
    assert domain_import_disposition(("from a import C", "from a import C")) == "ok"  # identical, dedup
    assert domain_import_disposition(("from a import C", "from b import C")) == "collision"  # ambiguous


def test_as_domain_source_renders_a_nested_dataclass_recursively():
    # #68a: a nested-dataclass field now RENDERS (was the abstention limit). dataclass repr is already
    # recursive and round-trippable, so `expr` is the nested constructor; the fix is unioning EVERY
    # class's import so the generated test resolves both names.
    se = _as_domain_source(_Nested(child=_Flat(name="a", weight=1)))
    assert isinstance(se, SourceExpr)
    assert se.expr == "_Nested(child=_Flat(name='a', weight=1))"
    imported = {imp.rsplit(" import ", 1)[-1] for imp in se.imports}
    assert imported == {"_Nested", "_Flat"}  # BOTH classes, or the render is unresolvable
    assert _domain_constructor_imports(_Nested(child=_Flat(name="a", weight=1))) is not None


def test_as_domain_source_still_abstains_where_the_render_is_genuinely_irreducible():
    # The honest residual (#68b) is preserved: a non-dataclass, a non-introspectable leaf, an
    # import-name collision, and over-deep nesting each stay None — a fixture hand-back, never a
    # fabricated / silently-wrong render.
    assert _as_domain_source(42) is None  # not a dataclass instance
    assert _as_domain_source(_HasOpaque(x=_Opaque())) is None  # non-introspectable leaf (#68b)
    assert _as_domain_source(_Holder(a=_DupX(v=1), b=_DupY(v=2))) is None  # import-name collision
    deep = _Rec()
    for _ in range(8):  # exceed _DOMAIN_NEST_CAP (5)
        deep = _Rec(child=deep)
    assert _as_domain_source(deep) is None


def test_domain_variants_varies_one_value_bearing_field_per_variant():
    variants = _domain_variants(_Flat(name="a", weight=1))
    assert variants is not None
    values = [v.value for v in variants]
    assert _Flat(name="a", weight=1) in values  # the base
    assert _Flat(name="xa", weight=1) in values  # name varied (distinct_field_value("a") == "xa")
    assert _Flat(name="a", weight=2) in values  # weight varied (distinct_field_value(1) == 2)
    assert all(isinstance(v, SourceExpr) for v in variants)  # each renders


# ── end-to-end: B2 turns a fixed-point candidate-equivalent into a KILL with a constructor witness ───
_CFG = (
    "from dataclasses import dataclass\n\n\n"
    "@dataclass\n"
    "class Cfg:\n"
    "    base: int\n\n\n"
    "def power(c: Cfg) -> int:\n"
    "    if isinstance(c, Cfg):\n"
    "        return c.base**2\n"
    "    return 0\n"
)


def _write_cfg(tmp_path) -> str:
    (tmp_path / "cfg.py").write_text(_CFG)
    tdir = tmp_path / "tests"
    tdir.mkdir()
    # A covering test at the FIXED POINT base=1 (1**n == 1), so it never distinguishes an exponent
    # mutation — the exact shape that leaves a value-bearing-field survivor for B2 to close.
    (tdir / "test_cfg.py").write_text(
        "from cfg import Cfg, power\n\n\ndef test_power():\n    assert power(Cfg(base=1)) == 1\n"
    )
    return str(tmp_path)


def _exponent_survivor_killed(rep) -> bool:
    # A VALUE survivor killed with a witness whose sole arg renders as a Cfg constructor (base != 1).
    for v in rep.verdicts:
        if v.category == "VALUE" and v.killable and v.witness is not None:
            (arg,) = v.witness.args
            if repr(arg).startswith("Cfg(base="):
                return True
    return False


def test_b2_kills_a_fixed_point_domain_object_survivor(tmp_path):
    # base=1 hides every exponent VALUE-mutant (1**n == 1); no --input can express a Cfg. B2 synthesizes
    # Cfg(base=2) — where 2**2 != 2**3 — and the mutation is distinguished: a real KILL, rendered as a
    # constructor witness, NOT a flag. This is the differential domain-object gap, closed.
    rep = classify_survivors("cfg.py", "power", _write_cfg(tmp_path), deadline_s=None)
    assert _exponent_survivor_killed(rep), "B2 should kill the fixed-point exponent survivor with Cfg(base=2)"


def test_b2_off_leaves_the_survivor_candidate_equivalent(tmp_path, monkeypatch):
    # Isolate the B2 signal: with its own gate forced to "skip", the exponent VALUE-mutant persists as
    # candidate-equivalent (no --input reaches it, base=1 hides it) — proving B2, not another stage, is
    # what upgrades it. Mirrors the B1 test's guard_retry_gate monkeypatch.
    monkeypatch.setattr(engine, "domain_variant_retry_gate", lambda *a, **k: "skip")
    rep = classify_survivors("cfg.py", "power", _write_cfg(tmp_path), deadline_s=None)
    assert not _exponent_survivor_killed(rep), "without B2 the fixed-point exponent survivor must remain"
    assert any(v.category == "VALUE" and not v.killable and not v.crash_only for v in rep.verdicts), (
        "the exponent mutant should file candidate-equivalent when B2 is off"
    )
