"""Intent tests for target-error help reaching through --project-root (Detective #1).

#1 asked that the most likely first-run mistake — forgetting `::` — hand back the same function
menu the wrong-name case already gives. That was implemented: `_split_target` grew a
`project_root` parameter, it works, and a unit test covers it by passing `tmp_path` directly.

It was wired at ONE of seven call sites.

    detective diagnose src/m.py                              -> menu        (cwd == root)
    detective diagnose src/m.py --project-root /tmp/port     -> bare message

The unit was correct, the unit test passed the root explicitly, and the suite was green — while
six production paths resolved the target relative to the CWD instead. The tool's own sibling
error even says "the path is relative to --project-root", so it documented a convention this
path did not follow.

THE STRUCTURAL TEST IS THE POINT. `test_no_call_site_drops_the_project_root` parses cli.py and
asserts every `_split_target(...)` call passes a second argument. A behavioural test can only
cover the entry points someone thought to drive; this one fails on an eighth call site added
next year, which is exactly how the first six came to exist.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys

import pytest

import Detective.cli as cli_mod
from Detective.cli import _split_target


@pytest.fixture
def project(tmp_path):
    """A tiny project whose source sits UNDER the root, so cwd-relative resolution fails."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "m.py").write_text("def classify(n: int) -> str:\n    return 'pos' if n > 0 else 'neg'\n")
    return tmp_path


def test_the_menu_is_reachable_when_the_path_is_root_relative(project):
    """The exact regression: resolution must follow --project-root, not the CWD."""
    with pytest.raises(SystemExit) as exc:
        _split_target("src/m.py", str(project))
    msg = str(exc.value)
    assert "functions in that file: classify" in msg
    assert "src/m.py::classify" in msg


def test_a_nonexistent_file_still_gets_only_the_bare_format_message(project):
    """The fix must not invent a menu for a path that names nothing."""
    with pytest.raises(SystemExit) as exc:
        _split_target("src/nosuch.py", str(project))
    msg = str(exc.value)
    assert "must be 'file.py::function'" in msg
    assert "functions in that file" not in msg


def test_without_a_root_the_cwd_relative_case_still_works(project, monkeypatch):
    monkeypatch.chdir(project)
    with pytest.raises(SystemExit) as exc:
        _split_target("src/m.py")
    assert "functions in that file: classify" in str(exc.value)


def test_no_call_site_drops_the_project_root():
    """THE test that would have caught this, and catches the next one.

    Six of seven call sites passed one argument. Nothing about that is visible from the
    function, its unit tests, or a passing suite — only from the call graph. Parsing for it is
    what makes the wiring itself the thing under test.
    """
    source = open(cli_mod.__file__, encoding="utf-8").read()
    bare: list[int] = []
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_split_target"
            and len(node.args) + len(node.keywords) < 2
        ):
            bare.append(node.lineno)
    assert not bare, (
        f"_split_target called without a project_root at cli.py lines {bare} — "
        "the target-error menu is unreachable from those paths (#1)"
    )


def test_the_real_command_hands_back_the_menu_through_project_root(project):
    """End to end, because the unit was already correct when the CLI was not."""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [os.path.dirname(os.path.dirname(cli_mod.__file__)), env.get("PYTHONPATH", "")]
    )
    proc = subprocess.run(
        [sys.executable, "-m", "Detective.cli", "diagnose", "src/m.py", "--project-root", str(project)],
        capture_output=True,
        text=True,
        env=env,
        cwd=os.path.dirname(str(project)),
    )
    combined = proc.stdout + proc.stderr
    assert "functions in that file: classify" in combined, combined
