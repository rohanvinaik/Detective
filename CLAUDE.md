# Working on Detective (and Wesker)

Extends the global CLAUDE.md — Serena-first/grep-last and Detective-pinning-first are
assumed there and not repeated. What follows is what is specific to **this pair**.

Read `~/.claude/projects/-Users-rohanvinaik-tools-Detective/memory/feedback_sandwich_thesis.md`
BEFORE reasoning about architecture, performance, caching, or scoping. The unit is ONE
function's operators and ONE function's tests. Anything that scales with the suite or the
repo is a category error, not a slow path.

## Standing invocation

Detective and Wesker are a published-dependency pair, developed together. Both resolve
through PYTHONPATH — the LOCAL repos, never the PyPI install:

```bash
export PP=/Users/rohanvinaik/tools/Detective:/Users/rohanvinaik/tools/Wesker
```

Every `detective` and every `pytest` invocation carries it. Prove resolution once per
session before doing any work:

```bash
PYTHONPATH=$PP python3 -c "
import Detective, Wesker
print('Detective ->', Detective.__file__)
print('Wesker    ->', Wesker.__file__)
"
```

**Drive Detective through the CLI only.** The `mcp__Detective__*` tools are stale and unused.

## Testing Detective on another repo (greenfield dogfood)

Running Detective on a real OUTSIDE repo is how production usability bugs surface — the
internal suites cannot, because they have no foreign dependencies. It found two real advice
bugs in one session (`d7177f0`, `77e3b3d`). But it has ONE non-obvious requirement.

**Detective opens an IN-PROCESS live pytest session under its OWN interpreter.** So the
interpreter that runs `detective` must import BOTH pytest AND the target repo's own deps (its
`conftest.py` imports them). A bare global `detective` (miniconda / `~/.local/bin`) usually
has neither for a foreign project, so Detective correctly REFUSES ("could not be collected")
rather than measure nothing — that refusal is the tool working.

**Run detective from the TARGET repo's own venv** — the one that has pytest + the project's
deps + a `detective` console script (a runtime-only venv without pytest cannot run the suite)
— with `PYTHONPATH=$PP` to shadow the pinned copies with our LOCAL code:

```bash
cd /path/to/target-repo
# pick the venv that has pytest AND the deps, NOT a runtime-only one:
PYTHONPATH=$PP ./.venvXXX/bin/detective diagnose 'src/mod.py::func'
```

- **Confirm you are running LOCAL code**, not the PyPI build, before trusting the result:
  `PYTHONPATH=$PP ./.venvXXX/bin/python -c "import Detective; print(Detective.__file__)"` must
  print `/Users/rohanvinaik/tools/Detective/...`. (`PYTHONPATH=$PP` = local code; the venv's
  python = the target's deps. Two orthogonal knobs — you need both.)
- **Read the CLI output DIRECTLY and in FULL — never `| tail`.** A refusal names the exact
  interpreter and the fix; that IS the instruction to act on.
- **Do NOT invoke a bare/global `detective`** for a foreign repo, and do NOT hand-pick a venv
  that lacks pytest/detective.
- **Heavy suites: BACKGROUND the run** and read the full output file. A real repo's live
  baseline trace + widen can take minutes (ARC_AGI_3's story tests: 10–30s each); a short
  foreground `timeout` CUTS it mid-widen (exit 124) and is NOT a Detective problem.

Worked example — `~/Projects/ARC_AGI_3`: `.venv312` is the capable env (pytest + `arc_agi` +
`detective`); `.venv` is runtime-only (no pytest). Scoping narrowed its 96 test files to 9
function-routed tests for one target — the sparse-repo scoping win.

## The per-issue loop

Read every issue body in ONE call — not one `gh issue view` per issue — then build a task
queue with real dependency edges (`addBlockedBy`) and work in dependency order:

```bash
gh issue list --state open --limit 100 --json number,title,body
```

Prioritize from the *current* issue bodies. Not from theory docs, not from previously
implemented epics.

Then, per issue:

1. **Claim the task**, `activate_project` on repo switch.
2. **Serena-probe the mechanism.** `get_symbols_overview` (unfamiliar module only) →
   `find_symbol` (prefer `include_info`) → **`find_referencing_symbols` before every edit** →
   narrow `Read` with offset/limit. `find_referencing_symbols` is the load-bearing call: it
   answers "is this wired, or defined-but-unused?" and has twice proven an issue already
   half-fixed, saving all the code.
3. **Ground the bug in CURRENT code.** Reproduce the issue's own worked example and read
   `converge --json`. Prove the defect is live before fixing a ghost.
4. **Extract the pure decision** (see below) and pin it.
5. **Wire it** into the impure boundary.
6. **Write hand-written intent tests** (see below).
7. **Gate**: full suite + pinned ruff.
8. **Commit as a checkpoint.** Push per-wave.
9. **Close with evidence** — sha, pinned decision, verification.

## Extracting the pure decision — the crux

The pin target is **manufactured, not found**.

`--input` parses a **literal allowlist** on purpose — that is what makes "no arbitrary code
execution" checkable. So a parameter typed `Any`, a callable, or an object is *inexpressible*,
and every branch behind it is unreachable by input synthesis. When converge reports a gap on
such a branch, the fix is not more inputs — it is to split the decision out so it takes only
`str` / `bool` / `int` / `list[str]` / `dict`.

Conventions for the extracted function:

- Return a **named string code**, not a bool — `write` / `refuse_foreign` / `refuse_unowned`;
  `admissible` / `observed` / `none_admissible`. Two conditions that mean different things
  must not collapse into one truthy check; that conflation has been the actual bug more than
  once.
- Place it with `insert_before_symbol` / `insert_after_symbol` directly beside the impure
  function it serves. The accessor keeps the object handling and holds no decision of its own.
- Docstring tagged `(#NN, pure — pinned)`, stating why the split was needed.

Precedent to imitate: `audit_gate_exit`, `receipt_load_refusal`, `line_proof_basis`,
`write_disposition`, `resolve_test_id`.

**Not everything gets a pin.** Pure I/O (atomic writes, quarantine) gets hand-written
durability tests only. If a function can't be pinned, skip it — impure ones route to
needs-fixture and get ordinary unit tests.

## Running converge

Bare first, to find the gap:

```bash
PYTHONPATH=$PP detective converge 'Detective/converge.py::line_proof_basis' 2>&1 | tail -8
```

Then follow the `DO THIS` block **literally** — one `--input` per uncovered line, read
straight off the `Uncovered` conditions — and re-run until `✓ COMPLETE`:

```bash
PYTHONPATH=$PP detective converge 'Detective/certify.py::write_disposition' \
  --input "(True, 'other.py::f', 'mine.py::f')" \
  --input "(True, '', 'mine.py::f')" 2>&1 | tail -8
```

- Compute real digests/paths rather than inventing them (`D=$(python3 -c "import hashlib;...")`).
- Read `converge --help` for the input grammar rather than guessing it.
- `modulo N unproven-equivalent` **counts as done** — candidate-equivalents are undecidable
  and get resolved by `detective flag`, never by grinding.
- A stale generated golden is **regenerated, not hand-patched**: `rm` the `*_synth.py` and
  re-run converge.
- Clear the caches between runs so a cached verdict OR a recalled `--input` can't mask a change:
  `rm -f .detective/inputs.json .detective/pins.json .detective/verdict_cache.json`. These are
  FILES, not dirs — the old `.detective/pins` / `.detective/samples` PATHS DO NOT EXIST, so
  `rm -rf`-ing them is a silent no-op that leaves supplied inputs recalled (measured: converge kept
  re-applying stale `--input`s across runs, which masked the true no-input behaviour).
- Every command resolves the testing **regime** first and REFUSES on a shadowed target or
  conflicting conftest. A refusal is the tool working; `detective regime` is where the reason
  is. Never work around it.

## Generated tests are a characterization, not a review

Detective says so itself when no pre-existing test reached the function: the suite pins what
the code *does*, so **anything wrong today is now pinned wrong**. Every issue therefore also
gets a hand-written intent test file whose module docstring states the defect and cites the
issue number. Only tests written from intent can catch a wrong implementation pinned wrong.

## Gates before every commit

Ruff is **pinned to 0.14.10 via uvx**, never bare `ruff` — the local newer one showed 125
spurious errors and is not the CI gate.

```bash
PYTHONPATH=$PP python3 -m pytest 2>&1 | tail -1 \
  && uvx ruff@0.14.10 format Detective tests 2>&1 | tail -1 \
  && uvx ruff@0.14.10 check Detective tests 2>&1 | tail -3 \
  && uvx ruff@0.14.10 format --check Detective tests 2>&1 | tail -1
```

**After any Wesker change, also run Detective's suite against the local Wesker.** Wesker's own
suite has been fully green through a regression that only the cross-repo run caught:

```bash
PYTHONPATH=$PP python3 -m pytest 2>&1 | tail -3
```

Run pytest twice — once with `-q` to see failures, once bare with `| tail -1` to capture the
exact count that goes into the commit body.

## Commits

Heredoc essay, never `-m`. Subject `fix(#NN):` / `feat(#NN):` describing the behaviour change.
Body: the defect verbatim → why the obvious fix is wrong → what each state of the pure
decision means → **what was NOT closed** → the pin receipt (`✓ COMPLETE … N/M killed`) → suite
count and `ruff … clean under pinned 0.14.10` → the `Co-Authored-By` trailer.

Note `fix(#NN):` does **not** auto-close on GitHub. Close explicitly with evidence.

## Serena cautions specific to these repos

- **Call Serena fresh each time and verify the returned body matches what you asked for.**
- **Avoid `replace_symbol_body`.** Its index drifts on heavily edited files and has silently
  corrupted a source file here. Prefer `include_info` + narrow `Read` + `replace_content`
  with a literal needle. `info` stays reliable when `body` extraction drifts.
- Grep is permitted only to locate a line number for a subsequent `Read` — never to trace
  wiring or find references.

## Dogfooding Detective on itself

Detective can analyze its **own** source only via a renamed package copy (`DetectiveUUT/`),
because `sys.modules` is keyed by dotted name. Pointing it at the live tree silently degrades
to an empty namespace and returns a profile that looks fine and means nothing. Full
constraints — including that BSD `sed` no-ops the rename and reports success — are in
`memory/project_dogfood_harness.md`. Read it before any self-analysis run.

This does not affect pinning ordinary functions in this repo via `converge`; it applies to
whole-package self-profiling.

## Scope boundaries

- **Publishing, version bumps, publish order, and closing issues are the user's domain.**
  Never publish to PyPI. Don't produce unrequested release advisories.
- Fixes must be **general**, not idiomatic to whatever repo surfaced them — they should hold
  for arbitrary code.
- Don't stop to offer menus when told to proceed. Don't rank "cheap" against "the one the
  issue actually names" and then pick cheap.
- Before a redesign, ground it in executing code first, and report if grounding changed the
  plan — before writing any of it.

## Two recorded failure modes

1. **Verification must be adversarial.** An external review found 4 real gaps after a program
   was declared complete, all because testing covered happy paths and primary repros but not
   null/invalid/edge inputs (invalid receipt, forced exception, deadline-crosses-final-mutant).
2. **Trace the signal all the way to the decision.** The measurement/decision gap hides at
   EVERY layer — engine → loop → aggregation → gate/badge. Each layer must **consume** the
   computed signal, never re-derive a narrower proxy. Verify end-to-end, not per-layer.

## After a /compact

Reading the session JSONL is **non-negotiable** when instructed — not the summary. Not the
entire context either: extract user prompts and assistant text responses with timestamps for
the last 1–4 hours, surface relevant tool calls only where needed, write it to a file, and
read it. Skipping this once caused a bad regression: settled grounding was re-derived and a
finished design was re-searched from scratch.
