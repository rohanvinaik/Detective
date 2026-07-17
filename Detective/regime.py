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
from .engine import ShadowedTarget, _suite_path, shadowed_target
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
    has_config: bool  # a pyproject.toml exists to declare into
    conftests: tuple[str, ...]  # every conftest.py pytest would load, repo-relative
    # Conftests that share ONE importable name (their directory is not a package, so each is the
    # module `conftest`). Two of those in one process is `import file mismatch`.
    colliding_conftests: tuple[str, ...]
    # Which conftests DETECTIVE wrote. Load-bearing for the refusal: if one of a colliding pair
    # is ours, the fix is exact and safe — delete ours. If neither is, we do not guess, because
    # the obvious alternative is not safe (see below) and both files are the user's.
    generated_conftests: tuple[str, ...] = ()
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


def _pytest_table(root: str) -> dict:
    """`[tool.pytest.ini_options]`, or {} when there is no readable config."""
    try:
        import tomllib

        with open(os.path.join(root, "pyproject.toml"), "rb") as fh:
            table = tomllib.load(fh).get("tool", {}).get("pytest", {}).get("ini_options", {})
    except (OSError, ValueError, ImportError, AttributeError):
        return {}
    return table if isinstance(table, dict) else {}


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
    table = _pytest_table(root)
    markers = table.get("markers", []) or []
    target = module = None
    shadow = None
    if file:
        full = os.path.abspath(file if os.path.isabs(file) else os.path.join(root, file))
        if os.path.isfile(full):
            target = full
            rel = os.path.relpath(full, root)
            if not rel.startswith(os.pardir):
                module = importable_module(rel, root)
                shadow = shadowed_target(full, root)
    return TestRegime(
        root=root,
        layout=_layout(root),
        suite_path=tuple(_suite_path(root)),
        testpaths=tuple(table.get("testpaths", []) or []),
        pythonpath=tuple(table.get("pythonpath", []) or []),
        marker_declared=any(str(m).startswith("detective:") for m in markers),
        has_config=os.path.isfile(os.path.join(root, "pyproject.toml")),
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
    needs_root = root_conftest_is_ours or regime.layout == "scripts"
    declare_pythonpath = needs_root and "." not in regime.pythonpath
    blocked: list[str] = []
    if regime.shadow is not None:
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
