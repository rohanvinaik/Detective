"""Intent tests for doctor's YELLOW axis — the ceiling, and the mix that beats the sum.

Design: `docs/DOCTOR.md` §2 (yellow is max health, not healing), §3 (the superadditive products),
§7.4 (yellow's cost). Written from the design, not the code.

Yellow is the mapping that earns the herb scheme. Taste findings heal nothing — an entangled
function, an inexpressible parameter, a pure decision behind a heavy import: none of that is
damage, and all of it CAPS how much of Detective the code lets you reach. Getting that distinction
into the vocabulary is the whole point; a yellow row that reads like a defect has broken it.
"""

from __future__ import annotations

import json

import pytest

from Detective.cli import _TASTE_CODES, main
from Detective.doctor import taste_disposition
from Detective.survey import survey_disposition

# A heavy import that is NOT installed here — so this fixture legitimately produces a GREEN finding
# as well as a yellow one. That coupling is real, not an artefact: a module importing an absent heavy
# package genuinely has both a setup fault and a ceiling.
_TRAPPED = "import jax\n\n\ndef f(x):\n    if x <= 0:\n        return 0\n    return x * 2\n"
# YELLOW WITHOUT GREEN, and it took a measurement to find one. Every member of
# `survey._HEAVY_IMPORT_ROOTS` is absent from this venv, so no `trapped_by_imports` fixture can
# avoid tripping green too. `numpy` is installed (S11 declared it) and is NOT a heavy root, while
# `np.ndarray` IS in `_INEXPRESSIBLE_ROOTS` — so this caps the ceiling and leaves setup clean, on any
# machine that can run this suite.
_CAPPED = "import numpy as np\n\n\ndef f(x: np.ndarray):\n    if x.size:\n        return 1\n    return 0\n"
_CLEAN = "def add(a, b):\n    return a + b\n"


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "m.py").write_text(_CLEAN)
    return tmp_path


def _run(capsys, *args) -> tuple[int, str]:
    code = main(["doctor", *args])
    return code, capsys.readouterr().out


# ---------------------------------------------------------------- the ceiling, ranked


def test_the_ranking_is_surveys_own_consumed_not_restated() -> None:
    """§5's rule applied to yellow: a second reader of the same facts is the drift every repair in
    CORRECTNESS_REPAIRS turned out to be. `_TASTE_CODES` is the argument ORDER, bound to the
    vocabulary `survey_disposition` actually produces — a code here that survey never returns would
    be a count that is always zero, and a code survey returns that is missing here would be a
    finding that silently never caps anything."""
    produced = {
        survey_disposition(True, False, False),
        survey_disposition(False, True, False),
        survey_disposition(False, False, True),
        survey_disposition(False, False, False, True),
    }
    assert set(_TASTE_CODES) == produced


@pytest.mark.parametrize(
    ("counts", "expected"),
    [
        ((1, 1, 1, 1), "extractable_core"),
        ((0, 1, 1, 1), "impure_body"),
        ((0, 0, 1, 1), "trapped_by_imports"),
        ((0, 0, 0, 1), "unresolved_param"),
        ((0, 0, 0, 0), "clear"),
    ],
)
def test_the_highest_ceiling_leads(counts, expected) -> None:
    """Most-blocking first, and `unresolved_param` LAST among the findings on purpose: it is not a
    claim that anything is in the way, only that the question is open (R4). Ranking it above a
    proven block would put an unproven case behind a proven one's name."""
    assert taste_disposition(3, *counts) == expected


def test_nothing_scanned_is_not_the_same_as_nothing_found() -> None:
    """ "We looked and found nothing in the way" and "there was nothing to look at" are different
    facts with different meanings for the reader, and `plan` already names the second
    (`NOTHING_TO_READ`) rather than reporting a clean read of an empty set."""
    assert taste_disposition(0, 0, 0, 0, 0) == "nothing_to_read"
    assert taste_disposition(1, 0, 0, 0, 0) == "clear"


def test_a_negative_count_cannot_manufacture_a_clean_read() -> None:
    """Defensive on the SAFE side: a caller that computes a nonsense scan count must not get
    `clear`, which is the one answer that closes the axis."""
    assert taste_disposition(-1, 0, 0, 0, 0) == "nothing_to_read"


# ---------------------------------------------------------------- through the real command


def test_a_trapped_pure_decision_is_reported_as_a_ceiling_not_a_defect(repo, capsys) -> None:
    """The vocabulary IS the design. This code is not broken and runs perfectly; what it does is cap
    how much of the tool reaches it. A row that reads like a defect has lost the distinction that
    makes yellow worth having as its own axis."""
    (repo / "t.py").write_text(_TRAPPED)
    _, out = _run(capsys, "t.py", "--project-root", str(repo), "--yellow")
    assert "trapped_by_imports" in out
    assert "none of this is broken" in out
    assert "caps how much of Detective" in out


def test_it_names_the_command_that_raises_the_ceiling(repo, capsys) -> None:
    """Every doctor row must name the move. A finding whose remedy the reader has to infer is the
    gap doctor exists to close, not an instance of it."""
    (repo / "t.py").write_text(_TRAPPED)
    _, out = _run(capsys, "t.py", "--project-root", str(repo), "--yellow")
    assert "detective survey" in out
    assert "detective extract" in out


def test_a_clean_target_says_no_ceiling_found_and_refuses_to_praise_it(repo, capsys) -> None:
    """The fence, on yellow's side. "Nothing is capping what converge can reach" is a claim about
    REACH; "this code is good" is a claim about the code, which doctor must never make."""
    _, out = _run(capsys, "m.py", "--project-root", str(repo), "--yellow")
    assert "nothing found is capping" in out
    assert "never a claim that the code is good" in out


def test_yellow_degrades_at_directory_scope_WITH_its_reason(repo, capsys) -> None:
    """§7.4: taste costs a static pass per function, so it is read for a TARGET rather than swept.
    The degradation must be a REPORTED state — a silent skip is the same defect as an empty process
    section, and it is the one this whole surface exists to prevent."""
    _, out = _run(capsys, "--project-root", str(repo), "--yellow")
    assert "not read" in out
    assert "no target given" in out
    assert "detective doctor <file.py>" in out, "the degradation names how to get the read"


def test_a_scoped_target_reads_only_that_function(repo, capsys) -> None:
    both = (
        "import numpy as np\n\n\n"
        "def capped(x: np.ndarray):\n    if x.size:\n        return 1\n    return 0\n\n\n"
        "def plain(a, b):\n    if a > b:\n        return a\n    return b\n"
    )
    (repo / "two.py").write_text(both)
    _, scoped = _run(capsys, "two.py::plain", "--project-root", str(repo), "--yellow")
    _, whole = _run(capsys, "two.py", "--project-root", str(repo), "--yellow")
    assert "capped" in whole
    assert "capped" not in scoped, "a scoped read must not report a sibling's ceiling"


# ---------------------------------------------------------------- the mix, not the sum


def test_green_and_yellow_together_produce_a_verdict_neither_gives_alone(repo, capsys) -> None:
    """§3's whole argument. G+Y is UNRELIABILITY: a taste finding measured through a broken
    environment is measuring the ENVIRONMENT, so it must be re-derived after the fix rather than
    acted on. Three lists concatenated cannot say this; the ordering is the product."""
    (repo / "t.py").write_text(
        "import jax\nimport definitely_not_a_real_package_xyz\n\n\ndef f(x):\n    return x\n"
    )
    code, out = _run(capsys, "t.py", "--project-root", str(repo))
    assert code == 2
    assert "GREEN + YELLOW" in out
    assert "RE-DERIVE" in out
    assert "measured through that fault" in out


def test_the_product_stays_silent_when_only_one_axis_is_live(repo, capsys) -> None:
    """A line that always appears is a line nobody reads. The ordered-remediation block earns its
    space by being the thing two live axes make true, so one live axis must not print it."""
    (repo / "t.py").write_text(_CAPPED)
    _, yellow_only = _run(capsys, "t.py", "--project-root", str(repo))
    assert "extractable_core" in yellow_only, "yellow must actually be live for this to mean anything"
    assert "GREEN + YELLOW" not in yellow_only
    _, green_only = _run(capsys, "m.py", "--project-root", str(repo))
    assert "GREEN + YELLOW" not in green_only


def test_a_yellow_finding_never_changes_the_exit_code(repo, capsys) -> None:
    """Yellow raises a ceiling; it is not damage and it is not your world being wrong. Only a GREEN
    finding earns exit 2, or the code stops meaning what the table says it means."""
    (repo / "t.py").write_text(_CAPPED)
    code, out = _run(capsys, "t.py", "--project-root", str(repo))
    assert "extractable_core" in out
    assert code == 0, "a ceiling is not a fault"


def test_an_unparseable_target_yields_nothing_to_read_rather_than_raising(repo, capsys) -> None:
    (repo / "broken.py").write_text("def broken(:\n")
    code, out = _run(capsys, "broken.py", "--project-root", str(repo), "--yellow")
    assert code == 0
    assert "nothing_to_read" in out


def test_the_ledger_is_untouched_by_a_taste_read(repo, capsys) -> None:
    """Advisory, writes nothing — asserted separately for yellow because it is the axis that reads
    the most source and would be the easiest place to accidentally cache something."""
    (repo / "t.py").write_text(_TRAPPED)
    _run(capsys, "t.py", "--project-root", str(repo))
    assert not (repo / ".detective").exists()
    assert not (repo / "tests" / "detective").exists()


def test_a_recorded_green_fault_also_triggers_the_ordered_remediation(repo, capsys) -> None:
    """The G+Y product must key on the green DISPOSITION, not specifically on the dependency probe —
    a stale recorded failure is a green finding too, and a reader who acts on a taste finding
    measured through one has the same problem."""
    (repo / "t.py").write_text(_CAPPED)
    d = repo / "tests" / "detective"
    d.mkdir(parents=True, exist_ok=True)
    (d / "certificates.json").write_text(json.dumps({"t.py::f": {"cut_reasons": ["target_load_failed"]}}))
    code, out = _run(capsys, "t.py::f", "--project-root", str(repo))
    assert code == 2
    assert "stale_load_failure" in out
    assert "GREEN + YELLOW" in out
