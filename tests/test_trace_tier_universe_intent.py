"""trace_tier predicts over profile's universe — discovery is scoped to the regime's testpaths (#E1 §4.6).

Before: `trace_tier` called `discover_test_callables` with NO testpaths, so `audit --plan`'s fan-in /
mutant-budget numbers counted tests the mutation tier — which scopes to testpaths — never runs (an
installed dependency's suite a repo-walk reaches under `.venv*`, say). The two tiers must describe ONE
universe or the cheap tier's answer is about a different measurement than the profile it informs.
"""

from __future__ import annotations

from Detective.engine import trace_tier


def test_trace_tier_scopes_to_declared_testpaths(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[tool.pytest.ini_options]\ntestpaths = ["tests"]\n')
    (tmp_path / "mod.py").write_text("def f(n):\n    return n + 1\n")
    tdir = tmp_path / "tests"
    tdir.mkdir()
    (tdir / "test_f.py").write_text("from mod import f\n\n\ndef test_f():\n    assert f(1) == 2\n")
    # A FOREIGN test OUTSIDE testpaths — the kind a repo-walk reaches under an installed dep's tree.
    foreign = tmp_path / "vendored" / "lib"
    foreign.mkdir(parents=True)
    (foreign / "test_foreign.py").write_text("def test_dep():\n    assert True\n")

    tier = trace_tier("mod.py", "f", str(tmp_path))

    # Only the in-testpaths test is counted; the foreign one is excluded, matching profile's universe.
    assert tier.tests_total == 1
