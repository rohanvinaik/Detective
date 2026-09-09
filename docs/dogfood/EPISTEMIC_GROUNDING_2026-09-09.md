# Epistemic grounding — written for post-compact me, 2026-09-09

You are resuming a session that ran ~90% of a 1M context. The auto-summary above this is
**inference you cannot verify**. This file is what I actually knew, why I worked the way I did, and
what to read to re-ground. Read it before touching anything.

---

## 0. Read these, in this order, before acting

| # | What | Why |
|---|---|---|
| 1 | `docs/OPEN_ITEMS.md` | The ONLY authoritative list of what remains. Everything else has drifted at least once. |
| 2 | `docs/dogfood/SESSION_HANDOFF_2026-09-09.md` | Narrative of what landed and the environment facts that bite. |
| 3 | `git log --oneline -25` | The verifiable record. Commit bodies carry the reasoning; they are the primary source, not the docs. |
| 4 | `docs/DOCTOR.md` §8–§12 | Doctor as BUILT. §1–§7 is the original design and is partly anti-correlated. |
| 5 | `docs/INVOCATION_LEDGER.md` §8–§11 | The ledger as BUILT. §1–§7 likewise. |

**Symbolic traces to re-run rather than trust me on** (Serena, not grep):

```
find_symbol           Detective/doctor.py            → the whole axis surface
find_symbol           Detective/ledger.py            → the four decisions + the shell
find_referencing_symbols  signpost_disposition       → should be doctor + the signpost site only
find_referencing_symbols  audit_next_action          → _audit_action, nothing else
find_symbol           Detective/cli.py::_run_doctor  → the verb; _doctor_green/_red/_yellow beside it
find_symbol           Detective/cli.py::_signpost_rows → the pre-dispatch site (D1 withholding)
find_symbol           Detective/cli.py::main         → the ledger's ONE try/finally call site
```

**Drive the real command** — this is not optional, see §3:

```
cd /private/tmp/claude-502/…/scratchpad/s10        # the fixture everything was driven against
detective doctor 'motion.py::sync_step'            # all three axes live + G+R+Y product
detective survey motion.py                         # D1: withheld, exit 2
detective survey shipping.py                       # clean: report prints, exit 0
```

---

## 1. What this session was, in one paragraph

Opened with 10 unpushed commits and a red Sonar gate. Closed a correctness wave (§MI, #60, S10,
S14), then **designed and built `detective doctor` end to end** — green, yellow, red, the verb, the
signpost, all four superadditive products — plus the invocation ledger it needed (persistence shell,
one `try/finally` call site, `outcome` propagation, `purge --prune`). Suite **2784 → 3075**. Sonar
bar held at 0 bugs / 0 vulns / 0 hotspots throughout.

---

## 2. THE EPISTEMIC STATE — what I believe and how confident I am

**Load-bearing, verified by driving the real command:**
- Doctor works on all three axes. I watched it name `funcy`/`jax` under `~/miniconda3` while absent
  from the project venv — §1's acceptance test, on this machine.
- The ledger records refusals (`exit: null, refusal: 'target_not_found'`) that a tail append misses.
- Red names the outcome code: *"you ran `audit …` again with nothing changed and got `fix_load`
  each time."*

**Believed on strong evidence but NOT independently re-verified:**
- That the four `ledger` dispositions' *semantics* are right. I consumed them; I did not re-derive
  their truth tables. They were pinned before this session.
- That `_run_live`'s regime refusal covers every live verb. I read the one call site and the
  `conflicts` branch; I did not enumerate every path into it.

**Known unknowns I did not close:**
- Whether D2's "target that reliably admits a certificate" exists on a shared runner at all. If it
  does not, **that is itself the finding** — record it, do not work around it.
- Whether the 11 unwired verbs' missing `outcome` costs a real finding. Deliberately unmeasured.

**Where I was WRONG this session, so you weight my notes accordingly:**
1. I filed S4 by reading a field's NAME instead of its contract. The premise was false.
2. My own 2026-09-08 handoff said `_audit_action` must not be wired. Overcautious; it cost audit its
   process visibility for a wave.
3. I told the founder there'd be R3 rework for doctor. There wasn't.
4. I predicted three axis states in `DOCTOR.md` §8.3; all three were wrong until I checked.

**The lesson: my handoff notes are leads, not rulings. Ground them.**

---

## 3. THE WORKFLOW — why slow, when faster exists

I could have written all of doctor in three big edits and run the suite once. I did not, and each
constraint below bought something specific *in this session*. Receipts, not theory.

### 3.1 Symbolic diagnosis before ANY edit (Serena, never grep)

**Why:** grep finds strings; the language server understands the code. The rule exists because a
fix landing on one of two paths, while the sibling keeps the bug, is this project's dominant
failure.

**What it bought here:** `DOCTOR.md` §4 proposed `emission_disposition` — a name **already taken**
by a pinned, unrelated function in the same package. One `get_symbols_overview` caught it before a
line was written. Grep for "emission_disposition" would have found it too; what grep would NOT have
found was §8.3's three wrong axis-state assumptions, which needed the reference graph.

### 3.2 Extract the pure decision, converge it IN ISOLATION, then wire

**Why:** a decision wired first has a covering set that inflates to suite scale and the pin hangs
(measured previously: `line_gap_why` ran past 600s wired, seconds unwired).

**What it bought:** eight pinned decisions this session, each ✓ COMPLETE before anything consumed
it — `signpost_disposition` 24/28, `setup_disposition` 15/15, `taste_disposition` 47/47,
`process_disposition` 29/29, `mix_product` 15/15, `command_setup_fault` 8/8, `state_basis` 11/11,
`audit_next_action` 60/64, `diagnose_next_action` 21/21. None hung.

### 3.3 Named string codes, never bools

**Why:** *"two conditions that mean different things must not collapse into one truthy check."*

**What it bought:** the entire §MI repair was a missing named state. `clear` / `nothing_to_read` /
`not read` are three different facts about yellow that a bool would have made one.

### 3.4 Drive the REAL command at the branch you just wrote

**Why:** a green suite means "nothing I wrote a test for is broken", not "this works."

**What it bought — three defects invisible to a green suite:**
- Doctor's recorded-failure branch was **unreachable** (`_split_target` returns a repo-relative
  path; I re-relativized it and produced `../../..`). Every unit test passed.
- The signpost's `CUT_REASONS` was undefined, degrading to **silence** inside its own catch-all —
  so it never fired for two of three fault kinds. Found by three linters; 14 tests were green.
- `import time` missing broke **every command**. Caught in ~90 seconds because the next action after
  wiring was running the command.

### 3.5 Read the gate's exit code with the shell, not with my eyes

**Why:** `ruff check … | tail -1 && git commit` masks the exit code.

**What it cost when I skipped it:** I committed over a live E501 this session. Cosmetic, but the
habit is the point. Use `cmd; echo $?`.

### 3.6 Fix the genuine lint residue instead of filing it under the Quality Profile

**What it bought:** six real findings in my own code this session — S1172 ×2, S3358 ×2, W0404,
R1711 — plus two noqa comments I wrote that carried trailing prose, the exact S7632 trigger S12
spent a whole migration removing. All would have been "known residue" if I had not looked.

### 3.7 Surface founder calls instead of deciding them

**Why:** the session opened with an alignment pass about exactly this — *"you make decisions based
on unstated priors that are opaque and in violation of my explicit words."*

**What it bought:** every ruling this session came back **different from or sharper than my
recommendation** — the herbs stay (I proposed plain flags); D1 withholds (I built a banner); D5 is
"depends on why" (I offered a binary); the digest basis got an escalation neither option had.

---

## 4. THE ONE PATTERN — six defects, one shape

> **A claim that holds over the subspace where it was checked, with nothing recording that the
> subspace was a subspace.**

`OPEN_ITEMS.md` §5 lists all six with mechanisms. The remedy is not more tests — it is **asking what
the check does NOT cover and recording that**. A guard that swallows its own failure needs a test
per BRANCH, because its failure mode is indistinguishable from its healthy one.

**The founder's framing, verbatim, and it is the through-line:**

> *"The problem isn't breaking things, it's breaking things **silently**. Without checking, allowing
> things to drift endlessly and propagate."*

Loud breakage caught in ninety seconds is fine. Every defect above was silent, and none broke a
build.

---

## 5. Standing constraints (violate none of these)

- **Never publish to PyPI.** Publishing, version bumps, publish order and **closing GitHub issues**
  are the founder's domain.
- **Push is ask-first.** Commits are free and go straight to `main`, never a feature branch.
- **Never grep Python source for wiring** — a hard hook blocks it. Serena or AST.
- **Never offload symbolic tracing to a subagent.**
- Sonar creds at `~/.config/detective/sonar-local.env`, minted once, never re-mint.
- **`ab/.venv-det` must keep jax/funcy/matplotlib/torch ABSENT** — that absence IS the conorheins
  repro.
- Detective is **AI research, frequently NOT ML**. Never reframe symbolic/deterministic work as ML.
- `pytest` **bare** (addopts already has `-q`); `ruff format --check .` **whole-tree**; `check`
  scoped.

---

## 6. What to do next

`OPEN_ITEMS.md` is the list. If the next move is code, the order I would take:

1. **D2** — the cache guard's reliable target. Ruled, unbuilt, and the smallest.
2. **D5 / U1** — ruled "depends on why", with the build note in `OPEN_ITEMS.md` §2a. Engine-depth;
   deserves a fresh context. **Do not extend `admits_certificate`** — a third state wants its own
   place, as `measurement_invalid` did.
3. **W1 is the one I would NOT do yet.** Wait for red to run against real history and show which of
   the eleven absences actually costs a finding. Building them now is speculative.

D4 (witness search on un-exercised branches) is still unruled.
