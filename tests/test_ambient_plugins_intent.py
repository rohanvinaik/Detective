"""#98: `regime` and `doctor` disclose the auto-loaded pytest plugins the project never declared.

THE DEFECT (Detective#98, EP-C4): Detective opens an in-process pytest session under its own interpreter, and
pytest loads every installed `pytest11` entry point into it. In a dev interpreter carrying asyncio, anyio,
codeflash-benchmark, jaxtyping, logfire, memray and timeout, the same commit read 25 failed against 3228
passed in the locked environment, and a converge did 2.2x the work. Neither `detective regime` nor
`detective doctor` said a word. Founder ruling: DISCLOSE, never disable.

The state is constructed with a fake distribution on `sys.path` (a `.dist-info` with an entry_points.txt), so
nothing is installed into any shared environment. The suite sets PYTEST_DISABLE_PLUGIN_AUTOLOAD for its own
nested sessions, so each test that reads the real standing unsets it.
"""

from __future__ import annotations

import json
import re
import types

import pytest

from Detective import cli
from Detective.plugins import (
    AUTOLOAD_OFF,
    BLOCKED,
    DECLARED,
    EXPLICIT,
    STANDING_SAID,
    UNDECLARED,
    AmbientPlugin,
    ambient_plugins,
    declared_distributions,
    known_effect,
    normalize_requirement,
    plugin_declaration,
    plugin_flags,
    plugin_rows,
    undeclared,
)
from Detective.regime import resolve_regime


def _dist(root, name: str, version: str, entry: str, module: str) -> None:
    info = root / f"{name.replace('-', '_')}-{version}.dist-info"
    info.mkdir(parents=True)
    (info / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n", encoding="utf-8"
    )
    (info / "entry_points.txt").write_text(f"[pytest11]\n{entry} = {module}\n", encoding="utf-8")


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A project that declares pytest-timeout only, and a sys.path carrying three fake plugins."""
    fake = tmp_path / "site"
    fake.mkdir()
    _dist(fake, "pytest-fakeslow", "2.3", "fakeslow", "pytest_fakeslow")
    _dist(fake, "pytest-timeout", "9.9", "timeout", "pytest_timeout")
    _dist(fake, "pytest-asyncio", "1.0", "asyncio", "pytest_asyncio")
    monkeypatch.syspath_prepend(str(fake))
    monkeypatch.delenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", raising=False)
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    monkeypatch.delenv("PYTEST_PLUGINS", raising=False)
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "pyproject.toml").write_text(
        '[project]\nname = "proj"\nversion = "0"\ndependencies = ["Pytest_Timeout>=1"]\n'
        '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n',
        encoding="utf-8",
    )
    return proj


def _by_name(plugins):
    return {p.name: p for p in plugins}


# ------------------------------------------------------------- the pure decision


@pytest.mark.parametrize(
    ("blocked", "explicit", "off", "declared", "expected"),
    [
        (False, False, False, False, UNDECLARED),
        (False, False, False, True, DECLARED),
        (False, False, True, False, AUTOLOAD_OFF),
        (False, False, True, True, AUTOLOAD_OFF),  # the switch outranks declaration: it does not load
        (False, True, False, False, EXPLICIT),
        (False, True, True, False, EXPLICIT),  # `-p name` loads even with autoload off
        (True, False, False, False, BLOCKED),
        (True, True, True, True, BLOCKED),  # a block wins over everything
    ],
)
def test_plugin_declaration_precedence(blocked, explicit, off, declared, expected) -> None:
    assert plugin_declaration(blocked, explicit, off, declared) == expected


def test_every_standing_has_its_own_sentence() -> None:
    assert set(STANDING_SAID) == {BLOCKED, EXPLICIT, AUTOLOAD_OFF, DECLARED, UNDECLARED}
    assert len(set(STANDING_SAID.values())) == 5


def test_requirement_names_are_normalised() -> None:
    assert normalize_requirement("Pytest_Cov[toml]>=4; python_version>'3'") == "pytest-cov"
    assert normalize_requirement("pytest.timeout") == "pytest-timeout"
    assert normalize_requirement("") == ""
    assert normalize_requirement("   >=1") == ""


def test_addopts_requests_and_blocks_are_read_in_every_spelling() -> None:
    requested, blocked = plugin_flags("-p fakeslow -pasyncio -p no:timeout -ra", "-p no:anyio")
    assert requested == {"fakeslow", "asyncio"}
    assert blocked == {"timeout", "anyio"}
    assert plugin_flags(["-p x", "-q"]) == (frozenset({"x"}), frozenset())
    assert plugin_flags(None) == (frozenset(), frozenset())
    assert plugin_flags('-p "unterminated') == (frozenset({'"unterminated'}), frozenset())  # never raises


def test_known_effects_match_whole_words_and_unknown_is_not_guessed() -> None:
    assert "wall-clock" in known_effect("timeout", "pytest-timeout")
    assert "event loop" in known_effect("asyncio", "pytest-asyncio")
    assert "coverage" in known_effect("pytest_cov", "pytest-cov")
    assert "not characterised" in known_effect(
        "recovery", "pytest-recovery"
    )  # 'cov' inside a word is not 'cov'
    assert "not characterised" in known_effect("fakeslow", "pytest-fakeslow")


# ------------------------------------------------------------- the reading


def test_the_project_declarations_are_read_from_metadata(tmp_path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="p"\ndependencies=["a-b>=1"]\n[project.optional-dependencies]\nx=["Opt_Dep"]\n'
        '[dependency-groups]\ndev=["pytest-cov", {include-group="other"}]\n'
        '[tool.uv]\ndev-dependencies=["uvdev"]\n',
        encoding="utf-8",
    )
    (tmp_path / "requirements-test.txt").write_text("# c\n-r base.txt\nreqs_pkg==1\n", encoding="utf-8")
    assert declared_distributions(str(tmp_path)) == {"a-b", "opt-dep", "pytest-cov", "uvdev", "reqs-pkg"}
    assert declared_distributions(str(tmp_path / "missing")) == frozenset()


def test_ambient_plugins_stand_against_the_projects_declarations(world) -> None:
    found = _by_name(ambient_plugins(str(world), None))
    assert found["fakeslow"].standing == UNDECLARED
    assert found["asyncio"].standing == UNDECLARED
    assert found["timeout"].standing == DECLARED  # Pytest_Timeout normalises to pytest-timeout
    assert (found["fakeslow"].distribution, found["fakeslow"].version) == ("pytest-fakeslow", "2.3")
    assert {"asyncio", "fakeslow"} <= {p.name for p in undeclared(tuple(found.values()))}
    assert "timeout" not in {p.name for p in undeclared(tuple(found.values()))}


def test_dash_p_no_blocks_dash_p_requests_and_the_switch_turns_the_rest_off(world, monkeypatch) -> None:
    found = _by_name(ambient_plugins(str(world), "-p no:asyncio -p fakeslow"))
    assert found["asyncio"].standing == BLOCKED
    assert found["fakeslow"].standing == EXPLICIT
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    off = _by_name(ambient_plugins(str(world), "-p fakeslow"))
    assert off["fakeslow"].standing == EXPLICIT
    assert off["asyncio"].standing == AUTOLOAD_OFF and off["timeout"].standing == AUTOLOAD_OFF


def test_detectives_and_weskers_own_distributions_are_not_strays(tmp_path, monkeypatch) -> None:
    fake = tmp_path / "site"
    fake.mkdir()
    _dist(fake, "wesker", "1.0", "wesker", "wesker_plugin")
    _dist(fake, "detective-spec", "1.0", "detective", "detective_plugin")
    monkeypatch.syspath_prepend(str(fake))
    assert not {"wesker", "detective"} & {p.name for p in ambient_plugins(str(tmp_path), None)}


def test_a_regime_that_did_not_read_the_plugins_says_none_and_one_that_found_none_says_so(
    world, tmp_path
) -> None:
    """Absence is not a value: None (not read) and () (read, none auto-load) never share a sign."""
    assert resolve_regime(str(world)).ambient_plugins is None
    read = resolve_regime(str(world), plugins=True).ambient_plugins
    assert isinstance(read, tuple) and {"fakeslow", "asyncio", "timeout"} <= {p.name for p in read}
    assert plugin_rows(None) == []
    assert plugin_rows(()) == [("· pytest plugins", "none auto-loaded by this interpreter")]


# ------------------------------------------------------------- the pages and --json


def test_the_regime_page_names_each_undeclared_plugin_and_what_it_changes(world) -> None:
    page = cli._format_regime(resolve_regime(str(world), plugins=True))
    # the interpreter running the suite may carry real plugins too (pytest-cov), so count is a floor
    assert re.search(r"\d+ auto-loadable by this interpreter, \d+ not declared by the project", page)
    assert "⚠ undeclared" in page and "fakeslow (pytest-fakeslow 2.3)" in page
    assert "event loop" in page  # asyncio's known effect
    assert "timeout — the project declares its distribution as a dependency" in page
    assert "never disables them" in page


def test_the_regime_page_prints_nothing_about_plugins_when_they_were_not_read(world) -> None:
    assert "plugin" not in cli._format_regime(resolve_regime(str(world)))


def test_regime_json_carries_the_list_and_the_exit_code_is_untouched(
    world, tmp_path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    args = types.SimpleNamespace(target=None, project_root=str(world), migrate=False, json=True)
    code = cli._run_regime(args)
    payload = json.loads(capsys.readouterr().out)
    standing = {p["name"]: p["standing"] for p in payload["regime"]["ambient_plugins"]}
    assert standing["fakeslow"] == UNDECLARED and standing["timeout"] == DECLARED
    assert code == 0  # a disclosure is not a conflict


def test_doctor_discloses_beside_green_and_changes_neither_its_code_nor_its_exit(world) -> None:
    code, facts = cli._doctor_green(str(world), "", "")
    assert code == "clean"
    page = "\n".join(cli._render_doctor_green(code, facts))
    assert "GREEN — setup" in page and "fakeslow" in page and "⚠ undeclared" in page
    assert {p.name for p in facts["ambient_plugins"]} >= {"fakeslow", "asyncio", "timeout"}


def test_doctor_without_the_key_prints_no_plugin_rows() -> None:
    page = "\n".join(cli._render_doctor_green("clean", {}))
    assert "plugin" not in page


def test_ambient_plugin_records_are_plain_dataclasses() -> None:
    plugin = AmbientPlugin("n", "d", "1", UNDECLARED, "e")
    assert plugin_rows((plugin,))[1][0] == "⚠ undeclared"
