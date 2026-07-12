"""Shared pytest configuration for the Detective suite.

Test-support builders live in ``tests/_support.py`` as plain functions, not
fixtures: a fixture-dependent test contributes no mutation kill power under
Wesker (its discovery skips tests needing real fixtures), so tests that must pin
survivors call the helpers directly.
"""

from __future__ import annotations
