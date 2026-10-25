"""Intent: a function that writes files is measured to a full page, never aborted, and its survivors are
named with the one repair that can reach them (#105).

THE DEFECT, measured 2026-10-25 on fcd3348 / Wesker 6ba533d by a containment verification:

    $ detective audit 'm.py::atomic_write_text'        # a writer whose tests write under tmp_path
    INCOMPLETE:  filesystem_write_blocked: speculative filesystem effects were intercepted:
                 /private/var/…/pytest-40304/test_atomic_write_text_writes_4/a.txt.tmp-3285
    $ echo $?
    3

That was every audit and converge of a file-writing function with a survivor, in five briefed runs and
on #105's own fixture under `--two-sign`. Survivor classification replays the test's harvested
arguments, or invented ones, in-process under `block_fs_writes` (#30). The guard prevented each write
correctly: nothing landed in 13 runs. But it raised `ObservationIncomplete` to the CLI's top-level
handler, which replaced the page with one line, exit 3 ("re-run"), and re-running reproduced it. One
refused input ended the measurement, and the prevented mutant was never named.

THE RULING:
- A refused write is that input's own outcome (`_OUTCOME_WRITE_REFUSED`, a fixed marker, never the
  path). It routes to the existing `blocked` (unclassified, never equivalent).
- Only `filesystem_write_blocked` is narrowed; every other incomplete observation still aborts.
- Property rendering and verification each guard per survivor, and the reach diagnostic skips the trial.
- The survivors are named apart (`write_refused`), with a repair no search or `--input` supplies: a test
  that writes under tmp_path. Both ladders route to it (`pin_write_refused`, step `write_test`) when it is
  the open residual, never DONE and never an `--input` ask.
"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys

import pytest

from Detective.capture import ObservationIncomplete
from Detective.cli import audit_next_action, audit_step, converge_next_action, converge_step
from Detective.equivalence import (
    _OUTCOME_WRITE_REFUSED,
    _outcome,
    _pair_disposition,
    _search_witness_detail,
)


def _writer(path):
    with open(path, "w") as fh:
        fh.write("x")
    return path


def test_a_refused_write_is_the_inputs_own_outcome_and_nothing_lands(tmp_path):
    target = tmp_path / "never.txt"
    assert _outcome(_writer, (str(target),)) == _OUTCOME_WRITE_REFUSED
    assert not target.exists(), "the guard must prevent the write before it lands"


def test_a_refused_write_on_either_side_is_blocked_never_a_witness():
    assert _pair_disposition(_OUTCOME_WRITE_REFUSED, "1") == "blocked"
    assert _pair_disposition("1", _OUTCOME_WRITE_REFUSED) == "blocked"
    assert _pair_disposition(_OUTCOME_WRITE_REFUSED, _OUTCOME_WRITE_REFUSED) == "blocked"


def test_the_search_names_a_write_refused_survivor_and_classifies_nothing(tmp_path):
    search = _search_witness_detail(_writer, _writer, [(str(tmp_path / "a"),), (str(tmp_path / "b"),)])
    assert search.witness is None and search.blocked and search.write_refused
    assert not os.listdir(tmp_path)


def test_only_a_refused_write_is_absorbed_every_other_incomplete_observation_still_aborts(monkeypatch):
    @contextlib.contextmanager
    def uncontained():
        yield
        raise ObservationIncomplete("outcome_uncontained", "a live worker", contained=False)

    monkeypatch.setattr("Detective.synthesis.characterization.block_fs_writes", uncontained)
    with pytest.raises(ObservationIncomplete) as caught:
        _outcome(lambda: 1, ())
    assert caught.value.code == "outcome_uncontained"


# block, has_failing_tests, killable_gaps, missing_lines, redundant_tests, removing,
# candidate_equivalent, has_equivalent_ids, unclassified — then diverged=, errored=, write_refused=
@pytest.mark.parametrize(
    ("args", "kw", "expected"),
    [
        (("", False, 0, 0, 0, False, 0, False, 2), {"write_refused": 2}, "pin_write_refused"),
        (("", False, 0, 0, 0, False, 3, True, 2), {"write_refused": 2}, "pin_write_refused"),
        (("", False, 0, 0, 0, False, 0, False, 2), {"write_refused": 2, "diverged": 1}, "pin_write_refused"),
        (("", False, 0, 0, 0, False, 0, False, 2), {"write_refused": 2, "errored": 1}, "repair_errored_test"),
        (("", False, 1, 0, 0, False, 0, False, 2), {"write_refused": 2}, "close_the_gap"),
        (("", False, 0, 0, 1, False, 0, False, 2), {"write_refused": 2}, "remove_redundant"),
        (("", True, 0, 0, 0, False, 0, False, 2), {"write_refused": 2}, "fix_failing_test"),
        (("", False, 0, 0, 0, False, 0, False, 2), {}, "done_unclassified"),
    ],
)
def test_audits_ladder_names_the_write_refused_residual_where_done_would_be_false(args, kw, expected):
    assert audit_next_action(*args, **kw) == expected


def test_converges_ladder_hands_the_residual_to_a_test_never_to_an_input_ask():
    assert converge_next_action("incomplete", "", True, False, write_refused="open") == "pin_write_refused"
    assert converge_next_action("incomplete", "", True, False) != "pin_write_refused"
    assert converge_next_action("ungateable", "", True, False, write_refused="open") == "repair_measurement"


@pytest.mark.parametrize("two_sign", [False, True])
def test_the_move_is_a_test_the_person_writes_in_both_verbs(two_sign):
    assert audit_step("pin_write_refused", two_sign) == ("write_test", "pin_write_refused")
    assert converge_step("pin_write_refused", "", "", False, "", "") == ("write_test", "pin_write_refused")


# ── end to end through the real CLI ─────────────────────────────────────────────────────────────

_WRITER = (
    "import os\n\n\n"
    "def atomic_write_text(path, text):\n"
    "    tmp = f'{path}.tmp-{os.getpid()}'\n"
    "    with open(tmp, 'w') as fh:\n"
    "        fh.write(text)\n"
    "    os.replace(tmp, path)\n"
)
_WRITER_TEST = (
    "from m import atomic_write_text\n\n\n"
    "def test_atomic_write_text_writes(tmp_path):\n"
    "    target = tmp_path / 'a.txt'\n"
    "    atomic_write_text(str(target), 'hello')\n"
    "    assert target.read_text() == 'hello'\n"
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


def _files(root):
    return sorted(
        os.path.relpath(os.path.join(d, f), root)
        for d, dirs, fs in os.walk(root)
        if not any(
            part.startswith((".detective", ".wesker", ".pytest_cache", "__pycache__"))
            for part in d.split(os.sep)
        )
        for f in fs
    )


def test_a_file_writer_gets_a_full_page_naming_the_test_to_write_and_nothing_lands(tmp_path):
    project = tmp_path / "proj"
    (project / "tests").mkdir(parents=True)
    (project / "m.py").write_text(_WRITER)
    (project / "tests" / "test_m.py").write_text(_WRITER_TEST)
    assert _detective(project, "regime", "--migrate", "--project-root", str(project)).returncode == 0
    before = _files(project)

    audit = _detective(project, "audit", "m.py::atomic_write_text")
    assert audit.returncode == 0, audit.stdout + audit.stderr
    assert "filesystem_write_blocked" not in audit.stdout, "one refused input ended the measurement"
    assert "survivor(s) nothing in the suite detects: the function writes files" in audit.stdout, audit.stdout
    assert "DONE" not in audit.stdout, "DONE over a residual a hand-written test reaches"

    converge = _detective(project, "converge", "m.py::atomic_write_text")
    assert "filesystem_write_blocked" not in converge.stdout, converge.stdout
    assert "WRITE TEST:  pin the" in converge.stdout and "AUTHOR INPUT" not in converge.stdout, (
        converge.stdout
    )

    record = json.loads(_detective(project, "audit", "m.py::atomic_write_text", "--json").stdout)
    assert record["decision"]["code"] == "pin_write_refused" and record["write_refused"] > 0

    after = [f for f in _files(project) if f != os.path.join("tests", "detective", "certificates.json")]
    assert after == before, "a speculative run wrote into the project"
    assert sorted(os.listdir(tmp_path)) == ["proj"], "a speculative run wrote beside the project"
