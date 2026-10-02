# Fix round — progress record, 2026-10-02 (Detective + Wesker)

A session worked the #99 index in parallel workers, then wound down on request. This file says
what landed, what is partial, what was grounded but not built, what new defects were found, and
what needs a founder decision. The commit essays carry the full reasoning; this is the map.

Nothing here closes an issue — closing is the founder's. Nothing was published. At the founder's
direction the completed branch was fast-forwarded into `main` in both repos (Wesker first, then
Detective with its `uv.lock` bumped to that Wesker); the unfinished #76 work rides along only as a
patch file under `docs/wip/`, never as code.

## Where the work is

| Repo | Branch | Base | Commits |
|---|---|---|---|
| Detective | `claude/wesker-project-issues-7wejxy` | `c3ee434` | 6 (+ this record and one WIP patch file) |
| Wesker | `claude/wesker-project-issues-7wejxy` | `81c5cc1` | 8 |

Detective CI resolves Wesker from GitHub `main` through `uv.lock`, so the Wesker branch went to
`main` first and Detective's lock moved off `81c5cc1` to that Wesker in the same push (#88's rule).
The published floor (`Wesker>=1.1.1`) is unchanged: raising it is a release decision, and nothing
here was published. This Detective against the OLD Wesker `81c5cc1` was not run.

## Status by issue

### Landed (merged on the branch, gated)

| Issue | Commit(s) | What changed | Pin receipts |
|---|---|---|---|
| Wesker #17 | `d8c228e` `e212f7e` `8ee8beb` | Every baseline row carries a typed `baseline_outcome` (passed / failed / skipped / xfailed / error). Skipped and xfail rows used to read as passed AND admissible, so an xfail test's reach closed lines in the view Detective's certificate reads; each non-pass is now refused under its own name (also persisted in the trace cache). Reach in a child thread the test starts and joins is traced (was an admissible NEGATIVE: 0/5 killed, all false survivors → 5/5); a thread that outlives its test marks the row `incomplete_thread` (unknown, never negative, never cached). Stale "ARCS ARE NOT YET RECORDED" docstring fixed. | `item_run_status` ✓ 39/39 · `baseline_outcome` ✓ modulo 1 · 34/35 · `trace_admissibility` ✓ 39/39 |
| Wesker #34 | `3e2a88a` | The isolated worker formats no failure traceback (mutant runs and its determinism baseline). SAME check through `converge --isolated` on the shipping fixture: FINAL, generated suite, certificates byte-identical; per-mutant kill records identical. Converge process-tree CPU 29.4 s → ~20.3 s (−31%). | — (I/O path) |
| Wesker #31 | `87ebdd3` | The whole-pool fallback runs only baseline-screened tests; the unscreened remainder is typed unknown on the survivor record (`scope`, `unscreened_tests`). Measured: hold-back alone dropped `detective audit` (isolated mode never widens) of a caller-tested helper from 8/13 to 0/13, so isolated mode now screens the consulted tests up front — back to 8/13, and its false "3 uncovered lines" is gone. | `attribution_standing` ✓ 7/7 · `mutant_scope_route` ✓ modulo 1 · 17/17 (`--isolated`) |
| Wesker #28 (D1 only) | `b2d790c` | A worker whose starting thread holds the execution lock is refused BEFORE the C-level acquire with a named `nested_measurement` control exception; the status is written on the worker first, so pytest's capture and broad `except` handlers cannot unwrite it. An unscored, non-kill, non-survival disposition; the profile is non-gateable; the baseline guard's workers are covered and keep such tests. Before/after on `baseline_probe_disposition` through Detective's real path: a false timeout kill and a cut run → 19/19 killed by assertion, the one mutant named. 29 intent tests on event-driven schedules. | `nested_acquire_disposition` ✓ 15/15 · `baseline_probe_disposition` ✓ 20/20 · `mutant_disposition` ✓ 28/28 (all `--isolated`) |
| Wesker #18 | `7176e9a` `23ab488` | A `not_entered` record names WHY: `cause` ∈ `not_reached` / `decorator_wrapper` / `captured_at_import` / `pre_bound_reference` / `holder_not_found` / `no_reach_data`, with `reach`, `holders` (`{kind, where}`), `holder_scan`, `ended_by`; per-profile counts in `ProfilingResult.not_entered_causes` (in `to_dict()`). Decided from observed facts (baseline reach of the tests that actually ran + a bounded scan of module-level references the install does not rebind) — NOT from test syntax: measured, a same-name `from m import fn` IS rebound, so #77's import-form hypothesis names the wrong mechanism. The `entered=None`-with-no-tests rule is documented beside the dispositions. | `baseline_reach` ✓ 19/19 · `not_entered_cause` ✓ 32/32 |
| Detective — | `8988c1f` | The unwritable-project ledger test skips under root, like its siblings (root ignores 0o500). | — |
| Detective #78 | `6196613` `2f70d9d` | `nan`, `inf`, `-inf`, `float("nan")`, `float("inf")` are input spellings in every module: the one parser folds them to constants BEFORE the unchanged grammar gate and dunder ban (adversarial tests: `float.fromhex`, `nan.__class__`, walrus, lambda all still refused; a module's own `float` is never called). Everything Detective prints spells a non-finite float `float('nan')` — accepted by `--input` and valid Python. Two more readers of the same split fixed: generated tests and golden rows wrote bare `nan` (a NameError — the killing test was judged unsound and never written), and golden capture silently dropped a supplied NaN. | `nonfinite_float_spelling` ✓ 36/36 · `float_spelling` ✓ 16/16 (re-pinned after `2f70d9d` swapped `value != value` for `math.isnan`; was 18/18) |
| Detective #71 (a)+(b) | `cdb4f4d` | A boundary-probe pass over the residual: the `None` of an Optional first, both sides of every comparison edge, float interiors, the dict keys the body reads, the table keys a string parameter is looked up in. Residual-only and positive-only; a probe that distinguishes a FLAGGED mutant overturns the flag. The DONE block and audit's closing row no longer say "UNDECIDABLE … not a gap": they say whether the residual was probed, and if not that it may be search budget, with the remedy; `flag` is offered only for candidate-equivalents. Before → after (committed goldens moved aside): `outcome_disposition` mod 3 · 25/28 → ✓ 28/28; `suite_state_comparison` 7/7 → 7/7; `same_recorded_state` mod 7 · 41/48 → mod 4 + 1 crash-only · 44/48; `consumption_disposition` mod 2 · 21/23 → ✓ 23/23; Wesker `step_budget_verdict` mod 2 · 10/11 → mod 1 + 1 crash-only · 10/11 (`(0, None)` now distinguishes `if cap is None:` → `if False:` by crash). | `boundary_probe_gate` ✓ 18/18 (`--isolated`) · `residual_done_basis` ✓ 24/24 · `residual_done_why` ✓ 12/12 · `boundary_probe_values` ✓ modulo 3 · 169/172 |
| Detective #91 | `08966ba` | `routing_outcome` → `routed` / `unrouted` / `routing_failed`. A routing failure runs NO test (was: the not-consulted test ran 4× for one function, no cut, gateable and cacheable); cut reason `routing_failed` (schema 3→4) reaches every layer — never cached, certificate `ungateable`, ledger, a `fix_routing` repair route, FINAL banner, `--json` (`cut_reasons`, `routing_error`), exit 3. The seeded ContextVar is reset when a raise follows the seed. | `routing_outcome` ✓ 3/3 · `measurement_cut_reasons` ✓ 47/47 · `cut_reason_sentence` ✓ 43/43 · `repair_measurement_route` ✓ modulo 2 · 73/75 |
| Detective #92 | `d9e3fb4` | The verdict cache stores and restores `observed_return_types` (an empty codomain stays empty, never "missing"); an old row re-observes over the pool `profile` would consult (`codomain_source`). A warm two-sign converge runs no not-consulted test and classifies as the cold run. Also fixed: `audit --two-sign` classified with the one-sign mutant set, so its negative-sign survivors landed in `unclassified`. | `codomain_source` ✓ 3/3 |

### Partial (kept, NOT merged)

**Detective #76** — `docs/wip/0001-wip-76-satisfiable-attributed-witness-suggestions-fr.patch`
(a `git format-patch` of the worker's WIP commit; apply with `git am -3`, then delete the file).
Done in it: suggestions are the test converge would write (`repr(result) == 'nan'`, `pytest.raises`),
never `== nan`; each names the mutant it kills and what that mutant gives; `witness_confirmation`
re-runs original and mutant on fresh copies before proposing (equal observables, NaN included, are no
witness; ✓ COMPLETE modulo 1 · 30/31); killable and crash-only exclusive; supplied inputs compared by
value and across runs, never re-proposed; environment-reading targets go to "write the pins by hand".
The three reported functions did not loop on current code; their live defect was the `<= -1` VALUE
mutant filed crash-only, now killed at `(0.0, -0.5)`. NOT done: `suggestion_form` unpinned; the
broad classifier/converge/audit set was not re-run after the fresh-call re-check entered the witness
search (it changes behaviour for argument-mutating and nondeterministic functions); the FINAL banner's
"N killable · M/M killed" pairing is unchanged. It edits `tests/test_witness_dedupe.py` (asserted a
single suggestion names no mutant — the opposite of #76).

### Grounded, not built (notes for the next session)

- **#96** — reproduced: a fixture copy of pre-`6e7c2a4` `numeric_backend_for` converged to a golden
  documented "VALUE golden captures — pure + deterministic", pinning `"numpy"` / `"scipy"`. Plan:
  extend the static scan in `purity.environment_reads`; every consumer is already wired
  (`converge._golden_properties` → `environment_coupled`; the witness gate `_capturable`;
  `environment_gated` → `certificate_refusal`; `--json`). Withhold rather than stamp — a stamp cannot
  make a `sys.modules` golden reproducible (it varies with test order). Pitfalls: the reason text
  must not contain "process env" (`capabilities.env_covers` substring-matches it, so `--env` would
  "cover" it); a `platform.` rule must exclude names bound in the function; aliased imports and reads
  one helper down stay outside a local scan.
- **#98** — design: pure `plugin_declaration(...)` → `blocked` / `explicit` / `autoload_off` /
  `declared` / `undeclared`, consumed code-by-code (the distinction guard would flag a truthy
  collapse); enumeration opt-in so `resolve_regime` (every profile pass) stays cheap, with "not read"
  (`None`) distinct from "none found" (`()`); disclosure on stderr from `_run_live`, a `regime` row and
  JSON field, a doctor GREEN-section row that changes neither code nor exit. Tests must unset
  `PYTEST_DISABLE_PLUGIN_AUTOLOAD` (`tests/conftest.py` sets it session-wide).
- **#97** — `killed_records` and `kill_matrix` are persisted in the verdict cache, so the recorded
  killing tests are known without a run; the failure TEXT is never stored (the cheap repr). `flag`
  finds a mutant by re-profiling the whole function — too costly to reuse. Open: rebuild one mutant
  from its id and run one test against it with full reporting.

### Not started this round

Detective #93, #94, #95, #77 (the renderer — now unblocked: consume Wesker #18's `cause`), #80 (now
also: Detective must learn `nested_measurement`, below), #84, #89, #86, #79 (the founder's README),
#88 and Wesker #35 (release), Wesker #27, #29, #30, #32, and the P3 programme.

## New defects found while working (not fixed)

1. **Detective does not know `nested_measurement`.** A converge of a Wesker engine function whose
   last mutant is refused that way stops with "engine refused unspecified". Workaround: `--isolated`.
   Belongs with #80's consumer work.
2. **Verdict-cache eviction** (filed with item 3 as #100) — `verdict_cache.params_suffix` assumes keys END in
   `:max:pass:budgets`, but `:two_sign` and the regime digest are appended after them: in a live
   session a two-sign pass evicts the other passes' rows, and a fast run evicts the full run's row
   for the same pass. Measured: a two-pass two-sign converge's final measurement missed the cache
   right after pass 0 stored it.
3. **A written generated test fingerprints differently in the next session**, so the next converge
   never reuses the previous run's final result. Observed; cause not found.
4. **#91 changed the FINAL banner for every Detective-side cut** — it now reads the certificate
   verdict, so `collection_incomplete` and the others render UNGATEABLE where they rendered
   "Incomplete". Arguably the honest reading; flagged for review. Separately (pre-existing): audit's
   next-action text and diagnose's text report show no cut reasons; doctor's setup checks do not
   know `routing_failed`.
5. **Pinning the lock-check code in-process is unreliable** (the #29 "mutated machinery" shape):
   one in-process run read COMPLETE, a later one `Incomplete: 5 killable`. Only `--isolated`
   receipts are robust for containment primitives.
6. Wesker's fast-mode shape gate reads a stamp that live-session tests never carry, so a
   thread-spawning live test reads as safe (#19 territory).
7. Wesker's `pyproject` sets `pytest` `pythonpath = ["."]`: pytest run from a Wesker checkout uses
   THAT checkout whatever `PYTHONPATH` says — a trap when verifying "fails on the old code".
   Run such checks from outside the repo.
8. Wesker `test_hermetic_first_kill_loop_intent` fails when Detective is on the path — identical on
   untouched `81c5cc1`, so pre-existing.
9. `_build_test_scope` is now 63 statements (pylint's limit is 50) after #31.
10. Wesker #28 residue: threads started by the code under test are not tracked (a cycle through one
    is detected, not prevented); a narrow false-kill window remains in the per-function baseline
    path after a refused test's nested point.
11. Left for `detective flag` (judged equivalent by inspection, not by the tool): the `| None`
    annotation mutants on `def` lines (the Wesker #30 shape) in `baseline_outcome`,
    `mutant_scope_route`, `same_recorded_state`, `step_budget_verdict`; two mutants in
    `same_recorded_state` that drop a `bool(...)` its callee only tests for truth.

## Decisions for the founder

New this round:
- **Wesker #31** — should a survivor carrying an unscreened remainder make the result non-gateable?
  Left unchanged (gateable) because the issue does not say.
- **Detective #91** — keep the FINAL banner reading the certificate verdict for all cut reasons
  (item 4 above)?
- **Detective #76** — the WIP's fresh-call witness confirmation changes witness search for
  argument-mutating and nondeterministic functions; confirm the direction before it is finished.

Still pending from #99: Wesker #27 (step-budget factor k and floor; compute-budget setting), Wesker
#28 option D2, Wesker #30 option A or B, Detective #83 (reproducibility pass: regenerate or take the
propagated universe), #86 option A or B, #90 (the restatement), versions and the publish.

## Verification

Container: Linux, 4 cores, uv-managed CPython 3.14.0rc2, running as root (permission tests skip).
`PP=/home/user/Detective:/home/user/wesker`.

- Wesker branch, full suite: **1006 passed, 5 skipped** (baseline at `81c5cc1`: 901 passed, 5 skipped).
- Detective branch against the Wesker branch, full suite: **3485 passed, 18 skipped, 1 xfailed, 0
  failed** (baseline at `c3ee434`: 1 failure, the root-only ledger test fixed in `8988c1f`). Taken
  just before the one-line `2f70d9d`; after it, the affected goldens and intent files: 77 + 56 passed.
- Pinned ruff 0.16.7: check (scoped) and format check (whole tree) clean in both repos.
- pylint (`uvx --python 3.14 pylint`, the Sonar-tuned config), filtered to the lines this round
  changed: Detective 9, Wesker 6. Residue by the house rules — W0718 on broad excepts that carry the
  house `# BLE001: <reason>` + bare `# noqa: BLE001` form (3 Detective, 6 Wesker) and E0401 (pylint's
  environment has no Wesker; 2). Fixed: R0124 `value != value` (`2f70d9d`). Left, as refactor
  nits: R0916 `_NonFiniteFold.visit_Call` (6/5 boolean expressions), R1702 `engine._compared_constants`
  (6/5 nested blocks), C0123 `type(value) is complex` in `is_expressible` (deliberate: exact type).
  Plus item 9 above (`_build_test_scope` statement count).
- Both suites also ran on CPython 3.12.11 (the floor): identical counts. The sdist check passed in
  both repos (all members tracked).
- GitHub CI on the new `main` heads — Wesker `23ab488`, Detective `6537487`: green in every matrix
  cell (3.12 / 3.13 / 3.14 × ubuntu / macOS), package, workflow audit and CodeQL.
- SonarCloud (CI's scan; the local SonarQube container is not available in a cloud session):
  - Wesker gate **OK**.
  - Detective gate **ERROR on `new_security_rating`, and it was already red before this round**:
    the analysis of `c3ee434` (2026-10-01, the previous `main`) is tagged "Red (was Green)" with
    "Changes in 'Sonar way comprehensive' (py)" — the profile gained the `pythonsecurity:S8707` /
    `S8705` "path traversal / argument injection via LLM-supplied CLI arguments" rules, which now
    report 11 open vulnerabilities, all created between 2026-08-07 and 2026-09-26 (`atomic_store`,
    `certify`, `cli`, `parsimony_map`, `dev/`). None is from this round. Whether a CLI that takes a
    path from its own user is a traversal is a profile/triage decision for the founder.
  - New-code issues this round added — code smells only (no bugs, vulnerabilities or hotspots):
    S3776 cognitive complexity (Detective: 5 in `engine.py`'s boundary-probe helpers around
    lines 2333–2494, 2 in `equivalence.py` at 366/401; Wesker: `engine.py` 4232, 5350, 5489 — the last
    is 35); S107 `_build_test_scope` has 15 parameters (Wesker, after #31); S5778 ×4 in
    `tests/test_nonfinite_input_spelling_intent.py` (144, 146, 148, 250 — the rule `c3ee434` fixed);
    S9073 composite assertions in the new intent tests (the founder's profile decision, per
    CLAUDE.md); and two classified as not-a-defect: S5655 at `cli.py` 2249/3238 is a FALSE POSITIVE
    (`_residual_counts` returns `tuple[int, int]`, which unpacks exactly into
    `residual_done_basis(int, int, str)` — transition it with a comment), and S5709 at Wesker
    `interrupt.py:55` is BY DESIGN (`nested_measurement` must be a BaseException so a nested broad
    `except Exception` cannot swallow it — #28's whole point).
- Not run here: the local SonarQube container, the macOS/`taskpolicy` SAME checks. One worker ran
  `ty` on its Wesker change: the same 6 environment-only diagnostics before and after.

## Resuming

Start from #99 as usual, then this file. In a cloud container: clone Wesker beside Detective, set
`PP` to the two checkouts, `uv sync` in each, and run Detective's suite with Detective's `.venv`.
Serena is not available there (grep + narrow reads instead). For engine functions, pin with
`--isolated` until Detective consumes `nested_measurement`.
