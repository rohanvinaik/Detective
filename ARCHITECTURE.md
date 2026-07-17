# Detective — Architecture & Operational Map

The single reference for **what Detective does, how it does it, and where to look
when something breaks.** Cold start: read §1 (mental model), skim §3 (data structures)
and §5 (the full CLI), keep §9 (debug map) open — a symptom there points at the exact
function and why it fails.

Detective is a **clean-room** package on **Wesker + stdlib only** (no lintgate in the
runtime import graph). Runtime dep: `Wesker` (git URL). Console scripts: `detective`
(CLI) and `detective-mcp` (optional MCP). Everything below is operational.

---

## 0. Thesis (the one idea)

A function's **mutation profile is a complete map of the behavioral distinctions it
makes.** Killed mutant = a distinction the tests pin. Survivor = a degree of freedom
no test distinguishes. Read backwards, that map is a *specification*: it says exactly
which behaviors are unpinned, so you can pin them with warranted tests — or recognize
that nothing *can* pin them (equivalent mutants). Every command consumes that map.

**Value-specification vs run-specification (the load-bearing distinction).** A kill is
only a *value* specification if a test **assertion** distinguishes the mutant — it pins
*what the function returns*. A kill by **crash** or **timeout** proves only that the code
*runs*, not what it computes, so it is an **unspecified value-DOF** (a value-survivor).
Detective's "specified/complete" always means *value*-specified:

- `value_killed` = assertion kills only.
- `value_survived` = true survivors **+** crash/timeout kills.
- **Mutation-completeness** (`functionally_complete`) = every *killable* mutant is killed
  by an assertion; the only survivors left have no distinguishing input (equivalents).

**Two orthogonal axes** — do not conflate them:
- **Mutation completeness** — the *proof* metric. It is what makes a decomposition
  provably behavior-preserving and a suite a real specification.
- **Line completeness** — the standard "every executable line is covered." Weaker and
  *orthogonal*: a line whose mutants are all killed is specified whether or not coverage
  counts it, and a covered line whose mutants survive proves nothing. Line-completeness
  is reported, never used as a proof gate.

---

## 1. Mental model (the pipeline in one breath)

```
  your function ──▶ Wesker (mutate + run covering tests) ──▶ ProfilingResult
                                                                │
        ┌────────────────────────────────────────────────────────┤
        ▼                    ▼                 ▼          ▼        ▼
     scope             classify_survivors   minimize   line-cov  decompose seams
   (diagnose)          (killable / equiv /  (2-axis    (baseline (find_extraction_
                        unclassified, by     cover)     trace)    candidates)
                        EXECUTION)
        │                    │                 │          │        │
        └──────────▶ converge · audit · decompose ◀────────────────┘
                          │
                          ▼
        clean pytest files on disk + a full report on disk + a terse FINAL banner in the CLI
```

Detective **owns one function at a time.** Every command takes `file.py::function`,
asks Wesker to profile it, then reshapes/acts on the result. Detective holds no
cross-run RAM state; persisted state is on disk (§8). Profiling is **content-cached** and
**serial** — the cache is transparent and verdict-identical to an uncached run (§7).

---

## 2. The two input surfaces

### 2a. INPUT FROM WESKER (the engine seam) — `Detective/engine.py`, `Detective/scope.py`

Detective imports exactly these from Wesker (the *entire* dependency surface):

| Import | From | Used for |
|---|---|---|
| `run_function_profiling(node, func_key, categories, tests, original, *, budget_ms, mem_budget_mb, max_per_category, pass_index, progress, scope_tests, mutant_slice, precomputed_line_data, pregenerated)` | `Wesker.engine` | THE profile call — mutate + run **covering** tests + baseline line-coverage |
| `generate_mutants(func_node, categories, *, max_per_category, pass_index)` → `list[Mutant]` | `Wesker.engine` | the deterministic mutant set (reused across probe/shards; witness search) |
| `estimate_universe_size`, `greedy_coverage_guarantee` | `Wesker.engine` | DOF count + the a-priori greedy coverage floor (the converge "stats flex") |
| `ProfilingResult`, `CategoryResult`, `MutationCategory` | `Wesker.engine` | the result type (see §3) |
| `discover_test_callables(root, rel, func_names, extra_dirs)` → `list[Callable]` | `Wesker.ci` | find the real tests exercising a function (pytest-aware, binds parametrize). **Inside a live session it returns the session's callables and ignores every other argument** |
| `run_with_live_suite(root, fn, target_files, paths, trace_progress, trace_budget_s, trace_session_budget_s)` | `Wesker.ci` | **THE session seam.** `cli._run_live` wraps the whole command in it once; everything underneath transparently upgrades. Returns `None` — and ONLY `None` — when no session could start |
| `refresh_live_suite(root, path)` → `int` | `Wesker.ci` | tell the session a test file changed on disk. Called from `certify._write`, the one choke point every generated test passes through |
| `walk_functions(tree)` → `[(qualname, node), …]` | `Wesker.ci` | enumerate functions in a module |
| `filter_categories(node, pure)` → `set[MutationCategory]` | `Wesker.filter` | which mutation categories apply (drops STATE for pure fns) |
| `DEFAULT_TRACE_BUDGET_S`, `DEFAULT_TRACE_SESSION_BUDGET_S` | `Wesker.engine` | the trace caps. **Imported, never restated** — a second copy would drift silently |
| `telemetry`, `purge_caches` | `Wesker.memory_guard` | CLI footer + the `.wesker/` HALF of `purge` (§8) |

**The live session is the load-bearing seam, and it is a correctness feature, not a speed one.**
Wesker's fallback discovery collects with `--collect-only`, which tears the session down at once,
so every fixture-taking test is skipped. A mutant only such a test could kill then reports as a
surviving behavioral gap — Detective claims a dimension is unspecified when the suite already pins
it, and `converge` writes a test for behavior that was never unspecified. Measured on Prism: 0 of
445 tests bound the old way, 445 the new way. `cli._run_live` and `mcp_server._in_session` are the
only two entry points, and both degrade **loudly**; a silent fallback is the exact failure the seam
exists to end.

Three things ride on that same seam, and all three are Detective's job to pass:

* **`paths`** — pytest's own collection argument, narrowed by `reachability.reachable_test_paths`
  to the files that could execute the target's lines. The session baseline traces EVERYTHING it
  collects before a single mutant runs, so an unscoped collection makes cost scale with the
  **suite**, not the function (Regenesis: 2134 test functions traced for one 13-line function,
  1928 of them in modules that cannot reach it even transitively). `None` = collect everything =
  byte-identical to before.

  **The scoping is computed BEFORE the seam chdirs, so it must not depend on the cwd — and it
  did.** `module_name` resolved a relative target with `os.path.abspath`, i.e. against the
  *process's* cwd rather than `project_root`. From a CLI run standing in the project the two
  coincide and it scopes correctly; from a stdio server — whose cwd is wherever its client
  launched it — the target resolved outside the tree, fell out of the graph, and the analysis
  returned `None`. Because `_reachable_paths` deliberately degrades any failure to "collect
  everything", a wrong answer and a declined optimisation are indistinguishable from outside: the
  MCP surface silently traced ~9x the suite (2113 vs 240), which then guaranteed the session trace
  budget cut and reported the cut coverage as unpinned behaviour. Resolve relative paths against
  `root`, never the cwd — the rule `engine.profile` already follows for the file it opens.
* **The trace budgets** — they bound the pass that traces the suite, and on the live path that
  pass runs *inside this seam*, not in `profile()`. Sent only to `profile()` they reached the
  per-function path a live session never uses, so raising the flag changed nothing.

  **The mirror of that bug is the cache key, and it is why `profile()`'s budget arguments are not
  what the key records.** Inside a live session `_build_test_scope` prefers the `SessionBaseline`
  and never consults those arguments, so they describe nothing about the verdict; the seam's
  budgets do. The CLI passed the same values to both and was correct by discipline, while every
  other caller (`audit_suite`, `converge`, `certify`, `decompose_apply`, `classify_survivors`, the
  MCP surface) sent them to one side only — writing a tightly-budgeted measurement under the
  DEFAULTS' key, to be served later to a run that asked for the defaults. `profile` therefore keys
  on `Wesker.engine.session_budgets()` — what actually produced the answer — and falls back to its
  arguments only outside a session, where they do drive the trace. A verdict must be keyed on
  everything that could have produced it; discipline is not a mechanism.
* **`refresh_live_suite`** — see below.

**The session's collection is a SNAPSHOT, and Detective writes tests.** `discover_test_callables`
short-circuits to the session's callables, which is right for a consumer that only READS a suite
and silently wrong for one whose product is writing tests: `converge` writes, re-profiles, and is
handed a list that predates its own work. `certify._write` therefore calls `refresh_live_suite`
after every write **and every delete** — it is the single choke point through which generated tests
reach disk, which is what makes "the suite changed" impossible to forget at a call site. That call
does two things, and needs both: it replaces the callables from that file, **and** invalidates the
`SessionBaseline`, whose trace decides which tests are run against which mutant. Refreshing the
list alone changes what is *discovered* and nothing about what is *run* — the count stays exactly
as wrong (measured: 18 mutants killed by tests on disk, reported as 2, with the user asked to
supply inputs for the 14 already dead).

**What Detective gets back — `ProfilingResult`** (the single most important object):

| Field | Type | Meaning |
|---|---|---|
| `function_key` | str | `rel/path.py::qualname` — the identity everywhere |
| `total_mutants / total_killed / total_survived` | int | raw headline counts |
| `per_category` | list[`CategoryResult`] | per-cat `total/killed/survived/killed_by_assertion/killed_by_crash/timed_out` |
| `kill_matrix` | dict[mutant_desc → list[test]] | which tests kill which mutant → minimize |
| `survivor_records` / `killed_records` | list[dict] | each carries `mutant_id`, `category`, `diff_summary`, `killed_by`, `elapsed_ms` |
| `line_coverage` | dict[test → list[int]] | which target lines each test covers (baseline pass) |
| `executable_lines` | list[int] | statement lines of the target (the denominator) |
| `failing_tests` | list[str] | tests that `assert`-fail on the UNMUTATED function → audit ⚠ — REPO-WIDE (the baseline runs every discovered test, for every function); `audit_suite` scopes it to this function's own suite before reporting |
| `tests_discovered` | int | how many test callables were found (`0` = "nothing to kill with", `-1` = unknown) |
| `budget_exhausted` | bool | time/MEMORY budget stopped the run early |
| **DERIVED properties** (never stored — cannot drift) | | |
| `value_killed` | int (property) | Σ `killed_by_assertion` — value-specified |
| `value_survived` | int (property) | true survivors + crash/timeout kills — value-*un*specified |
| `value_survivor_records` | list[dict] (property) | survivor-shaped record for every value-survivor (incl. crash-kills, with their diff for witness search) |

`line_coverage`/`executable_lines`/`failing_tests` come from Wesker's **baseline pass**
(`Wesker/line_coverage.py`, via `sys.settrace`) run once against the original before the
untraced mutation loop.

### 2b. INPUT FROM THE USER

| Surface | Where | What |
|---|---|---|
| CLI target | `file.py::function` positional | the one function to act on |
| Common flags | `--project-root`, `--json` | per-command behavior (§5) |
| `--input "(…)"` | converge, decompose | a **Zone-2 residual** — a Python-literal positional-arg tuple the tool asked for (the semantic prior synthesis couldn't build) |
| `.detective/equivalents.json` | project root | **manual equivalence flags** (user data — §8); read by `classify_survivors` |
| `WESKER_MEM_BUDGET_MB` | env var | user-selectable memory ceiling (§7) |
| existing test files | project `tests/` etc. | the suite `audit` assesses / `converge` augments (Wesker-discovered) |
| covering tests' runtime inputs | project `tests/` | when synthesis provably can't build a param (a domain object), `capture_call_inputs` reuses the REAL args those tests already pass — never fabricated (the honest alternative to abstaining) |

---

## 3. Core data structures (what flows between stages)

All in `Detective/`. Frozen dataclasses unless noted.

- **`ScopeMap`** (`scope.py`) — *diagnose output.* `regime` (A tractable / B entangled),
  `specification` (variants/pinned/unspecified/inert — *value*-pinned), `kill_quality`
  (`by_value_assertion` vs `by_crash` + warning), `behavioral_dof`, `tests_discovered`,
  **`decompose_seams`** (structural extraction count —
  the STRUCTURAL half of "is this >1 thing"; regime B is the behavioral half). Produced by
  `scope_from_profiling` + `diagnose`; consumed by `_format_scope`.
- **`Witness`** (`equivalence.py`) — a concrete input where original and mutant differ by a
  **value**: `args`, `original`, `mutant`. A value-witness is PROOF of value-killability =
  a concrete killing assertion. Produced by `find_witness` — which **skips "mutant newly
  raises"** differences (a crash-kill does not pin value; see §9).
- **`MutantVerdict` / `SurvivorReport`** (`equivalence.py`) — one survivor classified
  (`killable`, `witness`, `diff_summary`) and the per-function roll-up (`.killable` /
  `.equivalent` / `unclassified` / `manual_equivalent`). Disjoint buckets; completeness
  reads them directly.
- **`SourceExpr`** (`equivalence.py`) — a synthesized **non-literal** input (AST node /
  built object): runs as its live `value`, renders as its constructor `expr` (via
  `__repr__`), threads its `imports`. How AST/object inputs both *run* and *render*.
- **`ExecutableProperty`** (`synthesis/oracle_light.py`) — one test-to-be (`setup_code`,
  `assertion_code`, `needs_oracle`, `golden_case`). The unit the writer renders.
- **`ConvergeResult`** (`converge.py`) — converge output: `functionally_complete`,
  `line_complete`, `at_ceiling`, `survivor_report`, `missing_lines`, `redundant_tests`,
  `minimal_test_count`, `universe_size`, `fast`, **`coverage_guarantee`** (the proven greedy
  floor), `signature`/`param_names` (for the `--input` residual template), `written_path`,
  `wiring`. `.complete` = functionally ∧ line complete.
- **`SuiteAudit`** (`audit.py`) — audit output: `mutant_complete`, `line_complete`,
  `redundant_tests`, `failing_tests`, `killable_gaps`, `missing_lines`, `minimal_test_count`,
  `candidate_equivalent`/`unclassified`/`manual_equivalent`, `.complete`,
  `.complete_modulo_equivalent`, `.bloat`. EVERY emitted test list is scoped to THIS function's
  suite (a test that kills one of its mutants or covers one of its lines) — the rule is stated
  once in `audit_suite` as `suite` and every field derives from it. Wesker's baseline is
  repo-wide, so an unscoped field silently reports other functions' tests as this one's:
  `failing_tests` was that field, and it put 2126 unrelated names (56KB) into a one-function
  report until it was bound by the same rule as its siblings.
- **`Extraction` / `Decomposition` / `DecompositionApply`** (`decompose_apply.py`) — a
  generated helper (`helper_name`, `params`, `returns`, `new_source`) and the outcome
  (`applied`, `proposed`, `unsafe_blocks`, **`proof`** = the converge run, so the CLI can
  surface the residual `--input` when it cannot prove).
- **`EquivalenceFlag`** (`equivalents.py`) — a manual equivalence assertion keyed by
  `func_key` + `sha256(diff)[:16]`; the diff embeds the code, so it is content-validated.

---

## 4. Module map (responsibility · key functions)

| Module | Responsibility | Key functions |
|---|---|---|
| `engine.py` | **THE Wesker adapter** + caching + witness classification + input synthesis | `profile`, `diagnose`, `classify_survivors`, `representative_site`, `_count_decompose_seams`, `_load_original` |
| `verdict_cache.py` | **content-hashed profile cache** (§7) + purges Detective's own regeneratable state (§8) | `cache_key`, `params_suffix`, `get`, `put`, `purge`, `_to_json`/`_from_json`, `tests_fingerprint` |
| `reachability.py` | **static test-impact scoping**: which test files could execute a target's lines, for the session's `paths` (§2a, §7). Conservative in ONE direction — any doubt returns `None` = collect everything | `reachable_test_paths`, `module_name` |
| `scope.py` | reshape ProfilingResult → behavioral map | `scope_from_profiling` |
| `equivalence.py` | classify survivor killable/equivalent BY EXECUTION; typing; SourceExpr | `find_witness`, `classify_survivor`, `_outcome`, `synth_ast_input`, `unwrap` |
| `purity.py` | is-pure predicate (gates STATE + golden capture) | `is_pure`, `analyze_function` |
| `call_sites.py` | recover inputs/types from how a fn is CALLED across the repo (static, literal args) | `discover_call_site_inputs`, `infer_param_types` |
| `capture.py` | **runtime harvest** of REAL args from the covering tests when synthesis can't build a domain-object input (`sys.setprofile` on the target's code object) | `capture_call_inputs` |
| `synthesis/{typed_synthesis,characterization,oracle_light,writer}.py` | make inputs, capture goldens, build properties, render pytest | `synthesize_value`, `capture_golden`, `golden_assert_line`, `generate_executable_property`, `render_module`, `individual_test_names` |
| `converge.py` | **the closed loop**: diagnose→synth-sound→write→re-profile to the ceiling | `converge`, `property_holds`, `passes_to_complete`, `_golden_properties`, `_witness_property`, `_raises_witness_property` |
| `certify.py` | one-shot synth (library API, no longer a CLI command) + pytest wiring | `certify`, `wire_pytest`, `verify_under_pytest`, `ensure_conftest` |
| `minimize.py` | two-axis set cover (kill ∪ line) | `minimal_cover_2axis`, `redundant_2axis`, `missing_lines` |
| `audit.py` | read-only assessment of an EXISTING suite | `audit_suite` |
| `suite_edit.py` | apply confirmed test deletions | `apply_removals` |
| `decompose.py` | propose extraction candidates — **STRUCTURE-gated** (not survivor-gated) | `decompose`, `find_extraction_candidates`, `compute_cognitive_complexity` |
| `decompose_apply.py` | **extract-function**: converge (proof) → cluster → trial-apply → prove → apply | `apply_decomposition`, `extract_candidate` |
| `equivalents.py` | persist/read manual equivalence flags | `add_flag`, `load_flags`, `flag_key` |
| `cli.py` | arg parsing + formatting (`--version`, streaming narrative, minimal terse view + `--full`); wraps every command in the live session; **zero compute** | `main`, `_run_live`, `_run`, `_build_parser`, `_reachable_paths`, `_trace_budget`/`_trace_session_budget`, `_format_converge`/`_format_converge_terse`, `_final_banner`, `_plain_terms`, `_boundary_hint`, `_notify_stderr`, `_write_converge_report` |
| `mcp_server.py` | optional MCP surface (`detective-mcp`, §5a): `diagnose`/`converge`/`decompose`/`audit`/`deep_context`, each inside a live session; **zero compute** | `build_server`, `_in_session`, `_rendered`, `_render_diagnose`/`_render_converge`/`_render_decompose`, `_ask_for_input`, `main` |
| (Wesker) `memory_guard.py` | telemetry footer + the `.wesker/` half of `purge` | `telemetry`, `purge_caches` |

---

## 5. The CLI — every command, fully explained

Shape: `detective <command> file.py::function [flags]`. `cli._run` splits the target,
calls the library, prints a formatter; `cli.main` emits a `memory_guard.telemetry()` footer
to **stderr**. `detective --version` reports the package version. Live mutation progress and
the converge phase narrative also stream to **stderr**, so stdout stays clean for the result
/ `--json` (and the terse `FINAL` banner stays the last stdout line). Common to most
commands: `--project-root` (default `.`), `--json`. Commands: `converge`, `audit`,
`decompose`, `diagnose`, `flag`, `purge` (`certify` is a library API, not a CLI command).

**There is no parallelism, and there is no flag for it.** Every command runs serial. The
fan-out was removed in 0.8.0 because it could not run: `main` wraps every command in the live
session (`_run_live`), and a worker cannot re-bind the session's callables across a process
spawn — so `profile` refused to fan out inside one, which is *always*. `--parallel` and
`--serial` were measured to cost the same (5.04s vs 5.13s) and a forced `--parallel` on a
37-mutant function spawned zero workers: two documented flags that could not reach the thing
they named. The session baseline is paid once per session, so per-function cost is small; a
worker would re-pay it in full.

### `diagnose file::fn`  — read-only
**Purpose:** show a function's behavioral scope and point at the right next command.
**Operation:** `engine.diagnose` → `profile` → `scope_from_profiling`, plus a structural
read (`_count_decompose_seams` = `find_extraction_candidates`). No writes.
**You see:** regime (A/B); variants / value-pinned / unspecified / inert; kill quality
(value-assertion vs crash, with a ⚠ if crash-dominated); a plain-language "what to run
next"; and the **decompose guidance from two independent signals**:
- regime B **and** a structural seam → **`★ LOOK HERE FIRST`** (both methods agree it's
  really >1 thing — the high-value decompose target);
- regime B, no seam → "entangled but structurally one piece — `converge`, not decompose";
- a seam but cohesive behavior → "clean seam exists — `decompose` is safe if you want it".

### `converge file::fn [--write-dir tests] [--max-iterations N] [--fast] [--full] [--input "(…)"]`  — the flagship, writes tests
**Purpose:** generate a **mutation-complete, line-complete, minimal** pytest suite.
**Operation:**
1. **Loop** (≤ N passes): `profile` → value-survivors → synthesize `ExecutableProperty`s
   (oracle-light per survivor + golden captures for pure fns via `representative_site`);
   keep only those that **hold on the unmutated fn** (`property_holds`); render the UNION
   across passes (`render_module`) and write. Stop at 0 value-survivors / no progress.
2. **Witness pass** (`classify_survivors`): for each *value*-witness, auto-write the
   killing test — a golden for a value-returning original, a `pytest.raises` for a raising
   one (`_raises_witness_property`). Auto-apply because a witness is deterministic proof.
   When synthesis can't build an input, `classify_survivors` first **harvests a real one**
   from the covering tests (`capture_call_inputs`) rather than abstain.
3. **Final authoritative profile** → `functionally_complete`, line/minimal/redundant via
   `minimize`, pytest wiring (`wire_pytest`).
4. **Minimize before shipping:** drop any test WE generated that is redundant for BOTH
   kills and lines (`redundant_2axis` + `individual_test_names` maps the finding back to its
   property), re-render, re-profile — so the written suite IS minimal by construction, not
   merely accompanied by removal proposals. A non-generation, not a deletion (never auto).
**Modes:** default **comprehensive** (every mutant, first pass); `--fast` greedy-samples a
`(1−1/e)`-optimal subset per category per pass. `--max-iterations` caps passes.
**Output:** live phase narrative streams to stderr (`_notify_stderr`); the default stdout is
a **minimal terse block** — a plain-language verdict, the one quick action, a report pointer,
ending in a greppable `FINAL …` banner that is ALWAYS the last line. The full report is
written to `.detective/reports/converge_<fn>.txt`; `--full` prints it to the terminal too.
**You see (in the report / `--full`):** a COMPLETE/INCOMPLETE verdict (tiered: complete /
complete-modulo-equivalent / incomplete, naming the concrete cause — killable residual or
line gap); score + the **DOF stats flex** (universe · mode · measured % · proven greedy
floor); per-pass survivors; the **spec-completeness ETA in passes** (or "structure exhausted
— supply `--input`"); the written test file + wired `conftest.py`; and for any residual, the
exact `--input "(<slots>)"` to supply — plus, for a BOUNDARY residual, the **distinguishing
input named** (`_boundary_hint`: the equality edge, e.g. `supply an input where units == 100`).
`--input` supplies that residual and re-runs to close the loop.

### `audit file::fn [--remove]`  — read-only (unless `--remove`)
**Purpose:** assess an **existing** suite on both axes without changing it.
**Operation:** one `profile` of the current suite → `redundant_2axis` (pointless tests) +
`missing_lines` + `minimal_cover_2axis` + `classify_survivors` (killable gaps vs
equivalents). **You see:** N existing tests; kills %; mutant-complete / line-complete
(tiered, incl. "complete modulo N candidate-equivalent — flag to confirm"); the minimal
cover + bloat; pointless tests to prune; killable gaps with the input that kills them;
failing-test warnings; and `[audit reads only — writes nothing]`. `--remove` **confirms**
deletion of the proposed pointless tests (`apply_removals`), then re-audits. Deletion is
never automatic.

### `decompose file::fn [--apply] [--input "(…)"]`  — proves, then writes (with `--apply`)
**Purpose:** extract a compound block into a helper, **provably behavior-preserving** and
SICP-cleaner. **Operation** (`apply_decomposition`): (1) **converge** the target to a
mutation-complete suite = the behavioral spec/proof; (2) **cluster** the body into clean
extraction candidates (`find_extraction_candidates`: single-exit, small interface,
cognitive-complexity ≥3) — this is **structure-gated**, independent of test coverage;
(3) trial-apply each, re-run the suite, keep only what stays green (proof of preservation).
The proof gate is **mutation-completeness** (not line-completeness) — and **Detective need
not be the suite's author**: when converge writes nothing *because the pre-existing
hand-written suite already kills every killable mutant* (the best case), the proof is those
files. `_covering_test_files` resolves them from the `kill_matrix`, so only tests that
provably killed a mutant OF THIS TARGET can stand as proof — never the whole discovered
suite, which would let an unrelated passing test stand in. **You see:** `✓ APPLIED
(specified behavior preserved, auto)` with the extracted helper + thinned caller — but only
when the suite proved it. If converge could not reach mutation-completeness (a killable
mutant synthesis couldn't reach — the genuine "semantic prior" case), it says so and
surfaces the exact `decompose … --apply --input "(<slots>)"` to supply and close the loop.
`--apply` writes the file; without it, proposals are shown, never written.

### `flag file::fn MUTANT_ID [--note "why"]`  — manual oracle
**Purpose:** assert a surviving mutant is truly equivalent (nothing can kill it).
**Operation:** `profile` to find the survivor's `diff_summary` → `add_flag` →
`.detective/equivalents.json`. Future `classify_survivors` treats it as
`manual_equivalent`. **You see:** the survivor no longer counts as a gap. A later real
witness overrides it (proof beats opinion). Content-keyed: a code change to that line
invalidates the flag by design.

### `purge [--project-root .]`
Delete regeneratable analysis cruft from **both** packages: `.wesker/*_report.json` (via
`memory_guard.purge_caches`) **and** `.detective/verdict_cache.json` + `.detective/reports/`
(via `verdict_cache.purge`). Never touches generated tests, `conftest.py`, or the two user-data
files — `inputs.json` and `equivalents.json` (§8). Prints every path it removed; a purge that
claims cleanliness it did not achieve is worse than none.

`certify()` is no longer a CLI command (superseded by `converge`'s loop). It remains a
library API (`from Detective import certify`) and its module still backs the pytest wiring
(`wire_pytest`, `verify_under_pytest`) that `decompose` depends on — **and** `certify._write`, the
one choke point every generated test passes through on its way to disk, which is why the live
session's refresh (§2a) is published from there.

---

## 5a. The MCP surface — `detective-mcp` (`mcp_server.py`)

Five tools: `diagnose`, `converge`, `decompose`, `audit`, `deep_context`. Optional (`[mcp]`
extra); `mcp` is imported lazily so the core stays Wesker + stdlib. Zero compute — each tool calls
the same library the CLI does, inside the same live session (`_in_session` → `run_with_live_suite`,
scoping included). It went without that wrap once, calling the library directly, and every verdict
it returned on a fixture-driven repo was wrong in the tool's least honest direction: MORE
unspecified behavior than exists.

**It is not the CLI's text.** That was tried. `cli.py` renders every result correctly and
completely *for a human*, and relaying it verbatim to an LLM failed — the same bytes, in full,
went to stdout and were piped to `tail -3` unread. The CLI's rendering is a **theorem**: every
clause as true as the engine can make it. This surface's output is a **prompt**: correctness is
whether it is *effective*, not whether it is *true*, and it deliberately says things the CLI would
not. Both objects are right; they answer to different criteria.

| Choice | Why |
|---|---|
| **No score in the default view** | a ratio is the most reliable way to make an LLM caller reach outside the tool and grind. The numbers are real and correct — behind `full=True` / `deep_context`, where reading them is deliberate |
| **The mutant kinds ARE shown** | the failure is symmetrical: too terse and the task reads as scut work to shortcut. The behavioral distinctions are the interesting *and* honest part |
| **One next action, an imperative, never a menu** | not because the world is unambiguous — the equivalents fork is undecidable — but because the *caller's legal move set* is singular even when the epistemics are not |
| **Flat prohibitions** ("more passes will not help") | strictly these overclaim. They are the load-bearing sentences |
| **No `flag` tool, no `purge` tool** | `flag` is a human oracle on an undecidable question — the renderer routes it to the user instead. `purge` is a delete-state button, and handing one to a grinding caller invites "the number didn't move, purge and retry" |
| **A header on every CLI-rendered report** | `full=True`/`deep_context` return the CLI's text, which says `--input "(…)"`, `--apply`, `detective flag …` — terminal syntax the caller cannot invoke. The header says: read the detail, ignore the imperatives |

**The engine's epistemics are untouched — and that is checked, not assumed.** Nothing here
re-decides a verdict, softens an UNPROVEN, or spends a crash kill to flatter a number. The
renderers use **direct attribute access, never `getattr(obj, name, default)`**: a default silently
absorbs a wrong field name, and this file did exactly that — it asked `SurvivorReport` for
`candidate_equivalent` (the field is `equivalent`), got `()` forever, and reported *"the suite is
complete, nothing to derive"* over nine UNPROVEN survivors. The engine had classified them
honestly; the renderer promoted UNPROVEN to done. `trace_truncated` is surfaced first for the same
reason: a completeness verdict resting quietly on a truncated measurement is the one failure this
tool cannot afford, and a surface that drops the warning commits it while looking tidier.

---

## 6. The synthesis stack (how inputs are made AND rendered)

Witness search and golden capture both need inputs that (a) run the function and (b)
render into a runnable test. Literals cover scalars/containers; `SourceExpr` bridges
non-literals.

```
annotation ──_type_of──▶ type name
   scalar (int/str/float/bool)      → _grid_for / _SCALAR_SAMPLE           (literal)
   container (list[int], dict[...]) → _synth_from_ann (recurse elements)   (literal)
   dataclass                        → _synth_value (build from fields)     (object)
   ast.* (FunctionDef, expr, …)     → synth_ast_input (parse a snippet)    → SourceExpr
   unannotated                      → infer_param_types (call-site) → int fallback (§10)
   synthesis raises on every grid   → capture_call_inputs: reuse a REAL arg the covering
                                       tests pass (runtime harvest) → the honest last resort
```

- **Harvest, don't fabricate.** When every synthesized candidate raises (a domain object no
  grid builds), `capture_call_inputs` installs a `sys.setprofile` hook keyed to the target's
  code object, runs the discovered covering tests, and records the actual bound arguments —
  reusing a real input instead of guessing one. Fires lazily (only when the soundness gate
  would otherwise abstain); the abstention stays the honest Zone-3 fallback when even the
  tests don't exercise the DOF.
- **Minimal by construction.** After the final profile, converge drops any test it generated
  that is redundant for both kills and lines (`individual_test_names` maps a `redundant_2axis`
  finding back to the property) and re-profiles — the written suite is the minimal cover, not
  the full set plus removal proposals.

- **Call sites** `unwrap(arg)` so a `SourceExpr` runs as its live value; **render sites**
  use `repr(arg)` so `SourceExpr.__repr__` emits round-trippable constructor code, with
  imports threaded into the test header.
- **Assertion rendering** uses value-equality for set-containing outputs (repr order is
  hash-seed-dependent → flaky) else exact repr-equality.
- **Zone contract:** Zone-1 provable → auto-emit; **Zone-2** partial → the CLI emits the
  exact `--input` residual, the human supplies *that value*, the AST builds the test;
  Zone-3 can't-exercise → typed hand-off. The human never authors a test.

---

## 7. Performance & memory (the layers that keep it fast and bounded)

**Coverage-scoped test selection** (`run_function_profiling`, `scope_tests=True`): each
mutant runs only against the tests that **execute its mutated line** (each mutant carries
its `mutated_line` from the mutator fire site). Verdict-preserving — a test that never runs
the mutated line cannot observe the mutation — and the dominant speedup (4–7× locally, more
on large suites). Failing-baseline tests are folded into every scoped set so it stays
exactly identical to a full run.

**Content-hashed verdict cache** (`verdict_cache.py`, `.detective/verdict_cache.json`):
`profile()` serves an unchanged function's result from disk. Key = `func_key : AST-dump-hash
: tests-source-hash : max_per_category : pass_index : trace_budgets`. The AST hash is
position-independent (editing *other* functions never invalidates this one); any edit to the
function or its tests misses. A cache hit is byte-for-byte identical to a fresh run; only
complete (non-budget-exhausted) runs cache.

The **trace budgets are in the key** because they change the answer: a budget cuts the traced
baseline, and what it cut lands in the result as `truncated` and as absent `line_coverage`. A key
blind to them serves the tighter run's coverage to the looser one — which made the CLI's own
remedy ("raise `--trace-budget` to measure them fully") unfollowable: you raised it and the cached
under-count came back unchanged. Scoping is deliberately **not** in the key: scoped and full runs
are proven verdict-identical, so `paths` cannot change what a result says.

**The key is a positional contract with two readers** — `cache_key` builds it, `put` re-parses it
for single-valid-copy (drop this function's entries for the same *question* whose content hash no
longer matches, so the file stays bounded at one row per function/params). They must agree, so the
field count lives in `_PARAM_FIELDS` beside the builder and `put` calls `params_suffix()` rather
than slicing inline. Appending a field without that is not theoretical: it silently redefined the
slice, and a `--fast` run evicted the comprehensive entry it should have sat beside.

**No parallelism (removed in 0.8.0), and the deletion is the lesson.** `parallel.py` held a
model-A fan-out, an adaptive probe, a shard merge, and a portable memory guarantee sizing the
fleet by construction — ~200 lines, plus a private `Wesker.memory_guard._DEFAULT_WORKER_PEAK`
import. None of it ran. `main` wraps every command in the live session, the session's callables
cannot cross a process spawn, and `profile` therefore refused to fan out inside one — which is
every CLI and MCP run. Proven, not inferred: `--parallel` (5.04s) and `--serial` (5.13s) cost
the same, the 448-test suite made **0** calls to `parallel_profile`, and a *forced* `--parallel`
on a 37-mutant function spawned **0** workers while returning the identical verdict.

The apparatus was load-bearing only for itself. It existed because the baseline was
suite-shaped and per-function cost looked large; once the baseline became a per-session
constant, the cost it was built to amortise was already gone. The memory guarantee guarded a
fleet that never existed. **Serial is not a regression here — it is what was always running.**

---

## 8. Persisted state (what's on disk, who owns it)

| Path | Owner | Regeneratable? | Purged by `purge`? |
|---|---|---|---|
| `tests/test_<fn>_synth.py` | Detective (product output) | yes | **never** — it is the product |
| `conftest.py` (root) | Detective (pytest wiring) | yes | never |
| `.detective/reports/converge_<fn>.txt` | Detective (full converge report; terminal stays terse) | yes | **yes** |
| `.detective/verdict_cache.json` | Detective (profile cache) | yes | **yes** |
| `.detective/equivalents.json` | **user** (manual flags) | **no** | **never** |
| `.detective/inputs.json` | **user** (supplied `--input` samples — `samples.py`) | **no** | **never** |
| `~/.detective/telemetry.json` | Detective (per-machine per-mutant EMA) | yes | no (machine-global, not project state) |
| `.wesker/mutation_report.json`, `.wesker/mcdc_report.json` | Wesker | yes | yes (via `Wesker.memory_guard.purge_caches`) |

**`purge` spans BOTH packages, because neither can purge the other's.** `cli` calls
`memory_guard.purge_caches` for `.wesker/` **and** `verdict_cache.purge` for `.detective/`. It
used to delegate only to Wesker — written back when Wesker owned all the state — so it purged a
file that (outside Wesker's own tests) is never written, missed the multi-MB one that is, and
reported *"a clean state"* over it. A command that purges one of two caches while announcing
cleanliness is worse than one that purges neither: the user acts on the claim.

**The user/regeneratable split is the invariant, not a nicety.** `inputs.json` and
`equivalents.json` are the two things in the pipeline Detective **cannot derive** — the semantic
prior synthesis provably could not build, and a human's equivalence judgement on an undecidable
question. Purging them asks the person to redo the only irreducible work, which is the opposite of
this command's purpose. Everything else here is rebuilt from current code on the next run, so
purging can only ever cost time.

**Cross-run RAM state: none.** The two ContextVars (`_LIVE_SUITE`, `_SESSION_BASELINE`) live in
Wesker and exist only for the duration of one `run_with_live_suite` call; both are reset in its
`finally`. The MCP server holds nothing between calls — each tool opens its own session (§5a).

---

## 9. DEBUG MAP (symptom → touch this → why)

| Symptom | Touch | Why |
|---|---|---|
| Kills all show as **crash**, "0 pinned" on a real fn | this is the crash-vs-value split — check the synthesized input actually RETURNS (not crashes) | `value_killed` counts assertion kills only; a crash-killed mutant is a value-survivor |
| A mutant a value-assertion *should* kill stays a survivor | `Wesker.engine.evaluate_mutant` (value-precedence: assertion kill beats a crash kill; keep scanning past crash kills) | else a crash-killer that runs first stamps `killed_by=crash` and hides the value-kill |
| `find_witness` suggests a crash input as "killable" | `equivalence.find_witness` (skips "mutant newly raises") | a crash-kill doesn't pin value; keep searching for a value-witness |
| `decompose` says "no separable blocks" on a big fn | `decompose.find_extraction_candidates` gates (single-exit, ≤4in/≤2out, CC≥3) | flat/wide fns (dict-builders) have no small-interface block — correct, not a bug |
| `decompose` won't prove a clearly-decomposable fn | `decompose_apply.apply_decomposition` proof gate = `functionally_complete` (NOT `line_complete`) | mutation-completeness is the proof; line-completeness is orthogonal |
| `decompose` refuses a fn whose EXISTING suite already specifies it | `decompose_apply._covering_test_files` — the proof falls back to the hand-written covering files when converge writes nothing (`written_path` None ∧ `functionally_complete`) | the proof is mutation-completeness, not authorship; gating on "Detective wrote it" rejected the best case |
| `decompose` says "not mutation-complete" but converge reports COMPLETE | `cli._format_decompose` — a complete suite that rejects the rewrite reads `REJECTED … PROVES this extraction changes behavior` | the three causes (no suite / incomplete suite / disproved) are distinct verdicts and must not share one message |
| `decompose` can't prove & gives no way forward | `_format_decompose` residual block (reads `result.proof`) | surface the `--input` the internal converge computed |
| `diagnose` says "decompose" but decompose finds nothing | `_format_scope` convergent signal (`regime B` **and** `decompose_seams`) | only flag decompose when a structural seam exists |
| extracted helper carries the PARENT's docstring (and the parent loses its own) | `decompose.find_extraction_candidates` skips a leading docstring (`ast.get_docstring`) | a docstring belongs to the function, never to an extracted block |
| converge writes a test its own audit then calls redundant | converge step 4 minimize (`redundant_2axis` + `writer.individual_test_names`) | ship the minimal cover, not the full set + removal proposals |
| Cache serves a stale result | `verdict_cache.cache_key` | must hash fn-AST + tests-source + params + **trace budgets**; content, never path. Anything that can change the answer belongs in the key |
| **The command prints NOTHING and exits 0** (in CI: an empty artifact, a green check) | `Wesker.engine._run_test_with_timeout` — `_abandon` + the unwind join must happen INSIDE the redirect | the baseline runs the target's own suite; a test over its cap is abandoned, and the abandoned frame unwinds through any `redirect_stdout` IT entered, reinstalling that buffer AFTER the engine restored the real one. `sys.stdout` is then a dead buffer for the rest of the PROCESS. Belt-and-braces: `ci._body` re-enters the streams around the baseline. **Not a crash — the analysis is correct and posted to a discarded buffer** |
| `converge` reports a tiny kill count, calls itself Incomplete, and asks for inputs it does not need | `certify._write` → `Wesker.ci.refresh_live_suite` | the live session's collection is a SNAPSHOT; converge writes tests, re-profiles, and is handed a list predating its own work (measured: 18 killed on disk, 2 reported). The refresh must ALSO invalidate the `SessionBaseline` — refreshing the list alone changes what is *discovered*, not what is *run*, and the count stays exactly as wrong |
| `--trace-budget` / `--trace-session-budget` change nothing | `cli._run_live` must pass them to `run_with_live_suite`, not only to `profile()` | on the live path the suite is traced inside the seam; the per-function path a session never uses was the only thing hearing the flag |
| A warm cache is still slow (full trace before an instant answer) | `Wesker.engine.LazySessionBaseline` — the baseline must stay demand-driven | built eagerly it is the whole cost of a run, paid *outside* the region the cache protects, then dropped unread (Regenesis: 486s → 3.6s once lazy) |
| `diagnose` on a big repo traces the whole suite for one small function | `cli._reachable_paths` → `reachability.reachable_test_paths` → the session's `paths` | scoping must happen at pytest COLLECTION, before anything is imported — `scope_tests` selection is derived FROM the trace, so it cannot save the trace |
| An MCP tool reports "complete / nothing to derive" over UNPROVEN survivors | `mcp_server` — direct attribute access, never `getattr(obj, name, default)` | a default silently absorbs a wrong field name; `SurvivorReport.equivalent` was asked for as `candidate_equivalent` and returned `()` forever. A rename must break loudly, not promote UNPROVEN to done |
| Generated test is **flaky** (set output) | `characterization.golden_assert_line` | set repr order is hash-seed-dependent → value-equality |
| `verify_under_pytest` reports 0 passed for a passing suite | `certify.verify_under_pytest` | `-o addopts=` so the target's `-q` doesn't become `-qq` |
| Survivor reads "uncertain — inputs don't exercise" | `engine._input_grids` / `representative_site` / `call_sites` / `capture.capture_call_inputs` (runtime harvest) | synthesis can't build a fitting value AND no covering test exercises it (domain-value / unannotated — §10) |
| a BOUNDARY residual says "supply an input" but not WHICH | `cli._boundary_hint` names the equality edge (`left == right`) | a `>`↔`>=` shift differs exactly when operands are equal — the valid relation, not a generic template |
| memory grows on a huge run | `run_function_profiling` mutant loop + `memory_guard.over_budget` | guard bounds accumulation |

---

## 10. Known boundaries & open gaps (honest)

**Synthesis boundaries (the real limits behind most "uncertain"/"equivalent" verdicts).**
Unannotated params fall back to `int` (after a call-site inference attempt); **domain-value
inputs** (lookup keys, specific source strings, valid domain dicts) aren't synthesizable →
they surface as a Zone-2 `--input` residual (the correct hand-back, not a defect); self-only
methods have no receiver synthesis; integration fns (subprocess/file-IO) and engine-core
(the profiler itself) can't self-profile. The fix is always richer input synthesis or a
supplied `--input` / manual `flag` — **never a hand-written test**.

**Open / deferred (not blocking).** σ-based spec-completeness ETA (upgrade the "≈N passes"
estimate to a paper-grounded model); occasional `converge` multi-pass progress cosmetics.

**The decompose↔spec coupling (design, not bug).** A function converge can fully specify
(pure, simple inputs) decomposes cleanly cold; one it can't (dicts/methods) needs a supplied
`--input` first — the tool surfaces exactly that input, and the loop closes **whenever the
residual is expressible as a Python literal**.

**Where the `--input` loop does NOT close (the scope of the hand-back).** `--input` is
`ast.literal_eval` only — deliberately: no code execution (§6). So it can carry a scalar,
container, dict or string, but *not an instance* — a `ProfilingResult`, a `SourceExpr`, any
domain object. The residual is still printed for those (`--input "(<result>,)"`); it simply
cannot be filled. The complement is `capture_call_inputs` (§6, "harvest, don't fabricate"),
which reuses a REAL argument from the covering tests — so an object-parameter function is
specifiable *iff some test already passes it one*. A cold function whose parameter is a
domain object is reachable by neither, and that is the honest Zone-3 abstention, not a
defect. Detective's own core is largely in this class (it passes `ProfilingResult` around),
which is why `scope.py::scope_from_profiling` is its own top decompose candidate and still
needs a covering test to harvest from.

---

## 11. Working on this codebase (the discipline)

**Dogfood before AND after every function change** — profile with the literal `detective`
(this *is* the product's intended workflow, not a checkbox):

```
PYTHONPATH=/Users/rohanvinaik/tools/Detective \
  /Users/rohanvinaik/tools/Wesker/.venv/bin/python -m Detective.cli \
  converge "PATH::FUNC" --project-root ROOT   # generates its tests AND tests the pipeline
```

- **Serena for navigation** (symbol graph, references) — not grep/name-matching; it is a
  dev-time oracle, never a runtime dependency.
- **Never hand-write** a test for a Detective/Wesker function — run `converge`; if it can't,
  fix the *input generation* (§6) or supply the `--input` residual, don't hand-write.
- **Bidirectional**: if dogfooding shows the bug is in Wesker, the fix goes in Wesker.
- **Auto-apply principle**: deterministically-correct → auto; only-mostly-correct → propose
  (show code); **deletion is never auto** (propose + confirm).
- **Determinism is the product** (the audience is Sussman-lineage): any cache is
  content-addressed, any run repeatable. Verify, don't assume — and verify a path RUNS before
  optimising it (§7: a fan-out was tuned for releases without ever spawning a worker).
- **The unit is ONE function's operators and ONE function's tests.** Both are static and free:
  the mutant space is a property of THIS function's AST (`+` has a `-`, derived de novo, exactly),
  and a green suite is a set of grounded facts you are GIVEN. Anything that aggregates across
  functions is not a slow path, it is a different question. `diagnose --learn` was the standing
  violation and was removed in 0.8.0: it accumulated per-category value-survival into a
  project-wide `.wesker/mutation_report.json` and reported "which categories THIS project leaves
  weak" — a statistical smear over unrelated functions, standing where an exact per-function
  derivation already was. It changed no verdict; nothing branched on it, no test named it, and it
  only ever ordered categories for a sampler this tool does not use by default. There is no such
  object as "the mutant profile of a codebase" worth computing.
- Engine-core / integration fns that can't self-profile are guarded by the unit suite — the
  *only* exemption from the converge rule.

Suites: Detective `python -m pytest` (258 green) + Wesker (92 green), run with the Wesker
venv python and `PYTHONPATH` at the repo root. Push / PyPI publish are **user-only**.
