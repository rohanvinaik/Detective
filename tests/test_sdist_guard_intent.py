"""Hand-written intent tests for the sdist reproducibility guard.

Authored from INTENT, not from the implementation, because the generated suite for
``sdist_verdict`` is a characterization: it pins what the function does, so anything wrong today
would be pinned wrong. These state what the function is FOR.

The defect that motivated the guard, 2026-09-09, one command before Detective 1.0.0 went to PyPI:
the sdist was 38 MB compressed / 115 MB unpacked / 9,537 files, of which 110.71 MB was
``docs/theory/operator_completeness/proofs/.lake`` — 6.9 GB of vendored Lean packages on disk,
untracked by git, gitignored, and packaged anyway.

Size was the symptom, not the defect. The defect is that an sdist containing untracked files is a
function of the BUILDER's working tree rather than of the commit: two people running ``uv build``
on the same sha ship different tarballs, and no one downstream can tell which they got.

The mechanism, measured with a minimal probe project rather than assumed: hatchling's VCS-ignore
default reads the ROOT ``.gitignore`` only, and a nested one is invisible to it. So a path can be
genuinely gitignored — absent from ``git status``, absent from ``git ls-files``, invisible to every
habit a developer has — and ship. Which is why the guard asks git what it tracks instead of asking
what is ignored.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_sdist.py"


def _load():
    """Import the build script by path — it is deliberately not a package member."""
    spec = importlib.util.spec_from_file_location("check_sdist_under_test", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check_sdist = _load()
sdist_verdict = check_sdist.sdist_verdict


def test_every_member_tracked_is_reproducible():
    """The whole claim: this artifact is derivable from the commit."""
    members = ["pkg-1.0/Detective/cli.py", "pkg-1.0/README.md", "pkg-1.0/PKG-INFO"]
    tracked = ["Detective/cli.py", "README.md"]
    assert sdist_verdict(members, tracked, ["PKG-INFO"]) == "reproducible"


def test_untracked_member_is_the_defect():
    """The real 1.0.0 case, in miniature: one gitignored build artifact riding along."""
    members = [
        "pkg-1.0/Detective/cli.py",
        "pkg-1.0/docs/theory/operator_completeness/proofs/.lake/packages/mathlib/Mathlib.lean",
    ]
    tracked = ["Detective/cli.py"]
    assert sdist_verdict(members, tracked, ["PKG-INFO"]) == "carries_untracked"


def test_empty_sdist_is_not_reproducible():
    """An empty archive must not pass by vacuous truth.

    "Every one of its zero files is tracked" is formally true and operationally a lie: an sdist
    with no members is a broken build, and answering ``reproducible`` would route the reader past
    the one fact that matters. This is why the function returns three codes rather than a bool —
    the bool would have collapsed a broken build into a clean bill of health.
    """
    assert sdist_verdict([], ["Detective/cli.py"], ["PKG-INFO"]) == "empty"


def test_generated_members_are_not_violations():
    """``PKG-INFO`` is synthesised by the backend, so git could not possibly track it."""
    assert sdist_verdict(["pkg-1.0/PKG-INFO"], [], ["PKG-INFO"]) == "reproducible"


def test_generated_allowlist_is_a_parameter_not_a_hardcode():
    """A member is exempt only because it was DECLARED generated, never because it looks it."""
    assert sdist_verdict(["pkg-1.0/PKG-INFO"], [], []) == "carries_untracked"


def test_version_prefix_is_stripped_before_comparison():
    """Members carry ``<name>-<version>/``; the tracked set does not.

    Comparing the two spellings without stripping would report every file as untracked — a
    universal false alarm, which is the failure direction that gets a guard disabled rather than
    fixed.
    """
    assert sdist_verdict(["detective_spec-1.0.0/Detective/cli.py"], ["Detective/cli.py"], []) == (
        "reproducible"
    )


def test_a_malformed_prefixless_member_fails_toward_the_alarm():
    """A member with no ``<name>-<version>/`` prefix is malformed, and the guard flags it.

    This test was originally written asserting the opposite — that a prefix-less member should
    compare whole and pass — and it failed. The code was right and the assertion was wrong, which
    is worth recording rather than quietly deleting.

    Every member of a well-formed sdist carries the prefix; that is the format. So stripping the
    first segment is not a heuristic, it is the inverse of how the archive was built, and a member
    lacking the prefix means the archive is not the thing this guard was asked about. In that state
    ``_stem`` strips a real directory component and compares the wrong string, which yields
    ``carries_untracked``.

    That is the correct direction to be wrong in. A false alarm on a malformed archive costs
    someone a look; a false pass would let an unexamined artifact reach PyPI, which is the exact
    outcome the guard exists to prevent. Pinned here so a later "cleanup" that makes the comparison
    lenient has to argue with a test that names the tradeoff.
    """
    assert sdist_verdict(["Detective/cli.py"], ["Detective/cli.py"], []) == "carries_untracked"


def test_tracked_file_absent_from_the_sdist_is_not_a_violation():
    """The check is ONE-DIRECTIONAL on purpose, and this is the test that says so.

    Under-inclusion is a legitimate, declared choice: ``AGENTS.md`` and ``CLAUDE.md`` are tracked
    and deliberately excluded because they carry absolute ``/Users/...`` paths. Over-inclusion is
    the defect, because it is the direction that makes the artifact depend on the builder. A guard
    that flagged both would fire on every intentional exclusion and be turned off within a week.
    """
    assert sdist_verdict(["pkg-1.0/README.md"], ["README.md", "CLAUDE.md", "AGENTS.md"], []) == (
        "reproducible"
    )


def test_verdict_is_one_of_the_three_named_codes():
    """No fourth state, and never a bare bool: each code has a distinct remedy."""
    for members, tracked in (([], []), (["a-1/x"], []), (["a-1/x"], ["x"])):
        assert sdist_verdict(members, tracked, []) in {
            "reproducible",
            "carries_untracked",
            "empty",
        }


def test_the_shipped_artifact_itself_passes():
    """End-to-end through the real object, not the internal function alone.

    Skipped rather than failed when no sdist has been built: "I could not ask" and "I asked and it
    is wrong" are different facts, and the suite must not report the first as the second.
    """
    # Globbed rather than pinned to a version, so a release bump does not silently turn this into
    # a permanent skip — which is the quiet way an end-to-end test stops being one.
    built = sorted((_SCRIPT.parent.parent / "dist").glob("detective_spec-*.tar.gz"))
    if not built:
        pytest.skip("no built sdist in dist/ — run `uv build --out-dir dist` first")
    assert check_sdist.main([str(built[-1])]) == 0
