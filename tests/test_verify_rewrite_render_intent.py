"""Intent tests for the verify-rewrite STALE_RECEIPT render (Finding C, revalidation_2026-09-06.md).

The defect, observed on a greenfield clone: `verify-rewrite` on an UNCHANGED function returns the
correct verdict (STALE_RECEIPT) but the render (a) prints "· proof replay  the original suite ran
skipped on the rewritten source" — a replay that never ran, over a rewritten source that does not
exist — and (b) prints the "nothing was rewritten" fact TWICE (the verdict message and a reverse-
phrased note). These pin the fix from intent: the proof-replay row appears only when a replay RAN,
and the note line is suppressed when the verdict message already states it. Written from the defect,
not the code, so a regression that reintroduces either flips a test.
"""

from __future__ import annotations

from Detective.cli import _format_rewrite
from Detective.rewrite import (
    RewriteVerification,
    verify_rewrite_note_shown,
    verify_rewrite_replay_row_shown,
)

# ------------------------------------------------------------------ the pure decisions (truth tables)


def test_replay_row_shown_only_when_a_replay_ran():
    # A real replay status shows the row.
    assert verify_rewrite_replay_row_shown("passed") == "ran"
    assert verify_rewrite_replay_row_shown("failed") == "ran"
    assert verify_rewrite_replay_row_shown("no_tests") == "ran"
    # An early-return verdict never replays: "skipped" (STALE_RECEIPT / BASIS_MOVED) or "" (a
    # pre-replay refusal, INVALID_RECEIPT) → no row.
    assert verify_rewrite_replay_row_shown("skipped") == "skipped"
    assert verify_rewrite_replay_row_shown("") == "skipped"


def test_note_line_suppressed_only_for_stale_receipt():
    # STALE_RECEIPT's verdict message already states the note's fact → suppress the duplicate line.
    assert verify_rewrite_note_shown("STALE_RECEIPT") == "redundant"
    # Everywhere else the note carries real information (INVALID_RECEIPT's reason; BASIS_MOVED has no
    # verdict-message entry at all) → show it.
    assert verify_rewrite_note_shown("INVALID_RECEIPT") == "show"
    assert verify_rewrite_note_shown("BASIS_MOVED") == "show"
    assert verify_rewrite_note_shown("PRESERVED") == "show"


# ------------------------------------------------------------------ the render (_format_rewrite)


def _stale() -> RewriteVerification:
    # Exactly what `verify_rewrite` returns on an unchanged function (rewrite.py STALE_RECEIPT branch).
    return RewriteVerification(
        "STALE_RECEIPT",
        "m.py::f",
        "skipped",
        (),
        (),
        (),
        note="the current source is identical to the receipt's original — nothing was rewritten",
    )


def test_stale_receipt_render_has_no_phantom_proof_replay_row():
    out = _format_rewrite(_stale())
    assert "proof replay" not in out, out
    assert "on the rewritten source" not in out, out


def test_stale_receipt_render_states_nothing_was_rewritten_exactly_once():
    out = _format_rewrite(_stale())
    # The verdict message is present; the reverse-phrased note line is suppressed, so the "identical
    # to the receipt's original" fact appears once, not twice.
    assert "nothing was rewritten — the current source is identical to the receipt's original" in out
    assert out.count("identical to the receipt's original") == 1, out


def test_invalid_receipt_still_shows_its_reason_note():
    # The note is the REASON for INVALID_RECEIPT (the verdict message ends "see the reason below"),
    # so suppressing it there would strip the only explanation — it must still print.
    inv = RewriteVerification(
        "INVALID_RECEIPT",
        "m.py::f",
        "",
        (),
        (),
        (),
        note="wrong_function: receipt is for other.py::g",
    )
    out = _format_rewrite(inv)
    assert "wrong_function: receipt is for other.py::g" in out
    assert "proof replay" not in out  # no replay ran here either


def test_a_real_verdict_still_shows_the_proof_replay_row():
    preserved = RewriteVerification("PRESERVED", "m.py::f", "passed", (), (), (), note="")
    out = _format_rewrite(preserved)
    assert "proof replay" in out
    assert "the original suite ran passed on the rewritten source" in out
