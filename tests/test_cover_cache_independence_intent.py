"""audit's cover and redundant set do not depend on the trace cache's warmth (#145).

THE DEFECT (#145, measured 2026-10-26 on #104's fixture): `detective audit 'src/calc.py::f'` on one unedited
tree read a cover of 2 (cold cache, fully warm cache) and a cover of 3, with `test_dup` no longer redundant,
when the trace cache held only `test_pos` and `test_nonpos`. `--json` credited five of `test_pos`'s six kills
to `test_dup`: Wesker's matrix names the FIRST killer, and the cache decides the order.

These run the real CLI on the fixture in a disposable project, the verdict cache removed before each run,
and read `--json`: the cover size, the redundant set and each test's discharged kills must be IDENTICAL across
the cold, the fully warm and the partial cache.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

_PYPROJECT = '[tool.pytest.ini_options]\npythonpath = ["src"]\ntestpaths = ["tests"]\n'
_CALC = 'def f(x):\n    if x > 0:\n        return "pos"\n    return "nonpos"\n'
_TESTS = textwrap.dedent(
    """\
    import pytest
    from calc import f


    def test_pos():
        assert f(1) == "pos"


    def test_nonpos():
        assert f(0) == "nonpos"


    def test_dup():
        assert f(5) == "pos"


    @pytest.mark.parametrize("x", [3, 4])
    def test_more_pos(x):
        assert f(x) == "pos"
    """
)
_FINGERPRINTS = textwrap.dedent(
    """\
    import os, sys
    root = os.path.realpath(sys.argv[1])
    os.chdir(root)
    from Wesker.ci import discover_test_callables, callable_test_id, run_with_live_suite
    from Wesker.trace_cache import test_fingerprint

    def body():
        tests = discover_test_callables(root, "src/calc.py", ["f"])
        return [(callable_test_id(t), test_fingerprint(t)) for t in tests]

    for tid, fp in sorted(run_with_live_suite(root, body, target_files=["src/calc.py"])):
        print("FRESH", tid, fp)
    """
)


def _run(cwd: Path, *argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
        env=dict(os.environ),
    )


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "proj"
    (project / "src").mkdir(parents=True)
    (project / "tests").mkdir()
    (project / "pyproject.toml").write_text(_PYPROJECT)
    (project / "src" / "calc.py").write_text(_CALC)
    (project / "tests" / "test_calc.py").write_text(_TESTS)
    assert (
        _run(project, "-m", "Detective", "regime", "--migrate", "--project-root", str(project)).returncode
        == 0
    )
    return project


def _audit(project: Path) -> dict:
    (project / ".detective" / "verdict_cache.json").unlink(missing_ok=True)
    done = _run(project, "-m", "Detective", "audit", "src/calc.py::f", "--json")
    return json.loads(done.stdout)


def _reading(report: dict) -> tuple:
    discharged = {w["test"]: w["discharged"]["mutation_dims"] for w in report["function_basis"]["admitted"]}
    return report["minimal_test_count"], tuple(report["redundant_tests"]), discharged


@pytest.fixture(scope="module")
def readings(tmp_path_factory):
    project = _project(tmp_path_factory.mktemp("cover"))
    cache = project / ".wesker" / "trace_cache.json"
    cache.unlink(missing_ok=True)
    cold = _audit(project)
    full_cache = cache.read_text()
    warm = _audit(project)
    # Keep ONLY test_pos and test_nonpos, entries and outcome maps alike: the issue's partial state.
    fresh = {
        line.split()[1]: line.split()[2]
        for line in _run(project, "-c", _FINGERPRINTS, str(project)).stdout.splitlines()
        if line.startswith("FRESH ")
    }
    keep_ids = {t for t in fresh if t.endswith(("::test_pos", "::test_nonpos"))}
    assert len(keep_ids) == 2
    trimmed = json.loads(full_cache)
    trimmed["entries"] = {k: v for k, v in trimmed["entries"].items() if k in {fresh[t] for t in keep_ids}}
    assert len(trimmed["entries"]) == 2
    for name in ("outcome_fingerprints", "outcome_status"):
        trimmed[name] = {k: v for k, v in trimmed.get(name, {}).items() if k in keep_ids}
    trimmed["outcomes_observed"] = [t for t in trimmed.get("outcomes_observed", []) if t in keep_ids]
    cache.write_text(json.dumps(trimmed))
    partial = _audit(project)
    return {"cold": cold, "warm": warm, "partial": partial}


def test_the_fixture_reads_the_covers_the_issue_expects(readings):
    cold = readings["cold"]
    assert cold["cover_standing"] == "full_matrix"
    assert cold["minimal_test_count"] == 2
    assert len(cold["redundant_tests"]) == 3
    assert {t.rsplit("::", 1)[1] for t in cold["redundant_tests"]} == {
        "test_dup",
        "test_more_pos[3]",
        "test_more_pos[4]",
    }


def test_the_cover_and_the_redundant_set_are_the_same_on_a_cold_a_warm_and_a_partial_cache(readings):
    cold, warm, partial = (_reading(readings[k]) for k in ("cold", "warm", "partial"))
    assert cold[:2] == warm[:2] == partial[:2]


def test_each_tests_discharged_kills_are_identical_across_the_three_cache_states(readings):
    cold, warm, partial = (_reading(readings[k])[2] for k in ("cold", "warm", "partial"))
    assert cold == warm == partial
    # and they are the relation, not a credit: test_dup is credited its kills although test_pos ran first
    dup = next(t for t in cold if t.endswith("test_dup"))
    pos = next(t for t in cold if t.endswith("test_pos"))
    assert cold[dup] and set(cold[dup]) <= set(cold[pos])


def test_the_attribution_is_named_as_the_full_matrix_on_every_state(readings):
    assert {r["function_basis"]["kill_attribution"] for r in readings.values()} == {"full_matrix"}
    assert {r["cover_standing"] for r in readings.values()} == {"full_matrix"}
