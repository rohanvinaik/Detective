"""Defer shape-hazardous tests from the speculative search — the pure admission decision.

Usability (ARC dogfood): the converge/diagnose widen (kill-measurement) speculatively traces tests
whose reachability is unconfirmed. A shape-hazardous test (non-hermetic — subprocess/thread/signal/
custom-collector) forces the expensive isolation path, and a 50s live-game system test traced per
widen step dominates cost while almost never being the minimal witness for a unit mutant. So a
non-hermetic test is DEFERRED from the speculative widen by default — and, critically, DISCLOSED,
never silently dropped: ``--include-shaped`` forces them back in.

INTENT test authored from the design: the truth table pins the total function completely, and the
key invariant is that deferral is a NAMED disposition (`defer_shaped`), distinct from admission —
so a caller can count and disclose it rather than lose a suite-kill in silence.
"""

from __future__ import annotations

import itertools

from Detective.engine import search_pool_admission


def test_admission_truth_table():
    # Two booleans, four rows, complete. A hermetic test is ALWAYS admitted regardless of the opt-in;
    # a non-hermetic test is admitted only when the caller opted in, else deferred (disclosed).
    for is_hermetic, include_shaped in itertools.product([False, True], repeat=2):
        if is_hermetic:
            expected = "admit"
        else:
            expected = "admit_shaped" if include_shaped else "defer_shaped"
        assert search_pool_admission(is_hermetic, include_shaped) == expected, (
            is_hermetic,
            include_shaped,
        )


def test_a_hermetic_test_is_never_deferred_even_without_the_opt_in():
    # The default must not touch the cheap floor — only speculative isolation-hazardous tests.
    assert search_pool_admission(True, False) == "admit"


def test_deferral_is_a_distinct_named_code_not_a_dropped_admit():
    # Deferral MUST be its own code so the caller can count + disclose it; collapsing it into a
    # falsy "not admitted" is exactly the silent-exclusion the design forbids.
    deferred = search_pool_admission(False, False)
    assert deferred == "defer_shaped"
    assert deferred not in {"admit", "admit_shaped"}


def test_opt_in_forces_a_shaped_test_back_into_the_pool():
    assert search_pool_admission(False, True) == "admit_shaped"


def test_classify_survivors_threads_include_shaped_into_its_internal_reprofile(monkeypatch, tmp_path):
    # Regression — the ~488s witness-pass bug. converge's witness pass IS classify_survivors, and it
    # RE-PROFILES internally when handed no profile_result. An earlier fix deferred converge's DIRECT
    # profile calls but MISSED this internal one, so its target-first widen traced shape-hazardous
    # unknowns undeferred (the whole cost). Pins the wiring directly: the flag the caller passes must
    # reach the internal profile() call, or the deferral never touches the pass that pays for it.
    import Detective.engine as engine

    (tmp_path / "m.py").write_text("def f(x):\n    return x + 1\n")
    (tmp_path / "test_m.py").write_text("from m import f\n\n\ndef test_f():\n    assert f(1) == 2\n")

    seen: dict = {}
    real = engine.profile

    def spy(*a, **k):
        seen["include_shaped"] = k.get("include_shaped")
        return real(*a, **k)

    monkeypatch.setattr(engine, "profile", spy)
    engine.classify_survivors("m.py", "f", str(tmp_path), include_shaped=False)
    assert seen.get("include_shaped") is False


def test_converge_threads_include_shaped_into_every_profile_including_the_finalize(tmp_path, monkeypatch):
    """Regression — the CLI defers by default, so EVERY profile() in the converge flow must inherit
    that intent: the loop, and each authoritative `final_result` re-profile. The FINALIZE re-profile
    (`converge.py`) was the one call that defaulted to include_shaped=True, so a defer run re-traced
    the slow speculative pool at the very end and — with the include_shaped-keyed cache — recorded
    under the full-measurement key in a deferred run. Spy on converge's `profile`: no call may leak."""
    import importlib

    # `Detective.converge` the attribute is the re-exported FUNCTION; get the MODULE to spy on its
    # `profile` binding (the one `_converge_impl` calls).
    cvmod = importlib.import_module("Detective.converge")

    (tmp_path / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\ntestpaths = ['tests']\nmarkers = ['detective: generated']\n"
    )
    (tmp_path / "m.py").write_text("def f(x):\n    if x > 0:\n        return x * 2\n    return -x\n")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_m.py").write_text("from m import f\n\ndef test_f():\n    assert f(1) == 2\n")

    seen: list = []
    real = cvmod.profile

    def spy(*a, **k):
        seen.append(k.get("include_shaped", "DEFAULTED"))
        return real(*a, **k)

    monkeypatch.setattr(cvmod, "profile", spy)
    cvmod.converge("m.py", "f", str(tmp_path), include_shaped=False, write_dir=str(tests), deadline_s=120.0)
    assert seen, "converge ran no profile() — the flow did not reach the finalize"
    assert all(v is False for v in seen), (
        f"a converge profile() call leaked the defer intent (include_shaped not threaded): {seen}"
    )
