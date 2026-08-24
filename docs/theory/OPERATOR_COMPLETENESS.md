---
title: "The Completeness of Mutation Operators"
subtitle: "A transformation-monoid decidability dichotomy for behavioral specification, and why a dimension-bounded minimal complete basis cannot exist"
author: "Rohan Vinaik"
date: "2026-08-25"
status: "DRAFT SCAFFOLD — theorem statements authored, proofs are PLACEHOLDERS (Wayfinder/Aristotle targets). Do not cite as proven. Every proof obligation carries a status tag and a strategy sketch; nothing here is machine-checked yet."
priors_do_not_rederive:
  - "σ = teaching dimension (SC Thm 2.7, machine-checked); σ is μ-parameterized (SC §2.3)"
  - "The two-sign policy σ(P, μ ∪ μ⁻) and the negative operator family Π (NEGATIVE_SPECIFICATION Def 3.1, 11.8, 11.8b)"
  - "Π-completeness as codomain separation (NEGATIVE_SPECIFICATION Def 11.8b) — this paper is its decidability analysis"
  - "σ intrinsic vs σ̂ observed; the decidability qualifier (NEGATIVE_SPECIFICATION Rem 1.3b, Thm 8.1/8.2)"
bibliography: "LITERATURE_PI_COMPLETENESS.md (42 sources, workflow-verified 2026-08-25)"
---

# The Completeness of Mutation Operators

> **Scaffold notice.** This is an incomplete draft. Theorem *statements* are authored; every *proof* is a
> placeholder marked `▢ PROOF OBLIGATION` with a strategy sketch and a target tag `[Wayfinder/Aristotle:
> Tx]`. Placeholders are the point — the statements are what the proof engine will be handed. Nothing below
> is claimed as proven until its obligation is discharged and audited.

## Abstract

Mutation-based specification (the Wesker/Detective engine; the $\sigma(P,\mu\cup\mu^-)$ two-sign construction
of *Negative Specification*) measures a program by whether a covering suite distinguishes a finite family of
syntactic and codomain mutants. Its guarantee is only as strong as the **completeness** of that operator
family: does the family realize *every* behavioral distinction a near-miss could exhibit? Mutation testing
has never had a completeness theorem — the field rests on the **coupling-effect hypothesis** (DeMillo–Lipton–
Sayward 1978), an unproven assumption, and its strongest formal results (sufficient operators, minimal
dominator sets) are **basis-** or **test-set-relative** by construction. We show this is not an oversight but
a decidability boundary. Modelling the negative operator family $\Pi_R$ as a finite generating set of the
transformation monoid on a codomain type $R$, we prove a **dichotomy**: on a **finite** codomain, completeness
is *decidable* (PSPACE-complete, Kozen 1977) and *constructive* (a complete basis of size 3 exists, from
$\operatorname{rank}(T_n)=3$, Gomes–Howie 1987); on a **structured/infinite** codomain, completeness is
*undecidable* (reduction from the word problem for finitely-presented semigroups, Post & Markov 1947; and
from program equivalence, Rice 1953 / Budd–Angluin 1982). The dichotomy is the exact operator-layer analogue
of $\sigma$ vs $\hat\sigma$: a completeness certificate is absolute on the decidable fragment and necessarily
*basis-relative* off it — the qualifier being **decidability, not tool maturity**. We further prove a
**foreclosure**: via the teaching-plan $\Leftrightarrow$ sample-compression equivalence (Doliwa et al. 2014),
a *minimal* complete basis is a compression scheme, and no such scheme is bounded by any function of a
VC-like fault dimension in the multiclass regime a real fault space inhabits (Pabbaraju 2024;
Hanneke–Moran–Waknine 2024) — so completeness cannot be certified by a capacity dimension. Finally we isolate
the **syntactic** criterion: operator-totality over a finitely-specified abstract grammar (Python's ASDL) is a
decidable *necessary* condition for completeness, cleanly separated from the undecidable behavioral one. The
contribution is the recognition that "is this mutation operator set complete?" is a *transformation-monoid
generation problem modulo the word problem*, and its honest answer is a decidability dichotomy.

---

## 1. Introduction

### 1.1 The gap

A mutation-based specification tool certifies a function against a finite family of mutants: the positive
family $\mu$ (program-text variants) and the negative family $\mu^-/\Pi$ (codomain perturbations,
*Negative Specification* §3, §11.8). The certificate "SC = 1 modulo the operator universe" is only as strong
as the family is **complete** — does it express every behavioral distinction an incorrect implementation
could exhibit at the codomain (*Negative Specification* Def 11.8b)? The field has never answered this. A
source-verified sweep of the canonical literature (42 sources, `LITERATURE_PI_COMPLETENESS.md`) returns a
single, sharp finding: **no completeness theorem for mutation operators exists**, and the strongest results
are relative-by-construction:

- the **coupling effect** and **competent-programmer hypothesis** (DeMillo, Lipton & Sayward 1978) — the
  propositions that *would* underwrite completeness — are stated as motivating **assumptions**, never proven;
- "sufficient mutation operators" (Offutt et al. 1996) is an **experimental** determination relative to the
  full operator set;
- "theoretical minimal sets of mutants" (Ammann, Delamaro & Offutt 2014) — the most theorem-like prior result
  — defines minimality **relative to a fixed test set and an already-generated pool**;
- and the ordering a completeness theorem would rank against, *true* (semantic) mutant subsumption, is
  **undecidable** (Kurtz, Ammann & Offutt 2015).

### 1.2 The thesis

The gap is **structural, not a missing proof**. We recast operator completeness as a **transformation-monoid
generation** question and show it inherits the classical decidability boundary of that theory: decidable and
constructive on finite carriers, undecidable on structured/infinite ones. This turns "we hope our operators
are complete" into a theorem with two sides — an *effective procedure* where the codomain is finite, and a
*provable impossibility of a uniform procedure* where it is not, forcing an honest basis-relative certificate
exactly as $\hat\sigma$ relativizes $\sigma$ (*Negative Specification* Rem 1.3b, Thm 8.1/8.2). We then close
the tempting escape hatch — a *minimal* complete basis bounded by a learning-theoretic dimension — by a
foreclosure from the sample-compression impossibilities.

### 1.3 Contributions

1. A formalization of $\Pi$-completeness as generation of the codomain transformation monoid (§2).
2. **Theorem A** — finite-codomain completeness is decidable (PSPACE) and constructive (basis size 3) (§3).
3. **Theorem B** — structured/infinite-codomain completeness is undecidable (word-problem reduction) (§4).
4. **Theorem C** — the dichotomy and the basis-relative certificate; the $\sigma/\hat\sigma$ homology (§5).
5. **Theorem D** — no dimension-bounded minimal complete basis (compression foreclosure) (§6).
6. **Theorem E** — ASDL operator-totality: a decidable *necessary* syntactic criterion (§7).

---

## 2. Preliminaries

We inherit the mutation-system apparatus (*Specification Complexity* §2; *Negative Specification* §1, §3) and
fix the algebraic setting.

**Definition 2.1 (Codomain, perturbation monoid).** A *codomain type* $R$ has a carrier set $|R|$ (finite or
infinite). The *perturbation monoid* $M_R = (\,|R| \rightharpoonup |R|,\ \circ,\ \mathrm{id}\,)$ is the monoid
of partial self-maps of $|R|$ under composition. When $|R| = n$ is finite, the total sub-monoid is the **full
transformation monoid** $T_n$ ($n^n$ elements). A *negative policy* $\Pi_R \subseteq M_R$ is a finite family
(*Negative Specification* Def 3.1); $\langle \Pi_R \rangle$ is the submonoid it generates.

**Definition 2.2 (Behavior, codomain deviation).** A program's observable output behavior is its denotation
$f : D \to |R|$. A *codomain deviation* of $f$ is a pair $(x, r')$ with $r' \neq f(x)$ — a wrong output at
input $x$. A perturbation $p$ *realizes* the deviation at $x$ iff $p(f(x)) = r'$; the perturbed denotation is
$f \oplus p = p \circ f$ (*Negative Specification* Def 3.1).

**Definition 2.3 ($\Pi$-completeness / codomain separation).** $\Pi_R$ is **complete for $R$** iff
$\langle \Pi_R \rangle$ realizes every codomain deviation: for every $r \in |R|$ and every $r' \in |R|$ there
is $p \in \langle \Pi_R \rangle$ with $p(r) = r'$ — equivalently, $\langle \Pi_R \rangle$ acts *transitively*
on $|R|$ and separates every pair of behaviors distinguishable at the codomain (*Negative Specification* Def
11.8b). *(Refinement, deferred to Lemma 3.2: completeness for the SEPARATION task — distinguishing any two
admissible-vs-near-miss behaviors under a covering oracle — may require strictly less than full transitive
realization; §3 states the strong form and fences the minimal-separating-set refinement as open.)*

**Remark 2.4 (why the monoid).** This is the negative-sign instance of the positive **operator-basis**
question *Specification Complexity* §2.3 leaves open: "does a finite operator family span the space it is
meant to specify?" For the codomain, the space of deviations at a point is $M_R$ acting on $|R|$, so
"span the deviation space" is literally "generate (enough of) $M_R$" — a generation problem in a
transformation monoid, which is where the classical decidability results live.

---

## 3. The finite-codomain fragment: completeness is decidable and constructive

**Theorem A (finite-codomain completeness).** Let $R$ be a finite codomain, $|R| = n$.
1. *(characterization)* $\Pi_R$ is complete (Def 2.3) iff $\langle \Pi_R \rangle = T_n$.
2. *(constructive basis)* A complete $\Pi_R$ exists with $|\Pi_R| = 3$: a transposition, an $n$-cycle, and one
   rank-$(n-1)$ idempotent generate $T_n$; i.e. $\operatorname{rank}(T_n) = 3$.
3. *(decidability)* Deciding whether a given finite $\Pi_R$ is complete is **decidable and PSPACE-complete**.

> `▢ PROOF OBLIGATION A.1 (characterization)` — Show Def 2.3's transitive-realization condition is equivalent
> to $\langle \Pi_R \rangle = T_n$. *Strategy:* full realization of every $(r,r')$ deviation means every
> constant-image and every permutation is generated; a monoid on $[n]$ realizing all $(r \mapsto r')$ and
> closed under composition is $T_n$. *Status: mechanical algebra. [Wayfinder/Aristotle: T_A1]*
>
> `▢ PROOF OBLIGATION A.2 (basis)` — $\operatorname{rank}(T_n) = 3$. *Strategy:* CITE Gomes & Howie 1987
> (transposition + $n$-cycle generate $S_n$ at rank 2; adjoining one rank-$(n-1)$ map reaches all of $T_n$).
> This is inherited classical algebra, not a new proof — transcribe and machine-check the generation.
> *Status: transcription of a proved result. [Wayfinder/Aristotle: T_A2]*
>
> `▢ PROOF OBLIGATION A.3 (decidability)` — membership/generation in a finite transformation monoid is
> decidable, and generability is PSPACE-complete. *Strategy:* CITE Kozen 1977 (transformation-monoid
> generability / automata-intersection non-emptiness is PSPACE-complete); the decision procedure is closure of
> the generated set under composition, bounded by $|T_n| = n^n$. *Status: cite + assemble. [Wayfinder/Aristotle: T_A3]*

**Corollary A.4 (finite completeness certificate is absolute).** On a finite codomain, "$\Pi_R$ is complete"
is a decidable, absolute predicate — no basis-relativity, no observing-set qualifier. This is the negative-sign
counterpart of *Negative Specification* Thm 8.1 (unqualified correctness on the finite/decidable class).

**Lemma 3.2 (the minimal-separating-set refinement — OPEN).** For the weaker *separation* task (distinguish any
admissible $f$ from any near-miss $f'$ under a fixed covering oracle), the minimal complete $\Pi_R$ may have
size $< 3$ or a different structure than a monoid generating set. Characterizing it is open (§8). *Status:
CONJECTURE / open.*

---

## 4. The undecidability wall: structured and infinite codomains

**Theorem B (structured-codomain completeness is undecidable).** Let $R$ be a codomain with infinite carrier
presented by a finite set of generators and relations (lists/tuples/dicts/records over an infinite base type,
or any recursively-presented transformation sub-monoid of $M_R$). Then:
1. *(word-problem reduction)* Deciding whether $\Pi_R$ is complete — equivalently whether
   $\langle \Pi_R \rangle$ equals the target sub-monoid $\mathcal{S}_R$ of admissible deviations — is
   **undecidable**.
2. *(equivalence reduction)* Deciding whether a *specific* behavioral deviation is realizable by
   $\langle \Pi_R \rangle$ reduces to mutant/program equivalence and is **undecidable**.
3. *(corollary)* No algorithm uniformly decides $\Pi$-completeness across structured codomains.

> `▢ PROOF OBLIGATION B.1 (word problem)` — reduce the word problem for finitely-presented semigroups to
> $\Pi$-completeness. *Strategy:* given a finite semigroup presentation $\langle A \mid \mathcal{R}\rangle$ with
> unsolvable word problem (Post 1947; Markov 1947), realize its generators as perturbations on a structured
> $R$ so that a target deviation is realizable iff two words are equal in the presentation; then "does
> $\Pi_R$ realize the target" decides "$u = v$", contradiction. *Status: the LOAD-BEARING new proof of this
> paper. [Wayfinder/Aristotle: T_B1 — the hard one; may need an Aristotle pass on the embedding lemma.]*
>
> `▢ PROOF OBLIGATION B.2 (equivalence)` — CITE Rice 1953 (non-trivial semantic properties undecidable) and
> Budd & Angluin 1982 (equivalent-mutant undecidability); "is deviation $(x,r')$ realizable by some
> $p \in \langle\Pi_R\rangle$" is a non-trivial semantic property of the perturbed denotation. *Status: cite +
> instantiate. [Wayfinder/Aristotle: T_B2]*

**Remark 4.1 (the boundary is exactly the carrier).** Theorems A and B locate the frontier precisely at
codomain *finiteness*: the same generation question is decidable on $T_n$ and undecidable on a
finitely-presented infinite transformation monoid — the transition is the word problem (Post/Markov), the same
object that separates decidable from undecidable throughout computability. Bounded-size instances of a
structured codomain (lists of length $\le k$ over a finite base) are finite and fall under Theorem A; the
undecidability is a property of the *unbounded* type, not of any concrete input.

---

## 5. The dichotomy and the honest certificate

**Theorem C (decidability dichotomy for $\Pi$-completeness).** $\Pi$-completeness is decidable **iff** the
codomain carrier is finite (or effectively bounded). Consequently a completeness certificate is:
1. **absolute and decidable** on the finite-codomain fragment (Thm A, Cor A.4);
2. necessarily **basis-relative** on structured/infinite codomains (Thm B) — "complete over the operator
   family $\Pi$ and the stated observing oracle," never over the full behavioral space.

> `▢ PROOF OBLIGATION C.1` — immediate from Thm A ($\Leftarrow$) and Thm B ($\Rightarrow$). *Status: corollary.
> [Wayfinder/Aristotle: T_C1]*

**Corollary 5.1 (the $\sigma / \hat\sigma$ homology).** Theorem C is the operator-layer image of the
value-layer dichotomy of *Negative Specification*: $\sigma$ (intrinsic, undecidable off the decidable class) vs
$\hat\sigma$ (test-relative, computed, residual named); Thm 8.1 (unqualified on finite $D$) vs Thm 8.2
(qualified off it, obstructed by Rice). The two dichotomies share a cause — the same undecidability of
semantic equivalence — and the same honest response: **name which side you are on**. A tool that claims
absolute completeness on a structured codomain is making the overclaim Thm C forbids; a tool that reports
"complete over $\Pi$, observing set named" is exactly correct.

**Remark 5.2 (this resolves *Negative Specification* §18 Q4).** The open "completeness of $\Pi$ (Def 11.8b)"
item is answered: it is not one question but a dichotomy — solved on finite codomains, provably not uniformly
solvable off them, honest-basis-relative in between. The engine's existing posture (candidate-equivalent —
UNPROVEN, never promoted; the observing-set qualifier) is *forced by Theorem C*, not a limitation.

---

## 6. No dimension-bounded minimal complete basis (a foreclosure)

The tempting strengthening — a *minimal* complete basis whose size is bounded by a learning-theoretic
"fault dimension" — is not merely open; it is **foreclosed** in the regime a real fault space inhabits.

**Theorem D (compression foreclosure).** Let a minimal complete negative-specification basis be read, via the
teaching-plan $\Leftrightarrow$ sample-compression equivalence, as a sample-compression scheme for the induced
concept class. Then:
1. *(binary, open)* even for a binary concept class of VC-dimension $d$, only compression **exponential in
   $d$** is known (Moran–Yehudayoff 2015); the linear conjecture is open, and $\mathrm{NCTD} \le \mathrm{VCD}$
   is open (Liu–Li 2026 withdrawn, "Lemma 2 wrong");
2. *(multiclass, foreclosed)* the fault space is **multiclass** (many wrong outputs per input), and finite
   DS-dimension multiclass learnability does **not** imply a compression scheme bounded by any function of
   DS-dimension (Pabbaraju 2024); list compression fails (Hanneke–Moran–Waknine 2024).

Hence a minimal complete basis, where it exists, **cannot be certified by a capacity dimension**; completeness
must be stated basis-relative (as in Thm C), never as a dimension bound.

> `▢ PROOF OBLIGATION D.1` — assemble the cited impossibilities into the negative-specification setting.
> *Strategy:* (a) invoke Doliwa et al. 2014 (repetition-free teaching plan = unlabeled sample compression for
> maximum classes) to identify minimal-basis with compression; (b) argue the fault space is multiclass/list,
> not binary; (c) invoke Pabbaraju 2024 and Hanneke–Moran–Waknine 2024 for the impossibility in that regime.
> No NEW impossibility is proven — this is a transport of established negative results. *Status: assembly of
> proved foreclosures. [Wayfinder/Aristotle: T_D1 — verify the transport is faithful, not a new claim.]*

**Remark 6.1 (this confirms the μ⁻ retraction).** Theorem D is the same wall *Negative Specification* Prop 15.6
hit when it **retracted** consolidation = sample compression to a conjecture. That retraction was correct;
Theorem D promotes it from "we couldn't prove the bound" to "the bound provably fails in the operative regime,"
which is a stronger and more useful statement.

---

## 7. The syntactic criterion: ASDL operator-totality

Behavioral completeness is undecidable off finite codomains (Thm B); a *syntactic* completeness criterion is
decidable, and it is the honest thing a tool can actually check.

**Theorem E (ASDL-totality is a decidable necessary criterion).** Let a language's abstract syntax be finitely
specified (Python's ASDL: a finite set of node kinds and fields). Define $\Pi$ **syntactically total** iff it
assigns a mutation/perturbation to every node kind (and, for the codomain, every base type of the observed
return grammar). Then:
1. *(decidable)* syntactic totality is decidable — a finite coverage check against the ASDL;
2. *(necessary)* syntactic totality is **necessary** for behavioral $\Pi$-completeness (a node kind with no
   operator leaves a behavioral distinction unexpressible);
3. *(not sufficient)* it is **not sufficient**: syntactic saturation only *correlates* with behavioral
   coverage (grammar-coverage vs code-coverage Spearman $\approx 0.95 < 1$; Purdom 1972; Fuzzing Book), it does
   not entail it.

> `▢ PROOF OBLIGATION E.1` — (1) finite check, immediate. (2) contrapositive: an unmutated node kind fixes a
> behavioral dimension. (3) CITE the sub-unity grammar/code coverage correlation as the counterexample witness
> to sufficiency. *Status: (1)-(2) immediate; (3) empirical citation. [Wayfinder/Aristotle: T_E1]*

**Remark 7.1 (the actionable gate).** Theorem E is the buildable criterion: wire Wesker's operator dispatch to
the ASDL as a total-coverage check, retiring "did we miss a node kind" as a permanent, decidable gate —
without ever claiming it entails behavioral completeness (which Thm B forbids). No source in the verified
corpus frames ASDL this way; this is white space.

---

## 8. Relation to two-sign specification

This paper is the completeness-analysis layer beneath *Negative Specification*. The two-sign
$\sigma(P, \mu \cup \mu^-)$ bounds behavioral identity *over the operator universe*; Theorem C says that
"over the operator universe" qualifier is **forced** — absolute completeness is available only on finite
codomains, and the tool's basis-relative certificate is exactly correct elsewhere. Theorem A supplies, for the
finite case, a *minimal complete negative basis of size 3* — a concrete instance of the "author the teaching
set once" reduction (*Negative Specification* Thm 6.2, §12). Theorem D confirms the paper's retracted
compression reading. Theorem E supplies the decidable syntactic gate the engine can actually run.

`▢ INTEGRATION OBLIGATION` — pull the machine-checked $\sigma = \mathrm{TD}$ (SC Thm 2.7), the two-sign
construction, and the isolation theorem (*Negative Specification* Thm 5.2) into this paper's preliminaries as
inherited scaffolding, so it stands alone. *(Placeholder: cite by file+section now; expand into a
self-contained §2 before submission.)*

---

## 9. Related work

The full source-verified survey is `LITERATURE_PI_COMPLETENESS.md`. In brief: mutation-testing theory has no
completeness theorem (DeMillo 1978 hypothesis; Offutt 1996 empirical; Ammann 2014 relative; Kurtz 2015
undecidable subsumption); transformation-semigroup theory supplies the finite case (Gomes–Howie 1987;
Kozen 1977); computability supplies the wall (Post/Markov 1947; Rice 1953; Budd–Angluin 1982; the
Luckham–Park–Paterson 1970 schema-equivalence boundary is the precedent for the dichotomy *form*); learning
theory supplies the foreclosure (Doliwa 2014; Moran–Yehudayoff 2015; Pabbaraju 2024; Hanneke–Moran–Waknine
2024); grammar-coverage supplies the syntactic side (Purdom 1972; Fuzzing Book's sub-unity correlation).

---

## 10. Open problems

1. **The minimal separating set (Lemma 3.2).** For the separation task under a fixed oracle, characterize the
   minimal complete $\Pi_R$ on a finite codomain — is it always $\le 3$, or task-dependent?
2. **Decidable structured sub-fragments.** Which structured codomains admit decidable completeness by a
   *restricted* presentation (confluent/terminating rewriting, so the word problem is decidable there)? — the
   TCE / regression-verification analogue for operators.
3. **The exact reduction target for Theorem B.** Which finitely-presented semigroup with unsolvable word
   problem embeds most cleanly into a Python structured codomain (lists? dicts? dataclasses)?
4. **NCTD ≤ VCD** (external, but load-bearing for any future dimension bound): still open after the withdrawn
   2026 proof.

---

## 11. Status ledger

*Nothing here is machine-checked yet. This ledger is the proof-engine work list.*

| Result | Kind | Status | Target |
|---|---|---|---|
| Thm A.1 (characterization) | mechanical algebra | ▢ to prove | T_A1 |
| Thm A.2 ($\operatorname{rank} T_n = 3$) | inherited (Gomes–Howie) | ▢ transcribe + check | T_A2 |
| Thm A.3 (PSPACE decidable) | inherited (Kozen) | ▢ cite + assemble | T_A3 |
| Thm B.1 (word-problem reduction) | **NEW, load-bearing** | ▢ to prove | T_B1 |
| Thm B.2 (equivalence reduction) | inherited (Rice / Budd–Angluin) | ▢ cite + instantiate | T_B2 |
| Thm C (dichotomy) | corollary of A+B | ▢ to prove | T_C1 |
| Thm D (compression foreclosure) | assembly of proved impossibilities | ▢ transport + verify | T_D1 |
| Thm E (ASDL syntactic criterion) | decidable + empirical caveat | ▢ to prove | T_E1 |
| Lemma 3.2 (minimal separating set) | conjecture | open | — |

**Provenance.** The gap this paper fills was confirmed by a source-verified literature workflow (42/42
sources, 2026-08-25; `LITERATURE_PI_COMPLETENESS.md`). The algebraic and computability results are classical
and cited; the reduction of the finiteness dichotomy to $\Pi$-completeness (Thm B.1, the dichotomy Thm C) is
this paper's contribution and is **unproven pending the Wayfinder/Aristotle pass**. Do not cite as proven.
