# Changelog

Notable changes, newest first. Dates are the commit dates.

## Unreleased

Development source after 1.2.2; no version or release is implied.

- **The hang watchdog's stack dump survives a test that holds fd-level capture.** The live session
  captures at the `sys` level, but a test using pytest's `capfd` fixture, or its own `dup2`, points
  fd 2 at a temporary file; the dump landed there and the watchdog's hard exit discarded it, so a hang
  inside such a test ended with nothing on stderr. The watchdog now writes to a copy of stderr
  duplicated before the session starts. (`26741de`)
- The receiver-factory finalization test reports `measurement_valid` and the validity note when it
  fails, so the CI-only invalid measurement of D#138 names its cut. Its cause is not yet established.
  (`d2294ce`)
- The development lock selects Wesker `9915a9e`: W#47's single-invocation repair and its
  forwarding-wrapper follow-up, and the badge run's stack-dump diagnostics. Verdict-cache rows
  recorded under an older observation identity are not reused. (`5723410`, `ca00210`)
- The resumable repair checkpoint after the paired 1.2.2 publication, and the deferred
  construction-contract proposal (D#137), are recorded. (`0d26891`, `b9fef92`)

## 1.2.2 — 2026-10-24

Requires **`Wesker>=1.2.2`**, a pairing floor. Supersedes 1.2.1, whose exact release commit failed
macOS 3.14 CI after its release was created (see 1.2.1).

### The harvest deadline

- **An observation that arrives after the aggregate wall is not admitted.** The input harvest checked
  time between tests, but a worker could finish after the wall before its parent resumed, and its
  sample was kept. Late input and return observations, and snapshots that cross the wall during copy
  or repr, are now rejected. Timely partial inputs survive for their diagnostic and search purpose,
  and an incomplete codomain still refuses certification. The return-observation cache policy
  changes, so old observations cannot stand in for the corrected contract. (`e5f7c98`, D#108)
- **Setup and startup draw from the same absolute deadline.** The remaining join allowance is
  recomputed after startup, a final-test overrun remains a named cut, a started worker is reaped
  before an operator's interrupt propagates, and cancellation ownership is kept while cleanup may be
  retried. (`e5f7c98`, `bf3f87b`, D#108)

Controlled-clock regressions cover late entry, partial retention, copy/repr overruns, a late
codomain, setup/startup expiry and the remaining join allowance. They fail on 1.2.1 without relying
on sleep timing.

### Release integrity

- **Artifacts are built and signed only after exact-commit CI.** The release workflow refuses unless
  push CI for the exact checked-out release commit completed successfully. (`e5f7c98`)
- The signed 1.2.1 artifacts and the maintainer upload commands are recorded in
  `docs/RELEASE_1_2_1.md`. (`3c0eea0`)

## 1.2.1 — 2026-10-24

Requires **`Wesker>=1.2.1`**, the engine that preserves cold opcode observations beside a coverage
tool. (`10962b0`)

- The README shows live release and quality signals, and the shared repair plan is recorded under
  `openspec/`. (`bc37d87`)

**The upload clearance was premature.** The exact release commit `bc37d87` failed its macOS 3.14 CI
job after the GitHub release was created: `test_the_aggregate_wall_also_bounds_the_current_test`
retained an input observed after the aggregate deadline. A later documentation-only commit passed,
which did not establish that the race was repaired. The 1.2.1 tag and distributions remain
immutable; 1.2.2 is the correction.

## 1.2.0 — 2026-10-24

Requires **`Wesker>=1.2.0`** and Python 3.12 or newer; 3.14 is the standard interpreter (`df37730`).
Published Wesker 1.1.1 lacks `JoinedWorker`, which Detective's execution paths import, and the
development Git lock had concealed that, so the floor corrects a real incompatibility. Runtime source
`02d96d2`; `abbfeb2` records its installed-package acceptance (`docs/RELEASE_1_2_0.md`).

### Measurement correctness

- **The engine runs only the tests routing consulted.** Its pool had been the whole collection. A
  routing failure is a named cut, `routing_failed`, that authorises no test: never cached, never
  gateable, a STOP that names the error, exit 3, and `cut_reasons` with `routing_error` in `--json`.
  (`071fc73`, `08966ba`, D#91)
- **A warm two-sign run carries the observed codomain with the verdict** and re-harvests nothing; an
  empty codomain stays empty and is never read as missing. (`d9e3fb4`, D#92)
- Fast-mode shape hazards are adapted, an unknown containment is resolved, and value pins and
  mutation kills are accounted separately. Initial and final scores are formatted from independent
  populations and basis identities; simultaneous shape-hazard blockers are kept together, with the
  affected tests disclosed; "counts are a floor" is restricted to warranted clean partiality, and
  uncontained or unknown refusals print diagnostic counts. (`39e3eca`, `27e6c18`)
- Boundary probes reach the residual a fully expressible signature allows, and `modulo N` no longer
  claims a frontier it did not establish. (`cdb4f4d`, D#71)
- The opcode counter leaves out its own frame, so a co-resident tool's first-hit DISABLE no longer
  varies the read, and `count_opcodes` runs on Wesker's monitoring owner. (`3ad2dee`, `a6c9cc2`)
- A capture harvest never takes a profile hook it cannot hand back. (`2c40ebc`)

### Inputs and witnesses

- **`nan`, `inf`, `-inf`, `float("nan")` and `float("inf")` are input spellings in every module.** The
  one parser turns them into constants before its unchanged grammar gate and dunder ban, and
  everything Detective prints spells a non-finite float as a `float(...)` call that parses back.
  (`6196613`, `2f70d9d`, D#78)
- **Harvested arguments are snapshotted at call entry.** Aliases within a row survive, rows are
  isolated from later trials, and a copy or repr failure is a named refusal
  (`input_snapshot_failed`, `input_snapshot_unrepresentable`). (`1ca0202`)
- **A witness's values come from the bounded invocation that established it**; the unbounded value and
  receiver-state re-executions are gone. (`219a062`)
- Property checks, golden capture and witness and suite rendering run in bounded workers under the
  remaining command deadline; an intercepted speculative filesystem write is named
  `filesystem_write_blocked`. (`02d96d2`)

### The operator's path

- **One decision record per invocation.** `--json` carries what the page routes on, and the ledger
  records it once on every channel. (`383e54c`)
- A witness's test is written by converge's own writer, a loop ends when a supplied value changes
  nothing, the record carries the FINAL line, and a clean two-sign audit names converge. (`9c1276b`)
- `audit --remove` keeps any test a function it runs still needs, names why each test is kept, and
  leaves a formatter-clean test file formatter-clean. (`4eded8b`, `d6606a3`, D#103, D#106)

### State and trials

- **Every durable store has one reader.** Unreadable is not empty, nothing is overwritten unseen, a
  store the tool could not use is never reported as saved or as empty, and every write of a file the
  user owns is atomic. (`bcc433a`, `28e171b`, `c8c3b82`, `d5cc910`)
- A decompose trial is journaled and restored on every exit, and an interrupted trial retires the
  trial's bytecode. (`6b8fa2e`, `7a66833`)

### Guards and tests

- Standing guards: every consumer distinguishes a decision's codes or says why (invariant 3), and no
  defaulted `getattr` reads a name nothing declares (invariant 7). (`d812775`, `824b23f`)
- The suite's result does not depend on the machine's installed pytest plugins, and a temp project
  leaves no trace in the interpreter. (`6959005`, `5666523`)

### Not in this release

Containment of filesystem writes made by existing profiled tests (D#105), hard native-code and
resource containment, and the wider safe-removal work remain open obligations. No tests were purged.

## 1.1.1 — 2026-09-14

Requires **`Wesker>=1.1.1`** (see `dev/DEPENDENCY_FLOORS.md`).

### Removed

- **The MCP surface is parked.** The `[mcp]` extra and the `detective-mcp` command are no longer in the
  package; the server, its tests and the steps to restore it are in `parked/mcp/`. Nothing in the
  `detective` CLI or the library API changes. Agents drive the CLI, whose every command names the next.
  This removes an installable entry point in a patch release, which is why it leads this entry.

### Generated tests

- The header no longer points at a README section that no longer exists ("Generated tests & lint").
- The warrant docstring no longer prints `(confidence N)`, a hand-set number per synthesis strategy that
  nothing decided on. Suites already on disk keep both until `converge` regenerates them.

### The CLI and its documentation

- One "START HERE" (`detective regime`); `diagnose` and `plan` describe themselves as the first read for
  a function and for style.
- The README states that Detective runs the code it measures, and that a function which visibly reaches
  outside the process gets no invented inputs.
- `ARCHITECTURE.md` is a reference: every command, every module, a vocabulary, and where each reference
  code in the source is defined. The incidents behind its rules moved to `docs/HISTORY.md`.

### Correctness and hygiene

- Wesker 1.1.1: the equivalence probe distinguishes argument positions, which changes `diagnose`'s inert
  count (`total_equivalent`) on functions of three or more parameters; isolated workers no longer leak a
  descriptor; the makereport wrapper no longer re-raises in its teardown.
- pytest runs with warnings as errors. The 29 warnings that would have tripped it were fixed at their
  source, and the one exemption (`PluggyTeardownRaisedWarning`) is removed now that Wesker 1.1.1 fixes it.
- `subprocess.run` calls state `check=`; ty 0.0.80 clean; ruff 0.16.7.
- Two diff-parsing regexes in `synthesis/oracle_light.py` no longer backtrack super-linearly (possessive
  quantifiers). Their matches are unchanged, checked against the old patterns on 207,381 generated inputs.
- ruff passes over the whole tree, not only the package and tests: the paper's build script (whose output
  is byte-identical) and the parked MCP tests. deptry is configured for the `Wesker` import name.

### Security

- Workflows pin actions to commit SHAs, run with read-only tokens, do not persist checkout credentials,
  and are audited by zizmor; CodeQL on push, pull request and weekly; GitHub releases are Sigstore-signed.
- CI installs with `uv sync --locked` and runs every later step with `--no-sync --no-build`, so nothing
  is resolved, installed or built after the install step; zizmor installs with `--no-build`.
- `scripts/check_sdist.py` opens only an sdist in the repository's own `dist/`, rebuilt from a matched
  file name. Any other argument exits 2 rather than being opened as given.
- `SECURITY.md` (private reporting through the Security tab) and `CONTRIBUTING.md`.

## 1.1.0 — 2026-09-11

Requires **`Wesker>=1.1.0`** — a silent-degrade floor, so it is worth reading `dev/DEPENDENCY_FLOORS.md`
before relaxing it. Three defects closed, each the same shape: a measurement that existed and a
decision that never consumed it.

### A receipt is bound to the QUESTIONS it was measured under

`RewriteReceipt` has always recorded `policy_id`, and nothing read it back — verified with the
language server, which found the writer and three test constructors and no production consumer. So a
receipt taken under one mutation policy could be verified after a policy bump, with the
new-dimension scan asking a different set of questions than the verdict spoke for.

**New verdict `POLICY_MOVED`** (exit 2, the precondition class) refuses before anything is measured.
`policy_identity` keeps four states apart, because the ways to be unable to compare do not share a
remedy: `match`, `moved`, `unrecorded` (the receipt names no policy), and `unversioned` (the engine
cannot name its own).

### The argument-order budget is disclosed — and reaches the verdict

Wesker 1.1.0 counts the argument-order questions its budget declines. Detective now reads that
count (it referenced the operator census in **zero** places before), decides on it once, and renders
it on both the banner and the archived report plus `--json`.

It also reaches the preservation verdict, which is the half that matters: a baseline with unasked
argument-order questions **cannot** yield PRESERVED. Measured before the fix — a six-argument
wrapper whose suite is degenerate across the withheld pair returned `PRESERVED`, exit 0, for a
rewrite computing 66 where the original computes 91. It now returns `ABSTAIN`, exit 3, carrying a
structured `reason` so the advice names the remedy that applies: re-running will not change a
withheld baseline, and saying "re-run" there would be an instruction that cannot work.

**The gate sits BELOW the CHANGED branch, deliberately.** A difference is a direct observation —
both implementations executed at a concrete input — not an inference from baseline quality, so a
weak baseline must never suppress it. Folded in above, a rewrite that provably broke something would
report ABSTAIN and hide the very difference a supplied input was requested to expose.

### Absence stops reading as zero

A missing operator census reported `(0, 0)` — so "the engine measured and withheld nothing" and "no
engine told us" reached the reader identically. That was pinned as intended behaviour by a test
this release deletes. The census read now carries availability, the disclosure has a fourth
`unavailable` state checked first, and it is never phrased as a count. At the serialization
boundary `RewriteReceipt.swap_budget` defaults to `None`, not to a state, so a receipt predating the
field stays UNKNOWN rather than silently asserting that nothing was withheld.

### Quality

Local SonarQube new-code gate to OK / 0 bugs / 0 vulnerabilities / 0 hotspots — 60 findings cleared,
including all 17 cognitive-complexity refactors (`_flow_stmt` came down from 68 to a handler table
over statement families, every rule body unchanged). Behaviour is unchanged throughout; the suite
went from 3237 to 3268 passing.

## 1.0.0 — 2026-09-09

First stable release. 113 commits since 0.13.0 (2026-08-27). Requires `Wesker>=1.0.0`.

Two things arrived in this window that the earlier versions did not have: a **second half** — the
style layer, which puts stylistic judgement on the same measurement basis as the proofs — and a
**third surface**, `doctor`, which reads the operator rather than the code. A correctness wave
between them repaired eleven defects that shared one shape.

### `detective doctor` — the operator axis

A tool that cannot be *measured* wrongly can still be *used* wrongly, and that is the residual
failure mode of everything else here. The motivating case is on the record: two dependencies
installed mid-session went to a different interpreter than the run used, and the report — correct in
every particular — described a state its reader believed he had already left.

- Three axes, and the mix is the default: **green** (setup — present damage, works alone), **red**
  (process — what the operator did, completes green), **yellow** (taste — what caps how much of the
  tool is reachable). All four superadditive products are live: G+R suppression, G+Y unreliability,
  R+Y ordering, G+R+Y ordered remediation.
- **Cross-interpreter dependency probe.** Names the missing package *and* the interpreter that
  already has it — the inference the operator has no reason to make.
- **The signpost.** The static taste verbs (`plan`, `survey`, `extract`, `parsimony`, `censor`) now
  say when a setup fault outranks the verdict they were about to give, because the user in the
  failure state is by definition the one who does not know to run a diagnostic. A pre-empted command
  **withholds** its verdict and exits 2; a warning a reader can act past is not a pre-emption.
- **The fence:** doctor never speaks about your code. The moment it did it would inherit the
  measurement/verdict conflation the rest of the tool exists to refuse.

### The invocation ledger

`.detective/ledger.jsonl` — append-only, per project, gitignored, never purged by `purge` because
history is not regeneratable by re-running. It makes questions about the *operator* decidable
instead of inferred: did you run the same command again with nothing changed; did you run the taste
half before behaviour was pinned; did the interpreter change under you.

- Recorded from one `try/finally` call site in `main`, which is what makes **refusals** land — a
  tail append misses the three typed-refusal paths, and "you pointed at a target that does not
  exist, three times" is exactly a process finding.
- **`outcome` records the named ending**, so red says *"you got `fix_load` each time"* rather than
  *"you ran this three times"*. Only the first names what to stop doing.
- `purge --prune` exists for a user who wants the history gone, and it asks. Anything that is not an
  explicit yes is a no; a closed stdin is never consent.

### The style layer (`plan`)

Stylistic judgement, on the same measurement basis as the proofs, and never a gate.

- **`detective plan`** — the entry verb for the style half's per-function read. `parsimony` keeps
  its own job and its own name: the static repo/module/class map, which takes a path, claims no
  proof, and is the one repo-scale surface in the tool.
- Seven lenses vote ternary and are **never averaged**: a weighted sum of incommensurable axes is
  how code-quality scores lie. A smell is reported only where **two independent lenses agree**; one
  support is `AMBIGUOUS` and escalates to the driver, which is where taste lives.
- **The informational zero.** A lens with nothing to say votes 0, never against. Cleanliness on one
  axis is not evidence against fixing another, and a lens whose input was never measured votes 0 —
  *we did not measure this* and *we measured it and it is clean* must never render identically.
- **`flag --style`** records a defeasible style judgement on its own ledger; **`verify-rewrite
  --budget`** rides the paired opcode read beneath the gate it belongs to, and can only ever move a
  PRESERVED 0 to a 3, never a 1 to anything.
- **`detective survey`** — the static pure-decision-in-impure-shell detector, with usage-based
  parameter inference behind it.

### Correctness

Eleven repairs, and they turned out to be one shape: *a claim that holds over the subspace where it
was checked, with nothing recording that the subspace was a subspace.*

- **A target that never imported cannot support a certificate.** It was producing no cut reason at
  all, so `admits_certificate` stayed true and converge answered `AUTHOR INPUTS` at exit 0 over a
  module that could not run. Supplying the requested inputs returned byte-identical output — a
  printed instruction that could not change the state it described.
- **One shared measurement-block route, wired to every renderer.** `converge`, `audit` and — as of
  this release — `diagnose`, which had attributed a load failure to *absent tests* and routed the
  reader to a `converge` that refuses for the import.
- **`measurement_invalid`**: an invalid measurement is a RECORD, not an absence, and the only status
  whose remedy is nothing. It previously read as *no certificate exists*, which prescribed the
  converge that produced it.
- **Three mutant-phase failures split apart** — construction, installation, entry — each with its
  own remedy, where one sentence had named only the first.
- **Multi-reason cuts disclose every live reason**, and lead with the one Wesker's own phase
  precedence puts first; the ladder had been inverting its engine.
- **The load-failure exit-code contract is chosen and pinned**, with the rule underneath: a verb may
  exit 0 here only because it *names* the cause.
- **A golden of a BLAS result is a platform-specific observation** and now says so. The pin stays
  exact; the generated suite records the platform and backend it was observed under, so a last-ULP
  mismatch elsewhere reads as a different platform before it reads as a regression.

### Housekeeping

- The README is the story now; the operational reference lives in `ARCHITECTURE.md`.
- A fourth theory paper, `docs/theory/COMMUNICATING_DETERMINISM.md`, on the command surface as an
  information channel with its own correctness criterion.
- A standing guard that every pinned pure decision is consumed in production or carries a written
  reason naming what does consume it. Two were neither.
- `pylint`-as-Sonar configuration and the local SonarQube recipe in `pyproject.toml`, so the
  pre-push gate is reproducible rather than reconstructed.
- **The sdist is checked against git rather than trusted to an exclude list.** This release was one
  command from publishing a 38 MB sdist, 110 MB of it vendored Lean build output that `git status`
  never showed. The size was the symptom; the defect is that such an artifact is a function of the
  builder's working tree rather than of the commit, so the same `uv build` on the same sha ships
  different tarballs to different people. The cause is worth stating because it is invisible from
  the outside: hatchling's VCS-ignore default reads the **root** `.gitignore` only — a nested one
  is not consulted — so a path can be genuinely gitignored and packaged at the same time. Measured
  with a probe project rather than inferred. `scripts/check_sdist.py` now fails on any sdist member
  git does not track, in CI and in the pre-push gate, and the decision under it is pinned.

### Known limits

Unchanged and stated rather than fenced. It preserves behaviour, not correctness. Impure code is
declined with the remedy named. It invents no domain values. A failed search proves nothing — an
undistinguished survivor stays `UNPROVEN`. One function at a time, always.

Open work is tracked as issues and indexed in `docs/OPEN_ITEMS.md`.

---

Earlier releases predate this file. `git log` is the record.
