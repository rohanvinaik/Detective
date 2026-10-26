# Repair workflow — the open work, in order (2026-10-26)

This is the run order for the 84 issues open on 2026-10-26: 54 in Detective and 30 in Wesker. It is written
for an agent picking the work up cold. It does not restate the issues. Each issue's body was brought to its
current state on 2026-10-26, against Detective `d2750f7` and Wesker `2fbd029`. Read the issue and do what
it says; this file only says **in what order, in which lane, behind which decision, and how a wave is
accepted**.

**Sources of truth, in order:**
1. The issue itself: its top block is the current state, and its acceptance section is the bar.
2. [`openspec/changes/complete-paired-repair/tasks.md`](../openspec/changes/complete-paired-repair/tasks.md), the work packages B00–B12.
3. [`docs/REPAIR_QUEUE_2026-10-24.json`](REPAIR_QUEUE_2026-10-24.json): the issue-to-package map and its dependency rules.
4. `AGENTS.md` / `CLAUDE.md`: the per-issue loop, the gates and the commit essay. Everything there applies here and is not repeated.
5. `docs/theory/COMMUNICATING_DETERMINISM.md`, before any change to what a page prints or which exit code it returns.

When this file and an issue disagree, the issue wins. Fix this file in the same wave.

## The order: by which promise a defect breaks

| Class | Promise broken | Waves |
|---|---|---|
| (a) | A COMPLETE, a kill or an "equivalent" that is false. **Every evaluation must be independent of the others.** | 1 |
| (b) | A page that says something false: a wrong next command, a gap that is not one, "NO tests" over five | 2 |
| (c) | The release badge: Wesker's spec-full self-measurement | 1 (W#52), then 3 |
| (d) | Robustness of measurement, B01–B03 | 3 |
| (e) | The declared operator basis, B06. Decision-gated, with one policy bump | 4 |
| (f) | Durable state and safe removal, B07/B08 | 5 |
| (g) | Performance, B09/B10. **Benchmarks first** (B12 13.7) | 6 |
| (h) | New capability (`DEFERRED_ADDITION`), tracking and release issues | out of scope until the founder says go |

## Wave 0: before any code

1. **Setup.**
   - Prove that the local pair resolves (AGENTS.md "Standing invocation").
   - Read the protocol, COMMUNICATING_DETERMINISM and ARCHITECTURE §11.
   - Run `python3 scripts/sync_repair_queue.py`: it must exit `0` (in sync). Exit `1` is drift, which `--write`
     repairs. Exit `3` is a placement or an acceptance that only a reader can supply.
2. **Decisions.** Ask the founder in the batches below, at most four questions per AskUserQuestion. Batch A
   goes before any Wave-1 push. The others go before the wave that needs them.
   - Work that no ruling gates proceeds meanwhile.
   - Present the evidence and the options. A "lean" below is a recommendation, never a settled default.
   - Record each ruling as a comment on its issue, and in `tasks.md` 14.3.

| # | Decision (issue) | Blocks | Options (lean) |
|---|---|---|---|
| A1 | How W#55 makes evaluations independent, and whether that changes "the meaning of fresh reproducibility" (a queue owner decision) | W#55's push; D#127, D#108 closes | (A) fresh test arguments for every evaluation, in both modes; (B) an original control in the isolated worker, so a failure the original also produces is never a kill; (C) both. *Lean: C.* A removes the leak; B guards whatever shared state a copy cannot reach (module globals, class attributes, files). |
| A2 | Refuse `flag … equivalent` for a mutant the search's own witness crashes, or the suite detects (D#110, D#113) | D#110's push | Refuse; refuse unless `--fence`; keep. *Lean: refuse `equivalent` and keep `--fence`.* This narrows `_run_flag`'s deliberate "crash-killed is flaggable" invariant, so it needs a veto question. |
| A3 | Compute the redundant set from the full kill matrix (D#145) | D#145's push | Full matrix (`record_all_killers`) wherever a redundant set is printed or acted on; full matrix for `--remove` only; a canonical test order with first-killer recording kept. *Lean: the first option, over the one function's own tests* (the cost scales with that function's suite). |
| A4 | Close D#113 as a duplicate of D#110, with its fixture as an acceptance case. Separately: the `--remove` page that ends `DONE` over open real gaps (comment on D#142): a defect, or deliberate? | D#113's close; that D#142 sub-item | *Lean: duplicate. Lean on the page: the audit ladder's directive stays the page's last directive while the measurement is incomplete.* |
| B1 | W#29: the 180-minute limit | W#29's close only; W#52 proceeds | Raise it; shard the badge run (a matrix of file groups plus an aggregation job); redefine the acceptance. *Lean: shard*, since a whole-codebase run scales with the codebase (ARCHITECTURE §11). |
| B2 | Ratify the step-budget constants k = 32 and F = 10,000 (W#27; the queue's "step-cap parameter warrant") | W#27's close; D#80 (2) | Ratify (the calibration found 0 of 3,176 observations misfiled), or re-calibrate. |
| B3 | W#28 D2: measure engine-running tests in-process? | W#28's close | Build delegated re-entrancy; or keep the named refusal and the `--isolated` route, which works today (29/29). *Lean: keep.* |
| B4 | A memory-cap stop is a named non-gateable cut (W#21's design), but W#45's acceptance says "memory-bounded kills" | W#45/W#39 acceptance wording | Amend the acceptance to "named cut"; or score as a kill. *Lean: amend.* |
| C1 | W#54: how the rollup names harness dispositions | W#54 | A harness line beside the kill rate; or the exclusion stated on every summary that prints a ratio. |
| C2 | W#31 (closed): should an unscreened remainder make a result non-gateable? | nothing open; a follow-up issue if yes | Gate; name only. |
| C3 | D#143: refused survivors that a test detects by crash | D#143 | A named floor now ("COMPLETE modulo N …", with its policy); or a sandboxed speculative run. And: does the strict gate's 2026-10-25 standing rule extend to them? *Lean: the floor now, the sandbox later as a deferred addition.* |
| D1 | W#48: interpreter-independent mutant ids | W#48; the Wave-4 policy bump | Our own canonical serializer, plus a `POLICY_VERSION` bump and a one-time flag migration; or keep two id families. |
| D2 | D#123: does `state-noop`'s realization by positive operators meet Def. 11.8 (viii)? | D#123's close | Accept, recorded in the catalog and named on the page; or build an OUTPUT sub-mode. |
| D3 | Missing structural and effect operator premises (D#121 field/class, D#122 clamp, D#123 state-extra; a queue owner decision) | those generators | Supply the premises; or record them as permanently unsupported, and say so on a two-sign COMPLETE (D#140 item 3). |
| D4 | The broad-handler narrowing target rule (W#37; tasks 7.4; a queue owner decision) | W#37 | Supply a rule; or keep the semantic witness and refuse to invent a subclass. |
| E1 | D#82: move `.detective/` to SQLite (tasks 8.1) | D#82; W#20's storage half | Go; no-go. |
| E2 | The code-kappa graph / domain basis (a queue owner decision; tasks 9.2; D#135) | B08 9.2 | Supply it; or keep retaining tests when the basis is unavailable. |
| E3 | Start any deferred addition? (D#72–#74, D#90, D#97, D#109, D#135–#137, W#25's static half) | each one | *Default: none until Waves 1–3 are accepted.* |
| E4 | Release order and timing (D#88, W#35; the founder's domain) | the release | Wesker first, then Detective with a raised floor (see "Release fact" below). |

## The table: every open issue

Read the columns this way:
- **Lane** is file ownership (next section).
- **Gated** names a Wave-0 decision, a **veto** (a pinned ladder or deliberate invariant changes, so put one veto question to the founder before the push), or a **policy** change (the operator universe or the policy id moves).
- **Tasks** is the `tasks.md` row the work checks off.

| Issue | Wave | Lane | Depends on | Gated | Tasks |
|---|---|---|---|---|---|
| W#55 | 1 | WX | — | A1, veto (kill counts change) | 3.5, 4.2 |
| D#127 | 1 | DC | W#55, lock bump | — | 3.5 |
| W#49 | 1 | WX | — | policy? Check whether resetting the stale wrapper per test moves the two-sign id | 7.3 |
| D#110 | 1 | DC | — | A2, veto | 6.1 |
| D#113 | 1 | DC | D#110 | A4 | 6.1 |
| D#145 | 1 | DC | — | A3, veto | 9.5 |
| D#86 | 1 | DC | — | — | 4.3 |
| D#104 | 1 | DC | D#145 | — | 4.3 |
| W#52 | 1 | WB | — | — | 2.5b |
| W#29 | 1→3 | WB | W#52 | B1 | 2.5, 2.5a, 2.5b |
| D#144 | 1 | DG | — | — | 11.3 |
| D#138 | 1 | DG | D#144 | — | 11.3 |
| D#85 | 1 | DG | — | — | 11.3 |
| D#115 | 2 | DP | — | — | 6.3 |
| D#142 | 2 | DP | — (item 2's Wesker half is W#53) | A4 (the DONE page) | 6.1 |
| D#89 | 2 | DP | — | — | 6.1 |
| D#101 | 2 | DP | — | — | 6.1 |
| D#134 | 2 | DP | — | — | 5.1 |
| D#76 | 2 | DP | — | — | 3.6, 6.1 |
| D#140 | 2 | DP | item 3: Wesker exposes `negative_policy.unbuilt` as a field (WO) | — | 6.1, 7.3 |
| D#96 | 2 | DP | — | — | 6.1 |
| D#98 | 2 | DP | — | — | 6.4 |
| W#45 | 2 | WB+DP | — | B4 | 1.4 |
| W#54 | 2 | WB | — | C1 | 5.1 |
| W#17 | 2 | WT | — | — | 2.4 |
| D#107 | 2 | DR | — | — | 4.4 |
| D#77 | 2 | DR | — | — | 4.1 |
| D#93 | 2 | DG | — | — | 6.4 |
| D#94 | 2 | DG | — | — | 6.4 |
| D#95 | 2 | DG | — | — | 6.4 |
| W#32 | 3 | WT | — | — | 2.2, 2.3, 2.4 |
| W#28 | 3 | WT | — | B3 | 2.4 |
| W#27 | 3 | WX | — | B2 | 2.6 |
| D#80 | 3 | DC | W#27 | B2 | 2.6, 2.6a |
| W#18 | 3 | WX | — | — | 4.1 |
| W#46 | 3 | WX | — | — | 4.2 |
| W#50 | 3 | WX | — | — | 4.2 |
| W#39 | 3 | WX | W#45 | B4 | 1.4 |
| D#108 | 3 | DC | W#55 | — | 3.5 |
| D#143 | 3 | DC | — | C3 | 3.4a |
| D#100 | 3 | DS | — | — | 8.2 |
| W#53 | 4 | WO | — | policy (bump with the rest of Wave 4) | 5.1 |
| W#48 | 4 | WO | — | D1, policy | 5.2 |
| W#30 | 4 | WO | — | policy | 5.3 |
| W#22 | 4 | WO | W#30 | — | 5.3 |
| W#44 | 4 | WO | — | D3, policy | 7.1, 7.2, 7.3 |
| D#120 | 4 | WO | — | policy | 7.2 |
| D#121 | 4 | WO | — | D3, policy | 7.2 |
| D#122 | 4 | WO | — | D3, policy | 7.2 |
| D#123 | 4 | WO | — | D2, D3, policy | 7.2 |
| W#37 | 4 | WO | — | D4, policy | 7.4 |
| W#20 | 5 | WS | — | E1 (storage half) | 8.2 |
| D#82 | 5 | DS | — | E1 | 8.1 |
| D#81 | 5 | DS | — | — | 8.3 |
| W#43 | 6 | PF | — | — | 13.7 |
| D#132 | 6 | PF | — | — | 13.7 |
| W#40 | 6 | PF | W#43 | — | 10.1 |
| W#42 | 6 | PF | W#43 | — | 10.1 |
| W#41 | 6 | PF | W#43 | — | 10.2 |
| W#21 | 6 | PF | W#43 | — | 10.3 |
| D#83 | 6 | PF | W#21 | — | 10.2 |
| D#130 | 6 | PF | D#132 | — | 10.4 |
| D#131 | 6 | PF | D#132 | — | 10.3 |
| W#33 | 6 | PF | W#21, W#20, D#81 | — | 11.1, 11.2 |
| D#84 | 6 | PF | D#85 | — | 11.3 |
| D#87 | 6 | PF | W#27, W#33, D#83 | — | 10.4 |
| W#25 | 6 | DP | — | E3 (the static-subsumption half only) | 10.3 |
| D#75 | 6 | DG | — | — | 13.5 |
| D#72, D#73, D#74, D#90, D#97, D#109, D#135, D#136, D#137 | — | — | — | E3 | — |
| D#79 | — | — | — | founder (the README is the founder's) | 13.6 |
| D#88, W#35 | — | — | — | E4 (release) | 1.3, 1.4, 13.x |
| D#99, D#133, W#36, D#102 | — | — | — | index: a comment per wave | 14.3 |

**A wave lands a portion; an issue closes only on its whole acceptance.**
- A wave that meets part of an issue lands that part, updates the issue's status block with what remains, and
  leaves the issue open.
- A `tasks.md` row is checked only when its whole text is accepted. A partial gets a dated sub-row, as
  2.5a/2.5b, 3.4a/3.4b and 6.1a/6.1b do.

These issues are addressed only in part by the wave in their row:
- **D#110.** Wave 1 lands the false-equivalence portion: `flag` refuses an `equivalent` that a known input
  distinguishes, and a mutant the suite detects by crash leaves the candidate class. The reach half is
  deferred with D#109 (E3), and with it the acceptance's "no killable mutant left as a candidate, without
  hand-supplied inputs". D#110 stays open.
- **D#140.** Wave 2 lands items 1, 5 and 6. Item 3 waits for Wave 4: Wesker exposing
  `negative_policy.unbuilt`, and ruling D3.
- **W#29.** Wave 1 lands W#52's half. Acceptance, a completed spec-full run, needs ruling B1 and Wave 3.
- **W#44 and D#120–#123.** Each generator waits on ruling D2 or D3. Until then each issue carries what is
  built and what is unsupported.
- **Several items in one issue, landing separately:**
  - W#17: pre-existing threads, subprocess reach, short-circuit arcs;
  - W#27: the liveness bound, and separately ruling B2;
  - W#28: the start/join gap, and separately ruling B3;
  - W#32: the guard test, the SAME check, and B01 2.2–2.4;
  - W#45 and W#39: macOS reporting, and separately Linux interception;
  - D#80: items (2) and (3);
  - D#89: each listed item;
  - D#142: its four items, and the DONE page behind A4.

**Two cross-issue notes.**
- **Until D#145 lands,** which test is credited with a kill depends on the order the tests ran. Do not cite per-test kill attribution as evidence in another issue.
- **After W#55 lands,** re-measure every receipt taken with `--isolated` on a function that writes into its arguments. Re-pin any certificate whose receipt was isolated, and say which ones changed.

## Lanes and integration

Lanes are file ownership. Lanes run in parallel; one lane edits a hot file at a time.

| Lane | Owns |
|---|---|
| WX | `Wesker/_isolated_worker.py`; `Wesker/engine.py`'s evaluate/install path; `Wesker/mu_minus.py`'s wrapper |
| WB | `Wesker/action.py`, `Wesker/ci.py` (rollup, badge) |
| WT | `Wesker/line_coverage.py`, `trace_evidence.py`, `monitoring.py`, `interrupt.py` |
| WO | `Wesker/mu_minus.py` catalog, `policy.py`, `filter.py`; `engine.py`'s generation |
| WS | `Wesker/trace_cache.py` |
| DC | `Detective/audit.py`, `equivalence.py`, `minimize.py`, `engine.py`'s profile; `cli.py`'s `_run_flag` |
| DP | `Detective/cli.py`'s renderers and action routing, `converge.py`'s next action, `doctor.py`, `regime.py`, `samples.py`, `purity.py` |
| DR | Detective's routing and reach (`engine.py` routing, `kappa.py`, `scope.py`) |
| DG | guards and CI signal (`tests/`, `capture.py`'s flake) |
| DS | `Detective/verdict_cache.py`, `.detective/` stores, `decompose_apply.py` |
| PF | both repos, after the benchmarks exist |

- **One integrator.** Lane agents work in git worktrees and hand back commits. The integrator lands them on
  `main` one at a time and re-runs the gates on the integrated tree.
- **Never hand-merge `tests/detective/certificates.json` or a `*_synth.py`.** Every pin rewrites them. On the
  integrated tree, re-run `converge` for each function a lane pinned, and commit what it writes.
- **Sonar is one shared container.** Run scans one at a time.
- **Parallel runs need independent resources.** Reproduction and verification are not read-only:
  - converge writes generated suites and certificates;
  - every profile writes `.detective/` and `.wesker/` state;
  - an in-process run can leave runtime state behind (D#86).

  Run in parallel only when each run has its own disposable project copy and its own `HOME`, and writes
  nothing into either repository. Otherwise serialize.
- **A Wesker push restarts the 3-hour spec-full run.**
  - Batch Wesker changes. One push per wave is the target, not a cap: a corrective push after a failed
    verification is allowed, and its push question says it restarts the run.
  - W#52 rides the first push, so that run tests it.
  - Iterate W#52 and W#29 on the two-file Docker reproduction, not on CI. The command is in W#29's body.
  - After every Wesker push, bump Detective's `uv.lock` (`build: uv.lock pins Wesker <sha>`), then run
    Detective's suite against local Wesker.
- **One policy bump for Wave 4.** Each universe-changing Wesker change moves `POLICY_VERSION` and the policy
  id, invalidates receipts and flags, and needs a CHANGELOG entry. Land W#53, W#48, W#30 and the μ⁻ operators
  under one bump, not four.
  - The rule batches Wave 4's universe additions only.
  - A Wave-1 correctness fix that moves the policy id bumps it in Wave 1, with its own CHANGELOG entry. W#55
    or W#49 might, since an observation-rule change has moved the id before.
  - Never hold a false-COMPLETE fix back to share a bump.

## Per issue: what AGENTS.md's loop does not already say

1. **Reproduce from the issue's own fixture first.** Every body or comment dated 2026-10-26 names one. Where
   the source is not inline, rebuild it from the description, and post the source as a comment.
2. **Turn the reproduction into the intent test**, so the issue's own failure is what the test pins.
3. **Prove sensitivity, before and after.** With the fix disarmed in a scratch copy, the new intent tests must
   fail; record how many. Keep this check: it is the regression check.
   - A `converge` that reaches COMPLETE over the intent tests is a separate, additional check. It shows the
     tests distinguish every operator mutant of the pure decision.
   - It does not show that they fail on the historical defect, which may lie outside the operator universe
     or in the wiring around the decision.
   - If converge stops with `holder_not_found`, the tests reach the function through a module object no
     installed mutant enters.
   - Bind the function or module under the name `detective regime` reports. `tests/test_sync_repair_queue_intent.py` is the example.
4. **Veto before push** where the table says so.
5. **A verifier who did not implement it** re-runs the acceptance on the integrated `main` before any close.
   It runs the acceptance's own cases, plus null, invalid and edge inputs (AGENTS.md's first recorded failure mode).
6. **Close with evidence, or leave the issue open with its status block updated.**
   - Evidence is the sha, the pin receipt and the measurement.
   - Record the acceptance with `python3 scripts/sync_repair_queue.py --accept Repo#N="<receipt>" --write`,
     written by whoever read the evidence.
   - After any issue body edit, run `--write` (bodies are hashed in the queue). Comments are free.

## Per wave: done means

- Both suites pass, plus Detective's suite against local Wesker. Pinned ruff passes, with the whole-tree
  format check. The pylint delta is empty. The Sonar gate is `OK`, with 0 bugs, 0 vulnerabilities and 0 hotspots.
- One question to the founder before the wave's push, covering both repos and every veto in it.
- CI's test workflow is green on both heads.
  - On macOS, `test_uncontained_execution_marks_contained_false` is D#144, until it is fixed in Wave 1:
    re-run once, and treat a second failure as real.
- **Wesker waves: read the spec-full run on the pushed head through to its end.** Record its outcome on W#29
  and in the wave's D#99 comment.
  - Until W#29 is accepted, a wave is accepted when the run shows no failure beyond the ones already named
    on open issues.
  - A known failure stays visible: named on its issue and in the comment, never reported green.
  - A new failure class blocks the wave until it is named on an issue.
- One docs commit. It checks off the `tasks.md` rows (whole rows only) and runs
  `scripts/sync_repair_queue.py --write`, with `--map Repo#N=SCOPE:B..` for each issue filed in the wave and
  `--accept` for each issue closed in it. It also records the wave.
- A comment on D#99 naming what landed and what did not.

## Pitfalls this session paid for (beyond AGENTS.md)

- **The cwd comes before `PYTHONPATH`.** A `python -c` probe run from a repo root measures that live tree.
  Run probes from a scratch directory, and run CLI reproductions with `HOME` pointed at a scratch home.
- **Keep a recall from masking a change, without destroying user data.**
  - `.detective/pins.json` and `.detective/verdict_cache.json` are regeneratable (`Detective/pins.py`).
    Remove them between runs.
  - `.detective/inputs.json` is user data: `Detective/samples.py` says supplied inputs are never purged. And
    `.detective/` is gitignored, so a deletion cannot be recovered.
  - To measure without recall, run in a disposable copy of the project. Or move the file aside and restore
    it: `mv .detective/inputs.json <scratch>/inputs.json.bak` … `mv <scratch>/inputs.json.bak .detective/inputs.json`.
  - AGENTS.md says the same.
- **A partial trace cache changes the audit's cover** (D#145). Compare runs cold, or with an identical cache.
- **The local Sonar scanner stalls in SCM blame sometimes.** The watchdog exits 137; re-run it, and poll the
  CE task before reading the gate.
- **`--isolated` is not a neutral re-measure until W#55 lands.** For argument-writing functions it can
  certify COMPLETE over mutants no test can kill.

## Release fact (for D#88 and W#35; publishing stays the founder's)

- Detective `main` does not import against the published Wesker 1.2.2.
  `Detective/equivalence.py:45` imports `STEP_BUDGET_FACTOR` and `STEP_BUDGET_FLOOR`, which arrived in
  Wesker `3ca7531`, a commit no tag contains.
- `pyproject.toml` declares `Wesker>=1.2.2`, and the comment at `equivalence.py:43-44` says that floor
  provides both names. On `main` it does not.
- The release order is Wesker first, then Detective with a raised floor. Correcting the comment is fair
  game in any wave; changing the floor is part of the release.

## Tooling

`scripts/sync_repair_queue.py` keeps the queue's tracker facts equal to the trackers (tasks.md 14.3). It
claims no more than that.
- **Facts it maintains:** title, state and body hash. For a closed issue, also its close reason, its close
  time, and the comment posted with the close. That comment is a pointer; the script does not read it.
- **It never records an acceptance.**
  - `accepted_*` comes only from `--accept Repo#N="<receipt>"`, written by whoever read the evidence.
  - A replaced or withdrawn receipt moves to `receipt_history`.
  - A closure that is not a completion (duplicate, not planned) records its reason and claims nothing.
- **It never places an issue.** An open issue the queue does not map waits for `--map`.
- **Exit codes:** `0` in sync; `1` drift (`--write` repairs it); `2` could not ask, or a malformed argument;
  `3` a reader is needed, and nothing is written.
- **What its pin covers.** `record_disposition` is COMPLETE over `tests/test_sync_repair_queue_intent.py`,
  which covers that decision's operators. The integration behaviour (what is written, and when nothing is)
  is covered by the same file's `main`-level tests, not by the pin.
