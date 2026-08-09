"""Intent tests for the adversarial adequacy benchmark (issue #15).

The benchmark falsifies #16's ``witnessed`` statuses: it injects a fault a buggy transformer could
emit into a PROVEN extraction and asks whether the mutation-complete proof suite REJECTS it. These
pin the fault families (AST surgery converge cannot ``--input``-synthesise) and the classification
meaning; the pure decisions ``adequacy_bucket`` / ``bucket_is_finding`` carry their own synth pins.
The heavy end-to-end run (a real converge + suite reruns) is exercised separately as the benchmark
executing, not from here.
"""

from __future__ import annotations

import ast

from Detective.adequacy import (
    FAULT_FAMILIES,
    AdequacyReport,
    FaultOutcome,
    adequacy_bucket,
    bucket_is_finding,
    drop_helper_param,
    drop_ordered_effect,
    swap_call_unpacking,
    swap_helper_returns,
)
from Detective.certify import run_pytest_verification

# A rendered two-output extraction with an ordered effect — every fault family applies.
_SRC = (
    "def _seg(a, b):\n"
    "    log(a)\n"
    "    lo = a - b\n"
    "    hi = a + b\n"
    "    return lo, hi\n"
    "\n\n"
    "def f(a, b):\n"
    "    lo, hi = _seg(a, b)\n"
    "    return hi - lo\n"
)


def _parses(src: str | None) -> ast.Module:
    assert src is not None
    return ast.parse(src)  # a fault must still yield loadable source, or it is untestable


# ── the fault families change what they claim to, and stay parseable ────────


def test_drop_helper_param_removes_the_last_parameter():
    tree = _parses(drop_helper_param(_SRC, "_seg"))
    seg = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_seg")
    assert [a.arg for a in seg.args.args] == ["a"]  # b was dropped; the call still passes it


def test_swap_helper_returns_reverses_the_returned_tuple():
    tree = _parses(swap_helper_returns(_SRC, "_seg"))
    seg = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_seg")
    ret = next(n for n in ast.walk(seg) if isinstance(n, ast.Return))
    assert isinstance(ret.value, ast.Tuple)
    assert [e.id for e in ret.value.elts] == ["hi", "lo"]  # was lo, hi


def test_swap_call_unpacking_reverses_the_assignment_targets():
    tree = _parses(swap_call_unpacking(_SRC, "_seg"))
    call_assign = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Assign)
        and isinstance(n.value, ast.Call)
        and isinstance(n.value.func, ast.Name)
        and n.value.func.id == "_seg"
    )
    assert isinstance(call_assign.targets[0], ast.Tuple)
    assert [e.id for e in call_assign.targets[0].elts] == ["hi", "lo"]  # was lo, hi


def test_drop_ordered_effect_removes_a_bare_call_statement():
    tree = _parses(drop_ordered_effect(_SRC, "_seg"))
    seg = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_seg")
    assert not any(isinstance(s, ast.Expr) and isinstance(s.value, ast.Call) for s in seg.body)


# ── the families abstain (None) when they do not apply, never mis-fire ──────


def test_swap_families_not_applicable_to_a_single_output_helper():
    single = "def _g(a):\n    return a + 1\n\n\ndef f(a):\n    r = _g(a)\n    return r\n"
    assert swap_helper_returns(single, "_g") is None  # only one return value
    assert swap_call_unpacking(single, "_g") is None  # not a tuple unpack


def test_drop_effect_not_applicable_without_a_bare_call():
    pure = (
        "def _g(a, b):\n    lo = a - b\n    hi = a + b\n    return lo, hi\n\n\n"
        "def f(a, b):\n    lo, hi = _g(a, b)\n    return lo + hi\n"
    )
    assert drop_ordered_effect(pure, "_g") is None


def test_a_missing_helper_name_is_not_applicable():
    assert drop_helper_param(_SRC, "_does_not_exist") is None
    assert drop_ordered_effect(_SRC, "_does_not_exist") is None


# ── the classification meaning, from intent ─────────────────────────────────


def test_bucket_only_undetected_is_a_finding():
    assert adequacy_bucket(produced=False, import_broke=False, suite_passed=False) == "not_applicable"
    assert adequacy_bucket(produced=True, import_broke=True, suite_passed=False) == "structurally_impossible"
    assert adequacy_bucket(produced=True, import_broke=False, suite_passed=False) == "detected"
    assert adequacy_bucket(produced=True, import_broke=False, suite_passed=True) == "undetected"
    assert bucket_is_finding("undetected")
    assert not any(bucket_is_finding(b) for b in ("not_applicable", "structurally_impossible", "detected"))


# ── the report distinguishes an abstention from a proof of adequacy ─────────


def test_abstention_is_not_adequacy():
    # a run that could not attack anything must NOT read as "adequate" — it made no claim
    r = AdequacyReport("m.py::f", "pol", "1.abc", (), abstain_reason="no proven extraction to attack")
    assert not r.adequate
    assert not r.findings


def test_a_clean_run_with_all_detected_is_adequate():
    r = AdequacyReport(
        "m.py::f",
        "pol",
        "1.abc",
        (
            FaultOutcome("drop_helper_param", "_seg", "detected"),
            FaultOutcome("swap_helper_returns", "_seg", "detected"),
            FaultOutcome("drop_ordered_effect", "_seg", "not_applicable"),
        ),
    )
    assert r.adequate
    assert r.findings == ()


def test_an_undetected_fault_is_surfaced_and_blocks_adequacy():
    r = AdequacyReport(
        "m.py::f",
        "pol",
        "1.abc",
        (
            FaultOutcome("swap_helper_returns", "_seg", "detected"),
            FaultOutcome("swap_call_unpacking", "_seg", "undetected"),
        ),
    )
    assert not r.adequate
    assert [o.family for o in r.findings] == ["swap_call_unpacking"]


# ── end-to-end: a real pinning suite REJECTS every behavior-changing fault ───

# A valid decomposition — f delegates a two-output segment with an ordered effect to _seg —
# and a suite tight enough to distinguish each fault: asymmetric outputs (a swap changes the
# result), both params used (a drop breaks the call), the effect counted (a drop changes len).
_E2E_MODULE = (
    "_EVENTS = []\n\n\n"
    "def _seg(a, b):\n"
    "    _EVENTS.append(a)\n"
    "    lo = a - b\n"
    "    hi = a + b\n"
    "    return lo, hi\n\n\n"
    "def f(a, b):\n"
    "    _EVENTS.clear()\n"
    "    lo, hi = _seg(a, b)\n"
    "    return hi * 100 + lo * 10 + len(_EVENTS)\n"
)
_E2E_SUITE = (
    "from m import f\n\n\n"
    "def test_values():\n"
    "    assert f(5, 2) == 100 * 7 + 10 * 3 + 1\n"
    "    assert f(9, 1) == 100 * 10 + 10 * 8 + 1\n"
)


def test_every_applicable_fault_is_detected_by_a_real_suite(tmp_path):
    """The benchmark's core claim, run through the REAL pytest runner: on this fixture every fault
    a family produces changes behaviour, and the mutation-pinning suite rejects each one — bucket
    ``detected``, never ``undetected``. This is what makes the ``witnessed`` statuses honest here."""
    (tmp_path / "m.py").write_text(_E2E_MODULE)
    (tmp_path / "test_m.py").write_text(_E2E_SUITE)
    root = str(tmp_path)
    suite = "test_m.py"

    # baseline: the clean decomposition is green
    assert run_pytest_verification(root, suite).status == "passed"

    for family, inject in FAULT_FAMILIES:
        faulted = inject(_E2E_MODULE, "_seg")
        assert faulted is not None, f"{family} should apply to this fixture"
        (tmp_path / "m.py").write_text(faulted)
        v = run_pytest_verification(root, suite)
        bucket = adequacy_bucket(
            produced=True, import_broke=v.status == "collection_failed", suite_passed=v.status == "passed"
        )
        assert bucket == "detected", f"{family}: suite failed to reject the fault ({v.status})"
        (tmp_path / "m.py").write_text(_E2E_MODULE)  # restore for the next family
