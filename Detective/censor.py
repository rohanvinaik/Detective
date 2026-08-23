"""Population-derived censors for code — the §9 / §14 negative layer above per-function μ⁻ (Q1).

A CENSOR is a forbidden input/output region for a function — "no correct implementation produces
(x, y)" — derived from an observed NEAR-MISS, NOT from the function alone (Rem 9.2: a censor is a fact
about the call-site POPULATION or a rejected rewrite, never a per-function μ⁻ survivor). Two spine
sources are unified here (user decision):

  * ``call_site_absence`` — the inputs observed across every call site (``discover_call_site_inputs``)
    define the admissible region; a systematically-absent, type-valid degenerate input ("no caller ever
    passes None") is the near-miss.
  * ``rejected_rewrite`` — a rewrite that CHANGED behaviour (``verify-rewrite`` 'different') yields a
    distinguishing (input, wrong-output): a spine-sourced near-miss no correct implementation produces.

This module's PURE decisions (below) are the §14 well-definedness core — the admissibility guard and the
κ-gated propose rule — pinned in isolation. The κ SCORING transports from :mod:`Detective.kappa`
(marginal coverage over the call graph). The impure SOURCING (harvesting near-misses) and the promotion
LEDGER are separate, deferred layers; these decisions are what any of them must consult, computed not held.
"""

from __future__ import annotations

from dataclasses import dataclass

# The two OBSERVED near-miss sources a censor may be spine-sourced from (the user-chosen unification).
# Anything else — most importantly the engine's OWN derived output — is inadmissible by construction.
_SPINE_SOURCES = ("call_site_absence", "rejected_rewrite")


@dataclass(frozen=True)
class Censor:
    """A population-derived forbidden region for ONE function (§9) — "no correct implementation
    produces this", carved from an observed near-miss, NOT from the function alone (Rem 9.2).

    ``kind`` names WHAT is forbidden (``input_absent`` — no caller ever passes ``subject``; or
    ``output_forbidden`` — no correct impl produces ``subject``); ``subject`` is the region descriptor
    (a repr / a region key); ``source`` is the spine (one of :data:`_SPINE_SOURCES`). The object holds
    no decision — :func:`score_censor` is where the admissibility + κ-gated propose logic lives.
    """

    func_key: str
    kind: str  # "input_absent" | "output_forbidden"
    subject: str  # the forbidden input/output descriptor
    source: str  # the spine source — "call_site_absence" | "rejected_rewrite"
    note: str = ""


def censor_spine_confirmed(source: str) -> bool:
    """Admissibility (i), §14 — SPINE-SOURCED. True iff the near-miss came from an OBSERVED source (a
    real call-site absence or a rejected-rewrite witness), NEVER the engine's own derived output.

    Without it ``I_ind`` is UNDEFINED, not merely unsafe (Prop. 9.4): a censor confirmed from the
    engine's own derivations reduces the residual by construction while carrying ZERO information. This
    is the structural guard §14 requires; the valid sources are exactly the two the loop unifies.
    """
    return source in _SPINE_SOURCES


def censor_retains_plurality(sigma_hat_after: int) -> bool:
    """Admissibility (ii), §14 — RETAINED PLURALITY. True iff adopting the censor leaves the program
    space still admitting more than one reading: ``σ̂(P | C ∪ {c}) > 0``.

    Maps SSL §4.4's retained-plurality budget (``R̂`` must not hit 0) to code: σ̂ is Detective's
    test-set-relative complexity estimate, and a censor that drives it to 0 has collapsed the space to a
    single self-confirming program (the over-forbidding degenerate controller, ``EIG = 0``). A negative
    σ̂ is treated as collapse — there is no admissible program left, so plurality is not retained.
    """
    return sigma_hat_after > 0


def censor_admissible(source: str, sigma_hat_after: int) -> str:
    """§14 admissibility, BOTH conditions, as a NAMED code (§18 Q1 guard, pure — pinned).

    A candidate censor is ``admissible`` ONLY IF it is spine-sourced AND retains plurality. The two
    failures are DIFFERENT and must not fuse into one truthy check — an unsourced censor is a
    provenance violation (the engine confirming itself), a collapsing one is a well-definedness
    violation (σ̂ → 0) — so each gets its own named refusal:

    * ``refuse_unsourced``  — not from an observed near-miss source (Prop. 9.4 (i) fails).
    * ``refuse_collapses``  — adopting it drives σ̂ to 0, collapsing plurality (Prop. 9.4 (ii) fails).
    * ``admissible``        — both conditions hold; the censor is well-defined and may be scored.
    """
    if not censor_spine_confirmed(source):
        return "refuse_unsourced"
    if not censor_retains_plurality(sigma_hat_after):
        return "refuse_collapses"
    return "admissible"


def censor_disposition(marginal_kappa: int, admissible: str) -> str:
    """The κ-gated PROPOSE decision (§14 Prop. 14.2, pure — pinned).

    Propose the ADMISSIBLE censor that maximizes κ-compression (a high-κ censor collapses a whole
    downstream cluster into one fence — the bulk); STOP when ``κ → 0`` (the bulk/tail knee, the
    principled halt, not an arbitrary cap — a κ=0 censor opens no new reach and is a tail constraint to
    be TAUGHT, not fenced). An inadmissible candidate is never proposed regardless of κ. Codes:

    * ``refuse_inadmissible`` — the guard did not pass (``admissible`` is a refusal code); κ irrelevant.
    * ``abstain_low_kappa``   — admissible but κ ≤ 0: the tail, taught not fenced (the §14 stop).
    * ``propose``             — admissible and κ > 0: a bulk censor worth adopting.
    """
    if admissible != "admissible":
        return "refuse_inadmissible"
    if marginal_kappa <= 0:
        return "abstain_low_kappa"
    return "propose"


def score_censor(censor: Censor, marginal_kappa: int, sigma_hat_after: int) -> str:
    """The full DECISION for one candidate censor (§14): the admissibility guard THEN the κ-gated
    propose rule, over the censor's spine source. Returns the disposition code — ``propose`` /
    ``abstain_low_kappa`` / ``refuse_inadmissible`` (see :func:`censor_disposition`).

    The accessor + composition; it holds no decision of its own. ``marginal_kappa`` comes from
    :func:`Detective.kappa.marginal_coverage` on the call graph (the censor's worth); ``sigma_hat_after``
    is Detective's σ̂ estimate AFTER hypothetically adopting the censor (the retained-plurality budget).
    """
    admissible = censor_admissible(censor.source, sigma_hat_after)
    return censor_disposition(marginal_kappa, admissible)


def call_site_absent_censors(func_key: str, observed_inputs: list, arity: int) -> list[Censor]:
    """Candidate censors from CALL-SITE ABSENCE — Def. 9.1's OWN example, "no caller ever passes None"
    (§18 Q1 sourcing, pure — pinned).

    For each argument position that the call-site POPULATION actually exercises, if ``None`` is never
    observed there, that is a near-miss → a candidate ``input_absent`` censor. A CANDIDATE generator
    only: it PROPOSES broadly (Prop. 12.4 — propose, never gate); :func:`score_censor`'s admissibility
    guard + κ-gate + human triage dispose, so over-generation is SAFE, not a false fence.

    Empty ``observed_inputs`` yields NOTHING — a function with no observed call sites has no population,
    so there is no near-miss to fence (a censor is a fact about the population, not about f alone,
    Rem 9.2). A position the population never exercises yields nothing either (no population there). v1
    fences the universal ``None`` only; type-specific degenerates (0, ``""``, ``[]``) are a later
    refinement. Membership is by identity (``is None``) so an unhashable observed arg (a list) is safe.
    """
    if not observed_inputs:
        return []
    out: list[Censor] = []
    for i in range(arity):
        seen_at_i = [t[i] for t in observed_inputs if len(t) > i]
        if seen_at_i and not any(v is None for v in seen_at_i):
            out.append(
                Censor(
                    func_key=func_key,
                    kind="input_absent",
                    subject=f"arg{i}=None",
                    source="call_site_absence",
                    note="no observed caller passes None at this position",
                )
            )
    return out


def harvest_call_site_censors(func_key: str, project_root: str, arity: int) -> list[Censor]:
    """Impure adapter: harvest the observed call-site inputs (``discover_call_site_inputs``) and run the
    pure :func:`call_site_absent_censors` over them. ``func_key`` is ``path::qualname``; the bare
    qualname drives the call-site scan. A thin shell — the near-miss DECISION is the pure function it
    calls; this only supplies the observed population."""
    from .call_sites import discover_call_site_inputs

    qualname = func_key.split("::")[-1]
    observed = discover_call_site_inputs(qualname, project_root)
    return call_site_absent_censors(func_key, observed, arity)
