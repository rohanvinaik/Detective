"""Intent tests for the plan assembly (DETERMINISTIC_SICP §14.3, slice 3).

What the code is FOR, stated from intent:

- ONE traversal: the plan reads the same regions the parsimony map reads (`module_functions`),
  so the two surfaces cannot disagree about what a region is; nested functions are not regions;
  the map's class grouping survives the refactor;
- "clean" is DEFINED: SILENT with every lens measured; a SILENT region with an unmeasured lens is
  `unread`, never clean (§14.2 demand 1);
- the static DOF proxy prices a region or says it cannot (`None`), and an unpriceable region is
  excluded as "unpriced" — never funded on a guess (§14.2 demand 2);
- the lens order is the attribution priority, regime absent by construction, overload read off
  the static proxy and SAYING so;
- END TO END over a real tree: a smelly, template-matching region is excluded `unpinned` until a
  complete certificate exists for its current definition, and funded after (the ordering law
  through the assembly); a single-lens smell escalates; every exclusion is named.
"""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path

import pytest

from Detective import pins
from Detective.certificates import record_certificate
from Detective.controller import (
    AMBIGUOUS,
    CONSTRUCTIVE,
    COST_STATIC_DOF_PROXY,
    COST_UNMEASURED,
    DESTRUCTIVE,
    SILENT,
    RegionRead,
    plan_moves,
)
from Detective.parsimony import _LENS_PRIORITY
from Detective.parsimony_map import module_functions, score_path
from Detective.plan import (
    CLEAN,
    NOT_CLEAN,
    UNREAD,
    assemble_plan,
    clean_disposition,
    overload_lens_static,
    region_lenses,
    static_dof_proxy,
)

# ---------------------------------------------------------------- clean_disposition (pure)


@pytest.mark.parametrize(
    "verdict, measured, expected",
    [
        (SILENT, True, CLEAN),
        (SILENT, False, UNREAD),
        (CONSTRUCTIVE, True, NOT_CLEAN),
        (CONSTRUCTIVE, False, NOT_CLEAN),
        (AMBIGUOUS, True, NOT_CLEAN),
        (DESTRUCTIVE, True, NOT_CLEAN),
        ("WEIRD", True, NOT_CLEAN),  # an unknown verdict is never clean by fall-through
    ],
)
def test_clean_disposition(verdict, measured, expected) -> None:
    assert clean_disposition(verdict, measured) == expected


# ---------------------------------------------------------------- the shared traversal

_MODULE = textwrap.dedent(
    """
    def top(a):
        def nested(b):
            return b
        return nested(a)

    class C:
        def m1(self):
            return 1

        async def m2(self):
            return 2

    async def tail():
        return 3
    """
)


def test_module_functions_yields_regions_in_source_order_and_skips_nested() -> None:
    got = [(k, m, c) for k, _n, m, c in module_functions(ast.parse(_MODULE), "pkg/mod.py")]
    assert got == [
        ("pkg/mod.py::top", False, None),
        ("pkg/mod.py::C.m1", True, "pkg/mod.py::C"),
        ("pkg/mod.py::C.m2", True, "pkg/mod.py::C"),
        ("pkg/mod.py::tail", False, None),
    ]


def test_score_path_still_groups_methods_under_their_class(tmp_path) -> None:
    (tmp_path / "mod.py").write_text(_MODULE, encoding="utf-8")
    score = score_path(str(tmp_path), str(tmp_path))
    (module,) = score.children
    assert module.functions == 4
    (cls,) = module.children
    assert cls.kind == "class" and cls.name == "mod.py::C"
    assert [r.qualname for r in cls.reads] == ["mod.py::C.m1", "mod.py::C.m2"]
    assert [r.qualname for r in module.reads][:1] == ["mod.py::top"]


# ---------------------------------------------------------------- the price and the banks


def _fn(src: str) -> ast.FunctionDef:
    node = ast.parse(textwrap.dedent(src)).body[0]
    assert isinstance(node, ast.FunctionDef)
    return node


def test_static_dof_proxy_prices_a_function_and_declines_garbage() -> None:
    assert (static_dof_proxy(_fn("def f(a, b):\n    return a + b\n"), False) or 0) > 0
    assert static_dof_proxy(ast.parse("x = 1").body[0], False) is None  # type: ignore[arg-type]


def test_unpriceable_overload_abstains_and_is_unmeasured() -> None:
    lens = overload_lens_static(None, 3)
    assert lens.vote == 0 and lens.measured is False
    priced = overload_lens_static(30, 3)
    assert priced.measured and "static proxy" in priced.detail and priced.zero_state is not None


def test_region_lenses_follow_priority_without_regime() -> None:
    node = _fn("def f(a):\n    return a\n")
    names = [lens.name for lens in region_lenses(node, False, 4)]
    assert names == [n for n in _LENS_PRIORITY if n != "regime"]
    assert names[0] == "overload" and names[-1] == "purity"


# ---------------------------------------------------------------- the plan, end to end

_SMELLY = textwrap.dedent(
    """
    def dedupe_many(xs, a, b, c, d, e):
        out = []
        for x in xs:
            if x not in out:
                if a:
                    if b:
                        if c:
                            if d:
                                if e:
                                    out.append(x)
        return out
    """
)
# Exactly ONE smell (interface width). A one-line body would also trip overload — 6 DOF over 2
# lines reads 3.0 DOF/line on the static proxy — so the body carries enough plain lines to keep
# the density inside the band. Measured while writing this fixture, not assumed.
_WIDE = textwrap.dedent(
    '''
    def wide(a, b, c, d, e):
        """Five parameters, nothing else."""
        values = [a, b, c, d, e]
        first = values[0]
        return first
    '''
)
_QUIET = textwrap.dedent(
    '''
    def describe(x):
        """A label for x."""
        name = str(x)
        return name
    '''
)


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "smelly.py").write_text(_SMELLY, encoding="utf-8")
    (tmp_path / "wide.py").write_text(_WIDE, encoding="utf-8")
    (tmp_path / "quiet.py").write_text(_QUIET, encoding="utf-8")
    return tmp_path


def _by_region(assembly):
    return {d.read.region: d for d in assembly.regions}


def test_assembly_reads_every_region_once_with_named_verdicts(tmp_path) -> None:
    assembly = assemble_plan(str(_repo(tmp_path)), str(tmp_path))
    details = _by_region(assembly)
    assert set(details) == {"smelly.py::dedupe_many", "wide.py::wide", "quiet.py::describe"}
    smelly = details["smelly.py::dedupe_many"].read
    assert smelly.verdict == CONSTRUCTIVE and smelly.agreement >= 2
    assert smelly.template == "quadratic_membership_scan" and smelly.gate_exists
    assert details["smelly.py::dedupe_many"].gate  # the grammar names the gate
    assert "line" in details["smelly.py::dedupe_many"].template_evidence
    assert smelly.cost_provenance == COST_STATIC_DOF_PROXY and smelly.cost > 0
    assert details["wide.py::wide"].read.verdict == AMBIGUOUS  # one lens: necessary, never sufficient
    assert assembly.fences_note  # the 0 is stated, never implied


def test_the_ordering_law_through_the_assembly(tmp_path) -> None:
    root = _repo(tmp_path)
    before = assemble_plan(str(root), str(root))
    assert before.plan.funded == ()
    excluded = dict(before.plan.excluded)
    assert excluded["smelly.py::dedupe_many"] == "unpinned"  # constructive, recognized, gated — and unproven
    assert excluded["wide.py::wide"] == "escalated"

    node = ast.parse(_SMELLY).body[0]
    record_certificate(str(root), "smelly.py::dedupe_many", pins.function_digest(node), "complete", "")
    after = assemble_plan(str(root), str(root))
    assert [r.region for r in after.plan.funded] == ["smelly.py::dedupe_many"]
    assert _by_region(after)["smelly.py::dedupe_many"].read.status == pins.PINNED


def test_a_stale_certificate_does_not_fund(tmp_path) -> None:
    root = _repo(tmp_path)
    record_certificate(str(root), "smelly.py::dedupe_many", "not-the-current-digest", "complete", "")
    assembly = assemble_plan(str(root), str(root))
    assert dict(assembly.plan.excluded)["smelly.py::dedupe_many"] == "pinned_stale"


def test_clean_is_defined_not_assumed(tmp_path) -> None:
    assembly = assemble_plan(str(_repo(tmp_path)), str(tmp_path))
    quiet = _by_region(assembly)["quiet.py::describe"]
    assert quiet.read.verdict == SILENT
    assert quiet.clean == CLEAN
    assert all(lens.measured for lens in quiet.lenses)
    assert _by_region(assembly)["smelly.py::dedupe_many"].clean == NOT_CLEAN


def test_scope_name_is_root_relative(tmp_path) -> None:
    root = _repo(tmp_path)
    assert assemble_plan(str(root), str(root)).scope == root.name
    assert assemble_plan(str(root / "quiet.py"), str(root)).scope == "quiet.py"


# ---------------------------------------------------------------- unpriced is never funded


def test_an_unpriced_admissible_region_is_excluded_as_unpriced() -> None:
    priced = RegionRead("a", CONSTRUCTIVE, 2, "t", True, 1.0, pins.PINNED, COST_STATIC_DOF_PROXY)
    unpriced = RegionRead("b", CONSTRUCTIVE, 2, "t", True, 0.0, pins.PINNED, COST_UNMEASURED)
    plan = plan_moves((priced, unpriced), budget=10.0)
    assert [r.region for r in plan.funded] == ["a"]
    assert ("b", "unpriced") in plan.excluded
