"""A verdict is keyed on the pytest regime it was measured under, and absent-regime never thrashes (#63).

Increment 2 of #63: `cache_key` omitted the pytest execution regime (plugins / import-mode / rootdir /
ini), so a warm verdict measured under one regime could be served to a run under another. It now folds
in a regime digest via the pinned `regime_keyed`. The load-bearing decision is the EMPTY case: outside a
live session, or against an older Wesker that cannot report the regime, the digest is "" and the key must
stay byte-identical — an unknown regime is "no new information", not "a different regime", and silently
rewriting every key would drop the whole warm cache (the unnamed-capability assumption #60 forbids).
Pinned from intent, not from current output.
"""

from __future__ import annotations

from Detective.verdict_cache import cache_key, regime_keyed, wesker_policy_id


def _t():  # a throwaway test callable — cache_key fingerprints the list, not what it asserts
    pass


def test_regime_keyed_appends_only_a_present_digest():
    """The pure fold: an empty digest is identity; a present one appends. Two conditions that mean
    different things (unknown regime vs a specific regime) must not collapse."""
    assert regime_keyed("base", "") == "base"
    assert regime_keyed("base", "d1") == "base:d1"


def test_absent_regime_leaves_the_key_byte_identical():
    """Backward-compat / release-skew guard: the default (empty) regime yields exactly the pre-#63
    key, so an older Wesker or a call outside a live session invalidates nothing."""
    args = ("mod.py::g", "def g(): ...", [_t], 3, 0, (None, None))
    assert cache_key(*args, "") == cache_key(*args)
    assert cache_key(*args, "abc") == cache_key(*args) + ":abc"


def test_a_different_regime_keys_a_verdict_apart():
    """The point of the increment: identical code/tests/budgets under DIFFERENT regimes are different
    results, so their keys differ and one is never served for the other."""
    args = ("mod.py::g", "def g(): ...", [_t], 3, 0, (None, None))
    assert cache_key(*args, "regimeA") != cache_key(*args, "regimeB")
    assert cache_key(*args, "regimeA") == cache_key(*args, "regimeA")


def test_a_shaped_deferred_run_keys_apart_from_a_full_run():
    """shaped-defer: a DEFERRED run measures a smaller speculative pool (widen + capture) than a full
    one, so it is a different result. `include_shaped` must key them apart, or an --include-shaped
    request is served the stale deferred under-count (the symptom: the re-run for the full measurement
    returns the deferred one unchanged). The default (True, measure-everything) leaves the key
    byte-identical, so no warm entry is dropped — the same absent-value contract as the regime digest."""
    args = ("mod.py::g", "def g(): ...", [_t], 3, 0, (None, None))
    # Default (measure everything) == the pre-shaped-defer key: nothing invalidated.
    assert cache_key(*args, "", include_shaped=True) == cache_key(*args)
    # A deferred run is a DIFFERENT result — keyed apart, never served to the full request.
    assert cache_key(*args, "", include_shaped=False) != cache_key(*args, "", include_shaped=True)
    assert cache_key(*args, "", include_shaped=False) == cache_key(*args) + ":defer_shaped"


def test_a_two_sign_run_keys_apart_from_a_one_sign_run():
    """The two-sign contract σ(P, μ ∪ μ⁻) profiles a strictly LARGER universe (the μ⁻ OUTPUT
    operator) than the one-sign default, so it is a different result and must key apart — else a
    two-sign verdict is served to a one-sign request, or the reverse. The default (False) leaves the
    key byte-identical, so no warm one-sign entry is invalidated."""
    args = ("mod.py::g", "def g(): ...", [_t], 3, 0, (None, None))
    # Default (one-sign) == the pre-two-sign key: nothing invalidated.
    assert cache_key(*args, "", two_sign=False) == cache_key(*args)
    # A two-sign run is a DIFFERENT (larger) universe — keyed apart, never served across.
    assert cache_key(*args, "", two_sign=True) != cache_key(*args, "", two_sign=False)
    assert cache_key(*args, "", two_sign=True) == cache_key(*args) + ":two_sign"


def test_wesker_policy_id_names_the_two_sign_policy():
    """A two-sign converge/certify must stamp the σ(P, μ ∪ μ⁻) policy id, not the one-sign default —
    else the certificate names the wrong universe it was measured over. Skipped on a Wesker that
    predates the two-sign policy (the same version-skew guard the cross-repo tests use)."""
    import inspect

    from Wesker import mutation_policy

    if "two_sign" not in inspect.signature(mutation_policy).parameters:
        import pytest

        pytest.skip("installed Wesker predates the two-sign policy")
    one, two = wesker_policy_id(), wesker_policy_id(two_sign=True)
    assert one and two and two != one
    assert "+neg" in two and "+neg" not in one
