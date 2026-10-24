# Evidence flow repair and suite cleanup

Status: executing. Owner-authorized repair pass, 2026-10-23.

Continuation, 2026-10-24: use `REPAIR_HANDOFF_2026-10-24.md` and its issue queue
for the next builder. All earlier worktree changes are now committed and pushed;
Detective's lock is aligned to the pushed Wesker checkpoint. Worktree descriptions
and gate results below retain their historical basis rather than asserting a new run.

## Pass brief

Restore the information contract across Wesker's measurements, Detective's decisions,
and the commands that carry those decisions forward. Then evaluate test consolidation
under `TEST_SUITE_CLEANUP_CONTRACT.md`. There is no deletion quota or assumed speedup.

Authority: the current Negative Specification, Communicating Determinism, and active
Adequacy Completeness theory; repository instructions; Rohan's current directions.
`PROFESSIONAL_CODING_PERFORMANCE_ENGINEERING.md` supplies the engineering process,
not a replacement theory. Existing dirty work in both repositories is preserved.

Protected observations include returned values, declared exceptions, effects,
ordering, diagnostic codes, policy identity, proof provenance, containment, and
certificate standing. Corrective changes intentionally replace the diagnosed wrong
outcomes; this is not a same-answer optimization of those outcomes.

Execution uses each project's managed environment and both local packages on
PYTHONPATH. Baseline receipt `wesker-detective-repair-nlvck5pa` records source copies,
per-file hashes, revisions, dirty state, interpreter, and actual imports. Earlier
full-run receipts remain historical evidence, not newly passing gates.

Real paths: Wesker CLI profiling; Detective help -> regime -> prescribed function
audit/converge; pytest under each project's own environment against the local pair.
Self-dogfood uses a renamed package snapshot. Publishing and version changes are
outside this pass. No push or remote issue closure occurs without applicable gates.

## What warrants computation

For each computation record its input evidence, question, possible named outcomes,
validity conditions, producer, and consumer. Run it because distinguishing those
outcomes can change a declared decision. Reuse an observation only within its
recorded source/policy/domain/regime boundary. A changed boundary requires fresh
evidence; a repeated inconclusive observation is not automatically more knowledge.

Information combines by the problem's specified rules. Examples:

- An observed `int` and an observed `NoneType` jointly exclude an int-only output
  perturbation. Neither a majority vote nor the last type observed can replace the
  universal applicability predicate.
- A complete kill ledger plus an invalid observation does not warrant a certificate.
  The invalidity reaches the gate independently of the favorable kill count.
- Equal counts under different mutation policies do not establish the same result.
  A next command must retain the policy whose residual it promises to address.
- A test redundant for one function remains needed if it is the retained witness of
  another affected obligation. Unknown impact retains the witness.

These are bounded decisions over typed evidence. No entropy, mutual-information
value, independence assumption, or semantic equivalence is inferred from test counts.
Intent remains authored. The finite experiment's distinctions and uncertainty are
propagated explicitly instead of being converted into guessed meaning.

## Ownership and flow

| Owner | Input | Produced fact | Consumer and warranted action |
| --- | --- | --- | --- |
| Wesker monitoring | subscription, code, thread, live run | owned observation or named observation failure | coverage/capture/control boundary accepts qualified evidence or marks it unavailable |
| Execution boundary | callable, independent arguments, budget | outcome, timeout, containment, refusal | classifier and validity gate distinguish value evidence from failed measurement |
| Codomain harvest | admitted test pool and owned return events | all observed types plus harvest standing | output-policy generation admits only applicable operators; validity stays attached |
| Decision derivation | qualified function basis and residual | named remedy and policy-bearing argv | CLI text/JSON render the same next action |
| Removal assessment | candidate identities and affected obligations | retained witnesses, verified redundancy, or unresolved impact | exact staged batch is accepted only on the preservation predicate |

Wesker owns interpreter instrumentation; Detective consumes that service. Do not
introduce a second monitoring owner or a framework merely to draw this graph.
Use references to verify the implemented graph and real runs to verify execution.

## Communication preservation

`docs/theory/COMMUNICATING_DETERMINISM.md` was reread in full during this pass.
Its criterion is stronger than literal truth: the encoding must preserve distinctions
between epistemic states whose remedies differ (§3). A reader must not be led from a
true number to an invented cause or an unsupported next action. This applies to the
cleanup itself as well as to the tool being repaired.

Review each retained obligation across three layers: qualified observation, warranted
conclusion, and emitted sign/action. Every decision needs a consumer; every consumer
must distinguish its codes or explicitly name and justify a deliberate collapse.
Reflection-based serialization is not evidence that a decision is consumed (§3.2, §11).

- Unavailable capability, incomplete observation, unresolved survivor, and an observed
  gap are different states. Preserve the cause through human output, JSON, certificates
  and the invocation ledger wherever each channel applies. Do not emit a certificate or
  completed verdict under a warning when its required observation was refused.
- A next command asserts that a particular future invocation can change what is known
  (§5). Missing measurements do not by themselves warrant authoring tests, supplying
  inputs, flagging equivalence, or repeating the same command. A named refusal can be
  the complete product of a run, with no next action established (§4).
- Zero contribution from an advisory lens is not opposition. Unmeasured and measured-
  clean inputs remain distinguishable; no quality scalar replaces the specified
  independent-lens concurrence (§7).
- Bound-relative step exceedance does not prove infinite execution. A finite-policy
  completeness result does not establish program intent or completeness outside that
  policy/domain/regime. Favorable counts cannot supply these missing warrants.
- Rare refusal branches are part of the communication alphabet (§4), not deletion
  candidates merely because ordinary runs seldom use them. A test-removal receipt must
  retain their distinct obligations and the consumers that carry them to the reader.
- The CLI's theorem-like rendering and the historical model-facing surface's behavioral
  prompt answer to different criteria (§6). Preserve documented anti-affordances and
  deliberate prompt prohibitions; do not transfer that license to CLI claims or quietly
  soften it during consolidation. The paper does not claim mechanized sentence
  correctness or a proven complete epistemic state space (§11).

## Ordered repair tracks

| Track | Question and existing evidence | Mechanism and consumers | Acceptance and stop condition |
| --- | --- | --- | --- |
| R1 monitoring liveness | Can broker activity observe itself without a lock cycle? Bounded self-observation deadlocks; full suites previously stalled. | Repair re-entrancy/ownership at the broker; coverage and every harvest depend on it. | Owning-thread interruption, self-observation, both cleanup orders, setup/cancellation paths and full pair gates complete. A passing focused case does not explain an unrelated full-run stall. |
| R2 observation standing | Can failed or retired observation be mistaken for complete evidence? A retired token still received a queued callback; observer errors were swallowed. | Preserve admission and failure state through subscription handles and every observation consumer. | No new observation starts after retirement; affected faults reach validity without becoming target crashes; completed evidence is stable. Explicitly account for already-running observers. |
| R3 capture and applicability | Can the observed codomain support the generated operators? `None` is omitted; uncontained return capture produces an unqualified set. | One qualified harvest result, owned run lifetimes, all observed types, deadline and containment propagation; remove duplicate harvest decisions. | Mixed returns exclude inapplicable operators; cut/uncontained/unavailable observations remain named through the final gate; late worker calls cannot become another test's evidence. Resolve obsolete profiler expectations without weakening consumer guards. |
| R4 policy continuity | Does the next invocation answer the preceding question? Recorded two-sign audit 12/12 -> prescribed one-sign converge 8/8. | Share command construction from the policy-bearing decision record across renderers and handlers. | Real prescribed walks retain policy through rerun, flag and preservation commands; final output and certificates identify the measured policy. |
| R5 alternate execution paths | Do reach probes preserve supplied inputs and hook ownership? Reaching a line mutates a caller's list; two legacy tracing sites remain. | Reuse independent-input and bounded-execution boundaries; move remaining observation onto the broker. | Uncopyable inputs refuse explicitly; timeouts/containment survive; foreign hooks remain intact; existing reach and outcome obligations remain guarded. |
| R6 removal preservation | Do all affected checks use the same policy and preserve the required closure? Other-function profiles default to one sign; post-edit recheck covers only the target. | Carry policy, exact identities and qualified impact through preflight and fresh staged verification. | Preserve the two-sign witness and relevant kappa-closure; unknown impact retains tests; exact-batch verification and recovery satisfy the cleanup contract. Local kill/line equality is supporting evidence, not the closure theorem. |
| R7 reference integrity | Can explicitly unverified evidence become truthy? Inline comments suppress a false verification flag; five local hashes drift. | Strict manifest scalar/schema handling; review changed claims separately from hashing. | Plain/commented false behave identically; malformed or missing verification is explicit; no automatic rehash to silence drift. |
| R8 measured cleanup | Which executions add no required distinction? No safe deletion quantity has been established. | Advisory collection/cost census, then one function-level removal pilot and verified batches. | Exact removed IDs, retained obligations, fresh collection, both suites, honest residuals, and separate resource measurements. If evidence is invalid, repair its producer rather than delete the exposing test. |

## Opportunity cards and resource claims

R1-R7 are correctness repairs. Their reproductions establish defects, not speedups.
R1's mechanism is eliminating a lock cycle; R2/R3 represent qualified evidence once;
R4 shares command derivation; R5 shares safe execution; R6 narrows deletion to proven
impact; R7 preserves Boolean meaning. Cost is UNMEASURED until an applicable paired
experiment exists. Run only the instrument needed to resolve the remaining question.

W#40/W#42 scanning/allocation reductions require separate production attribution and
paired measurements after correctness stabilizes. W#41's precomputed original key is
a separate implementation. W#25 empirical grouping remains presentation-only;
proof-grade static subsumption is separate work. The remaining mu-minus family work
needs explicit generator/consumer/policy acceptance and cannot be declared complete
because `--two-sign` exists. These items do not disappear into suite cleanup.

## Verification and durable state

For each track: reproduce before editing; inspect current definitions and references;
pin a genuine literal-typed decision where there is one; wire its consumers; preserve
or extend the existing intent obligations; run focused tests and real entry points.
Add tests for missing distinctions, rather than creating another parallel suite of
implementation-mirroring assertions. Impure ownership/containment gets boundary tests.

After a Wesker change, acceptance requires both full suites against local Wesker.
Use pinned Ruff 0.16.7 and the whole-tree format check. Run the prescribed type read
as an advisory and retain its actual limitations. All long runs write complete logs;
read them in full. External deadlines classify an unfinished check as invalid.

Keep commands, complete outputs, source identities and test results in the local
receipt directory. Update this plan with track outcomes and remaining work. Do not
label a track accepted from a unit test alone or infer that the full issue acceptance
has been met from one repaired subcase. Commits, pushes, issue closures, and releases
retain their separate repository gates.

## Execution record

- Baseline captured; both imports resolve locally under managed CPython 3.14.7.
- R1: the new self-observation intent failed before editing. A re-entrant lock
  repaired that case but the combined run still stalled; its Python stack showed
  a remaining thread blocked on the token lock after the worker exited. Replaced
  token locking with CPython built-in integer-token operations. The same combined
  workload then passed (receipt `r1-focused-lockfree`); the full Wesker run at that
  R1 source basis passed 1,054 tests (`r1-wesker-full`). Later edits need fresh gates.
- R2: retirement-during-delivery and silent-observer-failure tests failed before
  repair. Subscription state now owns observer failures and in-flight delivery;
  owner-boundary checks refuse that evidence. Coverage and the isolated baseline
  consume the checks; capture consumes them through its shared execution boundary.
  Focused receipt `r2-focused` passed. Full cancellation/coexistence acceptance is
  still pending; W#32 is not declared closed.
- R3: per-test tokens/subscriptions and worker-object ownership replace a growing
  ident set. Successful codomain results include NoneType; incomplete codomain
  observation raises HarvestIncomplete with partial diagnostic evidence. The
  primary and fallback paths share their allowance, restore seeded state on
  failure, and the CLI distinguishes invalid measurement (3) from unavailable
  monitoring capability (2). The cache keys two-sign rows on the observation
  contract so older incomplete type evidence cannot survive this repair.
  Receipts `r3-capture` and `r3-standing` passed their focused scopes. The first
  integration run exposed one outdated exact cache-key expectation, now migrated;
  it still needs rerun and the full pair gates.
- Capture semantic migration retains the no-hook-theft obligation. The two
  `test_*_declines_an_unrestorable_hook` IDs in test_capture_foreign_profiler_intent
  become the corresponding `test_*_coexists_with_an_unrestorable_hook` IDs. No test
  was deleted. Ghost consumer records were removed; the current harvest decision
  is wired, and the exported legacy profile decision has an explicit compatibility
  reason instead of being presented as a production capture pin.
- R2 follow-through: worker ownership is filtered before frame materialization;
  the CPython thread registry bridge avoids creating DummyThreads while observing
  threading bootstrap/teardown. The aggregate trace allowance now also bounds
  the current test. A later full gate exposed a cancellation window between an
  observer's in-flight reservation and its cleanup block. A deterministic
  interrupt-at-admission test failed before repair; reservation now occurs inside
  the try/finally. The affected monitoring/trace-budget/containment scope passed
  35 tests afterward (`r2-admission-after`). Fresh full gates are still required.
- R4: terminal, JSON and archived converge commands now carry the two-sign policy,
  including the decomposition proof report and OUTPUT survivor flagging. A real
  empty-string target exposed the archive-only omission; its bad command could
  not find the OUTPUT survivor. The corrected converge -> flag -> audit walk
  completed under the same policy. Receiver/environment/clock continuity still
  needs its complete acceptance matrix. The walk also exposed a separate DOF
  accounting defect: 5 value kills divided by a reported universe of 2 (250%).
  Do not repair that by clamping a percentage; trace the policy/count producers.
- R5: RIP reach and audit reach consume owned monitoring and bounded execution;
  independent argument copies retain aliases. Unknown candidate reach no longer
  spends profiles that cannot authorize removal. Witness `_outcome` now uses
  JoinedWorker and preserves containment, monitoring faults, and refusal records.
  All three new outcome cases failed before repair; the related focused scope
  passed 73 tests afterward. Live-value and receiver-state rendering helpers
  still execute another call directly; audit those before accepting this track.
- R5 consumer follow-through: final converge classification, required isolated
  verification, audit classification and rewrite classification swallowed named
  monitoring failures as ordinary advisory exceptions. Six reproduced consumer
  cases failed before repair. These failures now reach the existing CLI boundary:
  capability unavailable -> REFUSED / 2; failed observation -> INVALID_MEASUREMENT
  / 3, retaining its cause. The focused library/human/JSON and rewrite scope passed
  45 tests (`r5-proof-consumers-cli`), including the ordinary rewrite-advisory
  fallback. No input, equivalence or completion prescription is emitted on these
  refusal paths. This is one preservation edge, not acceptance of every R5 path.
- R6 policy preflight: `module_safe_removals`, `_consult_reach` and `_audit_remove`
  now forward the selected two-sign mode into sibling, neighboring-function and
  observed-reach profiles. Nine failing cases preceded the repair; the affected
  focused scope passed 66 tests. The subsequent Detective suite passed 3,796 tests
  at that recorded source basis (`detective-r6-suite`), before the later R5
  consumer edits. Kappa-weighted closure, fresh affected post-edit verification
  and reversible exact-batch application remain open; no deletion is authorized
  by policy propagation alone.
- R7: the reference checker now parses Boolean evidence flags with inline
  comments as Booleans, rejects malformed/missing flags and missing sections,
  and reports a named malformed-manifest exit. The real checker still reports
  five local prior hash drifts and eleven load-bearing unverified citations.
  No prior hash or citation verification flag was changed. Claim-by-claim drift
  review remains open; the parser repair is not that review.
- R6/R8: no broad test-pruning wave is accepted. Restored 27 earlier deleted test
  definitions because no preservation receipt accompanied their deletion. Kept
  semantic migrations for owned monitoring, annotation exclusion and aggregate
  deadlines, with the obligations mapped in `REPAIR_REVIEW_LEDGER_2026-10-23.md`.
  Removed three unused legacy coverage helpers only after checking references;
  migrated their remaining test to the production monitoring boundary.
- Push gates: pinned Ruff, lockfile audits, workflow security, secret scanning and
  pylint have been executed; retain their actual findings, not just exit codes.
  The missing local Sonar service was recovered against a backup copy of its
  persistent data. Installed server 26.10 reports DB_MIGRATION_NEEDED and refuses
  the embedded-database upgrade. No current Sonar gate exists; pushing is held.
  The original data volume remains separate from the recovery copy.

## Checkpoint gate record

`REPAIR_CHECKPOINT_RESULTS_2026-10-23.json` records command outcomes and source
manifest identities for the fresh pair run. Both managed-environment suites passed,
including Detective under pytest-cov. The source/test manifest comparison was
unchanged after those runs. Pinned Ruff check and whole-tree format passed in both
repositories. Ty reports warnings (two Wesker, seven Detective), with no errors;
pylint reports residue and is not claimed clean. The Sonar push gate remains
unavailable because the installed server cannot upgrade the recovered embedded
database. No issue or broader track is marked complete from these gates.

The renamed WeskerUUT pin for `measurement_entry_disposition` reached two-sign
COMPLETE with 10/10 mutants killed and fresh isolated reproducibility confirmed.
Its two generated value cases were read; the original handwritten intent cases
remain the independent requirements. This is one decision's pin, not a proof of
the monitoring lifecycle or a suite-removal preservation receipt.

The later R5 consumer checkpoint is separate:
`REPAIR_CHECKPOINT_RESULTS_2026-10-23_R5.json` binds its logs and source manifest.
Detective passed 3,827 tests, with four skips and one expected failure, against local
Wesker under pytest-cov. The package/test sources remained unchanged during the run
and at checkpoint creation. Ruff check and whole-tree format passed; ty reported
seven warnings and no errors. These results cover the recorded dirty working tree,
not a claim that its source changes are already in a commit. Generated-banner
characterization review and the remaining direct re-execution paths are still open.
