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
| **EP-A1** | H | `decompose_apply._apply_decomposition_impl` trial-writes the user's source (`open(full, "w")`, L999), runs `_suite_green()`, reverts at L1035 — no `try/finally`, even when `write=False`. Remedy: `try/finally` revert, atomic writes, and a write-ahead trial journal in `.detective/` so a hard kill is detected and restored on the next run. | OPEN |
| **EP-A2** | H | `samples.remember` writes `.detective/inputs.json` truncate-then-fill, and on a parse failure sets `data = {}` and writes back ONLY the current function's entry — one interruption plus one `--input` erases every other function's human input. The one human store #63 missed. | OPEN |
| **EP-A3** | M | Unreadable ≡ empty, in 8 of 9 stores (`equivalents`, `line_flags`, `judgments`, `pins`, `certificates`, `samples`, `promotion_ledger`; `ledger` skips lines). A hand edit with a stray comma or a merge-conflict marker is then silently overwritten by the next write. `verdict_cache.load` alone quarantines (`.corrupt`) — protection inverted relative to value. Remedy: ONE reader discipline shared by every store, with a named disposition (`absent` / `readable` / `unreadable`) and quarantine-before-write, mirroring #63's one writer. | OPEN |
| **EP-A4** | M | Other truncate-then-fill writes of files that matter: `suite_edit.apply_removals` (user tests, `audit --remove`), `regime.apply_migration` / `_declare_pythonpath` and `certify.ensure_marker_registered` (user `pyproject.toml`), `certify._write` (the product), `converge` restoring a prior suite (L2286), `receipt -o` (a pre-rewrite snapshot), `cli._update_per_mutant_ms` (telemetry). | OPEN |
| **EP-A5** | L | Two atomic writers in the pair with different guarantees: Wesker `trace_cache` fsyncs before `os.replace`; Detective `atomic_store` does not. | OPEN |
| **EP-A6** | M | No project lock around read-modify-write of shared stores. `atomic_store`'s docstring names it as owed (#63); "never run two converges at once" is a human rule the tool does not enforce. For a cache a lost update costs time; for a human store it loses a judgment. | FOUNDER |
| **EP-A7** | L | The verdict cache never evicts entries for functions that no longer exist (single-valid-copy is per function). Harmless at measured sizes (largest: Peitho 1.4 MB). | OPEN |

### B. Interpreter and process state (what is shared while a run is in flight)

| Code | Sev | Finding | Status |
|---|---|---|---|
| **EP-B1** | H | `_MUTANT_ALLOWANCE_FLOOR_MS = 50` (`Wesker/engine.py`) with `× 50` baseline scaling is calibrated against the TEST's runtime; the evaluation also pays thread start, pytest's protocol and, per kill, ~14 ms of report formatting (EP-C1). A pre-entry timeout reads as `mutant_not_entered` → UNGATEABLE, or flips kill/survive. Evidence §3.1. Remedies, in order of how general they are: (a) calibrate the floor from a measured harness quantum at session start (this is what "adapt to the hardware" means concretely); (b) treat a timeout that fired before the probe was entered as a retriable measurement limit, re-run once with an escalated allowance, never as evidence; (c) remove harness waste (EP-C1). Probably explains the e2e `_skip_if_proof_cut` CI skips. **Hypothesis, not tested:** part of the documented live-session scored-count noise (MEMORY: converge determinism) may be this rather than state leakage. | FOUNDER |
| **EP-B2** | M | `capture.capture_call_inputs` / `capture_return_types` save and restore `sys.getprofile()` assuming a Python callable. Under pyinstrument the slot holds `ProfilerState`; the restore raises `TypeError` and the converge dies with a traceback. The harvest also has no per-test bound (only between tests), so one runaway test runs until the hang watchdog hard-exits the whole command. | OPEN |
| **EP-B3** | M | Three owners of process-global interpreter hooks, each with its own install/restore: Wesker `line_coverage` (`sys.settrace`), Detective `capture` (`sys.setprofile`), Detective `equivalence._reached_lines` (`sys.settrace`). On 3.12+ cProfile, VizTracer, memray and coverage.py all leave both legacy slots EMPTY — they moved to `sys.monitoring`, whose tool IDs coexist by design and whose local events cost nothing on code other than the target. Recommendation: one instrumentation owner with a `sys.monitoring` backend (3.12+) and the legacy backend (3.10/3.11). Semantics to settle: `settrace` is per-thread, `sys.monitoring` is process-wide, so the monitoring backend must filter by thread or a leaked runaway could attribute coverage to the next test. | FOUNDER |
| **EP-B4** | M | `synthesis/writer.numeric_backend_for` reads `sys.modules` to append a version. Its synth golden captured `'numpy'`; with jaxtyping's pytest plugin importing numpy at session start it returns `'numpy 2.5.3'` — one of the 25 miniconda failures. Detective pinned a process-state fact as a pure value: `purity` does not treat `sys.modules` (or `sys.path`, `sys.flags`, platform) reads as environment dependence. Remedy: split the pure decision (source → backend name) from the impure version read, per the house extraction rule; extend environment-read detection. | OPEN |
| **EP-B5** | — | NOT a finding: the execution lock (`_LOCK_OWNER_TID`/`_LOCK_DEPTH`, three orphan channels, bounded acquires, pinned disposition) was built 2026-09-10 and is sound. The memory note calling the RLock hang "undiagnosed" predates it. | — |
| **EP-B6** | ? | Hypothesis, unverified: tests run in fresh worker threads, which start with an EMPTY context on the default 3.14 build (they inherit it on free-threaded builds, `sys.flags.thread_inherit_context`). Anything a test thread reaches that reads `_LIVE_SUITE` / `_SESSION_BASELINE` sees the default. Wants a probe before it is a claim. | OPEN |

### C. Efficiency (measured; SICP — compute a value once, where it becomes known, and never compute one nobody consumes)

| Code | Sev | Finding | Status |
|---|---|---|---|
| **EP-C1** | H | Failure-report formatting nobody reads (§3.2). Remedy: in Wesker's measurement session only, give each item a cheap `repr_failure` so pytest's own report construction runs unchanged but skips source extraction. Verified against: identical verdicts, identical generated suites, full suites of both repos. | OPEN |
| **EP-C2** | M | `generate_mutants` runs once per profiling pass (4× per converge, 0.97 s cumulative, ~16%) though the function under test does not change between passes. Remedy: memoize per (source digest, qualname, policy, categories, per-category cap) for the process. | OPEN |
| **EP-C3** | L | `estimate_universe_size` 211 calls per converge (0.23 s); `_patch_module_qualified` scans all of `sys.modules` for every mutant (372 scans, 0.23 s) though the set of namespaces holding the target does not change between mutants. | OPEN |
| **EP-C4** | H (dev) | Ambient pytest plugins in the dev interpreter. Outer-process instructions for one e2e test: `.venv` 3.11 1.05 G · miniconda no-plugins 1.45 G · all ambient plugins 4.77 G (codeflash-benchmark +2.09 G, logfire +1.52 G, jaxtyping +0.44 G, memray +0.26 G); wall 6.7 / 7.6 / 17.2 s. The same plugins make 25 tests red via process-global warnings state (pytest-asyncio 1.4.0's `pytest_configure` warns; the suite's `filterwarnings = ["error"]` turns that into an INTERNALERROR in the nested session). Remedy: Detective's own nested sessions under test must not depend on undeclared plugins; the interpreter that runs Detective should not carry toolkit plugins (the toolkit's own rule: declare tools in a project's dev extra). Product-side proposal: `detective regime` could disclose undeclared ambient plugins, since they change both speed and semantics. | OPEN / FOUNDER (env) |
| **EP-C5** | — | Where native code would and would not help: measured cost is not in Python-level compute Detective owns. `compile` for 372 mutant evaluations: 0.03 s. Detective/Wesker AST work: < 1 MB allocation per call site. No Numba/Cython/Rust candidate exists until EP-C1–C3 are done and a re-measurement shows compute-bound hot loops. | — |
| **EP-C6** | M (dev) | One test is 36% of the suite: `test_structural_search_b0_intent` 110.5 s on both interpreters (so intrinsic compute, not environment). The rest: ~3,230 tests ≈ 100 s. Profile it after EP-C1 (it converges internally, so C1 may already cut it). | OPEN |

### D. Parallelism and hardware

| Code | Sev | Finding | Status |
|---|---|---|---|
| **EP-D1** | — | H7 removed parallelism because "the session's callables cannot cross a process SPAWN". `fork` does not pickle: a forked child inherits the warm live session by copy-on-write. Measured fork+work+exit+wait from a warm Detective/Wesker/pytest parent: 2.6 ms median (`gc.freeze()` no measurable change at that size). A fork-per-mutant worker pool would give parallelism AND per-mutant state isolation (cross-mutant leakage — and whatever of the count noise it causes — gone by construction). Preconditions: a single-threaded parent at fork (3.12+ warns otherwise, and the suite runs `-W error`), a fork-safety probe on macOS (Accelerate/Objective-C in the target's imports → serial), worker count from P-cores, free memory ÷ measured child RSS, and current load — and EP-B1's calibration first, because contention stretches evaluations. | FOUNDER |
| **EP-D2** | — | Hardware facts for sizing: 10 cores (8 P + 2 E); a converge on the fixture peaks at 47.9 MB heap (memray) / 72 MB RSS (3.11) / 127 MB RSS (3.14); the full suite peaks at 249 MB RSS. Memory is not bloated at the peak; ALLOCATION CHURN is (1.415 GB allocated for a 48 MB peak, 67% of it EP-C1). | — |

### E. Environment, CI, advice

| Code | Sev | Finding | Status |
|---|---|---|---|
| **EP-E1** | M | CI tests 3.11/3.12/3.13; the founder's standing interpreter is 3.14.6, and the converge path already runs 3.14-only machinery (`annotationlib`). Either add 3.14 to the matrix and the classifiers, or develop on a claimed version. | FOUNDER |
| **EP-E2** | M | `cli._format_session_warning` says "Pytest rejected a config/marker owned by `pytest-asyncio`. Install that plugin in this exact interpreter" when the plugin IS installed there and is the one raising. The premise (absent) is never checked — doctor's own named defect class. Remedy: a pinned pure decision over (plugin named, importable here, error kind) returning a named remedy code. | OPEN |

### F. The instruments themselves

| Code | Sev | Finding | Status |
|---|---|---|---|
| **EP-F1** | — | Observer effects on Detective, measured: pyinstrument → crash (EP-B2); cProfile, VizTracer, memray → `✓ COMPLETE` becomes `⚠ UNGATEABLE`/`Incomplete` (EP-B1). cProfile's `-m` runner also swallows `SystemExit`, so a `3` reads as `0`. Until EP-B1 is fixed, the faithful profiler for the full converge path is **py-spy** (external sampling, no interpreter hook; `sudo` on macOS). Instrumented runs of the pre-witness phases are usable: they match the plain run's narrative exactly through pass 1. | — |

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

(Filled as commits land.)
