# Tasks

Checked rows record bounded accepted subsets. Every unchecked row is remaining work or
acceptance still owed, not a claim that its implementation is wholly absent. Issue
membership and dependency edges are in `docs/REPAIR_QUEUE_2026-10-24.json`.

## 1. B00 — Integrated pair and artifact basis

- [x] 1.1 Correct the published runtime floor to the release that provides JoinedWorker and owned monitoring; prepare and owner-publish paired 1.2.0 artifacts (RELEASE_1_2_0.md).
- [x] 1.2 Commit/push the 1.2.1 coverage repair and require Wesker>=1.2.1; retain a precise development Git lock.
- [ ] 1.3 Accept generated suites/certificates against current source, policy and provenance; retain the nine _final_banner_status characterization tests independently of its wrapper certificate.
- [ ] 1.4 Reproduce the original B00 public-command cases against the installed pair and record their exact accepted subsets.

## 2. B01 — Monitoring, cancellation and containment

- [x] 2.1 Preserve cold instruction counts beside a foreign PY_START disabler; verify the direct broker regression and Detective budget coverage tests on 3.12/3.14 (Wesker 8aa2b4e).
- [ ] 2.2 Finish the seven-site inventory, including the already-migrated count_opcodes; verify hook absence, tool/thread ownership, callback failure qualification and all consumers.
- [ ] 2.3 Verify concurrent/same-event overlap, both cleanup orders, global-mask changes with existing subscribers, setup rollback, startup cancellation, retirement/inflight delivery and thread-ID reuse.
- [ ] 2.4 Verify child-thread/subprocess uncertainty and foreign coverage/profiler coexistence across 3.12–3.14; retain per-TestId line, arc, capture and outcome equality.
- [x] 2.4a (2026-11-12) Wesker#32 closed on `f7b4b67`, re-run under 3.12 and 3.14: an AST guard in each repo fails the build on a hook call outside `Wesker/monitoring.py` (Wesker aed82d8, Detective 64732f6); per-TestId lines and arcs are pinned equal in-process vs isolated, beside a foreign monitoring tool, a `sys.setprofile` hook, cProfile and a running coverage.py (c6718a2, e445e79); setup rollback, a failed rollback, same-event overlap, global-mask changes and thread-id reuse are tested (e94fd07). A pre-existing thread and a child process make reach unknown (`incomplete_preexisting_thread`, `incomplete_subprocess`; 5a7b725, d878e76). Not accepted: capture equality in the corpus; pyinstrument; Detective reading the new reach codes (Wesker#17 stays open for it).
- [ ] 2.5 Reproduce W#29's six self-measurement containment failures with an unmutated containing parent; do not infer success from the ordinary CI suite.
- [ ] 2.5a (2026-10-25, not accepted) The spec-full self-measurement on Wesker 6ba533d hit its 180-minute bound. The stall dumps locate a permanent hang: the main thread in `Thread.start()` -> `_started.wait()` from `_run_test_with_timeout`, from 14:57 to 17:27, with no other Python thread (W#29 comment). It is not the `with`-stranding fixed in 91c3b93/b1fd0e1.
- [ ] 2.5b (2026-10-26, not accepted) The hang's cause and its fixes:
  - **Cause:** the equivalence check ran `_apply_mem_limit`'s original in the measuring process, setting RLIMIT_AS=(1, 1).
  - **Fixes:** Wesker f1598bf (`contain_speculation`) and eb6a17a (`worker_lost`, a named refusal).
  - **Run 40237240506 (f99281c):** passed the hang point, then went silent.
  - **Run 40254151337:** on 2fbd029, whose fix (W#52) stops the measured tests from removing the stall dump. It measured `_isolated_worker.py` (0/301) and `action.py` (109/324, 51 s), then crashed: `OSError: [Errno 9] Bad file descriptor` on the measuring process's stdout.

  Not accepted:
  - the nested Action's stream code killing stdout (W#52);
  - `_isolated_worker.py::_build_mutant` exceeding its budget (0/62);
  - the original six (2.5);
  - whether 180 minutes can hold the run (founder decision, W#29).
- [ ] 2.5c (2026-11-12, not accepted) Spec-full after the Wave 1-3 containment work:
  - **Run 43102482321 (fb2f8b4):** completed in 2 h 26 min and printed its report over all 24 files for the first time; a named refusal (584 functions partially evaluated: 572 "could not stop: the session's baseline trace", 12 over budget).
  - **Run 43134316406 (185985c):** ran out its 180 minutes while still evaluating mutants (stall dumps in a different evaluation each time). No report.
  - **Landed (Wesker f7b4b67):** a test the baseline cannot stop is named and a child-process wait is stopped (62bf514); the baseline's one-time cost is not charged to the first function (576e153); measured code cannot write into the run's output (c2e41e3, W#52); a survivor no test ran against says so (5c40bd8); under `--isolated` the measuring process runs no mutant uncapped (381878c, W#45/#39).

  Not accepted: the sharded run (decision B1, in progress); the 12 over-budget functions; a worker blocked on anything but a child process; W#45's finding that a mutant stopped at the memory cap is recorded `contained=False`, ends its function early and varies run to run.
- [ ] 2.6 Validate original-measurement warrants for mutant step caps and propagate named wall/observer/arm failures through every gate.
- [x] 2.6a (2026-10-25) The witness search budgets a mutant with Wesker's calibrated STEP_BUDGET_FACTOR/FLOOR (Detective 01337aa): the `//` -> `/` halving mutant (1,075 iterations) is distinguished, never filed divergent. The strict gate names every no-verdict mutant and fails only on a repairable one (founder ruling). Not accepted: the original's probe cap (STEP_PROBE_CAP), the steps_140m wall split (W#27), and the harvest step budget (D#80 (3)).

## 3. B02 — Invocation evidence and effects

- [x] 3.1 Snapshot the argument graph at PY_START, preserve within-row aliases, isolate rows and name copy/unrepresentable failures (1ca0202; B02 execution record).
- [x] 3.2 Carry witness values and receiver state from the same admissible bounded invocation; remove unbounded value/state re-execution (219a062).
- [x] 3.3 Bound property checks, golden capture and witness/suite rendering under the remaining deadline; propagate speculative-write refusals (02d96d2).
- [x] 3.4 Close D#105's existing-test path-swapping reproduction using explicit test/regime write authority; preserve legitimate temp writes and never score containment interception as assertion detection (2026-10-25: D#105 closed at e341b25, Wesker#51 at fc661d0).
- [x] 3.4a (2026-10-25) D#105, verified by fresh-folder file sweeps across 13 runs:
  - write authority prevents every out-of-authority write (nothing landed);
  - a prevented mutant is named per mutant and never scored;
  - legitimate tmp_path writes are preserved;
  - 6e10cf8: a file-writing function's speculative classification refuses the input instead of aborting the run, and write-refused survivors route to a WRITE TEST.
  - e341b25 (D#105 reopened): that WRITE TEST looped on survivors the suite already detected by crash. Each write-refused survivor is now named by standing, WRITE TEST names only those nothing detects, and a detected-only residual is converge's INCOMPLETE hand-back `write_refused_detected`. Accepted over three rounds on the c1 fixture: the advised test closes the open survivor and is never called redundant.
  - Wesker fc661d0 (Wesker#51): the CLI rollup counts and names write_outside_authority.
  Not accepted: a writer with an always-raising mutant cannot reach COMPLETE, since its value search is the refused one (D#143).
- [x] 3.4b (2026-10-26) D#141 (157510e): a speculative call can no longer change Detective's own process.
  - **Refused:** resource limits, spawns, signals, cwd and env, by Detective's ContextVar-scoped hook (Wesker's list, kept one by a fence test).
  - **The outcome:** `<effect-refused>`, through `speculative_refusal`.
  - **The survivor:** joins #105's family under its named cause ("calls subprocess.Popen").
  - **Accepted:** the RLIMIT_NOFILE target, with the limit unchanged; converge on a spawning function spawns nothing, and the advised stubbed-call test reaches COMPLETE 6/6.

  Not accepted: the residuals in D#143 (unclassifiable refused survivors, `--check-strict`, the refusal's boundary).
- [ ] 3.5 Re-run D#108/#127 original CLI reproductions, including slow copy/repr/rendering and cancellation, then accept only the demonstrated deadline and authored-input obligations.
- [x] 3.5a (2026-11-12) Wesker#55 and D#127 closed. Every evaluation gets fresh authored arguments in both modes and an original control (Wesker `FreshArguments`, `original_control_standing`); a failure the original also produces is the unscored `original_also_fails`, named on every Detective surface in the sign of its cause (1da374b). Arguments that cannot be copied or compared are named (`shared_arguments`). Not accepted: D#108's witness-writing loop and its slow copy/repr/rendering cases (3.5 itself).
- [ ] 3.6 Verify nonfinite literal round trips, evaluated distinctions and NaN assertions through written tests and public reports; leave unrelated D#76 reporting work in B05.
- [x] 3.7 Reject harvest observations/snapshots admitted after the absolute deadline, include setup/startup in the remaining budget, and reap startup/pre-join cancellation (Detective e5f7c98/bf3f87b, ten controlled regressions; exact 1.2.2 CI). This accepts the added boundary subset, not 3.4–3.6 or the full D#108 field reproduction.

## 4. B03 — Actual program and test identity

- [ ] 4.1 Verify patch owner, install and entry acknowledgement across direct/from-import/alias/default/registry/decorator/descriptor/closure topologies and both execution modes.
- [ ] 4.2 Screen fallback tests against the baseline; reproduce Compose.__name__ and canonical-package/relative-import cases without fabricated kill attribution.
- [x] 4.2a (2026-10-25) Compose.__name__ on real toolz 1.2.0: the crash reproduced at d0c1e41^, and post-fix both modes complete (Wesker#38 closed). The canonical namespace package with relative imports loads by package name in every verb (D#129 closed; Fix row by cause in f2be333). Not accepted: the refused binding reads not_entered, and in-process records attribute crash kills to an unrelated test (Wesker#50, the fabricated-attribution clause of 4.2).
- [ ] 4.3 Recollect after mid-file edits and verify the actual mutant universe/TestIds; reproduce different-project sequences without test conftest cleanup.
- [ ] 4.4 Fix/accept cold same-module helper routing and exact collected identity; distinguish empty synthesis from unknown entry.

## 5. B04 — Policy, universe and units

- [ ] 5.1 Reaccept authoritative universe/estimate/sample/withheld counts and mutation kills versus value pinning versus behavioral DOF; do not clamp inconsistent percentages.
- [ ] 5.2 Exercise source/codomain/policy/context propagation through converge, flag, audit, decompose and verify-rewrite, including two-sign and warm/cold variants.
- [ ] 5.3 Verify site census and qualification, annotation-policy exclusion and explicit invalidation of affected historical evidence.

## 6. B05 — CLI knowledge and action contract

- [ ] 6.1 Reproduce the remaining report/routing cases from the queue; preserve distinct causes for observation, collection, environment, intent failure, crash-only and equivalence outcomes.
- [x] 6.1a (2026-10-25) Re-measured and repaired in this wave, each with its own sign:
  - the failing floor before writing (D#114/#124 closed);
  - an errored fixture's own route (`repair_errored_test`; no DONE, no "setup is clean");
  - the gate warning naming its cause;
  - the load-failure Fix row by cause;
  - "no test written";
  - regime's migrate rows read from its plan;
  - no false "every mutant killed";
  - write-refused survivors' WRITE TEST.
  Filed: D#139 (uncovered vs failing-only lines) and D#140 (μ⁻ survivor rendering).
- [x] 6.1b (2026-10-26) D#139 closed (fc87423). D#140 items 2 and 4 (fe57369; correction d2750f7):
  - a function that takes no argument is never asked for an --input, and a method's receiver counts as an input;
  - "detected by crash" appears only where a current test detects it.

  Not accepted: D#140 items 1, 3, 5 and 6. Filed:
  - D#142: an incomplete observation names no next command; an unchanged mutant renders an empty diff and is offered flag; a divergent residual is recorded as flaggable; under a step-budget floor, the uncovered row points at an action that names nothing.
  - Wesker#53: SWAP of identical arguments.
  - Wesker#54: harness dispositions unnamed in the rollup.
  - D#144: a containment intent test that fails intermittently on CI's macOS runners.
- [x] 6.1c (2026-11-12) Wave 2, pages that said something false. Closed with re-run evidence: D#76 (a suggested assertion is satisfiable and names its mutant), D#77 (the decorator_wrapper sentence), D#86 (library entries restore the process), D#96 (process-state reads refuse the golden), D#101 (clock / fixture / --input routing), D#104 (`audit --remove` re-checks the edited suite in a fresh process), D#107 (helper, alias and constant reach), D#113 and D#115 (next commands carry the run's universe), D#144. Landed in part, each with a status comment on its issue: D#110 (a distinguished mutant is never flagged equivalent; the reach half is open), D#134, D#140 (item 3 waits on the operator catalog), D#142 (`--trace-budget 0` ends UNGATEABLE and asks for the same flags again), D#89 (U5, the audit count qualifier and two display cuts landed; eight items open).
- [ ] 6.2 Verify human stdout, full report, JSON, ledger and certificate agreement for unknown/multiple refusals, absent/unknown containment and provenance-bearing shape hazards.
- [ ] 6.3 Round-trip printed witness/mutant identity, full usable outcomes, nonfinite spellings, valid next targets and clock/environment/two-sign context.
- [ ] 6.4 Complete decision-code/field-consumption guards, foreign missing-evidence handling, plugin disclosure and nested invocation-ledger finalization.

## 7. B06 — Already-declared operator basis

- [ ] 7.1 Build the exact μ⁻ catalog from NEGATIVE_SPECIFICATION definitions 11.4/11.6/11.8/11.10, mapping identity, applicability, observation premise, generator, consumer and witness.
- [ ] 7.2 Implement/accept missing declared operators and universal observed-codomain applicability, including NoneType; disclose unsupported structural/effect premises.
- [x] 7.2a (2026-10-25) Of Def. 11.8's 38 operators: 30 built, 2 partial (dict swap, raise inject), 2 realized by others (0, state-noop), 4 unsupported (field, class, clamp, state-extra) (Wesker d5029f5/c20ad75/7b6191a). Families (i)-(iv) accepted (D#116-#119 closed). Not accepted: (v)-(viii); per-return-site typing; and the unbuilt list's surfacing (D#140).
- [ ] 7.3 Verify wrapper lifetime/reset, generators, effects, policy/census identities and Detective consumption; withhold full-basis claims where capability is absent.
- [ ] 7.4 Obtain the missing broad-handler narrowing target rule; retain its semantic witness instead of inventing an arbitrary subclass.

## 8. B07 — Durable state and safe trials

- [ ] 8.1 Implement/accept approved SQLite/WAL transactions, concurrent writers, provenance/history, foreign-key cleanup and corruption-preserving lossless migration.
- [ ] 8.2 Preserve sibling cache variants and validate fixture/helper/conftest/config/plugin/environment context; never turn replayed non-reach into fresh proof.
- [ ] 8.3 Finish subprocess import-overlay trials and recovery; prove user bytes and mtime remain unchanged on dry trials, including crash paths.

## 9. B08 — Safe existing removal

- [ ] 9.1 Complete exact collected identity, edit authorization/provenance and supported class/parameter shape refusals; force-include candidate tests in affected sibling profiles.
- [ ] 9.2 Establish every required affected-obligation premise; retain tests when the code-kappa/domain basis or another required witness is unavailable.
- [ ] 9.3 Verify the exact staged edit fresh, reject intervening edits, coordinate source/certificate/index acceptance and restore exact before images on failure.
- [ ] 9.4 Reaccept cleanup C01–C18 and the joint final-witness case before any purge; failed recovery must stop the next edit.
- [x] 9.5 (2026-10-26, D#145; closed 2026-11-12) Make the redundant set and the cover count independent of execution order and trace-cache state. The kill matrix credited each mutant to its first killer, so the same tree read a cover of 2 or 3. Now the redundant set and the cover come from the full per-test kill relation, read from the one profile the audit already runs (Wesker `full_matrix`, `kill_relation`; Detective f51cd6d, 827cfb5), and `cover_standing` names when the relation is not available.

## 10. B09 — Measured same-answer work elimination

- [ ] 10.1 Attribute actual costs and validate W#40/#42 scan/allocation opportunities without losing same-size rebinding or module-replacement observations.
- [ ] 10.2 Reaccept W#41 original TCE-key reuse separately; preserve full policy/codomain/pass/compiler/schema bases for shared generation.
- [ ] 10.3 Accept compact descriptors, cheap failure formatting and native Ruff resolution using independent behavior and resource receipts; empirical groups remain presentation-only.
- [ ] 10.4 Consider worker reuse/native kernels only after measured residual cost and ownership/cancellation/contamination evidence; never replace bounds with an unsupported purity assumption.

## 11. B10 — Portable scheduling

- [ ] 11.1 Implement/accept spawn workers using plain descriptors, node IDs, context and explicit CPU/memory/deadline budgets; preserve serial evidence.
- [ ] 11.2 Verify serial/spawn support and resource measurements through the live CLI; do not resurrect unreachable parallel flags.
- [ ] 11.3 Separately resolve overlay/order flakes and accept xdist collection/obligation equality before changing CI scheduling; do not mask failures with retries.

## 12. B11 — Advisory census and controlled cleanup

- [ ] 12.1 Record exact IDs, source, setup/call/teardown/fixture cost and named obligations; disclose instrumentation effects. Overlap only prioritizes inspection.
- [ ] 12.2 Run one disposable-copy pilot only after its B08 premises; retain rare refusal, integration, cancellation and operator-blind-spot witnesses.
- [ ] 12.3 Record exact removed/consolidated IDs, retained-witness mapping, fresh affected evidence, joint-removal result, recovery identity and paired resource measurements before wider waves.

## 13. B12 — Build, quality, references and release

- [x] 13.1 Repair the observed coverage/3.12 CI failures and pass both six-cell 3.12–3.14 Linux/macOS matrices (Wesker 40074238464; Detective 40074339034).
- [x] 13.2 Align Sonar version/runtime metadata; retain pinned lint/format, packaging and workflow checks.
- [x] 13.3 Record the historical paired 1.2.1 artifact/signing and installed-wheel receipt, its subsequent PyPI publication, and the retraction of premature clearance after the exact Detective tag failed macOS 3.14 CI (docs/RELEASE_1_2_1.md). That receipt does not establish exact-tag CI acceptance.
- [ ] 13.4 Triage remaining Sonar findings against the real trust boundary, with reasoned transitions or code fixes; separately repair the shared local Sonar setup without resetting its original database.
- [ ] 13.5 Finish supply-chain/repository hygiene and supported optional-tool/bootstrap checks; maintain both dependencies-present and dependencies-absent reproductions.
- [ ] 13.6 Review the five theory-prior drifts and actual literature before updating reference hashes; prepare example source material without rewriting the owner's manifesto.
- [ ] 13.7 Build production-derived benchmark/memory advisories and calibrate any threshold before making it a gate; keep unmeasured claims explicit.
- [x] 13.8 Supersede the defective 1.2.1 install target with the corrected 1.2.2 pair: observe both on PyPI with all four hashes matching GitHub, install both from the ordinary index in a fresh managed 3.14.7 environment, and follow help → regime → converge to COMPLETE, 17/17 killed, three tests and isolated reproducibility confirmation (docs/RESUME_PAIRED_REPAIR_2026-10-24.md). This is fixture characterization, not universal proof.
- [x] 13.9 Complete the paired 1.2.2 correction: Wesker 60df89b push → Detective exact floor/lock/sync → bf3f87b full frozen-candidate CI → both exact-CI guarded GitHub build/sign jobs → matched handoff packet → observed PyPI publication (docs/RELEASE_1_2_2.md). Preserve the immutable 1.2.1 files and retracted clearance.

## 14. Scope and handoff maintenance

- [x] 14.1 Preserve all 89 snapshotted issue mappings and dependencies in a shared OpenSpec planning home; carry forward classification without claiming fresh acceptance of every issue.
- [x] 14.2 Update GitHub tracking/release/affected issue records with exact accepted subsets and residual work; never close an umbrella issue from a green suite alone (W#32/#35/#36; D#88/#99/#105/#108/#127/#133).
- [ ] 14.3 Keep Type (2) additions in their existing issues and record missing owner premises. Each accepted work wave updates this plan, queue and relevant issue receipt together.
- [x] 14.3a (2026-11-11) The Wave-0 decisions of `docs/REPAIR_WORKFLOW_2026-10-26.md`, derived from the theory. The founder, 2026-11-11: they are not rulings to wait for; the papers and the statements of intent decide them. Each row names what decides it. A derivation is a reading, so a row is reopened by showing the cited text says otherwise.
  - **A1 (W#55): both.** KNOWABILITY Def. 2.3: a suite kills `p∘f` iff `p(f(x)) ≠ f(x)` for some `x` in it. A kill is a difference from the original on the same authored input. So every evaluation gets the authored arguments, in both modes, and a failure the original also produces in the same state is never a kill.
  - **A2 (D#110): refuse `flag … equivalent`; keep any spelling that makes a different, true claim.** KNOWABILITY §10: a witnessed execution resolves non-equivalence positively; only a justified proof resolves it negatively. A mutant with a distinguishing execution on record is decided, so "equivalent" is a false record.
  - **A3 (D#145): the full kill matrix, over the one function's own tests.** Killing is a relation over (test, mutant) (Def. 2.3, Prop. 7.1); a first-killer record is an artifact of order. ARCHITECTURE §11 prices it: the cost scales with one function's suite.
  - **A4: D#113 is D#110's reporting half** (its own status block), with its fixture as an acceptance case. **The `--remove` page that ends DONE over open gaps is a defect** (COMMUNICATING_DETERMINISM §3: a page's last directive is a claim about the next command).
  - **B1 (W#29): shard the badge run.** ARCHITECTURE §11: anything that scales with the codebase is a different question; the unit is one function, so the run is a matrix of file groups with an aggregation job.
  - **B2 (W#27): k = 32 and F = 10,000 stand**, on the calibration's evidence (0 of 3,176 terminating observations misfiled). A constant is re-opened by a measurement, not by a preference.
  - **B3 (W#28): keep the named refusal and the `--isolated` route.** COMMUNICATING_DETERMINISM §4: a refusal is an output. In-process re-entrancy is a new capability, deferred (E3).
  - **B4 (W#45/W#39): amend the acceptance to "named cut".** ARCHITECTURE §0 and W#27: a stop by a budget proves nothing about the value, so it is never a kill.
  - **C1 (W#54): a harness line beside the kill rate**, counted per disposition with the functions named. COMMUNICATING_DETERMINISM §4/§9.5: absence and emptiness never render identically; a ratio that drops mutants says how many and why.
  - **C2 (W#31): an unscreened remainder is its own state and reaches the page and the gate.** "Measured no gap" and "could not measure" do not share a sign (§3.1, last row). Wesker computes `unscreened_tests` and nothing reads it (invariant 2/the field guard, D#94). A follow-up issue is filed when Wave 2 reaches it.
  - **C3 (D#143): the named floor now** ("COMPLETE modulo N refused crash-detected survivors"), in KNOWABILITY §10's sense of a certificate conditional on what it names. The strict gate's 2026-10-25 rule extends: it fails only on a cause the reader can fix. A sandboxed speculative run is a new capability (E3).
  - **D1 (W#48): one canonical serializer, one policy bump, one flag migration.** ARCHITECTURE §11: determinism is the product and any cache is content-addressed; an id that depends on the interpreter is not content-addressed.
  - **D2 (D#123): `state-noop`'s realization by the positive operators is accepted**, recorded in the catalog and named on the page. NEGATIVE_SPECIFICATION Remark 11.9(b): a perturbation that duplicates a positive operator is retained only where the codomain-total guarantee needs it, and a two-sign run includes both positives.
  - **D3 (D#121–#123): a premise comes from observation or the operator is named unsupported.** NEGATIVE_SPECIFICATION Def. 11.10 (Fork 2): a perturbation is generated only where every observed type admits it, so it never raises and never mis-attributes. `field` is built where the baseline observes the record's shape (Prop. 11.14 measured an instance). `class`, `clamp` and `state-extra` have no premise an observation supplies; they stay unsupported, and a two-sign COMPLETE names them (D#140 item 3; COMMUNICATING_DETERMINISM §4).
  - **D4 (W#37): observed narrowing, plus drop-one for tuple handlers.** The same Fork-2 rule: the target is a type the handler was observed to catch; a fixed subclass is invented and refused.
  - **E1 (D#82): go.** Already ruled (ENGINEERING_PASS §6 items 4, 7, 8; the issue's body).
  - **E2 (D#135, 9.2): retain the test when the basis is unavailable.** TEST_SUITE_CLEANUP_CONTRACT: unknown impact retains the test. No graph is invented.
  - **E3: no deferred addition starts before Waves 1–3 are accepted.**
  - **E4 (release order and timing): the founder's.** Not derived.
- [x] 14.4 Save a resumable checkpoint with the complete live 89-issue mapping, accepted/subset versus outstanding work, the preserved certificate worktree edit, publication receipts, owner premises, dependency order and a procedure for newly discovered defects (docs/RESUME_PAIRED_REPAIR_2026-10-24.md).
- [x] 14.5 (2026-10-26) Every open issue in both trackers was checked against Detective d2750f7 / Wesker 2fbd029:
  - 45 bodies were rewritten to their current state, and 27 were re-verified as written with a dated comment;
  - closed with re-verified evidence: Wesker#47, Wesker#31 and D#112;
  - D#115 was reopened, because `diagnose --two-sign` drops `--two-sign`;
  - filed: D#145, plus D#142 item 4;
  - filed Wesker#55, which escalates D#127: under `--isolated`, an argument-writing mutant alters a shared parametrize row, and later failures count as kills. An identical mutant was reported killed, and `converge --isolated` printed COMPLETE.

  The queue's issue records are synced with GitHub (`issue_audit_2026_10_26`), and the index issues carry the 2026-10-26 checkpoint. Not accepted by this: anything a body marks "not re-run" or "not verified".
- [x] 14.6 (2026-10-26) `docs/REPAIR_WORKFLOW_2026-10-26.md` orders the 84 open issues into waves and lanes, with the founder decisions each one waits on, and with which part of an issue each wave lands. `scripts/sync_repair_queue.py` keeps the queue's tracker facts (title, state, body hash, close reason, the comment posted with a close) equal to the trackers. It never records an acceptance (`--accept` with a receipt does), never places an issue (`--map` does), and exits 0/1/2/3 for in sync / drift / could not ask / a reader is needed. The 14 acceptances its first version had inferred from closures were re-recorded from their closing comments' evidence, with the old pointers kept in `receipt_history`. `record_disposition` is pinned COMPLETE 33/33; integration is covered by `tests/test_sync_repair_queue_intent.py`'s `main`-level tests.
