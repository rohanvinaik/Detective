"""shaped-defer on the CAPTURE harvest: classify_survivors holds shape-hazardous tests out of
`capture_call_inputs`, discloses the count, and re-admits them under --include-shaped.

The residual the widen-only fix (9a247f7 / 00597a9) left: the witness/rescue harvest RUNS every
discovered test to profile-hook its inputs, so a slow live-game system test is traced there even when
the widen already deferred it — a PURE function with candidate-equivalent survivors hits exactly this
(reported on ARC: `serialize_rule`, 9 slow traces). A spy on `capture_call_inputs` pins that the
shaped test is held out by default and re-admitted under include_shaped, and that the deferral count
is disclosed on `SurvivorReport.deferred_shaped` (never a silent drop). The spy returns [] so no
shape-hazardous test ever actually runs — the assertion is on which tests the harvest was HANDED.
"""

from __future__ import annotations

import Detective.engine as engine


def _repo(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    # `score` takes an OBJECT — scalar/list/dict synthesis all raise on `.n`, so nothing synthesized
    # exercises it and classify_survivors falls into the capture-harvest rescue (the residual path).
    (pkg / "mod.py").write_text(
        "def score(obj):\n    if obj.n > 0:\n        return obj.n * 2\n    return obj.n - 1\n"
    )
    (tmp_path / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\ntestpaths = ['tests']\nmarkers = ['detective: generated']\n"
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_score.py").write_text(
        "from pkg.mod import score\n\n"
        "class Obj:\n    def __init__(self, n):\n        self.n = n\n\n"
        "def test_pos():\n    assert score(Obj(3)) == 6\n"
    )
    # A SHAPE-HAZARDOUS (subprocess) test that names `score`, so static discovery includes it in the
    # harvest — the deferral is on its SHAPE, not its routing (capture runs every harvested test).
    (tests / "test_slow.py").write_text(
        "import subprocess\nfrom pkg.mod import score\n\n"
        "class Obj:\n    def __init__(self, n):\n        self.n = n\n\n"
        "def test_slow_shaped():\n    subprocess.run(['true'])\n    assert score(Obj(5)) == 10\n"
    )
    return str(tmp_path)


def _harvested(root, *, include_shaped, monkeypatch):
    """Return (test names the harvest was handed, the classification report). Spy returns [] so a
    shape-hazardous test is never actually executed — only its ADMISSION is under test."""
    seen: dict = {"names": []}

    def spy(original, tests, **kw):
        seen["names"].extend(getattr(t, "__name__", "?") for t in tests)
        return []

    monkeypatch.setattr(engine, "capture_call_inputs", spy)
    report = engine.classify_survivors("pkg/mod.py", "score", root, include_shaped=include_shaped)
    return seen["names"], report


def test_the_capture_harvest_defers_a_shaped_test_by_default_and_discloses(tmp_path, monkeypatch):
    names, report = _harvested(_repo(tmp_path), include_shaped=False, monkeypatch=monkeypatch)
    assert names, "the capture harvest never ran — the test did not exercise the residual path"
    assert "test_slow_shaped" not in names, "a shape-hazardous test reached the capture harvest"
    assert "test_pos" in names, "the hermetic test must still be harvested"
    assert report.deferred_shaped >= 1, "the deferral must be disclosed on the report, never silent"


def test_include_shaped_readmits_the_shaped_test_to_the_capture_harvest(tmp_path, monkeypatch):
    names, report = _harvested(_repo(tmp_path), include_shaped=True, monkeypatch=monkeypatch)
    assert "test_slow_shaped" in names, "--include-shaped must re-admit the shaped test to the harvest"
    assert report.deferred_shaped == 0, "nothing deferred under the opt-in, so nothing to disclose"
