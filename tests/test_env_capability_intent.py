"""``--env`` makes an environment-reading function pinnable, scoped to the declared set (#48 part B).

Detective refuses a golden whose return depends on ``os.environ`` — it is CI-dependent (green here,
red on another host). ``--env NAME=value`` (or ``NAME-`` for absent) declares that dependency: the
read is applied at capture so the branch is reachable, COVERED so the capture is admissible, and
rendered into the emitted test (stdlib only) so it re-applies and restores — the pin holds with no
fixture and no Detective at runtime. A variable the function reads but the user does NOT declare stays
refused: an undeclared dependency must never ride a certificate. These pin that contract from intent,
mirroring the shipped ``--clock`` capability.
"""

from __future__ import annotations

import os

import pytest

from Detective.capabilities import apply_env, capability_identity, parse_env, restore_env
from Detective.purity import uncovered_env_reads


def test_parse_handles_set_absent_and_refuses_malformed():
    assert parse_env(["A=1", "B-", "C="]) == (("A", "1"), ("B", None), ("C", ""))
    with pytest.raises(ValueError):
        parse_env(["NONAME"])


def test_apply_and_restore_round_trips_including_absent(monkeypatch):
    """A declared env applies live and restores EXACTLY — a prior value comes back, and a variable
    that was absent is put back to absent, never left set."""
    monkeypatch.setenv("KEEP", "orig")
    monkeypatch.delenv("WASABSENT", raising=False)
    saved = apply_env((("KEEP", "new"), ("WASABSENT", "temp"), ("DECLAREDABSENT", None)))
    assert os.environ["KEEP"] == "new" and os.environ["WASABSENT"] == "temp"
    restore_env(saved)
    assert os.environ["KEEP"] == "orig"
    assert "WASABSENT" not in os.environ  # restored to absent, not left set


def test_capability_identity_folds_env_and_stays_clock_compatible():
    assert capability_identity(None, (("A", "1"),)) == "env=A='1'"
    assert capability_identity(None, (("A", "1"), ("B", None))) == "env=A='1',B-"
    assert capability_identity(1.0, (("A", "1"),)) == "clock=1.0 env=A='1'"
    assert capability_identity(1.0) == "clock=1.0"  # clock-only unchanged
    assert capability_identity(None, ()) is None


def test_a_declared_env_covers_the_read_gate_an_undeclared_one_does_not():
    """The admissibility split: with ``--env`` supplied a process-env read is covered (the golden may
    proceed); without it the read stays refused. Env does NOT cover a clock read — each capability
    controls only its own class."""
    env_read = ("reads process env via os.environ",)
    assert uncovered_env_reads(env_read, False, env_supplied=True) == ()
    assert uncovered_env_reads(env_read, False, env_supplied=False) == env_read
    clock_read = ("reads the clock via time.time()",)
    assert uncovered_env_reads(clock_read, False, env_supplied=True) == clock_read


def test_a_declared_env_read_is_pinnable_an_undeclared_one_is_refused(tmp_path):
    """The B decision, end to end at the level it lives (`_golden_properties`, a direct call — not a
    full converge, whose live baseline is flaky when nested in pytest): with the env DECLARED the
    read is captured and a golden property is built, its assertion re-applying the env; UNDECLARED,
    the same read stays refused. (The full ``detective converge --env`` path is validated by the CLI
    e2e; here we pin the capture/coverage decision deterministically.)"""
    import ast

    from Detective.converge import _golden_properties

    src = (
        "import os\n\n\ndef mode():\n    if os.environ.get('FEATURE') == 'on':\n"
        "        return 'enabled'\n    return 'disabled'\n"
    )
    (tmp_path / "feat.py").write_text(src)
    node = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "mode")
    full = str(tmp_path / "feat.py")

    props, refused = _golden_properties(
        "feat.py::mode", node, full, "mode", str(tmp_path), env=(("FEATURE", "on"),)
    )
    assert not refused, f"a DECLARED env read must not be refused: {refused}"
    assert props, "a declared env read must yield a golden property"
    assert "FEATURE" in props[0].assertion_code and "environ" in props[0].assertion_code

    props2, refused2 = _golden_properties("feat.py::mode", node, full, "mode", str(tmp_path))
    assert not props2 and refused2, "an UNDECLARED env read must stay refused, not silently pin"
