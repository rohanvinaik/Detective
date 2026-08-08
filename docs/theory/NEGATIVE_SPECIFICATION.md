---
title: "Negative Specification: the Other Half of the Teaching Set"
subtitle: "Winston's near-miss restored to mutation testing — μ⁻ over output space, censors as I_ind, and why the interesting cases are the ones that break the guarantee"
author: "Rohan Vinaik"
date: "2026-08-08"
status: "theory document (design-complete, pre-build; blocked on correctness/retooling in Detective + Wesker)"
target: "internal theory doc; feeds a Detective/Wesker build and possibly a short paper"
one_sentence_thesis: >
  σ is a teaching dimension over LABELED examples and is parameterized by the mutation policy, so a
  policy that enumerates only program space specifies one sign of a two-sign teaching set; restoring
  the second sign — Winston's near-miss, as μ⁻ over output space and as censors carried in I_ind —
  is not an addition to the theory but the completion of a homology that is already asymmetric only
  at the code end.
priors_do_not_rederive:
  - "σ = teaching dimension (SC Thm 2.7 / T5.17); σ is μ-parameterized (SC §2.3); Five-Field Identification"
  - "Representation independence (SC Thm 2.3); redundant ⟺ zero information gain (SC Thm 3.11); composition gap (SC Thm 3.15)"
  - "SSL completeness equation dH/dt = −(N + C(H)); bulk→tail transition; L, I_solve, H*"
  - "I_solve = I_ind + I_ext; L_ind the self-teaching fraction (SIGNIFICANCE_WEIGHTING §12)"
  - "The falsifiability guard: self_confirming_cannot_certify, falsifiability_pivot, retained-plurality budget"
  - "Censors as Winston near-miss made hard (law_as_architecture §7); regime = symmetry, regime is part of the key (§8)"
  - "Negative learning defined (SSL §3.1); Genesis IV-F censor-without-retraction, IV-G withdraw-on-does-not"
  - "Submodularity FAILS at bridges; bounded supermodular degree is the real object (SIGNIFICANCE_WEIGHTING §13)"
  - "Safe forgetting = σ-preserving reduction under κ (SIGNIFICANCE_WEIGHTING §17)"
voice: >
  measured; the finding is that a 1970 result was half-inherited, not that anything new was invented.
  Credit Winston and Minsky by name. The negative results (§6) are load-bearing and stated as such —
  the comfortable version of this theory would be a theory of the boring cases.
external_citation_caveat: >
  Every EXTERNAL citation in this document was recalled during design discussion, not looked up.
  Verify before quoting publicly. Internal references (the author's corpus, this repo's code) were
  read directly and are cited by file and section.
---

# Negative Specification

### The other half of the teaching set — a theory document

**One-sentence abstract.** Detective specifies a function by killing mutants, and the kill-set is
already negative *in content* — but the enumeration runs over program space only, so the authoring
surface has one sign where the teaching dimension it is proved equal to has two; we restore the second
sign as Winston's near-miss in two distinct mechanisms (**μ⁻**, a mutation operator on the codomain,
and **censors**, population-derived exclusions occupying the previously-unpriced `I_ind` region of the
completeness map), show that the existing falsifiability guard is already the correct governance for
both, and identify the real obstacle as the bridge/supermodularity failure that makes every inference
worth having also the reason a clean greedy bound does not hold.

---

## The Empowerment Promise

**What you can do after reading this that you could not before.**

- Say of a function not only *what its tests pin* but *what its tests forbid* — and know that those
  are different quantities, one of which is currently uncomputed.
- Explain, with a receipt, why a `✓ COMPLETE` certificate can be passed by a behaviour-changing
  rewrite, without that being a defect: the certificate names its observing set, and the rewrite is
  outside it.
- Price the region between "structure resolved it for free" and "a human must tell us" — the
  corpus-teachable middle (`I_ind`) that Detective currently reports as though it were irreducibly
  external.
- Know in advance which half of this is cheap (μ⁻: one wrapper, existing kill matrix) and which half
  is a research project (censors: blocked on κ for code), and why.

**The promise is deterministic, auditable, and abstaining — unchanged.** Nothing here introduces
inference into the engine. A negative constraint is evidence with a provenance or it is not adopted.

**The humility that makes it strong.** Winston's 1970 learner had two operators. The field inherited
one. This document does not invent the second; it observes that the author's own corpus already
restored it twice, in two other domains, and that the code end of the homology is the only place it is
still missing.

---

## 0. The invariant that keeps it honest

Stated once, never violated below:

> **A negative constraint is evidence with a provenance, never an authored assumption. It may only be
> derived from an observed near-miss, and it must remain breakable by a witness — exactly as `flag`
> is. A censor that cannot be broken is not a specification; it is a bug with a veto.**

**Commitment.** This is `flag`'s governance with the sign reversed, and that symmetry is deliberate
rather than convenient. `flag` records a human oracle about the *positive* space (this mutant is
equivalent) and is outranked by any distinguishing input — "proof beats judgement." A censor records
an oracle about the *negative* space (no correct implementation does this) and must be outranked by any
*wanted behaviour* that violates it. Same hierarchy, opposite sign. Reusing it means the epistemics are
already built and already machine-checked (§5).

---

## 1. The historical claim

**What this section argues:** "CS ignored half the input space" is a precise statement about which half
of a 1970 learner survived into a field, not a rhetorical flourish — and the missing half has already
been restored twice in this corpus.

Winston's structural learner (*Learning Structural Descriptions from Examples*, MIT AI-TR-231, 1970;
bundled at `ARC_AGI_3/docs/theory/external/`) had **two** operators:

1. **generalize** from a positive example — widen the concept;
2. **specialize** from a **near-miss** — a non-example differing in exactly one crucial respect,
   installing a MUST-NOT link.

Software testing inherited the first and dropped the second — not by argument, but because the
test-as-example framing had no slot for the second sign.

**Commitment (the corpus already has both halves; only the code end does not).** The restoration is
not speculative:

| where | the negative operator, running |
|---|---|
| `law_as_architecture.md` §7 | "The censors — **forbidding what no real instance does**." Near-misses carved into Minsky censors; the response to an almost-valid-but-impossible candidate is *"not to score them down but to forbid them"* — "a hard veto, an `−∞` in the dynamic program, not a penalty." |
| `SSL_PAPER_SKELETON.md` §3.1 | "**Negative learning, defined.** The informative constraints are exactly the ones that kill a candidate you did not know was alive — you learn at the **residual**." |
| Genesis IV-F (SSL §7.3) | a censor recorded to explain an exception **with no retraction** — annotated in the corpus as *"the dual of version-space widening."* |
| Genesis IV-G (SSL §7.3) | a sub-threshold candidate meeting a contradicting *does-not* is withdrawn before it ever fires — *"negative learning made literal."* |
| Detective / Wesker | **absent.** |

**The gap is in the homology, not the theory.** `SSL_PAPER_SKELETON.md` §6.1's table maps program
identity ↔ a text's meaning, surviving mutant ↔ candidate reading, killing test ↔ context constraint.
Every row is symmetric *except* that the semantic side runs both version-space operators and the
program side runs one. Detective is the asymmetric end of an otherwise symmetric homology.

**Read:** Winston 1970 · Minsky, *A Framework for Representing Knowledge* (1974) and *K-lines* (1980) ·
`law_as_architecture.md` §7 · `SSL_PAPER_SKELETON.md` §§3.1, 6.1, 7.3.

---

## 2. The formal statement

**What this section argues:** three facts already in the corpus give the result with no new theory, and
the Lean does not need rewriting.

### 2.1 σ is a teaching dimension over LABELED examples

`specification_complexity_paper.md` Thm 2.7 (`T5_17_teaching_dimension_lower_bound` /
`_upper_bound`): σ(P, μ) equals the teaching dimension of P's semantic equivalence class in the concept
space induced by μ.

**Commitment.** Teaching dimension (Goldman–Mathias 1996; Goldman–Kearns 1995) is defined over labeled
examples of *both signs*. There is no positive-only teaching dimension: for most concept classes
nothing bounds the concept from above without negatives. The quantity σ is proved equal to therefore
*already* has two signs in its definition.

### 2.2 σ is parameterized by μ, and the paper owns this

`specification_complexity_paper.md` §2.3, "The role of the mutation policy." The completeness claim is
relative to μ. `✓ COMPLETE (operator universe · modulo N unproven-equivalent)` is correctly scoped and
always was.

**Commitment.** The claim here is *not* that the badge overclaims. It is that the badge is honestly
scoped to a universe which enumerates **one label**. Adequacy over one sign of a two-sign teaching set
is exactly as complete as it says and no more.

### 2.3 Therefore negative operators are a second policy, not a repair

The object is **σ(P, μ ∪ μ⁻)**. Blum axiom satisfaction, the exponential separation, and the
Five-Field Identification are all stated over an arbitrary μ and do not change.

> **The Lean formalization does not need rewriting. It needs a second policy instantiation.**

This is the formal content of "the same engine, with negative operators."

### 2.4 ★ The demonstrated boundary (measured, this repo, 2026-08-07)

`boltons/strutils.py::slugify`, converged to `✓ COMPLETE (operator universe · modulo 6
unproven-equivalent) · 9/15 killed`. A hand-authored structural rewrite —

```diff
- ret = delim.join(split_punct_ws(text)) or delim if text else ''
+ ret = delim.join(split_punct_ws(text)) if text else ''
```

— **changes behaviour** (`slugify("!!!")`: `'_'` → `''`) and **passes the COMPLETE contract**.

**Commitment.** This is not a defect and must not be reported as one. The transformation is outside μ —
a *context outside the observing set* the certificate names. It is the grounded demonstration that the
boundary is real and locates it exactly. A negative constraint — *"never returns empty for non-empty
input"* — catches it immediately and **is not expressible as any operator mutation**.

> **Semantic negatives cover exactly the region the syntactic universe cannot reach.**

That is the strongest single argument in this document, and it is measured rather than argued.

### 2.5 Corollary: "degenerate witness" is a category error, and it will recur

Converge's witnesses for `slugify` — `slugify(text=0, delim=0, lower=0, ascii=0) == ""`,
`slugify(0, 1, 2, 3) == b""`, an `AttributeError` capture — were called *degenerate* by a reviewing
model (Opus 5, session 2026-08-07/08).

Tested against four plausible refactors, those three tests caught the **str→bytes API break** (the most
likely real-world "modernization" of that function), caught an early-return guard change, correctly
stayed green on a behaviour-preserving reorder, and missed only §2.4's out-of-universe rewrite.
`boltons` ships **zero** tests for `slugify`; absent `slugify(0,1,2,3) == b""`, nothing in the repo pins
the return type.

**Commitment.** Teaching dimension is defined by a **teacher choosing examples to minimize
identification cost**, explicitly not by sampling a natural distribution — which is the whole reason TD
and VC are incomparable. Grading a witness by "does this look like a test a person would write" applies
*learner*-intuition to a *teaching* artifact. The framework predicts the computed near-miss wins. It
did.

*Recorded because it recurs: every model review of this tool has raised this objection, and the
objection is predicted by the framework the tool implements.*

**Read:** `specification_complexity_paper.md` §§2.3, 2.4 · Goldman–Kearns 1995 · Zilles et al. 2011 (RTD).

---

## 3. Two mechanisms, and they are not the same design

**What this section argues:** conflating μ⁻ with censors is the way this gets muddy; they occupy
different regions, carry different provenance, and belong to different repos.

| | **μ⁻ — output perturbation** | **Censors** |
|---|---|---|
| what | a mutation operator on the **codomain**: perturb the return value, re-run covering tests | a learned exclusion: "no correct implementation does X" |
| enumerates | output space | nothing — it *forbids* a region |
| provenance | mechanical, per-function, deterministic | derived from observed near-misses across call sites |
| region (§4) | extends μ — known-knowns | `I_ind` — unknown-knowns |
| home | **Wesker** (it is an operator) | **Detective** (it needs judgement + governance) |
| may it gate? | yes, same status as any operator | only under §5 admissibility |
| blocked on | nothing | κ for code (§8 Q1), regime key (§8 Q2) |

**Commitment (μ⁻ is the cheap symmetric half).** Wrap the target, return a perturbed value, run the
covering tests; green means that output dimension is unpinned. It is **indifferent to syntax**, which is
why it reaches §2.4's case. It reuses the existing kill matrix, trace, and minimal-cover machinery, and
it is the obvious first build.

**Commitment (censors are the deep half, and they are `I_ind`).** They are population-derived, not
per-function, which puts them in a region Detective does not currently compute at all.

---

## 4. Where each sits: the three-region completeness map

**What this section argues:** Detective already reports two of the three regions and already prints
`I_solve` by name; censors are the missing middle.

`SSL_PAPER_SKELETON.md` §2.5 gives the two-region map; `SIGNIFICANCE_WEIGHTING.md` §12 splits the
residual:

$$I_{\text{solve}}(D) = \underbrace{I_{\text{ind}}(D)}_{\text{the corpus can teach itself}} + \underbrace{I_{\text{ext}}(D)}_{\text{must be told}}, \qquad L_{\text{ind}} = \frac{I_{\text{ind}}}{I_{\text{solve}}}$$

| region | quantity | who resolves it | in Detective today |
|---|---|---|---|
| known-knowns | `L(D)` | structure, for free | **reported** — "% resolved by structure for free" |
| unknown-knowns | `L_ind(D)` | the corpus, by induction | **not computed** |
| known-unknowns | `I_ext(D)` | a teacher, irreducibly | **reported as `I_solve`** — the `--input` residual |

The `converge` report already prints *"structure exhausted — N killable residual(s) = I_solve"*, so the
SSL equation is wired into the output under its own variable name. What is missing is the middle.

**Commitment (censors ARE `I_ind` for code).** §12's characterization transports exactly:

> $I_{\text{ind}}$ is latent in the corpus and unreachable *per read*: story A alone does not support
> the law; A…N together do.

*"No caller ever passes `None`"* is not derivable from the function. It is derivable from the
**population of call sites**, and is invisible to any single read. That is `I_ind`; it is
`law_as_architecture.md` §7's *forbidding what no real instance does*; and the mechanism is SSL's **H6**
— a distorted or absent expected signal is itself a signal. The absence in the observed distribution
is the datum.

### 4.1 Commitment: this does not violate the one-function law

`ARCHITECTURE.md` §11 forbids repo-scale aggregation — *"There is no such object as 'the mutant profile
of a codebase' worth computing"* — and removed `diagnose --learn` for exactly that.

That law targets the **statistical smear**: per-category survival accumulated across unrelated
functions into a project-wide weakness report. `I_ind` is a different object: **co-occurrence over call
sites**, computing a fact about how *this* function is used, not an average over functions that have
nothing to do with each other. The proof stays one function at a time; only the censor's *derivation*
reads the population.

State this explicitly in any issue. The two shapes look similar, and the distinction is the entire
license.

**Read:** `SSL_PAPER_SKELETON.md` §§1.4b, 1.4c, 2.5 · `SIGNIFICANCE_WEIGHTING.md` §12 ·
`law_as_architecture.md` §7.

---

## 5. Governance — the guard is load-bearing on the math, not on safety

**What this section argues:** the obvious objection (negatives introduce false refusal) is not a new
failure mode, and the guard that handles it is already proved.

`SIGNIFICANCE_WEIGHTING.md` §14 is unambiguous:

> **Without the guard, the extension's central quantity is not merely unsafe; it is undefined.**

A censor confirmed from the engine's own derivations reduces the residual *by construction* while
carrying zero information: the descent looks fast and means nothing, and `L_ind → 1` vacuously.

> **Admissibility (censor form).** Adopt censor `c` only if
> **(i) spine-sourced** — carved from an *observed* near-miss (a real call site; a rejected rewrite's
> witness), never authored a priori, and structurally incapable of confirmation from derived output;
> **and (ii) σ(P | C ∪ {c}) > 0** — the program space still admits plurality after adoption.

**Commitment (over-censoring is the degenerate controller, from the other side).** Forbid enough and
exactly one program survives: σ collapses, EIG = 0. The formal detectors already exist and are
machine-checked — `self_confirming_cannot_certify`, `falsifiability_pivot` (MI > 0 ⇔ the answer channel
is non-degenerate) — with SSL §4.4's retained-plurality budget (R̂ must not be driven to 0) as the
quantified lower bound. **This is the principled-abstention design for the negative side, and it is
not new work.**

**Commitment (verdict vocabulary mirrors the existing discipline exactly).**
`candidate-equivalent — UNPROVEN` is never promoted to `equivalent`; likewise a negative constraint is
**`UNVERIFIED`** until spine-sourced and passing (ii), and is never promoted to **`forbidden`** by
assertion. An LLM-authored constraint is an unverified assertion and **must not gate**.

**Commitment (reporting channel).** Negative results get their own channel and are **never folded into
the kill count** — for the same reason crash kills are not (`ARCHITECTURE.md` §0: value-specification
vs run-specification). A censor is not a kill; it is an exclusion with a different warrant.

**Read:** `SIGNIFICANCE_WEIGHTING.md` §14 · `SSL_PAPER_SKELETON.md` §§4.3, 4.4.

---

## 6. ★ THE CRUX: the bridge problem, and it is quantitative

**What this section argues:** the real obstacle is negative, it is the same finding as
`SIGNIFICANCE_WEIGHTING.md` §13, and the comfortable version of this theory would be a theory of the
boring cases.

Coverage is submodular over a **fixed** ground structure. Where adopting a constraint *changes the
graph coverage is read from*, submodularity is violated — and constructively: a **bridge** connecting
two previously-disjoint clusters has small marginal gain alone and large marginal gain once another
bridge is present. Gains are **super**-additive.

> **And this is not an edge case — it is the target.** Every deep inference worth having is a bridge.

### 6.1 Three names, one quantity

- **γ** — composition gap: σ(A∘B) ≤ σ(A) + σ(B) + γ(A,B), bounded by the number of **interface
  mutants**, vanishing for independent components (`specification_complexity_paper.md` Thm 3.15).
- **d** — supermodular degree (Feige–Izsak): the number of adoptions connecting previously-disjoint
  components; greedy recovers (1−1/e) exactly at d = 0 (§13).
- **the bridge count.**

**Commitment.** These are the same number: γ vanishes for independent components, d = 0 for no bridges,
and independent components *are* no bridges. Detective #16 ("model the decomposition composition gap as
explicit interface obligations") is therefore the code-side instance of §13's crux, and **measuring
interface obligations is measuring d.** One quantity to measure, not two to reconcile.

### 6.2 Prediction, and an explicit correction

Censors span call sites. In a **sparse** obligation graph with genuinely disconnected clusters — which
a call graph over functions most likely resembles, and which Regenesis's rule graph measured as
(b ≈ 0.46–0.56 < 1) — a censor **is a bridge**: super-additive with positive tests, not redundant with
them.

That is *stronger* than "negatives are valuable early," and *worse* for tractability: negative operators
would be the biggest wins **and** the reason a clean greedy bound does not hold.

**Correction, recorded so it is not re-made.** During design discussion it was predicted that censors
would land in the **bulk** regime and produce a sharp knee, by analogy with SSL's measured ~3 % knee and
28× drop. That imports constants from the wrong regime. §13 is explicit:

> the *structure* (coverage, monotonicity) transfers; the *constants* (`L=0.528`, the ~3 % knee, the 28×
> drop) were measured on a dense graph and say nothing about a sparse one. They must be measured on the
> rule graph or not cited.

> **Measure d on the obligation graph before claiming any bound. Do not cite SSL's constants for code.**

### 6.3 What survives regardless

- **Monotonicity.** Adoption is a forward closure; adding a constraint can only grow the excluded set.
  Nearly free in Lean.
- **Submodularity away from bridges.** Within a connected component the classic argument goes through;
  the violation is localized to bridge events.

So the target theorem is **bounded-curvature greedy**, degrading in d — not submodular greedy.
Golovin–Krause adaptive submodularity is the other candidate frame and fails in the same place.

**Read:** `SIGNIFICANCE_WEIGHTING.md` §13 · `specification_complexity_paper.md` Thm 3.15 ·
Feige–Izsak (bounded supermodular degree) · Golovin–Krause 2011.

---

## 7. What this theory already fixes

**What this section argues:** two live issues are instances of this theory rather than separate bugs,
and one of them has a machine-checked fix waiting upstream.

### 7.1 `audit --remove` measures the wrong invariant (#54)

Field-observed: Detective proposes deleting a test as line- and mutant-redundant; the test turns out to
encode behaviour load-bearing elsewhere.

**Commitment.** That is §13's bridge counterexample exactly — **near-zero marginal gain inside one
function's kill-profile, large gain over the closure.** `audit --remove` measures the local quantity,
which §13 proves is the wrong one precisely at the cases that matter.

`SIGNIFICANCE_WEIGHTING.md` §17 gives the correct gate from theorems already machine-checked upstream —
representation independence (SC Thm 2.3) and redundant ⟺ zero information gain (SC Thm 3.11) — with
**κ** as the invariant rather than local coverage:

> A test is safe to remove iff it banks zero **significance-weighted** coverage over the closure — not
> iff it is redundant for this function's kills and lines.

§17 already names Detective's `decompose --apply` as the same operator run forward on code
("consolidation is that same operator run OFFLINE over accumulated MEANING"), so the symmetry is
recognized in the corpus. Blocked on §8 Q1 (κ for code).

### 7.2 The observing set should appear on the certificate

§2.4's rewrite passes a COMPLETE badge. The badge is honestly scoped, but a reader takes "COMPLETE"
from the headline and the scope from a parenthetical.

**Commitment.** Once μ⁻ exists, the certificate should name its **context set** — the observing set the
claim is made over — not only a ratio. A receipt that states its own boundary is a stronger artifact,
and it makes the claim self-limiting in writing rather than in a footnote. This is the code-side form of
SSL §1.4c ("completeness is relative to the substrate — and that is the feature, not the flaw").

---

## 8. Open questions, in the order they block the build

1. **What is κ for code, and is it computable from what we already hold?** In GSE it is genealogy
   PageRank over the IS-A graph. The code analogue needs a graph — call graph? import graph? the
   obligation graph induced by interface mutants? — and the choice decides whether `I_ind` is cheap or a
   research project. **Blocks censors AND §7.1.**
2. **What is the regime key?** T6.15: regime = symmetry; admissible resolutions are lawful
   symmetry-breakings indexed by the constraint frame's invariance group. For meaning, GSE's paraphrase
   operators are *proved* to generate that group (`gse_paraphrase_complete`). For code the analogue is
   the semantic-equivalence class — and a censor keyed *below* it over-reaches (traps positions that
   merely rhyme, `law_as_architecture` §8), keyed *above* it under-reaches. Working guess: typed
   interface + purity class. **Wants a derivation, not an intuition.**
3. **Does μ⁻ need its own equivalence notion?** Two output perturbations can be indistinguishable for
   the same reasons two mutants can. If so, `candidate-equivalent — UNPROVEN` needs a mirror on the
   negative side — and TCE-style bytecode identity (Wesker #24) does **not** apply, since there is no
   mutant program to compile.
4. **Ordering.** μ⁻ is buildable now and independent of κ. Censors are blocked on Q1 + Q2. The
   correctness/retooling work in both repos precedes all of it.

---

## 9. Status ledger — proved / transported / asserted / conjectured / measured

**PROVED (inherited, machine-checked — cite, do not re-derive).**
σ = teaching dimension (SC Thm 2.7 / T5.17); σ μ-parameterized (SC §2.3); representation independence
(SC Thm 2.3); redundant ⟺ zero information gain (SC Thm 3.11); composition gap (SC Thm 3.15);
`self_confirming_cannot_certify`; `falsifiability_pivot`; `coverage_submodular`, `marginal_antitone`,
`greedy_coverage_bound` — **the last three over a *fixed* ground structure only; see §6.**

**TRANSPORTED (argued here, not re-proved).**
That teaching dimension's two-label definition makes positive-only enumeration one-sign (§2); that
§14's admissibility applies to censors with the sign reversed (§5); that §12's `I_ind` is the region
censors occupy (§4); that §17's κ-gate is the correct `audit --remove` invariant (§7.1); that γ = d =
bridge count (§6.1).

**ASSERTED / UNBUILT.**
μ⁻ as an operator family; censor derivation from call-site populations; κ for code (§8 Q1).

**CONJECTURED.**
Bounded-bridge greedy for the obligation graph (§6, following §13's conjecture); that censors are
bridges rather than bulk (§6.2 — a prediction, explicitly not a result).

**MEASURED (this repo, 2026-08-07).**
The out-of-universe rewrite passing a COMPLETE contract (§2.4); the near-miss witnesses outperforming
hand-written tests on plausible refactors (§2.5).

---

## Appendix A — Equation entry points (to be developed into Definitions/Theorems)

- **The object.** σ(P, μ ∪ μ⁻) — specification complexity under a two-sign policy. All SC results are
  stated over arbitrary μ; this is an instantiation, not an extension.
- **μ⁻ (output perturbation).** For target f with covering tests T: for each perturbation p in a
  policy-defined family over f's codomain, `unpinned(p) ⇔ ∀t ∈ T : t(f ⊕ p) passes`. The kill matrix
  gains rows keyed by perturbation instead of mutant.
- **Censor.** c ⊆ (input × output) forbidden pairs, derived from call-site population evidence;
  `admissible(c) ⇔ spine_sourced(c) ∧ σ(P | C ∪ {c}) > 0`.
- **Three-region map.** `I_solve = I_ind + I_ext`; `L_ind = I_ind / I_solve`; extended completeness
  tuple `(H₀, L, L_ind, H*, I_ext)`.
- **Bridge degree.** d = |{adoptions connecting previously-disjoint components}| = γ's interface-mutant
  bound. Target: greedy guarantee degrading in d, recovering (1−1/e) at d = 0.
- **κ-gated removal.** `safe_remove(t) ⇔ κ_closure(T) = κ_closure(T \ {t})` — significance-weighted,
  not local.

## Appendix B — Citation ledger (priors to cite, not re-derive)

**Author's corpus (read directly; cite by file + section).**
`specification_complexity_paper.md` §§2.3, 2.4, Thm 2.3, Thm 2.7, Thm 3.11, Thm 3.15 ·
`SSL_PAPER_SKELETON.md` §§1.4b, 1.4c, 2.5, 3.1, 4.3, 4.4, 6.1, 7.3 ·
`SIGNIFICANCE_WEIGHTING.md` §§12, 13, 14, 17 · `law_as_architecture.md` §§7, 8 ·
`ARC_AGI_3/docs/GLOSSARY.md` · this repo: `ARCHITECTURE.md` §§0, 11; `docs/PARSIMONY_ADVISORY.md`.

**External priors (RECALLED, NOT VERIFIED — check before quoting).**
Winston 1970 (near-miss / structural descriptions) · Minsky 1974 (frames), 1980 (K-lines), 1986
(censors) · Mitchell 1982 (version spaces / candidate elimination) · Goldman–Kearns 1995,
Goldman–Mathias 1996 (teaching dimension) · Angluin 1987/1988 (exact learning) · Zilles et al. 2011,
Doliwa et al. 2014 (RTD) · Ammann & Offutt (RIPR; minimal mutant sets with Delamaro) · Budd & Angluin
1982 (equivalence undecidable) · Papadakis et al. (Trivial Compiler Equivalence) · Feige–Izsak (bounded
supermodular degree) · Nemhauser–Wolsey–Fisher (greedy (1−1/e)) · Golovin–Krause 2011 (adaptive
submodularity) · Hindle et al. (naturalness of software) · Landauer 1961 (erasure cost — the correct
frame for the DNA-repair analogy; local entropy decrease is a demon paying its bill, not a violation).

## Appendix C — Related issues

Wesker#23 (theory index: RIPR / equivalence / subsumption) · Wesker#24 (TCE) · Wesker#25 (subsumption /
dominator sets) · Wesker#15 (routing vs proof; static vs dynamic selection) · Wesker#16 (nodeid
identity) · Wesker#18 (RIPR's R as verified phase) · Detective#64 (theory index: observational
equivalence, behaviour-preserving transformation, evidence provenance) · Detective#16 (composition gap =
d) · Detective#54 (κ-gated removal) · Detective#63 (state boundary for oracles).

---

## Provenance

Designed with Rohan in session 2026-08-07/08, out of a cold-start review of Detective 0.11.0 that
produced §2.4 and §2.5 as measurements rather than arguments. The theory grounding is the ARC_AGI_3
corpus, reached via `docs/GLOSSARY.md` — the near-miss/censor half of the design is that corpus's, not
this document's; the contribution here is the observation that the code end of the homology never
received it, plus the three-names-one-quantity identification in §6.1 and the falsifiable ΔL / ΔI_solve
experiment implied by §4.

The biochemical framing that motivated the design — DNA repair as staged error correction whose
redundancy lives in the *representation* rather than in a controller, inborn rather than derived — is
recorded here because it is the generative intuition, and because it predicts the architecture: two
channels over one message let you *correct*, where one only lets you *detect*.
