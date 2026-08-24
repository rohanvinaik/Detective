"""A collection error must degrade the measurement LOUDLY — never a silent shrink (Detective dogfood bug).

Defect: a test file that failed to COLLECT (an ImportError — a torch dep, a broken conftest) was silently
absent from the routed suite. The engine still reported ``is_gateable=True`` (it collected and ran the
survivors), so Detective read ``✓ COMPLETE`` over a floor missing tests the layout implies — and ``regime``
said the layout resolved cleanly, so nothing fired. This is a violation of the "degrade loudly" law: the
tool must never claim COMPLETE over a measurement it could not fully take.

The disclosure chain, pinned here: Wesker surfaces the erroring node-ids (``last_collection_errors``, its
own intent test); Detective attaches them to the result and ``normalize_validity`` turns a NON-EMPTY list
into the ``collection_incomplete`` cut reason — which makes the run ungateable (``admits_certificate`` False
→ ``certificate_standing`` "ungateable" → the CLI exits 3, invalid_measurement_rerun), the same class as a
budget cut. An older engine that does not report the field is flagged ``absent:collection_errors``, never
fabricated as "collection was complete".
"""

from __future__ import annotations

from Detective.converge import certificate_standing
from Detective.validity import cut_reason_sentence, measurement_cut_reasons, normalize_validity


class _Result:
    """Minimal Wesker-result stub; only the fields normalize_validity reads."""

    def __init__(self, **kw):
        self.is_gateable = kw.get("is_gateable", True)
        self.budget_exhausted = kw.get("budget_exhausted", False)
        self.coverage_depth = kw.get("coverage_depth", "profiled")
        self.all_contained = kw.get("all_contained", True)
        self.execution_mode = kw.get("execution_mode", "isolated")
        if "collection_errors" in kw:
            self.collection_errors = kw["collection_errors"]


# ── the pure decision ──
def test_a_collection_error_is_its_own_cut_reason():
    assert "collection_incomplete" in measurement_cut_reasons(
        True, True, False, "profiled", "contained", False, collection_incomplete=True
    )
    assert "collection_incomplete" not in measurement_cut_reasons(
        True, True, False, "profiled", "contained", False, collection_incomplete=False
    )


def test_the_reason_has_an_actionable_and_distinct_sentence():
    s = cut_reason_sentence("collection_incomplete")
    assert s and "collect" in s and "collection_incomplete" not in s
    # distinct from a truncated-coverage cut, which sends the reader to --deadline, not the imports.
    assert s != cut_reason_sentence("coverage_truncated")


# ── the end-to-end disclosure ──
def test_a_nonempty_collection_errors_list_makes_the_run_ungateable():
    v = normalize_validity(_Result(is_gateable=True, collection_errors=("tests/test_x.py",)))
    assert "collection_incomplete" in v.cut_reasons
    assert v.admits_certificate is False  # an engine-gateable run with a cut reason still cannot stand
    # the decision layer consumes it: ungateable outranks incomplete/complete.
    assert certificate_standing(True, True, False, False, False, admits_certificate=False) == "ungateable"


def test_a_clean_collection_is_observed_not_absent_and_still_gateable():
    v = normalize_validity(_Result(is_gateable=True, collection_errors=()))
    assert "collection_incomplete" not in v.cut_reasons
    assert "absent:collection_errors" not in v.capability_flags  # observed, 0 errors — not absent
    assert v.admits_certificate is True


def test_an_older_engine_without_the_field_is_flagged_absent_not_fabricated():
    v = normalize_validity(_Result(is_gateable=True))  # no collection_errors attribute at all
    assert "absent:collection_errors" in v.capability_flags
    assert "collection_incomplete" not in v.cut_reasons  # absence of the field is not a collection error
