---
title: "The Completeness of Mutation Operators"
subtitle: "Output-mutation completeness is a transformation-monoid generation problem: a trichotomy (finite-decidable, infinite-impossible, relative-undecidable) and the post-composition ceiling"
author: 
date: 
status: "DRAFT — proofs written; finite fragment machine-checked. Thm A (finite decidability + rank-3 basis) is proven; its base cases n=2,3 are machine-checked in Lean 4 (Mathlib) and #print-axioms clean ([propext, Classical.choice, Quot.sound], no sorryAx). Thm B (infinite impossibility) is an elementary cardinality argument, also machine-checked in Lean 4 (Mathlib) and #print-axioms clean ([propext, Classical.choice, Quot.sound], no sorryAx). Thm C (relative undecidability) is a paper proof citing classical undecidability (Post/Markov word problem; Rice). Thm D is the trichotomy assembled from A/B/C. Conjecture E (dimension-bounded basis foreclosure) is stated as CONJECTURAL: it is contingent on a basis-to-compression bridge not established here (Doliwa 2014 is restricted to maximum classes). Prop F (ASDL coverage) is a decidable engineering invariant; the earlier 'necessary for behavioral completeness' claim is WITHDRAWN. Not peer-reviewed; do not cite as fully proven."
bibliography: "LITERATURE_PI_COMPLETENESS.md (42 sources, verified 2026-08-25)"
---

# The Completeness of Mutation Operators

> **Draft notice.** **Thm A** (finite fragment: decidability *in P* and the rank-3 basis) is proven, with its
> base cases machine-checked in Lean 4 / Mathlib (`T2_generated`, `T3_generated_rank3`; `#print axioms` clean,
> no `sorryAx`) and the general $n$ transcribed from Gomes–Howie 1987. **Thm B** (infinite impossibility) is an
> elementary cardinality argument, machine-checked in Lean 4 / Mathlib (`pi_incomplete_infinite`; `#print axioms`
> clean, no `sorryAx`). **Thm C** (relative undecidability) is a paper proof citing Post/Markov and
> Rice. **Thm D** is the trichotomy. **Conjecture E** is explicitly conjectural — the basis-to-compression
> bridge it needs is not established here. **Prop F** (ASDL coverage) is a decidable invariant, not a logical
> prerequisite for completeness. Not peer-reviewed; do not cite as fully proven.

## Abstract

Mutation testing measures a program by whether a covering test suite distinguishes a finite family of
mutation operators — both traditional program-text mutations and *output* (extreme) mutations that perturb the
returned value. Its guarantee is only as strong as the **completeness** of that operator family. Yet mutation
testing has never had a completeness theorem: the field rests on the **coupling-effect hypothesis**
(DeMillo–Lipton–Sayward 1978), an unproven assumption, and its strongest formal results (sufficient operators,
minimal dominator sets) are **basis-** or **test-set-relative** by construction. We show this is not an
oversight but the shadow of a decidability boundary. Modelling an output-operator family $\Pi_R$ as a finite
generating set of the transformation monoid on a codomain type $R$, "is this family complete?" becomes "does
this finite set generate the monoid?" — and the answer is a **trichotomy**. On a **finite** codomain, absolute
completeness is *decidable* — in fact in **polynomial time** (not, as one might fear, PSPACE) — and
*constructive*: a complete basis of size $3$ exists, from $\operatorname{rank}(T_n)=3$ (Gomes–Howie 1987), with
the base cases machine-checked in Lean. On an **infinite** codomain, absolute completeness by a finite family
is *impossible* — a one-line cardinality argument (a countable closure cannot equal an uncountable monoid), so
the only meaningful notion there is **relative** completeness against a finitely-presented target of admissible
deviations. That relative question is *undecidable* in general (reduction from the word problem for
finitely-presented semigroups, Post & Markov 1947; and from program equivalence, Rice 1953 / Budd–Angluin
1982) — but its boundary is the **presentation**, not the carrier: restricted presentations
(confluent/terminating rewriting) are decidable. We also isolate a hard **ceiling**: because output operators
act by post-composition, they can never express a fault that separates two inputs the correct function
identifies — so output-mutation completeness is completeness for *output recodings*, a strict subspace of
behavioral faults. Two further results frame the practice: a *conjectured* foreclosure of any
capacity-dimension-bounded minimal complete basis (contingent on a teaching/compression bridge we do not
prove), and a decidable *syntactic* coverage invariant (operator-totality over Python's ASDL) that is useful
but, we show, neither necessary nor sufficient for the behavioral notion. The contribution is the recognition
that mutation-operator completeness *is* a transformation-monoid generation problem, and that its honest answer
is a trichotomy with a ceiling.

---

## 1. Introduction

### 1.1 The gap

A mutation-based specification tool certifies a function against a finite family of mutation operators:
program-text mutations (traditional mutation testing) and *output* mutations that perturb the returned value
(extreme mutation — replacing a method body with `return c`, à la Descartes; Niedermayr et al. 2016;
Vera-Pérez et al. 2018). A "mutation score $=1$" certificate is only as strong as the operator family is
**complete** — does it express every behavioral distinction an incorrect implementation could exhibit at the
output? The field has never answered this. A source-verified sweep of the canonical literature (42 sources,
`LITERATURE_PI_COMPLETENESS.md`) returns a single, sharp finding: **no completeness theorem for mutation
operators exists**, and the strongest results are relative-by-construction:

- the **coupling effect** and **competent-programmer hypothesis** (DeMillo, Lipton & Sayward 1978) — the
  propositions that *would* underwrite completeness — are stated as motivating **assumptions**, never proven;
- "sufficient mutation operators" (Offutt et al. 1996) is an **experimental** determination relative to the
  full operator set;
- "theoretical minimal sets of mutants" (Ammann, Delamaro & Offutt 2014) — the most theorem-like prior result —
  defines minimality **relative to a fixed test set and an already-generated pool**;
- and the ordering a completeness theorem would rank against, *true* (semantic) mutant subsumption, is
  **undecidable** (Kurtz, Ammann & Offutt 2015).

### 1.2 The thesis

The gap is **structural, not a missing proof**. We recast output-operator completeness as a
**transformation-monoid generation** question and show it inherits the classical decidability landscape of that
theory — but the landscape is richer than a two-way "decidable vs undecidable" split. It is a **trichotomy**,
sorted by *which* completeness one asks for and *where*:

1. **absolute** completeness on a **finite** codomain — generate the whole monoid — is *decidable in
   polynomial time* and *constructive* (a size-3 basis);
2. **absolute** completeness on an **infinite** codomain is *impossible* for any finite operator family, by
   cardinality — so nothing there is left to decide;
3. **relative** completeness — generate a finitely-presented target of *admissible* deviations — is where the
   computability lives: *undecidable in general*, with the boundary drawn by the **presentation** (the word
   problem), not by the carrier's cardinality.

Underneath all three sits a ceiling no amount of operator richness removes: output operators act by
post-composition, so they cannot express faults that separate inputs the correct function collapses. This turns
"we hope our operators are complete" into a precise map of what is achievable, what is decidable, and what is
foreclosed.

### 1.3 Contributions

1. A formalization of $\Pi$-completeness as generation of the codomain transformation monoid, with the
   **post-composition ceiling** made explicit (§2).
2. **Theorem A** — finite-codomain absolute completeness is decidable **in P** and constructive (basis size 3);
   base cases machine-checked in Lean (§3).
3. **Theorem B** — infinite-codomain absolute completeness by a finite family is **impossible** (cardinality)
   (§4).
4. **Theorem C** — relative (presented-target) completeness is **undecidable** in general (word-problem
   reduction), with the boundary at the *presentation* (§5).
5. **Theorem D** — the trichotomy and the forced, honestly-scoped certificate (§6).
6. **Conjecture E** — a *conjectured* foreclosure of any dimension-bounded minimal complete basis, and exactly
   what bridge is missing to prove it (§7).
7. **Proposition F** — ASDL operator-coverage: a decidable engineering invariant, neither necessary nor
   sufficient for behavioral completeness (§8).

---

## 2. Preliminaries

We recall the standard mutation-testing setting (a program, a covering test suite, a finite family of mutation
operators) and fix the algebraic model for output operators.

**Definition 2.1 (Codomain, transformation monoid).** A *codomain type* $R$ has a carrier set $|R|$ (finite or
infinite). Output perturbations are **total** self-maps of the return value (e.g. `return c` is the constant
map, `x ↦ x+1` the successor) — so the ambient object is the **full transformation monoid**
$T(R) = (\,|R| \to |R|,\ \circ,\ \mathrm{id}\,)$ of total self-maps under composition. When $|R| = n$ is
finite, $T(R) = T_n$, the finite monoid of $n^n$ maps. An *output-operator family* $\Pi_R \subseteq T(R)$ is a
finite set of perturbations; $\langle \Pi_R \rangle$ is the submonoid it generates.

> *(Remark: we use total maps throughout. An earlier partial-map framing is unnecessary — the output operators
> a tool actually applies are total — and conflating the partial monoid $PT_n$ ($(n{+}1)^n$ elements) with the
> total $T_n$ would mis-state the basis size. Everything below is about $T(R)$.)*

**Definition 2.2 (Behavior, codomain deviation).** A program's observable output behavior is its denotation
$f : D \to |R|$. A *codomain deviation* of $f$ is a pair $(x, r')$ with $r' \neq f(x)$ — a wrong output at
input $x$. A perturbation $p$ *realizes* the deviation at $x$ iff $p(f(x)) = r'$; the perturbed denotation is
$f \oplus p = p \circ f$ (the standard post-composition an output operator applies).

**Proposition 2.3 (the post-composition ceiling).** Output operators act only by post-composition, so for every
$p \in T(R)$ and all $x_1, x_2 \in D$,
$$ f(x_1) = f(x_2) \ \Longrightarrow\ (p \circ f)(x_1) = (p \circ f)(x_2). $$
Hence **no** output perturbation can separate two inputs the correct denotation $f$ identifies. The set of
faults expressible by an output family is exactly the orbit of output recodings
$\{\, p \circ f : p \in \langle \Pi_R \rangle \,\} \subseteq |R|^{D}$, which is a **strict** subset of the
behavioral fault space $|R|^{D}$ whenever $f$ is non-injective. *Proof.* Post-composition applies the same $p$
to equal values $f(x_1)=f(x_2)$, giving equal outputs; a fault $f'$ with $f'(x_1)\neq f'(x_2)$ while
$f(x_1)=f(x_2)$ is therefore not of the form $p\circ f$. $\square$

> This is the honest scope statement for the entire enterprise: output-mutation completeness is completeness
> for *output recodings*, not for arbitrary behavioral faults. Everything below characterizes completeness
> **within** that ceiling; §8 and §9 return to what it means for practice.

**Definition 2.4 (two completeness notions).** Fix a codomain $R$ and family $\Pi_R \subseteq T(R)$.

- **Absolute completeness.** $\Pi_R$ is *absolutely complete* iff $\langle \Pi_R \rangle = T(R)$ — it generates
  the **entire** transformation monoid. This is the strongest available notion, chosen deliberately: a maximal
  assertion is informative precisely where it *fails*, and the place it fails localizes exactly the deviation
  the family cannot express.
- **Relative completeness.** Given a finitely-generated submonoid $\mathcal{S}_R \subseteq T(R)$ of *admissible*
  deviations (the perturbations a specification actually deems faults), $\Pi_R$ is *complete relative to
  $\mathcal{S}_R$* iff $\langle \Pi_R \rangle \supseteq \mathcal{S}_R$.

Absolute completeness is the special case $\mathcal{S}_R = T(R)$. The distinction is not cosmetic: §4 shows
absolute completeness is unattainable on infinite carriers, so relative completeness is the *only* meaningful
notion there — and it is a different mathematical object with a different decidability status (§5).

**Remark 2.5 (three strictly increasing notions — do not conflate them).** It is tempting to gloss "generate
$T_n$" as "realize every deviation," but three notions must be kept apart:

$$ \underbrace{\forall r,r'\ \exists p \in \langle\Pi\rangle:\ p(r)=r'}_{\text{(i) point-transitivity}}
\ \subsetneq\ \underbrace{\langle\Pi\rangle \text{ distinguishes any two admissible behaviors}}_{\text{(ii) separation}}
\ \subsetneq\ \underbrace{\langle\Pi\rangle = T(R)}_{\text{(iii) generation}}. $$

The inclusions are strict. **(i) does not imply (iii):** the regular action of the cyclic group $C_n$ on $n$
points is point-transitive (for any $r,r'$ some rotation sends $r$ to $r'$) yet contains only $n$ permutations,
nowhere near the $n^n$ maps of $T_n$. Absolute completeness (Def 2.4) is (iii), the strongest; §3's basis is a
*generating* set, and §7's open question is about the minimal *separating* set (ii), a genuinely distinct
problem.

**Remark 2.6 (why the monoid).** This is the output-operator instance of the standing **operator-basis /
sufficiency** question of mutation testing: "does a finite operator family span the faults it is meant to
detect?" For the codomain, the perturbations at a point form $T(R)$ acting on $|R|$, so "span the (admissible)
deviation space" is literally "generate (enough of) $T(R)$" — a generation problem in a transformation monoid,
which is where the classical decidability results live.

---

## 3. The finite-codomain fragment: absolute completeness is decidable (in P) and constructive

**Theorem A (finite-codomain absolute completeness).** Let $R$ be a finite codomain, $|R| = n$.

1. *(constructive basis)* An absolutely complete $\Pi_R$ exists with $|\Pi_R| = 3$: a transposition, an
   $n$-cycle, and one rank-$(n-1)$ idempotent generate $T_n$; i.e. $\operatorname{rank}(T_n) = 3$ for $n \ge 3$.
2. *(decidability, in P)* Deciding whether a given finite $\Pi_R$ is absolutely complete is **decidable in
   polynomial time**.

*Proof of A.1 (constructive basis).* By Gomes & Howie (1987, Math. Proc. Camb. Phil. Soc. 101(3):395–403),
$\operatorname{rank}(T_n) = 3$ for $n \ge 3$: an $n$-cycle and a transposition generate the symmetric group
$S_n$ (rank $2$), and adjoining a single map of rank $n-1$ (a non-injective idempotent collapsing one pair)
generates every element of $T_n$ — any $f \in T_n$ of rank $r$ factors as a permutation, a product of $n-r$
rank-lowering maps (each a conjugate of the adjoined idempotent by a permutation), and a permutation. For
$n \le 2$ the count is smaller ($\operatorname{rank}(T_1)=1$, $\operatorname{rank}(T_2)=2$). The generation is
**machine-checked at the base cases** in Lean 4 / Mathlib: `T2_generated` (the successor and constant-$0$ maps
generate $T_2$) and `T3_generated_rank3` (a $3$-cycle, a transposition, and a rank-$2$ idempotent generate all
$27$ elements of $T_3$) are fully proven, no `sorry` (`proofs/T2_generated.lean`,
`proofs/T3_generated_rank3.lean`), each discharging the enumeration by `decide` over the finite monoid. The
general $n$ is the cited classical result. $\square$ *[`#print axioms` clean — see §12; the general statement
is transcribed from Gomes–Howie, not re-proven.]*

*Proof of A.2 (decidability in P).* We do **not** compute the closure (which can reach $n^n$ elements). The key
is that rank is non-increasing under composition, $\operatorname{rank}(g \circ h) \le \min(\operatorname{rank}
g, \operatorname{rank} h)$. Two consequences:

- **Permutations come only from permutation generators.** A product of generators is a permutation iff every
  factor is a permutation (one singular factor forces rank $< n$). Hence the group of units
  $\langle \Pi_R \rangle \cap S_n$ equals $\langle \Pi_R \cap S_n \rangle$.
- **The top singular rank is a generator's rank.** Any singular element of $\langle \Pi_R \rangle$ is a product
  containing at least one singular generator, and its rank is at most the maximum rank among the singular
  generators. So $\langle \Pi_R \rangle$ contains a rank-$(n-1)$ element iff $\Pi_R$ itself contains one.

Combined with A.1 (Gomes–Howie), this gives the exact criterion:
$$ \langle \Pi_R \rangle = T_n \quad\Longleftrightarrow\quad
\big(\, \langle \Pi_R \cap S_n \rangle = S_n \,\big) \ \wedge\ \big(\, \Pi_R \text{ contains a map of rank } n-1 \,\big). $$
($\Leftarrow$: $\langle \Pi_R \rangle \supseteq \langle S_n \cup \{\text{rank-}(n{-}1)\}\rangle = T_n$ by A.1.
$\Rightarrow$: $T_n \supseteq S_n$ forces the permutation generators to generate $S_n$; $T_n$ contains
rank-$(n{-}1)$ maps, forcing such a generator.) Both conditions are polynomial-time checkable: the first is
membership/generation for a permutation group — decidable in polynomial time by the **Schreier–Sims** algorithm
(compute the order of $\langle \Pi_R \cap S_n \rangle$ and compare to $n!$); the second is an $O(|\Pi_R| \cdot
n)$ rank scan. Hence absolute completeness on a finite codomain is decidable in **P**. $\square$

**Corollary A.3 (finite completeness certificate is absolute — and cheap).** On a finite codomain, "$\Pi_R$ is
absolutely complete" is a decidable, absolute predicate, computable in polynomial time — no basis-relativity, no
observing-set qualifier, and no exponential closure.

**Remark 3.1 (this is a *nicer* result than PSPACE — and Kozen belongs elsewhere).** One might expect
transformation-monoid questions to be PSPACE-hard, and indeed the general **membership** problem — given
$g, f_1, \dots, f_m \in T_n$, decide $g \in \langle f_1, \dots, f_m \rangle$ — is PSPACE-complete (Kozen 1977,
FOCS). But recognizing that a family generates the *entire* monoid is strictly easier: the rank argument above
sidesteps the closure entirely and lands in P. Kozen's PSPACE-completeness is the right tool for the *relative*
question (membership in a presented target $\mathcal{S}_R$, §5), not for absolute recognition. The finite
fragment is therefore even cleaner than a decidability claim: it is efficient.

**Remark 3.2 (the strong definition is deliberate; the separating set is a distinct question).** We adopt
absolute completeness ($\langle \Pi_R \rangle = T_n$) as the maximal notion because a theoretical limit is
learned by asserting the maximum and reading the contradiction that countermands it (Def 2.4). The weaker
*separation* task (Rem 2.5(ii): distinguish any admissible $f$ from any near-miss $f'$ under a fixed oracle) may
be met by a proper subset of $T_n$; the **gap** between "generates all of $T_n$" and "separates the observed
behaviors" is diagnostic — every place the strong definition fails while separation still holds *localizes* a
codomain deviation the family cannot express. Characterizing the minimal *separating* set (as opposed to the
minimal *generating* set, which A.1 fixes at 3) is a distinct downstream question (§11, Open Problem 1), and it
is open.

---

## 4. The infinite carrier: absolute completeness is impossible

On an infinite codomain there is nothing to decide, because the strong notion is unattainable outright — and the
reason is a one-line cardinality count, not a subtle reduction.

**Theorem B (infinite-codomain absolute completeness is impossible).** Let $R$ have an **infinite** carrier and
let $\Pi_R \subseteq T(R)$ be **finite**. Then $\langle \Pi_R \rangle \neq T(R)$; i.e. no finite output-operator
family is absolutely complete on an infinite codomain.

*Proof.* Every element of $\langle \Pi_R \rangle$ is the value of a finite word over the finite alphabet
$\Pi_R \cup \{\mathrm{id}\}$. The set of such words is a countable union of finite sets, hence countable, so
$|\langle \Pi_R \rangle| \le \aleph_0$. But $T(R) = |R|^{|R|}$ has cardinality at least $2^{|R|} > |R| \ge
\aleph_0$ (Cantor), hence uncountable. A countable set cannot equal an uncountable one, so
$\langle \Pi_R \rangle \subsetneq T(R)$. $\square$

> **Machine-checked.** This is proven in Lean 4 / Mathlib as `pi_incomplete_infinite`
> (`proofs/pi_incomplete_infinite.lean`), no `sorry`, `#print axioms` clean
> (`[propext, Classical.choice, Quot.sound]`, no `sorryAx`): the closure of a `Finset` of maps is
> countable (`Submonoid.exists_list_of_mem_closure` + `Set.countable_range`), while
> `Function.End R` is uncountable for `[Infinite R]` (`Cardinal.cantor`, `Cardinal.mk_arrow`) — so
> `closure ↑P = ⊤` is contradictory. Together with `T2_generated`/`T3_generated_rank3` (§3), **both
> ends of the trichotomy are now machine-verified**; the undecidable middle (Thm C) is the cited
> paper proof.

**Corollary B.1 (only relative completeness survives).** On an infinite codomain, the meaningful completeness
question is not "does $\Pi_R$ generate $T(R)$?" (always *no*) but "does $\Pi_R$ generate a given finitely-
presented target $\mathcal{S}_R$ of admissible deviations?" — the *relative* notion of Def 2.4. §5 shows that
question is where undecidability actually lives.

**Remark 4.1 (impossibility, not undecidability — the honest reading).** The strength of Theorem B is its
triviality: it needs no word problem and no Rice's theorem. It says the ambition of an *absolute* completeness
certificate on an unbounded type is not blocked by our cleverness but by counting. This *replaces* any attempt
to prove "absolute completeness is undecidable on infinite carriers" — that framing is a category error, since
the predicate is a constant `false` there, hence (vacuously) decidable. The genuine computability content is in
the relative question, to which we now turn.

---

## 5. Relative completeness: undecidable in general, with the boundary at the presentation

**Theorem C (relative completeness is undecidable).** Let $R$ be a codomain with infinite carrier presented by
a finite set of generators and relations (lists/tuples/dicts/records over an infinite base type, or any
recursively-presented transformation sub-monoid of $T(R)$), and let $\mathcal{S}_R$ be a finitely-generated
target of admissible deviations. Then:

1. *(word-problem reduction)* Deciding whether $\Pi_R$ is complete relative to $\mathcal{S}_R$ — i.e. whether
   $\langle \Pi_R \rangle \supseteq \mathcal{S}_R$ — is **undecidable** in general.
2. *(equivalence reduction)* Deciding whether a *specific* deviation is realizable by $\langle \Pi_R \rangle$
   reduces to mutant/program equivalence and is **undecidable**.
3. *(the boundary is the presentation, not the carrier)* Undecidability is a property of the *presentation*: for
   presentations whose word problem is solvable (e.g. finite confluent-and-terminating rewriting systems),
   relative completeness is decidable. Carrier cardinality alone does not settle it.

*Proof of C.1 (word-problem reduction — the load-bearing result).* Fix a finite semigroup presentation
$P = \langle A \mid \mathcal{R} \rangle$ whose **word problem is recursively unsolvable** — given words
$u, v \in A^\ast$, deciding $u =_P v$ admits no algorithm (Post 1947; Markov 1947, independently). Realize $P$
as a structured codomain and a perturbation family:

- **Codomain.** Let $R$ carry the free monoid $A^\ast$ modulo the congruence $\sim_{\mathcal{R}}$ generated by
  $\mathcal{R}$ — a recursively-presented infinite type a real program inhabits (a `list A` return value modulo
  the rewriting $\mathcal{R}$).
- **Perturbations.** For each generator $a \in A$ let $p_a : R \to R$ be left-translation
  $[w] \mapsto [a \cdot w]$; set $\Pi := \{ p_a : a \in A \}$. For a word $x = a_1 \cdots a_k$ write
  $p_x := p_{a_1} \circ \cdots \circ p_{a_k} \in \langle \Pi \rangle$.

The map $x \mapsto p_x$ is a homomorphism $P \to \langle \Pi \rangle \subseteq T(R)$, injective on $P$: $p_u =
p_v$ as elements of $T(R)$ iff $[u \cdot w] = [v \cdot w]$ for all $w$, which (taking $w = [\varepsilon]$) forces
$[u] = [v]$, i.e. $u =_P v$; the converse is the congruence. So **deciding equality of two composites in
$\langle \Pi \rangle$ is exactly deciding the word problem of $P$** (Lemma C.1a below routes this through
submonoid membership to reach relative completeness without hand-waving). Since the word problem is unsolvable,
no algorithm decides relative completeness across such presentations, giving (1); the construction is uniform in
$P$. $\square$

**Lemma C.1a (word problem $\le$ submonoid membership $\le$ relative completeness).** The step "a completeness
oracle yields a word-equality oracle" is discharged through the standard undecidable problem. Define the
**submonoid-membership problem**: given a target $g$ (a word over $\Pi$'s generators) and $\Pi$, decide
$g \in \langle \Pi \rangle$. Then (i) membership is undecidable — the injective embedding $x \mapsto p_x$ makes
$p_u \in \langle \{p_v\} \cup \Pi' \rangle$ decide the *generalized word problem* of $P$, undecidable whenever
the word problem is (Post/Markov 1947); and (ii) **relative completeness is a finite conjunction of membership
queries** — $\langle \Pi \rangle \supseteq \mathcal{S}_R$ iff each of the finitely many generators
$g_1, \dots, g_m$ of $\mathcal{S}_R$ satisfies $g_i \in \langle \Pi \rangle$, so a completeness oracle answers
every membership query and by (i) decides the generalized word problem — contradiction. This is the exact
reduction (word problem $\le$ generalized word problem / membership $\le$ relative completeness). $\square$

*Proof of C.2 (equivalence reduction).* "The deviation $(x, r')$ is realizable by some $p \in \langle \Pi_R
\rangle$" is a non-trivial semantic property of the perturbed-denotation family $\{ f \oplus p \}$. By **Rice's
theorem** (1953) every non-trivial semantic property of partial recursive functions is undecidable; **Budd &
Angluin** (1982) give the mutation-testing instantiation (equivalent-mutant detection is undecidable). Hence
deviation-realizability — and a fortiori completeness, which quantifies over all admissible deviations — is
undecidable off the finite class. $\square$

**Remark 5.1 (the boundary is the word problem, not $|R|$).** Theorems B and C together correct the naive
picture. It is *not* that "completeness is decidable iff the carrier is finite." Absolute completeness is
decidable-and-cheap when finite (Thm A) and vacuously settled (impossible) when infinite (Thm B); *relative*
completeness is undecidable for presentations with unsolvable word problem and **decidable** for those without
(confluent/terminating rewriting, where $=_P$ is decidable by normal forms). So the genuine
decidable/undecidable frontier is drawn inside the relative notion, by the **presentation** — exactly the
classical object (the word problem) that separates decidable from undecidable throughout computability. Bounded
instances of a structured codomain (lists of length $\le k$ over a finite base) are finite and fall under
Theorem A; the undecidability is a property of the *unbounded, unrestricted* presentation, never of a concrete
input.

---

## 6. The trichotomy and the honest certificate

**Theorem D (the completeness trichotomy).** For output-operator completeness under Def 2.4:

1. **Finite codomain — absolute, decidable, constructive.** Absolute completeness is decidable in **P** (Thm A),
   with a constructive complete basis of size $3$ (Cor A.3); the certificate is absolute, with no basis- or
   oracle-relativity.
2. **Infinite codomain — absolute completeness impossible.** No finite family is absolutely complete (Thm B);
   the only meaningful notion is relative completeness against a named finitely-presented target.
3. **Relative completeness — presentation-dependent.** Deciding $\langle \Pi_R \rangle \supseteq \mathcal{S}_R$
   is undecidable in general (Thm C) but decidable for restricted (e.g. confluent/terminating) presentations;
   the frontier is the word problem, not the carrier.

Consequently a completeness **certificate** is:

- **absolute and (efficiently) decidable** on the finite-codomain fragment (1);
- necessarily **relative** on structured/infinite codomains (2,3) — "complete over the operator family $\Pi$ and
  the named admissible target / observing oracle," never over the full behavioral space — and, even so,
  established only when the presentation's word problem is solvable.

*Proof.* Direct assembly: (1) is Theorem A + Corollary A.3; (2) is Theorem B + Corollary B.1; (3) is
Theorem C. The certificate consequences are the contrapositive readings: where absolute completeness is
unavailable (2) or undecidable-for-this-presentation (3), any certificate must name the family and target it is
relative to. $\square$

**Remark 6.1 (name which side you are on).** Theorem D shares its cause with the classical undecidability of
semantic program equivalence (Rice 1953), and it dictates the same honest response for any mutation-based tool:
a certificate must state which regime it is in. Claiming *absolute* completeness on a structured codomain is the
overclaim Theorem D forbids (Thm B makes it not merely unproven but false); reporting "complete over the
operator family $\Pi$, admissible target and observing set named" is exactly correct. A residual survivor a
finite family does not distinguish is therefore reported *unproven*, never promoted to *equivalent* — the
correct disposition, forced by the trichotomy, not a tool limitation. And beneath all of it, Proposition 2.3's
ceiling holds: even a certificate that is absolute (finite codomain) certifies completeness only for *output
recodings*, never for input-separating faults.

---

## 7. A conjectured foreclosure: no dimension-bounded minimal complete basis

The tempting strengthening — a *minimal* complete basis whose size is bounded by a learning-theoretic "fault
dimension" — is, we conjecture, foreclosed in the regime a real fault space inhabits. We state it as a
**conjecture**, because the step that would make it a theorem is a bridge we do not establish here, and we say
exactly which.

**Conjecture E (compression foreclosure — CONDITIONAL).** *Suppose* a minimal complete (or minimal
identifying) operator basis can be read as a sample-compression scheme for the induced concept class. Then no
such basis is bounded by any function of a VC-like capacity dimension in the multiclass/list regime a fault
space inhabits, so completeness cannot be certified by a capacity dimension.

*What is proven, and what is assumed.* The **external impossibilities are real and cited**: for a binary class
of VC-dimension $d$ only compression exponential in $d$ is known (Moran–Yehudayoff 2015), the linear conjecture
is open, and $\mathrm{NCTD} \le \mathrm{VCD}$ is open (the 2026 Liu–Li proof was withdrawn, "Lemma 2 wrong");
in the multiclass regime, finite DS-dimension learnability does **not** imply a DS-dimension-bounded compression
scheme (Pabbaraju 2024), and list compression can fail while uniform convergence persists
(Hanneke–Moran–Waknine 2024). And **Lemma D.a below is proven**: a fault space is genuinely multiclass/list, so
it sits in exactly the regime those impossibilities target — *if* the antecedent holds.

**The missing bridge (why this is a conjecture, not a theorem).** The antecedent — "a minimal complete
*generating* basis *is* a sample-compression scheme" — is **not established here**, and two obstacles stand in
the way:

1. Doliwa, Fan, Simon & Zilles (2014) prove the teaching-plan $\Leftrightarrow$ unlabeled-compression
   equivalence **only for maximum concept classes**; a fault space need not be a maximum class, so their
   equivalence does not transport for free.
2. More fundamentally, a **generating set of transformations under composition** and a **subsample sufficient to
   reconstruct labels** are different mathematical objects. Calling both "minimal identifying objects" is a
   suggestive analogy, not a reduction; a genuine proof would have to construct one from the other.

Until a reduction bridging (1)–(2) is supplied, E remains conjectural. We include it because the direction is
important for practice — *do not advertise a capacity-dimension-bounded minimal operator set* — and because
naming the missing bridge precisely is more useful than a false theorem.

**Lemma D.a (the fault-space class is multiclass, and list-valued under set-fences — proven).** For a function
under specification, the object to identify is its behavioral class $[f]_{\equiv} \subseteq R^{D}$: a concept is
a map $D \to R$, so the **label space is the codomain $R$**, not $\{0,1\}$. Hence the class is a *multiclass*
concept class with $|R|$ labels ($|R| \ge 3$ generically; infinite for structured $R$) — precisely Pabbaraju
(2024)'s setting. When the specification admits a *set* of correct outputs at an input (several implementations
all acceptable), the target is a *list* concept — precisely Hanneke–Moran–Waknine (2024)'s setting. So the
fault-space class sits in exactly the two regimes the cited impossibilities foreclose; the binary VC regime
(where a dimension bound might survive) is *not* where code specification lives. $\square$

**Remark 7.1 (the honest positive reading).** What survives unconditionally: a real fault space is
multiclass/list (Lemma D.a), and in that regime the *general* learning-theoretic hope for a
capacity-dimension-bounded minimal object is already foreclosed *for compression schemes and teaching sets*
(Pabbaraju; HMW). What is conjectural is only the transport of that foreclosure onto *operator generating bases*
via a bridge we have flagged. Either way, completeness is safest stated basis-relative (Thm D), not
dimension-bounded.

---

## 8. Syntactic operator coverage: a decidable invariant (not a completeness criterion)

Behavioral completeness is undecidable off finite codomains (Thm C); a *syntactic* coverage check is decidable,
and it is the honest thing a tool can actually run — provided it is not oversold as a completeness criterion.

**Proposition F (ASDL operator-coverage).** Let a language's abstract syntax be finitely specified (Python's
ASDL: a finite set of node kinds and fields). Define $\Pi$ **syntactically total** iff it assigns a
mutation/perturbation to every node kind (and, for the codomain, every base type of the observed return
grammar). Then:

1. *(decidable)* syntactic totality is decidable — a finite coverage check against the ASDL, linear in its size;
2. *(not sufficient)* it does **not** entail behavioral completeness: syntactic (production/grammar) coverage
   correlates with behavioral coverage only sub-unity (grammar-coverage vs code-coverage Spearman $\approx
   0.9478 < 1$; Havrikov & Zeller 2019; The Fuzzing Book), and — the logical backstop — a *decidable* syntactic
   criterion cannot entail the *undecidable* relative completeness of §5;
3. *(not necessary for the codomain notion)* it is **not** necessary for output-operator completeness (Def 2.4):
   by Theorem A, three output operators are absolutely complete on a $3$-element codomain while mutating **no**
   AST node whatsoever. Syntactic coverage is a coverage invariant over *program-text* operators, a different
   family from the codomain operators completeness (Def 2.4) is about.

*Proof.* (1) The ASDL is finite; membership "$\Pi$ assigns a perturbation to every node kind" is a finite check.
(2) The correlation is empirical and sub-unity (cited); the logical non-entailment is Thm C (decidable $\not\Rightarrow$
undecidable). (3) Theorem A exhibits an absolutely complete output family with empty AST coverage, so coverage
is not necessary for Def 2.4 completeness. $\square$

**Remark 8.1 (what changed, and why).** An earlier draft asserted ASDL-totality as *necessary* for behavioral
completeness. That claim is **withdrawn**: it conflated program-text operator coverage with the codomain
completeness of Def 2.4, and Theorem A refutes the necessity directly. What remains is genuinely useful and
correctly scoped — a decidable engineering gate ("did our operator dispatch miss a node kind?") that a tool can
run permanently, honestly advertised as *neither* necessary *nor* sufficient for the behavioral notion. No
source in the verified corpus frames ASDL coverage this way; the decidable-gate framing is white space, the
necessity claim was the overreach.

---

## 9. Consequences for mutation-based tools

The results apply to any tool that certifies code against a finite operator family — traditional or output
(extreme) mutation.

- **Report which regime you are in (Thm D).** Absolute completeness is available, decidable, and cheap only on
  finite codomains; on structured/infinite codomains it is *impossible* (Thm B), so a basis-relative
  certificate — "complete over operator family $\Pi$ and named admissible target/oracle" — is exactly correct,
  and even that holds only when the presentation's word problem is solvable. Treat an undistinguished survivor
  as *unproven*, never *equivalent* (Rem 6.1).
- **Know the ceiling (Prop 2.3).** Even an absolute certificate certifies completeness for *output recodings*
  only; a fault that separates inputs the correct function collapses is outside what any output family can
  express. A tool that also mutates program text is reaching for a *different*, larger fault space — one this
  paper's codomain results do not cover.
- **Three output operators suffice — when the codomain is finite (Thm A).** For a finite return type, a
  transposition, a cycle, and a rank-$(n{-}1)$ map are a complete basis; that is the concrete answer to "how
  many output operators do we need," in the case where "all of them" is even attainable.
- **Do not advertise a dimension-bounded minimal operator set (Conj E).** The learning-theoretic hope is, at
  best, conjecturally foreclosed and, for compression/teaching objects, already foreclosed in the
  multiclass/list regime a real fault space inhabits.
- **Run the one decidable coverage gate honestly (Prop F).** ASDL operator-totality is a decidable invariant
  worth checking — advertised as neither necessary nor sufficient for behavioral completeness.

---

## 10. Related work

The full source-verified survey is `LITERATURE_PI_COMPLETENESS.md`. In brief: mutation-testing theory has no
completeness theorem (DeMillo 1978 hypothesis; Offutt 1996 empirical; Ammann 2014 relative; Kurtz 2015
undecidable subsumption); transformation-semigroup theory supplies the finite case (Gomes–Howie 1987; and the
membership complexity, Kozen 1977); computability supplies the wall (Post/Markov 1947; Rice 1953; Budd–Angluin
1982; the Luckham–Park–Paterson 1970 schema-equivalence boundary is the precedent for the dichotomy/trichotomy
*form*); learning theory supplies the (conjectural) foreclosure ingredients (Doliwa 2014 — restricted to
maximum classes; Moran–Yehudayoff 2015; Pabbaraju 2024; Hanneke–Moran–Waknine 2024); grammar-coverage supplies
the syntactic side (Purdom 1972; Havrikov–Zeller 2019 / The Fuzzing Book's sub-unity correlation).

---

## 11. Open problems

1. **The minimal separating set (Rem 2.5, 3.2).** For the separation task under a fixed oracle (Rem 2.5(ii),
   distinct from the strong generating-set completeness A.1 fixes at 3), characterize the minimal *separating*
   $\Pi_R$ on a finite codomain — always $\le 3$, or task-dependent?
2. **Decidable structured sub-fragments (Thm C.3).** Which structured codomains admit decidable *relative*
   completeness by a restricted presentation (confluent/terminating rewriting, so the word problem is decidable
   there)? — the TCE / regression-verification analogue for operators.
3. **The exact reduction target for Theorem C.** Which finitely-presented semigroup with unsolvable word problem
   embeds most cleanly into a Python structured codomain (lists? dicts? dataclasses)? A concrete `List A`
   embedding of a specific such presentation is the natural next Lean artifact.
4. **The basis-to-compression bridge (Conj E).** Is a minimal complete *generating* basis reducible to a
   sample-compression scheme / teaching set beyond maximum classes? Establishing (or refuting) this converts
   Conjecture E into a theorem (or retires it).
5. **NCTD ≤ VCD** (external, load-bearing for any future dimension bound): still open after the withdrawn 2026
   proof.

---

## 12. Status ledger

*Proof strategy. The finite constructive fragment (Thm A) is machine-checked in Lean 4 / Mathlib on concrete
generation witnesses; the infinite impossibility (Thm B) is elementary; the relative-undecidability (Thm C) is a
paper proof citing already-proven classical results — their dependencies (word-problem undecidability, Rice) are
not in Mathlib and need not be re-formalized. Conjecture E is explicitly conditional on an unproven bridge.*

| Result | Kind | Proof form | Status |
|---|---|---|---|
| **Thm A.1 (n=2): `T2_generated`** | concrete constructive witness | **Lean 4 / Mathlib** | ✅ proven, no `sorry`; `#print axioms` = `[propext, Classical.choice, Quot.sound]` |
| **Thm A.1 (n=3, rank 3): `T3_generated_rank3`** | concrete constructive witness | **Lean 4 / Mathlib** | ✅ proven, no `sorry`; `#print axioms` = `[propext, Classical.choice, Quot.sound]` |
| Thm A.1 (general $\operatorname{rank}T_n=3$) | inherited (Gomes–Howie 1987) | paper §3 (cite) | ✍ written; n=2,3 are the machine-checked instances |
| Thm A.2 (finite decidability **in P**) | rank argument + Schreier–Sims | paper §3 proof | ✍ written (upgrades the earlier PSPACE claim to P) |
| Prop 2.3 (post-composition ceiling) | elementary | paper §2 | ✅ proven (one line) |
| **Thm B (infinite impossibility): `pi_incomplete_infinite`** | **cardinality**, machine-checked | **Lean 4 / Mathlib** + paper §4 | ✅ proven, no `sorry`; `#print axioms` = `[propext, Classical.choice, Quot.sound]` (no `sorryAx`) — replaces "undecidable off finite" |
| Thm C.1 (relative undecidability) | word-problem reduction | **paper proof §5** (Post/Markov 1947) | ✍ written + tightened (Lemma C.1a: word problem ≤ membership ≤ relative completeness); optional concrete `List A` embedding remains |
| Thm C.2 (equivalence reduction) | inherited (Rice 1953 / Budd–Angluin 1982) | paper §5 (cite) | ✍ written |
| Thm C.3 (boundary = presentation) | corollary (decidable word problem ⇒ decidable) | paper §5 | ✍ written |
| Thm D (trichotomy) | assembly of A+B+C | paper §6 | ✍ written |
| **Conj E (dimension-bounded basis)** | **CONJECTURE** (bridge unproven) | paper §7 | ⚠ conjectural — Doliwa restricted to maximum classes; generating-basis ↔ compression bridge not established |
| Lemma D.a (class is multiclass/list) | elementary identification | paper §7 | ✅ proven (supports the antecedent of Conj E) |
| Prop F (ASDL coverage) | decidable; not nec., not suff. | paper §8 | ✍ written (earlier "necessary" claim withdrawn — Rem 8.1) |
| Open: minimal separating set | conjecture | — | open |

**Lean artifacts.** In this paper's `proofs/` folder: **three closed proofs** — `T2_generated.lean`,
`T3_generated_rank3.lean` (Thm A.1, finite generation, base cases $n=2,3$, each discharging the finite
enumeration by `decide`), and `pi_incomplete_infinite.lean` (Thm B, infinite impossibility: closure of a
`Finset` of maps is countable via `Submonoid.exists_list_of_mem_closure` + `Set.countable_range`, while
`Function.End R` is uncountable for `[Infinite R]` via `Cardinal.cantor` + `Cardinal.mk_arrow`). All three are
**fully proven (no `sorry`)** in Lean 4 / Mathlib with `#print axioms` **clean** (`[propext, Classical.choice,
Quot.sound]`, **no `sorryAx`**) — so **both ends of the trichotomy are machine-verified**: the finite
constructive basis and the infinite impossibility. The umbrella `operator_completeness.lean` carries
**statements only**: the finite-decidability `instance` is a signature stub (the proof is the P-time algorithm
of §3, Thm A.2, not a Lean term), and the file records **one cited classical fact as an axiom** — the
undecidability of extensional equality of $\mathbb{N} \to \mathbb{N}$ functions, the Rice-flavored ingredient
behind Thm C.2. That axiom is **not** a formalization of the word-problem reduction (Thm C.1) and is not claimed
to be; the reduction lives in the paper proof (§5) and Lemma C.1a. The honest summary: the two ends of the
trichotomy (Thm A basis, Thm B impossibility) are machine-checked and axiom-clean; the undecidable middle
(Thm C), the P-time decidability (Thm A.2), and everything else are paper proofs or (for Conj E) an open
conjecture.

**Provenance.** The gap this paper fills was confirmed by a source-verified literature review (42 sources,
`LITERATURE_PI_COMPLETENESS.md`). The algebraic and computability results are classical and cited; the recasting
of output-operator completeness as monoid generation, the trichotomy (Thm D), the P-time finite recognition
(Thm A.2), the cardinality impossibility (Thm B), and the post-composition ceiling (Prop 2.3) are this paper's
contributions. Register: *fully proven and audited* on the finite fragment (Thm A) and the elementary results
(Thm B, Prop 2.3, Lemma D.a); *rigorous paper proof* on Thm C; *conjectural* on E. Not peer-reviewed.
