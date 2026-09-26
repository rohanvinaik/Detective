"""A harvest never takes a profile hook it cannot give back (EP-B2 — docs/ENGINEERING_PASS_2026-09-26.md).

The capture harvests save ``sys.getprofile()``, install their own hook, and restore the saved one. A
C-level profiler (pyinstrument) leaves a NON-callable state object in that slot, and
``sys.setprofile`` refuses it on the way back: measured, ``TypeError: 'ProfilerState' object is not
callable`` ended a whole ``detective converge`` run under pyinstrument. Pinned here from intent: with an
unrestorable hook present, each harvest declines — returns nothing, never calls ``sys.setprofile``, and
says why on stderr, so "a profiler holds the hook" never reads like "no test reaches this function".

A non-callable hook can only be installed from C, so the slot is stood in for by patching
``sys.getprofile``; the end-to-end check under a real pyinstrument run is recorded in the commit.
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


def test_the_input_harvest_declines_an_unrestorable_hook(monkeypatch, capsys):
    monkeypatch.setattr(sys, "getprofile", lambda: _ProfilerState())
    monkeypatch.setattr(sys, "setprofile", _never_install)
    assert capture.capture_call_inputs(_target, [_reaches]) == []
    assert "profiler holds the process profile hook" in capsys.readouterr().err


def test_the_return_type_harvest_declines_an_unrestorable_hook(monkeypatch, capsys):
    monkeypatch.setattr(sys, "getprofile", lambda: _ProfilerState())
    monkeypatch.setattr(sys, "setprofile", _never_install)
    assert capture.capture_return_types(_target, [_reaches]) == frozenset()
    assert "the return-type harvest was skipped" in capsys.readouterr().err


def test_a_python_hook_is_still_borrowed_and_handed_back():
    """The ordinary path is unchanged: a callable hook is displaced for the harvest and restored."""
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
