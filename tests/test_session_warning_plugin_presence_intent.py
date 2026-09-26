"""A plugin an error names is not called missing when it is installed (EP-E2, docs/ENGINEERING_PASS).

The live-session warning turns a collection error into a remedy. When the error named a plugin
(`asyncio_*` → `pytest-asyncio`), it said "Install that plugin in this exact interpreter" — without
asking the interpreter. Measured 2026-09-26 under miniconda: `pytest-asyncio` 1.4.0 WAS installed, its
own configure hook warned, the project's `filterwarnings = ["error"]` made that fatal, and the advice
sent the reader to install the plugin that was already there and was the one raising. A false cause
is worse than silence (COMMUNICATING_DETERMINISM §3.1).

Pinned from intent: installed → the text says so and offers no install; absent → the install command
stands, unchanged; the real probe answers for this interpreter and never raises.
"""

from __future__ import annotations

from Detective import cli

_ASYNCIO_CONFIG = {
    "reason": "collection_errors",
    "errors": [("tests/test_x.py", "PytestConfigWarning: asyncio_default_fixture_loop_scope is unset")],
}
_ASYNCIO_IMPORT = {
    "reason": "collection_errors",
    "errors": [("conftest.py", "ImportError loading conftest: cannot import name 'x' from pytest_asyncio")],
}


def test_an_installed_plugin_is_never_told_to_be_installed(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "_installed_here", lambda _pkg: True)
    text = cli._format_session_warning(_ASYNCIO_CONFIG, str(tmp_path))
    assert "Install that plugin" not in text and "uv pip install" not in text
    assert "`pytest-asyncio` IS installed" in text
    assert "The failures above are the installed plugin's own" in text


def test_an_absent_plugin_keeps_its_install_command(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "_installed_here", lambda _pkg: False)
    text = cli._format_session_warning(_ASYNCIO_CONFIG, str(tmp_path))
    assert "Install that plugin" in text
    assert "pytest-asyncio" in text and "uv pip install --python" in text


def test_an_import_failure_naming_an_installed_package_does_not_call_it_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "_installed_here", lambda _pkg: True)
    text = cli._format_session_warning(_ASYNCIO_IMPORT, str(tmp_path))
    assert "Likely missing" not in text
    assert "IS installed in this interpreter" in text and "not for want of it" in text


def test_an_error_that_names_nothing_keeps_the_generic_hint(monkeypatch, tmp_path):
    """`unnamed`: nothing to install, nothing to point at — the probe is not even asked."""

    def _never(_pkg):
        raise AssertionError("nothing was named, so there is nothing to probe")

    monkeypatch.setattr(cli, "_installed_here", _never)
    unnamed = {"reason": "collection_errors", "errors": [("tests/test_y.py", "some unrelated failure")]}
    text = cli._format_session_warning(unnamed, str(tmp_path))
    assert "testpaths" in text


def test_the_real_probe_answers_for_this_interpreter_and_never_raises():
    assert cli._installed_here("pytest") is True
    assert cli._installed_here("surely-not-an-installed-distribution-xyz") is False
    assert cli._installed_here("..not a module path..") is False
