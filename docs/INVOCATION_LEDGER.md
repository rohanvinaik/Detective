# The invocation ledger — design

Status: BUILDING. Written 2026-09-08; founder rulings and grounding corrections 2026-09-09.
Built: the four pure decisions, the process-scoped observation channel, `state_basis`, and the
PERSISTENCE SHELL (append / read / digests / eviction).
the `try/finally` CALL SITE in `main`.
and `outcome` propagation across the four verbs an operator actually repeats.
Not built: `purge --prune`, propagation for the remaining verbs, and doctor's RED axis.

Prerequisite for [`DOCTOR.md`](DOCTOR.md)'s **red / process** axis, which cannot be built without
it. Standalone artifact: the founder has named a second use — mining the space past the boundary
of knowability by inference over implicit patterns — so the schema is designed to be read by
something other than doctor.

---

## 1. What it is

An append-only record of Detective invocations in a project, so that questions about the
**operator** become decidable instead of inferred:

- Did you run the same command again with nothing changed in between? (**spiral**)
- Did you run a taste command before behaviour was pinned? (**order**)
- Did you flag a mutant equivalent in a branch the witness search never reached? (**judgement
  without proof** — observed live 2026-09-08; see `CORRECTNESS_REPAIRS_2026-09-08.md` §R5)
- Did the interpreter change under you between runs? (**the propagation case**)
- Did you act on a cached verdict as though it were fresh?

None of these are answerable from a single run. All of them are answerable from two.

---

## 2. Hard requirements

1. **It must never fail a run.** A correctness tool does not acquire a new failure source for an
   advisory artifact. Every write is wrapped and swallowed.
2. **But the absence is disclosed where it matters.** Swallowing silently at write time is right;
   swallowing at *read* time is the thing this project exists to prevent. When doctor reads a
   ledger that is missing or unwritable, it says so and reports that **process findings are
   unavailable** — never an empty process section that reads as "nothing wrong".
3. **It records facts, never verdicts.** The ledger stores what happened. Every interpretation is
   a separate pure decision over it (§5), so the record stays reusable by a consumer that is not
   doctor.
4. **It is not cache.** See §4.

---

## 3. Schema

`.detective/ledger.jsonl` — one JSON object per line, append-only.

JSONL rather than a single JSON document because a single `open(..., "a")` + one `write()` of a
newline-terminated line needs no read-modify-write, so concurrent runs cannot lose each other's
entries, and a truncated final line costs one record instead of the file.

```jsonc
{
  "v": 1,                              // schema version — forward-compat for the inference work
  "ts": "2026-09-08T14:22:03.114Z",    // wall clock, UTC
  "dur_ms": 4821,

  "verb": "converge",                  // the subcommand
  "target": "dsl.py::add",             // normalised; null for repo-scoped verbs
  "args": {                            // ONLY measurement-affecting flags, normalised + sorted
    "input": ["((1,2),(3,4))", "(1,(2,3))"],
    "apply": false,
    "trace_budget": null
  },

  "exit": 0,
  "refusal": null,                     // e.g. "generated_suite_collision" on the typed-refusal paths

  "env": {
    "interpreter": "/…/scratchpad/ab/.venv-det/bin/python",   // THE propagation case
    "detective": "/Users/…/tools/Detective/Detective/__init__.py",
    "wesker":    "/Users/…/tools/Wesker/Wesker/__init__.py",
    "version": "0.13.0",
    "project_root": "/…/arc-dsl"
  },

  "state": {                           // what a re-run would be measuring
    "target_src": "sha256:…",          // digest of the target FILE
    "suite": "sha256:…",               // digest over sorted (name, size, mtime_ns) of the generated dir
    "inputs": "sha256:…",              // .detective/inputs.json
    "equivalents": "sha256:…"          // .detective/equivalents.json
  },

  "outcome": null                      // RESERVED — see §6
}
```

### Notes on the fields

- **`env.interpreter` + `env.detective` + `env.wesker` are the load-bearing environment fields.**
  They are the two-knob fact, recorded. They are what lets doctor say *"your last five runs used
  `.venv-det`; the packages you installed went to `~/miniconda3`."*
- **`state` is what makes "nothing changed" decidable** rather than a guess. Four digests, all
  cheap: one file read, one stat-walk, two small file reads.
- **No rendered output is stored.** It would duplicate source into a new file and grow without
  bound. A spiral is detected from `args` + `state` (§5), not from comparing output bytes.
- **`args` records only flags that affect the measurement.** `--json`, `--verbose` and the like
  are excluded: two runs differing only in rendering are the same invocation for process purposes.

---

## 4. `purge`, and why the ledger is exempt

`purge`'s own stated criterion is the answer, and it does not need a new rule:

> *"Everything removed is regeneratable by re-running — the next run is just cold."*

**History is not regeneratable by re-running.** A re-run produces a new entry; it cannot
reproduce the entry that recorded what you did an hour ago. So the ledger fails purge's criterion
and must not be purged — by the existing rule, not an exception to it.

It sits with `inputs.json` and `equivalents.json` on the never-purged side, though for a different
reason: those are *authored judgements*; this is *observed history*. Both are unreproducible; only
one is a claim.

### Retention

Unbounded growth is real, and pruning is not purging. Proposed: a size cap
(**5 MB default, configurable**), oldest-evicted, applied on append. At the schema above that is
on the order of 10⁴ entries — far more than any process question needs, and deliberately generous
because the founder has named this as a data source for later inference work. Eviction is logged
in-band as a single `{"v":1,"evicted":N}` record so a reader never mistakes a pruned head for the
beginning of history.

**Open (§7.2):** whether a `--prune` flag on `purge` should exist for a user who genuinely wants
the history gone, and whether it should require a confirmation `purge` currently does not have.

### Retention is a placeholder for something better — DEFERRED ON PURPOSE

Size-capped oldest-evicted is a **raw-ledger** policy: it treats every entry as equally worth
keeping until it is equally worth discarding, which is only true if the entries carry no
structure. They do carry structure.

The better system is **meaningfulness-focused**: retain by what an entry *means* in the arc of the
operator's work, not by its position in a queue. A spiral's three identical entries are one event
and could collapse to one record carrying a count; the run where the interpreter changed is worth
more than the fifty around it; a long-quiet stretch is itself a fact. That is a story-understanding
problem over a data geometry — the same shape as Homeostat — and it is the natural bridge to the
inference work past the boundary of knowability, because what survives eviction *is* the implicit
pattern.

This requires deep conceptual work and is **intentionally deferred**, not overlooked. The 5 MB cap
is a holding position chosen to be generous enough that no data needed by that future design is
being thrown away in the meantime. Recorded here so the deferral is visible rather than becoming
an accident of the first implementation.

---

## 5. The pure decisions

The ledger's I/O is a shell; the decisions read off it are the pinnable part, and they are
extracted first and converged **in isolation before wiring**
(`feedback_converge_before_wiring`). All total over `str`/`bool`/`int`, all returning named
string codes — two conditions that mean different things must not collapse into one truthy check.

```python
def spiral_disposition(
    prior_repeats: int,      # consecutive prior entries with the same verb+target+args
    same_args: bool,
    same_state: bool,
) -> str:
    """no_prior · progressed · repeat_state_changed · repeat_no_change · spiral"""
```

- `repeat_no_change` — one repeat, nothing changed. Worth a note.
- `spiral` — two or more. This is the state doctor names loudly, and it is the exact shape
  observed on conorheins: the operator followed the printed instruction and the instruction could
  not change the state.
- `repeat_state_changed` — a re-run after an edit is **normal work**, not a finding. Keeping this
  distinct from `repeat_no_change` is the whole reason for a named code rather than a bool.

```python
def order_disposition(
    command_herb: str,          # "green" | "red" | "yellow"
    target_ever_pinned: bool,
    target_has_prior_measurement: bool,
) -> str:
    """ok · taste_before_behaviour · taste_without_measurement · behaviour_first"""


def environment_drift_disposition(
    same_interpreter: bool,
    same_engine_paths: bool,
    same_version: bool,
) -> str:
    """stable · interpreter_changed · engine_changed · version_changed"""
```

The I/O shell — append, read, prune, digest — is **impure and gets hand-written durability tests
only**, per the project's rule that pure I/O is not converge-pinnable. Those tests cover: a
missing `.detective/`, a read-only directory, a truncated final line, concurrent appends, and
eviction at the cap.

---

## 6. Wiring — one call site

**Traced.** `cli.main` (`cli.py:4970-5036`) is the single funnel: it parses, calls `_run_live`,
and returns a code. It already carries the precedent for exactly this discipline — a best-effort
tail block whose comment reads *"monitoring must never fail the actual work"*, with
`except Exception:  # noqa: BLE001 — telemetry is advisory and never fatal`.

**But the tail is the wrong place.** `main` has three typed-refusal paths
(`GeneratedSuiteCollision`, `AuditAccountingError`, `LookupError/FileNotFoundError/SyntaxError`)
that exit via `raise SystemExit` or `return 1` and would **bypass** a tail append. A refusal is a
process fact — *"you pointed at a target that does not exist, three times"* is precisely a red
finding — so the append must cover them.

→ **`try/finally` around `main`'s body, one call site.** `finally` runs on the `SystemExit`
propagation paths too. Where the exception paths leave `code` unbound, the entry records
`exit: null` with `refusal` set.

### `outcome` IS propagated — founder call, 2026-09-08

`outcome` — the *named next-action code* a command emitted (`fix_load`, `close_the_gap`,
`settled`, `repair_measurement`) — is computed deep inside `_converge_action` / `_audit_action`
and is not visible at `main`. Propagating it means touching every command's return path.

**Founder ruling: pay the propagation cost now — build wide rather than narrow-then-iterate.**

So `outcome` is populated in v1. Doctor can therefore say *"you ran a `fix_load` three times"*
rather than the weaker *"you ran this three times with nothing changed"* — which matters, because
the named code is what makes the finding actionable rather than merely observed.

Consequence for the build: the propagation is its own step, traced with Serena before any edit,
and it must not change any command's rendered output or exit code. A run's verdict is unaffected
by whether the ledger is watching.

---

## 7. Open questions — founder call

1. **`state.suite` digest basis.** Sorted `(name, size, mtime_ns)` over the generated test dir is
   cheap but mtime-sensitive: a `touch` with no content change reads as a state change, which
   makes `spiral_disposition` *under*-report (safe direction — it would say `repeat_state_changed`
   and stay quiet). Content-hashing every generated test is exact but costs a full read per run.
   The cheap version fails safe; is safe-and-cheap the right trade, or should it be exact?
2. **A `purge --prune` escape** for a user who wants history gone (§4).
3. **Cross-project reads.** The ledger is per-project. The propagation case is *cross*-project by
   nature — the operator installed into an interpreter shared across repos. Doctor's green axis
   probes interpreters live, so it does not need this; but the later inference work might want a
   machine-level index. Not proposed here — flagged so the per-project choice is deliberate.
4. **Does `--json` mode append?** It is the same invocation and a programmatic caller can spiral
   exactly as a human can, so yes by default. Recorded because it is the kind of default that is
   easier to argue now than to change later.


---

## 8. Founder rulings and grounding, 2026-09-09

### 8.1 §7.1 suite-digest basis — RULED: cheap, with an escalation where cheap can lie

"Cheap with fallback triggered when the situation knowably calls for it." That is a better answer
than either option the section offered, and it is built as `ledger.state_basis` (✓ COMPLETE 11/11).

The cheap basis — sorted `(name, size, mtime_ns)`, one stat-walk, no reads — is **exact in one
direction and not the other**:

| cheap says | truth |
|---|---|
| UNCHANGED | content unchanged, barring deliberate mtime restoration |
| CHANGED | content **may be identical** — a `touch`, a checkout, a copy, a `git stash` round-trip all move mtime without moving a byte |

Only the second matters, and only in one situation: the operator re-ran the SAME command with the
SAME arguments and the digest says the state moved. Either they genuinely edited something (normal
work, nothing to report) or the mtimes shifted underneath them and **this is a spiral the cheap
basis is about to hide**. Those two are worth one full read to tell apart; nothing else is.

So the healthy path never pays — a first run, a progressed run and an unchanged run all take the
stat-walk. Measured 2026-09-09: `touch` on a synth moves the cheap digest and leaves the exact one
identical, and `state_basis` returns `escalate_exact` for exactly that case.

**Known limit, stated rather than papered over:** the other direction — content changed while mtime
was RESTORED — would let cheap report `unchanged` and produce a FALSE spiral accusation, which is
the worse error of the two. It is not escalated because catching it costs a full read on every
repeat including every healthy one, and its precondition is deliberate mtime restoration rather
than anything an operator does by accident.

### 8.2 §7.2 `purge --prune` — RULED: yes, with confirmation. Not built yet.

"Was very useful during debugging/building, and should only be removed if there's no possible way
for a mistake in operation, which is obviously far away. Theoretically possible, but not today."

So the escape exists and asks first. `purge` currently has no confirmation because everything it
removes is regeneratable; this is the one thing it would remove that is not.

**AND THE LEDGER NEEDED NO EXEMPTION TO SURVIVE ORDINARY PURGE.** The section asked whether an
invocation ledger belongs in a directory `purge` is documented to clear. Grounded against current
code: `verdict_cache.purge` works from an explicit ALLOWLIST — the cache file plus
`.detective/reports/*` — rather than sweeping `.detective/`, so history survives by construction.
A test pins it, because a future purge that switched to a sweep would silently destroy evidence
while reporting a clean state.

### 8.3 §7.3 cross-project reads — RULED: project scope

No machine-level index. Green already probes interpreters live, so RED does not need one, and a
machine-wide index is a much larger commitment than the deferred meaningfulness work should
inherit. `.detective/` is gitignored, which is correct: this is the OPERATOR's invocation history,
not a fact about the project, and it must not travel with a clone.

### 8.4 The shell, as built

`.detective/ledger.jsonl`, one `open(..., "a")` and one newline-terminated `write()` per record —
no read-modify-write, so concurrent runs cannot lose each other's entries and a truncated final
line costs ONE record instead of the file. Both are pinned by tests rather than asserted.

`read_recent` returns `()` for a missing, unreadable OR empty ledger, so `ledger_available` exists
beside it: **"we have no history" and "you have run nothing" are different claims about the
operator**, and rendering the first as the second would let a missing ledger read as a clean
process report — the one thing this surface must never do. Doctor's red axis consumes both.

Eviction: 5 MB cap, oldest half dropped, and the drop recorded IN BAND as
`{"v":1,"evicted":N}` so a reader never mistakes a pruned head for the beginning of history. The
marker is filtered out of `read_recent` — it is bookkeeping about the FILE, not a fact about the
operator, and a consumer counting repeats must not see it as one.


---

## 9. The call site, as built (2026-09-09)

§6's structural claim was checked against current source rather than trusted — the section cites
`cli.py:4970-5036` and the file has grown ~450 lines since — and it holds exactly. `main` carries
three typed-refusal paths:

| path | leaves via |
|---|---|
| `GeneratedSuiteCollision` | `return 1` (json) or `raise SystemExit` |
| `AuditAccountingError` | `return 1` (json) or `raise SystemExit` |
| `LookupError / FileNotFoundError / SyntaxError` | `raise SystemExit` |

A TAIL append misses all three, and a refusal is the most process-shaped event there is — "you
pointed at a target that does not exist, three times" is a red finding and nothing else can see it.
So: `try/finally` around the body, `_exit`/`_refusal` set beside each exit, and where an exception
path leaves the code unbound the record keeps `exit: null` rather than inventing a number.

Verified through the real command:

```
{'verb': 'survey',   'target': 'shipping.py',                    'exit': 0,    'refusal': None}
{'verb': 'diagnose', 'target': 'shipping.py::no_such_function',  'exit': None, 'refusal': 'target_not_found'}
{'verb': 'converge', 'target': 'shipping.py::shipping_cost',     'exit': 0,
 'outcome': [['outcome', 'converge', 'settled']], 'dur_ms': 1842}
```

### `args` is an EXCLUSION list, deliberately

`_LEDGER_ARG_NOISE` names the rendering flags (`--json`, `--verbose`, colour) plus the fields that
have their own slot. Everything else is keyed by default.

An INCLUSION list would have been the obvious shape and is the wrong one: it silently drops every
new flag nobody remembered to add, and a measurement-affecting flag that is not keyed makes two
DIFFERENT questions look like a repeat — or worse, makes a repeat look like progress. §3 states the
rule this implements: "two runs differing only in rendering are the same invocation for process
purposes", and the exclusion list is the only shape where forgetting fails safe.

### A regression this introduced and how it was caught

`time.monotonic()` in `main` against a `time` that cli.py never imported at module scope — every
command died with `NameError` on the first line of the new block. Caught by driving `detective
survey` immediately after wiring, not by the suite; the tests were written afterwards. Recorded
because the lesson is the ordering, not the typo: the wiring step's verification is the real
command, and it costs seconds.

### `outcome` is PARTIAL, and says so

Only `converge` calls `observe` today, so a converge run carries its named next-action code and
every other verb records `[]`. The field is always PRESENT — absent must never read as none — and
the recorder's own comment names the gap rather than leaving it to look complete. Full propagation
is the next step, and its constraint stands: it must not change any command's rendered output or
exit code, because a run's verdict cannot depend on whether the ledger is watching.


### 9.1 Does the ledger break "writes nothing"? — the contract, sharpened

Wiring the call site broke three doctor tests, and the break was a finding rather than a
regression. `doctor`, `plan`, `survey`, `parsimony` and `censor` are all documented **advisory:
writes nothing** — and `main` now records every invocation, theirs included.

The tests asserted whole-tree mtime equality, which was a PROXY for the intent "does not mutate
the project it is diagnosing". That proxy agreed with the intent only over the subspace where the
invocation ledger did not exist. Same shape as §MI, the #60 MCP drift, S10 and the doctor fence
guard — the fifth instance this session of a claim that held over the subspace where it was checked.

The contract, stated precisely rather than left as a flat phrase:

> **"Writes nothing" is about the PROJECT** — your source, your suite, Detective's own artifacts
> (synths, certificates, verdict cache). The invocation ledger is a different category: it records
> that you RAN a command, not a change to what the command was looking at.

Doctor must be no exception. "You ran doctor five times" is precisely a process fact, and exempting
one verb would put a hole in exactly the axis being built to read it. The tests now pin BOTH halves
— nothing in the project moves, and the ledger does — which is strictly stronger than the mtime
proxy was.

Worth carrying forward: every advisory verb's help text says "writes nothing", and that sentence is
now imprecise for all of them. Not rewritten here, because it is user-facing copy across six verbs
and a wording change is the founder's call.


---

## 10. `outcome` propagation, as built (2026-09-09)

Four sites live: **converge · audit · diagnose · doctor**.

    doctor     exit=2   outcome=[['outcome','doctor','deps_elsewhere/trapped_by_imports']]
    diagnose   exit=0   outcome=[['outcome','diagnose','settled']]
    audit      exit=0   outcome=[['outcome','audit','remove_redundant']]
    converge   exit=0   outcome=[['outcome','converge','settled']]

### The handoff's warning was mine, and it was overcautious

`docs/dogfood/SESSION_HANDOFF_2026-09-08.md` said `_audit_action` is "deliberately NOT wired: its
ladder has no single named code, and inventing one recreates the drift R3 removed." That was my own
note, not a founder ruling, and grounding struck it.

R3's drift was **two readers of ONE report answering differently**. Extracting `audit_next_action`
is one decision with one renderer, and its first branch DELEGATES to `measurement_block_route`
rather than restating it — the same consumption R3 installed. Nothing about it recreates the drift.

What it buys: "you ran `fix_load` three times" instead of "you ran audit three times with nothing
changing". Only the first names what to stop doing.

`audit_next_action` — ✓ COMPLETE 60/64 modulo 4. Nine codes, and the ORDER is the judgement, each
rank with a reason rather than a preference: a measurement that could not RUN outranks everything
(Finding E); a failing suite outranks the numbers it invalidates; real gaps outrank bloat; and
`flag` — the one claim a human makes against the engine — comes last, so it is never offered while
a real gap is open.

`diagnose_next_action` — ✓ COMPLETE 21/21. Three codes, two of which are CONVERGE'S
(`close_the_gap`, `settled`) reused rather than paraphrased. The record is `(kind, verb, code)` so
the verb disambiguates, and a shared vocabulary makes "you got `close_the_gap` from diagnose and
then from converge" ONE story — two spellings of the same state would be two, and the repeat would
be invisible.

Doctor observes its own read, because the command that diagnoses the operator must not be the one
verb exempt from being observed. "You ran doctor five times and it said `deps_elsewhere` every
time" is precisely what red exists to name.

### Scope, stated rather than implied

Wired: the four verbs an operator actually repeats when stuck. NOT wired: plan, survey, extract,
decompose, receipt, verify-rewrite, parsimony, censor, flag, regime, purge. Those record
`outcome: []` — the field is always PRESENT, so absent never reads as none.

That is a real gap and not a finished job. The four were chosen because they are where a spiral
happens; the taste verbs are advisory reads rather than instructions to repeat, and the bracket
commands are one-shot. Worth revisiting once red has run against real history and shown which
absences actually cost a finding.

### The constraint, held

No command's rendered output or exit code changed. The strongest evidence is not in the new tests:
it is the **126 pre-existing audit tests passing unchanged** over a renderer whose entire branch
structure was rewritten to dispatch on the named code.

### A test that failed for the right reason

The wiring test first asserted on the observation CHANNEL after running `main`, and found it empty
— because `_record_invocation` drains it in its `finally`, which is exactly the per-invocation
property another test in the same file pins. Reading the channel after the drain tests the drain,
not the wiring. Corrected to read the LEDGER, which is the surface that actually carries the claim.
