"""A collection/config-load failure should name the SPECIFIC missing package, not say "install deps".

Found dogfooding structlog: it uses `--strict-config` and carries a pytest-asyncio ini option
(`asyncio_default_fixture_loop_scope`), so without the plugin pytest refuses the WHOLE config and
NOTHING collects. The old message ("install the project's dependencies") is too vague to act on when
the real fix is `pip install pytest-asyncio`. `plugin_hint` turns "install something" into "install
THIS".
"""

from __future__ import annotations

from Detective import cli
from Detective.cli import _format_session_warning, plugin_hint

# ── the pure decision ──


def test_a_bare_module_not_found_names_the_module_directly():
    assert plugin_hint("ModuleNotFoundError: No module named 'rich'") == "rich"
    assert plugin_hint("no module named 'pytest_asyncio'") == "pytest-asyncio"
    assert plugin_hint("no module named 'foo.bar.baz'") == "foo"  # top-level package only


def test_a_strict_config_ini_option_names_its_plugin():
    """The structlog case: no `no module named`, just an unknown ini option whose PREFIX is the
    plugin. `asyncio_default_fixture_loop_scope` -> pytest-asyncio."""
    assert plugin_hint("Unknown config option: asyncio_default_fixture_loop_scope") == "pytest-asyncio"
    assert plugin_hint("DJANGO_SETTINGS_MODULE is not set") == "pytest-django"


def test_an_unrecognised_error_yields_no_guess():
    """Absence over a bad guess: an error we don't recognise returns "", so the caller keeps the
    generic guidance rather than fabricate a package name."""
    assert plugin_hint("SyntaxError: invalid syntax") == ""
    assert plugin_hint("") == ""


# ── the render consumes it ──


def test_the_collection_error_warning_names_the_missing_plugin(monkeypatch):
    """End of the chain: a config-load failure whose detail carries the asyncio signature renders a
    `pip install pytest-asyncio` line, on top of the generic guidance.

    The plugin is fixed ABSENT. Since EP-E2 the render asks the running interpreter whether a named
    plugin is installed (`_installed_here`), so unfixed, this test's verdict was a read of whichever
    interpreter ran it: green under the project venv, red under miniconda's base, which carries
    pytest-asyncio (measured 2026-10-02). The installed branch is pinned in
    `test_session_warning_plugin_presence_intent.py`."""
    monkeypatch.setattr(cli, "_installed_here", lambda _pkg: False)
    diagnostic = {
        "reason": "collection_errors",
        "errors": [
            ("conftest/config load", "ERROR: Unknown config option: asyncio_default_fixture_loop_scope")
        ],
    }
    msg = _format_session_warning(diagnostic)
    assert "pytest-asyncio" in msg
    assert "uv pip install --python" in msg
    assert msg.count("pytest-asyncio") >= 2


def test_an_unrecognised_collection_error_keeps_the_generic_guidance():
    diagnostic = {
        "reason": "collection_errors",
        "errors": [("tests/test_x.py", "ImportError: cannot import name 'q' from 'x'")],
    }
    msg = _format_session_warning(diagnostic)
    # still names the import-failure remedy, but invents no package
    assert "install the project's dependencies" in msg
    assert "Likely missing:" not in msg
