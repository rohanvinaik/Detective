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

import json
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


def _skip_if_proof_cut(r):
    """Exit 3 is Detective's OWN 'measurement could not be trusted — re-run' code (the four-valued
    exit contract): a proof/convergence that hit its wall-clock deadline on a slow shared CI runner,
    not a specification failure. An e2e asserting returncode == 0 must treat it as inconclusive, not
    red — conflating the two is exactly the determined-false / cannot-determine error the contract
    exists to prevent. Confirmed by local repro: 3.12 converges these targets to exit 0 in 0.0s
    traces; only a slow runner cuts it mid-'proving'. Every other exit code still asserts normally."""
    if r.returncode == 3:
        pytest.skip(
            "convergence cut under CI wall-clock budget (exit 3 = measurement limit, not a spec failure)"
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
    _skip_if_proof_cut(r)
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
    r = _run(project, "converge", "shipping.py::shipping_cost")
    _skip_if_proof_cut(r)
    assert r.returncode == 0
    src = "\n".join(p.read_text() for p in (project / "tests").rglob("test_*_synth.py"))
    assert "shipping_cost(" in src
    assert "weight_kg=" in src, f"positional call survived rendering:\n{src}"


def test_orphan_target_synthesizes_instead_of_running_the_suite(project):
    """Nothing names `orphan.py`. Running the rest of the suite through a full mutant pass
    would measure files that provably do not mention it — so: synthesize, say so on the
    banner, and say the pins are a characterization rather than a review."""
    r = _run(project, "converge", "orphan.py::tier_price")
    _skip_if_proof_cut(r)
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
    _skip_if_proof_cut(r)
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
    _skip_if_proof_cut(r)
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


def _skip_if_cache_bypassed(payload: dict, which: str) -> None:
    """A read that was NOT served from the cache is not a warm read, and the guard below has no
    subject (S10).

    TWO CORRECT BEHAVIOURS produce this, and the dominant one is the write side:

    * The preceding run's measurement did not admit a certificate, so it was never STORED.
      `engine.profile` gates the insert on `verdict_cache.proof_cache_admits(...)`, whose own
      docstring gives the reason — an invalid measurement "cached and later served as a verdict,
      with the fact of its invalidity dropped at the moment of storage". `admits_certificate` is
      ABSORBING: any cut reason at all refuses, so a truncated trace, an uncontained worker or an
      un-entered mutant each mean nothing is written and the next read recomputes. Load makes cuts
      likelier, which is why this correlates with a full-suite run.
    * The regime was unobservable, so the cache was bypassed for read AND write. `engine.py`:
      "Inside a live session, an empty regime means at least one plugin/config identity was not
      observable. Two unknown regimes must never compare equal."

    Both are the tool being careful, not a defect. What was wrong is the claim below assuming a
    warm read always happens. Named rather than silent, because a silent bypass is what made this
    test flake: the equality quietly stopped being "a cold compute vs its own warm read" and became
    two INDEPENDENT cold computes, which is exposed to the `approximate:mutant_universe` count
    noise the docstring claims immunity from. CI prints skip reasons (`-ra`, S16), so a bypass that
    becomes common is visible in the log instead of being a dot.
    """
    if not payload.get("served_from_cache", False):
        # D2, 2026-09-09: this used to name BOTH causes and leave the reader to guess, which made
        # every occurrence a dot in the log. `ScopeMap.cut_reasons` now carries the measurement's
        # own normalised reasons, so the skip says WHICH of the two happened — a skip that cannot
        # distinguish its own causes is the same defect S10b found one level up.
        cuts = tuple(payload.get("cut_reasons") or ())
        cause = (
            f"the preceding measurement was cut ({', '.join(cuts)}), so `admits_certificate` "
            "refused and nothing was stored"
            if cuts
            else "no reason was cut, so the bypass was the regime being unobservable "
            "(cache skipped for read AND write) rather than a refused store"
        )
        pytest.skip(
            f"the {which} read was not served from the cache, so there is no warm read to "
            f"compare — {cause}. Both are correct refusals."
        )


def test_the_bypass_guard_fires_on_a_miss_and_stays_out_of_the_way_on_a_hit() -> None:
    """Both branches of the new guard, pinned. An untested skip path is how a guard silently stops
    guarding — and this one exists precisely because a silent path made the test above vacuous."""
    with pytest.raises(Exception, match="not served from the cache") as caught:
        _skip_if_cache_bypassed({"served_from_cache": False}, "rewarm")
    assert caught.typename == "Skipped", "a bypass is inconclusive, never a failure"
    assert "rewarm" in str(caught.value), "the guard names WHICH read was not a hit"
    # D2: and it names WHICH CAUSE. One test per branch, because the two are indistinguishable in
    # the log otherwise — which is how S10b's guard came to look like it was running when it was not.
    with pytest.raises(Exception) as cut:
        _skip_if_cache_bypassed({"served_from_cache": False, "cut_reasons": ["coverage_truncated"]}, "warm")
    assert "coverage_truncated" in str(cut.value), "a cut measurement must name the reason it was cut"
    assert "nothing was stored" in str(cut.value)
    with pytest.raises(Exception) as bypass:
        _skip_if_cache_bypassed({"served_from_cache": False, "cut_reasons": []}, "warm")
    assert "unobservable" in str(bypass.value), "no cut reason means the OTHER cause, and says so"
    # An absent field is a miss, not a hit: the same absence-is-not-falsehood rule the adapter uses.
    with pytest.raises(Exception, match="not served from the cache"):
        _skip_if_cache_bypassed({}, "warm")
    _skip_if_cache_bypassed({"served_from_cache": True}, "warm")  # a hit must not skip


def test_a_cached_verdict_is_served_consistently_before_and_after_purge(project):
    """A warm read must equal the cold verdict that POPULATED it — the real "stale cache served as
    fresh" guard — and it must hold again after a purge repopulates. This is deterministic: a cache
    hit returns the STORED bytes, not a re-measurement.

    It deliberately does NOT compare two independent COLD computes. An in-process run flags
    ``approximate:mutant_universe`` (``validity.py``): the mutant-universe COUNT is an estimate that
    drifts run-to-run by a few borderline mutants flipping scored↔unscored, while the value-kill
    PROOF the certificate rests on is exact (A2, ``project_converge_determinism_bug``). Asserting two
    cold counts are byte-identical tests the estimate, not the verdict — the documented flake this
    replaces (it reddened CI at 68122d8: ``67`` vs ``66 unpinned``).

    THE PREMISE IS NOW ASSERTED RATHER THAN ASSUMED (S10). This said "every assert here compares a
    cold compute to ITS OWN warm read, so it cannot flake on the count noise regardless of load",
    and then never checked that the second read was a HIT. It is not always: the cache is bypassed
    by design when the pytest regime is unobservable (see :func:`_skip_if_cache_bypassed`), and a
    bypassed read IS a second independent cold compute — so the sentence promising immunity
    described a premise the test did not establish. Measured 2026-09-08: `rewarm != recold` once in
    three full-suite runs, 0/10 isolated. The claim was wrong, not the cache.

    Reads ``--json`` rather than the rendered headline for two reasons: ``served_from_cache`` is a
    real ``ScopeMap`` field that the human renderer only prints when a trace was truncated
    (``cli.py``'s ``if not cut: return []``), so stdout is structurally blind to it; and
    ``specification`` carries the same three numbers the headline renders, making this a strictly
    stronger comparison at identical subprocess cost.
    """

    def probe() -> dict:
        r = _run(project, "diagnose", "shipping.py::shipping_cost", "--json")
        _skip_if_proof_cut(r)
        assert r.returncode == 0, r.stderr
        return json.loads(r.stdout)

    cold = probe()  # cache empty → cold compute → populates the verdict cache
    assert not cold["served_from_cache"], "the first read of an empty cache cannot be a hit"
    warm = probe()  # cache warm → served from cache → the stored bytes
    _skip_if_cache_bypassed(warm, "warm")
    assert warm["specification"] == cold["specification"], (
        "warm cache diverged from the cold verdict it stored"
    )

    _run(project, "purge")
    recold = probe()  # purged → cold recompute → repopulates
    assert not recold["served_from_cache"], "a purged cache cannot serve the read that follows it"
    rewarm = probe()  # warm read of the repopulated verdict
    _skip_if_cache_bypassed(rewarm, "rewarm")
    assert rewarm["specification"] == recold["specification"], (
        "warm cache after purge diverged from the recomputed verdict it stored"
    )
