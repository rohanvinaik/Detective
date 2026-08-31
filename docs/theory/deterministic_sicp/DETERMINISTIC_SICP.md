---
title: "Deterministic SICP: The Control Layer"
subtitle: "Specification-driven code quality as a multi-objective control problem — the fourth transport of the specification-complexity apparatus, and the second half of Detective"
author: "Rohan Vinaik"
date: "2026-08-31"
status: >
  founding design specification (2026-08-31). NOTHING in this document is built beyond the seams it
  names as existing. It records the theory, the transport, the control architecture, and the build
  program for the layer that completes Detective's core goal: making the idiomatic remainder of SICP
  — taste, efficiency, parallelization, organization, performance engineering — a directly
  optimizable set of decisions rather than vibes. Per-claim status tags throughout; the ledger is
  §13. The handoff cheat sheet is CONSTRAINT_BLOCK.md beside this file — carry it verbatim into any
  summary.
provenance: >
  This is a DETECTIVE-NATIVE document, not a separate project. It extends NEGATIVE_SPECIFICATION.md
  §15 (the canonical form as the σ+γ+I⁻ minimizer) across the remaining SICP axes, consumes the
  adequacy/knowability boundary (operator_completeness/) and the effect/meaning boundary
  (mechanical_layer/), imports Peitho's control-system hardware and Wayfinder's transport
  disciplines by citation, and is gated end-to-end by Detective's existing proof machinery. Where
  this document disagrees with the cited priors, the priors win.
priors_do_not_rederive:
  - "σ = teaching dimension (SC Thm 2.7); composition gap γ + interface-mutant bound (SC Thm 3.15/3.16); the greedy dynamics and bulk→tail transition (SC §3); regime = symmetry (SC Thm 4.1)"
  - "The adequacy ceiling — a full output-mutation score certifies exactly output coverage (operator_completeness Thm 4.4/4.5, machine-checked); the intent residual (KNOWABILITY §9–10)"
  - "Effect vs meaning — the mechanical layer computes effect, never meaning (MECHANICAL_LAYER Prop 3.3); coupling = footprint non-factorization = positive MI = γ>0 (Thm 4.2); extraction decidable for a bounded grammar, undecidable in general (Thm 4.4)"
  - "Two-sign σ(P, μ ∪ μ⁻); channel isolation (NEG_SPEC Thm 5.2); the automation boundary — automation total below the teaching set, nil at it (Thm 6.2); censor admissibility = spine-sourced + retained plurality (Def 9.3, Prop 14.7, machine-checked guards); bounded curvature `bridge_curvature_bound` (proved AND #print-axioms audited)"
  - "The canonical form: σ+γ+I⁻ minimization = consolidation = decompose run offline (NEG_SPEC §15, Thm 15.2/15.4, Prop 15.3/15.5)"
  - "The Peitho geometry: five-tuple positions off mined zeros, interference not averaging, the discrimination guarantee, the gate laws, exact min-cost flow (Peitho DESIGN §§2–6, otp/position/flow; transported once already as THE_REFOUNDING §4.1b's seven laws)"
  - "The Wayfinder disciplines: the deterministic core with a removable statistical layer (THE_DETERMINISTIC_CORE); the σ_search transport under SSL's license (THE_REFOUNDING §2); budget accounting + delta≥0 paired measurement (EXP-RF-005a/b); union/two-ledger accounting (§7.3 D3); the anti-overfitting law (§10.7); the granularity law for negative evidence (§10 item 8); regime conversion — structure is recognized, not predicted (WAYFINDER_RESEARCH §2.9.5)"
  - "The sandwich thesis: the PROOF unit is ONE function's operators and ONE function's tests; the one repo-scale surface is advisory and says so (Detective ARCHITECTURE §11; PARSIMONY_ADVISORY §0)"
---

# Deterministic SICP: The Control Layer

## The second half of Detective

### Abstract

Detective's first half is complete: what a suite can know about a function is characterized to its
theoretical maximum (the adequacy ceiling), the knowability boundary between mechanical effect and
authored intent is drawn exactly (the effect/meaning decomposition, the automation boundary), and
behavior is pinnable and provably preservable one function at a time. That half formalizes the
*provable* content of Structure and Interpretation — behavior pinned, seams proven, complexity
priced. What remains of SICP is the half every tool leaves to taste: efficiency, parallelization,
organization, language fit, engineering discipline — the judgment currently performed by
experienced engineers and encoded nowhere. This document specifies the layer that makes that
remainder *directly optimizable*: a control system whose **state estimator** places every code
region on independent signed-ternary banks against norms mined from the corpus itself; whose
**decision rule** is elimination by interference, never a weighted sum; whose **controller** routes
a finite improvement budget over admissible arcs by exact min-cost flow, where an arc is admissible
*iff a Detective proof gate exists for its transform*; and whose **actuator** is Detective's
existing behavior-preservation machinery, extended by warranted emission for the expensive moves.
The construction is the fourth transport of the specification-complexity apparatus (programs →
meaning → proofs → *form*), licensed by the same enumeration-fidelity condition the previous three
satisfied, and its central novel claim is that the expert's "rarified skillset" is a **regime
conversion**: performance engineering is template *recognition* over code (Regime A, polynomial σ)
followed by deterministic per-template transform grammars — not open-ended judgment (Regime B).
Taste survives exactly where the automation boundary puts it: at intent, and at the AMBIGUOUS
verdicts the banks escalate. Nothing here weakens the one-function proof law: the geometry is
repo-scale and *advisory*, exactly as `parsimony` already is; every write still passes a
per-function proof gate.

---

## 0. Why this document exists, and its governing use

**The founder is an unreliable oracle by his own designation, and this document is the mitigation.**
Stated 2026-08-31, verbatim:

> "I have severe ADHD and the concomitant memory issues, so formal documentation of decisions,
> design, and the logical deduction that is underneath it is absolutely a first-order priority. I
> am an unreliable oracle, because two hours from now this entire idea will have completely
> vanished from my head. If I engage in the problem space and reason through the important
> decisions, it will be almost completely from scratch, repeated indefinitely. Proper documentation
> lets you have stable ground, and lets me have a bit of a cheat sheet to reconstruct the whole
> idea."

Consequences, binding on every future session that touches this layer:

1. **This document is the ground truth for the design intent**, superseded only by the
   machine-checked priors it cites and by an explicit founder revision. A session must not
   re-derive a decision recorded here from scratch; it reads, then extends.
2. **`CONSTRAINT_BLOCK.md` beside this file is the reconstruction cheat sheet** — the compressed,
   carry-verbatim form. It must pass the Remove-X check: a fresh agent with only that block must
   recover the constraints, the build order, the forbidden moves, and the same next action.
3. **Every design decision lands here with its deduction**, not just its conclusion — the
   deduction is what vanishes from the oracle and what a future session cannot re-supply.

## 1. The Case

### 1.1 The founder's statement, verbatim (2026-08-31)

The motivating idea, in the founder's own words, preserved because the *reasoning* is the part
memory loses:

> "The original motivating idea was two-fold. First, I'm a biochemist by training, so the *moment*
> I first heard that there was such a thing as mutation testing I became obsessed. I never knew
> that was something that could exist, and when I heard even just the name I knew it was the
> answer. Second is SICP. I've actually met Gerald Sussman, the way he thinks is clean and
> delightful. I think SICP is a quirky and idiomatic, but actually deeply correct approach to what
> makes code good, efficient, powerful, and useful. I think that my formal work on my complexity
> metric and learning theory back up these intuitive insights with proofs and math."

> "What we have built here is the formal half of SICP. The part that is most clearly mathematical
> in nature. Even without a proof, it's obvious that a function that is less entangled and has
> lower complexity is a cleaner and more stable/better-specified function. Complexity is purely
> additive, decomposition definitionally leaves the surface of failures less than (or equal to in
> the trivial case) the sum of the failure space of the entangled function."

> "Now I have a desire to engage with what remains of SICP that we haven't completely integrated.
> Taste, efficiency, parallelization, engineering discipline, organization of the code and
> functions, and the job that is currently performed by experienced performance engineers
> (parallelization, JIT, one-hit, in-memory compute, cache optimization, etc). Right now in CS
> generally, and in SICP, these are idiomatic and vibe-y. But what we've built here is the
> computational and formal specification basis to make these concepts not vibes, but a directly
> optimizable set of decisions."

> "I see this as a control systems problem. These factors are all intertwined. Yes, it's nice to
> have functions be minimal, but too many functions start risking bloat, and a focus only on
> cutting lines of code PER function can risk duplication of function with slightly different
> idiomatic presentation. Parallelization and performance engineering is *obviously* a good thing,
> we pay people a LOT for that and it's a rarified skillset, but a naive view of complexity might
> see that as a form of entanglement to remove."

> "I see this as a resource optimization problem. We want to optimize several 'independent' systems
> at the same time. Code should be small per function. Functions should be disentangled and
> independent. Code should be organized cleanly by intended function and type of operation.
> Computational efficiency should be optimized. Code should be written in the proper language and
> paradigm that appropriately executes the operation (e.g. Rust vs Python vs C++). There should be
> clean commenting and type-checking. Linters should have little to bite on."

And the placement ruling, which governs this document's home:

> "This isn't a NEW project. It's supposed to be part of Detective itself. It's all based on the
> same mutation and specification complexity infrastructure as Detective. These aren't unique
> systems, they're inherently linked, this is the second part of Detective, needed to complete the
> core project goals."

*Precision note on the additive claim (recorded so the informal statement is never cited as the
theorem).* The exact form is SC Thm 3.15: σ(A∘B) ≤ σ(A) + σ(B) + γ(A,B), with γ = 0 exactly for
specification-independent components and γ bounded by the interface-mutant count (Thm 3.16). So
"complexity is purely additive" holds *at a clean seam* (γ = 0), and "decomposition leaves the
failure surface ≤ the entangled sum" is true **conditional on the seam** — a split with γ > 0
leaks specification across its interface and can cost. This is not a caveat against the founder's
intuition; it is the mechanism that *prices* it, and it is why the γ read is a bank of the
estimator (§4) rather than an assumption. [Status: PROVED prior.]

### 1.2 Why this is Detective's second half, not an application of it

Detective's README states the project's own division: the provable half of clean code gates writes;
the stylistic/epistemic half "is not provable, so Detective carries it as an advisory read"
(PARSIMONY_ADVISORY §0). The first half is now complete — and its completion *produced the
measurement basis the second half needs*:

- **σ and γ** price behavioral density and seam cleanliness (SC; already surfaced by `diagnose`).
- **The adequacy ceiling and the intent residual** (operator_completeness) draw the line between
  what any mechanical layer can know and what only the author holds — so the control layer knows,
  by theorem, where its own authority ends.
- **The effect/meaning decomposition** (mechanical_layer) proves the inert region is predicted,
  not noise — so the controller expects most flagged distinctions to carry no intent-information
  and never grinds on them.
- **The two-sign machinery, censors, κ, and bounded curvature** (NEG_SPEC §§9, 14) supply the
  governed negative channel — fences with admissibility conditions and a proved tractability
  bound — which is what keeps a self-improving control loop from confabulating its own constraints.
- **§15's canonical form** (σ+γ+I⁻ minimization = consolidation = `decompose` run offline) is the
  seed of this entire document: it already defines the *provable* axes of the objective and
  identifies the actuator. This document extends the objective across the remaining axes —
  efficiency, organization, duplication, language fit — which are **advisory** axes, and supplies
  the control law that navigates all of them at once. [Status: §15 is TRANSPORTED prior; the
  extension is this document's ASSERTED move.]

The existing code seams this layer grows from (all shipped, none new): `parsimony.py` /
`parsimony_map.py` (the banks and the one repo-scale advisory surface), `diagnose` (per-function
composition of the behavioral + structural reads), `audit --plan` (the per-move cost estimate
*without paying for it* — the arc-cost estimator), `decompose --apply` and `receipt` /
`verify-rewrite` (the proof-gated actuators), `censor.py` / `kappa.py` / `promotion_ledger.py`
(the negative channel and the call-graph κ machinery), `flag --fence` (authored must-nots).
[Status: ALL BUILT — this is the load-bearing fact that makes the second half a completion, not a
new system.]

## 2. The Stack — what each prior supplies

One table, so a future session never re-derives the division of labor:

| Layer | Source | Supplies | Status |
|---|---|---|---|
| Measurement theory + oracle | Detective/Wesker (this repo + engine) | σ, γ, DOF, value-vs-run, the adequacy ceiling, the intent residual; per-function proof gates (`decompose --apply`, `receipt`/`verify-rewrite`); the advisory/proof separation | PROVED / BUILT |
| Estimator + controller hardware | Peitho (`~/Projects/Peitho`) | signed-ternary banks off mined zeros; five-tuple positions (sign·depth·zero·path); interference (CONSTRUCTIVE/DESTRUCTIVE/AMBIGUOUS/SILENT); the discrimination guarantee; the conservative-keep gate laws; exact SSP min-cost flow over admissible arcs | BUILT + mutation-pinned (in Peitho) |
| Transport license + loop disciplines | Wayfinder (`~/Projects/Wayfinder`) | the σ_search precedent (third transport, THE_REFOUNDING §2); computed reads replacing estimated coordinates; the censor gate paying in *budget* at solve-delta exactly 0 (EXP-RF-005); split-validated norm/censor mining; the anti-overfitting law (§10.7); the granularity law; union/two-ledger accounting; regime conversion | MEASURED (in Wayfinder) |
| The negative channel, governed | NEG_SPEC §§9,14 + Detective `censor`/`kappa` | spine-sourced + retained-plurality admissibility (machine-checked guards); κ-ranked promotion to the κ→0 fixpoint; `bridge_curvature_bound` (audited) | BUILT / PROVED |

The Peitho and Wayfinder imports are **by citation and port** — their mechanisms transport, their
measured constants do NOT (NEG_SPEC Caveat 10.5: every κ/knee constant was measured on another
graph; nothing quantitative is asserted for code until measured here). [Status: standing law.]

## 3. The Fourth Transport: σ_form

### 3.1 The license and the table

SSL's transport license: the specification-complexity apparatus survives noun translation when the
candidate neighborhood is finitely enumerable and faithfully generated. Exercised three times —
program identity (SC), textual meaning (SSL), proof search (Wayfinder, σ_search). This document
performs the fourth: **form** — the identification of the correct transform for a code region.

| Specification Complexity (proved prior) | σ_form (this transport) |
|---|---|
| program identity | the region's target form — the σ+γ+I⁻-minimal member of its behavior class, *extended* by the advisory axes (§4) |
| surviving mutant (unconstrained DOF) | a candidate move (transform × site) the current evidence leaves admissible |
| a test that kills a mutant | a bank read of the region (a computed structural/behavioral/budget fact) — or a probe (a measured paired run) |
| σ = min tests to SC=1 | σ_form(region) = min bank reads/probes to isolate the correct move class |
| bulk phase (correlated kills) | the mechanical majority — lint-grade moves one read eliminates or licenses wholesale |
| tail phase (independent DOF) | the performance-engineering residual — one typed template per region (§6) |
| regime = symmetry of μ | symmetry of the transform grammar over code space (OPEN, §11) |
| composition gap γ | already literal: the interface cost of a decomposition, computable from interface mutants |

**Enumeration fidelity is satisfied by construction**, on the same ground as the third transport:
the candidate space is a **closed transform dictionary** × enumerable sites. The seed dictionary
(v1, deliberately small — every entry must eventually carry a proof gate): `extract-function` ·
`inline-function` · `deduplicate` (merge idiomatic near-twins) · `hoist-invariant` · `memoize` ·
`vectorize-loop` · `parallelize-map` · `batch-io` · `relocate` (move to the organizationally
correct module) · `rewrite-in-<lang>` (gated last, §8). σ_form is **grammar-relative**, exactly as
σ is μ-relative and σ_search is tactic-policy-relative — the relativity is named, not solved
(§11 Q1). [Status: transport ASSERTED under the license; the table is the claim EXP-DS-001 grounds.]

### 3.2 What the dynamics predict

Transported, the greedy dynamics predict: a **bulk** of cheap correlated eliminations (most
regions' correct move class is isolated by one or two reads — "clean, leave it alone" is the
dominant verdict, the SILENT majority), a **knee**, and a **tail** of regions each demanding its
own targeted evidence — the performance-engineering residual. The prediction is falsifiable on
day one: run the estimator over a real corpus and plot verdict-isolation cost per region
(EXP-DS-002). The Wayfinder precedent (EXP-058's 63.8% falling to the structural majority) says
the bulk is large; if code's bulk is small, the transport is in trouble and we want to know
immediately. [Status: TRANSPORTED dynamics; the code-domain knee is UNMEASURED.]

## 4. The State Estimator: banks for code

### 4.1 The existing seven, and the new axes

Detective already computes seven lenses under the exact protocol Peitho proved at production scale
(ternary votes, unmeasured→0, consensus by agreement — PARSIMONY_ADVISORY §§3–5; the convergence
of the two projects on this protocol was independent, which is evidence for the protocol). The
estimator = those seven, promoted from "advisory read" to "control-system state," plus the new
axes the founder's objective list demands:

| Bank | Reads | Zero mined from | Status |
|---|---|---|---|
| complexity | cognitive complexity | corpus percentile backstop (calibrated 2026-08-06) | BUILT |
| cohesion | def-use components | structural rule (1 component) | BUILT |
| overload | behavioral DOF / line | corpus backstop | BUILT |
| interface width | params | structural (`max_params=4`) | BUILT |
| seam | extraction candidates | structural | BUILT |
| regime | A/B entanglement | structural | BUILT |
| purity | is_pure | boolean | BUILT |
| **γ-seam** | interface-mutant estimate for a candidate split | structural (γ=0 is the zero) | BUILD (computable now — SC Thm 3.16; the bank that prices the founder's split-vs-bloat interlock) |
| **duplication** | idiomatic near-twin detection across the corpus | mined similarity norm | BUILD (deferred in PARSIMONY_ADVISORY §8 — this document un-defers it) |
| **organization** | import-layering / placement vs the module's declared role | mined layering norm | BUILD (deferred in §8 likewise) |
| **budget** | deterministic cost profile (§7) | mined per-corpus cost norms | BUILD |
| **language/paradigm fit** | shape-of-computation vs implementation idiom (the vectorizable-loop read, the IO-bound-loop read) | template membership (§6) | BUILD |
| **lint surface** | pinned-linter findings density | mined norm | BUILD (thin wrapper; the "long tail" bank) |

Bank protocol, inherited verbatim and binding: positions are Peitho five-tuples (sign, depth,
mined zero, provenance path) so the raw fact, the read, and its norm live in one row; banks never
fuse or average; an unmeasured bank votes 0; the informational zero is a verdict, not missing
data. [Status: protocol BUILT twice (Peitho, parsimony); new banks BUILD.]

### 4.2 The norms discipline — the answer to the self-normalizing-bad-repo problem

The question that blocked the design at first pass: per-repo zeros self-calibrate but a uniformly
bad repo reads as uniformly normal. The answer is **not a corpus choice but a discipline**,
imported from Wayfinder §10.7 and EXP-RF-005a, now stated as law:

1. **Mine per-corpus, validate out-of-sample.** Every mined zero and every censor is mined on a
   split (half the corpus, or a sibling-corpus panel) and validated on the unseen remainder
   before it may influence a verdict. A norm that fails out-of-sample is inadmissible — not
   tuned, *rejected*.
2. **Weight the mine by κ.** The demand-weighted-median move (Peitho: sellers mine the sales
   zero) transports as centrality-weighting: dead and unreferenced code cannot drag a norm,
   because the mine weights by call-graph κ (`kappa.py`, already built).
3. **Population-level warrant, never residual-chasing.** A new bank, norm, or template is
   admissible only with (i) a mechanistic justification independent of the failure that prompted
   it, (ii) a population-level measurement over the full corpus, (iii) out-of-sample validation.
   Parameterization is by rank/read/norm, **never by identity** of the function that annoyed us.
4. **The discrimination guarantee is the completeness check.** Two regions an expert treats
   differently sharing one signature is a *structural bug*; the fix is a new orthogonal bank off
   its own mined zero — never a moved threshold. The founder's own worry — "a naive view of
   complexity might see [parallelization] as entanglement to remove" — is exactly a collapsed
   signature (hot parallel kernel ≡ God-function under complexity+interface alone) and its fix is
   exactly a new dimension (the budget bank + template membership), which this design carries
   from day one. [Status: laws TRANSPORTED from measured practice; the code-domain instances UNMEASURED.]

## 5. The Controller

### 5.1 The decision rule: interference, then escalation

Per region, orient the bank positions toward the question ("should this region change, and how")
exactly as Peitho's `restock.orient` does, then read the interference verdict:

- **SILENT** — no bank has an opinion → leave it alone. The default, and the majority (asymmetric
  emission — silence is not a score of 0.5, it is the absence of a case).
- **CONSTRUCTIVE** — banks agree on a move family → the move enters the plan, *pending its proof
  gate*.
- **DESTRUCTIVE** — banks agree against → censor-grade elimination of that move family for this
  region (recorded with its warrant).
- **AMBIGUOUS** — banks disagree → **escalate to the driver** (human or model). This is where
  taste lives, by theorem: the automation boundary (NEG_SPEC Thm 6.2) puts intent outside the
  mechanical layer, and the AMBIGUOUS verdict is its operational address. The controller never
  resolves an AMBIGUOUS by weighting; one confident opposition vetoes a pile of weak supports.

Two gate laws bind, inherited from Peitho `resolve.gate`: *no signature → conservative keep*
(elimination requires positive evidence, never absence of measurement), and the *protected-class
escape hatch* (a region the founder marks under-study is never struck by a single read).
[Status: rule BUILT twice elsewhere; the code orientation tables are BUILD.]

### 5.2 The resource layer: budgeted flow over admissible arcs

The founder's "resource optimization problem," made literal. Improvement attention is a finite
budget flowing from a source to region-deficits over **admissible arcs**, solved by exact
min-cost flow (Peitho `query/flow.py` — SSP, integral by total unimodularity, dependency-free,
pinnable):

- **A deficit** = a region with a CONSTRUCTIVE verdict, sized by agreement count and depth.
- **An arc** = (move, region), existing **iff a proof gate exists for that move** (§8). No gate,
  no arc — an unprovable improvement is not an improvement this system can plan.
- **Arc cost** = the measured estimate from `audit --plan` (built: tier-0 static + tier-1 fan-in
  + a measured tier-2 mutation-cost estimate, without paying for it) plus the move's own
  transform cost class.
- **The plan** = the flow — which moves, where, in what order, under this budget. `parsimony
  --plan` (built) is the seed of this surface: it already emits the ordered work queue; this
  layer prices and gates it.

The split-vs-bloat interlock resolves inside this structure without a judgment call: a candidate
`extract-function` arc's cost includes its γ-bank read (a γ>0 seam is priced, not forbidden), and
a `deduplicate` deficit competes for the same budget — the controller trades them numerically,
and where the banks genuinely disagree the region reads AMBIGUOUS and escalates. [Status:
flow solver BUILT (Peitho); the code instantiation is BUILD.]

### 5.3 The negative channel

Censors for form: "move family F never pays on region shape φ" — mined from the population of
attempted/rejected transforms (the spine: `verify-rewrite` CHANGED verdicts, rejected `decompose`
trials, paired-run budget regressions), admissible only spine-sourced + retained-plurality
(machine-checked guards, already ported to Detective's `censor.py`), κ-ranked, split-validated,
and **paying in budget at behavior-delta exactly 0** — the EXP-RF-005 measurement shape
transports as the standing acceptance test for every censor wave. The granularity law binds from
day one: a fence mined at function granularity warrants nothing at module granularity — the
Wayfinder loop measured that failure so this layer never has to (§10 item 8). [Status: machinery
BUILT; the form-domain spine and mining run are BUILD.]

## 6. Regime Conversion: the expert as template recognizer

The central novel claim, stated conservatively:

**Claim (taste-as-recognition).** The performance engineer's skill decomposes as (a) *recognition*
of a bounded library of computation-shape templates — "vectorizable map," "IO-bound loop,"
"cache-hostile traversal," "memoizable pure recursion," "batch-able chatty interface" — and (b)
a deterministic per-template transform grammar. Raw "make this fast" is Regime B (each region
unique, exponential σ_form); template membership is Regime A (many regions per template,
polynomial σ_form). Structure is recognized, not predicted — the same conversion that turned
proof-structure prediction into template classification in Wayfinder (RESEARCH §2.9.5), with the
same architectural consequence: the recognition vocabulary is a bank (§4's language/paradigm-fit
bank), the grammar is deterministic, and anything statistical is confined to *ranking within* the
recognized template's candidate set. [Status: ASSERTED — the direct test is EXP-DS-004; the
precedent conversion is MEASURED in two domains.]

**The residualization tower** (transported shape): first order removes the mechanical bulk
(lint-grade, one-read moves); the typed residual goes to per-template executors (the analogue of
Dr. Ducky — each template's grammar applied deterministically, verified by the gate); what
survives is rendered as a **structured residual artifact** — the region's full signature, what
was eliminated and under which warrant, the surviving admissible moves — handed to the driver,
never as raw code + a shrug. A higher order is justified only by a strictly cleaner residual.
**Standing prediction, inherited from the measured Wayfinder exhaustion:** the one-shot-transform
tier will saturate, and the genuinely deep band is *composed campaigns* — multi-move refactors
where each move's value is enabling a later one. Plan for skeleton-and-holes campaign machinery
in the tower's second order; do not chase the composed band with more single-move grammar.
[Status: tower shape MEASURED elsewhere; code instances BUILD.]

## 7. The Budget Observable — efficiency without wall-clock

Determinism is the product; wall-clock is noise. The efficiency bank reads **deterministic,
countable budgets**:

1. **Operation counts on fixed inputs** — instruction/allocation/call counts under a
   deterministic counter, on inputs the converge synthesis stack already manufactures.
2. **The size-ladder read** — run the region over a synthesized input-size ladder (the synthesis
   machinery exists; this is a new consumer of it) and fit the count curve: a deterministic
   empirical-asymptotic read, the bank's depth value.
3. **Paired arms under the safety constraint** — every efficiency claim is a paired measurement:
   candidate vs incumbent, behavior-delta gated to exactly 0 by the Detective proof suite (the
   kernel of this domain), budget delta the payoff. The two-ledger rule binds: the proof gate
   owns validity (a proven-preserving transform stays proven regardless of run quality); run
   quality gates only the *evidence* about the machinery.

[Status: the measurement shape MEASURED (Wayfinder EXP-RF-005b — budget paid at delta exactly 0,
five consecutive paired rounds); the code instruments are BUILD (EXP-DS-003).]

## 8. The Actuator — no gate, no arc

Every transform in the grammar must name its proof gate before it may carry flow:

| Move | Gate | Status |
|---|---|---|
| extract/inline/hoist/deduplicate/relocate (same-language) | `decompose --apply` machinery / `receipt` + `verify-rewrite` | BUILT |
| memoize/vectorize/parallelize/batch (same-language) | `receipt` + `verify-rewrite` + the paired budget run (§7) | gate BUILT; budget harness BUILD |
| rewrite-in-<lang> | **warranted cross-language emission** — the receipt's obligations replayed against an emission that carries value/source duality, its toolchain/environment pin, and its warrant (the LeanExpr precedent: Lean-checked was strictly harder than Python-compiles and was crossed; `SourceExpr` → `LeanExpr` → this) | BUILD (last; EXP-DS-006) |

Until a move's gate exists, its arc does not — the controller plans only over what it can prove.
Parallelization gates carry one honest extra obligation: `receipt`/`verify-rewrite` certify
value behavior at the recorded obligations; scheduling nondeterminism outside the value channel
(ordering of side effects the spec never pinned) is exactly the two-sign residual — fence it with
authored `flag --fence` must-nots or report it UNREVIEWED, never absorb it. [Status: table is the
design; the cross-language gate is the hardest BUILD and is sequenced last.]

## 9. The Laws

Binding constraints, each with its reason, none restated elsewhere:

1. **The one-function proof law survives untouched.** The geometry is repo-scale and ADVISORY
   (parsimony's existing license: static, no mutants, proves nothing, says so); every write
   passes a per-function proof gate. There is still no repo-scale mutation profile, and this
   layer never needs one — the sandwich thesis is a constraint the design satisfies by
   construction, not a tension it manages.
2. **Advisory output never writes.** No path from a bank/verdict/plan to source mutation except
   through a gate (PARSIMONY_ADVISORY's reviewer check, extended to the whole layer).
3. **Interference, never weighted sums.** The two prototype post-mortems (Yami, ModelAtlas) and
   two production systems agree; a weighted sum of incommensurable axes is the named failure.
4. **Statistical components rank, never fence, never emit content.** Elimination requires a
   warrant (an admissible censor or a structural impossibility). Discovered structure is
   installed in the deterministic layer as rules (the tactic-compiler lesson).
5. **Norms and censors: mined at population level, κ-weighted, split-validated, granularity-
   bounded.** (§4.2, §5.3.)
6. **Budget claims are paired, delta-gated, two-ledgered.** (§7.)
7. **The intent residual stays human.** Which distinctions *matter* is meaning, not effect
   (MECHANICAL_LAYER Prop 3.3); the AMBIGUOUS escalation and the fence vocabulary are its
   channels. The automation boundary is the payoff, not a limitation.
8. **Constants do not transport.** Every number cited from Peitho/Wayfinder/SSL is
   mechanism-evidence only; measure d, the knee, and every norm on code before trusting any of
   them.
9. **Verbatim-doc discipline.** Decisions land in this document with their deduction; the
   constraint block is re-issued when this document changes; a summary that contradicts either
   has drifted.

## 10. What is NOT claimed

- Not a repo-scale proof, a quality score, or a ranking product — the controller plans; the
  driver decides; the gates prove.
- Not a claim that taste is eliminated — it is *located* (intent + AMBIGUOUS) and budgeted.
- Not a claim that the template library is complete, ever — the discrimination guarantee makes
  its gaps findable; completeness of a finite template family over open code is exactly the kind
  of claim the operator-completeness work forecloses, and it is not made.
- Not a performance guarantee — a budget read is a measurement with a stated instrument, not a
  promise about production wall-clock.
- Not autonomous: the fully-driverless form of this loop is Uroboros's territory and remains
  out of scope (a dumb relentless process cannot adjudicate AMBIGUOUS; the trilogy division
  stands).

## 11. Open Questions (flag, never guess)

1. **The transform-grammar μ question.** σ_form is grammar-relative; no canonical transform
   dictionary exists. Same shape as the tactic-policy question (THE_REFOUNDING §10.1) and the
   operator-basis question (NEG_SPEC Q4). The v1 dictionary (§3.1) is a choice, named as one.
2. **Regime = symmetry for code space.** Which symmetry governs the transform grammar over
   regions — when does one read eliminate a whole family. Unformalized (parallel to NEG_SPEC Q2).
3. **d on the code obligation graph.** Measure supermodular degree before trusting any greedy
   bound for censor/norm promotion (EXP-DS-005; `bridge_curvature_bound` supplies the bound
   *once d is measured*).
4. **The duplication read's key.** Idiomatic near-twin detection needs an equivalence key coarser
   than text and finer than behavior; candidate: normalized-AST shape × kill-profile overlap.
   Wants a derivation, not a heuristic.
5. **The composed-campaign representation.** Skeleton-and-holes for multi-move refactors —
   deferred to the tower's second order by design (§6), recorded so it is not rediscovered as a
   surprise when the one-shot tier saturates.
6. **The cross-language receipt.** Obligation replay across a subprocess/toolchain boundary;
   environment pinning; which obligations are language-portable. EXP-DS-006's question.

## 12. Build Order (each slice: Serena-probe the wiring → extract the pure decision → converge it in isolation → wire → intent tests → gate)

Waves, each landing with its paired experiment; a wave that cannot show its measurement does not
merge its claims into this document:

- **Wave 0 — the reads, consolidated (EXP-DS-001). SHIPPED + MEASURED (2026-08-31).**
  `ParsimonyLens` promoted to the five-tuple (depth · zero_state · path, additive/defaulted; the
  mined zeros are the already-recorded 527-function calibration MEDIANS — CC 3.0, DOF/line 1.29);
  `deviation_depth` is the one depth rule; the γ-seam bank built (`_gamma_seam_vote` +
  `gamma_seam_lens`, priced off the CHEAPEST candidate's crossing count, thresholds anchored to
  decompose's own ≤4-in/≤2-out gates); `purity_lens` — found defined-but-UNWIRED — wired into the
  fusion (verdict-invariant: its vote is structurally {0,+1}); `parsimony_map` deduplicated onto
  the shared builders, which also fixed a latent flaw (a failed seam scan used to vote +1 clean;
  it now abstains unmeasured). Pins: `deviation_depth`/`_gamma_seam_vote` carry hand-written
  truth-table pins (founder-authorized cheap-out — the module's suite surface made the isolated
  converge grind past its wall; the cut run's partial synth golden stands beside them) + the
  intent suite `tests/test_parsimony_five_tuple.py` (verdict invariance, five-tuple population,
  γ provenance). Gate: 1653 passed / 2 skipped; ruff clean under pinned 0.14.10; ty-clean on the
  touched modules. *Measured* (`dev/exp_ds_001_signature_audit.py`, Detective+Wesker corpus,
  1,119 functions): distinct static signatures **47 → 106** (set A 4 banks → set B 6 banks;
  spaces 81/729), largest cluster 294 → 265. Two honest reads: the surviving big clusters are
  dominated by small CLEAN functions — expected collisions (regions an expert treats the same
  SHOULD share a signature; discrimination is owed only to operationally-different pairs); and
  **γ-seam fires rarely** (mid-band 3–4 crossings dominates) — a calibration lead for a
  population-level, split-validated pass, deliberately NOT tuned from this one look (§4.2 law 3).
- **Wave 1 — the norms miner + the knee (EXP-DS-002). SHIPPED + MEASURED (2026-08-31).**
  `Detective/norms.py` holds the four pure decisions — `split_of` (hash-parity, seedless),
  `weighted_median` (κ-weighted, `None` on cannot-determine), `norm_disposition`
  (admissible/drifting/degenerate — a drifting norm is REJECTED, never tuned), and
  `verdict_isolation_cost` (the per-region read cost, with a brute-forced invariance property
  test). Pinned by hand-written truth tables under a **targeted, founder-granted exemption**
  (recorded in the test module's docstring: this repo's dense-package reachability makes an
  isolated converge trace the whole 1.6k-test suite — the exemption is scoped to these four
  functions and this idiom, NOT a precedent). The κ-weight consumes `kappa.build_call_graph`
  in-degree (weighting beats exclusion: dead code counts once and cannot drag, entry points
  still count); the overload raw is mined STATICALLY (DOF = the function's mutant-universe size
  off its own AST — the sandwich thesis's "one function's operators are static and free").
  *Measured* (`dev/exp_ds_002_norms_knee.py`, 1,123 functions, stated tolerance 0.25):
  **(a)** the CC re-mine was REFUSED by its own gate (halves 2.0/1.0 → drifting; relative
  tolerance is brittle on a low-median INTEGER distribution — methodological lead recorded;
  the 2026-08-06 calibration zero stands). **(b)** the overload mine VALIDATED (halves
  1.0/1.304, drift 0.233 — narrow margin, recorded) and `_OVERLOAD_ZERO` was adopted at the
  κ-weighted 1.1 with provenance. **(c)** the knee: every early decider (reads 2–5, 8.6%) is
  flagged-side — the flag-side bulk the transport predicts — while the clean majority's cost is
  DEGENERATE by construction (a clean verdict under the ≥2 floor cannot decide before read n−1;
  66.3% mass at read 6 of 7 is the floor's structural bound, not a tail). Go/no-go verdict:
  **not failed, partially informative** — the instrument must consume the interference verdict
  (CONSTRUCTIVE/DESTRUCTIVE/AMBIGUOUS/SILENT), not the binary flag, to measure the clean side;
  that refinement is a named deliverable of Wave 4's controller instrumentation.
- **Wave 2 — the budget bank (EXP-DS-003). SHIPPED + MEASURED (2026-08-31).** `Detective/budget.py`:
  `growth_class` (log-log tail-slope median → five named bands, boundaries stated; n·log n lands
  in "linear" at this instrument's width — stated, not hidden; degenerate input → "unmeasurable",
  never a fabricated class), `budget_verdict` (class dominates ratio; the parity band keeps "no
  payoff measured" a real outcome), `paired_disposition` (the two-ledger law as one pure decision
  — nonzero delta → "inadmissible" outranks every payoff), `ladder_value` (sized instances of the
  `--input`-expressible kinds only — a domain object has no mechanical ladder; consolidation with
  the synthesis stack's typed grids deferred, that stack builds single representatives today), and
  `count_opcodes` (the impure instrument shell). *Instrument findings, measured not assumed:*
  **(a)** on Python 3.14 the legacy `f_trace_opcodes` path silently delivers ZERO opcode events —
  the first harness run read 0 everywhere and the bank honestly refused to classify; the counter
  was rebuilt on `sys.monitoring` INSTRUCTION events (probed deterministic: 322 == 322, clean
  growth), with abstention on a missing API (3.11 floor), no free tool slot, or a crashed arm,
  and the slot always released. **(b)** The counter's stated boundary: Python-level instructions
  only — C-level work is invisible; reads compare arms, never Python versions. The allocation
  axis is deferred. *Measured* (`dev/exp_ds_003_budget_bank.py`, ladder 16..512): both seeded
  known optimizations **re-derived blind** — dedupe `quadratic_plus → linear` (refund, ratio
  0.0079 at the top; 977,315 → 7,757 instructions) and series `linear → constant` (refund),
  behavior-delta exactly 0 on every ladder input. *Pins:* `growth_class` carries an
  engine-written synth (banked before the batch stop); the other three carry truth-table pins
  under the SECOND targeted exemption (founder-granted; scope recorded in the test docstring).
  *The wave's standing process finding:* **in-repo pin batches are serial-cold by construction**
  — converge invalidates its own session baseline per writing pass (the `refresh_live_suite`
  seam, load-bearing), and each pin's synth invalidates the next pin's trace cache
  (tests-source-hash is in the key, correctly). Thrice-observed; budget for it, or grant the
  scoped exemption — do not tool around the cache keys, whose completeness is a soundness
  property.
- **Wave 3 — the template library v1 + per-template grammars (EXP-DS-004).** Five templates, each
  with its deterministic transform and its gate; the taste-as-recognition claim's direct test:
  template recognition vs an expert's judgment on a held-out corpus, and transform payoff under
  Wave 2's harness.
- **Wave 4 — the controller (EXP-DS-005).** Orientation tables + interference + the flow plan
  over `audit --plan` costs; the censor spine starts accumulating from gate rejections; measure d
  on the obligation graph. *Measurement:* plan quality vs `parsimony --plan`'s unpriced queue,
  and the first censor wave's budget refund at delta 0.
- **Wave 5 — warranted cross-language emission (EXP-DS-006).** The receipt replayed against a
  pinned-environment emission; the `rewrite-in-<lang>` arc opens only when this gate is green.
- **Throughout:** every extracted pure decision converged in isolation BEFORE wiring
  (converge-before-wiring is a standing feedback law); hand-written intent tests beside every
  synth suite; the full pre-commit gate.

## 13. Status Ledger

**Proved (machine-checked priors; cite, never re-derive).** σ = TD; γ + interface bound; the
adequacy ceiling and its Lean development; channel isolation's guards; `bridge_curvature_bound`
(audited); the canonical-form theorems (SC 2.3/3.11 via NEG_SPEC §15).

**Built (in this repo or the named siblings; the seams this layer grows from).** The seven
parsimony lenses + consensus + calibration; `parsimony --plan`; `audit --plan`; `decompose
--apply`; `receipt`/`verify-rewrite`; `censor`/`kappa`/`promotion_ledger`; `flag --fence`;
Peitho's otp/position/flow (pinned); Wayfinder's structural-reads/censor-store/lean_expr/
cheat-sheet stack (the porting precedents).

**Measured (elsewhere; mechanism evidence only — constants non-transferable).** The bank protocol
at production scale (Peitho); the negative channel paying in budget at delta exactly 0
(EXP-RF-005a/b); regime conversion (two domains); the residualization tower and its saturation;
the granularity failure; split-validated norm generalization.

**Asserted (this document's moves; each with its named test).** The fourth transport / σ_form
(EXP-DS-001/002); taste-as-recognition (EXP-DS-004); the budget bank suffices as the efficiency
observable (EXP-DS-003); the flow controller beats the unpriced queue (EXP-DS-005); the
cross-language receipt is buildable (EXP-DS-006).

**Measured (in-repo).** EXP-DS-001 (2026-08-31): static-signature distinctness 47 → 106 over
1,119 Detective+Wesker functions on adding γ-seam + purity to the bank space; γ-seam's rare-fire
band recorded as a calibration lead for Wave 1's split-validated norms pass. EXP-DS-002
(2026-08-31, 1,123 functions): the norms discipline exercised end-to-end — one re-mine REFUSED
by its own admissibility gate (CC, drifting on a low-median integer distribution), one
validated and adopted (`_OVERLOAD_ZERO` → κ-weighted 1.1); the knee instrument shows the
flag-side bulk (all early deciders flagged, 8.6% by read 5) and is degenerate on the clean side
by construction — the interference-verdict refinement is Wave 4's named deliverable.

**Build.** Waves 3–5 of §12 (Waves 0–2 shipped 2026-08-31). EXP-DS-003 added to the in-repo
measured ledger: both seeded optimizations re-derived blind at delta exactly 0; the 3.14
`f_trace_opcodes` silent-zero finding; the serial-cold pin-batch idiom. Nothing else in this
document is claimed shipped beyond the seams §1.2 names.

---

*The first half of Detective made "specified" a checkable property with a stated boundary. This
half makes "well-made" one: not a vibe, not a score — a signature, a priced plan, a gated move,
and a residual that names itself. The person stays where the theorems put them: at intent, and at
the verdicts the banks cannot resolve.*
