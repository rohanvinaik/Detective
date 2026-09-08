---
title: "Effect and Meaning in Mutation-Based Specification"
subtitle: "Evidence, conditional dependence, and bounded test-input synthesis"
author: "Rohan Vinaik"
date: "2026-08-26"
status: "draft — audit-corrected 2026-09-07; semantic, probabilistic and syntactic claims separated; no mechanization of the new probability model is claimed"
provenance: >
  Companion to two papers: the adequacy-completeness paper (operator_completeness/, footprint reduction,
  ceiling theorem, decidability spectrum) and the negative-specification paper (NEGATIVE_SPECIFICATION.md,
  σ = teaching dimension, DOF⁺/DOF⁻/DOF⁰, composition gap γ, falsifiability_pivot). This paper does NOT
  re-characterize adequacy (that is the first paper's Theorem 3.2). Its contribution is the effect/meaning
  boundary as an organizing frame, and bounded dataflow candidates for improving synthesis.
  Statistical coupling and semantic reachability are distinct from those candidates. Cite the results of
  the companion papers.
---

# Effect and Meaning in Mutation-Based Specification

## Evidence, conditional dependence, and bounded test-input synthesis

### Abstract

Mutation analysis separates evidence about observable program differences from claims
about intended behavior. We define effect by a mutant's detection set and distinguish
individual execution witnesses from the generally undecidable task of recovering that
set completely. Intent information requires a specified joint experiment connecting a
latent intended function to test selection; it cannot be inferred from program text
alone. For positive-probability killing regions on finite input spaces, dependence of
the conditional input distribution is equivalent to positive mutual information.
This statistical identity does not by itself identify a specification-complexity
composition gap or prove that a syntactic dataflow edge witnesses dependence.
A bounded grammar can extract candidate conditioning edges and guide synthesis.
Independent product sampling can still discover coupled killing regions: its eventual
success depends on positive probability, while conditioning can improve finite-budget
discovery. Execution-based admission keeps these heuristics subordinate to the
measured one-function operator universe and its grounded tests.

---

## 1. Introduction

Mutation testing seeds a program with a small syntactic fault — a *mutant* — and measures a test suite by
whether it *kills* the mutant, distinguishing it from the original on some input. A high kill rate is read
as evidence that the suite specifies the program, and the reading has force: knowing *what a suite fails to
check* is the kind of thing a competent engineer does by understanding the code. A tool that reports it
therefore seems to understand the code. It does not. It walks the abstract syntax tree, rewrites one
operator, recompiles, and runs the suite; no representation of the program's purpose is built or consulted.

The apparent judgement is real but misplaced. It was performed by the author, once, at the time of writing,
and frozen into the program text; the tool reads it back. When a programmer writes `price >= floor`, the
decision that the relevant relation is an ordering has already been made and committed to a token that
denotes an ordering and nothing else. The tool does not recover that the comparison is an ordering — the
operator *is* the ordering. This is not a fact about mutation testing but about programs, and it is what
lets an adequacy measurement be mechanical and still informative.

Two distinctions organize this paper. First (§3), a detection set is determined by
program semantics, but that does not make general equivalence decidable. Observed
differences and external intent must remain separate. Second (§4–§5), dependence
within a killing region is a property of a specified distribution. Syntactic
conditioning edges can guide candidate construction, with finite-budget benefits,
without being necessary or sufficient for semantic coupling.

### 1.1 Contributions

- A precise observation experiment for intent information and counterexamples to
  recovering either all effects or intent information from syntax alone (§3).
- The finite-distribution equivalence between conditional dependence and positive
  mutual information, with its hypotheses and the unproved composition-gap bridge
  stated explicitly (§4.1).
- A bounded syntactic extraction method, distinguished from undecidable semantic
  reachability (§4.3), and an implementation that admits candidates through execution.
- A support-based discovery theorem replacing the incorrect claim that independent
  synthesis succeeds exactly on uncoupled footprints (§5).

The companion output-mutation ceiling is used only under its absolute-sufficiency,
exact-oracle and semantic-equivalence hypotheses. It is not a completeness theorem
for arbitrary finite syntactic mutation families.

## 2. Preliminaries

We recall the footprint model of the companion adequacy-completeness paper and fix the probabilistic setup
the meaning layer needs.

**Programs and output mutation.** A program denotes a total function $f : D \to R$ from inputs to a return
type, $|R| \ge 2$. An *output operator* is a map $p : R \to R$; it produces the mutant $p \circ f$. The
*footprint* $\Mov(p) = \{ r \in R : p(r) \neq r \}$ is the set of values it changes. Writing $I = f(D)$ for
the reachable outputs and $O = f(T)$ for those a suite $T$ observes, $p\circ f$ is non-equivalent iff
$\Mov(p)\cap I \neq \varnothing$ and is killed by $T$ iff $\Mov(p)\cap O \neq \varnothing$ (companion paper,
Prop. "an operator is its footprint"). We take as given its **ceiling theorem**: a full absolute score holds
exactly when $O = I$, i.e. a perfect mutation score certifies output coverage and nothing more.

**Detection sets for input mutation.** Extraction (§4) concerns functions of several arguments and mutations
at a program point. For a mutant $m$ of $f$, the *detection set* is $\Det(m) = \{ x \in D : m(x) \neq f(x)\}$
— the inputs on which $m$ is observably distinct. We use $\Det$ for the general (input-space) effect and
$\Mov$ for the output-operator special case; the two agree for output mutation via $\Det(p\circ f) =
f^{-1}(\Mov(p))$.

**Intent and observation experiment.** Let $\Theta$ be a random intended function with
prior $\mu$ on an admissible class $\Phi$. Specify a conditional test-selection channel
$Q(dx\mid\theta)$ and the joint law
$\Pr(\Theta=\theta,X\in dx)=\mu(\theta)Q(dx\mid\theta)$.
For fixed $f,m$, put $K_m=\mathbf{1}[m(X)\ne f(X)]$. The quantity used below is
$I(K_m;\Theta)$ under this **specified joint experiment**, not $I(K_m;\Phi)$ with
a set as an argument. If $X$ is independent of $\Theta$, then $K_m$ is independent
of $\Theta$ and the information is zero. Normative relevance requires a justified
connection from intended behavior to the chosen tests or assertions; this probability
model does not infer that connection from syntax.

## 3. Effect and meaning

**Definition 3.1 (effect).** The *effect* of a mutant $m$ is its detection set $\Det(m)$. For output
mutation this is $f^{-1}(\Mov(p))$, hence determined by the footprint. An effect is a fact about the text and
its executions.

**Definition 3.2 (intent information).** Relative to the specified $(\mu,Q)$ experiment,
a mutant's intent information is $I(K_m;\Theta)$. Call it *informationally inert* when
this is zero. This is a property of the experiment, not an intrinsic semantic label
for the operator. A positive association alone does not prove that the mutation
represents a requirement the author values.

**Proposition 3.3 (observed effect and external intent).** For computable total $f,m$,
membership of a supplied input in $\Det(m)$ can be checked by execution. Exhaustive
representation, emptiness, and equivalence of detection sets are not computable in
general. Further, $I(K_m;\Theta)$ is not determined by $f,m$ and the marginal input
distribution.

*Proof.* For a machine $M$, let $f(n)=0$ and let $m(n)$ indicate whether $M$ halts within
$n$ steps. Both are total and $\Det(m)$ is nonempty iff $M$ halts. For the second
claim take $f(x)=0,m(x)=x$ on Booleans and uniform $\Theta,X$. Under independent
selection $I(K_m;\Theta)=0$; under $X=\Theta$, the same marginal inputs and same
programs give $I(K_m;\Theta)=1$ bit. The missing joint law changes the quantity.
An observer lacking intended-function labels cannot choose between these experiments. $\qed$

The effect/intent distinction therefore has two boundaries. Executions establish
individual differences; a finite operator family and its tests bound the resulting
certificate. General equivalence remains unresolved without additional proof. Intent
information additionally requires an externally supplied observation experiment.
Comparing names and comparing prices may have different intended significance, but
the operand names do not determine a mutual-information value. Developer judgments
that a mutation merits no new test are evidence about preferences, not measurements
of zero mutual information under an unspecified channel.

## 4. Statistical coupling and syntactic conditioning edges

Given a target and mutant, synthesis seeks an input witnessing a difference. A bounded
grid can witness some differences but need not contain one, even for a scalar function.
Relations between parameters can make such grids inefficient or put witnesses outside
their support. We distinguish statistical coupling from the syntactic patterns used
to propose candidate inputs.

### 4.1 Definition and the equivalence

Let $f(a,b)$ have parameters in finite sets $A,B$, and fix a mutant $m$ and a product
law $\nu=\nu_A\times\nu_B$. Let $\kappa(a,b)=\mathbf{1}[m(a,b)\ne f(a,b)]$ and assume
$Z=\sum_{a,b}\kappa(a,b)\nu_A(a)\nu_B(b)>0$. Define the conditional killing distribution
$q(a,b)=\kappa(a,b)\nu_A(a)\nu_B(b)/Z$.

**Definition 4.1 (coupling).** Parameters $a$ and $b$ are *coupled* for $m$ iff the killing-region joint $q$
does not factor: $q(a,b) \neq q_A(a)\,q_B(b)$ for some $(a,b)$, where $q_A, q_B$ are the marginals. Otherwise
they are *independent* for $m$.

**Proposition 4.2 (statistical characterization).** On finite input spaces with positive
killing probability, coupling in Definition 4.1 is equivalent to $I(A;B)>0$ under $q$.

*Proof.* Mutual information is $D_{\mathrm{KL}}(q\Vert q_Aq_B)$, which is nonnegative
and zero exactly when the distributions agree. The normalized distribution and its
positive normalizer are hypotheses; when no killing input has positive probability,
$q$ is undefined, not an independent distribution. $\qed$

This is a probabilistic identity. It does **not** identify this particular killing
distribution with the specification-complexity composition gap $\gamma$. That theory's
components, specification family and composition interface require a separate bridge
to $(f,m,q)$; no such bridge is established here. The cited composition theorem is
retained in its own domain, without transporting an unsupported biconditional.

### 4.2 The conditioning edge

A candidate conditioning edge is a syntactic def-use relation: a value derived
from one parameter is consumed as a key into a collection derived from another.
For example:

```python
by_name = {e[k]: e for e in A}
value = by_name[B]
```

This suggests constructing related keys. It does not prove that the lookup is
reachable, that its result affects the return, or that a chosen mutant's conditional
killing distribution fails to factor. The original and mutant must be executed to
establish a distinguishing witness. Absence of a discovered witness remains
candidate equivalence, never a proof of equivalence.

### 4.3 Extraction: decidable for a bounded grammar, undecidable in general

**Definition 4.3 (conditioning-edge grammar $\mathcal{G}$).** A conditioning edge is in $\mathcal{G}$ when: a
dictionary is comprehended from a parameter $A$ keyed on a constant field of its elements
($\{e[k] : \cdots \mid e \in A\}$), and a value that traces — through a bounded def-use grammar of views
($\texttt{list}$/$\texttt{set}$/$\texttt{sorted}$), element extraction ($\texttt{.pop()}$), and
single-target comprehensions — to a *distinct* parameter $B$ is used as a subscript key into, or a
membership test against, that dictionary.

**Proposition 4.4 (bounded syntax; unbounded semantic reachability).**
1. Candidate edges in the explicitly bounded def-use grammar are mechanically
   enumerable: the AST is finite and the origin propagation has a finite bound.
2. Whether an arbitrary program point conditioned on an input is ever reachable
   is undecidable, even for total programs.

*Argument.* A bounded number of passes over finitely many bindings terminates;
syntactic matching then returns the represented triples. This establishes a total
bounded extractor, not soundness or completeness for statistical coupling.
For the semantic boundary, given $M$, define a total function that simulates $M$
for $b$ steps and reads $a$ at a distinguished point only if the simulation halted.
Some input reaches that point iff $M$ halts. Deciding that reachability would decide
halting. No identification of this reachability query with mutual information or
$\gamma$ is used.

The implementation's grammar coverage needs its own structural proof if claimed
complete for a separately specified grammar. Behavior pins check the implementation
against its selected mutation family; they do not discharge that metatheorem.

### 4.4 Implementation and evaluation

The bounded syntactic extractor described in Proposition 4.4(1) and a conditioning-aware synthesizer are implemented in a
production mutation-adequacy tool (`Detective`/`Wesker`). The extractor (`conditioning_edge`) returns the
triple $(A,k,B)$ or abstains; the synthesizer builds, for an extracted edge, inputs that instantiate $A$ as
cross-referential records whose fields differ and whose reference field forms a multi-hop graph, and $B$ as
keys naming into those records — a relation a chosen independent grid may miss. The band is *positive-only*:
a synthesized input is adopted only when it proves a new kill, so a mis-extraction can never manufacture a
false adequacy verdict, only fail to help.

The extractor is pinned to fire on two independently-written functions of the coupling shape — a transitive-
closure worklist and a production PEP-695 type-parameter resolver — and to abstain on functions lacking the
shape (no dictionary comprehension, a single parameter, a self-referential lookup, an unreferenced second
parameter). On the worklist target, the previously-unreached survivors that independent sampling reported as
candidate-equivalent become reached and killed by a clean value distinction (the coupling input drives the
worklist to a larger reachable set than the mutant computes). That experiment established
classification witnesses; it did not by itself establish their retention in a minimal written suite.
The current converge path passes witnesses through test construction, execution-based admission,
reprofiling, minimization and certificate verification. Each of those is an engineering obligation:
only the final valid measurement and green proof suite can support completion for a particular
function. No general synthesis-completeness claim follows from the original coupling experiment.

## 5. Synthesis completeness and the moving residual

**Proposition 5.1 (support and discovery).** Fix a sampling law $\nu$ and let
$p=\nu(\Det(m))$. Under independent draws of whole input tuples, the probability
of finding a distinguishing input within $n$ draws is $1-(1-p)^n$. Discovery
occurs almost surely eventually iff $p>0$. This includes product laws over parameters:
coupling of the conditional killing distribution does not imply $p=0$.

*Proof.* Each draw misses with probability $1-p$; independence across draws gives
$(1-p)^n$ for all misses. Its limit is zero iff $p>0$. $\qed$

**Counterexample to the former independence biconditional.** On two Booleans let
$f(a,b)=(a=b)$ and $m(a,b)=\mathrm{False}$. Independent uniform parameter sampling
kills with probability $1/2$. Conditional on a kill, $q$ puts mass $1/2$ on each
diagonal pair, so $I(A;B)=1$ bit. Four product-grid inputs exhaust the domain and
certainly find a kill despite coupling. Conversely, even an uncoupled killing region
can be missed forever by a sampling law whose support excludes it. On continuous
domains, nonempty zero-measure regions can also have $p=0$.

Conditioning-aware synthesis can increase finite-budget hit probability or reach
regions omitted by the chosen support. A bounded extraction grammar is one sufficient
way to construct such candidates, not a necessary condition for the existence of a
successful synthesizer. Successful construction is certified by the resulting execution,
not by the presence of a syntactic edge.

The practical synthesis residual changes when the candidate generator reaches more useful inputs.
That is a statement about this bounded search, not a theorem that every remaining input requires
human authorship. Another algorithm or a wider supported domain may find it. What remains unresolved
must be named as a search, representation, semantic-equivalence, or intent limitation on the evidence
actually available.

## 6. Why this is available for code

The decomposition and the extraction rest on a structural property of programs that natural language lacks.

Natural language carries relational content through an *inferential register* — implicature, defeasible and
context-dependent, that a reader reconstructs. "A is smaller than B," "B is bigger than A," and "B is looking
rather healthy next to A" can convey one ordering; recovering the operator from the third is inference, and
building a system that does it reliably is the standing problem of natural-language understanding. Code has no
such register. A program that depends on an ordering contains the ordering operator; there is no sub-token or
supra-token channel carrying relational content absent from the operators. The disambiguation that language
understanding must *perform*, the author of a program has already performed, at the time of writing, and
frozen into a typed token.

Program syntax makes explicit operations and many def-use relations available for
mechanical analysis. It does not settle their reachable semantic effects: dynamic
dispatch, arbitrary computation and unbounded domains remain relevant. A bounded
extractor reads a represented syntactic relation; execution or proof establishes
whether it witnesses an actual difference. This preserves the value of explicit
program structure without turning explicit syntax into decidable semantics.

## 7. The measurement as an instrument

A tool honest about the effect/meaning boundary must, at its interface, compute the effect layer and *name*
the meaning residual rather than present the second as the first. The production tool's command surface,
built prior to this analysis, realizes four such commitments, which we record because a surface that
independently converges on the theory's demands is evidence the demands are load-bearing. (i) Its exit codes
form a four-valued epistemic logic — clean; a real gap or refusal; a precondition to fix in the environment;
and an *invalid measurement* to re-run — separating "measured no gap" from "could not measure," the
determined-false / cannot-determine distinction as a machine-readable status. (ii) A verdict that would be
measured against the wrong file (a shadowed target, a colliding test module) is refused with the fix
printed, rather than reported. (iii) The `--input` grammar by which a human supplies what synthesis could not
is a decidable literal allowlist — the checkable boundary of §5's residual, one definition shared by the
writer and reader of the input store. (iv) Its help text states the epistemic role of each verb, installing
the mental model on which correct use depends. The coupling result sharpens (iii): the residual the surface
names is not fixed, and a new extraction grammar (§4.3) recedes it.

## 8. Related work

Mutation testing originates with DeMillo et al. (1978) and Hamlet (1977); its justification rests on the
competent-programmer and coupling-effect hypotheses, empirically supported (Offutt 1992; Just et al. 2014)
with results under restricted models rather than a general guarantee. Formal treatments — Budd and Angluin (1982), sufficient operator sets (Offutt et al. 1996),
minimal/dominator mutants (Ammann et al. 2014), semantic subsumption (Kurtz et al. 2015) — are relative to a
fixed program, pool, or test set, or establish undecidability of the associated decision problems; the
companion adequacy-completeness paper gives the program- and suite-independent characterization for output
mutation that this paper takes as its effect-layer summit. Extreme mutation and pseudo-testedness (Niedermayr
et al. 2016; Vera-Pérez et al. 2018) supply motivation for distinguishing observable changes from intended requirements. Proposition 4.2 uses
only the standard dependence/MI identity; a bridge to the companion composition-gap model is not proved. The extraction of §4 is a bounded
abstract-interpretation / taint analysis; its novelty is not the analysis technique but the identification —
of useful candidate relations, kept distinct from the statistical characterization in Proposition 4.2
and the support-based discovery result in Proposition 5.1. The normative reading of §6–§7 is in the tradition of Abelson
and Sussman on what program structure should make explicit.

## 9. Scope and open problems

The supported claims are finite execution witnesses, the conditional-distribution identity of
Proposition 4.2, termination of a bounded syntactic extractor, and the support-based discovery law.
None establishes complete semantic coupling extraction for arbitrary programs. A grammar-coverage
proof and a justified bridge to the composition-gap model would be additional results, not consequences
of mutation pins. The intent-information model requires an explicit prior and observation channel;
no empirical mutual-information measurement is claimed here. Implementation evidence is bounded by
its named targets, mutation policy and test regime. Classification witnesses must pass through test
writing, replay and the final validity gate before supporting a completed suite.

## 10. Conclusion

A mutation tool can enumerate a declared finite operator family and establish
individual differences by execution. General semantic equivalence remains outside
that guarantee, and intended significance requires external specification.
Statistical coupling is defined relative to a distribution; syntactic conditioning
edges are useful candidate generators rather than universal witnesses of that
coupling. Independent sampling succeeds almost surely when the killing set has
positive sampling probability. Conditioning changes practical discovery rates and
support. Every improvement must preserve the distinction between witnessed behavior,
unresolved semantics and authored intent.
