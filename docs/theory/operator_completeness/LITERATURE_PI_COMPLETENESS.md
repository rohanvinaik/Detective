# Literature — the Π-completeness decidability boundary and the PAC-vs-exact boundary

*Source-verified reference set for the operator-completeness work (the standalone paper
`OPERATOR_COMPLETENESS.md` and §18 Q4 of `NEGATIVE_SPECIFICATION.md`). Every entry below was
independently fetch-verified — title, authors, year, and that the source states the attributed claim —
by a 53-agent verification workflow (2026-08-25): 43 candidates swept, 42 unique, **42/42 verified**, 0
hallucinated citations passed. Confidence and any verbatim-fetch caveat are recorded per entry. This file
is a bibliography, not a claim ledger; the claims it supports carry their own status in the papers.*

## The load-bearing finding

An adversarial gap-critic (an agent tasked to *find* a mutation-testing completeness theorem and fail)
returned **`completeness_theorem_exists: false`**, and — the sharp part — the gap is **structural, not
merely unproven**:

> There is no theorem proving a finite mutation-operator set captures the full fault/behavioral space.
> The field's completeness rests on the **coupling-effect HYPOTHESIS** (DeMillo–Lipton–Sayward 1978),
> never proven. The strongest results are **basis-/test-set-relative** (Offutt 1996 empirical; Ammann–
> Delamaro–Offutt 2014 minimal sets relative to a fixed pool + test set). And an *absolute* theorem is
> **foreclosed**: program equivalence is undecidable (Rice 1953; Budd–Angluin 1982) and *true* mutant
> subsumption is undecidable (Kurtz–Ammann–Offutt 2015) — so the ordering a completeness theorem would
> rank against cannot be computed.

*Evidence caveat (recorded by the critic):* the fresh-WebSearch budget was exhausted before new
adversarial queries; the verdict rests on the 42-source corpus + the structural foreclosure (which is
airtight independent of search). So *"no absolute theorem can exist"* is proven; *"no basis-relative
decidability-dichotomy framing has been published"* is strongly-supported but warrants a targeted
ISSTA/ICSE/TSE novelty check before submission.

---

## A. Mutation-testing completeness / sufficiency / subsumption

| Source | Establishes | URL |
|---|---|---|
| DeMillo, Lipton & Sayward 1978, *Hints on Test Data Selection* (Computer 11(4):34–41) | Origin of the **competent-programmer hypothesis** and **coupling effect** — stated as motivating ASSUMPTIONS, never proven; no operator-completeness theorem. | https://doi.org/10.1109/C-M.1978.218136 |
| Offutt, Lee, Rothermel, Untch & Zapf 1996, *An Experimental Determination of Sufficient Mutant Operators* (ACM TOSEM) | A small **sufficient** subset of Mothra operators — an **experimental** determination relative to the full set, not a completeness proof. | https://dl.acm.org/doi/10.1145/227607.227610 |
| Ammann, Delamaro & Offutt 2014, *Establishing Theoretical Minimal Sets of Mutants* (ICST, pp. 21–30) | Dynamic mutant subsumption + **minimal (dominator) sets** — defined RELATIVE to a fixed test set and mutant pool; reduces redundancy within a pool, not a fault-space claim. The most "theorem-like" prior result. | https://doi.org/10.1109/ICST.2014.13 |
| Kurtz, Ammann & Offutt 2015, *Static Analysis of Mutant Subsumption* (ICST Workshops) | **True (semantic) subsumption is UNDECIDABLE**; only the dynamic (test-set-relative) approximation is computable. The negative result that obstructs any absolute completeness theorem. | https://doi.org/10.1109/ICSTW.2015.7107454 |
| Niedermayr, Juergens & Wagner 2016, *Will My Tests Tell Me If I Break This Code?* | **Extreme mutation** / pseudo-tested methods as a coverage-validity heuristic — no completeness claim. | https://arxiv.org/abs/1611.07163 |
| Vera-Pérez, Danglot, Monperrus & Baudry 2018, *A Comprehensive Study of Pseudo-tested Methods* | Empirical study (Descartes/PITest); calls for targeted generation, does not claim extreme operators span the fault space. | https://arxiv.org/abs/1807.05030 |

## B. Transformation-monoid generation (the finite-codomain algebra)

| Source | Establishes | URL |
|---|---|---|
| Gomes & Howie 1987, *On the ranks of certain finite semigroups of transformations* (Math. Proc. Camb. Phil. Soc. 101(3):395–403) | **rank(T_n) = 3** (full transformation monoid), rank(Sing_n) = idempotent rank = n(n−1)/2 for n≥3, **rank(S_n) = 2**. The exact finite-codomain completeness basis. | https://www.cambridge.org/core/product/identifier/S0305004100066780/type/journal_article |
| Kozen 1977, *Lower Bounds for Natural Proof Systems* (FOCS, pp. 254–266) | Transformation-monoid generability / finite-automata intersection non-emptiness is **PSPACE-complete** — the finite question is DECIDABLE but hard. | https://dblp.org/rec/conf/focs/Kozen77.html |
| *Symmetric group* — Wikipedia | Corroborates rank(S_n)=2 (n-cycle + adjacent transposition). *Does not* mention T_n rank-3 (partial support only). | https://en.wikipedia.org/wiki/Symmetric_group |

## C. Undecidability walls (why the finite results do not transfer to program space)

| Source | Establishes | URL |
|---|---|---|
| Post 1947, *Recursive Unsolvability of a Problem of Thue* (JSL 12:1) | The **word problem** for finitely-presented semigroups (Thue systems) is recursively **unsolvable**. Independently by **Markov**, same year (joint attribution confirmed). | https://www.cambridge.org/core/product/identifier/S0022481200076295/type/journal_article |
| *Word problem (mathematics)* — Wikipedia | Confirms the joint Post/Markov 1947 attribution verbatim. | https://en.wikipedia.org/wiki/Word_problem_(mathematics) |
| Rice 1953, *Classes of Recursively Enumerable Sets and Their Decision Problems* (Trans. AMS 74(2):358–366) | Every non-trivial semantic property of partial recursive functions is **undecidable** ⇒ program equivalence undecidable. | https://www.ams.org/tran/1953-074-02/S0002-9947-1953-0053041-6/ |
| Budd & Angluin 1982, *Two notions of correctness and their relation to testing* (Acta Informatica 18) | The canonical application: **equivalent-mutant / program-equivalence undecidability** in testing. | https://doi.org/10.1007/BF00625279 |
| Luckham, Park & Paterson 1970, *On Formalised Computer Programs* (JCSS 4(3):220–249) | Program-**schema** equivalence has a genuine **decidable/undecidable boundary** — the template for a decidability dichotomy. | https://doi.org/10.1016/S0022-0000(70)80022-8 |
| Papadakis, Jia, Harman & Le Traon 2015, *Trivial Compiler Equivalence* (ICSE) | TCE soundly detects a **portion** (not all) of equivalent/duplicate mutants — the decidable-fragment sidestep. | https://doi.org/10.1109/ICSE.2015.103 |
| Kintis, Papadakis, Jia, Malevris, Le Traon & Harman 2018, *Detecting Trivial Mutant Equivalences via Compiler Optimisations* (IEEE TSE) | Compiler-optimisation equivalence detection (C, Java) — sound but partial. | https://doi.org/10.1109/TSE.2017.2684805 |
| Godlin & Strichman 2013, *Regression verification* (STVR 23(3):241–258) | Sidesteps undecidable equivalence for *similar* programs via uninterpreted-function abstraction — sound-but-incomplete. | https://onlinelibrary.wiley.com/doi/10.1002/stvr.1472 |

## D. Teaching dimension / exact learning (the σ = TD scaffolding)

| Source | Establishes | URL |
|---|---|---|
| Goldman & Kearns 1995, *On the Complexity of Teaching* (JCSS 50(1):20–31) | **Teaching dimension** = smallest teaching set uniquely identifying each concept. | https://doi.org/10.1006/jcss.1995.1003 |
| Goldman & Mathias 1996, *Teaching a Smarter Learner* (JCSS 52(2):255–267) | **Collusion-freeness** — the correctness criterion any TD variant must satisfy. | https://doi.org/10.1006/jcss.1996.0020 |
| Hegedüs 1995, *Generalized Teaching Dimensions and the Query Complexity of Learning* (COLT) | Generalized TD **characterizes exact-learning query complexity** (up to a log factor). | https://dblp.org/rec/conf/colt/Hegedus95.html |
| Hellerstein, Pillaipakkamnatt, Raghavan & Wilkins 1996, *How Many Queries Are Needed to Learn?* (JACM 43(5):840–862) | Poly-query exact learnability ⇔ poly-size **certificates**. | https://doi.org/10.1145/234752.234755 |
| Zilles, Lange, Holte & Zinkevich 2011, *Models of Cooperative Teaching and Learning* (JMLR 12) | **RTD** (recursive teaching dimension) + subset TD; both can be ≪ classic TD without coding tricks. | https://www.jmlr.org/papers/v12/zilles11a.html |
| Kirkpatrick, Simon & Zilles 2019, *Optimal Collusion-Free Teaching* (COLT, PMLR v98) | **NCTD(C) ≤ M-TD(C)** for any collusion-free model M — NCTD is the sharpest collusion-free teaching parameter. | https://proceedings.mlr.press/v98/kirkpatrick19a.html |
| Devulapalli & Hanneke 2024, *The Dimension of Self-Directed Learning* (ALT, PMLR v237) | **SDdim** exactly characterizes the self-directed-learning mistake bound. | https://proceedings.mlr.press/v237/devulapalli24a.html |

## E. PAC-vs-exact / sample compression (the minimal-basis foreclosure)

| Source | Establishes | URL |
|---|---|---|
| Doliwa, Fan, Simon & Zilles 2014, *Recursive Teaching Dimension, VC-Dimension and Sample Compression* (JMLR 15) | **RTD ≤ VCD** for VCD-1 / intersection-closed / finite-maximum classes; and **repetition-free teaching plan ⇔ unlabeled sample compression** for maximum classes — the bridge making minimal-witness = compression. | https://www.jmlr.org/papers/v15/doliwa14a.html |
| Chen, Cheng & Tang 2016, *On the Recursive Teaching Dimension of VC Classes* (NeurIPS) | First VCD-only bound: **RTD(C) ≤ d·2^{d+1}**. | https://proceedings.neurips.cc/paper/2016/hash/69a5b5995110b36a9a347898d97a610e-Abstract.html |
| Hu, Wu, Li & Wang 2017, *Quadratic Upper Bound for RTD of Finite VC Classes* | Improves to **RTD(C) = O(d²)** for finite classes. | https://arxiv.org/abs/1702.05677 |
| Liu & Li 2026, *The No-Clash Teaching Dimension is Bounded by VC Dimension* | **WITHDRAWN** (v4, 3 Aug 2026, "The proof of Lemma 2 is wrong") — so **NCTD ≤ VCD remains OPEN**. | https://arxiv.org/abs/2603.23561 |
| Moran & Yehudayoff 2015/16, *Sample compression schemes for VC classes* (JACM) | Every binary VC-d class admits compression, but of size **EXPONENTIAL in d**; the linear conjecture is **open**. | https://arxiv.org/abs/1503.06960 |
| Pabbaraju 2023, *Multiclass Learnability Does Not Imply Sample Compression* (ALT 2024) | **Multiclass learnability ⇏ compression** — no scheme bounded by any function of DS-dimension. FORECLOSES a dimension-bounded minimal basis in the non-binary regime. | https://arxiv.org/abs/2308.06424 |
| Hanneke, Moran & Waknine 2024, *List Sample Compression and Uniform Convergence* (COLT) | **List compression FAILS** while uniform convergence stays equivalent to learnability. | https://arxiv.org/abs/2403.10889 |

## F. Grammar coverage / syntactic-completeness (the decidable-but-not-sufficient side)

| Source | Establishes | URL |
|---|---|---|
| Purdom 1972, *A sentence generator for testing parsers* (BIT 12:366–375) | The canonical decidable/finite **production-coverage** criterion (every CFG production ≥ once). | https://doi.org/10.1007/BF01932308 |
| Lämmel & Schulte 2006, *Controllable Combinatorial Coverage in Grammar-Based Testing* (TestCom, LNCS 3964) | Tunable combinatorial grammar coverage above basic production coverage. | https://doi.org/10.1007/11754008_2 |
| Havrikov & Zeller 2019, *Systematically Covering Input Structure* (ASE) | **k-path** grammar coverage; empirically higher code coverage than prior grammar generation. | https://doi.org/10.1109/ASE.2019.00027 |
| Godefroid, Kiezun & Levin 2008, *Grammar-based Whitebox Fuzzing* (PLDI) | Grammar spec + symbolic execution. | https://doi.org/10.1145/1375581.1375607 |
| Zelenov & Zelenova 2005/06, *Automated Generation of Positive and Negative Tests for Parsers* (FATES, LNCS 3997) | Grammar drives BOTH positive and negative tests. | https://doi.org/10.1007/11759744_13 |
| Zeller, Gopinath, Böhme, Fraser & Holler 2023, *The Fuzzing Book — Grammar Coverage* | **The empirical wedge**: grammar coverage vs code coverage Spearman **≈ 0.9478 < 1.0** — syntactic completeness APPROXIMATES but does not guarantee behavioral completeness. | https://www.fuzzingbook.org/html/GrammarCoverageFuzzer.html |

## G. Oracle / metamorphic (the negative-sign completeness angle)

| Source | Establishes | URL |
|---|---|---|
| Chen, Cheung & Yiu 1998, *Metamorphic Testing* (arXiv re-post 2020) | Metamorphic relations as a **partial oracle** without a full oracle. | https://arxiv.org/abs/2002.12543 |
| Segura, Fraser, Sánchez & Ruiz-Cortés 2016, *A Survey on Metamorphic Testing* (IEEE TSE 42(9):805–824) | Across 119 papers, **deriving effective metamorphic relations is an OPEN problem** — no MR-set completeness construction. | https://doi.org/10.1109/TSE.2016.2532875 |
| Jahangirova, Clark, Harman & Tonella 2016, *Test Oracle Assessment and Improvement* (ISSTA) | Oracle quality splits into **completeness (false positives)** and **soundness (false negatives)** — a measurable two-sided notion. | https://doi.org/10.1145/2931037.2931062 |
| Schuler & Zeller 2011, *Assessing Oracle Quality with Checked Coverage* (ICST) | **Checked coverage** = dynamic slice of statements that actually influence an oracle. | https://doi.org/10.1109/ICST.2011.32 |
| Claessen & Hughes 2000, *QuickCheck* (ICFP) | Property-based testing: properties ARE the oracle; adequacy hinges on **generator distribution coverage**. | https://dl.acm.org/doi/10.1145/351240.351266 |

---

## Synthesis — the three key gaps (workflow output, verbatim summaries)

**Decidability boundary.** There is no decidable, program-SEMANTIC notion of mutation-operator
(Π-)completeness, and the gap is structural. The exact algebraic generation/rank results hold only for
FINITE transformation semigroups (Gomes–Howie; Kozen PSPACE — decidable but hard); they do not transfer to
program space because the word problem is unsolvable (Post/Markov) and program equivalence is undecidable
(Rice; Budd–Angluin). Every "minimal"/"sufficient" mutant result is therefore basis-/test-set-relative
(Offutt; Ammann–Delamaro–Offutt), and true subsumption — the ordering completeness would rank against — is
undecidable (Kurtz). Usable theorems must relativize to a decidable fragment (schema equivalence, TCE,
regression verification) or a fixed test set / dimension.

**PAC-vs-exact.** No proven general theorem says finite learnability/teaching dimension guarantees a
bounded-size witness (compression) set — the exact shape a completeness theorem would need. The
teaching↔compression bridge (Doliwa) makes minimal-witness = compression; that question is OPEN even for
binary VC (only exponential known; linear conjecture unproven; NCTD ≤ VCD withdrawn) and provably FAILS in
the multiclass / list regimes (Pabbaraju; Hanneke–Moran–Waknine) that a real fault space resembles. So a
completeness claim must be basis-/test-set-relative, never a dimension bound.

**Syntactic + oracle.** There is no verified bridge from a decidable *syntactic*-completeness criterion to
a *behavioral* one — the strongest published link is a sub-unity correlation (≈0.95). No source in the
corpus addresses **ASDL** as such a criterion (genuine white space). The oracle side can *measure* an
oracle (checked coverage; completeness/soundness axes) but offers no construction certifying a finite
oracle/MR set complete, and the general behavioral notion is undecidable.
