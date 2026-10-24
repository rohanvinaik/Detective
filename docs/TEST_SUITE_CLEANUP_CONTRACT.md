# Wesker and Detective test-suite cleanup contract

Status: accepted working contract, 2026-10-23. This is the shared contract for both
repositories. It specifies acceptance; it does not assert that the current removal
machinery implements every requirement. Capability gaps block the affected edits.

## 1. Objective, authority and scope

Remove unnecessary test execution and maintenance cost while preserving supported
behavior, established specification evidence, authored intent and integration
obligations. There is no deletion quota. Test counts and speed are measured outcomes.

The project's theory, owner-authored requirements and repository instructions govern
what must be preserved. Detective is the mechanized correctness authority within its
declared function, operator, domain, regime and measurement-validity contract. Other
instruments supply evidence for the questions they measure; their scores cannot
override a Detective refusal or decide intended behavior.

This contract preserves existing completeness and incompleteness honestly. Cleanup
does not itself close an existing specification gap. Finite measurements establish
claims within their recorded boundaries; an unresolved boundary prevents a stronger
claim. Unknown is never treated as false, absent or redundant.

Normative terms: MUST is required for acceptance; MAY is permitted when its stated
conditions hold. A missing required field is unknown and blocks the affected edit.

Protected behavior includes values, exceptions and their relevant messages, side
effects, public schemas, ordering, diagnostic codes, containment, cancellation,
certificate standing and cross-project consumption of measured signals. Follow each
signal through engine, loop, aggregation and public gate/report.

## 2. Pass brief and immutable baseline

Before selecting edits, record the objective, permitted changes, protected behavior,
workloads, real entry points, environment, acceptance gates and known unknowns.

The baseline MUST identify the actual working trees of BOTH repositories, including
relevant modified and untracked files. Committed HEAD alone is insufficient. Include:

- Source, test, fixture, helper, generated-test and configuration identities.
- Interpreter, platform, dependency lock and actual imported package locations.
- Relevant plugins, environment settings and supported execution modes.
- Mutation policy, operator selection, domain, inputs, seeds, flags and budgets.
- Relevant input/pin stores, certificates, caches and external fixture identities.
- Complete commands, output receipts, collection and measurement-validity outcomes.

Preserve the baseline without overwriting pre-existing work. Do not clear live
teacher inputs, flags or stores to obtain an apparently fresh result. Fresh isolated
copies may initialize their own state from explicitly recorded authoritative inputs.
Cached evidence is routing information unless its contract permits more. A replayed
negative MUST NOT exclude a test from consideration.

Any relevant concurrent source, fixture, policy, dependency or execution-setting
change invalidates the affected evidence. Rebaseline before proceeding. Do not record
secrets or private machine state in committed receipts.

## 3. Entry gate and advisory census

A suite-wide advisory census MAY record exact collected IDs, outcomes, setup/call/
teardown durations, fixture costs, static similarity and coverage contexts. It MUST
not become a suite-wide mutation proof: the proof unit remains one function's
operators and relevant tests.

Advisory discovery can proceed while a measurement defect is investigated. A deletion
requires an admissible baseline for every affected scope and the required complete
suite checks. A failed, interrupted, stale or unexpectedly reduced baseline is a
blocker, not an optimization opportunity obtained by deleting the troublesome test.

Instrumentation MUST disclose its effects. Compare ordinary collection and outcomes
with instrumented runs. Where profiler/coverage/monitoring coexistence is unproven,
collect advisory measurements separately and label the limitation. Do not install a
plugin that changes the regime and then treat the result as the original baseline.

## 4. Obligation ledger and candidate record

Maintain one ledger across the pair. Each candidate record MUST contain the following
fields, directly or through immutable evidence references:

| Field | Required content |
| --- | --- |
| Identity | Collected node IDs, file/class/definition, parameter bindings and marks, source digest |
| Provenance | Recorded intent, characterization, generated origin or unattributed; authoritative source |
| Intent | Named positive requirements, MUST-NOT behavior and regression scenarios |
| Measurement | Admissible lines, arcs, individual mutant descriptors and distinguishing outcome classes |
| Boundaries | CLI, filesystem, serialization, process, thread, fixture and cross-repo obligations |
| Replacements | Exact retained witnesses and how each obligation remains protected |
| Impact | Affected functions/helpers/fixtures and all unresolved reach or attribution |
| Basis | Both source identities, environment, policy, domain, regime, inputs, capabilities and validity |
| Evidence | Complete commands and raw receipts, with explicit missing or cut evidence |
| Edit | Exact proposed definitions/cases/files and the authorized scope |
| Recovery | Before images, expected after identities and restoration procedure |
| Disposition | State, named reason, behavior/resource outcome and remaining work |

Provenance comes from the record, not a filename, marker or directory. Generated
observations cannot establish intended behavior. If an owner adopts a generated
witness for a stated intent, preserve both its generated origin and that explicit
adoption. Routine removal within an already authorized scope does not require a new
permission prompt when the contract is satisfied.

Each authored obligation MUST retain an adequate witness and its authoritative
meaning after consolidation. Moving a test does not retire its requirement. A helper
or parametrization must remain visible to the relevant routing/measurement paths.

## 5. Preservation predicate

For every affected function, compare before and after on the same admissible basis.
The exact edit is acceptable only when ALL of these conditions hold:

1. Every previously established assertion-based mutant distinction remains
   established by retained tests with admissible execution evidence.
2. Every previously established line and branch-arc obligation remains guarded.
   Missing arc measurement is unknown; an empty map is not proof of no obligations.
3. Every declared intent and integration obligation retains an adequate witness.
4. Known distinguishing inputs, fences, flags and unresolved residuals remain
   represented with their standing and reproducibility intact.
5. No new skip, xfail, filter, routing exclusion, weakened oracle, reduced budget or
   execution mode conceals lost evidence.
6. Public outputs and side effects remain protected through their real entry points.

Compare individual obligations and mutant transformations. Equal percentages,
counts, coverage sets or aggregate killsets do not establish the whole predicate.
An assertion distinction becoming a crash, timeout, divergence or unresolved
execution is a regression in the evidence. An observer failure cannot count as a
passing test or absence of reach.

Test identities MAY change through consolidation only with an explicit before/after
mapping, preserved case bindings and fresh recollection. Subject code identities and
mutant transformations must remain comparable. A relevant subject behavior change
belongs in a separate corrective pass with a new baseline.

## 6. Universe and residual preservation

Record policy, operator selection, applicability, seeds, domain, execution regime and
budgets. Verify the same universe of mutant transformations, rather than equal
counts alone. Identifier equality without the matching transformation and source
basis is insufficient.

Cleanup MUST NOT obtain apparent completeness by shrinking an observed domain or
mutation universe. In particular, removing the only call exposing a codomain type
must not silently erase its mu-minus output perturbations. Preserve the relevant
domain through legitimate retained observations or an established authored domain
contract; injecting an assumed type is not fresh evidence.

Empirical groups are presentation/scheduling information and MUST NOT prune the proof
universe. Static subsumption needs its own established warrant and separate change.
Operator blind spots require retention of the semantic test or separate operator
work; absence of an exposing mutant does not authorize deletion.

A valid incomplete measurement MAY support preservation cleanup. Existing killable
survivors, fences and other gaps remain explicit. Candidate-equivalent is not proven
equivalent. Cleanup cannot promote a weaker outcome to completion or erase a known
positive distinguishing witness. Invalid/cut/stale/unresolved measurements refuse
the affected deletion.

## 7. Full impact and conservative boundaries

Before editing, establish consumers and alternate production paths using symbolic
references. Combine this with qualified fresh reach evidence, fixture/helper/import
effects and the current removal-safety contract.

Check indirect reach: a test can enter f, pass through g and protect h. Include every
affected function and cross-repository consumer, not only the requested target or
its immediate neighbor. Candidate tests must actually be included in each relevant
measurement; a successful profile that never admitted them does not establish safety.

Runtime non-observation is not non-reach. Reflection, native code, subprocesses,
ambient/child threads and opaque fixtures require explicit boundary evidence. Keep
the relevant tests where their impact cannot be established. Do not replace a
boundary test with pure-function evidence that cannot observe the boundary.

## 8. Classes of change

- Redundant deletion: retain all obligations through identified remaining witnesses.
- Characterization consolidation: preserve cases, oracle strength and provenance.
- Parametrization: preserve bindings, marks, exception expectations, fixture lifetimes
  and collected identity mappings. Unsupported case edits remain report-only.
- Fixture/helper reuse: re-establish isolation, ordering, routing and execution context.
- Gate scheduling: keep all deep obligations visible, required and failing when broken.

Production optimization, instrumentation repair, operator change, dependency change,
feature retirement and support reduction are separate passes. Rebaseline after them.
Do not fold them into deletion to make a comparison pass.

## 9. Transaction and recovery

The lifecycle is:

`DISCOVERED -> PREPARED -> VERIFIED_IN_COPY -> APPLIED_PENDING_VERIFY -> ACCEPTED`

An unmet prerequisite yields `BLOCKED`. A failed/invalid applied edit yields
`ROLLED_BACK`. Incomplete restoration yields `RECOVERY_REQUIRED`, which stops further
cleanup and preserves forensic copies.

Each transaction MUST:

1. Capture the actual baseline and before images without overwriting other work.
2. Stage one exact edit or jointly verified batch in a disposable copy.
3. Freshly collect and remeasure every affected scope after the staged edit.
4. Verify the full preservation predicate and collection delta.
5. Compare the live workspace to its expected basis before promotion.
6. Apply the verified edit, run the required post-apply gates and accept its evidence
   coherently, or restore the preceding state.

Verify a batch as that exact batch. Do not union individually safe deletions: two
tests may each be removable while removing both loses the final witness.

Atomic file replacement protects a write, not an entire multi-file transaction.
Journal prepared/applied/accepted stages. Source, certificates and indexes must be
accepted coherently; until rebuilt, stale evidence must be explicitly unavailable.
Never hand-edit certificate standing. On interruption, inspect the journal and verify
restoration before another wave. Do not overwrite concurrent edits during recovery.

This process MAY be performed manually in controlled copies. It does not require a
new bulk-pruning framework. A missing capability still blocks the affected edit.

## 10. Fresh execution and tool protocol

After edits, recollect and remeasure from a fresh process unless the refresh mechanism
itself has an established correctness contract. Avoid stale definitions, shifted
line identities, imported test objects and cached routing claims.

Follow the repository's real CLI protocol, beginning with help/regime where required,
and read complete outputs and prescribed next actions. Respect refusals. Keep each
walk in a fresh directory. Use the required renamed-package snapshot for self-audit
so the live engine is protected from its own mutants. Confirm actual local imports.

Do not clear or rewrite live evidence stores as a substitute for recording the basis.
Rebuild certificates through the supported path. Issue acceptance, suite acceptance
and benchmark claims are separate decisions.

## 11. Measurement validity and containment

Receipts MUST disclose collection/execution completeness, containment, cancellation,
instrumentation availability, observer failures, thread ownership, late-event handling
and missing/truncated/stale evidence.

Observer exceptions must invalidate the affected evidence or yield an explicit
capability outcome. Retired runs cannot append to completed reports. Uncontained
workers cannot silently leave later measurements admissible. Child-thread attribution
and uncertainty must remain explicit.

Coverage, profiling and monitoring coexistence require evidence on supported
interpreters and modes. Fast rejection or a passing isolated containment test alone
does not establish cross-suite lifecycle correctness.

## 12. Required gates

| Scope | Required evidence |
| --- | --- |
| Candidate | Identity, provenance, obligations, full impact, basis and recovery plan |
| Staged edit | Fresh collection and preservation proof for all affected scopes |
| Accepted wave | Both complete local suites against the declared local pair |
| Quality | Repository-required pinned Ruff checks and whole-tree format check |
| Compatibility | Existing supported Python/OS matrix and relevant execution modes |
| Push | Existing repository-specific verification requirements |

Unexpected missing tests block acceptance. Gate commands and their complete outputs
are recorded. Do not weaken gates, remove failure paths or redefine a failed baseline
through cleanup. Type checks and structural advisors retain their stated advisory
standing. Local verification and supported-matrix verification are distinct fields;
pending checks stay pending.

Use each project's own environment and the declared local pair resolution. For any
Wesker behavior change, acceptance includes Detective against that local Wesker.
Release/version/publication decisions remain outside this cleanup pass.

## 13. Adversarial acceptance of the cleanup mechanism

Before broad deletion, establish these obligations using existing adequate tests
where available and adding only genuinely missing obligations:

| ID | Adversarial case | Required result |
| --- | --- | --- |
| C01 | Empty/unexpectedly reduced collection | Refuse acceptance |
| C02 | Same mutant count, changed transformations | Invalidate comparison |
| C03 | Assertion distinction becomes crash/timeout | Preserve old witness or refuse |
| C04 | Missing arcs represented by an empty map | Unknown, never discharged |
| C05 | Two-hop, fixture-only or cross-repo reach | Include affected obligation |
| C06 | Opaque/native/subprocess/child-thread impact | Keep boundary witness or establish evidence |
| C07 | Mutually redundant tests deleted together | Verify exact batch; retain final witness |
| C08 | Ambiguous definition or parameter case edit | Report-only/refuse unsupported edit |
| C09 | Mid-file edit with stale collection | Fresh recollection required |
| C10 | Removed codomain observation shrinks mu-minus | Invalidate apparent improvement |
| C11 | Generated characterization replaces intent | Require retained authoritative intent obligation |
| C12 | Concurrent source/policy/fixture changes | Invalidate affected basis |
| C13 | Interrupted or partially applied multi-file edit | Verified rollback or recovery-required |
| C14 | Stale certificate/index or failed restoration | No acceptance; stop next wave |
| C15 | Observer failure or callback from retired run | No admitted evidence; disclose invalidity |
| C16 | Uncontained worker contaminates later run | No silent admissibility |
| C17 | Missing measurement field or unknown outcome code | Fail closed with named unresolved reason |
| C18 | Operator blind spot hides a semantic distinction | Keep semantic obligation |

## 14. Resource evidence

Measure collection, setup, call, teardown, total wall time and relevant memory/worker
costs on reproducible workloads. Separate ordinary and instrumented runs and cold and
warm measurements. Speed claims need repeated paired measurements with the declared
tooling; a single shorter run is a lead. Attribute profiler costs and validate that
instrumentation did not change the verdict.

Behavior outcomes: `PRESERVED`, `CHANGED`, `UNRESOLVED`, `INVALID_MEASUREMENT`.

Resource outcomes: `REFUND`, `PARITY`, `REGRESSION`, `UNMEASURABLE`, `INADMISSIBLE`.

Neither outcome implies the other. Fewer definitions can save little execution cost;
a small consolidation can remove expensive repeated setup. Record the actual result.

## 15. Durable reporting and completion

Every accepted wave records exact removals/consolidations, retained witnesses,
obligation mappings, complete checks, limitations, resource findings and recovery
identity. Raw receipts may remain local; shared records must identify their basis and
availability without committing private material or credentials.

Candidate dispositions are `KEPT`, `CONSOLIDATED`,
`REMOVED_WITH_VERIFIED_OBLIGATIONS`, and `UNRESOLVED`, each with a named reason.
Unresolved candidates are retained. A complete assessment can report unresolved
candidates, but must not claim their deletion or their obligations verified. A
completed cleanup wave requires every applied edit accepted and every restoration
verified; a completed broader roadmap requires its remaining actionable work closed
separately with evidence.

Future tests should identify the additional named obligation and why existing
witnesses do not cover it. Keep intent, characterization and integration roles
explicit. Consolidate only when their obligations survive. This ledger is maintained
as functions, contracts and routing move; it is not discarded after the purge.

## 16. Execution order and related contracts

Proceed in dependency order: measurement/containment validity, fresh identity and
collection, transactional restoration and certificate coherence, one controlled
candidate pilot, then verified waves. Advisory inventory may run earlier.

Before using an existing removal command destructively, demonstrate that its path
satisfies this contract or supply the missing checks in the surrounding controlled
transaction. A two-axis kill/line proposal alone does not discharge arc, intent and
integration obligations.

Read this alongside [the repository instructions](../AGENTS.md),
[the architecture](../ARCHITECTURE.md) and [the test-basis contract](TEST_BASIS.md).
Where an earlier implementation or proposal supplies a narrower check, this contract
requires the additional evidence before accepting cleanup. It does not silently
upgrade that implementation's claims.
