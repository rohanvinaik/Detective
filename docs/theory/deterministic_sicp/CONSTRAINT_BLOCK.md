# Deterministic SICP — Constraint Block · carry VERBATIM into any summary or handoff

<!-- The reconstruction cheat sheet the founder asked for: severe ADHD means the idea vanishes and
gets re-derived from scratch indefinitely unless this block holds. Constraints WITH reasons;
resolved questions stated AS RESOLVED; the next action as ONE imperative; the sources that can
contradict this block named LAST — and they win. Section references are to DETERMINISTIC_SICP.md
beside this file. -->

**Remove-X check this block must pass:** remove the conversation that produced it. Can a fresh
agent recover what this layer IS, the constraints, the build order, the forbidden moves, and pick
the same next action? If not, the block is broken, not the reader.

---

## What this IS (one breath)

The **second half of Detective** — not a new project (founder ruling, 2026-08-31). The first half
characterized what a suite can know about a function (adequacy ceiling, effect/meaning boundary,
per-function proof gates). This half makes the idiomatic remainder of SICP — efficiency,
parallelization, organization, duplication, language fit, "taste" — a **control problem over
formally measured axes**: Peitho-pattern banks off mined zeros → interference verdicts → a
budgeted min-cost-flow plan over arcs that exist **iff a Detective proof gate exists for the
move** → gated actuation. It is the fourth transport of the σ apparatus (programs → meaning →
proofs → **form**), extending NEG_SPEC §15's canonical form (σ+γ+I⁻) across the advisory axes.

## Constraints (each with the why that gives it mass)

1. **Part of Detective; same repo, same infrastructure** *(it runs on σ, γ, mutant profiles,
   parsimony, censor/kappa, the gates — "inherently linked… needed to complete the core project
   goals"; §1.1–1.2)*. Never scaffold it as a separate project. (That mistake was made once and
   reverted the same turn — a `Kybernetes` directory; do not repeat it.)

2. **The one-function proof law is untouched** *(sandwich thesis; ARCHITECTURE §11)*. The
   geometry is repo-scale ADVISORY under parsimony's existing license; every write passes a
   per-function gate. No repo-scale mutation profile exists or is needed.

3. **Advisory never writes; no gate, no arc** *(a controller that plans an unprovable move plans
   nothing; §5.2, §8)*. The transform dictionary is closed, and each entry names its proof gate
   before it may carry flow.

4. **Interference, never weighted sums; statistical components rank, never fence, never emit**
   *(two post-mortems + two production systems; elimination carries the soundness burden; §5.1,
   Law 3–4)*. AMBIGUOUS escalates to the driver — that is where taste lives, by the automation
   boundary (NEG_SPEC Thm 6.2), not a gap.

5. **Norms/censors: mined at population level, κ-weighted, SPLIT-VALIDATED, granularity-bounded**
   *(the self-normalizing-bad-repo problem is solved by discipline, not corpus choice — Wayfinder
   §10.7 + EXP-RF-005a; a fence mined at function granularity warrants nothing at module
   granularity — measured failure, Wayfinder §10 item 8; §4.2, §5.3)*. Never parameterize by the
   identity of the function that annoyed us.

6. **Efficiency = deterministic budgets, never wall-clock** *(determinism is the product)*:
   operation counts on synthesized inputs, the size-ladder asymptotic read off the existing
   synthesis stack, paired arms with behavior-delta gated to **exactly 0** by the proof suite;
   two-ledger rule (the gate owns validity; run quality gates only evidence). §7.

7. **Constants do not transport** *(every Peitho/Wayfinder/SSL number is mechanism-evidence
   only)*. Measure the knee, d, and every norm on code before trusting any bound.

8. **The intent residual stays human** *(MECHANICAL_LAYER Prop 3.3: meaning is not in the text)*.
   Which distinctions matter is authored — via AMBIGUOUS escalation and `flag --fence` — never
   computed.

9. **Decisions land in the paper WITH their deduction; this block is re-issued when it changes**
   *(the founder is a self-declared unreliable oracle; the doc is the stable ground; §0)*.

## Resolved — state AS RESOLVED, never as open

- **Home**: `docs/theory/deterministic_sicp/` inside Detective. NOT a new repo/tool.
- **The three blocking uncertainties are answered** (they stalled the design at first pass):
  (i) *norms corpus* → per-corpus mining + κ-weighting + out-of-sample split validation (the
  EXP-RF-005a protocol, measured); (ii) *efficiency observable* → deterministic budget accounting
  under the delta-0 paired constraint (measured shape, EXP-RF-005b); (iii) *actuator for
  expensive moves* → warranted emission with environment pin (the SourceExpr→LeanExpr precedent;
  Lean-checked was harder than Python-compiles and was crossed).
- **The split-vs-bloat interlock is priced, not judged**: the γ-seam bank (SC Thm 3.16) puts the
  interface cost of a candidate split in the arc cost; duplication competes for the same budget;
  genuine disagreement reads AMBIGUOUS and escalates.
- **The parallelization-reads-as-entanglement worry is a collapsed signature**, fixed by the
  discrimination guarantee (add the budget/template dimension), never by a threshold.
- **"Complexity is purely additive" is conditional on γ=0** (SC Thm 3.15) — quote the founder's
  intuition, cite the theorem, never cite the informal form as the theorem.
- **The expert's skillset is claimed as regime conversion** (template recognition, Regime A, +
  deterministic per-template grammars) — ASSERTED with a named test (EXP-DS-004), precedented in
  two measured domains.
- **Existing seams are the implementation base** (all BUILT): parsimony lenses + `--plan`,
  `audit --plan` (arc costs), `decompose --apply`, `receipt`/`verify-rewrite`, `censor`/`kappa`/
  `promotion_ledger`, `flag --fence`, Peitho `otp`/`position`/`flow`, converge's input synthesis
  (feeds the size-ladder read).

## Still genuinely open (do not state as resolved)

1. The transform-grammar μ question — σ_form is grammar-relative; the v1 dictionary is a named
   choice. §11 Q1.
2. Regime = symmetry for code space. §11 Q2.
3. d on the code obligation graph — measure before any greedy bound is trusted. §11 Q3.
4. The duplication key (normalized-AST shape × kill-profile overlap is a candidate, not a
   derivation). §11 Q4.
5. Composed campaigns (skeleton-and-holes) — deferred to the tower's second order BY DESIGN; the
   one-shot tier WILL saturate (measured elsewhere); do not chase the composed band with more
   single-move grammar. §11 Q5.
6. The cross-language receipt (obligation portability, environment pinning). §11 Q6.

## THE NEXT ACTION — one imperative

> **Build Wave 4 (EXP-DS-005): the controller — orientation tables + interference over the
> banks, the flow plan priced by `audit --plan`, the censor spine accumulating from gate
> rejections, and d measured on the obligation graph. Include the interference-verdict knee
> instrument (the Wave-1 clean-side refinement, owed to this wave).** Waves 0–3 SHIPPED +
> MEASURED 2026-08-31: signatures 47 → 106; the norms discipline exercised (one re-mine
> refused by its own gate; `_OVERLOAD_ZERO` κ-weighted 1.1); the budget bank re-derived seeded
> optimizations blind at delta exactly 0; the template library 5/5 end-to-end with the
> discharge property. Standing facts: in-repo pin batches are serial-cold by construction (two
> scoped truth-table exemptions granted; each future one needs its own grant); the budget
> counter lives on `sys.monitoring` (3.14 legacy path silently dead) and ABSTAINS below 3.12;
> **recognizable ≠ priceable** — `in <list>` quadratic work is C-invisible to the v1
> instruction axis (measured), the C-call axis is instrument v2, and bank disagreement is
> itself signal.

**Then, in order:** Wave 2 (budget bank + delta-0 paired harness) → Wave 3 (template library v1 —
the taste-as-recognition test) → Wave 4 (controller: orientation + interference + flow over
`audit --plan` costs; start the censor spine; measure d) → Wave 5 (warranted cross-language
emission; the `rewrite-in-<lang>` arc opens only when green). Every extracted pure decision is
converged **in isolation before wiring** (standing feedback law), with hand-written intent tests
beside every synth suite.

## The sources that can contradict this block — and they WIN

| source | authority over |
|---|---|
| `DETERMINISTIC_SICP.md` (beside this file) | the design, the laws, the ledger, the deductions |
| `../NEGATIVE_SPECIFICATION.md` | σ±, censors/κ/curvature, §15 canonical form, the automation boundary |
| `../operator_completeness/` (+ its Lean proofs) | the adequacy ceiling, the intent residual |
| `../mechanical_layer/MECHANICAL_LAYER.md` | effect/meaning, the coupling boundary |
| `../../../ARCHITECTURE.md` | present behavior of Detective, §11's one-function law |
| `../../PARSIMONY_ADVISORY.md` | the advisory/proof separation and the bank protocol |
| `~/Projects/Peitho` (DESIGN/ARCHITECTURE + pinned source) | the estimator/controller hardware |
| `~/Projects/Wayfinder/docs/Research_Paper/THE_REFOUNDING.md` + `THE_DETERMINISTIC_CORE.md` | the transport license, the loop disciplines, the measured failures |

**Nothing in this layer is built beyond the seams named as existing.** A summary that reports any
wave as shipped has drifted.
