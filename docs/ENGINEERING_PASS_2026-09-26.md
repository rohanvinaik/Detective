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
| **EP-A3c** | M | A write refused under EP-A3 is announced on stderr, but the verbs that called it (`flag`, `flag-line`, `flag --style`, `--input`) still exit as if it saved. Thread the refusal into their exit status. | OPEN |
| **EP-A4** | M | Other truncate-then-fill writes of files that matter: `suite_edit.apply_removals` (user tests, `audit --remove`), `regime.apply_migration` / `_declare_pythonpath` and `certify.ensure_marker_registered` (user `pyproject.toml`), `certify._write` (the product), `converge` restoring a prior suite (L2286), `receipt -o` (a pre-rewrite snapshot), `cli._update_per_mutant_ms` (telemetry). | OPEN |
| **EP-A5** | L | Two atomic writers in the pair with different guarantees: Wesker `trace_cache` fsyncs before `os.replace`; Detective `atomic_store` does not. | OPEN |
| **EP-A6** | M | No project lock around read-modify-write of shared stores. `atomic_store`'s docstring names it as owed (#63); "never run two converges at once" is a human rule the tool does not enforce. For a cache a lost update costs time; for a human store it loses a judgment. | FOUNDER |
| **EP-A7** | L | The verdict cache never evicts entries for functions that no longer exist (single-valid-copy is per function). Harmless at measured sizes (largest: Peitho 1.4 MB). | OPEN |

### B. Interpreter and process state (what is shared while a run is in flight)

| Code | Sev | Finding | Status |
|---|---|---|---|
| **EP-B1** | H | `_MUTANT_ALLOWANCE_FLOOR_MS = 50` (`Wesker/engine.py`) with `× 50` baseline scaling is calibrated against the TEST's runtime; the evaluation also pays thread start, pytest's protocol and, per kill, ~14 ms of report formatting (EP-C1). A pre-entry timeout reads as `mutant_not_entered` → UNGATEABLE, or flips kill/survive. Evidence §3.1. Remedies, ranked by the project's own laws (DETERMINISTIC_SICP constraint 6, "efficiency = deterministic budgets, never wall-clock"; COMMUNICATING_DETERMINISM §4, cannot-determine never renders as determined): (a) **wall-clock may BOUND a measurement, never BE one** — a timeout that fired before the entry probe was reached is "could not measure", so it is retried under a bounded, escalated allowance and, only if it persists, recorded as the cut reason it already names; (b) size the floor from a harness quantum measured at session start, which reduces how often (a) fires on a slow or loaded machine — this is the concrete meaning of "adapt to the hardware"; (c) remove the harness waste that eats the margin (EP-C1). Probably explains the e2e `_skip_if_proof_cut` CI skips. **Hypothesis, not tested:** part of the documented live-session scored-count noise (MEMORY: converge determinism) may be this rather than state leakage. | FOUNDER |
| **EP-B2** | M | `capture.capture_call_inputs` / `capture_return_types` save and restore `sys.getprofile()` assuming a Python callable. Under pyinstrument the slot holds `ProfilerState`; the restore raises `TypeError` and the converge dies with a traceback. The harvest also has no per-test bound (only between tests), so one runaway test runs until the hang watchdog hard-exits the whole command. | OPEN |
| **EP-B3** | M | Three owners of process-global interpreter hooks, each with its own install/restore: Wesker `line_coverage` (`sys.settrace`), Detective `capture` (`sys.setprofile`), Detective `equivalence._reached_lines` (`sys.settrace`). On 3.12+ cProfile, VizTracer, memray and coverage.py all leave both legacy slots EMPTY — they moved to `sys.monitoring`, whose tool IDs coexist by design and whose local events cost nothing on code other than the target. Recommendation: one instrumentation owner with a `sys.monitoring` backend (3.12+) and the legacy backend (3.10/3.11). Semantics to settle: `settrace` is per-thread, `sys.monitoring` is process-wide, so the monitoring backend must filter by thread or a leaked runaway could attribute coverage to the next test. | FOUNDER |
| **EP-B4** | M | `synthesis/writer.numeric_backend_for` reads `sys.modules` to append a version. Its synth golden captured `'numpy'`; with jaxtyping's pytest plugin importing numpy at session start it returns `'numpy 2.5.3'` — one of the 25 miniconda failures. Detective pinned a process-state fact as a pure value: `purity` does not treat `sys.modules` (or `sys.path`, `sys.flags`, platform) reads as environment dependence. Remedy: split the pure decision (source → backend name) from the impure version read, per the house extraction rule; extend environment-read detection. | OPEN |
| **EP-B5** | — | NOT a finding: the execution lock (`_LOCK_OWNER_TID`/`_LOCK_DEPTH`, three orphan channels, bounded acquires, pinned disposition) was built 2026-09-10 and is sound. The memory note calling the RLock hang "undiagnosed" predates it. | — |
| **EP-B6** | ? | Hypothesis, unverified: tests run in fresh worker threads, which start with an EMPTY context on the default 3.14 build (they inherit it on free-threaded builds, `sys.flags.thread_inherit_context`). Anything a test thread reaches that reads `_LIVE_SUITE` / `_SESSION_BASELINE` sees the default. Wants a probe before it is a claim. | OPEN |

### C. Efficiency (measured; SICP — compute a value once, where it becomes known, and never compute one nobody consumes)

| Code | Sev | Finding | Status |
|---|---|---|---|
| **EP-C1** | H | Failure-report formatting nobody reads (§3.2). Remedy built: in Wesker's measurement session only, each item gets a cheap `repr_failure` so pytest's own report construction runs unchanged but skips source extraction. Verified: identical verdicts, byte-identical generated suites and certificates, full suites of both repos. Follow-up: the isolated worker (a separate process) still formats. | FIXED Wesker `49f7e91` |
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

### G. The CLI — a communication surface, audited against its own theory

Read first, and binding: `theory/mechanical_layer/MECHANICAL_LAYER.md` §7, `theory/COMMUNICATING_DETERMINISM.md`
(the injectivity criterion, the §9 invariants, the §10 list of refused "improvements"),
`theory/deterministic_sicp/DETERMINISTIC_SICP.md` §14 and its constraint block. The surface is DERIVED;
its size (`cli.py` is 8,407 lines, ~25% of the package — matching the paper's "roughly a quarter") is
the product, not overhead. So this pass does not re-shape what the surface says. It builds the checks the
theory calls decidable and missing, and it records claims for the founder to rule on.

| Code | Sev | Finding | Status |
|---|---|---|---|
| **EP-G1** | M | Invariant 3 — "every consumer distinguishes all of a decision's codes" — is decidable over the reference graph and unbuilt (COMMUNICATING_DETERMINISM §3.2, §11). §MI and #60 were both instances found by hand. Build it as a standing guard beside `consumption.py`. | OPEN |
| **EP-G2** | M | The consumption guard covers functions, not FIELDS (§11): a computed field no reader reads (`capability_flags` for a wave) is invisible. Field-level consumption, with serialization-by-reflection (`asdict`, `to_json`) named as the known blind spot. | OPEN |
| **EP-G3** | M | Invariant 7 — no `getattr(obj, name, default)` where a renamed field would be absorbed into a silent clean verdict — is unchecked. A string-literal attribute access is exactly what the reference graph cannot see; an AST query can. | OPEN |
| **EP-G4** | M | Invariant 8 — "one derivation, N renderers" — is unchecked: detect a renderer that re-derives what a decision already computed. The SICP lineage question (compute once, hand to every consumer) applied to the surface. | OPEN |
| **EP-G5** | L | `cli.py` is in `[tool.coverage.run] omit`, so its line coverage is unknown. A MEASUREMENT (never a gate): run coverage on it once and report which renderer branches no test reaches. | OPEN |
| **EP-G6** | — | Claims for the founder, recorded, not changed: decompose's STOP block says "your source was NOT touched", and ARCHITECTURE §5 says a dry run "writes nothing"; during the run the trial IS written to the user's file and then restored (EP-A1). True of the end state, not of the run. | FOUNDER |

Census for orientation, not as a target: 169 top-level functions — 19 pinned decisions (689 lines), 33
renderers (1,963), 18 verb handlers (1,377), the parser (668), 98 others (2,948). Size is not a defect
under this theory; a non-injective sign is.

### H. The test suite

| Code | Sev | Finding | Status |
|---|---|---|---|
| **EP-H1** | M | Suite time is concentrated, not diffuse. Locked `.venv`: 3,256 tests in ~208 s; `test_b0_kills_a_residual_the_default_pool_leaves_candidate_equivalent` alone is 110.5 s (~53%); the top seven ≈ 70%; the other ~3,250 tests ≈ 60 s. **Root cause of the 110 s, measured** (a `faulthandler` stack sampler — no trace/profile/monitoring hook, so it cannot perturb the timing-sensitive search the hooking profilers perturbed): all 55 samples show a worker thread inside `<mutant>:sum_reachable` and the main thread in `bounded_join ← _outcome ← _search_witness ← classify_survivors`. The test spends its whole life waiting out `_CLASSIFY_TIMEOUT_S = 5.0` on worklist mutants that never terminate (~22 timeouts); CPU-bound (they spin), 44 MB peak (they do not allocate — the memory hypothesis was refuted). A timeout is `blocked` — never evidence — so its SIZE trades only speed against the ceiling. One-variable A/B on the test's own two calls: the complete classification (every verdict's repr, both arms) is **byte-identical at 5.0 s and 0.25 s; 110.5 s → 6.0 s**. **Test-level fix applied** (the bound set inside that test, evidence in its comment). **Engine-level, a founder call:** every user function with a loop pays up to 5 s per (non-terminating mutant × candidate input); a per-input bound relative to the ORIGINAL's measured time on that input (hardware-adaptive), plus one full-cap probe per mutant to protect the ceiling, is the general form — measure the classification delta on real targets before adopting. EP-C1 should also cut every test that runs a real converge. | test-level FIXED (§5) · engine FOUNDER |
| **EP-H2** | M | **The decompose trial path had no working end-to-end test.** `test_decompose_apply_preserves_behaviour` SKIPS ("no seam was applied") because `shipping_cost`'s only candidate leaves a pure delegating wrapper and the value gate rejects it before any trial. EP-A1's intent test uses a fixture with a genuine seam, and FAILS rather than skips if it ever stops trialling. The e2e test's fixture needs the same treatment. | OPEN |
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
| Wesker `49f7e91` | EP-C1 | the measurement session's items get a cheap `repr_failure` / `_repr_failure_py`; pytest's report construction otherwise untouched | SAME check through the real CLI: FINAL + generated suites + certificates byte-identical on two fixtures; instructions 27.85 G → 17.66 G (−37%) and 8.34 G → 7.47 G; B0 digests unchanged · Wesker `tests/test_cheap_failure_repr_intent.py` (4) · Wesker 894 passed · Detective 3267 passed in 95.3 s |
