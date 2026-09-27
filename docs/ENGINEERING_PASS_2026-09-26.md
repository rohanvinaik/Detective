# Engineering pass — state, persistence, caching, performance (2026-09-26)

Codes in this document are `EP`-codes. The pass applied the organization/tracing/performance
toolkit (global CLAUDE.md, installed 2026-09-25) to Detective and Wesker: organize → diagnose →
measure → pin → gate. **Every number below was measured in this session; nothing is estimated
from reading.** Where a claim rests on reasoning alone it says so.

Two rules governed every measurement, and both were learned the hard way inside this pass:

1. **A profile that changes the answer is not evidence.** Every instrumented run was accepted only if
   its `FINAL` verdict matched the uninstrumented one. Four of four in-process profilers FAILED that
   test on a trivial fixture (EP-B1, EP-F1) — which is itself the most important finding here.
2. **Wall-clock on this machine is bimodal.** 8 performance + 2 efficiency cores, with other sessions
   running: the same command varied 2–3× depending on which core it landed on. A/B comparisons use
   **instructions retired** (`/usr/bin/time -l`), which is identical across repetitions to three
   significant figures and independent of core type.

The fixture for every converge measurement is the e2e suite's own (`tests/test_cli_pipeline_e2e_native.py`:
`shipping_cost`, 18 lines, 2 real tests + 12 noise tests, `regime --migrate` applied), run through the
real CLI. Its uninstrumented verdict, identical on 3.11 (`.venv`) and 3.14 (miniconda):
`✓ COMPLETE (operator universe · modulo 2 unproven-equivalent · 3 crash-only value gaps) · 91/93 killed · 7 test(s)`.

---

## 1. Headlines

* **EP-B1 — the verdict depends on machine load.** Wesker's per-mutant allowance floor (50 ms) ignores
  harness overhead. Under any ~3× slowdown (a profiler, an efficiency core, a loaded CI runner) killing
  evaluations time out before they reach the mutant, and the SAME function reads `⚠ UNGATEABLE` or
  `Incomplete` instead of `✓ COMPLETE`. 8/8 runs wrong at the default floor, 5/5 right at 5000 ms. The
  tool never printed a false ✓ — it refuses honestly — but "determinism is the product" does not hold
  under load.
* **EP-C1 — ~45% of a converge computes a value nobody reads.** Every killed mutant is a failing test to
  pytest, and `runtestprotocol` formats a full source-annotated failure report for each. Wesker reads
  only `report.failed` and the raw exception. That formatting is ~2.9 s of a ~6 s converge and **99% of
  all AST allocation churn** (945 MB of 1.415 GB allocated). It also eats the margin EP-B1 runs out of.
* **EP-A1 — `decompose` can leave an unproven rewrite in the user's source.** The trial is written to
  the user's file, the suite run, then reverted — with no `try/finally`, and in dry-run mode too. An
  exception, Ctrl-C, or the hang watchdog's hard exit mid-trial leaves the trial (possibly one the
  suite had just REJECTED) on disk, silently.
* **EP-A2/A3 — the human stores are the least protected.** 8 of 9 durable stores read an unreadable file
  as EMPTY, so the next write destroys it; the only quarantine is on the verdict cache, the one store
  that can be regenerated. `inputs.json` (human input, never purged) is also written truncate-then-fill.
* **EP-C4 — the dev interpreter is not hermetic.** Yesterday's toolkit install put auto-loading pytest
  plugins into miniconda base. The suite there reads 25 failed / 3212 passed; the locked `.venv` reads
  3228 passed / 0 failed on the same commit. A converge there also does 2.2–2.3× the wall-clock work.
* **EP-C5 — native code would buy nothing here.** Mutant compilation is 0.03 s of a converge; Detective's
  and Wesker's own AST work is under 1% of allocation. The costs are structural (unread values,
  recomputation, harness overhead), which is SICP's territory, not Rust's.

---

## 2. The findings

Severity: **H** high (correctness/data loss or verdict stability), **M** medium, **L** low.
Status: `FIXED <sha>` in this pass · `FOUNDER` a design call, recommendation given · `OPEN` bounded work.

### A. Persistence (what is on disk, and what survives an interruption)

| Code | Sev | Finding | Status |
|---|---|---|---|
| **EP-A1** | H | `decompose_apply._apply_decomposition_impl` trial-writes the user's source (`open(full, "w")`, L999), runs `_suite_green()`, reverts at L1035 — no `try/finally`, even when `write=False`. **Reproduced:** a Ctrl-C while a dry-run trial is on disk leaves the file holding the extracted helper. Remedy built: `Detective/trial_journal.py` — `SourceTrial` restores on every exit that runs Python; the trial and the restore are atomic; a write-ahead journal per file (`.detective/trials/`) lets the next command — any command, recovered in `cli.main` before it reads source — restore after a hard kill; a file edited since is never overwritten (`trial_recovery_disposition`, pinned); a second trial never clobbers an unresolved journal. | FIXED (§5) |
| **EP-A2** | H | `samples.remember` writes `.detective/inputs.json` truncate-then-fill, and on a parse failure sets `data = {}` and writes back ONLY the current function's entry — one interruption plus one `--input` erases every other function's human input. The one human store #63 missed. | FIXED `bcc433a` |
| **EP-A3** | M | Unreadable ≡ empty, in 8 of 9 stores (`equivalents`, `line_flags`, `judgments`, `pins`, `certificates`, `samples`, `promotion_ledger`; `ledger` skips lines). A hand edit with a stray comma or a merge-conflict marker is then silently overwritten by the next write. `verdict_cache.load` alone quarantines (`.corrupt`) — protection inverted relative to value. Remedy built: ONE reader discipline shared by every store (`atomic_store.read_json_store` / `write_json_store`; decisions `store_read_disposition` and `store_write_disposition`, pinned): corrupt is set aside with every copy kept, unreadable is never overwritten. | FIXED `bcc433a` |
| **EP-A3b** | M | The same loss one level down: each loader skips an entry it cannot parse, and each save rebuilt the store from what the loader returned — so an entry from a newer schema, or one malformed entry, was deleted by the next unrelated write. Remedy built: `write_json_store(parses=…)` carries every on-disk entry the store's own schema rejects. Residual: the censor ledger's lenient parser drops unknown TOP-level fields on round trip. | FIXED `bcc433a` |
| **EP-A3c** | H | A write refused under EP-A3 is announced on stderr, but the savers dropped the refusal, so the verbs whose whole product is that write carried on: `flag-line` printed "✓ recorded … DONE" and exited 0 over a refused write, and so did `flag`, `flag --style` and `censor --promote` — a sign for a state the tool had just measured as false. Found while fixing it, the read twin: a verb that reports ON a store read an unreadable one as empty, so `flag-line --remove` answered "no flag recorded at line N" and `--list` "(none)". Remedy built: the human-store savers raise `StoreRefused` (path + `store_write_disposition`'s code); the loaders take `strict=` where the store IS the product (flag-line add/list/remove/clean, censor list/promote), deciding with the same pinned `store_write_disposition` ("may it be written over" and "may its content be reported as the whole truth" fail in the same states); the verbs name the store, the code and a remedy per code, and exit 2. `verify-rewrite --learn` keeps its verdict's exit code and no longer announces learning it could not save. `converge --input` keeps its verdict too; the writer's notice names the refusal. | FIXED (§5) |
| **EP-A3d** | M | The lenient read the verdict paths keep by design ("a missing oracle is no oracle", `load_line_flags`) was SILENT for an unreadable store: a converge measured without the human's flags read as one measured with them. `read_json_store` now announces it, as it already announced a corrupt one. | FIXED (§5) |
| **EP-A4** | M | Other truncate-then-fill writes of files that matter: `suite_edit.apply_removals` (user tests, `audit --remove`), `regime.apply_migration` / `_declare_pythonpath` and `certify.ensure_marker_registered` (user `pyproject.toml`), `certify._write` (the product), `converge` restoring a prior suite (L2286), `receipt -o` (a pre-rewrite snapshot), `cli._update_per_mutant_ms` (telemetry). All eight now go through `atomic_write_text`; an interrupted `audit --remove` or config rewrite leaves the user's file byte-identical (pinned). A generated characterization of `regime.apply_migration` caught the writer leaking its pid-named staging file into the error message; errors now name the caller's file, restoring the old message exactly. | FIXED (§5) |
| **EP-A5** | L | Two atomic writers in the pair with different guarantees: Wesker `trace_cache` fsyncs before `os.replace`; Detective `atomic_store` did not. Now both sync before the rename. | FIXED (§5) |
| **EP-A6** | M | No project lock around read-modify-write of shared stores. `atomic_store`'s docstring names it as owed (#63); "never run two converges at once" is a human rule the tool does not enforce. For a cache a lost update costs time; for a human store it loses a judgment. | FOUNDER |
| **EP-A7** | L | The verdict cache never evicts entries for functions that no longer exist (single-valid-copy is per function). Harmless at measured sizes (largest: Peitho 1.4 MB). | OPEN |

### B. Interpreter and process state (what is shared while a run is in flight)

| Code | Sev | Finding | Status |
|---|---|---|---|
| **EP-B1** | H | `_MUTANT_ALLOWANCE_FLOOR_MS = 50` (`Wesker/engine.py`) with `× 50` baseline scaling is calibrated against the TEST's runtime; the evaluation also pays thread start, pytest's protocol and, per kill, ~14 ms of report formatting (EP-C1). A pre-entry timeout reads as `mutant_not_entered` → UNGATEABLE, or flips kill/survive. Evidence §3.1. Remedies, ranked by the project's own laws (DETERMINISTIC_SICP constraint 6, "efficiency = deterministic budgets, never wall-clock"; COMMUNICATING_DETERMINISM §4, cannot-determine never renders as determined): (a) **wall-clock may BOUND a measurement, never BE one** — a timeout that fired before the entry probe was reached is "could not measure", so it is retried under a bounded, escalated allowance and, only if it persists, recorded as the cut reason it already names; (b) size the floor from a harness quantum measured at session start, which reduces how often (a) fires on a slow or loaded machine — this is the concrete meaning of "adapt to the hardware"; (c) remove the harness waste that eats the margin (EP-C1). Probably explains the e2e `_skip_if_proof_cut` CI skips. **Hypothesis, not tested:** part of the documented live-session scored-count noise (MEMORY: converge determinism) may be this rather than state leakage. | FOUNDER |
| **EP-B2** | M | `capture.capture_call_inputs` / `capture_return_types` save and restore `sys.getprofile()` assuming a Python callable. Under pyinstrument the slot holds `ProfilerState`; the restore raises `TypeError` and the converge dies with a traceback. The harvest also has no per-test bound (only between tests), so one runaway test runs until the hang watchdog hard-exits the whole command. **Crash fixed:** `profile_hook_disposition` (pinned) — an unrestorable C-level hook makes the harvest DECLINE, with a one-line notice, instead of crashing; verified through the real command: the pyinstrument-profiled converge that crashed now completes with the uninstrumented verdict (✓ COMPLETE · 91/93). The per-test bound stays open. | crash FIXED (§5) · bound OPEN |
| **EP-B3** | M | Three owners of process-global interpreter hooks, each with its own install/restore: Wesker `line_coverage` (`sys.settrace`), Detective `capture` (`sys.setprofile`), Detective `equivalence._reached_lines` (`sys.settrace`). On 3.12+ cProfile, VizTracer, memray and coverage.py all leave both legacy slots EMPTY — they moved to `sys.monitoring`, whose tool IDs coexist by design and whose local events cost nothing on code other than the target. Recommendation: one instrumentation owner with a `sys.monitoring` backend (3.12+) and the legacy backend (3.10/3.11). Semantics to settle: `settrace` is per-thread, `sys.monitoring` is process-wide, so the monitoring backend must filter by thread or a leaked runaway could attribute coverage to the next test. | FOUNDER |
| **EP-B4** | M | `synthesis/writer.numeric_backend_for` reads `sys.modules` to append a version. Its synth golden captured `'numpy'`; with jaxtyping's pytest plugin importing numpy at session start it returns `'numpy 2.5.3'` — one of the 25 miniconda failures — and, measured under random order, it is ALSO order-dependent inside one interpreter: it fails whenever any earlier test in the run imported numpy. Remedy built: the pure decision `numeric_backend_name(source)` (AST only, pinned) with `numeric_backend_for` as the thin impure shell that appends the loaded version at the one call site; the generated suite that pinned process state is removed, not regenerated (regenerating would re-characterize whatever happens to be imported). Recorded lesson: the extraction was wired in the same edit, so its covering set inherited a heavy converge-driving test (6.3 s/mutant) and the first pin was CUT at the 300 s wall — converge-before-wiring, broken by me and paid for exactly as the memory predicts. | FIXED (§5) |
| **EP-B4b** | M | The product half of EP-B4: Detective's purity/environment-read detection does not treat reads of `sys.modules` (or `sys.path`, `sys.flags`, `platform`) as environment dependence, so `converge` on a function like `numeric_backend_for` emits "pure + deterministic" goldens that describe the PROCESS. Remedy candidates: count those reads in `purity.environment_reads`, and stamp or withhold such goldens the way W3 scopes float goldens. | FOUNDER |
| **EP-B5** | — | NOT a finding: the execution lock (`_LOCK_OWNER_TID`/`_LOCK_DEPTH`, three orphan channels, bounded acquires, pinned disposition) was built 2026-09-10 and is sound. The memory note calling the RLock hang "undiagnosed" predates it. | — |
| **EP-B6** | — | Hypothesis: tests run in fresh worker threads, which start with an EMPTY context on the default 3.14 build (they inherit it on free-threaded builds, `sys.flags.thread_inherit_context`). Anything a test thread reaches that reads `_LIVE_SUITE` / `_SESSION_BASELINE` sees the default. **Measured, refuted on the fixture path.** Every module-level ContextVar in the pair (8: Wesker's `_LIVE_SUITE`, `_PROJECT_ROOT`, `_SESSION_BASELINE`, `_SESSION_IDENTITY`, the three discovery vars; Detective's `_OPEN_WATCH`) replaced by a recording proxy — no hook, no timing change; the converge reproduced its documented verdict exactly (✓ COMPLETE · 91/93) — and all 2,062 reads happened on the MAIN thread; none from a worker. The one var a worker can read, `_OPEN_WATCH` (the write-block's audit hook), is SET inside the worker by construction (`equivalence._outcome` enters `block_fs_writes()` in the thread's own `_run`). Remaining edge, by reading only: a target that starts its OWN threads runs them with an empty context, so their writes are not blocked during speculative execution. Probe: `scratchpad b6_probe.py` shape, recorded in the commit. | measured · refuted |

### C. Efficiency (measured; SICP — compute a value once, where it becomes known, and never compute one nobody consumes)

| Code | Sev | Finding | Status |
|---|---|---|---|
| **EP-C1** | H | Failure-report formatting nobody reads (§3.2). Remedy built: in Wesker's measurement session only, each item gets a cheap `repr_failure` so pytest's own report construction runs unchanged but skips source extraction. Verified: identical verdicts, byte-identical generated suites and certificates, full suites of both repos. Follow-up: the isolated worker (a separate process) still formats. | FIXED Wesker `49f7e91` |
| **EP-C2** | M | `generate_mutants` runs once per profiling pass (4× per converge, 0.97 s cumulative, ~16%) though the function under test does not change between passes. Two forms, and they differ in exactly the property this pass is about. (a) A content-keyed memo for the process, keyed by (source digest, qualname, policy, categories, per-category cap): the smallest change, but it is hidden state whose correctness rests on the key naming EVERY input — one omitted input and a pass is served another universe, silently — and in a long-lived process (the parked MCP server, a library user) it needs a bound. (b) Explicit propagation, SICP's form and the toolkit's organizing rule ("each value computed once where it becomes known and handed to every consumer"): converge generates the universe once and passes it to every profiling pass as a named value whose lifetime is the call. No hidden state; but it is a Wesker API change (a precomputed universe accepted by the engine) and a uv.lock bump. Recommendation: (b). Founder question inside it: the reproducibility pass calls itself a "fresh isolated observation" — should it regenerate the universe (checking the generator's determinism too), or may it take the propagated one (checking only the measurement)? | FOUNDER |
| **EP-C3** | L | `estimate_universe_size` 211 calls per converge (0.23 s); `_patch_module_qualified` scans all of `sys.modules` for every mutant (372 scans, 0.23 s) though the set of namespaces holding the target does not change between mutants. Recommendation: do NOT cache the namespace scan. The set can change between mutants — a test that imports a new alias of the target mid-run adds a namespace — and a stale set installs the mutant in fewer places than hold the function: a false survivor, the base ripped out from underneath. The per-mutant scan is the correctness guarantee, at ~4% of a converge. `estimate_universe_size` is a pure function of the source and can ride EP-C2's propagation. | measured · no change |
| **EP-C4** | H (dev) | **Harness fixed** (a session-scoped `PYTEST_DISABLE_PLUGIN_AUTOLOAD` in `tests/conftest.py`, restored at session end; the outer session's plugins unaffected): the standing invocation, miniconda 3.14 with every ambient plugin still installed, went from 25 failed / 3212 passed in 309.7 s to **3275 passed in 128.2 s** (with EP-B4). The environment recommendation below is still the founder's. Ambient pytest plugins in the dev interpreter. Outer-process instructions for one e2e test: `.venv` 3.11 1.05 G · miniconda no-plugins 1.45 G · all ambient plugins 4.77 G (codeflash-benchmark +2.09 G, logfire +1.52 G, jaxtyping +0.44 G, memray +0.26 G); wall 6.7 / 7.6 / 17.2 s. The same plugins make 25 tests red via process-global warnings state (pytest-asyncio 1.4.0's `pytest_configure` warns; the suite's `filterwarnings = ["error"]` turns that into an INTERNALERROR in the nested session). Remedy: Detective's own nested sessions under test must not depend on undeclared plugins; the interpreter that runs Detective should not carry toolkit plugins (the toolkit's own rule: declare tools in a project's dev extra). Product-side proposal: `detective regime` could disclose undeclared ambient plugins, since they change both speed and semantics. | OPEN / FOUNDER (env) |
| **EP-C5** | — | Where native code would and would not help: measured cost is not in Python-level compute Detective owns. `compile` for 372 mutant evaluations: 0.03 s. Detective/Wesker AST work: < 1 MB allocation per call site. No Numba/Cython/Rust candidate exists until EP-C1–C3 are done and a re-measurement shows compute-bound hot loops. | — |
| **EP-C6** | M (dev) | One test is 36% of the suite: `test_structural_search_b0_intent` 110.5 s on both interpreters (so intrinsic compute, not environment). The rest: ~3,230 tests ≈ 100 s. Measured and fixed at the test level as **EP-H1** (it was the 5 s classifier timeout on non-terminating mutants, not C1's formatting). | see EP-H1 |

### D. Parallelism and hardware

| Code | Sev | Finding | Status |
|---|---|---|---|
| **EP-D1** | — | H7 removed parallelism because "the session's callables cannot cross a process SPAWN". `fork` does not pickle: a forked child inherits the warm live session by copy-on-write. Measured fork+work+exit+wait from a warm Detective/Wesker/pytest parent: 2.6 ms median (`gc.freeze()` no measurable change at that size). A fork-per-mutant worker pool would give parallelism AND per-mutant state isolation (cross-mutant leakage — and whatever of the count noise it causes — gone by construction). Preconditions: a single-threaded parent at fork (3.12+ warns otherwise, and the suite runs `-W error`), a fork-safety probe on macOS (Accelerate/Objective-C in the target's imports → serial), worker count from P-cores, free memory ÷ measured child RSS, and current load — and EP-B1's calibration first, because contention stretches evaluations. | FOUNDER |
| **EP-D2** | — | Hardware facts for sizing: 10 cores (8 P + 2 E); a converge on the fixture peaks at 47.9 MB heap (memray) / 72 MB RSS (3.11) / 127 MB RSS (3.14); the full suite peaks at 249 MB RSS. Memory is not bloated at the peak; ALLOCATION CHURN is (1.415 GB allocated for a 48 MB peak, 67% of it EP-C1). | — |

### E. Environment, CI, advice

| Code | Sev | Finding | Status |
|---|---|---|---|
| **EP-E1** | M | CI tests 3.11/3.12/3.13; the founder's standing interpreter is 3.14.6, and the converge path already runs 3.14-only machinery (`annotationlib`). Either add 3.14 to the matrix and the classifiers, or develop on a claimed version. | FOUNDER |
| **EP-E2** | M | `cli._format_session_warning` says "Pytest rejected a config/marker owned by `pytest-asyncio`. Install that plugin in this exact interpreter" when the plugin IS installed there and is the one raising. The premise (absent) is never checked — doctor's own named defect class. Remedy built: `plugin_presence(plugin, installed_here)` (pinned: `unnamed` / `absent` / `present`) with the probe `_installed_here` asking THIS interpreter (distribution, then import name; never raises). `present` says the package IS installed and the failures above are its own, and offers no install — in both the import-failure and the config-rejection branches; `absent` keeps the install command unchanged. | FIXED (§5) |

### F. The instruments themselves

| Code | Sev | Finding | Status |
|---|---|---|---|
| **EP-F1** | — | Observer effects on Detective, measured: pyinstrument → crash (EP-B2); cProfile, VizTracer, memray → `✓ COMPLETE` becomes `⚠ UNGATEABLE`/`Incomplete` (EP-B1). cProfile's `-m` runner also swallows `SystemExit`, so a `3` reads as `0`. Until EP-B1 is fixed, the faithful profiler for the full converge path is **py-spy** (external sampling, no interpreter hook; `sudo` on macOS). Instrumented runs of the pre-witness phases are usable: they match the plain run's narrative exactly through pass 1. | — |

### G. The CLI — a communication surface, audited against its own theory

Read first, and binding: `theory/mechanical_layer/MECHANICAL_LAYER.md` §7, `theory/COMMUNICATING_DETERMINISM.md`
(the injectivity criterion, the §9 invariants, the §10 list of refused "improvements"),
`theory/deterministic_sicp/DETERMINISTIC_SICP.md` §14 and its constraint block. The surface is DERIVED;
its size (`cli.py` is 8,407 lines, ~25% of the package — matching the paper's "roughly a quarter") is
the product, not overhead. So this pass does not re-shape what the surface says. It builds the checks the
theory calls decidable and missing, and it records claims for the founder to rule on.

| Code | Sev | Finding | Status |
|---|---|---|---|
| **EP-G1** | M | Invariant 3 — "every consumer distinguishes all of a decision's codes" — is decidable over the reference graph and unbuilt (COMMUNICATING_DETERMINISM §3.2, §11). §MI and #60 were both instances found by hand. **Built** as `Detective/distinction.py` (the gathering layer, AST only, and `distinction_disposition`, pinned) and the standing guard `tests/test_consumer_distinction_intent.py`, beside `consumption.py` and on its model: a registry entry takes a REASON, split BY_DESIGN / OPEN. Measured on the package: 98 of 171 declared decisions have a closed code set; they have 106 consumer sites: 36 distinguish every code, 45 forward the code on (read downstream, not followed), 25 merge two or more codes into one path, 0 compare against a code the decision cannot return. Of the 25, 17 are BY_DESIGN with the reason already written in the code (quoted) or the merged codes impossible at that call site (stated); **8 were OPEN** when it was built — see §2.G1 below; two since fixed (EP-G4), **6 OPEN**. | FIXED (§5) · 6 OPEN for the founder |
| **EP-G2** | M | The consumption guard covers functions, not FIELDS (§11): a computed field no reader reads (`capability_flags` for a wave) is invisible. Field-level consumption, with serialization-by-reflection (`asdict`, `to_json`) named as the known blind spot. **Measured** (AST, by name): 71 dataclasses, 476 fields; 39 fields no production code reads — 21 read only by tests (the `capability_flags` shape), 18 by nothing. The by-name reading overstates, for exactly the reasons §11 gives: 21 `asdict` sites emit whole objects to `--json` or persist them (the four human stores), and a frozen class's generated `==`/`hash` consumes every field (`regime.FileIdentity.dev`/`ino`, `RevisionId`'s digests are compared whole). Candidates, not findings, that no reflection or equality reading obviously covers: `converge.ConvergeResult.at_ceiling`, `certify.CertifyResult.{at_ceiling, test_source, decomposition}`, `certify.PytestWiring.{conftest_wired, collects}`, `certify.PytestVerification.basis`, `emission.CrossLangEmission.{language, environment}`, `binding.TargetBinding.receiver_params`, `binding.ExecutionBinding.import_name`, `scope.CategoryScope.{inert, by_crash_only}`, `scope.ScopeMap.unspecified_behaviors`. A guard needs the reflection- and equality-aware reading §11 lists as open; not built. | measured · founder |
| **EP-G3** | M | Invariant 7 — no `getattr(obj, name, default)` where a renamed field would be absorbed into a silent clean verdict — is unchecked. A string-literal attribute access is exactly what the reference graph cannot see; an AST query can. Measured: 251 defaulted `getattr` reads with a literal name; 157 read a name our classes declare, 41 a CLI option, 32 a dunder, 10 an `ast` field; **47 read a fault flag** (`budget_exhausted`, `load_failed`, `stale_target`, `trace_truncated`, `environment_coupled`, …) with a default meaning "no problem", 37 of them in cli.py. **Built** as `Detective/absorption.py` (`absorption_disposition`, pinned) and the guard `tests/test_absorbed_rename_intent.py`: every such name must be declared by the pair (class fields/methods/properties, any attribute STORED on any object — the three stashes on Wesker's `ProfilingResult` count — and the CLI parser's options), by `ast`, or by the data model; five names declared elsewhere carry reasons (`sys.monitoring`, a code object's `co_filename`, the 3.12+/3.13+ `ast` type-parameter fields). Its first finding was in its own module. Limit, stated: "declared by something" is not "declared by this object's type" — a name three classes declare survives a rename on one. The founder question that remains: whether the 47 fault-flag reads should become direct attribute reads (so a rename fails loudly at the read), or carry a non-clean sentinel default. | built (§5) · 47 for the founder |
| **EP-G4** | M | Invariant 8 — "one derivation, N renderers" — is unchecked: detect a renderer that re-derives what a decision already computed. The SICP lineage question (compute once, hand to every consumer) applied to the surface. No separate detector was built: the invariant-3 guard (EP-G1) surfaces a re-derivation as a collapse, which is how four instances were found. **Two fixed** where the decision's own docstring already dictated the remedy: `_format_decompose` now asks `decompose_terminal` once and dispatches all six endings on the code (three were early returns re-reading the same facts first); `_input_template` reads `unknown` from `parameter_scope`'s code rather than by truthiness. Both verified byte-identical by a before/after render of every ending (no test asserted the text of five of the six). **Two left OPEN** for the founder: `regression_recovery` (fixing it folds "is there anywhere to write the retry" into the decision's `minimized` argument, a semantic call) and `array_source_disposition` (the finiteness read must stay behind the dtype check). | 2 FIXED (§5) · 2 OPEN |
| **EP-G5** | L | `cli.py` is in `[tool.coverage.run] omit`, so its line coverage is unknown. A MEASUREMENT (never a gate): run coverage on it once and report which renderer branches no test reaches. **Measured** over the whole suite (in-process only — the e2e tests that spawn the CLI as a subprocess are not counted, so this is a floor): lines 2484/3091 (80%), branches 954/1290 (74%). Of 172 top-level functions, 81 run every statement, 88 run partly, 3 never run in-process (`_run_regime`, `_run_decompose`, `_run_receipt` — the subprocess e2e tests are their likely readers). Most unrun: `_derived_input` (41/132 statements, 20 branches — the derived `--input` a DO THIS block prints), `_run_flag_line` (37/76), `_run_audit` (35/54), `_format_converge_terse` (33/83), `_format_regime` (19/20), `_format_decompose` (17/56), `_format_parsimony_plan` (13/14), `_dead_suite_action` (11/12), `lock_refusal_route` (9/10, 8 branches). Per COMMUNICATING_DETERMINISM §11 ("nothing pins a sentence") these are sentences no test has read; which deserve an intent test is the founder's call. Reproduce: a coveragerc with `include = Detective/cli.py`, `branch = true`, and `pytest --cov --cov-config=<it>` (`--cov=Detective` sets a source, which makes coverage ignore `include` and warn — fatal under the suite's `filterwarnings = error`). | measured |
| **EP-G6** | — | Claims for the founder, recorded, not changed: decompose's STOP block says "your source was NOT touched", and ARCHITECTURE §5 says a dry run "writes nothing"; during the run the trial IS written to the user's file and then restored (EP-A1). True of the end state, not of the run. | FOUNDER |

**§2.G1 — the eight open sites** (each entry in `OPEN` carries the full reason; the question in each is the founder's):

| Site | What the code documents | What the site does |
|---|---|---|
| ~~`decompose_terminal` @ `cli._format_decompose`~~ | "one code … never re-derived" | FIXED (EP-G4): the code is read once and all six endings dispatch on it |
| ~~`parameter_scope` @ `cli._input_template`~~ | truthiness is what hides the None/() conflation | FIXED (EP-G4): `unknown` is read from the code |
| `regression_recovery` @ `converge._converge_impl` | three codes, one per recovery | asked once with `retried=False`; after the retry, ship vs restore re-reads `regressed` — the retried branch is pinned and never reached from production (invariant 8) |
| `array_source_disposition` @ `array_inputs.array_source` | `nonfinite`, `unsupported_type` | passes `True, True`; finiteness re-derived inline after the decision; the gate that runs is unpinned (invariant 8) |
| `learn_disposition` @ `cli._run_verify_rewrite` | the skips are distinct "so a reader sees WHY nothing was learned" | prints a line for `learn` only |
| `rewrite_classification_status` @ `rewrite.verify_rewrite` | three reasons classification could not run | one bool, one sentence; the remedies differ (environment vs re-run) |
| `signpost_disposition` @ `cli._signpost_rows` | `unknown_herb` is "NAMED, never admitted by fall-through" | falls through with `emit` into no signpost |
| `value_portability` @ `emission.run_c_gate` | `numeric_model_risk` "COUNTED (the modulo qualifier)" vs `inexpressible` "named and deferred" | one `skipped` count |

The first four are also EP-G4 instances (a second reading of facts a decision already computed), found by this guard's
blind spot rather than by an EP-G4 check: a re-derivation reads as a collapse here. One more observation, recorded in the
BY_DESIGN entry for `owned_obligation_disposition`: the decision's docstring says `unwitnessed` is "never invented into the
receipt", while its one consumer's docstring keeps `unwitnessed` ("never dropped for missing attribution") — two of the
founder's sentences that read as disagreeing.

Census for orientation, not as a target: 169 top-level functions — 19 pinned decisions (689 lines), 33
renderers (1,963), 18 verb handlers (1,377), the parser (668), 98 others (2,948). Size is not a defect
under this theory; a non-injective sign is.

### H. The test suite

| Code | Sev | Finding | Status |
|---|---|---|---|
| **EP-H1** | M | Suite time is concentrated, not diffuse. Locked `.venv`: 3,256 tests in ~208 s; `test_b0_kills_a_residual_the_default_pool_leaves_candidate_equivalent` alone is 110.5 s (~53%); the top seven ≈ 70%; the other ~3,250 tests ≈ 60 s. **Root cause of the 110 s, measured** (a `faulthandler` stack sampler — no trace/profile/monitoring hook, so it cannot perturb the timing-sensitive search the hooking profilers perturbed): all 55 samples show a worker thread inside `<mutant>:sum_reachable` and the main thread in `bounded_join ← _outcome ← _search_witness ← classify_survivors`. The test spends its whole life waiting out `_CLASSIFY_TIMEOUT_S = 5.0` on worklist mutants that never terminate (~22 timeouts); CPU-bound (they spin), 44 MB peak (they do not allocate — the memory hypothesis was refuted). A timeout is `blocked` — never evidence — so its SIZE trades only speed against the ceiling. One-variable A/B on the test's own two calls: the complete classification (every verdict's repr, both arms) is **byte-identical at 5.0 s and 0.25 s; 110.5 s → 6.0 s**. **Test-level fix applied** (the bound set inside that test, evidence in its comment). **Engine-level, a founder call:** every user function with a loop pays up to 5 s per (non-terminating mutant × candidate input); a per-input bound relative to the ORIGINAL's measured time on that input (hardware-adaptive), plus one full-cap probe per mutant to protect the ceiling, is the general form — measure the classification delta on real targets before adopting. EP-C1 should also cut every test that runs a real converge. | test-level FIXED (§5) · engine FOUNDER |
| **EP-H2** | M | **The decompose trial path had no working end-to-end test.** `test_decompose_apply_preserves_behaviour` SKIPS ("no seam was applied") because `shipping_cost`'s only candidate leaves a pure delegating wrapper and the value gate rejects it before any trial. EP-A1's intent test uses a fixture with a genuine seam, and FAILS rather than skips if it ever stops trialling. The e2e test's fixture needs the same treatment. Measured: even the seam fixture never APPLIES as written — the real `decompose --apply` ends `STOP. Not a rejection — this rewrite was never tested`, blocked by 5 candidate-equivalent survivors (the three exclusive boundaries and two value shifts no synthesized input reached). With project tests that pin those boundaries it reaches `✓ APPLIED … DONE: your source is rewritten`. **Added** `test_decompose_apply_on_a_genuine_seam_rewrites_and_preserves_behaviour`: the real console script, `--apply`, then the rewritten module checked against the ORIGINAL over 12 inputs crossing every branch and boundary; a FAIL, not a skip, if nothing is applied. | FIXED (§5) |
| **EP-H4** | H (library) · M (suite) | **Cross-project contamination through process-global state.** A library-level `profile()` leaves its project's modules in `sys.modules` AND its root on `sys.path`. A later profile of a DIFFERENT project with a same-named module (`m`) binds the previous project's `f` — the cached module, or, once that is evicted, the stale file through `sys.path` — and measures code it never wrote. Measured by a field-by-field differential of the victim's result: alone, its two tests cover lines `[2,3]`/`[2,4]` and kill 7 mutants; after a predecessor, the same two tests cover `[]` and kill 0, and the tests fingerprint changes (`f00d1d35…` → `f11048cb…`). Serial file order hid it; an 8-worker run exposed it and a pairwise bisection found 3 of 29 same-named predecessors that break `test_basis_admitted_witnesses_intent`. Each leak ALONE was measured insufficient (restoring only `sys.modules`, or only `sys.path`, leaves the pairs red); restoring both fixes all three. The CLI is unaffected (one process per command); the parked MCP server, library users and this suite are not. Harness fix applied: `tests/conftest.py`'s autouse snapshot/restore — pytest's own `pytester` pattern — so a temp project leaves no trace. Product fix, a founder call: a top-level profile/session restores `sys.path` and evicts the project-root modules it imported ("clean up after yourself"), or binds imports through `session_manifest` identity rather than bare names (Wesker's rule for module identity). | harness FIXED (§5) · product FOUNDER |
| **EP-H6** | M | An environment-dependent flake, found while probing order: `test_cor106_bridge_intent::test_a_genuinely_redundant_candidate_is_still_removable` fails **5/10 in plain file order** when the suite runs from a `uv run --with …` overlay interpreter (6/10 with randomization), and **0/20** from the locked `.venv` — so it is NOT order dependence, and raising the allowance floor does not change it. The overlay differs in `sys.executable`/`sys.prefix`; something in `module_safe_removals` is intermittently sensitive to it. It fails conservatively (`safe == ()`: a redundant test kept, never a needed one deleted). Mechanism not isolated. It also means one parallel-run failure (run 2 of 2) cannot be attributed to order dependence. | OPEN |
| **EP-H5** | M (dev) | Once order-independent, the suite parallelizes: 8 workers (the P-cores) run it in ~37 s against ~95 s serial, ephemerally via `uv run --no-sync --with pytest-xdist … -n 8 --dist loadfile`. Adding `pytest-xdist` to the `dev` group (inert without `-n`) and `-n auto` to CI's six-cell matrix is a founder call on CI config. | FOUNDER |
| **EP-H3** | — | The verified analysis toolkit (each installed in a throwaway env 2026-09-26): `pytest-randomly` 5.0.0 (order dependence = inter-test state), `pytest-xdist` 3.8.0 (what breaks under `-n auto` maps hidden shared on-disk state), `pytest-flakefinder` 1.1.0 / `pytest-repeat` 0.9.4, `pytest-deadfixtures` 3.1.0, `pytest-testmon` 2.2.0 (dev loop only; the gate runs everything), `pytest-monitor` 1.6.6, `pytest-duration-insights` 0.1.2, `pytest-socket` 0.8.1, `pytest-split` 0.11.0, `coverage` 7.16.1 per-test contexts, ruff `PT`. **Redundancy is decided by Detective's own `audit` (mutation-level, per function), never by coverage** — a test that adds no line may still kill a unique mutant. **None is installed where it would auto-load** (EP-C4): run each ephemerally, `uv run --no-project --with <plugin> …`. | — |

---

## 3. Evidence

### 3.1 EP-B1 — the allowance floor A/B (one variable)

Harness: set `Wesker.engine._MUTANT_ALLOWANCE_FLOOR_MS` from argv, then call the unmodified
`Detective.cli.main` (`_adaptive_allowance` reads the module global at call time). Each run on a fresh
copy of the fixture, plugin autoload off.

| instrument | floor 50 ms (current) | floor 5000 ms |
|---|---|---|
| none | ✓ COMPLETE (2/2, 3.11 and 3.14) | — |
| memray | UNGATEABLE ×3, Incomplete (1 killable) ×1 | ✓ COMPLETE ×3 |
| cProfile | UNGATEABLE ×3 | ✓ COMPLETE ×2 |
| VizTracer | UNGATEABLE ×1 | — |

The divergence is localized: instrumented and plain narratives are identical through pass 1; under an
instrument the witness pass writes 0 distinguishing kills instead of 7, 50 survivors remain instead of 5,
and the final profile records `mutant_not_entered`.

### 3.2 EP-C1 — where a converge's time goes

cProfile (3.14, `sys.monitoring`-based, so worker threads are recorded) over the CLI converge:
`pytest_runtest_makereport` 720 calls, 2.94 s cumulative; `repr_failure` 106 calls, 1.54 s (≈14.5 ms
each); pytest `getsource` 239 calls, 2.47 s; `ast.parse` 444 calls, 0.57 s of compile — against
`compile` for the 372 mutant evaluations themselves, 0.03 s. Wesker's reader
(`pytest_runner._make_item_callable.run`) consumes `r.failed` and `_ExcCapture`'s raw exception only;
`runtestprotocol(..., log=False)` means no reporter sees the report either.

memray (valid-verdict run, floor 5000): total allocated 1.415 GB, peak 47.9 MB; `ast.parse` 952.7 MB,
of which **944.6 MB** is the chain `repr_traceback → repr_traceback_entry → _getentrysource →
getsource → getstatementrange_ast → ast.parse`. Every other parse site is under 1 MB.

### 3.3 EP-C4 — the two environments, same commit (`0bcbe6c`)

| | miniconda 3.14.6 (standing invocation) | `.venv` 3.11 (locked, what CI runs) |
|---|---|---|
| suite | 25 failed, 3212 passed, 5 skipped, 1 xfailed, 309.7 s | 3228 passed, 14 skipped, 1 xfailed, 202.9 s |
| auto-loaded pytest plugins | asyncio, anyio, codeflash-benchmark, jaxtyping, logfire ×2, memray, timeout | pytest-cov only |

24 of the 25 failures are the nested-session INTERNALERROR; the 25th is EP-B4. `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`
turns a failing one green; disabling `asyncio` in the OUTER session alone does not (the nested session
autoloads independently). Note: 3.14's first suite run overlapped another session's CPU load, so its
wall time is not comparable; the instruction counts in §2 are.

---

## 4. How to measure Detective (until EP-B1 lands)

* Metric: `instructions retired` from `/usr/bin/time -l`, two repetitions, interleaved arms.
* Acceptance: the `FINAL` line matches the uninstrumented run, or the profile is discarded.
* Profiler for the whole path: `sudo py-spy record --subprocesses --idle -o out.svg -- <command>`.
* In-process profilers (cProfile, VizTracer, memray) are fine for the phases before the witness pass;
  pyinstrument cannot be used at all until EP-B2 lands.
* Never `python -m cProfile` for an exit code: it swallows `SystemExit`.

---

## 5. Fixed in this pass

| Commit | Codes | What changed | Pins · intent |
|---|---|---|---|
| `8ca0133` | — | this document | — |
| `bcc433a` | EP-A2, EP-A3, EP-A3b | one reader and one guarded writer for all seven durable stores; `inputs.json` atomic | `store_read_disposition` ✓ 8/8 · `store_write_disposition` ✓ 12/13 modulo 1 · `tests/test_store_read_discipline_intent.py` (21) |
| `6b8fa2e` | EP-A1 | `trial_journal.py`: journaled, atomic, restored-on-every-exit decompose trials; recovery in `cli.main` before any command reads source | `trial_recovery_disposition` ✓ 11/11 · `tests/test_decompose_trial_journal_intent.py` (8; the real-decompose repro FAILS on the previous code) |
| `6f81d52` | EP-H1 (test level) | the B0 intent test binds the classifier timeout it does not test; suite 206.2 s → 102.1 s | complete classification byte-identical at 5.0 s and 0.25 s (both arms) |
| `5666523` | EP-H4 | `tests/conftest.py`: a temp project's modules and `sys.path` entries do not outlive its test (pytester's snapshot/restore) | the three bisected pairs green; serial 3267 green |
| `6e7c2a4` | EP-B4 | `numeric_backend_name` (pure, pinned) split from the impure version read; the process-state golden removed | `numeric_backend_name` ✓ 29/32 modulo 7 + 9 crash-only |
| `6959005` | EP-C4 | nested sessions and spawned CLIs load only declared plugins during the suite | standing invocation 3275 passed (was 25 failed); `.venv` 3265 passed |
| `c8c3b82` | EP-A4, EP-A5 | the eight remaining writes of user-owned files go through `atomic_write_text`, which now fsyncs before the rename and reports errors against the caller's path | `tests/test_user_file_writes_atomic_intent.py` (4; the three behavioural ones FAIL on the previous code) · the unchanged `apply_migration` characterization |
| `2c40ebc` | EP-B2 | the capture harvests decline a profile hook they cannot hand back | `profile_hook_disposition` ✓ 3/3 · `tests/test_capture_foreign_profiler_intent.py` (3) · the real pyinstrument converge completes, verdict unchanged |
| `d812775` | EP-G1 | `Detective/distinction.py` + `tests/test_consumer_distinction_intent.py`: invariant 3 as a standing guard; 17 BY_DESIGN with reasons, 8 OPEN | `distinction_disposition` ✓ 25/30 modulo 5 + 2 crash-only · the guard's gathering layer tested on 11 toy packages (the §3.2 `_TERMINAL_STANDINGS` shape among them) |
| `28e171b` | EP-A3c, EP-A3d | `StoreRefused` + `require_usable` (atomic_store); strict loads where the store is the product; `cli._store_refused` (exit 2, a remedy per code); `read_json_store` announces an unreadable store | the existing pinned `store_write_disposition` decides both directions · `tests/test_store_refusal_reaches_the_verb_intent.py` (13; the 10 behavioural ones FAIL on the previous wiring) · EP-A3's own intent test now expects the raise |
| `84c304f` | EP-E2 | the session warning asks the interpreter before telling anyone to install a plugin | `plugin_presence` ✓ 3/3 · `tests/test_session_warning_plugin_presence_intent.py` (5) |
| `824b23f` | EP-G3 | `Detective/absorption.py` + `tests/test_absorbed_rename_intent.py`: invariant 7 as a standing guard, five EXTERNAL names with reasons | `absorption_disposition` ✓ 4/4 · green on 3.11 and 3.14 · the tamper checks (a field renamed away, a stale entry, a ghost entry) each turn it red |
| `814d32c` | EP-G4 | `_format_decompose` and `_input_template` dispatch on their decisions' codes; two OPEN entries deleted, compulsorily (the guard reported them `collapse_stale`) | before/after render of all six decompose endings and the input template: byte-identical |
| `bd80ab4` | EP-H2, EP-G2, EP-G5, EP-C2, EP-C3 | the `--apply` path's first end-to-end test; the field-consumption and cli.py-coverage measurements; the compute-once options for the mutant universe | the new e2e test passes through the real console script; the others are measurements, recorded |
| `ec0c019` | EP-B6 | measured and refuted: every ContextVar read on the converge path is on the main thread | recording proxies, verdict unchanged (✓ COMPLETE · 91/93) |
| `1cd47af`, `f6ec465` | pre-push gates | pylint knows `ast`'s `_attributes`; the eight new-code Sonar findings fixed (S3516, S5778, S3776 ×7) by code motion | local SonarQube GATE OK for Detective and Wesker (0 new violations; Detective new-code coverage 91.6%, 0 bugs/vulnerabilities/hotspots); SAME checks: 109 site reads, 28 flag runs byte-identical · pip-audit (all extras and groups) clean · zizmor clean |
| Wesker `3718b0a` | pre-push gates | the cheap failure repr accepts pytest's formatting options by `*_args, **_kwargs` (W0613 / S1172) | Wesker 894 passed · Detective 3335 passed against it |
| `df37730`, Wesker `1561067` | EP-E1, EP-C4 (interpreter) | 3.12 floor, 3.14 standard in both repos: requires-python, classifiers, CI matrices (Wesker's SonarCloud cell 3.11 → 3.14), `.python-version`, `[tool.uv] python-preference = "only-managed"` (with conda active, uv had resolved the pin to conda's interpreter); the Wesker Action defaults to 3.14 (founder: "default should be 3.14"); CLAUDE.md standing invocations run `.venv/bin/python`. The floor made visible: `binding`'s receiver clone dropped a PEP 695 generic's type parameters (a NameError on 3.12/3.13), dead `tomllib`/3.10 guards | Detective 3345 passed on 3.14 (ten PEP 695 tests that skipped on 3.11 now run); Wesker 894 → 906; ty clean in both |
| Wesker `a24171e` | EP-B3 (foundation), item 1 | `Wesker/monitoring.py`: the one `sys.monitoring` owner (tool id chosen from the free ones — coverage.py holds id 1) and `step_budget`: counts loop iterations (backward JUMP events) on the opening thread and raises `StepBudgetExceeded` into the looping frame past the cap — deterministic evidence and a deterministic stop (a runaway stopped at exactly cap+1 in ~1.4 ms, identically every run; ~2.8x on the monitored loops only). Not wired yet. **Open:** converging `step_budget_verdict` is refused with an orphaned execution lock whenever its intent tests are routed to it (6/6); bisection clears it only by removing the whole intent file; one hypothesis (a plain lock leaked by abandonment) falsified. Since measured and its trigger fixed: §7 | `step_cap` ✓ COMPLETE 7/8 modulo 1 · 10 intent tests |
| `071fc73` | §7 | `profile`'s pool is the consulted set (candidates, then the widen- and shape-admitted unknowns; nothing for a leaf orphan), and the two-sign return-type harvest takes the same pool — the whole collection had been runnable through `_tests_for`'s fallback, which is how a def-line annotation mutant ran Wesker's engine-in-engine test and orphaned the execution lock | `tests/test_engine_pool_is_the_consulted_set_intent.py` (2, live session; both FAIL on the previous code) · e2e fixture byte-identical (no-regression only) · Detective 3347 passed |
| Wesker `81c5cc1` | item 1 | `step_budget_verdict` pinned under the fixed pool | ✓ COMPLETE (operator universe · modulo 2 unproven-equivalent) · 10/11 · Wesker 907 passed |
| Wesker `49f7e91` | EP-C1 | the measurement session's items get a cheap `repr_failure` / `_repr_failure_py`; pytest's report construction otherwise untouched | SAME check through the real CLI: FINAL + generated suites + certificates byte-identical on two fixtures; instructions 27.85 G → 17.66 G (−37%) and 8.34 G → 7.47 G; B0 digests unchanged · Wesker `tests/test_cheap_failure_repr_intent.py` (4) · Wesker 894 passed · Detective 3267 passed in 95.3 s |


---

## 6. Founder rulings and the plan (2026-09-26, after the pass)

The founder's framing, which governs every row below: several conservative mechanisms — the per-mutant
allowance floor, "never run two converges at once", the removal of parallelism (H7), the harvest's wall,
the in-place decompose trial, Uroboros's serial crawl — were **safety valves built before tracing and
timing tools were available**, to keep unknown statefulness from spiralling. Each is to be REPLACED by a
principled, measured mechanism, not tuned. On the fleet: *"Same reason. Statefulness."*

An independent reading was taken once, from Codex (GPT-6-Astra, medium, read-only), on the native-code /
parallelism / persistence / boundary questions; the lead's own reading was written first. Where they
agree it is noted as evidence; its corrections were verified in the code before being adopted:

* **Timeouts are scored as KILLS today.** `Wesker/engine.py:5696-5709` returns `killed=True,
  killed_by="timeout"` when a mutant's allowance runs out, and `:5727` counts an uncontained timeout as a
  run-only kill. So wall-clock IS evidence now, and under load a slow survivor can read as killed — the
  wrong direction (a suite looks stronger than it is). EP-B1 as written ("pre-entry" timeouts) was too
  narrow. Remedy direction, from DETERMINISTIC_SICP law 6 (*efficiency = deterministic budgets, never
  wall-clock*): divergence is established by a DETERMINISTIC step budget (the mutant executes more than
  k× the lines the original executes on the same test — the same count on every machine and load), and
  wall-clock only bounds liveness: a wall bound that fires is `undetermined`, never killed, never survived.
* **The mutant universe is not a function of the source alone.** `generate_mutants` (`engine.py:4347`)
  also takes `pass_index`, `observed_return_types`, `seed`, `category_order`, `greedy` and the per-category
  cap; observed types change as synthesis progresses. EP-C2's "the same universe four times" must be
  verified before anything is reused, and a cache key must carry every generation input plus the
  generator's version, the Python AST/compiler version and the serialization schema — and store mutant
  DESCRIPTORS, never `wrapper_factory` callables.
* **EP-C5's headline was too strong.** One fixture's allocation share does not establish CPU share across
  targets. The rule stands (re-measure before porting), the headline softens to "no native candidate on
  the measured fixture".
* **EP-D1 overclaimed isolation.** fork separates memory, not files, inherited sockets or external services.

| # | Item | Ruling (founder, quoted) | Plan |
|---|---|---|---|
| 1, 9 | EP-B1 allowance | "an ad-hoc implementation … a fail-safe for engineering debt"; "set this timeout to beyond the level any sane mutant should require" | Deterministic step budgets decide divergence; wall bounds become a generous liveness filter sized from a start-of-session harness calibration × a user compute-budget setting; a fired wall bound = `undetermined` (retried once, then named). Acceptance: the SAME check across this machine normally, under `taskpolicy -b` (efficiency cores — a slow-machine simulation), and on the old Mac Pro. |
| 2 | EP-C1 | "have the record honestly abstain about the context, maybe point to … a command … for a proper, complete diagnosis" | The formatting cost is already gone (Wesker `49f7e91`: reports carry `Type: message`). Add explain-on-request: one command re-runs ONE mutant's killing test with full pytest reporting — the cost paid only when asked, and the kill record points at it. |
| 3 | EP-A1 | in-memory "seems like … ANOTHER burden on RAM/statefulness" | Never write the trial into the user's file at all: the verification already runs pytest in a subprocess with `-p Wesker.verification_manifest` (`certify.run_pytest_verification`), so an import-overlay plugin serves the trial source for exactly the target module inside that subprocess. Cost: one module's source in a temp dir; nothing to restore; the journal retires to a one-release recovery shim. |
| 4 | EP-A2/A3 | "addressed/persisted with appropriate provenance tracing" | `.detective/` is gitignored, so the human stores have no history anywhere. An append-only judgment history (time, actor/command, versions, target revision, evidence digest, before/after, superseded event) written in the same transaction as the current state. |
| 5, 14 | EP-C4 | "Advice on how to handle the package management?"; "professionalism pass item" | One uv-managed `.venv` on 3.14 runs Detective (tests and CLI); the analysis toolkit lives in `uv tool` installs or its own env, never the interpreter that runs Detective; toolkit pytest plugins only ephemerally (`uv run --with`); the standing invocation moves off miniconda base. Product side: `regime`/`doctor` DISCLOSE undeclared auto-loaded plugins (never disable a user's plugins). |
| 6 | EP-C5 | native paradigms, C/C++/Rust/JIT | Agreed with Codex: re-profile across target classes after the timeout, parallel and compute-once work; the pinned decision layer never leaves Python (it must stay pinnable by Detective itself); native (mypyc first, Rust only for a measured kernel) only where a profile shows a substantial mechanical kernel. |
| 7 | EP-A6 | "If we're doing this right, then that shouldn't be an issue … a MASSIVE unlock" (Uroboros) | Transactional stores + source-untouched trials + private bytecode + private generated-test directories published by one coordinator with revision checks. Then Uroboros stage 3: K functions × M=1 first, nested parallelism second, one jobserver-style CPU budget plus a memory bound. |
| 8 | EP-A7 | "We should implement this"; cross-correlated files | SQLite (stdlib) for `.detective/`: short transactions, WAL, foreign keys with cascades (the "cross-correlated existence" asked for: a function's cache, pins and certificates follow its record; eviction becomes a query), JSON export for review. The PRODUCT (generated suites, certificates) stays files in git, published via a manifest. |
| 10 | EP-B2 | "Same" | The harvest stays in-process (captured inputs are live objects) with the same step budget and liveness bound as every other execution. |
| 11 | EP-B3 | "disciplined handling of >=3.12 as the standard with appropriate legacy handling" | One instrumentation owner: `sys.monitoring` on 3.12+ (also the cheap way to count steps for item 1), `settrace`/`setprofile` as the legacy backend. |
| 12 | EP-B4b | "similar ignorance-driven issue" | Reads of `sys.modules`, `sys.path`, `sys.flags`, `platform`, `sys.version*` count as environment reads; such goldens are withheld or stamped. |
| 13 | EP-C2 | "sensible cache lookup if code is unchanged between runs" | First verify whether passes really regenerate an identical universe (see the correction above); propagate within a run; persist across runs only under the full generation key, after measuring hit rate against generation cost. |
| 15 | EP-D1 | "I'd love to be able to genuinely build parallelism in" | Executor lives in Wesker beside its pytest runner, behind a plain-data protocol. First measurement (Codex's): serial vs parallel evidence equality, startup cost, memory. Backend choice below (a founder decision). |
| 16 | EP-E1 | "Yes, add 3.14. I meant for 3.14 to be the standard" | `.python-version` 3.14, `.venv` rebuilt on 3.14, 3.14 in the CI matrix and classifiers, 3.14 the Sonar/coverage cell. |
| 17 | EP-G1 | "the ceiling is to implement a typed, named solution for every genuinely deterministic, resolvable item … and communicate it correctly" | Resolve the six OPEN sites by typed, named solutions: split `array_source_disposition` (dtype admissibility, then finiteness over the measured fact); give `regression_recovery` an explicit retry-possible input and dispatch on it; name `skip_unchanged`; carry the three classification causes to the verdict; NAME `unknown_herb`; count the two C-gate standings apart. |
| 18 | EP-G2 | "Professionalism pass" | Build the field guard, reflection- and equality-aware; each unread field is wired or deleted. |
| 19 | EP-G3 | "best implementation that aligns with the strict information theoretic rigor on knowability" | Absence is not a value: where the object's type is known, a DIRECT read (a rename fails loudly, and ty sees it); where it genuinely may lack the field, a three-valued read (present-true / present-false / absent) whose `absent` renders as "could not determine", never as clean; `typing.Protocol`s for the duck-typed results so ty checks every read. |
| 20 | EP-G4 | "Same" | Fix the two remaining re-derivations as part of item 17. |
| 21 | EP-G6 | "The end state is what matters, mid-process issues are operator problems … Weakening this weakens the strict guarantees" | CLOSED: no change to the sentence. (Item 3 also makes it literally true mid-run.) |
| 22 | EP-H1 | "classify, reason over best practice handling" | Named outcomes for the witness search (terminated-distinct, terminated-same, step-budget-divergent, wall-undetermined); per-input step budgets relative to the original on that input; the wall bound only for liveness. |
| 23 | EP-H5 | "yes, high value target" | `pytest-xdist` in the dev group, `-n auto --dist loadfile` in CI, after repeated green runs under xdist. |

**Order proposed:** (1) measurement correctness — timeout semantics and step budgets, the monitoring owner,
calibrated liveness bounds, the cross-hardware SAME check; (2) state foundations — SQLite stores with
history and cascades, source-untouched trials, compute-once, 3.14 and package hygiene, xdist in CI;
(3) the parallel executor behind the plain-data boundary; (4) the Uroboros fleet; (5) the surface items
(G1–G4, B4b, explain-on-request), which are independent and can interleave anywhere; (6) re-profile, then
native only where measured.

---

## 7. The orphaned execution lock (2026-09-27) — measured, one layer fixed, the rest for the founder

**Symptom.** From Wesker's repo, `detective converge 'Wesker/monitoring.py::step_budget_verdict'` was
REFUSED on every run ("the engine could not take its execution lock (orphaned)") while
`tests/test_monitoring_step_budget_intent.py` existed. Removing any subset of its tests that left one
routed to the target did not clear it; removing the whole file did.

**Instrument.** A `sitecustomize` probe (scratchpad, not product code): `Wesker.engine._EXECUTION_LOCK`
replaced by a forwarding proxy right after the module executes (repr forwarded, so the repr-owner orphan
channel reads exactly what it read), logging every acquire attempt/result/release with thread and stack;
wrappers on `_run_test_with_timeout`, `interrupt.abandon` (with the target thread's stack at that moment)
and `_build_test_scope` (its inputs and outputs, and each mutant's covering set). Accepted as evidence
because the verdict under it is unchanged (REFUSED, twice). One engine module and one lock in the process —
the second-module hypothesis is refuted.

**The chain, measured.**

1. Pass 0 (`converge.py:1836`): target-first seeds the session baseline with the 2 candidate intent tests
   (`line_cov` = lines 82–84, correct), but the POOL handed to `run_function_profiling` was **694** tests —
   the collection minus proof-grade impossibles (`Detective/engine.py`, the `run_function_profiling` call
   in `profile`). 690 are `not_consulted` under the 2026-09-05 ruling and were never traced.
2. The first mutant, `ARITHMETIC_7e90ecd4`, is on the `def` line: it rewrites the `|` in the parameter
   annotation `cap: int | None`, which `from __future__ import annotations` keeps a string nothing
   evaluates. Line 75 is outside the traced lines, so `_tests_for` (`Wesker/engine.py:4222`, "no data for
   this line — cannot scope safely") returns the whole pool. No candidate can kill an inert mutant, so the
   evaluation walks the suite.
3. At +0.13 s it reaches `tests/test_admissible_evidence.py::test_a_failing_tests_reach_is_observed_but_not_admissible`,
   which runs `run_function_profiling` in-process on a fixture. In the test's worker thread the nested
   `_baseline_failures` is refused `held_by_live_thread` (bounded) and carries on; the nested
   `evaluate_mutant` then blocks in `_serialized`'s 5 s C-level acquire. A wait-for cycle: the main thread
   holds the lock and joins the worker; the worker waits on the lock.
4. The mutant's allowance (~230 ms) expires; `bounded_join` → `abandon`: the injection cannot land in a
   thread blocked in C (`contained=False`, result `uncontained`). The main thread finishes and releases.
5. The worker's acquire returns and the pending `Abandoned` lands before `_note_lock_entry` — the documented
   HONEST LIMIT window — so it dies owning the RLock with the record 0/0. The next evaluation's probe reads a
   dead owner in the repr: `orphaned`, re-raised, REFUSED.
6. Without the intent file, pass 0 has no candidate: `_activate_target_first` → `synthesize`, an EMPTY pool,
   and later passes profile only the written suite — the whole-collection pool never occurs. That is the
   whole of "only removing the file clears it".

**An independent reading** (Codex, GPT-6-Astra medium, read-only; the lead's reading written first, to
`scratchpad/codex/my_reading_lock_orphan.md`) agreed on the chain and on both fixes, and added four points,
each checked in the code: the same cycle can form in the BASELINE phase (`_baseline_failures` holds the
lock while its workers run tests, `Wesker/engine.py:4012-4018`); a refusal raised as a `BaseException`
alone is still read as a crash kill (`_run_test_with_timeout`'s `except BaseException`, `:6001`, and
pytest's own capture), so it needs a status channel that survives interception; the two-sign return-type
harvest ran the whole collection even for a leaf orphan; and a routing exception silently falls back to
the whole collection.

**Fixed (Detective, this pass).** `profile`'s pool is the CONSULTED set: on the seed route, the candidates
then the widen-admitted, shape-admitted unknowns (the capture harvest's membership, `_applicable_harvest_pool`,
with the widen's shape deferral); on the leaf-orphan route, nothing. The two-sign harvest takes the same
pool. Evidence: `tests/test_engine_pool_is_the_consulted_set_intent.py` (2, through a real live session; a
no-path test that counts its own executions — both FAIL on the previous code, at exactly `ran == 0`); the
e2e fixture's converge is byte-identical before/after (FINAL, generated suite, certificates, full report) —
a no-regression check only, since its pass pools were already the candidates; and the refused converge now
reads `✓ COMPLETE (operator universe · modulo 2 unproven-equivalent) · 10/11 killed`, `not consulted 690`.
Verdicts cached under the old pool are keyed identically until the next version bump (`engine_fingerprint`).

**Open — the founder's calls, with both readings' recommendations.**

| Item | What | Recommendation |
|---|---|---|
| Lock cycle | A consulted test that runs the engine in-process (most of Wesker's engine internals have them) still deadlocks the same way, in evaluation or in the baseline guard — detected and refused honestly, never prevented. | Prevent it: a worker whose measurement parent holds the lock refuses INSTANTLY (never enters the C wait) with a named non-kill outcome carried by a status channel that survives interception — undetermined, never a crash kill, never survival. Build it with item 1, which rewrites the same test-outcome vocabulary. Delegated re-entrancy for the measurement's own worker is the fuller answer (the isolated worker already gets it from same-thread RLock re-entrancy) but more invasive, and until timeouts stop being kills it turns a nested overrun into a false kill. |
| Annotation sites | The generator mutates annotations; under PEP 563 (and PEP 649 absent introspection) such a mutant is inert except to code that evaluates annotations (FastAPI, pydantic, beartype, `get_type_hints`). | Codex: exclude annotation subtrees from the runtime operator universe (a policy change: the policy id moves). Lead: the founder's call — for introspecting frameworks the site is behavioural. |
| Unscreened fallback | The fallback now runs only consulted tests, but a widen-admitted test in the pool is not baseline-screened until the widen traces it. | Screen before the fallback may run it (defensive, Wesker side). |
| Routing failure | `profile`'s target-first `except Exception` and `_applicable_harvest_pool`'s `ImportError` path both authorize the whole collection silently. | Under the ruling routing is the applicability bound, not an optimisation: name the failure rather than widen to the suite. |
| Allowance vs pool | `evaluate_mutant`'s `timeout_ms` is ONE budget for the whole mutant, sized from the covering tests; a large fallback pool spends it and returns `killed_by="timeout"` — a false kill (code reading; no timeout occurred in these runs). | Closed by item 1 (a fired wall bound is undetermined); the pool fix removes the amplifier. |

`step_budget_verdict`'s two remaining candidates, as the tool reports them: `ARITHMETIC_7e90ecd4` (the
annotation) and `BOUNDARY_1406e1d0` (`if cap is None:` → `if False:`). The lead's observation, not the
tool's: the witness search tries only integers for `cap`, and `(0, None)` makes the second raise `TypeError`
where the original returns `"unbounded"`; the intent test with `cap=None` already detects it by crash.
