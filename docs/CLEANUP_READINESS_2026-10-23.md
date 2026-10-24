# Cleanup readiness observation — 2026-10-23

Historical pre-repair observation. Later repairs and fresh gates are recorded in
[the execution plan](EVIDENCE_FLOW_REPAIR_PLAN.md) and
[the review ledger](REPAIR_REVIEW_LEDGER_2026-10-23.md); the failures below identify
the original evidence basis, not the state after those repairs.

Generated from run receipts on 2026-10-23 local time (2026-10-24 UTC). This is a dated
observation of the source bases below, not a continuing health badge. Re-run after relevant changes.

**Decision: BLOCKED for test deletion.** The shared [cleanup contract](TEST_SUITE_CLEANUP_CONTRACT.md)
is saved. No live test or production source was changed by this pass. Existing dirty work was preserved.

## Measured environment and source basis

Both project environments ran CPython 3.14.7 on macOS 27 arm64. Both imported the LOCAL
Detective and Wesker trees. Installed pytest was 9.1.1; the only installed pytest entry-point
plugin was the declared pytest-cov 7.1.0. Installed Ruff was 0.16.7, and the checks used
`uvx ruff@0.16.7`. Environment receipts retain the exact executables and import locations.

The revisions alone do not identify these dirty trees. The source/test/config digests below
cover each package, tests, scripts and applicable project/lock/interpreter configuration.

| Repository | HEAD | Source/test/config manifest SHA-256 |
| --- | --- | --- |
| Wesker | `9e5023c245b0fe6a55a2bafbff19c6b7f445ed80` | `baa927c89145b1fbafa073e187129c038cc31d5c569b597913fa7eee51be4c1f` |
| Detective | `9c1276b1f5965ce0bfaf4e6e07851d8ca23b04d9` | `dbecced796b5aaa344bcdc299a86bf1d293d569bc999326cf6d35081383ffd06` |

Before/after comparisons found no production, test, script or configuration changes. The only
change to a file already in the initial manifest was a wording adjustment to the new cleanup
contract. This readiness document was added after measurement. Complete per-file manifests,
working-tree status and verified source copies are in the receipts.

## Run results

Process elapsed times below are single observations, not comparative performance claims.

| Run | Result | Process elapsed |
| --- | --- | --- |
| `wesker` | Ordinary full Wesker: 1,053 collected; unfinished; external 180 s budget exceeded; terminated | 191.296 s |
| `wesker-diagnostic` | Full Wesker with 15 s faulthandler diagnostics: unfinished; external 90 s budget exceeded; terminated | 101.403 s |
| `detective-pytest` | Full Detective: 3,734 passed, 4 failed, 4 skipped, 1 xfailed; 3,743 collected | 205.201 s |
| `wesker-focused` | Focused Wesker trace-budget + containment modules: 19/19 passed | 16.043 s |
| `detective-v2-audit` | Corrected renamed snapshot, two-sign removal_gate audit: complete, 12/12 value-pinned | 9.320 s |
| `detective-v2-converge` | Exactly prescribed default converge in snapshot: COMPLETE, 8/8 killed; two-sign mode lost | 23.977 s |

Budget-exceeded elapsed times include stack sampling and shutdown grace. These are interrupted
measurements, not completed suites. All launched test/audit command PIDs were absent when checked
after the runs. The plain suite runs added duration and JUnit reporting; the diagnostic runs
additionally enabled the declared faulthandler timeout. They did not enable coverage tracing.

| Quality gate | Child exit |
| --- | --- |
| `wesker-ruff-check` | 0 |
| `wesker-ruff-format` | 0 |
| `detective-ruff-check` | 0 |
| `detective-ruff-format` | 0 |

Checks were package/tests lint plus whole-tree `format --check .`. These passing gates do not
establish issue acceptance, deletion safety or a performance win.

## R1 — Wesker monitoring lifecycle is not ready

Observed with high confidence: the ordinary full run stopped making progress in
`tests/test_trace_budget.py`, after seven tests in that module. A native stack sample showed
the main thread and a worker waiting on lock acquisition inside monitoring callbacks.

The diagnostic full run passed that module and stalled in
`test_trace_containment.py::test_a_cut_worker_that_stops_is_reported_contained`.
Its complete Python stack dump identifies:

- Main thread: `monitoring._dispatch_py_start` line 310, reached through
  `threading.Thread.is_alive`, `interrupt.abandon`, `bounded_join`, and `_trace_one_multi`.
- Worker: `monitoring.is_run_token_active` line 124, reached through
  `_dispatch_py_start` during `threading.Thread._delete`.

The current definitions put the subscription RLock at the first site and the run-token Lock
at the second. The exact lock owner, acquisition history and cancellation window are unresolved.
A single-root-cause claim is not established by these stacks. The fresh focused run passing
19 tests does not repair or explain the two full-run stalls.

Next repair: establish cancellation-safe monitoring dispatch, registration and teardown,
with adversarial ownership evidence; then repeat both full suites. Preserve the tests that
expose the lifecycle problem. This pass made no engine repair.

## R2 — Detective has four concrete suite failures

The complete suite failure list is:

1. `test_capture_foreign_profiler_intent.py::test_the_input_harvest_declines_an_unrestorable_hook`.
2. `test_capture_foreign_profiler_intent.py::test_the_return_type_harvest_declines_an_unrestorable_hook`.
3. `test_consumer_distinction_intent.py::test_no_registry_entry_names_a_site_that_no_longer_exists`.
4. `test_pinned_decision_consumption_intent.py::test_every_pinned_decision_is_consumed_or_carries_a_reason`.

The first two require the previous legacy-profiler refusal. The current monitoring capture
continues harvesting and returns `(1,)` / the `int` codomain instead. The accepted W#32 design
calls for coexistence with the foreign legacy slot. My reading: these expectations need an
explicit semantic migration that retains the no-hook-theft/coexistence obligation; merely
deleting failing tests would not discharge it.

The registry guard reports three ghost consumer sites: `capture.harvest_disposition` at
`capture.capture_call_inputs`, and `capture.profile_hook_disposition` at both harvests.
The pinned-decision guard reports the same two helpers have no production consumer.
Fresh symbolic references confirm calls from tests and no production call sites. The capture
loop now repeats the enough/deadline branches inline; the old profile-hook helper is exported
and described as retained for interface stability. Its compatibility standing needs an explicit
decision. Restore meaningful production use or document deliberate compatibility/retirement;
do not weaken the guards or add fictitious consumer records.

The four skips include two decomposition cases with no applied seam/helper, an unobservable
warm-cache comparison, and the sdist check without a built artifact. The expected xfail is the
existing receipt-ordering question. These are not passed checks of those missing paths.

## R3 — The real CLI handoff loses the two-sign basis

The fresh snapshot used a mechanical `Detective` -> `DetectiveUUT` namespace transformation,
kept the real tests and support files, excluded the root conftest and live ignored stores,
and used Detective's environment with local engine imports. Help and regime were read in full.

The actual commands in the corrected walk were:

```text
detective --help
detective regime
detective audit DetectiveUUT/audit.py::removal_gate --two-sign
```

The audit reported one intent-grounded routed test, `12/12 value-pinned`, and `complete`.
It prescribed:

```text
DO THIS:  detective converge 'DetectiveUUT/audit.py::removal_gate'
```

Following it exactly in the disposable copy produced `8/8 killed` and `COMPLETE`.
The mode flag disappeared and the measured universe decreased from 12 to 8. The subject source
did not change; the only changed pre-existing snapshot file was its certificates JSON.
This result is not preservation evidence for the preceding two-sign basis. Repair command
continuity and verify mode/universe identity through the next command and its certificate.
No destructive removal command was run. This probe exercised a function proof path, not the
full cleanup transaction or all contract acceptance cases.

The first snapshot attempt correctly reported `INCOMPLETE` despite 12/12 value pins because
I omitted `scripts/check_sdist.py`. A direct collection run confirmed FileNotFoundError.
That setup mistake was corrected by copying the declared working-tree files into a NEW
snapshot and restarting help -> regime -> audit. Both histories are retained; the invalid
first attempt is not accepted as a successful audit.

## R4 — Existing removal code provides a narrower contract

These are current code-inspection findings, not completed adversarial verification:

- `audit._removal_needs` (line 624) derives need from kill and line evidence. It does not
  independently establish arc, authored-intent or integration adequacy.
- `audit.module_safe_removals` (line 869) consults siblings, neighbors and bounded observed
  reach. The sibling path does not explicitly force candidate inclusion as the neighbor path
  does. Candidate admission and unresolved/opaque impact still need explicit evidence.
- `cli._audit_remove` (line 8097) applies edits and then re-audits only the target in the same
  process. It does not restore the edit on an invalid/failed recheck or supply a fresh
  all-affected-functions post-edit transaction.
- `suite_edit.apply_removals` (line 360) writes each file atomically. It has no outer
  multi-file/source/certificate acceptance and rollback transaction. Parameter rows correctly
  remain report-only.

A valid `gap` can still support preservation cleanup under the shared contract. The missing
additional checks must be supplied by a controlled surrounding transaction or implemented
before accepting deletion. The current flags alone do not establish the stronger contract.

## R5 — Monitoring consolidation still has open boundaries

Current whole-definition reads also show:

- `audit.candidate_reach` still installs `threading.setprofile_all_threads` and restores only
  the current thread's previous profile slot after clearing the all-thread hook.
- `equivalence._reached_lines` still installs and clears a legacy `sys.settrace` hook.
- `capture_return_types` discards `_run_for_effects`' containment result and returns only a
  frozenset. `_consulted_codomain` forwards that set with an empty routing-error string after
  successful routing. Containment is not carried along that return path.
- Monitoring observation dispatchers catch observer exceptions without recording a measurement
  failure. Run-token admission is checked when forming the delivery list, without a later
  admission check immediately before each observer invocation.

These are evidence/ownership gaps to resolve, not reproduced claims that every affected report
is wrong. This was not a complete re-audit of every legacy hook or the entire open-issue list.
W#32 cannot be accepted as complete on the strength of the focused passing tests.

## Next execution order

1. Repair and pin the monitoring cancellation/lock lifecycle independently of test deletion.
2. Finish the capture semantic migration and resolve the orphan/ghost decision records while
   retaining their distinct obligations. Preserve containment through both capture paths.
3. Repair two-sign command continuity; replay the full prescribed walk and compare the basis.
4. Obtain stable complete local pair gates, then implement or demonstrate the additional
   freshness, impact, arc/intent and rollback checks for one controlled deletion pilot.
5. Only then accept small exact batches, with the ledger and verification required by the
   shared contract. Revisit the broader roadmap separately.

Behavior assessment: `UNRESOLVED`; the interrupted full Wesker measurements are
`INVALID_MEASUREMENT`. Resource assessment: `INADMISSIBLE` for improvement claims because no
paired benchmark experiment was performed. No quantity of safe deletion has been established.

## Evidence and limits

Local receipt ID: `wesker-detective-acceptance.wyx7m205`.
Persistent local archive ID: `cleanup-readiness-2026-10-23-wyx7m205/receipts.tar.gz`.
Archive SHA-256: `74522aa2ccf76d8ba59edcb68b7a4871164950403b1afec37a94da841e390bb5`.

The session delivery links the local archive/index. It contains raw complete logs, commands,
child exit codes, source manifests/copies, JUnit, stacks and both self-audit walks. The command
capture helper's own exit does not represent the child verdict; use the recorded `exit_code`
and full child output. Only the two-sign/default counts quoted above were transcribed from
complete CLI pages; suite counts and run tables were computed from JUnit/run records.

Not run: the supported multi-Python/multi-OS matrix, CI coverage coexistence, packaging/release
checks or pre-push Sonar/pylint gates. No publish, release, issue closure or deletion is implied.
No purge/reset command was run against live stores. Ignored live runtime state was not fully
fingerprinted; this is a readiness observation, not a deletion proof. No live code or test
edits were made.
