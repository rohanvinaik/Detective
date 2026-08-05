"""Off-terminal progress heartbeat (issue #19).

Field shape: two converges of a heavy-import module ran 15-25 minutes with a
tee'd log that stayed EMPTY until completion — off-terminal, the in-place
progress line had nowhere to redraw, so the callback printed first + last and
nothing between. "Running" and "hung" were distinguishable only by ps. The
fix: off-terminal frames emit a newline-terminated heartbeat, throttled to
one per 15s so CI logs stay bounded.
"""

from __future__ import annotations

import Detective.cli as cli


def _drive(monkeypatch, capsys, frames):
    monkeypatch.setattr(cli, "_interactive_stderr", lambda: False)
    monkeypatch.setattr(cli, "_read_per_mutant_ms", lambda: None)
    monkeypatch.setattr(cli, "_update_per_mutant_ms", lambda _ms: None)
    cb = cli._stream_progress("serialize_rule")
    for done, total, elapsed_ms in frames:
        cb(done, total, elapsed_ms)
    return capsys.readouterr().err


def test_off_terminal_emits_throttled_heartbeats(monkeypatch, capsys):
    err = _drive(
        monkeypatch,
        capsys,
        [
            (0, 26, 0.0),  # opener is live-only — silent off-terminal
            (5, 26, 5_000.0),  # first intermediate frame → heartbeat
            (6, 26, 7_000.0),  # 2s later → throttled
            (14, 26, 21_000.0),  # 16s after last emit → heartbeat
            (26, 26, 30_000.0),  # completion line
        ],
    )
    beats = [ln for ln in err.splitlines() if "(heartbeat)" in ln]
    assert len(beats) == 2, err
    assert "5/26" in beats[0]
    assert "14/26" in beats[1]
    # Every off-terminal line is newline-terminated — no partial lines in logs.
    assert not err.endswith(" ")
    assert "26/26" in err.splitlines()[-1]
    assert "done in" in err.splitlines()[-1]


def test_off_terminal_short_run_stays_quiet(monkeypatch, capsys):
    # A fast run (all frames inside the throttle window) keeps the old
    # first+last economy: one completion line, no heartbeat spam.
    err = _drive(
        monkeypatch,
        capsys,
        [(0, 8, 0.0), (3, 8, 400.0), (6, 8, 900.0), (8, 8, 1_200.0)],
    )
    lines = [ln for ln in err.splitlines() if ln.strip()]
    heartbeats = [ln for ln in lines if "(heartbeat)" in ln]
    assert len(heartbeats) == 1  # the first intermediate frame anchors "alive"
    assert "done in" in lines[-1]
