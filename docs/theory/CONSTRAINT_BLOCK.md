# Negative Specification — Constraint Block · carry VERBATIM into any summary or handoff

<!-- Structured to the ARC_AGI_3 compaction-drift spec: constraints WITH reasons;
resolved questions stated AS RESOLVED; the next action as ONE imperative; the
sources that can contradict this block named LAST — and they win. Written
2026-08-08 at design-complete / pre-build. -->

**Remove-X check this block must pass:** remove the conversation that produced it.
Can a fresh agent recover the constraints, the build order, the forbidden actions,
and pick the same next action? If not, this block is broken, not the reader.

---

## Constraints (each with the why that gives it mass)

1. **A negative constraint is evidence with a provenance, never an authored
   assumption** *(a censor that cannot be broken is not a specification, it is a
   bug with a veto — `NEGATIVE_SPECIFICATION.md` §0)*. It is derived from an
   **observed** near-miss and stays breakable by a witness, exactly as `flag` is.

2. **`UNVERIFIED` is never promoted to `forbidden` by assertion** *(mirrors the
   standing rule that `candidate-equivalent — UNPROVEN` is never promoted to
   `equivalent`; the whole tool's credibility is this one discipline)*. An
   LLM-authored constraint is an unverified assertion and **must not gate**.

3. **Negative results get their own reporting channel and are NEVER folded into
   the kill count** *(same reason crash kills are not — `ARCHITECTURE.md` §0
   value-specification vs run-specification; a censor is an exclusion with a
   different warrant, not a kill)*.

4. **Admissibility is two-part and both parts are required** *(§14: without the
   guard the central quantity is not merely unsafe, it is **undefined** —
   `L_ind → 1` vacuously)*: **(i)** spine-sourced, structurally incapable of
   confirmation from derived output; **(ii)** σ(P | C ∪ {c}) > 0.

5. **`I_ind` reads the population; the PROOF stays one function at a time**
   *(`ARCHITECTURE.md` §11 forbids the statistical smear and removed
   `diagnose --learn` for being one — co-occurrence over call sites is a
   different object, and that distinction is the entire license)*.

6. **Do NOT cite SSL's constants for code** — `L=0.528`, the ~3 % knee, the 28×
   drop *(measured on a DENSE graph; a code obligation graph is likely sparse —
   `SIGNIFICANCE_WEIGHTING.md` §13 says the structure transfers and the constants
   do not)*. Measure **d** first.

7. **External citations in this system are RECALLED, NOT VERIFIED** *(the manifest
   marks them `verified: false` on purpose; six are load-bearing)*. They gate
   publication, not the build. Do not quote them publicly unchecked.

8. **μ⁻ and censors are two mechanisms, not one** *(different provenance,
   different region of the completeness map, different repo — conflating them is
   how the epistemics get muddy)*. μ⁻ is an operator in Wesker. Censors are a
   governed artifact in Detective.

9. **The theory doc's claims are footed on hashed priors** *(a prior changing
   under a claim must fail loudly)*. Run
   `python docs/theory/check_reference_manifest.py` before trusting a citation.
   **Never re-hash to silence a DRIFT without re-reading what changed** — the hash
   is the claim's footing.

---

## Resolved questions — state them AS RESOLVED, never as open

- **The gap is in the homology, not the theory.** RESOLVED. `SSL_PAPER_SKELETON.md`
  §6.1's table is symmetric except that the semantic side runs both version-space
  operators and the program side runs one. Do not re-derive this; it is §1.

- **The Lean does not need rewriting.** RESOLVED. σ is μ-parameterized (SC §2.3),
  so the object is σ(P, μ ∪ μ⁻) — a second policy instantiation. Blum axioms,
  exponential separation, and the Five-Field Identification are stated over
  arbitrary μ and do not change.

- **"Negatives introduce a false-refusal failure mode the proof channel can't
  absorb" — ANSWERED, not open.** Over-censoring is the degenerate controller from
  the other side; the detectors are `self_confirming_cannot_certify` and
  `falsifiability_pivot`, already machine-checked, with SSL §4.4's
  retained-plurality budget as the quantified bound.

- **The boundary is MEASURED, not argued.** RESOLVED. A behaviour-changing
  structural rewrite (`or delim` dropped from `boltons::slugify`) passes a
  `✓ COMPLETE` contract. That is not a defect — the transformation is outside μ.
  It is the grounded demonstration that semantic negatives reach where syntax
  cannot. §2.4.

- **The "degenerate witness" objection is a category error.** RESOLVED and
  recorded because it recurs in every model review. Teaching dimension is defined
  by a teacher minimizing identification cost, not by sampling a natural
  distribution. The integer near-misses beat hand-written tests on plausible
  refactors and caught the str→bytes API break on a function with zero shipped
  tests. §2.5.

- **γ = d = bridge count.** RESOLVED as an identification (transported, not
  proved): composition gap ≡ supermodular degree ≡ bridge count. Detective #16 is
  therefore the code-side instance of §13's crux, and measuring interface
  obligations *is* measuring d. One quantity, not two.

- **`audit --remove` measures the wrong invariant.** RESOLVED as a diagnosis
  (#54): local kill+line redundancy is the bridge counterexample. The correct gate
  is κ-weighted coverage over the closure, from theorems already machine-checked
  upstream (SC Thm 2.3, Thm 3.11). Blocked on κ-for-code, not on analysis.

- **A prediction that was made and is WRONG — do not re-make it.** That censors
  would land in the **bulk** regime and produce a sharp knee, by analogy with
  SSL's measured constants. That imports the wrong regime. Censors span call
  sites, so in a sparse obligation graph a censor **is a bridge** — super-additive
  with positive tests, which is a stronger claim and a worse one for tractability.

---

## Still genuinely open (do not state these as resolved)

1. **κ for code.** GSE uses genealogy PageRank over IS-A. The code analogue needs
   a graph — call graph, import graph, or the obligation graph induced by interface
   mutants — and the choice decides whether `I_ind` is cheap or a research project.
   **Blocks censors AND κ-gated removal.**
2. **The regime key.** Keyed below the semantic-equivalence class a censor
   over-reaches (traps positions that merely rhyme, `law_as_architecture` §8);
   above it, under-reaches. Working guess: typed interface + purity class. Wants a
   derivation, not an intuition.
3. **Whether μ⁻ needs its own equivalence notion.** Two perturbations can be
   indistinguishable for the same reasons two mutants can. TCE-style bytecode
   identity (Wesker #24) does **not** apply — there is no mutant program to compile.
4. **Whether the certificate should name its context set** rather than only report
   a ratio (§7.2). Design question, not a blocker.

---

## THE NEXT ACTION — one imperative

> **Do not start this. Finish the correctness and retooling work in Detective and
> Wesker first** — the newest issue batch (Detective #57–#63, Wesker #15–#22) is a
> coherent evidence-provenance refactor, and Wesker #16 (`nodeid` as test identity)
> is a prerequisite for any per-case negative evidence to have somewhere to attach.

**When that work lands, the first build step is μ⁻**, because it is the only piece
that is unblocked: an operator over the codomain, reusing the existing kill matrix,
trace, and minimal-cover machinery, independent of κ and of the regime key.

**The experiment that decides the thesis** (design in `NEGATIVE_SPECIFICATION.md`
§8, runnable with instrumentation that already exists): converge a corpus of pure
functions under μ, then under μ ∪ μ⁻, and report **ΔL**, **ΔI_solve**, measured
**d**, and the out-of-universe recapture rate. The magnitude of ΔL and ΔI_solve
*is* the value of the negative half — measured, not argued.

---

## The sources that can contradict this block — and they WIN

Listed last on purpose. If this block disagrees with any of them, the block is
wrong.

| source | authority over |
|---|---|
| `docs/theory/NEGATIVE_SPECIFICATION.md` | the theory, the commitments, the status ledger |
| `docs/theory/GLOSSARY.md` | stage → commitment → reading map |
| `docs/theory/REFERENCE_MANIFEST.yaml` + `check_reference_manifest.py` | what the priors actually say, and whether they have drifted |
| `ARCHITECTURE.md` | **present behaviour of the tool**, and §11's one-function law |
| `docs/PARSIMONY_ADVISORY.md` | the advisory/proof separation this inherits |
| `ARC_AGI_3/docs/theory/` (hashed in the manifest) | every transported theorem; **cite, do not re-derive** |
| `ARC_AGI_3/docs/GLOSSARY.md` | the librarian form this system is modelled on |

**Nothing in this block is built.** It is design-complete and pre-build. A summary
that reports any of it as shipped has drifted.
