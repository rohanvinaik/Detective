"""Intent tests for the behavior-status read — the ordering law's one fact per region (§14.1).

DETERMINISTIC_SICP §14.1 (founder rulings 2026-09-05): style after behavior, STRICTLY. A style
move is admissible only on a region whose Detective contract is current and complete, so the plan
needs a static, decidable answer to "has converge certified this function AS IT NOW STANDS?".

Two artifacts carry the answer. The CERTIFICATE (the `certificates` ledger converge writes on every
run) is primary: it is the only record left when the hand-written suite already kills every mutant —
slice 1 read the generated suite alone, and `behavior_status`, `admission_reason` and
`controller_verdict` themselves therefore read `unpinned` the day after converge certified them
complete (measured; the defect slice 1b closes). The generated SUITE refines: a human edit or an
older digest on it means the recorded basis is gone.

What this pins from intent, which a generated characterization cannot:

- the six states are DISTINCT facts with distinct remedies and never collapse — in particular
  "no digest was ever recorded" is `pinned_unverified`, never `pinned` and never `pinned_stale`;
  a measured gap is `pinned_incomplete`, a decline is `refused`, and neither is `unpinned`;
- a complete certificate with NO generated suite is `pinned` (the slice-1 defect, closed);
- a current-digest suite with NO certificate is `pinned_unverified`, not `pinned` (slice 1's
  reading, demoted: a suite is evidence tests were written, a certificate of what they pin);
- an invalid measurement (stale / ungateable standing) asserts nothing about the function;
- the header's second line round-trips the function digest through ONE writer and ONE reader and
  leaves both readers of line 0 (`generated_owner`, `_HEADER_RE`) untouched;
- the accessor reads the real artifacts: the ledger `record_certificate` writes and the suite
  `_write` produces.
"""

from __future__ import annotations

import ast
import os

import pytest

from Detective import pins
from Detective.certificates import record_certificate
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
STANDINGS = ("", "stale", "ungateable", "unverified", "incomplete", "complete")
BOOLS = (False, True)


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


def _expected(cs, cur, ref, owned, has, match, edited) -> str:
    # The reference table, written from the docstring's six states — not from the code.
    if owned and edited:
        return "pinned_stale"
    if cs in ("complete", "incomplete", "unverified"):
        if not cur:
            return "pinned_stale"
        if cs == "complete":
            return "pinned"
        if cs == "incomplete" and ref:
            return "refused"
        return "pinned_incomplete"
    if not owned:
        return "unpinned"
    if has and not match:
        return "pinned_stale"
    return "pinned_unverified"


@pytest.mark.parametrize("cs", STANDINGS)
@pytest.mark.parametrize("cur", BOOLS)
@pytest.mark.parametrize("ref", BOOLS)
@pytest.mark.parametrize("owned", BOOLS)
@pytest.mark.parametrize("has", BOOLS)
@pytest.mark.parametrize("match", BOOLS)
@pytest.mark.parametrize("edited", BOOLS)
def test_behavior_status_truth_table(cs, cur, ref, owned, has, match, edited) -> None:
    assert behavior_status(cs, cur, ref, owned, has, match, edited) == _expected(
        cs, cur, ref, owned, has, match, edited
    )


def test_the_six_states_are_all_reachable_and_distinct() -> None:
    states = {
        behavior_status("complete", True, False, False, False, False, False),
        behavior_status("incomplete", True, False, False, False, False, False),
        behavior_status("incomplete", True, True, False, False, False, False),
        behavior_status("complete", False, False, False, False, False, False),
        behavior_status("", False, False, True, False, False, False),
        behavior_status("", False, False, False, False, False, False),
    }
    assert states == set(pins.BEHAVIOR_STATUSES)
    assert len(pins.BEHAVIOR_STATUSES) == 6


def test_a_complete_certificate_with_no_suite_is_pinned() -> None:
    # THE slice-1 defect: converge certified the hand-written suite complete, wrote no synth, and
    # the function read unpinned. The certificate is the fact; the suite is optional evidence.
    assert behavior_status("complete", True, False, False, False, False, False) == "pinned"


def test_a_current_suite_without_a_certificate_is_unverified_not_pinned() -> None:
    # Slice 1 read this `pinned`. A suite proves tests were written; only a certificate says what
    # they pin — and the ordering law's fact is the second.
    assert behavior_status("", False, False, True, True, True, False) == "pinned_unverified"


def test_no_recorded_digest_is_unverified_never_pinned_or_stale() -> None:
    assert behavior_status("", False, False, True, False, True, False) == "pinned_unverified"
    assert behavior_status("", False, False, True, False, False, False) == "pinned_unverified"


def test_a_certificate_for_an_older_definition_is_stale_whatever_it_said() -> None:
    for standing in ("complete", "incomplete", "unverified"):
        assert behavior_status(standing, False, False, False, False, False, False) == "pinned_stale"


def test_a_measured_gap_and_a_decline_are_different_states() -> None:
    assert behavior_status("incomplete", True, False, False, False, False, False) == "pinned_incomplete"
    assert behavior_status("incomplete", True, True, False, False, False, False) == "refused"
    # A red proof basis is a shortfall, not a decline, whatever refusal text rides along.
    assert behavior_status("unverified", True, True, False, False, False, False) == "pinned_incomplete"


def test_an_invalid_measurement_asserts_nothing_about_the_function() -> None:
    # stale / ungateable standings are about the RUN, not the definition: fall through to the suite.
    for standing in ("stale", "ungateable"):
        assert behavior_status(standing, True, False, False, False, False, False) == "unpinned"
        assert behavior_status(standing, True, False, True, True, True, False) == "pinned_unverified"
        assert behavior_status(standing, True, False, True, True, False, False) == "pinned_stale"


def test_an_edited_suite_outranks_a_complete_certificate() -> None:
    # The certificate's basis included that suite; a human has since taken it over.
    assert behavior_status("complete", True, False, True, True, True, True) == "pinned_stale"


# ---------------------------------------------------------------- the header: one writer, one reader


def test_digest_line_round_trips_and_leaves_line0_readers_unaffected(tmp_path) -> None:
    digest = pins.function_digest(_node("def f(x):\n    return x + 1\n"))
    src = render_module(KEY, [_prop()], function_digest=digest)
    path = tmp_path / "test_f_synth.py"
    path.write_text(src, encoding="utf-8")

    assert generated_function_digest(str(path)) == digest
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


# ---------------------------------------------------------------- the accessor, on the real artifacts

BEFORE = "def f(x):\n    return x + 1\n"
AFTER = "def f(x):\n    return x + 2\n"


def _write_suite(tmp_path, node: ast.FunctionDef | None) -> str:
    digest = pins.function_digest(node) if node is not None else None
    source = render_module(KEY, [_prop()], function_digest=digest)
    written = _write(source, str(tmp_path), KEY, str(tmp_path))
    assert written and written.endswith(synth_filename(KEY))
    return written


def _certify(
    tmp_path,
    node: ast.FunctionDef,
    standing: str = "complete",
    refusal: str = "",
    write_dir: str | None = None,
) -> None:
    # The ledger lives beside the suite. This file's suite is written at tmp_path itself (`_status`
    # reads with write_dir=tmp_path), so the certificate is recorded there unless a test says where.
    assert record_certificate(
        str(tmp_path),
        KEY,
        pins.function_digest(node),
        standing,
        refusal,
        write_dir=write_dir or str(tmp_path),
    )


def _status(tmp_path, node: ast.FunctionDef) -> str:
    return read_behavior_status(str(tmp_path), str(tmp_path), KEY, node)


def test_complete_certificate_alone_is_pinned(tmp_path) -> None:
    node = _node(BEFORE)
    _certify(tmp_path, node)
    assert _status(tmp_path, node) == "pinned"


def test_complete_certificate_plus_current_suite_is_pinned(tmp_path) -> None:
    node = _node(BEFORE)
    _certify(tmp_path, node)
    _write_suite(tmp_path, node)
    assert _status(tmp_path, node) == "pinned"


def test_changing_the_function_makes_the_certificate_stale(tmp_path) -> None:
    before, after = _node(BEFORE), _node(AFTER)
    _certify(tmp_path, before)
    _write_suite(tmp_path, before)
    assert _status(tmp_path, after) == "pinned_stale"


def test_reformatting_or_commenting_the_function_keeps_it_pinned(tmp_path) -> None:
    # The digest is over the AST, not the text (pins.function_digest) — a comment is not a change.
    before = _node(BEFORE)
    commented = _node("def f(x):\n    # a note\n    return x + 1\n")
    _certify(tmp_path, before)
    assert _status(tmp_path, commented) == "pinned"


def test_a_human_edit_to_the_suite_makes_it_stale_despite_the_certificate(tmp_path) -> None:
    node = _node(BEFORE)
    _certify(tmp_path, node)
    written = _write_suite(tmp_path, node)
    with open(written, "a", encoding="utf-8") as fh:
        fh.write("\n\ndef test_hand_written():\n    assert True\n")
    assert _status(tmp_path, node) == "pinned_stale"


def test_incomplete_and_refused_certificates_read_as_themselves(tmp_path) -> None:
    node = _node(BEFORE)
    _certify(tmp_path, node, "incomplete")
    assert _status(tmp_path, node) == "pinned_incomplete"
    _certify(tmp_path, node, "incomplete", "environment_gated:time.time")
    assert _status(tmp_path, node) == "refused"


def test_a_cut_run_leaves_no_verdict(tmp_path) -> None:
    node = _node(BEFORE)
    _certify(tmp_path, node, "ungateable")
    assert _status(tmp_path, node) == "unpinned"
    _write_suite(tmp_path, node)
    assert _status(tmp_path, node) == "pinned_unverified"


def test_a_current_suite_with_no_certificate_is_unverified(tmp_path) -> None:
    node = _node(BEFORE)
    _write_suite(tmp_path, node)
    assert _status(tmp_path, node) == "pinned_unverified"


def test_an_older_suite_with_no_certificate_is_stale(tmp_path) -> None:
    before, after = _node(BEFORE), _node(AFTER)
    _write_suite(tmp_path, before)
    assert _status(tmp_path, after) == "pinned_stale"


def test_a_digestless_suite_with_no_certificate_is_unverified(tmp_path) -> None:
    node = _node(BEFORE)
    _write_suite(tmp_path, None)
    assert _status(tmp_path, node) == "pinned_unverified"


def test_nothing_at_all_is_unpinned(tmp_path) -> None:
    assert _status(tmp_path, _node(BEFORE)) == "unpinned"


def test_another_targets_file_at_this_path_is_unpinned(tmp_path) -> None:
    # A collision lands another owner's generated file at OUR filename: not ours, so unpinned —
    # never read as a pin for this function, whatever digest that file records.
    node = _node(BEFORE)
    other = render_module("other.py::f", [_prop()], function_digest=pins.function_digest(node))
    path = os.path.join(str(tmp_path), synth_filename(KEY))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(other)
    assert generated_owner(path) == "other.py::f"
    assert _status(tmp_path, node) == "unpinned"


def test_relative_write_dir_resolves_under_root(tmp_path) -> None:
    node = _node(BEFORE)
    write_dir = os.path.join(str(tmp_path), "tests", "detective")
    os.makedirs(write_dir)
    # The certificate is recorded beside THIS suite (relative write-dir), and the reader resolves
    # the same relative write-dir under root for both the ledger and the synth.
    _certify(tmp_path, node, write_dir=os.path.join("tests", "detective"))
    source = render_module(KEY, [_prop()], function_digest=pins.function_digest(node))
    assert _write(source, write_dir, KEY, str(tmp_path))
    assert read_behavior_status(str(tmp_path), os.path.join("tests", "detective"), KEY, node) == "pinned"
