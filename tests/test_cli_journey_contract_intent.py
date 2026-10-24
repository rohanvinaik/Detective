"""Intent regressions for #58: one runtime/target identity and executable guidance only.

The defect was a human journey, not a mutant count: a foreign launcher was diagnosed as a
missing project package, a src-layout target acquired two module names, and an angle-bracket
template was printed as a command even though Detective's own parser rejected it.
"""

from __future__ import annotations

import shlex
from dataclasses import replace
from types import SimpleNamespace

from Detective.audit import SuiteAudit
from Detective.cli import (
    _audit_action,
    _audit_decision,
    _build_parser,
    _converge_action,
    _converge_decision,
    _derive_input_plan,
    _derived_input,
    _final_banner,
    _format_converge,
    _reachable_paths,
    _regime_action,
    execution_disposition,
    main,
)
from Detective.converge import ConvergeResult
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


def test_src_layout_reachability_consumes_the_module_identity_regime_measured(tmp_path):
    source = tmp_path / "src" / "acme"
    tests = tmp_path / "tests"
    source.mkdir(parents=True)
    tests.mkdir()
    (source / "__init__.py").write_text("")
    target = source / "pricing.py"
    target.write_text("def quote(value):\n    return value + 1\n")
    relevant = tests / "test_pricing.py"
    relevant.write_text("from acme.pricing import quote\n\ndef test_quote():\n    assert quote(1) == 2\n")
    noise = tests / "test_noise.py"
    noise.write_text("def test_noise():\n    assert True\n")
    (tmp_path / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\npythonpath = ['src']\ntestpaths = ['tests']\n"
    )

    regime = resolve_regime(str(tmp_path), str(target))
    scope = _reachable_paths(
        str(tmp_path),
        [str(target)],
        target_module=regime.module,
        import_roots=regime.suite_path,
    )

    assert regime.module == "acme.pricing"
    assert scope.disposition == "scoped"  # it narrowed — not declined, not roots
    assert scope.paths is not None
    assert str(relevant) in scope.paths
    assert str(noise) not in scope.paths


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

    assert out[0].startswith("STOP:")
    assert "without naming a reason" in out[0]
    assert "--trace-budget" not in " ".join(out)


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


def test_two_sign_audit_prescribes_the_same_policy_in_text_and_argv():
    audit = SuiteAudit(
        function="m.py::scale",
        test_count=1,
        kill_pct=8 / 9,
        mutant_complete=False,
        line_complete=True,
        redundant_tests=(),
        failing_tests=(),
        killable_gaps=("OUTPUT_missing",),
        missing_lines=(),
        minimal_test_count=1,
        total_mutants=9,
        value_killed=8,
    )
    decision = _audit_decision(audit, two_sign=True)
    out = _audit_action(audit, decision=decision)
    argv = shlex.split(out[0].removeprefix("DO THIS:  "))[1:]
    assert tuple(argv) == decision.argv
    assert _build_parser().parse_args(argv).two_sign is True


def test_two_sign_converge_preserves_policy_through_rerun_and_style_handoff():
    result = ConvergeResult(
        function="m.py::scale",
        converged=True,
        at_ceiling=True,
        initial_survivors=0,
        final_survivors=0,
        iterations=(),
        written_path=None,
        functionally_complete=True,
    )
    rep = SurvivorReport(verdicts=(), unclassified=())
    for case in (result, replace(result, stale_target=True)):
        decision = _converge_decision(case, rep, two_sign=True, render_tests=False)
        out = "\n".join(_converge_action(case, rep, decision=decision))
        commands = (decision.argv,) if case.stale_target else decision.optional
        for argv in commands:
            parsed = _build_parser().parse_args(argv)
            if parsed.command in ("converge", "decompose"):
                assert parsed.two_sign is True
                assert "--two-sign" in out


def test_final_names_the_measured_policy():
    result = ConvergeResult(
        function="m.py::scale",
        converged=True,
        at_ceiling=True,
        initial_survivors=0,
        final_survivors=0,
        iterations=(),
        written_path=None,
        functionally_complete=True,
        policy_id="8.example-two-sign",
    )
    assert "policy 8.example-two-sign" in _final_banner(result)


def test_archived_flag_command_retains_the_measured_two_sign_policy():
    verdict = MutantVerdict(
        mutant_id="OUTPUT_empty",
        category="OUTPUT",
        diff_summary="return '' -> return type('')()",
        killable=False,
        witness=None,
        searched=1,
    )
    result = ConvergeResult(
        function="empty.py::empty",
        converged=True,
        at_ceiling=True,
        initial_survivors=1,
        final_survivors=1,
        iterations=(),
        written_path=None,
        survivor_report=SurvivorReport(verdicts=(verdict,), unclassified=()),
    )
    report = _format_converge(result, two_sign=True)
    commands = [part for part in report.split("`") if part.startswith("detective flag ")]
    assert len(commands) == 1
    parsed = _build_parser().parse_args(shlex.split(commands[0])[1:])
    assert parsed.two_sign is True
    assert parsed.mutant_id == "OUTPUT_empty"


def test_flag_can_address_output_survivors_in_the_two_sign_universe(monkeypatch, tmp_path):
    from Detective import cli, engine, equivalents

    args = _build_parser().parse_args(
        [
            "flag",
            "m.py::scale",
            "OUTPUT_missing",
            "--two-sign",
            "--note",
            "authored proof",
            "--project-root",
            str(tmp_path),
            "--json",
        ]
    )
    seen = {}

    def measured(*a, **kwargs):
        seen.update(kwargs)
        return SimpleNamespace(
            function_key="m.py::scale",
            value_survivor_records=[
                {"mutant_id": "OUTPUT_missing", "diff_summary": "return None -> type(None)()"}
            ],
        )

    monkeypatch.setattr(engine, "profile", measured)
    monkeypatch.setattr(equivalents, "add_flag", lambda *a, **kw: None)
    assert cli._run_flag(args, "m.py", "scale") == 0
    assert seen["two_sign"] is True
