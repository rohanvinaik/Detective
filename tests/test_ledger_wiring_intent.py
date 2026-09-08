"""Intent tests for wiring the observation channel into converge's render path.

Design: `docs/INVOCATION_LEDGER.md` §6. The wiring exists so the routed next-action code — which
`_converge_action` otherwise consumes and discards — can leave the run, because a spiral is an
identical code re-emitted over unchanged state and no single invocation can see that.

The founder's ruling (2026-09-08) was to build the gathering layer rather than thread the value
up through five rendering layers: production threading is shallow, but `_converge_action` returns
`list[str]` to ~12 pinned call sites across 5 intent files, and changing that shape would edit the
intent record to carry a value none of it is about.

The two defects these prevent, and only one of them is about the ledger:

1. **An observation that changes the observed.** The whole warrant for putting a side effect in a
   render path is that it is inert. If wiring alters one character of output, one branch or one
   exit code, it has broken the thing it was added to watch. Pinned by comparing a fully rendered
   action block against the same block produced with the channel drained between runs.
2. **A silently unwired channel.** `observe` could be imported, called, and reach nothing — the
   `defined-but-unused` failure this repo checks references for. A test that only asserts "output
   unchanged" passes just as well when the call was never made, so completeness is asserted
   directly: the code is recorded, and it is the code converge actually routed on.
"""

from __future__ import annotations

import types

from Detective.cli import _converge_action
from Detective.ledger import reset_observations, take_observations


def _complete_result():
    """Reaches the settled DONE branch — converge_next_action returns "settled"."""
    return types.SimpleNamespace(
        function="dsl.py::add",
        functionally_complete=True,
        verification=None,
        line_complete=True,
        missing_lines=(),
        stale_target=False,
        admits_certificate=True,
        written_path="tests/detective/test_dsl_add_synth.py",
        synthesized_only=False,
        environment_gated=(),
    )


def _gap_result():
    """A real line gap with a gateable measurement — routes to "close_the_gap".

    Shaped after the fixture in test_cli_journey_contract_intent.py: the gap renderer reads
    `signature` / `param_names` to build its input template, so a namespace without them raises
    before the routing decision is even reached.
    """
    return types.SimpleNamespace(
        function="dsl.py::add",
        functionally_complete=False,
        verification=None,
        line_complete=False,
        final_survivors=2,
        missing_lines=(19, 21),
        signature="add(a, b)",
        param_names=("a", "b"),
        stale_target=False,
        admits_certificate=True,
        written_path="tests/detective/test_dsl_add_synth.py",
        synthesized_only=False,
        environment_gated=(),
    )


def _rep(equivalent=()):
    return types.SimpleNamespace(
        equivalent=list(equivalent),
        killable=[],
        unclassified=[],
        inputs_expressible=True,
        load_failed=False,
        note="",
    )


def test_the_routed_code_is_recorded_at_all():
    """The channel is WIRED, not merely importable. A `defined-but-unused` observe() would pass
    every output-comparison test in this file while recording nothing."""
    reset_observations()
    _converge_action(_complete_result(), _rep())
    gathered = take_observations()
    assert gathered, "converge rendered an action block and recorded nothing"
    assert [(kind, verb) for kind, verb, _ in gathered] == [("outcome", "converge")]


def test_the_recorded_code_is_the_one_converge_actually_routed_on():
    """Recording a plausible-looking code that is not the routed one would be worse than
    recording nothing: doctor would speak confidently from a fabrication."""
    reset_observations()
    _converge_action(_complete_result(), _rep())
    assert [code for _, _, code in take_observations()] == ["settled"]

    reset_observations()
    _converge_action(_gap_result(), _rep())
    assert [code for _, _, code in take_observations()] == ["close_the_gap"]


def test_observing_changes_no_rendered_output():
    """THE warrant for a side effect in a render path. Two runs over identical inputs must
    produce byte-identical action blocks whether or not the channel was drained in between."""
    reset_observations()
    first = _converge_action(_complete_result(), _rep())
    take_observations()  # drain, so the second run starts from a different channel state
    second = _converge_action(_complete_result(), _rep())
    assert first == second


def test_a_full_channel_does_not_alter_the_next_render():
    """Observations accumulate within a process. A render that behaved differently on a non-empty
    channel would make output depend on history — the one thing a verdict must never do."""
    reset_observations()
    clean = _converge_action(_gap_result(), _rep())
    for _ in range(50):
        _converge_action(_gap_result(), _rep())
    crowded = _converge_action(_gap_result(), _rep())
    assert clean == crowded
    take_observations()


def test_every_render_records_exactly_one_outcome():
    """One invocation of the renderer, one routing decision. More than one would make
    `outcome_disposition` read `ambiguous` and discard a good observation."""
    reset_observations()
    _converge_action(_gap_result(), _rep())
    assert len(take_observations()) == 1
