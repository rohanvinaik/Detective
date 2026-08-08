"""File origin is canonical; a dotted module name is an ALIAS (issue #58).

Detective reconstructs the pytest regime in five separate places, each a prediction of what
pytest would do rather than a record of what it did. The failure mode is exactly the case where
prediction and runner disagree, so a certificate cannot rest on a mirror.

This module holds the correctness core: a module name that resolves to more than one file means
the import system served different code under one identity, and every observation attributed to
that name is attributed to something the report cannot name. It is the same shadowing condition
`regime` already refuses a verdict over.

Written by hand ON PURPOSE. Detective's own generated suite for this function is a
CHARACTERIZATION — it pins what the code does, and it said so — so these state what the code
SHOULD do, which is the only thing that can catch a wrong implementation pinned wrong.
"""

from __future__ import annotations

from Detective.session_manifest import module_identity_conflicts


def test_one_name_two_files_is_a_conflict():
    """The defect. Two files under one name means a measurement attributed to that name could
    have come from either — the shadowing condition, stated in identities rather than paths."""
    assert module_identity_conflicts({"pkg.mod": ["/a/mod.py", "/b/mod.py"]}) == ["pkg.mod"]


def test_one_name_one_file_is_clean():
    """The control. A well-formed session is the overwhelmingly common case and must cost
    nothing — a detector that flagged it would make every run refuse."""
    assert module_identity_conflicts({"pkg.mod": ["/a/mod.py"]}) == []


def test_the_same_file_listed_twice_is_not_a_conflict():
    """Observed repeatedly is not observed inconsistently. The map records an origin per
    observation, so repetition is an artefact of how often a name was touched."""
    assert module_identity_conflicts({"pkg.mod": ["/a/mod.py", "/a/mod.py"]}) == []


def test_a_name_with_no_origin_is_not_a_conflict():
    """Nothing was attributed to it, so there is nothing to misattribute. Treating absence as
    conflict would refuse verdicts over names that never participated."""
    assert module_identity_conflicts({"pkg.mod": []}) == []


def test_every_conflicting_name_is_reported_not_just_the_first():
    """A refusal that names one cause sends the user to fix one of several. Sorted, so two
    identical sessions cannot produce different reports."""
    assert module_identity_conflicts(
        {
            "z.mod": ["/a.py", "/b.py"],
            "a.mod": ["/c.py", "/d.py"],
            "m.ok": ["/e.py"],
        }
    ) == ["a.mod", "z.mod"]


def test_clean_and_conflicting_names_coexist():
    """The realistic shape: one bad name among many good ones must surface without dragging the
    others into the refusal."""
    assert module_identity_conflicts(
        {"good": ["/a.py"], "bad": ["/b.py", "/c.py"], "also_good": ["/d.py"]}
    ) == ["bad"]


def test_an_empty_session_has_no_conflicts():
    assert module_identity_conflicts({}) == []
