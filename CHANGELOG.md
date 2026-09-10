# Changelog

Notable changes, newest first. Dates are the commit dates.

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

### Known limits

Unchanged and stated rather than fenced. It preserves behaviour, not correctness. Impure code is
declined with the remedy named. It invents no domain values. A failed search proves nothing — an
undistinguished survivor stays `UNPROVEN`. One function at a time, always.

Open work is tracked as issues and indexed in `docs/OPEN_ITEMS.md`.

---

Earlier releases predate this file. `git log` is the record.
