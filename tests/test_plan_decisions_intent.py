"""Intent tests for the plan layer's shared decisions (DETERMINISTIC_SICP §14.6 / §14.9, slice 8).

What the layer is FOR, stated from intent:

- one closing line per response, chosen by ONE pinned decision (`plan.plan_closing`): the first funded
  gate · else the first region the ordering law says to converge · else YOURS · else DONE;
- the same next move per region on every surface (`plan.next_move`), each surface spelling its own
  syntax — the CLI's is `plan.next_command`;
- a plan target resolves through ONE resolver (`plan.resolve_plan`) and a style judgment records
  through ONE actuator (`judgments.record_style_judgment`), so the surfaces cannot drift.

The pure decisions are pinned by hand truth tables under the in-repo exemption request (§14.9: the
converge witness-pass widen grinds on this tree).

Split 2026-09-13 from `test_mcp_plan_intent.py` when the MCP surface was parked: the tests that drove
`_render_plan`, `_plan_call` and the real server moved to `parked/mcp/tests/test_mcp_plan_server.py`.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from Detective import pins
from Detective.judgments import record_style_judgment
from Detective.plan import (
    AUDIT_PLAN,
    CONVERGE,
    DECOMPOSE_APPLY,
    DO_CONVERGE,
    DO_FUNDED,
    DONE,
    FUNDED,
    JUDGE,
    NO_SUCH_FUNCTION,
    NOTHING_TO_READ,
    RECEIPT_BRACKET,
    REGIME_CONFLICT,
    YOURS,
    next_command,
    next_move,
    plan_closing,
    resolve_plan,
)

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
_QUIET = textwrap.dedent(
    '''
    def describe(x):
        """A label for x."""
        name = str(x)
        return name
    '''
)
# Exactly ONE smell (a seam) AND a recognized template: the AMBIGUOUS-with-a-move shape (measured
# while writing the §14.5 fixtures, not assumed).
_SCAN = textwrap.dedent(
    """
    def dedupe(xs):
        out = []
        for x in xs:
            if x not in out:
                out.append(x)
        return out
    """
)


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "smelly.py").write_text(_SMELLY, encoding="utf-8")
    (tmp_path / "pkg" / "quiet.py").write_text(_QUIET, encoding="utf-8")
    (tmp_path / "pkg" / "scan.py").write_text(_SCAN, encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------- next_move (pure) and its two spellings

_MOVE_TABLE = [
    (FUNDED, "decompose 'x' --apply", DECOMPOSE_APPLY),
    (FUNDED, "receipt + verify-rewrite", RECEIPT_BRACKET),
    (FUNDED, "", ""),
    (FUNDED, "something the grammar names and no surface spells", ""),
    (pins.UNPINNED, "", CONVERGE),
    (pins.PINNED_STALE, "receipt", CONVERGE),  # a status reason outranks whatever the gate says
    (pins.PINNED_UNVERIFIED, "", CONVERGE),
    (pins.PINNED_INCOMPLETE, "", CONVERGE),
    (pins.REFUSED, "", CONVERGE),
    ("escalated", "", JUDGE),
    ("unpriced", "", AUDIT_PLAN),
    ("fenced", "decompose", ""),
    ("judged_leave", "receipt", ""),
    ("silent", "", ""),
    ("no_template", "", ""),
    ("no_gate", "", ""),
    ("over_budget", "decompose", ""),
    ("verdict_unknown", "", ""),
    ("status_unknown", "", ""),
    ("", "", ""),
]


@pytest.mark.parametrize("reason, gate, expected", _MOVE_TABLE)
def test_next_move_table(reason, gate, expected) -> None:
    assert next_move(reason, gate) == expected


@pytest.mark.parametrize("reason, gate, expected", _MOVE_TABLE)
def test_next_command_is_the_cli_spelling_of_next_move(reason, gate, expected) -> None:
    spelling = {
        DECOMPOSE_APPLY: "detective decompose 'pkg/m.py::f' --apply",
        RECEIPT_BRACKET: "detective receipt 'pkg/m.py::f' -o ",
        CONVERGE: "detective converge 'pkg/m.py::f'",
        JUDGE: "detective flag 'pkg/m.py::f' --style --leave",
        AUDIT_PLAN: "detective audit 'pkg/m.py::f' --plan",
    }
    cmd = next_command(reason, "pkg/m.py::f", gate, "extract")
    if expected:
        assert cmd.startswith(spelling[expected])
    else:
        assert cmd == ""


# ---------------------------------------------------------------- plan_closing (pure)


@pytest.mark.parametrize("funded", [0, 2])
@pytest.mark.parametrize("waiting", [0, 3])
@pytest.mark.parametrize("escalated", [0, 1])
def test_plan_closing_order_funded_then_converge_then_yours_then_done(funded, waiting, escalated) -> None:
    expected = DO_FUNDED if funded else DO_CONVERGE if waiting else YOURS if escalated else DONE
    assert plan_closing(funded, waiting, escalated) == expected


# ---------------------------------------------------------------- resolve_plan: the shared resolver


def test_resolve_plan_path_form_and_region_form(tmp_path) -> None:
    root = _repo(tmp_path)
    tree = resolve_plan(str(root / "pkg"), str(root))
    assert tree.refusal == "" and tree.assembly is not None
    assert tree.assembly.scope == "pkg" and len(tree.assembly.regions) == 3
    one = resolve_plan("pkg/scan.py::dedupe", str(root))
    assert one.refusal == "" and one.assembly is not None
    assert one.assembly.scope == "pkg/scan.py::dedupe" and len(one.assembly.regions) == 1
    assert (one.file, one.function) == ("pkg/scan.py", "dedupe")


def test_resolve_plan_refusals_are_typed_and_carry_the_detail(tmp_path) -> None:
    root = _repo(tmp_path)
    missing = resolve_plan("pkg/scan.py::nope", str(root))
    assert missing.refusal == NO_SUCH_FUNCTION and missing.assembly is None
    assert "'nope'" in missing.detail and "dedupe" in missing.detail
    (root / "empty").mkdir()
    empty = resolve_plan(str(root / "empty"), str(root))
    assert empty.refusal == NOTHING_TO_READ and empty.assembly is None
    assert "unmeasured, not clean" in empty.detail


def test_resolve_plan_refuses_a_colliding_regime_before_reading_anything(tmp_path) -> None:
    root = _repo(tmp_path)
    (root / "conftest.py").write_text("", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "conftest.py").write_text("", encoding="utf-8")
    res = resolve_plan("pkg/scan.py::dedupe", str(root))
    assert res.refusal == REGIME_CONFLICT and res.assembly is None and res.regime is not None


# ---------------------------------------------------------------- record_style_judgment: the shared actuator


@pytest.mark.parametrize(
    "has_id, leave, proceed, code",
    [
        (True, True, False, "mutant_id_with_style"),
        (False, False, False, "no_disposition"),
        (False, True, True, "both_dispositions"),
    ],
)
def test_record_style_judgment_refuses_the_malformed_shapes_before_touching_disk(
    tmp_path, has_id, leave, proceed, code
) -> None:
    root = _repo(tmp_path)
    rec = record_style_judgment(str(root), "pkg/scan.py", "dedupe", has_id, leave, proceed)
    assert rec.refusal == code and rec.region == ""
    assert not (root / ".detective").exists()


def test_record_style_judgment_names_the_files_regions_on_a_missing_function(tmp_path) -> None:
    root = _repo(tmp_path)
    rec = record_style_judgment(str(root), "pkg/scan.py", "nope", False, True, False)
    assert rec.refusal == NO_SUCH_FUNCTION and rec.regions_in_file == ("dedupe",)
    assert not (root / ".detective" / "judgments.json").exists()
