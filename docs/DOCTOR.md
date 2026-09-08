# `detective doctor` — design

Status: DESIGN, for founder mark-up. Nothing built. Written 2026-09-08.

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
5. **Naming.** `detective doctor` is the command. Whether the herb vocabulary surfaces to the
   user (`--green` / `--red` / `--yellow`) or stays internal with plain flags
   (`--setup` / `--process` / `--taste`) is a taste call. The herbs are a good *mnemonic* and a
   bad *requirement*.
