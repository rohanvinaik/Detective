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

10. **Style after behavior, STRICTLY** *(founder ruling 2026-09-05: two layers, and the second
    runs only over ground the first secured — a refactor for form can break a guarantee only
    where none exists; §14.1)*. Every region carries a behavior status — SIX codes, spelled once
    in `pins.BEHAVIOR_STATUSES`: pinned · pinned_incomplete · refused · pinned_stale ·
    pinned_unverified · unpinned — read PRIMARILY off the converge certificate ledger
    (`tests/detective/certificates.json`, written by the `converge()` wrapper on every run, slice 1b)
    and refined by the generated suite (an edit or an older suite digest outranks any
    certificate). A style move is admissible only on `pinned`; for anything else the next command
    is `converge`, never `decompose --apply`. No pin, no gate armed. A current-digest suite with no
    certificate is `pinned_unverified`, NOT pinned: a suite is evidence tests were written, a
    certificate is evidence of what they pin.

11. **The taste surface is DERIVED, not bolted on** *(the CLI is a communication surface — the
    intent half of the work is done THROUGH it, so it is half the computation; §14)*. Four
    demands: four-valued advisory verdict never a score (clean KEPT and DEFINED: SILENT ∧ all
    lenses measured — unread is never clean) · every finding carries warrant + residual · the
    AMBIGUOUS list is the typed human channel · the unexamined is named, never implied approved.
    One entry verb `plan` (tree or `file::fn`), co-equal with `diagnose`; `parsimony` deprecated
    as a VERB (module stays — it is the bank, not a line counter); `verify-rewrite --budget`;
    `flag --style` writing a SEPARATE ledger the behavior layer never reads; exit 0/2/3 only,
    never 1; the MCP gets the same verb.

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
- **The wave library has ZERO production consumers** (grounded 2026-09-05, reference graph):
  `controller`/`templates`/`budget`/`norms`/`emission` are reached only from `dev/exp_ds_*` and
  the intent tests. The README's "66 flagged / 5 funded / 7 deferred / 54 no recipe" is an
  experiment's output until `plan` ships — flagged, not hidden.
- **The certificate is the converge verdict ledger, not the suite and not the receipt** (founder
  ruling 2026-09-05, after the real run showed ✓ COMPLETE functions with zero synth reading
  `unpinned`): `certificates.record_certificate` records `ConvergeResult.standing` verbatim per
  (func_key, function digest); regenerable, purge deletes it; deterministic bytes. §14.1 slice 1b.
- **The surface decisions are SETTLED** (2026-09-05; §14): new verb `plan`, not a grown
  `parsimony --plan` · "clean" kept and defined · judgment ledger via `flag --style` with strict
  file/reader separation · exit 3 for an unmeasurable paired budget read · advisory never exits 1
  · emission is vocabulary, not a verb, this pass.

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

> **The §12 wave program is COMPLETE (Waves 0–5 shipped + measured, 2026-08-31).** Next: pick
> from the post-wave frontier (paper §13 Build, priority order) — instrument-v2 C-call axis ·
> template-library growth from the 54 `no_template` regions (population-level, split-validated)
> · `audit --plan` live arc costs · codec v2 · the censor spine's first accumulation ·
> the composed-campaign band · controller CLI integration (a design task under the
> CLI-redesign discipline). Wave-5 landing: the cross-language gate 3/3 end-to-end through the
> REAL receipt (faithful PRESERVED under the recorded pin; a genuinely non-equivalent mutant
> CHANGED with its distinguishing input; broken INVALID_MEASUREMENT); **Q6's v1 answer: the
> portability boundary IS the L boundary** minus numeric-model edges; VACUOUS is a first-class
> verdict (an empty observing set never reads preserved); the first adversarial arm was itself
> an EQUIVALENT mutant — the live demonstration, recorded. Pin upgrades: `controller_verdict`
> engine-proved ✓ COMPLETE 37/37 over the hand-written truth tables (zero new synths);
> `split_of` + `weighted_median` engine synths banked. Standing facts unchanged (serial-cold
> batches · sys.monitoring counter · recognizable ≠ priceable · opposition requires a warrant).

> **SUPERSEDED 2026-09-05 — the next action is now the §14 surface, in slice order** (slices
> 1, 1b, 2, 3, 4, 5, 6, 7, 8 SHIPPED 2026-09-05 — `1e201f0`, `f32b8ac`, `f0daf18`, `b5ad349`,
> `3081510`, `18b1513`, `c6cb215`, `0c65e37`, `55f2003`; slice 9 DRAFTED in `README.draft.md`
> only — `README.md` untouched, the founder promotes. The §14 surface is BUILT end to end; what
> remains open on it is (a) the founder's GRANT of the hand-table pin exemptions listed below,
> (b) the two widen-grind defects, (c) the surfaced-not-built seam-driven `extract` template).
> **The slice 4–5 grind — DIAGNOSED AND FIXED 2026-09-05 (§14.9 item 4's note).** Root cause
> was NOT the deadline in the widen loop (it fires; measured twice) but (a) the witness pass's
> capture harvest running every collected test with no wall check, and (b) the widen's eligible
> set being every test without a static path — discovery inverted into a whole-suite trace.
> Founder ruling: discovery is an efficiency device for ONE function's applicable tests, never a
> proof of a negative; `file_peer` dropped; no opt-in. Fixed in Detective: `widen_admission` (only
> `caller_reaches` is widened; the rest disclosed as `not_consulted`), `_route_tests` (one router),
> `_applicable_harvest_pool` + `harvest_disposition` (the wall as backstop between tests).
> **The exemption REQUEST is withdrawn — every §14 hand-table decision is now converge-pinned**
> (2026-09-06, `--deadline 300`, all ✓ COMPLETE): `next_command` 40/40 modulo 2 (26 s; was 51 min,
> killed) · `receipt_path` 22/23 modulo 1 (154 s; was 54 min, killed) · `unexamined` 5/5 (21 s) ·
> `plan_exit` 7/7 · `next_move` 27/27 · `plan_closing` 25/25 · `judgment_standing` 20/20 ·
> `style_flag_refusal` 11/11 · `ladder_kinds` 12/14 modulo 2 · `budget_exit` 15/15 ·
> `widen_admission` 5/5 · `harvest_disposition` 3/3 — each 5–17 s. The hand tables stay as the
> intent tests beside the engine synths. Never run two converges concurrently; never run a
> converge alongside a pytest gate. Wesker follow-ups DONE (Wesker `25f1b96`): the widen persists
> its trace-cache cells once per widen (`PendingPersist` · `expand(persist=False)` · `flush()`), and
> every soundness docstring now reads "the driver's applicable set", not "the unknown set". The
> uv.lock Wesker pin still points at `981e8b2`; bump it after the Wesker push (the push sequence:
> Wesker → `uv lock --upgrade-package wesker` → Detective).
> (1) `behavior_status` pure decision + reader (ground whether the suite header carries the
> function digest) → (1b) the converge certificate ledger → (2) `plan_moves` gains `unpinned`;
> `RegionRead` gains status + cost provenance → (3) plan assembly as a library function (from
> `exp_ds_005.main`) → (4) renderers
> terse/full/JSON + `.detective/reports/plan_*` + the unexamined line + clean defined → (5) the
> `plan` verb, help pedagogy, regime stage, `parsimony` deprecation shim → (6) `flag --style` +
> `judgments.json` + the reopen rule → (7) `verify-rewrite --budget`, exit 3 on unmeasurable →
> (8) MCP `_render_plan` → (9) the README line becomes a transcript.

Every extracted pure decision is converged **in isolation before wiring** (standing feedback law),
with hand-written intent tests beside every synth suite. The waves paragraph that stood here is
history: Waves 0–5 shipped 2026-08-31.

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

**Waves 0–5 are built as LIBRARY code with intent tests and dev experiments; the §14 surface is
NOT built.** A summary that reports `detective plan`, `flag --style`, or `verify-rewrite --budget`
as shipped has drifted. A summary that reports the waves as unbuilt has drifted the other way.
