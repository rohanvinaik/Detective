"""Intent tests for wiring the observation channel into converge — at the HANDLER, once per invocation.

Design: `docs/INVOCATION_LEDGER.md` §6. The wiring exists so the routed next-action code can leave the
run, because a spiral is an identical code re-emitted over unchanged state and no single invocation can
see that.

The observation used to sit inside `_converge_action`, the page's renderer, so it fired only when that
renderer ran: a `--json` run, a `--full` run, and the stale and cut endings the terse page prints before
its action block recorded no outcome at all. It now sits where `_run_converge` holds the result and
computes the decision record once; the renderers consume that record and never observe. These tests
moved with it, and their intent did not change:

1. **An observation that changes the observed.** The whole warrant for a side effect beside a render
   path is that it is inert. If recording alters one character of output, one branch or one exit code,
   it has broken the thing it was added to watch. Pinned by comparing a fully rendered page against the
   same page produced with the channel drained, and crowded, between runs.
2. **A silently unwired channel.** `observe` could be imported, called, and reach nothing — the
   `defined-but-unused` failure this repo checks references for. A test that only asserts "output
   unchanged" passes just as well when the call was never made, so completeness is asserted directly:
   the code is recorded, exactly once, and it is the code the page routed on.
"""

from __future__ import annotations

import importlib
import types

import pytest

from Detective.cli import _converge_action, _run_converge
from Detective.converge import ConvergeResult
from Detective.ledger import reset_observations, take_observations


def _settled() -> ConvergeResult:
    """Reaches the settled DONE branch — every axis discharged, gateable, nothing outstanding."""
    return ConvergeResult("m.py::add", True, True, 0, 0, (), None, functionally_complete=True)


def _gap() -> ConvergeResult:
    """A real line gap with a gateable measurement — routes to "close_the_gap"."""
    return ConvergeResult(
        "m.py::add",
        False,
        False,
        2,
        2,
        (),
        None,
        functionally_complete=False,
        line_complete=False,
        missing_lines=(19, 21),
        signature="add(a, b)",
        param_names=("a", "b"),
    )


def _args(root) -> types.SimpleNamespace:
    """The namespace `converge`'s parser builds, for a terse run with no supplied input."""
    return types.SimpleNamespace(
        input=None,
        project_root=str(root),
        env=None,
        write_dir="tests/detective",
        max_iterations=3,
        clock=None,
        receiver_factory=None,
        fast=False,
        deadline=300.0,
        include_shaped=False,
        two_sign=False,
        isolated=False,
        json=False,
        full=False,
        verbose=False,
    )


@pytest.fixture
def handler(monkeypatch, tmp_path, capsys):
    """Run `_run_converge` — the handler, where the record is computed and the outcome recorded — over a
    fixed result, and hand back the page it printed. The MODULE is patched, not the package attribute:
    `Detective.converge` on the package is the re-exported function, and `_run_converge` imports the
    function from the module."""

    def run(result: ConvergeResult) -> str:
        monkeypatch.setattr(
            importlib.import_module("Detective.converge"), "converge", lambda *_a, **_k: result
        )
        _run_converge(_args(tmp_path), "m.py", "add")
        return capsys.readouterr().out

    return run


def test_the_routed_code_is_recorded_at_all(handler):
    """The channel is WIRED, not merely importable. A `defined-but-unused` observe() would pass every
    output-comparison test in this file while recording nothing."""
    reset_observations()
    handler(_settled())
    gathered = take_observations()
    assert gathered, "converge printed its page and recorded nothing"
    assert [(kind, verb) for kind, verb, _ in gathered] == [("outcome", "converge")]


def test_the_recorded_code_is_the_one_converge_actually_routed_on(handler):
    """Recording a plausible-looking code that is not the routed one would be worse than recording
    nothing: doctor would speak confidently from a fabrication."""
    reset_observations()
    handler(_settled())
    assert [code for _, _, code in take_observations()] == ["settled"]

    reset_observations()
    handler(_gap())
    assert [code for _, _, code in take_observations()] == ["close_the_gap"]


def test_observing_changes_no_rendered_output(handler):
    """THE warrant for a side effect beside a render path. Two runs over identical inputs must print
    byte-identical pages whether or not the channel was drained in between."""
    reset_observations()
    first = handler(_settled())
    take_observations()  # drain, so the second run starts from a different channel state
    second = handler(_settled())
    assert first == second


def test_a_full_channel_does_not_alter_the_next_render(handler):
    """Observations accumulate within a process. A page that read differently on a non-empty channel
    would make output depend on history — the one thing a verdict must never do."""
    reset_observations()
    clean = handler(_gap())
    for _ in range(50):
        handler(_gap())
    crowded = handler(_gap())
    assert clean == crowded
    take_observations()


def test_every_invocation_records_exactly_one_outcome(handler):
    """One invocation, one routing decision. More than one would make `outcome_disposition` read
    `ambiguous` and discard a good observation."""
    reset_observations()
    handler(_gap())
    assert len(take_observations()) == 1


def test_the_renderer_records_nothing():
    """The other half of the move. The page's renderer consumes the record and never observes — so a
    renderer reached twice in one invocation cannot record twice, and a page is the same text whether or
    not anything is watching."""
    reset_observations()
    out = _converge_action(_gap(), None)
    assert out[0].startswith("AUTHOR INPUTS:")
    assert take_observations() == ()
