---
title: "What a Mutation Score Certifies"
subtitle: "Adequacy-completeness for output-mutation operators: a footprint characterization, the value-guard basis, and the coupling effect as a corollary"
author: 
date: 
status: "DRAFT — self-contained, and MACHINE-CHECKED end to end (from programs, not merely footprints). The main characterization (Thm 3.2) and every consequence (Cor 4.1, Cor 4.2, ceiling Thm 4.4, coupling Thm 6.1, subsumption Prop 7.1, detection factoring Prop 7.2, teaching dimension Thm 8.1), AND the program↔footprint bridge (Prop 2.4 formal, realizability, and Thm 3.2 restated over real programs f : D → R and finite suites) are fully proven in Lean 4 / Mathlib (no sorry), every theorem #print-axioms clean ([propext, Classical.choice, Quot.sound], no sorryAx) — see proofs/adequacy_completeness.lean. Results are elementary; the contribution is the definition and its structure. Not peer-reviewed."
bibliography: "LITERATURE_PI_COMPLETENESS.md"
---

# What a Mutation Score Certifies

> **Draft notice.** All results are elementary; none is deep, and that is the point — the contribution is a
> *definition* (completeness measured by what a kill certifies, program- and suite-independently) and the clean
> structure that falls out of it. **The main theorem (Thm 3.2), every consequence, and the full bridge down to
> real programs `f : D → R` and finite suites are machine-checked in Lean 4 / Mathlib**
> (`proofs/adequacy_completeness.lean`, no `sorry`, every theorem `#print axioms` clean, no `sorryAx`) — so the
> definition's structure is auditable to the kernel end to end. Not peer-reviewed.

## Abstract

Mutation testing certifies a program by the fraction of a fixed family of *mutant* programs its test suite
distinguishes; a score of $1$ is read as evidence that the suite is adequate. But adequate *for what*? The field
has never had a completeness theorem for its operators, and its strongest formal results — sufficient operator
sets, minimal mutant sets, mutant subsumption — are relative to a fixed program text or a fixed test suite by
construction. We give a completeness notion that is neither. Restricting to **output mutation** (perturb the
returned value — extreme/Descartes-style mutation), we observe that for adequacy purposes an output operator is
exactly its **footprint** $\mathrm{Mov}(p) = \{r : p(r) \neq r\}$: equivalence and killing both depend only on
where $p$ moves values, never on where it sends them. Calling an operator family $\Pi$ **adequacy-complete for a
target family $\Gamma$** iff *for every program and every suite, killing all non-equivalent $\Pi$-mutants forces
killing all non-equivalent $\Gamma$-mutants*, we prove an exact characterization (Thm 3.2): $\Pi$ is complete for
$\Gamma$ iff every target footprint is the union of the $\Pi$-footprints it contains. Consequences: (i) on a
finite codomain of $n$ values the minimal absolutely-complete family has size **exactly $n$** — the *value
guards* "if the result is $r$, return something else" — and Descartes-style constants are complete iff $n = 2$,
so extreme mutation is provably optimal on Booleans and provably deficient beyond; (ii) an absolute score of $1$
certifies **exactly output coverage** (the suite exercises every value the program can produce) and nothing more
— the operational ceiling of output mutation; (iii) the **coupling effect** for output mutation is a *theorem*,
not a hypothesis: any absolutely-complete first-order family also kills every higher-order output mutant; (iv)
relative completeness is decidable exactly when footprint containment is (polynomial for value tables, decidable
for semilinear footprints, undecidable for arbitrary program-defined footprints) — a spectrum that runs through
*set containment*, not group-theoretic word problems; and (v) output-mutant detection *factors through the
footprint*, $\mathrm{Det}(p \circ f) = f^{-1}(\mathrm{Mov}(p))$, which is why output-operator completeness can be
stated program-independently while program-text completeness cannot. Finally the minimum suite that certifies
completeness equals the number of distinct reachable outputs (§8), the teaching dimension of the program against
the operator family. The picture is elementary; its value is that every claim is about what a passing mutation
score actually guarantees.

---

## 1. Introduction

### 1.1 The gap

Mutation testing (DeMillo, Lipton & Sayward 1978; Hamlet 1977) seeds a program with small faults — *mutants* —
and measures a test suite by the fraction it *kills* (distinguishes from the original). A **mutation score of
$1$** is the field's adequacy certificate. Its strength rests entirely on the **operator family**: the score
certifies the suite against *the faults the operators can express*, and no more. Two questions have never been
answered cleanly:

- **What does a score of $1$ certify?** Not "the program is correct" — only that no seeded fault survived. The
  bridge from "no seeded fault survives" to "no real fault survives" is the **coupling-effect hypothesis**
  (DeMillo–Lipton–Sayward 1978) and the **competent-programmer hypothesis** — stated as motivating assumptions,
  never proven.
- **When is an operator family complete?** The strongest prior results are relative by construction:
  *sufficient* operator sets (Offutt et al. 1996) are determined experimentally against a full operator pool;
  *minimal* mutant sets and *dominator* mutants (Ammann, Delamaro & Offutt 2014) are minimal relative to a fixed
  test set and an already-generated pool; and *true* (semantic) mutant subsumption — the order a completeness
  theorem would rank against — is **undecidable** (Kurtz, Ammann & Offutt 2015).

The relativity is not incidental; it is forced by the object. A program-text mutation *schema* has no
operator-only invariant that fixes its detection behaviour uniformly across source programs — the mutant it
produces depends on the *text* of $f$, not on $f$ as a function — so "does schema $X$ subsume schema $Y$" has no
program-independent answer (§7). Output mutation is the sub-class that does admit such an invariant, which is
what makes a program-independent completeness notion available for it.

### 1.2 The thesis

We restrict to **output mutation**: operators that perturb the *returned value* of a function, independent of
how the function computes it (extreme mutation — replacing a body with `return c`, à la Descartes; Niedermayr et
al. 2016; Vera-Pérez et al. 2018 — is the special case of constant output operators). For this class we define
completeness by **what a kill certifies**, uniformly over all programs and all suites:

> $\Pi$ is *adequacy-complete for $\Gamma$* iff, for every program and every suite, a mutation score of $1$
> against $\Pi$ forces a mutation score of $1$ against $\Gamma$.

This is program-independent and suite-independent by fiat — the two relativities of the prior results are
quantified away. The definition turns out to be governed by a single combinatorial object, the **footprint** of
an operator (where it moves values), and everything else in the paper is a consequence of one characterization
theorem about footprints.

### 1.3 Contributions

1. The **footprint reduction** (§2): for adequacy, an output operator *is* its footprint — equivalence and
   killing depend only on $\mathrm{Mov}(p)$.
2. The **characterization theorem** (§3, Thm 3.2): $\Pi$ is adequacy-complete for $\Gamma$ iff every target
   footprint is the union of the $\Pi$-footprints contained in it.
3. The **value-guard basis** (§4): on $n$ values the minimal absolutely-complete family has size exactly $n$;
   Descartes constants are complete iff $n = 2$ (extreme mutation optimal on Booleans, deficient beyond).
4. The **ceiling with content** (§4): an absolute score of $1$ certifies *exactly* output coverage.
5. The **coupling effect as a corollary** (§6): completeness $\Rightarrow$ higher-order output mutants all die.
6. The **decidability spectrum via set containment** (§5) and the **program-independent subsumption factoring**
   (§7).
7. The **teaching-dimension reading** (§8): the minimum certifying suite has size $|f(D)|$.

---

## 2. Preliminaries: programs, suites, and footprints

**Definition 2.1 (program, suite, output operator).** A program computes a total function — its *denotation* —
$f : D \to R$ from an input domain $D$ to a codomain (return type) $R$ with $|R| \ge 2$. A *test suite* is a
finite $T \subseteq D$. An *output operator* is a total map $p : R \to R$; it produces the *mutant* $p \circ f$
(run the program, then apply $p$ to the result — the post-composition an output/extreme mutation performs). An
*output-operator family* $\Pi$ is a set of output operators.

**Definition 2.2 (footprint).** The *footprint* of an output operator $p$ is
$$ \mathrm{Mov}(p) = \{\, r \in R : p(r) \neq r \,\} \subseteq R, $$
the set of values $p$ actually changes. Write $I = f(D) \subseteq R$ for the program's **reachable** outputs and
$O = f(T) \subseteq I$ for the suite's **observed** outputs.

**Definition 2.3 (equivalence, killing, score).** For a program $f$ and suite $T$:

- $p \circ f$ is **equivalent** to $f$ iff $p(f(x)) = f(x)$ for all $x \in D$;
- $T$ **kills** $p \circ f$ iff $p(f(x)) \neq f(x)$ for some $x \in T$;
- the **score** $\mathrm{score}_\Pi(f, T) = 1$ iff $T$ kills every non-equivalent mutant $p \circ f$, $p \in \Pi$.

**Proposition 2.4 (the footprint reduction — an operator is its footprint).** For any program $f$, suite $T$,
and operator $p$:
$$ p \circ f \text{ is equivalent} \iff \mathrm{Mov}(p) \cap I = \varnothing, \qquad
T \text{ kills } p \circ f \iff \mathrm{Mov}(p) \cap O \neq \varnothing. $$
Consequently, for fixed $(f, T)$, whether $p$ is a non-equivalent survivor depends **only** on
$\mathrm{Mov}(p)$; two operators with equal footprints are interchangeable, and $\mathrm{score}_\Pi(f, T)$ depends
only on the set of footprints $\{\mathrm{Mov}(p) : p \in \Pi\}$.

*Proof.* $p \circ f$ is equivalent iff $p$ fixes $f(x)$ for every $x \in D$, i.e. $p$ fixes every element of
$I = f(D)$, i.e. no element of $I$ is moved: $\mathrm{Mov}(p) \cap I = \varnothing$. $T$ kills $p \circ f$ iff
some $x \in T$ has $p(f(x)) \neq f(x)$, i.e. $f(x) \in \mathrm{Mov}(p)$ for some $x \in T$, i.e.
$\mathrm{Mov}(p) \cap f(T) = \mathrm{Mov}(p) \cap O \neq \varnothing$. Both conditions read only $\mathrm{Mov}(p)$
against the fixed sets $I, O$. $\square$

**Remark 2.5 (every subset is a footprint).** For $|R| \ge 2$, every $S \subseteq R$ is the footprint of some
output operator. Fix two distinct values $a \neq b$ and let $q(a) = b$, $q(x) = a$ for $x \neq a$; then $q$ is
fixed-point-free (it never returns its input), and $p(x) := q(x)$ for $x \in S$, $p(x) := x$ otherwise has
$\mathrm{Mov}(p) = S$. (We use this explicit map rather than "an $|R|$-cycle": a single cyclic permutation only
covers a *countable* orbit under integer iteration, so it cannot be fixed-point-free on an uncountable $R$ — the
swap-to-$a$ map has no such defect.) So the footprints range over the *entire* powerset $2^R$, and — by Prop 2.4
— the adequacy content of an operator family $\Pi$ is exactly the set
$\mathrm{Foot}(\Pi) = \{\mathrm{Mov}(p) : p \in \Pi\} \subseteq 2^R$. Where operators send the values they move
is adequacy-invisible; this is the seed of every result below. *(Formalized as `mov_surjective` — see §13.)*

---

## 3. Adequacy-completeness and the footprint characterization

**Definition 3.1 (adequacy-completeness).** Let $\Pi$ and $\Gamma$ be output-operator families. $\Pi$ is
**adequacy-complete for $\Gamma$** iff for *every* program $f : D \to R$ and *every* finite suite $T \subseteq D$,
$$ \mathrm{score}_\Pi(f, T) = 1 \ \Longrightarrow\ \mathrm{score}_\Gamma(f, T) = 1. $$
$\Pi$ is **absolutely complete** iff it is complete for $\Gamma = T(R)$, the family of *all* output operators.
By Prop 2.4 this depends only on $\mathrm{Foot}(\Pi)$ and $\mathrm{Foot}(\Gamma)$; the quantifier over all $(f,T)$
removes both the program-text and the test-suite relativity of prior completeness notions.

**Theorem 3.2 (footprint characterization).** Let $\Pi$ be **finite**. Then $\Pi$ is adequacy-complete for
$\Gamma$ iff
$$ \forall\, g \in \Gamma,\ \forall\, b \in \mathrm{Mov}(g),\ \exists\, p \in \Pi:\quad
b \in \mathrm{Mov}(p) \subseteq \mathrm{Mov}(g). $$
Equivalently: **every target footprint is the union of the $\Pi$-footprints it contains**,
$\mathrm{Mov}(g) = \bigcup \{\, \mathrm{Mov}(p) : p \in \Pi,\ \mathrm{Mov}(p) \subseteq \mathrm{Mov}(g) \,\}$.

*Proof.* ($\Leftarrow$) Assume the condition. Fix any $(f, T)$ with $\mathrm{score}_\Pi(f, T) = 1$ and any
non-equivalent $g \in \Gamma$; we show $T$ kills $g \circ f$. Non-equivalence gives (Prop 2.4)
$\mathrm{Mov}(g) \cap I \neq \varnothing$; pick $b \in \mathrm{Mov}(g) \cap I$. By hypothesis there is $p \in \Pi$
with $b \in \mathrm{Mov}(p) \subseteq \mathrm{Mov}(g)$. Then $b \in \mathrm{Mov}(p) \cap I$, so $p \circ f$ is
non-equivalent, so — as the $\Pi$-score is $1$ — it is killed: $\mathrm{Mov}(p) \cap O \neq \varnothing$. Since
$\mathrm{Mov}(p) \subseteq \mathrm{Mov}(g)$, also $\mathrm{Mov}(g) \cap O \neq \varnothing$, i.e. $T$ kills
$g \circ f$. Hence $\mathrm{score}_\Gamma(f, T) = 1$.

($\Rightarrow$) Contrapositive: assume the condition fails, witnessed by $g \in \Gamma$ and
$b \in \mathrm{Mov}(g)$ such that *every* $p \in \Pi$ with $b \in \mathrm{Mov}(p)$ has some escape point
$a_p \in \mathrm{Mov}(p) \setminus \mathrm{Mov}(g)$. Let $A = \{ a_p : p \in \Pi,\ b \in \mathrm{Mov}(p) \}$;
since $\Pi$ is finite, $A$ is finite, and $b \notin A$ (each $a_p \notin \mathrm{Mov}(g)$ while
$b \in \mathrm{Mov}(g)$). Build the separating instance: let $I^\star = \{b\} \cup A$, take $D = I^\star$ and
$f = \mathrm{id}_{I^\star}$ (so $f(D) = I^\star = I$), and take the suite $T = A$ (so $O = f(T) = A$). Then:

- **$\mathrm{score}_\Pi(f, T) = 1$.** Let $p \in \Pi$ be non-equivalent, i.e. $\mathrm{Mov}(p) \cap I \neq
  \varnothing$. If $b \in \mathrm{Mov}(p)$ then $a_p \in \mathrm{Mov}(p) \cap A = \mathrm{Mov}(p) \cap O$, so $p$
  is killed. If $b \notin \mathrm{Mov}(p)$ then $\mathrm{Mov}(p) \cap I = \mathrm{Mov}(p) \cap (\{b\} \cup A) =
  \mathrm{Mov}(p) \cap A \neq \varnothing$ (non-equivalence), i.e. $\mathrm{Mov}(p) \cap O \neq \varnothing$, so
  $p$ is killed. Every non-equivalent $\Pi$-mutant dies.
- **$g \circ f$ survives.** $b \in \mathrm{Mov}(g) \cap I$, so $g \circ f$ is non-equivalent; but
  $\mathrm{Mov}(g) \cap O = \mathrm{Mov}(g) \cap A = \varnothing$ (each $a_p \notin \mathrm{Mov}(g)$), so $T$
  does not kill it. Hence $\mathrm{score}_\Gamma(f, T) < 1$.

So $\mathrm{score}_\Pi(f, T) = 1 \not\Rightarrow \mathrm{score}_\Gamma(f, T) = 1$: $\Pi$ is not complete for
$\Gamma$. $\square$

**Remark 3.3 (why finiteness, and the infinite form).** Finiteness of $\Pi$ is used only to keep the escape set
$A$ finite, so the separating program has a finite reachable set. For infinite $\Pi$ the condition weakens: the
containment "$\mathrm{Mov}(p) \subseteq \mathrm{Mov}(g)$" relaxes to "for every finite $F \subseteq R \setminus
\mathrm{Mov}(g)$ there is $p \in \Pi$ with $b \in \mathrm{Mov}(p)$ and $\mathrm{Mov}(p) \cap F = \varnothing$" —
a $\Pi$-footprint through $b$ that avoids every finite obstruction outside the target. We work with finite $\Pi$
throughout; it is the case a real operator family inhabits.

**Remark 3.4 (composition survives what generators die on).** Theorem 3.2 dissolves the temptation to define
completeness by *generation under composition*. Killing the operators in $\Pi$ does not kill their composites:
take $R = \{0,1,2\}$, a program with the single reachable/observed value $0$, and $a, b$ with $a(0) = 1$,
$b(1) = 0$, $b(0) = 2$. Both $a \circ f$ and $b \circ f$ are killed at $0$ ($a$ moves $0 \to 1$, $b$ moves
$0 \to 2$), yet $(b \circ a)(0) = b(1) = 0$, so $(b \circ a) \circ f$ is *not* killed — indeed it is equivalent
on this program. Composition acts on exactly the part of an operator adequacy cannot see (Prop 2.4:
$\mathrm{Mov}(b \circ a)$ can be strictly smaller than both $\mathrm{Mov}(a)$ and $\mathrm{Mov}(b)$), which is
why "$\Pi$ generates the transformation monoid" says nothing about what a score of $1$ certifies. The right
object is footprint containment, not composition closure.

---

## 4. The absolute case: the value-guard basis and the ceiling

**Corollary 4.1 (the value-guard basis; minimal size $n$).** Let $|R| = n$. A family $\Pi$ is absolutely
complete iff it contains, for **every** value $r \in R$, an operator whose footprint is the singleton
$\{r\}$ — a *value guard* $\gamma_r$: "if the result is $r$, return some other value." The minimal absolutely-
complete family is $\{\gamma_r : r \in R\}$, of size exactly $n$.

*Proof.* Absolute completeness is completeness for $\Gamma = T(R)$, whose footprints are all of $2^R$
(Rem 2.5). Apply Thm 3.2 to the target footprints $\{b\}$ (singletons, which are footprints since $n \ge 2$):
completeness forces, for each $b$, some $p \in \Pi$ with $b \in \mathrm{Mov}(p) \subseteq \{b\}$, i.e.
$\mathrm{Mov}(p) = \{b\}$ — a value guard for $b$. Conversely, if $\Pi$ has a guard $\gamma_b$ for every $b$,
then for any target footprint $S$ and any $b \in S$, $\gamma_b$ satisfies $b \in \{b\} \subseteq S$, so Thm 3.2's
condition holds and $\Pi$ is absolutely complete. Minimality: each of the $n$ singleton targets forces a
distinct guard, so no family of size $< n$ suffices. $\square$

**Corollary 4.1a (finite/infinite dichotomy for absolute completeness).** For a finite operator family $\Pi$:
$$ \begin{array}{ll} |R| < \infty &:\ \Pi \text{ can be absolutely complete, with minimum size } |R| \text{ (Cor 4.1);} \\[1mm]
|R| = \infty &:\ \text{no finite } \Pi \text{ is absolutely complete.} \end{array} $$
*Proof.* The finite case is Cor 4.1. For the infinite case, absolute completeness requires a distinct singleton
footprint $\{r\}$ for every $r \in R$ (Cor 4.1); as $r \mapsto \{r\}$ is injective, a complete family realizes
$|R|$ distinct footprints, so no finite family suffices. $\square$

The infinite case is an impossibility, not a cost: on the codomains typical of real programs (integers,
strings, collections, records, floating-point values under a semantic equality), no finite output-operator
family is absolutely adequacy-complete, and only *relative* completeness for a designated target class (§5)
is available. (Formalized: `complete_univ_infinite`, `progComplete_univ_infinite`; §13.)

**Corollary 4.2 (extreme mutation is optimal on Booleans, deficient beyond).** A Descartes-style *constant*
operator `return c` has footprint $R \setminus \{c\}$ (it moves every value except $c$). The constant family
$\{\,`return c` : c \in R\,\}$ is absolutely complete iff $n = 2$.

*Proof.* By Cor 4.1, absolute completeness requires a singleton footprint for each value; a constant's footprint
$R \setminus \{c\}$ is a singleton iff $|R \setminus \{c\}| = 1$ iff $n = 2$. For $n = 2$, `return true` has
footprint $\{\mathrm{false}\}$ and `return false` has footprint $\{\mathrm{true}\}$ — precisely the two value
guards, so extreme mutation is exactly the minimal complete family on Booleans. For $n \ge 3$ every constant
footprint has size $\ge 2$, so no constant is a value guard and the family is incomplete. $\square$

**Example 4.3 (a surviving fault the constants miss).** Let $R = \{a, b, c\}$, a program reaching all three, a
suite observing only $a$ and $b$ ($O = \{a, b\}$, $I = \{a, b, c\}$). All three constant mutants are killed
(`return a` moves $\{b,c\}$, observed at $b$; `return b` moves $\{a,c\}$, at $a$; `return c` moves $\{a,b\}$, at
$a$), so the constant score is $1$. But the fault "returns $b$ where it should return $c$" — an operator with
footprint $\{c\}$ — is non-equivalent ($c \in I$) and unkilled ($\{c\} \cap O = \varnothing$). A perfect
extreme-mutation score certifies nothing about the $c$-outputs the suite never observed.

**Theorem 4.4 (the ceiling — what an absolute score certifies).** For $|R| \ge 2$ and any program $f$, suite $T$:
$$ \mathrm{score}_{T(R)}(f, T) = 1 \iff I \subseteq O \iff O = I, $$
i.e. an absolute mutation score of $1$ holds **exactly when the suite exercises every reachable output**. This
is the whole of what output mutation can certify, and no more.

*Proof.* ($\Leftarrow$) If $O = I$, every non-equivalent $g$ has $\mathrm{Mov}(g) \cap I \neq \varnothing =
\mathrm{Mov}(g) \cap O \neq \varnothing$, so all die. ($\Rightarrow$) If $I \not\subseteq O$, pick
$b \in I \setminus O$ and the guard $\gamma_b$ (footprint $\{b\}$): non-equivalent ($b \in I$), unkilled
($\{b\} \cap O = \varnothing$), so the score is $< 1$. $\square$

**Remark 4.5 (the ceiling, operationally).** Theorem 4.4 is the honest reading of output mutation: a full score
certifies **output coverage** — the dynamic property "every value the program can return is observed by the
suite" — and the value guards are the cheapest operator family that makes that certificate *exact*. It says
nothing about faults that separate two inputs mapped to the same output: if $f(x_1) = f(x_2)$ then
$p(f(x_1)) = p(f(x_2))$ for every output operator $p$, so no output mutant distinguishes $x_1$ from $x_2$.
Output mutation certifies output coverage; input-separating faults are structurally outside its reach.

---

## 5. Relative completeness and its decidability spectrum

Fix a finite $\Pi$ and a finitely-presented target $\Gamma$. By Thm 3.2, deciding completeness is deciding the
**footprint-containment** condition; its complexity is exactly that of the footprint representation.

**Proposition 5.1 (the exact reach of a finite family).** The value guards $\{\gamma_{r_1}, \dots,
\gamma_{r_k}\}$ (footprints the singletons $\{r_1\}, \dots, \{r_k\}$) are adequacy-complete for exactly
$$ \Gamma_{\max} = \{\, g : \mathrm{Mov}(g) \subseteq \{r_1, \dots, r_k\} \,\}. $$
So a partial guard family yields a *legible* certificate: "every guarded value the program can produce is
exercised, hence any fault confined to the guarded values is caught."

*Proof.* By Thm 3.2, the guards are complete for $g$ iff every $b \in \mathrm{Mov}(g)$ has a guard $\gamma_{r_i}$
with $b \in \{r_i\} \subseteq \mathrm{Mov}(g)$, i.e. $b \in \{r_1, \dots, r_k\}$. This holds for all
$b \in \mathrm{Mov}(g)$ iff $\mathrm{Mov}(g) \subseteq \{r_1, \dots, r_k\}$. $\square$

**Theorem 5.2 (decidability spectrum).** Deciding whether finite $\Pi$ is adequacy-complete for finite
$\Gamma$ reduces to finitely many footprint-containment tests $\mathrm{Mov}(p) \subseteq \mathrm{Mov}(g)$ and
membership tests $b \in \mathrm{Mov}(p)$. Hence:

1. **Finite codomain (value tables).** Footprints are explicit subsets of $[n]$; each test is a linear scan, so
   completeness is decidable in **polynomial time**.
2. **Semilinear footprints ($R = \mathbb{Z}$, Presburger-definable $\mathrm{Mov}$).** Containment of
   Presburger-definable sets is decidable, so completeness is **decidable**.
3. **Computable operators (undecidable).** If operators are given as total computable functions over a
   computable codomain, each footprint $\mathrm{Mov}(p)$ is a *decidable* set, but deciding footprint containment
   $\mathrm{Mov}(p) \subseteq \mathrm{Mov}(g)$ — and hence adequacy-completeness — is **undecidable**.

*Proof.* The reduction to footprint containment is Thm 3.2 (a finite conjunction over $g \in \Gamma$,
$b \in \mathrm{Mov}(g)$, quantifying $p \in \Pi$). (1) Value tables give $O(1)$ membership and $O(n)$ containment.
(2) Containment of Presburger-definable sets is expressible in Presburger arithmetic, which is decidable. (3) We
reduce from non-halting. Given a Turing machine $M$, define the total computable operator $g_M : \mathbb{N} \to
\mathbb{N}$ by $g_M(n) = n+1$ if $M$ halts within $n$ steps and $g_M(n) = n$ otherwise; then
$\mathrm{Mov}(g_M) = \{ n : M \text{ halts within } n \text{ steps} \}$ is decidable (simulate $M$ for $n$ steps).
Now $\mathrm{Mov}(g_M) \subseteq \mathrm{Mov}(\mathrm{id}) = \varnothing$ holds iff $\mathrm{Mov}(g_M) =
\varnothing$ iff $M$ never halts, so a decision procedure for footprint containment would decide non-halting. By
Thm 3.2, a completeness query subsumes such containment tests. (We do not claim r.e. footprints: the argument
uses *decidable* footprints of total computable operators, and undecidability of their *containment*, not of any
r.e. set difference.) $\square$

**Remark 5.3 (the spectrum runs through set containment, not word problems).** The P / decidable / undecidable
gradient here is that of **subset containment** of increasingly expressive set representations — the natural
object for an adequacy question. No group- or monoid-theoretic machinery (word problems, Cayley embeddings)
appears, because none is needed: adequacy never composes operators (Rem 3.4), so the containment order, not a
generation order, is what governs decidability.

---

## 6. Coupling for higher-order output mutants

The **coupling-effect hypothesis** (DeMillo–Lipton–Sayward 1978) asserts that test suites killing first-order
mutants also kill higher-order ones; in the general setting (arbitrary combinations of syntactic faults) it
remains a hypothesis supported empirically. We prove a **restricted** form: it holds, as a theorem, for
higher-order *output* mutants — finite compositions of output operators. We claim nothing about the general
(program-text) coupling hypothesis.

**Theorem 6.1 (completeness implies coupling).** Let $\Pi$ be absolutely complete, and let $\Gamma = \langle \Pi
\rangle$ be the family of all **higher-order** output mutants (finite compositions of $\Pi$-operators). Then
$\Pi$ is adequacy-complete for $\langle \Pi \rangle$: for every program and suite, killing every non-equivalent
first-order $\Pi$-mutant kills every non-equivalent higher-order mutant.

*Proof.* By Cor 4.1, $\Pi$ contains a value guard $\gamma_b$ (footprint $\{b\}$) for every $b \in R$. Take any
$g \in \langle \Pi \rangle$ and any $b \in \mathrm{Mov}(g)$; the guard $\gamma_b$ satisfies $b \in \{b\}
\subseteq \mathrm{Mov}(g)$, so Thm 3.2's condition holds for $\Gamma = \langle \Pi \rangle$. Hence $\Pi$ is
complete for $\langle \Pi \rangle$. $\square$

**Remark 6.2 (scope, and coupling as a downstream consequence).** The proof uses no property of composition
beyond the fact that a higher-order output mutant is *some* output operator with *some* footprint, every
nonempty instance of which contains a singleton the guard family covers. Two scope caveats. First, $\langle \Pi
\rangle$ is the class of higher-order *output* mutants (post-compositions of the result); the result does not
address higher-order *program-text* mutants, for which coupling remains an empirical hypothesis. Second, the
theorem is conditional on *absolute* first-order completeness (the full value-guard basis); a partial family
couples only for the target class its footprints cover (Prop 5.1). Within this scope, coupling is a consequence
of first-order completeness rather than an independent assumption. (Formalized: `coupling`, `progComplete_coupling`;
§13.)

---

## 7. Why output-operator completeness is program-independent (and program-text completeness is not)

**Proposition 7.1 (program-independent subsumption).** For output operators $p, g$: *every test that kills
$p \circ f$ also kills $g \circ f$, for every program $f$*, iff $\mathrm{Mov}(p) \subseteq \mathrm{Mov}(g)$.

*Proof.* ($\Leftarrow$) A test $x$ kills $p \circ f$ iff $f(x) \in \mathrm{Mov}(p) \subseteq \mathrm{Mov}(g)$,
so $x$ kills $g \circ f$. ($\Rightarrow$) If $b \in \mathrm{Mov}(p) \setminus \mathrm{Mov}(g)$, take $f$ with $b$
reachable and a suite observing $b$: it kills $p \circ f$ ($b \in \mathrm{Mov}(p)$) but not $g \circ f$
($b \notin \mathrm{Mov}(g)$). $\square$

So Theorem 3.2 reads, in the language of mutant subsumption (Kurtz, Ammann & Offutt 2015; Ammann, Delamaro &
Offutt 2014): **$\Pi$ is adequacy-complete for $\Gamma$ iff every target mutant is subsumed by some
$\Pi$-mutant, uniformly over all programs.** It is the *program-independent* form of dominator theory.

**Proposition 7.2 (the factoring that buys program-independence).** For an output operator, the detection set
factors through the footprint:
$$ \mathrm{Det}(p \circ f) = \{ x : p(f(x)) \neq f(x) \} = f^{-1}(\mathrm{Mov}(p)), $$
so it depends on $f$ **only** through the pre-image structure $f^{-1}(\cdot)$, and crucially the operator $p$
enters *only* through the program-independent object $\mathrm{Mov}(p)$: the same $\mathrm{Mov}(p)$ governs
detection across *all* programs $f$.

We are careful about the contrast with program-text mutation. The detection set of *any* mutant $m$,
$\mathrm{Det}(m) = \{ x : m(x) \neq f(x) \}$, is a *semantic* object — it depends only on the functions $m$ and
$f$, not on their syntactic form. The asymmetry is therefore not that program-text detection is "syntactic"
while output detection is "semantic"; both are semantic. It is that output operators carry an **operator-only
invariant** $\mathrm{Mov}(p)$ that determines detection uniformly over all $f$ (Prop 7.1, 7.2), whereas for a
program-text mutation *schema* $\mu$ there is in general no operator-only invariant: the mutant $m = \mu(\text{
source of } f)$ is produced by applying $\mu$ to the *text* of $f$, so $\mu$'s detection behavior is not a
function of $\mu$ alone but of the (schema, source) pair, and varies across source programs computing the same
$f$. This is why the field's completeness/sufficiency/subsumption results are relative-by-construction (§1.1):
absent a program-independent invariant, "complete" can be stated only against a fixed program (or fault model
tying schemas to detection sets). Output mutation is the sub-class that admits such an invariant, which is what
makes the program- and suite-independent Definition 3.1 available for it.

---

## 8. The certifying suite: a teaching-dimension reading

An adequate suite is one whose observed set $O$ makes the score $1$. The cheapest such suite has an exact size.

**Theorem 8.1 (minimum certifying suite).** Fix an absolutely-complete family and a program $f$ with reachable
set $I = f(D)$. A suite $T$ achieves $\mathrm{score}(f, T) = 1$ iff $O = f(T) = I$. Consequently:

1. *(finite reachable set)* if $I$ is finite, a certifying suite exists and the minimum size is
   $$ \sigma(f) = |I| = |f(D)|, $$
   the number of distinct reachable outputs (one test per reachable value, choosing for each $r \in I$ some
   $x \in f^{-1}(r)$);
2. *(infinite reachable set)* if $I$ is infinite, **no finite suite is certifying** — a finite suite has a
   finite observed set $O$, which cannot equal the infinite $I$.

*Proof.* By Thm 4.4 the score is $1$ iff $O = I$ (which requires $I \subseteq O$; since $O = f(T) \subseteq I$
always, this is $O = I$). (1) For finite $I$, a suite with $O = I$ must contain, for each $r \in I$, at least one
$x$ with $f(x) = r$, so $|T| \ge |I|$; one such $x$ per value gives $|T| = |I|$ and $O = I$. (2) For infinite $I$,
$O = f(T)$ is finite (as $T$ is finite), so $O \neq I$ and no finite suite certifies. $\square$

The hypothesis $I$ finite is essential and is not vacuous in practice: it fails exactly for programs whose set
of reachable outputs is infinite (e.g. an unbounded integer- or string-valued function), which by Cor 4.1a is
also the regime where absolute completeness by a finite operator family is impossible. (Both cases formalized:
`certify_lb`, `certify_ub`, `certify_infinite`; §13.)

**Remark 8.2 (the sample complexity of certification).** $\sigma(f)$ is the **teaching dimension** of the
program against the operator family in the classical sense (Goldman & Kearns 1995): the minimum number of
labeled examples (here, tests with their observed outputs) required to distinguish $f$ from every non-equivalent
mutant the family can express. For output mutation it is exactly the number of reachable outputs — a clean,
program-structural quantity. It is the exact-identification counterpart of the completeness result: Theorem 3.2
says *which* faults a family can certify against; Theorem 8.1 says *how many tests* the certification costs. A
mutation-based tool that reports "$\sigma(f)$ tests, all reachable outputs observed" is stating precisely the
guarantee its score underwrites — and nothing it does not.

---

## 9. Consequences for mutation-based tools

The results apply to any tool that certifies code against an **output/extreme** mutation family.

- **A passing score means output coverage, exactly (Thm 4.4).** Report it as such: "every value the program can
  return was observed." Do not read an output-mutation score as evidence about input-separating faults — those
  are outside the ceiling (Rem 4.5), and a tool that also mutates program text is certifying a *different*,
  larger, and program-dependent fault space (§7).
- **Use value guards, not constants, past Booleans (Cor 4.1–4.2).** The minimal complete output family is the
  $n$ value guards; Descartes constants are complete only for $n = 2$. On richer return types, `return c`
  operators leave the surviving faults of Example 4.3.
- **A partial guard family gives a legible partial certificate (Prop 5.1):** "faults confined to the guarded
  values are caught." State the guarded set.
- **Coupling is earned, not assumed (Thm 6.1):** a complete first-order family already kills higher-order output
  mutants, so a tool need not generate them.
- **Report the certifying-suite size $\sigma(f) = |f(D)|$ (Thm 8.1)** as the honest cost and content of the
  guarantee.

---

## 10. Discussion

The results of this paper are confined to output mutation, and the central quantitative result is deliberately
modest: an absolutely complete output family certifies exactly output coverage (Thm 4.4), not program
correctness or arbitrary fault detection. The contribution we wish to emphasize is not the individual theorems,
which are elementary, but the definitional choice that organizes them (Def 3.1): an operator family is measured
by *what killing its mutants certifies*, quantified over all programs and suites, rather than by the mutants it
can produce. We record several consequences of adopting this object of study.

**Operator design becomes basis design.** For output mutation the relevant space is $(2^R, \subseteq)$ under
footprint containment. Complete families are characterized (Thm 3.2) not as those that generate all
transformations under composition, but as those whose footprints cover the target; absolute completeness forces
the atoms, the singleton value guards (Cor 4.1). The design question shifts from "which operators should be
implemented?" to "which footprint basis is required to certify a given target class?".

**Expressive power and evidentiary power are distinct.** A family can generate the entire transformation monoid
on a small finite codomain — a fact with tiny generating sets (e.g. two maps on a two-element codomain) — while
certifying almost nothing, because composition can remove exactly the moved values that caused the generators to
be killed (Rem 3.4). In the terms of this paper, footprint containment, not compositional generation, governs
what a passing score entails. The distinction — that fault expressibility does not entail test-suite
discriminating power — is not specific to output mutation and may be worth isolating on its own.

**Coupling, within scope, is a consequence rather than a hypothesis.** Theorem 6.1 derives coupling for
higher-order *output* mutants from first-order completeness, without assuming anything about how compositions
behave. We claim nothing about the general coupling hypothesis (arbitrary program-text faults), which remains
empirical; but within the output fragment the phenomenon is forced by the structure of the certificate rather
than posited.

**Negative results are actionable.** The infinite-codomain impossibility (Cor 4.1a) does not report a failure of
mutation testing; it specifies the alternative. Since no finite operator family is absolutely complete when $R$
is infinite, the framework directs one to choose a target class $\Gamma$, determine the footprint basis required
to certify against it (Prop 5.1), and report the resulting *relative* certificate. This suggests a form of tool
output stronger than a bare score: "complete against operator family $\Pi$, which is complete for fault class
$\Gamma$; therefore this suite certifies property $C$," in place of an uninterpreted "$X\%$ mutation score."

**Epistemic content.** For output mutation the definition yields an exact semantic characterization of the
number a mutation-testing tool reports: under an absolutely complete family, a score of $1$ is equivalent to
output coverage (Thm 4.4). This is weaker than any notion of correctness, but it is precise, and it replaces an
operational reading of the score (killed perturbations correlate empirically with adequate tests) with a
characterized one.

Whether this reorganization extends beyond output mutation is open. The decisive structural fact is Prop 7.2:
output operators admit a program-independent detection invariant, $\mathrm{Mov}(p)$. The natural question (§12)
is which other fault classes admit an analogous invariant. If several do, each would carry its own partial
order, basis theorem, minimum certifying suite, coupling consequence, and decidability boundary — a family of
mutation-certificate theories. If none do, the present results stand as a complete account of one restricted but
practically common class.

---

## 11. Related work

The full source-verified survey is `LITERATURE_PI_COMPLETENESS.md`. In brief: mutation testing lacks a
completeness theorem — the coupling effect and competent-programmer hypothesis are *assumptions* (DeMillo,
Lipton & Sayward 1978), "sufficient operators" is experimental (Offutt et al. 1996), "minimal mutant sets" and
dominator mutants are test-set-/pool-relative (Ammann, Delamaro & Offutt 2014), and semantic subsumption is
undecidable (Kurtz, Ammann & Offutt 2015). Extreme/output mutation is Niedermayr et al. 2016 and Vera-Pérez et
al. 2018 (Descartes). We recover extreme mutation as the $n = 2$ optimum (Cor 4.2) and give the general-$n$
completeness theory it lacked. The teaching-dimension reading is the classical exact-learning notion of Goldman
& Kearns 1995. What is new here is the *program- and suite-independent* completeness definition (Def 3.1), its
footprint characterization (Thm 3.2), the value-guard basis and its size (Cor 4.1), coupling as a corollary
(Thm 6.1), and the detection-set factoring that explains the field's relativity (Prop 7.2).

---

## 12. Future directions

The program↔footprint bridge, previously the sole formalization gap, is closed (§13). The remaining directions
concern generalization and use.

1. **A program-independent invariant for other fault classes.** The results rest on Prop 7.2: output-operator
   detection factors through the footprint $\mathrm{Mov}(p)$, a program-independent object. Identify the largest
   fault classes admitting an analogous invariant — the classes for which a program- and suite-independent
   completeness theory (Def 3.1) is available. Success would yield a family of mutation-certificate theories,
   one per class; failure would delimit output mutation as the maximal such class.
2. **Cost-optimal partial families.** Given a target fault class $\Gamma$ and a per-operator cost, determine the
   minimum-cost $\Pi$ adequacy-complete for $\Gamma$. By Thm 3.2 the feasibility predicate is footprint
   coverage, placing this as a weighted set-cover problem over $2^R$; characterize its complexity and
   approximability.
3. **Decidable relative fragments.** Determine which target footprint classes admit *decidable* relative
   completeness. Thm 5.2 gives polynomial time for explicit finite footprints and decidability for
   Presburger-definable ones over $\mathbb{Z}$; a systematic account of the boundary (e.g. regular, semilinear,
   or tree-automatic footprint families) is open.
4. **Input-separating faults.** The ceiling (Rem 4.5) bounds output mutation to output recodings. The companion
   theory for operators that separate inputs a program collapses (program-text or input-space mutation) is where
   the program-independent invariant is lost (Prop 7.2); quantify what completeness content is recoverable, and
   against what fixed structure.
5. **Certificate-carrying tool output.** Formalize the reporting contract suggested in §10 — "$100\%$ against
   $\Pi$, complete for $\Gamma$, therefore property $C$" — as a checkable artifact, and integrate the
   minimum-certifying-suite bound (Thm 8.1) as its stated cost.

---

## 13. Status ledger

*Every result is elementary; none is deep. The contribution is the definition (Def 3.1) and the structure it
forces — and that structure is machine-checked in Lean 4 / Mathlib (`proofs/adequacy_completeness.lean`), each
theorem `#print axioms`-clean (`[propext, Classical.choice, Quot.sound]`, no `sorryAx`).*

| Result | Statement | Lean name | Status |
|---|---|---|---|
| Prop 2.4 | operator ≡ footprint (program score = footprint score) | `progScore_iff_scoreAt` | ✅ Lean, no `sorry`; axioms clean |
| **Thm 3.2** | **footprint characterization** (the main theorem) | **`footprint_characterization`** | ✅ **Lean, no `sorry`; axioms clean** |
| Rem 2.5 | every subset is a footprint | `mov_surjective` | ✅ Lean, no `sorry`; axioms clean |
| Cor 4.1 | value-guard basis (footprints) | `absolute_iff_guards` | ✅ Lean, no `sorry`; axioms clean |
| Cor 4.1a | finite/infinite dichotomy; infinite impossibility | `complete_univ_infinite` | ✅ Lean, no `sorry`; axioms clean |
| Cor 4.2 | extreme mutation complete iff $n=2$ | `constants_iff_card_two` | ✅ Lean, no `sorry`; axioms clean |
| Thm 4.4 | absolute score $= 1$ iff output coverage $I=O$ | `ceiling` | ✅ Lean, no `sorry`; axioms clean |
| Thm 5.2 | decidability spectrum (P / decidable / undecidable) | *(meta; the reduction is Thm 3.2)* | ✍ paper (rests on the checked Thm 3.2) |
| Thm 6.1 | completeness $\Rightarrow$ coupling (higher-order output) | `coupling` | ✅ Lean, no `sorry`; axioms clean |
| Prop 7.1 | program-independent subsumption $=$ footprint $\subseteq$ | `subsumes_iff_subset` | ✅ Lean, no `sorry`; axioms clean |
| Prop 7.2 | $\mathrm{Det}(p\circ f) = f^{-1}(\mathrm{Mov}(p))$ | `det_factors` | ✅ Lean, `rfl` (no axioms) |
| Thm 8.1 | min certifying suite $= |f(D)|$ (finite); none (infinite) | `certify_lb`, `certify_ub`, `certify_infinite` | ✅ Lean, no `sorry`; axioms clean |
| Bridge | realizability of $(I, O)$ by a program | `realizable` | ✅ Lean, no `sorry`; axioms clean |
| Bridge | program-level $=$ footprint-level completeness | `progComplete_iff_complete` | ✅ Lean, no `sorry`; axioms clean |
| **Thm 3.2 (over programs)** | characterization on `f : D → R`, `T : Finset D` | **`progComplete_characterization`** | ✅ **Lean, no `sorry`; axioms clean** |
| Cor 4.1 (over operators) | absolute completeness $\Leftrightarrow$ operator value guards | `progComplete_absolute_iff_guards` | ✅ Lean, no `sorry`; axioms clean |
| Cor 4.1a (over operators) | infinite $R$: no finite operator family is complete | `progComplete_univ_infinite` | ✅ Lean, no `sorry`; axioms clean |
| Thm 6.1 (over operators) | operator-level coupling | `progComplete_coupling` | ✅ Lean, no `sorry`; axioms clean |

**Formalization.** The development is machine-checked **end to end, from real programs down to the kernel**.
`ProgScore`/`ProgComplete` define completeness directly over programs `f : D → R` and finite suites
`T : Finset D`; `progScore_iff_scoreAt` (Prop 2.4) reduces a program's score to the footprint-level `ScoreAt` at
the reachable set `range f` and observed set `f '' T`; `realizable` shows every reachable/observed pair `(I, O)`
with `O ⊆ I` is realized by an actual program; `progComplete_iff_complete` glues these into `ProgComplete Π Γ ↔
Complete (Mov '' Π) (Mov '' Γ)`; and `progComplete_characterization` restates the main theorem (Thm 3.2) over
programs. The absolute corollaries are also carried to the operator/program level: `mov_surjective` (Rem 2.5,
every subset is a footprint) gives `Mov '' \mathrm{univ} = \mathrm{univ}`, from which `progComplete_absolute_iff_guards`
(Cor 4.1 over operators), `progComplete_coupling` (Thm 6.1 over operators), and `progComplete_univ_infinite`
(the infinite impossibility over operators) follow — so the paper's absolute results, not only the main theorem,
are stated and checked over real operator families rather than over footprint sets. **Every theorem is
`#print axioms`-clean** — each depends on exactly `[propext, Classical.choice, Quot.sound]` (the standard base;
`det_factors` on none), with **no `sorryAx`**. The only result not carried as a Lean theorem is Thm 5.2's
decidability *spectrum* (a meta-statement over set representations; its load-bearing reduction to footprint
containment *is* the checked Thm 3.2). To reproduce: drop the `.lean` file into a Lean 4 project with Mathlib
(`lake exe cache get`) and run `#print axioms progComplete_characterization` (etc.).

**Provenance.** Self-contained; grounded on standard mutation-testing theory (coupling, sufficiency, subsumption)
and the classical teaching-dimension notion, cited in §11 and `LITERATURE_PI_COMPLETENESS.md`. Not peer-reviewed.
