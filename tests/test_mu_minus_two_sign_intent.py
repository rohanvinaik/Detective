"""μ⁻ two-sign contract — Detective-side classification of the codomain operator (Fork 1 + Fork 2).

Regression + intent for the wiring that lets ``classify_survivors`` witness-search OUTPUT (μ⁻)
survivors. The bug this pins: ``classify_survivors`` rebuilt its ``by_id`` (survivor-id → mutant
object) by regenerating mutants ONE-SIGN — ``filter_categories(node, pure)`` with no ``two_sign`` —
so every OUTPUT survivor's content-addressed id was absent, it read as "un-buildable", and it fell to
``unclassified`` instead of being witness-searched. A signed function's →abs perturbation
(``return abs(x*2)``) is value-killable at ``x = -1``, so under the two-sign contract it MUST classify
killable with a witness, never land in ``unclassified``.

Each test uses a UNIQUE module name: the return-type harvest keys on the target's code object, and a
module name shared across tests would let a prior test's cached module shadow this one's (a fresh CLI
process never hits that — clean ``sys.modules`` — but an in-process test run does). Authored from
intent, not characterization.
"""

from __future__ import annotations

from Detective.engine import classify_survivors

_SIGNED = "def scale(x):\n    return x * 2\n"


def _repo(tmp_path, name, src=_SIGNED):
    # A DEGENERATE suite (scale(0)==0) leaves the sign/dependence OUTPUT perturbations surviving and
    # — critically for Fork 2 — gives the return-type harvest a passing test to run so the codomain
    # (int) is OBSERVED and the type-conditional perturbations (→negate/→abs) are generated at all.
    (tmp_path / f"{name}.py").write_text(src)
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / f"test_{name}.py").write_text(
        f"from {name} import scale\n\n\ndef test_zero():\n    assert scale(0) == 0\n"
    )
    (tmp_path / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\ntestpaths = ['tests']\nmarkers = ['detective: generated']\n"
    )
    return str(tmp_path), f"{name}.py"


def test_output_survivors_are_witness_classified_not_dropped_to_unclassified(tmp_path):
    root, f = _repo(tmp_path, "muclass")
    rep = classify_survivors(f, "scale", root, two_sign=True)

    # Some OUTPUT survivor must classify KILLABLE with a real distinguishing witness — proof the
    # codomain mutant was rebuilt and searched, not looked up as None.
    output_killable = [
        v for v in rep.killable if v.category == "OUTPUT" and v.killable and v.witness is not None
    ]
    assert output_killable, [(v.category, v.killable) for v in rep.killable]

    # And NO OUTPUT mutant may sit in `unclassified` (the id-absent → un-buildable symptom).
    assert not any("OUTPUT" in u for u in rep.unclassified), rep.unclassified


def test_fork2_abs_survivor_is_killable_with_a_negative_witness(tmp_path):
    # The exact case that exposed the gap: →abs on a signed return is value-killable ONLY on a
    # negative input (which the int grid already includes, -1). It must come back killable.
    root, f = _repo(tmp_path, "muabs")
    rep = classify_survivors(f, "scale", root, two_sign=True)
    abs_killable = [
        v for v in rep.killable if v.category == "OUTPUT" and "abs(" in (v.diff_summary or "") and v.killable
    ]
    assert abs_killable, [(v.diff_summary, v.killable) for v in rep.killable if v.category == "OUTPUT"]
    assert abs_killable[0].witness is not None


def test_one_sign_classification_has_no_output_verdicts(tmp_path):
    # The opt-in guarantee at the classification layer: a default (one-sign) run classifies no
    # OUTPUT survivor at all — the codomain operator is simply absent from the universe.
    root, f = _repo(tmp_path, "muone")
    rep = classify_survivors(f, "scale", root)
    assert not any(v.category == "OUTPUT" for v in rep.killable)
    assert not any("OUTPUT" in u for u in rep.unclassified)
