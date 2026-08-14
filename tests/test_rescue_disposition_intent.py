"""Witness-pass early termination: don't run the whole covering suite to hunt a literal a grid can't
synthesize — ask for --input instead.

The pool-poverty rescue (`classify_survivors`) captures real inputs by RUNNING the covering tests.
That is valuable for STRUCTURED inputs a grid cannot fabricate, but futile when the function is
grid-friendly and the residual is just a literal the grid didn't try (it burned the full --deadline
on ARC-scale suites). `rescue_disposition` decides; the generated golden characterizes it, and this
asserts INTENT — including that the rescue's real value is preserved.
"""

from Detective.engine import rescue_disposition


def test_grid_friendly_with_no_inexpressible_witness_skips_and_asks_for_input():
    # install_extra_target's shape: a literal input exercises it, the survivors are literal-value
    # mutants no synthesized input hits -> skip the suite-wide capture, ask for --input.
    assert (
        rescue_disposition(expressible=True, rescuable=True, has_inexpressible_witness=False)
        == "skip_ask_input"
    )


def test_an_inexpressible_witness_still_runs_the_rescue():
    # a witness only a test can build (a domain object) -> the capture may supply it; keep the rescue.
    assert rescue_disposition(expressible=True, rescuable=True, has_inexpressible_witness=True) == "run"


def test_a_non_literal_exercising_input_still_runs_the_rescue():
    # expressible=False: the function was exercised only by a captured object, not a literal grid
    # value -> a structured-input function, exactly where the rescue earns its cost.
    assert rescue_disposition(expressible=False, rescuable=True, has_inexpressible_witness=False) == "run"


def test_not_rescuable_is_nothing():
    assert rescue_disposition(expressible=True, rescuable=False, has_inexpressible_witness=False) == "nothing"
    assert rescue_disposition(expressible=False, rescuable=False, has_inexpressible_witness=True) == "nothing"
