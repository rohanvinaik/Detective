"""suite_edit resolves a callable's ORIGIN; removal is a module-level act.

Two defects this file pins, both found live on a post-decompose wrapper:

* ``_locate`` read ``__code__.co_filename`` raw, so discovery's pytest-backend
  WRAPPERS (closures defined in Wesker's own modules) "located" every test in
  ``pytest_runner.py`` — removal parsed that file, found no test defs, and
  no-opped with an empty ``not_found`` (the name was "located", just uselessly).
  One name-collision away from rewriting a file in site-packages.
* the redundant set is single-function evidence, but deletion is module-wide:
  a test pointless for the wrapper was the only killer of the helper's ``<=``
  boundary mutant. ``module_safe_removals`` is the filter that keeps it.

Fixture-free where possible; ``profile`` is patched per the house convention
(see test_audit_native.py) — these tests pin wiring, not Wesker's engine.
"""

from __future__ import annotations

import textwrap
from unittest.mock import patch

from _support import make_pr

from Detective.audit import module_safe_removals
from Detective.suite_edit import apply_removals


def _write(path, body: str):
    path.write_text(textwrap.dedent(body))
    return path


def _project(tmp_path):
    """A target module and one test file, on disk — _locate parses both."""
    _write(
        tmp_path / "m.py",
        """
        def f(x):
            return x + 1
        """,
    )
    test_file = _write(
        tmp_path / "test_m.py",
        """
        from m import f

        def test_a():
            assert f(1) == 2

        def test_b():
            assert f(0) == 1
        """,
    )
    return test_file


def _wrapper(name: str, **attrs):
    """A discovery-style wrapper: its OWN code object lives in THIS file."""

    def run() -> None:  # pragma: no cover — never called
        pass

    run.__name__ = name
    for k, v in attrs.items():
        setattr(run, k, v)
    return run


def test_locate_resolves_wrapper_origin_tag(tmp_path):
    """A tagged wrapper locates to the TEST file, not to the wrapper's module."""
    test_file = _project(tmp_path)
    fake = [_wrapper("test_a", __wesker_origin__=str(test_file))]
    with patch("Detective.suite_edit.discover_test_callables", return_value=fake):
        report = apply_removals("m.py", str(tmp_path), ["test_a"])
    assert report.removed == ("test_a",)
    assert report.not_found == ()
    assert "def test_a" not in test_file.read_text()
    assert "def test_b" in test_file.read_text()


def test_locate_never_edits_outside_project_root(tmp_path):
    """An origin that resolves outside the root (the wrapper's own module) is
    refused, and the accounting SAYS so instead of a bare 'removed nothing'."""
    _project(tmp_path)
    # No tag, no __wrapped__ — resolution falls through to co_filename, which
    # is THIS test file: outside tmp_path, exactly the site-packages shape.
    fake = [_wrapper("test_a")]
    with patch("Detective.suite_edit.discover_test_callables", return_value=fake):
        report = apply_removals("m.py", str(tmp_path), ["test_a"])
    assert report.removed == ()
    assert report.not_found == ("test_a",)  # located-nowhere is REPORTED
    assert report.files_changed == ()


def test_locate_follows_wrapped_function(tmp_path):
    """No tag, but __wrapped__ points at the real test — the live-item shape."""
    test_file = _project(tmp_path)
    # A function whose code object carries the TEST FILE's path — the only
    # property __wrapped__ resolution reads; importing the module is beside it.
    ns: dict = {}
    exec(compile("def test_b():\n    pass\n", str(test_file), "exec"), ns)
    fake = [_wrapper("test_b", __wrapped__=ns["test_b"])]
    with patch("Detective.suite_edit.discover_test_callables", return_value=fake):
        report = apply_removals("m.py", str(tmp_path), ["test_b"])
    assert report.removed == ("test_b",)


def _pr_for(function_key, kill_matrix, line_coverage):
    pr = make_pr(function_key=function_key)
    pr.kill_matrix = kill_matrix
    pr.line_coverage = line_coverage
    return pr


def test_module_safe_removals_retains_a_siblings_only_killer(tmp_path):
    """The wrapper's 'pointless' test that is the helper's only killer stays."""
    _write(
        tmp_path / "m.py",
        """
        def helper(x):
            return x * 2

        def f(x):
            return helper(x) + 1
        """,
    )
    sibling_pr = _pr_for(
        "m.py::helper",
        # test_boundary is helper's ONLY killer; test_extra kills nothing and
        # covers nothing of helper — uninvolved there, safe to drop.
        {"MUT_H1": ["test_boundary"]},
        {"test_boundary": [2], "test_extra": []},
    )
    with patch("Detective.audit.profile", return_value=sibling_pr):
        safe, retained = module_safe_removals(
            "m.py", "f", str(tmp_path), ["test_boundary", "test_extra"]
        )
    assert retained == {"test_boundary": "helper"}
    assert safe == ("test_extra",)


def test_module_safe_removals_passes_sibling_redundant_tests(tmp_path):
    """Redundant for the target AND redundant for every sibling → deletable."""
    _write(
        tmp_path / "m.py",
        """
        def helper(x):
            return x * 2

        def f(x):
            return helper(x) + 1
        """,
    )
    sibling_pr = _pr_for(
        "m.py::helper",
        # Both tests kill MUT_H1 and cover the same line: the minimal cover
        # keeps one, so the OTHER is redundant for the sibling too.
        {"MUT_H1": ["test_one", "test_two"]},
        {"test_one": [2], "test_two": [2]},
    )
    with patch("Detective.audit.profile", return_value=sibling_pr):
        safe, retained = module_safe_removals("m.py", "f", str(tmp_path), ["test_two"])
    assert safe == ("test_two",)
    assert retained == {}


def test_module_safe_removals_no_siblings_is_all_safe(tmp_path):
    _write(
        tmp_path / "m.py",
        """
        def f(x):
            return x + 1
        """,
    )
    safe, retained = module_safe_removals("m.py", "f", str(tmp_path), ["test_a"])
    assert safe == ("test_a",)
    assert retained == {}
