"""Intent tests for S1 and S2 — two places the output claimed more than it showed.

Design: `docs/CORRECTNESS_REPAIRS_2026-09-08.md` §S1, §S2.

Different surfaces, one shape: a report that states a fact the reader cannot act on, because the
part they would act on is missing and nothing says it is missing.

S1 — converge rendered `11 line(s): [93, 95, 97, 98, 100, 101, 104, 107]`. Eight numbers under a
header saying eleven, with no marker. A reader who closes those eight has closed the gap the
report SHOWED them and not the gap it COUNTED. `audit` already used `_first_n` on the identical
fact, so the two commands disagreed about how much they were disclosing.

S2 — `--version` printed `detective 0.13.0 (Wesker 0.13.0)` for two DIFFERENT engines. A version
is a property of the release, not of the bytes running, so it cannot answer "which engine is
this" — the first question of a bug report, and the one an A/B must settle before its results
mean anything. Measured: a worktree at an older commit and the live tree were indistinguishable.
"""

from __future__ import annotations

from Detective.cli import _first_n, _resolved_engines

# ---------------------------------------------------------------- S1: the truncated line list


def test_the_disclosing_helper_marks_a_cut_and_only_a_cut():
    """The behaviour both rows now share. `audit` already used this; converge's uncovered row was
    the one place that did not, which is how the two commands came to disagree about how much they
    were disclosing."""
    assert _first_n(range(11), 8).endswith("… (+3 more)")
    assert _first_n([1, 2], 8) == "1, 2", "a list that fits must not claim a remainder"


def test_no_render_row_truncates_a_line_list_with_a_bare_slice():
    """A property of the MODULE, asserted at source level on purpose.

    The end-to-end behaviour is verified through the real command (GofL `Game.update_cell` renders
    `11 line(s): 93, 95, ... … (+3 more)`); what this guards is that no row goes back to a bare
    `[:8]`, which is what the defect WAS. A behavioural test here would need a ~25-field fixture
    for `_format_converge_terse`, and a fixture that large rots into testing itself — this asserts
    the one thing that actually regressed, and it fails if a second row acquires the same habit.
    """
    import ast
    import pathlib

    tree = ast.parse(pathlib.Path("Detective/cli.py").read_text())
    offenders = []
    for node in ast.walk(tree):
        # an f-string row that mentions line(s) and interpolates a raw subscript slice
        if not isinstance(node, ast.JoinedStr):
            continue
        text = "".join(
            p.value for p in node.values if isinstance(p, ast.Constant) and isinstance(p.value, str)
        )
        if "line(s)" not in text:
            continue
        for part in node.values:
            if isinstance(part, ast.FormattedValue) and isinstance(part.value, ast.Subscript):
                if isinstance(part.value.slice, ast.Slice):
                    offenders.append(node.lineno)
    assert offenders == [], f"a line list is sliced without a truncation marker at cli.py:{offenders}"


# ---------------------------------------------------------------- S2: which engine is running


def test_the_version_string_names_where_each_engine_was_imported_from():
    """A version number is a property of the RELEASE. Two checkouts of 0.13.0 are both 0.13.0, so
    the number cannot answer which one ran — the path can."""
    out = _resolved_engines()
    assert "Detective" in out and "Wesker" in out
    assert ".py" in out, "a path, not just a name"


def test_it_reports_the_LIVE_module_not_a_declared_dependency():
    """The floor in the metadata is what was ASKED for; a report is produced by what is LOADED.
    An editable checkout, a PYTHONPATH sibling and a stale venv all differ here and nowhere else."""
    import Wesker

    import Detective

    out = _resolved_engines()
    assert Detective.__file__ in out
    assert Wesker.__file__ in out


def test_it_never_raises_even_when_an_engine_cannot_be_imported(monkeypatch):
    """This string exists to be trusted in a bug report. A `--version` that dies is worse than one
    that says it could not look."""
    import builtins

    real = builtins.__import__

    def _boom(name, *a, **k):
        if name in ("Detective", "Wesker"):
            raise ImportError("boom")
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", _boom)
    out = _resolved_engines()
    assert "NOT IMPORTABLE" in out
