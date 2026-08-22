---
title: "Negative Specification: Two-Sign Mutation Testing as Complete Behavioral Characterization"
subtitle: "The output-space mutation operator μ⁻, population-derived censors, and the specification complexity σ(P, μ ∪ μ⁻)"
author: "Rohan Vinaik"
date: "2026-08-22"
status: "formal specification, extended 2026-08-23 into the full stack (μ⁻ Forms A+B, Fork 1+2 built and grounded against the live engine; the learner §13/ESL, the corpus-κ §14/Significance-Weighting, the canonical form §15, and the paradigm §16 integrated with per-claim proved/transported/built/measured/conjectured status)"
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

Mutation-based specification, as realized by the Wesker engine (`Wesker` on PyPI) and the Detective
front-end (`detective-spec` on PyPI), measures a
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
the live engine (§11), including the channel-propagation discipline that closes two measured leaks of the
isolation result (§11.12). §12 formalizes the authoring problem the whole construction reduces to. §§13–16
then close the loop the construction opens: §13 turns $\sigma$ from a ruler into a learner (the σ-gap as a
benchmark read forward and a curriculum descended backward, the Detective CLI as its exact-learning
harness, and the two-sign extension as the target of a fully-automated form we name Uroboros); §14 supplies
the $\kappa$ machinery that scores a population-derived censor and states the load-bearing *negative*
result — the censor loop's tractability is bounded-curvature, not submodular, because the valuable censors
are *bridges* (measured, not conjectured); §15 makes the canonical implementation computable as the
$\sigma + \gamma$ minimizer and identifies it with consolidation, the σ-invariant run backward; and §16
states the resulting paradigm and its honest, decidability-bounded register. §17 is the honest
positioning: μ⁻ is the *unification*, under $\sigma =$ teaching dimension, of four established testing
lines — extreme mutation (whose operators and `effects`/`detect` calculus it adopts wholesale), checked
coverage (the value/run axis), oracle assessment (the deficiency-as-false-negative reading), and
metamorphic testing (the value-agnostic codomain oracle) — with $\sigma =$ TD grounded in the
exact-learning teaching-dimension line (Hegedűs; Hellerstein — a characterization *up to a log factor*) and
co-characterized *dynamically* as recursive-teaching (the batch suite) / self-directed-learning (the
adaptive `converge` trajectory). The reading of consolidation as a *bounded* sample-compression scheme is
retracted to a conjecture fenced by the multiclass compression impossibilities (§15, Prop. 15.6). The
novelty is the two-sign construction, the isolation theorem, Form B, and the censor layer — not the
operators, which the field already built.

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

**Remark 1.3b (σ intrinsic vs $\hat\sigma$ observed; the decidability caveat and the bounded range).**
Definition 1.3's $\sigma$ is the *intrinsic* object — the minimum over all suites separating every
**non-equivalent** mutant — and non-equivalence is where undecidability enters. The *policy* $\mu$ is
decidable: Python has a closed operator dictionary, so $\mathrm{Mut}_\mu(P)$ is a finite, enumerable set.
But *behavioral equivalence over those mutants* is not — deciding $m \equiv P$ reduces to program
equivalence, undecidable on an infinite domain (Rice 1953; Budd & Angluin 1982 for mutation equivalence
specifically) — and the two facts must not be conflated (μ-decidable $\neq$ equivalence-decidable). So the
engine never computes $\sigma$ directly: it reports $\hat\sigma$, the **test-set-relative** estimate (the
*dynamic subsumption* quantity, as against *true subsumption over all tests*; Kurtz, Ammann & Offutt 2015),
and names the undischarged residual explicitly — `candidate-equivalent — UNPROVEN`, never promoted to
`equivalent` (Def. 12.4). The Blum-measure status inherited in Prop. 2.5 is accordingly relativized to a
decidable $\mu$ with an equivalence oracle (SC Thm 2.5's finite-domain case; Thm 8.1 here), not asserted
for the intrinsic object off the decidable class. Between its endpoints $\sigma$ is a *range*, not a single
number: the **floor** is the intent minimum — the happy-path suite witnessing only that the function does
what it is meant to — and the **ceiling** is the exact specification — the suite separating every
non-equivalent element of the full operator space; the closure between them is the learning-theoretic
content of §13. Even given the finite kill matrix, computing the *exact* minimum in that range is the Test
Cover / Set Cover problem — NP-hard, inapproximable below $(1-o(1))\ln n$ (Feige 1998; Dinur–Steurer 2014),
double-exponentially hard in the solution parameter (Chakraborty, Foucaud, Majumdar & Tale, ISAAC 2024) —
so $\hat\sigma$ is reached greedily with the $\Theta(\log n)$ set-cover gap (Moret–Shapiro 1985; Prop. 15.6),
never as a poly-time exact object.

**Definition 1.4 (Value vs. run specification).** A kill by an assertion that distinguishes the
returned value is a *value* kill; a kill by crash or timeout is a *run* kill and pins only that the
mutant *executed differently*, not what it computes. Write $\mathrm{kill}_v$ for the assertion-kill
relation. *Value-completeness* requires every killable mutant to be $\mathrm{kill}_v$-killed; run kills
bank nothing toward it. (Detective ARCHITECTURE §0; the distinction is enforced, not cosmetic, and it
recurs on the negative side in §7.) *Prior art:* this is exactly Schuler & Zeller's **checked coverage**
(2011) — coverage that additionally requires an assertion to *constrain the computed value*, separating
"the line executed" from "the value was checked"; $\mathrm{kill}_v$ is checked-coverage's kill relation.
The distinction is *measured*, not cosmetic: Vera-Pérez et al. (2018/19) found a pseudo-tested method's
*traditional* mutation score is never $0$ — but only because "all [surviving-effect] mutations made the
program crash with an exception, and are thus trivially detected," i.e. run-kills inflate the score while
the value stays unpinned. Extreme mutation (μ⁻) is the more honest measure precisely because it does not
count the crash. *Monitorability scope (grounded 2026-08-23).* The value-kill / survivor / run-kill
trichotomy is, term for term, the three-valued **LTL₃** verdict $\top$/?/$\bot$ (Bauer, Leucker &
Schallhart 2011): a value kill is a finite *bad prefix* witnessing a violated **safety** (or co-safety)
property, a survivor is the inconclusive `?`, a run kill is an execution difference carrying no value
verdict. This *scopes* the guarantee rather than weakening it — value-completeness fences precisely the
safety/co-safety invariants, those with a finite bad prefix (Alpern & Schneider 1985/1987); a perturbation
whose only manifestation is a *liveness* violation (eventually-returns, terminates) has no finite witness
and is therefore *run-only*, banking nothing toward the value specification exactly as Def. 1.4 already
requires of a crash. The pseudo-tested / unpinned condition (§3, Rem. 11.9b) is the testing twin of
**vacuity** — a specification that passes while never constraining the system (Kupferman & Vardi 2003) —
and a value kill is its constructive non-vacuity witness (the RIP/PIE *propagation* step of Offutt–Untch
and Voas 1992, caught by the oracle; the run kill is *reachability + infection* without one).

**Proposition 1.5 (σ is a two-sign teaching dimension; cited).** For finite $D$ with faithful oracles,
$\sigma(P,\mu)$ equals the teaching dimension $\mathrm{TD}$ of the $\equiv$-class of $P$ in the concept
class induced by $\mu$ (SC Thm 2.7, machine-checked as `T5_17_teaching_dimension_{lower,upper}_bound`).
Teaching dimension is defined as the minimum labeled sample — labels drawn from $\{+,-\}$ — that
uniquely identifies a target concept (Goldman–Kearns 1995; Goldman–Mathias 1996).

**Proposition 1.5b (σ is co-characterized — static teaching dimension AND dynamic recursive teaching
dimension; this is the precise PAC↔exact bridge).** Two learning-theoretic characterizations of $\sigma$
hold simultaneously, and the complete reading keeps both.

*Static.* $\sigma(P,\mu) = \mathrm{TD}$ is the minimum teaching set (Prop. 1.5), and the static object that
carries to exact learning is the **extended** teaching dimension $\mathrm{XTD}$ (targets permitted outside
the class; $\mathrm{TD}\le\mathrm{XTD}$, separately and strictly). $\mathrm{XTD}$ characterizes the query
complexity of exact (membership-query) learning **up to a logarithmic factor** — a *two-sided* bound
$\mathrm{XTD} \le \mathrm{MQ} \le \mathrm{XTD}\cdot O(\log|C|)$, not an equality (Hegedűs 1995; Hellerstein,
Pillaipakkamnatt, Raghavan & Wilkins 1996). So SC Thm 4.3's "$\sigma =$ Angluin query complexity" holds as
a characterization *up to that log factor*, and the $\sigma\leftrightarrow$exact-learning edge is grounded
at its origin with the factor named rather than elided.

*Dynamic.* The greedy specification **trajectory** (SC §3 — proportional progress, exponential decay, the
bulk→tail phase transition) peels the highest-marginal mutants first, *recursively*. Which teaching object
this is depends on **who chooses the order**, and the two cases must not be conflated. Under a *batch*,
benevolent-teacher ordering the trajectory is the recursive teaching sequence defining the **recursive
teaching dimension** $\mathrm{RTD}$ (Zilles, Lange, Holte & Zinkevich 2011). But when `converge` picks the
next kill **adaptively, from the residual it is itself building** — no benevolent teacher, the *process*
chooses the order — the correct object is *self-directed* learning, whose exact measure is the
**self-directed learning dimension** $\mathrm{SDdim}$ (Devulapalli & Hanneke, ALT 2024), a distinct
quantity from teacher-directed $\mathrm{RTD}$. So $\sigma$ has a static face $\sigma_{\text{static}} =
\mathrm{XTD}$ (the min identifying set) and a dynamic face that is $\mathrm{RTD}$ for the consolidated batch
suite and $\mathrm{SDdim}$ for the adaptive `converge` trajectory; the bulk/tail transition (§3.4-analogue)
and the composition gap (§10) are dynamic-flavoured, not flat-TD.

*The bridge (an open axis, not a proved equivalence).* The dynamic dimensions link the *statistical* pole
(VC, PAC) to the *exact* pole (TD, query complexity), but the linkage is a set of open bounds, not an
identity: $\mathrm{RTD} \le \mathrm{VCD}$ holds for several natural classes (VC-dim 1, intersection-closed,
finite maximum; Doliwa, Fan, Simon & Zilles 2014) and $\mathrm{RTD}(C) \le d\cdot 2^{d+1}$ for
$\mathrm{VCD}(C)=d$ (Chen, Cheng & Tang 2016), but whether $\mathrm{RTD}$ — or the collusion-free
$\mathrm{NCTD}$ (Kirkpatrick, Simon & Zilles 2019), the parameter a *legitimate* compression scheme needs —
is *linearly* bounded by VCD, the statement that would carry to the sample-compression conjecture, is
**open** (Simon 2015; the 2026 Liu–Li $\mathrm{NCTD}\le\mathrm{VCD}$ preprint was withdrawn with a flawed
lemma). So "$\sigma$ = the gap between statistical and exact learning" names a real *axis* — $\sigma$ sits
on the RTD/SDdim–VC–compression line — but is not a computed identity, and the compression *reading* of
consolidation is a conjecture fenced by the multiclass impossibilities of Prop. 15.6, not an operational
payoff. [Status: static $\mathrm{XTD} =$ exact-learning query complexity *up to a log factor* is PROVED
prior art (Hegedűs; Hellerstein); the RTD/SDdim characterizations and the partial $\mathrm{RTD}\le\mathrm{VCD}$
results are CITED prior art (Zilles; Doliwa; Chen; Devulapalli–Hanneke); the identification of $\sigma$'s
*adaptive* dynamics with $\mathrm{SDdim}$ is this document's ASSERTED move, and the earlier
consolidation-*is*-compression identification is retracted to a fenced conjecture (Prop. 15.6).]

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

**Remark 2.2b (The sign is the probed AXIS, not the mechanism — extreme mutation is the negative sign
under a positive mechanism).** Definition 2.1 identifies the positive sign with *program-text*
transformation, but the boundary is subtler, and the literature already crossed it. **Extreme mutation**
(Niedermayr, Juergens & Wagner 2016; Vera-Pérez, Danglot, Monperrus & Baudry 2018/19) replaces a method
body with `return <constant>` — a program-text transformation, hence *positive* by Def. 2.1 — yet its
unpinned survivor, a **pseudo-tested method** (covered but no effect assessed), *is* a witnessed
non-example: the suite admits the pair $(x, \text{const})$ that Prop. 2.2 says a positive policy cannot
expose. Both cannot hold as stated. The resolution recasts the sign: **it is the *axis the mutant probes*
— the *computation / domain* (traditional mutation: swap an operator, shift a boundary) versus the
*codomain / output* (extreme mutation: collapse the return) — not the mechanism (program-text vs
post-composition).** For a pure single-return $f$, replacing the body with `return c` (a positive-mechanism
program-text mutation) *equals* the post-composition $f \oplus \mathrm{const}_c$ (a negative-sign codomain
perturbation, Def. 3.1) — the same object on two axes. So μ⁻ Form A (Def. 11.4, "a positive-shaped AST
mutator") is exactly extreme mutation, and Prop. 2.2 sharpens to: a *computation-probing* policy cannot
witness a non-example; a *codomain-probing* one (extreme mutation $=$ μ⁻) can, and does, though it is
program-text. The teaching-set sign is the probed axis; the mechanism is free.

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
an output dimension no covering test constrains. *Prior art:* this is an **oracle deficiency** in the
sense of Jahangirova, Clark, Harman & Tonella (ISSTA 2016), who assess a test oracle by searching for
inputs on which it *accepts a wrong output*; an unpinned $p$ is precisely such a wrong output the suite's
oracle admits without objection. The output-space perturbation $f \oplus p$ (Def. 3.1) is a codomain
relation used as an oracle — the standing framework for which is **metamorphic testing** (Chen, Cheung &
Yiu 1998; Segura et al. survey 2016), a *value-agnostic* output-space oracle (a metamorphic relation
constrains outputs across executions without knowing the correct value — Thm 5.2's channel isolation, in
the field's own terms). μ⁻ is its negative-perturbation dual: a metamorphic relation is a *positive*
codomain constraint; $f \oplus p$ is a *negative* one ("the output must not survive $p$ undetected").

**Remark 3.2b (The `effects`/`detect` formalism — the established form of the negative kill matrix, and it
already spans Form B).** The negative kill matrix is, in the vocabulary of Vera-Pérez, Danglot, Monperrus &
Baudry (2018/19), the $\mathrm{detect}$ predicate over a method's $\mathrm{effects}$. They fix
$\mathrm{effects}(m)$ = the observable effects a method produces — **(i) the returned value, (ii) a state
change on the receiver, (iii) a state change on other objects** — and $\mathrm{detect}: TS \times S \to
\{\top,\bot\}$ = whether a covering suite pins effect $s$. A method is **pseudo-tested** iff
$\forall s \in \mathrm{effects}(m):\ \nexists t:\ \mathrm{detect}(t,s)$ (every effect unpinned — all
negative DOF survive) and **required** iff $\exists s:\ \mathrm{detect}(t,s)$. The identification is exact:
a perturbation $p$ targets one effect $s$, and $p$ is *killed* iff $\mathrm{detect}(t,s)$. Two consequences.
First, the established formalism **already spans Form B**: its three effect types are precisely μ⁻'s return
codomain plus the non-return (self-state, other-state) codomain (Def. 11.6), so codomain-totality (Def.
3.4) is not a new object but effects-over-all-three-types the field defined. Second, μ⁻ adopts this
vocabulary: $\mathrm{effects}(f)$ for the codomain degrees of freedom, $\mathrm{detect}$ for the negative
kill relation — the negative matrix is the $\mathrm{effects}\times TS$ detection table, and "pseudo-tested"
is its all-zero row.

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

The positive and negative channels measure *non-redundant* quantities: the negative sign carries
information the positive one cannot derive. We say **non-redundant** rather than "orthogonal / independent"
deliberately — Theorem 5.2 is an *existence* witness of a distinction present in one channel and absent
from the other, which is exactly non-redundancy: a strictly weaker and provable claim than statistical
independence of the two channels over all constructs. This is the property that makes the negative sign
worth adding rather than a re-derivation of the first.

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

**Remark 5.3b (the two-sign object is may/must testing; the incomparability corroborates, the cost is
bounded).** The positive sign ("some test distinguishes $m$ from $P$") and the negative sign ("no
admissible implementation produces $(x,y)$") are the two polarities of **may/must testing** (De Nicola &
Hennessy 1984): may-testing succeeds if *some* context does, must-testing if *every* context does (a
refusal is observable). Their preorders are provably **incomparable** — neither refines the other — which
is the process-calculus form of Theorem 5.2's non-redundancy, established forty years prior; μ⁻ inherits it
rather than asserts it. The same literature bounds the negative channel's *cost*: extreme / stub mutations
(μ⁻'s universal family) are a leading empirical source of value-*equivalent* mutants (Kushigian et al.,
ISSTA 2024), so Fork 1 over-produces exactly the value-equivalences the two-sign object must then discharge
— handled by `candidate-equivalent — UNPROVEN` and `flag` (Def. 9.5, 12.4), not by a soundness exception.

**Definition 5.4 (Overlap coupling).** Although the channels' *content* is non-redundant, both constrain
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
of `cut`: a perturbation with $\nu(p) = \bot$ (Def. 7.2 — a degenerate/collapsed negative measure)
receives `undefined`. It is **not** added to `SCORED_DISPOSITIONS`.

*Note (two sources of inapplicability; only the collapsed-measure one is `undefined` for free —
grounded, 2026-08-22).* A perturbation can also be inapplicable because it is *mis-typed* to the
codomain (→negate on a `str`). Such a perturbation **raises when the mutant runs, and the engine
attributes a raise as a crash kill** (`evaluate_mutant`), not `undefined` — a run kill (ARCHITECTURE
§0). So routing a mis-typed perturbation to `undefined` is a wiring obligation the engine does *not*
satisfy for free, and leaving it as a crash kill is *unsound*: it marks the output dimension **pinned**
when the perturbation was merely inapplicable. The Form-A skeleton (Def. 11.10, Fork 1) therefore admits
only *always-applicable* perturbations — which never raise on any value — so it produces no source-(b)
`undefined` at all and its soundness (Prop. 7.4) is trivial. The type-conditional perturbations that can
raise are generated only under Fork 2's observed typing (where they are applicable by construction), or
behind a distinguished-inapplicability signal; both are deferred with the type-conditional family.

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
\setminus \{t\})$, resting on the machine-checked SC Thm 2.3 and 3.11. Now grounded: κ, its dynamics, and the
admissibility guard are supplied in §14 (built for the rule graph); the residual is the code-graph choice
of §18 Q1.

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
machinery. This resolves §18 Q3 for Form A. (Inherited limitation: `check_equivalent` skips methods —
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

**Remark 11.9b (Prior art: the universal family *is* extreme mutation; the contribution is its sign).**
The universal sub-family (Def. 11.8(i): $p_{\mathrm{none}}$, $p_{\mathrm{const}}$, $p_{\mathrm{zero\text{-}of}}$,
$p_{\mathrm{id}}$ — return `None` / a constant / the type's zero / an argument unchanged) is **extreme
mutation** (Niedermayr, Juergens & Wagner 2016; Vera-Pérez, Danglot, Monperrus & Baudry 2018/19, the
*Descartes* PIT plugin), and an unpinned $p_{\mathrm{const}}$ is exactly their **pseudo-tested method** — a
method exercised by passing tests that do not constrain what it returns. $p_{\mathrm{const}}$, this
document's "single most load-bearing perturbation," is *Descartes' central operator* (replace the body
with `return <constant>`). We therefore do **not** claim the universal perturbations as new; they are
established practice, and the honesty sharpens rather than weakens the contribution, which is orthogonal
to the operators: (i) recognizing them as the **negative sign** of the two-sign teaching set (Prop. 2.2),
so that "pseudo-tested method," "checked-coverage gap" (Def. 1.4; Schuler & Zeller 2011), "oracle
deficiency" (Def. 3.2; Jahangirova et al. 2016), and "unpinned negative degree of freedom" are *one*
quantity that $\sigma =$ teaching dimension already ranges over; (ii) the **channel-isolation** theorem
(Thm 5.2) that says why the sign is non-redundant with the positive policy; and (iii) the extension of the
same family to structured and non-return codomains (Def. 11.8(iv)–(viii), Form B — the region metamorphic
testing addresses ad hoc). Extreme mutation supplied the operators; the two-sign construction supplies
their place in the learning theory. Descartes' *exact* operator table (return `null`; `boolean→true/false`;
numeric`→0/1`; `String→""`/`"A"`; `T[]→∅`) spans not only Fork 1 but Fork-2 pieces — the boolean fences
$p_\top/p_\bot$ (Def. 11.8(ii)), the string $p_{\mathrm{empty}}$, the container $p_{\mathrm{empty}}$ — so
Wesker's built two-sign engine and Descartes largely coincide on the shared codomain types, differing where
μ⁻ reaches structured/ordered/effect codomains (Def. 11.8(v)–(viii)) that extreme mutation does not. The
prior art is measured at scale: pseudo-tested methods appear in **all of 21 projects over 28K+ methods**,
prevalence $1$–$46\%$, and developers judged **$<30\%$ "worth an additional testing action"** — the
$\mathrm{DOF}^-$/$\mathrm{DOF}^0$ triage (Def. 12.1) confirmed. The full cross-tradition map is §17.

**Definition 11.8b (Π-completeness).** $\Pi$ is *complete for codomain $R$* iff its reach $\rho(\mu^-)$
separates every pair of behaviors distinguishable at the codomain: for admissible $f$ and any
inadmissible near-miss $f'$ with $f \not\equiv f'$ observable at the output, some $p \in \Pi_R$ realizes
the crossing (some covering test fails on $f \oplus p$ exactly when it would witness $f \ne f'$). For
*finite* $R$ this is achievable by one perturbation per codomain deviation (the negative analogue of SC
Thm 2.2's one-test-per-mutant); for structured $R$, $\Pi_R$ must *generate*, under composition, enough of
the deviation monoid on $R$ to separate the intended concept from its near-misses. Whether a *finite*
$\Pi_R$ is complete for a given structured $R$ is the negative analogue of SC §2.3's open
operator-basis question (§18 Q4), and its measurement requires Fork 2's observed codomain type (Def.
11.10).

**Definition 11.10 (Typing Π — two forks).** A perturbation must be typed to the codomain to be valid,
and the engine holds **no return-type model** [traced: `run_function_profiling` takes `func_node`,
`test_functions`, `original_func`, `is_pure` — no return type and no return-value capture; only
`check_equivalent` calls $f$ directly, gated on numeric boundary inputs].

* **Fork 1 (always-applicable only — the shipped skeleton).** Admit only perturbations that are *total
  on any value* and therefore cannot be mis-typed: $p_{\mathrm{none}}$ (`return None`), $p_{\mathrm{const}}$
  (`return 0`), $p_{\mathrm{id}}$ (`return <arg>`) — the independence pair plus existence (Def. 11.8, the
  load-bearing core). None of these can raise on application, so Fork 1 produces **no source-(b)
  `undefined`** (Def. 7.3) and is **sound by construction**, not sound-but-noisy: every kill is by
  assertion (a value distinction), every survivor a real negative DOF. It types nothing from the AST
  because it needs no type; the type-conditional perturbations are simply *out of scope* here — they are
  not over-generated and pruned. The earlier "over-generate and let `undefined` prune the ill-typed rows"
  framing was wrong (grounding, 2026-08-22): a mis-typed perturbation is a *crash kill*, not `undefined`
  (Def. 7.3 note), so pruning by `undefined` was never free. [Built 2026-08-22 as
  `MutationCategory.OUTPUT`, opt-in two-sign policy; Wesker `dfce857`.]
* **Fork 2 (sample-typed — the type-conditional completion).** Observe $f$'s returns during a baseline
  pass (a return-capturing probe on `original_func`, the return sibling of Detective's input
  capture-harvest `capture_call_inputs`), yielding the observed codomain type; generate the
  type-conditional perturbations ($p_{\mathrm{neg}}, p_{\mathrm{empty}}, p_{\mathrm{NaN}}, p_{\mathrm{perm}},
  \dots$) **only where the observed type makes them applicable**, so they never raise and never
  mis-attribute. This adds the reach Fork 1 omits without reintroducing the crash-vs-`undefined` hazard.
  Cost: crosses the Detective/Wesker boundary (return capture + observed type threaded into generation).

**Proposition 11.11 (Fork 1 is sound by restriction; Fork 2 adds typed reach).** Fork 1 emits no false
signal because it admits only always-applicable perturbations — nothing raises, so nothing is
mis-attributed, and Prop. 7.4's abstention obligation is *vacuous* for it (no source-(b) `undefined`
arises). Fork 2 extends $\Pi$ to the type-conditional family under observed types, where applicability is
guaranteed by construction, so it too never mis-attributes. They compose as Form A/Form B do: Fork 1 the
always-applicable skeleton, Fork 2 the typed-reach completion.

### 11.12 Channel-information propagation (the operational realization of §5)

Isolation (Thm 5.2) makes the negative sign worth *measuring*; the following is what makes the
measurement *reach the certificate*. Two failures of it were found and closed by direct trace against
the live engine on 2026-08-22, and they are the first measured instances of a general obligation.

**Definition 11.12 (Channel-propagation).** A two-sign measurement is *channel-propagating* iff every
codomain distinction the classifier can OBSERVE (at the repr level, via `equivalence._observe`) is one
the certificate can CONSUME — i.e. every flagged distinction becomes, where the identity holds, a
*written* value-killing pin. The failure mode is a **leaked** distinction: a negative-channel difference
that is measured (the survivor is flagged killable) yet unpinnable (no `==`-golden kills it), so the
survivor re-surfaces as *killable-but-unwritten* and the report asserts a soundness failure that did not
occur. This is the negative-channel instance of the standing discipline "trace the signal to the
decision — each layer must *consume* the computed signal, never re-derive a narrower proxy" (Detective
ARCHITECTURE §0). Isolation is why the second channel carries information; propagation is why that
information is not discarded before the pin.

**Proposition 11.13 (The existence fence must value-kill, not crash-kill; built `f5e0efc`).** For a
generator target (Form B codomain, Def. 11.6) the dominant mutant deletes the `yield`, collapsing the
observable output to a non-iterable ($\texttt{None}$). The characterization golden
`assert iter(result) is result and list(result) == […]` kills this mutant by CRASH — `iter(None)` raises
`TypeError` — which banks nothing toward the value specification (Def. 1.4, Remark 3.3). Prepending the
existence fence $p_{\mathrm{none}}$ (Def. 11.8(i), "the output must exist") as a *short-circuit
conjunct*, `assert result is not None and iter(result) is result and …`, makes the same mutant fail by
ASSERTION (the conjunction is `False` before `iter(None)` is evaluated). *Measured:* `converge <gen>
--two-sign` moved from `Incomplete: 1 killable · unsound` to `✓ COMPLETE · 6/6`, the deleted-yield mutant
now VALUE-pinned. The fence is $p_{\mathrm{none}}$ realized in the golden synthesizer, and the
proposition is the value-vs-run precedence (Def. 1.4) enforced on the negative channel.

**Proposition 11.14 (The container-contract fence requires the mutant's VALUE, not its repr; built
`3ba2387`).** By Thm 5.2 a construct choice can be value-$\equiv$-equal yet negative-channel-distinct.
The measured instance: a positive `SWAP` mutant strips `frozenset(...)` from a returned dataclass field,
so `Flow(uses=frozenset({1,2}))` becomes `Flow(uses={1,2})` — value-`==`-equal (`frozenset({1,2}) ==
{1,2}`, and the dataclass `__eq__` agrees) yet type-distinct: the $p_{\mathrm{ctype}}$ container-mutability
fence (Def. 11.8(v)) *inside a field* ($p_{\mathrm{field}}$, Def. 11.8(vi)). The classifier flags it
killable off the *repr* difference; but the witness carried only the mutant's repr, and a dataclass repr
is not `literal_eval`-able, so the type pin `assert type(result.uses) is frozenset` could not be
synthesized — the `==`-golden passed on the mutant too (SOUND but NON-KILLING), and the survivor
re-surfaced *killable-unsound*. Threading the mutant's live value (a symmetric `_outcome_value(mutant,
args)` carried on the `Witness`) lets the distinction walk to the leaf and pin it by type. *Measured:*
`converge <flow> --two-sign` moved from `Incomplete: 1 killable · unsound` to `✓ COMPLETE · 8/8`. The
proposition is the information-theoretic completeness principle at the operational layer: the positive
path must propagate ALL available negative-channel information — the value itself, never a lossy repr
projection — or a Thm-5.2 distinction is silently discarded.

**Remark 11.15 (One phenomenon, two leaks).** Props. 11.13–11.14 are the two failure modes of a single
gap: a negative-channel distinction (existence; type) is COMPUTED but does not PROPAGATE to a value-kill
— once because the kill leaked out as a crash, once because the value was projected to a repr before the
leaf was reached. In both, the certificate asserted `unsound` (a soundness *failure*) when the truth was
*sound, but the fence did not reach the decision*. They are the first measured instances of the general
obligation Def. 11.12 names, and they locate exactly where §11's operational realization touches §5's
isolation theorem: the fence is only as good as its propagation to the pin.

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

## 13. Exact Specification Learning: σ as Ruler and Reward

The preceding sections treat $\sigma(P, \mu^{\pm})$ as a *measure* of a program's two-sign identity. It
is also, because it is COMPUTED by a theorem-checked engine rather than read from a hand-authored key,
simultaneously a *benchmark* (read the gap to the optimum) and a *curriculum* (descend that gap). This
section imports the Exact Specification Learning construction (Vinaik, *Exact Specification Learning* —
hereafter ESL) and extends it from the one-sign to the two-sign policy. ESL is cited, not re-proved; its
own status ledger (forward pass demonstrated on a running prototype 2026-07-17; backward pass designed,
not run) is inherited verbatim.

**Definition 13.1 (The σ-gap).** For an agent $A$ driving specification of $P$ over the degree-of-freedom
universe $\mathrm{Mut}^{\neq}_{\mu^{\pm}}(P)$, the *coverage gap* $g_{\mathrm{cov}}(A) = 1 -
\mathrm{SC}_{\mathrm{achieved}}(A)$ (distance from complete identification) and the *efficiency gap*
$g_{\mathrm{eff}}(A) = |T_A| / \sigma(P, \mu^{\pm})$ (distance from optimal identification). In Wesker's
DOF mode the cover sets are singletons, so greedy is EXACTLY optimal — not merely $(1-1/e)$ — and the
optimum $A$ is scored against is COMPUTED and PROVED (`coverage_submodular`, `marginal_antitone`,
`greedy_coverage_bound`, machine-checked). There is no "our reference solver might be suboptimal"
confound: on the DOF universe the engine *is* the exact minimum.

**Proposition 13.2 (The exact-learning identity; cited).** Greedy mutation testing is an Angluin exact
learner (SC Thm 4.3, `T6_6_greedy_is_exact_learner`): a *membership query* is one input; an *equivalence
query* is the suite-against-a-mutant check. An agent that, shown the surviving mutants, synthesizes
inputs to kill them IS performing exact identification (identity testing, SC T6.17). Hence
$g_{\mathrm{cov}}$ is a learner's distance from *complete* identity and $g_{\mathrm{eff}}$ its distance
from *optimal* identity — both against the proved optimum.

**Theorem 13.3 (The duality — one apparatus, two directions; cited ESL).** Because $\sigma$ is generated
by a deterministic engine and not by a finite labeled key, the σ-gap is a *benchmark* read forward and a
*training reward* descended backward — the same object. A labeled benchmark's labels are an exhausting
resource, so it can only measure; ESL's labels are engine-generated, so measurement and training are one
signal read in two directions. *Forward:* fix the agent, read `gap = optimal − achieved` over held-out
functions — a leaderboard of exact-learning competence on provable ground truth. *Backward:* take the
same gap as reward — every killed mutant a verified bit pinned, every survivor a dense typed error signal
(by category), descended by SFT or RL with the *tests as the target rather than the check*.

**Definition 13.4 (The CLI is the exact-learning harness).** Detective's `converge`, its `--json` state
machine, and the `DO THIS: --input` loop constitute the forward-pass harness: the learner is invoked at
*exactly one branch* — input synthesis, the Angluin membership query — the per-category survivor set is
the dense typed reward, and the residual state machine is the trajectory. The discipline that keeps this
classical rather than a model with a shell is ESL §4.1's "agency is the bug; the model is a pure function
from residual to candidate inputs": the *architecture* is the deterministic, Lean-checked σ-engine, and
any learner is a schema-constrained, injection-proof tail whose reward is a theorem, never a learned
reward model. Under this reading the tool's apparently over-built CLI is not overhead — it is the correct
*instrument* of an exact-learning benchmark, and every element (the DO-THIS derivation, the typed
categories, the residual machine) is a named component of it.

**Proposition 13.5 (Two-sign ESL closes the target).** ESL as constructed measures the agent against the
ONE-SIGN $\sigma$ (the eight positive categories, Def. 11.1). Under the two-sign policy the target
becomes $\sigma(P, \mu^{\pm})$: the learner must construct the minimum distinguishing set over the
positive mutants AND the $\mu^-$ codomain fences. Proposition 4.3 — that the interactive `--input`
residual is mostly mis-classified un-authored *negative* intent — is precisely the statement that
one-sign ESL OVERSTATES the external-teaching cost $I_{\mathrm{ext}}$: authoring the negative sign once
(the teaching set, §6) moves that content out of the per-run query loop. Hence two-sign ESL has a
strictly smaller $I_{\mathrm{ext}}$ than one-sign ESL, and the difference is the second sign's
information content — the C3 falsifiable prediction (Appendix C), now with a named mechanism.

**Definition 13.6 (Uroboros).** The fully-automated form is two-sign ESL run backward: a fleet of exact
learners, trained on the $\sigma(P, \mu^{\pm})$-gap curriculum, driving code to its complete two-sign
teaching set and — via consolidation (§15) — to its canonical form. The apparatus that MEASURES
correctness (the ruler) and the reward that TRAINS the learner which ACHIEVES it (the curriculum) are one
object; the loop closes on itself, which is the name. *Status: designed.* The learner substrate
(ShortcutForge) and the Wesker-verified reward exist; no trained two-sign learner exists, and the
exact-learning-to-intelligence bridge (György et al., 2025, plus the parent paper's conjecture that
$\sigma$ measures the statistical/exact gap) is promising-not-established and is not collapsed here.

---

## 14. The Corpus Self-Teaching Loop: κ, Bridges, and the Bounded-Curvature Obstruction

Section 9 defined censors (population-derived negative constraints) and Conjecture 10.4 asserted they are
bridges. This section supplies the mechanism — $\kappa$, the marginal-coverage quantity that scores a
censor's worth — imports the significance-weighting theory that realizes it in a running engine (Vinaik,
*Significance Weighting*; built in Regenesis, `regenesis/significance.py`, `promotion_ledger.py`), and
states the load-bearing NEGATIVE result: the tractability guarantee the naive story assumes does not
transfer, and the place it breaks is exactly where the valuable censors live.

**Definition 14.1 (κ, the marginal coverage).** For a rule/obligation graph $G$, a node $v$, and an
adopted set $S$, $\kappa(v \mid S) = |\mathrm{cover}(v) \setminus \mathrm{cover}(S)|$ — the
forward-reachable set $v$ adds beyond what $S$ already covers. $\kappa$ is the hub-score, realized in the
semantic domain as genealogy PageRank over the IS-A graph. [Built: `significance.coverage` /
`marginal_coverage` / `_reachable`; measured $L(\mathrm{NLP}) = 0.528$, ≈53% resolved for free.]

**Proposition 14.2 (κ scores a censor's worth; it is the induction prior and its stopping rule).** A
censor spanning call sites (Def. 9.1) has worth equal to its marginal coverage: a *high-κ* censor
collapses a whole cluster of admissible near-misses into one fence (the **bulk** — propose it), a
*low-κ* censor is an independent tail constraint (**tail** = $I_{\mathrm{solve}}$ — abstain, it must be
taught). Propose the fence maximizing κ-compression of a surprising near-miss chain; STOP when
$\kappa \to 0$ (the bulk/tail knee is the principled halting condition, not an arbitrary cap). [Built:
`promotion_ledger.rank_candidates` / `marginal_kappa`.]

**Definition 14.3 (κ re-flows — the endogenous teaching term).** $\kappa$ is a function of the graph, so
every adopted censor adds an edge and re-computes $\kappa$: the source region's coverage rises, and a
censor **bridging** two previously-disjoint clusters is the largest κ jump. This is $C(H)$ structural
amplification (Def. 4.2; SSL §2.5) promoted to a dynamical law,
$$\frac{dH}{dt} = -\big(N_{\mathrm{ext}} + \underbrace{N_{\mathrm{ind}}(H)}_{\text{the corpus teaches itself}} + C(H)\big),$$
where $N_{\mathrm{ind}}(H)$ is the rate of admissible corpus-derived censors — the discrete self-teaching
term SSL *names* (unknown-knowns, SSL §1.4c) but does not price. This yields the three-region completeness
split of Def. 4.2, $I_{\mathrm{solve}} = I_{\mathrm{ind}} + I_{\mathrm{ext}}$, with
$L_{\mathrm{ind}} = I_{\mathrm{ind}}/I_{\mathrm{solve}}$ the *self-teaching fraction* — what structure
gives free ($L$), what the corpus teaches itself ($L_{\mathrm{ind}}$), and what a teacher must supply
($I_{\mathrm{ext}}$). [Cited *Significance Weighting* §§11–12; the code computes a coverage analog of
$L_{\mathrm{ind}}$, `promotion_ledger.self_teaching_fraction`, not the entropy-bit quantity.]

**Theorem 14.4 (THE CRUX — submodularity fails at bridges; measured, constructive).** The κ-coverage
function $f(S) = |\bigcup_{v \in S} \mathrm{cover}(v)|$ is submodular over a STATIC ground structure
(machine-checked `coverage_submodular`). But under the corpus loop the ground structure is *not* static —
adopting a censor mutates the graph $\kappa$ is read from (Def. 14.3) — and submodularity is VIOLATED,
constructively: let cluster $A$ reach $x$ via $r'$ and let $B$ be disconnected from $A$; let $r$ be a
bridge $x \to B$. With $S = \varnothing$, adding $r'$ covers $x$ plus $A$'s small downstream (small
marginal); with $T = \{r\} \supseteq S$, adding $r'$ now reaches all of $B$ (large marginal). So
$f(T \cup \{r'\}) - f(T) > f(S \cup \{r'\}) - f(S)$ for $S \subseteq T$ — diminishing returns FAILS; $r$
and $r'$ are **complementary**, not redundant. [Measured, *Significance Weighting* §16.1a, six real pulls:
supermodular degree $d \le 14$–$25$, $15$–$26$ weakly-connected components; the Macbeth witness — promoting
one real bridge RAISES 16 other nodes' κ, $\kappa(\text{give} \mid \varnothing): 2 \to 3$ — is
antitonicity violated on real captured data, not a toy.]

**Corollary 14.5 (Censors are bridges — measured, not conjectured).** Conjecture 10.4 is upgraded to a
measured fact of the regime: the *valuable* censors — those spanning call sites, fencing a cross-cluster
near-miss — ARE bridges, hence super-additive with the positive tests, hence exactly the constraints a
clean greedy bound cannot cover. The biggest wins and the reason the easy proof fails are the same
constraints; a theory that assumed submodularity would be a theory of the boring cases.

**Definition 14.6 (Bounded curvature — the correct tractability object).** The tractable object is not
submodular greedy but *bounded supermodular degree* $d$ (Feige–Izsak): a function submodular except for a
controlled amount of complementarity retains a degraded greedy guarantee, degrading in $d$ and recovering
$(1-1/e)$ at $d = 0$ (no bridges); $d$ here is essentially the number of bridging adoptions. What survives
regardless: monotonicity of forward closure (nearly free), and submodularity WITHIN a connected component.
The dense-graph constants ($L = 0.528$, the ~3% knee, the 28× drop) were measured on a *dense* IS-A graph
and DO NOT transfer to a *sparse* obligation graph — measured, the sparse rule graph knees 3–12× later
with a 3.5–8× softer drop; citing the dense constants for code would be wrong by an order of magnitude.
[Conjecture: `bridge_curvature_bound`, a Lean TARGET; $d$ measured on the rule graph, unproved for the
obstruction bound.]

**Proposition 14.7 (Admissibility is machine-checked, and it is the well-definedness condition).** A
censor is admissible iff (i) it is *spine-sourced* — carved from an observed near-miss or a rejected-
rewrite witness, structurally incapable of confirmation from the engine's own derived output — AND (ii)
$\sigma(P \mid C \cup \{c\}) > 0$ (retained plurality). Without (i), $N_{\mathrm{ind}}$ and
$I_{\mathrm{ind}}$ are UNDEFINED, not merely unsafe: a censor confirmed from the engine's own derivations
reduces the residual by construction while carrying ZERO information ($L_{\mathrm{ind}} \to 1$ vacuously,
the descent looking fast and meaning nothing). The guard is the *same object* as SSL's falsifiability
constraint, machine-checked `self_confirming_cannot_certify` and `falsifiability_pivot` (mutual
information $> 0 \iff$ the answer channel is non-degenerate), with the retained-plurality budget (SSL
§4.4; $\hat{R}$ not driven to $0$) the quantitative lower bound. This is exactly Def. 9.3, now with its
mechanism proved and built. [Built + tested: `promotion_ledger.is_spine_confirmed` / `retains_plurality`
/ `admissible` / `corpus_fixpoint`; the loop is conservative-empty on clean data *by construction* — a
positive promotion requires a corpus authored so the strengthened rule bridges disconnected clusters.]

*Remark 14.8 (what is code-specific, and what transports).* Everything above is proved-or-built for the
semantic *rule* graph. What is code-specific is a single unmade choice: the graph over which $\kappa$ is
computed for programs — the call graph, the import graph, or the obligation graph induced by interface
mutants (Def. 10.1) — and the measurement of $d$ on it (§18 Q1). The mechanism (κ = marginal coverage),
the dynamics (κ re-flows), the tractability object (bounded curvature), and the guard (spine-sourced +
retained plurality) all transport unchanged; only the graph and its $d$ are to be measured.

---

## 15. The Canonical Form: σ+γ Minimization and Consolidation

Section 6 located the human contribution at the teaching set; §12 reduced authoring to a finite triage.
The dual question remains: given the pinned two-sign identity, what is the *canonical implementation* of
it? This section shows the answer is computable, is the σ-invariant run *backward*, and is the operator
Detective already ships as `decompose`.

**Definition 15.1 (Two readings of "the purest code").** Given a two-sign teaching set pinning the
behavioral-plus-negative identity $[f]_{\equiv^{\pm}}$: (a) the *identity* itself is unique and
well-defined (the contract pins it); (b) a canonical *representative implementation* is a further
selection among the implementations satisfying it. Reading (a) is settled by the two-sign contract;
reading (b) is what this section resolves.

**Theorem 15.2 (The composition gap is the computable clean-abstraction-barrier; cited).**
$\sigma(A \circ B, \mu) \le \sigma(A,\mu) + \sigma(B,\mu) + \gamma(A,B)$, with $\gamma \ge 0$ and
$\gamma = 0$ for specification-independent components (SC Thm 3.15, `gammaZeroIfIndependent`), and
$\gamma \le |\mathrm{InterfaceMutants}(A,B)|$ (SC Thm 3.16, `gammaLeInterfaceMutantsCard`), COMPUTABLE
from the mutation analysis. A decomposition is *clean* — a SICP abstraction barrier — iff its interface
leaks no specification, i.e. $\gamma = 0$; entangled behavioral dimensions cost $\Theta(\prod n_i)$ and
independent ones $\Theta(\sum n_i)$. This is a complexity-theoretic argument, not a stylistic preference
for smaller functions (SC §3.3).

**Proposition 15.3 (The canonical representative is the σ+γ+accidental-I⁻ minimizer).** Among
implementations of $[f]_{\equiv^{\pm}}$, the canonical one minimizes total specification cost on three
computable terms: *low $\sigma$ per piece* (does-one-thing — few independent behavioral dimensions to
pin); *$\gamma = 0$ at the seams* (composable — clean interfaces, Thm 15.2); and *minimal ACCIDENTAL
negative signature* — Thm 5.2 discriminates value-equivalent siblings by their induced must-nots, so the
`x+y`-over-`(3x+3y)/3` preference is exactly "fewest accidental fences." All three are computed by
machinery Detective ships (`decompose`, the interface-mutant $\gamma$ estimate, the two-sign survivor
set). This is the corpus claim "$\sigma$ makes SICP computable": SICP's informal aesthetic — minimal,
composable, abstraction-clean code — receives a complexity-theoretic ground as the σ+γ+I⁻ minimizer.
[The mechanism is verified here against SC Thm 3.15/3.16; the *phrasing* "σ makes SICP computable" is
carried in `thesis_vision.md`, not read — status ASSERTED for the naming, PROVED for the mechanism. The
minimizer selects an *equivalence class / decomposition structure*, μ-relative and possibly non-unique
(ties), not necessarily a single syntactic string.]

**Theorem 15.4 (Consolidation = σ-preserving reduction; cited).** *Safe forgetting* is σ-preserving
reduction to the simplest member of the kill-profile equivalence class. Representation independence (SC
Thm 2.3, machine-checked) says $\sigma$ is invariant under mutation-preserving transformations, so the
class may be moved within freely; redundancy = zero information gain (SC Thm 3.11, machine-checked) says
exactly what banks no significance-weighted coverage may be dropped WITH PROOF. Transported to the
two-sign setting: a rewrite is safe iff it preserves the two-sign σ-witness — the value pins AND the
negative fences. [Machine-checked SC 2.3/3.11; the transport is the ASSERTED target
`safe_forget_preserves_sigma_sem`, *Significance Weighting* §17.]

**Proposition 15.5 (Consolidation is `decompose`, run offline; the σ-dynamics reversed).** Detective's
`decompose --apply` is exactly this operator on CODE: it discards a tangled implementation and keeps
whatever preserves the mutant-kill witness, applying the rewrite only when the preservation is PROVEN
behavior-identical. Reading (b) of Def. 15.1 is thereby resolved and mechanized — the canonical
representative is the fixpoint of σ-preserving reduction. The two directions are one invariant:
*waking* (active reading) is the forward greedy accumulation of the drift-laden bulk; *sleep* is reverse
redundancy-elimination to the exact tail (SC Thm 3.4's statistical→exact transition enacted offline —
the Crick–Mitchison reverse-learning theory of dreams, turned from conjecture into a definition: a
spurious structure *is* a zero-κ derivation). Parts §1–§14 GENERATE the two-sign spec; consolidation
makes it CANONICAL. [Cited *Significance Weighting* §17.1; the "consolidation minimizes a specification
free energy" reading (SC Thm 3.10) is CONJECTURE, needing the σ free-energy machinery wired here.]

**Proposition 15.6 (Consolidation is a σ-preserving greedy reduction; whether it is a *bounded*
sample-compression scheme is open — and obstructed from dimension alone).** Consolidation (Thm. 15.4)
reduces the two-sign teaching set to a **minimal σ-witness** — the value pins AND the negative fences that
no smaller set preserves. Two facts about it are settled; one reading the earlier draft asserted is open,
and is retracted here.

*Settled (the hardness, hence the greedy form).* Computing the exact minimal witness is the Test Cover /
Minimum Set Cover problem: NP-hard and inapproximable below $(1-o(1))\ln n$ unless P $=$ NP (Feige 1998;
Dinur–Steurer 2014), and — even given the finite kill matrix — double-exponentially hard in the solution
parameter $k$, resisting kernelization (Chakraborty, Foucaud, Majumdar & Tale, ISAAC 2024). So `decompose`'s
reduction to the minimal witness is *greedy by necessity, not by design*, and its worst-case ratio is the
known $\Theta(\log n)$ set-cover gap (Moret–Shapiro 1985), not a novel compression guarantee. The minimal
σ-witness is a well-defined **lower bound**, not a poly-time-computed object.

*Retracted (the compression reading).* The earlier claim — that `decompose` *is* a sample-compression
scheme of size $\sigma_{\text{dyn}} = \mathrm{RTD}$ — over-reached, and grounding the cited results (2026-08-23)
shows the over-reach is not repairable by the obvious fix. The two-sign object is genuinely **multiclass**
(a positive which-implementation label and a negative must-not label), and for multiclass classes finite
dimension does **not** imply a compression scheme bounded by any function of that dimension (Pabbaraju,
*Multiclass Learnability Does Not Imply Sample Compression*, ALT 2024); the natural repair — recast it as a
*list* sample-compression scheme — also fails in general, since there are list-learnable classes that admit
no bounded list compression (Hanneke, Moran & Waknine, *List Sample Compression and Uniform Convergence*,
COLT 2024). The collusion-free parameter that *would* legitimize a compression reading is the no-clash
teaching dimension $\mathrm{NCTD}$ (Kirkpatrick, Simon & Zilles, ALT 2019); but $\mathrm{NCTD} \le
\mathrm{VCD}$ is **open** (the 2026 Liu–Li preprint asserting it was withdrawn with an acknowledged flawed
lemma), and $\mathrm{RTD}$ itself can exceed VC. We therefore keep consolidation as a σ-preserving greedy
reduction (Thm. 15.4) and record the compression *reading* as a conjecture fenced by these impossibilities,
not as an operationalized RTD–VC bridge. [Status: the set-cover / Test-Cover hardness and the greedy
$\Theta(\log n)$ gap are PROVED prior art (Feige; Dinur–Steurer; Chakraborty 2024; Moret–Shapiro); the
identification of consolidation *with* a bounded compression scheme is **WITHDRAWN** as a claim of this
document — it is open, and obstructed for multiclass classes from dimension alone (Pabbaraju; Hanneke–Moran–Waknine).]

---

## 16. The Paradigm: From Handicraft to Assembly Line

The construction closes a loop that the tool's own design half-implements and the theory names. Its
consequence is a workflow for authoring code whose correctness is a certificate rather than a hope.

**Definition 16.1 (The four-station pipeline).** (1) *Intent* — decide what the code must do. (2) *A
happy-path implementation* — code that does it, if only on one path (human- or agent-written). (3) *The
two-sign contract* — much of it auto-filled by the $\mu^-$ operator-tree walk (Def. 3.1, 11.8), the idiom
lens (Prop. 12.4), and the corpus censor loop (§14), leaving the operator only the irreducible
$I_{\mathrm{ext}}$ (Thm 6.2) as a finite triage (Def. 12.1). (4) *Mutation as selection pressure* —
Detective subjects the code to the two-sign mutation universe and consolidates the survivor to its
canonical form (§15). One artifact (the two-sign certificate), two feeds (greenfield / ingestion,
Def. 12.5).

**Proposition 16.2 (The stack).** The paradigm is the composition of four documents, each edge proved,
built, or a named port:

| Layer | Source | Contributes |
|---|---|---|
| Proved core | *Specification Complexity* | $\sigma$ = teaching dimension; Blum measure; composition gap $\gamma$ (computable); the consolidation theorems (2.3, 3.11); greedy = Angluin exact learner |
| Complete target | this document | $\mu^-$ → two-sign $\sigma(P, \mu \cup \mu^-)$ — the whole teaching set |
| Learner / curriculum | *Exact Specification Learning* | the σ-gap as ruler-forward and reward-backward; the CLI as the exact-learning harness |
| Corpus + canonical form | *Significance Weighting* | $\kappa$; censors-as-bridges (measured); the self-teaching loop; consolidation = the canonical-form operator |

**Remark 16.3 (The honest register of the claim).** The paradigm is *provable-where-decidable* (Thm 8.1,
finite-domain, unqualified `correct`) and *honestly-scoped-complete* elsewhere (Thm 8.2, Cor. 8.3 —
`correct modulo (μ ∪ μ⁻), observing set named`; the qualifier is decidability, not tool maturity). It
does not say code authorship is automated (Remark 6.3); it says verification and pinning are mechanized
down to the teaching set, the negative half of that set is now measurable rather than leaked into the
per-run loop, and the canonical form is COMPUTED from the pinned identity. "Correct code" thereby acquires
a definition — the σ+γ+I⁻-minimal member of the two-sign identity class — that is neither "clean" nor
"well-written" but *provably identified and minimally represented, given the policy*.

---

## 17. Prior Art: μ⁻ as the Unification of Four Testing Traditions

The two-sign construction is best read not as a novel operator set but as the *unification*, under
$\sigma =$ teaching dimension, of four established testing-research lines and one learning-theory line —
each of which measured a facet of the negative sign without naming it as the second label of a teaching
set. Stating the map is what makes the contribution honest and, thereby, stronger.

**§17.1 The cross-tradition map.**

| μ⁻ construct (this document) | Established line | What it is there | The gap μ⁻ crosses |
|---|---|---|---|
| universal family (Def. 11.8(i)); Form A | **extreme mutation** (Niedermayr, Juergens & Wagner 2016; Vera-Pérez et al. 2018/19, Descartes) | the operators; the `effects`/`detect` calculus (Rem. 3.2b) | recognizing them as the negative *sign*; isolation; the non-return codomain (Form B) |
| value-kill vs run-kill (Def. 1.4) | **checked coverage** (Schuler & Zeller 2011) | oracle-constrained value via dynamic slice; more sensitive than coverage | making it the load-bearing axis of a *two-sign* σ |
| unpinned perturbation (Def. 3.2) | **oracle assessment** (Jahangirova, Clark, Harman & Tonella 2016) | an oracle *false-negative* (accepts a wrong output) + improvement loop | the fence as authored intent (§12); κ-scored censors (§14) |
| codomain relation $f \oplus p$ (Def. 3.1) | **metamorphic testing** (Chen–Cheung–Yiu 1998; Segura et al. 2016) | value-agnostic output-space oracle | its negative-perturbation dual; the teaching-dimension placement |
| σ = TD (Prop. 1.5) | **teaching dimension / exact learning** (Goldman–Kearns/Mathias; Hegedűs 1995; Hellerstein et al. 1996) | TD = query complexity of exact identification | the two-label instantiation over a mutation-induced class |
| σ dynamics; consolidation (§15) | **RTD/SDdim–VC–compression** (Zilles 2011; Doliwa 2014; Chen 2016; Devulapalli–Hanneke 2024) | recursive / self-directed teaching; sample compression | the code-domain realization; `decompose` as a σ-preserving reduction (the compression *reading* fenced open, Prop. 15.6) |

**§17.2 The one-line reading.** Extreme mutation lent the *operators* and the effects/detect *formalism*;
checked coverage the *value/run axis*; oracle assessment the *deficiency = false-negative* reading;
metamorphic testing the *value-agnostic codomain oracle*; teaching dimension the *unit* (σ = min evidence
to identity = query complexity of exact learning, *up to a log factor*, Hegedűs); RTD/SDdim–VC–compression
the *open axis between statistical and exact* and the (fenced, Prop. 15.6) *compression reading of
consolidation*. μ⁻ supplies what none has alone: the recognition that
these are *one quantity* — the negative label of a two-sign teaching set — plus the isolation theorem
(Thm 5.2), the codomain-total extension (Form B, the effects the field addressed ad hoc), the corpus/κ
censor layer (§14), and the operational realization against a live engine (§11).

**§17.3 What is genuinely new, stated conservatively.** *Not* the operators (extreme mutation), *not* the
oracle framing (checked coverage / oracle assessment / metamorphic), *not* σ = TD (Hegedűs; the SC paper).
New here: (i) the **two-sign** specification complexity $\sigma(P, \mu \cup \mu^-)$ as the first quantity
bounding behavioral identity over both labels (§2, §8); (ii) **channel isolation** (Thm 5.2) — the negative
sign is *non-redundant* with the positive (an existence witness of a one-channel distinction, not a claim
of statistical independence; the may/must incomparability of De Nicola–Hennessy 1984 is its process-calculus
form), which is why extreme mutation is not redundant with traditional mutation (empirically
correlated-but-distinct, Appendix C); (iii) the codomain-total realization (**Form B**) reaching the
non-return effects; (iv) the population-derived **censor** layer with its κ / bounded-curvature theory
(§9, §14); and (v) the co-characterization of $\sigma$'s dynamics — $\mathrm{XTD}$ static, $\mathrm{RTD}$
(batch) / $\mathrm{SDdim}$ (adaptive `converge`) dynamic (Prop. 1.5b). The *consolidation = sample
compression* reading is claimed neither as new nor as established: it is **retracted to a conjecture**
fenced by the multiclass compression impossibilities (Prop. 15.6). Everything else is assembly, cited as
such.

---

## 18. Open Problems

The frontier is now four *named, scoped* items (Q1, Q5, Q7, Q8) plus three standing theory questions
(Q2–Q4) and one build-through target (Q6). None is a fog; §§13–16 turned the earlier open ground into
these.

1. **κ for code — the graph choice (was "blocks censors"; now the sole code-specific residual).** §14
   supplies κ's definition (marginal coverage = PageRank), its re-flow dynamics, the bounded-curvature
   tractability object, and the machine-checked admissibility guard — all built for the semantic *rule*
   graph (Regenesis). What remains code-specific is which graph κ is computed over: call graph, import
   graph, or the obligation graph induced by interface mutants (Def. 10.1). The choice decides whether
   $I_{\mathrm{ind}}$ is cheap or a research project; it is a decision plus a measurement (Q5), not an
   invention.
2. **The regime key (Def. 9.1 keying).** Regime = symmetry; a censor keyed below the semantic-equivalence
   class over-reaches (traps positions that merely rhyme), keyed above it under-reaches. Working guess:
   typed interface + purity class. Wants a derivation.
3. **μ⁻ equivalence — resolved for Form A (Prop. 11.5), open for Form B.** Form B has no compilable
   mutant, so TCE-style bytecode identity (Wesker #24) does not apply; a negative mirror of
   `candidate-equivalent — UNPROVEN` may be required per sibling type.
4. **Completeness of Π (Def. 11.8, 11.8b).** How much of the codomain a finite perturbation family fences
   — the negative analogue of the positive operator-basis question SC §2.3 leaves open. Bounds require
   measuring reach against a codomain model, i.e. Fork 2's observed type (Def. 11.10). (The user's
   fenced-off "full-40 Π" completeness item.)
5. **The bounded-curvature bound (Def. 14.6; Conj. 10.4 → Cor. 14.5, now measured).** The obstruction is
   no longer conjectured: `promotion_not_submodular` is measured constructively (Thm 14.4, $d \le 14$–$25$
   on six real pulls, the Macbeth $\kappa(\text{give}\mid\varnothing): 2\to3$ witness). Open is the
   POSITIVE bound — `bridge_curvature_bound`, greedy degrading in $d$ and recovering $(1-1/e)$ at $d=0$
   (Feige–Izsak, or Golovin–Krause adaptive) — a Lean TARGET, to be proved against a graph whose $d$ is
   already known. Measure $d$ on the *code* obligation graph once Q1 fixes it.
6. **Build ordering (μ⁻ realizations — largely closed).** Form A + Fork 1, Fork 2, and Form B are all
   built (Wesker `dfce857`/`bdefe56`/`bf0f179`), with Detective's two-sign consumption wired
   (`diagnose`/`converge --two-sign`) and the two channel-propagation leaks closed (Props. 11.13–11.14,
   `f5e0efc`/`3ba2387`). What remains under build is the corpus censor loop's *code* port (Q1) and the
   `UNDEFINED` disposition (Def. 7.3), needed only once a degenerate-measure case lands.
7. **Unify ESL's DOF universe with μ⁻ (§13).** ESL (forward prototype) drives a learner against the
   ONE-SIGN σ; two-sign ESL (Prop. 13.5) requires the DOF universe the learner descends to be
   $\mu \cup \mu^-$. The unification is the concrete next build toward Uroboros (Def. 13.6), and its
   payoff — a strictly smaller $I_{\mathrm{ext}}$ — is the C6 falsifiable prediction (Appendix C).
8. **The greenfield persisted-contract artifact (Def. 12.5).** The two-sign certificate exists as
   ingredients (μ⁻ survivors, the idiom lens, `flag`), but the *author-once, persisted* triage of the
   greenfield line is not a first-class artifact; the tool is still in ingestion/brownfield mode, which
   is why the negative intent still leaks into the per-run `--input` loop (Prop. 4.3). This is the
   station that turns the pipeline (§16) from a very good mutation tester into the paradigm.
9. **Wire the σ / SSL H-series here for the entropy-bit quantities.** $L_{\mathrm{ind}}$ (Def. 14.3) and
   the consolidation-as-free-energy reading (Prop. 15.5) are CONJECTURE pending the entropy-bit machinery
   ($H_0$, $L(D)$, $I_{\mathrm{solve}}$ in bits); the built quantities are coverage analogs. And
   `safe_forget_preserves_sigma_sem` (Thm 15.4's transport) is an unproved Lean target.

---

## 19. Status Ledger

*The smoothness of a document is not evidence of its truth; this ledger keeps proved / transported /
built / measured / conjectured separate for every claim the added sections make.*

**Proved (inherited, machine-checked — cite, do not re-derive).** σ = teaching dimension (SC Thm 2.7);
σ μ-parameterized (SC §2.3); representation independence (SC Thm 2.3); redundant ⟺ zero information gain
(SC Thm 3.11); composition gap and interface-mutant bound (SC Thm 3.15/3.16); finite-domain Blum status
and decidability (SC Thm 2.5); greedy = Angluin exact learner (SC Thm 4.3); the DOF singleton-cover exact
optimality and `coverage_submodular`, `marginal_antitone`, `greedy_coverage_bound`,
`resolution_bulk_bounded` — **all over a fixed ground structure only (Def. 10.2, Thm 14.4)**;
`self_confirming_cannot_certify`, `falsifiability_pivot` (the admissibility guard, Prop. 14.7).

**Transported (argued here from cited priors, not re-proved).** Prop. 2.2 (positive policies are
one-sign); Prop. 2.5 (μ⁻ is a second instantiation, no new metatheory); Theorem 5.2 (channel isolation);
Theorem 6.2 (automation boundary from σ = TD); Cor. 8.3 (the qualifier is decidability); Prop. 9.4
(admissibility as well-definedness); Prop. 10.3 (γ = d = bridge count); Cor. 10.6 (κ-gated removal);
Thm 13.3 (the ruler/reward duality, from ESL); Prop. 13.2/13.5 (the agent as two-sign exact learner);
Thm 15.2/15.4 (composition gap = clean-abstraction-barrier; consolidation = σ-preserving reduction);
Prop. 15.3 (the σ+γ+I⁻ minimizer is the canonical representative — mechanism proved, naming asserted).

**Built (Wesker `dfce857`/`bdefe56`/`bf0f179`; Detective `f8e912c`..`3ba2387`; all 2026-08-22 unless
noted).** μ⁻ **Form A + Fork 1** (Def. 11.4, 11.10) — `MutationCategory.OUTPUT` with the always-applicable
sub-modes ($p_{\mathrm{const}}, p_{\mathrm{id}}, p_{\mathrm{none}}$), return-site AST rewrites reusing the
evaluate/score/cover pipeline. **Fork 2** — the type-conditional family generated only for an observed
codomain type (`bdefe56`). **Form B** — the runtime `wrapper_factory` reaching the non-return codomain
(generators, yield sub-modes; `bf0f179`). The **two-sign policy** σ(P, μ ∪ μ⁻) as an opt-in
`mutation_policy(two_sign=True)` with its own id, the default one-sign id byte-identical. **Detective's
consumption** — `diagnose`/`converge --two-sign`, the Fork-2 return-type capture, the classification and
compile paths taught both new mutant kinds. **Channel propagation** (Props. 11.13–11.14) — the
$p_{\mathrm{none}}$ existence fence in the generator golden (`f5e0efc`) and the mutant-value threading for
the $p_{\mathrm{ctype}}$ field fence (`3ba2387`), each pinned by hand-written intent tests. **The corpus
censor loop** (§14) — κ, marginal-coverage selection, the machine-checked admissibility gate, oscillation→
specialize, the corpus fixpoint with demotion — built and tested *in Regenesis*
(`significance.py`/`promotion_ledger.py`), conservative-empty on clean data by construction. **ESL forward
pass** — a running prototype (2026-07-17), the CLI-as-harness (Def. 13.4).

**Measured.** The out-of-universe rewrite passing a positive SC=1 badge (Prop. 3.5, slugify, 2026-08-07);
the "degenerate" near-miss witnesses outperforming hand-written tests (2026-08-07; a teaching artifact,
not a natural sample). The two channel-propagation closures end-to-end (`gen` 6/6, `flow` 8/8,
2026-08-22). The bridge/bounded-curvature regime (Thm 14.4): $d \le 14$–$25$ over six real pulls, the
sparse rule graph kneeing 3–12× later with a 3.5–8× softer drop than the dense IS-A graph, the Macbeth
antitonicity-violation witness (all *Significance Weighting* §16.1a, 2026-07-15). *Prior art measured*
(read 2026-08-23): pseudo-tested methods in **all 21 projects over 28K+ Java methods**, prevalence
$1$–$46\%$, MS_pseudo significantly below MS_required yet nonzero and Spearman $\approx 0.6$ (Vera-Pérez et
al. — C4/C5), with $<30\%$ developer-judged worth fixing (the triage).

**Grounded in prior art (§17; the unification is an assembly, not new machinery — cite, do not re-derive).**
The universal μ⁻ operators $=$ extreme mutation (Niedermayr; Vera-Pérez/Descartes); the
$\mathrm{effects}$/$\mathrm{detect}$ calculus (Rem. 3.2b) $=$ Vera-Pérez's Defs. 3–4; value-kill $=$ checked
coverage (Schuler–Zeller); the unpinned perturbation $=$ an oracle false-negative (Jahangirova); the
codomain relation $=$ metamorphic testing (Segura); σ $=$ TD $=$ exact-learning query complexity (Hegedűs;
Hellerstein); the RTD–VC–compression bridge (Doliwa; Chen). The contribution is orthogonal: the two-sign
σ, channel isolation, Form B, the censor layer, and the TD/RTD co-characterization.

**Conjectured / unbuilt (the Lean targets and the code ports).** `bridge_curvature_bound` — the positive
degrading guarantee (Def. 14.6; the negative `promotion_not_submodular` is measured, the positive bound
is not). κ for code — the graph choice (§18 Q1). Two-sign ESL and Uroboros (Def. 13.6) — designed; the
backward pass is unrun and no trained two-sign learner exists. The greenfield persisted contract
(Def. 12.5, §18 Q8). The entropy-bit $L_{\mathrm{ind}}$ and consolidation-as-free-energy (Prop. 15.5,
§18 Q9); `safe_forget_preserves_sigma_sem` (Thm 15.4's transport). The `UNDEFINED` disposition
(Def. 7.3), needed only once a degenerate-measure case lands.

**Asserted (interpretations, argued not proved).** "σ makes SICP computable" as a *phrasing*
(`thesis_vision.md`, not read; the *mechanism* is proved, Prop. 15.3). The identification of ESL's
statistical/exact gap with intelligence (György et al. + the parent conjecture, promising-not-established,
Def. 13.6). The reading of the corpus self-teaching term as SSL's unknown-knowns regime (Def. 14.3;
*Significance Weighting* §11's own asserted move). The sign as *probed axis* not mechanism (Rem. 2.2b —
extreme mutation is a positive-mechanism, negative-sign policy). The co-characterization of
$\sigma$'s dynamics — $\mathrm{RTD}$ for the batch suite, $\mathrm{SDdim}$ for the adaptive `converge`
trajectory (Prop. 1.5b; Devulapalli–Hanneke 2024) — is argued from the greedy trajectory's structure, not
proved.

**Retracted (this pass, 2026-08-23 — grounding the cited results overrode an earlier over-claim).**
*Consolidation $=$ a bounded sample-compression scheme* (former Prop. 15.6). Directly grounding the recent
literature showed the identification is open and, worse, obstructed: multiclass finite dimension does not
imply a dimension-bounded compression scheme (Pabbaraju, ALT 2024), the *list* relaxation can also fail to
compress (Hanneke–Moran–Waknine, COLT 2024), and the collusion-free route $\mathrm{NCTD}\le\mathrm{VCD}$ is
unproven (the 2026 Liu–Li preprint was withdrawn with a flawed lemma). Prop. 15.6 is now the conservative
statement: consolidation is a σ-preserving *greedy set-cover reduction* with the known $\Theta(\log n)$ gap
over an NP-hard / double-exponential-hard exact problem (Feige; Dinur–Steurer; Chakraborty 2024;
Moret–Shapiro), the compression *reading* a fenced conjecture. Two smaller phrasings were corrected the
same pass: Hegedűs to a two-sided (up-to-log) bound (Prop. 1.5b), and "orthogonal / independent channels"
to "non-redundant" (Thm 5.2 is an existence witness; the De Nicola–Hennessy may/must incomparability
corroborates).

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
| $\gamma, d$ | composition gap, supermodular degree (Def. 10.1–10.2, 14.6) |
| $\kappa(v \mid S)$ | marginal coverage / hub-score = genealogy PageRank (Def. 14.1) |
| $L_{\mathrm{ind}}, N_{\mathrm{ind}}(H)$ | self-teaching fraction; rate of admissible corpus-derived censors (Def. 14.3) |
| $g_{\mathrm{cov}}, g_{\mathrm{eff}}$ | coverage gap, efficiency gap — the σ-gap (Def. 13.1) |
| $[f]_{\equiv^{\pm}}$ | the two-sign (behavioral + negative) identity class (Def. 15.1) |

## Appendix B — Citation ledger (priors read directly; cite, do not re-derive)

**Author's corpus (read in full for the §§13–16 integration, 2026-08-22/23; cite, do not re-derive).**
`specification_complexity_paper.md` — the proved core: Thm 2.3 (representation independence), 2.5 (Blum),
2.7 (σ = teaching dimension), 3.4 (bulk→tail = statistical→exact), 3.10 (free energy), 3.11 (redundancy =
zero information), 3.15/3.16 (composition gap $\gamma$; interface-mutant bound), 4.1 (regime = symmetry),
4.3 (greedy = Angluin exact learner) · `Semantic_Specification_Learning/01_PAPER_SKELETON.md` (SSL) §§1.4c
(three information regimes), 2.5 (Completeness Equation, $\kappa$, the machine-checked
submodular/antitone/greedy/knee results, $L(\mathrm{NLP})=0.528$), 3.2, 4.3/4.4 (the falsifiability guard,
retained-plurality budget), 5 (lawful plurality) · `Semantic_Specification_Learning/06_EXACT_SPECIFICATION_LEARNING.md`
(ESL) §§1.4/1.4b (the ruler/reward duality), 2.2 (singleton covers ⇒ exact optimality), 4.1/4.2 (the
harness; agency-is-the-bug), 4.3, 5 (the backward pass) · `SIGNIFICANCE_WEIGHTING.md` §§5 (weight by
$\kappa$), 7b (κ re-flows), 11 ($N_{\mathrm{ind}}$), 12 ($I_{\mathrm{ind}}/I_{\mathrm{ext}}$), 13 (the
bridge crux), 14 (admissibility = well-definedness), 16.1a (the measurement), 17/17.1 (consolidation) ·
`law_as_architecture.md` §§7, 8 · this repo: `ARCHITECTURE.md` §§0, 11; `docs/PARSIMONY_ADVISORY.md`. Not
read: `thesis_vision.md` (the "σ makes SICP computable" phrasing — a communication document; the mechanism
is proved here from SC Thm 3.15/3.16, the naming is carried ASSERTED).

**Live source (traced 2026-08-22/23).** `Wesker/engine.py`: `Mutant`, `MutationCategory`,
`_RECORD_MUTATOR_FACTORIES`, `_BaseMutator`, `mutant_disposition`, `SCORED_DISPOSITIONS`,
`generate_mutants`, `evaluate_mutant`, `check_equivalent`, `run_function_profiling`, `_DataflowMutator`
(`return_sub`), the `wrapper_factory` Form-B seam. `Detective`: `equivalence.Witness`/`_search_witness`/
`_outcome_value` (the mutant-value threading, Prop. 11.14), `synthesis/characterization.golden_assert_line`/
`distinction_pin_lines`/`_walk_distinction` (the fences, Props. 11.13–11.14). `Regenesis`
(`/Users/rohanvinaik/Projects/Regenesis`, the Python Genesis port, verified 2026-08-23): `significance.py`
(`coverage`/`marginal_coverage`/`is_bridge`/`greedy_coverage`/`measure_coverage`) and `promotion_ledger.py`
(`marginal_kappa`/`rank_candidates`/`is_spine_confirmed`/`retains_plurality`/`admissible`/`corpus_fixpoint`/
`_demotion_keys`) — the built corpus censor loop of §14.

**Prior art READ DIRECTLY (2026-08-23; verified against the paper, §17).** Vera-Pérez, Monperrus & Baudry
2018, *Descartes: A PITest Engine to Detect Pseudo-Tested Methods* (arXiv:1811.03045 — the extreme-mutation
operator table, Rem. 11.9b) · Vera-Pérez, Danglot, Monperrus & Baudry 2018/19, *A Comprehensive Study of
Pseudo-tested Methods* (arXiv:1807.05030 — the $\mathrm{effects}$/$\mathrm{detect}$ calculus Defs. 3–4,
Rem. 3.2b; prevalence $1$–$46\%$ over 28K+ methods; the crash-kill/value finding, Def. 1.4; the $<30\%$
triage, C5) · Schuler & Zeller 2011, *Assessing Oracle Quality with Checked Coverage* (ICST — value/run
$=$ checked/ordinary coverage; read via publisher record + the dynamic-slice definition).

**Prior art VERIFIED THIS SESSION (2026-08-23, via arXiv abstract fetch — existence, title, authors, and
central claim confirmed against the source; cite as grounded).** Pabbaraju, *Multiclass Learnability Does
Not Imply Sample Compression* (arXiv:2308.06424, ALT 2024 — multiclass finite DS-dim ⇏ a dimension-bounded
compression scheme; the Prop. 15.6 obstruction) · Hanneke, Moran & Waknine, *List Sample Compression and
Uniform Convergence* (arXiv:2403.10889, COLT 2024 — there exist list-learnable classes with **no** bounded
list compression; the *list* relaxation does not rescue Prop. 15.6) · Devulapalli & Hanneke, *The Dimension
of Self-Directed Learning* (arXiv:2402.13400, ALT 2024 — SDdim characterizes self-directed learning,
distinct from teacher-directed RTD; Prop. 1.5b's adaptive dynamics) · Chakraborty, Foucaud, Majumdar & Tale,
*Tight (Double) Exponential Bounds for Identification Problems: Locating-Dominating Set and Test Cover*
(arXiv:2402.08346, ISAAC 2024 — Test Cover is double-exponentially hard in the solution parameter; Rem. 1.3b,
Prop. 15.6) · Yue, Chen, Lu, Zhao, Wang, Song & Huang, *Does Reinforcement Learning Really Incentivize
Reasoning Capacity in LLMs Beyond the Base Model?* (arXiv:2504.13837, NeurIPS 2025 — RLVR sharpens within
base-model sampling support; the ESL backward-pass caveat, Def. 13.6). **Verified as WITHDRAWN — cited only
as an OPEN problem, never as a result:** Liu & Li, *The No-Clash Teaching Dimension is Bounded by VC
Dimension* (arXiv:2603.23561, 2026 — withdrawn, author comment "the proof of Lemma 2 is wrong"); so
$\mathrm{NCTD}\le\mathrm{VCD}$ is open here (Prop. 1.5b, 15.6).

**External (RECALLED / from search records, NOT full-read — check before public use).** Winston 1970
(near-miss) · Minsky 1974/1980/1986 (frames, K-lines, censors) · Mitchell 1982 (version spaces) ·
Goldman–Kearns 1995, Goldman–Mathias 1996 (teaching dimension) · Angluin 1987/1988 (exact learning) ·
**Hegedűs 1995 (generalized TD = query complexity of exact learning)** · **Hellerstein, Pillaipakkamnatt,
Raghavan & Wilkins 1996 (query complexity / certificates)** · Zilles et al. 2011, Doliwa et al. 2014 (RTD;
RTD–VCD–compression) · **Chen, Cheng & Tang 2016 ($\mathrm{RTD}\le d\,2^{d+1}$)** · **Simon 2015 (RTD-vs-VCD,
open problem)** · **Niedermayr, Juergens & Wagner 2016 (extreme mutation / pseudo-tested, origin)** ·
**Jahangirova, Clark, Harman & Tonella 2016 (oracle assessment; +48.6% fault detection — PDF host down,
from record)** · **Chen, Cheung & Yiu 1998; Segura et al. 2016 (metamorphic testing)** · Budd & Angluin
1982 (mutation equivalence undecidable) · Papadakis et al. (TCE) · Feige–Izsak (bounded supermodular
degree) · Golovin–Krause 2011 (adaptive submodularity) · Nemhauser–Wolsey–Fisher 1978 (greedy $(1-1/e)$) ·
Blais et al. 2012 (identity testing) · György et al. 2025 (exact learning for general intelligence) ·
Crick–Mitchison 1983 (reverse learning) · Rice 1953 · Landauer 1961 (erasure cost) · Abelson & Sussman
(SICP — the aesthetic §15 makes computable).

**Foundational, newly cited this pass (2026-08-23; classical results entering the text at Rem. 1.3b, Def. 1.4,
Rem. 5.3b, Prop. 15.6 — safe to cite, not full-read).** De Nicola & Hennessy 1984 (may/must testing;
incomparable preorders — Rem. 5.3b) · Alpern & Schneider 1985/1987 (safety/liveness; finite bad prefixes —
Def. 1.4) · Bauer, Leucker & Schallhart 2011 (LTL₃ ⊤/?/⊥ runtime verdict — Def. 1.4) · Kupferman & Vardi
2003 (vacuity detection — Def. 1.4, §3) · Offutt–Untch RIP / Voas PIE 1992 (reachability–infection–
propagation = run-kill vs value-kill — Def. 1.4) · Meyer 1992 (Design by Contract; blame assignment) ·
Kurtz, Ammann & Offutt 2015 (true vs dynamic subsumption = σ vs $\hat\sigma$ — Rem. 1.3b) ·
Ammann–Delamaro–Offutt ICST 2014 (Thm 2: minimal mutant sets share one cardinality — well-definedness) ·
Moret & Shapiro 1985 (minimum distinguishing test set; the greedy $\Theta(\log n)$ gap — Rem. 1.3b, Prop. 15.6) ·
Feige 1998 / Dinur–Steurer 2014 (set-cover inapproximability — Rem. 1.3b, Prop. 15.6) ·
Kirkpatrick, Simon & Zilles 2019 (no-clash teaching dimension NCTD — the collusion-free parameter, Prop. 1.5b/15.6) ·
Maton, Kapfhammer & McMinn ICSME 2024 (statement-level pseudo-testedness — the method-granularity qualifier;
RECALLED, not full-read).

## Appendix C — Empirical Predictions and Falsifiable Tests

The construction makes measurable predictions. Several are already measured — C1, C2 (2026-08-07), the two
channel-propagation closures (§11.12, `gen`/`flow`, 2026-08-22), and the bridge/bounded-curvature regime on
the rule graph (§14, *Significance Weighting* §16.1a) — and the rest are runnable with instrumentation the
tool already exposes (`converge` reports the killable residual = $I_{\mathrm{solve}}$).

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

**C4 (non-redundancy — CORRELATED BUT DISTINCT, partially measured; refined from "largely disjoint").** By
Theorem 5.2 the channels are *non-redundant* in content (Thm 5.2 witnesses a distinction present in one and
absent from the other — not a claim of statistical independence), so the negative ($\mu^-$/extreme-mutation)
survivors are not a re-derivation of the positive ($\mu$/traditional) survivors. The prior art *measures*
this and it is more nuanced than disjointness: Vera-Pérez et al. (2018/19) found the traditional mutation
score of pseudo-tested (extreme-survivor) methods is *significantly lower* than that of required methods
(Wilcoxon $p<0.01$, effect size $1.5$) yet **nonzero and moderately correlated** (Spearman $\approx 0.6$,
Descartes vs. Gregor) — precisely the may/must *incomparability* (De Nicola–Hennessy 1984) rather than
independence. So the two channels are correlated-but-distinct, not disjoint — as Thm 5.2 predicts (the
graph of $(x,y)$ pairs overlaps, Def. 5.4, but the *content* is non-redundant). Falsifier: *identity* of the
two survivor sets (perfect correlation) — would collapse $\mu^-$ into redundancy (Cor. 5.3); *this is
refuted by the measured gap*.

**C5 (independence pair / pseudo-tested prevalence — CONFIRMED at scale).** *A measurable fraction of
green functions fail $p_{\mathrm{const}}$ or $p_{\mathrm{id}}$.* This is the pseudo-tested-method
phenomenon, and it is measured: pseudo-tested methods (all effects unpinned — the $p_{\mathrm{const}}$
survivor, Rem. 11.9b) appear in **all of 21 open-source Java projects across 28K+ methods**, at prevalence
$1$–$46\%$ (Vera-Pérez et al. 2018/19; Niedermayr et al. 2016 reported $6$–$53\%$). The fraction is a
direct measurement of what positive-only completeness misses, and it is far from $0$. Refined addendum:
developers judged **$<30\%$ of these worth a testing action** — the $\mathrm{DOF}^-$ (real fence) vs
$\mathrm{DOF}^0$ (admissible) triage (Def. 12.1) measured, confirming that most unpinned negative DOF are
admissible mechanical residual, a minority intent-bearing fences. Falsifier: prevalence $\approx 0$ on a
broad corpus — *refuted*.

**C6 (two-sign ESL residual, predicted — §13).** *A learner driving specification against $\sigma(P,
\mu^{\pm})$ has a strictly smaller external-teaching residual $I_{\mathrm{ext}}$ than one driving against
one-sign $\sigma(P, \mu)$.* Prop. 13.5: authoring the negative sign once moves the mis-classified negative
intent (Prop. 4.3) out of the per-run query loop. Run the ESL forward pass under $\mu$ and under
$\mu^{\pm}$ on the same held-out functions; the gap in query count is the second sign's information
content. Falsifier: no reduction — would refute Prop. 13.5 and, with C3, the automation-relocation claim.

**C7 (bounded curvature on the code graph, predicted — §14, §18 Q1/Q5).** *The code obligation graph is
fragmented, so its supermodular degree $d$ is large and the borrowed $(1-1/e)$ greedy bound is far from
holding; and $d$ falls as induced censors bridge components.* Measured on the *rule* graph, $d \le 14$–$25$
across six pulls (Thm 14.4); the prediction is that a call/import/obligation graph over a real package is
similarly fragmented (sparse, $b < 1$). Runnable once Q1 fixes the graph: compute $d$; then grow the censor
set and re-measure. Falsifier: $d \approx 0$ (a connected code graph) — would make the naive submodular
bound apply and retire Def. 14.6 for code (a welcome refutation, but predicted false).

**C8 (consolidation preserves the two-sign witness, predicted — §15).** *`decompose --apply` under a
two-sign profile returns a σ-minimal representative whose value pins AND negative fences are byte-identical
to the pre-consolidation certificate.* Thm 15.4 transported: safe forgetting drops only zero-κ
(zero-information) structure. Run `decompose --apply` on a converged two-sign target; re-profile. Falsifier:
any surviving fence or value pin that the consolidated form no longer kills — would show the reduction
crossed the σ-witness, refuting the representation-independence transport.

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

**§§13–16 — the stack integration (2026-08-23).** Sections 1–12 are the two-sign contract; §§13–16 were
added by tracing four previously-separate documents of the author's corpus into one place, because the
connective tissue between them is not written anywhere else and is easily lost. Each contributes one
layer that this document had left implicit: *Exact Specification Learning* (ESL) supplies the observation
that a computable $\sigma$ is a ruler read forward and a reward descended backward — so the tool's CLI was
always an exact-learning harness, not an over-built menu (§13); *Significance Weighting* supplies the
$\kappa$ machinery for population-derived censors and its load-bearing negative result — that the censor
loop's tractability is bounded-curvature and not submodular, because the valuable censors are bridges — a
result *measured*, on a running symbolic engine (Regenesis), before it was assumed (§14); the
*Specification Complexity* composition-gap and redundancy theorems supply the computable definition of the
canonical form and identify it with consolidation, the σ-invariant run in reverse — Detective's own
`decompose`, and the Crick–Mitchison wake/sleep dynamics (§15). The result is one paradigm (§16): intent →
implementation → the auto-fillable two-sign contract → mutation-as-selection to the canonical form. The
integration is an *assembly*, not new machinery — every load-bearing claim carries the status (§19) of the
document it came from, and the interpretive moves (the SICP naming, the intelligence bridge, the
unknown-knowns reading) are marked ASSERTED, not proved. Nothing here is deterministic-AI dressed as a
model: the architecture is the theorem-checked σ-engine throughout; any learner is a schema-constrained,
injection-proof tail whose reward is a theorem (ESL §4.1, "agency is the bug").
