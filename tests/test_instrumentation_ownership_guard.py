"""#32: ONE owner of interpreter instrumentation, `Wesker/monitoring.py`. An AST guard, and here no
Detective module is exempt.

THE DEFECT. Three modules once each installed and restored their own process-global hook
(`sys.settrace`, `sys.setprofile`), and a second owner silently replaces the first. The migration to
`sys.monitoring` through the broker removed every call, but nothing stopped a new one: "no hook
remains" was a measurement taken once, not a property the suite checks.

THE GUARD. No module of the `Detective` package may

* call or reference `sys.settrace`, `sys.setprofile`, `threading.settrace`, `threading.setprofile`
  or their `_all_threads` forms (by attribute, by `from ... import`, or by a string handed to
  `getattr`), nor
* claim or drive a `sys.monitoring` tool: `use_tool_id`, `free_tool_id`, `clear_tool_id`,
  `get_tool`, `register_callback`, `set_events`, `get_events`, `set_local_events`,
  `get_local_events`, `restart_events`, or one of the `*_ID` constants.

`sys.monitoring.events.*` (event constants a caller hands to the broker) and `DISABLE` / `MISSING`
are vocabulary, not ownership, and stay allowed. The scanner is a pure function over source text so
the guard itself is tested against code that must be refused.

Wesker carries the same guard for its own package (`tests/test_instrumentation_ownership_guard.py`
there), with `Wesker/monitoring.py` as the one exempt module.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import Detective

_HOOKS = {
    "settrace",
    "setprofile",
    "settrace_all_threads",
    "setprofile_all_threads",
}
_HOOK_HOLDERS = {"sys", "threading"}
_MONITORING_OWNERSHIP = {
    "use_tool_id",
    "free_tool_id",
    "clear_tool_id",
    "get_tool",
    "register_callback",
    "set_events",
    "get_events",
    "set_local_events",
    "get_local_events",
    "restart_events",
    "DEBUGGER_ID",
    "COVERAGE_ID",
    "PROFILER_ID",
    "OPTIMIZER_ID",
}


def instrumentation_violations(source: str, filename: str = "<src>") -> list[str]:
    """Every ownership violation in ``source`` as ``file:line: what`` (pure)."""
    tree = ast.parse(source, filename)
    found: list[str] = []
    # `import sys as s` must not be a way round the guard.
    holders = set(_HOOK_HOLDERS)
    monitoring_roots = {"sys.monitoring"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname and alias.name in _HOOK_HOLDERS:
                    holders.add(alias.asname)
                    if alias.name == "sys":
                        monitoring_roots.add(f"{alias.asname}.monitoring")

    def _dotted(node: ast.AST) -> str:
        parts: list[str] = []
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if isinstance(node, ast.Name):
            parts.append(node.id)
        return ".".join(reversed(parts))

    for node in ast.walk(tree):
        where = f"{filename}:{getattr(node, 'lineno', 0)}"
        if isinstance(node, ast.Attribute):
            dotted = _dotted(node)
            head, _, tail = dotted.rpartition(".")
            if head in holders and tail in _HOOKS:
                found.append(f"{where}: references {dotted}")
            if head in monitoring_roots and tail in _MONITORING_OWNERSHIP:
                found.append(f"{where}: drives {dotted}")
        elif isinstance(node, ast.ImportFrom):
            names = {a.name for a in node.names}
            if node.module in _HOOK_HOLDERS and names & _HOOKS:
                found.append(f"{where}: imports {sorted(names & _HOOKS)} from {node.module}")
            if node.module == "sys.monitoring" and names & _MONITORING_OWNERSHIP:
                found.append(f"{where}: imports {sorted(names & _MONITORING_OWNERSHIP)} from sys.monitoring")
            if node.module == "sys" and "monitoring" in names:
                found.append(f"{where}: imports the sys.monitoring module itself")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in _HOOKS | _MONITORING_OWNERSHIP:
                found.append(f"{where}: names {node.value!r} as a string")
    return found


def _package_files() -> list[Path]:
    # The owner is Wesker/monitoring.py: NO Detective module is exempt.
    return sorted(Path(Detective.__file__).resolve().parent.rglob("*.py"))


def test_no_module_but_the_owner_touches_interpreter_hooks_or_tool_ids():
    files = _package_files()
    assert len(files) > 10, "the scan found no package: the guard would pass on nothing"
    violations: list[str] = []
    for path in files:
        violations += instrumentation_violations(path.read_text(), str(path))
    assert violations == [], "\n".join(violations)


@pytest.mark.parametrize(
    "source",
    [
        "import sys\nsys.settrace(None)\n",
        "import sys\nsys.setprofile(f)\n",
        "import threading\nthreading.settrace(f)\n",
        "import threading\nthreading.setprofile_all_threads(f)\n",
        "import sys\nsys.settrace_all_threads(f)\n",
        "from sys import settrace\n",
        "from threading import setprofile\n",
        "import sys\ngetattr(sys, 'settrace')(None)\n",
        "import sys\nsys.monitoring.use_tool_id(3, 'x')\n",
        "import sys\nsys.monitoring.set_events(3, 0)\n",
        "import sys\nsys.monitoring.register_callback(3, 1, f)\n",
        "import sys\nsys.monitoring.set_local_events(3, c, 0)\n",
        "import sys\nx = sys.monitoring.COVERAGE_ID\n",
        "from sys.monitoring import use_tool_id\n",
        "from sys import monitoring\n",
        "import sys\nhook = sys.settrace\n",
        "import sys as s\ns.settrace(None)\n",
        "import threading as t\nt.setprofile(None)\n",
        "import sys as s\ns.monitoring.use_tool_id(1, 'x')\n",
    ],
)
def test_the_scanner_refuses_each_spelling(source):
    assert instrumentation_violations(source), source


@pytest.mark.parametrize(
    "source",
    [
        "import sys\nev = sys.monitoring.events.LINE\n",
        "import sys\nx = sys.monitoring.DISABLE\n",
        "import sys\nsys.gettrace()\n",
        "import threading\nthreading.enumerate()\n",
        "def settrace_notes():\n    return 'a comment about tracing'\n",
    ],
)
def test_the_scanner_does_not_refuse_vocabulary_or_unrelated_names(source):
    assert instrumentation_violations(source) == [], source
