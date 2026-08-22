# Theory map — negative specification, stage by stage

Navigational index for the negative-specification work. Each stage: what it is, the load-bearing
commitment, and where it lives in the formal document. Terse by design; the mathematics is in
`NEGATIVE_SPECIFICATION.md`, cited here by section and numbered result.

`ARCHITECTURE.md` maps what **exists today**; this file maps what is **designed** (and, for μ⁻ Form A,
grounded against the live engine but code-unwritten). Where they disagree, ARCHITECTURE wins on present
behaviour. Where this file disagrees with `NEGATIVE_SPECIFICATION.md`, the formal document wins.

**Verify the cited corpus:** `python docs/theory/check_reference_manifest.py`. Priors are hashed, not
copied; a prior changing under a claim fails loudly. External citations marked `verified: false` are
recalled, not looked up — they gate publication, not the build.

**Formal document:** `docs/theory/NEGATIVE_SPECIFICATION.md`. **Handoff block:** `docs/theory/CONSTRAINT_BLOCK.md`.

---

## Sign asymmetry — the kill-set is negative in content, single-signed in enumeration

**Commitment:** σ = teaching dimension over **labeled** examples (SC Thm 2.7), σ is μ-parameterized
(SC §2.3). A policy over program space alone specifies one sign of a two-sign teaching set, so the
object is σ(P, μ ∪ μ⁻) — a second policy instantiation, not new metatheory.
**Where:** §1 (Prop. 1.5), §2 (Prop. 2.2, 2.5; Def. 2.4). Read: SC §2.3, Thm 2.7 · Goldman–Kearns 1995.

## Winston's second operator — the historical claim

**Commitment:** the near-miss is the half of the 1970 learner that *specializes* a concept by the
example that fails. Testing inherited generalization and dropped specialization, because test-as-example
has no slot for a non-example.
**Where:** §2 (Historical note 2.6). Read: Winston 1970 · `law_as_architecture.md` §7 ·
`SSL_PAPER_SKELETON.md` §3.1 · Genesis IV-F/IV-G (SSL §7.3).

## μ⁻ — the output-space mutation operator (Wesker; Form A grounded)

**What:** a mutation operator on the **codomain**: perturb the return, re-run covering tests; all-green
means that output dimension is unpinned (a negative DOF).
**Commitment:** indifferent to syntax — it reaches behaviour no program-text operator expresses
(Prop. 3.5, the measured slugify separation). **Two build forms, both required** (grounded 2026-08-22):
*Form A* rewrites `return X → return _perturb(X)`, making each perturbation an ordinary `Mutant` that
reuses `evaluate_mutant`/`check_equivalent`/score/cover unchanged (this supersedes the earlier
"sibling type / rows keyed by perturbation" framing for the return codomain); *Form B* is a runtime
wrapper reaching the non-return codomain (generators, implicit-None, side effects), bespoke per sibling
type, load-bearing for the completeness guarantee.
**Where:** §3 (Def. 3.1–3.4, Prop. 3.5), §11 (Def. 11.4 Form A, 11.6 Form B, Prop. 11.7), Appendix A.
Read: `ARCHITECTURE.md` §0 (value-vs-run boundary μ⁻ respects).

## The perturbation family Π — the negative operator set

**What:** a type-indexed family Π = ⋃ Πᵣ (dispatched by codomain type), each perturbation fencing one
MUST-NOT invariant.
**Commitment:** the load-bearing core is the **independence pair** — →constant (the output must depend
on the input) and →identity (the output must be a non-trivial transform) — the value-space analogues of
the MC/DC independence conditions, caught by no positive operator. Design criterion: populate Πᵣ
preferentially with perturbations **orthogonal to the positive reach** (→const, →id, →empty on a
computed string, →NaN, →reorder), keeping positive-redundant ones only where codomain-totality needs
them.
**Where:** §11.8 (Def. 11.8 taxonomy, Def. 11.8b Π-completeness), Remark 11.9. Open: completeness of a
finite Πᵣ for structured R (§13 Q4).

## Typing Π — two forks (the engine holds no return-type model)

**Commitment:** [traced] `run_function_profiling` carries no return type and captures no return value.
*Fork 1* types Π from the AST alone and over-generates — a mis-typed perturbation raises on application
and receives `undefined`, so it is sound but noisy (partial self-correction: catches raising mismatches,
misses silent coercions like →negate on `bool`). *Fork 2* observes the codomain from a baseline
return-capture (the return sibling of Detective's `capture_call_inputs`) and types Π precisely. Fork 1 =
sound skeleton, Fork 2 = precision-completing pass.
**Where:** §11 (Def. 11.10, Prop. 11.11). Open: §13 Q4.

## Channel isolation — why the negative sign is non-redundant

**Commitment:** the positive and negative channels measure orthogonal quantities: `x+y ≡ (3x+3y)/3`
positively (identical value-kills) yet the choice carries negative-space information (the division's
undefined-at-a-point). Isolation is exactly what makes μ⁻ worth adding. Coupling is local and sparse
(collisions at shared (x,y) pairs), so the consistency cross-check (below) is real but partial.
**Where:** §5 (Thm 5.2 isolation, Prop. 5.5 consistency, Cor. 5.6 the two irreducible residues).

## The automation boundary — where the human is

**Commitment:** σ = teaching dimension, and a teaching dimension is undefined without a teacher.
Automation is total *below* the two-sign teaching set (the mechanical residual, oracle-free) and nil
*at* it. The tool relocates the oracle from synthesis-time (per-run `--input`) to authoring-time (once,
a finite triage); it does not remove it. The negative half of intent — the MUST-NOTs — is the part
previously leaking into the synthesis loop.
**Where:** §6 (Thm 6.2), §4 (Prop. 4.3 the `--input` residual is mis-classified un-authored intent).

## Censors — population-derived exclusions (Detective; blocked on κ)

**What:** "no correct implementation does X", derived from observed near-misses across **call sites**,
not from the function alone.
**Commitment:** a censor is I_ind — latent in the corpus, invisible per single read ("no caller passes
`None`" is a fact about the population). This is why censors need governance where μ⁻ does not, and why
they live in Detective, not the engine. The proof stays one function at a time; only the censor's
*derivation* reads the population — co-occurrence over call sites, NOT the per-function statistical smear
`ARCHITECTURE.md` §11 forbids.
**Where:** §9 (Def. 9.1, Rmk 9.2 one-function law). Read: SIGNIFICANCE_WEIGHTING §12; `law_as_architecture.md` §7.

## Governance — admissibility as a well-definedness condition

**Commitment:** adopt a censor only if **(i)** spine-sourced (carved from an observed near-miss, never
authored a priori, structurally incapable of confirmation from derived output) **and (ii)**
σ(P | C ∪ {c}) > 0. Without (ii) the central quantity is undefined, not merely unsafe (L_ind → 1
vacuously). Over-censoring is the degenerate controller from the negative side (σ collapses, EIG = 0),
detected by the machine-checked `self_confirming_cannot_certify` / `falsifiability_pivot`. `UNVERIFIED`
is never promoted to `forbidden`, exactly as `candidate-equivalent — UNPROVEN` is never promoted to
`equivalent`.
**Where:** §9 (Def. 9.3, Prop. 9.4, Def. 9.5). Read: SIGNIFICANCE_WEIGHTING §14; SSL §§4.3–4.4.

## The three-region completeness map

**Commitment:** I_solve = I_ind + I_ext. Structure resolves DOF⁺ for free (reported as `L`); the corpus
can teach DOF via induction (I_ind, uncomputed — the censor region); a teacher must supply the rest
(I_ext, reported as the `--input` residual). Detective currently reports the middle as though it were
the third.
**Where:** §4 (Def. 4.1 three regions, Def. 4.2 I_solve). Read: SSL §§1.4c, 2.5; SIGNIFICANCE_WEIGHTING §12.

## The UNDEFINED disposition — the negative channel's principled abstention

**Commitment:** the negative measure has its own denominator (codomain universe size); a
degenerate/inverting input collapses it to ⊥. That is `undefined`, a disposition sibling to `cut`,
excluded from `SCORED_DISPOSITIONS` — never coerced to `unconstrained` (the error slips) nor into
`SC=1` (a false badge). The negative-channel form of value-vs-run and cannot-determine-vs-determined-false.
**Where:** §7 (Def. 7.1–7.3, Prop. 7.4). Read: `ARCHITECTURE.md` §0.

## Decidability of the unqualified contract

**Commitment:** on the finite-domain, decidable-equivalence class with a complete μ±, `SC=1` is a
decision procedure for behavioural identity and the certificate `provably correct` needs no qualifier.
Off that class equivalence is undecidable (Rice; Budd–Angluin 1982) and the qualifier is mandatory. The
boundary is decidability, not the maturity of μ⁻; the certificate names its side.
**Where:** §8 (Thm 8.1, 8.2, Cor. 8.3 the observing set on the certificate).

## The authoring problem — a triage of a finite set

**Commitment:** Thm 6.2 reduces the human contribution to authoring the teaching set, and the act is a
**partition of the finite enumerated survivor set**: `equivalent/valid` (the `flag` side) vs `invalid`
(a fence). μ⁻ widens the triage universe so "partition the list" equals "specify the intent" rather than
"specify the syntactically-reachable subset" (Prop. 12.2). The un-triaged region is a high-entropy
signal that *asks* the operator (elicitation). Idiom partially auto-fills the valid partition by lens
agreement but never gates (a fluent wrong implementation writes fluent idiom).
**Where:** §12 (Def. 12.1 triage, Prop. 12.2, Def. 12.3 elicitation, Prop. 12.4 idiom, Def. 12.5 two
feed points: greenfield-native + ingestion-retrofit).

## ★ The bridge crux — γ = d = bridge count

**Commitment:** coverage is submodular over a **fixed** ground structure; a constraint that changes the
graph (a *bridge* joining disjoint clusters) violates submodularity — constructively, at the valuable
cases. Three quantities coincide: γ (composition gap, SC Thm 3.15), d (supermodular degree, Feige–Izsak),
bridge count. Target theorem: bounded-curvature greedy, degrading in d, recovering (1−1/e) at d = 0.
**Do not** cite SSL's dense-graph constants (L=0.528, ~3% knee, 28× drop) for a likely-sparse code
graph; measure d first.
**Where:** §10 (Def. 10.1–10.2, Prop. 10.3, Conj. 10.4, Caveat 10.5). Read: SIGNIFICANCE_WEIGHTING §13;
SC Thm 3.15.

## κ-gated removal — the fix this theory implies (#54)

**Commitment:** `audit --remove` deletes a test line-and-mutant-redundant *for one function*; the field
failure is that it was load-bearing over the closure — the bridge counterexample. Correct invariant:
safe to remove iff it banks zero κ-weighted coverage over the closure. Supporting theorems already
machine-checked (SC Thm 2.3, 3.11). Blocked on κ-for-code.
**Where:** §10 (Cor. 10.6). Read: SIGNIFICANCE_WEIGHTING §17; Detective #54.

## Empirical grounding — measured, not argued

**Commitment:** a behaviour-changing rewrite passes a positive `SC=1` badge on `slugify` (the boundary
is demonstrated, not inferred); the "degenerate" near-miss witnesses beat hand-written tests on
plausible refactors, catching the str→bytes API break on a zero-shipped-tests function — predicted by
teaching theory (a witness is a teaching artifact, not a natural sample). Plus the runnable ΔI_solve
thesis experiment.
**Where:** §14 (Measured), Appendix C (C1–C2 measured, C3 the ΔI_solve experiment, C4–C5 predicted).

## The generative intuition — staged error correction without a controller

**Commitment:** DNA fidelity is base selection + proofreading exonuclease + mismatch repair composed,
each cheap. The correcting information lives redundantly in the **representation** (the complementary
strand is the backup), not in a controller, and is inborn not derived. Two channels over one message
permit *correction*; one permits only *detection*. Landauer for the thermodynamics — local order is paid
for globally, so the construction is a compute budget, not a violation.
**Where:** Provenance. Read: Landauer 1961; SIGNIFICANCE_WEIGHTING §17.1.

---

## Open problems (formal statements in §13)

1. **κ for code** — the graph choice (call / import / obligation) decides whether I_ind is cheap or a
   research project. Blocks censors and κ-gated removal.
2. **The regime key** — keyed below the semantic-equivalence class a censor over-reaches, above it
   under-reaches. Working guess: typed interface + purity class. Wants a derivation.
3. **μ⁻ equivalence** — RESOLVED for Form A (Prop. 11.5: `check_equivalent` generalizes free, since a
   return-wrap perturbation is a compilable mutant); open for Form B (no mutant program to compile).
4. **Completeness of Π** — how much codomain a finite perturbation family fences; needs Fork 2's observed
   type to measure.
5. **The bounded-curvature bound** — measure d on the obligation graph; prove greedy degrading in d.
6. **Build ordering** — Form A + Fork 1 is buildable now (the walking skeleton); Form A + Fork 2 and
   Form B are the completeness passes; censors blocked on Q1–Q2.
