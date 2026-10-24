# Wesker / Detective mechanical repair handoff

Owner-directed scope, 2026-10-24. Read this before starting another implementation wave.

## Mandate and starting state

Finish **Type (1): make the projects correctly perform their existing, specified jobs**.
This includes missing implementations of already-declared contracts, integration,
same-answer performance work and evidence-preserving cleanup. Adding code is not
automatically adding scope. **Type (2): broader capability or a new promise** stays
in its GitHub issue for a later owner-directed build.

The code checkpoint is Wesker `5169b9b` and Detective `09aa3a4`. Detective `bd4efa6`
then pins its development lock to Wesker's exact pushed commit
`5169b9b0f910dccb64b5037bd474b921e8639039`. `tool.uv.sources` still names Wesker's
main branch; the lock selects that exact revision. No release version was changed.
Documentation commits can follow these code checkpoints.

All pre-existing modified/untracked source, tests and certificate artifacts were
committed and pushed at the owner's request. Both worktrees were clean immediately
after those pushes. **Committed does not mean every issue is accepted.** The generated
artifacts were checkpointed with their outstanding review recorded, not promoted to
newly verified proof.

Historical receipts: the last recorded Wesker wave passed 1,069 tests; the later
Detective R5 wave passed 3,827, with four skips and one expected failure, against
local Wesker. The source manifests and complete logs, not these counts, identify
their basis. No tests or quality gates were rerun for the 2026-10-24 pushes: the
owner explicitly said to commit and push everything without gates. Do not describe
those pushes, the refreshed lock, or remote CI as newly verified.

The issue snapshot contained 26 open Wesker and 60 open Detective issues. This pass
added Detective #134 (repair), #135 and #136 (deferred additions). The companion
`REPAIR_QUEUE_2026-10-24.json` maps every snapshotted issue to a work package or
deferred scope. An open issue count is not a count of unimplemented repairs.
Neither checkout currently has an `openspec/` directory. Do not invent an OpenSpec
status or initialize another planning framework merely for this handoff.

## Authority and working method

Read both AGENTS.md files. Detective's governs the pair. Read the complete applicable
units of ARCHITECTURE (especially the one-function law), NEGATIVE_SPECIFICATION,
COMMUNICATING_DETERMINISM, TEST_BASIS, CONSTRAINT_BLOCK, and
`TEST_SUITE_CLEANUP_CONTRACT.md`. Use `EVIDENCE_FLOW_REPAIR_PLAN.md` and
`REPAIR_REVIEW_LEDGER_2026-10-23.md` as the repair record.

Read the performance-engineering document in full:
`~/Projects/rohan-vinaik.github.io/papers/Core Documents/LLM_WORKFLOW/PROFESSIONAL_CODING_PERFORMANCE_ENGINEERING.md`.
It supplies the process; the project theory supplies the oracle. Existing issue prose
and old implementation sketches do not override either.

For each bounded change:

1. State the question, input basis, protected obligation, named outcomes, producer,
   consumers, real entry point and missing evidence. Find references and alternate
   paths before editing; read whole definitions/sections, not search excerpts.
2. Reproduce the defect on current code. If it is already fixed, perform its missing
   acceptance instead of reimplementing it. Keep a before image and exact identities.
3. Change one cause. Extract/pin a literal-typed pure decision only at a real seam;
   impure containment and durability need boundary tests, not fabricated pins.
4. Follow Detective's CLI protocol and complete printed output. Keep self-dogfood in
   a renamed package snapshot. Keep each CLI walk in a fresh directory.
5. Trace the fact through all consumers and renderers. A computed field is not used
   merely because reflection serializes it. Different remedies retain distinct signs.
6. Record behavior and resource outcomes separately. An absent observation is unknown.
   A timing claim needs production attribution and paired measurements with units/spread.
7. Commit coherent waves with the exact receipt and remaining work. Close an issue
   only against its current acceptance, not a green count. No AI attribution.

The owner has authorized work and pushes; do not repeatedly ask to proceed. The
latest explicit push direction waived push gates. That waiver does not supply missing
behavior evidence. Run the development checks needed to substantiate repair claims;
do not install new mandatory push hooks or block an authorized push on a stale gate.
Publishing, release numbers and tags remain outside the build agent's scope.

## Work already present — acceptance remains

- Wesker CLI/ci/converged isolation and worker cleanup; named timeout/non-kill
  accounting; preserved execution facts; policy-8 annotation exclusion; live globals
  and package metadata; original TCE key computation; nested-measurement refusal.
- Wesker monitoring subscriptions, run retirement, thread filtering before frame
  materialization, observer-failure ownership, admission cleanup, and migrated coverage.
- Detective qualified harvest including NoneType, independent trial input copies,
  explicit uncopyable outcomes, divergence routing, required-observation refusal
  propagation, two-sign command/flag continuity, removal-preflight mode propagation,
  codomain-aware cache contract, and native Ruff resolution.
- The reference-manifest parser preserves commented false as false and refuses
  malformed verification flags. Five local prior drifts and eleven unverified
  load-bearing citations were left explicit.
- Twenty-seven unsupported earlier test deletions were restored. No broad purge is
  accepted. Three dead legacy coverage helpers were removed after reference review.

These are starting points to verify, not permission to close their entire issues.

## Dependency-ordered work packages

### B00 — Accept the integrated pair and repair proof artifacts

**Both repositories; first.** The lock is now aligned; verify a fresh locked install
without PYTHONPATH as well as the prescribed local-pair invocation. They answer
different integration questions. Do not bump a publication floor to an unreleased
version or leak a development Git dependency into wheel metadata.

Regenerate/revalidate the checkpointed certificates through supported commands.
Review `tests/detective/test_Detective_cli__final_banner_synth.py`: its policy suffix
was hand-adjusted during the repair and is not a fresh generated proof. The wrapper
pin reached 14/14 in a disposable copy, but one wrapper case cannot replace the nine
older status cases. Preserve their distinct obligations while validating the wrapper
and `_final_banner_status`. Never edit a certificate standing to make a gate green.

**Done:** reproducible pair setup; generated artifacts have correct source/policy/
provenance; retained status obligations are explicit; fresh relevant checks recorded.

### B01 — Finish monitoring ownership, cancellation and containment

**W#17, #27, #28, #29, #32; D#80, #126, #130.** Start in `Wesker/monitoring.py`,
`interrupt.py`, `line_coverage.py`, `_isolated_worker.py`; then Detective `capture.py`,
`equivalence.py`, `audit.py` and **`budget.py::count_opcodes`**.

The last site still claims a separate tool ID, installs global INSTRUCTION events,
counts without a thread selector, and directly executes its arm. Include it in the
inventory; the earlier six-site list was incomplete. Preserve the opcode instrument's
declared boundary, including foreign-tool DISABLE behavior, when consolidating it.
The paired reader must not treat two failed-outcome markers as evidence of zero
behavior delta. Counter unavailable, arm failure and incomplete execution need their
own causes rather than a guessed slot-exhaustion diagnosis.

Finish registry-lock/cancellation ownership; same-event overlap and both cleanup
orders; setup failure; retirement during an in-flight observer; reused thread IDs;
child-thread/subprocess uncertainty; foreign coverage/profilers; Python 3.12/3.13/3.14.
Observer failure cannot become a target exception kill. A bound exceedance is relative
to the stated budget, not proof of infinite execution. Original measurements must
warrant mutant caps; do not restore an unmeasured fixed ceiling.

**Done:** adversarial schedules finish or refuse by name, restore ownership, and leave
the next run usable. Qualified lines/arcs/captures/outcomes survive the migration.
Account separately for the six self-measurement failures in W#29; mutating the stopping
machinery requires an unmutated containing parent. No whole-repository proof is made
inside a function audit merely to check the scheduled workflow.

### B02 — Capture entry state once and keep every witness phase bounded

**D#105, #108, #127; outcome/rendering portion of #76.** The complete argument graph is
copied per trial, but entry capture still needs its own independent snapshot audit.
Snapshot at entry, preserve aliases within a row, and name an uncopyable or incomplete
row. A later copy of an already-mutated live reference cannot recover entry state.

`_outcome_value` and `_receiver_state_after` directly call the function again;
`_search_witness`/state fallback then attach those results to earlier bounded outcome
text. Prefer carrying the value/state from the admissible invocation already made.
If another invocation is necessary, qualify/bound it and check consistency rather
than silently joining facts from different executions.

Bring witness rendering, recursive literal/import traversal, `property_holds`, and
the post-classification writing loop under the same remaining deadline and effect
boundary. Expensive copying/repr/compilation is also work; checking time only between
mutants does not bound it. Do not render an incomplete value as a complete witness.

Contain filesystem effects during profiling of existing tests as well as invented
calls (D#105). A mutated path must not overwrite the repository merely because the
test's original path was temporary. Derive write authority from an explicit test/
regime boundary, preserve legitimate reads/writes, and disclose/refuse execution that
cannot be contained. Process memory isolation is not filesystem isolation, and an
interception refusal is not an assertion kill. The future effect-archetype system
in D#90 is not a prerequisite for refusing today's unsafe measurement honestly.

**Done:** D#108's recursive accumulator never distinguishes the original from itself
through input aliasing; supplied input remains authored; its deadline reproduction
returns a named cut within the stated unwind boundary, without unbounded rendering.
Required observation failures reach the public refusal path, never an advisory fallback.
The D#105 path-swapping reproduction cannot damage the project or report a containment
interception as test detection.

### B03 — Bind the actual program and its admitted baseline tests

**W#18, #31, #38, #46; D#77, #86, #104, #107, #112, #113, #129.** Follow target
resolution, `session_manifest`, patch owner, installation, entry acknowledgement and
test identity all the way through both execution modes.

Test direct/from-import/alias, defaults, registries, decorators, descriptors and nested
closures. A cause-specific entry refusal must be supported by evidence; do not blame
every failure on a decorator. No-test synthesis and unknown entry are distinct.
Screen an admitted fallback test before it can supply a kill. Handle `Compose.__name__`
without killing the whole file or fabricating a suite kill.

Preserving `__package__` in an existing namespace does not repair a loader that chose
the wrong module identity. Reproduce D#129's clean-regime/canonical-import disagreement.
Run D#86's different-project library sequence without test conftest cleanup. Refresh
or recollect after mid-file edits; do not retain deleted items or a 2-of-11 universe.
Follow same-test-module helper paths cold; do not depend on a previous warm trace.

**Done:** the measured target and test identities match the real imported program;
standalone and sequenced runs agree or name their invalid basis; difficult topology
and observed reach are not mislabeled as specification weakness.

### B04 — One policy, universe and count basis

**D#134, #115, #128; W#22, #30.** Fix the denominator at its authoritative producer.
Do not clamp 250% or divide mutant kills by a dimension count. Distinguish full
universe, estimate, selected sample, withheld operators and unexecuted outcomes.
Carry source, codomain, policy and count unit through final profiling, scope, receipts,
terminal, full report and JSON.

Complete the policy/context matrix through converge, flag, audit, decompose and
verify-rewrite: receiver, clock, environment, inputs and mode as applicable. The latter
currently verifies one-sign receipts; never advertise two-sign preservation through
a narrower proof. Retain the archived-report flag regression. Add stable per-site
census/qualification without losing annotation policy 8's exclusion rule.

**Done:** all applicable surfaces describe the same question/population; one-sign,
two-sign, mixed codomain, fast/full, warm/cold and cut runs have honest counts and
commands. A policy change invalidates the affected old evidence explicitly.

### B05 — Finish the CLI's knowledge and action contract

**D#76, #78, #89, #91, #93–#96, #98, #101, #111, #114, #124, #125; reporting half
of #110; W3/W6 in #102.** Reproduce each small case before editing it.

Required observations, route failures, missing fields, load failures, failing routed
intent tests, unclassified outcomes, crash-only distinctions and equivalence judgments
need their own causes/remedies. A passing characterization cannot overrule a failing
intent test. A supplied sample cannot fix an environment/capability condition. Preserve
the current refusal propagation through audit, converge and verify-rewrite.

Ensure emitted witnesses belong to the printed mutant, round-trip nonfinite input
spellings safely, and never ask for `== nan`. Render full usable observations or a
typed cut with a usable full artifact. Prescribe targets the next verb accepts. Carry
clock/env remedies into the decision instead of printing them only as caveats. Disclose
ambient plugins without disabling them.

Finish the decision-code and reflection-aware field-consumption guards; known result
types use direct reads, older/foreign missing evidence stays named unknown. Do not
delete a field just because AST analysis cannot see its machine consumer. Isolate
nested invocation ledger state and finalize one outcome after all refusals.

**Done:** human/full/JSON/ledger/certificate channels agree where applicable; every
prescription has its premise and retained context. No unsupported verdict survives
under a warning. Deliberate CLI/model-prompt distinctions remain intact.

### B06 — Complete the already-declared operator basis

**W#44 with D#116–#123; W#37.** This is Type (1): the negative basis is already
declared by the theory. Build from NEGATIVE_SPECIFICATION Definitions 11.4/11.6/
11.8/11.10, not the abbreviated family list in W#44 or D#133. Create a catalog
mapping each theoretical operator to generator mode, form, applicability, identity,
observation needs, consumer and retained witness. Do not equate runtime sub-mode
count with the paper's count or invent extra operators to reach 38.

Observed-codomain applicability is universal over the qualified observed set, including
NoneType. Type names alone may not establish a structural, ordering or effect premise.
If the required observation/declared effect is absent, name unsupported/not-applicable/
unresolved; do not invent constructors, bounds, previous-call state or a fake world.
Test wrapper lifetime/reset, generator semantics and effect observations independently.

W#37's broad-handler narrowing rule is not fully specified: tuple-member deletion is
precise but does not settle its UnicodeError example. Record the missing target-type
decision instead of choosing an arbitrary subclass. Keep the semantic test meanwhile.

**Done:** every declared operator has its exact implementation or a named justified
boundary; full-basis claims are withheld where capability is missing; policy/census/
identities and Detective consumption agree. No test deletion exploits an operator hole.

### B07 — Durable state, fresh context and safe trial isolation

**W#20; D#81, #82, #100.** Implement the already-approved SQLite/WAL design with
short transactions, concurrent-writer preservation, same-transaction judgment history,
provenance, foreign-key cleanup, review export and a lossless/corruption-preserving
migration. Generated suites/certificates remain versioned product files. Meaning-based
retention is separate deferred work.

Use named cache fields. Fast/two-sign/pass/regime variants must not evict their valid
siblings. Diagnose generated-test fingerprint differences instead of masking misses.
Key context on fixture/conftest/helper/config/plugin/environment facts where required;
cached positive routing evidence cannot become fresh proof or a negative reach oracle.

Use the approved subprocess import overlay for decompose trials; retain recovery of
old journals while transitioning. A subprocess isolates memory, not filesystem writes.

**Done:** crash/concurrent migration tests preserve committed state; changed contexts
invalidate exactly their evidence; a dry trial leaves the user's bytes and mtime alone.

### B08 — Make existing removal safe before any purge

**D#102 A0/A2, #104, #107, #112, #85; W#37.** Complete exact collected identity,
edit authorization/provenance, class/parameter shape refusals, dependency-qualified
evidence and recovery. Force-include candidate tests in sibling profiles, as in the
neighbor/reach paths; policy propagation alone did not establish their inclusion.

Verify all affected retained obligations after the exact staged edit in a fresh process:
mutant transformations and assertion classes, lines/arcs, intent/MUST-NOTs, codomain,
fixture/helper/import boundaries, residuals and cross-repo consumers. Old certificates
without their basis remain unknown. A reverse dependency index is not the full
kappa-closure. The code-kappa graph/basis is an open theory decision: do not replace it
with an unweighted reach set or invent a definition. Retain affected tests when that
required premise cannot be established; continue independent repairs.

Coordinate source, certificate and index acceptance. Reject intervening edits; on
failure restore exact before images; failed recovery stops later cleanup. Do not
combine individually safe removals without verifying their joint final-witness effect.

**Done:** cleanup C01–C18 hold for the supported edit shape. The current command
either proves the exact edit safe or retains it with the true reason. A new sweep
verb/row grammar is not required for this repair (deferred #136).

### B09 — Remove measured duplicate work without weakening observations

**W#21, #25 presentation, #34, #40–#42; D#83, #87, #130, #131.** Attribute real
cost first. The current patch/global changes retain correctness but still scan/copy
per evaluation: their advertised allocation/scanning savings are unestablished.
Same-size rebinding and module replacement must remain observable. Cache length is
not an identity/invalidation proof.

Verify W#41's original-key computation across all TCE paths; keep it separate from
W#40/#42. Share generation only under its full policy/codomain/pass/compiler/schema
basis; use compact descriptors, never cached live wrapper closures. Keep the required
fresh isolated verification fresh; do not silently redefine it to verify only execution.

Use cheap pytest failure formatting in the isolated worker where full reports are
unconsumed. Native Ruff resolution exists; establish real output/cost acceptance.
Empirical redundancy groups may be reported, never prune the proof universe.

Do not implement D#130's in-thread execution merely because a function is called
pure: C blocking, recursion, allocation and child effects are not bounded by a JUMP
counter. Worker reuse needs ownership, cancellation and contamination proofs.
Native/JIT work is conditional on a remaining measured kernel, not a rewrite quota.

**Done:** each opportunity has SAME/behavior evidence and a separate paired resource
verdict; no speedup is claimed from a passing test or a shorter incidental run.

### B10 — Restore portable scheduling after its prerequisites

**W#33; D#84, #85; dependencies B01/B03/B07/B09.** Spawn workers consume plain
descriptors, node IDs, context and budgets, set up once, and return typed outcomes.
Share an explicit CPU/memory budget; preserve serial evidence and proof standing.
Do not resurrect flags whose live-session path cannot reach an executor.

Separately test xdist/order behavior under the locked interpreter before changing CI
collection. Diagnose the overlay-interpreter flake; do not fix it by retries or a
larger allowance. Parallel test execution and parallel mutant evaluation are different
operations and need separate acceptance.

**Done:** serial/spawn evidence equality, platform/support matrix and measured startup/
memory cost; CI collects the same required obligations. Scheduling is same-answer work,
not an excuse to relax the proof unit or run multiple unsafe in-place trials.

### B11 — Census, one controlled cleanup pilot, then verified waves

Advisory inventory/cost work can start early; deletion waits for its own valid basis.
Record exact collected IDs/origin, setup/call/teardown and fixture costs, reach,
coverage/arcs and named obligations. Separate instrumented observations from ordinary
runs and disclose monitoring/plugin effects. Coverage overlap prioritizes inspection;
it does not decide redundancy.

Start with one function/cluster and the existing manual disposable-copy transaction.
Retain rare refusal, integration, cancellation and operator-blind-spot witnesses.
Consolidation must keep assertions, inputs, marks, exception expectations, fixture
lifetime and routing visible. No new bulk-pruning framework is needed.

**Done:** exact removed/consolidated IDs, retained-witness mappings, fresh affected
Detective evidence, full pair checks, collection delta, rollback identity and resource
measurements. Unresolved candidates stay. There is no test-count or purge-percentage goal.

### B12 — Finish build reproducibility, reference review and documentation

**W#35, #43; D#75, #79, #88, #132; R7.** Check the declared bootstrap, lock, installed
entry points, wheel/sdist boundaries and actual CI collection, not just local imports.
Keep a deps-present environment for the positive load-repair case without destroying
the deps-absent reproduction. Verify current optional-tool/runtime support before use.

Review the five theory-prior drifts against the recorded revisions and dependent
claims before updating hashes. Literature stays unverified until actually checked.
Prepare README example source material, not an unsolicited rewrite of the owner's
manifesto. Update issue status/acceptance and indexes only from current evidence.

For benchmark/local-CI infrastructure, use production-derived recordings, actual layer
contracts and visible advisories. D#132 names mixed impure modules as pure; inspect
their real graph before copying that prohibition. Do not install guessed flags,
unavailable instruments or noisy mandatory memory thresholds. Calibrate a threshold
before treating it as a gate.

Local Sonar's last recovery used a separate copy; the installed server refused the
embedded-database upgrade. No current Sonar acceptance is established. This is a named
setup gap, not a reason to stop an owner-authorized push. Do not migrate/reset the
shared original database or mint credentials to obtain a green badge.

**Done:** a reproducible engineering packet with explicit unmeasured/unexamined areas;
code, artifact and resource claims have their own evidence. Release versions, tags,
PyPI publishing and owner design decisions are handed back separately.

## Deliberately deferred Type (2)

Keep these in their existing issues, without implementing them during this pass:

| Addition | Canonical issue |
| --- | --- |
| Non-introspectable object constructor/fixture models | D#72 |
| Meaning-based invocation-history retention | D#73 |
| New drop-to-synthesis machinery | D#74 |
| User-selected effect archetypes and literal world models | D#90 |
| New explain-on-request command | D#97 |
| Broader content/constant-directed synthesis beyond the supported fragment | D#109 and search portion of D#110 |
| Certified negative residuals / finite-partition proofs | D#135 (split from #102 K3/K6) |
| New sweep interface / additional parametrized-row editing | D#136 (split from #102 A3/A4) |
| Proof-grade static subsumption beyond existing warrants | Static-proof portion of W#25; coordinate D#135 |

Do not defer the real bugs inside mixed issues: D#110's crash-only flag/report
disagreement is B05; exact-identity/transaction repairs in #102 are B08; fixing a
solver's already-supported fragment is repair, not broader search. A missing declared
mu-minus operator is B06, even though implementing it adds code.

## Decisions a mechanical agent must not manufacture

Record the missing premise and continue independent rows: code-kappa graph/domain;
the broad-handler narrowing target; effect/structured operator premises absent from
current observations; step-cap parameters without their required measured basis;
changing what fresh reproducibility verifies. Existing choices are not reopened
without evidence: annotation exclusion/policy 8 and named nested-measurement refusal
are already built. Do not invent intent, equivalence, safe deletion, or a new fault
model merely to make a task DONE.

## Receipts and final hand-back

The 2026-10-23 complete logs/before images are archived locally at
`~/Library/Logs/Detective/evidence-flow-repair-2026-10-23/receipts.tar.gz`.
The 2026-10-24 issue snapshots are under
`~/Library/Logs/Detective/repair-handoff-2026-10-24/`; their identities are recorded
in the queue. Do not copy private machine artifacts or credentials into the repository.

For each finished package return: commit(s), exact accepted obligations and current
issue status, actual commands/full receipts and source basis, behavior disposition,
resource disposition, unresolved cases and one warranted next action. Report the
remaining deferred additions separately. Neither an issue-count reduction nor a
green suite alone is the completion criterion.
