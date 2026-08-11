"""A clock read through a renamed from-import is caught, and frozen at the binding actually consumed (#48-E).

`from time import time as clk` binds the clock FUNCTION directly into the target module. Patching the
`time` module attribute never reaches that binding — so BOTH the `--clock` freeze AND the perturbed-epoch
determinism probe that exists to catch a free clock miss it, and the free clock is falsely certified
deterministic (the residual of #39 that #48-E closes). `apply_clock` now also freezes any target-namespace
binding that IS a clock function, matched by IDENTITY, so the probe catches a free clock and `--clock`
freezes the real binding. (`import time as t` needs none of this — `t` is the module object, already
covered by the module-attribute patch.)
"""

from __future__ import annotations

import time as _t

from Detective.capabilities import apply_clock, restore_clock
from Detective.synthesis.characterization import _try_capture


def _renamed_from_import_reader():
    """Simulate a module that did ``from time import time as clk`` — its globals bind ``clk`` to the
    clock FUNCTION, and ``stamp`` reads it through that local binding."""
    ns: dict = {"clk": _t.time}
    exec("def stamp():\n    return int(clk())", ns)  # noqa: S102 — building a target module namespace
    return ns["stamp"], ns


def test_a_renamed_from_import_free_clock_is_detected_only_with_the_namespace():
    """The gap and its close: without the target namespace the perturbed probe patches the `time`
    module and misses the `clk` binding (false determinism); with it, the binding is perturbed by
    identity and the free clock is caught."""
    stamp, ns = _renamed_from_import_reader()
    missed = _try_capture(stamp, (), {})  # no namespace — the module patch cannot reach `clk`
    assert missed is not None and missed.clock_dependent is False  # documents the gap
    caught = _try_capture(stamp, (), {}, namespace=ns)
    assert caught is not None
    assert caught.clock_dependent is True, "a renamed-import free clock must read as clock-dependent"


def test_apply_clock_freezes_a_target_namespace_binding_by_identity_and_restores_it():
    """The freeze reaches the from-import binding itself, and restore puts it back to the real
    function exactly — no leak into the consumer's own tests."""
    ns: dict = {"clk": _t.time}
    saved = apply_clock(1000.0, ns)
    try:
        assert ns["clk"]() == 1000.0, "the freeze must reach the from-import binding, not just the module"
    finally:
        restore_clock(saved)
    assert ns["clk"] is _t.time, "restore must put the binding back to the real clock exactly"
