# Session handoff — 2026-09-09

Grounding for whoever picks this up, including a post-compact me.

**Read [`docs/OPEN_ITEMS.md`](../OPEN_ITEMS.md) first.** It is the single index for what remains,
and it says which design-doc claims have drifted. This file is the narrative of how today got there.

---

## What this session was

Started from the 2026-09-08 handoff with 10 unpushed commits and a red Sonar gate. Closed the
correctness wave (§MI, #60, S10, S14), then **designed and built `detective doctor` end to end**
plus the invocation ledger it needed.

## Landed — 6 pushed waves, then 7 more commits

| | |
|---|---|
| **§MI** | an invalid measurement is a RECORD, not an absence — and not a converge target |
| **#60** | the MCP surface said COMPLETE where the CLI and certificate said UNGATEABLE |
| **S10** | assert the premise the flake guard assumed — it fails 5/5, not 1-in-3 |
| **S14** | a multi-reason cut named one reason and led with the wrong one |
| **doctor** | lattice · green · the verb · yellow · the signpost · **red** · all four products |
| **ledger** | persistence shell · the one `try/finally` call site · `outcome` propagation · `purge --prune` |
| **docs** | `OPEN_ITEMS.md`, and four stale claims struck across three design docs |

Suite: **2784 → 3073**. Sonar bar held at **0 bugs / 0 vulns / 0 hotspots** throughout; new coverage
86.7% → **89.6%**.

---

## The one thing worth carrying forward

Six defects this wave were **the same shape**, and it is epistemic rather than technical:

> **A claim that holds over the subspace where it was checked, with nothing recording that the
> subspace was a subspace.**

`OPEN_ITEMS.md` §5 lists all six with their mechanisms. The remedy is not more tests — it is asking
what the check does NOT cover and recording that. **A guard that swallows its own failure needs a
test per BRANCH**, because its failure mode is indistinguishable from its healthy one.

The founder's framing, which is the through-line and worth quoting verbatim:

> *"The problem isn't breaking things, it's breaking things **silently**. Without checking, allowing
> things to drift endlessly and propagate."*

Loud breakage caught in ninety seconds is fine. This session broke every command once (a missing
`import time`) and it cost nothing, because the next action was running the real command.

---

## Habits this session paid for, with the receipts

1. **Drive the REAL command at the branch you just wrote.** Three defects were invisible to a green
   suite and fell out immediately under one invocation: doctor's unreachable recorded-failure branch
   (a `../../..` path that matched nothing), the signpost's undefined `CUT_REASONS` degrading to
   silence, and the `import time` regression.
2. **Ground the design doc before building to it.** `DOCTOR.md` §4 proposed `emission_disposition` —
   a name already taken by a pinned, unrelated function in the same package. Its §4 worry about R3
   rework did not apply. Its §8.3 axis-state assumptions were wrong in all three directions.
3. **A handoff note is not a ruling.** The 2026-09-08 handoff said `_audit_action` must not be wired
   because "inventing a named code recreates the drift R3 removed". That was *my own note*, it was
   overcautious, and it cost audit its process visibility for a wave.
4. **Fix the genuine Sonar residue rather than filing it under the Quality Profile.** Five findings
   this session were mine (S1172 ×2, S3358 ×2, W0404, R1711) and each was real.
5. **Two of my own noqa comments carried trailing prose** — the exact S7632 trigger S12 spent a
   whole migration removing, reintroduced four commits later. A tokenizer sweep is the check.

---

## Founder rulings encoded this session

All are in prose in the design docs so they cannot be quietly re-litigated:

- **The herbs stay the user-facing vocabulary.** `DOCTOR.md` §2 carries the reasoning at length,
  because the rename to `--setup/--process/--taste` will look like an improvement to everyone who
  meets it fresh. The opacity is a check on false confidence — *"a token that carries no meaning
  cannot lend borrowed meaning to a guess."*
- **Doctor exits 2 on a live green finding**, reversing §7.2's lean. Exit codes are epistemics.
- **Cheap digest with an escalation where cheap can lie** (`state_basis`) — a better answer than
  either option §7.1 offered.
- **`purge --prune` exists and asks first.** Project scope, no machine-level index.
- **Stay on hard pins** for the five self-refusing in-repo decisions (S15).

---

## Harness and environment facts that bite

- **`ab/.venv-det` must keep jax/funcy/matplotlib/torch ABSENT** — that absence IS the conorheins
  repro. Do not install into it.
- **Every member of `survey._HEAVY_IMPORT_ROOTS` is absent from the project venv.** So no
  `trapped_by_imports` fixture can avoid tripping a green finding too. A yellow-only fixture needs
  `numpy` (installed, not a heavy root) annotated `np.ndarray` (in `_INEXPRESSIBLE_ROOTS`).
- **`python -c` puts cwd at `sys.path[0]`** — prove two-knob resolution from the TARGET repo's cwd
  or the A/B is silently vacuous.
- **pytest BARE** in the gate; `addopts` already carries `-q`.
- **`ruff format --check .`** whole-tree, matching CI. `check` stays scoped.
- The scratchpad fixture at `scratchpad/s10/` (shipping.py, motion.py) is what every doctor and
  ledger behaviour in this session was driven against.

---

## Where to start

`docs/OPEN_ITEMS.md`. Five founder calls that are decisions rather than work; three bounded builds;
two research items. Nothing is blocked on implementation except by choice.

If the next move is code, **W1 (outcome propagation for the remaining verbs) is the one I would
NOT do yet** — converge/audit/diagnose/doctor are where spirals happen, and red running against
real history will show which of the other eleven absences actually costs a finding. Building them
now is speculative.
