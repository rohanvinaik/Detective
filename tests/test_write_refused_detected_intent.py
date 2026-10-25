"""Intent: a write-refused survivor the suite already detects is named with the test that detects it,
never handed back as a test to write; only one nothing detects is (#105, reopened).

THE DEFECT, measured 2026-10-25 on fc87423 with #105's own c1 fixture (`atomic_write_text`, whose test
writes under tmp_path and asserts the content):

    $ detective audit 'm.py::atomic_write_text'
    ⚠ unclassified       6 — the search could not run on them
                         6 of them: ... pin them with a test that writes under tmp_path.
    WRITE TEST:  pin the 6 survivor(s) Detective could not run: the function writes files

A test written to the letter of that block wrote twice under tmp_path, asserted both contents and that
no staging file remained, and closed none of the six. The next audit named it redundant and offered
`--remove`; after the removal the same block returned. A forward claim (COMMUNICATING_DETERMINISM §5)
with no exit.

Five of the six were already detected: the suite's own run of each mutant crashed. The search that
would have sorted them is the one refused for a writer, so every one became "write a test". The sixth,
the staging file's name, changed nothing that test could see.

THE RULING:
- `audit.write_refused_standing` reads the suite's own kill: "crash_detected" for a crash kill, "open"
  otherwise. `audit.write_refused_survivors` names each with its change and, for a detected one, a test
  that detects it. One derivation, read by both verbs' rows and ladders.
- WRITE TEST (`pin_write_refused`) fires only while an open one remains, and names each with its change.
- When every write-refused survivor is detected, converge's code is `write_refused_detected`: an
  INCOMPLETE hand-back with no command and no `flag`. FINAL reads Incomplete, since none of them is
  classified, and a DONE above it is a recorded contradiction. Audit keeps `done_unclassified`.
- "detected by crash; whether a value pins them was not searched", never "no value pins them": for two
  of the five, `assert target.exists()` over a pre-existing target is a value kill.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from Detective.audit import write_refused_standing, write_refused_survivors
from Detective.cli import (
    _write_refused_action,
    _write_refused_detected_action,
    _write_refused_rows,
    converge_next_action,
    converge_step,
    write_refused_residual,
)


@pytest.mark.parametrize(
    ("killed_by", "standing"),
    [("crash", "crash_detected"), ("", "open"), ("timeout", "open"), ("undetermined", "open")],
)
def test_only_the_suites_own_crash_kill_makes_a_write_refused_survivor_detected(killed_by, standing):
    assert write_refused_standing(killed_by) == standing


def test_each_survivor_is_named_with_its_change_and_a_detected_one_with_a_test_that_detects_it():
    records = [
        ["VALUE_a", "staging name", "tmp = f'{p}.tmp' → tmp = f'{p}'", ""],
        ["STMT_b", "replace deleted", "os.replace(tmp, p) → pass", "crash"],
    ]
    kill_matrix = {"replace deleted": ["tests/t.py::test_z", "tests/t.py::test_a"], "staging name": []}
    assert write_refused_survivors(records, kill_matrix) == (
        ("VALUE_a", "tmp = f'{p}.tmp' → tmp = f'{p}'", "open", ""),
        ("STMT_b", "os.replace(tmp, p) → pass", "crash_detected", "tests/t.py::test_a"),
    )


def test_an_open_survivor_names_no_killer_even_where_the_matrix_records_a_timeout():
    # Wesker records a timeout's test in the kill matrix, and a timeout is no detection (`undetermined`
    # in its own disposition): the survivor is open, and naming that test would say it detects it.
    records = [["VALUE_t", "loops", "while x: → while True:", "timeout"]]
    assert write_refused_survivors(records, {"loops": ["tests/t.py::test_slow"]}) == (
        ("VALUE_t", "while x: → while True:", "open", ""),
    )


def test_the_kill_matrix_is_read_by_the_mutants_description_never_by_its_id():
    # The defect a first draft had: it looked the id up among a test → mutant map, found nothing, and
    # named no test for any of them.
    records = [["STMT_b", "replace deleted", "os.replace(tmp, p) → pass", "crash"]]
    assert write_refused_survivors(records, {"STMT_b": ["tests/t.py::test_x"]})[0][3] == ""
    assert write_refused_survivors(records, {"replace deleted": ["tests/t.py::test_x"]})[0][3] == (
        "tests/t.py::test_x"
    )


@pytest.mark.parametrize(
    ("standings", "unclassified", "killable", "line_gap", "residual"),
    [
        (["open", "crash_detected"], 2, False, False, "open"),
        (["crash_detected", "crash_detected"], 2, False, False, "detected"),
        (["crash_detected"], 2, False, False, "none"),  # mixed: another unclassified survivor
        (["crash_detected"], 1, True, False, "none"),  # a killable survivor keeps its own route
        (["open"], 1, False, True, "none"),  # so does a line gap
        ([], 0, False, False, "none"),
    ],
)
def test_the_residual_is_write_refused_only_when_every_unclassified_survivor_is(
    standings, unclassified, killable, line_gap, residual
):
    assert write_refused_residual(standings, unclassified, killable, line_gap) == residual


def test_converge_hands_back_a_detected_residual_and_pins_an_open_one():
    assert converge_next_action("incomplete", "", True, False, write_refused="detected") == (
        "write_refused_detected"
    )
    assert converge_next_action("incomplete", "", True, False, write_refused="open") == "pin_write_refused"
    # the standing still outranks it: an untrusted or stale measurement hands back nothing
    assert converge_next_action("ungateable", "", True, False, write_refused="detected") == (
        "repair_measurement"
    )
    assert converge_next_action("stale", "", True, False, write_refused="detected") == "rerun_stale"


def test_the_detected_hand_back_runs_nothing():
    assert converge_step("write_refused_detected", "", "", False, "", "") == ("hand_back", "crash_detected")


_SURVIVORS = (
    ("VALUE_a", "tmp = f'{p}.tmp' → tmp = f'{p}'", "open", ""),
    ("STMT_b", "os.replace(tmp, p) → pass", "crash_detected", "tests/t.py::test_a"),
    ("SWAP_c", "open(tmp, 'w') → open('w', tmp)", "crash_detected", "tests/t.py::test_a"),
)


def test_the_write_test_block_names_only_the_survivor_nothing_detects_with_its_change():
    block = "\n".join(_write_refused_action(_SURVIVORS, ("converge", "m.py::f")))
    assert "WRITE TEST:  pin the 1 survivor(s) nothing in the suite detects" in block
    assert "VALUE_a  tmp = f'{p}.tmp' → tmp = f'{p}'" in block
    assert "STMT_b" not in block and "SWAP_c" not in block, "a detected survivor handed back as a test"


def test_the_rows_name_every_survivor_by_standing_and_never_claim_no_value_pins_one():
    rows = "\n".join(_write_refused_rows(_SURVIVORS))
    assert "1 nothing in the suite detects:" in rows and "VALUE_a" in rows
    assert "2 detected by crash; whether a value pins them was not searched:" in rows
    assert "(by tests/t.py::test_a)" in rows and "STMT_b" in rows and "SWAP_c" in rows
    assert "no value pins" not in rows


def test_a_long_group_says_where_the_rest_are_named():
    many = tuple((f"SWAP_{i}", f"change {i}", "crash_detected", "tests/t.py::test_a") for i in range(9))
    rows = "\n".join(_write_refused_rows(many))
    assert "(+3 more — --json names every one)" in rows and "SWAP_8" not in rows


def test_the_detected_block_is_incomplete_with_no_command_and_no_flag():
    block = _write_refused_detected_action(_SURVIVORS[1:])
    assert block[0].startswith("INCOMPLETE:  2 survivor(s) the suite detects only by crash")
    text = "\n".join(block)
    assert "DONE" not in text and "detective " not in text
    assert "Nothing to `flag`" in text


# ── end to end: the advice closes, and the test it asks for is never called redundant ─────────────

_WRITER = (
    "import os\n\n\n"
    "def atomic_write_text(path, text):\n"
    "    tmp = f'{path}.tmp-{os.getpid()}'\n"
    "    with open(tmp, 'w') as fh:\n"
    "        fh.write(text)\n"
    "    os.replace(tmp, path)\n"
)
_WRITER_TEST = (
    "import os\n\n"
    "from m import atomic_write_text\n\n\n"
    "def test_atomic_write_text_writes(tmp_path):\n"
    "    target = tmp_path / 'a.txt'\n"
    "    atomic_write_text(str(target), 'hello')\n"
    "    assert target.read_text() == 'hello'\n"
)
# The test the WRITE TEST block asks for: it fails under the one survivor nothing detected, the
# staging file's name.
_STAGING_TEST = (
    "\n\ndef test_atomic_write_text_consumes_its_own_staging_file(tmp_path):\n"
    "    target = tmp_path / 's.txt'\n"
    "    staging = tmp_path / f's.txt.tmp-{os.getpid()}'\n"
    "    staging.write_text('stale')\n"
    "    atomic_write_text(str(target), 'fresh')\n"
    "    assert target.read_text() == 'fresh'\n"
    "    assert not staging.exists()\n"
)


def _detective(cwd, *argv):
    return subprocess.run(
        [sys.executable, "-m", "Detective", *argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
        env=dict(os.environ),
    )


def test_writing_the_test_the_block_names_closes_the_open_survivor_and_ends_in_a_hand_back(tmp_path):
    project = tmp_path / "proj"
    (project / "tests").mkdir(parents=True)
    (project / "m.py").write_text(_WRITER)
    (project / "tests" / "test_m.py").write_text(_WRITER_TEST)
    assert _detective(project, "regime", "--migrate", "--project-root", str(project)).returncode == 0

    first = json.loads(_detective(project, "audit", "m.py::atomic_write_text", "--json").stdout)
    assert first["decision"]["code"] == "pin_write_refused"
    opened = [s for s in first["write_refused_survivors"] if s[2] == "open"]
    assert len(opened) == 1 and first["write_refused"] == 1, first["write_refused_survivors"]
    assert sum(s[2] == "crash_detected" for s in first["write_refused_survivors"]) == 5

    with open(project / "tests" / "test_m.py", "a", encoding="utf-8") as fh:
        fh.write(_STAGING_TEST)

    after = json.loads(_detective(project, "audit", "m.py::atomic_write_text", "--json").stdout)
    assert after["write_refused"] == 0 and opened[0][0] not in [
        s[0] for s in after["write_refused_survivors"]
    ]
    assert after["decision"]["code"] == "done_unclassified"
    assert not after["redundant_tests"], "the test the block asked for was called redundant"

    converge = _detective(project, "converge", "m.py::atomic_write_text")
    assert converge.returncode == 0, converge.stdout + converge.stderr
    page = converge.stdout
    assert "INCOMPLETE:  5 survivor(s) the suite detects only by crash" in page, page
    assert "WRITE TEST" not in page and "AUTHOR INPUT" not in page and "DONE" not in page, page
    assert "FINAL m.py::atomic_write_text: Incomplete" in page, page
