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

from Detective.verdict_cache import cache_key, regime_keyed


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
