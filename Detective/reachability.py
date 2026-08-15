"""Which test files could possibly execute a target module's lines.

WHY: the baseline trace runs EVERY collected test under a per-line callback to discover
which ones touch the target's lines. Scoping (``Wesker.engine._tests_for``) is correct but
derived FROM that trace, so the trace is the whole bill and it scales with the SUITE, not
the function. Measured on Regenesis: 2134 test functions traced to profile one 13-line
function; the mutation phase never started. 1928 of those (90%) are in modules that cannot
import the target's module even transitively, so they provably cannot execute one of its
lines, so tracing them can only ever produce the empty set.

This computes that "provably cannot" statically, so the live session collects only the rest.

SOUNDNESS IS THE WHOLE POINT. A test wrongly excluded is a lost kill, which surfaces as an
overstated survivor — a tool reporting behavior as unspecified when a test does pin it. That
is precisely the lie the project refuses everywhere else, so this module is conservative in
one direction only: ANY doubt returns None (or includes the file), and None means the caller
collects everything exactly as it does today. It never trades a verdict for speed.
"""

from __future__ import annotations

import ast
import os

# Modules that can reach anything: importing these makes reachability undecidable here.
# NOTE: `pytest_plugins` is deliberately NOT here — it is a conftest module-level *variable*,
# never an imported module, so an import-name check can never see it (that was G2's dead entry).
# A `pytest_plugins = [...]` assignment is detected structurally in `_imports_of` instead.
_DYNAMIC = frozenset({"importlib", "pkgutil", "__import__"})

# `mutants/` is here for the same reason `.venv/` is: it's a *shadow* of the real source tree that
# a common test-adjacent tool (mutmut) writes into the repo. Walking into it enumerates a second
# `tests/conftest.py` under the same importable name as the real one — pytest's importer raises
# `ImportPathMismatchError` and the session dies on collection. `.pytest_cache` / `.mypy_cache`
# are byproduct dirs pytest itself already ignores; listing them here keeps our walker aligned.
_SKIP_DIRS = frozenset(
    {
        "__pycache__",
        ".git",
        ".venv",
        "venv",
        "dist",
        "build",
        ".tox",
        "node_modules",
        "mutants",
        ".pytest_cache",
        ".mypy_cache",
    }
)


def _pytest_norecursedirs(root: str) -> frozenset[str]:
    """User-authored `norecursedirs` from `pyproject.toml`'s `[tool.pytest.ini_options]`.

    Merged into `_SKIP_DIRS` so anything the project's pytest already prunes during discovery
    is pruned during Detective's reachability walk too — a project-native config, not one the
    user has to duplicate for Detective. Silently returns the empty set when the file is
    absent, unreadable, or has no such section: this is a hint, not a requirement.
    Only bare directory names (not globs) are honored — matches how our walker prunes.
    """
    try:
        import tomllib  # Python ≥ 3.11; Detective requires it.
    except ImportError:
        return frozenset()
    path = os.path.join(root, "pyproject.toml")
    try:
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError):
        return frozenset()
    raw = data.get("tool", {}).get("pytest", {}).get("ini_options", {}).get("norecursedirs", ())
    if isinstance(raw, str):
        raw = raw.split()
    # Only bare names — a pattern like `*.egg` cannot match a dir NAME literally, so it is a
    # no-op here rather than a source of surprise pruning.
    return frozenset(d for d in raw if isinstance(d, str) and "*" not in d and "/" not in d)


def module_name(root: str, path: str, import_roots: tuple[str, ...] = ()) -> str:
    """Dotted import name under the suite's authoritative import roots.

    A source file under ``root/src/pkg`` imports as ``pkg``, not ``src.pkg``.  The testing regime
    already measured that distinction; reachability must consume those roots instead of deriving a
    second, root-relative identity.  The deepest containing root wins, with ``root`` as the
    conservative fallback for test modules and flat layouts.
    """
    full = os.path.abspath(path)
    candidates = {os.path.abspath(root), *(os.path.abspath(p) for p in import_roots)}
    containing: list[str] = []
    for candidate in candidates:
        try:
            if os.path.commonpath((candidate, full)) == candidate:
                containing.append(candidate)
        except ValueError:
            continue
    base = max(containing, key=len) if containing else os.path.abspath(root)
    rel = os.path.relpath(full, base)
    stem = rel[:-3] if rel.endswith(".py") else rel
    parts = [p for p in stem.split(os.sep) if p not in ("", ".")]
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _imports_of(tree: ast.AST, this_module: str) -> tuple[set[str], bool]:
    """Every dotted name ``tree`` imports, and whether it does anything undecidable.

    The bool is the escape hatch: a star-import or a dynamic-import module means this file's
    reachability cannot be settled statically, and the caller must assume it reaches.
    Relative imports are resolved against ``this_module``'s package, since an unresolved
    relative import would otherwise look like "imports nothing" — a false NEGATIVE, the one
    error direction that costs a verdict.
    """
    out: set[str] = set()
    opaque = False
    pkg = this_module.rsplit(".", 1)[0] if "." in this_module else ""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out.add(a.name)
                if a.name.split(".")[0] in _DYNAMIC:
                    opaque = True
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                # `from . import x` inside a.b.c -> a.b ; `from .. import x` -> a
                anchor = this_module.split(".")
                anchor = anchor[: len(anchor) - node.level] if node.level <= len(anchor) else []
                base = ".".join([*anchor, base]) if base else ".".join(anchor)
            if not base:
                opaque = True
                continue
            out.add(base)
            for a in node.names:
                if a.name == "*":
                    opaque = True
                else:
                    out.add(f"{base}.{a.name}")
            if base.split(".")[0] in _DYNAMIC:
                opaque = True
        elif isinstance(node, ast.Call):
            fn = node.func
            name = getattr(fn, "id", None) or getattr(fn, "attr", None)
            if name in ("__import__", "import_module"):
                opaque = True
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            # A `pytest_plugins = [...]` declaration pulls in plugin modules that pytest imports
            # and whose fixtures it injects with no import edge — so the plugin can reach (and
            # inject) the target while this file names it nowhere. Treat the declaring module as
            # opaque; that keeps a fixture-only reacher instead of dropping it (G2, a lost kill).
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(t, ast.Name) and t.id == "pytest_plugins" for t in targets):
                opaque = True
    if pkg:
        out.add(pkg)
    return out, opaque


def is_virtualenv_root(dir_filenames: list[str]) -> bool:
    """Pure (#15 — pinned): does a directory's file listing mark it a Python virtualenv?

    ``pyvenv.cfg`` is the authoritative PEP 405 marker written at a venv's root — present in every
    virtualenv (``.venv``, ``.venv312``, ``.tox/py``, a poetry/uv env under any name) and nowhere
    else. Pruning on it drops the whole venv subtree from the import-graph walk without a name list
    the next differently-named env defeats: the authoritative-boundary principle (see
    ``within_declared_testpaths``) applied to the WALK, so an installed dependency's sources are
    never even parsed. Fixes the pre-session cost where the graph builder opened ``.venv312``
    sources before rejecting their tests (measured on ARC: 34s across two reachability calls)."""
    return "pyvenv.cfg" in dir_filenames


def _build_graph(
    root: str, import_roots: tuple[str, ...] = ()
) -> tuple[dict[str, set[str]], dict[str, str], set[str]]:
    """``(module -> imported names, module -> path, modules whose imports are opaque)``."""
    graph: dict[str, set[str]] = {}
    paths: dict[str, str] = {}
    opaque: set[str] = set()
    skip = _SKIP_DIRS | _pytest_norecursedirs(root)
    for dirpath, dirnames, filenames in os.walk(root):
        if is_virtualenv_root(filenames):
            # A dir with pyvenv.cfg is a virtualenv: never our source or suite. Prune the whole
            # subtree WITHOUT parsing its files, so an installed dependency's sources are not
            # opened at all (the pre-session cost Fix A only rejected AFTER parsing).
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if d not in skip]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            p = os.path.join(dirpath, fn)
            try:
                with open(p, encoding="utf-8") as fh:
                    tree = ast.parse(fh.read(), filename=p)
            except (OSError, SyntaxError, ValueError):
                # Unparseable: cannot rule it out, so let it reach (never exclude on error).
                m = module_name(root, p, import_roots)
                paths[m] = p
                graph[m] = set()
                opaque.add(m)
                continue
            m = module_name(root, p, import_roots)
            paths[m] = p
            graph[m], is_opaque = _imports_of(tree, m)
            if is_opaque:
                opaque.add(m)
    return graph, paths, opaque


def _reaches(start: str, target: str, graph: dict[str, set[str]], opaque: set[str]) -> bool:
    """Can ``start`` transitively import ``target``? Opaque modules reach everything."""
    seen: set[str] = set()
    stack = [start]
    while stack:
        m = stack.pop()
        if m in seen:
            continue
        seen.add(m)
        if m in opaque:
            return True  # undecidable -> assume yes
        for dep in graph.get(m, ()):
            if dep == target or dep.startswith(target + "."):
                return True
            # `from a.b import c` records "a.b.c"; the module is "a.b". Walk the prefixes
            # so an attribute import still lands on the module that defines it.
            base = dep
            while base:
                if base == target:
                    return True
                if base in graph and base not in seen:
                    stack.append(base)
                if "." not in base:
                    break
                base = base.rsplit(".", 1)[0]
    return False


def within_declared_testpaths(rel_path: str, testpaths: list[str]) -> str:
    """Pure (#15/#67 — pinned): is a collected test file admissible under the project's declared
    pytest ``testpaths``?

    ``rel_path`` is the candidate's repo-relative path with ``/`` separators; ``testpaths`` the
    declared ``[tool.pytest.ini_options] testpaths`` (each a ``/``-normalized, slash-stripped
    directory). Returns:

    * ``"unrestricted"`` — no testpaths declared, so pytest itself collects from the whole tree and
      Detective must not narrow harder than pytest does (byte-identical to before this existed).
    * ``"within"`` — the file lives under a declared testpath: this project's own suite.
    * ``"foreign"`` — testpaths ARE declared and this file is outside every one, so pytest would
      never collect it. It is an installed dependency's ``test_*.py`` (a repo-walk reaches
      ``.venv*/site-packages/**``, which no name-based skip list can enumerate) — excluding it is
      matching pytest's authoritative boundary, not a heuristic guess.
    """
    if not testpaths:
        return "unrestricted"
    if any(rel_path == tp or rel_path.startswith(tp + "/") for tp in testpaths):
        return "within"
    return "foreign"


def _testpaths_floor(root: str, testpaths: tuple[str, ...]) -> list[str] | None:
    """The collection to hand pytest when reachability cannot NARROW but testpaths ARE declared:
    the declared test directories themselves. This is pytest's own default suite — strictly the
    real tests, never the whole repository root — so a ``None``-would-be case still cannot re-admit
    an installed dependency's suite. ``None`` (whole-root, today's behaviour) only when nothing is
    declared to bound it."""
    dirs = [os.path.join(root, tp) for tp in testpaths]
    return dirs or None


def reach_disposition(module_reaches: bool, fixture_reaches: bool) -> str:
    """Pure (#15 §4.3 — pinned): may a collected test execute the target's lines?

    Named codes, never a bool — the two positive reasons are DIFFERENT evidence of reach and
    must not collapse, because §4.3's soundness hole was exactly the fixture path going unseen:

      "direct"    the test's own module transitively imports the target — it can call it.
      "fixture"   the module does not, but an ANCESTOR conftest that DOES reach the target
                  could inject it through a fixture (autouse or requested). Kept as a sound
                  OVER-approximation: a conftest that cannot reach the target defines no
                  fixture that can, so this never keeps a provable non-reacher and — the whole
                  point of §4.3 — never drops a real fixture-mediated reacher.
      "unreached" neither holds — the test provably cannot execute a target line; safe to exclude.
    """
    if module_reaches:
        return "direct"
    if fixture_reaches:
        return "fixture"
    return "unreached"


def reachable_test_paths(
    root: str,
    target_file: str,
    target_module: str | None = None,
    import_roots: tuple[str, ...] = (),
    testpaths: tuple[str, ...] = (),
) -> list[str] | None:
    """Test files that could execute ``target_file``'s lines, bounded to pytest's ``testpaths``.

    When the static analysis cannot NARROW — no target module, target outside the tree, or every
    test reaching anyway — the result is the ``testpaths`` FLOOR (the declared test dirs), or
    ``None`` (collect everything, byte-identical to before) only when no testpaths are declared to
    bound it. A ``test_*.py`` outside every declared testpath is FOREIGN — an installed dependency's
    suite a repo-walk reached — and never collected: pytest's own boundary, not a name-skip guess.
    ``conftest.py`` is always included for the kept tests; a dropped conftest breaks collection.

    A test is kept when its own module reaches the target OR an ancestor ``conftest.py`` does — the
    latter closing §4.3's soundness hole: a fixture-only reacher imports nothing from the target, so
    a conftest that reaches it (and could inject it through a fixture) is what keeps the test in.
    """
    root = os.path.abspath(root)
    floor = _testpaths_floor(root, testpaths)
    tp_norm = [tp.replace(os.sep, "/").rstrip("/") for tp in testpaths]
    target = target_module or module_name(root, target_file, import_roots)
    if not target:
        return floor
    graph, paths, opaque = _build_graph(root, import_roots)
    if target not in graph:
        return floor  # target outside the tree -> cannot reason -> pytest's own suite

    keep: list[str] = []
    conftests: list[str] = []
    conftest_reach: dict[str, bool] = {}
    candidates: list[tuple[str, str]] = []
    # First pass: score every conftest's reach and gather in-scope candidate tests. Conftests
    # must be scored before tests are judged — dict order can place a fixture-only test before
    # the conftest that governs it, and its keep decision depends on that conftest's reach.
    for m, p in paths.items():
        base = os.path.basename(p)
        if base == "conftest.py":
            conftests.append(p)
            # A conftest that reaches the target may inject it through a fixture (§4.3); one that
            # cannot reach it defines no fixture that can. Recording the reach is what stops a
            # fixture-only test from being wrongly called unreachable.
            conftest_reach[p] = m == target or _reaches(m, target, graph, opaque)
            continue
        if not base.startswith("test_"):
            continue
        rel = os.path.relpath(p, root).replace(os.sep, "/")
        if within_declared_testpaths(rel, tp_norm) == "foreign":
            continue  # an installed dependency's test_*.py — pytest never collects it
        candidates.append((m, p))
    tests = len(candidates)
    for m, p in candidates:
        module_reaches = m == target or _reaches(m, target, graph, opaque)
        test_dir = os.path.dirname(os.path.abspath(p))
        fixture_reaches = any(
            test_dir == (cd := os.path.dirname(os.path.abspath(c))) or test_dir.startswith(cd + os.sep)
            for c, reached in conftest_reach.items()
            if reached
        )
        if reach_disposition(module_reaches, fixture_reaches) != "unreached":
            keep.append(p)
    if not tests:
        return floor
    if not keep:
        return floor  # nothing reachable is more likely a broken analysis than pytest's own suite
    return sorted(keep + _ancestor_conftests(conftests, keep))


def _ancestor_conftests(conftests: list[str], kept_tests: list[str]) -> list[str]:
    """Only the conftests that GOVERN a kept test file — never a sibling directory's.

    Every conftest used to be passed, on the reasoning that "pytest needs it to collect at all,
    and a dropped conftest turns a scoped collection into a broken one." True of an ANCESTOR and
    false of a sibling, and the difference is not cosmetic: a path argument is a COLLECTION
    TARGET, so naming `tests/integration/conftest.py` makes pytest import it even when nothing
    under `tests/integration/` is being collected. If that conftest happens to be broken — a
    stale import, the most ordinary drift there is — collection dies, the session binds zero
    callables, and every verdict in the repo becomes a false `0 pinned`. Measured on
    TailChasingFixer: exactly that, from one `ModuleNotFoundError` in a conftest governing a
    directory the run never touched.

    Dropping a non-ancestor cannot lose coverage, which is why this is safe in the one direction
    that matters: pytest loads conftests by DIRECTORY, walking from rootdir down to each collected
    file. A conftest that governs none of our files is one pytest would never have loaded — so
    naming it can only add a failure, never a fixture. Ancestors are still passed: for them the
    import happens either way, so this changes nothing.
    """
    dirs = {os.path.dirname(os.path.abspath(t)) for t in kept_tests}
    return [
        c
        for c in conftests
        if any(d == (cd := os.path.dirname(os.path.abspath(c))) or d.startswith(cd + os.sep) for d in dirs)
    ]
