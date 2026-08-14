"""A fixture-only reacher is admissible evidence — the §4.3 soundness hole, closed.

Defect (TEST_BASIS §4.3): `reachable_test_paths` kept a test file only when the test's OWN module
transitively imports the target (`m == target or _reaches(m, target)`). A test whose only path to
the target is an injected fixture imports nothing from it, so `_reaches` returned False and the
test was DROPPED — a real reacher called unreachable, i.e. a lost kill surfacing as an overstated
survivor. This is an UNDER-approximation: the one error direction the module forbids ("ANY doubt
returns None / includes the file").

Intent: reachability must be a sound OVER-approximation. A conftest that reaches the target may
inject it through a fixture (autouse or requested), so a test governed by such a conftest is kept.
A conftest that CANNOT reach the target defines no fixture that can, so its governed tests are not
kept on its account — the over-inclusion is bounded and degrades at worst to the testpaths floor,
never to a dropped reacher. Written from intent — the `*_synth` golden only pins current behaviour.
"""

from __future__ import annotations

import os
import tempfile

from Detective.reachability import reach_disposition, reachable_test_paths


def test_reach_disposition_names_three_distinct_codes():
    # The two positive reasons are different evidence and must not collapse to one bool.
    assert reach_disposition(module_reaches=True, fixture_reaches=False) == "direct"
    assert reach_disposition(module_reaches=True, fixture_reaches=True) == "direct"  # direct wins
    assert reach_disposition(module_reaches=False, fixture_reaches=True) == "fixture"
    assert reach_disposition(module_reaches=False, fixture_reaches=False) == "unreached"


def _fixture_repo(root: str) -> None:
    """A tree where the ONLY path from one test to the target is a conftest fixture."""

    def w(rel: str, body: str) -> None:
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(body)

    w("src/story/__init__.py", "")
    w("src/story/crystallize.py", "def serialize_rule(r):\n    return str(r)\n")
    # tests/conftest.py — NON-reaching (imports nothing from the target). Governs tests/plain/.
    w("tests/conftest.py", "import pytest\n")
    # tests/test_direct.py — imports the target directly. Kept as "direct".
    w(
        "tests/test_direct.py",
        "from src.story.crystallize import serialize_rule\n\n\n"
        "def test_d():\n    assert serialize_rule(1) == '1'\n",
    )
    # tests/withfix/conftest.py — REACHING: imports the target and exposes it as a fixture.
    w(
        "tests/withfix/conftest.py",
        "import pytest\nfrom src.story.crystallize import serialize_rule\n\n\n"
        "@pytest.fixture\ndef ser():\n    return serialize_rule\n",
    )
    # fixture-only reacher: imports NOTHING; reaches the target solely through `ser`. Kept as "fixture".
    w("tests/withfix/test_uses.py", "def test_x(ser):\n    assert ser(1) == '1'\n")
    # no-fixture test under the SAME reaching conftest — kept as sound over-inclusion, not a bug.
    w("tests/withfix/test_noparam.py", "def test_n():\n    assert True\n")
    # genuinely unreachable: no import, and its only ancestor conftest (tests/) does NOT reach. Dropped.
    w("tests/plain/test_plain.py", "def test_p():\n    assert True\n")


def _rels(root, paths):
    return sorted(os.path.relpath(p, root) for p in paths) if paths is not None else None


def test_fixture_only_reacher_is_kept_and_a_true_nonreacher_is_dropped():
    with tempfile.TemporaryDirectory() as td:
        root = os.path.abspath(td)
        _fixture_repo(root)
        kept = _rels(
            root,
            reachable_test_paths(
                root,
                "src/story/crystallize.py",
                target_module="src.story.crystallize",
                import_roots=(root,),
                testpaths=("tests",),
            ),
        )
        # The §4.3 fix: the fixture-only reacher survives (pre-fix it was dropped).
        assert "tests/withfix/test_uses.py" in kept
        # Direct importer survives, as always.
        assert "tests/test_direct.py" in kept
        # Sound over-inclusion: a no-fixture test under a REACHING conftest is kept, not dropped.
        assert "tests/withfix/test_noparam.py" in kept
        # Soundness is one-directional, not a floor: a test with no import and no reaching-conftest
        # ancestor is still excluded — the fix widens the kept set, it does not disable scoping.
        assert "tests/plain/test_plain.py" not in kept
