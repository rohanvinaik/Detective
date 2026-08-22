# Negative Specification — Constraint Block · carry VERBATIM into any summary or handoff

<!-- Constraints WITH reasons; resolved questions stated AS RESOLVED; the next action as ONE
imperative; the sources that can contradict this block named LAST — and they win. Section references
are to docs/theory/NEGATIVE_SPECIFICATION.md (formal spec, restructured 2026-08-22). -->

**Remove-X check this block must pass:** remove the conversation that produced it. Can a fresh agent
recover the constraints, the build order, the forbidden actions, and pick the same next action? If not,
the block is broken, not the reader.

---

## Constraints (each with the why that gives it mass)

1. **A negative constraint is evidence with a provenance, never an authored assumption** *(a censor that
   cannot be broken is not a specification; §9, Def. 9.3/9.5)*. Derived from an **observed** near-miss,
   breakable by a witness, exactly as `flag` is.

2. **`UNVERIFIED` is never promoted to `forbidden` by assertion** *(mirrors `candidate-equivalent —
   UNPROVEN` never promoted to `equivalent`; §9, Def. 9.5)*. An LLM- or a-priori-authored constraint is
   an unverified assertion and **must not gate**.

3. **Negative results get their own reporting channel and are NEVER folded into the kill count** *(same
   reason crash kills are not — `ARCHITECTURE.md` §0 value-vs-run; a censor is an exclusion with a
   different warrant, §9 Def. 9.5)*.

4. **Admissibility is two-part and both parts are required** *(SIGNIFICANCE_WEIGHTING §14: without the
   guard the central quantity is **undefined**, L_ind → 1 vacuously; here §9 Prop. 9.4)*: **(i)**
   spine-sourced, structurally incapable of confirmation from derived output; **(ii)** σ(P | C ∪ {c}) > 0.

5. **I_ind reads the population; the PROOF stays one function at a time** *(`ARCHITECTURE.md` §11 forbids
   the statistical smear — co-occurrence over call sites is a different object; §9 Rmk 9.2)*.

6. **The UNDEFINED disposition is not `unconstrained` and not `COMPLETE`** *(a degenerate negative
   measure is a measurement limit, excluded from the scored set, sibling to `cut`; §7 Def. 7.3)*.
   Coercing it either way is how a negative-space intent error slips or a false badge is minted.

7. **Do NOT cite SSL's constants for code** — L=0.528, ~3% knee, 28× drop *(measured on a DENSE graph;
   a code obligation graph is likely sparse — SIGNIFICANCE_WEIGHTING §13)*. Measure **d** first.

8. **External citations are RECALLED, NOT VERIFIED** *(the manifest marks them `verified: false`; six are
   load-bearing)*. They gate publication, not the build.

9. **μ⁻ and censors are two mechanisms, not one** *(different provenance, region, and repo; §3 vs §9)*.
   μ⁻ is an operator in Wesker; censors are a governed artifact in Detective.

10. **`provably correct` is unqualified only on the finite-domain / decidable class** *(§8: off it,
    Rice/Budd–Angluin make the qualifier mandatory; the certificate names its side)*.

11. **The theory doc's claims are footed on hashed priors** *(a prior changing under a claim must fail
    loudly)*. Run `check_reference_manifest.py`; **never re-hash to silence a DRIFT without re-reading
    what changed.**

---

## Resolved — state AS RESOLVED, never as open

- **The gap is in the homology, not the theory.** SSL §6.1's table is symmetric except the semantic side
  runs both version-space operators and the program side runs one. §2.

- **The Lean does not need rewriting.** σ is μ-parameterized (SC §2.3), so the object is σ(P, μ ∪ μ⁻),
  a second policy instantiation; Blum axioms, exponential separation, five-field ID hold over arbitrary
  μ. §2 (Prop. 2.5).

- **"Negatives introduce a false-refusal mode the proof channel can't absorb" — ANSWERED.**
  Over-censoring is the degenerate controller from the other side; detectors `self_confirming_cannot_certify`
  / `falsifiability_pivot` are machine-checked, with SSL §4.4's retained-plurality budget. §9 (Prop. 9.4).

- **The boundary is MEASURED.** A behaviour-changing rewrite (`or delim` dropped from `boltons::slugify`)
  passes a positive `SC=1` contract — outside μ, not a defect: semantic negatives reach where syntax
  cannot. §3 (Prop. 3.5).

- **The "degenerate witness" objection is a category error.** Teaching dimension is defined by a teacher
  minimizing identification cost, not by sampling a natural distribution; the near-misses beat
  hand-written tests and caught the str→bytes break. §14 (Measured); Appendix C2.

- **γ = d = bridge count.** An identification (transported): composition gap ≡ supermodular degree ≡
  bridge count. Detective #16 is the code-side instance; measuring interface obligations *is* measuring
  d. §10 (Prop. 10.3).

- **`audit --remove` measures the wrong invariant (#54).** Local kill+line redundancy is the bridge
  counterexample; correct gate is κ-weighted coverage over the closure (SC Thm 2.3, 3.11). Blocked on
  κ-for-code. §10 (Cor. 10.6).

- **A prediction that was WRONG — do not re-make it.** That censors land in the **bulk** regime with a
  sharp knee, by analogy with SSL's constants. Censors span call sites, so in a sparse graph a censor
  **is a bridge** — super-additive, a stronger and worse-for-tractability claim. §10 (Conj. 10.4).

- **μ⁻ operationally grounded (2026-08-22).** [traced] μ⁻ splits into **Form A** (return-wrap AST
  mutator, reuses `evaluate_mutant`/`check_equivalent`/score/cover; new `MutationCategory.OUTPUT`,
  bespoke generator/recorder on the STATE/EXCEPTION/DATAFLOW precedent) and **Form B** (runtime wrapper,
  non-return codomain, bespoke per sibling type, load-bearing for completeness). The UNDEFINED
  disposition is a `cut`-sibling excluded from `SCORED_DISPOSITIONS`. §11.

- **μ⁻ needs no separate equivalence notion — for Form A.** A return-wrap perturbation is a compilable
  mutant, so `check_equivalent` generalizes free. §11 (Prop. 11.5). (Open for Form B.)

- **The perturbation family Π is a type-indexed set; the independence pair is the core.** →constant and
  →identity fence input-dependence and non-triviality — caught by no positive operator. §11.8.

---

## Still genuinely open (do not state as resolved)

1. **κ for code.** The graph choice (call / import / obligation-induced) decides whether I_ind is cheap
   or a research project. **Blocks censors AND κ-gated removal.** §13 Q1.
2. **The regime key.** Below the semantic-equivalence class a censor over-reaches; above it,
   under-reaches. Working guess: typed interface + purity class. Wants a derivation. §13 Q2.
3. **μ⁻ equivalence for Form B.** No mutant program to compile, so TCE bytecode identity (Wesker #24)
   does not apply; a negative mirror of `candidate-equivalent — UNPROVEN` may be needed per sibling type.
   §13 Q3.
4. **Completeness of Π.** How much codomain a finite Πᵣ fences; measurable only with Fork 2's observed
   type. §13 Q4.
5. **The bounded-curvature bound.** Measure d on the obligation graph; prove greedy degrading in d. §13 Q5.

---

## THE NEXT ACTION — one imperative

> **Build μ⁻ Form A + Fork 1 as the walking skeleton.** It is unblocked, κ-free, and grounded against
> the live engine (§11): a return-site AST mutator under a new `MutationCategory.OUTPUT`, generated by a
> bespoke `_generate_output_perturbations` and recorded by `_record_output_dimensions` (template:
> `_generate_exception_mutants`, `_DataflowMutator.return_sub`), typed statically from the AST (Fork 1),
> with mis-typed perturbations routed to the `undefined` disposition. The seed Π is the independence pair
> (→constant, →identity) plus §11.8's universal and type-conditional members.

**Then, in order:** Form A + Fork 2 (baseline return-capture → observed-type Π), then Form B (per sibling
type), then censors (blocked on κ, Q1–Q2).

**The experiment that decides the thesis** (Appendix C3, runnable now): converge a corpus of pure
functions under μ, then under μ ∪ μ⁻, and report ΔI_solve (the `--input`/killable residual reduction),
measured d, and the out-of-universe recapture rate. The magnitude of ΔI_solve *is* the value of the
negative half.

---

## The sources that can contradict this block — and they WIN

Listed last on purpose. If this block disagrees with any of them, the block is wrong.

| source | authority over |
|---|---|
| `docs/theory/NEGATIVE_SPECIFICATION.md` | the theory, the numbered results, the status ledger |
| `docs/theory/GLOSSARY.md` | the stage → commitment → section map |
| `docs/theory/REFERENCE_MANIFEST.yaml` + `check_reference_manifest.py` | what the priors say, and whether they drifted |
| `Wesker/engine.py` | the live engine facts marked [traced] |
| `ARCHITECTURE.md` | present behaviour of the tool, and §11's one-function law |
| `docs/PARSIMONY_ADVISORY.md` | the advisory/proof separation this inherits |
| `ARC_AGI_3/docs/theory/` (hashed in the manifest) | every transported theorem; cite, do not re-derive |

**Nothing in this block is built.** The theory is formalized and μ⁻ Form A is grounded against the
engine; no μ⁻ code is written. A summary that reports any of it as shipped has drifted.
