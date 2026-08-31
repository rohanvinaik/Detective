"""Intent tests AND truth-table pins — Wave 5 / EXP-DS-006, warranted cross-language emission
(docs/theory/deterministic_sicp/ §8, §11 Q6).

What the code is FOR:

- The portability boundary IS the L boundary minus the target's numeric-model edges (Q6's v1
  answer, found rather than chosen): expressible values ride; a bigint beyond i64 or a
  non-finite float is skipped AND COUNTED (the modulo qualifier); a container is codec v2.
- The disposition keeps five states apart, and the order encodes the epistemics: not-run is a
  measurement (INVALID_MEASUREMENT, exit-3 class), a disagreement is determined-false
  (CHANGED), an empty observing set must not read preserved (VACUOUS — the vacuity
  discipline), and PRESERVED always names its observing set (full vs modulo-unportable).
- The codec never guesses: `c_literal` returns None off the portable set; the harness
  generator refuses a ledger it cannot render whole.
- The bridge abstains without a toolchain (the count_opcodes pattern); float comparison is
  exact BY DESIGN — the conservative failure is a false CHANGED, never a false PRESERVED.

Converge attempted against the settled tree post-landing; these tables stand as the pins.
"""

import shutil

import pytest

from Detective.emission import (
    CrossLangEmission,
    c_harness,
    c_literal,
    emission_disposition,
    run_c_gate,
    value_portability,
)

# ── value_portability ────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "value, expected",
    [
        (True, "portable"),
        (False, "portable"),
        (0, "portable"),
        (-(2**63), "portable"),  # i64 min, inclusive
        (2**63 - 1, "portable"),  # i64 max, inclusive
        (2**63, "numeric_model_risk"),  # one past the model's edge
        (-(2**63) - 1, "numeric_model_risk"),
        (1.5, "portable"),
        (float("nan"), "numeric_model_risk"),
        (float("inf"), "numeric_model_risk"),
        ("abc", "portable"),
        ([1, 2], "inexpressible"),  # containers are codec v2, named
        ({"a": 1}, "inexpressible"),
        (None, "inexpressible"),
    ],
)
def test_portability_truth_table(value, expected) -> None:
    assert value_portability(value) == expected


# ── emission_disposition ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "compiled, ran, mismatches, portable, skipped, expected",
    [
        (False, False, 0, 5, 0, "INVALID_MEASUREMENT"),  # did not compile: re-measure, no claim
        (True, False, 0, 5, 0, "INVALID_MEASUREMENT"),  # compiled but did not run: same class
        (True, True, 1, 5, 0, "CHANGED"),  # one disagreement is determined-false
        (True, True, 0, 0, 3, "VACUOUS"),  # empty observing set must NOT read preserved
        (True, True, 0, 4, 2, "PRESERVED_MODULO_UNPORTABLE"),  # names its partial observing set
        (True, True, 0, 6, 0, "PRESERVED_PORTABLE"),  # the full stated family rode and agreed
    ],
)
def test_disposition_truth_table(compiled, ran, mismatches, portable, skipped, expected) -> None:
    assert emission_disposition(compiled, ran, mismatches, portable, skipped) == expected


# ── c_literal (the codec's write half) ───────────────────────────────────────────────────────


def test_codec_renders_portables_and_refuses_the_rest() -> None:
    assert c_literal(True) == "1" and c_literal(False) == "0"  # bool BEFORE int: they differ
    assert c_literal(42) == "42LL"
    assert c_literal(1.5) == "1.5"
    assert c_literal('a"b\\c\nd') == '"a\\"b\\\\c\\nd"'  # the v1 escape set, byte-faithful
    assert c_literal([1]) is None  # the codec never guesses
    assert c_literal(2**63) is None  # numeric-model risk does not render


def test_harness_refuses_a_ledger_it_cannot_render_whole() -> None:
    em = CrossLangEmission("c", "long long f(long long x) { return x; }", "f", "pin", "w")
    assert c_harness(em, [((1,), 1), (([1],), 1)]) is None  # one bad row refuses the whole


# ── the bridge (toolchain-dependent; abstains honestly without one) ──────────────────────────

_CC = shutil.which("cc") is not None

_IDENTITY = CrossLangEmission(
    language="c",
    source="long long f(long long x) { return x + 1; }",
    entrypoint="f",
    environment="",
    warrant="seed",
)


@pytest.mark.skipif(not _CC, reason="no C toolchain — the gate abstains, which is itself the contract")
def test_bridge_round_trip_preserved(tmp_path) -> None:
    result = run_c_gate(_IDENTITY, [((1,), 2), ((41,), 42)], str(tmp_path))
    assert result["disposition"] == "PRESERVED_PORTABLE"
    assert result["environment"]  # the pin is recorded on every result


@pytest.mark.skipif(not _CC, reason="no C toolchain")
def test_bridge_detects_a_changed_implementation(tmp_path) -> None:
    result = run_c_gate(_IDENTITY, [((1,), 2), ((41,), 43)], str(tmp_path))
    assert result["disposition"] == "CHANGED"
    assert result["mismatches"][0]["args"] == [41]


@pytest.mark.skipif(not _CC, reason="no C toolchain")
def test_bridge_reads_a_broken_emission_as_invalid_measurement(tmp_path) -> None:
    broken = CrossLangEmission("c", "long long f(long long x) { return x +; }", "f", "", "w")
    result = run_c_gate(broken, [((1,), 2)], str(tmp_path))
    assert result["disposition"] == "INVALID_MEASUREMENT"  # a compile failure is never CHANGED


@pytest.mark.skipif(not _CC, reason="no C toolchain")
def test_bridge_skips_and_counts_unportable_obligations(tmp_path) -> None:
    result = run_c_gate(_IDENTITY, [((1,), 2), ((2**63,), 0)], str(tmp_path))
    assert result["disposition"] == "PRESERVED_MODULO_UNPORTABLE"
    assert result["skipped"] == 1  # counted, never silently dropped


@pytest.mark.skipif(not _CC, reason="no C toolchain")
def test_bridge_vacuous_when_nothing_can_ride(tmp_path) -> None:
    result = run_c_gate(_IDENTITY, [(([1],), [1])], str(tmp_path))
    assert result["disposition"] == "VACUOUS"  # zero obligations observed → never preserved
