"""W7 — the load-failure exit-code contract, CHOSEN rather than emergent.

`CORRECTNESS_REPAIRS_2026-09-08.md` left this open in as many words:

    "Open contract question: which exit code a load-failure refusal carries. The documented table
    has `1 = a real gap or typed REFUSAL` and `3 = INVALID MEASUREMENT, re-run`. 'Nothing was
    measured' argues 3. CI branches on this, so it should be chosen, not emergent."

Measured 2026-09-09 by driving every verb against a module whose import fails, the implementation
had already converged on a coherent answer — and nothing pinned it, so it could drift without a
test going red. That is the whole defect: not a wrong code, an UNGUARDED one, on a contract the
issue itself says CI branches on.

`test_target_load_failure_intent.py` pins the validity layer (R1) exhaustively and stops there.
These pin the surface CI actually reads.

THE CONTRACT, and why each code is the right one rather than merely the current one:

    converge        3   nothing was measured, so the measurement cannot be trusted — the README's
                        own gloss for 3. Not 1: a "measured gap" implies a measurement happened.
    audit --check   1   a typed REFUSAL, which is what 1 covers. S6 settled that a spec gap
                        outranks it, so 2 is unreachable while a line gap co-exists — which on an
                        unloadable module is always.
    audit (bare)    0   read-only BY DESIGN and gates only when asked (S6). It still NAMES the
                        failure; exiting 0 is not the same as reporting clean.
    diagnose        0   the same read-only contract as bare audit, and for the same reason. It too
                        must NAME the failure — which it did not until 2026-09-09.

The pairing is the point: a verb may exit 0 only if it says what is wrong. `audit` and `diagnose`
buy their 0 with the STOP block, not with silence.
"""

from __future__ import annotations

import pytest

from Detective.cli import main

_UNIMPORTABLE = "import definitely_not_a_real_package_xyz as dep\n\n\ndef classify(n):\n    if n > 10:\n        return dep.big(n)\n    return 'small'\n"


@pytest.fixture(scope="module")
def broken(tmp_path_factory):
    root = tmp_path_factory.mktemp("loadfail")
    (root / "mod.py").write_text(_UNIMPORTABLE)
    (root / "tests").mkdir()
    (root / "tests" / "test_p.py").write_text("def test_placeholder():\n    assert True\n")
    return root


def _run(argv) -> int:
    try:
        return int(main(argv) or 0)
    except SystemExit as exc:  # the typed-refusal paths leave via SystemExit
        return int(exc.code or 0)


# ---------------------------------------------------------------- the four codes


def test_converge_reports_INVALID_MEASUREMENT_not_a_gap(broken, capsys) -> None:
    """3, not 1. A "measured gap" claims a measurement happened; nothing here ran at all."""
    code = _run(["converge", "mod.py::classify", "--project-root", str(broken)])
    capsys.readouterr()
    assert code == 3


def test_audit_check_reports_a_typed_refusal(broken, capsys) -> None:
    """1 — "a real gap OR typed REFUSAL". S6 corrected the help to state that a spec gap outranks
    the strict code, so 2 is unreachable whenever a line gap co-exists, which on an unloadable
    module is always."""
    code = _run(["audit", "mod.py::classify", "--check", "--project-root", str(broken)])
    capsys.readouterr()
    assert code == 1


def test_bare_audit_stays_read_only(broken, capsys) -> None:
    """0, and S6 filed the opposite reading as a MIS-filing: bare audit is read-only by design and
    gates only when asked."""
    code = _run(["audit", "mod.py::classify", "--project-root", str(broken)])
    out = capsys.readouterr().out
    assert code == 0
    assert "could not be loaded" in out, "a 0 is only honest if the verb SAYS what is wrong"


def test_diagnose_matches_bare_audit(broken, capsys) -> None:
    """The same read-only contract, and — since 2026-09-09 — the same obligation to name the cause.
    Before that it exited 0 AND attributed the run to absent tests, which is a 0 that reads clean."""
    code = _run(["diagnose", "mod.py::classify", "--project-root", str(broken)])
    out = capsys.readouterr().out
    assert code == 0
    assert "could not be loaded" in out


# ---------------------------------------------------------------- the rule behind the codes


def test_every_verb_that_exits_zero_still_names_the_failure(broken, capsys) -> None:
    """The contract in one assertion. A verb is allowed to exit 0 here ONLY because it reports the
    cause; silence plus 0 is the state that sent an operator to author inputs for a module that
    could not import (Finding E / R3's spiral)."""
    for verb in ("audit", "diagnose"):
        code = _run([verb, "mod.py::classify", "--project-root", str(broken)])
        out = capsys.readouterr().out
        assert code == 0, verb
        assert "could not be loaded" in out, f"{verb} exits 0 without naming the cause"


def test_no_verb_invites_input_authoring_over_an_unimportable_module(broken, capsys) -> None:
    """Finding E's spiral, closed on every surface at once. `--input` cannot run without the module,
    so offering it is an instruction that provably cannot change the state it describes."""
    for verb in ("converge", "audit", "diagnose"):
        _run([verb, "mod.py::classify", "--project-root", str(broken)])
        out = capsys.readouterr().out
        assert "AUTHOR INPUTS" not in out, verb
