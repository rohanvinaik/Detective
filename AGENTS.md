# Working on Detective (and Wesker)

Canonical and tool-neutral: `CLAUDE.md` imports this file and adds only Claude Code's own lines; other agents read it
directly. It extends the global instructions (rendered for each client from `~/Projects/SquishOS/ops/agents/`), which
already carry Serena-first/grep-last and Detective-pinning-first; neither is restated here. What follows is specific
to **this pair**.

**The unit is ONE function's operators and ONE function's tests.** Anything that scales with the suite or the repo is a
category error, not a slow path. Read `ARCHITECTURE.md` §11 (the one-function law) before reasoning about
architecture, performance, caching or scoping.

## Driving Detective/Wesker

You are the hands, not the head. Run the command, read the ENTIRE output, and do exactly what the final block says.
The protocol is the global reference `~/Projects/SquishOS/ops/agents/reference/detective-protocol.md` (reached from
the global routing index). Read it before the first command. The SquishOS hooks refuse two things in any spelling:
filtering Detective's or Wesker's output, and printing their exit status in its place.

## Standing invocation

Detective and Wesker are a published-dependency pair, developed together. Both resolve through PYTHONPATH — the LOCAL
repos, never the PyPI install:

```bash
export PP=/Users/rohanvinaik/tools/Detective:/Users/rohanvinaik/tools/Wesker
```

Every `detective` and every `pytest` invocation carries it, and runs under the project's OWN environment:
`.venv/bin/python` and `.venv/bin/detective`.
- **What it is.** The uv-managed CPython 3.14 that `uv sync` builds from `uv.lock` (`[tool.uv] python-preference =
  "only-managed"`). It is what CI runs: `uv sync --locked`, then `uv run --no-sync pytest`.
- **Never a bare `python3` or a bare `detective`.** On this machine both resolve to miniconda's base, which auto-loads
  eight pytest plugins this project does not declare (measured 2026-10-02). The suite read 25 failed under it on
  2026-09-26 (EP-C4) and 1 failed on 2026-10-02, a test whose verdict read the interpreter; that test has since been
  fixed.
- **Versions.** The floor is 3.12 and 3.14 is the standard (founder ruling 2026-09-26). Rebuild with `uv sync` if
  `.venv` is missing.

Prove resolution once per session, before doing any work:

```bash
PYTHONPATH=$PP .venv/bin/python -c "
import Detective, Wesker
print('Detective ->', Detective.__file__)
print('Wesker    ->', Wesker.__file__)
"
```

**Drive Detective through the CLI only.** The MCP surface is parked (`parked/mcp/`); any `mcp__Detective__*` tools come
from an old install.

## Testing Detective on another repo (greenfield dogfood)

Running Detective on a real OUTSIDE repo is how production usability bugs surface; the internal suites cannot, because
they have no foreign dependencies. It found two real advice bugs in one session (`d7177f0`, `77e3b3d`). But it has ONE
non-obvious requirement.

**Detective opens an IN-PROCESS live pytest session under its OWN interpreter.** So the interpreter that runs
`detective` must import BOTH pytest AND the target repo's own dependencies (its `conftest.py` imports them). A bare
global `detective` (miniconda, `~/.local/bin`) usually has neither for a foreign project. Detective then correctly
REFUSES ("could not be collected") rather than measure nothing — that refusal is the tool working.

**Run detective from the TARGET repo's own venv**, the one that has pytest, the project's dependencies and a
`detective` console script (a runtime-only venv without pytest cannot run the suite). Add `PYTHONPATH=$PP` to shadow
the pinned copies with our LOCAL code:

```bash
cd /path/to/target-repo
# pick the venv that has pytest AND the deps, NOT a runtime-only one:
PYTHONPATH=$PP ./.venvXXX/bin/detective diagnose 'src/mod.py::func' > run.log 2>&1
# then Read run.log IN FULL
```

- **Confirm you are running LOCAL code**, not the PyPI build, before trusting the result:
  `PYTHONPATH=$PP ./.venvXXX/bin/python -c "import Detective; print(Detective.__file__)"` must print
  `/Users/rohanvinaik/tools/Detective/...`. `PYTHONPATH=$PP` selects local code and the venv's python selects the
  target's dependencies: two orthogonal knobs, and you need both.
- **Do NOT invoke a bare/global `detective`** for a foreign repo, and do NOT hand-pick a venv that lacks pytest or
  detective.
- **Heavy suites: BACKGROUND the run** and read the full output file. A real repo's live baseline trace and widen can
  take minutes (ARC_AGI_3's story tests take 10–30s each). A short foreground `timeout` CUTS it mid-widen (exit 124),
  and that is NOT a Detective problem.

Worked example — `~/Projects/ARC_AGI_3`: `.venv312` is the capable env (pytest, `arc_agi` and `detective`); `.venv` is
runtime-only (no pytest). Scoping narrowed its 96 test files to 9 function-routed tests for one target, the
sparse-repo scoping win.

## The per-issue loop

Read every issue body in ONE call, not one `gh issue view` per issue. Then build a task queue with real dependency
edges and work in dependency order:

```bash
gh issue list --state open --limit 100 --json number,title,body
```

Prioritize from the *current* issue bodies: not from theory docs, and not from previously implemented epics.

Then, per issue:

1. **Claim the task.**
2. **Probe the mechanism symbolically:**
   - `get_symbols_overview` (an unfamiliar module only);
   - `find_symbol` (prefer `include_info`);
   - **`find_referencing_symbols` before every edit**;
   - a narrow `Read` with offset/limit.

   `find_referencing_symbols` is the load-bearing call. It answers "is this wired, or defined-but-unused?", and it has
   twice proven an issue already half-fixed, saving all the code.
3. **Ground the bug in CURRENT code.** Reproduce the issue's own worked example and read `converge --json`. Prove the
   defect is live before fixing a ghost.
4. **Extract the pure decision** (see below) and pin it.
5. **Wire it** into the impure boundary.
6. **Write hand-written intent tests** (see below).
7. **Gate**: the full suite and pinned ruff (below).
8. **Commit as a checkpoint.** Push per wave, after asking.
9. **Close with evidence**: the sha, the pinned decision, the verification.

## Extracting the pure decision — the crux

The pin target is **manufactured, not found**.

`--input` parses a **literal allowlist** on purpose; that is what makes "no arbitrary code execution" checkable. So a
parameter typed `Any`, a callable or an object is *inexpressible*, and every branch behind it is unreachable by input
synthesis. When converge reports a gap on such a branch, the fix is not more inputs. It is to split the decision out so
it takes only `str` / `bool` / `int` / `list[str]` / `dict`.

Conventions for the extracted function:

- Return a **named string code**, not a bool — `write` / `refuse_foreign` / `refuse_unowned`; `admissible` /
  `observed` / `none_admissible`. Two conditions that mean different things must not collapse into one truthy check;
  that conflation has been the actual bug more than once.
- Place it with `insert_before_symbol` / `insert_after_symbol` directly beside the impure function it serves. The
  accessor keeps the object handling and holds no decision of its own.
- Tag the docstring `(#NN, pure — pinned)`, stating why the split was needed.

Precedent to imitate: `audit_gate_exit`, `receipt_load_refusal`, `line_proof_basis`, `write_disposition`,
`resolve_test_id`.

**Not everything gets a pin.** Pure I/O (atomic writes, quarantine) gets hand-written durability tests only. If a
function can't be pinned, skip it; impure ones route to needs-fixture and get ordinary unit tests.

## Running converge

Bare first, to find the gap:

```bash
PYTHONPATH=$PP .venv/bin/detective converge 'Detective/converge.py::line_proof_basis' > run.log 2>&1
# then Read run.log IN FULL — never tail it
```

Then follow the `DO THIS` block **literally** — one `--input` per uncovered line, read straight off the `Uncovered`
conditions — and re-run until `✓ COMPLETE`:

```bash
PYTHONPATH=$PP .venv/bin/detective converge 'Detective/certify.py::write_disposition' \
  --input "(True, 'other.py::f', 'mine.py::f')" \
  --input "(True, '', 'mine.py::f')" > run.log 2>&1
# then Read run.log IN FULL — never tail it
```

- Compute real digests and paths rather than inventing them (`D=$(python3 -c "import hashlib;...")`).
- Read `converge --help` for the input grammar rather than guessing it.
- `modulo N unproven-equivalent` **counts as done**. Candidate-equivalents are undecidable and get resolved by
  `detective flag`, never by grinding.
- A stale generated golden is **regenerated, not hand-patched**: `rm` the `*_synth.py` and re-run converge.
- Clear the caches between runs, so that neither a cached verdict nor a recalled `--input` can mask a change:
  `rm -f .detective/inputs.json .detective/pins.json .detective/verdict_cache.json`.
  - These are **FILES, not directories**. The old `.detective/pins` / `.detective/samples` PATHS DO NOT EXIST, so
    `rm -rf`-ing them is a silent no-op that leaves supplied inputs recalled.
  - Measured: converge kept re-applying stale `--input`s across runs, masking the true no-input behaviour.
- Every command resolves the testing **regime** first and REFUSES on a shadowed target or a conflicting conftest. A
  refusal is the tool working; `detective regime` is where the reason is. Never work around it.

## Generated tests are a characterization, not a review

Detective says so itself when no pre-existing test reached the function: the suite pins what the code *does*, so
**anything wrong today is now pinned wrong**. Every issue therefore also gets a hand-written intent test file whose
module docstring states the defect and cites the issue number. Only tests written from intent can catch a wrong
implementation pinned wrong.

## Gates before every commit

Ruff is **pinned to 0.16.7 via uvx**, the same version as the dev-group pin CI installs. Never use bare `ruff`: an
unpinned local ruff is not the CI gate.

```bash
PYTHONPATH=$PP .venv/bin/python -m pytest; echo "SUITE=$?"
uvx ruff@0.16.7 format Detective tests
uvx ruff@0.16.7 check Detective tests; echo "CHECK=$?"
uvx ruff@0.16.7 format --check .; echo "FORMAT=$?"
```

**The format check is WHOLE-TREE (`.`), not `Detective tests`**, because CI's is
(`.github/workflows/ci.yml`: `uv run ruff format --check .`). Its comment records why: *"#34: docs/theory/*.py drifted
unformatted for a release because the gate did not reach docs/."* Scoped to the two package dirs, this gate is
NARROWER than the one that decides the build, so a file elsewhere passes locally and reddens CI. Measured 2026-09-08:
`docs/theory/operator_completeness/submission/build_knowability.py` arrived unformatted, passed the scoped gate, and
was pushed. `check` stays scoped (it is the code gate); `format --check` matches CI.

**Read each exit code; never `| tail` a gate before `&& git commit`.** The pipe makes the shell report the filter's
status, so you commit over a failure that printed and was discarded.

**After any Wesker change, also run Detective's suite against the local Wesker.** Wesker's own suite has been fully
green through a regression that only the cross-repo run caught:

```bash
PYTHONPATH=$PP .venv/bin/python -m pytest
```

**Run pytest BARE; do not add `-q`.** `[tool.pytest.ini_options] addopts` already carries `-q --strict-markers
--strict-config`, so a second `-q` becomes `-qq`, which suppresses the summary line entirely: there is then no count to
read for the commit body. CI hit exactly this, and its own workflow comment records it. Run it once, bare, and read the
whole output; the failures and the summary count are both in it.

### Before every PUBLISH: build, then check the artifact against git

```bash
rm -rf dist && uv build --out-dir dist && python3 scripts/check_sdist.py
```

Non-optional, and specifically a LOCAL step. CI runs it too, but CI checks out a clean tree, so the case it cannot see
is the one that actually happened: untracked output sitting in *your* tree and getting swept into the tarball.
Detective 1.0.0 was one command from publishing a 38 MB sdist, 110 MB of it
`docs/theory/operator_completeness/proofs/.lake` — vendored Lean packages, gitignored, invisible to `git status`,
packaged anyway.

Why an exclude list is not enough on its own: **hatchling's VCS-ignore default reads the ROOT `.gitignore` only.** A
nested `.gitignore` is not consulted (measured with a probe project, 2026-09-09), so "it's gitignored" is not a reason
to believe it will not ship. The checker asks git what it *tracks* instead: an sdist member is either tracked or
backend-generated, with no third category. Exit `1` is a measured defect; `2` is "could not ask" (no sdist, not a
checkout).

### Before every PUSH: pylint-as-Sonar, then the REAL Sonar, locally

Ruff is the commit gate. A push needs two more passes, in this order, and neither is optional (2026-09-06: both were
skipped once and the founder noticed):

1. `uvx --python 3.14 pylint Detective`, reproducible from `[tool.pylint]` in pyproject (tuned to Sonar's ruleset, not
   pylint's defaults). Fix what is genuine in the code you wrote.
   - Known residue, not findings: the house `except Exception:  # noqa: BLE001` guard and the big orchestrators'
     statement counts.
   - Also residue: `E1101` on `sys.monitoring` members. Pylint's inference library does not model `sys.monitoring`
     at all; measured 2026-10-01, it is still reported under 3.14, so the 3.12 floor does NOT remove them (an earlier
     note said it did).
   - `--python 3.14` runs pylint under the project's interpreter; bare `uvx pylint` picks its own.
2. The local SonarQube: the persistent Docker container `peitho-sonar` at `localhost:9000` (shared with Peitho and
   Wesker; credentials in `~/.config/detective/sonar-local.env`, minted once — never re-mint per session). Coverage
   first, then the scanner, then read the gate by API:

   ```bash
   uv run --no-sync python -m pytest tests/ --cov=Detective --cov-report=xml:coverage.xml
   set -a && . ~/.config/detective/sonar-local.env && set +a
   docker run --rm -e SONAR_HOST_URL=http://host.docker.internal:9000 -e SONAR_TOKEN="$SONAR_TOKEN" \
     -v "$PWD:/usr/src" sonarsource/sonar-scanner-cli -Dsonar.organization=
   curl -s -u "$SONAR_TOKEN:" "$SONAR_HOST_URL/api/qualitygates/project_status?projectKey=rohanvinaik_Detective"
   ```

   - **Poll before reading the gate.** The scanner returns before the server has processed the report: poll the task
     the scanner names (`api/ce/task?id=<id>`, from its last log lines) until `SUCCESS`. `api/ce/component` can answer
     with the PREVIOUS task's SUCCESS (measured: an unchanged verdict read back as if the rescan had run).
   - **House form for a suppression comment:** the REASON goes on its own line ABOVE, as `# CODE: <reason>`, and the
     code line carries a BARE `# noqa: CODE`.

     ```python
     # BLE001: the plan is advisory; a region the engine chokes on is unpriced rather than fatal
     except Exception:  # noqa: BLE001
     ```

     Sonar (S7632) parses EVERYTHING after `# noqa:` as a code list, so any trailing prose is a syntax error to it,
     comma or not. Ruff honours both forms (measured: `--isolated --select BLE001` suppresses under either, and fires
     with neither), so no suppression was ever inert; this form simply satisfies both tools.
     - CORRECTED 2026-09-08: this rule previously said the trigger was a COMMA in the reason. That was wrong:
       `plan.py:91` used a semicolon, `engine.py:237` had no punctuation at all, and both were flagged.
     - So the 2026-09-06 sweep removed commas and left the real trigger in 66 places. All 70 have since migrated to the
       form above, and no noqa comment now carries trailing prose (`docs/CORRECTNESS_REPAIRS_2026-09-08.md` §S12).
   - `sonar-project.properties` is read; `relative_files = true` in `[tool.coverage.run]` is what lets the container
     resolve the report.
   - **Bar: gate `OK`, 0 bugs, 0 vulnerabilities, 0 hotspots.** Expected residue is handled by API transition WITH a
     comment, never silently:
     - S3776 on the intentional essential-complexity orchestrators (`accept`);
     - S5863 on the deliberate `f(x) == f(x)` determinism checks in tests (`falsepositive`).

     Composite-assertion smells (S9073) are a Quality Profile decision for the founder, not a per-session fix.

## Commits

Heredoc essay, never `-m`. Subject `fix(#NN):` / `feat(#NN):` describing the behaviour change. The body, in order:
1. the defect verbatim;
2. why the obvious fix is wrong;
3. what each state of the pure decision means;
4. **what was NOT closed**;
5. the pin receipt (`✓ COMPLETE … N/M killed`);
6. the suite count and `ruff … clean under pinned 0.16.7`.

No AI attribution (the global rule). Note `fix(#NN):` does **not** auto-close on GitHub; close explicitly, with
evidence.

## Dogfooding Detective on itself

Detective can analyze its **own** source only via a renamed package copy (`DetectiveUUT/`), because `sys.modules` is
keyed by dotted name. Pointing it at the live tree silently degrades to an empty namespace and returns a profile that
looks fine and means nothing. Three constraints bite:
- **Do the rename with perl, not sed.** BSD `sed` has no `\b`, so a `sed` rename silently no-ops and exits 0. Use
  `perl -pi -e 's/\bDetective\b/DetectiveUUT/g'`, which also covers the path strings
  (`"Detective/scope.py"`), not just the dotted imports.
- **Do not copy the root `conftest.py`.** Register the `detective` marker in the copy's `pyproject.toml` instead.
- **Read the right pass signal.** It is `tests_discovered`, not the trace count.

This does not affect pinning ordinary functions in this repo via `converge`; it applies to whole-package
self-profiling.

## Scope boundaries

- **Publishing, version bumps, publish order, and closing issues are the user's domain.** Never publish to PyPI. Don't
  produce unrequested release advisories.
- Fixes must be **general**, not idiomatic to whatever repo surfaced them; they should hold for arbitrary code.
- Don't stop to offer menus when told to proceed. Don't rank "cheap" against "the one the issue actually names" and
  then pick cheap.
- Before a redesign, ground it in executing code first, and report if grounding changed the plan — before writing any
  of it.

## Two recorded failure modes

1. **Verification must be adversarial.** An external review found 4 real gaps after a program was declared complete,
   all because testing covered happy paths and primary repros but not null, invalid or edge inputs (an invalid
   receipt, a forced exception, a deadline crossing the final mutant).
2. **Trace the signal all the way to the decision.** The measurement/decision gap hides at EVERY layer: engine → loop →
   aggregation → gate/badge. Each layer must **consume** the computed signal, never re-derive a narrower proxy. Verify
   end-to-end, not per-layer.
