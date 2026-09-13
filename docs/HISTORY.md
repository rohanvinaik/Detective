# Detective — why the rules are what they are

[ARCHITECTURE.md](../ARCHITECTURE.md) states how Detective works now. This file keeps the incidents
that produced its rules, because the evidence is the reason: each rule there that begins "why:" links
to an entry here. Numbers are as measured at the time and are not kept current.

---

<a id="h1"></a>
## H1. Discovery without a live session skipped every fixture-taking test

Wesker's fallback discovery collects with `--collect-only`, which tears the session down at once, so
every fixture-taking test is skipped. A mutant only such a test could kill then reports as a surviving
behavioral gap — Detective claims a dimension is unspecified when the suite already pins it, and
`converge` writes a test for behavior that was never unspecified. Measured on Prism: 0 of 445 tests
bound the old way, 445 the new way. `cli._run_live` became the only entry point (the parked MCP
surface's `_in_session` was the second), and it degrades **loudly**; a silent fallback is the exact
failure the seam exists to end.

<a id="h2"></a>
## H2. Scoping resolved relative paths against the process's cwd

The scoping is computed BEFORE the seam chdirs, so it must not depend on the cwd — and it did.
`module_name` resolved a relative target with `os.path.abspath`, i.e. against the *process's* cwd
rather than `project_root`. From a CLI run standing in the project the two coincide and it scopes
correctly; from a stdio server — whose cwd is wherever its client launched it — the target resolved
outside the tree, fell out of the graph, and the analysis returned `None`. Because `_reachable_paths`
deliberately degrades any failure to "collect everything", a wrong answer and a declined optimisation
are indistinguishable from outside: the MCP surface silently traced ~9x the suite (2113 vs 240),
which then guaranteed the session trace budget cut and reported the cut coverage as unpinned
behaviour.

<a id="h3"></a>
## H3. The trace budgets reached only a path a live session never uses — and the cache recorded the wrong ones

The trace budgets bound the pass that traces the suite, and on the live path that pass runs *inside
the seam*, not in `profile()`. Sent only to `profile()` they reached the per-function path a live
session never uses, so raising the flag changed nothing.

The mirror of that bug was the cache key. Inside a live session `_build_test_scope` prefers the
`SessionBaseline` and never consults `profile()`'s budget arguments, so they describe nothing about
the verdict; the seam's budgets do. The CLI passed the same values to both and was correct by
discipline, while every other caller (`audit_suite`, `converge`, `certify`, `decompose_apply`,
`classify_survivors`, the MCP surface) sent them to one side only — writing a tightly-budgeted
measurement under the DEFAULTS' key, to be served later to a run that asked for the defaults. A
verdict must be keyed on everything that could have produced it; discipline is not a mechanism.

<a id="h4"></a>
## H4. Budgets missing from the cache key made the CLI's own remedy unfollowable

A budget cuts the traced baseline, and what it cut lands in the result as `truncated` and as absent
`line_coverage`. A key blind to the budgets served the tighter run's coverage to the looser one, so
the CLI's own remedy ("raise `--trace-budget` to measure them fully") returned the cached under-count
unchanged — measured on Regenesis, 152 cuts served where a fresh run computes 210.

<a id="h5"></a>
## H5. The live session's collection is a snapshot, and Detective writes tests

`discover_test_callables` short-circuits to the session's callables, which is right for a consumer
that only READS a suite and silently wrong for one whose product is writing tests: `converge` writes,
re-profiles, and was handed a list that predated its own work. Refreshing the list alone changed what
was *discovered* and nothing about what was *run* — the count stayed exactly as wrong (measured: 18
mutants killed by tests on disk, reported as 2, with the user asked to supply inputs for the 14
already dead).

<a id="h6"></a>
## H6. `failing_tests` reported other functions' tests as this one's

Wesker's baseline is repo-wide, so an unscoped field silently reports other functions' tests as the
target's: `failing_tests` was that field, and it put 2126 unrelated names (56KB) into a one-function
report until it was bound by the same scoping rule as its siblings.

<a id="h7"></a>
## H7. Parallelism was removed in 0.8.0 because it never ran

`parallel.py` held a model-A fan-out, an adaptive probe, a shard merge, and a portable memory
guarantee sizing the fleet by construction — ~200 lines, plus a private
`Wesker.memory_guard._DEFAULT_WORKER_PEAK` import. None of it ran. `main` wraps every command in the
live session, the session's callables cannot cross a process spawn, and `profile` therefore refused to
fan out inside one — which is every CLI and MCP run. Proven, not inferred: `--parallel` (5.04s) and
`--serial` (5.13s) cost the same, the 448-test suite made **0** calls to `parallel_profile`, and a
*forced* `--parallel` on a 37-mutant function spawned **0** workers while returning the identical
verdict.

The apparatus was load-bearing only for itself. It existed because the baseline was suite-shaped and
per-function cost looked large; once the baseline became a per-session constant, the cost it was
built to amortise was already gone. The memory guarantee guarded a fleet that never existed. Serial is
not a regression — it is what was always running.

<a id="h8"></a>
## H8. The cache key has two readers, and they drifted

`cache_key` builds the key; `put` re-parses it for single-valid-copy (drop this function's entries for
the same *question* whose content hash no longer matches, so the file stays bounded at one row per
function/params). Appending a key field without updating the parse silently redefined the slice, and a
`--fast` run evicted the comprehensive entry it should have sat beside. The field count now lives in
`_PARAM_FIELDS` beside the builder, and `put` calls `params_suffix()` rather than slicing inline.

<a id="h9"></a>
## H9. `purge` purged one of two caches and announced a clean state

`purge` used to delegate only to Wesker — written back when Wesker owned all the state — so it purged
a file that (outside Wesker's own tests) is never written, missed the multi-MB Detective cache that
is, and reported *"a clean state"* over it. A command that purges one of two caches while announcing
cleanliness is worse than one that purges neither: the user acts on the claim. Wesker's
`purge_caches` later had the same gap for its own `trace_cache.json`.

<a id="h10"></a>
## H10. `diagnose --learn` was removed in 0.8.0

It accumulated per-category value-survival into a project-wide `.wesker/mutation_report.json` and
reported "which categories THIS project leaves weak" — a statistical smear over unrelated functions,
standing where an exact per-function derivation already was. It changed no verdict; nothing branched
on it, no test named it, and it only ever ordered categories for a sampler this tool does not use by
default.

<a id="h11"></a>
## H11. The command printed nothing and exited 0

The baseline runs the target's own suite; a test over its cap is abandoned, and the abandoned frame
unwinds through any `redirect_stdout` IT entered, reinstalling that buffer AFTER the engine restored
the real one. `sys.stdout` was then a dead buffer for the rest of the process: in CI, an empty
artifact and a green check. Not a crash — the analysis was correct and posted to a discarded buffer.
The fix lives in Wesker's `_run_test_with_timeout` (the unwind join happens inside the redirect), with
`ci._body` re-entering the streams around the baseline as a second guard.

<a id="h12"></a>
## H12. A generated `conftest.py` collided with the project's own

Registering the `detective` pytest marker used to write a root `conftest.py`. A generated
`conftest.py` and an existing `tests/conftest.py` both import as the module `conftest` in any tree
whose `tests/` is not a package, and in a process that imports both the second raises
`import file mismatch`. Plain pytest tolerates it; Detective's own in-process live session did not, so
it died, silently fell back to collect-only discovery, and every fixture-taking test vanished from the
profile — overstating surviving behaviour on exactly the repositories careful enough to use fixtures,
including Detective's own. The marker is now declared in `pyproject.toml`
(`certify.ensure_marker_registered`), which cannot become a second module named `conftest`.
