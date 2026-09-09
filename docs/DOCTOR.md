# `detective doctor` — design

> **Open items live in [`OPEN_ITEMS.md`](OPEN_ITEMS.md), not here.** This document was written to
> GUIDE work that has since landed, so it is anti-correlated with current truth wherever it
> describes a defect. Ground against current source before acting on anything in it.

Status: BUILDING. Written 2026-09-08; founder rulings and grounding corrections 2026-09-09.
Built so far: the precedence lattice (`doctor.signpost_disposition`, ✓ COMPLETE 24/28), the GREEN
axis (`setup_disposition`, ✓ COMPLETE 15/15, plus its gathering layer), the **YELLOW** axis
(`taste_disposition`, ✓ COMPLETE 47/47, consuming `survey_source`), the **`detective doctor` verb**,
and the first superadditive product (**G+Y ordered remediation**). RED reports `not read` WITH its
reason rather than an empty section. Exit 2 on a live setup fault, 0 otherwise.
the **per-command signpost** on the static taste verbs, and — as of 2026-09-09 — **RED** and all
four **superadditive products**. Doctor is COMPLETE as designed.
Open, and named rather than deferred: §11's strict-preemption question, propagation for the verbs
that still record `outcome: []`, and `purge --prune`.

---

## 1. What it is, and the fence

Detective's guarantee is about measurement: it refuses rather than report a number measured
against the wrong file. Nothing in that guarantee reaches the operator. A tool that cannot be
measured wrongly can still be *used* wrongly, and the residual failure mode of the whole project
is an operator — human or model — holding a partial model of it and acting on the gap.

**Doctor is the founder's guiding hand, operationalised for when he is not at the terminal.**
Every line in the CLI of the form *"a score of 0 is not a problem with the tool — check X"* is a
fragment of it. Doctor is that, made systematic and reachable.

### The CLI is the literal; doctor is the shadow

The division is not "correctness vs. UX". It is sharper than that:

> **The CLI states what is literally true and measured. Doctor interrogates the PREMISE that
> true statement rests on, and asks whether it holds in the operator's full situation.**

The CLI must stay loud, literal and correctness-focused — that is its job and it does it well.
It says `ModuleNotFoundError: No module named 'funcy'`. Every word is true. What it cannot say,
because it is not a claim about the measurement, is that the premise a reader will infer from it
— *you do not have funcy* — is **false**: funcy is installed on this machine, under a different
interpreter. The operator does not have an installation problem. They have a propagation problem,
and every minute spent installing funcy again is spent moving away from the fix.

That gap — between a literally correct statement and its relevance to the situation the operator
is actually in — is doctor's entire subject. It is where the "obvious" fix lives, and "obvious"
is exactly what an operator holding a partial model cannot see.

### The fence (load-bearing, not a convention)

> **Doctor diagnoses the OPERATOR and the ENVIRONMENT. It never speaks about the code.**

It answers *"what is blocking correct use of this tool"*. It must never emit anything that reads
as a correctness verdict — no "your code is fine", no coverage claim, no completeness claim. The
moment it does, it has inherited exactly the measurement/verdict conflation the project exists to
kill, and it will be believed, because it is the command a confused user runs.

Consequences of the fence:
- **Advisory. Writes nothing.** Same class as `plan` / `survey` / `parsimony` / `censor`.
- **Never gates.** It is not a step in the correctness chain and cannot block a certificate.
- **Cheap.** Static reads and environment probes. It does not run the target's suite, does not
  profile mutants, and does not import the target to find out things. Anything behavioural
  belongs to the command that already owns it.

### The motivating case (observed live, 2026-09-08)

Mid-session the founder installed `jax` and `funcy` to unblock a test. They landed in
`~/miniconda3`. The interpreter Detective runs under is a project venv, which still lacks them.
**The packages exist on the machine and are invisible to the run.** The fix was performed and not
propagated, so the tool's report — correct in every particular — describes a state the operator
believes he has already left.

Following the tool literally at that moment leads away from the answer. Recovering requires an
inference the tool does not make and the operator has no reason to make: *the dependency exists,
somewhere else, under a different interpreter.* A user without the full model concludes the tool
is broken. This is U2 from the pabkit ledger — recorded there as *"the single biggest greenfield
stumble"* — reproduced by the author of the tool during the conversation about building the thing
that catches it.

That is doctor's job, and that case is its acceptance test.

---

## 2. The herbs

Resident Evil 4's set — green, red, yellow — and the mechanics are load-bearing, not a skin.
Green heals and is the only one that works alone. Red does nothing alone and turns green into a
*full* heal — it completes green's axis rather than adding one. Yellow does nothing alone and
raises **maximum** health — a different axis from healing damage. Any permutation combines, and
the mix is worth more than the sum.

| Herb | Axis | What it is | Alone? |
|---|---|---|---|
| **Green** | **setup** | present damage — the project or environment is malformed | yes, always meaningful |
| **Red** | **process** | the operator is doing something wrong, or in the wrong order | no — completes green |
| **Yellow** | **taste** | nothing is broken; something caps how much of Detective is reachable | no — raises the ceiling |

**Yellow is the mapping that earns the scheme.** Taste findings heal nothing — an entangled
function, an overly broad discovery, a pure decision trapped in an impure shell: none of that is
damage. What they do is cap how much of the tool is available to you. That is max health exactly.

### Why the herb names stay — the opacity is the feature (founder ruling, 2026-09-09)

The obvious usability move is to rename these `--setup` / `--process` / `--taste`, on the grounds
that a self-describing flag is kinder than a video-game reference. That move is wrong, and it is
wrong for a reason worth writing down, because it will look like an improvement to everyone who
meets it fresh.

**Nobody playing Resident Evil thinks through what each herb does.** They remember that the
combination is the goal, and that green is the one you can eat in an emergency. It is not
knowledge, it is a *heuristic* — a spot in your head, reached for by habit under pressure. That is
precisely how a human uses a diagnostic tool, and pretending otherwise is a pretension the naming
should refuse rather than flatter.

**And the opacity is a check on false confidence — especially for an LLM.** A flag named
`--process` invites a model to fire it by pattern-match: the token *means* something, so reaching
for it feels like reasoning, and the reach is indistinguishable from a guess. `--red` carries no
such affordance. An LLM that calls `--red` without the actual purposive context for why has done
something that reads as an utterly ridiculous choice — visibly, to itself and to a reviewer. The
token that carries no meaning cannot lend borrowed meaning to a guess.

So the herb names do double duty: a mnemonic for the human, and a deliberate absence of semantic
handle for the model. Both are the design. Neither survives the rename.

### GREEN — setup

Present damage. Actionable standalone.

- **Interpreter and dependencies.** Does the interpreter that will run Detective have pytest, and
  the target's own deps? **And — the motivating case — does the missing package exist under a
  *different* interpreter on this machine?** If so, say so and name both paths. This is the
  inference the operator cannot be expected to make.
- **Regime faults** — shadowed target, conftest collision, undeclared marker, layout. **Consumed
  from `regime`'s existing derivation, never re-derived** (see §5).
- **Target load** — the module will not import, with the underlying exception.
- **Collection** — test files that fail to collect, with their import errors.

### RED — process

Adds no new axis; completes green's. Knowing *what the operator was trying to do* turns "your venv
lacks funcy" into "…and that is why your converge reported 0 kills and asked you for inputs; fix
the import first, then re-run — do not author inputs."

- **Order** — the taste half run before behaviour is pinned; `decompose` before `converge`;
  `flag` before a witness search has run.
- **Spiral** — the same command issued again with no state change between runs and byte-identical
  output. This is directly detectable and is the single highest-value red signal.
- **Advice that cannot apply** — authoring inputs against a module that will not import.
- **Pinning an entangled function** before splitting it.
- **Reading a cached verdict as fresh.**

> **Open dependency (§7.1):** red needs an invocation ledger — what ran, in what order, with what
> arguments, and the outcome. It is not established that `.detective/` records one. If it does
> not, that is a new artifact and its own design decision, not an implementation detail.

### YELLOW — taste

Raises the ceiling. Never damage.

- **Overly broad test discovery** — the covering set inflating toward suite scale.
- **An entangled function** that should be split before it is pinned.
- **A pure decision trapped behind an impure boundary** — consumed from `survey`, not re-derived.
- **An inexpressible parameter** whose extraction would make the function pinnable.
- **Suite import warts** that make every run slower without making any run wrong.

---

## 3. Precedence, and what the mix buys

### Ranking

> **GREEN outranks RED outranks YELLOW.**

- A **green** fault invalidates red and yellow findings *measured through it*. Entanglement
  measured through a broken discovery is measuring the discovery.
- A **red** fault invalidates yellow findings that depend on a pin which does not exist.
- **Yellow invalidates nothing.** It only raises the ceiling.

### The superadditive products

This is the part that is a mechanism rather than a metaphor. Each combination yields a verdict
neither component produces alone:

| Mix | Verdict it produces that no single axis can |
|---|---|
| **G + R** | **suppression** — *"this process advice is void; that setup fault outranks it."* |
| **G + Y** | **unreliability** — *"this taste finding was measured through a broken environment; re-derive it after the fix."* |
| **R + Y** | **ordering** — *"you are about to do the taste half before the correctness half."* |
| **G + R + Y** | **ordered remediation** — fix green, then re-derive red and yellow, *because both were measured through the green fault.* |

The full mix is not three lists concatenated. It is three lists **plus the statement of which
findings must be re-derived after the repair, and in what order.** That is the boost above the
simple sum, and it is the reason the mix is the default.

**G + R is the general form of the converge spiral** recorded in `CORRECTNESS_REPAIRS_2026-09-08.md`
§3: converge emitted a red verdict (author these inputs) while a green fault (funcy absent) was
live and preemptive. Neither axis alone catches it. That is not a coincidence — it is why this
design should land before those renderers are wired.

### Partial reads

Faithful to the mechanic: `--red` / `--yellow` alone are runnable for scoping, and carry an
explicit banner that the read is partial and may be invalidated by an unread axis. **The default
is the full mix**, because making the operator discover the right combination is a puzzle, and a
puzzle in a diagnostic tool is the spiral this project bans (§4).

---

## 4. The CLI must carry it — the signpost

A repair system that is not obvious in turn-by-turn output is pointless: the user in the failure
state is, by definition, the user who does not know what is wrong, so they never run it.

This is Finding A's failure mode generalised. `decompose` existed all along, marked
`Next (optional)`; a greenfield user read "optional" and skipped it, and the ledger records the
founder himself skipping the style half on every ✓ COMPLETE for the same reason. Doctor is more
exposed to this than decompose was.

### The trigger is derived, not a heuristic

**Every command knows its own herb.**

| Herb | Commands |
|---|---|
| green | `regime` |
| red | `converge`, `audit`, `diagnose`, `receipt`, `verify-rewrite` |
| yellow | `plan`, `survey`, `extract`, `decompose`, `parsimony`, `censor` |

> **A command may emit its own verdict only when no higher-ranked herb has a live finding.
> Otherwise it names that finding and offers the full mix.**

As a pure decision, in house form — literal arguments, named string codes:

```
emission_disposition(command_herb, green_finding, red_finding, yellow_finding) -> str
    "emit"                  — no higher-ranked finding; the command speaks normally
    "preempted_by_setup"    — a green finding outranks; name it, do not emit this verdict
    "preempted_by_process"  — a red finding outranks (yellow commands only)
    "emit_with_note"        — may speak, but a lower-ranked finding is worth naming
```

Pinnable in isolation with `converge`, and it is the **one derivation** behind three surfaces:
doctor's combined report, the per-command signpost, and the load-failure routing repair. One
derivation, three renderers, never a re-derived narrower proxy — which is why the repairs should
consume *this*, not get `measurement_block_route` bolted on and rewired later.

### Signpost discipline

- **Never on a clean run.** A line that always appears is a line nobody reads.
- **Fires exactly when a cross-axis finding exists** — when the command cannot explain the
  situation with its own herb.
- **Names the finding, not the command.** "Run `detective doctor`" is as useless as
  "Next (optional)". It must say what doctor will tell them:

  > `your interpreter cannot import 'funcy' — that is why this run measured nothing.`
  > `'jax' and 'funcy' ARE installed under /Users/…/miniconda3/bin/python3, which is not this run's interpreter.`
  > `detective doctor   # the full setup / process / taste read`

- **The signpost is the one escape** — it satisfies the un-spiral-able rule rather than adding a
  second thing to try.

---

## 5. Relationship to `regime`

`regime` stays the entry point: it answers *how does this repo import its code and run its tests*,
and every command already resolves it first. Doctor answers a different question — *why can I not
proceed / what am I doing wrong.*

Green overlaps regime heavily but is strictly larger: per U2, regime explains the testing regime
and explicitly does **not** diagnose "you are in an interpreter without pytest / the project's
deps." That gap is the motivating case.

> **Doctor CONSUMES regime's derivation. It does not re-derive it.**

Same reason we are retiring `classification_ran = report is not None`: a second reader of the same
facts is a sibling that will drift from the first, which is the bug class this whole repair wave
exists to close.

---

## 6. What doctor is not

- Not a correctness verdict, in any form (§1).
- Not a gate. Never blocks a certificate, never appears in the completeness chain.
- Not a profiler. No mutants, no suite run, no target import to "find out".
- Not a fixer. It proposes and names; the operator acts. (Consistent with `survey` / `extract` /
  `plan` / `censor`. `regime --migrate` remains the one command that repairs, and only the part
  that is Detective's to repair.)
- Not a puzzle. The full mix is the default (§3).

---

## 7. Open questions — founder call

1. **The invocation ledger.** Red needs to know what ran, in what order, with what arguments and
   outcomes. Does `.detective/` record this today? If not: what is recorded, where, with what
   retention, and does an invocation ledger belong in a directory `purge` is documented to clear?
   (It is not cache — it is evidence — so it likely belongs with `inputs.json` /
   `equivalents.json` on the never-purged side.)
2. **Exit code.** Doctor is advisory, which argues for always 0. But a green finding is a
   precondition failure, and the documented table has `2 = a conflict / precondition`. Exiting 2
   would make doctor CI-usable as an environment preflight. These pull opposite ways; the fence in
   §1 says advisory, the utility says 2. Not decided here.
3. **The bound on the cross-interpreter probe.** "Does this package exist under another
   interpreter" must not become a filesystem sweep. Proposed bound: venvs at/near the project
   root, the interpreter on `PATH`, and any interpreter regime names. Not every Python on the
   machine.
4. **Yellow's cost.** Green and red are cheap (probe the interpreter; read the ledger). Yellow
   needs a static pass. Does the default mix run yellow every time, or does yellow degrade to
   "not read" with a named reason when the target is large? A "not read" state is honest and
   consistent with `plan`'s `regime — unread`.
5. ~~**Naming.**~~ **RULED 2026-09-09: the herbs ARE the user-facing vocabulary.**
   `--green` / `--red` / `--yellow`. The proposal to "clarify" them into
   `--setup` / `--process` / `--taste` was rejected, and the reasoning is load-bearing rather
   than aesthetic — see §2, *Why the herb names stay*. Do not re-open this as a usability
   improvement; the opacity is the feature.


---

## 8. Grounding corrections, 2026-09-09

Written when the build started, because this document predates R1–R4, S13, §MI and S14 and was
therefore partly fix-guiding — anti-correlated with current truth wherever it describes a defect
those repairs eliminated. Each item below was checked against current source before building.

### 8.1 `emission_disposition` was already taken

§4 proposes that name. `Detective/emission.py::emission_disposition` already exists — the
cross-language C-codegen gate, pinned, returning `PRESERVED_PORTABLE` / `VACUOUS` / `CHANGED` /
`INVALID_MEASUREMENT`. Unrelated in every respect except the name. **Built as
`doctor.signpost_disposition`**, which names the surface it drives.

### 8.2 The R3 worry does not apply

§4 argues D should land before R3 "which is why the repairs should consume *this*, not get
`measurement_block_route` bolted on and rewired later". R3 landed first, and on inspection there is
nothing to rewire: the two answer different questions. `measurement_block_route` picks WHICH block
route a measurement problem needs; the signpost decides WHETHER a command may speak at all given a
higher-ranked herb finding. Orthogonal. No absorption, no rework.

### 8.3 The three axes are in very different states — which sets the build order

| Axis | Consumption point | State at build time |
|---|---|---|
| **Yellow** | `survey.survey_disposition` → 4 finding codes + `reachable` | complete; pure consumption, no new machinery |
| **Green** | `regime.TestRegime.conflicts` → only `shadowed-target` / `conftest-collision` | thin; interpreter, deps, target load and collection are all NEW gathering — and that gap IS the motivating case (U2) |
| **Red** | four pinned dispositions in `Detective/ledger.py` | **no data**: `observe` has one production call site and `.detective/ledger.jsonl` does not exist |

So red is the expensive axis and is entirely blocked on the ledger's persistence shell, while green
is the motivating case and yellow is nearly free. Build order: **lattice + green + the verb →
yellow → ledger shell + red → the signpost.** This is slicing by AXIS, not building narrow and
widening: the lattice is built once, sized for all three, and each axis is complete when it lands.
It also matches the mechanic — green heals and works alone, yellow raises the ceiling, red does
nothing alone and completes green.

### 8.4 §MI made the stale-failure probe possible INSIDE the fence

§1 forbids importing the target to find out, and §2 nevertheless lists "Target load — the module
will not import" as a green finding. Those were in tension when this was written. They no longer
are: §MI added `cut_reasons` to the certificate ledger, so `target_load_failed` and
`collection_incomplete` are readable **from disk**, as facts a prior run recorded. Before that a
load failure was stored as a bare `ungateable` standing with no reason and this probe could not
have existed without breaking the fence. The capability and the fence arrived together, by accident.

### 8.5 The dependency probe, as built

The motivating case needs the missing module NAME, which no recorded reason carries. Resolved
statically and inside the fence: AST the target's top-level imports (`target_imports`), keep only
the first dotted segment — `find_spec` on a dotted name imports the parent packages to locate the
child, which executes code — drop stdlib and relative imports, then ask `find_spec` here
(`missing_here`) and one bounded subprocess per candidate interpreter for the rest
(`found_elsewhere`). Verified on the real machine, 2026-09-09: `funcy` and `jax` absent from the
project venv, both found under `~/miniconda3`, `definitely_not_a_real_package_xyz` found nowhere —
`setup_disposition` → `deps_elsewhere`. That is §1's acceptance test, passing.


---

## 9. The verb, as built (2026-09-09)

```
detective doctor [target] [--green] [--red] [--yellow] [--project-root DIR]
```

`target` is optional and may be `file.py::function` or a bare `file.py`. It scopes two reads: the
dependency probe (which imports to check) and the certificate read (whose recorded cut reasons).
With no target the ledger is unioned — "your recent runs recorded these" — which is the honest
repo-scoped answer.

Dispatched from `_STATIC_COMMANDS`, above `_split_target`, because an OPTIONAL target that may be a
bare path must not fall into the separator menu a required `file::func` verb uses.

### What it looks like on the case it exists for

```
detective doctor · /…/scratchpad/s10
  target: motion.py::sync_step

  GREEN — setup        deps_elsewhere
  · Not importable     funcy   (by this run's interpreter)
    …but present in    /Users/…/miniconda3/bin/python3
  · Not importable     jax   (by this run's interpreter)
    …but present in    /Users/…/miniconda3/bin/python3
  · This run uses      /Users/…/tools/Detective/.venv/bin/python3
  · Why this matters   you do not have an INSTALLATION problem — you have a
                       PROPAGATION problem. …
  · Fix                install into THIS interpreter, or run detective under the one
                       that already has it (detective regime names the one in use).

exit 2 — a setup fault is live; fix it before trusting any verdict from this repo
```

### Not-read is a rendered state, not an omission

RED and YELLOW were not built WHEN THIS SECTION WAS WRITTEN (both landed later the same day — §10,
§12), and the report said so in their own sections with the reason. The principle is what survives,
and it is the one doctor is most likely to lose: an unread axis is a REPORTED state. This is
§2's hard requirement applied to doctor itself: swallowing at WRITE time is right, swallowing at
READ time is what the project exists to prevent, and an empty process section reads as "nothing
wrong" — the one thing it must not say.

### A bug this found, worth recording because of HOW

The recorded-failure branch was UNREACHABLE on first write. `_split_target` returns the file already
relative to the project root — which is exactly the certificate ledger's key form — and the handler
re-relativised it against the CWD, producing a `../../..` path that matched nothing. A ledger
recording `target_load_failed` rendered `clean`.

Every unit test passed while that was true, because none went near the branch. It was caught by
driving the real command at it, which is the project's own recorded rule: *validate end-to-end
through the real command, not by calling the internal function directly*. The regression test now
covers both directions — the key that matched nothing, and the over-correction where one target's
recorded failure leaks into another's read.

The same pass caught a FALSE ALARM in the fence guard: it banned the word "mutant", which
`cut_reason_sentence('target_load_failed')` legitimately contains. That test passed on a clean repo
because the branch was unreachable and would have fired wrongly the first time a real user hit the
stale case — agreement over a subspace, the same shape as §MI, the #60 MCP drift and S10. It now
bans verdict PHRASINGS and exercises both branches.


---

## 10. YELLOW, as built (2026-09-09)

Pure consumption, as §8.3 predicted: `survey_source` already answers this question per function, so
the axis needed no new machinery beyond a ceiling decision over its counts.

`taste_disposition(scanned, extractable_core, impure_body, trapped_by_imports, unresolved_param)`
→ `extractable_core` · `impure_body` · `trapped_by_imports` · `unresolved_param` · `clear` ·
`nothing_to_read`. The ranking is `survey_disposition`'s own, consumed rather than restated — a
second reader of the same facts is the drift every repair in `CORRECTNESS_REPAIRS` turned out to be.
`_TASTE_CODES` binds the count order to the vocabulary survey actually produces, and a test asserts
the two sets are equal, so a code on one side and not the other cannot silently become a count that
is always zero.

`nothing_to_read` is distinct from `clear` because "we looked and found nothing in the way" and
"there was nothing to look at" are different facts — `plan` already names the second rather than
reporting a clean read of an empty set. And neither is the same as the caller's `not read`, which is
§7.4's directory-scope degradation: yellow costs a static pass per function, so it is read for a
TARGET and otherwise reports why it declined. Collapsing those would let an unread axis render as a
clean one, which is the single failure this surface exists to prevent.

### The mix, demonstrated

With two axes live the G+Y product is real output rather than a design claim:

```
  GREEN + YELLOW       ordered remediation — the mix, not the sum
  · First              fix the setup fault above. Nothing below is trustworthy until you do.
  · Then RE-DERIVE     the taste finding was measured through that fault, so re-run
                       this read afterwards rather than acting on it now.
```

It prints only when BOTH are live — a line that always appears is a line nobody reads — and a yellow
finding never changes the exit code, because a ceiling is not damage and not "your world is wrong".

### What testing yellow measured about this repo

Every member of `survey._HEAVY_IMPORT_ROOTS` (torch, jax, scipy, matplotlib, sklearn, tensorflow,
keras, cv2, jaxlib) is ABSENT from the project venv. So no `trapped_by_imports` fixture can avoid
tripping a green finding as well — the coupling is real rather than an artefact, since a module
importing an absent heavy package genuinely has both a setup fault and a ceiling. A machine-
independent yellow-only fixture needs a package that is installed and is not a heavy root:
`numpy` (declared by S11) annotated as `np.ndarray`, which is in `_INEXPRESSIBLE_ROOTS`. Four tests
were written on a wrong model of what `survey_source` flags and were corrected by querying it
directly rather than by adjusting the assertions.


---

## 11. The signpost, as built (2026-09-09)

§4 says "every command knows its own herb", and the first thing grounding changed is WHICH commands
need the line.

### Traced, not assumed: the live commands already hold their green awareness

`_run_live` resolves the regime and **refuses** on a conflict, for both the human and the `--json`
channel. R1/R3 already route a `target_load_failed` measurement to `fix_load` with the dependency
named. So converge / audit / diagnose / decompose / receipt / verify-rewrite are covered, and a
signpost there would be a second voice saying what the command already says.

The **static taste verbs — plan, survey, extract, parsimony, censor — never resolve the regime at
all.** Every one is YELLOW. They emit taste advice with no way of knowing the environment makes it
meaningless, which is precisely §3's G+Y product (unreliability) arriving at the surface where it
was missing. That is where the signpost is load-bearing rather than decorative.

### Cheap by construction

The signpost runs INSIDE another command, so it pays only for what is free: the regime resolution
these verbs should arguably be doing anyway, one AST parse, `find_spec` per top-level import, and
one JSON read of the certificate ledger. It does **not** run green's cross-interpreter probe —
that shells out per candidate interpreter, and taxing every healthy `survey` for it would be the
diagnostic charging rent. Naming the finding is the line's job; the inference about WHICH
interpreter has the package is what `detective doctor` is for.

`command_setup_fault` (✓ COMPLETE 8/8) is deliberately NOT `setup_disposition` with empty probe
arguments: that would return `stale_load_failure` for a fault the current run just hit, and "a
prior run recorded this, it may be stale" is the opposite of the truth. Two questions that differ
in tense are two decisions.

### What it prints

```
  ⚠ SETUP FAULT        dependency_not_importable — a GREEN finding outranks this yellow verdict
                       funcy, jax not importable by this interpreter
  · Why it matters     what this command just told you was measured THROUGH that
                       fault. Fix the setup first, then RE-DERIVE this read — acting on
                       it now is acting on a measurement of your environment.
  · The full read      detective doctor 'motion.py'
```

Silent on a clean run, silent on `--json` (a parsed contract must not gain a prose banner), and
silent on any internal failure — a signpost that breaks the command it decorates has cost a verdict
to deliver a hint.

### RULED 2026-09-09 — a pre-empted command WITHHOLDS its verdict

§4's literal reading, and it reverses what was built first. The banner form printed the taste report
under a warning; the strict form does not print it at all.

The argument for the strict reading is the one the mix exists to make: **a taste verdict measured
through a live setup fault is a measurement of the ENVIRONMENT, not of the code.** Printing it under
a warning still leaves the reader free to act on it — which is the unreliability doctor exists to
NAME rather than decorate. A warning the reader may act past is not a pre-emption.

Exit **2** — the documented "your world is wrong — fix that, not the code", and the same code
`doctor` returns for the same finding, so a caller branching on it gets ONE answer from both
surfaces rather than two.

The **machine channel is exempt**, deliberately: `--json` is a parsed contract and must not silently
change shape. A programmatic consumer gets its green facts from `detective doctor`'s structured
surface, which is where they belong.

And the banner's own copy changed with it. It used to say "what this command just told you was
measured THROUGH that fault… RE-DERIVE this read", which described a report that no longer arrives.
It now says why the read was withheld — because a refusal that does not explain itself is the same
defect as advice that cannot be acted on, and "withheld" with no reason reads as the tool being
broken, which is exactly the conclusion U2's greenfield user draws.

Also open: the signpost currently fires for GREEN faults only. RED pre-emption of the taste verbs —
"you are running the taste half before behaviour is pinned" — needs the invocation ledger, and will
light up the same site when red lands.


---

## 12. RED, as built (2026-09-09) — and the mix, complete

The axis that "does nothing alone and completes green". Its four decisions
(`spiral_disposition`, `order_disposition`, `environment_drift_disposition`,
`outcome_disposition`) had been pinned since the start and had no data; the ledger's persistence
shell and `outcome` propagation are what made them answerable.

`process_disposition` (✓ COMPLETE 29/29) ranks them, and the top rank is not a taste call:

> **`ground_moved` outranks everything.** Every other red finding is a comparison BETWEEN runs, and
> a comparison across changed ground compares different things. A "spiral" computed across an
> interpreter change is not a spiral — it is two measurements of two environments, and reporting it
> as a repeat sends the operator to stop doing the one thing that was actually varying.

Then `spiral`, then `order`, then `repeat_no_change` — which is NAMED but is not a spiral, because
two identical runs is how anyone checks a result and the remedy differs (there is none).
`progressed` and `repeat_state_changed` never reach a finding at all: an edit-then-rerun loop IS
how the tool is used.

### What it actually says

```
  RED — process        spiral
  · The finding        you ran `audit motion.py::sync_step` again with nothing changed
                       and got `fix_load` each time
  · Why it matters     a re-run is the normal shape of work; a re-run that cannot
                       change its own outcome is a spiral. …
```

That sentence is the entire argument for `outcome` propagation. "You ran this three times" does not
name what to stop doing; "you got `fix_load` each time" does.

### Reading discipline

Reports on the most recent NON-DOCTOR invocation — "you ran doctor twice" is not the finding anyone
came for. Scopes the comparison to the same verb AND the same target, because a different target is
a different question and mixing them would manufacture spiral accusations out of ordinary work
across a codebase (the false-positive direction, which is the worse one). And `available` is
separate from every code: an unreadable or missing ledger reports **UNAVAILABLE**, never `clear`.

`_target_ever_pinned` consumes the CERTIFICATE rather than asking the ledger whether a converge
"looked successful" — a converge that ran is not a converge that pinned, and `order_disposition`'s
question is about the contract existing.

### The four products (§3), all live

`mix_product` (✓ COMPLETE 15/15) — and this is the part of the herb scheme that is a mechanism
rather than a metaphor:

| mix | verdict no single axis produces |
|---|---|
| **G+R** | **suppression** — the process advice is VOID; the instruction could never have worked in this environment, so repeating it is not the mistake, following it at all is |
| **G+Y** | **unreliability** — the taste finding was measured THROUGH the fault, so re-derive rather than act |
| **R+Y** | **ordering** — the taste half before the correctness half it presupposes |
| **G+R+Y** | **ordered remediation** — fix green, re-run once (the process finding may simply DISSOLVE, having been a symptom), then re-derive the taste read |

Silent below two live axes: a product needs two things to multiply, and a mix line over a single
finding would be the line that always appears — the signpost discipline's own defect, reproduced
inside doctor.

Red never changes the exit code. Only GREEN earns exit 2 ("your world is wrong"); a process finding
is about what you DID, and conflating them would make the code stop meaning what the table says.
