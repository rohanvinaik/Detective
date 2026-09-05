"""Intent tests for the behavior-status read — the ordering law's one fact per region (§14.1).

DETERMINISTIC_SICP §14.1 (founder ruling 2026-09-05): style after behavior, STRICTLY. A style move
is admissible only on a region whose Detective contract is current and unedited, so the plan needs
a static, decidable answer to "does a current, unedited generated suite exist for this function AS
IT NOW STANDS?" — which the suite artifact could not answer before, because its header recorded the
target's NAME (the func_key) but not its CONTENT identity (`pins.function_digest`).

What this pins from intent, which a generated characterization cannot:

- the header's second line round-trips the function digest through ONE writer
  (`render_module`) and ONE reader (`generated_function_digest`), and leaves both existing readers
  of line 0 — `generated_owner` and the writer's `_HEADER_RE` — untouched;
- the four states are DISTINCT; in particular "no digest recorded" is ``pinned_unverified``, never
  ``pinned`` (a currency it cannot show) and never ``pinned_stale`` (a movement nobody measured) —
  the cannot-determine / determined-false discipline applied to identity;
- the accessor reads the real artifact `_write` produces: a suite written for the current
  definition is ``pinned``; the same suite after the function changes is ``pinned_stale``; after a
  human edit it is ``pinned_stale``; a digest-less suite is ``pinned_unverified``; no file, or a
  file another target owns, is ``unpinned``.
"""

from __future__ import annotations

import ast
import os

import pytest

from Detective import pins
from Detective.certify import (
    _write,
    behavior_status,
    generated_function_digest,
    generated_owner,
    read_behavior_status,
    synth_filename,
)
from Detective.synthesis.oracle_light import ExecutableProperty
from Detective.synthesis.writer import FUNCTION_DIGEST_PREFIX, foreign_generated_test_names, render_module

KEY = "m.py::f"


def _prop() -> ExecutableProperty:
    return ExecutableProperty(
        "VALUE",
        {},
        "from m import f",
        "assert f(1) == 2",
        [],
        0.9,
        golden_case=("(1,)", "2"),
    )


def _node(src: str) -> ast.FunctionDef:
    node = ast.parse(src).body[0]
    assert isinstance(node, ast.FunctionDef)
    return node


# ---------------------------------------------------------------- the pure decision, every row


def _expected(owned: bool, has: bool, matches: bool, edited: bool) -> str:
    # The reference table, written from the docstring's four states — not from the code.
    if not owned:
        return "unpinned"
    if edited:
        return "pinned_stale"
    if not has:
        return "pinned_unverified"
    return "pinned" if matches else "pinned_stale"


@pytest.mark.parametrize("owned", [False, True])
@pytest.mark.parametrize("has", [False, True])
@pytest.mark.parametrize("matches", [False, True])
@pytest.mark.parametrize("edited", [False, True])
def test_behavior_status_truth_table(owned: bool, has: bool, matches: bool, edited: bool) -> None:
    assert behavior_status(owned, has, matches, edited) == _expected(owned, has, matches, edited)


def test_the_four_states_are_all_reachable_and_distinct() -> None:
    states = {
        behavior_status(False, False, False, False),
        behavior_status(True, False, False, False),
        behavior_status(True, True, False, False),
        behavior_status(True, True, True, False),
    }
    assert states == {"unpinned", "pinned_unverified", "pinned_stale", "pinned"}


def test_no_recorded_digest_is_unverified_never_pinned_or_stale() -> None:
    # The load-bearing distinction: absence of a record is not evidence of movement, and not
    # evidence of currency either. `digest_matches` is meaningless without a record and is ignored.
    assert behavior_status(True, False, True, False) == "pinned_unverified"
    assert behavior_status(True, False, False, False) == "pinned_unverified"


def test_a_human_edit_is_stale_regardless_of_digest() -> None:
    assert behavior_status(True, True, True, True) == "pinned_stale"


# ---------------------------------------------------------------- the header: one writer, one reader


def test_digest_line_round_trips_and_leaves_line0_readers_unaffected(tmp_path) -> None:
    digest = pins.function_digest(_node("def f(x):\n    return x + 1\n"))
    src = render_module(KEY, [_prop()], function_digest=digest)
    path = tmp_path / "test_f_synth.py"
    path.write_text(src, encoding="utf-8")

    assert generated_function_digest(str(path)) == digest
    # Line 0 is untouched: both existing readers still see the owner.
    assert generated_owner(str(path)) == KEY
    assert f"{FUNCTION_DIGEST_PREFIX}{digest}." in src
    # `_HEADER_RE` (the writer's own reader of line 0) still matches: from another target's point
    # of view this file is FOREIGN, so its test names are reported.
    assert foreign_generated_test_names(str(tmp_path), "other.py::g")


def test_without_a_digest_the_header_is_byte_identical_and_reads_empty(tmp_path) -> None:
    plain = render_module(KEY, [_prop()])
    assert render_module(KEY, [_prop()], function_digest=None) == plain
    assert FUNCTION_DIGEST_PREFIX not in plain
    path = tmp_path / "test_f_synth.py"
    path.write_text(plain, encoding="utf-8")
    assert generated_function_digest(str(path)) == ""


def test_unreadable_or_headerless_records_no_digest(tmp_path) -> None:
    broken = tmp_path / "broken.py"
    broken.write_text("def (\n", encoding="utf-8")
    assert generated_function_digest(str(broken)) == ""
    bare = tmp_path / "bare.py"
    bare.write_text("x = 1\n", encoding="utf-8")
    assert generated_function_digest(str(bare)) == ""
    assert generated_function_digest(str(tmp_path / "missing.py")) == ""


# ---------------------------------------------------------------- the accessor, on the real artifact


def _write_suite(tmp_path, node: ast.FunctionDef | None) -> str:
    digest = pins.function_digest(node) if node is not None else None
    source = render_module(KEY, [_prop()], function_digest=digest)
    written = _write(source, str(tmp_path), KEY, str(tmp_path))
    assert written and written.endswith(synth_filename(KEY))
    return written


def test_a_suite_written_for_the_current_definition_is_pinned(tmp_path) -> None:
    node = _node("def f(x):\n    return x + 1\n")
    _write_suite(tmp_path, node)
    assert read_behavior_status(str(tmp_path), str(tmp_path), KEY, node) == "pinned"


def test_changing_the_function_makes_the_suite_stale(tmp_path) -> None:
    before = _node("def f(x):\n    return x + 1\n")
    after = _node("def f(x):\n    return x + 2\n")
    _write_suite(tmp_path, before)
    assert read_behavior_status(str(tmp_path), str(tmp_path), KEY, after) == "pinned_stale"


def test_reformatting_or_commenting_the_function_keeps_it_pinned(tmp_path) -> None:
    # The digest is over the AST, not the text (pins.function_digest) — a comment is not a change.
    before = _node("def f(x):\n    return x + 1\n")
    commented = _node("def f(x):\n    # a note\n    return x + 1\n")
    _write_suite(tmp_path, before)
    assert read_behavior_status(str(tmp_path), str(tmp_path), KEY, commented) == "pinned"


def test_a_human_edit_to_the_suite_makes_it_stale(tmp_path) -> None:
    node = _node("def f(x):\n    return x + 1\n")
    written = _write_suite(tmp_path, node)
    with open(written, "a", encoding="utf-8") as fh:
        fh.write("\n\ndef test_hand_written():\n    assert True\n")
    assert read_behavior_status(str(tmp_path), str(tmp_path), KEY, node) == "pinned_stale"


def test_a_digestless_suite_is_unverified(tmp_path) -> None:
    node = _node("def f(x):\n    return x + 1\n")
    _write_suite(tmp_path, None)
    assert read_behavior_status(str(tmp_path), str(tmp_path), KEY, node) == "pinned_unverified"


def test_no_suite_is_unpinned(tmp_path) -> None:
    node = _node("def f(x):\n    return x + 1\n")
    assert read_behavior_status(str(tmp_path), str(tmp_path), KEY, node) == "unpinned"


def test_another_targets_file_at_this_path_is_unpinned(tmp_path) -> None:
    # A collision lands another owner's generated file at OUR filename: not ours, so unpinned —
    # never read as a pin for this function, whatever digest that file records.
    node = _node("def f(x):\n    return x + 1\n")
    other = render_module("other.py::f", [_prop()], function_digest=pins.function_digest(node))
    path = os.path.join(str(tmp_path), synth_filename(KEY))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(other)
    assert generated_owner(path) == "other.py::f"
    assert read_behavior_status(str(tmp_path), str(tmp_path), KEY, node) == "unpinned"


def test_relative_write_dir_resolves_under_root(tmp_path) -> None:
    node = _node("def f(x):\n    return x + 1\n")
    write_dir = os.path.join(str(tmp_path), "tests", "detective")
    os.makedirs(write_dir)
    source = render_module(KEY, [_prop()], function_digest=pins.function_digest(node))
    assert _write(source, write_dir, KEY, str(tmp_path))
    assert read_behavior_status(str(tmp_path), os.path.join("tests", "detective"), KEY, node) == "pinned"
