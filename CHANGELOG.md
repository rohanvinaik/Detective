# Changelog

Notable changes, newest first. Dates are the commit dates.

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
