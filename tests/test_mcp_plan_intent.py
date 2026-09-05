"""Intent tests for the MCP surface of the style layer (DETERMINISTIC_SICP §14.6 / §14.9, slice 8):
`plan` as a tool and `flag(style=True)` as the driver's recorded answer, both STATIC — driven through
the REAL server (`build_server()` + FastMCP's `call_tool`), never by calling the renderers alone.

What the surface is FOR, stated from intent:

- if the driver can be a model, the model must be able to RECEIVE escalations: the AMBIGUOUS queue is
  a typed channel (YOURS), rendered as a decision to record, never as a task to grind;
- one closing line per response, chosen by ONE pinned decision (`plan.plan_closing`): the first funded
  gate · else the first region the ordering law says to converge · else YOURS · else DONE;
- the same next move per region on both surfaces (`plan.next_move`), each surface spelling its own
  syntax — and a gate this surface lacks (the receipt → verify-rewrite bracket) is handed to the user
  as a terminal command, never paraphrased into a tool that does not exist;
- `plan` and `flag(style=True)` open NO live session (the behaviour layer's `_rendered` is never
  entered), and the style ledger is a different file from the equivalence ledger;
- the CLI and the MCP tool resolve a plan target through ONE resolver (`plan.resolve_plan`) and record
  a style judgment through ONE actuator (`judgments.record_style_judgment`), so they cannot drift.

The pure decisions are pinned by hand truth tables under the in-repo exemption request (§14.9: the
converge witness-pass widen grinds on this tree). The server tests need the `mcp` extra and skip
without it; the renderers and decisions do not.
"""

from __future__ import annotations

import ast
import asyncio
import json
import textwrap
from pathlib import Path

import pytest

import Detective.mcp_server as mcp_server
from Detective import pins
from Detective.certificates import record_certificate
from Detective.judgments import record_style_judgment
from Detective.mcp_server import _CLI_REPORT_HEADER, _plan_call, _render_plan, build_server
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


_CLOSINGS = ("DO THIS:", "STOP.", "DONE:", "YOURS:")


def _closing_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith(_CLOSINGS)]


def _no_session(*_args, **_kwargs):
    raise AssertionError("the style layer must never open a live session")


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


def test_plan_call_spells_this_surfaces_syntax_or_hands_the_terminal_bracket_over() -> None:
    region = "pkg/m.py::f"
    assert (
        _plan_call(DECOMPOSE_APPLY, region, "/abs")
        == "decompose(file='pkg/m.py', function='f', project_root='/abs', apply=True)"
    )
    assert (
        _plan_call(CONVERGE, region, "/abs") == "converge(file='pkg/m.py', function='f', project_root='/abs')"
    )
    judge = _plan_call(JUDGE, region, "/abs")
    assert judge.startswith("flag(file='pkg/m.py', function='f', project_root='/abs', style=True, leave=True")
    assert "proceed=True" in judge
    bracket = _plan_call(RECEIPT_BRACKET, region, "/abs", move="extract")
    assert "TERMINAL" in bracket
    assert "detective receipt 'pkg/m.py::f' -o .detective/receipts/" in bracket
    assert "detective verify-rewrite .detective/receipts/" in bracket and "'extract'" in bracket
    # Never a tool that does not exist on this surface.
    assert "receipt(" not in bracket and "verify_rewrite(" not in bracket and "verify-rewrite(" not in bracket
    assert "detective audit 'pkg/m.py::f' --plan" in _plan_call(AUDIT_PLAN, region, "/abs")
    assert _plan_call("", region, "/abs") == ""


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


# ---------------------------------------------------------------- _render_plan: one closing, chosen


def test_render_plan_closes_on_converge_first_when_a_constructive_region_is_unpinned(tmp_path) -> None:
    root = _repo(tmp_path)
    text = _render_plan(resolve_plan(str(root / "pkg"), str(root)).assembly, str(root))
    closings = _closing_lines(text)
    assert len(closings) == 1
    assert closings[0].startswith("DO THIS: converge(file='pkg/smelly.py', function='dedupe_many'")
    # The closing is LAST: everything after it is its own indented explanation, nothing else.
    lines = text.splitlines()
    assert all(line == "" or line.startswith("  ") for line in lines[lines.index(closings[0]) + 1 :])
    assert text.startswith(
        "pkg — plan · 3 region(s) · 1 constructive · 1 ambiguous · 0 destructive · 1 silent"
    )
    assert "residual — every exclusion named:" in text
    assert "unpinned 1" in text and "escalated 1" in text and "silent 1" in text
    assert "  yours: 1 AMBIGUOUS" in text and "pkg/scan.py::dedupe" in text  # the typed channel, in the body
    assert "unexamined:" in text and "advisory" in text and "Style AFTER behaviour" in text
    assert "%" not in text and "score" not in text.lower()


def test_render_plan_closes_on_the_funded_gate_handed_over_as_a_terminal_bracket(tmp_path) -> None:
    root = _repo(tmp_path)
    node = ast.parse(_SMELLY).body[0]
    record_certificate(str(root), "pkg/smelly.py::dedupe_many", pins.function_digest(node), "complete", "")
    text = _render_plan(resolve_plan(str(root / "pkg"), str(root)).assembly, str(root))
    closings = _closing_lines(text)
    assert len(closings) == 1 and closings[0].startswith("DO THIS: hand the user this bracket")
    assert "detective receipt 'pkg/smelly.py::dedupe_many' -o .detective/receipts/" in text
    assert "detective verify-rewrite .detective/receipts/" in text
    assert "funded 1 ·" in text and "gate: hand the user" in text
    assert "Funded is not applied" in text


def test_render_plan_hands_an_ambiguous_only_scope_to_the_driver_as_yours(tmp_path) -> None:
    root = _repo(tmp_path)
    text = _render_plan(resolve_plan("pkg/scan.py::dedupe", str(root)).assembly, str(root))
    closings = _closing_lines(text)
    assert len(closings) == 1 and closings[0].startswith("YOURS: 1 AMBIGUOUS region(s)")
    assert f"flag(file='pkg/scan.py', function='dedupe', project_root={str(root)!r}, style=True" in text
    assert "leave=True" in text and "proceed=True" in text
    assert "DO THIS" not in text  # a judgment is never rendered as a task


def test_render_plan_is_done_on_a_clean_silent_scope(tmp_path) -> None:
    root = _repo(tmp_path)
    text = _render_plan(resolve_plan("pkg/quiet.py::describe", str(root)).assembly, str(root))
    closings = _closing_lines(text)
    assert len(closings) == 1 and closings[0].startswith("DONE: nothing funded")
    assert "clean 1 · unread 0" in text and "neither is approval" in text


def test_render_plan_converge_first_outranks_yours_and_includes_an_answered_proceed(tmp_path) -> None:
    root = _repo(tmp_path)
    rec = record_style_judgment(str(root), "pkg/scan.py", "dedupe", False, False, True, "go")
    assert rec.refusal == "" and rec.disposition == "proceed"
    text = _render_plan(resolve_plan(str(root / "pkg"), str(root)).assembly, str(root))
    # PROCEED answered the ambiguity; behaviour still comes first — the region now WAITS beside smelly.
    assert "converge first: 2 region(s)" in text and "pkg/scan.py::dedupe" in text
    assert "  yours:" not in text
    assert _closing_lines(text)[0].startswith("DO THIS: converge(")


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


# ---------------------------------------------------------------- through the real server


@pytest.fixture
def server():
    pytest.importorskip("mcp")
    return build_server()


def _call(server, name: str, **arguments) -> str:
    result = asyncio.run(server.call_tool(name, arguments))
    if isinstance(result, tuple):
        result = result[0]
    if isinstance(result, dict):
        return json.dumps(result)
    return "\n".join(getattr(block, "text", "") for block in result)


def test_the_tools_are_registered_with_the_style_parameters(server) -> None:
    tools = {t.name: t for t in asyncio.run(server.list_tools())}
    assert "plan" in tools
    assert "project_root" in tools["plan"].inputSchema["required"]
    assert (
        "AFTER behaviour" in tools["plan"].description
        and "Funded is NOT applied" in tools["plan"].description
    )
    flag = tools["flag"]
    assert {"style", "leave", "proceed", "why", "mutant_id"} <= set(flag.inputSchema["properties"])
    assert "mutant_id" not in flag.inputSchema.get("required", [])
    assert "project_root" in flag.inputSchema["required"]
    assert "TWO LEDGERS" in flag.description


def test_plan_tool_end_to_end_is_static_and_writes_only_the_report(server, tmp_path, monkeypatch) -> None:
    root = _repo(tmp_path)
    monkeypatch.setattr(mcp_server, "_rendered", _no_session)
    text = _call(server, "plan", target=str(root / "pkg"), project_root=str(root))
    assert text.startswith("pkg — plan · 3 region(s)")
    assert len(_closing_lines(text)) == 1
    assert (
        f"DO THIS: converge(file='pkg/smelly.py', function='dedupe_many', project_root={str(root)!r})" in text
    )
    assert (root / ".detective" / "reports" / "plan_pkg.txt").exists()
    assert "full report:" in text
    assert not (root / ".detective" / "judgments.json").exists()
    assert not (root / ".detective" / "equivalents.json").exists()


def test_plan_tool_full_relays_the_archive_under_the_header(server, tmp_path) -> None:
    root = _repo(tmp_path)
    text = _call(server, "plan", target=str(root / "pkg"), project_root=str(root), full=True)
    assert text.startswith(_CLI_REPORT_HEADER)
    assert "pkg/quiet.py::describe" in text and "pkg/smelly.py::dedupe_many" in text


def test_plan_tool_refusals_are_stops_that_read_nothing(server, tmp_path) -> None:
    root = _repo(tmp_path)
    missing = _call(server, "plan", target="pkg/scan.py::nope", project_root=str(root))
    assert "STOP. no function 'nope' in pkg/scan.py — regions in that file: dedupe" in missing
    (root / "empty").mkdir()
    empty = _call(server, "plan", target=str(root / "empty"), project_root=str(root))
    assert "STOP. nothing to read under" in empty and "unmeasured, not clean" in empty
    malformed = _call(server, "plan", target="pkg/scan.py::", project_root=str(root))
    assert "STOP. target must be a path, or 'file.py::function'" in malformed
    for text in (missing, empty, malformed):
        assert len(_closing_lines(text)) == 1 and "DO THIS" not in text
    assert not (root / ".detective" / "reports").exists()


def test_plan_tool_refuses_a_colliding_regime_in_its_own_words(server, tmp_path) -> None:
    root = _repo(tmp_path)
    (root / "conftest.py").write_text("", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "conftest.py").write_text("", encoding="utf-8")
    text = _call(server, "plan", target="pkg/scan.py::dedupe", project_root=str(root))
    assert "STOP. The testing regime says no verdict about this file can be trusted" in text
    assert "conftest" in text


def test_flag_style_tool_records_leave_in_its_own_ledger_and_plan_honours_it(
    server, tmp_path, monkeypatch
) -> None:
    root = _repo(tmp_path)
    monkeypatch.setattr(mcp_server, "_rendered", _no_session)
    text = _call(
        server,
        "flag",
        file="pkg/scan.py",
        function="dedupe",
        project_root=str(root),
        style=True,
        leave=True,
        why="fine as it is",
    )
    assert "recorded: style judgment — leave (fine as it is)" in text
    assert _closing_lines(text) == [
        "DONE: plan excludes this region by your decision (judged_leave) until the code or its"
    ]
    assert f"Next: plan(target='pkg/scan.py::dedupe', project_root={str(root)!r})" in text
    assert (root / ".detective" / "judgments.json").exists()
    assert not (root / ".detective" / "equivalents.json").exists()  # a different ledger
    plan_text = _call(server, "plan", target=str(root / "pkg"), project_root=str(root))
    assert "judged_leave 1" in plan_text and "  yours:" not in plan_text


def test_flag_style_tool_proceed_then_the_ordering_law_then_funded(server, tmp_path) -> None:
    root = _repo(tmp_path)
    text = _call(
        server,
        "flag",
        file="pkg/scan.py",
        function="dedupe",
        project_root=str(root),
        style=True,
        proceed=True,
    )
    assert "recorded: style judgment — proceed" in text and "behaviour first" in text
    plan_text = _call(server, "plan", target="pkg/scan.py::dedupe", project_root=str(root))
    # PROCEED answered the ambiguity; behaviour still comes first.
    assert (
        f"DO THIS: converge(file='pkg/scan.py', function='dedupe', project_root={str(root)!r})" in plan_text
    )
    node = ast.parse(_SCAN).body[0]
    record_certificate(str(root), "pkg/scan.py::dedupe", pins.function_digest(node), "complete", "")
    funded_text = _call(server, "plan", target="pkg/scan.py::dedupe", project_root=str(root))
    assert "funded 1 ·" in funded_text and "quadratic_membership_scan" in funded_text
    assert _closing_lines(funded_text)[0].startswith("DO THIS: hand the user this bracket")


@pytest.mark.parametrize(
    "kwargs, marker",
    [
        (dict(style=True), "needs exactly one of leave=True / proceed=True"),
        (dict(style=True, leave=True, proceed=True), "a judgment is ONE answer"),
        (dict(style=True, leave=True, mutant_id="SOME_ID"), "judges a REGION, not a mutant"),
        (dict(), "or style=True to judge the REGION's form"),
    ],
)
def test_malformed_flag_calls_are_stops_that_record_nothing_and_open_no_session(
    server, tmp_path, monkeypatch, kwargs, marker
) -> None:
    root = _repo(tmp_path)
    monkeypatch.setattr(mcp_server, "_rendered", _no_session)
    text = _call(server, "flag", file="pkg/scan.py", function="dedupe", project_root=str(root), **kwargs)
    assert len(_closing_lines(text)) == 1 and _closing_lines(text)[0].startswith("STOP.")
    assert marker in text and "Nothing was recorded" in text
    assert not (root / ".detective" / "judgments.json").exists()


def test_flag_style_tool_on_a_missing_function_names_the_files_regions(server, tmp_path) -> None:
    root = _repo(tmp_path)
    text = _call(
        server, "flag", file="pkg/scan.py", function="nope", project_root=str(root), style=True, leave=True
    )
    assert "STOP. No function 'nope' in pkg/scan.py — regions in that file: dedupe" in text
    assert not (root / ".detective" / "judgments.json").exists()


def test_the_report_header_names_the_two_terminal_only_commands() -> None:
    assert "detective receipt" in _CLI_REPORT_HEADER and "detective verify-rewrite" in _CLI_REPORT_HEADER
    assert "plan(target=" in _CLI_REPORT_HEADER and "style=True" in _CLI_REPORT_HEADER
