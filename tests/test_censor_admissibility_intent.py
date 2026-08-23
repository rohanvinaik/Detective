"""Q1 intent — the code censor admissibility guard (§14 well-definedness) and the κ-gated propose rule.

A censor is admissible ONLY IF it is spine-sourced (from an OBSERVED near-miss — a call-site absence or a
rejected-rewrite witness, never the engine's own output; Prop. 9.4 (i)) AND retains plurality (σ̂ > 0 after
adoption; Prop. 9.4 (ii)). The two failures mean DIFFERENT things and must not fuse. These pin each branch
from intent, so a re-merge (e.g. dropping the source check, letting the engine confirm itself) fails here.
"""

from __future__ import annotations

from Detective.censor import (
    Censor,
    censor_admissible,
    censor_disposition,
    censor_retains_plurality,
    censor_spine_confirmed,
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
