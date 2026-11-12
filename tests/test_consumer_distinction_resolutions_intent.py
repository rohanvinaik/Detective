"""#93: the six consumer sites that collapsed a pinned decision's codes each carry a NAMED outcome now.

The defect (Detective#93, founder ruling 2026-09-26 item 17: "implement a typed, named solution for every
genuinely deterministic, resolvable item ... and communicate it correctly to the user"): six consumers of a
pinned decision folded distinct codes into one branch, one bool or one count, so a state the decision keeps
apart reached the reader as one:

* `regression_recovery`      the converge ladder asked it once and re-read `regressed` afterwards;
* `array_source_disposition` called with constants, the gate that ran (finiteness, float width) unpinned;
* `learn_disposition`        only `learn` printed, so `--learn` on a clean rewrite said nothing;
* `rewrite_classification_status` three causes became one bool and one sentence;
* `signpost_disposition`     `unknown_herb` fell through with `emit` to "no signpost";
* `value_portability`        `numeric_model_risk` and `inexpressible` merged into one `skipped` count.

These tests are written from intent: each states what the reader must be told apart.
"""

from __future__ import annotations

import ast
import json
import pathlib
import shutil
import types

import pytest

from Detective import cli
from Detective.array_inputs import array_source, array_source_disposition, array_source_status
from Detective.converge import RESTORE_PRIOR, RETRY_UNMINIMIZED, SHIP, regression_recovery
from Detective.emission import CrossLangEmission, obligation_portability, run_c_gate, value_portability
from Detective.rewrite import (
    _CLASSIFICATION_SAID,
    RewriteVerification,
    abstain_reason,
    rewrite_classification_status,
)

# ------------------------------------------------------------- regression_recovery


def test_converge_asks_the_recovery_decision_again_after_the_retry() -> None:
    """The retried branch was unreachable from production: the decision was asked once with
    retried=False, then `regressed` was re-read. It must be asked a second time with retried=True and the
    restore/ship dispatch must read ITS code."""
    tree = ast.parse(pathlib.Path(cli.__file__).with_name("converge.py").read_text(encoding="utf-8"))
    calls = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "regression_recovery"
    ]
    retried = sorted(ast.literal_eval(c.args[2]) for c in calls)
    assert retried == [False, True]
    src = pathlib.Path(cli.__file__).with_name("converge.py").read_text(encoding="utf-8")
    assert "if recovery == RESTORE_PRIOR:" in src and "if recovery == SHIP:" in src


def test_the_three_recovery_codes_still_mean_what_the_ladder_dispatches_on() -> None:
    assert regression_recovery(False, True, False) == SHIP
    assert regression_recovery(True, True, False) == RETRY_UNMINIMIZED
    assert regression_recovery(True, True, True) == RESTORE_PRIOR
    # nowhere to retry (no pre-trim superset, or no write dir): restore at once, never RETRY
    assert regression_recovery(True, False, False) == RESTORE_PRIOR


# ------------------------------------------------------------- array_source


def test_a_refused_array_says_which_refusal() -> None:
    numpy = pytest.importorskip("numpy")
    assert array_source_status(numpy.array([1, 2])) == "render"
    assert array_source_status(numpy.array([float("inf")])) == "nonfinite"
    assert array_source_status(numpy.array([float("nan")])) == "nonfinite"
    assert array_source_status(numpy.array([object()])) == "unsupported_dtype"
    assert array_source_status(numpy.zeros((17,))) == "outside_bound"
    assert array_source_status(numpy.zeros((1, 1, 1))) == "outside_bound"
    assert array_source_status([1, 2]) == "not_numpy"
    assert array_source_status(numpy.ma.masked_array([1])) == "not_numpy"  # an ndarray subclass is not exact


def test_the_float_width_gate_is_a_decision_code_not_an_unpinned_inline_check() -> None:
    numpy = pytest.importorskip("numpy")
    wide = numpy.zeros((1,), dtype=numpy.longdouble)
    if wide.dtype.itemsize <= 8:
        pytest.skip("this platform's longdouble is float64")
    assert array_source_status(wide) == "unsupported_width"
    assert array_source(wide) is None
    assert array_source_disposition(1, 1, "f", True, True, 16) == "unsupported_width"
    assert array_source_disposition(1, 1, "f", True, True, 8) == "render"
    assert array_source_disposition(1, 1, "i", True, True, 16) == "render"  # width gates floats only


def test_finiteness_is_never_read_for_an_object_dtype() -> None:
    """`numpy.isfinite` raises on object dtype: the structural question refuses BEFORE the measured one."""
    numpy = pytest.importorskip("numpy")
    assert array_source_status(numpy.array([None, "x"], dtype=object)) == "unsupported_dtype"


# ------------------------------------------------------------- learn_disposition


def _verify_args(**over):
    base = {"receipt_path": "r.json", "project_root": ".", "json": False, "learn": True, "budget": False}
    base.update(over)
    return types.SimpleNamespace(**base)


def _stub_verify(monkeypatch, verdict: str) -> None:
    import Detective.rewrite as rw

    monkeypatch.setattr(rw, "receipt_load_refusal", lambda _text, _schema: "")
    monkeypatch.setattr(rw.RewriteReceipt, "from_json", classmethod(lambda cls, _t: object()))
    monkeypatch.setattr(
        rw,
        "verify_rewrite",
        lambda *a, **k: RewriteVerification(verdict, "m.py::f", "passed", (), (), (), note=""),
    )


def test_learn_on_a_clean_rewrite_says_why_nothing_was_learned(tmp_path, monkeypatch, capsys) -> None:
    (tmp_path / "r.json").write_text("{}", encoding="utf-8")
    _stub_verify(monkeypatch, "PRESERVED")
    cli._run_verify_rewrite(_verify_args(receipt_path=str(tmp_path / "r.json")), "m.py", "f")
    err = capsys.readouterr().err
    assert "--learn: nothing was learned" in err and "PRESERVED" in err and "CHANGED" in err


def test_learn_off_prints_no_learn_line_and_json_carries_the_code(tmp_path, monkeypatch, capsys) -> None:
    (tmp_path / "r.json").write_text("{}", encoding="utf-8")
    _stub_verify(monkeypatch, "PRESERVED")
    cli._run_verify_rewrite(_verify_args(receipt_path=str(tmp_path / "r.json"), learn=False), "m.py", "f")
    assert "--learn" not in capsys.readouterr().err  # the flag being off needs no line
    cli._run_verify_rewrite(_verify_args(receipt_path=str(tmp_path / "r.json"), json=True), "m.py", "f")
    out = capsys.readouterr()
    assert json.loads(out.out)["learn_disposition"] == "skip_unchanged"
    assert "nothing was learned" not in out.err  # --json keeps stderr to what it always carried
    cli._run_verify_rewrite(
        _verify_args(receipt_path=str(tmp_path / "r.json"), json=True, learn=False), "m.py", "f"
    )
    assert "learn_disposition" not in json.loads(capsys.readouterr().out)  # absent when not asked


# ------------------------------------------------------------- rewrite_classification_status


def test_every_reason_classification_cannot_run_has_its_own_sentence_and_reason() -> None:
    causes = {
        rewrite_classification_status(False, False, True),
        rewrite_classification_status(True, True, True),
        rewrite_classification_status(True, False, False),
    }
    assert causes == {"unavailable", "load_failed", "invalid_measurement"}
    assert set(_CLASSIFICATION_SAID) == causes
    sentences = list(_CLASSIFICATION_SAID.values())
    assert len(set(sentences)) == 3
    reasons = {abstain_reason("ABSTAIN", "valid", "clear", c) for c in causes}
    assert reasons == {f"classification_{c}" for c in causes}


def test_the_classification_cause_never_outranks_the_receipt_nor_decorates_a_non_abstain() -> None:
    assert abstain_reason("ABSTAIN", "unfrozen", "clear", "load_failed") == "receipt_unfrozen"
    assert abstain_reason("CHANGED", "valid", "clear", "load_failed") == ""
    assert abstain_reason("ABSTAIN", "valid", "withheld", "load_failed") == "classification_load_failed"
    assert abstain_reason("ABSTAIN", "valid", "withheld") == "withheld"  # observed: order decides, as before
    assert abstain_reason("ABSTAIN", "valid", "clear") == ""


@pytest.mark.parametrize("cause", ["unavailable", "load_failed", "invalid_measurement"])
def test_the_page_names_the_classification_cause_and_its_remedy(cause) -> None:
    res = RewriteVerification(
        "ABSTAIN", "m.py::f", "passed", (), (), (), note="", reason=f"classification_{cause}"
    )
    page = cli._format_rewrite(res)
    assert "UNPROVEN" in page
    assert "review by hand" not in page  # the generic line's remedy does not apply
    if cause == "load_failed":
        assert "Re-running\n       will not change it" in page
    else:
        assert "Re-run" in page


def test_the_three_classification_pages_differ() -> None:
    pages = {
        cli._format_rewrite(
            RewriteVerification("ABSTAIN", "m.py::f", "passed", (), (), (), reason=f"classification_{c}")
        )
        for c in ("unavailable", "load_failed", "invalid_measurement")
    }
    assert len(pages) == 3


# ------------------------------------------------------------- signpost_disposition


def _fault_present(monkeypatch, tmp_path):
    import Detective.doctor as doctor

    target = tmp_path / "t.py"
    target.write_text("import not_a_real_module_xyz\n", encoding="utf-8")
    monkeypatch.setattr(doctor, "missing_here", lambda _imports: ("not_a_real_module_xyz",))
    return str(target)


def test_a_verb_with_no_declared_herb_under_a_live_fault_is_named_not_silent(monkeypatch, tmp_path) -> None:
    import Detective.doctor as doctor

    target = _fault_present(monkeypatch, tmp_path)
    monkeypatch.delitem(doctor.COMMAND_HERB, "survey")
    rows = cli._signpost_rows("survey", str(tmp_path), target)
    text = "\n".join(rows)
    assert "SETUP FAULT" in text
    assert "no declared herb" in text and "'survey'" in text
    assert "a GREEN finding outranks" not in text  # it does not claim a rank nobody established


def test_a_declared_yellow_verb_still_reads_as_preempted_by_the_green_finding(monkeypatch, tmp_path) -> None:
    target = _fault_present(monkeypatch, tmp_path)
    text = "\n".join(cli._signpost_rows("survey", str(tmp_path), target))
    assert "a GREEN finding outranks this yellow verdict" in text
    assert "no declared herb" not in text


def test_no_fault_no_signpost_for_a_verb_without_a_herb(monkeypatch, tmp_path) -> None:
    import Detective.doctor as doctor

    target = tmp_path / "t.py"
    target.write_text("x = 1\n", encoding="utf-8")
    monkeypatch.delitem(doctor.COMMAND_HERB, "survey")
    assert cli._signpost_rows("survey", str(tmp_path), str(target)) == []


# ------------------------------------------------------------- value_portability


def test_obligation_portability_names_each_standing() -> None:
    p, r, i = "portable", "numeric_model_risk", "inexpressible"
    assert obligation_portability([p, p], p, True) == "portable"
    assert obligation_portability([r], p, True) == "numeric_model_risk"
    assert obligation_portability([p], r, False) == "numeric_model_risk"
    assert obligation_portability([i], p, True) == "inexpressible"
    assert obligation_portability([r, i], p, True) == "inexpressible"  # the strongest standing wins
    assert obligation_portability([p], p, False) == "return_not_integer"  # float/str/bool result
    assert obligation_portability([], p, True) == "portable"  # a nullary function rides


def test_the_gate_counts_the_standings_apart_even_with_no_toolchain(tmp_path) -> None:
    emission = CrossLangEmission("c", "long long f(long long x) { return x; }", "f", "", "w")
    obligations = [
        ((2**63,), 0),  # numeric_model_risk (arg beyond i64)
        ((float("inf"),), 0),  # numeric_model_risk (non-finite arg)
        (([1],), 1),  # inexpressible (container arg)
        ((1,), None),  # inexpressible (None result)
        ((1,), 2.5),  # return_not_integer
        ((1,), True),  # return_not_integer (bool is not the %lld channel)
    ]
    result = run_c_gate(emission, obligations, str(tmp_path))
    assert result["skipped"] == 6
    assert result["skipped_by"] == {"numeric_model_risk": 2, "inexpressible": 2, "return_not_integer": 2}
    assert result["portable"] == 0


@pytest.mark.skipif(shutil.which("cc") is None, reason="no C toolchain")
def test_the_breakdown_rides_every_result_that_rides_and_sums_to_skipped(tmp_path) -> None:
    emission = CrossLangEmission("c", "long long f(long long x) { return x + 1; }", "f", "", "w")
    result = run_c_gate(emission, [((1,), 2), ((2**63,), 0), (([1],), [1])], str(tmp_path))
    assert result["disposition"] == "PRESERVED_MODULO_UNPORTABLE"
    assert result["skipped_by"] == {"numeric_model_risk": 1, "inexpressible": 1, "return_not_integer": 0}
    assert sum(result["skipped_by"].values()) == result["skipped"]


def test_value_portability_codes_are_unchanged() -> None:
    assert value_portability(1) == "portable"
    assert value_portability(2**63) == "numeric_model_risk"
    assert value_portability([1]) == "inexpressible"
