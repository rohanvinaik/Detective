---
title: "The Completeness of Mutation Operators"
subtitle: "Output-mutation completeness as transformation-monoid generation: a P / PSPACE-complete / impossible / undecidable landscape and the post-composition ceiling"
author: 
date: 
status: "DRAFT — proofs written; two corners of the landscape machine-checked. Thm A.1 (rank-3 basis, finite generation) base cases n=2,3 are machine-checked in Lean 4 (Mathlib), #print-axioms clean ([propext, Classical.choice, Quot.sound], no sorryAx). Thm A.2 (finite ABSOLUTE completeness in P) and A.3 (finite RELATIVE completeness PSPACE-complete, Kozen 1977) are paper proofs. Thm B (infinite-absolute impossibility) is an elementary cardinality argument, machine-checked in Lean 4 (Mathlib), #print-axioms clean. Thm C (relative completeness ≡ finitely-generated submonoid membership; undecidable in general) is a paper proof by direct L_g reduction, citing Mihailova 1958 / Lohrey–Steinberg 2008 for undecidable submonoid membership WITH decidable word problem (so the frontier is membership, NOT the word problem). Thm D is the 2×2 landscape (P / PSPACE-complete / impossible / undecidable). Conjecture E (dimension-bounded basis foreclosure) is CONJECTURAL: contingent on a basis-to-compression bridge not established here (Doliwa 2014 restricted to maximum classes). Prop F (ASDL coverage) is a decidable engineering invariant; the earlier 'necessary for behavioral completeness' claim is WITHDRAWN. NOTE: the Mihailova / Lohrey–Steinberg citations were corroborated by an external reviewer (2026-08-26; Lohrey–Steinberg transitive-forest characterization confirmed), but a primary-source DOI/venue fetch is still pending for camera-ready. Not peer-reviewed; do not cite as fully proven."
bibliography: "LITERATURE_PI_COMPLETENESS.md (42 sources, verified 2026-08-25)"
---

# The Completeness of Mutation Operators

> **Draft notice.** **Thm A** — finite *absolute* completeness *in P* (A.2) and *relative* completeness
> *PSPACE-complete* (A.3, Kozen 1977), with the rank-3 basis (A.1) machine-checked at its base cases in Lean 4 /
> Mathlib (`T2_generated`, `T3_generated_rank3`; `#print axioms` clean, no `sorryAx`), general $n$ transcribed
> from Gomes–Howie 1987. **Thm B** (infinite-absolute impossibility) is an elementary cardinality argument,
> machine-checked in Lean 4 / Mathlib (`pi_incomplete_infinite`; `#print axioms` clean, no `sorryAx`). **Thm C** —
> relative completeness *is* finitely-generated submonoid membership, hence undecidable in general (direct $L_g$
> reduction; the frontier is membership, **not** the word problem — Mihailova 1958; Lohrey–Steinberg 2008).
> **Thm D** is the 2×2 landscape (P / PSPACE-complete / impossible / undecidable). **Conjecture E** is explicitly
> conjectural — the basis-to-compression bridge it needs is not established here. **Prop F** (ASDL coverage) is a
> decidable invariant, not a logical prerequisite for completeness. Not peer-reviewed; do not cite as fully
> proven. *(Mihailova / Lohrey–Steinberg corroborated in review; primary-source fetch pending for camera-ready.)*

## Abstract

Mutation testing measures a program by whether a covering test suite distinguishes a finite family of
mutation operators — both traditional program-text mutations and *output* (extreme) mutations that perturb the
returned value. Its guarantee is only as strong as the **completeness** of that operator family. Yet mutation
testing has never had a completeness theorem: the field rests on the **coupling-effect hypothesis**
(DeMillo–Lipton–Sayward 1978), an unproven assumption, and its strongest formal results (sufficient operators,
minimal dominator sets) are **basis-** or **test-set-relative** by construction. We show this is not an
oversight but the shadow of a decidability boundary. Modelling an output-operator family $\Pi_R$ as a finite
generating set of the transformation monoid on a codomain type $R$, "is this family complete?" becomes "does
this finite set generate the monoid?" — and the answer is a clean **2×2 landscape**, sorted by *which*
completeness (absolute: generate all of $T(R)$; relative: generate a named target of admissible deviations) and
*where* (finite vs infinite codomain). **Finite, absolute:** decidable in **polynomial time** — a rank
argument, not the PSPACE one might fear — with a constructive size-3 basis ($\operatorname{rank}(T_n)=3$,
Gomes–Howie 1987), base cases machine-checked in Lean. **Finite, relative:** exactly finitely-generated
submonoid membership, hence **PSPACE-complete** (Kozen 1977). **Infinite, absolute:** *impossible* for any
finite family — a one-line cardinality argument (a countable closure cannot equal an uncountable monoid),
machine-checked in Lean. **Infinite, relative:** we show relative completeness *is* the finitely-generated
submonoid-membership problem, **undecidable in general** — and, crucially, its frontier is **membership, not the
word problem**: there are monoids with decidable word problem but undecidable submonoid membership (Mihailova
1958; Lohrey–Steinberg 2008), so word-problem tractability does not buy decidable completeness. Underneath the
whole table sits a hard **ceiling**: because output operators act by post-composition, they can never express a
fault that separates two inputs the correct function identifies — so output-mutation completeness is
completeness for *output recodings*, a strict subspace of behavioral faults. Two further results frame the
practice: a *conjectured* foreclosure of any capacity-dimension-bounded minimal complete basis (contingent on a
teaching/compression bridge we do not prove), and a decidable *syntactic* coverage invariant (operator-totality
over Python's ASDL) that is useful but, we show, neither necessary nor sufficient for the behavioral notion. The
contribution is the recognition that mutation-operator completeness is a transformation-monoid problem —
whole-monoid **generation** for the absolute notion, finitely-generated **submonoid membership** for the
relative one — and that the *gap* between those two objects is exactly the **P vs PSPACE-complete** (finite) and
**impossible vs undecidable** (infinite) structure of the landscape, all under a post-composition ceiling.

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
theory. The landscape is a clean **2×2**, sorted by *which* completeness one asks for (absolute vs relative) and
*where* (finite vs infinite codomain):

| | **absolute** ($\langle\Pi\rangle = T(R)$) | **relative** ($\langle\Pi\rangle \supseteq \mathcal{S}_R$) |
|---|---|---|
| $\lvert R\rvert < \infty$ | **P** (rank argument, §3) | **PSPACE-complete** (Kozen membership, §3) |
| $\lvert R\rvert = \infty$ | **impossible** for finite $\Pi$ (cardinality, §4) | **submonoid-membership-dependent; undecidable in general** (§5) |

The two crucial corrections to the naive "decidable iff finite" picture are the two right-hand cells.
*Absolute* completeness collapses to a clean dichotomy (efficient when finite, impossible when infinite), but
*relative* completeness — the only meaningful notion on an infinite codomain (Thm B) — is precisely the
**finitely-generated submonoid-membership problem**, and its frontier is **membership, not the word problem**:
there exist monoids with decidable word problem yet undecidable submonoid membership (Mihailova 1958;
Lohrey–Steinberg 2008), so a "nice" (confluent/terminating) presentation does *not* by itself make completeness
decidable. Underneath every cell sits a ceiling no amount of operator richness removes: output operators act by
post-composition, so they cannot express faults that separate inputs the correct function collapses. This turns
"we hope our operators are complete" into a precise map of what is achievable, what is efficient, and what is
foreclosed.

### 1.3 Contributions

1. A formalization of $\Pi$-completeness as generation of the codomain transformation monoid, with the
   **post-composition ceiling** made explicit (§2).
2. **Theorem A** — finite-codomain *absolute* completeness is decidable **in P** and constructive (basis size 3,
   base cases machine-checked in Lean); and finite-codomain *relative* completeness is exactly transformation-
   monoid membership, hence **PSPACE-complete** (Kozen 1977) — a genuine P/PSPACE gap between the two notions
   (§3).
3. **Theorem B** — infinite-codomain absolute completeness by a finite family is **impossible** (cardinality),
   machine-checked in Lean (§4).
4. **Theorem C** — relative completeness *is* the finitely-generated **submonoid-membership** problem, hence
   **undecidable** in general, with the frontier at **membership, not the word problem** (Mihailova 1958;
   Lohrey–Steinberg 2008) (§5).
5. **Theorem D** — the 2×2 landscape (P / PSPACE-complete / impossible / undecidable) and the forced,
   honestly-scoped certificate (§6).
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
behavioral fault space $|R|^{D}$ whenever $f$ is non-injective **and $|R| \ge 2$**. *Proof.* Post-composition
applies the same $p$ to equal values $f(x_1)=f(x_2)$, giving equal outputs; with $|R| \ge 2$ pick $r' \neq
f(x_1)$ and a fault $f'$ agreeing with $f$ except $f'(x_1)=r'$, so $f'(x_1)\neq f'(x_2)$ while $f(x_1)=f(x_2)$ —
this $f'$ is therefore not of the form $p\circ f$. (For $|R| = 1$ the space $|R|^{D}$ is a singleton and the
inclusion is not strict — but the ceiling is vacuous there.) $\square$

> This is the honest scope statement for the entire enterprise: output-mutation completeness is completeness
> for *output recodings*, not for arbitrary behavioral faults. Everything below characterizes completeness
> **within** that ceiling; §8 and §9 return to what it means for practice.

**Definition 2.4 (two completeness notions).** Fix a codomain $R$ and family $\Pi_R \subseteq T(R)$.

- **Absolute completeness.** $\Pi_R$ is *absolutely complete* iff $\langle \Pi_R \rangle = T(R)$ — it generates
  the **entire** transformation monoid. This is the strongest available notion, chosen deliberately: a maximal
  assertion is informative precisely where it *fails*, and the place it fails localizes exactly the deviation
  the family cannot express.
- **Relative completeness.** Given *any* submonoid $\mathcal{S}_R \subseteq T(R)$ of *admissible* deviations (the
  perturbations a specification actually deems faults), $\Pi_R$ is *complete relative to $\mathcal{S}_R$* iff
  $\langle \Pi_R \rangle \supseteq \mathcal{S}_R$. Absolute completeness is literally the special case
  $\mathcal{S}_R = T(R)$.

The *definition* of relative completeness is stated for an **arbitrary** submonoid $\mathcal{S}_R$; the
*decision problem* studied below restricts to **finitely-generated** targets, presented by a finite generating
set $\mathcal{S}_R = \langle g_1, \dots, g_m \rangle$ — the representation a specification supplies. Absolute
completeness ($\mathcal{S}_R = T(R)$) is *not* an instance of that decision problem on an infinite carrier,
precisely because $T(R)$ is then **not** finitely generated (Thm B) — consistent with §4, where absolute-
infinite completeness is settled by cardinality, not by a membership algorithm. The distinction from absolute
completeness is not cosmetic: §4 shows absolute completeness is unattainable on infinite carriers, so the
finitely-generated *relative* problem is the *only* meaningful notion there — and it is a different mathematical
object with a different decidability status (§5).

**Remark 2.5 (three distinct notions — do not conflate them).** It is tempting to gloss "generate $T_n$" as
"realize every deviation," but three notions must be kept apart:

- **(i) point-transitivity** — $\forall r,r'\ \exists p \in \langle\Pi\rangle:\ p(r)=r'$;
- **(ii) separation** — $\langle\Pi\rangle$ distinguishes any two admissible behaviors under a fixed oracle;
- **(iii) generation** — $\langle\Pi\rangle = T(R)$, i.e. absolute completeness.

These are genuinely distinct, and in particular **(i) does not imply (iii):** the regular action of the cyclic
group $C_n$ on $n$ points is point-transitive (for any $r,r'$ some rotation sends $r$ to $r'$) yet contains only
$n$ permutations, nowhere near the $n^n$ maps of $T_n$. So "realize every deviation" (point-transitivity) is
strictly weaker than generation, and the intuitive gloss on absolute completeness is *not* an equivalence. (We
state (i)–(iii) as three notions rather than a formal chain of set inclusions, since "separation" is oracle-
relative and not pinned down here; the strict separation (i) $\neq$ (iii) is the one we use.) Absolute
completeness (Def 2.4) is (iii), the strongest; §3's basis is a *generating* set, and §7/§11's open question is
about the minimal *separating* set (ii), a genuinely distinct problem.

**Remark 2.6 (why the monoid).** This is the output-operator instance of the standing **operator-basis /
sufficiency** question of mutation testing: "does a finite operator family span the faults it is meant to
detect?" For the codomain, the perturbations at a point form $T(R)$ acting on $|R|$, so "span the (admissible)
deviation space" is literally "generate (enough of) $T(R)$" — a generation problem in a transformation monoid,
which is where the classical decidability results live.

---

## 3. The finite-codomain fragment: absolute completeness in P, relative completeness PSPACE-complete

Throughout this section transformations on $[n]$ are represented explicitly by their **$n$-entry value tables**
(the input model a mutation tool actually holds); complexity is measured against that representation, not a
succinct circuit encoding.

**Theorem A (finite-codomain completeness).** Let $R$ be a finite codomain, $|R| = n$.

1. *(constructive basis)* An absolutely complete $\Pi_R$ exists with $|\Pi_R| = 3$: a transposition, an
   $n$-cycle, and one rank-$(n-1)$ idempotent generate $T_n$; i.e. $\operatorname{rank}(T_n) = 3$ for $n \ge 3$.
2. *(absolute, in P)* For $n \ge 2$, deciding whether a given finite $\Pi_R$ is *absolutely* complete
   ($\langle \Pi_R \rangle = T_n$) is **decidable in polynomial time**. (The case $n = 1$ is trivial:
   $T_1 = \{\mathrm{id}\}$, so *every* $\Pi_R$ — including $\Pi_R = \varnothing$ — is absolutely complete.)
3. *(relative, PSPACE-complete)* Deciding whether $\Pi_R$ is complete *relative* to a finitely-generated target
   $\mathcal{S}_R = \langle g_1, \dots, g_m \rangle$ (i.e. $\langle \Pi_R \rangle \supseteq \mathcal{S}_R$) is
   **PSPACE-complete**.

*Proof of A.1 (constructive basis).* By Gomes & Howie (1987, Math. Proc. Camb. Phil. Soc. 101(3):395–403),
$\operatorname{rank}(T_n) = 3$ for $n \ge 3$: an $n$-cycle and a transposition generate the symmetric group
$S_n$ (rank $2$), and adjoining a single map of rank $n-1$ (a non-injective idempotent collapsing one pair)
generates every element of $T_n$ — any $f \in T_n$ of rank $r$ factors as a permutation, a product of $n-r$
rank-lowering maps (each a conjugate of the adjoined idempotent by a permutation), and a permutation. For
$n \le 2$ the count is smaller ($\operatorname{rank}(T_1)=0$ — under the submonoid convention $T_1 = \{\mathrm{id}\}$
is generated by the empty family — and $\operatorname{rank}(T_2)=2$). The generation is
**machine-checked at the base cases** in Lean 4 / Mathlib: `T2_generated` (the successor and constant-$0$ maps
generate $T_2$) and `T3_generated_rank3` (a $3$-cycle, a transposition, and a rank-$2$ idempotent generate all
$27$ elements of $T_3$) are fully proven, no `sorry` (`proofs/T2_generated.lean`,
`proofs/T3_generated_rank3.lean`), each discharging the enumeration by `decide` over the finite monoid. The
general $n$ is the cited classical result. $\square$ *[`#print axioms` clean — see §12; the general statement
is transcribed from Gomes–Howie, not re-proven.]*

*Proof of A.2 (decidability in P).* Take $n \ge 2$ (for $n = 1$, $T_1 = \{\mathrm{id}\}$ and every $\Pi_R$ is
absolutely complete — decidable in constant time). We do **not** compute the closure (which can reach $n^n$
elements). The key
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

*Proof of A.3 (relative completeness is PSPACE-complete).* By Def 2.4, $\langle \Pi_R \rangle \supseteq
\mathcal{S}_R$ iff every generator $g_i \in \langle \Pi_R \rangle$ — a finite conjunction of
**transformation-monoid membership** queries "$g \in \langle \Pi_R \rangle$?". Kozen (1977, FOCS, *Lower bounds
for natural proof systems*) proves exactly this membership problem PSPACE-complete for transformations of a
finite set. **Membership (PSPACE):** guess the word one generator at a time, maintaining the running composite
(an $n$-entry table) and a **binary step-counter capped at $n^n$**. The bound is sound: the reachable set
$\{\mathrm{id}\} \subseteq S_1 \subseteq S_2 \subseteq \dots$ is monotone in the finite lattice of subsets of
$T_n$ ($n^n$ elements), so it stabilizes within $n^n$ steps and every reachable element — in particular $g$, if
$g \in \langle \Pi_R \rangle$ — is realized by a word of length $< n^n$. The counter costs $O(\log n^n) =
O(n \log n)$ bits and the composite $O(n \log n)$ bits, so the whole nondeterministic search runs in polynomial
space; $\mathrm{PSPACE} = \mathrm{NPSPACE}$ (Savitch), and a conjunction of $m$ such queries stays in PSPACE.
**Hardness:** a single membership instance "$g \in \langle \Pi_R \rangle$?" is the relative-completeness
instance with $\mathcal{S}_R = \langle g \rangle$, so Kozen's lower bound transfers verbatim. Hence relative
completeness is PSPACE-complete. $\square$

**Corollary A.4 (finite completeness certificate is absolute — and cheap).** On a finite codomain, "$\Pi_R$ is
*absolutely* complete" is a decidable, absolute predicate, computable in polynomial time — no basis-relativity,
no observing-set qualifier, and no exponential closure.

**Remark 3.1 (a genuine P/PSPACE gap between the two notions).** The two completeness notions of Def 2.4 have
*different complexity* on the very same finite codomain: *absolute* completeness is in **P** (A.2), because
"generate the whole monoid" has structure the rank argument exploits and never touches the exponential closure;
*relative* completeness is **PSPACE-complete** (A.3), because "generate this presented target" is general
transformation-monoid membership (Kozen 1977), which has no such shortcut. This gap is the finite shadow of the
§5 phenomenon — the difference between recognizing a whole object and recognizing membership in a presented
subobject is exactly what re-emerges, off the finite fragment, as the difference between the (trivial)
cardinality obstruction and the (undecidable) submonoid-membership problem.

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
> machine-verifiable corners of the landscape (§6) are now proven** — the finite basis (top-left) and this
> infinite-absolute impossibility (bottom-left); the relative cells are the cited paper proofs.

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

## 5. Relative completeness *is* submonoid membership — undecidable, and the frontier is membership, not the word problem

**Theorem C (relative completeness $\equiv$ finitely-generated submonoid membership; undecidable in general).**
Let $R$ be a codomain with infinite carrier and $\mathcal{S}_R = \langle g_1, \dots, g_m \rangle$ a
finitely-generated target of admissible deviations. Then:

1. *(equivalence)* Relative completeness and finitely-generated submonoid membership are **polynomial-time
   Turing equivalent** (Cook). $\langle \Pi_R \rangle \supseteq \mathcal{S}_R$ iff $g_i \in \langle \Pi_R \rangle$
   for every $i$ — relative completeness reduces to a polynomial number ($m$) of membership queries; and
   conversely a single membership instance $g \in \langle \Pi_R \rangle$ is the relative-completeness instance
   $\mathcal{S}_R = \langle g \rangle$, a **many-one (Karp)** reduction the other way.
2. *(undecidability)* Relative completeness is **undecidable** in general: there is a structured codomain and a
   family for which no algorithm decides $\langle \Pi_R \rangle \supseteq \mathcal{S}_R$.
3. *(the frontier is membership, not the word problem)* Undecidability here is **not** controlled by the word
   problem of the codomain's presentation. There exist monoids/groups with **decidable word problem but
   undecidable finitely-generated submonoid membership** (Mihailova 1958; Lohrey–Steinberg 2008); a
   confluent/terminating presentation gives decidable *equality of represented elements*, not decidable
   *membership*. So neither carrier-cardinality nor word-problem tractability settles completeness.

*Proof of C.1 (equivalence).* Immediate from Def 2.4 and the definition of a generated submonoid:
$\langle \Pi_R \rangle$ is a submonoid, so it contains $\mathcal{S}_R = \langle g_1, \dots, g_m \rangle$ iff it
contains each generator $g_i$; the converse instance is the singleton target $\mathcal{S}_R = \langle g \rangle$.
$\square$

*Proof of C.2 (undecidability, by direct reduction).* Take a finitely generated monoid $G$ whose
finitely-generated **submonoid-membership problem is undecidable** — given $g, x_1, \dots, x_k \in G$, deciding
$g \in \langle x_1, \dots, x_k \rangle$ admits no algorithm. Such $G$ exist *with decidable word problem*:
Lohrey–Steinberg (2008) give undecidable finitely-generated submonoid membership in **graph groups** (right-
angled Artin groups) whose word problem is decidable, and Mihailova (1958) already gives undecidable
finitely-generated *subgroup* membership in $F_2 \times F_2$, a group with decidable word problem (in a group a
finitely-generated subgroup is a finitely-generated *submonoid* once the inverses of its generators are
adjoined, so subgroup membership is a special case of the submonoid problem we need). Let the
codomain be $R = G$ and represent each $h \in G$ by its **left translation** $L_h : R \to R,\ L_h(x) = h \cdot
x$. This representation is a *faithful* monoid homomorphism $G \hookrightarrow T(R)$: $L_{h h'} = L_h \circ
L_{h'}$, and $L_h(1_G) = h$ so $L_h = L_{h'} \Rightarrow h = h'$ (injective). Given a submonoid-membership
instance $g \in^? \langle x_1, \dots, x_k \rangle$, set
$$ \Pi := \{ L_{x_1}, \dots, L_{x_k} \}, \qquad \mathcal{S}_R := \langle L_g \rangle. $$
Because $h \mapsto L_h$ is an injective homomorphism,
$$ \mathcal{S}_R \subseteq \langle \Pi \rangle \iff L_g \in \langle L_{x_1}, \dots, L_{x_k} \rangle \iff
g \in \langle x_1, \dots, x_k \rangle. $$
A decision procedure for relative completeness would therefore decide submonoid membership in $G$ — impossible.
The reduction is uniform in the instance, giving undecidability across the class. $\square$

**Remark 5.1 (why membership, not the word problem — and why that is the *right* invariant).** The earlier
reflex — "undecidability comes from the word problem, so a confluent/terminating presentation restores
decidability" — is wrong, and correcting it sharpens the result. The relative-completeness predicate literally
*is* submonoid membership (C.1), and membership is strictly harder than equality: Mihailova's $F_2 \times F_2$
has a decidable (indeed linear) word problem, being a direct product of free groups, while finitely-generated
subgroup membership in it is undecidable; Lohrey–Steinberg place the same gap at the *submonoid* level for graph
groups. Confluence/termination decides whether two words denote the same element; it says nothing about whether
an element lies in an arbitrary finitely-generated submonoid. So the honest frontier for relative completeness
is the **decidability of finitely-generated submonoid membership** in the codomain monoid — an invariant that
refines both "finite vs infinite carrier" and "word problem solvable vs not." (Bounded instances — lists of
length $\le k$ over a finite base — are finite and fall under Theorem A; the undecidability is a property of the
*unbounded* type, never of a concrete input.)

**Remark 5.2 (relation to equivalent-mutant detection — non-load-bearing).** The classical undecidability of
equivalent-mutant detection (Budd–Angluin 1982), a corollary of Rice's theorem (1953), is the
*program-semantics* shadow of this obstruction: one cannot decide whether a specific perturbed program is
behaviorally equal to the original. Our reduction is sharper and self-contained — it does **not** route through
Rice (which would require identifying the precise program-index property to which Rice applies), but through the
exact combinatorial object the relative-completeness predicate denotes, submonoid membership. We record the
connection but do not rely on it.

---

## 6. The 2×2 landscape and the honest certificate

**Theorem D (the completeness landscape).** For output-operator completeness under Def 2.4, sorted by notion
(absolute vs relative) and carrier (finite vs infinite):

| | **absolute** ($\langle\Pi\rangle = T(R)$) | **relative** ($\langle\Pi\rangle \supseteq \mathcal{S}_R$) |
|---|---|---|
| $\lvert R\rvert < \infty$ | **P** — rank argument, size-3 basis (Thm A.1–A.2, Cor A.4) | **PSPACE-complete** — transformation-monoid membership, Kozen 1977 (Thm A.3) |
| $\lvert R\rvert = \infty$ | **impossible** for finite $\Pi$ — cardinality (Thm B) | **undecidable in general** — $\equiv$ f.g. submonoid membership (Thm C) |

*Proof.* Direct assembly: the finite row is Theorem A (A.2 absolute in P; A.3 relative PSPACE-complete); the
infinite–absolute cell is Theorem B (+ Cor B.1); the infinite–relative cell is Theorem C. $\square$

Two features of the table carry the paper. **(a)** There is a genuine **P vs PSPACE-complete** gap *within the
finite row* — recognizing whole-monoid generation is easy, recognizing membership in a presented target is not
— and this is the finite shadow of **(b)** the infinite row's **impossible vs undecidable** split: absolute
completeness fails by counting (trivial, Thm B), while relative completeness *is* submonoid membership and
inherits its undecidability, with the frontier at **membership, not the word problem** (Thm C.3). The naive
"decidable iff finite" picture is wrong in exactly the two right-hand cells.

Consequently a completeness **certificate** is: **absolute and efficiently decidable** only on the
finite-codomain fragment (top-left); **PSPACE-complete** to check against a presented target even when finite
(top-right); and on an infinite codomain necessarily **relative** — "complete over the operator family $\Pi$ and
the named admissible target / observing oracle," never over the full behavioral space — and, even so, decidable
only when the codomain monoid's finitely-generated submonoid membership is (bottom-right).

**Remark 6.1 (name which cell you are in).** Theorem D dictates the honest response for any mutation-based tool:
a certificate must state which cell it is in. Claiming *absolute* completeness on an infinite codomain is the
overclaim the table forbids (Thm B makes it not merely unproven but false); reporting "complete over the
operator family $\Pi$, admissible target and observing set named" is exactly correct. A residual survivor a
finite family does not distinguish is therefore reported *unproven*, never promoted to *equivalent* — the
correct disposition, forced by the landscape, not a tool limitation. And beneath every cell, Proposition 2.3's
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
all acceptable), the target is a *list* concept — precisely Hanneke–Moran–Waknine (2024)'s setting. So a
**general nonbinary** software fault space is multiclass, and a **set-valued** specification additionally enters
the list-valued regime — exactly the two regimes the cited impossibilities foreclose. (Boolean-returning
functions are the genuine binary exception, $|R|=2$, where a VC-dimension bound might survive; the claim is
about nonbinary codomains, which is the generic case.) $\square$

**Remark 7.1 (the honest positive reading).** What survives unconditionally: a general nonbinary / set-valued
fault space is multiclass/list (Lemma D.a), and in that regime the *general* learning-theoretic hope for a
capacity-dimension-bounded minimal object is already foreclosed *for compression schemes and teaching sets*
(Pabbaraju; HMW). What is conjectural is only the transport of that foreclosure onto *operator generating bases*
via a bridge we have flagged. Either way, completeness is safest stated basis-relative (Thm D), not
dimension-bounded.

---

## 8. Syntactic operator coverage: a decidable invariant (not a completeness criterion)

Off finite codomains, absolute completeness is trivially settled (impossible, Thm B) and *relative* completeness
is undecidable in general (Thm C); a *syntactic* coverage check is decidable, and it is the honest thing a tool
can actually run — provided it is not oversold as a completeness criterion.

**Proposition F (ASDL operator-coverage).** Let a language's abstract syntax be finitely specified (Python's
ASDL: a finite set of node kinds and fields). Define $\Pi$ **syntactically total** iff it assigns a
mutation/perturbation to every node kind (and, for the codomain, every base type of the observed return
grammar). Then:

1. *(decidable)* syntactic totality is decidable — a finite coverage check against the ASDL, linear in its size;
2. *(not sufficient)* it does **not** entail behavioral completeness: separate the program-text family
   $\Pi_{\text{text}}$ (the AST-dispatch operators the criterion counts) from the codomain family $\Pi_{\text{out}}$
   (Def 2.4). A dispatch table can be syntactically total — an operator for *every* node kind — while
   $\Pi_{\text{out}}$ fails even point-transitivity (Rem 2.5(i)), let alone generation. So syntactic totality
   says nothing sufficient about Def 2.4 completeness absent an explicit bridge relating the two families. (The
   empirical grammar-coverage vs code-coverage Spearman $\approx 0.9478 < 1$ — Havrikov & Zeller 2019; The
   Fuzzing Book — corroborates the gap but is not the argument.)
3. *(not necessary for the codomain notion)* it is **not** necessary for output-operator completeness (Def 2.4):
   by Theorem A, three output operators are absolutely complete on a $3$-element codomain while mutating **no**
   AST node whatsoever. Syntactic coverage is a coverage invariant over *program-text* operators, a different
   family from the codomain operators completeness (Def 2.4) is about.

*Proof.* (1) The ASDL is finite; membership "$\Pi$ assigns a perturbation to every node kind" is a finite check.
(2) Take any $\Pi_{\text{text}}$ that hits every ASDL node kind (syntactically total) paired with a
$\Pi_{\text{out}}$ that is not point-transitive on $R$ — e.g. $\Pi_{\text{out}} = \{\mathrm{id}\}$, whose
generated submonoid realizes *no* nontrivial deviation. This instance is syntactically total yet
behaviorally incomplete under Def 2.4, so totality is not sufficient; the two families are logically
independent without a bridge. (Note the naive backstop "a decidable criterion cannot entail an undecidable
property" is *invalid* — a decidable sufficient condition can imply an undecidable one — which is why we give an
explicit counterexample instead.) (3) Theorem A exhibits an absolutely complete output family with empty AST
coverage, so coverage is not necessary for Def 2.4 completeness. $\square$

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
  and even that is decidable only when the codomain monoid's finitely-generated submonoid membership is (Thm C).
  Treat an undistinguished survivor as *unproven*, never *equivalent* (Rem 6.1).
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
membership complexity, Kozen 1977 — PSPACE-complete, our finite relative cell); the undecidability wall is
**finitely-generated submonoid membership**: Mihailova 1958 (undecidable f.g. subgroup membership in
$F_2\times F_2$, decidable word problem) and Lohrey–Steinberg 2008 (undecidable f.g. submonoid membership in
graph groups, decidable word problem) — the results that show the frontier is membership, not the word problem;
Rice 1953 / Budd–Angluin 1982 (equivalent-mutant detection, our non-load-bearing Rem 5.2) and the
Luckham–Park–Paterson 1970 schema-equivalence boundary are the classical precedents for the decidability
*form*. Learning theory supplies the (conjectural) foreclosure ingredients (Doliwa 2014 — restricted to maximum
classes; Moran–Yehudayoff 2015; Pabbaraju 2024; Hanneke–Moran–Waknine 2024); grammar-coverage supplies the
syntactic side (Purdom 1972; Havrikov–Zeller 2019 / The Fuzzing Book's sub-unity correlation).

---

## 11. Open problems

1. **The minimal separating set (Rem 2.5, 3.2).** For the separation task under a fixed oracle (Rem 2.5(ii),
   distinct from the strong generating-set completeness A.1 fixes at 3), characterize the minimal *separating*
   $\Pi_R$ on a finite codomain — always $\le 3$, or task-dependent?
2. **Decidable structured sub-fragments (Thm C.3).** Which codomain monoids have *decidable finitely-generated
   submonoid membership* (e.g. commutative/trace monoids, or graph groups whose defining graph avoids the
   Lohrey–Steinberg obstruction), and thus decidable relative completeness? — note this is the *membership*
   question, strictly finer than word-problem decidability.
3. **The exact reduction target for Theorem C.** Which monoid with undecidable finitely-generated submonoid
   membership embeds most cleanly (via left translations) into a Python structured codomain (lists? dicts?
   dataclasses)? A concrete embedding of a specific Lohrey–Steinberg / Mihailova instance is the natural next
   Lean artifact.
4. **The basis-to-compression bridge (Conj E).** Is a minimal complete *generating* basis reducible to a
   sample-compression scheme / teaching set beyond maximum classes? Establishing (or refuting) this converts
   Conjecture E into a theorem (or retires it).
5. **NCTD ≤ VCD** (external, load-bearing for any future dimension bound): still open after the withdrawn 2026
   proof.

---

## 12. Status ledger

*Proof strategy. The finite constructive fragment (Thm A.1) is machine-checked in Lean 4 / Mathlib on concrete
generation witnesses; the finite decidability/complexity (A.2 in P, A.3 PSPACE-complete) and the infinite
impossibility (Thm B, also machine-checked) rest on the rank argument, Kozen 1977, and a cardinality count; the
relative-undecidability (Thm C) is a paper proof by direct reduction from finitely-generated submonoid
membership, whose undecidability (with a decidable word problem) is the cited Mihailova 1958 / Lohrey–Steinberg
2008 — not in Mathlib and not re-formalized. Conjecture E is explicitly conditional on an unproven bridge.*

| Result | Kind | Proof form | Status |
|---|---|---|---|
| **Thm A.1 (n=2): `T2_generated`** | concrete constructive witness | **Lean 4 / Mathlib** | ✅ proven, no `sorry`; `#print axioms` = `[propext, Classical.choice, Quot.sound]` |
| **Thm A.1 (n=3, rank 3): `T3_generated_rank3`** | concrete constructive witness | **Lean 4 / Mathlib** | ✅ proven, no `sorry`; `#print axioms` = `[propext, Classical.choice, Quot.sound]` |
| Thm A.1 (general $\operatorname{rank}T_n=3$) | inherited (Gomes–Howie 1987) | paper §3 (cite) | ✍ written; n=2,3 are the machine-checked instances |
| Thm A.2 (finite **absolute** decidability **in P**) | rank argument + Schreier–Sims | paper §3 proof | ✍ written (upgrades the earlier PSPACE claim to P) |
| Thm A.3 (finite **relative** = **PSPACE-complete**) | monoid membership (Kozen 1977) | paper §3 proof | ✍ written (membership PSPACE; hardness by singleton-target reduction) |
| Prop 2.3 (post-composition ceiling) | elementary | paper §2 | ✅ proven (one line) |
| **Thm B (infinite impossibility): `pi_incomplete_infinite`** | **cardinality**, machine-checked | **Lean 4 / Mathlib** + paper §4 | ✅ proven, no `sorry`; `#print axioms` = `[propext, Classical.choice, Quot.sound]` (no `sorryAx`) — replaces "undecidable off finite" |
| Thm C.1 (relative $\equiv$ f.g. submonoid membership) | definitional equivalence | paper §5 | ✅ proven (immediate) |
| Thm C.2 (relative undecidability) | **direct $L_g$ reduction** from f.g. submonoid membership | **paper proof §5** | ✍ written (cites Mihailova 1958; Lohrey–Steinberg 2008 for undecidable submonoid membership w/ decidable word problem) |
| Thm C.3 (frontier = membership, not word problem) | corollary of C.1–C.2 + cited gap | paper §5 | ✍ written (corrects the earlier "boundary = presentation") |
| Thm D (2×2 landscape: P / PSPACE-c / impossible / undecidable) | assembly of A+B+C | paper §6 | ✍ written |
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
Quot.sound]`, **no `sorryAx`**) — so **both machine-verifiable corners of the landscape are proven**: the
finite constructive basis (top-left) and the infinite-absolute impossibility (bottom-left). The umbrella
`operator_completeness.lean` carries **statements only**: the finite-decidability `instance` is a signature stub
(the proof is the P-time algorithm of §3, Thm A.2, not a Lean term), and the file records **one cited classical
fact as an axiom** — the undecidability of extensional equality of $\mathbb{N} \to \mathbb{N}$ functions, the
Rice-flavored ingredient behind the *non-load-bearing* Remark 5.2. That axiom is **not** the proof of Thm C: the
undecidability reduction (§5) is the direct $L_g$ embedding of finitely-generated submonoid membership, a paper
proof citing Mihailova 1958 / Lohrey–Steinberg 2008 (results not in Mathlib). The honest summary: the two
left-column corners (Thm A.1 basis, Thm B impossibility) are machine-checked and axiom-clean; the finite
complexity (A.2 P, A.3 PSPACE-complete), the relative undecidability (Thm C), and everything else are paper
proofs or (for Conj E) an open conjecture.

**Provenance.** The gap this paper fills was confirmed by a source-verified literature review (42 sources,
`LITERATURE_PI_COMPLETENESS.md`). The algebraic and computability results are classical and cited; the recasting
of output-operator completeness as monoid generation, the 2×2 landscape (Thm D), the P-time finite absolute
recognition (Thm A.2) and the P/PSPACE-complete gap against the relative notion (Thm A.3), the cardinality
impossibility (Thm B), the relative-completeness $\equiv$ submonoid-membership identification (Thm C), and the
post-composition ceiling (Prop 2.3) are this paper's contributions. Register: *fully proven and audited* on the
machine-checked corners (Thm A.1 basis, Thm B impossibility) and the elementary results (Prop 2.3, Lemma D.a);
*rigorous paper proof* on the finite complexity (A.2/A.3) and Thm C; *conjectural* on E. Not peer-reviewed.
