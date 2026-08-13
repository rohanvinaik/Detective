# Dependency floors — the forensics behind every version pin

Every floor in `pyproject.toml`'s `dependencies` exists because a specific, measured,
usually SILENT failure mode sits below it. The pins carry one-line pointers; this file
is the evidence. (Moved out of `pyproject.toml` — issue #4: it was some of the best
writing in the repo, in the one file nobody opens. `dev/` rather than `docs/` because
this repo keeps long-form contributor documents here, beside `BUILD_PLAN.md`.)

Ordering below is as the pins accumulated — each floor's narrative names the release
that closed it and what breaks beneath it.

---

Runtime deps: the Wesker mutation engine (the profiler) AND pytest — Detective's
PRODUCT is pytest suites and it runs pytest to wire + verify them, so pytest is a
runtime requirement, not dev-only.

The PRE-PyPI-PUBLISH CHECKLIST that stood here is DONE, in its documented order:
Wesker went to PyPI first, the git-URL became a plain package spec, and
`[tool.uv.sources] Wesker` + `[tool.hatch.metadata] allow-direct-references` are gone.
Both existed only for the git-URL dev path; a PyPI package depends on the PyPI package.

>= 0.6.2 is what the MCP surface REQUIRES TO EXIST AT ALL. Below it, running pytest in-process
uses pytest's default fd-level capture, which replaces file descriptor 1 — and for a stdio MCP
server descriptor 1 IS the JSON-RPC channel. pytest's own progress output ("." per test, the
summary) is written straight into the response frame, the client reads `.{"jsonrpc":…`, fails to
parse it, and closes the connection. The server disappears mid-session with no traceback,
because nothing crashed. Reproduced directly: identical server, identical call — fd capture dies
on `McpError: Connection closed`, `--capture=sys` returns rc=0. It is NOT a timeout, and raising
MCP_TOOL_TIMEOUT (which defaults to ~28 hours) fixes nothing.

>= 0.6.0 was a CORRECTNESS floor, and the sharpest until this one: below it Detective can produce
NO OUTPUT AT ALL and exit 0. The engine runs the target's own suite to build its baseline; a test
that overruns its cap is abandoned, and an abandoned frame unwinds through any `redirect_stdout`
it had entered, reinstalling that buffer AFTER the engine restored the real one. From then on
`sys.stdout` is a dead buffer for the rest of the process, so the entire report is written to
nothing while the command exits 0 — in CI, an empty artifact and a green check, which is exactly
the "green suite's lie" this project exists to refuse, in the tool itself. Measured on Regenesis
(2134 tests, one JVM-backed test over the 5s cap): `diagnose` printed 0 bytes, exit 0. 0.6.0
unwinds inside the redirect so the engine's restore is last.

0.6.0 also carries the two seam fixes this floor depends on. `--trace-budget` /
`--trace-session-budget` now reach `run_with_live_suite`, which is where the suite is actually
traced — before, they reached only the per-function path the live session never uses, so raising
them changed nothing. And the session baseline is LAZY: it was built eagerly before the consumer
got control, so a run answered from Detective's own cache still paid the full trace and dropped
it unread (Regenesis, warm cache: 486s → 3.6s once demand-driven).

It is a MINOR bump, not a patch, because it REMOVES public API: `profile_function_cached` and
`single_valid_copy` (plus `_code_hash` and the `.wesker/function_cache.json` subsystem) are gone.
Nothing outside Wesker's own tests ever called them, but they were documented, and the cache they
served keyed on the function's hash and NOT its tests' — so editing a test served a stale verdict
to anyone who believed the docs. This package's `verdict_cache` is that idea done once, keyed on
everything that can change the answer.

>= 0.5.0 was the previous floor. Below it the traced baseline pass — which
runs BEFORE any mutant and costs a callback per executed line — has no budget at all, so a
computationally heavy test in the target's suite makes `diagnose` hang with zero output: not a
slow answer, no answer. 0.5.0 also stops abandoning timed-out test threads, which used to leak a
live thread per timeout and make LATER mutants time out because earlier ones were still running.

>= 0.4.0 was the floor before that. 0.3.0 gates `return_none` behind
`not is_pure and (self_assigns or globals)`, so 92% of functions never have their return
value questioned, and its kill attribution silently discards every kill a parametrized
test earns. Detective's verdicts are only as honest as the engine underneath them.

Local dev now resolves Wesker from PyPI like everyone else. To make edits in a sibling
../Wesker checkout live again, add back (uv-only; it never reaches the wheel metadata):
    [tool.uv.sources]
    Wesker = { path = "../Wesker", editable = true }
>= 0.7.2 is a CORRECTNESS floor of the same family as 0.6.0, and it is what makes `audit`'s
⚠ line trustworthy at all. Below it, `pytest_runner._reset_item` invalidates a fixture by
assigning `cached_result = None` instead of calling `FixtureDef.finish()`. Only `finish()`
empties `_finalizers`, and it early-returns when `cached_result is None` — so nulling the cache
makes the fixture LOOK finished while its finalizers stay queued. They accumulate across the
re-runs one collection serves, until `FixtureDef.execute` trips its own
`assert not self._finalizers` during SETUP. The item then never reaches its CALL phase, the
runner's wrapper finds a failed report with no captured exception and raises `AssertionError`,
and the engine's assertion-vs-crash precedence reads that as "this test's expectation is wrong
on correct code". Measured on Regenesis (2154-green, 2162 items): 2135 tests reported as failing,
2154 on a second pass, the count drifting run to run because it tracks accumulated finalizers
rather than behaviour. Detective renders that list verbatim, so below this floor `audit` accuses
a green suite — silently, plausibly, and at a scale that buries every real finding. Fixed, three
consecutive passes are byte-identical.

>=0.7.0 is REQUIRED, not preferred: `engine.profile` keys its verdict cache on
`Wesker.engine.session_budgets()` — the budgets the live session's baseline is actually built
under. Inside a session the per-call `trace_budget_s` arguments describe nothing (the baseline
is the seam's, and `_build_test_scope` never consults them), so keying on them writes a
tightly-budgeted measurement under the DEFAULTS' key and serves it back to a run that asked for
the defaults. `session_budgets` does not exist before 0.7.0; the import is guarded, so an older
engine does not crash — it silently reverts to keying on numbers that had no bearing on the
answer. A dependency whose absence downgrades correctness in silence is a requirement, not a
preference. 0.7.0 also carries the trace-session-budget default (300s -> 1800s) that stops a
real suite being cut mid-baseline and reporting its own pinned behaviour as unpinned.
>=0.8.0 is REQUIRED, and it is what makes a function that VALIDATES ITS INPUTS analysable at
all — most real code. Below it, pytest's `Failed` (raised when a `pytest.raises(...)` contract
is violated) derives from BaseException, not AssertionError, so the engine classified that kill
as a CRASH. `value_survivor_records` re-lists every non-value kill as unpinned, so a mutant
killed by an error-path test came back a survivor, was re-classified killable off the same
witness, and the residual asked for an input that would rebuild the same test and discard it
again. Not a slow path to a verdict: a loop with no exit, on a mutant being killed the whole
time. Measured on a 5-branch validating function: 5 blockers that no input could ever clear,
`functionally_complete` permanently False, so `decompose` could never prove ANY extraction.
With 0.8.0 the same function proves and applies in one call, no inputs supplied.
The failure is SILENT below the floor — an older engine does not crash, it just re-invents the
loop — so this is a requirement, not a preference. 0.8.0 also adds `wesker --version`, which
did not exist: the engine decides the verdict and keys our cache, and could not state its own
identity.

>= 0.9.3 is a CORRECTNESS floor of the same silent kind: below it, the pytest-discovery
backend's bound parametrize cases all share ONE trace-cache fingerprint (two Wesker-internal
constants), so the per-test trace cache serves whichever case was traced first as the coverage
of every sibling. Downstream that is converge reporting a line gap its own written test provably
covers, and re-issuing the same `--input` forever — a terminal verdict that contradicts disk
state, on any suite with a parametrized golden (i.e., every suite converge itself writes). The
poisoned entry also survives `purge` below 0.9.3, so no documented recovery clears it.

---

>= 0.10.0 is a MUTATION-POLICY floor, the first of its kind here: it does not fix a
defect below it, it CHANGES WHAT THE NUMBERS MEAN. 0.10.0 adds the curated callee-dual
operator family (`SWAP:min~dual` etc. — min↔max, any↔all, math.floor↔math.ceil, with
provenance-resolved eligibility), so a "mutation-complete" verdict computed on 0.10.0
is a claim about a strictly larger behavioral universe than one computed on 0.9.x.
Detective's completeness reports, its DOF counts, and its converge ETA all describe
that universe, and its verdict cache keys on `Wesker.__version__` — so mixing engines
does not corrupt the cache, but it silently changes which specification a COMPLETE
banner certifies. Supporting both floors would mean documenting and testing two
universes whose verdicts genuinely differ; one floor, one meaning.

---

\>= 0.11.0 is a PERFORMANCE floor — the first one here that closes a defect nothing
reports. Below it `discover_test_callables` accepts `source_file` and `func_names` and,
on the pytest backend, uses neither: it collects the whole tree. The legacy path calls
`discover_tests`, which does not select either — its layer 3 appends every remaining test
file unconditionally, so the three layers RANK relevance rather than filter on it.
Profiling ONE function in this repo was handed 49 of 49 test files (549 of 637 callables),
and the ~12x that cannot reach the target were paid for three times over: in collection,
in the traced baseline, and again per mutant. Measured here, that is a `converge` on
`decompose_apply.py::extract_candidate` that produced no verdict in 10 minutes and was
killed; scoped, the same target's discovery takes 0.15s and selects 4 files. Nothing
failed below the floor and no number was wrong — which is exactly why it survived a green
CI and two releases.

It is also a CONTRACT change, hence Wesker's own MINOR bump, and Detective depends on the
new half: for a target no test file names, discovery returns EMPTY rather than the suite,
and converge reads that as "synthesize" — the `synthesized_only` banner and the
characterization note exist only because the empty answer is now reachable. Below 0.11.0
that branch is dead code and `relevant_test_files` does not exist at all, so the import
fails at module load rather than degrading; there is no partial-support path to document.

## Wesker >= 0.11.1

\>= 0.11.1 is a CLAIM-SCOPE floor. It is the first Wesker that publishes
`mutation_policy()` — the versioned mutation-policy manifest whose `policy_id` is
behavior-hashed over the engine's own eligibility (an embedded fingerprint corpus), so
the id moves when the universe's meaning moves, with no one remembering anything.
Detective 0.10.1 consumes it in two load-bearing places: every `ConvergeResult` and
`DecompositionApply` receipt records `policy_id` (a PROVEN decomposition is a claim
parameterized by the policy its proof suite is complete under — issue #14), and
`engine_fingerprint()` appends `+p<policy_id>` so the verdict cache invalidates exactly
the entries a policy change undermines.

Below the floor nothing crashes — `wesker_policy_id()` feature-detects and returns
None, receipts read "policy unversioned", the fingerprint keeps its historical format —
but the release's central claim (receipts that name their universe) is silently absent,
and a cached verdict's policy scope is unknowable after the fact. That is the same
one-fact-two-homes shape every floor above guards: the claim exists only if the engine
that produced it can be named. 0.11.1 also ships policies 2–5 themselves (DATAFLOW's
return_sub slice, the three-spelling and per-target STATE repairs, type-impossible
arithmetic exclusion), so verdicts under it are claims about a strictly more honest
universe than 0.11.0's.

## Wesker >= 0.11.2

\>= 0.11.2 is a PAIRING floor, maintainer-directed, and the ledger is honest about
its shape: the protected behavior is not on Detective's import surface. 0.11.2's
one change is `Wesker.action._stream_reentry` — the badge/self-profile runner
snapshots the real stdout/stderr fds before profiling and re-enters them before
anything report-shaped is written. Below it, a mutant of the fd-capture machinery
(a class the policy-5 universe reliably produces — DATAFLOW return-substitution
inside fd-restore paths) kills fd 1 for the rest of the process, and the action
completes its ENTIRE measurement and then dies at its first `::warning` with
EBADF, taking the report with it. Measured on Wesker's own whole-codebase badge
run, 2026-08-05.

Detective never imports `Wesker.action`, so no Detective verdict changes at any
Wesker in the 0.11.x line — this floor encodes "the pairing we ship and verified"
for repos that run both tools' CI, where the failure genuinely lands. That is a
weaker justification class than every floor above, and the entry says so rather
than dressing it up as one of them.

## Wesker >= 0.12.0

\>= 0.12.0 is the strongest justification class in this ledger: below it Detective does not run at
all. `Detective.cli` imports `Wesker.trace_evidence` — the typed per-TestId line ledger (#17), whose
`trace_admissibility` and `build_trace_ledger` the certificate's admissible view rests on — and
published 0.11.2 has no such module. A wheel resolving `Wesker>=0.11.2` from PyPI installs a Wesker
missing it, and `detective --help` dies on `ModuleNotFoundError: No module named
'Wesker.trace_evidence'` before it parses a single argument. `Wesker.__init__` still called itself
0.11.2 despite carrying the module, so the floor could not name the version that has it until this
release bumped Wesker to 0.12.0.

0.12.0 also carries the covering-tests fresh RE-OBSERVATION (#20): a warm `converge` / `diagnose`
re-observes exactly the target's covering tests this session rather than admitting a cache-replayed
trace, so a certificate stops reporting a false gap on a re-run. Detective reaches it through the
unchanged `run_with_live_suite` seam — not a new import symbol — but a Detective run against a 0.11.x
Wesker gets the OLD warm-run behaviour (the environment-sensitive
`test_verdicts_are_stable_across_repeated_runs`, red on Linux CI). That correctness coupling, not only
the crash, is why the pair must move together.
