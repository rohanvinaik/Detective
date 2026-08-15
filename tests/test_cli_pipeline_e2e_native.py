"""End-to-end: drive the real CLI over a real project and check what it PROMISES.

Every other suite here exercises a function. This one runs `detective` as a subprocess
against a throwaway project, because the failures it guards were all invisible to the
unit tests and to a green CI:

* discovery handed one function the whole repo's suite — nothing failed, it was only
  slow, and slow does not turn a build red;
* progress was written with `\\r` and no terminal check, so a captured run arrived as one
  line and read as a run that had printed nothing;
* an unparseable target exited through a raw SyntaxError traceback;
* `decompose --apply` REWRITES the user's source, and "behaviour preserved" is the one
  claim in this tool that must never be taken on trust.

Each test states the promise it is holding the CLI to. They share one built project via a
module-scoped fixture (converge is not free) and each runs in its own copy where it writes.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# The target: branching + arithmetic + an error path, small enough to converge quickly.
_SOURCE = '''\
"""Shipping cost estimation."""


def shipping_cost(weight_kg, distance_km, express=False, member=False):
    """Cost in dollars, rounded to cents."""
    if weight_kg <= 0:
        raise ValueError("weight must be positive")
    base = 4.50
    if weight_kg > 20:
        base += (weight_kg - 20) * 1.20
    elif weight_kg > 5:
        base += (weight_kg - 5) * 0.60
    fee = (distance_km - 100) * 0.05 if distance_km > 100 else 0.0
    total = base + fee
    if express:
        total *= 1.75
    if member:
        total *= 0.90
    return round(total, 2)
'''

_TESTS = """\
import pytest

from shipping import shipping_cost


def test_small_parcel():
    assert shipping_cost(2, 50) == 4.50


def test_zero_weight_rejected():
    with pytest.raises(ValueError):
        shipping_cost(0, 10)
"""

# A second module nothing references — the synthesized-only branch.
_ORPHAN = """\
def tier_price(units, member=False):
    if units <= 0:
        raise ValueError("units must be positive")
    price = 10.0
    if units > 100:
        price += (units - 100) * 0.25
    elif units > 10:
        price += (units - 10) * 0.50
    if member:
        price *= 0.9
    return round(price, 2)
"""

# Unrelated tests that must never be pulled into a scope for shipping.py.
_NOISE = "\n\n".join(f"def test_noise_{i}():\n    assert {i} + 1 == {i + 1}" for i in range(12))


def _console_script() -> Path:
    """The installed entry point, including the interpreter encoded in its shebang."""
    name = "detective.exe" if sys.platform == "win32" else "detective"
    script = Path(sys.executable).with_name(name)
    assert script.is_file(), f"installed-boundary test requires the console script beside {sys.executable}"
    return script


def _run(project, *args, timeout=300):
    """The CLI as a user gets it: the real console script in a captured subprocess."""
    return subprocess.run(
        [str(_console_script()), *args, "--project-root", str(project)],
        cwd=str(project),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    root = tmp_path_factory.mktemp("cli_e2e")
    (root / "shipping.py").write_text(_SOURCE)
    (root / "orphan.py").write_text(_ORPHAN)
    (root / "syntaxerr.py").write_text("def broken(:\n")
    tests = root / "tests"
    tests.mkdir()
    (tests / "test_shipping.py").write_text(_TESTS)
    (tests / "test_noise.py").write_text(_NOISE + "\n")
    done = _run(root, "regime", "--migrate")
    assert done.returncode == 0, done.stderr
    assert (root / "pyproject.toml").exists(), "regime --migrate must leave a usable config"
    return root


@pytest.fixture
def project(built, tmp_path):
    """A fresh copy per test that writes, so ordering can never matter."""
    dst = tmp_path / "proj"
    shutil.copytree(built, dst)
    return dst


# ── the promises ────────────────────────────────────────────────────────────


def test_analysis_is_scoped_to_the_target(project):
    """One function must not drag in the whole suite. `test_noise.py` names nothing in
    shipping.py, so the traced baseline must not include its 12 tests."""
    r = _run(project, "diagnose", "shipping.py::shipping_cost")
    assert r.returncode == 0, r.stderr
    traced = [ln for ln in r.stderr.splitlines() if "baseline traced" in ln]
    assert traced, f"no baseline line in:\n{r.stderr}"
    count = int(traced[-1].split("·")[1].strip().split()[0])
    assert count <= 4, f"scope leaked: traced {count} tests, the noise file should be excluded"


def test_captured_output_has_no_carriage_returns(project):
    """Piped, logged, or read by an agent, the run must be lines — not one redrawn line.
    This is the check that would have caught the progress reporter having no tty gate."""
    r = _run(project, "diagnose", "shipping.py::shipping_cost")
    assert "\r" not in r.stderr, "progress redraw leaked into non-terminal output"
    assert "\r" not in r.stdout
    for line in r.stderr.splitlines():
        assert line == line.rstrip(), f"trailing erase-padding in a log line: {line!r}"


def test_converge_writes_a_suite_that_actually_passes(project):
    """The product is a test file in someone else's repo. It has to run there, under
    their pytest, and be clean under a formatter — not merely be emitted."""
    r = _run(project, "converge", "shipping.py::shipping_cost")
    assert r.returncode == 0, r.stderr
    assert "FINAL" in r.stdout
    # Synth suites live in their own home under tests/ (issue #21) — rglob so
    # the assertion follows the certificate, not one directory layout.
    written = list((project / "tests").rglob("test_*_synth.py"))
    assert written, "converge reported success but wrote nothing"
    run = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(project / "tests")],
        cwd=str(project),
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert run.returncode == 0, f"generated suite does not pass:\n{run.stdout}\n{run.stderr}"
    fmt = subprocess.run(
        [sys.executable, "-m", "ruff", "format", "--check", *[str(p) for p in written]],
        cwd=str(project),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert fmt.returncode == 0, f"emitted file would fail a host's format gate:\n{fmt.stdout}"


def test_generated_calls_name_their_arguments(project):
    """`f(1, 2, 3, 4)` is unreadable as a permanent regression test and the parameter names
    are already on the node. Keyword form, whenever the signature allows it."""
    assert _run(project, "converge", "shipping.py::shipping_cost").returncode == 0
    src = "\n".join(p.read_text() for p in (project / "tests").rglob("test_*_synth.py"))
    assert "shipping_cost(" in src
    assert "weight_kg=" in src, f"positional call survived rendering:\n{src}"


def test_orphan_target_synthesizes_instead_of_running_the_suite(project):
    """Nothing names `orphan.py`. Running the rest of the suite through a full mutant pass
    would measure files that provably do not mention it — so: synthesize, say so on the
    banner, and say the pins are a characterization rather than a review."""
    r = _run(project, "converge", "orphan.py::tier_price")
    assert r.returncode == 0, r.stderr
    assert "synthesized" in r.stdout, f"banner did not mark the origin:\n{r.stdout}"
    assert "CHARACTERIZATION" in r.stdout, "a suite nobody has read must say so"
    # Named for the whole func_key, module included: `orphan.py::tier_price`. Two modules
    # defining the same function name would otherwise claim one file and the second converge
    # would overwrite the first's suite.
    assert list((project / "tests").rglob("test_orphan_tier_price_*_synth.py"))


def test_decompose_apply_preserves_behaviour(project):
    """The load-bearing claim: --apply rewrites the user's source and asserts the behaviour
    survived. Checked against the ORIGINAL module over a grid that crosses every branch and
    both tier boundaries — not by trusting the word PROVEN."""
    before = (project / "shipping.py").read_text()
    r = _run(project, "decompose", "shipping.py::shipping_cost", "--apply")
    assert r.returncode == 0, r.stderr
    after = (project / "shipping.py").read_text()
    if after == before:
        pytest.skip("no seam was applied; nothing to verify")

    (project / "_original.py").write_text(before)
    probe = project / "_equiv_probe.py"
    probe.write_text(
        "import _original, shipping\n"
        "bad = []\n"
        "for w in (0.5, 5, 5.01, 10, 20, 20.01, 25, 100):\n"
        "    for d in (0, 99.9, 100, 100.1, 250):\n"
        "        for e in (False, True):\n"
        "            for m in (False, True):\n"
        "                try: a = _original.shipping_cost(w, d, e, m)\n"
        "                except Exception as exc: a = type(exc).__name__\n"
        "                try: b = shipping.shipping_cost(w, d, e, m)\n"
        "                except Exception as exc: b = type(exc).__name__\n"
        "                if a != b: bad.append((w, d, e, m, a, b))\n"
        "print('MISMATCHES', len(bad), bad[:3])\n"
    )
    out = subprocess.run(
        [sys.executable, str(probe)], cwd=str(project), capture_output=True, text=True, timeout=120
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.startswith("MISMATCHES 0"), f"decompose changed behaviour: {out.stdout}"


def test_extracted_helper_keeps_the_callers_parameter_order(project):
    """Alphabetising a signature is deterministic and unreadable. The helper's parameters
    follow the enclosing function's own header."""
    r = _run(project, "decompose", "shipping.py::shipping_cost", "--apply")
    assert r.returncode == 0, r.stderr
    src = (project / "shipping.py").read_text()
    if "def _" not in src:
        pytest.skip("no helper extracted")
    helper = next(ln for ln in src.splitlines() if ln.startswith("def _"))
    params = [p.strip() for p in helper.split("(", 1)[1].rsplit(")", 1)[0].split(",") if p.strip()]
    order = ["weight_kg", "distance_km", "express", "member"]
    present = [p for p in order if p in params]
    assert [p for p in params if p in order] == present, (
        f"helper parameters are not in the caller's order: {params}"
    )


@pytest.mark.parametrize(
    "target",
    ["nope.py::f", "shipping.py::nosuchfn", "shipping.py", "syntaxerr.py::broken"],
)
@pytest.mark.parametrize("command", ["diagnose", "audit", "converge"])
def test_bad_targets_refuse_cleanly(project, command, target):
    """A user error must never reach the terminal as a traceback — the one shape a caller
    cannot tell from a crash, and the one a small model driving this has nothing to route on."""
    r = _run(project, command, target)
    assert r.returncode != 0, f"{command} {target} should not report success"
    combined = r.stdout + r.stderr
    assert "Traceback (most recent call last)" not in combined, combined
    assert "detective:" in combined, f"no actionable message for {command} {target}:\n{combined}"


def test_purge_is_honest_when_there_is_nothing_to_purge(project):
    """A no-op has to read as a no-op, not as a success that removed something."""
    r = _run(project, "purge")
    assert r.returncode == 0, r.stderr
    assert "nothing to purge" in (r.stdout + r.stderr).lower()


def test_a_cached_verdict_is_served_consistently_before_and_after_purge(project):
    """A warm read must equal the cold verdict that POPULATED it — the real "stale cache served as
    fresh" guard — and it must hold again after a purge repopulates. This is deterministic: a cache
    hit returns the STORED bytes, not a re-measurement.

    It deliberately does NOT compare two independent COLD computes. An in-process run flags
    ``approximate:mutant_universe`` (``validity.py``): the mutant-universe COUNT is an estimate that
    drifts run-to-run by a few borderline mutants flipping scored↔unscored, while the value-kill
    PROOF the certificate rests on is exact (A2, ``project_converge_determinism_bug``). Asserting two
    cold counts are byte-identical tests the estimate, not the verdict — the documented flake this
    replaces (it reddened CI at 68122d8: ``67`` vs ``66 unpinned``). Every assert here compares a
    cold compute to ITS OWN warm read, so it cannot flake on the count noise regardless of load."""

    def headline(r: subprocess.CompletedProcess) -> str:
        assert r.returncode == 0, r.stderr
        return next(ln for ln in r.stdout.splitlines() if "diagnose ·" in ln)

    def diagnose():
        return _run(project, "diagnose", "shipping.py::shipping_cost")

    cold = headline(diagnose())  # cache empty → cold compute → populates the verdict cache
    warm = headline(diagnose())  # cache warm → served from cache → the stored bytes
    assert warm == cold, "warm cache diverged from the cold verdict it stored"

    _run(project, "purge")
    recold = headline(diagnose())  # purged → cold recompute → repopulates
    rewarm = headline(diagnose())  # warm read of the repopulated verdict
    assert rewarm == recold, "warm cache after purge diverged from the recomputed verdict it stored"
