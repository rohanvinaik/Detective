"""Intent: a removal proposal says whose tests it proposes removing, audit says how exact its counts are,
and a display cut is marked (Detective #89: U5, the count-noise label, and #125's two remaining cuts).

THE DEFECTS: on a fixture of 5 hand-written tests audit proposed three for `--remove` and said nothing
about intent (the per-test origin was in `--json` only); converge's "PROPOSED removals" listed ids only;
audit's in-process counts carried none of the qualifier converge's report has; `_concise_diff` cut a
line at 100 characters with a bare `…`, and the session warning cut at 200 with no mark.
"""

from __future__ import annotations

import pytest

from Detective.audit import count_basis
from Detective.certify import origins_of_tests
from Detective.cli import _concise_diff, hand_written_note, removal_text


def test_a_removal_proposal_tags_each_test_with_who_wrote_it():
    origins = (("a.py::t1", "intent"), ("b.py::t2", "characterization"), ("c.py::t3", "unattributed"))
    text = removal_text(["a.py::t1", "b.py::t2", "c.py::t3"], origins)
    assert text == "a.py::t1 [hand-written], b.py::t2 [generated], c.py::t3 [origin unknown]"


def test_a_test_with_no_recorded_origin_is_untagged_not_called_generated():
    assert removal_text(["x.py::t"], ()) == "x.py::t"
    assert removal_text([], (("a", "intent"),)) == ""


@pytest.mark.parametrize(
    ("origins", "present"),
    [
        ((("a", "intent"),), True),
        ((("a", "intent"), ("b", "intent")), True),
        ((("a", "characterization"),), False),
        ((), False),
    ],
)
def test_the_hand_written_warning_appears_only_when_a_persons_test_is_proposed(origins, present):
    note = hand_written_note(origins)
    assert bool(note) is present
    if present:
        assert "hand-written" in note and "read before you remove" in note


def test_the_note_counts_and_agrees_in_number():
    assert hand_written_note((("a", "intent"),)).startswith("1 of these is hand-written")
    assert hand_written_note((("a", "intent"), ("b", "intent"))).startswith("2 of these are hand-written")


def test_origins_are_read_from_the_files(tmp_path):
    (tmp_path / "mine.py").write_text("def test_a():\n    assert True\n")
    origins = dict(origins_of_tests(str(tmp_path), ["mine.py::test_a", "missing.py::test_b"]))
    assert origins["mine.py::test_a"] == "intent"
    assert origins["missing.py::test_b"] == "unattributed"


@pytest.mark.parametrize(
    ("flags", "basis"),
    [
        (("approximate:mutant_universe",), "in_process_estimate"),
        (("absent:shared_arguments", "approximate:mutant_universe"), "in_process_estimate"),
        (("absent:shared_arguments",), "exact"),
        ((), "exact"),
    ],
)
def test_the_audit_count_basis_follows_the_validity_flag(flags, basis):
    assert count_basis(flags) == basis


def test_a_cut_diff_line_is_marked_with_what_it_dropped():
    long = "x" * 130
    cut = _concise_diff(long)
    assert cut.startswith("x" * 100) and "(+30 chars)" in cut
    assert _concise_diff("short line") == "short line"
