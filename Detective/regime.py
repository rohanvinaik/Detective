"""Testing-regime resolution — the ONE place that answers "how does this repo run its tests?"

Every command needs the same four facts: what name imports the target, what `sys.path` the suite
gets, whether that name resolves to the file we were pointed at, and whether the suite can even
start. Each answered those privately, differently, and some got them wrong:

* the test writer turned a path into a module by swapping `/` for `.`, so a src-layout got
  `from src.pkg.mod import f` — importable under PEP 420, and therefore silent: Python then held
  TWO module objects for one file and the generated suite tested a different program;
* the soundness gate put only `root` on the path, so on that same layout every property raised
  ImportError, was judged unsound, and was dropped — reported as `0/12 killed`, which reads as
  "unkillable code" rather than "the gate could not import it";
* nothing checked whether the target's own name resolved elsewhere, so a `.pth` aimed at another
  checkout produced a truthful `0 of 935 tests cover this` that read as "untested";
* nothing noticed that Detective's own generated `conftest.py` collided with the repo's
  `tests/conftest.py`, killing its in-process live session and silently dropping every
  fixture-taking test from the profile.

Those are four bugs with one cause: resolving the way THIS PROCESS does instead of the way the
SUITE does, in four places, none of which knew the others existed. This module is that knowledge,
computed once, as data. `resolve_regime` decides nothing and writes nothing — `conflicts` names
what makes a verdict untrustworthy, and the caller decides what to do about it.

`plan_migration`/`apply_migration` are the write half, and they are deliberately two functions:
the plan is data a caller can print, gate on, or ignore, and nothing touches disk until someone
asks. Migration only ever replaces a Detective artifact with its declarative equivalent — it
never edits a file the user wrote, and it names what it cannot fix rather than guessing.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .certify import _PYTEST_SECTION
from .engine import ShadowedTarget, _resolve_origin, _suite_path, shadowed_target
from .reachability import _SKIP_DIRS, _pytest_norecursedirs
from .synthesis.oracle_light import importable_module


@dataclass(frozen=True)
class TestRegime:
    """How a repository imports its code and runs its tests — as facts, not advice."""

    root: str
    layout: str  # "src" | "flat" | "scripts"
    suite_path: tuple[str, ...]  # the sys.path entries the SUITE gets (pythonpath first, then root)
    testpaths: tuple[str, ...]  # declared [tool.pytest.ini_options] testpaths, if any
    pythonpath: tuple[str, ...]  # declared pythonpath — the DECLARATIVE form of a sys.path insert
    marker_declared: bool  # `detective` legal under --strict-markers without a conftest
    has_config: bool  # a config file exists to declare into
    conftests: tuple[str, ...]  # every conftest.py pytest would load, repo-relative
    # Conftests that share ONE importable name (their directory is not a package, so each is the
    # module `conftest`). Two of those in one process is `import file mismatch`.
    colliding_conftests: tuple[str, ...]
    # Which conftests DETECTIVE wrote. Load-bearing for the refusal: if one of a colliding pair
    # is ours, the fix is exact and safe — delete ours. If neither is, we do not guess, because
    # the obvious alternative is not safe (see below) and both files are the user's.
    generated_conftests: tuple[str, ...] = ()
    # The config file pytest ACTUALLY reads, repo-relative ("" when none) — `pytest.ini`,
    # `pyproject.toml`, `tox.ini`, or `setup.cfg`, resolved by pytest's own precedence (see
    # `pytest_config`). Named, not assumed: a report saying "declared in pyproject" about a repo
    # whose `pytest.ini` outranks it describes a file with no effect on the run it describes.
    # Down here only because a dataclass cannot default a field ahead of non-defaulted ones; it
    # belongs beside `has_config`, which is the question it answers precisely.
    config_file: str = ""
    # A shadow that `pythonpath = ["."]` would FIX. The question is not which layout this is —
    # it is whether the suite can be made to import the tree we were pointed at, which is the
    # only thing the tool needs in order to read and write that suite. Answered by asking, not
    # by classifying: resolve the target's module with the root on the path and see if it lands
    # on the target file. False (and meaningless) when there is no shadow.
    root_resolves: bool = False
    target: str | None = None  # the file under analysis, absolute
    module: str | None = None  # the dotted name the REST of the repo imports it by
    shadow: ShadowedTarget | None = None  # set iff `module` resolves to a different file

    @property
    def conflicts(self) -> tuple[str, ...]:
        """What makes every verdict from this repo untrustworthy — empty when nothing does.

        Not "warnings". Each of these means the suite is not talking about the code we were
        asked about, and a number computed under one is worse than no number: it is a specific,
        confident, wrong answer that reads as a finding.
        """
        out: list[str] = []
        if self.shadow is not None:
            out.append("shadowed-target")
        if self.colliding_conftests:
            out.append("conftest-collision")
        return tuple(out)


def _layout(root: str) -> str:
    """Where this repo keeps its importable code. Descriptive only — nothing branches on it."""
    if os.path.isdir(os.path.join(root, "src")):
        for entry in os.listdir(os.path.join(root, "src")):
            if os.path.isfile(os.path.join(root, "src", entry, "__init__.py")):
                return "src"
    try:
        entries = os.listdir(root)
    except OSError:
        return "scripts"
    for entry in entries:
        if entry not in _SKIP_DIRS and os.path.isfile(os.path.join(root, entry, "__init__.py")):
            return "flat"
    return "scripts"


# pytest's OWN config precedence, in its own order. `pytest.ini` wins even when EMPTY; the other
# three count only when they actually carry a pytest section. `(filename, dialect, section)`.
_CONFIG_ORDER = (
    ("pytest.ini", "ini", "[pytest]"),
    ("pyproject.toml", "toml", "[tool.pytest.ini_options]"),
    ("tox.ini", "ini", "[pytest]"),
    ("setup.cfg", "ini", "[tool:pytest]"),
)


def pytest_config(root: str) -> tuple[str, str, str] | None:
    """The config file pytest will ACTUALLY read — `(path, dialect, section)` — or None.

    This module exists because four bugs shared one cause: resolving the way THIS PROCESS does
    instead of the way the SUITE does. This is the fifth, and it was inside the module written to
    end them. `_pytest_table` read `pyproject.toml` and `ensure_marker_registered` wrote it, both
    unconditionally — but `pytest.ini` OUTRANKS `[tool.pytest.ini_options]`, and so do `tox.ini`
    and `setup.cfg`. On any repo carrying one, `regime --migrate` declared the marker into a file
    pytest ignores and reported `✓ MIGRATED · this regime resolves cleanly`. pytest says so out
    loud — `configfile: pytest.ini (WARNING: ignoring pytest config in pyproject.toml!)` — and
    nobody was reading it. Measured on TailChasingFixer: the marker went into pyproject, pytest.ini
    carried `--strict-markers`, and every test Detective generated failed to COLLECT. A migration
    that reports success and changes nothing is worse than one that refuses: it is a green light
    on a broken regime.

    Returns None when nothing declares pytest config AND there is no `pyproject.toml` to declare
    into — there is no file to write and creating one is not ours to do. When no config exists but
    `pyproject.toml` does, that is the answer: it is where a declaration WOULD take effect, which
    is the same question.
    """
    for name, dialect, section in _CONFIG_ORDER:
        path = os.path.join(root, name)
        if not os.path.isfile(path):
            continue
        if name == "pytest.ini":
            return path, dialect, section  # wins unconditionally — even empty
        try:
            with open(path, encoding="utf-8") as fh:
                source = fh.read()
        except OSError:
            continue
        if section in source:
            return path, dialect, section
    pyproject = os.path.join(root, "pyproject.toml")
    if os.path.isfile(pyproject):
        return pyproject, "toml", "[tool.pytest.ini_options]"
    return None


def _pytest_table(root: str) -> dict:
    """The resolved config's pytest settings, or {} when there is no readable config.

    Reads whatever `pytest_config` resolved, in that file's dialect — not `pyproject.toml` on
    faith. A repo with a `pytest.ini` has its `testpaths` THERE, and reading them from a
    pyproject pytest is ignoring answers a question about a file that does not run.
    """
    resolved = pytest_config(root)
    if resolved is None:
        return {}
    path, dialect, section = resolved
    if dialect == "toml":
        try:
            import tomllib

            with open(path, "rb") as fh:
                table = tomllib.load(fh).get("tool", {}).get("pytest", {}).get("ini_options", {})
        except (OSError, ValueError, ImportError, AttributeError):
            return {}
        return table if isinstance(table, dict) else {}
    try:
        import configparser

        parser = configparser.ConfigParser()
        parser.read(path, encoding="utf-8")
        raw = dict(parser[section.strip("[]")])
    except (OSError, KeyError, ValueError, ImportError):
        return {}
    # An ini value is one string; the TOML side returns LISTS for the keys we read, and a caller
    # iterating a str gets its CHARACTERS — silently, as a falsy answer rather than an error.
    # `marker_declared` did exactly that: `any(m.startswith("detective:") for m in markers)` over
    # a string tested every CHARACTER, so a correctly-registered marker read as absent and
    # `--migrate` told you to migrate a repo it had just migrated.
    #
    # The two shapes split DIFFERENTLY and that is not a detail: a marker is `name: prose with
    # spaces`, one per LINE, so whitespace-splitting it shreds every entry into words, while
    # `testpaths` is whitespace-separated. Same dialect, two grammars.
    return {k: _as_list(k, v) for k, v in raw.items()}


def _by_line(v: str) -> list[str]:
    return [ln.strip() for ln in v.strip().splitlines() if ln.strip()]


def _as_list(key: str, value: str) -> object:
    """An ini value in the shape the TOML side of `_pytest_table` returns for the same key."""
    if key == "markers":
        return _by_line(value)
    if key in ("testpaths", "norecursedirs"):
        return value.split()
    return value


def _conftest_module(root: str, conftest: str) -> str:
    """The module name pytest imports a conftest under (prepend mode).

    The name is derived from the first directory ABOVE it that is not a package — exactly the
    rule `importable_module` uses. A conftest in a non-package directory is therefore plainly
    `conftest`, and every such conftest in the tree is the same module name as every other.
    """
    return importable_module(os.path.relpath(conftest, root), root)


def _conftests(root: str) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """``(every conftest pytest would load, those sharing one name, the ones WE wrote)``.

    Scoped to what pytest actually loads — the root conftest plus those under `testpaths` — and
    pruned by the project's own `norecursedirs`. A `mutants/` or `.venv/` shadow tree is full of
    conftests that pytest never touches; counting them would invent a conflict.
    """
    skip = _SKIP_DIRS | _pytest_norecursedirs(root)
    roots = [os.path.join(root, p) for p in _pytest_table(root).get("testpaths", []) or []]
    found: list[str] = []
    if os.path.isfile(os.path.join(root, "conftest.py")):
        found.append(os.path.join(root, "conftest.py"))
    for start in roots or [root]:
        for dirpath, dirnames, filenames in os.walk(start):
            dirnames[:] = [d for d in dirnames if d not in skip and not d.startswith(".")]
            if "conftest.py" in filenames:
                path = os.path.join(dirpath, "conftest.py")
                if path not in found:
                    found.append(path)
    by_module: dict[str, list[str]] = {}
    for path in found:
        by_module.setdefault(_conftest_module(root, path), []).append(path)
    colliding = [p for group in by_module.values() if len(group) > 1 for p in group]
    rel = tuple(os.path.relpath(p, root) for p in found)
    return (
        rel,
        tuple(os.path.relpath(p, root) for p in colliding),
        tuple(os.path.relpath(p, root) for p in found if _is_ours(p)),
    )


def _is_ours(conftest: str) -> bool:
    """Did Detective write this conftest? Its own generated header is the only honest signal."""
    try:
        with open(conftest, encoding="utf-8") as fh:
            return "Auto-generated by Detective" in fh.readline()
    except OSError:
        return False


def resolve_regime(project_root: str = ".", file: str | None = None) -> TestRegime:
    """Read the repo's testing regime. Reads only — never writes, never refuses.

    ``file`` is optional: without it the repo-level facts still resolve (layout, path, conftests,
    marker), which is what a `regime` report with no target needs. With it, the target-specific
    facts resolve too — the name that imports it, and whether that name means this file.
    """
    root = os.path.abspath(project_root)
    conftests, colliding, generated = _conftests(root)
    config = pytest_config(root)
    table = _pytest_table(root)
    markers = table.get("markers", []) or []
    target = module = None
    shadow = None
    root_resolves = False
    if file:
        full = os.path.abspath(file if os.path.isabs(file) else os.path.join(root, file))
        if os.path.isfile(full):
            target = full
            rel = os.path.relpath(full, root)
            if not rel.startswith(os.pardir):
                module = importable_module(rel, root)
                shadow = shadowed_target(full, root)
                if shadow is not None:
                    # One extra subprocess, and only on the shadow path — the rare case where
                    # the answer decides between "we can fix this" and "only you can".
                    origin = _resolve_origin(module, root, [root])
                    root_resolves = bool(origin) and os.path.realpath(origin) == os.path.realpath(full)
    return TestRegime(
        root=root,
        layout=_layout(root),
        suite_path=tuple(_suite_path(root)),
        testpaths=tuple(table.get("testpaths", []) or []),
        pythonpath=tuple(table.get("pythonpath", []) or []),
        marker_declared=any(str(m).startswith("detective:") for m in markers),
        root_resolves=root_resolves,
        has_config=config is not None,
        config_file=os.path.relpath(config[0], root) if config else "",
        conftests=conftests,
        colliding_conftests=colliding,
        generated_conftests=generated,
        target=target,
        module=module,
        shadow=shadow,
    )


@dataclass(frozen=True)
class Migration:
    """What it takes to make this repo's testing setup clean — as a PLAN, before anything runs.

    Migration is narrow on purpose. It replaces DETECTIVE's own artifacts with their declarative
    equivalents, and touches nothing else. It does not reformat, reorganise, or improve a repo:
    the only files it removes are ones Detective wrote, and the only thing it writes is config
    that reproduces what those files did.

    ``blocked`` is the honest half — what a clean setup still needs that no rewrite can supply.
    """

    root: str
    declare_marker: bool  # `@pytest.mark.detective` is not legal under --strict-markers yet
    declare_pythonpath: bool  # our conftest's sys.path insert has no declarative replacement yet
    remove_conftests: tuple[str, ...]  # OURS, obsolete once the two above are declared
    create_config: bool  # there is no pyproject.toml to declare into
    blocked: tuple[str, ...]  # what migration cannot fix — say so rather than half-fix

    @property
    def needed(self) -> bool:
        return bool(
            self.declare_marker or self.declare_pythonpath or self.remove_conftests or self.create_config
        )


def plan_migration(regime: TestRegime) -> Migration:
    """What would change, and what would still be wrong afterwards. Reads only.

    The one subtlety worth stating: Detective's generated conftest does TWO things — registers
    the marker and inserts the root on `sys.path` — and removing it without replacing BOTH breaks
    the repo. Measured: deleting it from a scripts-only tree left `pytest tests/` (the console
    script, which does not add cwd the way `python -m pytest` does) failing with
    `ModuleNotFoundError: No module named 'scorer'`. `pythonpath = ["."]` is the exact
    declarative equivalent of that insert, so the conftest is only removed once it is redundant.
    """
    ours = tuple(regime.generated_conftests)
    # `pythonpath = ["."]` is needed in two cases, and both are about the ROOT being importable:
    #
    #  * a root conftest of OURS is currently supplying it via sys.path.insert, and removing that
    #    file without the declarative replacement breaks the repo;
    #  * the code lives at the root and is imported bare (`from scorer import …`). pytest does
    #    NOT put the rootdir on sys.path for that — it inserts the TEST file's directory — so
    #    such a repo only ever worked via `python -m pytest` (which adds cwd) or a conftest.
    #    Measured: `pytest tests/` → `ModuleNotFoundError: No module named 'scorer'`.
    #
    # Declared once, both cases are fixed for every invocation, which is the difference between
    # a setup that happens to work and one that is correct.
    root_conftest_is_ours = "conftest.py" in ours
    #  * a shadow the root would RESOLVE. The whole requirement is that the tool can read and
    #    write THIS project's suite, and a suite importing another copy of the target cannot be
    #    read or written meaningfully. Where `pythonpath = ["."]` makes the name land on the tree
    #    we were pointed at, that is a migration we can perform — not a decision to hand back.
    #    Asked, never inferred from layout: a flat package at the root needs this exactly as much
    #    as a scripts tree does when nothing else puts the root on the path (measured on Wesker's
    #    own repo — `layout: flat`, no conftest, and bare `pytest` importing site-packages), while
    #    an editable-installed flat repo needs nothing and must not be edited for a non-problem.
    #    The resolution answers that; the layout does not.
    fixable_shadow = regime.shadow is not None and regime.root_resolves
    needs_root = root_conftest_is_ours or regime.layout == "scripts" or fixable_shadow
    declare_pythonpath = needs_root and "." not in regime.pythonpath
    blocked: list[str] = []
    if regime.shadow is not None and not regime.root_resolves:
        # BLOCKED only when we cannot fix it: the name resolves elsewhere and the root would not
        # change that (a src-layout needing `src`, a `.pth` aimed at another checkout, two
        # installs of one distribution). Then it is genuinely a choice about which tree is meant,
        # and guessing between two checkouts of someone's code is not ours to do.
        blocked.append(
            f"`{regime.shadow.module}` imports {regime.shadow.imported}, not this tree — "
            "install this one (`pip install -e .`) or point --project-root at that one"
        )
    theirs = tuple(c for c in regime.colliding_conftests if c not in ours)
    if len(theirs) > 1:
        blocked.append(
            f"{' and '.join(theirs)} share the module name `conftest` and neither is ours — "
            "give one a distinct name; we will not guess between two files you wrote"
        )
    return Migration(
        root=regime.root,
        declare_marker=not regime.marker_declared,
        declare_pythonpath=declare_pythonpath,
        remove_conftests=ours,
        create_config=not regime.has_config and (not regime.marker_declared or declare_pythonpath),
        blocked=tuple(blocked),
    )


def apply_migration(migration: Migration) -> tuple[str, ...]:
    """Do it. Returns what actually changed, in the order it happened.

    Config first, conftest last: if writing the config fails, the conftest still works and the
    repo is exactly as it was. The reverse order would leave a tree with neither.
    """
    from .certify import ensure_marker_registered

    done: list[str] = []
    if migration.create_config:
        path = os.path.join(migration.root, "pyproject.toml")
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("[tool.pytest.ini_options]\n")
            done.append("created pyproject.toml with [tool.pytest.ini_options]")
    if migration.declare_pythonpath and _declare_pythonpath(migration.root):
        done.append('declared pythonpath = ["."] — the root is importable under any pytest run')
    if migration.declare_marker and (what := ensure_marker_registered(migration.root)):
        done.append(what)
    for rel in migration.remove_conftests:
        path = os.path.join(migration.root, rel)
        try:
            os.remove(path)
        except OSError:
            continue
        done.append(f"removed {rel} — Detective wrote it; everything it did is now declared")
    return tuple(done)


def _declare_pythonpath(root: str) -> bool:
    """Add ``pythonpath = ["."]`` to the pytest table. True if the file changed."""
    path = os.path.join(root, "pyproject.toml")
    try:
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
    except OSError:
        return False
    if "pythonpath" in source:
        return False  # the repo already declares one — not ours to rewrite
    if _PYTEST_SECTION in source:
        updated = source.replace(_PYTEST_SECTION, f'{_PYTEST_SECTION}\npythonpath = ["."]', 1)
    else:
        updated = f'{source.rstrip()}\n\n{_PYTEST_SECTION}\npythonpath = ["."]\n'
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(updated)
    except OSError:
        return False
    return True
