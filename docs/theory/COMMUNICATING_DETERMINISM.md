---
title: "Communicating Determinism"
subtitle: "The command surface as an information channel with its own correctness criterion"
author: "Rohan Vinaik"
date: "2026-09-09"
status: "draft — written from the implemented surface and its recorded failures; no formal mechanization is claimed"
provenance: >
  Companion to three papers: the adequacy-completeness paper (operator_completeness/), the
  negative-specification paper (NEGATIVE_SPECIFICATION.md), and the effect/meaning paper
  (mechanical_layer/MECHANICAL_LAYER.md). Those three establish what can be measured and where
  measurement stops. This one concerns what happens after: the fact is established and must now
  produce a correct belief in a reader who has a prior. MECHANICAL_LAYER §7 records four commitments
  of the command surface as evidence FOR its theory; this paper takes the surface as its subject.
  Every claim below is grounded in an implemented decision or a recorded defect, cited by name.
---

# Communicating Determinism

## The command surface as an information channel with its own correctness criterion

### Abstract

A measurement establishes a fact. The fact underdetermines the belief it produces in a reader,
because the reader arrives with a prior. A tool may therefore measure correctly and still cause a
false belief, and that failure is invisible at the measurement layer — it breaks no build, fails no
test, and moves no number. We treat the command surface as a second channel with its own
correctness criterion, and state the requirement that criterion imposes: the encoding from
epistemic state to emitted sign must be **injective**. Two states whose remedies differ must not
share a signifier. Where injectivity fails, information correctly measured is destroyed at the
interface, and nothing downstream can recover it or detect the loss. We catalogue eight such
collisions found in one implementation, each repaired by splitting a sign rather than by improving
a measurement. We then describe three further requirements the same frame produces: an alphabet
containing symbols for what was *not* established; a forward channel whose payload is a claim about
a counterfactual future invocation, with a ledger as its return path; and a decoding rule for
advisory signals in which agreement across independent lossy lenses resolves a signal none carries
alone, with absence of signal never counted as evidence against.

---

## 1. Silence

Code differs from software in that it is naturally silent. It does what you ask it to do as a
statement of truth, not design. Booleans check truth. Mathematical operators do math. Build them and
run them and you inherently get nothing, really — just an empty line on your screen, and the fact
that electrons followed a pattern shaped by logic.

Everything a program says is a separate artifact somebody built. For most software that artifact
reports state: did it run, and what came back. Write a boolean and it prints `True`. Do arithmetic
and it prints the answer. Combine enough of them and you want to know which ones ran. That is
essentially the whole job, and it is a projection — the machine's condition, rendered into text.

The tool this paper concerns cannot do that, because its subject is not a value. Its subject is what
is *known* about a value, and the difference between knowing and having failed to look.

## 2. The instrument

The Dwemer Oculory is a machine for reading what cannot be read directly. Light enters, passes
through an array of lenses and a focusing crystal, and projects a single encoded artifact onto a
dome: one time, one space, one slice of reality per viewing. The truth it draws from is not made
legible. It is stepped down, once, into the mundane.

That is the job. The divine truth — what a program *is for* — is unknowable, and the companion
papers prove it is unknowable rather than merely hard (Prop. 3.3; NEG_SPEC Thm 6.2). The
measurement is undecipherable on its own: a mutation profile is a list of survivors and kills. The
surface takes it one layer lower.

The machine also carries its own warning. The Dwemer are gone, their mechanisms work, and nobody
knows why. A maintainer meeting `--red` cannot recover from the code why the flag is not
`--process`; the reasoning is a judgement about how a reader's confidence forms, and judgements do
not survive in source. §10 exists because of that.

## 3. The encoding requirement

Let a run establish a fact $F$ about a function. A reader receives a message $R$ and arrives with a
prior $P$. The tool's obligation is not that $R$ is true. It is that the reader's posterior is
correct — *including* correct about what $F$ did not establish.

$P$ is not observable, so the requirement has to be discharged by the encoding rather than by
adaptation to the reader. The load-bearing constraint is one property:

> **The map from epistemic state to emitted sign must be injective. Two states whose remedies
> differ must not share a signifier.**

Where injectivity fails, the loss happens *after* correct measurement and cannot be detected
downstream: the reader receives a well-formed message, forms a definite belief, and acts. Nothing
raises. The engine's answer was right the whole time.

This is the project's own rule — *two conditions that mean different things must not collapse into
one truthy check* — stated as a coding requirement rather than a style preference. Restating it that
way makes it checkable, and makes its failures a single family rather than a series of unrelated
bugs.

### 3.1 Eight collisions

Each row is a state pair that shared a signifier in the implementation, the remedies that differ,
and the repair. Every repair splits a sign. None improves a measurement.

| Shared signifier | States it merged | Remedies |
|---|---|---|
| `0 pinned`, "⚠ NO tests" | tests are weak · **the module never imported** | write tests · fix the interpreter |
| exit `2` (verify-rewrite) | `INVALID_RECEIPT` · `STALE_RECEIPT` · `BASIS_MOVED` | three different receipts to regenerate |
| exit `3` (decompose) | `proof_cut` · `preservation_unproven` | re-run · **supply the residual `--input`** |
| `state` dict equality | content changed · content unknown | report a spiral · stay silent |
| "not served from the cache" | nothing was stored · regime unobservable | two unrelated causes |
| "Built: `state_basis`" | the decision exists · the escalation happens | nothing · wire it |
| `read_behavior_status` | `unpinned` · `ungateable` (§MI) | converge · **converge cannot help** |
| a green suite | measured no gap · could not measure | ship · do not ship |

The last row is the whole project in one line, and the first seven are that line recurring at
smaller scale. The first row is worth stating fully because its shape is the clearest: `diagnose`
reported a correct count, attributed it to absent tests, and routed the reader to `converge` — which
on the same target exits 3 naming a missing dependency. The number was right. The cause was
invented. A reader beginning at the entry-point verb was sent to write tests for a module no test
could run.

A false cause is worse than silence. Silence leaves the prior intact; a false cause replaces it with
a confident wrong one, and the reader spends real effort moving away from the fix.

### 3.2 Injectivity is checkable, and was not being checked

The repairs above were found one at a time, over two days, each by driving a real command rather
than by any test going red. That is the expected yield: an injective-encoding failure produces
green suites by construction, because the tests assert the message that is emitted, not the
distinction that was lost.

Two questions decide the property and both are decidable over the reference graph:

1. **Is every decision consumed?** A pinned decision with no production caller emits nothing, so its
   distinctions never reach the surface. Measured on this implementation: **161 declared decisions,
   7 unconsumed**, each now carrying a written reason naming what does consume it — five research
   instruments driven by `dev/` harnesses, one redundant by construction, one the guard's own
   decision. Three more were unconsumed when the sweep first ran. `ledger.state_basis` was
   ✓ COMPLETE 11/11, exported, documented, tested, and had no caller for a full development wave, so
   the ruling it implemented could never fire. `converge.reproducibility_verdict` was pinned and its
   intent guard asserted a property against a function production never called — the live expression
   three lines away was unguarded. The third was a duplicate of a decision another repository
   already owned, produced the data for, and consumed.

   The declaration predicate itself had to be corrected mid-sweep, which is the same defect one
   level up: `"pure" in docstring` matches **"impure"**, and the house convention for extracting a
   decision says *place it beside the impure function it serves*. Seven false positives, one of them
   carried in a hand-written finding list.
2. **Does every consumer distinguish all of a decision's states?** `certify._TERMINAL_STANDINGS`
   admitted three of the five codes `certificate_standing` produces; the other two fell through into
   codes meaning *absence*. The anti-drift test written to catch exactly that drift called the
   function with five of its six arguments, comparing two surfaces over precisely the subspace where
   they cannot disagree.

The second question is unbuilt. The first is now a standing guard, and it takes a *reason* rather
than a name: an exemption must state what does consume the decision, because a bare allow-list is
indistinguishable from a hiding place.

## 4. Symbols for what was not established

An alphabet adequate to this channel must contain signs for the tool's own failure to know. Not a
degraded value — a distinct symbol, whose remedy is different and sometimes empty.

- **Exit codes are epistemics, not pass/fail.** `0` clean · `1` a measured gap or a typed refusal ·
  `2` the world is wrong, fix that and not the code · `3` the measurement cannot be trusted, re-run.
  Measured against a module that will not import: `converge` 3, `audit --check` 1, bare `audit` 0,
  `diagnose` 0 — with the rule underneath that a verb may exit 0 **only because it names the
  cause**. Silence plus zero is the state that sent an operator to author inputs for a module that
  could not import.
- **`measurement_invalid`** — the one status whose remedy is nothing. It is deliberately excluded
  from `plan._STATUS_REASONS` so `next_move` returns `""`, because the alternative had a loop in it:
  a certificate recording an invalid measurement was read as *no certificate*, which prescribed the
  `converge` that produced the invalid measurement.
- **Absence distinguished from emptiness, three times.** `nothing_to_read` is not `clear`;
  `cause_below` is not silence; `ledger_available` is not `spiral == "no_prior"`. In each case one
  member says *we did not look* and the other says *we looked and there is nothing there*.
- **Refusal as output.** A verdict measured against the wrong file is not reported with a caveat. It
  is refused, with the fix printed. The refusal is the product of that run.

The cost of this alphabet is that most of it is never used. A surface with signs for its own
blindness spends most of its life not needing them, which is exactly why they erode: they look like
dead branches to anyone counting.

## 5. The forward channel, and its return path

The `DO THIS` block is not a projection of state. It is a claim about a **counterfactual future
invocation**: there exists a next command whose execution would change what is known, and it is this
one. It is conditional on the specific way this run fell short — `close_the_gap` when behaviours
have no test pinning them, `fix_load` when nothing downstream helps until an import works,
`settled` when there is no next action at all.

The run that emits it will not exist when the action is taken. It is a message to a successor
process, and for most of this tool's life the only continuity was the operator: each invocation
spoke forward and no invocation could hear itself. A command could emit `fix_load` a hundred times
and never know it had said anything before.

The invocation ledger closes that loop. With the named outcome recorded per run, the process axis
can say *"you ran `audit motion.py::sync_step` again with nothing changed and got `fix_load` each
time"* — a report not about the operator's repetition but about **the failure of the surface's own
prior utterances to land**.

`outcome` is recorded only where it carries what the exit code cannot. The criterion is the §3
requirement applied to a stored field: record the ending where the map from ending to exit code is
**not injective**, and where the verb issues an instruction a reader would repeat. Three verbs meet
it — `verify-rewrite` (7 verdicts over 4 codes), `decompose` (6 endings over 3, two of which share
exit 3 with opposite remedies), `regime` (every conflict kind over one code). Eight do not, and the
reason is recorded rather than the absence.

## 6. Two surfaces, two criteria

The same verdict is rendered twice, differently, on purpose:

> The CLI's rendering is a **theorem**: every clause as true as the engine can make it. The MCP
> surface's output is a **prompt**: correctness is whether it is *effective*, not whether it is
> true, and it deliberately says things the CLI would not. Both objects are right; they answer to
> different criteria. *(ARCHITECTURE §5a)*

This is not a concession to a weaker reader. It follows from §3: the obligation is a correct
posterior, the prior differs between readers, and where the priors differ enough the message must.

The MCP surface withholds the score, because a ratio is the most reliable way to make a model caller
reach outside the tool and grind. It shows the mutant *kinds*, because too terse and the task reads
as scut work to shortcut. It offers one imperative and never a menu — not because the epistemics are
unambiguous (the equivalents fork is undecidable) but because the caller's legal move set is
singular even when the epistemics are not. It exposes no `flag` tool, because flagging is a human
oracle on an undecidable question, and no `purge` tool, because handing a delete-state button to a
grinding caller invites *the number didn't move, purge and retry*.

And it carries flat prohibitions — *"more passes will not help"* — which **strictly overclaim**, and
are the load-bearing sentences.

That last one is the paper's most uncomfortable sentence and it is deliberate. A surface whose
entire subject is not asserting more than was established contains, at one seam, an assertion
stronger than the evidence — because a hedged prohibition is not a prohibition, and the failure it
prevents is a caller grinding against a wall the tool has already measured. It is recorded here so
that its removal is a decision rather than a tidy-up.

## 7. Decoding by interference

The advisory half faces the mirror problem. Cohesion, the right abstraction, the behaviourally
overloaded function: these are not provable, and mutation testing has no opinion on them. The
temptation is a score.

A hand-tuned weighted sum of non-commensurable axes is broken, and both prior attempts in this
lineage are written post-mortems of that same failure. The surface does not build one. It reads
seven lenses — complexity, purity, interface width, structural seam, regime, behavioural overload,
cohesion — projects each to a ternary vote, and reports a smell only where **at least two
independent lenses agree**. One lens is necessary and never sufficient. Thresholding to
$\{-1, 0, +1\}$ erases the incommensurable magnitudes before anything is compared.

Two properties make this a decoding rule rather than a heuristic.

**The informational zero.** A lens with nothing to say votes $0$, never $-1$. Cleanliness on axis A
is not evidence against fixing axis B; opposition requires a warrant, and only an authored censor
carries one. A lens whose input was never measured also votes $0$ — *we did not measure this* and
*we measured it and it is clean* must never render identically.

**Agreement is the warrant, and its absence is a named state.** Exactly one supporting lens returns
`AMBIGUOUS`, which escalates to the driver. That is not a failure mode; it is where taste lives, at
the automation boundary the companion paper proves exists.

This is the §3 requirement again, on evidence rather than on proof. There, *measured no gap* must
not share a sign with *could not measure*. Here, *this lens is clean* must not share a sign with
*this lens objects*. One law, run twice.

## 8. The reader is inside the channel

If the obligation is a correct posterior, the reader's failure modes are design inputs, and some of
them are specific enough to engineer against.

The clearest case is a naming decision that looks cosmetic. The axes are `--green`, `--red`,
`--yellow`, and the obvious improvement is `--setup`, `--process`, `--taste`. The rename is refused,
and the reasoning is about how confidence forms rather than how words read.

Nobody playing the game the names come from reasons through what each herb does. They remember that
the combination is the goal and that green is the one you eat in an emergency. It is a heuristic — a
spot in your head, reached for by habit under pressure — and that is how a human uses a diagnostic
tool. The naming refuses to flatter the pretence otherwise.

For a language model the argument is sharper. A flag named `--process` carries a semantic handle: the
token *means* something, so reaching for it feels like reasoning, and the reach is indistinguishable
from a guess. `--red` offers nothing to grab. A model that calls `--red` without the actual
purposive context has done something that reads as an absurd choice — visibly, to itself and to a
reviewer. **A token that carries no meaning cannot lend borrowed meaning to a guess.**

That is an anti-affordance, and it is the one design decision in this surface that is entirely
invisible in the code it governs.

The same modelling produces the rest. The per-command signpost exists because the reader in the
failure state is by definition the one who does not know what is wrong, and therefore never thinks
to run the diagnostic. A pre-empted command **withholds** its verdict rather than printing it under
a warning, because a warning a reader may act past is not a pre-emption. And the operator axis
exists at all because a tool that cannot be measured wrongly can still be *used* wrongly, and the
residual failure mode of a correct instrument is a human or a model holding a partial model of it
and acting on the gap.

## 9. Invariants a reviewer checks

Stated as checks rather than principles, because a principle survives review and a check does not
have to be argued.

1. **No new bool where two states differ in remedy.** A decision returns named codes, and the codes
   are exhaustive over the state space it claims to cover.
2. **Every declared decision has a production consumer, or a written reason naming what consumes
   it.** An empty reason is not an exemption.
3. **Every consumer distinguishes all of a decision's codes**, or names the ones it deliberately
   collapses and why.
4. **A verb exits 0 only if it names the cause** of anything it could not establish.
5. **Absence and emptiness never render identically** — at any layer, including a document's own
   status vocabulary.
6. **No weighted sum over non-commensurable axes.** Fusion is agreement-count over ternary votes.
7. **An unmeasured input votes zero**, and no `getattr(obj, name, default)` stands where a renamed
   field could be absorbed into a silent clean verdict.
8. **One derivation, N renderers.** A second reading of the same facts is drift with a delay fuse.

## 10. What will look like an improvement

Every property this paper describes reads as a defect to a competent reviewer meeting it fresh. The
list is the point of writing any of this down.

| Will be proposed | Why it is refused |
|---|---|
| Rename `--green/--red/--yellow` to `--setup/--process/--taste` | §8. The opacity is the feature, and the rename destroys it while looking like kindness. |
| Collapse the four exit codes to pass/fail | §4. The distinctions are the payload; CI branches on them. |
| Return a single quality score | §7. A weighted sum of incommensurables is how code-quality scores lie. |
| Soften the flat prohibitions to hedges | §6. A hedged prohibition is not a prohibition. This one is a deliberate overclaim. |
| Print the pre-empted verdict under a warning | §8. A warning a reader can act past is not a pre-emption. |
| Trim the "verbose" next-action blocks | §3. Loudness is redundancy against a wrong prior; the terse form transmits nothing to the reader who needs it. |
| Reduce the named codes to booleans | §3. Every collision in §3.1 was produced this way. |
| Give the model caller the score, the `flag` tool, or `purge` | §6. Each is an instrument for grinding. |

The surface is roughly a quarter of the implementation. That is not overhead. The meaning space is
the product of the epistemic states, the channels each must reach — terse, full report, `--json`,
MCP, certificate, ledger — and the reader models each channel serves. Every cell must cohere with
every other, and the recorded failure is exactly a cell that did not: one shared route, three
renderers, and only one of them wired.

## 11. Scope and open problems

What is claimed: that injectivity over epistemic states is a requirement rather than a preference,
that its violations form one family, that eight instances were found and repaired by splitting
signs, and that the same requirement produces the alphabet of §4, the criterion of §5, the two
criteria of §6 and the decoding rule of §7.

What is not claimed: any formal result. There is no mechanization here and no measurement of a
posterior. The reader model is asserted from observed failures, not sampled; the claim that a
semantic handle raises a model's false-confidence rate is a design hypothesis supported by observed
behaviour and not an experiment. §3's requirement is stated over a state space the implementation
defines, and a proof that the space is complete would be a different paper.

Open:

- **The second decidable question of §3.2 is unbuilt.** Whether every consumer distinguishes all of
  a decision's codes is checkable over the reference graph; nothing checks it. §MI and the #60 drift
  are both instances, and both were found by hand.
- **The guard of §3.2(1) covers functions and not fields.** A computed *field* with no consumer is
  invisible to it — `capability_flags` carried `approximate:mutant_universe` for a full wave and was
  read only by tests, so a label the tool had computed about its own count reached no reader.
- **Serialization by reflection defeats reference analysis.** `asdict` and `to_json` never name the
  field they emit, so a field can reach a machine consumer while appearing unconsumed, and the
  reverse. The blind spot is the same one dynamic attribute access has.
- **Nothing pins a sentence.** A decision can be pinned mutation-complete; a rendering cannot. The
  correctness of this channel is established only by a person reading it and noticing — which is
  the boundary theorem, landing on the tool's own surface. It is the one component of this system
  whose correctness is not mechanizable, and it is the component this paper is about.
