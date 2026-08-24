---
title: "The Completeness of Mutation Operators"
subtitle: "A transformation-monoid decidability dichotomy for behavioral specification, and why a dimension-bounded minimal complete basis cannot exist"
author: "Rohan Vinaik"
date: "2026-08-25"
status: "DRAFT — proofs WRITTEN. The finite constructive fragment (Thm A, base cases n=2,3) is machine-checked by Aristotle (0 sorries; #print axioms audit owed — see §11). Thm B (undecidability), C (dichotomy), D (foreclosure), E (ASDL) are PAPER PROOFS citing the classical undecidability/impossibility results (Post/Markov, Rice, Pabbaraju, HMW). Not peer-reviewed or fully audited; the two previously-flagged steps are now tightened into Lemmas B.1a (word-problem ≤ submonoid-membership ≤ completeness) and D.a (label space = codomain ⇒ multiclass; set-fence ⇒ list), leaving one optional submission-time item (a concrete List A word-problem embedding). Do not cite as fully proven."
priors_do_not_rederive:
  - "σ = teaching dimension (SC Thm 2.7, machine-checked); σ is μ-parameterized (SC §2.3)"
  - "The two-sign policy σ(P, μ ∪ μ⁻) and the negative operator family Π (NEGATIVE_SPECIFICATION Def 3.1, 11.8, 11.8b)"
  - "Π-completeness as codomain separation (NEGATIVE_SPECIFICATION Def 11.8b) — this paper is its decidability analysis"
  - "σ intrinsic vs σ̂ observed; the decidability qualifier (NEGATIVE_SPECIFICATION Rem 1.3b, Thm 8.1/8.2)"
bibliography: "LITERATURE_PI_COMPLETENESS.md (42 sources, workflow-verified 2026-08-25)"
---

# The Completeness of Mutation Operators

> **Draft notice.** Proofs are now written. **Thm A** (finite fragment) is machine-checked at its base cases
> (`T2_generated`, `T3_generated_rank3` — Aristotle, 0 sorries, 2026-08-25) with the general $n$ transcribed
> from Gomes–Howie; **Thm B/C/D/E** are *paper proofs* citing the classical undecidability (Post/Markov, Rice)
> and impossibility (Pabbaraju, HMW) results — by design, since those dependencies are not in Mathlib and
> should not be re-formalized (the undecidability is recorded as the Lean axiom
> `pi_completeness_undecidable_infinite`, corpus style). The two previously-flagged steps are now discharged
> as **Lemma B.1a** (word-problem ≤ submonoid-membership ≤ completeness) and **Lemma D.a** (label space =
> codomain ⇒ multiclass; set-fence ⇒ list); the only remaining submission-time item is an optional concrete
> `List A` word-problem embedding. The `#print axioms` audit on the two Aristotle proofs is owed (§11). Not
> peer-reviewed; do not cite as fully proven.

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

**Definition 2.3 ($\Pi$-completeness — the STRONG definition).** $\Pi_R$ is **complete for $R$** iff
$\langle \Pi_R \rangle = M_R$ (for finite $R$, $= T_n$): the generated submonoid is the *entire* codomain
transformation monoid, so $\langle \Pi_R \rangle$ realizes **every** deviation $r \mapsto r'$ for all
$r, r' \in |R|$. This is the **strong / maximal** completeness notion — deliberately the strongest available,
not the weakest sufficient one. *(Methodological stance: a strong assertion is chosen precisely so its
FAILURE is informative — where the strong definition cannot be met, the countermanding contradiction exposes
the theoretical limitation exactly. A weaker "separation-only" notion — distinguish any admissible $f$ from
any near-miss under a fixed oracle — may be satisfiable by a proper subset of $M_R$; the gap between the two
is not a hedge but the measuring instrument (Rem. 3.3).)*

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

> `A.1 (characterization)` — **definitional** under the strong Def 2.3 ($\Pi_R$ complete $:\!\Leftrightarrow
> \langle \Pi_R \rangle = T_n$). No proof obligation; A.1 restates the definition to make the monoid-generation
> reading explicit. *(That "realize every $(r,r')$ deviation" $\Leftrightarrow \langle\Pi_R\rangle = T_n$ is
> itself a one-line lemma — every point-to-point map plus closure gives all of $T_n$ — is recorded but not
> load-bearing.)*
>
*Proof of A.2 (constructive basis).* By Gomes & Howie (1987, Math. Proc. Camb. Phil. Soc. 101(3):395–403),
$\operatorname{rank}(T_n) = 3$ for $n \ge 3$: an $n$-cycle and a transposition generate the symmetric group
$S_n$ (which has $\operatorname{rank} = 2$), and adjoining a single map of rank $n-1$ (a non-injective
idempotent collapsing one pair) generates every element of $T_n$ — any $f \in T_n$ of rank $r$ factors as a
permutation, a product of $n-r$ rank-lowering maps (each a conjugate of the adjoined idempotent by a
permutation), and a permutation. For $n \le 2$ the count is smaller ($\operatorname{rank}(T_1)=1$,
$\operatorname{rank}(T_2)=2$). The generation is **machine-checked at the base cases**: `T2_generated`
(the successor and constant-$0$ maps generate $T_2$) and `T3_generated_rank3` (a $3$-cycle, a transposition,
and a rank-$2$ idempotent generate all $27$ elements of $T_3$) were both closed by Aristotle with
`sorries_remaining = 0` (2026-08-25; `Wayfinder/…/proofs/{T2_generated,T3_generated_rank3}.lean`), each
discharging the enumeration by `decide` over the finite monoid. The general $n$ is the cited classical
result; $n = 2, 3$ are the verified instances. $\square$ *[machine-checked modulo `#print axioms` audit; the
general statement is transcribed from Gomes–Howie, not re-proven.]*

*Proof of A.3 (decidability, PSPACE).* $T_n = \operatorname{Function.End}([n])$ is a **finite** monoid with
$n^n$ elements. $\langle \Pi_R \rangle$ is computed by the standard closure iteration: initialize
$S_0 = \Pi_R \cup \{\mathrm{id}\}$, set $S_{k+1} = S_k \cup \{p \circ q : p, q \in S_k\}$, and stop at the
first fixpoint $S_{k+1} = S_k$; the chain is monotone in the finite lattice of subsets of $T_n$, so it
terminates in $\le n^n$ steps, and $\langle \Pi_R \rangle = S_\infty$. Completeness is then the finite check
$S_\infty = T_n$, i.e. $|S_\infty| = n^n$. Hence "$\Pi_R$ is complete" is **decidable**. The precise
complexity is **PSPACE-complete**: the closure can be explored in polynomial space (Kozen 1977, FOCS,
transformation-monoid generability / finite-automata intersection non-emptiness), and Kozen's lower bound
gives hardness. $\square$

**Corollary A.4 (finite completeness certificate is absolute).** On a finite codomain, "$\Pi_R$ is complete"
is a decidable, absolute predicate — no basis-relativity, no observing-set qualifier. This is the negative-sign
counterpart of *Negative Specification* Thm 8.1 (unqualified correctness on the finite/decidable class).

**Remark 3.3 (the strong definition is the measuring instrument).** We adopt Def 2.3's strong completeness
($\langle \Pi_R \rangle = T_n$) deliberately, following the method that a theoretical limit is learned by
asserting the maximum and reading the contradiction that countermands it. The weaker *separation* task
(distinguish any admissible $f$ from any near-miss $f'$ under a fixed covering oracle) may be met by a proper
subset of $T_n$; the **gap** between "generates all of $T_n$" and "separates the observed behaviors" is not a
hedge but the ruler — every place the strong definition fails while separation still holds *localizes* a
codomain deviation the operator family cannot express, which is exactly the diagnostic content the tool needs.
Characterizing the minimal *separating* set (as opposed to the minimal *generating* set, which Thm A fixes at
3) is therefore not a weakening of this paper's claim but a distinct downstream question (§8). *Status of the
separating-set characterization: open; the strong generating-set result (Thm A) stands on its own.*

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

*Proof of B.1 (word-problem reduction — the load-bearing result).* Fix a finite semigroup presentation
$P = \langle A \mid \mathcal{R} \rangle$ ($A$ finite, $\mathcal{R}$ a finite set of relations $u_i = v_i$)
whose **word problem is recursively unsolvable** — given words $u, v \in A^\ast$, deciding $u =_P v$ admits
no algorithm (Post 1947; Markov 1947, independently). Realize $P$ as a structured codomain and a
perturbation family:

- **Codomain.** Let $R$ carry the elements of $P$ — concretely the free monoid $A^\ast$ modulo the
  congruence $\sim_{\mathcal{R}}$ generated by $\mathcal{R}$. This is a recursively-presented infinite type,
  the codomain a real program inhabits (a `list A` return value modulo the rewriting $\mathcal{R}$).
- **Perturbations.** For each generator $a \in A$ let $p_a : R \rightharpoonup R$ be left-translation
  $[w] \mapsto [a \cdot w]$; set $\Pi := \{ p_a : a \in A \}$. Each $p_a$ is a perturbation of the codomain
  (Def 2.1), and for a word $x = a_1 \cdots a_k$ write $p_x := p_{a_1} \circ \cdots \circ p_{a_k} \in
  \langle \Pi \rangle$.

Now the map $x \mapsto p_x$ is a homomorphism $P \to \langle \Pi \rangle \subseteq T_R$, and it is
**injective on $P$**: $p_u = p_v$ as elements of $T_R$ iff $[u \cdot w] = [v \cdot w]$ for all $w$, which
(taking $w = [\varepsilon]$) forces $[u] = [v]$, i.e. $u =_P v$; the converse is immediate. Therefore
**deciding equality of two realizing perturbations in $\langle \Pi \rangle$ is exactly deciding the word
problem of $P$.** Any decision procedure for $\Pi$-completeness (Def 2.3) would, in resolving whether
$\langle \Pi \rangle$ realizes each codomain deviation and *by which composite*, in particular decide
equality of composites $p_u, p_v$ in $\langle \Pi \rangle$ — hence decide $u =_P v$, contradicting
Post/Markov. So $\Pi$-completeness on a structured codomain is undecidable. The construction is uniform in
$P$, which gives (3). $\square$

**Lemma B.1a (the clean form — submonoid membership).** The flagged step ("a completeness oracle yields a
word-equality oracle") is discharged by routing through the standard undecidable problem rather than the
informal "by which composite." Define the **submonoid-membership problem** for $\langle \Pi \rangle$: given a
target perturbation $g$ (a word over $\Pi$'s generators) and $\Pi$, decide $g \in \langle \Pi \rangle$. Then:
(i) membership is undecidable — the map $x \mapsto p_x$ embeds $P$ into $T_R$ (injective, above), so
$p_u \in \langle \{p_v\} \cup \Pi' \rangle$ decides the *generalized word problem* of $P$, undecidable
whenever the word problem is (Post/Markov 1947); (ii) **$\Pi$-completeness is a finite conjunction of
membership queries** — by Def 2.3, $\Pi$ is complete iff $\langle \Pi \rangle = \mathcal{S}_R$, i.e. iff each
of the finitely many generators $g_1, \dots, g_m$ of the target $\mathcal{S}_R$ satisfies
$g_i \in \langle \Pi \rangle$; so a completeness oracle answers each membership query, and by (i) decides the
generalized word problem — contradiction. This replaces the "by which composite" phrasing with the exact
reduction (word problem $\le$ generalized word problem / membership $\le$ completeness). $\square$

*[Paper proof. The undecidability invoked is Post 1947 / Markov 1947, cited not re-proven; the Lean form is
the axiom `pi_completeness_undecidable_infinite` (corpus style, cf. `bridge_B09.undecidability_infinite`).
The remaining submission-time formalization is a clean `List A`-codomain embedding of a *specific* semigroup
presentation with unsolvable word problem — a candidate for a small Aristotle pass on the embedding lemma,
not required for the paper proof.]*

*Proof of B.2 (equivalence reduction).* The predicate "the deviation $(x, r')$ is realizable by some
$p \in \langle \Pi_R \rangle$" is a non-trivial semantic property of the perturbed-denotation family
$\{ f \oplus p \}$. By **Rice's theorem** (1953) every non-trivial semantic property of partial recursive
functions is undecidable; **Budd & Angluin** (1982) give the mutation-testing instantiation
(equivalent-mutant detection is undecidable). Hence deviation-realizability — and a fortiori completeness,
which quantifies over all deviations — is undecidable off the finite class. $\square$

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

*Proof of C.* ($\Leftarrow$) If the carrier is finite (or effectively bounded, Rem 4.1), Thm A.3 gives a
decision procedure, and Cor A.4 makes the certificate absolute. ($\Rightarrow$) If the carrier is a
structured/infinite type, Thm B shows no decision procedure exists, so any certificate must be relativized to
the fixed operator family $\Pi$ and the stated observing oracle. The biconditional is the conjunction of the
two, and it pins the decidable/undecidable frontier exactly at codomain finiteness (Rem 4.1). $\square$

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

*Proof of D (transport of proved impossibilities).* (a) By Doliwa, Fan, Simon & Zilles (2014), for a maximum
concept class a repetition-free teaching plan is *equivalent* to an unlabeled sample-compression scheme; a
*minimal complete basis* — the smallest operator/witness set that identifies the target up to the observing
oracle — is exactly such a minimal teaching object, hence a compression scheme for the induced class. (b) The
concept class a fault space induces is **not binary**: at a given input a program may return any of many wrong
outputs, so the label set is the codomain, and the class is genuinely *multiclass* (and, when several wrong
outputs are jointly admissible, *list*-valued). (c) In that regime the requisite bound provably fails:
Pabbaraju (2024) shows a learnable multiclass class (finite DS-dimension) need admit **no** compression scheme
bounded by any function of DS-dimension; Hanneke, Moran & Waknine (2024) show list compression can fail
outright while uniform convergence persists. Therefore no bound on the minimal complete basis as a function of
a VC-like capacity dimension can hold in general; by (a) the basis inherits this impossibility. Completeness
must be stated basis-relative (Thm C), not dimension-bounded. $\square$

**Lemma D.a (the fault-space class is multiclass, and list-valued under set-fences — the clean form).** The
flagged "in the precise sense those theorems require" is discharged by identifying the concept class exactly.
For a function under specification, the object to identify is its behavioral class $[f]_{\equiv} \subseteq
R^{D}$: a concept is a map $D \to R$, so the **label space is the codomain $R$**, not $\{0,1\}$. Hence the
class is a *multiclass* concept class with $|R|$ labels ($|R| \ge 3$ generically; infinite for structured
$R$) — precisely Pabbaraju (2024)'s setting, whose DS-dimension is the multiclass analogue of VCD and for
which no dimension-bounded compression need exist. When the negative fence forbids a *set* of outputs at an
input (a $\mu^-$ censor admitting several correct values, *Negative Specification* §9), the target is a
*list* concept — precisely Hanneke–Moran–Waknine (2024)'s setting, where list compression can fail while
uniform convergence holds. So the fault-space class sits in exactly the two regimes the cited impossibilities
foreclose; the binary VC regime (where a dimension bound might survive) is *not* where code specification
lives. $\square$

*[No new impossibility is proven; D is the faithful transport of Pabbaraju 2024 / Hanneke–Moran–Waknine 2024
via the Doliwa 2014 teaching$\Leftrightarrow$compression bridge, and Lemma D.a pins the class-membership the
transport needs.]*

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

*Proof of E.* (1) The ASDL is a *finite* set of node kinds and fields; "does $\Pi$ assign a perturbation to
every node kind" is a finite membership check over that set — decidable, in fact linear in the ASDL size. (2)
Contrapositive: if some node kind $k$ has no operator in $\Pi$, then no mutant perturbs a program at a
$k$-occurrence, so the behavioral distinction between a program and its $k$-variant is unexpressible by
$\Pi$; hence $\Pi$ is behaviorally incomplete. So syntactic totality is *necessary*. (3) It is *not*
sufficient: syntactic (production/grammar) coverage is only a sub-unity statistical proxy for behavioral
coverage — Purdom's production coverage and its $k$-path refinements correlate with code coverage at Spearman
$\approx 0.9478 < 1$ (Havrikov & Zeller 2019; The Fuzzing Book), so a syntactically total $\Pi$ can still miss
behavioral distinctions. (Sufficiency would moreover contradict Thm B: a *decidable* syntactic criterion
cannot entail the *undecidable* behavioral completeness of §4.) $\square$

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

1. **The minimal separating set (Rem. 3.3).** For the separation task under a fixed oracle (distinct from the
   strong generating-set completeness Thm A fixes at 3), characterize the minimal *separating* $\Pi_R$ on a
   finite codomain — is it always $\le 3$, or task-dependent?
2. **Decidable structured sub-fragments.** Which structured codomains admit decidable completeness by a
   *restricted* presentation (confluent/terminating rewriting, so the word problem is decidable there)? — the
   TCE / regression-verification analogue for operators.
3. **The exact reduction target for Theorem B.** Which finitely-presented semigroup with unsolvable word
   problem embeds most cleanly into a Python structured codomain (lists? dicts? dataclasses)?
4. **NCTD ≤ VCD** (external, but load-bearing for any future dimension bound): still open after the withdrawn
   2026 proof.

---

## 11. Status ledger

*Proof strategy (decided 2026-08-25). The FINITE constructive fragment (Thm A) is machine-checked via
Wayfinder→Aristotle on concrete generation witnesses; everything undecidability- or ML-dependent (Thm B/C/D)
is a PAPER PROOF citing already-proven classical results — its dependencies (word-problem undecidability,
sample-compression impossibilities) are not in Mathlib and should not be re-formalized. This mirrors the
corpus pattern `bridge_B09_decidability.lean` (finite decidability a Lean theorem; undecidability an axiom
citing Turing/Rado).*

| Result | Kind | Proof form | Status |
|---|---|---|---|
| Thm A.1 (characterization) | definitional (strong Def 2.3) | — | no obligation |
| **Thm A.2 (n=2): `T2_generated`** | concrete constructive witness | **Lean → Aristotle** | ✅ **CLOSED (0 sorries) + `#print axioms` AUDITED CLEAN**: `[propext, Classical.choice, Quot.sound]`, no `sorryAx` |
| **Thm A.2 (n=3, rank 3): `T3_generated_rank3`** | concrete constructive witness | **Lean → Aristotle** | ✅ **CLOSED (0 sorries) + `#print axioms` AUDITED CLEAN**: `[propext, Classical.choice, Quot.sound]`, no `sorryAx` |
| Thm A.2 (general $\operatorname{rank}T_n=3$) | inherited (Gomes–Howie 1987) | paper §3 (cite) | ✍ written; n=2,3 are the machine-checked instances |
| Thm A.3 (finite decidability) | finite-iteration + Kozen (PSPACE) | paper §3 proof + Lean `instance` | ✍ written (proof of A.3) |
| Thm B.1 (word-problem reduction) | **NEW, load-bearing** | **paper proof §4** (reduce to Post/Markov 1947) | ✍ written + **tightened (Lemma B.1a: word-problem ≤ membership ≤ completeness)**; remaining = concrete `List A` embedding (optional Aristotle pass). Lean axiom `pi_completeness_undecidable_infinite` records it |
| Thm B.2 (equivalence reduction) | inherited (Rice 1953 / Budd–Angluin 1982) | paper §4 (cite) | ✍ written |
| Thm C (dichotomy) | corollary of A+B | paper §5 | ✍ written |
| Thm D (compression foreclosure) | assembly of proved impossibilities | paper §6 (transport Pabbaraju / HMW) | ✍ written + **tightened (Lemma D.a: label space = codomain ⇒ multiclass; set-fence ⇒ list)** |
| Thm E (ASDL syntactic criterion) | decidable + empirical caveat | paper §7 + empirical citation | ✍ written |
| Rem 3.3 (minimal separating set) | conjecture | — | open |

**Lean artifacts.** Source: `Wayfinder/data/lean_project/operator_completeness.lean` (the finite witnesses +
the undecidability axiom, corpus style) + manifest `…/operator_completeness_manifest.jsonl`. Closed proofs:
`Semantic_Specification_Learning/proofs/{T2_generated,T3_generated_rank3}.lean` — both **CLOSED by Aristotle,
`sorries_remaining = 0`** (2026-08-25), each discharging the finite enumeration by `decide`. The
`#print axioms` audit **PASSED CLEAN** (2026-08-25, after repairing the proofs-repo Mathlib cache and a
macOS `com.apple.provenance` backup-restore artifact in `.lake`): both proofs depend on exactly
`[propext, Classical.choice, Quot.sound]` — the standard Lean/Mathlib base — with **no `sorryAx`**.

**Provenance.** The gap this paper fills was confirmed by a source-verified literature workflow (42/42
sources, 2026-08-25; `LITERATURE_PI_COMPLETENESS.md`). The algebraic and computability results are classical
and cited; the reduction of the finiteness dichotomy to $\Pi$-completeness (Thm B.1) and the dichotomy
(Thm C) are this paper's contribution, delivered as **paper proofs citing the classical undecidability
results** (not Lean, by design — see the strategy note). The finite constructive fragment (Thm A, n=2/3) is
**machine-checked and axiom-audited CLEAN** (Aristotle, 0 sorries; `#print axioms` =
`[propext, Classical.choice, Quot.sound]`, no `sorryAx`). Register: *fully proven and audited* on the finite
fragment; *rigorous paper proof* on B–E (with the two former gaps discharged as Lemmas B.1a, D.a). Remaining
before submission: pull SC/SSL scaffolding inline (§8), and optionally a concrete `List A` embedding for B.1.
Not peer-reviewed.
