---
title: "What a Survivor Can Say"
subtitle: "Knowability II — wider regimes, three resolvers, and the information state of an unpinned dimension"
author: "Rohan Vinaik"
date: "2026-11-07"
status: >
  draft 0.1 — written from a design session (2026-11-06/07) against the live code of Wesker 2fbd029 and
  Detective ce2a500. Every numbered claim carries a status in §12: PROVED (inherited, machine-checked),
  DERIVED (a proof written here, not yet in Lean), CHECKED (exhaustively verified by the bundled script),
  MEASURED (read off the live code or a run), ASSERTED (argued, not proved), CONJECTURE (a falsifiable
  prediction). Nothing here is built yet; the build plan is openspec/changes/implement-knowability-ii/.
provenance: >
  Follow-up to the four documents that back the present tools. (1) The knowability paper,
  operator_completeness/KNOWABILITY.md (IEEE form: operator_completeness/submission/knowability_ieee.tex;
  numbering is shared: Thm 3.2, Cor 4.1–4.3, Thm 4.5, Thm 5.2, Prop 6.1, 7.1, 7.2, Thm 8.1, §9, §10).
  (2) NEGATIVE_SPECIFICATION.md (two signs; DOF⁺/DOF⁻/DOF⁰; Thm 5.2 isolation; Thm 6.2 automation
  boundary; §9 censors; §12 triage; §14 κ; §18 open problems). (3) COMMUNICATING_DETERMINISM.md (the
  injective-encoding requirement; symbols for what was not established). (4) SIGNIFICANCE_WEIGHTING.md
  (the Core Documents corpus; κ as marginal coverage; surprise = −log P; the bracket; §13 bridges).
  Design precedent outside this pair: TrialLedger (github.com/rohanvinaik/TrialLedger),
  TrialLedger/layer2/entail.py — exact finite enumeration over connected components, verdicts
  ENTAILED / REFUTED / UNDETERMINED / INCONSISTENT with the minimal deciding premise set.
---

# What a Survivor Can Say

## Knowability II — wider regimes, three resolvers, and the information state of an unpinned dimension

### Abstract

The knowability paper characterizes exactly what a passing score against **output mutation** can know about
a function: output coverage, and nothing else, with the value guards as the minimal sufficient regime
(Thm 3.2, Cor 4.1, Thm 4.5). Wesker and Detective run a far wider regime — ten program-text categories
plus the two-sign codomain family — and for every survivor of that wider regime the tools can today say
only `killable`, `candidate-equivalent — UNPROVEN`, or a fixture/structural caveat. The paper proves that no
universal certificate exists for program-text operators (Prop 7.2: their detection depends on the text).
This document shows that the absence of a universal certificate is not the absence of knowledge, in three
steps. **First**, the paper's theorem is exact at every mutation site once the site's local value is taken
as the codomain (Thm 3.1 here; this is weak mutation, Howden 1982). Run on a comparison's own truth table
it reproduces the Kaminski–Ammann–Offutt sufficient ROR set (Cor 3.2, checked), and run on Wesker's live
BOUNDARY table it finds a completeness gap: a suite can kill every BOUNDARY mutant of `a < b` without
ever exercising `a > b` (Cor 3.3, checked). **Second**, a program-text survivor is detected iff three
conditions hold on one input — the site is reached, the change infects the local value, the infected
value propagates to the oracle (DeMillo & Offutt 1991) — and each condition is a constraint read off the
code, so a survivor's residual is not one state but a typed grid of states with different remedies
(§5), decided by an exact finite-domain solver over the function's own premises (§4). **Third**, those
states are resolved by three resolvers, not two: structure (free), the corpus (self-taught censors,
NEGATIVE_SPECIFICATION §9), and the teacher (the finite triage of §12). Most of the per-run `--input`
demand is DOF⁰ and collapses mechanically (Thm 6.2); the teacher's share is small, finite, and — the
contribution of §7 — **ordered** before it is resolved, by κ (how much an answer collapses) and surprise
(how improbable a survival is given the structure), both emitted as brackets, never points. The result is
a function-level report of five numbers (H₀, L, L_ind, H*, I_ext) in place of one kill rate, and a command
surface whose alphabet distinguishes every state whose remedy differs (COMMUNICATING_DETERMINISM §3).
Six falsifiable predictions close the document (§11).

---

## 1. The question, and the shape of the answer

The paper answers one question exactly: *when does a full score against one output regime guarantee a
full score against another, for every program and suite?* Its answer (Thm 3.2) is program-independent
because output operators act on the returned value alone, and detection factors through the footprint
(Prop 7.2). The same proposition says why the answer does not extend: a program-text schema's mutant
depends on the text of f, so its detection varies across programs computing the same function.

Wesker runs program-text schemas by design — `VALUE, SWAP, STATE, BOUNDARY, TYPE, ARITHMETIC, LOGICAL,
STMT, EXCEPTION, DATAFLOW` (engine.py `MutationCategory`) — and the two-sign `OUTPUT` family. So the
tools are **wide where the paper is narrow, and sparse where the paper is exact**: a surviving BOUNDARY
mutant arrives with no theorem behind it, and converge can only search for a witness and, failing that,
file it under `candidate-equivalent — UNPROVEN` for a person.

The question this document answers is therefore: **what does a survivor of the wider regime tell you about
the function, and what is the honest, mechanical thing to do with it?** The answer has three parts.

1. **A theorem per site, not per program** (§3). The paper's theorem is exact for the *infect* condition
   at any site, with the local value as R. That is where program-independence survives.
2. **A state, not a verdict** (§4–§5). Reach, infect and propagate are constraints. A survivor's position
   in that grid decides its remedy, and the grid is finite.
3. **A quantity before a resolution** (§6–§7). The open states are resolved by structure, the corpus and
   the teacher, in that order; what the teacher is asked is ordered by κ and surprise, which are
   computable from the state alone.

Everything below is stated so that it can be built; the build is `openspec/changes/implement-knowability-ii/`.

---

## 2. Preliminaries and notation

From the paper: a program denotes $f : D \to R$; a suite is finite $T \subseteq D$; an output operator is
$p : R \to R$ with footprint $\mathrm{Mov}(p) = \{r : p(r) \ne r\}$; $I = f(D)$ reachable, $O = f(T)$
observed; an oracle is $\omega : R \to \Omega$ with $\mathrm{Det}_\omega(p) = \{r : \omega(p(r)) \ne
\omega(r)\}$ (Def 2.1–2.3, 9.1–9.2).

From NEGATIVE_SPECIFICATION: a positive policy $\mu$ (program-text variants) and a negative policy $\mu^-$
(codomain perturbations); $\mathrm{DOF}(f) = \mathrm{DOF}^{+} \sqcup \mathrm{DOF}^{-} \sqcup \mathrm{DOF}^{0}$
(Def 4.1); the teaching set $\Sigma^{\pm}(P)$ and the automation boundary (Thm 6.2); censors (Def 9.1) and
admissibility (Def 9.3); the finite triage (Def 12.1).

From SIGNIFICANCE_WEIGHTING: $\kappa(v \mid S) = |\mathrm{cover}(v) \setminus \mathrm{cover}(S)|$, the
marginal coverage of $v$ relative to an adopted set $S$ over a ground structure; surprise $= -\log P$ of a
chain given the branching the structure afforded; the $[\text{floor}, \text{ceiling}]$ bracket; bridges
(§13) and the supermodular degree $d$.

New here:

**Definition 2.1 (site, local value, local footprint).** A *site* $s$ is a node of the function's AST at
which a program-text mutant fires (`Mutant.mutated_line` locates it; `_BaseMutator._mark_applied` records
it). The *local value* at $s$ is the value the original expression at $s$ evaluates to on a given
execution; its type $R_s$ is the local codomain (for a comparison, the three regions $\{L, E, G\}$ of the
operands; for a Boolean connective, the four rows of its truth table; for an arithmetic expression over
ints, $\mathbb{Z}$). A program-text mutant $m$ at $s$ induces a map $p_m : R_s \to R_s$ on the local
value, and its *local footprint* is $\mathrm{Mov}_s(m) = \{v \in R_s : p_m(v) \ne v\}$.

**Definition 2.2 (the three conditions; cited).** For a program-text mutant $m$ at site $s$ and an input
$x$: $\mathrm{Reach}_s(x)$ iff executing $f$ on $x$ evaluates the expression at $s$; $\mathrm{Infect}_m(x)$
iff $\mathrm{Reach}_s(x)$ and the local value on $x$ lies in $\mathrm{Mov}_s(m)$; $\mathrm{Prop}_m(x)$ iff
$\mathrm{Infect}_m(x)$ and $\mathrm{sem}(m)(x) \ne f(x)$ (or, under an oracle, $\omega$ separates them).
This is the reachability / infection / propagation model of DeMillo & Offutt (IEEE TSE 17(9), 1991),
with the dynamic infection/propagation measurement of Just, Jalali & Ernst (ISSTA 2014). Nothing in it
is new; what is new is what the tools do with each condition separately.

**Definition 2.3 (premise, premise set, S-version).** A *premise* is a formula over the function's
parameters (and, for methods, the receiver's observed fields) in the literal language $L$ of
NEGATIVE_SPECIFICATION Def 6.4, with an *origin* (`author` | `caller` | `default` | `corpus`), a *status*
(`confirmed` | `proposed` | `rejected`) and a *scope* (function / module / repository). The *premise set*
$S$ is the set of confirmed premises in scope. Its *S-version* is a digest of the sorted confirmed premise
ids; every quantity computed relative to $S$ is stamped with it.

---

## 3. The theorem per site

**Theorem 3.1 (footprint characterization at a site; DERIVED).** Fix a site $s$ with local codomain
$R_s$, $|R_s| \ge 2$. Let $\Pi_s$ be a finite family of program-text mutants at $s$ and $\Gamma_s$ a
target family at $s$. Say $\Pi_s$ is *locally sufficient* for $\Gamma_s$ iff for every program and suite,
whenever every non-equivalent $\Pi_s$-mutant is *infected* by some test, every non-equivalent
$\Gamma_s$-mutant is infected by some test (non-equivalence and infection both read at the local value,
i.e. weak mutation). Then $\Pi_s$ is locally sufficient for $\Gamma_s$ iff
$$\forall g \in \Gamma_s,\ \forall b \in \mathrm{Mov}_s(g),\ \exists p \in \Pi_s:\ b \in \mathrm{Mov}_s(p) \subseteq \mathrm{Mov}_s(g).$$

*Proof.* Let $f_s : D \to R_s$ be the map from inputs to the local value at $s$ (defined on inputs that
reach $s$; restrict $D$ to those). A mutant at $s$ is infected on $x$ iff $f_s(x) \in \mathrm{Mov}_s(m)$,
and is locally non-equivalent iff $\mathrm{Mov}_s(m) \cap f_s(D) \ne \varnothing$. This is Prop 2.4 of the
paper with $f_s$ in place of $f$ and $R_s$ in place of $R$; the paper's Thm 3.2 then applies verbatim,
including its constructive separating program (realizability: every pair $(I, O)$ with $O \subseteq I
\subseteq R_s$ is met by some program whose expression at $s$ takes exactly those local values on $D$
and $T$). $\square$

*Remark.* The theorem is about **weak** mutation at $s$ (Howden 1982, cited by the paper). It says
nothing about reach or propagation, which are per-program; §4 handles those as constraints. For the
return site, reach is everything and propagation is the identity, and Thm 3.1 is the paper as written.

**Corollary 3.2 (local guards reproduce the sufficient ROR set; CHECKED).** For a comparison $a \mathrel{?}
b$ with $R_s = \{L, E, G\}$, the three singleton-footprint replacements are the minimal locally sufficient
regime for all seven replacements (the other five relational operators and the two predicate constants),
and for each of the six operators they are exactly the Kaminski–Ammann–Offutt sufficient set:
$<\!: \{\le, \ne, \mathrm{false}\}$, $\le\!: \{<, =, \mathrm{true}\}$, $>\!: \{\ge, \ne, \mathrm{false}\}$,
$\ge\!: \{>, =, \mathrm{true}\}$, $=\!: \{\le, \ge, \mathrm{false}\}$, $\ne\!: \{<, >, \mathrm{true}\}$.
(Checked exhaustively by `local_guards_check.py`, check 1.) The paper's §11 says per-schema program-
independent results "must be derived for its schema"; Cor 3.2 says the paper's own theorem derives them.

**Corollary 3.3 (Wesker's BOUNDARY table is locally incomplete for `<`, `>`, `==`, `!=`; CHECKED against
engine.py `_BoundaryMutator` at 2fbd029).** Wesker's alternatives for an ordering comparison are the
boundary shift, the direction reversal, the equality collapse and the two predicate constants (five
mutants). For `<` their local footprints are $\{E\}, \{G,L\}, \{E,L\}, \{E,G\}, \{L\}$; no footprint is
contained in $\{G\}$, so the $\ne$ guard (footprint $\{G\}$) is uncertified. The separating case: a
program whose comparison takes all three regions, and a suite observing only $L$ and $E$. All five Wesker
mutants die; the $\ne$ mutant is non-equivalent and survives. Symmetrically for `>`. For `==` and `!=`
on orderable operands the one-sided guards ($\le, \ge$ for `==`; $<, >$ for `!=`) are missing. (Check 2
of the script.) The repair is W1 of the build plan; note that on unorderable operands the one-sided
replacements raise, so that half of the repair is type-conditional (NEGATIVE_SPECIFICATION Def 11.10).

*What Cor 3.3 means in plain terms.* Today a suite that tests a threshold from below and at the threshold,
but never from above, is reported BOUNDARY-complete. The paper's theorem, applied locally, says the
"from above" question is a distinct value guard and no combination of the five existing mutants asks it.

**Proposition 3.4 (per-site ceiling for return sites; DERIVED).** Partition $D$ by the return site an
input exits through, $D = \bigsqcup_s D_s$, with $I_s = f(D_s)$ and $O_s = f(T \cap D_s)$. A full score
against the family of per-site output operators (an output operator applied only on the path through $s$;
NEGATIVE_SPECIFICATION Def 11.4 Form A already emits one mutant per `return` site) holds iff $O_s = I_s$
for every $s$. *Proof:* Thm 4.5 of the paper applied to $f|_{D_s}$ for each $s$. $\square$ A site with
$I_s = \varnothing$ is dead code (§5). This is a strictly finer certificate than Thm 4.5 (output coverage
per exit rather than per function) at no change in operator family.

**Remark 3.5 (what the local theorem does not give).** Local sufficiency is not sufficiency: two sites can
be reached on different inputs and an infected local value can be masked before the return. The paper's
no-universal-certificate result (Prop 7.2) is untouched. What Thm 3.1 adds is that one of the three
conditions — the one that decides *which mutants to generate* — has an exact, program-independent theory,
so the DOF count per site is a theorem (three questions per ordering comparison, not five), and the
operator basis per category can be derived rather than curated.

---

## 4. The three conditions as constraints

**Definition 4.1 (reach formula, infect formula, propagation observation).** For a survivor $m$ at site
$s$:

- $\varphi^{\mathrm{reach}}_s$ is the conjunction of the guards on the AST path to $s$, each with its
  polarity (`if c:` contributes $c$, its `else` contributes $\lnot c$, a `while c:` body contributes $c$,
  an `assert c` contributes $c$), rendered by `ast.unparse` over the function's parameter names. It is a
  formula in $L$ when every guard is; otherwise it is *opaque* and recorded as such.
- $\varphi^{\mathrm{infect}}_m$ is the condition on the local operands under which $p_m$ moves the local
  value, read off the operator's table: BOUNDARY `<`→`<=` gives $a = b$; `<`→`>` gives $a \ne b$;
  ARITHMETIC `+`→`-` gives $b \ne 0$, `*`→`+` gives $a \cdot b \ne a + b$; LOGICAL `and`→`or` gives
  $a \ne b$ (as truth values); VALUE $c$→$c'$ and OUTPUT perturbations give $\top$ (unconditional);
  DATAFLOW $x$→$y$ gives $x \ne y$; STATE, STMT and EXCEPTION are opaque unless the deleted statement's
  effect is a single assignment, in which case the formula is "the assigned value differs from the value
  the name held" (opaque in general; recorded as such).
- Propagation is **observed, not derived**: Wesker records, per covering test, whether the site was
  reached, whether the local value was infected (a site probe, build item W2), and whether the test killed.

Each formula carries a *kind*: `boolean` (finite), `linear` (comparisons of linear terms over the
parameters), `polynomial`, or `opaque`.

**Proposition 4.2 (detection is the conjunction; cited).** $x$ kills $m$ iff $\varphi^{\mathrm{reach}}_s(x)
\wedge \varphi^{\mathrm{infect}}_m(x) \wedge \mathrm{Prop}_m(x)$. *This is DeMillo–Offutt's necessity
and sufficiency conditions restated.*

**Proposition 4.3 (decidability of the symbolic part; DERIVED from the paper's Thm 5.2).** Satisfiability
of $\varphi^{\mathrm{reach}}_s \wedge \varphi^{\mathrm{infect}}_m \wedge \bigwedge S$:
(i) over finite literal domains (bools, enums, the pure-decision shape of ARCHITECTURE §11) is decidable
by exhaustion, and one input per region of the constants appearing in the formulas is exhaustive when
every formula is linear in one variable; (ii) when every formula is linear over ints it is the paper's
Presburger rung — decidable; (iii) when some formula is polynomial over unbounded ints there is no decision
procedure in general (Matiyasevich), so the honest verdict is *bounded*: `UNDETERMINED at bound B`, and a
single premise bounding the variables makes it finite; (iv) opaque formulas are not decided; the survivor
keeps the dynamic verdict only.

**Definition 4.4 (the solver and its verdicts; design transported from TrialLedger).** `decide(query,
premises, bound)` enumerates exactly, with `Fraction` arithmetic, over the connected component of the
query's variables (two formulas are connected iff they share a variable), returning one of
`ENTAILED` (no feasible assignment satisfies the premises with the query negated, and the premises are
satisfiable), `REFUTED` (likewise for the query itself), `UNDETERMINED` (both feasible, or the bound was
reached — never a negative finding), `INCONSISTENT` (the premises alone are unsatisfiable: a contradiction
anywhere in the component, nothing is entailed from it). Every verdict carries the minimal set of premises
that decided it and the blockers (unresolved content) that stopped it. The engine has no dependencies
beyond the standard library (Wesker's zero-dependency promise; TrialLedger's engine is the same shape and
the design reference, `TrialLedger/layer2/entail.py`). The satisfying assignment, when one exists and is
an $L$-term, is a candidate witness: the solver proposes, execution decides (§5, rule 2).

---

## 5. The alphabet: a survivor's state

**Definition 5.1 (survivor state).** A survivor's state is the tuple of (a) the dynamic record — reached
on $N_r$ covering executions, infected on $N_i \le N_r$, propagated on $N_p \le N_i$ (and killed by value
or by crash); (b) the symbolic verdicts on $\varphi^{\mathrm{reach}}_s$ and on $\varphi^{\mathrm{reach}}_s
\wedge \varphi^{\mathrm{infect}}_m$ under $S$; (c) the oracle class of the covering tests at the codomain
the mutant perturbs (§8); (d) whether any authored intent of either sign bears on the formula's variables.

**Proposition 5.2 (the state is finite and its remedies differ; ASSERTED, with the table as the object).**
Reading (a)–(d) through the paper's three kinds of knowledge (§1.2: semantic, observational, intent) and
NEGATIVE_SPECIFICATION's three regions yields the following states. Two rows with different remedies
must never share a sign (COMMUNICATING_DETERMINISM §3, the injectivity requirement); the table is the
specification of `Detective.equivalence.survivor_state` (build item D3), whose intent test is this table.

| State | Condition | Sign (CLI) | Remedy | Resolver |
|---|---|---|---|---|
| `killer_ready` | a witness exists (solver-proposed and execution-confirmed, or found by search) | `✗ real gap` | write the test (today's path) | structure |
| `dead_site` | $\varphi^{\mathrm{reach}}_s$ REFUTED under $S$ (or $\varnothing$ when $S = \varnothing$) | `dead site L<n>` | fix the code: the branch cannot run | author (code) |
| `reachable_if` | $\varphi^{\mathrm{reach}}_s \wedge \varphi^{\mathrm{infect}}_m$ satisfiable only by an assignment that violates a *confirmed* premise $P$ | `reachable if ¬P` | nothing, unless $P$ is wrong; re-ask $P$ by its κ | teacher (once) |
| `dof_zero` | satisfiable, and no intent of either sign bears on the variables | (never shown: becomes `killer_ready`) | synthesize the witness from the assignment; characterization test | structure |
| `local_equivalent` | $\varphi^{\mathrm{reach}}_s$ satisfiable, $\varphi^{\mathrm{reach}}_s \wedge \varphi^{\mathrm{infect}}_m$ REFUTED | `local equivalent` | nothing: a rewording ($x\cdot 1$); if by an invariant $x = y$, print the invariant | structure |
| `masked` | $N_i > 0$, $N_p = 0$, and surprise above the function's own bulk/tail knee (§7) | `masked on N` | fix the code: a distinction is made then erased (dead store, swallowed value) | author (code) |
| `pseudo_tested_oracle` | propagated at the codomain, but every covering test's oracle is in one $\omega$-class there (Prop 9.4 of the paper) | `pseudo-tested (ω)` | add the assertion, or fence the value as irrelevant | teacher |
| `open_at_bound` | any symbolic verdict UNDETERMINED at bound $B$, or $\bot$ within the step budget | `open at B` | raise $B$, supply a bounding premise, or flag | teacher / structure |
| `inconsistent_premises` | the component's confirmed premises are INCONSISTENT | `INCONSISTENT · {ids}` | fix the premise set, never the code | teacher |
| `value_residual`, `fixture_residual`, `structural_residual` | as today (`residual_disposition`) | as today | as today | structure |
| `genuine_equivalent` | reached ∧ expressible ∧ solver UNDETERMINED without bound ∧ no witness | `candidate-equivalent — UNPROVEN` | flag, as today | teacher |

Three rules govern the table.

1. **The literal level routes to code, not to a flag.** `dead_site`, `masked`, and a `local_equivalent`
   by invariant are the code contradicting itself: it states a distinction its own structure makes
   impossible. These are objectively wrong whatever the function is for, and today all three print as
   `candidate-equivalent — UNPROVEN`, inviting a flag. That is a collision in COMMUNICATING_DETERMINISM's
   sense (one sign, three remedies), and it is the first split the build makes.
2. **The solver proposes; execution decides.** A satisfying assignment is never a kill. It is a candidate
   input, run through the existing witness path (`equivalence.classify_survivor`), and only an observed
   difference writes a test. This preserves the standing rule that nothing is promoted by assertion.
3. **`dof_zero` is not a sign.** When no authored intent bears on the variables, the survivor is in
   $\mathrm{DOF}^{0}$ and collapses mechanically (Thm 6.2). It is printed only as the test it became.
   Prop 4.3 of NEGATIVE_SPECIFICATION — that the per-run `--input` demand is mostly un-authored intent —
   predicts that this row absorbs most of today's `--input` asks (prediction P2, §11).

---

## 6. Three resolvers, and what the report should say

**Proposition 6.1 (most of the residual is not the teacher's; cited).** By NEGATIVE_SPECIFICATION Thm 6.2
the specification of $\mathrm{DOF}^{0}$ is computable without an oracle, and by its Def 4.2 the teachable
remainder splits as $I_{\mathrm{solve}} = I_{\mathrm{ind}} + I_{\mathrm{ext}}$, with $I_{\mathrm{ind}}$
latent in the call-site population. So an open survivor is resolved by one of three resolvers, tried in
order:

- **Structure** — the formulas and the solver (§4–§5): dead sites, local equivalents, masked
  distinctions, and every $\mathrm{DOF}^{0}$ witness. Free.
- **Corpus** — a censor (Def 9.1): "no caller passes a negative amount" is a fact about the call-site
  population, carved from an observed near-miss, admitted only if spine-sourced and plurality-preserving
  (Def 9.3; machine-checked guard). It enters the ledger as a *proposed* premise with origin `corpus`,
  never confirmed by the engine's own derivations.
- **Teacher** — what survives both: the finite triage (Def 12.1), now *ordered* (§7).

**Definition 6.2 (premise ledger).** `.detective/premises.json` holds premises (Def 2.3). An
equivalence `flag` is a premise ("no input distinguishes $m$", origin `author`); a `--fence` is a negative
premise ("$(x,y)$ is forbidden", origin `author`); a censor is a `proposed` premise with origin `corpus`
and its spine source; a `default` premise names the convention it came from. A `--input` is a witness,
not a premise, and stays in `inputs.json`. The ledger replaces nothing: it names what `flag`, `--fence`,
`censor` and `samples` already record, in one place, with the S-version that every κ is stamped against.
This is NEGATIVE_SPECIFICATION §18 Q8, the greenfield persisted contract, in its minimal form.

**Definition 6.3 (the five-number report).** Per function, in place of one kill rate:

| Symbol | Meaning (coverage analog; counts, not bits) |
|---|---|
| $H_0$ | the behavioral dimensions in the universe (DOF total, as today) |
| $L$ | resolved by structure: value-killed + `dead_site` + `local_equivalent` + `masked` + `dof_zero` pinned |
| $L_{\mathrm{ind}}$ | resolvable by the corpus: survivors whose deciding premise is a proposed admissible censor |
| $H^{*}$ | open: `open_at_bound` + `genuine_equivalent` + `pseudo_tested_oracle` + `reachable_if` |
| $I_{\mathrm{ext}}$ | the teacher's queue: the items a person must answer, ordered by κ |

SIGNIFICANCE_WEIGHTING §16.5 is explicit that the built $L_{\mathrm{ind}}$ is a coverage analog of the
entropy-bit quantity; the same caveat holds here and is printed with the numbers.

**Proposition 6.4 (the agent is never trusted below the teaching set; interpretation of Thm 6.2).** In an
agentic workflow the party writing the code is not the party holding the intent. Everything in $L$ is
established without consulting either; $L_{\mathrm{ind}}$ is established from the call sites with a
machine-checked guard; only $I_{\mathrm{ext}}$ needs the human, and it arrives as concrete input/output
questions, not as code to read. An agent optimized to shrink the queue can only do so by moving items into
$L$ (writing tests that execute) or by making the code's distinctions fewer — and the latter is visible as
a change in $H_0$, which the receipt records. The Goodhart route (collapse outputs to hide faults) changes
$H_0$ and $|f(D)|$ in the same receipt, so it is not silent. *This is the alignment reading of the paper's
intent residual, and it is why the narrow paper matters to agentic coding: it draws the line below which
no trust in the agent is needed.*

---

## 7. κ and surprise: what can be said about an open item before it is resolved

**Definition 7.1 (κ by re-entailment; the graph is induced, not drawn).** For a candidate premise $v$ and
the current confirmed set $S$, $\kappa(v \mid S)$ is the number of open survivors whose solver verdict
changes when $v$ is adopted — computed by re-running `decide` on every component that mentions a variable
of $v$. The edge "$v \to m$" exists iff that re-run changes $m$'s status. There is no stored graph: the
graph *is* the solver's dependency, recomputed per $S$. This is the compute-not-impose law applied to the
ground structure itself, and it is why κ re-flows for free.

**Proposition 7.2 (κ is relative three ways; derived from the definition).** κ is relative to the
*space* (which survivors exist), to the *adopted set* $S$ (the same premise can have κ = 20 and, once a
censor already covers it, κ = 0), and to the *kind of resolution* (a within-function premise and a
cross-function censor collapse different things). It is not a scalar property of a premise. Every
printed κ therefore carries its S-version.

**Proposition 7.3 (the call graph is the quotient).** A censor spanning call sites reaches survivors in
every function it touches, so its κ is the sum of its within-function κ's; the call graph (Detective
`kappa.build_call_graph`, chosen in NEGATIVE_SPECIFICATION §18 Q1) is the quotient of the premise-survivor
graph by function. Bridges (`kappa.is_bridge`) and the supermodular degree $d$ live at the quotient. The
guarantee that applies is the bounded-curvature bound already closed in Lean
(`bridge_curvature_bound`: $\mathrm{opt} - \mathrm{gap}_k \ge (1 - e^{-1/(d+1)})\,\mathrm{opt}$), not the
submodular one; $d$ on any code graph is **unmeasured** (prediction P5).

**Definition 7.4 (surprise of a survivor; the null is measured, never defaulted).** For a survivor with
$N_i$ reached-and-infected executions and $N_p = 0$, let $q$ be the propagation rate measured on the
function's own killed mutants (killed reached-and-infected pairs over all reached-and-infected pairs).
The survival has probability $(1-q)^{N_i}$ under the null that propagation is independent per execution,
so its surprise is $-N_i \log_2 (1-q)$ bits. Emitted as a bracket: floor with $q$ from this function,
ceiling with $q$ from the repository's run, and **unmeasured** when no killed pair exists in the function
(never zero: an absent base is a missing measurement, not evidence). This is SIGNIFICANCE_WEIGHTING §2's
discipline (the base is read off the real graph) transported to execution traces.

**Proposition 7.5 (the absent expected kill is the signal).** A high-surprise survivor is one the
structure expected to die: reached, infected, and never propagated. That is the `masked` state of §5, and
its remedy is a code change, not a flag. Nothing about the survivor's equivalence had to be settled to
say it — the state of information is computable while the object stays unresolved, which is the point
of the second document applied here.

**Definition 7.6 (ordering and stopping).** The teacher's queue is ordered by κ bracket (floor first,
ties by ceiling, then by surprise). The stopping rule is κ → 0: a premise that settles nothing beyond
its own survivor is tail, and is asked only as that survivor's own `flag` question. Within a connected
component, greedy adoption by κ keeps the static submodular guarantee; across components it is the
bounded-curvature bound of Prop 7.3.

---

## 8. The categories, two-signed

Every category of the wider regime has a positive twin (which implementation; governed by Thm 3.1 and
§4) and a negative twin (which outputs are forbidden; governed by the knowability paper once the codomain
is enlarged). The two are isolated (NEGATIVE_SPECIFICATION Thm 5.2), so neither certifies the other.

| Category | Positive twin (DOF⁺) | Negative twin (DOF⁻) | What the residual mostly is | κ shape |
|---|---|---|---|---|
| A · expressions (ARITHMETIC, BOUNDARY, LOGICAL) | infection from the local table; Cor 3.2 gives the basis; Cor 3.3 the gap | $p_{\mathrm{neg}}, p_{\mathrm{abs}}, p_{\pm 1}$ on the return | structure; range questions are usually corpus censors | bulk: one range premise settles a component |
| B · variables, constants (VALUE, DATAFLOW, SWAP) | $x \to y$ infects where $x \ne y$; a constant infects unconditionally | $p_{\mathrm{const}}, p_{\mathrm{id}}$ (the independence pair) | structure: a surviving constant is pure reach/propagate evidence, high surprise when reached | tail, unless an invariant couples names |
| C · control flow (STMT, per-site return) | SDL infects iff the post-state changes; per-site output coverage (Prop 3.4) | $p_{\mathrm{const}}$ per return site | structure: `dead_site`, dead store | per-site reach premises are bulk |
| D · state, void (STATE) | statement deletion as above | $p_{\mathrm{state\text{-}noop}}, p_{\mathrm{state\text{-}extra}}$; the paper's §9 with $\omega = \pi_R$ (a return-only assertion is a non-injective oracle on $R \times S$) | corpus (which fields callers read), then teacher ("is $X$ in the contract?") | bridges: a state fence spans callers |
| E · exceptions, non-termination (EXCEPTION) | raised-type swap; handler body | $p_{\mathrm{raise}}$; the any-failure vs value oracle split of the paper's §9.5 = Detective's crash-kill vs value-kill | structure for crash-vs-value; `pytest.raises(Exception)` is a broad $\omega$-class (Prop 9.4b: the mixed score cannot reach one under it); $\bot$ is `open at B` | tail |
| F · dispatch, lazy values, identity (TYPE) | override/super deletion as per-slice mutants (Prop 3.4 with $D$ partitioned by receiver type) | $p_{\mathrm{class}}$; $p_{\mathrm{perm}}, p_{\mathrm{drop}}$ after materializing the stream | structure for the oracle fix (an address `repr` is the constant oracle, Prop 9.3); teacher for "is order load-bearing" | per-type |
| G · higher-order | masking of two infections on $O$ | composition shrinks footprints (Remark 3.3) | not certified; first-order remains the claim | — |

**The operator-addition criterion.** NEGATIVE_SPECIFICATION Remark 11.9's orthogonality rule decides what
is worth adding: perturbations the positive side cannot express. Under this document that rule has a
test: a candidate operator is worth adding iff its local footprint (Def 2.1) is not a union of existing
footprints at that site (Thm 3.1), or it probes a codomain the positive side cannot reach (state, raise,
stream). Cor 3.3 is the first application.

---

## 9. What the tool should say

COMMUNICATING_DETERMINISM's requirement is that the map from epistemic state to emitted sign is
injective over remedies. The alphabet of §5 is one half of the extension; the other half is that
quantities now travel with the signs, and quantities have their own collisions to avoid.

1. **Region travels with the sign.** Every open item prints its resolver (`structure-pending`,
   `corpus-pending`, `teacher`). "Needs you" and "the corpus has not been read" never share a line.
2. **A κ is a bracket with an S-version.** Never a point; never without the premise set it was computed
   against. A κ printed last week against a different $S$ is not the same number.
3. **A κ from the engine's own derivations is inadmissible, and says so.** The self-confirmation guard
   (NEGATIVE_SPECIFICATION §14; SIGNIFICANCE_WEIGHTING §14) is the well-definedness condition of
   $L_{\mathrm{ind}}$; a corpus candidate confirmed by the engine's own output prints as `inadmissible`,
   not as a low κ.
4. **Candidates are proposals.** A corpus-induced premise is `proposed` until spine-sourced and
   plurality-preserving, and a proposed premise never changes a verdict. The same rule TrialLedger
   applies to a reading: explored, never relied on.
5. **The one imperative names the max-κ item.** The `DO THIS` block, when the teacher's queue is
   non-empty, names the highest-κ premise and its bracket as the single next action; the full ordered
   queue is a verb (`detective ask`), not the default output.
6. **Surprise routes to code.** A `masked` survivor's next action is a code change; the block never
   suggests a flag for it. (Rule 1 of §5.)

---

## 10. Scope

The theorems of §3 are about weak mutation and inherit the paper's model (pure total denotations, an
exact or relativized oracle). The constraints of §4 are decided only when their formulas are in $L$ and
linear or finite; polynomial and opaque formulas are bounded or dynamic-only, and the document says so
rather than dissolving it. κ and surprise are coverage analogs with measured bases; the entropy-bit
quantities of SIGNIFICANCE_WEIGHTING are not wired here. The one-function law (ARCHITECTURE §11) holds
throughout: premises arrive as ledger entries with origins; no run widens to the suite or the repository.
Nothing here changes a verdict with site tracing and propagation off (regression requirement V5).

---

## 11. Falsifiable predictions

| # | Prediction | How to falsify |
|---|---|---|
| P1 | The BOUNDARY gap (Cor 3.3) is reproducible on a real suite: a function `a < b` with tests at $(1,2)$ and $(2,2)$ kills all five current mutants and the `!=` mutant survives | build the fixture (build item W1); if any current mutant survives on that suite, or `!=` dies, the corollary misdescribes the table |
| P2 | On Detective's README shipping example, $I_{\mathrm{ext}} = 0$: every survivor resolves by structure | run converge under D4; a non-empty teacher queue falsifies |
| P3 | On Detective's own repository, at least half of the survivors in the `masked` state are dead stores or branches no caller can reach, by hand classification | V3: classify every `masked` survivor; record the fraction |
| P4 | Ordering the teacher's queue by κ asks fewer questions per function than flat order on the dogfood set (`docs/dogfood/`) | V4: count questions to reach `COMPLETE` both ways on the same functions |
| P5 | $d$ on Detective's call-graph quotient is small relative to the number of adopted premises (bridges are rare) | V4: measure `d`; a `d` comparable to the adoption count falsifies the bounded-curvature framing for this code |
| P6 | The solver finds witnesses the grid misses: on functions whose infection formula is polynomial in ≥ 2 variables, at least one `candidate-equivalent` becomes `killer_ready` under D4 | V2: compare the survivor sets of converge with D4 on and off |

---

## 12. Status ledger

| Claim | Status | Basis |
|---|---|---|
| Thm 3.1 (per-site characterization) | DERIVED | the paper's Thm 3.2 and Prop 2.4 on $f_s$; not yet in Lean (a Lean target: instantiate `progComplete_characterization` at $f_s : D_s \to R_s$) |
| Cor 3.2 (Kaminski set from Thm 3.2) | CHECKED | `local_guards_check.py` check 1, exhaustive on the 3-region type |
| Cor 3.3 (Wesker BOUNDARY gap) | CHECKED against engine.py at 2fbd029; MEASURED on a suite pending (P1) | `local_guards_check.py` check 2 |
| Prop 3.4 (per-site ceiling) | DERIVED | Thm 4.5 on $f\vert_{D_s}$ |
| Def 2.2 / Prop 4.2 (three conditions) | PROVED, prior art | DeMillo & Offutt 1991; Just, Jalali & Ernst 2014 |
| Prop 4.3 (decidability rungs) | DERIVED | the paper's Thm 5.2 |
| Def 4.4 (solver) | DESIGN, precedent built elsewhere | TrialLedger `layer2/entail.py` |
| Prop 5.2 (the alphabet) | ASSERTED | the table is the object; its intent test is injectivity over remedies |
| Prop 6.1 (three resolvers) | PROVED/cited | NEGATIVE_SPECIFICATION Thm 6.2, Def 4.2, §9 |
| Def 6.3 (five numbers) | DESIGN; coverage analogs | SIGNIFICANCE_WEIGHTING §16.5's caveat applies |
| Prop 6.4 (agent not trusted below Σ±) | INTERPRETATION | of Thm 6.2; the Goodhart remark is a receipt-visibility claim, testable |
| Def 7.1 / Prop 7.2 / 7.3 (κ) | DERIVED from the definition; bound PROVED | `bridge_curvature_bound` (Lean, axiom-clean); $d$ on code UNMEASURED |
| Def 7.4 / Prop 7.5 (surprise) | DESIGN; null model ASSERTED | independence per execution is the stated null; measure before trusting |
| §8 table | INTERPRETATION | of the paper's §9 with state/raise in $R$; of NEGATIVE_SPECIFICATION Def 11.8 |
| §11 P1–P6 | CONJECTURE | each names its falsifier |

---

## 13. Open problems

1. **Lean for Thm 3.1.** Instantiate the existing `progComplete_characterization` at the local map; the
   realizability lemma for local values is the only new piece.
2. **The infection table for STMT/STATE.** Statement deletion's infection formula is opaque in general;
   the single-assignment case is decidable and should be the first slice.
3. **The null for surprise.** Independence per execution is the simplest null; a per-test null (tests
   reaching the site through the same path are not independent) is the honest refinement, and the
   bracket should widen to cover it.
4. **The regime key for premises** (NEGATIVE_SPECIFICATION §18 Q2): at what scope does a premise
   transport — the typed interface, the purity class, the module? A premise keyed too wide over-reaches
   exactly as a censor does.
5. **$d$ on code.** Measure before proving anything that depends on it (P5).
6. **The entropy-bit report.** Wire the H-series so $L_{\mathrm{ind}}$ is bits, not coverage; until then
   the report says "coverage analog" on every line that is one.

---

## Appendix A — the bundled checks

`docs/theory/knowability_ii/local_guards_check.py` — Cor 3.2 and Cor 3.3, exhaustive, no dependencies,
exit 0 iff both hold. A copy lives in Wesker at `docs/local_guards_check.py` and a Wesker intent test
pins check 2 against the live `_BoundaryMutator` table (build item 0.2), so a change to the table that
closes or reopens the gap fails loudly.

## Appendix B — where this document's ideas came from

The three-condition model and the local theorem came from reading the paper's Prop 7.2 against Wesker's
operator table. The three resolvers and the collapse of $\mathrm{DOF}^{0}$ are NEGATIVE_SPECIFICATION's,
and were missing from the first draft of the alphabet, which routed them to the teacher. The idea that an
open item has a computable information state before it is resolved — and that its graph is induced by
the solver rather than chosen — is TrialLedger's design and SIGNIFICANCE_WEIGHTING's theory, applied to
code. The BOUNDARY gap was found by running the paper's theorem on the engine's own table; it is the
first thing the build fixes because it is the one claim here that is already checked.
