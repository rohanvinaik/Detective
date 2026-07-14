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
cross-run RAM state; persisted state is on disk (§8). Profiling is **content-cached**
and **adaptively parallelized** — both transparent, both verdict-identical to a plain
serial run (§7).

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
| `discover_test_callables(root, rel, func_names, extra_dirs)` → `list[Callable]` | `Wesker.ci` | find the real tests exercising a function (pytest-aware, binds parametrize) |
| `walk_functions(tree)` → `[(qualname, node), …]` | `Wesker.ci` | enumerate functions in a module |
| `filter_categories(node, pure)` → `set[MutationCategory]` | `Wesker.filter` | which mutation categories apply (drops STATE for pure fns) |
| `prioritize_categories(cats, state)` | `Wesker.filter` | learned-weak ordering (`diagnose --learn`) |
| `worker_count`, `apply_address_limit` | `Wesker.memory_guard` | parallel fleet size (portable memory guarantee) + best-effort `RLIMIT_AS` |
| `telemetry`, `purge_caches` | `Wesker.memory_guard` | CLI footer + `purge` command |

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
| `failing_tests` | list[str] | tests that `assert`-fail on the UNMUTATED function → audit ⚠ |
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
| Common flags | `--project-root`, `--json`, `--parallel`/`--serial` (diagnose/converge/audit) | per-command behavior (§5) |
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
  `learned_priors` (opt-in `--learn`), **`decompose_seams`** (structural extraction count —
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
  `.complete_modulo_equivalent`, `.bloat`.
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
| `engine.py` | **THE Wesker adapter** + caching + adaptive parallelism + witness classification + input synthesis | `profile`, `diagnose`, `classify_survivors`, `representative_site`, `learn_priors`, `_count_decompose_seams`, `_load_original` |
| `verdict_cache.py` | **content-hashed profile cache** (§7) | `cache_key`, `get`, `put`, `_to_json`/`_from_json`, `tests_fingerprint` |
| `parallel.py` | **model-A fan-out** + adaptive merge (§7) | `parallel_profile`, `merge_results`, `shard_bounds`, `mean_mutant_ms` |
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
| `cli.py` | arg parsing + formatting (`--version`, streaming narrative, minimal terse view + `--full`); **zero compute** | `main`, `_run`, `_build_parser`, `_parallel_mode`, `_format_converge`/`_format_converge_terse`, `_final_banner`, `_plain_terms`, `_boundary_hint`, `_notify_stderr`, `_write_converge_report` |
| `mcp_server.py` | optional MCP surface (`detective-mcp`): exposes `diagnose`/`certify`; zero compute | `build_server`, `main` |
| (Wesker) `memory_guard.py` | RAM budget, fleet sizing, `RLIMIT_AS`, telemetry, purge | `resolve_budget`, `worker_count`, `apply_address_limit`, `over_budget`, `telemetry` |

---

## 5. The CLI — every command, fully explained

Shape: `detective <command> file.py::function [flags]`. `cli._run` splits the target,
calls the library, prints a formatter; `cli.main` emits a `memory_guard.telemetry()` footer
to **stderr**. `detective --version` reports the package version. Live mutation progress and
the converge phase narrative also stream to **stderr**, so stdout stays clean for the result
/ `--json` (and the terse `FINAL` banner stays the last stdout line). Common to most
commands: `--project-root` (default `.`), `--json`. Commands: `converge`, `audit`,
`decompose`, `diagnose`, `flag`, `purge` (`certify` is a library API, not a CLI command).

**Parallelism (diagnose · converge · audit).** Default is **adaptive auto**: a tiny
serial probe measures this function's real per-mutant cost, then it fans mutants across
worker processes *only if the remaining work justifies the spawn tax* — so small/fast
functions stay serial (≈2 ms overhead) and slow ones parallelize. `--parallel` forces the
whole run parallel (streaming disabled); `--serial` forces serial. Verdicts are **identical**
in every mode; the memory guarantee holds by construction (§7).

### `diagnose file::fn [--learn] [--parallel|--serial]`  — read-only
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
`--learn` also folds this run's per-category value-survival into
`.wesker/mutation_report.json` and prints the **learned-weak** priors (which categories
THIS project recurrently leaves value-unspecified).

### `converge file::fn [--write-dir tests] [--max-iterations N] [--fast] [--full] [--input "(…)"] [--parallel|--serial]`  — the flagship, writes tests
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

### `audit file::fn [--remove] [--parallel|--serial]`  — read-only (unless `--remove`)
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
The proof gate is **mutation-completeness** (not line-completeness). **You see:** `✓ APPLIED
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
Delete regeneratable analysis cruft (`.wesker/*.json`). Never touches generated tests,
`conftest.py`, or `.detective/` (user data).

`certify()` is no longer a CLI command (superseded by `converge`'s loop). It remains a
library API (`from Detective import certify`) and its module still backs the pytest wiring
(`wire_pytest`, `verify_under_pytest`) that `decompose` depends on.

**MCP** (`detective-mcp`): exposes `diagnose`/`certify` only; zero compute.

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
: tests-source-hash : max_per_category : pass_index`. The AST hash is position-independent
(editing *other* functions never invalidates this one); any edit to the function or its
tests misses. Single-valid-copy: a new hash purges the function's prior entry. A cache hit
is byte-for-byte identical to a fresh run; only complete (non-budget-exhausted) runs cache.

**Adaptive parallelism** (`parallel.py`, model A): the default. A small serial **probe**
times this function's real per-mutant cost (killing the stale-rate guessing problem), and —
if the remaining serial work exceeds the spawn tax — fans the remainder across `spawn`
worker processes (each re-imports, re-discovers, evaluates one contiguous mutant slice) and
merges. The probe is reused as shard 0 (and its baseline is shared), so the measurement is
≈free. Merge concatenates records in mutant order → **bit-identical to serial** (verified).
Progress can't stream across processes, so a fanned run prints a one-line `⚡ N mutants
across W workers` notice instead.

**Portable memory guarantee** (`memory_guard.py`): the fleet is sized so
`workers × per_worker_peak ≤ budget` **by construction** — pure arithmetic, identical on
Mac/Windows/Linux (`worker_count = min(cores−2, ⌊budget/peak⌋)`, budget = a RAM fraction
clamped to a ceiling). This is the *hard* guarantee, needing no OS resource limit.
`RLIMIT_AS` (best-effort, Linux only — macOS rejects it, Windows lacks `resource`) and a
`getrusage` self-check are bonus enforcement where the OS cooperates. `resource` is imported
defensively, so Wesker also imports on Windows. `WESKER_MEM_BUDGET_MB` overrides the budget.

---

## 8. Persisted state (what's on disk, who owns it)

| Path | Owner | Regeneratable? | Purged by `purge`? |
|---|---|---|---|
| `tests/test_<fn>_synth.py` | Detective (product output) | yes | never |
| `conftest.py` (root) | Detective (pytest wiring) | yes | never |
| `.detective/reports/converge_<fn>.txt` | Detective (full converge report; terminal stays terse) | yes | (under `.detective/`) |
| `.detective/equivalents.json` | **user** (manual flags) | **no** | **never** |
| `.detective/verdict_cache.json` | Detective (profile cache) | yes | (content-invalidated) |
| `~/.detective/telemetry.json` | Detective (per-machine per-mutant EMA) | yes | — |
| `.wesker/function_cache.json`, `.wesker/*_report.json` | Wesker | yes | yes |

Detective holds **no** cross-run RAM state (MCP server is stateless; CLI frees on exit).

---

## 9. DEBUG MAP (symptom → touch this → why)

| Symptom | Touch | Why |
|---|---|---|
| Kills all show as **crash**, "0 pinned" on a real fn | this is the crash-vs-value split — check the synthesized input actually RETURNS (not crashes) | `value_killed` counts assertion kills only; a crash-killed mutant is a value-survivor |
| A mutant a value-assertion *should* kill stays a survivor | `Wesker.engine.evaluate_mutant` (value-precedence: assertion kill beats a crash kill; keep scanning past crash kills) | else a crash-killer that runs first stamps `killed_by=crash` and hides the value-kill |
| `find_witness` suggests a crash input as "killable" | `equivalence.find_witness` (skips "mutant newly raises") | a crash-kill doesn't pin value; keep searching for a value-witness |
| `decompose` says "no separable blocks" on a big fn | `decompose.find_extraction_candidates` gates (single-exit, ≤4in/≤2out, CC≥3) | flat/wide fns (dict-builders) have no small-interface block — correct, not a bug |
| `decompose` won't prove a clearly-decomposable fn | `decompose_apply.apply_decomposition` proof gate = `functionally_complete` (NOT `line_complete`) | mutation-completeness is the proof; line-completeness is orthogonal |
| `decompose` can't prove & gives no way forward | `_format_decompose` residual block (reads `result.proof`) | surface the `--input` the internal converge computed |
| `diagnose` says "decompose" but decompose finds nothing | `_format_scope` convergent signal (`regime B` **and** `decompose_seams`) | only flag decompose when a structural seam exists |
| extracted helper carries the PARENT's docstring (and the parent loses its own) | `decompose.find_extraction_candidates` skips a leading docstring (`ast.get_docstring`) | a docstring belongs to the function, never to an extracted block |
| converge writes a test its own audit then calls redundant | converge step 4 minimize (`redundant_2axis` + `writer.individual_test_names`) | ship the minimal cover, not the full set + removal proposals |
| Parallel/auto result differs from serial | `parallel.merge_results` (shard-order concat) + `run_function_profiling` `mutant_slice` | records must concatenate in mutant-index order |
| Cache serves a stale result | `verdict_cache.cache_key` | must hash fn-AST + tests-source + params; content, never path |
| Generated test is **flaky** (set output) | `characterization.golden_assert_line` | set repr order is hash-seed-dependent → value-equality |
| `verify_under_pytest` reports 0 passed for a passing suite | `certify.verify_under_pytest` | `-o addopts=` so the target's `-q` doesn't become `-qq` |
| Survivor reads "uncertain — inputs don't exercise" | `engine._input_grids` / `representative_site` / `call_sites` / `capture.capture_call_inputs` (runtime harvest) | synthesis can't build a fitting value AND no covering test exercises it (domain-value / unannotated — §10) |
| a BOUNDARY residual says "supply an input" but not WHICH | `cli._boundary_hint` names the equality edge (`left == right`) | a `>`↔`>=` shift differs exactly when operands are equal — the valid relation, not a generic template |
| memory grows on a huge run | `run_function_profiling` mutant loop + `memory_guard.over_budget` | guard bounds accumulation; parallel bounds the fleet by construction |

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
estimate to a paper-grounded model); occasional `converge` multi-pass progress cosmetics;
tuning of the adaptive-parallel thresholds (`PROBE_SIZE`, `PARALLEL_MIN_REMAINING_MS`).

**The decompose↔spec coupling (design, not bug).** A function converge can fully specify
(pure, simple inputs) decomposes cleanly cold; one it can't (dicts/methods) needs a supplied
`--input` first — the tool now surfaces exactly that input, so the loop always closes.

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
- **Determinism is the product** (the audience is Sussman-lineage): any parallel path must
  be bit-identical to serial, any cache content-addressed. Verify, don't assume.
- Engine-core / integration fns that can't self-profile are guarded by the unit suite — the
  *only* exemption from the converge rule.

Suites: Detective `python -m pytest` (258 green) + Wesker (92 green), run with the Wesker
venv python and `PYTHONPATH` at the repo root. Push / PyPI publish are **user-only**.
