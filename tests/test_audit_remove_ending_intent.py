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
    _redundant_kept,
    _removal_lines,
    audit_next_action,
    audit_step,
    removal_ending,
)

ROW = "tests/test_c.py::test_rows[2-1]"
PLAIN = "tests/test_c.py::test_dup"


def _next(redundant, rows, removing=False, **kw):
    return audit_next_action(
        "", False, kw.get("gaps", 0), 0, redundant, removing, 0, False, 0, redundant_kept=rows
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


def test_the_kept_tests_are_read_from_the_recorded_dispositions_never_from_the_ids_spelling():
    """What `--remove` would keep is `removal_disposition`'s answer over the suite as it stands, recorded
    by the audit. A bracket in an id decides nothing here, and neither does its absence."""
    report = SimpleNamespace(
        redundant_dispositions=(
            (ROW, "parametrized_row"),
            (PLAIN, "remove"),
            ("tests/test_c.py::test_gone", "not_located"),
            ("test_twice", "ambiguous"),
            ("tests/test_c.py::Outer.Inner.test_deep", "unsupported_shape"),
        )
    )
    assert _redundant_kept(report) == (
        (ROW, "parametrized_row"),
        ("tests/test_c.py::test_gone", "not_located"),
        ("test_twice", "ambiguous"),
        ("tests/test_c.py::Outer.Inner.test_deep", "unsupported_shape"),
    )
    # A plain id recorded as a row is kept; a bracketed id recorded as removable is not.
    assert _redundant_kept(SimpleNamespace(redundant_dispositions=((PLAIN, "parametrized_row"),))) == (
        (PLAIN, "parametrized_row"),
    )
    assert _redundant_kept(SimpleNamespace(redundant_dispositions=((ROW, "remove"),))) == ()


def test_a_report_that_recorded_no_disposition_names_no_kept_test():
    """An unrecorded disposition is not a kept test: the ladder then directs `--remove` as before."""
    assert _redundant_kept(SimpleNamespace(redundant_dispositions=())) == ()
    assert _redundant_kept(SimpleNamespace()) == ()
    assert _next(2, 0) == "remove_redundant"


def test_every_kind_remove_keeps_is_a_hand_back_not_only_rows():
    """The first version handed back parametrized rows alone; an id no definition answers to, an
    ambiguous id and an unsupported shape are kept by `--remove` just the same, so `--remove` on a
    redundant set made only of those removed nothing and was directed again."""
    for kept in (1, 2, 3):
        assert _next(kept, kept) == "prune_by_hand"
    assert _next(3, 2) == "remove_redundant"  # one of the three is removable: --remove does something


def test_steps_and_commands_for_the_hand_prune():
    assert audit_step("prune_by_hand", False) == ("hand_back", "prune_by_hand")
    assert audit_step("prune_by_hand", True) == ("run", "")
    assert _audit_commands("prune_by_hand", "m.py::f", False) == (None, ("audit", "m.py::f"))
    assert _audit_commands("prune_by_hand", "m.py::f", True)[0] == ("converge", "m.py::f", "--two-sign")


def test_the_hand_back_names_each_kept_test_under_its_own_reason_and_never_remove():
    audit = SimpleNamespace(
        function="m.py::f",
        redundant_tests=(ROW, "tests/test_c.py::test_rows[3-1]", "tests/test_c.py::test_gone"),
        redundant_dispositions=(
            (ROW, "parametrized_row"),
            ("tests/test_c.py::test_rows[3-1]", "parametrized_row"),
            ("tests/test_c.py::test_gone", "not_located"),
        ),
    )
    page = "\n".join(_audit_closing_action(audit, "prune_by_hand"))
    assert page.startswith("PRUNE BY HAND:")
    assert ROW in page and "test_rows[3-1]" in page and "test_gone" in page
    # Each kind carries the sentence `--remove`'s own page prints for it.
    assert "a row of a live parametrized test; rows are never edited" in page
    assert "no definition in the current source answers to this id" in page
    assert "--remove'" not in page and "DO THIS" not in page
    assert page.rstrip().endswith("# re-audit")


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


def _cli_project(tmp_path, tests_source: str):
    import os
    import subprocess
    import sys

    d = str(tmp_path)
    os.makedirs(os.path.join(d, "tests"))
    with open(os.path.join(d, "pyproject.toml"), "w") as fh:
        fh.write('[tool.pytest.ini_options]\npythonpath = ["."]\ntestpaths = ["tests"]\n')
    with open(os.path.join(d, "m.py"), "w") as fh:
        fh.write('def f(x):\n    if x > 0:\n        return "pos"\n    return "nonpos"\n')
    with open(os.path.join(d, "tests", "test_m.py"), "w") as fh:
        fh.write(textwrap.dedent(tests_source))
    env = dict(os.environ, HOME=os.path.join(d, "home"), PYTHONPATH=os.pathsep.join(sys.path))

    def run(*argv):
        return subprocess.run(
            [sys.executable, "-m", "Detective.cli", *argv],
            cwd=d,
            env=env,
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        ).stdout

    run("regime", "--migrate", "--project-root", d)
    return run


_ROWS_ONLY = """\
    import pytest
    from m import f


    def test_pos():
        assert f(1) == "pos"


    def test_nonpos():
        assert f(0) == "nonpos"


    @pytest.mark.parametrize("x", [3, 4])
    def test_more_pos(x):
        assert f(x) == "pos"
"""


def test_redundant_rows_are_handed_back_through_the_real_command(tmp_path):
    """Measured 2026-11-11 on this fixture: audit said `redundant 2 test(s)` (the two rows) and directed
    `--remove`, which kept both. The page must not name a command that changes nothing."""
    import json

    run = _cli_project(tmp_path, _ROWS_ONLY)
    payload = json.loads(run("audit", "m.py::f", "--json"))
    assert sorted(payload["redundant_tests"]) == [
        "tests/test_m.py::test_more_pos[3]",
        "tests/test_m.py::test_more_pos[4]",
    ]
    assert dict(map(tuple, payload["redundant_dispositions"])) == {
        "tests/test_m.py::test_more_pos[3]": "parametrized_row",
        "tests/test_m.py::test_more_pos[4]": "parametrized_row",
    }
    assert payload["decision"]["code"] == "prune_by_hand"
    page = run("audit", "m.py::f")
    assert "PRUNE BY HAND:" in page, page
    assert "--remove\n" not in page and "DO THIS" not in page, page
    assert "test_more_pos[3]" in page and "test_more_pos[4]" in page


def test_a_removable_redundant_test_still_gets_remove_through_the_real_command(tmp_path):
    import json

    run = _cli_project(tmp_path, _ROWS_ONLY + '\n\n    def test_dup():\n        assert f(5) == "pos"\n')
    payload = json.loads(run("audit", "m.py::f", "--json"))
    dispositions = dict(map(tuple, payload["redundant_dispositions"]))
    assert dispositions["tests/test_m.py::test_dup"] == "remove"
    assert payload["decision"]["code"] == "remove_redundant"
    assert "DO THIS:  detective audit 'm.py::f' --remove" in run("audit", "m.py::f")
