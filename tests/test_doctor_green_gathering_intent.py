"""Durability tests for doctor's GREEN gathering layer (`docs/DOCTOR.md` §2, §7.3).

Pure I/O and environment probing, so hand-written tests only — the project's rule that an
impure shell is not converge-pinnable. What they cover is the property the whole surface rests on:

    EVERY probe here is advisory and MUST NOT RAISE.

Doctor is the command a confused user runs. A diagnostic that dies on the way to explaining a
failure is worse than no diagnostic, and worse again than admitting it could not look — so each
probe degrades to an empty/false answer that the render reports as "could not look", never as
"nothing wrong". Absence disclosed, not absence read as health.

Deliberately machine-independent: nothing here asserts that a particular interpreter or package
exists on the box running the suite. The one test that needs a second interpreter builds a fake one.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

from Detective.doctor import (
    candidate_interpreters,
    found_elsewhere,
    missing_here,
    pytest_importable,
    recorded_cut_reasons,
    target_imports,
)

# ---------------------------------------------------------------- target_imports: static, fenced


def test_it_reads_imports_without_importing_the_target(tmp_path) -> None:
    """§1 forbids importing the target to find out. A module with a side effect at import time
    proves the fence holds: if this were an import, the file would be written."""
    canary = tmp_path / "canary.txt"
    mod = tmp_path / "boom.py"
    mod.write_text(f"import funcy\nopen({str(canary)!r}, 'w').write('imported')\n")
    assert target_imports(str(mod)) == ("funcy",)
    assert not canary.exists(), "the target was IMPORTED — the fence is broken"


def test_only_the_top_level_segment_is_taken(tmp_path) -> None:
    """`find_spec` on a DOTTED name imports the parent packages to locate the child, which executes
    code. Taking the first segment is what keeps the later probe inside the fence."""
    mod = tmp_path / "m.py"
    mod.write_text("import a.b.c\nfrom d.e import f\n")
    assert target_imports(str(mod)) == ("a", "d")


def test_stdlib_and_relative_imports_are_not_dependencies(tmp_path) -> None:
    """A stdlib module is never the propagation case, and a relative import is the target's own
    package. Reporting either would be noise on a surface whose credibility is the product."""
    mod = tmp_path / "m.py"
    mod.write_text("import os, sys, json\nfrom . import sibling\nfrom .pkg import thing\nimport funcy\n")
    assert target_imports(str(mod)) == ("funcy",)


@pytest.mark.parametrize("content", ["def broken(:\n", ""])
def test_an_unreadable_or_unparseable_target_yields_nothing_rather_than_raising(tmp_path, content) -> None:
    mod = tmp_path / "m.py"
    mod.write_text(content)
    assert target_imports(str(mod)) == ()
    assert target_imports(str(tmp_path / "does_not_exist.py")) == ()


# ---------------------------------------------------------------- missing_here: conservative


def test_a_module_this_interpreter_has_is_not_reported_missing() -> None:
    assert missing_here(("json",)) == ()


def test_a_module_nobody_has_is_reported_missing() -> None:
    assert missing_here(("definitely_not_a_real_package_xyz",)) == ("definitely_not_a_real_package_xyz",)


def test_a_name_whose_finder_misbehaves_is_reported_MISSING_not_present() -> None:
    """ "We could not establish that it is importable" and "it is importable" are different facts,
    and only the conservative one is safe on a surface that tells people what to install."""
    assert missing_here(("",)) == ("",)
    assert missing_here(("...bad.name",)) == ("...bad.name",)


# ---------------------------------------------------------------- the interpreter bound (§7.3)


def test_the_running_interpreter_is_never_a_candidate() -> None:
    """It is the one missing the package — asking it again is the tautology the operator is already
    stuck inside."""
    here = os.path.realpath(sys.executable)
    assert all(os.path.realpath(c) != here for c in candidate_interpreters("."))


def test_candidates_are_deduplicated_by_real_path() -> None:
    cands = candidate_interpreters(".")
    reals = [os.path.realpath(c) for c in cands]
    assert len(reals) == len(set(reals)), "a symlinked python must not be probed twice"


def test_the_probe_is_bounded_and_does_not_sweep_the_filesystem(tmp_path) -> None:
    """A machine-wide hunt would surface interpreters the operator has no relationship with and
    turn a bounded inference into a guess. An empty project dir yields only PATH pythons."""
    cands = candidate_interpreters(str(tmp_path))
    assert all(os.path.dirname(os.path.dirname(c)) not in (str(tmp_path),) for c in cands)


# ---------------------------------------------------------------- found_elsewhere: never raises


def test_nothing_to_ask_or_nobody_to_ask_is_an_empty_answer() -> None:
    assert found_elsewhere((), ("/usr/bin/python3",)) == {}
    assert found_elsewhere(("funcy",), ()) == {}


def test_an_interpreter_that_cannot_run_tells_us_nothing_rather_than_raising(tmp_path) -> None:
    """An interpreter that hangs, dies or answers rubbish is one that told us nothing. The probe
    must survive it — doctor is what the user reaches for when things are already broken."""
    bogus = tmp_path / "not-a-python"
    bogus.write_text("#!/bin/sh\nexit 1\n")
    bogus.chmod(0o755)
    assert found_elsewhere(("funcy",), (str(bogus),)) == {}
    assert found_elsewhere(("funcy",), (str(tmp_path / "absent"),)) == {}


def test_it_names_the_interpreter_that_has_the_module_not_merely_that_one_does() -> None:
    """The whole value is the PATH: "install it again" vs "your install went somewhere else" is the
    difference between the fix and an hour spent moving away from it. A boolean cannot say that."""
    found = found_elsewhere(("json",), (sys.executable,))
    assert found == {"json": sys.executable}


# ---------------------------------------------------------------- the recorded half (§MI)


def _ledger(root, entries: dict) -> None:
    d = os.path.join(str(root), "tests", "detective")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "certificates.json"), "w", encoding="utf-8") as fh:
        json.dump(entries, fh)


def test_a_recorded_reason_is_read_without_importing_anything(tmp_path) -> None:
    """Only possible as of §MI. Before it, an invalid measurement was stored as a bare `ungateable`
    standing with no reason, so this probe would have had to import the target to find out — which
    §1 forbids. The capability and the fence arrived together."""
    _ledger(tmp_path, {"m.py::f": {"standing": "ungateable", "cut_reasons": ["target_load_failed"]}})
    assert recorded_cut_reasons(str(tmp_path)) == ("target_load_failed",)


def test_a_func_key_scopes_the_read_and_its_absence_unions_the_ledger(tmp_path) -> None:
    _ledger(
        tmp_path,
        {
            "m.py::f": {"cut_reasons": ["target_load_failed"]},
            "m.py::g": {"cut_reasons": ["collection_incomplete"]},
        },
    )
    assert recorded_cut_reasons(str(tmp_path), "m.py::f") == ("target_load_failed",)
    assert set(recorded_cut_reasons(str(tmp_path))) == {"target_load_failed", "collection_incomplete"}


def test_a_record_written_before_the_field_existed_contributes_nothing(tmp_path) -> None:
    """Absent is not empty (§MI). A pre-field record must not be read as "recorded, nothing cut" —
    this reader is the one place that distinction could quietly be destroyed."""
    _ledger(tmp_path, {"m.py::f": {"standing": "ungateable", "refusal": ""}})
    assert recorded_cut_reasons(str(tmp_path)) == ()


@pytest.mark.parametrize("payload", ["{not json", '"a string"', "[1, 2]", "null"])
def test_an_unreadable_or_malformed_ledger_is_no_ledger(tmp_path, payload) -> None:
    d = os.path.join(str(tmp_path), "tests", "detective")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "certificates.json"), "w", encoding="utf-8") as fh:
        fh.write(payload)
    assert recorded_cut_reasons(str(tmp_path)) == ()


def test_a_missing_ledger_is_no_ledger(tmp_path) -> None:
    assert recorded_cut_reasons(str(tmp_path)) == ()


def test_a_row_that_is_not_a_mapping_is_skipped_rather_than_fatal(tmp_path) -> None:
    _ledger(tmp_path, {"m.py::f": "not-a-dict", "m.py::g": {"cut_reasons": ["budget_exhausted"]}})
    assert recorded_cut_reasons(str(tmp_path)) == ("budget_exhausted",)


# ---------------------------------------------------------------- pytest


def test_pytest_is_importable_in_the_interpreter_running_this_suite() -> None:
    """Tautological here by construction — pytest is running — and that is the point: the probe
    agrees with observable reality, so a False from it on a user's machine means something."""
    assert pytest_importable() is True
