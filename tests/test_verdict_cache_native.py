"""The verdict key must include the code that PRODUCED the verdict.

`cache_key`'s own law is "a verdict must be keyed on everything that could have produced it".
The engine was the gap: Wesker generates the mutants, runs the baseline and attributes the
kills, and Detective decides which categories exist at all — so an engine fix does not merely
make new verdicts better, it makes the old ones WRONG. Keyed blind to it, they are served back
as fresh. Measured on Regenesis: rows holding 2153 / 2138 / 2135 fabricated failures survived
the Wesker 0.7.2 upgrade that removed the bug which fabricated them.

Zero-arg and fixture-free (see `_support`): a fixture-dependent test contributes no kill power
under Wesker.
"""

from __future__ import annotations

from unittest.mock import patch

from Detective.verdict_cache import cache_key, engine_fingerprint, key_prefix, params_suffix


def _key(**over):
    args = dict(
        func_key="m.py::f",
        func_source="def f(): pass",
        tests=[],
        max_per_category=0,
        pass_index=0,
        trace_budgets=(50.0, 1800.0),
    )
    args.update(over)
    return cache_key(**args)


def test_engine_fingerprint_names_both_engines():
    """Both versions matter: Wesker runs the mutants, Detective chooses which exist."""
    fp = engine_fingerprint()
    assert fp.startswith("d")
    assert "+w" in fp
    detective_ver, wesker_ver = fp[1:].split("+w")
    assert detective_ver and wesker_ver
    assert ":" not in fp, "a ':' would corrupt the key's field layout"


def test_the_key_contains_the_engine_fingerprint():
    assert engine_fingerprint() in _key()


def test_a_wesker_upgrade_invalidates_the_verdict():
    """THE REGRESSION: the same function, same tests, same budgets, a different ENGINE is a
    different verdict. Before this, a bug's fabricated results outlived the fix."""
    with patch("Detective.verdict_cache.engine_fingerprint", return_value="d0.5.4+w0.7.1"):
        old = _key()
    with patch("Detective.verdict_cache.engine_fingerprint", return_value="d0.5.4+w0.7.2"):
        new = _key()
    assert old != new, "an engine upgrade must miss the cache, not serve the old verdict"


def test_a_detective_upgrade_invalidates_the_verdict():
    """Detective's own purity/category logic decides which mutants exist, so it is part of the
    producing code too."""
    with patch("Detective.verdict_cache.engine_fingerprint", return_value="d0.5.3+w0.7.2"):
        old = _key()
    with patch("Detective.verdict_cache.engine_fingerprint", return_value="d0.5.4+w0.7.2"):
        new = _key()
    assert old != new


def test_the_same_engine_still_hits():
    """The cache must still BE a cache: identical question + identical engine = identical key."""
    assert _key() == _key()


def test_the_engine_does_not_disturb_the_functions_purge_prefix():
    """`key_prefix` drives single-valid-copy purging; the fingerprint sits AFTER it, so a
    function's rows — including its old-engine ones — remain purgeable."""
    assert _key().startswith(key_prefix("m.py::f"))


def test_the_engine_does_not_disturb_the_trailing_param_suffix():
    """`params_suffix` is the key's second reader and rsplits from the END. The fingerprint is
    inserted at the FRONT, so two runs differing only in engine still share a params suffix
    (same question) — and are evicted as stale copies, not kept as siblings."""
    with patch("Detective.verdict_cache.engine_fingerprint", return_value="d0.5.4+w0.7.1"):
        old = _key()
    with patch("Detective.verdict_cache.engine_fingerprint", return_value="d0.5.4+w0.7.2"):
        new = _key()
    assert params_suffix(old) == params_suffix(new)


def test_different_budgets_remain_different_questions():
    """The pre-existing law must survive the insertion: budgets still separate keys."""
    assert _key(trace_budgets=(50.0, 1800.0)) != _key(trace_budgets=(None, None))


def test_an_edit_to_the_function_still_misses():
    assert _key(func_source="def f(): pass") != _key(func_source="def f(): return 1")
