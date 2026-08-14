"""Intent regressions for #58: one runtime/target identity and executable guidance only.

The defect was a human journey, not a mutant count: a foreign launcher was diagnosed as a
missing project package, a src-layout target acquired two module names, and an angle-bracket
template was printed as a command even though Detective's own parser rejected it.
"""

from __future__ import annotations

import shlex
from types import SimpleNamespace

from Detective.cli import (
    _build_parser,
    _converge_action,
    _derive_input_plan,
    _derived_input,
    _regime_action,
    execution_disposition,
    main,
)
from Detective.equivalence import MutantVerdict, SurvivorReport, Witness
from Detective.regime import resolve_regime


class DomainObject:
    def __repr__(self) -> str:
        return "DomainObject(state=<State.READY: 'ready'>)"


def _object_verdict(index: int, value: DomainObject) -> MutantVerdict:
    return MutantVerdict(
        mutant_id=f"VALUE_{index:08x}",
        category="VALUE",
        diff_summary="- original + mutant",
        killable=True,
        witness=Witness(args=(value,), original="'real'", mutant="'mutant'"),
        searched=1,
    )


def _literal_verdict() -> MutantVerdict:
    return MutantVerdict(
        mutant_id="VALUE_00000001",
        category="VALUE",
        diff_summary="- original + mutant",
        killable=True,
        witness=Witness(args=(1,), original="'real'", mutant="'mutant'"),
        searched=1,
    )


def test_execution_disposition_refuses_a_foreign_console_interpreter(tmp_path):
    active = tmp_path / "project-venv"
    other = tmp_path / "launcher-venv"

    assert execution_disposition(None, str(other)) == "ready"
    assert execution_disposition(str(active), str(active)) == "ready"
    assert execution_disposition(str(active), str(other)) == "wrong_interpreter"


def test_live_command_refuses_before_pytest_can_misdiagnose_the_environment(tmp_path, monkeypatch, capsys):
    active = tmp_path / "project-venv"
    active.mkdir()
    monkeypatch.setenv("VIRTUAL_ENV", str(active))

    code = main(["diagnose", "missing.py::target", "--project-root", str(tmp_path)])

    captured = capsys.readouterr()
    assert code == 2
    assert "REFUSED" in captured.err
    assert "different interpreter" in captured.err
    assert str(active / "bin" / "detective") in captured.err
    assert "pytest collection" not in captured.err


def test_collection_universe_is_the_declared_testpaths_verbatim(tmp_path):
    """C1: Layer 1 is the declared testpaths, VERBATIM — no target, no import-graph filter, no
    synthesized file list. The per-item, target-aware narrowing is Layer 2/3's job."""
    from Detective.regime import collection_universe

    (tmp_path / "src" / "acme").mkdir(parents=True)
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "acme" / "__init__.py").write_text("")
    target = tmp_path / "src" / "acme" / "pricing.py"
    target.write_text("def quote(value):\n    return value + 1\n")
    (tmp_path / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\npythonpath = ['src']\ntestpaths = ['tests']\n"
    )

    regime = resolve_regime(str(tmp_path), str(target))
    assert regime.module == "acme.pricing"
    assert collection_universe(regime) == [str(tmp_path / "tests")]


def test_collection_universe_is_none_when_no_testpaths(tmp_path):
    from Detective.regime import collection_universe

    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    regime = resolve_regime(str(tmp_path), None)
    assert collection_universe(regime) is None


def test_one_test_built_object_is_not_reported_as_thirty_one_objects():
    value = DomainObject()
    rep = SurvivorReport(
        verdicts=tuple(_object_verdict(i, value) for i in range(31)),
        unclassified=(),
    )

    plan = _derive_input_plan(SimpleNamespace(), rep)

    assert plan.kind == "test"
    assert plan.item_total == 1
    assert plan.obligation_total == 31
    assert len(plan.items) == 1


def test_line_gap_never_prints_an_unparseable_do_this_command():
    proof = SimpleNamespace(
        signature="quote(result: DomainObject)",
        param_names=("result",),
        missing_lines=(34,),
        missing_line_guards=((34, "result.reference_levels == ()"),),
    )
    rep = SurvivorReport(verdicts=(), unclassified=())

    out = _derived_input(
        None,
        proof,
        rep,
        "src/acme/pricing.py::quote",
        verb="detective converge 'src/acme/pricing.py::quote'",
    )

    assert out[0].startswith("AUTHOR INPUTS:")
    assert not any(line.startswith("DO THIS:") for line in out)
    assert not any("<result>" in line for line in out if line.startswith("THEN RUN:"))
    rerun = next(line.removeprefix("THEN RUN:  ") for line in out if line.startswith("THEN RUN:"))
    argv = shlex.split(rerun)
    assert argv[0] == "detective"
    parsed = _build_parser().parse_args(argv[1:])
    assert parsed.command == "converge"


def test_missing_survivor_report_cannot_turn_an_incomplete_result_into_done():
    result = SimpleNamespace(
        function="p.py::quote",
        functionally_complete=False,
        final_survivors=2,
        missing_lines=(),
        signature="quote(value)",
        param_names=("value",),
        environment_gated=(),
    )

    out = _converge_action(result, rep=None)

    assert out[0].startswith("AUTHOR INPUTS:")
    assert not any(line.startswith("DONE:") for line in out)


def test_an_ungateable_measurement_outranks_every_input_suggestion():
    result = SimpleNamespace(
        function="p.py::quote",
        functionally_complete=False,
        final_survivors=1,
        missing_lines=(),
        admits_certificate=False,
        collection_conflicts=(),
        budget_exhausted=False,
    )
    rep = SurvivorReport(verdicts=(_literal_verdict(),), unclassified=())

    out = _converge_action(result, rep, attempted_inputs=("(1,)",))

    assert out[0].startswith("DO THIS:  detective converge 'p.py::quote' --input \"(1,)\"")
    assert "--trace-budget 0 --trace-session-budget 0" in out[0]
    assert "invalid measurement" in " ".join(out)


def test_an_input_that_already_failed_to_close_is_never_offered_again():
    result = SimpleNamespace(
        function="p.py::quote",
        functionally_complete=False,
        final_survivors=1,
        missing_lines=(),
        signature="quote(value)",
        param_names=("value",),
        environment_gated=(),
        admits_certificate=True,
    )
    rep = SurvivorReport(verdicts=(_literal_verdict(),), unclassified=())

    out = _converge_action(result, rep, attempted_inputs=("(1,)",))

    assert out[0].startswith("WRITE TEST:")
    assert "proven loop" in " ".join(out)
    assert not any('--input "(1,)"' in line for line in out)


def test_migration_reports_the_new_state_instead_of_saying_nothing_happened():
    regime = SimpleNamespace(conflicts=())
    out = _regime_action(regime, plan=None, applied=("registered marker",))

    assert "migration applied" in " ".join(out)
    assert "nothing to migrate" not in " ".join(out)
