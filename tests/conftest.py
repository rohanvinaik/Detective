"""Shared pytest configuration for the Detective suite.

Test-support builders live in ``tests/_support.py`` as plain functions, not
fixtures: a fixture-dependent test contributes no mutation kill power under
Wesker (its discovery skips tests needing real fixtures), so tests that must pin
survivors call the helpers directly.
"""

from __future__ import annotations

import os
import sys
import tempfile

import pytest

_TEMP = os.path.realpath(tempfile.gettempdir())


@pytest.fixture(autouse=True)
def _a_temp_project_leaves_no_trace():
    """A throwaway project a test builds under the temp dir must not outlive that test in the
    interpreter (EP-H4 — docs/ENGINEERING_PASS_2026-09-26.md).

    Dozens of tests build a project with the same module names (30 files write an ``m.py``, 17 a
    ``mod.py``) and profile it in THIS process. A library-level ``profile()`` leaves two pieces of
    process-global state behind: the project's modules in ``sys.modules`` and its root on ``sys.path``.
    A later test's ``from m import f`` then binds the PREVIOUS project's ``f`` — the stale module if it
    is still cached, the stale file through ``sys.path`` if it is not — and measures code it never
    wrote: its tests covered ``[]`` of its own lines and killed 0 of 7 mutants. Serial file order hid
    it; an 8-worker run and a pairwise bisection exposed it (three predecessor files break
    ``test_basis_admitted_witnesses_intent``). Each leak alone was measured insufficient to cause
    it; restoring both fixes all three pairs — the same snapshot-and-restore pytest's own ``pytester``
    applies around an in-process run.

    Function scope, so a module- or session-scoped fixture's own ``sys.path`` entries are already in
    the snapshot and survive. Autouse never enters a test's signature, so Wesker's legacy discovery
    still reads the suite's tests as zero-argument (see the module docstring above). Only modules
    ADDED during the test whose file lives under the temp dir are evicted; Detective, Wesker and the
    suite's own modules are never touched. The product-level form of the same obligation — a
    top-level profile cleaning up after itself — is a founder call recorded in the document.
    """
    modules_before = set(sys.modules)
    path_before = list(sys.path)
    yield
    sys.path[:] = path_before
    for name in set(sys.modules) - modules_before:
        module_file = getattr(sys.modules.get(name), "__file__", None)
        if module_file and os.path.realpath(module_file).startswith(_TEMP):
            sys.modules.pop(name, None)
