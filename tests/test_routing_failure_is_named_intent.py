"""Intent: a routing failure is a NAMED outcome that runs nothing — never a silent widening (#91).

The defect. Under the founder's 2026-09-05 ruling routing is the APPLICABILITY BOUND — the set of tests
a run may consult for one function — not an optimisation. Two paths still treated its failure as "run
everything", silently:

* `profile`'s target-first block caught any exception (`# BLE001: target-first is an optimisation;
  never fail the run`) and fell back to the whole collection. Measured on the fixture below with
  `_route_tests` raising: the not-consulted test ran 4 times for one function, the census was empty,
  there was NO cut reason, and the verdict came back gateable — so it was cacheable and certifiable.
* `_applicable_harvest_pool` (the capture harvest's bound) returned the WHOLE pool on ImportError.

Folded in: a raise AFTER `_session_baseline.set(_seeded)` (the shape admission sits below it) dropped
the token without resetting the ContextVar — measured, the seeded fork outlived the call in the
session's context, and the not-consulted test still ran.

The repair is a pinned decision, `engine.routing_outcome` → routed / unrouted / routing_failed, and a
cut reason of the same name that every layer consumes: the validity (never cached, never certified),
the certificate standing (`ungateable`) and ledger, converge's STOP block and FINAL banner, `--json`,
and converge's own loop (a blind measurement synthesizes nothing). Every behavioural test here runs
through a REAL pytest live session in a fresh subprocess, and counts executions of a no-path test the
way `test_engine_pool_is_the_consulted_set_intent.py` does — each FAILS on the previous code.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import types

import pytest

from Detective import engine as deng
from Detective.cli import _ROUTE_ADDRESSES, repair_measurement_route
from Detective.validity import CUT_REASONS, cut_reason_sentence, measurement_cut_reasons, normalize_validity

needs_target_first = pytest.mark.skipif(
    not getattr(deng, "_WESKER_TARGET_FIRST", False),
    reason="installed Wesker has no target-first seed/widen path",
)

# argv = root, mode. Prints the comparable facts as JSON on the last line; `ran` is how many times the
# no-path test executed. The injected failure is installed BEFORE the session for the profile modes,
# and AFTER a real profile for the harvest mode — so only the capture harvest's routing fails there.
_SESSION_SCRIPT = """
import sys, os, json
root, mode = sys.argv[1], sys.argv[2]
from Wesker.ci import run_with_live_suite
from Wesker.engine import _SESSION_BASELINE
import Detective.engine as deng
from Detective.validity import normalize_validity


def _raise_runtime(*a, **k):
    raise RuntimeError("injected routing failure")


def _raise_import(*a, **k):
    raise ImportError("cannot import name 'partition_live_callables'")


if mode == "route_raises":
    deng._route_tests = _raise_runtime
elif mode == "raise_after_seed":
    deng._admit_search_pool = _raise_runtime
out = {}


def body():
    import pkg
    before = _SESSION_BASELINE.get()
    if mode == "harvest_fails":
        r = deng.profile("pkg/mod.py", "weight", root, scope_tests=True, use_cache=False)
        out["profile_cut"] = list(normalize_validity(r).cut_reasons)
        deng._route_tests = _raise_import
        rep = deng.classify_survivors("pkg/mod.py", "weight", root, profile_result=r)
        # getattr: so the counter-test fails on what RAN, not on a missing field, against older code.
        out["routing_error"] = getattr(rep, "routing_error", None)
        out["note"] = rep.note or ""
        try:
            folded = normalize_validity(r, routing_failed=bool(out["routing_error"]))
            out["folded_cut"] = list(folded.cut_reasons)
        except TypeError:
            out["folded_cut"] = None
    else:
        r = deng.profile("pkg/mod.py", "target", root, scope_tests=True, use_cache=True)
        out["routing_outcome"] = getattr(r, "routing_outcome", None)
        out["routing_error"] = getattr(r, "routing_error", None)
        out["cut_reasons"] = list(normalize_validity(r).cut_reasons)
        out["test_routing"] = r.test_routing
        out["killed"] = r.total_killed
    out["ran"] = len(pkg.RAN)
    out["baseline_restored"] = _SESSION_BASELINE.get() is before


run_with_live_suite(
    root, body, target_files=[os.path.join(root, "pkg", "mod.py")], paths=[os.path.join(root, "tests")]
)
assert "ran" in out, "the live session never ran the body"
cache = os.path.join(root, ".detective", "verdict_cache.json")
out["cached_rows"] = len(json.load(open(cache))) if os.path.exists(cache) else 0
print(json.dumps(out))
"""

# argv = root, "json" | "text". The REAL `detective converge` command, `_route_tests` raising throughout.
_CLI_SCRIPT = """
import sys
root, mode = sys.argv[1], sys.argv[2]
import Detective.engine as deng


def _raise_runtime(*a, **k):
    raise RuntimeError("injected routing failure")


deng._route_tests = _raise_runtime
from Detective.cli import main

argv = ["converge", "pkg/mod.py::target", "--project-root", root]
if mode == "json":
    argv.append("--json")
code = main(argv)
import pkg
print(f"@@RAN={len(pkg.RAN)} EXIT={code}")
"""


def _repo(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\ntestpaths = ['tests']\nmarkers = ['detective: generated']\n"
    )
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("RAN = []\n")
    # `target` is the counter-test pattern's function (two candidates, one no-path test). `weight` is
    # one no synthesized input can exercise (every grid value raises on `payload["weight"]`), so its
    # classification must HARVEST a real input from the covering test — the harvest's routing path.
    (pkg / "mod.py").write_text(
        "from __future__ import annotations\n"
        "\n"
        "\n"
        "def target(x: int | None) -> int:\n"
        "    if x is None:\n"
        "        return 0\n"
        "    return x * 2\n"
        "\n"
        "\n"
        "def weight(payload):\n"
        '    return payload["weight"] * 2\n'
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_target.py").write_text(
        "from pkg.mod import target\n\n"
        "def test_none():\n    assert target(None) == 0\n\n"
        "def test_double():\n    assert target(3) == 6\n"
    )
    # A weak test (value-survivors remain), and a non-literal argument so call-site discovery cannot
    # hand classification the input: only the harvest, running this test, can.
    (tests / "test_weight.py").write_text(
        "from pkg.mod import weight\n\n"
        "def _payload():\n    return {'weight': 4}\n\n"
        "def test_weight_runs():\n    assert weight(_payload()) is not None\n"
    )
    # No static path to either function: never consulted, and it records every execution.
    (tests / "test_unrelated.py").write_text("import pkg\n\ndef test_u():\n    pkg.RAN.append('test_u')\n")
    (tmp_path / "_session_probe.py").write_text(_SESSION_SCRIPT)
    (tmp_path / "_cli_probe.py").write_text(_CLI_SCRIPT)
    return str(tmp_path)


def _run(script, *argv):
    proc = subprocess.run(
        [sys.executable, script, *argv],
        capture_output=True,
        text=True,
        env=os.environ,  # inherits PYTHONPATH (local) or the venv (pinned Wesker under uv run)
        timeout=300,
    )
    assert proc.returncode == 0, f"{script} {argv} failed:\n{proc.stdout}\n{proc.stderr}"
    return proc


def _session(root, mode):
    proc = _run(os.path.join(root, "_session_probe.py"), root, mode)
    return json.loads(proc.stdout.strip().splitlines()[-1])


# ── the pure decision ──────────────────────────────────────────────────────────────────────────────


def test_never_attempted_and_failed_are_different_facts():
    """THE collapse. Both used to leave `_pool = None` — "the collection stands" — so a failure read as
    a run that never routed. `raised` is irrelevant when nothing was attempted: nothing can fail that
    did not run."""
    assert deng.routing_outcome(attempted=False, raised=False) == deng.UNROUTED
    assert deng.routing_outcome(attempted=False, raised=True) == deng.UNROUTED
    assert deng.routing_outcome(attempted=True, raised=False) == deng.ROUTED
    assert deng.routing_outcome(attempted=True, raised=True) == deng.ROUTING_FAILED
    assert len({deng.ROUTED, deng.UNROUTED, deng.ROUTING_FAILED}) == 3


def test_the_failure_code_is_the_cut_reason_by_the_same_name():
    """One word for one fact: the outcome `profile` stamps is the reason `normalize_validity` emits."""
    assert deng.ROUTING_FAILED == "routing_failed"
    assert deng.ROUTING_FAILED in CUT_REASONS


def test_the_error_text_is_one_line_with_its_type():
    multi = RuntimeError("first line\n  Traceback detail that must not enter a report row")
    assert deng._routing_error_text(multi) == "RuntimeError: first line"
    assert deng._routing_error_text(ImportError()) == "ImportError"


# ── the validity layer consumes it ─────────────────────────────────────────────────────────────────


def test_a_failed_routing_on_the_result_cuts_the_measurement():
    stub = types.SimpleNamespace(routing_outcome=deng.ROUTING_FAILED)
    validity = normalize_validity(stub)
    assert validity.cut_reasons == ("routing_failed",)
    assert not validity.admits_certificate


def test_a_routed_or_unrouted_result_is_not_cut_and_absence_says_nothing():
    for code in (deng.ROUTED, deng.UNROUTED):
        assert normalize_validity(types.SimpleNamespace(routing_outcome=code)).cut_reasons == ()
    # A cache hit (a cut run is never stored) or a foreign result carries no outcome: no claim.
    assert normalize_validity(types.SimpleNamespace()).cut_reasons == ()


def test_the_harvests_failure_rides_in_beside_load_failed():
    """Classification's fact, supplied by the caller exactly as `load_failed` is."""
    validity = normalize_validity(types.SimpleNamespace(), routing_failed=True)
    assert validity.cut_reasons == ("routing_failed",)


def test_it_ranks_second_beside_the_load_failure():
    """Both mean nothing was observed, so both lead every other reason, in declaration order."""
    got = measurement_cut_reasons(
        True, True, True, "cut", "uncontained", True, True, True, True, True, True, routing_failed=True
    )
    assert got[:3] == ("target_load_failed", "routing_failed", "budget_exhausted")
    assert CUT_REASONS.index("routing_failed") == 1


def test_its_sentence_names_the_remedy_and_not_the_code():
    sentence = cut_reason_sentence("routing_failed")
    assert "routing_failed" not in sentence
    for must in ("ImportError", "report", "no test was authorised"):
        assert must in sentence, must


# ── the repair route consumes it ───────────────────────────────────────────────────────────────────


def test_it_routes_to_its_own_remedy_never_a_budget_or_the_residual():
    """S7's lesson: a reason added without a branch falls to `inspect_refusal`."""
    assert repair_measurement_route(("routing_failed",), False, False) == "fix_routing"
    assert _ROUTE_ADDRESSES["fix_routing"] == ("routing_failed",)


@pytest.mark.parametrize(
    "other",
    [
        "ambiguous_module_identity",
        "collection_incomplete",
        "mutant_not_entered",
        "budget_exhausted",
        "coverage_truncated",
        "uncontained_worker",
    ],
)
def test_nothing_observed_outranks_every_partial_observation(other):
    assert repair_measurement_route(("routing_failed", other), False, False) == "fix_routing"
    assert repair_measurement_route((other, "routing_failed"), False, False) == "fix_routing"


def test_a_module_that_will_not_import_still_leads():
    assert repair_measurement_route(("target_load_failed", "routing_failed"), False, False) == "fix_load"


# ── the engine, through a real live session ────────────────────────────────────────────────────────


@needs_target_first
def test_an_injected_routing_failure_runs_nothing_and_is_named(tmp_path):
    out = _session(_repo(tmp_path), "route_raises")
    assert out["ran"] == 0, "a not-consulted test was executed after routing failed"
    assert out["routing_outcome"] == deng.ROUTING_FAILED
    assert out["routing_error"] == "RuntimeError: injected routing failure"
    assert out["cut_reasons"] == ["routing_failed"]
    assert out["killed"] == 0  # no mutant met a test: an empty observation, named as one
    # No census: a partition that did not decide what ran must not be disclosed as if it had.
    assert not out["test_routing"]
    assert out["baseline_restored"]
    # Cut, so never stored as replayable proof (the cache admits only a certificate-grade result).
    assert out["cached_rows"] == 0


@needs_target_first
def test_a_raise_after_the_seed_restores_the_session_baseline(tmp_path):
    """The fold-in: the shape admission runs after `.set(_seeded)`. Its raise used to drop the token."""
    out = _session(_repo(tmp_path), "raise_after_seed")
    assert out["baseline_restored"], "the seeded fork outlived the call in the session's context"
    assert out["ran"] == 0
    assert out["cut_reasons"] == ["routing_failed"]
    assert not out["test_routing"]


def test_the_harvest_bound_never_widens_on_failure(tmp_path, monkeypatch):
    """Direct: an ImportError used to return the WHOLE pool. Any raise is now an empty, named pool."""

    def _raise_import(*a, **k):
        raise ImportError("cannot import name 'partition_live_callables'")

    monkeypatch.setattr(deng, "_route_tests", _raise_import)
    sentinel = [lambda: None, lambda: None]
    pool, not_consulted, error = deng._applicable_harvest_pool(
        sentinel, str(tmp_path), str(tmp_path / "m.py"), deng.ast.parse(""), "f", set()
    )
    assert pool == []
    assert not_consulted == 0
    assert error == "ImportError: cannot import name 'partition_live_callables'"


@needs_target_first
def test_a_harvest_whose_routing_fails_runs_nothing_and_cuts_the_run(tmp_path):
    """The profile routed fine; only the capture harvest's routing fails. It must run no test, carry
    the error, never claim the covering tests were consulted, and cut the run when folded in — a
    starved search must not stand as an equivalence claim about the code."""
    out = _session(_repo(tmp_path), "harvest_fails")
    assert out["profile_cut"] == []  # the measurement itself was sound
    assert out["ran"] == 0, "the harvest ran a not-consulted test after its routing failed"
    assert out["routing_error"] == "ImportError: cannot import name 'partition_live_callables'"
    assert "never call this function" not in out["note"]
    assert out["folded_cut"] == ["routing_failed"]
    assert out["baseline_restored"]


# ── the user-visible decision, through the real command ────────────────────────────────────────────


@needs_target_first
def test_converge_json_carries_the_named_outcome_and_runs_nothing(tmp_path):
    root = _repo(tmp_path)
    proc = _run(os.path.join(root, "_cli_probe.py"), root, "json")
    body, _, marker = proc.stdout.rpartition("@@RAN=")
    payload = json.loads(body)
    assert marker.split()[0] == "0", "the converge command executed a not-consulted test"
    assert "EXIT=3" in marker  # the four-valued contract: an invalid measurement, re-run
    assert payload["cut_reasons"] == ["routing_failed"]
    assert payload["validity"]["cut_reasons"] == ["routing_failed"]
    assert payload["routing_error"] == "RuntimeError: injected routing failure"
    assert payload["functionally_complete"] is False
    # A blind measurement writes nothing into the user's tree.
    assert payload["written_path"] is None
    ledger = json.loads((tmp_path / "tests" / "detective" / "certificates.json").read_text())
    row = ledger["pkg/mod.py::target"]
    assert row["standing"] == "ungateable"
    assert row["cut_reasons"] == ["routing_failed"]


@needs_target_first
def test_converge_report_names_the_failure_its_error_and_its_remedy(tmp_path):
    root = _repo(tmp_path)
    proc = _run(os.path.join(root, "_cli_probe.py"), root, "text")
    text, _, marker = proc.stdout.rpartition("@@RAN=")
    assert marker.split()[0] == "0"
    assert f"STOP:  {cut_reason_sentence('routing_failed')}" in text
    assert "RuntimeError: injected routing failure" in text
    final = next(line for line in text.splitlines() if line.startswith("FINAL "))
    assert "UNGATEABLE" in final and "COMPLETE" not in final
    # Not a gap to close: no budget, input or regime remedy leads.
    assert "DO THIS" not in text and "--trace-budget" not in text
