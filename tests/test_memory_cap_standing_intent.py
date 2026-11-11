"""Intent: a memory cap that was requested and not applied is on the page and in `--json` (Wesker#45).

THE DEFECT. No Detective source read Wesker's `memory_standing`, Detective had no memory-limit flag, and
`converge --isolated` passed no `worker_mem_limit_mb`, so its workers ran uncapped and a platform that
refuses the limit (macOS) was never mentioned. A cap is a promise only if the OS keeps it.

THE RULING (Detective tasks 14.3a, B4): a memory-cap stop is a named cut, never a kill; a cap that was
requested and refused is said, with what it means. Nothing requested is not a refusal, so it says
nothing; a cap that held says nothing here (its cut is named by the measurement's own cut reasons).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from Detective import engine
from Detective.cli import _memory_cap_rows, memory_cap_request, memory_cap_text
from Detective.converge import ConvergeResult
from Detective.validity import normalize_validity


@pytest.mark.parametrize(
    ("standing", "limit", "says"),
    [
        ("telemetry_only", 512, True),
        ("telemetry_only", 1, True),
        ("telemetry_only", 0, False),  # nothing requested: not a refusal
        ("telemetry_only", -3, False),
        ("enforced", 512, False),  # the cap held
        ("cut", 512, False),  # the cap held and cut a mutant: named elsewhere
        ("n/a", 512, False),  # not isolated: there was no worker to cap
        ("", 512, False),  # the engine did not report: nothing is claimed
    ],
)
def test_the_row_exists_only_for_a_requested_cap_the_os_refused(standing, limit, says):
    text = memory_cap_text(standing, limit)
    assert bool(text) is says
    assert bool(_memory_cap_rows(standing, limit)) is says


@pytest.mark.parametrize(
    ("flag", "isolated", "mb"),
    [
        (None, True, 512),  # isolated and silent: Wesker's own default
        (None, False, 0),  # no worker, nothing to cap
        (0, True, 0),  # asking for uncapped is honoured
        (256, True, 256),
        (256, False, 256),  # still reaches the verification's isolated calls
        (-4, True, 0),
    ],
)
def test_the_request_is_the_flag_else_wesker_default_under_isolated(flag, isolated, mb):
    assert memory_cap_request(flag, isolated) == mb


def test_the_row_says_what_it_means():
    text = memory_cap_text("telemetry_only", 512)
    assert "512" in text
    assert "NOT applied" in text
    assert "observed, not bounded" in text


def test_validity_carries_the_engines_standing_and_absence_is_not_a_standing():
    assert (
        normalize_validity(SimpleNamespace(memory_standing="telemetry_only")).memory_standing
        == "telemetry_only"
    )
    assert normalize_validity(SimpleNamespace(memory_standing="enforced")).memory_standing == "enforced"
    # an engine that does not report the field, and one that reports the empty string, are both "not reported"
    assert normalize_validity(SimpleNamespace()).memory_standing == ""
    assert normalize_validity(SimpleNamespace(memory_standing="")).memory_standing == ""


def test_the_converge_result_carries_both_facts_into_json():
    fields = {f for f in ConvergeResult.__dataclass_fields__}
    assert {"memory_standing", "memory_limit_mb"} <= fields


def test_the_requested_cap_is_what_isolated_profiles_start_under():
    engine.set_worker_mem_limit_mb(0)
    assert engine.worker_mem_limit_mb() == 0
    engine.set_worker_mem_limit_mb(256)
    try:
        assert engine.worker_mem_limit_mb() == 256
        engine.set_worker_mem_limit_mb(-1)
        assert engine.worker_mem_limit_mb() == 0
    finally:
        engine.set_worker_mem_limit_mb(0)
