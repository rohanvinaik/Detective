# Detective — Architecture & Operational Map

The single reference for **what Detective does, how it does it, and where to look
when something breaks.** If you arrived cold: read §1 (mental model), skim §3
(data structures) and §5 (per-command flows), and keep §9 (debug map) open — a bug
symptom there points you at the exact function and why it fails.

Detective is a **clean-room** package on **Wesker + stdlib only** (no lintgate in
the runtime import graph). Runtime dep: `Wesker` (git URL). Console scripts:
`detective` (CLI) and `detective-mcp` (optional MCP). Everything below is operational.

---

## 0. Thesis (the one idea)

A function's **mutation profile is a complete map of the behavioral distinctions it
makes.** Killed mutant = a distinction the tests pin. Survivor = a degree of freedom
no test distinguishes. Read backwards, that map is a *specification*: it tells you
exactly which behaviors are unpinned, so you can pin them with warranted tests, or
recognize that nothing *can* pin them (equivalent mutants). Everything Detective
does is a consumer of that map.

Two orthogonal completeness axes drive the whole system:
- **Mutant completeness** — every *killable* mutant is killed (a test distinguishes it).
- **Line completeness** — every executable line is covered by some test.
A suite is **complete** iff both hold, and **minimal** iff no test can be dropped
without losing a kill or a line (a two-axis set cover).

---

## 1. Mental model (the pipeline in one breath)

```
  your function ──▶ Wesker (mutate + run tests) ──▶ ProfilingResult
                                                        │
        ┌───────────────────────────────────────────────┤
        ▼                    ▼                 ▼          ▼
     scope             classify_survivors   minimize   line-coverage
   (diagnose)          (killable/equiv/     (2-axis     (which test hits
                        uncertain, by        cover)      which line)
                        EXECUTION)
        │                    │                 │          │
        └──────────▶ converge / audit / decompose ◀───────┘
                          │
                          ▼
                clean pytest files on disk + a validation report in the CLI
```

Detective **owns one function at a time.** Every command takes a `file.py::function`
target, asks Wesker to profile it, then reshapes/acts on the result. Detective holds
no cross-run state in RAM; the only persisted state is on disk (§4, §8).

---

## 2. The two input surfaces

### 2a. INPUT FROM WESKER (the engine seam) — `Detective/engine.py`, `Detective/scope.py`

Detective imports exactly these from Wesker (the *entire* dependency surface):

| Import | From | Used for |
|---|---|---|
| `run_function_profiling(node, func_key, categories, tests, original, *, budget_ms, mem_budget_mb)` | `Wesker.engine` | THE profile call — mutate + run tests + baseline line-coverage |
| `generate_mutants(func_node, categories)` → `list[Mutant]` | `Wesker.engine` | rebuild the mutant set to witness-search survivors (`classify_survivors`) |
| `ProfilingResult`, `CategoryResult` | `Wesker.engine` | the result type (see §3) |
| `discover_test_callables(root, rel, func_names)` → `list[Callable]` | `Wesker.ci` | find the real tests that exercise a function (pytest-aware, binds parametrize) |
| `walk_functions(tree)` → `[(qualname, node), …]` | `Wesker.ci` | enumerate functions in a module |
| `filter_categories(node, pure)` → `set[MutationCategory]` | `Wesker.filter` | which mutation categories apply (drops STATE for pure fns) |
| `telemetry()`, `purge_caches(root)` | `Wesker.memory_guard` | CLI footer + `purge` command |

**What Detective gets back — `ProfilingResult`** (produced by `run_function_profiling`;
this is the single most important object in the system):

| Field | Type | Meaning | Consumed by |
|---|---|---|---|
| `function_key` | str | `rel/path.py::qualname` | everywhere as the identity |
| `total_mutants / total_killed / total_survived / total_equivalent` | int | headline counts | scope, converge, audit |
| `universe_size` | int | full mutant universe | scope |
| `per_category` | list[`CategoryResult`] | per-category kill/survive/`killed_by_assertion`/`killed_by_crash` | scope (kill-quality) |
| `kill_matrix` | dict[mutant_desc → list[test_name]] | which tests kill which mutant | minimize (2-axis cover) |
| `survivor_records` | list[dict] | each: `mutant_id`, `mutant` (desc), `category`, `diff_summary`, `elapsed_ms` | classify_survivors, converge, audit |
| `killed_records` | list[dict] | each: `mutant_id`, `mutant`, `category`, `killed_by`, `test`, `elapsed_ms` | scope (load-bearing tests, kill quality) |
| `line_coverage` | dict[test_name → list[int]] | which target lines each test covers (baseline pass) | minimize (line axis), audit |
| `executable_lines` | list[int] | statement lines of the target (the denominator) | minimize (missing_lines) |
| `failing_tests` | list[str] | tests that `assert`-fail on the UNMUTATED function | audit (⚠ warn) |
| `budget_exhausted` | bool | time or MEMORY budget stopped the run early | (surfaced as partial) |

`line_coverage`, `executable_lines`, `failing_tests` are populated by Wesker's
**baseline pass** (`Wesker/line_coverage.py`: `executable_lines`, `trace_line_coverage`
via `sys.settrace`, `failing_on_baseline`) which runs each test once against the
original *before* the mutation loop. The mutation loop stays untraced (fast).

### 2b. INPUT FROM THE USER

| Surface | Where | What |
|---|---|---|
| CLI target | `file.py::function` positional | the one function to act on |
| CLI flags | `--project-root`, `--write-dir`, `--json`, `--apply` (decompose), `--remove` (audit), `--note` (flag), `--max-iterations` (converge) | per-command behavior |
| `.detective/equivalents.json` | project root | **manual equivalence flags** (user data — see §8); read by `classify_survivors` |
| `WESKER_MEM_BUDGET_MB` | env var | user-selectable memory ceiling (§7) |
| existing test files | project `tests/` etc. | the suite `audit` assesses and `converge` augments (discovered by Wesker) |
| `.wesker/function_cache.json` | project root | Wesker's per-function result cache (regeneratable; `purge`-able) |

---

## 3. Core data structures (what flows between stages)

All in `Detective/`. Frozen dataclasses unless noted.

- **`ScopeMap`** (`scope.py`) — *diagnose output.* `regime` (A tractable / B entangled),
  `specification` (variants/pinned/unspecified/inert), `kill_quality`
  (`by_value_assertion` vs `by_crash` + warning), `behavioral_dof` per category.
  Produced by `scope_from_profiling(ProfilingResult)`. Consumed by CLI `_format_scope`.
- **`Witness`** (`equivalence.py`) — a concrete input where original and mutant differ:
  `args`, `original` (repr of original's outcome), `mutant`. **A witness is PROOF of
  killability** = a concrete killing test. Produced by `find_witness`.
- **`MutantVerdict`** (`equivalence.py`) — one survivor classified: `killable` (bool),
  `witness` (present iff killable), `category`, `diff_summary`. Produced by `classify_survivor`.
- **`SurvivorReport`** (`equivalence.py`) — per-function classification: `verdicts`
  (→ `.killable` / `.equivalent` props), `unclassified` (couldn't build/exercise),
  `manual_equivalent` (user-flagged), `note`. Produced by `engine.classify_survivors`.
  **The buckets are disjoint; completeness checks read them directly.**
- **`SourceExpr`** (`equivalence.py`) — a synthesized **non-literal** input (an AST node,
  a constructed object): `value` (live object for calling), `expr` (constructor source
  for rendering), `imports`. `__repr__` returns `expr`, so every `repr(arg)` render seam
  emits round-trippable code for free; `unwrap(arg)` gives the live value at call sites.
  This is how AST/object inputs both *run* and *render into a test*.
- **`GoldenCapture`** (`synthesis/characterization.py`) — a pinned return value: `inputs`,
  `output` (repr), `deterministic`, `provenance`. Produced by `capture_golden`.
- **`ExecutableProperty`** (`synthesis/oracle_light.py`) — one test-to-be: `category`,
  `setup_code`, `assertion_code`, `needs_oracle`, `confidence`, `preconditions`. The unit
  the writer renders. Produced by `generate_executable_property` and converge's
  `_golden_property`/`_witness_property`.
- **`ConvergeResult`** (`converge.py`) — converge output: `functionally_complete`,
  `line_complete`, `at_ceiling`, `missing_lines`, `redundant_tests`, `minimal_test_count`,
  `survivor_report`, `wiring`, `written_path`, `total_mutants`/`killed`. `.complete` =
  functionally ∧ line complete.
- **`SuiteAudit`** (`audit.py`) — audit output: `mutant_complete`, `line_complete`,
  `redundant_tests` (propose-delete), `failing_tests` (warn), `killable_gaps`,
  `missing_lines`, `minimal_test_count`, `manual_equivalent`, `.bloat`, `.complete`.
- **`Extraction` / `DecompositionApply`** (`decompose_apply.py`) — a generated helper
  (`helper_name`, `params`, `returns`, `new_source`) and the apply outcome (`applied`,
  `proposed`, `unsafe_blocks`).
- **`EquivalenceFlag`** (`equivalents.py`) — a manual equivalence assertion:
  `func_key`, `diff`, `verdict`, `note`. Keyed by `flag_key(func_key, diff)` = func_key
  + sha256(diff)[:16]. The diff embeds the code, so a flag is content-validated for free.

---

## 4. Module map (responsibility · key functions · in→out)

| Module | Responsibility | Key functions | In → Out |
|---|---|---|---|
| `engine.py` | **THE Wesker adapter** + witness classification + input synthesis | `profile`, `diagnose`, `classify_survivors`, `representative_site`, `_input_grids`, `_synth_from_ann`, `_synth_value`, `_compile_mutant`, `_load_original` | file::fn → ProfilingResult / ScopeMap / SurvivorReport |
| `scope.py` | reshape ProfilingResult → behavioral map | `scope_from_profiling` | ProfilingResult → ScopeMap |
| `equivalence.py` | classify survivor killable/equivalent BY EXECUTION; input typing; SourceExpr | `find_witness`, `classify_survivor`, `_outcome`, `_type_of`, `synth_ast_input`, `unwrap`, `bounded_product`, `typed_inputs` | (original, mutant, inputs) → MutantVerdict |
| `purity.py` | is-pure predicate (gates STATE mutations, golden capture) | `is_pure`, `analyze_function` | fn node → bool |
| `synthesis/typed_synthesis.py` | annotation → representative value | `synthesize_value`, `_resolve_dataclass` | type → value |
| `synthesis/characterization.py` | golden capture + assertion rendering | `capture_golden`, `corroborate_captures`, `golden_assert_line`, `_try_capture` | (live fn, sites) → GoldenCapture; output → assertion |
| `synthesis/oracle_light.py` | survivor → relational ExecutableProperty (6 category generators) | `generate_executable_property`, `_import_line` | survivor dict → ExecutableProperty |
| `synthesis/writer.py` | assemble properties into an idiomatic pytest module | `render_module`, `synthesize_test_module`, `_collect_imports` | [ExecutableProperty] → pytest source |
| `converge.py` | **the closed loop**: diagnose→synth-sound→write→re-profile to the ceiling | `converge`, `property_holds`, `_golden_property`, `_witness_property`, `_setup_with_imports` | file::fn → ConvergeResult + test file |
| `certify.py` | one-shot diagnose+synthesize (older front door) + pytest wiring | `certify`, `wire_pytest`, `verify_under_pytest`, `ensure_conftest`, `_write` | file::fn → CertifyResult + test file |
| `minimize.py` | two-axis set cover (kill ∪ line) | `minimal_cover_2axis`, `redundant_2axis`, `missing_lines`, `_obligations_by_test` | (kill_matrix, line_coverage) → minimal set / redundant / gaps |
| `audit.py` | read-only assessment of an EXISTING suite | `audit_suite` | file::fn → SuiteAudit |
| `suite_edit.py` | apply confirmed test deletions | `remove_function_from_source` (pure), `apply_removals` | (source, name) → source; names → RemovalReport |
| `decompose.py` | propose extraction candidates (structural) | `decompose` | fn node → DecompositionPlan |
| `decompose_apply.py` | **extract-function**: analyze → generate → execution-validate → apply | `block_interface`, `structural_bindings`, `control_escapes`, `extract_block`, `preserves_behavior`, `apply_decomposition` | source → Extraction (validated) |
| `equivalents.py` | persist/read manual equivalence flags | `add_flag`, `load_flags`, `flag_key`, `is_flagged_equivalent` | (func_key, diff) → EquivalenceFlag store |
| `cli.py` | arg parsing + formatting; **zero compute** | `main`, `_run`, `_build_parser`, `_format_*` | argv → stdout + exit code |
| `mcp_server.py` | optional MCP wrapper (diagnose/certify); zero compute | `build_server`, `main` | MCP calls |
| (Wesker) `memory_guard.py` | RAM budget, telemetry, cache purge | `resolve_budget`, `over_budget`, `telemetry`, `purge_caches` | — |

---

## 5. Operational flows (per CLI command — what actually happens)

Every command: `cli._run` splits the target, calls the library function, prints a
formatter, then `cli.main` appends a `memory_guard.telemetry()` footer.

**`diagnose file::fn`** → `engine.diagnose` → `engine.profile` (Wesker) →
`scope.scope_from_profiling(ProfilingResult)` → `ScopeMap` → `cli._format_scope`.
*You get:* regime, variant/pinned/unspecified counts, kill quality. (Theory-heavy;
this is the raw scope read, not an action list.)

**`converge file::fn [--write-dir tests] [--max-iterations N]`** → `converge.converge`:
1. Parse file, resolve node, compute `func_key`.
2. **Loop** (≤ max_iterations): `profile` → survivors. Build properties:
   `oracle_light.generate_executable_property` per survivor + (if pure)
   `_golden_properties` (via `representative_site` → `capture_golden`). Keep only
   properties that **hold on the unmutated fn** (`property_holds` execs setup+assertion;
   catches `_pytest.outcomes.Failed` which is BaseException). Accumulate the UNION across
   passes; render with `writer.render_module`; `_write` to disk. Stop at 0 survivors,
   no-progress, or no-new-sound-test.
3. **Witness pass**: `classify_survivors` → for each killable witness whose original
   *returns a value*, auto-write a golden test at that input (`_witness_property`).
   ⚠️ **Witnesses whose original RAISES are only suggested, not written** (see §9/§10).
4. **Final profile** (authoritative). Compute `functionally_complete`
   (`not killable and not unclassified`), `missing_lines`/`minimal`/`redundant` via
   `minimize`, wire pytest (`certify.wire_pytest`).
*You get:* `tests/test_<fn>_synth.py` (clean pytest), a wired `conftest.py`, and a
report: mutation score, completeness on both axes, minimal-suite size, what was
auto-applied vs. suggested.

**`audit file::fn [--remove]`** → `audit.audit_suite`: one `profile` of the *current*
suite → `redundant_2axis` (pointless tests) + `missing_lines` + `minimal_cover_2axis`
+ `classify_survivors` (killable gaps vs. manual-equivalents). `--remove` →
`suite_edit.apply_removals(redundant_tests)` then re-audit. *You get:* complete?/minimal?
verdict, pointless tests to prune (propose; `--remove` executes), killable gaps with
kill inputs, failing-test warnings.

**`decompose file::fn [--apply]`** → `decompose_apply.apply_decomposition`: for each
`decompose.decompose` candidate block, `extract_block` (scope analysis →
`block_interface` params/returns; `control_escapes` rejects return/yield/free-break) →
`preserves_behavior` (run original vs decomposed on synthesized inputs). Validated →
apply under `--apply` (re-plan after each), else propose with code. *You get:* the
extracted helper + rewritten fn, applied only when execution proves behavior preserved.

**`flag file::fn MUTANT_ID [--note]`** → `profile` to find the survivor's `diff_summary`
→ `equivalents.add_flag` → `.detective/equivalents.json`. Future `classify_survivors`
moves it to `manual_equivalent`. *You get:* the survivor no longer counts as a gap.

**`purge`** → `memory_guard.purge_caches` removes `.wesker/*.json` (regeneratable). Never
touches generated tests or `.detective/` (user data). **`certify`** → one-shot
diagnose+synthesize (superseded by converge). **MCP** → `diagnose`/`certify` only.

---

## 6. The synthesis stack (how inputs are made AND rendered — the subtle part)

Witness search and golden capture both need *inputs* that (a) run the function and
(b) render into a runnable test. The literal-only default breaks on non-literals;
`SourceExpr` bridges it.

```
annotation ──_type_of──▶ type name
   scalar (int/str/float/bool)      → _grid_for / _SCALAR_SAMPLE           (literal)
   container (list[int], dict[...]) → _synth_from_ann (recurse elements)   (literal)
   dataclass                        → _synth_value (build from fields)     (object)
   ast.* (FunctionDef, expr, …)     → synth_ast_input (parse a snippet)    → SourceExpr
   unannotated                      → int fallback (KNOWN LIMIT §10)
```

- **Call sites** (`equivalence._outcome`, `characterization._try_capture`) `unwrap(arg)`
  so a `SourceExpr` runs as its live `value`.
- **Render sites** (`_golden_property`, `_witness_property`, `characterization`) use
  `repr(arg)`; `SourceExpr.__repr__` returns its `expr`, and `_setup_with_imports`
  threads the needed `import` (e.g. `import ast`) into the test header.
- **Assertion rendering** (`characterization.golden_assert_line`): value-equality
  (`result == <literal>`) when the output contains a **set/frozenset** (repr order is
  hash-seed-dependent → flaky), else exact repr-equality.

---

## 7. The memory / hygiene layer (Wesker `memory_guard.py`)

- **Budget**: `resolve_budget` = `WESKER_MEM_BUDGET_MB` (user) → else `system_RAM/8`
  clamped [256 MB, 2 GB]. `over_budget()` compares peak RSS (`resource.getrusage`).
- **Guard**: `run_function_profiling`'s mutant loop checks `over_budget` every 16
  mutants → stops + `reclaim()` (gc) → `budget_exhausted=True`. Proven to fire.
- **Telemetry**: `telemetry()` one-liner footer after every CLI command.
- **Purge**: `purge_caches` deletes `.wesker/function_cache.json` + reports.
- **Single valid copy** (`Wesker/ci.py` `single_valid_copy`): the function cache purges
  other-hash entries on write → exactly one result per function, never stale.

---

## 8. Persisted state (what's on disk, who owns it)

| Path | Owner | Regeneratable? | Purged? |
|---|---|---|---|
| `tests/test_<fn>_synth.py` | Detective (product output) | yes | never |
| `conftest.py` (root) | Detective (pytest wiring) | yes | never |
| `.detective/equivalents.json` | **user** (manual flags) | **no** | **never** |
| `.wesker/function_cache.json` | Wesker (result cache) | yes | `purge` |
| `.wesker/*_report.json` | Wesker (reports) | yes | `purge` |

Detective holds **no** cross-run RAM state (MCP server is stateless; CLI frees on exit).

---

## 9. DEBUG MAP (symptom → touch this → why)

| Symptom | Touch | Why |
|---|---|---|
| Generated test is **flaky** across runs (set output) | `characterization.golden_assert_line` | set repr order is hash-seed-dependent; must use value-equality |
| converge **says "converged"/complete but a killable/line gap remains** (error-path fn) | `converge.converge` witness pass (`w.original.startswith("<raised")`) + `_witness_property` | raising witnesses are only *suggested*, never auto-written as `pytest.raises` (§10 #1) |
| `audit` reports **too many "existing tests" / wrong bloat** | `audit.audit_suite` `test_names` | counts all tests in `line_coverage`, incl. ones covering 0 target lines (§10 #3) |
| converge **crashes** mid-run | `converge.property_holds` except clause | must catch `_pytest.outcomes.Failed` (BaseException), re-raise KeyboardInterrupt/SystemExit |
| `verify_under_pytest` reports **0 passed** for a passing suite | `certify.verify_under_pytest` | `-o addopts=` needed so the target's `-q` doesn't become `-qq` (suppresses summary) |
| Survivor reads **"uncertain — inputs don't exercise"** (str/object/method fn) | `engine._input_grids` / `_synth_from_ann` / `representative_site` | input synthesis can't build a fitting value (domain-value or unannotated — §10 #4) |
| AST-input fn (`func_node: ast.X`) can't be tested | `equivalence.synth_ast_input` + `_type_of` (Attribute) | needs SourceExpr synthesis |
| decompose extraction is **wrong** (UnboundLocalError, wrong result) | `decompose_apply.block_interface` + `structural_bindings` | loop/with/except targets must be excluded from params; `preserves_behavior` should catch it |
| decompose **won't apply** a safe block | `decompose_apply.preserves_behavior` inputs | validation needs an input that *exercises* the fn (weak inputs → not-exercised → propose) |
| `flag` doesn't take effect | `engine.classify_survivors` flag lookup (keyed by `diff_summary`) | a code change alters the diff → key no longer matches (by design); or a witness overrode it (proof beats opinion) |
| memory grows on a huge run | `Wesker.engine.run_function_profiling` (mutant list) + `memory_guard` | mutant list is materialized; guard bounds accumulation, not the initial list |
| new field on `ProfilingResult` not surfaced | `Wesker.engine.ProfilingResult.to_dict` (emit when non-empty) + the Detective consumer | contract is additive/backward-compatible |

---

## 10. Known boundaries & open gaps (honest)

**Fix-F acceptance findings (product-level):**
1. **[HIGH] Raising-witness never auto-written.** A function with an error path
   (`raise`) is left mutant- *and* line-incomplete: converge finds the killing input
   but only *suggests* it (no `pytest.raises` auto-write). `converge.converge` witness
   pass + `_witness_property` (needs a raises-form emitter). Most real functions hit this.
2. **[MED] `converged=True` reads as "done"** when a killable/line gap remains. The
   headline should lead with COMPLETE/INCOMPLETE (`functionally_complete ∧ line_complete`),
   which is already computed. `cli._format_converge`.
3. **[MED] audit `test_count`/`bloat` include tests that cover 0 target lines**
   (whole-repo discovery). `audit.audit_suite` `test_names` should require ≥1 obligation.
4. **[LOW] `diagnose` output is theory-jargon** — needs a plain-language action line.
5. **[LOW] `certify` vs `converge` overlap**; thin `--help`.

**Synthesis boundaries (not-dogfoggable / domain-value):** unannotated params default to
`int`; domain-value inputs (lookup keys, source strings) aren't synthesizable → false
"uncertain"/"equivalent"; self-only methods (no receiver synthesis); integration fns
(subprocess/file-IO) and engine-core (settrace/the profiler itself) can't self-profile.
These are the recorded limits behind most "uncertain" verdicts — the fix is richer
input synthesis or a **manual `flag`**, never hand-written tests.

---

## 11. Working on this codebase (the discipline)

**Dogfood before AND after every function change** — profile with the literal
`detective` (this *is* the product's intended workflow, not a checkbox):

```
PYTHONPATH=/Users/rohanvinaik/tools/Detective \
  /Users/rohanvinaik/tools/Wesker/.venv/bin/python -m Detective.cli \
  converge "PATH::FUNC" --project-root ROOT   # generates its tests AND tests the pipeline
```

- **Never hand-write** a test for a Detective/Wesker function — run `converge`; if it
  can't, fix the *input generation* (§6), don't hand-write.
- **Bidirectional**: if dogfooding shows the bug is in Wesker, the fix goes in Wesker.
- **Auto-apply principle**: deterministically-correct → auto; only-mostly-correct →
  propose (show code); **deletion is never auto** (propose + confirm).
- Engine-core / integration fns that can't self-profile are guarded by the unit suite;
  that is the *only* exemption from the converge rule.
```
Suites: Detective `python -m pytest` (263 green), Wesker likewise (83 green), run with
the Wesker venv python + `PYTHONPATH` at the repo root.
```
