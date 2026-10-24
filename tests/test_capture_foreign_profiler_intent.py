"""W#32: monitoring harvests coexist with a foreign legacy profiler without taking its hook.

The previous setprofile implementation had to refuse a C profiler state it could
not restore. Monitoring owns a separate tool ID. Keep the no-hook-theft obligation
and require real harvesting under both foreign C-state and Python-hook cases.
"""

from __future__ import annotations

import sys

from Detective import capture


class _ProfilerState:
    """What a C-level profiler leaves in the profile slot: an object, not a function."""


def _target(x):
    return x + 1


def _reaches():
    assert _target(1) == 2


def _never_install(*_a, **_k):
    raise AssertionError("the harvest must not take a hook it cannot hand back")


def test_the_input_harvest_coexists_with_an_unrestorable_hook(monkeypatch):
    state = _ProfilerState()
    monkeypatch.setattr(sys, "getprofile", lambda: state)
    monkeypatch.setattr(sys, "setprofile", _never_install)
    assert capture.capture_call_inputs(_target, [_reaches]) == [(1,)]
    assert sys.getprofile() is state


def test_the_return_type_harvest_coexists_with_an_unrestorable_hook(monkeypatch):
    state = _ProfilerState()
    monkeypatch.setattr(sys, "getprofile", lambda: state)
    monkeypatch.setattr(sys, "setprofile", _never_install)
    assert capture.capture_return_types(_target, [_reaches]) == frozenset({"int"})
    assert sys.getprofile() is state


def test_a_python_hook_is_still_borrowed_and_handed_back():
    """A callable foreign hook remains installed throughout the monitoring harvest."""
    seen: list[str] = []

    def theirs(_frame, event, _arg):
        seen.append(event)

    previous = sys.getprofile()
    sys.setprofile(theirs)
    try:
        assert capture.capture_call_inputs(_target, [_reaches]) == [(1,)]
        assert sys.getprofile() is theirs
    finally:
        sys.setprofile(previous)
