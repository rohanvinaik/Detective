"""#142 (routing items a and c, measured 2026-11-11):

(a) `audit` said `redundant 2 test(s)` (two rows of a live parametrized test) and directed `--remove`, which
keeps both ("rows are never edited (prune it by hand)"). When every redundant test is one `--remove` keeps,
the directive is the hand-prune hand-back naming the rows. It is derived from `removal_disposition` — the
decision `--remove` makes — not from the id's spelling.

(c) The founder's ruling A4: a `--remove` page that ends `DONE` while real gaps are open is a defect. The
ladder's directive stays the page's last while the measurement is incomplete."""

import os
import subprocess
import sys
import textwrap
from types import SimpleNamespace

from Detective.cli import (
    _audit_closing_action,
    _audit_commands,
    _redundant_row_count,
    _removal_lines,
    audit_next_action,
    audit_step,
    removal_ending,
)

ROW = "tests/test_c.py::test_rows[2-1]"
PLAIN = "tests/test_c.py::test_dup"


def _next(redundant, rows, removing=False, **kw):
    return audit_next_action(
        "", False, kw.get("gaps", 0), 0, redundant, removing, 0, False, 0, redundant_rows=rows
    )


def test_all_rows_redundant_is_a_hand_prune_not_remove():
    assert _next(2, 2) == "prune_by_hand"
    assert _next(2, 2, removing=True) == "prune_by_hand"


def test_a_removable_test_among_the_redundant_keeps_remove():
    assert _next(2, 1) == "remove_redundant"
    assert _next(1, 0) == "remove_redundant"
    assert _next(2, 1, removing=True) == "removing_now"


def test_no_redundancy_and_gaps_are_unchanged():
    assert _next(0, 0) == "done_complete"
    assert _next(2, 2, gaps=1) == "close_the_gap"


def test_row_count_reads_removal_disposition_not_a_bracket_regex():
    assert _redundant_row_count([ROW, PLAIN]) == 1
    assert _redundant_row_count([PLAIN]) == 0
    assert _redundant_row_count([]) == 0
    assert _redundant_row_count(["tests/t.py::TestC::test_m[x-1]"]) == 1


def test_steps_and_commands_for_the_hand_prune():
    assert audit_step("prune_by_hand", False) == ("hand_back", "prune_by_hand")
    assert audit_step("prune_by_hand", True) == ("run", "")
    assert _audit_commands("prune_by_hand", "m.py::f", False) == (None, ("audit", "m.py::f"))
    assert _audit_commands("prune_by_hand", "m.py::f", True)[0] == ("converge", "m.py::f", "--two-sign")


def test_the_hand_prune_block_names_the_rows_and_never_remove():
    audit = SimpleNamespace(function="m.py::f", redundant_tests=(ROW, "tests/test_c.py::test_rows[3-1]"))
    page = "\n".join(_audit_closing_action(audit, "prune_by_hand"))
    assert page.startswith("PRUNE BY HAND:")
    assert ROW in page and "test_rows[3-1]" in page
    assert "--remove'" not in page and "DO THIS" not in page


def test_removal_ending_ladder_vs_removal():
    assert removal_ending("removing_now") == "removal"
    for code in (
        "close_the_gap",
        "fix_load",
        "repair_measurement",
        "fix_failing_test",
        "provide_sample",
        "prune_by_hand",
    ):
        assert removal_ending(code) == "ladder"


def _record(removed):
    return {
        "outcomes": [],
        "removed": removed,
        "target": "m.py::f",
        "gate": "proceed",
        "after": {"reading": "gap_kept", "test_count": 3, "value_killed": 9, "total_mutants": 13},
    }


def test_ladder_ending_reports_the_removal_without_a_done():
    lines = _removal_lines(_record(["t::a"]), None, "ladder")
    assert not any(line.startswith("DONE:") for line in lines)
    assert any(line.startswith("  removal: removed 1 test(s)") for line in lines)
    assert any(line.startswith("DONE:") for line in _removal_lines(_record(["t::a"]), None, "removal"))


def test_a_stop_is_kept_under_the_ladder_ending():
    record = {
        **_record(["t::a"]),
        "after": {
            "reading": "gap_new",
            "newly_open": 1,
            "test_count": 1,
            "value_killed": 1,
            "total_mutants": 2,
        },
    }
    assert any(line.startswith("STOP:") for line in _removal_lines(record, None, "ladder"))


def test_remove_over_an_open_gap_ends_on_the_ladders_directive(tmp_path):
    d = str(tmp_path)
    os.makedirs(os.path.join(d, "home"))
    os.makedirs(os.path.join(d, "tests"))
    with open(os.path.join(d, "m.py"), "w") as fh:
        fh.write("def f(x):\n    return x + 1 if x > 0 else 0\n")
    with open(os.path.join(d, "tests", "test_m.py"), "w") as fh:
        fh.write(
            textwrap.dedent(
                """\
                from m import f

                def test_pos():
                    assert f(3) == 4

                def test_nonpos():
                    assert f(-1) == 0

                def test_dup():
                    assert f(3) == 4
                """
            )
        )
    env = dict(os.environ, HOME=os.path.join(d, "home"), PYTHONPATH=os.pathsep.join(sys.path))

    def run(*argv):
        return subprocess.run(
            [sys.executable, "-m", "Detective.cli", *argv],
            cwd=d,
            env=env,
            capture_output=True,
            text=True,
            timeout=900,
        ).stdout

    run("regime", "--migrate", "--project-root", d)
    page = run("audit", "m.py::f", "--remove")
    assert "real gaps" in page, page
    lines = [line for line in page.splitlines() if line.strip()]
    assert not any(line.startswith("DONE:") for line in lines)
    last_block = next(i for i in range(len(lines) - 1, -1, -1) if lines[i].startswith("DO THIS:"))
    assert all(not line.startswith(("DONE", "STOP")) for line in lines[last_block:])
