"""Q1 intent — the code censor admissibility guard (§14 well-definedness) and the κ-gated propose rule.

A censor is admissible ONLY IF it is spine-sourced (from an OBSERVED near-miss — a call-site absence or a
rejected-rewrite witness, never the engine's own output; Prop. 9.4 (i)) AND retains plurality (σ̂ > 0 after
adoption; Prop. 9.4 (ii)). The two failures mean DIFFERENT things and must not fuse. These pin each branch
from intent, so a re-merge (e.g. dropping the source check, letting the engine confirm itself) fails here.
"""

from __future__ import annotations

from types import SimpleNamespace

from Detective.censor import (
    Censor,
    call_site_absent_censors,
    censor_admissible,
    censor_disposition,
    censor_retains_plurality,
    censor_spine_confirmed,
    censors_from_verification,
    harvest_call_site_censors,
    rejected_rewrite_censors,
    score_censor,
)


def test_spine_confirmed_only_for_observed_sources():
    assert censor_spine_confirmed("call_site_absence") is True
    assert censor_spine_confirmed("rejected_rewrite") is True
    # the engine's own output is NEVER a spine source — the Prop. 9.4 (i) guard
    assert censor_spine_confirmed("engine_derived") is False
    assert censor_spine_confirmed("") is False


def test_retains_plurality_is_sigma_hat_strictly_positive():
    assert censor_retains_plurality(1) is True
    assert censor_retains_plurality(0) is False  # σ̂ → 0: the space collapsed to one program
    assert censor_retains_plurality(-1) is False  # negative counts as collapse, not plurality


def test_admissible_names_which_condition_failed():
    assert censor_admissible("call_site_absence", 5) == "admissible"
    assert censor_admissible("rejected_rewrite", 3) == "admissible"
    # unsourced OUTRANKS the plurality check (short-circuits) — a provenance violation is first
    assert censor_admissible("engine_derived", 5) == "refuse_unsourced"
    assert censor_admissible("", 0) == "refuse_unsourced"
    # sourced but collapsing
    assert censor_admissible("call_site_absence", 0) == "refuse_collapses"
    # the two refusals are DISTINCT codes (the split is real, not cosmetic)
    assert censor_admissible("engine_derived", 5) != censor_admissible("call_site_absence", 0)


def test_disposition_is_kappa_gated_and_never_proposes_the_inadmissible():
    # admissible + κ>0 → propose (a bulk censor worth adopting)
    assert censor_disposition(7, "admissible") == "propose"
    # admissible + κ≤0 → abstain: the tail, taught not fenced (the §14 κ→0 stop)
    assert censor_disposition(0, "admissible") == "abstain_low_kappa"
    assert censor_disposition(-3, "admissible") == "abstain_low_kappa"
    # inadmissible → never proposed regardless of κ (proof/provenance outranks worth)
    assert censor_disposition(99, "refuse_unsourced") == "refuse_inadmissible"
    assert censor_disposition(99, "refuse_collapses") == "refuse_inadmissible"


def test_score_censor_composes_the_guard_then_the_kappa_gate():
    admissible = Censor("m.py::f", "input_absent", "None", "call_site_absence")
    unsourced = Censor("m.py::f", "input_absent", "None", "engine_derived")
    # spine-sourced + retains plurality + κ>0 → propose
    assert score_censor(admissible, 8, sigma_hat_after=5) == "propose"
    # spine-sourced but κ→0 → abstain (the tail, taught not fenced)
    assert score_censor(admissible, 0, sigma_hat_after=5) == "abstain_low_kappa"
    # spine-sourced but adoption collapses σ̂ → inadmissible (retained-plurality fails)
    assert score_censor(admissible, 8, sigma_hat_after=0) == "refuse_inadmissible"
    # engine-derived provenance → inadmissible regardless of κ
    assert score_censor(unsourced, 99, sigma_hat_after=5) == "refuse_inadmissible"


# ─── the call-site-absence source (Def 9.1's "no caller ever passes None") ───
def test_call_site_absent_censors_fences_none_absence_where_the_population_exists():
    cands = call_site_absent_censors("m.py::f", [(1, "x"), (2, "y")], arity=2)
    subjects = {c.subject for c in cands}
    assert "arg0=None" in subjects  # None never observed at arg0 → near-miss
    assert "arg1=None" in subjects
    assert all(c.source == "call_site_absence" and c.kind == "input_absent" for c in cands)


def test_call_site_absent_censors_skips_a_position_where_none_is_observed():
    # a caller DOES pass None at arg0 → not a near-miss there; arg1 (never None) still fenced
    subjects = {c.subject for c in call_site_absent_censors("m.py::f", [(None, "x"), (2, "y")], 2)}
    assert "arg0=None" not in subjects
    assert "arg1=None" in subjects


def test_call_site_absent_censors_needs_a_population():
    assert call_site_absent_censors("m.py::f", [], arity=2) == []  # no call sites → no censor
    # a position the population never exercises (arity 3, tuples len 2) yields nothing there
    assert "arg2=None" not in {c.subject for c in call_site_absent_censors("m.py::f", [(1, 2)], 3)}


def test_harvest_call_site_censors_reads_the_real_call_sites(tmp_path):
    (tmp_path / "m.py").write_text("def f(a, b):\n    return a + b\n\n\ndef caller():\n    return f(1, 2)\n")
    subjects = {c.subject for c in harvest_call_site_censors("m.py::f", str(tmp_path), arity=2)}
    assert "arg0=None" in subjects  # the only caller passes (1, 2) — never None → both fenced
    assert "arg1=None" in subjects


# ─── the rejected-rewrite source (a CHANGED rewrite's differences are near-misses) ───
def test_rejected_rewrite_censors_only_on_a_changed_verdict():
    cands = rejected_rewrite_censors("m.py::f", "CHANGED", ("f(1)->old2 new3", "f(0)->old0 new9"))
    assert {c.subject for c in cands} == {"f(1)->old2 new3", "f(0)->old0 new9"}
    assert all(c.source == "rejected_rewrite" and c.kind == "output_forbidden" for c in cands)
    assert rejected_rewrite_censors("m.py::f", "PRESERVED", ("x",)) == []  # no near-miss
    assert rejected_rewrite_censors("m.py::f", "ABSTAIN", ("x",)) == []  # not a rejection to learn from
    assert rejected_rewrite_censors("m.py::f", "CHANGED", ()) == []  # changed but nothing differed


def test_censors_from_verification_unpacks_the_outcome():
    v = SimpleNamespace(verdict="CHANGED", differences=("f(None)->old_raise new0",))
    cands = censors_from_verification("m.py::f", v)
    assert len(cands) == 1
    assert cands[0].subject == "f(None)->old_raise new0"
    assert cands[0].source == "rejected_rewrite"
