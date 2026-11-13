"""Intent: a function whose only open survivors are refused (a write or process effect) AND detected by
the suite by crash reads `✓ COMPLETE … modulo N refused crash-detected survivor(s)`; one the suite does
not detect stays open (#143).

THE DEFECT (Detective #143, measured 2026-10-26 on #105's c1 fixture, `atomic_write_text`):

    FINAL m.py::atomic_write_text: Incomplete · 7/7 killed · minimal cover 1 test(s) · policy …

with every killable behaviour pinned. Three mutants raise on every call (`open('w', tmp)`,
`with tmp as fh`, mode `''`), two more crash the suite's own test. Detective refuses a speculative
call's file writes, and the witness search that would sort such a survivor into crash-only, killable or
equivalent IS the refused call, so a writer or spawner could never reach COMPLETE. `--check-strict`
also failed (exit 2) on them: `audit_measurement_incomplete` counted every unclassified survivor.

THE RULING (tasks.md row 14.3a): the NAMED FLOOR now. The certificate is conditional on what it names
(KNOWABILITY §10): `audit.refused_floor_standing` reads `floor` when every unclassified survivor is
refused and detected by crash. `--check-strict` fails only on a cause the reader can fix, so it names the
floor and does not fail on it; a refused survivor nothing detects gates, as does any other unclassified
survivor. A sandboxed speculative run is not built.

The floor rides by name on `ConvergeResult.refused_floor` / `SuiteAudit.refused_floor`, in the FINAL
line, the page, `--json`, the decision record and the certificate ledger's `floor` key.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from Detective.audit import gating_unclassified, refused_floor_standing
from Detective.certificates import load_certificate, record_certificate
from Detective.cli import _unclassified_row, audit_headline_verdict


@pytest.mark.parametrize(
    ("standings", "unclassified", "code"),
    [
        (["crash_detected"] * 3, 3, "floor"),
        (["crash_detected"], 1, "floor"),
        # an open refused survivor is closed by a test the reader writes: not a floor
        (["crash_detected", "open"], 2, "partial"),
        # another unclassified survivor (not refused) remains beside the floor
        (["crash_detected", "crash_detected"], 3, "partial"),
        (["open", "open"], 2, "none"),
        ([], 0, "none"),
        ([], 4, "none"),
        # a standings list longer than the count it came from is not a floor
        (["crash_detected", "crash_detected"], 1, "partial"),
    ],
)
def test_the_floor_is_the_whole_unclassified_residual_being_refused_and_detected(
    standings, unclassified, code
):
    assert refused_floor_standing(standings, unclassified) == code


@pytest.mark.parametrize(
    ("unclassified", "standings", "gating"),
    [
        (5, ["crash_detected"] * 5, 0),
        (6, ["crash_detected"] * 5 + ["open"], 1),
        (7, ["crash_detected"] * 5 + ["open"], 2),  # one unclassified survivor that is not refused at all
        (3, [], 3),
        (0, [], 0),
        (1, ["crash_detected"] * 2, 1),  # inconsistent: every survivor still gates, never a negative count
    ],
)
def test_only_a_cause_the_reader_can_fix_gates(unclassified, standings, gating):
    assert gating_unclassified(unclassified, standings) == gating


def test_the_headline_names_the_floor_and_lists_it_beside_other_residue():
    assert audit_headline_verdict(True, False, 0, 0, 7, refused_floor=5) == "complete_modulo_refused"
    assert (
        audit_headline_verdict(True, True, 2, 0, 7, refused_floor=5)
        == "complete_modulo_refused_and_equivalent"
    )
    assert (
        audit_headline_verdict(True, True, 2, 2, 7, refused_floor=1)
        == "complete_modulo_refused_and_equivalent"
    )
    # an incomplete audit stays incomplete whatever the floor, and no floor changes nothing
    assert audit_headline_verdict(False, False, 0, 0, 7, refused_floor=5) == "incomplete"
    assert audit_headline_verdict(True, True, 2, 0, 7) == "complete_modulo_unproven"
    # an empty universe certifies nothing, floor or not
    assert audit_headline_verdict(True, False, 0, 0, 0, refused_floor=5) == "nothing_measured"


def test_the_unclassified_row_is_a_warning_only_when_something_is_open():
    assert _unclassified_row(5, ("a", "b")).lstrip().startswith("· refused floor")
    assert "completeness holds modulo these" in _unclassified_row(2, ("a", "b"))
    assert _unclassified_row(5, ()).lstrip().startswith("⚠ unclassified")


def test_the_ledger_records_the_floor_the_certificate_is_conditional_on(tmp_path):
    record_certificate(str(tmp_path), "m.py::f", "abc", "complete", "", floor=("SWAP_a", "VALUE_b"))
    assert load_certificate(str(tmp_path), "m.py::f")["floor"] == ["SWAP_a", "VALUE_b"]
    # recorded-and-none is `[]`; a missing key would mean "written before the field existed"
    record_certificate(str(tmp_path), "m.py::g", "abc", "complete", "")
    assert load_certificate(str(tmp_path), "m.py::g")["floor"] == []


# ── end to end: the real CLI on #105's c1 fixture ─────────────────────────────────────────────────

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
# The test the WRITE TEST block asks for: it fails under the one survivor nothing detects, the staging
# file's name.
_STAGING_TEST = (
    "\n\ndef test_atomic_write_text_consumes_its_own_staging_file(tmp_path):\n"
    "    target = tmp_path / 's.txt'\n"
    "    staging = tmp_path / f's.txt.tmp-{os.getpid()}'\n"
    "    staging.write_text('stale')\n"
    "    atomic_write_text(str(target), 'fresh')\n"
    "    assert target.read_text() == 'fresh'\n"
    "    assert not staging.exists()\n"
)
# What each always-raising mutant CHANGES, found in the run's own records by its change text, never by a
# content id (those differ between Python 3.12 and 3.13+).
_ALWAYS_RAISING = (
    "with open(tmp, 'w') as fh: → with open('w', tmp) as fh:",
    "with open(tmp, 'w') as fh: → with tmp as fh:",
    "with open(tmp, 'w') as fh: → with open(tmp, '') as fh:",
)


def _detective(cwd, *argv):
    env = dict(os.environ)
    env.pop("PYTHONUNBUFFERED", None)
    return subprocess.run(
        [sys.executable, "-m", "Detective", *argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
        env=env,
    )


def _project(tmp_path, with_staging_test):
    project = tmp_path / "proj"
    (project / "tests").mkdir(parents=True)
    (project / "m.py").write_text(_WRITER)
    (project / "tests" / "test_m.py").write_text(_WRITER_TEST + (_STAGING_TEST if with_staging_test else ""))
    assert _detective(project, "regime", "--migrate", "--project-root", str(project)).returncode == 0
    return project


def test_a_writer_whose_only_open_survivors_are_detected_is_complete_modulo_them_everywhere(tmp_path):
    project = _project(tmp_path, with_staging_test=True)

    page = _detective(project, "converge", "m.py::atomic_write_text")
    assert page.returncode == 0, page.stdout + page.stderr
    final = [line for line in page.stdout.splitlines() if line.startswith("FINAL ")]
    expected = (
        "FINAL m.py::atomic_write_text: ✓ COMPLETE "
        "(operator universe · modulo 5 refused crash-detected survivor(s))"
    )
    assert len(final) == 1 and final[0].startswith(expected), page.stdout
    assert "· refused floor" in page.stdout and "⚠ unclassified" not in page.stdout, page.stdout
    assert "Modulo 5 refused crash-detected survivor(s)" in page.stdout
    assert "INCOMPLETE" not in page.stdout and "WRITE TEST" not in page.stdout

    record = json.loads(_detective(project, "converge", "m.py::atomic_write_text", "--json").stdout)
    assert len(record["refused_floor"]) == 5 and record["functionally_complete"] is True
    assert record["decision"]["code"] == "settled"
    assert record["decision"]["state"]["refused_floor"] == record["refused_floor"]
    refused_changes = {survivor[1] for survivor in record["write_refused_survivors"]}
    assert set(_ALWAYS_RAISING) <= refused_changes, refused_changes
    assert {survivor[0] for survivor in record["write_refused_survivors"]} == set(record["refused_floor"])

    # the certificate ledger says what the page says
    ledger = json.loads((project / "tests" / "detective" / "certificates.json").read_text())
    entry = ledger["m.py::atomic_write_text"]
    assert entry["standing"] == "complete" and entry["floor"] == record["refused_floor"], entry

    # the strict gate names them and does not fail on them
    strict = _detective(project, "audit", "m.py::atomic_write_text", "--check-strict", "--json")
    gate = json.loads(strict.stdout)["gate"]
    assert strict.returncode == 0 and gate["exit"] == 0 and gate["measurement_incomplete"] is False, gate
    assert gate["unmeasured"]["gating_unclassified"] == 0 and gate["unmeasured"]["unclassified"] == 5
    assert gate["unmeasured"]["refused_crash_detected"] == record["refused_floor"]
    text = _detective(project, "audit", "m.py::atomic_write_text", "--check-strict")
    assert "complete, modulo 5 refused crash-detected survivor(s)" in text.stdout, text.stdout
    assert "named and not gating" in text.stderr, text.stderr


def test_a_refused_survivor_nothing_detects_stays_open_and_fails_the_strict_gate(tmp_path):
    project = _project(tmp_path, with_staging_test=False)

    page = _detective(project, "converge", "m.py::atomic_write_text")
    assert page.returncode == 0, page.stdout + page.stderr
    assert "FINAL m.py::atomic_write_text: Incomplete" in page.stdout, page.stdout
    assert "WRITE TEST" in page.stdout and "✓ COMPLETE" not in page.stdout, page.stdout
    record = json.loads(_detective(project, "converge", "m.py::atomic_write_text", "--json").stdout)
    assert record["refused_floor"] == [] and record["functionally_complete"] is False
    ledger = json.loads((project / "tests" / "detective" / "certificates.json").read_text())
    assert ledger["m.py::atomic_write_text"]["floor"] == []

    strict = _detective(project, "audit", "m.py::atomic_write_text", "--check-strict", "--json")
    gate = json.loads(strict.stdout)["gate"]
    assert strict.returncode == 2 and gate["measurement_incomplete"] is True, gate
    # the gate counts the open one only; the detected ones are named beside it
    assert gate["unmeasured"]["gating_unclassified"] == 1
    assert len(gate["unmeasured"]["refused_crash_detected"]) == 5
