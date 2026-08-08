# The theory librarian — negative specification, stage by stage

**Scope.** This file is the map for the **negative-specification** work: for each
stage, (a) what it does and where it will live, (b) the **theoretical
commitment** — the specific claim that explains why it is built this way and not
the obvious way, (c) a sketch of the idea, (d) the deeper reading.

`ARCHITECTURE.md` is the operational map for what **exists today**; this file is
the map for what is **designed and unbuilt**. Where they disagree, ARCHITECTURE
wins on present behaviour and this file wins on intent — and the disagreement is
a bug in this file.

**The commitments are not decoration.** Several are enforced by the existing
proof gate; the ones that get violated are the ones that turn a specification
tool into a confident liar, which is the failure this whole project exists to
refuse.

**Verify the corpus this cites:** `python docs/theory/check_reference_manifest.py`
Priors are hashed, not copied, so a prior changing under a claim fails loudly.
Load-bearing external citations are marked `verified: false` — recalled, not
looked up. They gate publication, not the build.

**Entry point for the whole theory:** `docs/theory/NEGATIVE_SPECIFICATION.md`.
**Handoff artifact (carry verbatim into any summary):** `docs/theory/CONSTRAINT_BLOCK.md`.

---

## The frame: the kill-set is already negative; the enumeration is not

**Commitment:** σ is proved equal to a teaching dimension over **labeled**
examples (SC Thm 2.7), and σ is **parameterized by the mutation policy**
(SC §2.3). A policy enumerating only program space therefore specifies one sign
of a two-sign teaching set — so the object is **σ(P, μ ∪ μ⁻)**, a second policy
instantiation, not a new theory.
**Sketch:** every killed mutant is already an exclusion, so the *content* is
negative today. What has one sign is the authoring surface and the enumeration:
nothing ranges over output space, and nothing accepts "no correct implementation
does this."
**Read:** `specification_complexity_paper.md` §2.3, Thm 2.7 ·
`NEGATIVE_SPECIFICATION.md` §2 · Goldman–Kearns 1995 (`verified: false`).

## The historical claim — Winston's second operator

**Commitment:** the near-miss is not an enhancement, it is the half of the 1970
learner that **specializes** a concept by the example that just fails. Testing
inherited generalization and dropped specialization — not by argument, but
because test-as-example had no slot for the second sign.
**Sketch:** a positive example widens the concept; a near-miss (a non-example
differing in exactly one crucial respect) installs a MUST-NOT link. Both
operators, or the concept is unbounded above.
**Read:** Winston 1970 (`verified: false`; PDFs of the later Winston work are
bundled in the ARC corpus) · `law_as_architecture.md` §7 ·
`SSL_PAPER_SKELETON.md` §3.1 — negative learning **defined** · Genesis IV-F/IV-G
(SSL §7.3) — censor-without-retraction and withdraw-on-*does-not*, **running**.

## μ⁻ — output perturbation (Wesker; buildable now)

**What:** a mutation operator on the **codomain**. Wrap the target, return a
perturbed value, re-run the covering tests; green means that output dimension is
unpinned.
**Commitment:** it is **indifferent to syntax**, which is the entire point — it
reaches behaviour no operator over program text can express. It is an operator,
so it lives in the engine and carries an operator's status: it may gate, and it
extends μ rather than sitting beside it.
**Sketch:** the kill matrix gains rows keyed by *perturbation* instead of by
*mutant*. Everything downstream — minimal cover, the trace, the certificate —
reuses machinery that already exists.
**Read:** `NEGATIVE_SPECIFICATION.md` §§2.4, 3 · Appendix A (the definition) ·
`ARCHITECTURE.md` §0 (the value-vs-run boundary μ⁻ must respect).

## Censors — population-derived exclusions (Detective; blocked)

**What:** a learned artifact — "no correct implementation does X" — derived from
observed near-misses across **call sites**, not from the function alone.
**Commitment:** a censor is `I_ind` — information latent in the corpus and
unreachable per read. *"No caller ever passes `None`"* is not derivable from the
function; it is derivable from the population, and it is invisible to any single
read. This is why censors need judgement and governance where μ⁻ does not, and
why they live in Detective rather than the engine.
**Sketch:** the absence in the observed distribution IS the datum — SSL's **H6**
("a distorted or absent expected signal is itself a signal"), which is
`law_as_architecture` §7's title made literal: *forbidding what no real instance
does*.
**Read:** `SIGNIFICANCE_WEIGHTING.md` §12 (the three-region split) ·
`law_as_architecture.md` §7 · `SSL_PAPER_SKELETON.md` §3.1 ·
`NEGATIVE_SPECIFICATION.md` §4.

## The three-region completeness map — and the one-function law

**What:** `I_solve = I_ind + I_ext`. Detective already reports `L` ("% resolved
by structure for free") and `I_solve` by name; the middle region is uncomputed.
**Commitment:** `I_ind` is **co-occurrence over call sites**, NOT an aggregate of
per-function mutation scores. `ARCHITECTURE.md` §11 forbids the statistical smear
(and removed `diagnose --learn` for being one); this is a different object, and
the distinction is the entire license. The proof stays one function at a time;
only the censor's *derivation* reads the population.
**Sketch:** three regions — structure resolves it free / the corpus can teach
itself / a human must tell us — and Detective currently reports the second as
though it were the third.
**Read:** `SSL_PAPER_SKELETON.md` §§1.4c, 2.5 · `SIGNIFICANCE_WEIGHTING.md` §12 ·
`ARCHITECTURE.md` §11 · `NEGATIVE_SPECIFICATION.md` §4.1.

## Governance — admissibility, and why the guard is load-bearing on the MATH

**What:** adopt a censor only if **(i)** it is spine-sourced — carved from an
observed near-miss, never authored a priori, structurally incapable of
confirmation from derived output — **and (ii)** σ(P | C ∪ {c}) > 0.
**Commitment:** *"Without the guard, the extension's central quantity is not
merely unsafe; it is undefined."* A censor confirmed from the engine's own
derivations reduces the residual by construction while carrying zero information:
`L_ind → 1` vacuously. Over-censoring is the **degenerate controller from the
other side** — forbid enough and one program survives, σ collapses, EIG = 0. So
the objection "negatives introduce false refusal" names a mode that is already
detected and already machine-checked.
**Sketch:** `flag`'s governance with the sign reversed. `flag` is a positive-space
oracle outranked by a distinguishing input; a censor is a negative-space oracle
outranked by a wanted behaviour that violates it. `UNVERIFIED` is never promoted
to `forbidden`, exactly as `candidate-equivalent — UNPROVEN` is never promoted to
`equivalent`.
**Read:** `SIGNIFICANCE_WEIGHTING.md` §14 · `SSL_PAPER_SKELETON.md` §§4.3, 4.4 ·
`self_confirming_cannot_certify`, `falsifiability_pivot` (machine-checked,
v4.28) · `NEGATIVE_SPECIFICATION.md` §5.

## ★ The bridge crux — γ = d = bridge count

**What:** the real obstacle. Coverage is submodular over a **fixed** ground
structure; where adopting a constraint changes the graph coverage is read from,
submodularity is violated — constructively, and at exactly the valuable cases.
**Commitment:** *the interesting cases are precisely the ones that violate
submodularity.* A theory that assumed submodularity would be a theory of the
boring cases. And three quantities are one: **γ** (composition gap, bounded by
interface mutants, SC Thm 3.15), **d** (supermodular degree, Feige–Izsak), and
the bridge count. So Detective #16 is the code-side instance of this crux, and
measuring interface obligations *is* measuring d.
**Sketch:** a bridge joining two disjoint clusters has small marginal gain alone
and large gain once another is present — gains are **super**-additive. Target
theorem: bounded-curvature greedy, degrading in d, recovering (1−1/e) at d = 0.
**Do not** cite SSL's constants (`L=0.528`, the ~3 % knee, the 28× drop) for
code: they were measured on a **dense** graph and a code obligation graph is
likely sparse. Measure d first.
**Read:** `SIGNIFICANCE_WEIGHTING.md` §13 · `specification_complexity_paper.md`
Thm 3.15 · `NEGATIVE_SPECIFICATION.md` §6 · Feige–Izsak, Golovin–Krause
(both `verified: false`).

## κ-gated removal — the fix this theory already implies

**What:** `audit --remove` currently proposes deleting a test that is line- and
mutant-redundant **for this function**. Field-observed failure: the test was
load-bearing elsewhere.
**Commitment:** that is the bridge counterexample — near-zero marginal gain
inside one kill-profile, large gain over the closure. The correct invariant is
**significance-weighted** coverage, not local coverage: *a test is safe to remove
iff it banks zero κ-weighted coverage over the closure.* Both supporting
theorems are already machine-checked upstream — representation independence
(SC Thm 2.3) and redundant ⟺ zero information gain (SC Thm 3.11).
**Sketch:** §17 already names `decompose --apply` as the same operator run
forward on code, so the symmetry is recognized in the corpus; this is that
operator's removal half, gated correctly.
**Read:** `SIGNIFICANCE_WEIGHTING.md` §17 · `NEGATIVE_SPECIFICATION.md` §7.1 ·
Detective #54.

## The observing set belongs on the certificate

**What:** a structural rewrite outside μ passed a `✓ COMPLETE` badge (measured,
§2.4). The badge is honestly scoped; the scope is in a parenthetical.
**Commitment:** completeness is relative to the substrate, **and that is the
feature, not the flaw** — so the certificate should NAME its context set rather
than only report a ratio. A receipt that states its own boundary is self-limiting
in writing instead of in a footnote.
**Sketch:** the code-side form of SSL §1.4c's field/artifact distinction: claim
the artifact, name the field.
**Read:** `SSL_PAPER_SKELETON.md` §1.4c · `NEGATIVE_SPECIFICATION.md` §§2.4, 7.2.

## The empirical grounding — measured, not argued

**What:** two results from the cold-start review of Detective 0.11.0 (2026-08-07)
that the whole theory document rests on rather than reasons toward.
**Commitment:** the boundary is **demonstrated**, not inferred — a behaviour-
changing structural rewrite passes a COMPLETE contract on `slugify`, and the
"degenerate" integer near-miss witnesses beat hand-written tests on plausible
refactors (catching the str→bytes API break on a function with zero shipped
tests). The second result is *predicted* by teaching theory: teaching dimension
is defined by a teacher minimizing identification cost, not by sampling a natural
distribution, so grading a witness by "would a person write this" applies
learner-intuition to a teaching artifact.
**Sketch:** every model review of this tool has raised the degenerate-witness
objection. The objection is predicted by the framework the tool implements.
Recorded because it will recur.
**Read:** `NEGATIVE_SPECIFICATION.md` §§2.4, 2.5 · Goldman–Kearns 1995
(`verified: false`).

## The generative intuition — staged error correction without a controller

**What:** the biochemical framing that motivated the design, recorded because it
predicts the architecture rather than merely decorating it.
**Commitment:** DNA fidelity is not one accurate step; it is base selection,
proofreading exonuclease, and mismatch repair composed — each cheap and
individually mediocre. The information needed to repair lives **redundantly in
the representation** (the complementary strand IS the backup), not in a
controller that knows what the sequence means, and it is inborn rather than
derived. **Two channels over one message let you correct; one only lets you
detect.** Use **Landauer** for the thermodynamics — local entropy decrease is a
demon paying its bill, not a violation. The "violates entropy" framing is
attackable and unnecessary.
**Sketch:** μ⁻ is proofreading (cheap, at synthesis, catches the bulk, fails open
to the expensive stage); the mutation proof is mismatch repair (post-hoc, uses
the existing suite as template).
**Read:** `NEGATIVE_SPECIFICATION.md` Provenance · Landauer 1961
(`verified: false`) · `SIGNIFICANCE_WEIGHTING.md` §17.1 (Crick–Mitchison
reverse-learning made rigorous — the same σ run backwards).

---

## Open questions, in the order they block the build

1. **What is κ for code?** GSE uses genealogy PageRank over the IS-A graph. The
   code analogue needs a graph — call graph, import graph, or the obligation graph
   induced by interface mutants — and the choice decides whether `I_ind` is cheap
   or a research project. **Blocks censors AND κ-gated removal.**
2. **What is the regime key?** Regime = symmetry (T6.15); a censor keyed below the
   semantic-equivalence class over-reaches (traps positions that merely *rhyme*,
   `law_as_architecture` §8), keyed above it under-reaches. Working guess: typed
   interface + purity class. Wants a derivation.
3. **Does μ⁻ need its own equivalence notion?** Two perturbations can be
   indistinguishable for the same reasons two mutants can — and TCE-style bytecode
   identity (Wesker #24) does **not** apply, since there is no mutant program to
   compile.
4. **Ordering.** μ⁻ is buildable now and independent of κ. Censors are blocked on
   (1) and (2). The correctness/retooling work in both repos precedes all of it.
