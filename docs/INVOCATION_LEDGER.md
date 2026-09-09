# The invocation ledger — design

Status: BUILDING. Written 2026-09-08; founder rulings and grounding corrections 2026-09-09.
Built: the four pure decisions, the process-scoped observation channel, `state_basis`, and the
PERSISTENCE SHELL (append / read / digests / eviction).
Not built: the `try/finally` call site in `main`, `outcome` propagation, `purge --prune`, and
doctor's RED axis on top.

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
