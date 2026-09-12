# Working on Detective (and Wesker)

Extends the global AGENTS.md — Serena-first/grep-last and Detective-pinning-first are
assumed there and not repeated. What follows is what is specific to **this pair**.

Read `~/.claude/projects/-Users-rohanvinaik-tools-Detective/memory/feedback_sandwich_thesis.md`
BEFORE reasoning about architecture, performance, caching, or scoping. The unit is ONE
function's operators and ONE function's tests. Anything that scales with the suite or the
repo is a category error, not a slow path.

## Driving Detective/Wesker — you are the HANDS, not the head. READ THIS BEFORE THE FIRST COMMAND.

**The thesis of these tools is that using them correctly requires NO intelligence.** Every
command prints, statically, what happened, what it means, and the exact next command to run.
Reading that block and doing what it says IS the protocol; there is nothing else to do. A
few-million-parameter model that reads the block and runs the next line drives this correctly.
Every recorded failure came from a large model deciding it understood the situation better than
the printout — which is self-refuting, because the tool is the thing that knows. **Exercising
judgement here is not a supplement to the protocol. It is the violation of it.**

The frame that PRODUCES the failure: *Detective is an instrument, I am the scientist.* Under it,
a refusal is data about the instrument and forming a hypothesis is the obviously correct move —
which is why this failure feels like rigor from the inside, and why banning one spelling of it
(a pipe, a grep) never helps: the stance re-finds a new route every time. The frame that WORKS:
*Detective is the scientist, I am the hands.* The run is a state machine; the printed block is
the program counter.

> **The entire loop: run the command → read the ENTIRE output → do exactly what the final block
> says → repeat until it prints `DONE` or names no next action.**

- **Never run a command the output did not name; never skip one it did.** On an unfamiliar repo
  the first command is `detective --help`, and its first block is binding (`NEW REPO? START
  HERE: detective regime`). Having read the README, ARCHITECTURE and the theory papers does
  **not** license starting further down — that is prior knowledge substituting for the
  instruction, and it has not once been right.
- **A refusal is a VERDICT, not a bug report.** `STOP` · `UNGATEABLE` · `ABSTAIN` · `UNPROVEN` ·
  exit `2` · exit `3` are the product, and the block names the repair. Apply that repair
  **verbatim**, change nothing else, re-run. Do not diagnose the tool, do not A/B it, and never
  edit the target to make a refusal go away — "editing around" destroys the guarantee the tool
  exists to provide and invalidates the run.
- **If you are forming a theory about WHY it said something, STOP and hand it to the user.** The
  theory IS the failure mode. Report what it printed and what it prescribed; let them decide.
- **Read the whole output. No reduction of any kind, in any spelling, ever.** Not `| tail`,
  `| head`, `| grep`, `sed`, `awk`, `wc -l`, `-q`, "just the FINAL line", not `--json` field
  extraction, not "I'll read the exit code." You cannot know which line carries the verdict
  before you run it — if you could, running it would be pointless. Short run: run it bare, read
  the result. Long run: `> run.log 2>&1`, then `Read run.log` **in full**; the complete static
  report is always also at `.detective/reports/<verb>_<fn>.txt`. Capturing to a file and reading
  it whole is not filtering — it is the correct way to handle a long run.
- **One walk per FRESH directory.** Generated tests, `.detective/` caches, `pins.json`, recalled
  `--input`s and receipts are all state. The moment you deviate from the printed path, every
  observation after it is invalid — not "mostly fine." Do not tidy up and continue; start a new
  directory.
- **Never author work the tool did not ask for.** Do not hand-write a rewrite to see what the
  gate says: you then know the answer in advance and are grading the gate against your own
  prior, which is exactly the self-certification the project exists to refuse. A rewrite comes
  from the tool's own path (`decompose --apply`) or from a genuine task — never constructed to
  produce a verdict.
- **Report what it printed, not what you concluded.** Quote the blocks. Any inference on top of
  them is yours, not the tool's, and is labelled as such.

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
PYTHONPATH=$PP detective converge 'Detective/converge.py::line_proof_basis' > run.log 2>&1
# then Read run.log IN FULL — never tail it
```

Then follow the `DO THIS` block **literally** — one `--input` per uncovered line, read
straight off the `Uncovered` conditions — and re-run until `✓ COMPLETE`:

```bash
PYTHONPATH=$PP detective converge 'Detective/certify.py::write_disposition' \
  --input "(True, 'other.py::f', 'mine.py::f')" \
  --input "(True, '', 'mine.py::f')" > run.log 2>&1
# then Read run.log IN FULL — never tail it
```

- Compute real digests/paths rather than inventing them (`D=$(python3 -c "import hashlib;...")`).
- Read `converge --help` for the input grammar rather than guessing it.
- `modulo N unproven-equivalent` **counts as done** — candidate-equivalents are undecidable
  and get resolved by `detective flag`, never by grinding.
- A stale generated golden is **regenerated, not hand-patched**: `rm` the `*_synth.py` and
  re-run converge.
- Clear the caches between runs so a cached verdict OR a recalled `--input` can't mask a change:
  `rm -f .detective/inputs.json .detective/pins.json .detective/verdict_cache.json`. These are
  **FILES, not directories** — the old `.detective/pins` / `.detective/samples` PATHS DO NOT
  EXIST, so `rm -rf`-ing them is a silent no-op that leaves supplied inputs recalled (measured:
  converge kept re-applying stale `--input`s across runs, masking the true no-input behaviour).
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
PYTHONPATH=$PP python3 -m pytest; echo "SUITE=$?"
uvx ruff@0.14.10 format Detective tests
uvx ruff@0.14.10 check Detective tests; echo "CHECK=$?"
uvx ruff@0.14.10 format --check .; echo "FORMAT=$?"
```

**The format check is WHOLE-TREE (`.`), not `Detective tests`** — because CI's is
(`.github/workflows/ci.yml`: `uv run ruff format --check .`), and its comment records why:
*"#34: docs/theory/*.py drifted unformatted for a release because the gate did not reach
docs/."* Scoped to the two package dirs this gate is NARROWER than the one that decides the
build, so a file elsewhere passes locally and reddens CI. `check` stays scoped — it is the code
gate; `format --check` matches CI.

**Read each exit code; never `| tail` a gate before `&& git commit`** — the pipe makes the shell
report the filter's status, so you commit over a failure that printed and was discarded.

**After any Wesker change, also run Detective's suite against the local Wesker.** Wesker's own
suite has been fully green through a regression that only the cross-repo run caught:

```bash
PYTHONPATH=$PP python3 -m pytest
```

**Run pytest BARE. Do not add `-q`.** `[tool.pytest.ini_options] addopts` already carries
`-q --strict-markers --strict-config`, so a second `-q` becomes `-qq`, which suppresses the
summary line entirely — there is then no count to read for the commit body. CI hit exactly this
and its own workflow comment records it.

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
