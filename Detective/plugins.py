"""Which pytest plugins does this interpreter auto-load that the project never declared (#98).

Detective opens an IN-PROCESS live pytest session under its own interpreter, and pytest loads every
installed ``pytest11`` entry point into it. A project that declares none of them still gets them, and
they change the measurement: EP-C4 measured the same commit at 3228 passed / 0 failed in a locked
environment against 25 failed in a dev interpreter carrying asyncio, anyio, codeflash-benchmark,
jaxtyping, logfire, memray and timeout, and a converge doing 2.2x the work (codeflash-benchmark alone
+2.09 G instructions). Nothing in ``regime`` or ``doctor`` said so.

FOUNDER RULING (ENGINEERING_PASS §6 item 5): for users, Detective DISCLOSES stray auto-loaded plugins and
never disables a user's plugins. This module therefore only READS. It does not set
``PYTEST_DISABLE_PLUGIN_AUTOLOAD``, pass ``-p no:...`` or remove an entry point, and what it reports is
never a conflict, never a fault and never changes an exit code: a disclosure of what the measurement was
taken through.

Absence is not a value (§9 invariant 7). ``TestRegime.ambient_plugins`` is ``None`` when the entry points
were NOT READ (the regime is resolved on every profile pass, and enumerating them is opt-in) and ``()``
when they were read and none auto-loads: "we did not look" and "we looked and found none" never share a
sign.

KNOWN LIMITS, stated rather than papered over:

* "Declared" is read from the project's metadata (``pyproject.toml`` dependencies, optional dependencies,
  dependency groups, uv dev-dependencies, ``requirements*.txt``), by distribution NAME. A plugin installed
  transitively by a declared dependency reads as undeclared, because the project did not name it, which is
  the fact being disclosed.
* The effect text is a table of what is KNOWN about the common plugins. An unknown plugin gets the generic
  sentence, never a guessed one.
"""

from __future__ import annotations

import os
import re
import shlex
from dataclasses import dataclass

BLOCKED = "blocked"
EXPLICIT = "explicit"
AUTOLOAD_OFF = "autoload_off"
DECLARED = "declared"
UNDECLARED = "undeclared"

# Distributions that ARE Detective's or Wesker's own measurement machinery, never a stray.
_OWN = frozenset({"detective-spec", "detective", "wesker", "wesker-mutate", "pytest"})

# What is known a plugin changes in a measurement, keyed by a substring of the distribution or entry-point
# name. Phrased as the consequence for a Detective run, from the EP-C4 measurement where there is one.
_KNOWN_EFFECTS: tuple[tuple[str, str], ...] = (
    ("codeflash", "speed: benchmark instrumentation (+2.09 G instructions measured on one converge)"),
    (
        "asyncio",
        "semantics: wraps coroutine tests and owns the event loop, which changes what a test run does",
    ),
    ("anyio", "semantics: runs async tests through anyio's own runner and adds markers"),
    ("jaxtyping", "semantics and speed: an import hook type-checks annotated functions as they are called"),
    ("logfire", "speed and output: instruments the process and may emit telemetry"),
    ("memray", "speed: memory-profiling hooks around every test"),
    ("timeout", "semantics: aborts a test that exceeds a wall-clock limit, which a mutant's loop will hit"),
    (
        "xdist",
        "semantics: distributes tests across worker processes, away from Detective's in-process session",
    ),
    ("randomly", "semantics: reorders tests and reseeds RNGs between them"),
    ("rerunfailures", "semantics: re-runs a failing test, so a flaky pass can hide a kill"),
    ("cov", "speed: coverage tracing slows every test"),
    ("benchmark", "speed: benchmark timing rounds repeat tests"),
)
_GENERIC_EFFECT = (
    "unknown: a plugin can change collection, fixtures, warnings filters, test order or timing; "
    "its effect on this measurement is not characterised"
)

# The sentence each standing earns, as a TABLE indexed by the code so a consumer cannot name some of the
# five and let the rest fall through (the consumer-distinction guard reads a string-keyed table as comparing).
STANDING_SAID: dict[str, str] = {
    BLOCKED: "the project disables it (-p no:...), so it does not load",
    EXPLICIT: "the project asks for it (-p / PYTEST_PLUGINS), so it loads by declaration",
    AUTOLOAD_OFF: "PYTEST_DISABLE_PLUGIN_AUTOLOAD is set, so entry-point plugins do not load unasked",
    DECLARED: "the project declares its distribution as a dependency",
    UNDECLARED: "auto-loaded into every Detective measurement and declared by nothing in the project",
}


def plugin_declaration(blocked: bool, explicit: bool, autoload_off: bool, declared: bool) -> str:
    """How one auto-loadable pytest plugin stands against the project's declarations (#98, pure — pinned).

    Named codes, because each is a different fact with a different consequence for a measurement:

      "blocked"       the project says ``-p no:<name>``: pytest will not load it. Not ambient.
      "explicit"      the project asks for it by name (``-p <name>`` / ``PYTEST_PLUGINS``): it loads
                      because the project said so. Not ambient.
      "autoload_off"  ``PYTEST_DISABLE_PLUGIN_AUTOLOAD`` is set and nothing asked for it: entry-point
                      plugins do not load in this process. Not ambient.
      "declared"      it will auto-load, and the project declares the distribution (a dependency or a
                      dev group): the project knows it is there.
      "undeclared"    it will auto-load and nothing in the project declares it. THE disclosure: it is
                      in the measurement and the project never asked for it.

    Precedence is the order of loading: a block wins over everything, an explicit request over the
    autoload switch (``-p`` loads even with autoload off), the switch over declaration.
    """
    if blocked:
        return BLOCKED
    if explicit:
        return EXPLICIT
    if autoload_off:
        return AUTOLOAD_OFF
    if declared:
        return DECLARED
    return UNDECLARED


def normalize_requirement(requirement: str) -> str:
    """The canonical distribution name inside one requirement string: ``"Pytest_Cov[x]>=4; python_version"``
    -> ``"pytest-cov"``. An empty or unparseable string yields ""."""
    match = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", requirement or "")
    return re.sub(r"[-_.]+", "-", match.group(1)).lower() if match else ""


def known_effect(name: str, distribution: str) -> str:
    """What is known about this plugin's effect on a measurement, or the generic 'not characterised'."""
    words = set(re.split(r"[-_.\s]+", f"{name} {distribution}".lower()))
    return next((effect for key, effect in _KNOWN_EFFECTS if key in words), _GENERIC_EFFECT)


@dataclass(frozen=True)
class AmbientPlugin:
    """One ``pytest11`` entry point this interpreter can auto-load, and how the project stands to it."""

    name: str  # the entry-point name pytest registers it under (what ``-p`` and ``-p no:`` use)
    distribution: str  # the installed distribution that provides it ("" when the metadata names none)
    version: str  # that distribution's version ("" when unknown)
    standing: str  # one of the five `plugin_declaration` codes
    effect: str  # what is known about it changing a measurement


def declared_distributions(project_root: str) -> frozenset[str]:
    """Distribution names the project's own metadata declares, normalised. Reads only."""
    names: set[str] = set()
    pyproject = os.path.join(project_root, "pyproject.toml")
    try:
        import tomllib

        with open(pyproject, "rb") as fh:
            data = tomllib.load(fh)
    except (OSError, ValueError, ImportError):
        data = {}
    project = data.get("project", {}) if isinstance(data.get("project"), dict) else {}
    pools: list[object] = [project.get("dependencies", [])]
    optional = project.get("optional-dependencies", {})
    pools += list(optional.values()) if isinstance(optional, dict) else []
    groups = data.get("dependency-groups", {})
    pools += list(groups.values()) if isinstance(groups, dict) else []
    uv = data.get("tool", {}).get("uv", {}) if isinstance(data.get("tool"), dict) else {}
    pools.append(uv.get("dev-dependencies", []) if isinstance(uv, dict) else [])
    for pool in pools:
        for item in pool if isinstance(pool, list) else []:
            if isinstance(item, str):  # a dependency-group may include {include-group = ...}
                names.add(normalize_requirement(item))
    try:
        entries = sorted(os.listdir(project_root))
    except OSError:
        entries = []
    for entry in entries:
        if re.fullmatch(r"requirements[\w.-]*\.txt", entry):
            try:
                with open(os.path.join(project_root, entry), encoding="utf-8") as fh:
                    names.update(
                        normalize_requirement(line) for line in fh if not line.lstrip().startswith(("#", "-"))
                    )
            except OSError:
                continue
    names.discard("")
    return frozenset(names)


def plugin_flags(addopts: object, env_addopts: str = "") -> tuple[frozenset[str], frozenset[str]]:
    """``(requested, blocked)`` plugin names from pytest's ``addopts`` (a string or a list) and the
    ``PYTEST_ADDOPTS`` environment value: ``-p name`` / ``-pname`` request, ``-p no:name`` blocks."""
    tokens: list[str] = []
    for source in (addopts, env_addopts):
        if isinstance(source, str):
            try:
                tokens += shlex.split(source)
            except ValueError:
                tokens += source.split()
        elif isinstance(source, (list, tuple)):
            for piece in source:
                tokens += shlex.split(str(piece))
    requested: set[str] = set()
    blocked: set[str] = set()
    index = 0
    while index < len(tokens):
        token = tokens[index]
        value = ""
        if token == "-p" and index + 1 < len(tokens):
            value = tokens[index + 1]
            index += 1
        elif token.startswith("-p") and len(token) > 2:
            value = token[2:]
        if value.startswith("no:"):
            blocked.add(value[3:])
        elif value:
            requested.add(value)
        index += 1
    return frozenset(requested), frozenset(blocked)


def ambient_plugins(project_root: str, addopts: object = None) -> tuple[AmbientPlugin, ...]:
    """Every ``pytest11`` entry point this interpreter can auto-load, sorted by name, with the project's
    standing to it. Reads installed metadata and the project's declarations; changes nothing.

    Detective's and Wesker's own distributions are left out: they are the measurement machinery, not
    something the project's run happens to pick up."""
    from importlib import metadata

    declared = declared_distributions(project_root)
    requested, blocked = plugin_flags(addopts, os.environ.get("PYTEST_ADDOPTS", ""))
    requested = requested | frozenset(p for p in os.environ.get("PYTEST_PLUGINS", "").split(",") if p)
    autoload_off = bool(os.environ.get("PYTEST_DISABLE_PLUGIN_AUTOLOAD"))
    found: dict[str, AmbientPlugin] = {}
    for entry in metadata.entry_points(group="pytest11"):
        dist = entry.dist  # None when the metadata names no distribution
        distribution = dist.metadata["Name"] if dist is not None and dist.metadata["Name"] else ""
        canonical = normalize_requirement(distribution)
        if canonical in _OWN:
            continue
        standing = plugin_declaration(
            entry.name in blocked,
            entry.name in requested or entry.value.split(":")[0] in requested,
            autoload_off,
            canonical in declared,
        )
        found[entry.name] = AmbientPlugin(
            name=entry.name,
            distribution=distribution,
            version=dist.version if dist is not None else "",
            standing=standing,
            effect=known_effect(entry.name, distribution),
        )
    return tuple(found[name] for name in sorted(found))


def undeclared(plugins: tuple[AmbientPlugin, ...] | None) -> tuple[AmbientPlugin, ...]:
    """The plugins standing `undeclared` (the disclosure). `None` (not read) yields (), and callers that
    must tell 'not read' from 'none found' test the argument for None BEFORE calling this."""
    return tuple(p for p in plugins or () if p.standing == UNDECLARED)


def _provenance(plugin: AmbientPlugin) -> str:
    """'dist 1.2', or 'unknown distribution' when the metadata names none."""
    return (
        f"{plugin.distribution} {plugin.version}".strip() if plugin.distribution else "unknown distribution"
    )


def plugin_rows(plugins: tuple[AmbientPlugin, ...] | None) -> list[tuple[str, str]]:
    """The disclosure as ``(label, text)`` rows, ONE derivation for ``regime`` and ``doctor`` (#98).

    ``None`` (not read) yields no rows, so it can never print as 'none auto-loaded'; ``()`` says so in
    words. Plugins that are not ambient (blocked, explicit, autoload_off) and declared ones are summarised
    one row per standing from `STANDING_SAID`; each UNDECLARED one is named with what is known of its
    effect. Nothing here is a fault: the closing row says what the disclosure means for a measurement."""
    if plugins is None:
        return []
    if not plugins:
        return [("· pytest plugins", "none auto-loaded by this interpreter")]
    loose = undeclared(plugins)
    rows = [
        (
            "· pytest plugins",
            f"{len(plugins)} auto-loadable by this interpreter, {len(loose)} not declared by the project",
        )
    ]
    rows += [
        (
            "⚠ undeclared",
            f"{p.name} ({_provenance(p)}) — {p.effect}",
        )
        for p in loose
    ]
    for standing in (DECLARED, EXPLICIT, AUTOLOAD_OFF, BLOCKED):
        names = [p.name for p in plugins if p.standing == standing]
        if names:
            rows.append((f"· {standing}", f"{', '.join(names)} — {STANDING_SAID[standing]}"))
    if loose:
        rows.append(
            (
                "· For a measurement",
                "Detective runs its tests inside THIS interpreter's pytest session, so the undeclared "
                "plugins above are part of every measurement it takes. It reports them, never disables them.",
            )
        )
    return rows
