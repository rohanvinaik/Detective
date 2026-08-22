---
title: "Negative Specification: Two-Sign Mutation Testing as Complete Behavioral Characterization"
subtitle: "The output-space mutation operator μ⁻, population-derived censors, and the specification complexity σ(P, μ ∪ μ⁻)"
author: "Rohan Vinaik"
date: "2026-08-22"
status: "formal specification (design-complete; Form A of μ⁻ grounded against the live Wesker engine)"
priors_do_not_rederive:
  - "σ = teaching dimension (Specification-Complexity [SC] Thm 2.7 / Lean T5_17); σ is μ-parameterized (SC §2.3)"
  - "Representation independence (SC Thm 2.3); redundant ⟺ zero information gain (SC Thm 3.11); composition gap (SC Thm 3.15)"
  - "Value-vs-run specification: assertion kill ≠ crash kill (Detective ARCHITECTURE §0)"
  - "I_solve = I_ind + I_ext; L_ind the self-teaching fraction (SIGNIFICANCE_WEIGHTING §12)"
  - "Admissibility as a well-definedness condition; falsifiability guard (SIGNIFICANCE_WEIGHTING §14; SSL §4.3)"
  - "Submodularity fails at bridges; bounded supermodular degree is the real object (SIGNIFICANCE_WEIGHTING §13)"
external_citation_caveat: >
  External citations were recalled during design, not looked up; verify before public use. Internal
  references (the author's corpus, the Wesker/Detective source) were read directly and are cited by
  file, symbol, and section. Engine facts marked "[traced]" were obtained by symbolic trace of
  Wesker/engine.py on 2026-08-22.
---

# Negative Specification

## Two-Sign Mutation Testing as Complete Behavioral Characterization

### Abstract

Mutation-based specification, as realized by the Wesker engine and the Detective front-end, measures a
function $f$ by generating a finite set of syntactic variants (mutants) and asking which a covering
test suite distinguishes. The minimum suite achieving full mutation kill is the *specification
complexity* $\sigma(P,\mu)$, and $\sigma$ is proved equal to the **teaching dimension** of $P$'s
semantic equivalence class in the concept class induced by the mutation policy $\mu$ (SC Thm 2.7).
Teaching dimension is defined over *labeled* examples of **both** signs. The mutation policies in use
enumerate program space only, and therefore specify **one sign** of a two-sign teaching set. This
document formalizes the second sign. We define an output-space mutation operator $\mu^-$ (perturbation
of the codomain), give its two engineering realizations (Form A, a return-site AST rewrite that reuses
the existing kill-attribution pipeline unchanged; Form B, a runtime wrapper reaching the non-return
codomain), and study the resulting two-sign specification complexity $\sigma(P, \mu \cup \mu^-)$. We
prove three structural results contingent on cited machine-checked lemmas: (i) the positive and
negative channels are *information-theoretically isolated* (§5), which is exactly why the negative sign
is non-redundant; (ii) an *automation boundary* — the specification below the two-sign teaching set is
oracle-free, the teaching set itself is not, because $\sigma =$ teaching dimension is undefined without
a teacher (§6); and (iii) an *unqualified correctness* certificate is available precisely on the
finite-domain, decidable-equivalence class and is obstructed elsewhere by Rice's theorem (§8). We give
the disposition calculus that keeps degenerate negative measurements from corrupting the score (§7),
the admissibility condition governing population-derived censors (§9), the composition obstruction that
makes the valuable negative constraints super-additive (§10), and the operational realization against
the live engine (§11). §12 formalizes the authoring problem the whole construction reduces to.

---

## 1. Preliminaries

We recall the mutation-system apparatus (SC §2) and fix notation.

**Definition 1.1 (Mutation system).** A *mutation system* is a tuple
$\mathcal{M} = (D, R, \mathrm{sem}, \mu)$ where $D$ is a set of inputs, $R$ a set of outputs,
$\mathrm{sem} : \mathrm{Prog}(D,R) \to (D \to R)$ a semantic function assigning to each program its
denotation, and $\mu$ a *mutation policy* assigning to each program $P$ a finite set
$\mathrm{Mut}_\mu(P) \subseteq \mathrm{Prog}(D,R)$ of syntactic variants.

**Definition 1.2 (Kill, equivalence).** A test $t \in D$ *kills* a mutant $m$ with respect to $P$ iff
$\mathrm{sem}(P)(t) \neq \mathrm{sem}(m)(t)$. Programs are *behaviorally equivalent*,
$P_1 \equiv P_2$, iff $\mathrm{sem}(P_1)(x) = \mathrm{sem}(P_2)(x)$ for all $x \in D$. The
*non-equivalent mutants* are $\mathrm{Mut}^{\neq}_\mu(P) = \{ m \in \mathrm{Mut}_\mu(P) : m \not\equiv P \}$.

**Definition 1.3 (Specification completeness, specification complexity).** A suite $T \subseteq D$
*achieves specification completeness* ($\mathrm{SC}=1$) for $P$ under $\mu$ iff $T$ kills every
$m \in \mathrm{Mut}^{\neq}_\mu(P)$. The *specification complexity* is
$$\sigma(P,\mu) = \min \{\, |T| : T \text{ achieves } \mathrm{SC}=1 \text{ for } P \text{ under } \mu \,\}.$$

**Definition 1.4 (Value vs. run specification).** A kill by an assertion that distinguishes the
returned value is a *value* kill; a kill by crash or timeout is a *run* kill and pins only that the
mutant *executed differently*, not what it computes. Write $\mathrm{kill}_v$ for the assertion-kill
relation. *Value-completeness* requires every killable mutant to be $\mathrm{kill}_v$-killed; run kills
bank nothing toward it. (Detective ARCHITECTURE §0; the distinction is enforced, not cosmetic, and it
recurs on the negative side in §7.)

**Proposition 1.5 (σ is a two-sign teaching dimension; cited).** For finite $D$ with faithful oracles,
$\sigma(P,\mu)$ equals the teaching dimension $\mathrm{TD}$ of the $\equiv$-class of $P$ in the concept
class induced by $\mu$ (SC Thm 2.7, machine-checked as `T5_17_teaching_dimension_{lower,upper}_bound`).
Teaching dimension is defined as the minimum labeled sample — labels drawn from $\{+,-\}$ — that
uniquely identifies a target concept (Goldman–Kearns 1995; Goldman–Mathias 1996).

*Remark 1.6.* Proposition 1.5 is the load-bearing inherited fact. Every subsequent claim about the
negative sign is a consequence of $\sigma$ being equal to an object whose definition already ranges
over two labels, instantiated at a policy that supplies one.

---

## 2. The Sign Asymmetry

**Definition 2.1 (Sign of a policy).** A mutation policy $\mu$ is *positive* if every
$m \in \mathrm{Mut}_\mu(P)$ is obtained by a transformation of the *program text* of $P$ (a variant
implementation), and the kill relation compares $\mathrm{sem}(m)$ against $\mathrm{sem}(P)$ at test
inputs. All policies presently realized in Wesker (Def. 11.1) are positive.

**Proposition 2.2 (One-sign adequacy).** Let $\mu$ be positive. Then a suite achieving $\mathrm{SC}=1$
under $\mu$ certifies membership in exactly one label class of the teaching set of Prop. 1.5: it
witnesses, for each non-equivalent variant, an input on which $P$ and the variant *differ*. It does not
witness any *non-example* — an input/output pair that no correct implementation of the intended
function may produce.

*Justification.* Immediate from Def. 2.1: a positive policy's evidence is of the form "variant $m$ is
distinguishable from $P$", which is a positive-label discrimination among candidate implementations.
Teaching dimension over both labels additionally admits evidence of the form "no admissible concept
labels $(x,y)$ positive", i.e. a bound on the concept *from above*. No positive policy expresses this,
because it has no term ranging over the codomain independently of the program text. $\square$

**Corollary 2.3 (The badge is honestly scoped and half-signed).** A certificate
`SC = 1 (operator universe, modulo N unproven-equivalent)` is exactly as strong as it states and no
stronger: it is adequacy over the *positive* sign of a two-sign teaching set. This is not overclaiming;
it is single-sign completeness, correctly labeled.

**Definition 2.4 (Two-sign policy).** Given a positive policy $\mu$ and a negative policy $\mu^-$
(Def. 3.1), the *two-sign policy* is $\mu^{\pm} = \mu \cup \mu^-$, and the *two-sign specification
complexity* is $\sigma(P, \mu^{\pm})$.

**Proposition 2.5 (No new theory is required).** Every result of SC that is stated over an arbitrary
policy — Blum-measure status (SC Thm 2.5), the exponential separation (SC Thm 2.6), the five-field
identification (SC §4), the composition gap (SC Thm 3.15) — holds for $\mu^{\pm}$ by instantiation.
$\mu^-$ is a second policy instantiation, not an extension of the metatheory.

*Justification.* The cited results quantify over $\mu$ subject only to finiteness conditions on
$\mathrm{Mut}_\mu(P)$ (Def. 1.1), which $\mu^-$ satisfies (Def. 3.1 fixes a finite perturbation
family). $\square$

**Historical note 2.6.** The two labels are Winston's two structural-learning operators (1970):
*generalize* from a positive example, and *specialize* from a **near-miss** — a non-example differing
in one crucial respect, installing a MUST-NOT link. Software testing inherited the first and dropped
the second; the drop was not argued but structural — the test-as-example framing has no slot for a
non-example. The present construction restores the second operator to the code end of a homology
(program identity ↔ concept identity) whose semantic end already runs both (Genesis IV-F/IV-G).

---

## 3. The Output-Space Mutation Operator μ⁻

**Definition 3.1 (Perturbation, negative policy).** Fix a program $P$ with denotation
$f = \mathrm{sem}(P) : D \to R$ and covering suite $T \subseteq D$. A *perturbation* is a partial map
$p : R \rightharpoonup R$. The *perturbed denotation* is the post-composition
$f \oplus p := p \circ f$ (defined where $p$ is defined on $f(x)$). A *negative policy* $\mu^-$ is a
finite family $\Pi$ of perturbations together with, for each $p \in \Pi$, a *sub-mode key* naming the
codomain invariant $p$ probes (Def. 11.4). The *negative mutants* of $P$ are $\{ f \oplus p : p \in \Pi \}$.

**Definition 3.2 (Unpinned perturbation, negative kill matrix).** A perturbation $p$ is *unpinned* by
$T$ iff every covering test passes on the perturbed denotation:
$$\mathrm{unpinned}(p) \iff \forall t \in T:\ t\ \text{passes on}\ f \oplus p.$$
Equivalently, $p$ is *killed* iff some $t \in T$ fails on $f \oplus p$. The *negative kill matrix* has
one row per $p \in \Pi$, marked killed/unpinned; an unpinned $p$ is a **negative degree of freedom** —
an output dimension no covering test constrains.

*Remark 3.3 (polarity coincides with the positive matrix).* An unpinned $p$ is the exact analogue of a
surviving positive mutant: "all covering tests pass" is survival in both matrices. Hence the value-vs-run
precedence of Def. 1.4 transfers verbatim — a perturbation killed by an *assertion* pins the return
value (value kill); a perturbation that only makes a covering test *crash* is a run kill and banks
nothing. The two matrices are homogeneous in disposition, which is what permits the shared pipeline of
§11.

**Definition 3.4 (Reach of a negative policy).** The *reach* $\rho(\mu^-)$ is the set of behavioral
distinctions in the codomain expressible as $f \oplus p$ for some $p \in \Pi$. A negative policy is
*return-total* if every element of its reach is realizable by perturbing the *return value* of $f$, and
*codomain-total* if its reach is all of the observable output behavior of $f$ (including outputs
delivered by mutation of shared state, by yielding, or by exception).

**Proposition 3.5 (μ⁻ reaches distinctions no positive policy can).** There exist $P$ and a
behavior-changing rewrite $P'$ (i.e. $P' \not\equiv P$) with $P'$ *not* in $\mathrm{Mut}_\mu(P)$ for the
operative positive $\mu$, yet a single perturbation $p \in \Pi$ is killed by a test that would witness
$P' \not\equiv P$.

*Evidence (measured, 2026-08-07).* `boltons/strutils.py::slugify` converges to
`SC = 1 (modulo 6 unproven-equivalent)`. The rewrite
`ret = delim.join(split_punct_ws(text)) or delim if text else ''` $\to$
`ret = ... if text else ''` changes behavior (`slugify("!!!")`: `'_' \to ''`) and is outside the operative
positive $\mu$, so it passes the positive badge. The perturbation $p = (\text{non-empty} \mapsto \text{empty})$
is killed by any test asserting a non-empty result on non-empty input, and is *inexpressible* as any
program-text mutation. Hence $\rho(\mu^-)$ properly contains distinctions outside the positive reach.
$\square$

*Corollary 3.6.* Positive completeness and negative completeness are independent axes; neither
subsumes the other, and $\sigma(P,\mu^\pm)$ is the first quantity to bound behavioral identity over
both.

---

## 4. The Intentional Semantic Space

We partition the behavioral degrees of freedom of $f$ by the oracle that resolves each.

**Definition 4.1 (Three regions).** Relative to a two-sign teaching set for $P$:
$$
\mathrm{DOF}(f) = \underbrace{\mathrm{DOF}^{+}}_{\text{positive-pinned}} \ \sqcup\ \underbrace{\mathrm{DOF}^{-}}_{\text{negative-pinned}} \ \sqcup\ \underbrace{\mathrm{DOF}^{0}}_{\text{mechanical residual}},
$$
where $\mathrm{DOF}^{+}$ is pinned by positive intent tests (oracle: a grounded value, "the function
returns $y$ on $x$"), $\mathrm{DOF}^{-}$ is pinned by the negative fence (oracle: the upper bound, "no
correct implementation produces $(x,y)$"), and $\mathrm{DOF}^{0}$ is the residual on which no intent of
either sign has a claim — every value consistent with $\mathrm{DOF}^{+} \cup \mathrm{DOF}^{-}$ is
admissible.

**Definition 4.2 (Solve/teach decomposition; cited).** Write $I_{\mathrm{solve}}(P)$ for the
information required to resolve $\mathrm{DOF}(f)$ after structure has done all it can, and
$I_{\mathrm{solve}} = I_{\mathrm{ind}} + I_{\mathrm{ext}}$ (SIGNIFICANCE_WEIGHTING §12), where
$I_{\mathrm{ind}}$ is corpus-teachable (recoverable from the population of call sites) and
$I_{\mathrm{ext}}$ must be supplied by a teacher.

**Proposition 4.3 (The `--input` residual is mostly mis-classified un-authored intent).** In the
present tool, the interactive `--input` demand arises when positive synthesis reaches a branch behind a
domain value the code does not hold. Each such demand is a *second-sign* teaching label paid lazily and
per-run. Under a complete two-sign teaching set authored once, $\mathrm{DOF}^{0}$ contains no
intent-bearing residual, so synthesis over $\mathrm{DOF}^{0}$ is oracle-free.

*Justification.* A synthesis demand records that some input distinguishes a mutant only under a value
carrying intent (Def. 2.2's non-example content). Authoring $\mathrm{DOF}^{-}$ discharges exactly that
content at the teaching set, moving it out of the per-run residual. What remains in $\mathrm{DOF}^{0}$
is by construction value-indifferent. $\square$

---

## 5. Channel Isolation

The positive and negative channels measure orthogonal quantities. This is the property that makes the
negative sign worth adding rather than a re-derivation of the first.

**Definition 5.1 (Channel information).** For a construct choice $c$ realizing $f$ (a particular program
text among value-equivalent alternatives), let $I^{+}(c)$ be its information in the positive channel —
its effect on the value-equivalence class $[f]_{\equiv}$ — and $I^{-}(c)$ its information in the negative
channel — its effect on the fenced region $\mathrm{DOF}^{-}$ it induces or exposes.

**Theorem 5.2 (Isolation).** $I^{+}$ and $I^{-}$ are independent: there exist construct choices $c_1,
c_2$ with $\mathrm{sem}(c_1) \equiv \mathrm{sem}(c_2)$ (so $I^{+}(c_1 \leftrightarrow c_2) = 0$) yet
$I^{-}(c_1 \leftrightarrow c_2) > 0$.

*Proof (by the canonical witness).* Take $c_1 : x,y \mapsto x + y$ and $c_2 : x,y \mapsto (3x+3y)/3$.
Then $\mathrm{sem}(c_1) \equiv \mathrm{sem}(c_2)$ over $\mathbb{R}$, so their positive-channel
difference is nil by Def. 1.2. But $c_2$ introduces a division whose denominator is a constant that a
degenerate substitution can drive to $0$, exposing a codomain behavior (an `undefined`/exception at a
point where $c_1$ is total) that $c_1$ does not have. That behavior is a nonzero element of
$\mathrm{DOF}^{-}$ (a MUST-NOT: "must not raise on this class") visible in $c_2$'s negative channel and
absent from $c_1$'s. Hence $I^{-}(c_1 \leftrightarrow c_2) > 0$ while $I^{+}(c_1 \leftrightarrow c_2) =
0$. $\square$

**Corollary 5.3 (Non-redundancy).** The negative sign is not derivable from the positive one. Were the
channels coupled, $\mu^-$ would be redundant; Theorem 5.2 is the formal statement of its worth.

**Definition 5.4 (Overlap coupling).** Although the channels' *content* is orthogonal, both constrain
the same graph of $(x, y) \in D \times R$ pairs. A positive claim $f(x) = y$ and a negative claim
$(x,y) \in C$ (fenced) *collide* at the pair $(x,y)$.

**Proposition 5.5 (The consistency relation is decidable but partial).** Define the two-sign teaching
set *inconsistent* iff $\exists (x,y): (T^{+} \vdash f(x)=y) \wedge ((x,y) \in C)$. Inconsistency is
decidable at overlap points and its detection is the code analogue of mismatch repair (a base-pair
contradiction between strands). But overlaps are sparse — a consequence of Theorem 5.2 — so the check is
a *partial* verifier: it catches inconsistent mis-triage and is silent on the non-overlapping negative
channel.

**Corollary 5.6 (Two irreducible residues).** What survives the consistency check un-verifiable is
(i) *consistently-wrong intent* at overlap points — a coherent teaching set describing the wrong
function, the correctness-vs-completeness floor (`decompose` preserves behavior, not intent); and
(ii) the entire *non-overlapping* negative channel, which has no positive strand to repair it and rests
solely on the admissibility governance of §9.

---

## 6. The Automation Boundary

**Definition 6.1 (Teaching set, mechanical residual).** Let $\Sigma^{\pm}(P)$ be a minimal two-sign
teaching set for $P$ (the realized $\sigma(P,\mu^\pm)$-witness). The *mechanical residual* is the
specification work over $\mathrm{DOF}^{0}$ (Def. 4.1).

**Theorem 6.2 (Automation boundary).** The specification of $\mathrm{DOF}^{0}$ is computable without an
oracle; the specification of $\Sigma^{\pm}(P)$ is not, and no refinement of tooling removes the latter
dependency.

*Proof.* Over $\mathrm{DOF}^{0}$ every admissible value is consistent by Def. 4.1, so a synthesis
procedure may select any consistent witness mechanically (Prop. 4.3); this is the converge loop with
the intent-bearing demands discharged. For $\Sigma^{\pm}(P)$: by Prop. 1.5, $\sigma = \mathrm{TD}$, and
teaching dimension is *defined* by a teacher who knows the target concept and minimizes identification
cost. Absent a teacher there is no target concept, hence no dimension — the quantity is undefined, not
zero. Therefore the teaching set is an irreducible input; automation is total below $\Sigma^{\pm}$ and
nil at it. $\square$

*Remark 6.3.* Theorem 6.2 locates the human contribution at its information-theoretic minimum. It does
*not* say code authorship is automated; it says verification and pinning are mechanized down to the
teaching set, and the teaching set is the compressed formal statement of what the author uniquely holds
— intent, of both signs. The positive half of this was already the tool's stated boundary ("the human
belongs at intent"); the negative half — the MUST-NOTs — is the part Theorem 6.2 newly names as equally
teacher-supplied and, until now, leaked into the synthesis loop (Prop. 4.3).

---

## 7. Disposition Calculus and the UNDEFINED Verdict

The negative channel has its own measurement failure mode, which must not contaminate the score.

**Definition 7.1 (Scored dispositions; [traced]).** Wesker assigns each mutant a disposition by the
precedence chain `harness_error ≺ not_installed ≺ not_entered ≺ cut ≺ {killed_after_entry,
survived_after_entry}` (`mutant_disposition`, Wesker/engine.py). Only the last pair is *scored*
(`SCORED_DISPOSITIONS = ("killed_after_entry", "survived_after_entry")`); `cut` denotes "executed, but
the measurement is truncated or uncontained, hence evidence of neither kill nor survival."

**Definition 7.2 (Negative measure, degeneracy).** A negative policy induces a measure $\nu(p)$ on each
perturbation — in the simplest form a ratio whose denominator is the size of the observable codomain
universe for $f$ (Def. 3.4). $\nu(p)$ is *degenerate* when that denominator is $0$: the codomain is a
singleton, unobservable, or the perturbation inverts a quantity a degenerate input sends to $0$
(Theorem 5.2's mechanism). Write $\nu(p) = \bot$ in that case.

**Definition 7.3 (The UNDEFINED disposition).** Extend the disposition set with `undefined`, a sibling
of `cut`: a perturbation with $\nu(p) = \bot$, or one whose application to the observed return raises
because it is mis-typed to the codomain (Def. 11.6), receives `undefined`. It is **not** added to
`SCORED_DISPOSITIONS`.

**Proposition 7.4 (Soundness of abstention).** Under Def. 7.3 an `undefined` perturbation is coerced to
neither verdict: not to *unconstrained* (which would read a failed measurement as "nothing forbidden
here", admitting the intent error of Theorem 5.2), and not into $\mathrm{SC}=1$ (which would mint a
false badge over an unmeasured negative universe). It is reported as a measurement limit, exactly as an
unclassified positive survivor is (`audit --check` warns and exits $0$; `--check-strict` exits $2$).

*Remark 7.5.* Def. 7.3 is the negative-channel instance of two standing disciplines: value-vs-run
(Def. 1.4 — a measurement that ran but yields no value-evidence banks nothing) and the
cannot-determine/determined-false distinction. Over-forbidding (the degenerate controller of §9,
$\mathrm{EIG}=0$) and $\nu=\bot$ (the collapsed denominator here) are the two arithmetics of the same
principled-abstention requirement.

---

## 8. Decidability of the Unqualified Contract

**Theorem 8.1 (Unqualified correctness on the decidable class).** Let $P$ have finite domain $D$ with
decidable $\equiv$, and let $\mu^{\pm}$ be *complete* (its two-sign reach enumerates the whole behavior
space of $f$ up to $\equiv$). Then an $\mathrm{SC}=1$ two-sign contract is a decision procedure for the
behavioral identity of $f$, and the certificate `provably correct` carries **no** policy qualifier.

*Proof sketch.* For finite $D$, $\equiv$ is decidable by exhaustion and $\sigma(P,\mu^{\pm})$ is finite
and its witness enumerable (SC Thm 2.5, the finite-domain Blum case). A complete $\mu^{\pm}$ leaves no
behavioral distinction unexpressed, so $\mathrm{SC}=1$ pins $[f]_{\equiv}$ to a point; there is no
residual observing-set parenthetical because the observing set is the whole space. $\square$

**Theorem 8.2 (Obstruction off the decidable class).** For $P$ over an infinite domain, $\equiv$ is
undecidable (Rice's theorem; Budd–Angluin 1982 for mutation equivalence specifically), so no finite
$\mu^{\pm}$ is complete and the certificate retains its qualifier `correct modulo (μ ∪ μ⁻), observing
set named`.

*Corollary 8.3 (The qualifier is decidability, not maturity).* The boundary between the unqualified and
qualified certificate is Theorems 8.1–8.2, a decidability dichotomy — not the engineering completeness
of $\mu^{-}$. Enlarging $\mu^{-}$ widens the reach within the qualified regime; it does not move the
boundary. The certificate must *name which side it is on* (the observing-set requirement).

---

## 9. Censors: Population-Derived Negative Constraints

$\mu^-$ is per-function and mechanical. A second negative mechanism is not.

**Definition 9.1 (Censor).** A *censor* is a set $c \subseteq D \times R$ of forbidden input/output
pairs, asserted as "no correct implementation of the intended function produces $(x,y)$", and derived
from *observed near-misses across the population of call sites* rather than from $f$ alone. A censor
occupies the $I_{\mathrm{ind}}$ region of Def. 4.2: it is latent in the corpus and unreachable per single
function read (the statement "no caller ever passes `None`" is not a fact about $f$; it is a fact about
$f$'s call-site population).

*Remark 9.2 (one-function law preserved).* The proof stays per-function; only the censor's *derivation*
reads the population. This is co-occurrence over call sites, not a statistical smear of per-function
mutation scores across unrelated functions (the object ARCHITECTURE §11 forbids). The distinction is
the license.

**Definition 9.3 (Admissibility).** A censor $c$ is *admissible* iff
(i) it is *spine-sourced* — carved from an observed near-miss (a real call site, or a witness from a
rejected rewrite), never authored a priori, and structurally incapable of confirmation from the engine's
own derived output; **and** (ii) $\sigma(P \mid C \cup \{c\}) > 0$ — the program space still admits
plurality after adoption.

**Proposition 9.4 (Admissibility is a well-definedness condition; cited).** Without (ii) the central
quantity is undefined, not merely unsafe (SIGNIFICANCE_WEIGHTING §14): a censor confirmed from the
engine's own derivations reduces the residual by construction while carrying zero information
($L_{\mathrm{ind}} \to 1$ vacuously). Over-forbidding is the degenerate controller from the negative
side — forbid enough and exactly one program survives, $\sigma$ collapses, $\mathrm{EIG}=0$ — detected
by the machine-checked `self_confirming_cannot_certify` and `falsifiability_pivot` (mutual information
$>0 \iff$ the answer channel is non-degenerate), with the retained-plurality budget (SSL §4.4;
$\hat{R}$ not driven to $0$) as the quantitative lower bound.

**Definition 9.5 (Verdict vocabulary).** A censor is `UNVERIFIED` until spine-sourced and passing
(ii), and is never promoted to `forbidden` by assertion — mirroring `candidate-equivalent — UNPROVEN`
never promoted to `equivalent`. An LLM- or a-priori-authored constraint is an unverified assertion and
must not gate. Negative results occupy their own reporting channel and are never folded into the kill
count, for the reason run kills are not (Def. 1.4): a censor is an exclusion with a different warrant,
not a kill.

---

## 10. Composition and the Bridge Obstruction

The negative constraints of interest are exactly the ones that break the clean greedy guarantee.

**Definition 10.1 (Composition gap; cited).** For $P = A \circ B$,
$\sigma(A \circ B, \mu) \le \sigma(A,\mu) + \sigma(B,\mu) + \gamma(A,B)$, with $\gamma \ge 0$ the
composition gap, $\gamma \le |\mathrm{InterfaceMutants}(A,B)|$, and $\gamma = 0$ for
specification-independent components (SC Thm 3.15, 3.16).

**Definition 10.2 (Bridge, supermodular degree).** In the coverage formulation, $f(S) = |\bigcup_{v \in
S} \mathrm{cover}(v)|$ is submodular over a *fixed* ground structure. A constraint whose adoption
*changes the ground graph* — a *bridge* joining two previously-disjoint clusters — has small marginal
gain alone and large gain once a second bridge is present; gains are super-additive. The *supermodular
degree* $d$ (Feige–Izsak) counts adoptions that connect previously-disjoint components.

**Proposition 10.3 (Three names, one quantity).** $\gamma$ (composition gap), $d$ (supermodular
degree), and the bridge count coincide: $\gamma$ vanishes for independent components, $d = 0$ for no
bridges, and independent components *are* no bridges. Measuring interface obligations measures $d$.

**Conjecture 10.4 (Censors are bridges).** In a sparse obligation graph (a call graph over functions is
plausibly sparse; Regenesis's rule graph measured branching $b \approx 0.46$–$0.56 < 1$), a censor
spanning call sites is a bridge — super-additive with positive tests, not redundant with them. This is
*stronger* than "negatives are valuable" and *worse* for tractability: the biggest wins and the reason a
clean greedy bound fails are the same constraints.

*Caveat 10.5 (do not import dense-graph constants).* The submodular structure (coverage, monotonicity)
transfers; the constants ($L = 0.528$, the $\sim 3\%$ knee, the $28\times$ drop) were measured on a
*dense* graph and say nothing about a sparse one. Measure $d$ on the obligation graph before asserting
any bound. The target theorem is bounded-curvature greedy degrading in $d$ and recovering $(1-1/e)$ at
$d = 0$, not submodular greedy. What survives regardless: monotonicity of forward closure (nearly free),
and submodularity *within* a connected component.

**Corollary 10.6 (κ-gated removal).** `audit --remove` currently proposes deleting a test that is
line- and mutant-redundant *for one function*; the field failure is that the test was load-bearing over
the closure — Def. 10.2's bridge counterexample. The correct invariant is significance-weighted:
$\mathrm{safe\_remove}(t) \iff \kappa\text{-}\mathrm{closure}(T) = \kappa\text{-}\mathrm{closure}(T
\setminus \{t\})$, resting on the machine-checked SC Thm 2.3 and 3.11. Blocked on §13 Q1 (κ for code).

---

## 11. Operational Realization (Wesker)

All facts in this section marked [traced] were read from `Wesker/engine.py` on 2026-08-22.

**Definition 11.1 (Mutant, categories; [traced]).** A `Mutant` is a dataclass carrying
`category: MutationCategory`, `original_node`/`mutated_node : ast.AST` (both required), a content-addressed
`mutant_id`, a positional `target_index`, a `mutated_line`, and a `dimension` string. The categories are
`VALUE, SWAP, STATE, BOUNDARY, TYPE, ARITHMETIC, LOGICAL, STMT, EXCEPTION, DATAFLOW` — all *positive*
(Def. 2.1).

**Observation 11.2 (Two generation classes; [traced]).** Generation is not uniform. The record-factory
family (`_RECORD_MUTATOR_FACTORIES`: `VALUE, BOUNDARY, ARITHMETIC, LOGICAL, SWAP, TYPE, STMT`) walks
candidate *sites* via `_BaseMutator` and records one dimension per site. `STATE, EXCEPTION, DATAFLOW`
are **not** in that registry: each has a bespoke `_generate_*_mutants` and `_record_*_dimensions` and
still emits `Mutant` objects into the shared evaluate/score/cover pipeline. This second class is the
structural precedent for $\mu^-$.

**Definition 11.3 (Kill attribution reused; [traced]).** `evaluate_mutant(mutant, tests, original_func,
…)` compiles the mutated function, monkey-patches it into each test's namespace, runs, and attributes a
kill under VALUE-SPECIFICATION PRECEDENCE: an assertion kill pins the value and is order-independently
final; a crash/timeout kill is provisional (the search continues for a later assertion kill). This is
exactly the calculus Def. 3.2–3.3 require of the negative matrix.

**Definition 11.4 (Form A — return-site rewrite).** Realize $\mu^-$ as a positive-shaped AST mutator:
for each `return X` in $f$, and each $p \in \Pi$, emit the mutant `return X` $\to$ `return _perturb_p(X)`.
Each such mutant is an ordinary `Mutant` with a genuine `mutated_node`, so it rides the entire pipeline
of Def. 11.3 with no new type. Home: a new category `MutationCategory.OUTPUT`, generated by a bespoke
`_generate_output_perturbations` and recorded by `_record_output_dimensions` (template: the DATAFLOW
`return_sub` sub-mode already mutates return sites [traced]). Reach: return-total (Def. 3.4).

**Proposition 11.5 (Equivalence generalizes for Form A; [traced]).** `check_equivalent(func_node, mutant)`
compiles original and mutant and compares outputs on boundary inputs. For Form A a perturbation *is* a
compilable mutant, so `check_equivalent` decides candidate-equivalence of perturbations with no new
machinery. This resolves §13 Q3 for Form A. (Inherited limitation: `check_equivalent` skips methods —
no synthesizable `self`.)

**Definition 11.6 (Form B — runtime wrapper).** Realize $\mu^-$ as a wrapper on the function object that
perturbs the return at call time with no `return`-node rewrite. This requires a sibling representation
and a parallel evaluate path, *bespoke per sibling type* (generator, implicit-`None`, side-effect/state
codomain). Reach: codomain-total (Def. 3.4).

**Proposition 11.7 (Form B is required for the completeness guarantee).** Form A is return-total but not
codomain-total: functions whose observable output is delivered otherwise than by the return value lie
outside its reach. Hence the certificate of Theorem 8.1 has a hole exactly there unless Form B closes
it. Form B is therefore not optional coverage but a load-bearing component of the completeness claim;
Form A is the tractable walking skeleton, Form B the guarantee-completing pass.

**Definition 11.8 (The perturbation family Π — a type-indexed operator set).** $\Pi$ is not flat. It is
a family $\Pi = \bigcup_R \Pi_R$ indexed by the codomain type $R$ (Def. 11.10 selects the applicable
$\Pi_R$ by observed/inferred type), exactly as the positive mutators are category-dispatched. Each
perturbation $p$ fences a single codomain invariant — a MUST-NOT of the form "no correct implementation
produces this output deviation" — and is tagged **A** (realizable as a return-site rewrite, Def. 11.4)
or **B** (requires the runtime wrapper, Def. 11.6). We enumerate $\Pi$ by codomain structure.

*(i) Universal — existence and input-dependence (apply to every $R$).*

- $p_{\mathrm{none}}: v \mapsto \texttt{None}$ (or a typed sentinel) — **the output must exist.** [A]
- $p_{\mathrm{const}[c]}: v \mapsto c$ for a fixed $c$ (drawn from an observed return) — **the output must
  depend on the input.** [A] The single most load-bearing perturbation (Remark 11.9).
- $p_{\mathrm{id}[i]}: v \mapsto x_i$ (return the $i$-th argument unchanged) — **the output must be a
  non-trivial transform of its input, not a passthrough.** [A] (arity $\ge 1$)
- $p_{\mathrm{zero\text{-}of}}: v \mapsto \mathbf{0}_R$ (the canonical inhabitant: $0$, `""`, `[]`, `{}`)
  — **the output is not trivially the type's zero.** [A]
- $p_{\mathrm{type}}: v \mapsto \tau(v)$ (coerce to a distinct type) — **the output type is load-bearing.**
  [A] Subsumes the measured `str`$\to$`bytes` API-break (§Prop. 3.5's sibling witness).
- $p_{\mathrm{stale}}: v \mapsto v_{\mathrm{prev}}$ (the previous call's return) — **the output is a pure
  function of *this* call, carrying no leaked state / accidental memoization.** [B]

*(ii) Boolean $R$.*

- $p_{\lnot}: b \mapsto \lnot b$ — the boolean is load-bearing. [A] (near-redundant with a positive
  LOGICAL mutant on the return expression; see the orthogonality criterion, Remark 11.9.)
- $p_{\top}, p_{\bot}: b \mapsto \texttt{True}/\texttt{False}$ — **the predicate must not be constant.**
  [A] The two truth constants are *distinct* fences — the always-true and always-false degenerate
  classifiers are different failures and must not collapse into one.

*(iii) Numeric $R$ (int / float).*

- $p_{\mathrm{neg}}: v \mapsto -v$ — the sign is load-bearing. [A]
- $p_{\mathrm{abs}}: v \mapsto |v|$ — **the output may legitimately be negative** (distinct from
  $p_{\mathrm{neg}}$: fences sign-*presence*, not sign-*flip*). [A]
- $p_{\pm 1}: v \mapsto v \pm 1$ — the exact integer / boundary value. [A]
- $p_{\pm\varepsilon}: v \mapsto v \pm \varepsilon$ — the exact real value (the continuous boundary
  analogue). [A]
- $p_{\mathrm{scale}[k]}: v \mapsto k v$ — magnitude / units load-bearing. [A]
- $p_{\mathrm{round}}: v \mapsto \lfloor v \rceil$ — precision load-bearing. [A]
- $p_{\mathrm{NaN}}: v \mapsto \mathrm{NaN}$, $p_{\infty}: v \mapsto \pm\infty$ — **the output must be a
  finite number.** [A] (float)
- $p_{0}: v \mapsto 0$ — **the output must be non-zero** where that is an invariant (denominators,
  normalizers). [A]

*(iv) String $R$.*

- $p_{\mathrm{empty}}: s \mapsto \texttt{""}$ — **non-empty on non-empty input** (the measured slugify
  fence). [A]
- $p_{\mathrm{trunc}}: s \mapsto s[{:}k]$ — full content load-bearing. [A]
- $p_{\mathrm{case}}: s \mapsto \mathrm{swapcase}(s)$ — case load-bearing. [A]
- $p_{\mathrm{ws}}: s \mapsto \mathrm{strip/pad}(s)$ — whitespace load-bearing. [A]
- $p_{\mathrm{rev}}: s \mapsto \mathrm{reverse}(s)$ — character order load-bearing. [A]

*(v) Container $R$ (list / tuple / set / dict).*

- $p_{\mathrm{empty}}: xs \mapsto \varnothing$ — non-empty invariant. [A]
- $p_{\mathrm{perm}}: xs \mapsto \pi(xs)$ — **order load-bearing** (a no-op under set/dict-key semantics,
  which is itself the signal that order is *not* load-bearing there). [A]
- $p_{\mathrm{drop}}: xs \mapsto xs \setminus \{e\}$ — cardinality / element completeness. [A]
- $p_{\mathrm{dup}}: xs \mapsto xs + [e]$ — multiplicity load-bearing (list- vs set-semantics). [A]
- $p_{\mathrm{singleton}}: xs \mapsto [e]$ — cardinality load-bearing. [A]
- $p_{\mathrm{ctype}}: \texttt{list} \leftrightarrow \texttt{tuple} \leftrightarrow \texttt{set}$ — the
  container's mutability / order / uniqueness contract is load-bearing. [A]
- $p_{\mathrm{dict}}: $ key$\leftrightarrow$value swap, drop-field, default-field — the key/value binding
  and per-field presence are load-bearing. [A]

*(vi) Structured / object $R$ (dataclass, namedtuple, custom).*

- $p_{\mathrm{field}[k]}$: perturb one field recursively (apply $\Pi_{R_k}$ to field $k$) — per-field
  load-bearingness. [A]
- $p_{\mathrm{class}}$: return a super- or sub-type instance — the exact class is load-bearing (a
  Liskov-style fence). [A/B]

*(vii) Ordered / comparable $R$ (beyond numeric).*

- $p_{\mathrm{adj}}: v \mapsto \mathrm{succ}/\mathrm{pred}(v)$ in the order — the exact position in the
  order is load-bearing. [A]
- $p_{\mathrm{clamp}}: v \mapsto \mathrm{clip}(v, \ell, u)$ — a range invariant. [A]
- $p_{\mathrm{sortbreak}}$: for a sequence expected sorted, transpose two elements — sortedness
  load-bearing. [A]

*(viii) Effect / non-return codomain $R$ (Form B only).*

- $p_{\mathrm{yield}}$: suppress or inject a yielded element (generators) — the yielded sequence is the
  output. [B]
- $p_{\mathrm{raise}}$: swallow a raise, or inject one — the raise-vs-return contract (the *should-raise*
  side, complementary to the positive EXCEPTION category). [B]
- $p_{\mathrm{state\text{-}noop}}$: omit the documented side effect — the side effect is the output. [B]
- $p_{\mathrm{state\text{-}extra}}$: perform an extra mutation — **no unintended side effects.** [B]

**Remark 11.9 (the load-bearing core, and the orthogonality criterion).** Two design facts govern $\Pi$.
*(a) The independence pair.* $p_{\mathrm{const}}$ and $p_{\mathrm{id}}$ are the value-space analogues of
the MC/DC independence conditions — "the output is a function of the input" ($\lnot$ const) and "the
output is not its input" ($\lnot$ id). A function silently ignoring its arguments, or acting as a no-op,
is caught by *no other* perturbation and by no positive operator; these two are non-negotiable. *(b)
Orthogonality to the positive reach.* By Prop. 3.5 the *worth* of $\mu^-$ is the region the positive
policy cannot express. Perturbations that duplicate a positive operator ($p_{\lnot}$ ≈ a LOGICAL mutant
on the return; $p_{\pm 1}$ ≈ a BOUNDARY/ARITHMETIC mutant) are admissible but low-value for **A**; the
high-value members are those that perturb the *value independently of how it was computed*
($p_{\mathrm{const}}, p_{\mathrm{id}}, p_{\mathrm{empty}}$ on a computed string, $p_{\mathrm{NaN}}$,
$p_{\mathrm{perm}}$). Design criterion: **populate $\Pi_R$ preferentially with perturbations orthogonal
to $\rho(\mu)$**, retaining the redundant ones only where the codomain-total guarantee (Prop. 11.7)
requires them.

**Definition 11.8b (Π-completeness).** $\Pi$ is *complete for codomain $R$* iff its reach $\rho(\mu^-)$
separates every pair of behaviors distinguishable at the codomain: for admissible $f$ and any
inadmissible near-miss $f'$ with $f \not\equiv f'$ observable at the output, some $p \in \Pi_R$ realizes
the crossing (some covering test fails on $f \oplus p$ exactly when it would witness $f \ne f'$). For
*finite* $R$ this is achievable by one perturbation per codomain deviation (the negative analogue of SC
Thm 2.2's one-test-per-mutant); for structured $R$, $\Pi_R$ must *generate*, under composition, enough of
the deviation monoid on $R$ to separate the intended concept from its near-misses. Whether a *finite*
$\Pi_R$ is complete for a given structured $R$ is the negative analogue of SC §2.3's open
operator-basis question (§13 Q4), and its measurement requires Fork 2's observed codomain type (Def.
11.10).

**Definition 11.10 (Typing Π — two forks).** A perturbation must be typed to the codomain to be valid,
and the engine holds **no return-type model** [traced: `run_function_profiling` takes `func_node`,
`test_functions`, `original_func`, `is_pure` — no return type and no return-value capture; only
`check_equivalent` calls $f$ directly, gated on numeric boundary inputs].

* **Fork 1 (static / AST-typed).** Type $\Pi$ from the AST alone: universal perturbations
  unconditionally; conditional ones from return-node literal/annotation evidence. A mis-typed
  perturbation raises on application and receives `undefined` (Def. 7.3), so Fork 1 **over-generates and
  lets the disposition calculus prune the ill-typed rows** — sound but noisy. *Partial self-correction:*
  it catches mismatches that raise ($\to$ negate on `str`) and misses those that silently coerce
  ($\to$ negate on `bool`, since `bool <: int` in Python), which corrupt signal rather than abstain.
* **Fork 2 (sample-typed).** Observe $f$'s returns during a baseline pass (a return-capturing probe on
  `original_func`, the return-value sibling of Detective's input capture-harvest `capture_call_inputs`),
  yielding the observed codomain type; type $\Pi$ from it. Closes the silent-coercion hole; `undefined`
  then fires only for genuinely unobservable returns. Cost: crosses the Detective/Wesker boundary
  (return capture + observed-type threaded into generation).

**Proposition 11.11 (Fork 1 is sound; Fork 2 is precise).** Fork 1 never emits false signal (Prop. 7.4
routes every ill-typed row to `undefined`), but its self-correction is partial (silent coercion). Fork 2
removes the coercion hole at the cost of a runtime observation step. They compose as Form A/Form B do:
Fork 1 the sound skeleton, Fork 2 the precision-completing pass.

---

## 12. The Authoring Problem

Theorem 6.2 reduces the human contribution to authoring $\Sigma^{\pm}(P)$. This section formalizes that
act so it is tractable.

**Definition 12.1 (Triage).** Present the operator triages the *finite* enumerated survivor set
$S(f, \mu^{\pm})$ and supplies a partition into: `equivalent/valid` (the survivor computes the intended
function — this is `flag`, positive-space judgement, outranked by any distinguishing input) and
`invalid` (its survival is a bug — a $\mu^-$/censor fence, governed by Def. 9.3). Survivors killed by the
positive intent tests are already discharged. Thus "author a complete negative specification" (unbounded)
reduces to "partition this finite list" (closed).

**Proposition 12.2 (μ⁻ widens the triage universe to make it a contract).** $S$ is $\mu$-relative;
out-of-$\mu$ behaviors (Prop. 3.5's slugify witness) never appear in it, so the operator cannot fence
what is not shown. $\mu^-$ (Def. 3.1) drags codomain behaviors into $S$, which is what makes "partition
the list" equal "specify the intent" rather than "specify the syntactically-reachable subset." Without
$\mu^-$ the triage universe is provably too narrow to be a contract.

**Definition 12.3 (Elicitation of missing information).** The enumerated-but-un-triaged region of $S$ is
a high-entropy signal — missing information in the Shannon sense — that *asks* the operator rather than
waiting to be told (the absent-expected-signal-is-signal principle). This is the mechanism that surfaces
the type $\mu^-$ needs (Def. 11.10) as a question posed by a structural hole, without an active oracle.

**Proposition 12.4 (Idiom partially auto-fills the triage).** By Theorem 5.2, construct choice carries
negative-channel information. Idiom (operator/type/form choice) is therefore a lens *of* the contract —
it may *pre-populate* the `equivalent/valid` partition ranked by lens agreement (the parsimony
consensus) — but never *derive* it: a wrong implementation written fluently produces fluent idiom for the
wrong intent, so an idiom-proposed entry remains `candidate-equivalent — UNPROVEN` until a distinguishing
input or human `flag` disposes. Idiom proposes; it never gates.

**Definition 12.5 (Two feed points).** The construction has one artifact (the two-sign certificate: a
positive suite, a negative fence, and the triage record persisted with $f$) and two entry points: the
*greenfield* line, where the contract is authored when $f$ is first written (the native workflow), and
the *ingestion* line, where the same stations retrofit a triage onto pre-existing code (the present
brownfield behavior, reframed as the legacy path). Same artifact, same stations
($\mu^- \to$ triage $\to$ elicitation), two feeds.

---

## 13. Open Problems

1. **κ for code (blocks censors and Cor. 10.6).** In the semantic setting κ is genealogy PageRank over
   an IS-A graph. The code analogue needs a graph — call graph, import graph, or the obligation graph
   induced by interface mutants — and the choice decides whether $I_{\mathrm{ind}}$ is cheap or a
   research project.
2. **The regime key (Def. 9.1 keying).** Regime = symmetry; a censor keyed below the semantic-equivalence
   class over-reaches (traps positions that merely rhyme), keyed above it under-reaches. Working guess:
   typed interface + purity class. Wants a derivation.
3. **μ⁻ equivalence — resolved for Form A (Prop. 11.5), open for Form B.** Form B has no compilable
   mutant, so TCE-style bytecode identity (Wesker #24) does not apply; a negative mirror of
   `candidate-equivalent — UNPROVEN` may be required per sibling type.
4. **Completeness of Π (Def. 11.8).** How much of the codomain a finite perturbation family fences — the
   negative analogue of the positive operator-basis question SC §2.3 leaves open. Bounds require measuring
   reach against a codomain model, i.e. Fork 2's observed type (Def. 11.10).
5. **The bounded-curvature bound (Conj. 10.4, Caveat 10.5).** Measure $d$ on the obligation graph; prove
   greedy degrading in $d$, recovering $(1-1/e)$ at $d=0$.
6. **Build ordering.** Form A + Fork 1 is buildable now, κ-free, reuses the whole pipeline (the walking
   skeleton). Form A + Fork 2 and Form B are the completeness passes. Censors are blocked on Q1–Q2.

---

## 14. Status Ledger

**Proved (inherited, machine-checked — cite, do not re-derive).** σ = teaching dimension (SC Thm 2.7);
σ μ-parameterized (SC §2.3); representation independence (SC Thm 2.3); redundant ⟺ zero information gain
(SC Thm 3.11); composition gap (SC Thm 3.15); finite-domain Blum status and decidability (SC Thm 2.5);
`self_confirming_cannot_certify`, `falsifiability_pivot`; `coverage_submodular`, `marginal_antitone`,
`greedy_coverage_bound` — **the last three over a fixed ground structure only (Def. 10.2).**

**Transported (argued here from cited priors, not re-proved).** Prop. 2.2 (positive policies are
one-sign); Prop. 2.5 (μ⁻ is a second instantiation, no new metatheory); Theorem 5.2 (channel isolation);
Theorem 6.2 (automation boundary from σ = TD); Cor. 8.3 (the qualifier is decidability); Prop. 9.4
(admissibility as well-definedness); Prop. 10.3 (γ = d = bridge count); Cor. 10.6 (κ-gated removal).

**Asserted / grounded but unbuilt.** μ⁻ Form A (Def. 11.4) and Form B (Def. 11.6); the perturbation
family Π (Def. 11.8); the UNDEFINED disposition (Def. 7.3); Fork 1/Fork 2 typing (Def. 11.10); censor
derivation from call-site populations; κ for code (Q1). Form A's pipeline reuse is grounded against the
live engine (§11, [traced] 2026-08-22); everything in §11 remains code-unwritten.

**Conjectured.** Censors are bridges, not bulk (Conj. 10.4); bounded-curvature greedy for the obligation
graph (Q5).

**Measured (this repo, 2026-08-07).** The out-of-universe rewrite passing a positive SC=1 badge (Prop.
3.5, slugify); the "degenerate" near-miss witnesses outperforming hand-written tests on plausible
refactors — predicted by teaching theory, since teaching dimension is defined by a teacher minimizing
identification cost, not by sampling a natural distribution, so grading a witness by "would a person
write this" applies learner-intuition to a teaching artifact.

---

## Appendix A — Notation

| symbol | meaning |
|---|---|
| $\mathcal{M} = (D,R,\mathrm{sem},\mu)$ | mutation system (Def. 1.1) |
| $\mathrm{Mut}^{\neq}_\mu(P)$ | non-equivalent mutants of $P$ under $\mu$ |
| $\sigma(P,\mu)$ | specification complexity = min SC=1 suite size (Def. 1.3) |
| $\mathrm{TD}$ | teaching dimension (Prop. 1.5) |
| $\mathrm{kill}_v$ | value (assertion) kill relation (Def. 1.4) |
| $p : R \rightharpoonup R$, $f \oplus p = p \circ f$ | perturbation and perturbed denotation (Def. 3.1) |
| $\mu^- , \ \Pi$ | negative policy and its perturbation family (Def. 3.1, 11.8) |
| $\mu^{\pm} = \mu \cup \mu^-$ | two-sign policy (Def. 2.4) |
| $\rho(\mu^-)$ | reach of a negative policy (Def. 3.4) |
| $\mathrm{DOF}^{+}, \mathrm{DOF}^{-}, \mathrm{DOF}^{0}$ | positive / negative / mechanical regions (Def. 4.1) |
| $I_{\mathrm{solve}} = I_{\mathrm{ind}} + I_{\mathrm{ext}}$ | solve/teach decomposition (Def. 4.2) |
| $I^{+}, I^{-}$ | positive / negative channel information (Def. 5.1) |
| $\Sigma^{\pm}(P)$ | minimal two-sign teaching set (Def. 6.1) |
| $\nu(p), \ \bot$ | negative measure and its degenerate value (Def. 7.2) |
| $c \subseteq D \times R$ | censor (Def. 9.1) |
| $\gamma, d$ | composition gap, supermodular degree (Def. 10.1–10.2) |

## Appendix B — Citation ledger (priors read directly; cite, do not re-derive)

**Author's corpus.** `specification_complexity_paper.md` §§2.1, 2.3, 2.4, Thm 2.3, 2.5, 2.7, 3.11, 3.15 ·
`SSL_PAPER_SKELETON.md` §§2.5, 3.1, 4.3, 4.4 · `SIGNIFICANCE_WEIGHTING.md` §§12, 13, 14, 17 ·
`law_as_architecture.md` §§7, 8 · this repo: `ARCHITECTURE.md` §§0, 11; `docs/PARSIMONY_ADVISORY.md`.

**Live source (traced 2026-08-22).** `Wesker/engine.py`: `Mutant`, `MutationCategory`,
`_RECORD_MUTATOR_FACTORIES`, `_BaseMutator`, `mutant_disposition`, `SCORED_DISPOSITIONS`,
`generate_mutants`, `evaluate_mutant`, `check_equivalent`, `extract_boundary_inputs`, `BoundaryInput`,
`run_function_profiling`, `_DataflowMutator` (`return_sub`).

**External (RECALLED, NOT VERIFIED — check before public use).** Winston 1970 (near-miss) · Minsky 1974/
1980/1986 (frames, K-lines, censors) · Mitchell 1982 (version spaces) · Goldman–Kearns 1995,
Goldman–Mathias 1996 (teaching dimension) · Angluin 1987/1988 (exact learning) · Zilles et al. 2011,
Doliwa et al. 2014 (RTD) · Budd & Angluin 1982 (mutation equivalence undecidable) · Papadakis et al. (TCE)
· Feige–Izsak (bounded supermodular degree) · Nemhauser–Wolsey–Fisher (greedy $(1-1/e)$) · Rice 1953 ·
Landauer 1961 (erasure cost — the frame for the redundancy-in-representation intuition below).

## Appendix C — Empirical Predictions and Falsifiable Tests

The construction makes measurable predictions; two are already measured, three are runnable with
instrumentation the tool already exposes (`converge` reports the killable residual = $I_{\mathrm{solve}}$).

**C1 (measured, 2026-08-07).** *An out-of-$\mu$ behavior change passes a positive $\mathrm{SC}=1$ badge,
and $\mu^-$ catches it.* Confirmed on `slugify` (Prop. 3.5). Falsifier: a codomain-changing rewrite that
no admissible $\Pi_R$ perturbation distinguishes — would bound $\rho(\mu^-)$ from below.

**C2 (measured, 2026-08-07).** *Computed near-miss witnesses outperform hand-written tests on plausible
refactors.* On `slugify`'s zero-shipped-tests function, the "degenerate" witnesses caught the
`str`$\to$`bytes` API break that hand-written tests missed. Predicted by teaching theory (a witness is a
teaching artifact, not a natural sample). Falsifier: a refactor corpus on which hand-written tests
strictly dominate the synthesized witnesses.

**C3 (the thesis-deciding experiment — $\Delta I_{\mathrm{solve}}$).** *Authoring the negative sign
reduces the external-teaching residual by a measurable factor.* Converge a corpus of pure functions
under $\mu$ and under $\mu^{\pm}$; record $I_{\mathrm{solve}}^{\mu}$ (the killable/`--input` residual) and
$I_{\mathrm{solve}}^{\mu^{\pm}}$. Prediction (Prop. 4.3): $I_{\mathrm{solve}}^{\mu^{\pm}} <
I_{\mathrm{solve}}^{\mu}$, and the gap is the second sign's information content. Runnable now with the
existing residual instrumentation. Falsifier: no significant residual reduction — would refute Prop. 4.3
and the automation-relocation claim of Theorem 6.2.

**C4 (isolation, predicted).** *The negative survivors are largely disjoint from the positive survivors.*
By Theorem 5.2 the channels are orthogonal, so on a corpus the overlap between $\mu$-survivors and
$\mu^-$-survivors (as $(x,y)$-distinguishable dimensions) should be small. Falsifier: high overlap —
would refute isolation and reduce $\mu^-$ toward redundancy (Cor. 5.3).

**C5 (independence pair, predicted).** *A measurable fraction of green functions fail $p_{\mathrm{const}}$
or $p_{\mathrm{id}}$.* On functions whose shipped suites pass, some nonzero fraction leaves input-
dependence or non-triviality unpinned (Remark 11.9). This fraction is a direct measurement of what
positive-only completeness misses. Falsifier: the fraction is ~0 across a broad corpus — would show the
independence pair is redundant with existing positive coverage in practice.

## Provenance

The near-miss/censor half of this design is the ARC_AGI_3 corpus's (Winston's second operator, restored
in the semantic domain by Genesis IV-F/IV-G); the contribution here is the observation that the code end
of the σ = teaching-dimension homology never received it, the two-sign construction $\sigma(P,\mu^\pm)$,
and the operational realization grounded against the live engine (§11). The generative intuition is
biochemical: DNA fidelity is staged error correction — base selection, proofreading exonuclease, mismatch
repair — whose correcting information is inborn and redundant in the *representation* (the complementary
strand is the backup), not derived by a controller. Two channels over one message permit *correction*;
one permits only *detection*. μ⁻ is the second strand; the consistency relation of §5 is mismatch repair;
the thermodynamic accounting is Landauer's (local order paid for globally), which is why the construction
is a compute budget rather than a violation.
