"""Intent: a failing floor is named first, even when every synthesized input raises (Detective #124).

THE DEFECT. `order_total` raises on every input (it adds a float to a list). Its three routed intent
tests fail on current code. `detective audit 'orders.py::order_total' --two-sign` printed AUTHOR
INPUT ("every candidate raised; provide a real sample") and never named the failing tests: no
``⚠ FAILING NOW`` row at all. A sample cannot make those tests pass — the code or the tests must
change, which is the call FAILING NOW hands to a person.

TWO CAUSES, both measured:

1. The engine's ``failing_tests`` lists only tests that failed on an ASSERTION. These three fail with
   a TypeError the code under test raises during the call, which pytest itself reports as ``failed``
   — the engine's typed baseline outcome (`trace_evidence`, Wesker #17) records exactly that, but
   nothing consumed it, so audit's ``failing_tests`` came back empty (``test_count`` 3,
   ``failing_tests`` []). Converge's floor gate (#114) read the same list and missed them too.
2. Audit's ladder ranked ``provide_sample`` — a fact about the SEARCH's synthesized inputs — above
   ``fix_failing_test``, a fact about the suite. A failing floor outranks the numbers it invalidates;
   only a measurement that could not run or cannot be trusted (``fix_load``, ``repair_measurement``)
   still outranks it, as converge's standing ranks ``ungateable`` above ``floor_failing``.

THE RULING (the floor comes first, one derivation): `audit.function_failing_tests` takes the engine's
typed outcomes as well; a test whose typed outcome is ``failed`` is failing whatever it raised, while
``error`` (setup or teardown: a fixture, an import), ``skipped``, ``xfailed`` and ``unrecorded`` stay
out — the ambiguity the engine itself declines to read as a wrong expectation. Audit and converge
consume the SAME derivation, so they cannot disagree about one suite, warm or cold.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from types import SimpleNamespace

import pytest

from Detective.audit import baseline_typed_outcomes, function_failing_tests
from Detective.cli import audit_next_action

# ------------------------------------------------------------------ the typed derivation (pure)

KILL: dict[str, list[str]] = {}
LINES = {
    "tests/test_orders.py::test_order_total": [18],
    "tests/test_orders.py::test_setup_error": [18],
    "tests/test_orders.py::test_skipped": [18],
    "tests/test_other.py::test_other_raises": [],  # raised, but never ran this function
}


@pytest.mark.parametrize(
    ("outcome", "is_floor"),
    [
        ("failed", True),  # the call raised (a TypeError here): its expectation does not hold
        ("error", False),  # setup or teardown failed: a fixture, an import — ambiguous about the code
        ("skipped", False),
        ("xfailed", False),
        ("passed", False),
        ("unrecorded", False),  # an engine that did not type it: never inferred to be failing
    ],
)
def test_a_typed_failure_is_the_floor_whatever_the_call_raised(outcome, is_floor):
    typed = {"tests/test_orders.py::test_order_total": outcome}
    expected = ("tests/test_orders.py::test_order_total",) if is_floor else ()
    assert function_failing_tests([], KILL, LINES, typed) == expected


def test_a_typed_failure_that_never_ran_the_function_is_not_its_floor():
    typed = {"tests/test_other.py::test_other_raises": "failed", "unseen.py::t": "failed"}
    assert function_failing_tests([], KILL, LINES, typed) == ()


def test_the_engines_list_leads_and_a_test_in_both_is_named_once():
    typed = {
        "tests/test_orders.py::test_order_total": "failed",
        "tests/test_orders.py::test_skipped": "failed",
    }
    failing = ["tests/test_orders.py::test_skipped"]  # the engine listed it (an assertion)
    assert function_failing_tests(failing, KILL, LINES, typed) == (
        "tests/test_orders.py::test_skipped",
        "tests/test_orders.py::test_order_total",
    )


def test_no_typed_outcomes_is_the_assertion_only_derivation():
    failing = ["tests/test_orders.py::test_order_total"]
    assert function_failing_tests(failing, KILL, LINES) == ("tests/test_orders.py::test_order_total",)
    assert function_failing_tests(failing, KILL, LINES, {}) == ("tests/test_orders.py::test_order_total",)
    assert function_failing_tests([], KILL, LINES, None) == ()


def test_the_accessor_reads_the_engines_ledger_and_infers_nothing():
    row = SimpleNamespace
    result = SimpleNamespace(
        trace_evidence=(
            row(test_id="a::t", baseline_outcome="failed", provenance="fresh"),
            row(test_id="b::t", baseline_outcome="passed", provenance="fresh"),
            # Replayed from the verdict cache: it may never PROVE (#20), but the floor is a refusal,
            # and the engine's assertion list reaches the derivation through the same cache.
            row(test_id="r::t", baseline_outcome="failed", provenance="replayed"),
            row(test_id="", baseline_outcome="failed"),  # no identity: nothing to name
            row(test_id="u::t", baseline_outcome="unrecorded"),  # cached before outcomes were typed
            row(test_id="c::t"),  # no outcome attribute at all
        )
    )
    assert baseline_typed_outcomes(result) == {"a::t": "failed", "b::t": "passed", "r::t": "failed"}
    assert baseline_typed_outcomes(SimpleNamespace()) == {}  # an engine with no ledger
    assert baseline_typed_outcomes(SimpleNamespace(trace_evidence=None)) == {}


# ------------------------------------------------------------------ the ladder: the floor comes first


def test_a_failing_floor_outranks_a_sample_request():
    assert audit_next_action("provide_sample", True, 0, 1, 0, False, 0, False, 15) == "fix_failing_test"
    assert audit_next_action("provide_sample", False, 0, 1, 0, False, 0, False, 15) == "provide_sample"


@pytest.mark.parametrize("block", ["fix_load", "repair_measurement"])
def test_a_measurement_that_could_not_run_still_outranks_the_floor(block):
    # The same rank converge's standing gives `ungateable` above `floor_failing`: what an untrustworthy
    # measurement observed — failing tests included — is not yet evidence.
    assert audit_next_action(block, True, 0, 0, 0, False, 0, False, 0) == block


# ------------------------------------------------------------------ the issue's fixture, real CLI

ORDERS = '''
    """Order arithmetic: the total of one order line, and of an order."""

    def line_total(quantity, unit_price):
        """The total of one order line: its quantity times its unit price.

        Operations:
            ARITHMETIC: quantity times unit price
        """
        return quantity * unit_price

    def order_total(order):
        """The total of an order: the sum of its lines' totals. An empty order totals 0.0.

        Operations:
            ARITHMETIC: the running sum of the line totals
            VALUE: 0.0 for an empty order
        """
        return 0.0 + [line_total(line[0], line[1]) for line in order]
'''
ORDER_TESTS = """
    from orders import line_total, order_total


    def test_line_total():
        assert line_total(2, 1.5) == 3.0


    def test_order_total():
        assert order_total([(2, 1.5), (1, 4.0)]) == 7.0
        assert order_total([]) == 0.0
        assert order_total([(3, 2.0)]) == 6.0


    def test_order_total_depends_on_its_lines():
        assert order_total([(1, 1.0)]) != order_total([(2, 1.0)])


    def test_order_total_always_answers():
        result = order_total([(1, 1.0)])
        assert result is not None and result == 1.0
"""
FAILING = (
    "tests/test_orders.py::test_order_total",
    "tests/test_orders.py::test_order_total_always_answers",
    "tests/test_orders.py::test_order_total_depends_on_its_lines",
)


def _project(tmp_path):
    project = tmp_path / "proj"
    (project / "tests").mkdir(parents=True)
    (project / "orders.py").write_text(textwrap.dedent(ORDERS))
    (project / "tests" / "test_orders.py").write_text(textwrap.dedent(ORDER_TESTS))
    return project


def _cli(project, *args: str) -> subprocess.CompletedProcess:
    script = os.path.join(os.path.dirname(sys.executable), "detective")
    assert os.path.isfile(script), f"the installed console script is required beside {sys.executable}"
    return subprocess.run(
        [script, *args, "--project-root", str(project)],
        cwd=str(project),
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )


def test_audit_names_the_failing_floor_instead_of_asking_for_a_sample(tmp_path):
    project = _project(tmp_path)
    run = _cli(project, "audit", "orders.py::order_total", "--two-sign")
    out = run.stdout + run.stderr
    assert run.returncode == 0, out
    assert "⚠ FAILING NOW" in out and all(t in out for t in FAILING), out
    assert "AUTHOR INPUT" not in out and "provide a real sample" not in out, out
    assert "DO THIS:  pytest tests/test_orders.py::test_order_total" in out, out
    assert "is the TEST's expectation wrong, or is the CODE broken?" in out, out
    as_json = _cli(project, "audit", "orders.py::order_total", "--two-sign", "--json")
    payload = json.loads(as_json.stdout)
    assert payload["decision"]["code"] == "fix_failing_test"
    assert tuple(payload["failing_tests"]) == FAILING


def test_converge_reads_the_same_floor_cold_and_warm(tmp_path):
    # The second run is served from the verdict cache, whose trace rows come back `replayed`: the floor
    # must hold on it too, or #124 would work once and silently fail on every re-run.
    project = _project(tmp_path)
    for attempt in ("cold", "warm"):
        run = _cli(project, "converge", "orders.py::order_total", "--two-sign")
        out = run.stdout + run.stderr
        assert run.returncode == 1, f"{attempt}:\n{out}"
        assert "⚠ FAILING NOW" in out and all(t in out for t in FAILING), f"{attempt}:\n{out}"
        assert "AUTHOR INPUT" not in out, f"{attempt}:\n{out}"
        assert not list(project.rglob("*_synth.py")), "converge wrote a characterization over a failing floor"
