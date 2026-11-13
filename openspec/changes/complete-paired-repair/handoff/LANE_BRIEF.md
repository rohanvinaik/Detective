<!-- Copied from the cloud session of 2026-11-11..13 that ran the repair lanes. Container paths are replaced by the founder's layout (~/tools/Detective, ~/tools/Wesker). Every rule below is still in force. -->

# Lane brief — Detective/Wesker repair, Wave 1 (read this whole file first)

You are one lane of a parallel repair of two linked Python repos: **Wesker** (a mutation engine) and
**Detective** (which consumes Wesker's mutant profile to write a function's behavioural contract). An
integrator lands your commits; you never push, never touch `main`, never open a PR, never comment on or
close a GitHub issue.

## Where things are

- Your worktree(s) are named in your task. Edit ONLY inside them. Other lanes run concurrently in sibling
  worktrees; do not read conclusions from them or edit them.
- The issue you are fixing is a file under
  `the GitHub issue (`gh issue view`)`
  (`D-<n>.md` Detective, `W-<n>.md` Wesker; body first, then comments). **The issue's top block is the
  current state and its Expected/Acceptance section is the bar.** Read it in full before any code.
- House rules: `AGENTS.md` in each repo (read Detective's fully; Wesker's adds its hazards). Theory that
  decides any question of what a page prints or what counts as a kill:
  `docs/theory/COMMUNICATING_DETERMINISM.md` and `docs/theory/operator_completeness/KNOWABILITY.md` in
  the Detective repo. `ARCHITECTURE.md` §0 and §11 state the thesis and the one-function law.
- This is a Linux cloud container, not the founder's Mac. Paths in AGENTS.md under `/Users/rohanvinaik/…`
  do not exist. Serena, the SquishOS hooks, the local SonarQube container and `~/.claude/.../memory` are
  NOT available here; use Read/Grep/Glob instead of Serena, and skip Sonar. Everything else in AGENTS.md
  applies.

## Invocation (use exactly these interpreters)

```bash
DET=<your Detective tree>   # your worktree if you have one, else ~/tools/Detective (read-only for you)
WES=<your Wesker tree>      # your worktree if you have one, else ~/tools/Wesker (read-only for you)
export PP=$DET:$WES
# Detective's tests / CLI:
cd $DET && PYTHONPATH=$PP .venv/bin/python -m pytest tests/<file>.py
PYTHONPATH=$PP .venv/bin/detective converge 'path.py::func' > run.log 2>&1   # then Read run.log IN FULL
# Wesker's tests:
cd $WES && PYTHONPATH=$PP <Wesker>/.venv/bin/python -m pytest tests/<file>.py
# ruff, pinned:
uvx ruff@0.16.7 --version   # must print 0.16.7; use this binary, never a bare `ruff`
```

- Prove resolution once before working: from a scratch directory (NOT a repo root — the cwd comes before
  PYTHONPATH), `PYTHONPATH=$PP .venv/bin/python -c "import Detective, Wesker; print(Detective.__file__, Wesker.__file__)"`
  must print YOUR trees.
- Run pytest BARE (no `-q`; addopts already carries it). Read whole outputs; never pipe a gate through
  `tail`/`grep` and never judge by exit status alone.
- **Reproductions run in a disposable project directory with a scratch HOME**
  (`mktemp -d` under `/tmp/lane-<yourlane>/`, `HOME=<scratch>`), never inside a repo. A fresh fixture
  project needs `detective regime` then the `regime --migrate` it names, as the issues describe.
- **Do not run the whole suite of either repo.** Four cores are shared by six lanes and the engine's
  budgets are partly wall-clock; a loaded machine produces cuts that are not defects. Run the test files
  you touch plus the neighbouring intent files for the functions you changed. If a measurement shows a
  wall/deadline cut or `undetermined`, re-run it once before believing it. The integrator runs the full
  suites.
- Never delete `.detective/inputs.json` anywhere (user data). `pins.json` / `verdict_cache.json` are
  regeneratable.

## The per-issue method (AGENTS.md has the long form)

1. **Reproduce first, on current code, from the issue's own fixture.** If you cannot reproduce it, stop
   and report exactly what you ran and saw — do not fix a ghost.
2. **Find what is wired.** Before editing a function, find every caller (Grep for the name across both
   repos) and read them. A fix that no consumer reads is not a fix: trace the signal engine → loop →
   aggregation → renderer/gate, and make each layer CONSUME the computed fact instead of re-deriving a
   narrower one.
3. **Extract the pure decision.** Where the fix is a decision, put it in a small function that takes only
   `str` / `bool` / `int` / `list[str]` / `dict` and returns a **named string code** (never a bool where
   two states have different remedies). Place it directly beside the impure function it serves, docstring
   tagged `(#NN, pure — pinned)` and saying why the split was needed. The impure function keeps the
   object handling and holds no decision of its own.
4. **Write a hand-written intent test file** (`tests/test_<topic>_intent.py`) whose module docstring
   states the defect and cites the issue number. Its tests are the issue's own reproduction plus null,
   invalid and edge inputs. Bind the function/module under the name the project's tests normally import
   it by (module-level `from X import f`), not a private re-load.
5. **Prove sensitivity.** With your fix disarmed (git stash, or a scratch copy), the new intent tests
   must FAIL; record how many failed out of how many. Then with the fix, they pass.
6. **Pin the pure decision**: `detective converge '<path>::<function>'` from the repo root of the tree
   that owns it (for a Wesker function, run from your Wesker tree with Detective's `detective`). Follow
   the final `DO THIS` block literally (one `--input` per uncovered line) until `✓ COMPLETE`
   (`modulo N unproven-equivalent` counts as done). Record the final line verbatim. **Do NOT commit what
   converge writes** — `tests/detective/*` (certificates.json, `*_synth.py`), `.detective/`, `.wesker/`,
   or a `pyproject.toml` marker edit. `git checkout`/remove them before committing. The integrator
   regenerates pins on the integrated tree. If converge refuses or cannot reach COMPLETE, report the
   exact final block; do not grind and do not work around a refusal.
7. **Gates on what you changed:** the touched test files green; then
   `uvx ruff@0.16.7 format <changed files>` and
   `uvx ruff@0.16.7 check <repo package dir> tests` clean, and
   `ruff format --check .` clean on the whole tree of each repo you changed.
8. **Commit in your worktree, one commit per issue (or per separable item of an issue).** Heredoc essay,
   never `-m`. Subject `fix(#NN): <the behaviour, stated as what is now true>`. Body, in order: the defect
   verbatim; why the obvious fix is wrong; what each state of the pure decision means; **what was NOT
   closed**; the converge receipt line; the tests run and their counts; `ruff clean under pinned 0.16.7`.
   For a Wesker commit fixing a Detective issue write `(Detective #NN)`. **No AI attribution, no
   Co-Authored-By, no session link, no model name.** Do not `git add -A`; add files by name.

## House conventions that reviewers reject on sight

- A fix must be GENERAL — true for arbitrary code, not shaped to the fixture that surfaced it.
- Absence is not a value: "we did not measure" and "we measured and it is clean" never share a sign, a
  default, or a count. No `getattr(obj, name, default)` that could absorb a renamed fault flag.
- A refusal, cut, timeout, crash of the harness, or anything the original also does is NEVER a kill.
- Suppression comments: the reason on its own line above as `# CODE: <reason>`, the code line carries a
  bare `# noqa: CODE`.
- Never skip, xfail, loosen or delete a test to get green. Never hand-edit a generated `*_synth.py` or
  `certificates.json`.
- No new documentation files. Update an existing doc only where your change makes a sentence in it false
  (e.g. a CHANGELOG entry when a policy id moves).
- If a change moves Wesker's policy id / `POLICY_VERSION` (an observation rule changing can), say so
  loudly in your report and add the CHANGELOG entry; do not avoid a correct fix to dodge the bump.

## Your final report (this is what the integrator reads — be exact, not upbeat)

For each issue: (a) reproduced? the command and the before-output lines that show the defect;
(b) what you changed, file:function, and each new pure decision with its codes; (c) the after-output for
the same reproduction; (d) sensitivity: N of M intent tests fail with the fix disarmed; (e) the converge
final line per pinned function, or the refusal block; (f) test files run and counts; ruff results;
(g) commit sha(s) and branch; (h) **every acceptance item of the issue marked met / not met / not
verified**, and anything you noticed that is a separate defect (describe, do not fix). If you ran out of
road, say where. Do not claim an item you did not run.

## Wave 2 addendum (read after the above; it overrides where they differ)

- Both mains moved: Wesker `fb2f8b4` (policy one-sign `9.008828e5f6a9`, two-sign `9+neg.1a13fddd1d5f`), Detective
  `c62c790` whose lock pins that Wesker. Your worktree was cut from the current main. `.venv` interpreters are
  unchanged: `.venv/bin/python` and `<Wesker>/.venv/bin/python`.
- If you have only a Detective worktree, your read-only Wesker is `~/tools/Wesker` (main). If you have only a
  Wesker worktree, your read-only Detective is `~/tools/Detective` (main). Never edit a tree that is not yours.
- Detective's full suite now takes about 15 minutes. Do not run it. Run the files you touch and their neighbours.
- A converge whose routed tests spawn CLI subprocesses can end `UNGATEABLE — the profile was cut`: re-run it once
  with `--deadline 900`; if it is still cut, report the final block and move on (the integrator pins on an idle
  machine). Never commit generated pin files.
- Wave 1 added vocabulary you may meet: the unscored reason `original_also_fails` (three spellings in
  `Detective/validity.py`), `shared_arguments`, `cover_standing`, `distinguishing_fact`, and the decorator
  `@restores_process_state(declared_roots)` on library entries. Another lane is replacing Detective's per-test kill
  relation (`audit.measure_per_test_kills`, `minimize.cover_standing`'s inputs) with a one-pass relation from
  Wesker: stay out of `Detective/minimize.py` and the kill-relation functions in `Detective/audit.py`.
- Wave 2 is about PAGES THAT SAY SOMETHING FALSE. The law is `docs/theory/COMMUNICATING_DETERMINISM.md` §3-§5 and
  §9: two states whose remedies differ never share a sign; a `DO THIS` is a claim that this next command changes
  what is known, so it never names a command that will do nothing or that was already run; a verb exits 0 only if
  it names the cause of anything it could not establish; absence and emptiness never render alike. For every item,
  the acceptance is the PAGE (and `--json`, the full report, the decision record) as a person would read it:
  paste the before and after pages verbatim in your report.
- One issue can hold several separable items. Commit each item separately (`fix(#NN): …`), and for each say
  met / not met / not verified. Leave an item you cannot finish well: say so; do not half-fix it.

## Addendum 2 (2026-11-11, after CI failed on Python 3.12)

- **Never name a mutant by a literal content id in a test** (`SWAP_f9431aa0`). An id hashes `ast.dump`, whose output
  differs between Python 3.12 and 3.13+ (Wesker#48), so a literal names no mutant under the other family. Find the
  mutant from the run's own records by what it CHANGES (its diff/change text), its category, or its `killed_by`.
  Detective `3d4b3de` is the example (`tests/test_flag_refuses_distinguished_mutants_intent.py`).
- **Run every test file you add or change under BOTH interpreters before you commit:** the usual
  `.venv/bin/python` (3.14) and, for Detective tests, `<a 3.12 env built from the same lock>` (3.12.13,
  built from the same lock; give it the same `PYTHONPATH=$PP`). For Wesker tests under 3.12 use
  `PYTHONPATH=$PP <a 3.12 env built from the same lock> -m pytest …` from your Wesker tree. If that environment is missing,
  rebuild it: `cd ~/tools/Detective && UV_PROJECT_ENVIRONMENT=<path outside /tmp> uv sync --locked --python 3.12`.
  Report both counts.
- Your session was cut off by a usage limit once already. Commit each finished item as soon as it is green, so an
  interruption loses at most the item in progress. Keep reports tight.

## Addendum 3 (2026-11-12, after CI failed on all six Wesker cells)

- **This container exports `PYTHONUNBUFFERED=1`; CI does not.** With it set, Python never buffers stdout, so any
  defect in the ORDER of output between `sys.stdout` and a raw descriptor (or a child process) is invisible here and
  fails in CI, where stdout is a block-buffered pipe. Wesker `fe210ca` is the example. Run every test file you add or
  change with the variable removed: `env -u PYTHONUNBUFFERED PYTHONPATH=$PP <python> -m pytest …`, under both
  interpreters. A test that launches a subprocess and reads its output should drop the variable from the child's
  environment itself, so it measures what CI measures on any machine.

## Addendum 4 (2026-11-13): the guards are part of every lane's gate

The founder: "We shouldn't be adding guards that we know we're about to trip." Both repos carry guards that most
changes touch. Integration lost hours to lanes that never ran them. Before EVERY commit, run them with the files you
touched:
- Detective: `tests/test_consumer_distinction_intent.py`, `tests/test_field_consumption_intent.py`,
  `tests/test_absorbed_rename_intent.py`, `tests/test_pinned_decision_consumption_intent.py`.
- Wesker: `tests/test_instrumentation_ownership_guard.py`, `tests/test_unscored_rollup_intent.py`,
  `tests/test_policy.py`, and any `tests/test_*guard*.py` / `*consumption*` / `*totality*`.
- A field you add to a result type needs a reader, and every test double of that type (`SimpleNamespace`, `Dummy*`)
  gains the field in the same commit: grep `tests/` for them. A fault flag is read DIRECTLY where the type declares
  it, never `getattr(obj, flag, <clean default>)`.
- Fix the cause; edit a guard's registry only where its docstring says that is the right response, and say why.
