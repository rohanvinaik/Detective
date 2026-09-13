# Detective — Architecture & Operational Map

The reference for **what Detective does, how it does it, and where to look when something breaks.**
Cold start: read §0 (the idea) and §0.1 (the vocabulary), then §1 (the mental model); skim §3 (data
structures) and §5 (every command); keep §9 (debug map) open — a symptom there points at the function
to touch and the rule it must keep.

Detective is a **clean-room** package (no lintgate in the runtime import graph). Runtime deps: `Wesker`,
`pytest` and `ruff`, all from PyPI; CI and local dev resolve Wesker from its git main via
`[tool.uv.sources]`, which never enters the published wheel. Console script: `detective`. The MCP
surface is parked (§5a). This file states rules; the incidents behind them are in
[docs/HISTORY.md](docs/HISTORY.md), linked as *why: Hn*.

---

## 0. Thesis (the one idea)

A function's **mutation profile is a complete map of the behavioral distinctions it makes.** Killed
mutant = a distinction the tests pin. Survivor = a degree of freedom no test distinguishes. Read
backwards, that map is a *specification*: it says exactly which behaviors are unpinned, so you can pin
them with warranted tests — or recognize that nothing *can* pin them (equivalent mutants). Every
command consumes that map.

**Value-specification vs run-specification (the load-bearing distinction).** A kill is only a *value*
specification if a test **assertion** distinguishes the mutant — it pins *what the function returns*. A
kill by **crash** or **timeout** proves only that the code *runs*, not what it computes, so it is an
**unspecified value-DOF** (a value-survivor). Detective's "specified/complete" always means
*value*-specified:

- `value_killed` = assertion kills only.
- `value_survived` = true survivors **+** crash/timeout kills.
- **Mutation-completeness** (`functionally_complete`) = every *killable* mutant is killed by an
  assertion; the only survivors left have no distinguishing input (equivalents).

**Two orthogonal axes** — do not conflate them:
- **Mutation completeness** — the *proof* metric. It is what makes a decomposition provably
  behavior-preserving and a suite a real specification.
- **Line completeness** — the standard "every executable line is covered." Weaker and *orthogonal*: a
  line whose mutants are all killed is specified whether or not coverage counts it, and a covered line
  whose mutants survive proves nothing. Line-completeness is reported, never used as a proof gate.

---

## 0.1 Vocabulary

The words the output, the code and the docs use, each as it is meant here.

**Measuring a function**

| Term | Meaning |
|---|---|
| **pinned** | Every mutant is killed by a value assertion except those no input can distinguish. The mechanical form of "does what it was made to do, and nothing it does can change unnoticed". |
| **survivor · DOF** | A mutant no test kills: a degree of freedom (DOF) the tests do not constrain. |
| **value kill · crash-only** | A kill by an assertion on the returned value pins behaviour. A kill by crash or timeout pins only that the code ran differently; such a survivor is reported `crash-only-equiv` and never counts toward specification (§0). |
| **real gap · killable · witness** | A survivor with a distinguishing input — a *witness*, where original and mutant return different values. It gets a test. |
| **candidate-equivalent — UNPROVEN** | The search found no distinguishing input. Equivalence is undecidable, so this is never promoted to "equivalent"; it is left labelled, or settled by a person with `flag`. |
| **unclassified** | The search could not evaluate the survivor. A measurement limit, not a code gap. |
| **fence** | The opposite judgment to an equivalence flag: `flag --fence` records that a survival is a bug, an authored MUST-NOT the suite does not enforce yet. It fails `audit --check` and blocks ✓ COMPLETE. |
| **operator universe · policy** | The versioned set of mutation operators every verdict is measured against. Its identifier is written into receipts; `✓ COMPLETE (operator universe)` means exactly that and nothing wider. |
| **two-sign · μ⁻** | Opt-in (`--two-sign`): also perturb the function's *return value* (→None, →constant, →identity). A surviving perturbation is a *negative* DOF — an output invariant no test pins. |
| **Monty Hall filter** | Wesker's elimination of mutants that cannot bear on the function as written (an addition has no boolean to flip), before any test runs. |
| **cut · INVALID MEASUREMENT** | A run a budget or deadline stopped early. Never gateable; exit `3`, re-run. |

**Which tests count**

| Term | Meaning |
|---|---|
| **testing regime** | How the repository imports its code and runs its tests: the name that imports the target, the `sys.path` the suite gets, the conftests pytest loads. Every command resolves it first and refuses on a conflict. (Not to be confused with `ScopeMap.regime`, diagnose's A tractable / B entangled reading.) |
| **live session** | One in-process pytest session wrapping a command, so fixture-taking tests run as they do under pytest (§2a). |
| **basis · `FunctionBasis`** | The per-function record of which test items are admissible evidence about the target, and what that evidence supports: `complete`, `gap` or `unresolved`. |
| **warrant** | Why one test item is or is not evidence: `proof` (fresh, admissible, covers — may discharge an obligation), `routing` (covers but replayed or inadmissible — orders, never proves), `barred` (its baseline outcome bars it), `disjoint` (a fresh observed non-reach — the only observation that may exclude), `pending` (not yet observed). |
| **fresh · replayed** | Observed in this session, or served from a cache. A replayed observation may order work but never prove. |
| **intent (ℋ) · characterization (𝒢)** | Hand-written tests, and generated tests a person has since edited, are *intent* evidence. Unedited generated tests are *characterization*: they pin what the code does, which may already be wrong. Origin is a recorded fact (a content digest in the generated file's first line), never a path glob. |
| **census** | A tally by named code. `audit`'s origin census counts intent / characterized / unattributed tests; `diagnose`'s routing census counts candidate / unknown / impossible / observed tests, plus deferred and not-consulted ones. |
| **shaped · deferred** | A shape-hazardous test (subprocess, thread, signal, custom collector) is deferred from the speculative widen by default and counted; `--include-shaped` brings it back. |
| **floor · ceiling · sandwich** | The minimum evidence σ is a range: the *floor* is the intent minimum (a happy-path suite), the *ceiling* the exact specification (a suite separating every non-equivalent mutant). The *sandwich thesis*: the unit is ONE function's operators and ONE function's tests (§11). The *synthesis floor*: a target nothing reaches is pinned by synthesizing tests, never by tracing the whole suite. |

**What Detective records and hands back**

| Term | Meaning |
|---|---|
| **certificate** | The recorded terminal converge verdict for one (target, definition), in `<write-dir>/certificates.json`. The style layer reads it to know whether a region is pinned. |
| **receipt** | A snapshot of a function taken *before* an arbitrary rewrite — source, proof suite, policy, operator universe — which `verify-rewrite` checks the rewrite against. |
| **pure decision · "pure — pinned"** | A function over literal-expressible inputs (`str`, `bool`, `int`, `list`, `dict`) returning a named string code, extracted from an impure shell so `converge` can pin it. Docstrings tag it `(pure — pinned)`. |
| **`--input` · Zones 1/2/3** | Zone 1: provable, emitted automatically. Zone 2: partial — the CLI asks for one exact literal `--input`. Zone 3: cannot be exercised — a typed hand-off. `--input` parses a literal allowlist, which is what makes "no arbitrary code execution" checkable (§6). |
| **proof · advisory** | The proof layer (`converge`, `audit`, `decompose`, `verify-rewrite`) certifies. The advisory layer (`plan`, `parsimony`, `survey`, `extract`, `censor`, `doctor`) reads and proposes, and never gates. |
| **AMBIGUOUS** | A style finding one lens raises alone, or on which the two signs disagree: the driver's call, recorded with `flag --style`. |
| **censor · κ** | A censor is a forbidden input/output region carved from observed near-misses across a population of call sites, never from one function; κ (marginal coverage over the call graph) ranks them. Unverified until promoted. |

**Reference codes in the prose.** Comments and docstrings cite design documents by code. `#NN` is a
GitHub issue. The rest, and where each is defined:

| Code | Defined in |
|---|---|
| `§N` in the style-layer modules (`plan`, `controller`, `judgments`, `templates`, `budget`, `certificates`) · `Wave N` · `EXP-DS-NNN` | `docs/theory/deterministic_sicp/DETERMINISTIC_SICP.md` |
| `§N` in the basis and scoping modules (`engine`, `scope`, `reachability`, `regime`, `audit`) · `D1`–`D5`, `X1`–`X6`, `G1`–`G7` | `docs/TEST_BASIS.md` |
| `§N` in the negative-specification modules (`censor`, `kappa`, `promotion_ledger`) · `Q1`–`Q8` (§18) · `Fork 1`/`Fork 2` (§11, Def. 11.10) | `docs/theory/NEGATIVE_SPECIFICATION.md` |
| `§N` in `doctor` / `ledger` | `docs/DOCTOR.md` / `docs/INVOCATION_LEDGER.md` |
| `S`-codes | `docs/CORRECTNESS_REPAIRS_2026-09-08.md` |
| `W`-codes | `docs/OPEN_ITEMS.md` |
| `Finding A`–`F` | `docs/dogfood/revalidation_2026-09-06.md` |

`§` numbers are per document, and a module that cites several documents does not always name which. A
module that cites one document names it in its docstring, in a `Design:` or `References:` line. Two collisions to know:
`OPEN_ITEMS.md` reuses `D`-numbers for different items than `TEST_BASIS.md`, and both `TEST_BASIS.md`
and `NEGATIVE_SPECIFICATION.md` use `B`-numbers.

---

## 0.5 The advisory read — SICP parsimony (Detective-native)

Everything in §0 is the **provable** half of clean code: behaviour pinned, seams proven. The
**stylistic / epistemic** half — cohesion, the right abstraction, the behaviourally-overloaded
God-function — is **not provable**, so Detective carries it as an **advisory read**, never a gate. It is
Detective-native by design: a stylistic call needs judgement, and Detective is the layer a human or
large model drives. `diagnose` surfaces a per-function parsimony consensus (complexity, purity,
cohesion, interface width, structural seam, and Wesker's behavioural overload — fused by lens
*agreement*, never a weighted sum) that points *where* to look; `plan` is the style layer's entry verb
over a tree; the proof gate still decides *whether* a change is safe. The signal never writes source.
Full design: `docs/PARSIMONY_ADVISORY.md`; the plan and its controller:
`docs/theory/deterministic_sicp/DETERMINISTIC_SICP.md` §14.

This is the trilogy's division of labour, which is also its epistemology: **Wesker** drives (mutation);
**Detective** is the operational layer a strong intelligence drives to change code, and the home of
these advisory signals; **Uroboros** is the mindless whole-repo purifier that churns on the *provable*
axis only — SICP decisions are out of its scope, because a dumb relentless process cannot adjudicate
them.

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

Detective **owns one function at a time.** Every proof command takes `file.py::function`, asks Wesker
to profile it, then reshapes or acts on the result. Detective holds no cross-run RAM state; persisted
state is on disk (§8). Profiling is **content-cached** and **serial** (§7).

The sixteen commands sit on three layers:

| Layer | Commands | What it may do |
|---|---|---|
| **Setup** | `regime`, `doctor`, `purge` | read the environment and the operator; `regime --migrate` fixes Detective's own setup; `purge` deletes caches |
| **Behavior (proof)** | `diagnose`, `converge`, `audit`, `decompose`, `flag`, `flag-line`, `receipt`, `verify-rewrite` | measure one function against its mutants; write tests, certificates and ledgers |
| **Style (advisory)** | `plan`, `parsimony`, `survey`, `extract`, `censor` | read static structure and propose; never gate, never write source |

Style comes AFTER behavior, strictly: a region's style reading consults its behavior certificate first.

---

## 2. The two input surfaces

### 2a. INPUT FROM WESKER (the engine seam)

Everything Detective imports from Wesker, grouped by Wesker module (the importing Detective modules in
brackets):

| Wesker module | Names | Used for |
|---|---|---|
| `Wesker.engine` | `run_function_profiling` [engine] | THE profile call — mutate + run covering tests + baseline line coverage |
| | `generate_mutants` [engine, plan] | the deterministic mutant set |
| | `estimate_universe_size`, `greedy_coverage_guarantee` [converge] | DOF count + the a-priori greedy coverage floor |
| | `ProfilingResult`, `CategoryResult`, `MutationCategory` [engine, scope, verdict_cache] | the result type (below) |
| | `DEFAULT_TRACE_BUDGET_S`, `DEFAULT_TRACE_SESSION_BUDGET_S` [cli, engine] | the trace caps — **imported, never restated** |
| | `session_budgets`, `session_regime_digest` [engine] | what a verdict inside a session was actually measured under (the cache key reads these) |
| | `_SESSION_BASELINE` [engine] | the session's baseline holder, forked per function for target-first seeding |
| | `ExecutionLockUnavailable` [cli] | the execution lock could not be taken — raised with a named reason instead of blocking |
| `Wesker.ci` | `run_with_live_suite` [cli] | **THE session seam.** `cli._run_live` wraps a command in it once; everything underneath transparently upgrades. Returns `None` — and ONLY `None` — when no session could start |
| | `refresh_live_suite` [certify, converge] | tell the session a test file changed on disk |
| | `discover_test_callables`, `load_test_callables` [audit, engine, suite_edit] | find the real tests exercising a function. **Inside a live session it returns the session's callables and ignores every other argument** |
| | `partition_live_callables` [engine], `relevant_test_files` [converge], `callable_origin` [engine, suite_edit] | routing: split a session's tests into candidate / tagged-unknown / provably-impossible for one function; the test files plausibly exercising a source file; the file a test came from |
| | `walk_functions` [audit, censor, cli, converge, engine, kappa, suite_edit] | enumerate functions in a module |
| | `_PROJECT_ROOT` [engine] | the project root ContextVar, set around profiling |
| `Wesker.filter` | `filter_categories` [converge, engine, plan] | which mutation categories apply (drops STATE for pure functions) |
| `Wesker.isolation` | `callable_shape_hazards`, `scan_source_hazards`, `fast_mode_standing` [engine] | a test's shape hazards (subprocess, threads, …) and whether in-process fast mode may be trusted for it |
| `Wesker.line_coverage` | `executable_lines`, `trace_line_coverage` [engine] | the target's statement lines and per-test coverage |
| `Wesker.trace_cache` | `observed_function_reach` [engine], `test_fingerprint` [verdict_cache] | observed reach from the persistent trace cache; test identity for the cache key |
| `Wesker.trace_evidence` | `TraceEvidence` [verdict_cache] | the per-test trace rows a result carries |
| `Wesker.pytest_discovery` | `last_collection_errors` [engine] | tests that failed to collect during this profiling |
| `Wesker.interrupt` | `Abandoned`, `bounded_join` [equivalence] | time-bounded calls that leave no runaway thread behind |
| `Wesker.memory_guard` | `telemetry`, `purge_caches` [cli] | the CLI's telemetry footer + the `.wesker/` half of `purge` (§8) |
| `Wesker` | `__version__`, `mutation_policy` [verdict_cache] | the engine's version and mutation policy, read by the verdict cache |

Two of these names are private (`_SESSION_BASELINE`, `_PROJECT_ROOT`): Detective and Wesker are
developed together, and a change to either needs Detective's suite run against the local Wesker.

**Rules at the seam.**

* **Every behavior command runs inside one live session** (`cli._run_live` → `run_with_live_suite`),
  and a failure to start one degrades **loudly**. Without it, fixture-taking tests are skipped and
  already-pinned behaviour reads as unpinned. *Why: [H1](docs/HISTORY.md#h1).*
* **`paths`** — pytest's own collection argument — is narrowed by `reachability.reachable_test_paths` to
  the files that could execute the target's lines; `None` = collect everything. Reachability is an
  **over-approximation** (it may include too much, never exclude a real reacher), and it is bounded by the
  project's declared `testpaths` (`within_declared_testpaths`). It is computed before the seam changes
  directory, so relative paths resolve against the project root, never the cwd. *Why:
  [H2](docs/HISTORY.md#h2).*
* **The trace budgets go to `run_with_live_suite`**, where the suite is traced, not only to `profile()`;
  and `profile` keys its cache on `Wesker.engine.session_budgets()`, what actually produced the answer.
  *Why: [H3](docs/HISTORY.md#h3).*
* **`certify._write` calls `refresh_live_suite` after every write and every delete.** It is the single
  choke point through which generated tests reach disk, and the refresh both replaces that file's
  callables **and** invalidates the `SessionBaseline`. *Why: [H5](docs/HISTORY.md#h5).*
* **Target-first profiling.** In a live session `engine.profile` forks a per-function baseline, seeds it
  with the tests that statically name the target, and widens lazily on a survivor or an uncovered line.
  Only the caller-reaching unknowns are widened (the applicability bound); the rest are counted as
  `not_consulted`, and a target nothing reaches is pinned by synthesis. Any failure degrades to the
  ordinary full run.

**What Detective gets back — `ProfilingResult`** (`Wesker.engine`), the single most important object:

| Field | Meaning |
|---|---|
| `function_key` | `rel/path.py::qualname` — the identity everywhere |
| `total_mutants / total_killed / total_survived` | raw headline counts |
| `per_category` | list of `CategoryResult`: per-category total / killed / survived / killed by assertion / by crash / timed out |
| `kill_matrix` | mutant → the tests that kill it (feeds `minimize`) |
| `survivor_records` / `killed_records` | per-mutant records: `mutant_id`, `category`, `diff_summary`, `killed_by`, `elapsed_ms` |
| `line_coverage` / `admissible_line_coverage` | test → target lines covered, observed / restricted to baseline-green tests |
| `executable_lines` | the target's statement lines (the denominator) |
| `failing_tests` | tests that fail on the UNMUTATED function — repo-wide; `audit_suite` scopes it to this function's suite before reporting (*why: [H6](docs/HISTORY.md#h6)*) |
| `tests_discovered` | how many test callables were found (`0` = nothing to kill with, `-1` = unknown) |
| `budget_exhausted` · `trace_truncated` · `is_gateable` | whether a budget stopped the run, whether the traced baseline was cut, and the engine's own verdict on whether the result may support a certificate |
| `trace_evidence` · `proof_basis` | the per-test trace rows and the proof-basis rows a certificate draws on |
| `universe_size` · `total_equivalent` · `dof_total` / `dof_covered` / `dof_pinned` | the operator universe and DOF accounting |
| **derived properties** (never stored — cannot drift) | `value_killed`, `value_survived`, `value_survivor_records`, `admissible_union`, `observed_union` |

Also carried: `categories_tested`, `survival_rate`, `coverage_depth`, `execution_mode`, `fast_mode`,
`memory_standing`, `determinism`, `collection_conflicts`, `elapsed_ms`, `test_routing`,
`operator_census`. Detective attaches a few attributes of its own after profiling (`measurement_basis`,
`profile_extra_test_dirs`, `observed_return_types`, `collection_errors`); they are deliberately not
fields, because the verdict cache stores fields and these describe one measurement.

`line_coverage` / `executable_lines` / `failing_tests` come from Wesker's **baseline pass** (`sys.settrace`
in `Wesker/line_coverage.py`), run once against the original before the untraced mutation loop.

### 2b. INPUT FROM THE USER

| Surface | Where | What |
|---|---|---|
| target | `file.py::function` positional | the one function to act on |
| `--project-root`, `--json` | most commands | project root; machine-readable output with the same verdict |
| `--input "(…)"` | converge, decompose | a **Zone-2 residual** — a Python-literal positional-argument tuple the tool asked for. Remembered in `.detective/inputs.json` |
| `--clock EPOCH` · `--env NAME=value` | converge | freeze `time.time()`, or declare an environment variable, while pinning; the emitted test re-applies and restores it |
| `--receiver-factory MODULE:CALLABLE` | converge | a zero-argument factory for a method target whose class cannot be built with no arguments |
| `--trace-budget` · `--trace-session-budget` · `--deadline` | proof commands | per-test and whole-pass trace caps; one aggregate wall for the command |
| `--two-sign` · `--include-shaped` | proof commands | the negative-specification operator; include deferred shape-hazardous tests |
| `.detective/equivalents.json` · `line_flags.json` · `judgments.json` | project root | **human judgments** — equivalence and fence flags, unreachable lines, style verdicts (§8) |
| `WESKER_MEM_BUDGET_MB` | env var | memory ceiling for profiling |
| existing test files | the project's suite | what `audit` assesses and `converge` augments |
| covering tests' runtime inputs | the project's suite | when synthesis provably cannot build a parameter, `capture_call_inputs` reuses the REAL arguments those tests pass — never fabricated |

---

## 3. Core data structures (what flows between stages)

All in `Detective/`; frozen dataclasses unless noted.

**Measurement**
- **`ScopeMap`** (`scope.py`) — *diagnose output.* `regime` (A tractable / B entangled), `specification`
  (variants / pinned / unspecified / inert — *value*-pinned), `kill_quality` (`by_value_assertion` vs
  `by_crash` + warning), `behavioral_dof`, `tests_discovered`, `test_routing`, `decompose_seams`
  (structural extraction count — the STRUCTURAL half of "is this >1 thing"; regime B is the behavioral
  half), `trace_truncated`. Produced by `scope_from_profiling` + `diagnose`.
- **`FunctionBasis`** (`engine.py`) — the per-function reporting projection of a completed measurement:
  obligations, the witnesses with their warrants (`basis_membership`), and `action` (complete | gap |
  unresolved). `converge` and `audit` rebuild it with the real classified count. It is the honest
  projection, not the loop's governor — that is `validity.normalize_validity`.
- **`MeasurementValidity`** (`validity.py`) — the one authoritative answer to "may this measurement
  support a certificate?", with the named reasons it may not (`measurement_cut_reasons`).
- **`TestRegime`** (`regime.py`) — how the repository runs its tests: layout, suite `sys.path`,
  `testpaths`, conftests and collisions, marker declaration, config file.

**Survivors and synthesis**
- **`Witness`** (`equivalence.py`) — a concrete input where original and mutant differ by a **value**. A
  value-witness is PROOF of value-killability = a concrete killing assertion. `find_witness` skips
  "mutant newly raises" differences (a crash does not pin value).
- **`MutantVerdict` / `SurvivorReport`** (`equivalence.py`) — one survivor classified, and the
  per-function roll-up: killable, equivalent (candidate), unclassified, manual equivalent, authored
  fence, plus why the search could not run (`load_failed`, `inputs_expressible`). Disjoint buckets.
- **`SourceExpr`** (`equivalence.py`) — a synthesized **non-literal** input: runs as its live `value`,
  renders as its constructor `expr`, threads its `imports`.
- **`ExecutableProperty`** (`synthesis/oracle_light.py`) — one test-to-be (`setup_code`,
  `assertion_code`, `needs_oracle`, `golden_case`). The unit the writer renders.
- **`GoldenCapture`** (`synthesis/characterization.py`) — a captured output with its provenance and the
  effects observed while capturing (filesystem writes, environment reads, clock dependence).

**Command results**
- **`ConvergeResult`** (`converge.py`) — `functionally_complete`, `line_complete`, `at_ceiling`,
  `survivor_report`, `missing_lines`, `redundant_tests`, `minimal_test_count`, `universe_size`,
  `coverage_guarantee` (the proven greedy floor), the `--input` residual template, `written_path`,
  `wiring`. `.complete` = functionally ∧ line complete.
- **`SuiteAudit`** (`audit.py`) — `mutant_complete`, `line_complete`, `redundant_tests`, `failing_tests`,
  `killable_gaps`, `missing_lines`, `minimal_test_count`, the candidate-equivalent / unclassified /
  manual-equivalent counts, the origin census (`intent_tests`, `characterized_tests`,
  `unattributed_tests`), and `function_basis`. EVERY emitted test list is scoped to THIS function's
  suite — a test that kills one of its mutants or covers one of its lines.
- **`Extraction` / `Decomposition` / `DecompositionApply`** (`decompose_apply.py`) — a generated helper and
  the outcome (`applied`, `proposed`, `unsafe_blocks`, and **`proof`**, the converge run, so the CLI can
  surface the residual `--input` when it cannot prove).
- **`RewriteReceipt` / `RewriteVerification`** (`rewrite.py`) — the snapshot `receipt` takes and the
  verdict `verify-rewrite` returns (PRESERVED / CHANGED / …, with differences and abstentions).

**Human judgments and the style layer**
- **`EquivalenceFlag`** (`equivalents.py`) — an equivalence or fence judgment keyed by `func_key` +
  `sha256(diff)[:16]`; the diff embeds the code, so it is content-validated.
- **`LineFlag`** (`line_flags.py`) — an uncovered line marked unreachable, keyed by statement identity so a
  moved line is recognised and an orphaned one reported.
- **`StyleJudgment`** (`judgments.py`) — the driver's LEAVE / PROCEED answer to an AMBIGUOUS region, tied
  to the function digest and reopened when either moves.
- **`RegionRead` / `Plan`** (`controller.py`), **`PlanAssembly`** (`plan.py`) — one region's style reading
  and the priced, gated plan over a tree.
- **`SurveyFinding`** (`survey.py), `ExtractionProposal` (`extract.py`), `Censor` /
  `CensorLedgerEntry` (`censor.py`, `promotion_ledger.py`), `PairedBudgetRead` (`budget.py`)** — the
  advisory commands' results.

---

## 4. Module map (responsibility · key functions)

**Entry and dispatch**

| Module | Responsibility | Key functions |
|---|---|---|
| `cli.py` | argument parsing, formatting and dispatch; wraps behavior commands in the live session; records every invocation. Also holds the pure decisions behind its own advice (which next action, which repair route) | `main`, `_build_parser`, `_run_live`, `_record_invocation`, `diagnose_next_action`, `converge_next_action`, `repair_measurement_route`, `measurement_block_route` |
| `_contain.py` | command-level output containment and the aggregate-deadline arithmetic | `contained_stdout`, `remaining_budget_ms`, `budget_is_exhausted` |
| `__init__.py`, `__main__.py`, `synthesis/__init__.py` | package metadata, `python -m Detective`, the synthesis package | — |

**The engine seam and measurement**

| Module | Responsibility | Key functions |
|---|---|---|
| `engine.py` | the Wesker adapter: profiling, target-first seeding, caching, witness classification, the function basis | `profile`, `diagnose`, `classify_survivors`, `function_basis`, `basis_membership`, `trace_tier` |
| `verdict_cache.py` | content-hashed verdict cache for `profile()` (§7) + purges Detective's regeneratable state (§8) | `cache_key`, `get`, `put`, `proof_cache_admits`, `purge`, `engine_fingerprint` |
| `validity.py` | one authoritative answer to "may this measurement support a certificate?" | `normalize_validity`, `measurement_cut_reasons`, `cut_reason_sentence` |
| `regime.py` | testing-regime resolution — the ONE place that answers "how does this repo run its tests?"; the migration to a declarative setup | `resolve_regime`, `plan_migration`, `apply_migration` |
| `reachability.py` | static test-impact scoping: which test files could execute a target's lines. Conservative in ONE direction — any doubt includes the file | `reachable_test_paths`, `within_declared_testpaths`, `module_name` |
| `scope.py` | reshape a `ProfilingResult` into the behavioral map | `scope_from_profiling` |
| `binding.py` | how a target is CALLED, and how a method's receiver is constructed | `classify_target`, `resolve_receiver_plan` |
| `capabilities.py` | declared environment capabilities (`--clock`, `--env`) applied during capture and rendered into tests | `parse_env`, `apply_env`, `apply_clock`, `capability_identity` |
| `purity.py` | does a function have observable side effects — and can it affect the world outside the process | `is_pure`, `analyze_function`, `world_effects`, `environment_reads` |
| `capture.py` | runtime harvest of REAL argument tuples and return types from the covering tests | `capture_call_inputs`, `capture_return_types` |
| `call_sites.py` | recover inputs and types from how a function is called across the repo | `discover_call_site_inputs`, `infer_param_types` |
| `array_inputs.py` | bounded NumPy witnesses — candidates, never reachability proofs | `array_source`, `array_grid` |

**The behavior layer (proof)**

| Module | Responsibility | Key functions |
|---|---|---|
| `converge.py` | **the closed loop**: diagnose → synthesize sound properties → write → re-profile to the ceiling | `converge`, `property_holds`, `passes_to_complete`, `reproducibility_verdict`, `line_proof_basis` |
| `audit.py` | read-only assessment of an EXISTING suite, and the CI gate | `audit_suite`, `audit_gate_exit`, `audit_check_failed` |
| `decompose.py` | propose extraction candidates — **structure-gated**, not survivor-gated | `decompose`, `find_extraction_candidates`, `apply_disposition` |
| `decompose_apply.py` | extract-function: converge (proof) → trial-apply → prove → apply | `extract_candidate`, `extract_block`, `decompose_outcome`, `decompose_exit` |
| `certify.py` | the pytest wiring and the one write path for generated tests; generated-file ownership and edit detection | `wire_pytest`, `verify_under_pytest`, `ensure_marker_registered`, `generated_owner`, `witness_origin_of`, `certify` |
| `certificates.py` | the converge verdict ledger — one recorded terminal verdict per (target, definition) | `record_certificate`, `load_certificate`, `certificate_refusal` |
| `rewrite.py` | old-vs-new preservation gate for ARBITRARY rewrites | `make_receipt`, `verify_rewrite`, `rewrite_verdict`, `verify_rewrite_exit` |
| `equivalence.py` | classify a survivor killable / equivalent-candidate BY EXECUTION; `--input` parsing; `SourceExpr` | `find_witness`, `classify_survivor`, `parse_input_expression`, `synth_ast_input` |
| `equivalents.py` | persist and read equivalence and fence flags | `add_flag`, `load_flags`, `flag_key` |
| `line_flags.py` | manual line-unreachability flags — the human oracle for the line ledger | `add_line_flag`, `flag_statuses`, `clean_orphaned_flags` |
| `minimize.py` | minimal complete suites — two-axis set cover (kills ∪ lines) | `minimal_cover_2axis`, `redundant_2axis`, `missing_lines` |
| `suite_edit.py` | apply confirmed test deletions | `apply_removals` |
| `pins.py` | generated properties remembered across runs, keyed by function digest | `function_digest`, `load`, `save` |
| `samples.py` | remember the Zone-2 inputs a person supplied | `load`, `remember`, `merge` |
| `adequacy.py` | adversarial adequacy benchmark for the decomposition transform | `run_adequacy`, `adequacy_bucket` |
| `consumption.py` | is a pinned pure decision actually CONSUMED by production code | `consumption_disposition`, `declared_decisions` |
| `synthesis/characterization.py` | characterization-backed golden captures, with effect blocking | `capture_golden`, `golden_assert_line`, `block_fs_writes` |
| `synthesis/oracle_light.py` | oracle-light executable properties from survivors | `generate_executable_property`, `property_identity` |
| `synthesis/typed_synthesis.py` | resolve a type annotation into a constructible test value | `synthesize_value` |
| `synthesis/writer.py` | assemble properties into an idiomatic pytest module | `render_module`, `synthesize_test_module`, `individual_test_names` |

**The style layer (advisory)**

| Module | Responsibility | Key functions |
|---|---|---|
| `plan.py` | the plan — the controller's assembly over a tree; `plan`'s resolution and exit | `resolve_plan`, `assemble_plan`, `region_lenses`, `plan_exit` |
| `controller.py` | orientation, interference, and the gated priced plan | `controller_verdict`, `admission_reason`, `plan_moves` |
| `parsimony.py` | the SICP parsimony lenses — Detective-native, never a proof | `complexity_lens`, `cohesion_lens`, `seam_lens`, `overload_lens` |
| `parsimony_map.py` | static repo / module / class parsimony map — the one repo-scale surface | `score_path`, `parsimony_plan`, `read_function` |
| `templates.py` | the computation-shape template library — taste as recognition | `template_matches` |
| `norms.py` | norms mining for the bank geometry | `norm_disposition`, `weighted_median` |
| `budget.py` | deterministic cost reads (opcode counts) for `verify-rewrite --budget` | `paired_budget_read`, `growth_class`, `budget_verdict` |
| `judgments.py` | the style judgment ledger | `record_style_judgment`, `judgment_standing` |
| `survey.py` | static scan for pure decisions trapped behind an impure boundary | `survey_source`, `survey_disposition` |
| `extract.py` | propose the pure decision to pull out of an impure shell | `extract_proposal`, `extract_readiness` |
| `cognitive_complexity.py` | cognitive complexity (SonarSource model) | `compute_cognitive_complexity` |
| `emission.py` | warranted cross-language emission — the `rewrite-in-<lang>` gate | `emission_disposition`, `run_c_gate` |

**The negative layer, the operator, utilities**

| Module | Responsibility | Key functions |
|---|---|---|
| `censor.py` | population-derived censors above per-function μ⁻ | `harvest_corpus_censors`, `censor_admissible`, `score_censor` |
| `kappa.py` | κ (marginal coverage) over the code call graph | `build_call_graph`, `marginal_coverage` |
| `promotion_ledger.py` | the corpus self-teaching ledger for censors | `corpus_fixpoint`, `load_ledger`, `save_ledger` |
| `doctor.py` | what is blocking correct USE of the tool — setup, process, taste | `setup_disposition`, `process_disposition`, `taste_disposition`, `mix_product` |
| `ledger.py` | the invocation ledger — what the operator did, so the process axis is decidable | `append`, `read_recent`, `spiral_disposition`, `prune` |
| `atomic_store.py` | one atomic writer for every durable JSON store | `atomic_write_text` |

The parked MCP server is not in the package; see §5a.

---

## 5. The CLI — every command

Shape: `detective <command> [target] [flags]`. `cli.main` parses, dispatches from two tables —
`_PATHLESS_COMMANDS` (taking an optional target or a path, dispatched before the `file::function` split)
and `_TARGETED_COMMANDS` — prints a formatter, and appends the invocation to `.detective/ledger.jsonl`
from a `finally` (`_record_invocation`, which never raises). Live progress and the phase narrative
stream to **stderr**, so stdout stays clean for the result / `--json`, and the terse `FINAL` banner stays
the last stdout line.

**Live or static.** `purge`, `regime`, `doctor`, `plan`, `parsimony`, `survey`, `extract` and `censor` are
static (`_STATIC_COMMANDS`): no pytest session, no mutant. Every other command runs inside `_run_live`
(§2a), and `flag --style` is static too. `_run_live`, `flag --style` and `plan`'s `file::function` form
resolve the testing regime first and REFUSE on a conflict (a shadowed target, colliding conftests),
printing the fix.

**Serial, and there is no flag for parallelism.** *Why: [H7](docs/HISTORY.md#h7).*

**Exit codes** — a verdict is also the exit status:

| Code | Meaning |
|---|---|
| `0` | clean / success |
| `1` | a real gap or typed REFUSAL — `audit --check` spec gap; `verify-rewrite` not PRESERVED; a collision / accounting refusal; `flag`: no such surviving mutant |
| `2` | a conflict / precondition — regime conflict, wrong interpreter, a bad `--env`, or `audit --check-strict` measurement-incomplete; `plan`: no such function / nothing to read; `doctor`: a live setup fault |
| `3` | INVALID MEASUREMENT, re-run — `converge` / `decompose` cut or stale target; a weak receipt baseline |

### Setup

#### `regime [file.py::function] [--migrate]` — static, read-only unless `--migrate`
**Purpose:** show the testing regime every other command resolves: the layout, the `sys.path` the suite
gets, the conftests pytest loads, whether the `detective` marker is declared, and — with a target — the
dotted name the rest of the repo imports it by and whether that name means THIS file.
**`--migrate`** applies the clean setup: declares the `detective` marker (and `pythonpath`, if a conftest
Detective wrote was supplying it) in `pyproject.toml`, then removes that conftest. It only ever replaces
Detective's own artifacts with their declarative equivalent; without the flag the plan is printed and
nothing changes. *Why the marker lives in pyproject: [H12](docs/HISTORY.md#h12).*

#### `doctor [target] [--green|--red|--yellow]` — static, advisory
**Purpose:** diagnose the OPERATOR and the ENVIRONMENT, never the code — "why can I not proceed / what am
I doing wrong". Three axes, mixed by default: **green** setup (the project or environment is malformed),
**red** process (read from the invocation ledger: repeats, spirals, wrong order), **yellow** taste
(nothing is broken, but something caps how much of the tool you reach). It interrogates the premise a
true message rests on — `No module named 'funcy'` can be true while funcy is installed under another
interpreter on the same machine.
**Writes** nothing; runs no suite and never imports the target. **Exit** `2` when a setup fault is live,
else `0`. Design: `docs/DOCTOR.md`.

#### `purge [--prune [--yes]]` — static
Deletes the regeneratable caches of **both** packages: Detective's `.detective/verdict_cache.json` and
`.detective/reports/` (`verdict_cache.purge`) and Wesker's `.wesker/` reports and trace cache
(`memory_guard.purge_caches`). Prints every path it removed. **Never** deletes generated tests,
certificates, or anything a person authored (§8). `--prune` also deletes the invocation history
(`.detective/ledger.jsonl`) and asks first; `--yes` skips the question for scripts. *Why both halves:
[H9](docs/HISTORY.md#h9).*

### Behavior (proof)

Common flags: `--project-root` (default `.`), `--json`; on `diagnose` / `converge` / `decompose` /
`audit` also `--verbose`, `--trace-budget SECONDS`, `--trace-session-budget SECONDS` and `--two-sign`;
on `diagnose` / `converge` also `--include-shaped`.

#### `diagnose file::fn` — live, read-only
**Purpose:** show a function's behavioral scope and point at the right next command.
**Operation:** `engine.diagnose` → `profile` → `scope_from_profiling`, plus a structural read
(`_count_decompose_seams` = `find_extraction_candidates`). **You see:** regime (A/B); variants /
value-pinned / unspecified / inert; kill quality (value-assertion vs crash, with a ⚠ if crash-dominated);
the routing census; the parsimony consensus; the next command; and the **decompose guidance from two
independent signals**:
- regime B **and** a structural seam → **`★ LOOK HERE FIRST`** (both methods agree it is really more than
  one thing);
- regime B, no seam → "entangled but structurally one piece — `converge`, not decompose";
- a seam but cohesive behavior → "clean seam exists — `decompose` is safe if you want it".

#### `converge file::fn` — live, the flagship, writes tests
Flags: `--write-dir DIR` (default `tests/detective`), `--max-iterations N` (default 3), `--fast`, `--full`,
`--input TUPLE` (repeatable), `--clock EPOCH`, `--env NAME=value` (repeatable; `NAME-` declares it absent),
`--receiver-factory MODULE:CALLABLE`, `--isolated`, `--deadline SECONDS` (default 300).
**Purpose:** generate a **mutation-complete, line-complete, minimal** pytest suite.
**Operation:**
1. **Loop** (≤ N passes): `profile` → value-survivors → synthesize `ExecutableProperty`s (oracle-light per
   survivor + golden captures for pure functions); keep only those that **hold on the unmutated
   function** (`property_holds`); render the union across passes and write. Stop at 0 value-survivors or
   no progress.
2. **Witness pass** (`classify_survivors`): for each value-witness, write the killing test — a golden for a
   value-returning original, a `pytest.raises` for a raising one. When synthesis cannot build an input,
   first **harvest a real one** from the covering tests (`capture_call_inputs`).
3. **Final authoritative profile** → completeness, line / minimal / redundant via `minimize`, pytest
   wiring (`wire_pytest`), and the reproducibility check.
4. **Minimize before shipping:** drop any generated test redundant for BOTH kills and lines, re-render,
   re-profile — the written suite IS minimal by construction. A non-generation, never a deletion of
   yours.

**Modes:** default **comprehensive**; `--fast` greedy-samples a `(1−1/e)`-optimal subset per category per
pass. `--isolated` evaluates mutants in isolated workers, for use after a reproducibility refusal.
**Writes:** the suite under `--write-dir` (each file's first line records a content digest, so a later
human edit is detectable); the certificate in `<write-dir>/certificates.json`; pins in
`.detective/pins.json`; supplied inputs in `.detective/inputs.json`; the full report in
`.detective/reports/`. **You see:** a minimal terse block — a plain-language verdict, the one next action,
a report pointer, ending in a greppable `FINAL …` banner; `--full` prints the report too. For any
residual, the exact `--input "(<slots>)"` to supply — for a BOUNDARY residual, the distinguishing input
named (`_boundary_hint`, e.g. `supply an input where units == 100`). **Exit** `3` on a cut or stale run.

#### `audit file::fn` — live, read-only unless `--remove`
Flags: `--remove`, `--check`, `--check-strict`, `--plan`.
**Purpose:** assess an **existing** suite on both axes without changing it.
**Operation:** one `profile` of the current suite → `redundant_2axis` + `missing_lines` +
`minimal_cover_2axis` + `classify_survivors`. **You see:** the test count; kills; mutant-complete /
line-complete (tiered, including "complete modulo N candidate-equivalent — flag to confirm"); the minimal
cover and bloat; pointless tests to prune; killable gaps with the input that kills them; failing tests;
the origin census. `--remove` **confirms** deletion of the proposed pointless tests (`apply_removals`),
then re-audits; deletion is never automatic.
**`--check`** is the CI gate: exit `1` on a real specification gap (a killable mutant not killed, a
reachable uncovered line, a failing test). Unclassified, candidate-equivalent and crash-only survivors do
not fail it. **`--check-strict`** also exits `2` when the measurement was incomplete and that is the only
problem. **`--plan`** estimates the mutation cost without mutating.

#### `decompose file::fn [--apply]` — live, proves then writes
Flags: `--apply`, `--input TUPLE` (repeatable), `--deadline SECONDS` (default 300).
**Purpose:** extract a compound block into a helper, **provably behavior-preserving**. **Operation**
(`apply_decomposition`): (1) **converge** the target to a mutation-complete suite — the proof; (2)
**cluster** the body into extraction candidates (`find_extraction_candidates`: single-exit, small
interface, cognitive complexity ≥3) — **structure-gated**, independent of test coverage; (3) trial-apply
each, re-run the suite, keep only what stays green. The proof gate is **mutation-completeness**, and
Detective need not be the suite's author: when the hand-written suite already kills every killable
mutant, the proof is those files (`_covering_test_files`, resolved from the `kill_matrix`, so only tests
that killed a mutant OF THIS TARGET can stand as proof). **You see:** `✓ APPLIED (specified behavior
preserved, auto)` with the helper and the thinned caller — only when the suite proved it; otherwise the
exact `decompose … --apply --input "(<slots>)"` that would close the loop. A cut proof is never applied.
Without `--apply`, proposals are shown and nothing is written.

#### `flag file::fn [MUTANT_ID]` — live (static with `--style`)
Flags: `--note`, `--fence`, `--style` with `--leave` / `--proceed`.
**Default:** assert a surviving mutant is truly equivalent → `.detective/equivalents.json`;
`classify_survivors` then treats it as `manual_equivalent`. A later real witness overrides it (proof beats
opinion), and a code change to that line invalidates the flag by design (content-keyed).
**`--fence`:** the opposite — this survival is a bug, an authored MUST-NOT. Reported as an unenforced gap
that fails `audit --check` and blocks ✓ COMPLETE.
**`--style`:** record a STYLE judgment for a whole region — the driver's `--leave` / `--proceed` answer to
an AMBIGUOUS `plan` row — in `.detective/judgments.json`. A separate ledger the behavior layer never
reads; reopened when the function or its reading changes. Takes no mutant id.
**Exit** `1` when there is no such surviving mutant.

#### `flag-line file::fn [LINE]` — live
Flags: `--note`, `--list`, `--remove`, `--clean`.
Mark an uncovered line as unreachable → `.detective/line_flags.json` (the line ledger only; it never
touches the mutant verdict). `--list` shows the function's flags with current / orphaned status;
`--remove` deletes one exact record; `--clean` deletes only confirmed-orphaned ones.

#### `receipt file::fn [-o receipt.json]` — live
Snapshot a function's specification BEFORE an arbitrary rewrite: its source (so the old implementation can
run), its mutation-complete proof suite, its policy and operator universe. Converges the target first, so
the recorded proof basis is real. Writes the receipt JSON to `-o` or stdout (`plan` suggests
`.detective/receipts/<region>.json`). **Exit** `3` on a weak baseline.

#### `verify-rewrite receipt.json file::fn` — live
Flags: `--budget`, `--learn`.
Check a rewritten function against the receipt: replay the original proof suite on the new source,
profile the new source for behaviours the old proof never covered, and evaluate OLD and NEW at each
distinguishing input — reporting equal / different / abstained rather than silently learning the new
behaviour. **PRESERVED** only when all three hold; otherwise exit `1`. **`--budget`** also reads the
rewrite's payoff in opcodes along a size ladder (refund · parity · regression · unmeasurable); the
preservation verdict owns validity, and a PRESERVED rewrite whose budget could not be measured exits `3`.
**`--learn`** sources censors from a rejected rewrite into `.detective/censors.json`.

### Style (advisory)

#### `plan TARGET` — static
Flags: `--budget` (DOF-proxy units, default 500), `--top` (default 5), `--write-dir` (read for each region's
behavior status, never written), `--full`, `--json`.
**Purpose:** the style layer's entry verb — what a codebase's PINNED regions could safely become: priced,
gated, every exclusion named. Over a directory or file it reads every region; over `file.py::function`
it reads one (and resolves the testing regime for that form). Admissible moves are funded
strongest-agreement-first, cheapest-first, until the budget is spent. Every count is a named code's
tally, never a score. **Writes** only its report under `.detective/reports/`. **Exit** `0` for a completed
read whatever it found, `2` for a precondition, never `1`.

#### `parsimony PATH` — static
Flags: `--top` (default 10), `--plan`, `--json`.
Roll the AST-only parsimony lenses (complexity, cohesion, interface width, structural seam) over a file or
directory: a clean-percent per module and class, and the worst offenders. `--plan` emits an ordered work
queue (flagged functions grouped by module, worst first) instead of the map. Writes nothing.

#### `survey PATH` — static
Find functions that hide a pinnable PURE decision behind an impure boundary — an inexpressible parameter
(ndarray / object / Any), a body entangled with I/O, or a pure function trapped in a module whose imports
are a heavy stack — and name the extraction that would let `converge` reach it. Proposes; writes nothing.

#### `extract file::fn` — static
For a function `survey` flags, name the concrete extraction: a pure function over the primitive values the
decision reads (the expressible parameters, plus scalars projected out of the inexpressible one).
Propose-only: no `--apply`; apply it by hand, then `converge` the extracted function in isolation.

#### `censor PATH` — static
Flags: `--top` (default 20), `--promote`, `--list`, `--json`.
Harvest population-derived censors across a corpus and rank them by κ. Read-only by default; `--promote`
runs the corpus fixpoint and persists promoted censors to `.detective/censors.json`; `--list` shows that
ledger. On clean data the result is conservatively empty by construction.

---

## 5a. The MCP surface — parked

Parked 2026-09-13. The server, its tests, the steps to restore it, and its design record — why it
rendered prompts for a model caller rather than the CLI's text — live in
[`parked/mcp/README.md`](parked/mcp/README.md).

---

## 6. The synthesis stack (how inputs are made AND rendered)

Witness search and golden capture both need inputs that (a) run the function and (b) render into a
runnable test. Literals cover scalars and containers; `SourceExpr` bridges non-literals.

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

- **Harvest, don't fabricate.** When every synthesized candidate raises (a domain object no grid builds),
  `capture_call_inputs` installs a `sys.setprofile` hook keyed to the target's code object, runs the
  covering tests, and records the actual bound arguments. It fires lazily, only when the soundness gate
  would otherwise abstain.
- **Never invent inputs for a function that escapes the process.** The search calls the target, and a str
  grid contains `"a"`. For a function that visibly reaches outside the process (`purity.world_effects` —
  file writes and modules such as `shutil`, `subprocess`, `socket`, `requests`, read from that function's
  own body, not its helpers), only evidence reaches it: a real call site, a captured input, or your `--input`.
- **Declared capabilities.** `--clock` and `--env` are applied while capturing and rendered into the
  emitted test, which re-applies and restores them; an undeclared environment read stays refused.
- **Receivers.** A method target is called through `binding.py`: a class that builds with no arguments is
  constructed directly; otherwise `--receiver-factory` names a factory that builds a fresh receiver for
  every capture and witness call, or the target is a named `needs-receiver` refusal.
- **Minimal by construction.** After the final profile, converge drops any test it generated that is
  redundant for both kills and lines and re-profiles.
- **Call sites** `unwrap(arg)` so a `SourceExpr` runs as its live value; **render sites** use `repr(arg)`,
  so `SourceExpr.__repr__` emits round-trippable constructor code, with imports threaded into the header.
- **Assertion rendering** uses value-equality for set-containing outputs (repr order is hash-seed
  dependent) and exact repr-equality otherwise.
- **Zone contract:** Zone 1 provable → emitted automatically; **Zone 2** partial → the CLI emits the exact
  `--input` residual, a person supplies *that value*, the AST builds the test; Zone 3 cannot be exercised →
  a typed hand-off. The person never authors the generated test.

---

## 7. Caching and performance

**Coverage-scoped test selection** (`run_function_profiling`, `scope_tests=True`): each mutant runs only
against the tests that execute its mutated line. Verdict-preserving — a test that never runs the line
cannot observe the mutation — and failing-baseline tests are folded into every scoped set so it stays
identical to a full run.

**Content-hashed verdict cache** (`verdict_cache.py`, `.detective/verdict_cache.json`). `profile()` serves
an unchanged function's result from disk. The key (`cache_key`) is: function key · engine fingerprint
(Detective's and Wesker's versions) · a hash of the function's AST dump · the tests' fingerprint ·
`max_per_category` · pass index · the trace budgets that produced the answer · `:defer_shaped` when shaped
tests were deferred · `:two_sign` for the two-sign contract · the testing-regime digest. The AST hash is
position-independent: editing *other* functions never invalidates this one.
- **Anything that can change the answer belongs in the key.** Budgets, deferral and the two-sign universe
  each change what is measured. *Why: [H4](docs/HISTORY.md#h4).* Scoping is deliberately not in the key:
  scoped and full runs are proven verdict-identical.
- **Only a result that may support a certificate is stored** (`proof_cache_admits`, on the one normalized
  validity), and the cache is bypassed entirely for isolated runs and when a live session's regime cannot
  be observed.
- **A cache hit is replayed, never fresh:** its trace rows are stamped `provenance="replayed"` on read, so
  they may order work but never prove.
- **The key has two readers** — `cache_key` builds it and `put` re-parses it for single-valid-copy — so the
  field count lives in `_PARAM_FIELDS` and `put` calls `params_suffix()`. *Why:
  [H8](docs/HISTORY.md#h8).*

**The session baseline is paid once per session and built lazily** (`Wesker.engine.LazySessionBaseline`),
and persisted across runs by Wesker's trace cache (`.wesker/trace_cache.json`). Per-function cost is then
small, which is why there is no parallelism. *Why: [H7](docs/HISTORY.md#h7).*

---

## 8. Persisted state (what is on disk, who owns it)

| Path | Written by | Kind | Removed by `purge`? |
|---|---|---|---|
| `tests/detective/test_*_synth.py` (`--write-dir`) | `converge`, through `certify._write` | the product; first line records a content digest | **never** |
| `tests/detective/certificates.json` | `converge` | the product: one verdict per (target, definition), versioned with the suites | **never** |
| `detective` marker in `pyproject.toml` | `regime --migrate` (`certify.ensure_marker_registered`) | configuration | never |
| `.detective/reports/*.txt` | `converge`, `plan` and other reporting commands | regeneratable | **yes** |
| `.detective/verdict_cache.json` | `engine.profile` | regeneratable | **yes** |
| `.detective/pins.json` | `converge` | properties remembered per function digest, re-verified before reuse | no |
| `.detective/equivalents.json` | `flag`, `flag --fence` | **human judgment** | **never** |
| `.detective/inputs.json` | `converge --input` (`samples.merge`) | **human input** | **never** |
| `.detective/line_flags.json` | `flag-line` | **human judgment** | **never** |
| `.detective/judgments.json` | `flag --style` | **human judgment** | **never** |
| `.detective/ledger.jsonl` | every invocation (`_record_invocation`) | evidence — a re-run cannot reproduce an earlier entry | only `purge --prune`, which asks first |
| `.detective/censors.json` | `censor --promote`, `verify-rewrite --learn` | the promoted censor ledger | no |
| `.detective/receipts/<region>.json` | `receipt -o`, at the path `plan` suggests | a deliberate pre-rewrite snapshot | never |
| `~/.detective/telemetry.json` | `cli` | per-machine timing, not project state | no |
| `.wesker/mutation_report.json`, `mcdc_report.json`, `trace_cache.json` | Wesker | regeneratable | **yes** (`Wesker.memory_guard.purge_caches`) |

Commands that change your source: `decompose --apply` (the extracted helper), `audit --remove` (deletes the
confirmed pointless tests), `regime --migrate` (`pyproject.toml`, and a conftest Detective wrote).

**`purge` spans both packages**, because neither can purge the other's state. *Why:
[H9](docs/HISTORY.md#h9).*

**The human/regeneratable split is the invariant, not a nicety.** The four human files are the things in
the pipeline Detective **cannot derive** — a semantic prior synthesis provably could not build, and a
person's judgment on an undecidable question. Purging them asks the person to redo the only irreducible
work. Everything purge removes is rebuilt from current code on the next run, so purging can only ever
cost time.

**Cross-run RAM state: none.** The two ContextVars (`_LIVE_SUITE`, `_SESSION_BASELINE`) live in Wesker,
exist only for the duration of one `run_with_live_suite` call, and are reset in its `finally`.

---

## 9. DEBUG MAP (symptom → touch this → why)

| Symptom | Touch | Why |
|---|---|---|
| Kills all show as **crash**, "0 pinned" on a real function | the crash-vs-value split — check the synthesized input actually RETURNS | `value_killed` counts assertion kills only; a crash-killed mutant is a value-survivor |
| A mutant a value-assertion *should* kill stays a survivor | `Wesker.engine.evaluate_mutant` (value precedence: an assertion kill beats a crash kill; keep scanning past crash kills) | a crash-killer that runs first would stamp `killed_by=crash` and hide the value kill |
| `find_witness` suggests a crash input as "killable" | `equivalence.find_witness` (skips "mutant newly raises") | a crash does not pin value |
| `decompose` says "no separable blocks" on a big function | `decompose.find_extraction_candidates` gates (single-exit, ≤4 in / ≤2 out, CC ≥3) | flat, wide functions have no small-interface block — correct, not a bug |
| `decompose` won't prove a clearly decomposable function | `decompose_apply.apply_decomposition` proof gate = `functionally_complete`, not `line_complete` | mutation-completeness is the proof |
| `decompose` refuses a function whose EXISTING suite already specifies it | `decompose_apply._covering_test_files` | the proof is mutation-completeness, not authorship |
| `decompose` says "not mutation-complete" but converge reports COMPLETE | `cli._format_decompose` — a complete suite that rejects the rewrite reads `REJECTED … PROVES this extraction changes behavior` | no suite / incomplete suite / disproved are distinct verdicts |
| `decompose` cannot prove and gives no way forward | `_format_decompose` residual block (reads `result.proof`) | surface the `--input` the internal converge computed |
| `diagnose` says "decompose" but decompose finds nothing | `_format_scope` convergent signal (regime B **and** `decompose_seams`) | only point at decompose when a structural seam exists |
| An extracted helper carries the PARENT's docstring | `decompose.find_extraction_candidates` skips a leading docstring | a docstring belongs to the function, never to an extracted block |
| converge writes a test its own audit then calls redundant | converge step 4 (`redundant_2axis` + `writer.individual_test_names`) | ship the minimal cover, not the full set + removal proposals |
| The cache serves a stale result | `verdict_cache.cache_key` | anything that can change the answer belongs in the key (§7) |
| **The command prints NOTHING and exits 0** | `Wesker.engine._run_test_with_timeout` — the abandon + unwind join must happen INSIDE the redirect; `ci._body` re-enters the streams | an abandoned test's frame can reinstall a dead stdout buffer. *Why: [H11](docs/HISTORY.md#h11)* |
| `converge` reports a tiny kill count and asks for inputs it does not need | `certify._write` → `Wesker.ci.refresh_live_suite` | the session's collection is a snapshot; the refresh must also invalidate the `SessionBaseline`. *Why: [H5](docs/HISTORY.md#h5)* |
| `--trace-budget` / `--trace-session-budget` change nothing | `cli._run_live` must pass them to `run_with_live_suite` | on the live path the suite is traced inside the seam. *Why: [H3](docs/HISTORY.md#h3)* |
| A warm cache is still slow (a full trace before an instant answer) | `Wesker.engine.LazySessionBaseline` — keep the baseline demand-driven | built eagerly it is the whole cost of a run, paid outside the region the cache protects |
| `diagnose` on a big repo traces the whole suite for one small function | `cli._reachable_paths` → `reachability.reachable_test_paths` → the session's `paths` | scoping must happen at pytest COLLECTION; `scope_tests` selection is derived from the trace and cannot save it |
| Tests from an installed dependency are traced | `reachability.within_declared_testpaths`, `is_virtualenv_root` | pytest's declared `testpaths` is the authoritative boundary; no name list enumerates every virtualenv |
| A generated test is **flaky** (set output) | `characterization.golden_assert_line` | set repr order is hash-seed dependent → value-equality |
| `verify_under_pytest` reports 0 passed for a passing suite | `certify.verify_under_pytest` | `-o addopts=` so the target's `-q` does not become `-qq` |
| A survivor reads "uncertain — inputs don't exercise" | `engine._input_grids` / `call_sites` / `capture.capture_call_inputs` | synthesis cannot build a fitting value AND no covering test exercises it (§10) |
| A BOUNDARY residual says "supply an input" but not WHICH | `cli._boundary_hint` | a `>`↔`>=` shift differs exactly when the operands are equal |
| Memory grows on a huge run | `run_function_profiling` mutant loop + `memory_guard.over_budget` | the guard bounds accumulation |
| A generated file is reported as intent evidence | `certify.content_edited` / `witness_origin_of` | its body no longer matches the digest Detective recorded: a person edited it, so it is now intent (ℋ) |

---

## 10. Known boundaries and open gaps (honest)

**Synthesis boundaries (the real limits behind most "uncertain" / "equivalent" verdicts).** Unannotated
parameters fall back to `int` (after a call-site inference attempt); **domain-value inputs** (lookup keys,
specific source strings, valid domain dicts) are not synthesizable → they surface as a Zone-2 `--input`
residual (the correct hand-back, not a defect); a method whose class cannot be built needs
`--receiver-factory`; integration functions (subprocess / file I/O) and engine-core (the profiler itself)
cannot self-profile. The fix is richer input synthesis or a supplied `--input` / `flag` — or, for a
function that genuinely cannot be pinned, an ordinary unit test (§11).

**The decompose↔spec coupling (design, not bug).** A function converge can fully specify (pure, simple
inputs) decomposes cleanly cold; one it cannot (dicts, methods) needs a supplied `--input` first — the tool
surfaces exactly that input, and the loop closes **whenever the residual is expressible as a Python
literal**.

**Where the `--input` loop does NOT close.** `--input` parses literals only — deliberately: no code
execution (§6). So it can carry a scalar, container, dict or string, but *not an instance* — a
`ProfilingResult`, a `SourceExpr`, any domain object. The residual is still printed for those; it simply
cannot be filled. The complement is `capture_call_inputs` (§6), which reuses a REAL argument from the
covering tests — so an object-parameter function is specifiable *iff some test already passes it one*. A
cold function whose parameter is a domain object is reachable by neither, and that is the honest Zone-3
abstention, not a defect. Detective's own core is largely in this class (it passes `ProfilingResult`
around), which is why its pure decisions are extracted into literal-typed functions and pinned separately.

---

## 11. Working on this codebase (the discipline)

**Run the local pair.** Detective and Wesker are developed together and resolve through `PYTHONPATH`, the
local checkouts, never the installed packages:

```
PYTHONPATH=/path/to/Detective:/path/to/Wesker \
  python -m Detective.cli converge "PATH::FUNC" --project-root ROOT
```

- **Converge first, and write the intent test too.** A generated suite is a *characterization*: it pins
  what the code does, so anything wrong today is pinned wrong. Every behaviour change therefore gets a
  hand-written test stating the intended behaviour, alongside what `converge` generates. A function that
  cannot be pinned (engine-core, integration, AST-object parameters — §10) is guarded by ordinary unit
  tests, and says so in its test module.
- **Extract the pure decision, then pin it.** A branch behind a parameter `--input` cannot express is
  unreachable by synthesis; the response is never more inputs but a literal-typed function returning a
  named string code, placed beside the impure function it serves.
- **Serena for navigation** (symbol graph, references) — not grep or name-matching; a dev-time oracle,
  never a runtime dependency.
- **Bidirectional:** if dogfooding shows the bug is in Wesker, the fix goes in Wesker — and Detective's
  suite is run against the local Wesker after any Wesker change.
- **Auto-apply principle:** deterministically correct → automatic; only mostly correct → proposed (show the
  code); **deletion is never automatic** (propose + confirm).
- **Determinism is the product** (the audience is Sussman-lineage): any cache is content-addressed, any
  run repeatable. Verify, don't assume — and verify a path RUNS before optimising it.
- **The unit is ONE function's operators and ONE function's tests.** Both are static and free: the mutant
  space is a property of THIS function's AST, and a green suite is a set of grounded facts you are GIVEN.
  Anything that aggregates across functions is not a slow path, it is a different question. There is no
  such object as "the mutant profile of a codebase" worth computing. *Why:
  [H10](docs/HISTORY.md#h10).*

Run both suites with `PYTHONPATH` covering both repositories. Push and PyPI publishing are the maintainer's.
