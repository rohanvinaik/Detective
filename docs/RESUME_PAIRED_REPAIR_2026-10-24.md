# Resume Wesker / Detective

This is the restart entry point after the paired 1.2.2 publication. It records an
observed checkpoint, not a standing claim about a future worktree. Recompute source,
lock, issues and runtime state before acting. The shared execution checklist is
[OpenSpec tasks](../openspec/changes/complete-paired-repair/tasks.md); the complete
[issue queue](REPAIR_QUEUE_2026-10-24.json) retains its classifications and dependency
edges. The [original handoff](REPAIR_HANDOFF_2026-10-24.md) supplies detailed obligations;
its original checkpoint/future-tense implementation paragraphs are historical.

## Published baseline

| Item | Observed basis |
| --- | --- |
| Wesker 1.2.2 source/tag | `60df89b86f4b35a8df2b03c850ebdb988d0e99af` |
| Detective 1.2.2 source/tag | `bf3f87b01bfe30246feb1a103de34463b5f5e32b` |
| Detective development lock | Exact Wesker source above |
| Detective wheel dependency | Plain `wesker>=1.2.2`, Python>=3.12 |
| GitHub release state | Both published; exact-commit CI prerequisite, build and signing passed |
| PyPI state | Both 1.2.2 packages observed on the ordinary index; all four distribution hashes match the signed GitHub assets |
| Ordinary-index acceptance | Fresh managed Python 3.14.7 environment; imports from site-packages without PYTHONPATH; help → clean regime → converge on the shipping fixture reached COMPLETE, 17/17 killed, three tests, isolated reproducibility confirmed |

Exact CI: [Wesker 40077116370](https://github.com/rohanvinaik/Wesker/actions/runs/40077116370),
[Detective 40077952748](https://github.com/rohanvinaik/Detective/actions/runs/40077952748).
Both six-cell Python 3.12/3.13/3.14 Linux/macOS matrices completed successfully
before release creation. CodeQL and SonarCloud checks passed. These results do not
clear every historical quality finding or the separate full self-specification job.

Build/sign: [Wesker 40078380799](https://github.com/rohanvinaik/Wesker/actions/runs/40078380799),
[Detective 40078385460](https://github.com/rohanvinaik/Detective/actions/runs/40078385460).
The [release receipt](RELEASE_1_2_2.md) records the change and artifact identities.
The earlier 1.2.1 clearance was premature; its tag/assets remain unchanged and its
release notes disclose the exact-tag deadline failure. Do not upload 1.2.2 again.

The last local coverage runs on this runtime basis passed 1,079 Wesker tests and
3,872 Detective tests (three skipped, one expected failure). Those are dated receipts,
not a substitute for running the next change's relevant acceptance. The shipping
fixture is characterization, not review of its intended behavior.

## Worktree to preserve

At this checkpoint Wesker is clean. Detective has one pre-existing unstaged edit:
`tests/detective/certificates.json`, SHA256
`f485a94f52b950dbdb13c1ec8d98c04acd51ce7cad832ac5d9c289868f302c60`.
It adds an incomplete status-function record. Preserve and review it under B00;
do not stage it with documentation or promote it to a fresh certificate.

Keep the nine status characterization tests. The wrapper's generated certificate
does not establish their redundancy or certify the status function. No broad purge
has been accepted. Earlier restored tests and rare semantic/refusal witnesses stay.

## Restart procedure

1. Read both AGENTS files and this entry point. Compute git status, HEAD/tag identities,
   Detective's locked Wesker revision, and actual import resolution. Preserve in-flight
   work; never treat this checkpoint as permission to reset a later worktree.
2. Refresh open issue bodies and compare their IDs with the queue. At this snapshot
   there are 26 Wesker and 63 Detective issues: 75 repair, three mixed, three tracking,
   eight deferred-addition records. Every issue has a mapping. An open issue is not
   evidence that its implementation is absent.
3. Choose a bounded unchecked obligation from OpenSpec in dependency order. Read
   its complete current definitions, theory and callers; reproduce it before editing.
   If already repaired, perform missing acceptance instead of rebuilding it.
4. Record the admissible basis, producer, consumers, named outcomes and authority for
   the exact change. Intent tests protect impure boundaries; generated characterization
   alone cannot establish intended behavior.
5. Trace facts through engine, loop, aggregation, validity, action selection, human
   report, JSON and durable evidence as applicable. Different remedies retain distinct
   outcomes. Unknown is neither false nor equivalent.
6. Record behavior, measurement validity and resource results separately. Run the
   relevant real-entry-point acceptance. Update the task, queue and issue receipt
   together. Do not close an umbrella from a green suite or claim a speedup from timing
   one incidental run.
7. Every accepted Wesker push requires Detective's exact lock refresh and sync.
   A future publication again requires exact-candidate CI, coordinated artifacts and
   Wesker-first dependency order. No next release/version is authorized by this document.

## Remaining work, with stopping conditions

| Package | Work still to establish |
| --- | --- |
| B00 | Review generated suites/certificates against current source/policy/provenance; retain the status cases; reproduce the original integrated public-command cases. |
| B01 | Complete all seven instrumentation-site ownership/coexistence schedules, inflight retirement, child/thread-ID behavior, observer-failure propagation, original-measured step-cap warrants and W#29's self-measurement under an unmutated containing parent. Broker migration and the cold instruction correction are already present. |
| B02 | Finish explicit existing-test filesystem authority (D#105), original D#108/#127 CLI/RSS/input reproductions, slow copy/repr/render/cancel acceptance and nonfinite generated assertions. Entry snapshots, same-invocation payloads and bounded rendering/property phases are already built. 1.2.2 adds ten deadline/startup regressions; these do not accept the entire package. |
| B03 | Verify actual module/mutant/TestId identity across difficult import/closure/descriptor topologies, cold helper routing, baseline admission and fresh recollection after edits. |
| B04 | Establish one source/codomain/policy/context basis and distinct mutant/value/DOF units on every path, including one-/two-sign and warm/cold variants. |
| B05 | Close remaining CLI cause/action/field-consumption gaps; establish human/report/JSON/ledger/certificate agreement, usable round-trip prescriptions and honest absent/unknown evidence. |
| B06 | Derive the exact already-declared μ⁻ catalog from theory, match applicability/observations/generation/consumption/witnesses, and name unsupported premises. Do not fill an operator quota or delete tests through an operator blind spot. |
| B07 | Accept the approved durable-store transactions/migration/history, context-qualified cache siblings and filesystem-safe subprocess overlay trials with exact recovery. |
| B08 | Accept exact authorized test edits against every affected obligation in a fresh process, including joint final-witness checks, intervening edits and atomic source/certificate/index recovery. Missing required premises mean retain. |
| B09 | Attribute real redundant work and measure same-answer savings; preserve same-size rebinding and module replacement. Keep W#41 separate from unestablished W#40/#42 savings; empirical grouping never prunes proof. |
| B10 | Establish portable plain-descriptor spawn scheduling and budgets after prerequisites; prove serial/spawn evidence agreement. Accept xdist/order behavior separately. |
| B11 | Inventory obligations and cost, then run one disposable-copy cleanup pilot after B08. Map every removal to retained witnesses and verify the joint result. No deletion percentage or test-count target. |
| B12 | Triage historical quality/supply-chain/bootstrap/reference gaps, repair local Sonar without resetting its database, and calibrate production-derived performance/memory advisories. Publication alone does not accept these. |

The next bounded work is B00 artifact/certificate review and the remaining B01
ownership acceptance, then B02's existing-test filesystem boundary. Independent
census and evidence collection may proceed; deletion and weaker proof claims may not.

## Owner premises and deferred additions

Do not invent: the code-kappa graph/domain basis; the broad-handler narrowing target;
missing structural/effect observation premises; unmeasured step-cap parameters; or
a weaker definition of fresh reproducibility. Record the exact missing premise and
continue independent work.

Type (2) stays scoped in D#72/#73/#74/#90/#97/#109, the search expansion in #110,
#135/#136 and proof-grade static subsumption in W#25. Mixed issues retain their
existing repair portions. An assessment of another construction system is not
authorization to replace these projects' theory or implement a new capability.

**Proposal supplement, 2026-10-24:**
[Detective#137](https://github.com/rohanvinaik/Detective/issues/137) and the separate
[construction-contract proposal](../openspec/changes/declare-construction-contracts/README.md)
record an optional function contract and Wesker-owned catalog interchange. This is
deferred Type (2), requested as a write-up; implementation remains unapproved. It
does not add a prerequisite to the current repairs or publication. The issue queue
now includes this additional proposal; the 89-issue counts above describe the earlier
pause snapshot, whose records and hashes remain intact.

## Discoveries that this inventory cannot pre-enumerate

This packet covers the known queue, not all possible future defects. For a new finding,
record its whole source/contract unit, supported input and execution context, observed
outcome, required outcome and theory warrant, affected producer/consumers, reproduction,
scope class, package/dependencies, acceptance and recovery. A missing observation stays
unknown. A new promise gets a deferred issue; an existing contract violation gets a
repair row. Preserve the original evidence and keep unsupported proposals separate
from implemented or accepted work.

## Durable local evidence

Current public-issue snapshots and the ordinary-index smoke logs/report are under
`~/Library/Logs/Detective/pause-2026-10-24/`; snapshot hashes are in the queue.
Earlier repair raw evidence remains at the paths in the original handoff.
Stable public source/CI/release links identify the release basis. Local paths are
receipt locations, not files to copy blindly into a public repository.
