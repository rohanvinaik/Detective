"""A stale target or a failed verification must never render DONE from the terse CLI renderer.

`ConvergeResult.complete` and the MCP renderer already refuse a `stale` run (target moved under the
measurement) and an `unverified` one (the written suite did not run green under real pytest), via the
single `certificate_standing` derivation. But `_converge_action` — the terse CLI surface a greenfield
user actually reads — re-derived a narrower proxy from `functionally_complete` + `admits_certificate`
+ `missing_lines`, which cannot see `stale_target` or a failed `verification`. So a run whose source
changed under it, or whose generated suite did not verify, printed:

    DONE:  the suite pins every behaviour this function makes.

— a certificate over a source that no longer exists, or a suite that does not run. This is the
false-DONE class the counter-review flagged as still live. These tests drive `_converge_action`
end to end (not the pure decision alone) and assert it now consumes the standing, and — the control —
that a genuinely complete run is unaffected.
"""

from __future__ import annotations

from types import SimpleNamespace

from Detective.cli import _converge_action


def _result(**overrides):
    base = dict(
        function="p.py::quote",
        functionally_complete=True,
        missing_lines=(),
        line_complete=True,
        stale_target=False,
        verification=None,
        admits_certificate=True,
        synthesized_only=False,
        environment_gated=(),
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_a_stale_target_does_not_render_done():
    out = _converge_action(_result(stale_target=True), rep=None)
    assert out[0].startswith("STOP:")
    assert "changed" in out[0]
    assert any("detective converge 'p.py::quote'" in line for line in out)  # re-run the settled file
    assert not any(line.startswith("DONE:") for line in out)


def test_a_failed_verification_does_not_render_done():
    out = _converge_action(_result(verification=SimpleNamespace(ok=False, status="tests_failed")), rep=None)
    assert out[0].startswith("STOP:")
    assert "did not verify" in out[0] and "tests_failed" in out[0]
    assert any("detective converge 'p.py::quote'" in line for line in out)
    assert not any(line.startswith("DONE:") for line in out)


def test_a_genuinely_complete_run_still_renders_done():
    """The control: consuming the standing must not suppress a real certificate — a verified,
    non-stale, gateable, mutant-complete run still says DONE."""
    out = _converge_action(_result(verification=SimpleNamespace(ok=True, status="ok")), rep=None)
    assert out[0].startswith("DONE:")
