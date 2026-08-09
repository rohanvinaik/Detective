"""A refusal must reach the surfaces a user reads, in one vocabulary (issue #60).

`MeasurementValidity` gave Detective one authoritative answer. An answer nothing renders is the
same defect one layer along: `last_session_manifest()` had zero consumers for an entire release
(#58), and `line_basis` was recorded on the result while nothing printed it (#59). A signal that
is computed and not surfaced is indistinguishable, to the person reading the output, from a
signal that was never computed.

TWO PROPERTIES, and both were violated by the banner this replaces.

EVERY reason, not just the first. The old branch re-derived the wording from
`collection_conflicts` and fell through to a single generic sentence about coverage depth — so a
run cut for two causes named one. The reader fixes it, re-runs, meets the second, and has no way
to know it was there all along.

ONE owner for the wording. #60 requires CLI, --json, MCP and receipts to preserve IDENTICAL cut
reasons. Two renderers of one vocabulary is how "the CLI said the worker was uncontained and the
receipt said the budget ran out" happens, and a reader reconciling two accounts of one refusal
cannot tell which is the measurement.
"""

from __future__ import annotations

import dataclasses

from Detective.cli import _final_banner
from Detective.converge import ConvergeResult
from Detective.validity import CUT_REASONS, cut_reason_sentence

# Same shape as `test_line_basis_banner._COMPLETE` — the repo's existing minimal complete
# result — rather than a second hand-rolled fixture that could drift from it.
_BASE = dict(
    function="x.py::f",
    converged=True,
    at_ceiling=True,
    initial_survivors=0,
    final_survivors=0,
    iterations=(),
    written_path="",
    functionally_complete=True,
    line_complete=True,
    total_mutants=4,
    killed=4,
)


def _result(**over) -> ConvergeResult:
    return ConvergeResult(**{**_BASE, **over})


# ── the vocabulary ──


def test_every_declared_reason_has_a_sentence():
    """A reason with no rendering cannot be shown consistently anywhere."""
    for reason in CUT_REASONS:
        sentence = cut_reason_sentence(reason)
        assert sentence and reason not in sentence, reason


def test_an_unknown_reason_degrades_to_a_named_unknown_not_a_blank():
    """A blank beside a refusal reads as 'no reason', which is the failure this vocabulary
    exists to prevent. A future engine's reason must be visible-but-unrecognised."""
    got = cut_reason_sentence("some_future_reason")
    assert got.strip()
    assert "some_future_reason" in got


def test_distinct_reasons_read_distinctly():
    """A truncated universe sends the reader to `--deadline`; an ambiguous module identity sends
    them to their import layout. Interchangeable wording sends them to the wrong place."""
    assert cut_reason_sentence("coverage_truncated") != cut_reason_sentence("ambiguous_module_identity")
    assert cut_reason_sentence("uncontained_worker") != cut_reason_sentence("budget_exhausted")


# ── the banner ──


def test_the_banner_names_every_reason_not_only_the_first():
    """THE regression."""
    banner = _final_banner(
        _result(
            measurement_gateable=False,
            cut_reasons=("uncontained_worker", "ambiguous_module_identity"),
        )
    )
    assert "UNGATEABLE" in banner
    assert cut_reason_sentence("uncontained_worker") in banner
    assert cut_reason_sentence("ambiguous_module_identity") in banner


def test_an_ungateable_run_never_reads_as_complete():
    """Absorbing, on the line people grep and quote. `11/11 killed` with a COMPLETE beside it
    would be a certificate over a measurement the engine disowned."""
    banner = _final_banner(_result(measurement_gateable=False, cut_reasons=("coverage_truncated",)))
    assert "COMPLETE" not in banner
    assert "counts are a floor" in banner


def test_a_gateable_run_is_unaffected():
    """The common case must not grow a refusal it never had."""
    banner = _final_banner(_result())
    assert "UNGATEABLE" not in banner
    assert "COMPLETE" in banner


def test_a_result_without_reasons_still_renders_the_older_wording():
    """A hand-built or older result carries no `cut_reasons`. It must still say why it is
    ungateable rather than fall through to a bare refusal — absence of the new field is not
    absence of a reason."""
    banner = _final_banner(_result(measurement_gateable=False, collection_conflicts=("pkg.mod",)))
    assert "UNGATEABLE" in banner and "pkg.mod" in banner


# ── the other surface ──


def test_the_json_surface_carries_the_same_reasons():
    """`--json` serializes the result wholesale, so the reasons must travel ON it — not be
    re-derived by the renderer, which is what made two surfaces able to disagree."""
    payload = dataclasses.asdict(
        _result(measurement_gateable=False, cut_reasons=("budget_exhausted", "uncontained_worker"))
    )
    assert payload["cut_reasons"] == ("budget_exhausted", "uncontained_worker")
    assert payload["measurement_gateable"] is False


def test_the_default_is_no_reasons_so_existing_results_are_unchanged():
    assert ConvergeResult(**_BASE).cut_reasons == ()
