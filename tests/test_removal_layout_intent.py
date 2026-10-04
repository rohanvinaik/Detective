"""A removal leaves the file spaced as it was, so a formatter-clean file stays clean (#106).

Measured while dogfooding `audit --remove` on Detective itself (2026-10-04): the editor deleted each
definition plus ONE blank line after it. A top-level separator is two blank lines, so a mid-file removal
left three; and a block's last definition has no blank after it, so the separator before it stayed behind
as trailing blank lines. Every edited file then failed `ruff format --check`, a gate this repository's CI
runs over the whole tree. The generated goldens had pinned the wrong layout, as characterization does:
removing `test_a` from a two-function file was captured with a leading blank line.

The rule: a definition goes with exactly one of the two separators around it, the one after it when another
statement follows it in its block, the one before it when it is the block's last statement. The spacing left
between its neighbours is then one the file already had.
"""

from __future__ import annotations

import subprocess
import sys
import tokenize
from pathlib import Path

import pytest

from Detective.suite_edit import remove_definition_from_source

_MODULE = (
    "import pytest\n\n\n"
    "def test_a():\n    assert 1\n\n\n"
    "@pytest.mark.slow\n"
    "def test_b():\n    assert 2\n\n\n"
    "def test_c():\n    assert 3\n"
)

_CLASSES = (
    "class TestC:\n"
    "    def test_a(self):\n        assert 1\n\n"
    "    def test_b(self):\n        assert 2\n\n"
    "    def test_c(self):\n        assert 3\n\n\n"
    "def test_d():\n    assert 4\n"
)


def test_a_mid_file_function_takes_the_two_blanks_after_it():
    assert remove_definition_from_source(_MODULE, "test_b") == (
        "removed",
        "import pytest\n\n\ndef test_a():\n    assert 1\n\n\ndef test_c():\n    assert 3\n",
    )


def test_the_first_function_after_the_imports_leaves_their_separator_alone():
    assert remove_definition_from_source(_MODULE, "test_a") == (
        "removed",
        "import pytest\n\n\n@pytest.mark.slow\ndef test_b():\n    assert 2\n\n\n"
        "def test_c():\n    assert 3\n",
    )


def test_the_last_function_takes_the_blanks_before_it_and_leaves_no_trailing_blank():
    assert remove_definition_from_source(_MODULE, "test_c") == (
        "removed",
        "import pytest\n\n\ndef test_a():\n    assert 1\n\n\n"
        "@pytest.mark.slow\ndef test_b():\n    assert 2\n",
    )


def test_a_class_s_first_method_takes_the_blank_after_it_so_none_follows_the_class_line():
    assert remove_definition_from_source(_CLASSES, "TestC.test_a") == (
        "removed",
        "class TestC:\n"
        "    def test_b(self):\n        assert 2\n\n"
        "    def test_c(self):\n        assert 3\n\n\n"
        "def test_d():\n    assert 4\n",
    )


def test_a_mid_class_method_keeps_the_one_blank_between_methods():
    assert remove_definition_from_source(_CLASSES, "TestC.test_b") == (
        "removed",
        "class TestC:\n"
        "    def test_a(self):\n        assert 1\n\n"
        "    def test_c(self):\n        assert 3\n\n\n"
        "def test_d():\n    assert 4\n",
    )


def test_a_class_s_last_method_leaves_the_two_blanks_before_the_next_top_level_function():
    assert remove_definition_from_source(_CLASSES, "TestC.test_c") == (
        "removed",
        "class TestC:\n"
        "    def test_a(self):\n        assert 1\n\n"
        "    def test_b(self):\n        assert 2\n\n\n"
        "def test_d():\n    assert 4\n",
    )


def test_a_lone_method_becomes_pass_and_both_separators_stay():
    source = "class TestOnly:\n    def test_lone(self):\n        assert 1\n\n\ndef test_d():\n    assert 4\n"
    assert remove_definition_from_source(source, "TestOnly.test_lone") == (
        "removed",
        "class TestOnly:\n    pass\n\n\ndef test_d():\n    assert 4\n",
    )


def test_a_comment_after_the_removed_function_stays_with_what_follows_it():
    source = (
        "def test_a():\n    assert 1\n\n\n"
        "def test_b():\n    assert 2\n\n\n"
        "# section\ndef test_c():\n    assert 3\n"
    )
    assert remove_definition_from_source(source, "test_b") == (
        "removed",
        "def test_a():\n    assert 1\n\n\n# section\ndef test_c():\n    assert 3\n",
    )


def test_spacing_the_edit_does_not_touch_is_left_as_it_was():
    """The edit is not a formatter: a one-blank gap elsewhere stays one blank."""
    source = "def test_a():\n    assert 1\n\ndef test_b():\n    assert 2\n\n\ndef test_c():\n    assert 3\n"
    assert remove_definition_from_source(source, "test_c") == (
        "removed",
        "def test_a():\n    assert 1\n\ndef test_b():\n    assert 2\n",
    )


# --------------------------------------------------------------------------------------
# Through the CLI: the dogfood's own shape
# --------------------------------------------------------------------------------------

# Every line carries ONE apostrophe, so tokenizing from any of them opens a string that never closes.
_DOCSTRING = (
    '    """It\'s zero,\n'
    "    that's the boundary,\n"
    "    it's the one value\n"
    "    that's not positive,\n"
    "    and it's pinned\n"
    '    on its own line, so it\'s here."""\n'
)
_KEPT_HEAD = 'from calc import f\n\n\ndef test_pos():\n    assert f(1) == "pos"\n\n\n'
_KEPT_TAIL = "def test_nonpos():\n" + _DOCSTRING + '    assert f(0) == "nonpos"\n'


def _console_script() -> Path:
    name = "detective.exe" if sys.platform == "win32" else "detective"
    script = Path(sys.executable).with_name(name)
    assert script.is_file(), f"installed-boundary test requires the console script beside {sys.executable}"
    return script


def test_a_mid_file_removal_above_a_docstring_completes_and_leaves_the_file_formatted(tmp_path):
    """A redundant test deleted ABOVE a test whose docstring spans several lines, as in the dogfood run.

    The in-process re-check then reads that test from its pre-edit first line, which now falls inside the
    docstring. Wesker's test fingerprint caught only OSError/TypeError around `inspect.getsource`, so the
    CLI died there with a `tokenize.TokenError` traceback, after the removal had been made. Now the run
    completes, and the file it edited is spaced as the formatter would space it.
    """
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "calc.py").write_text(
        'def f(x):\n    if x > 0:\n        return "pos"\n    return "nonpos"\n'
    )
    test_file = tmp_path / "tests" / "test_calc.py"
    test_file.write_text(_KEPT_HEAD + 'def test_dup():\n    assert f(5) == "pos"\n\n\n' + _KEPT_TAIL)
    (tmp_path / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\ntestpaths = ["tests"]\npythonpath = ["src"]\n'
    )
    run = subprocess.run(
        [str(_console_script()), "audit", "src/calc.py::f", "--remove", "--project-root", str(tmp_path)],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    assert "Traceback" not in run.stdout + run.stderr
    assert "removed 1: tests/test_calc.py::test_dup" in run.stdout
    assert test_file.read_text() == _KEPT_HEAD + _KEPT_TAIL
    # The precondition, so this cannot pass vacuously: `test_nonpos` was defined on line 12, and line 12
    # of the edited file now falls inside its docstring, the shape `inspect.getsource` cannot tokenize.
    stale = test_file.read_text().splitlines(keepends=True)[11:]
    with pytest.raises((SyntaxError, tokenize.TokenError)):
        list(tokenize.generate_tokens(iter(stale).__next__))
