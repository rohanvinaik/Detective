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
killing all non-equivalent $\Gamma$-mutants*, we prove a exact characterization (Thm 3.2): $\Pi$ is complete for
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

The relativity is not laziness; it is forced by the object. A program-text mutant $m$ has detection set
$\mathrm{Det}(m) = \{x : m(x) \neq f(x)\}$, which depends on *how $f$ is written*, so "does operator family $X$
subsume operator family $Y$" has no program-independent answer. §7 shows exactly where that relativity comes
from and why one restricted-but-important operator class escapes it.

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
output operator: send each $r \in S$ to any value $\neq r$ (possible since $|R| \ge 2$; for $S = R$ a
fixed-point-free self-map exists whenever $|R| \ge 2$, e.g. any $|R|$-cycle) and fix everything outside $S$.
So the footprints range over the *entire* powerset $2^R$, and — by Prop 2.4 — the adequacy content of an
operator family $\Pi$ is exactly the set $\mathrm{Foot}(\Pi) = \{\mathrm{Mov}(p) : p \in \Pi\} \subseteq 2^R$.
Where operators send the values they move is adequacy-invisible; this is the seed of every result below.

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
3. **Program-defined footprints (r.e. $\mathrm{Mov}$).** $\mathrm{Mov}(p) \subseteq \mathrm{Mov}(g)$ is
   emptiness of $\mathrm{Mov}(p) \setminus \mathrm{Mov}(g)$, an r.e. set-difference, hence **undecidable** in
   general (Rice 1953).

*Proof.* The reduction is Thm 3.2 (a finite conjunction over $g \in \Gamma$, $b \in \mathrm{Mov}(g)$, quantifying
$p \in \Pi$). (1) tables give constant-time membership and $O(n)$ containment. (2) is Presburger decidability. (3)
$\mathrm{Mov}(p) \setminus \mathrm{Mov}(g) = \varnothing$ is a non-trivial semantic property of the
program-defined footprint, undecidable by Rice. $\square$

**Remark 5.3 (the spectrum runs through set containment, not word problems).** The P / decidable / undecidable
gradient here is that of **subset containment** of increasingly expressive set representations — the natural
object for an adequacy question. No group- or monoid-theoretic machinery (word problems, Cayley embeddings)
appears, because none is needed: adequacy never composes operators (Rem 3.4), so the containment order, not a
generation order, is what governs decidability.

---

## 6. The coupling effect, as a corollary

The **coupling-effect hypothesis** (DeMillo–Lipton–Sayward 1978) asserts that test suites killing simple
(first-order) mutants also kill complex (higher-order) ones. For output mutation it is not a hypothesis.

**Theorem 6.1 (completeness implies coupling).** Let $\Pi$ be absolutely complete, and let $\Gamma = \langle \Pi
\rangle$ be the family of all **higher-order** output mutants (finite compositions of $\Pi$-operators). Then
$\Pi$ is adequacy-complete for $\langle \Pi \rangle$: for every program and suite, killing every non-equivalent
first-order $\Pi$-mutant kills every non-equivalent higher-order mutant.

*Proof.* By Cor 4.1, $\Pi$ contains a value guard $\gamma_b$ (footprint $\{b\}$) for every $b \in R$. Take any
$g \in \langle \Pi \rangle$ and any $b \in \mathrm{Mov}(g)$; the guard $\gamma_b$ satisfies $b \in \{b\}
\subseteq \mathrm{Mov}(g)$, so Thm 3.2's condition holds for $\Gamma = \langle \Pi \rangle$. Hence $\Pi$ is
complete for $\langle \Pi \rangle$. $\square$

**Remark 6.2 (coupling is downstream of completeness).** The proof needs nothing about composition beyond the
fact that a higher-order mutant is *some* operator with *some* footprint — and every nonempty footprint contains
a singleton the guard family covers. So for output mutation the coupling effect is a corollary of first-order
completeness, obtained without reasoning about how compositions behave. Composition, which the generation view
puts at the center, enters here only as a target class $\langle \Pi \rangle$ that a complete family
automatically handles.

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
so it depends on $f$ **only** through the reachable partition $f^{-1}(\cdot)$, never on how $f$ is written. A
program-text mutant $m$ has $\mathrm{Det}(m) = \{ x : m(x) \neq f(x) \}$, which does *not* factor through any
program-independent object — it depends on the syntactic form of $f$. This is exactly why the field's
completeness/sufficiency/subsumption results are relative-by-construction (§1.1): without the footprint
factoring, "complete" can only be stated against a fixed fault model that ties operators to detection sets. The
relativity is a structural fact about *syntactic* mutation, not a decidability boundary — and output mutation is
the sub-class that escapes it.

---

## 8. The certifying suite: a teaching-dimension reading

An adequate suite is one whose observed set $O$ makes the score $1$. The cheapest such suite has an exact size.

**Theorem 8.1 (minimum certifying suite).** For an absolutely-complete family and a program $f$ with reachable
set $I = f(D)$, a suite $T$ achieves $\mathrm{score}(f, T) = 1$ iff $O = f(T) = I$. The minimum size of such a
suite is
$$ \sigma(f) = |I| = |f(D)|, $$
the number of **distinct reachable outputs**: one test per reachable value, choosing for each $r \in I$ some
$x \in f^{-1}(r)$.

*Proof.* By Thm 4.4 the score is $1$ iff $O = I$. A suite with $O = I$ must contain, for each $r \in I$, at
least one $x$ with $f(x) = r$, so $|T| \ge |I|$; picking exactly one such $x$ per value gives $|T| = |I|$ and
$O = I$. $\square$

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

## 10. Related work

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

## 11. Open problems

*(The program↔footprint bridge, once listed here as the sole formalization gap, is now closed: the Lean
development models programs `f : D → R` and finite suites `T : Finset D` directly and proves `ProgComplete Π Γ ↔
Complete (Mov '' Π) (Mov '' Γ)` via `progScore_iff_scoreAt` (Prop 2.4, formal) and `realizable`, then restates
Thm 3.2 over programs as `progComplete_characterization` — all `#print axioms`-clean. See §12.)*

1. **Beyond output operators.** Characterize adequacy-completeness for operator classes whose detection sets do
   *not* factor through a program-independent object (Prop 7.2) — i.e. identify the largest operator class for
   which a program-independent completeness theorem survives.
2. **Cost-optimal partial families.** Given a fault budget $\Gamma$ and a per-operator cost, find the minimum-cost
   $\Pi$ adequacy-complete for $\Gamma$ — a set-cover-flavored optimization over footprints (Thm 3.2 makes the
   feasibility test explicit).
3. **Input-separating faults.** The ceiling (Rem 4.5) bounds output mutation; the companion theory for operators
   that *can* separate collapsed inputs (program-text or input-space mutation) is where program-independence is
   lost — quantify what is recoverable.

---

## 12. Status ledger

*Every result is elementary; none is deep. The contribution is the definition (Def 3.1) and the structure it
forces — and that structure is machine-checked in Lean 4 / Mathlib (`proofs/adequacy_completeness.lean`), each
theorem `#print axioms`-clean (`[propext, Classical.choice, Quot.sound]`, no `sorryAx`).*

| Result | Statement | Lean name | Status |
|---|---|---|---|
| Prop 2.4 | operator ≡ footprint (program score = footprint score) | `progScore_iff_scoreAt` | ✅ Lean, no `sorry`; axioms clean |
| **Thm 3.2** | **footprint characterization** (the main theorem) | **`footprint_characterization`** | ✅ **Lean, no `sorry`; axioms clean** |
| Cor 4.1 | value-guard basis | `absolute_iff_guards` | ✅ Lean, no `sorry`; axioms clean |
| Cor 4.2 | extreme mutation complete iff $n=2$ | `constants_iff_card_two` | ✅ Lean, no `sorry`; axioms clean |
| Thm 4.4 | absolute score $= 1$ iff output coverage $I=O$ | `ceiling` | ✅ Lean, no `sorry`; axioms clean |
| Thm 5.2 | decidability spectrum (P / decidable / undecidable) | *(meta; the reduction is Thm 3.2)* | ✍ paper (rests on the checked Thm 3.2) |
| Thm 6.1 | completeness $\Rightarrow$ coupling (higher-order) | `coupling` | ✅ Lean, no `sorry`; axioms clean |
| Prop 7.1 | program-independent subsumption $=$ footprint $\subseteq$ | `subsumes_iff_subset` | ✅ Lean, no `sorry`; axioms clean |
| Prop 7.2 | $\mathrm{Det}(p\circ f) = f^{-1}(\mathrm{Mov}(p))$ | `det_factors` | ✅ Lean, `rfl` (no axioms) |
| Thm 8.1 | minimum certifying suite $\sigma(f) = |f(D)|$ | `certify_lb`, `certify_ub` | ✅ Lean, no `sorry`; axioms clean |
| Bridge | realizability of $(I, O)$ by a program | `realizable` | ✅ Lean, no `sorry`; axioms clean |
| Bridge | program-level $=$ footprint-level completeness | `progComplete_iff_complete` | ✅ Lean, no `sorry`; axioms clean |
| **Thm 3.2 (over programs)** | characterization stated on `f : D → R`, `T : Finset D` | **`progComplete_characterization`** | ✅ **Lean, no `sorry`; axioms clean** |

**Formalization.** The development is machine-checked **end to end, from real programs down to the kernel**.
`ProgScore`/`ProgComplete` define completeness directly over programs `f : D → R` and finite suites
`T : Finset D`; `progScore_iff_scoreAt` (Prop 2.4) reduces a program's score to the footprint-level `ScoreAt` at
the reachable set `range f` and observed set `f '' T`; `realizable` shows every reachable/observed pair `(I, O)`
with `O ⊆ I` is realized by an actual program; `progComplete_iff_complete` glues these into `ProgComplete Π Γ ↔
Complete (Mov '' Π) (Mov '' Γ)`; and `progComplete_characterization` restates the main theorem (Thm 3.2) over
programs. **Every theorem is `#print axioms`-clean** — each depends on exactly `[propext, Classical.choice,
Quot.sound]` (the standard base; `det_factors` on none), with **no `sorryAx`**. The only results not carried as
Lean theorems are Thm 5.2's decidability *spectrum* (a meta-statement whose load-bearing reduction to footprint
containment *is* the checked Thm 3.2) — there is no remaining by-hand gap in the completeness chain itself. To
reproduce: drop the `.lean` file into a Lean 4 project with Mathlib (`lake exe cache get`) and run
`#print axioms progComplete_characterization` (etc.).

**Provenance.** Self-contained; grounded on standard mutation-testing theory (coupling, sufficiency, subsumption)
and the classical teaching-dimension notion, cited in §10 and `LITERATURE_PI_COMPLETENESS.md`. Not peer-reviewed.
