"""Intent test for S11 — a test dependency the environment lacks is a silent hole.

Design: `docs/CORRECTNESS_REPAIRS_2026-09-08.md` §S11.

`tests/test_array_input_closure_intent.py` guards three tests with
`pytest.importorskip("numpy")`, which is CORRECT: a contributor without numpy should still be able
to run the suite. What was missing is that numpy was declared NOWHERE — not in `pyproject.toml`,
not in `uv.lock` — so CI, which installs from the lock, skipped all three every single run.

The only array test CI executed was the pure `array_source_disposition` truth table. Everything
that exercises the work against a real array never ran there: round-trip fidelity (dtype, shape,
empty dimensions), the trial-independence guarantee, the object / non-finite / over-bound
refusals, the type-binding check, and the end-to-end converge. The closure report's `42/42` receipt
was real and covered the DECISION; the shell around it was unverified in CI for a whole wave.

Discovered only because a pre-push `uv sync` pruned an ad-hoc local install and the skip count
moved 24 -> 27. Nothing else would have surfaced it: a skip is a dot.

This guard is deliberately about the DECLARATION, not about numpy being importable here. Asserting
importability would defeat the `importorskip` and break the contributor case it exists to serve.
What must not happen silently is the declaration going away.
"""

from __future__ import annotations

import pathlib
import tomllib

_PYPROJECT = pathlib.Path(__file__).resolve().parents[1] / "pyproject.toml"


def _dev_group() -> list[str]:
    data = tomllib.loads(_PYPROJECT.read_text())
    return list(data.get("dependency-groups", {}).get("dev", []))


def test_numpy_is_declared_so_the_array_tests_actually_run_in_ci():
    """Removing this must be a DELIBERATE act with a visible failure, not a quiet return to the
    state where three tests skip and the log looks identical."""
    assert any(spec.split(">=")[0].split("==")[0].strip().lower() == "numpy" for spec in _dev_group()), (
        "numpy is missing from [dependency-groups] dev — the array-input tests will skip in CI "
        "and the capability becomes indistinguishable from a broken one (S11)"
    )


def test_numpy_is_not_a_runtime_dependency():
    """The other half, and the reason `dev` is the right group. Detective imports numpy nowhere —
    `array_inputs.py` EMITS `numpy.array(...)` source into a target repo's tests, and the target is
    what needs numpy. Promoting it to a runtime dependency would make every consumer install a
    package the tool never imports."""
    data = tomllib.loads(_PYPROJECT.read_text())
    runtime = [
        s.split(">=")[0].split("==")[0].split("<")[0].strip().lower() for s in data["project"]["dependencies"]
    ]
    assert "numpy" not in runtime


def test_the_array_tests_are_guarded_rather_than_hard_importing():
    """The guard stays. A contributor without the dev group installed must still be able to run the
    suite — the repair is that CI now HAS numpy, not that the tests demand it unconditionally."""
    src = (pathlib.Path(__file__).resolve().parent / "test_array_input_closure_intent.py").read_text()
    assert 'importorskip("numpy")' in src
