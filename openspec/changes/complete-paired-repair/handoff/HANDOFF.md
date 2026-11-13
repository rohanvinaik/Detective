# Handoff: the paired repair, from the cloud session of 2026-11-11 to 2026-11-13

Read this first, then `LANE_BRIEF.md` beside it, then `AGENTS.md` in each repo and `tasks.md` row 14.3a.

The founder's standing instructions, in force:

- **Every open issue in both trackers is in scope.** This includes #72, #74, #79, #90, #97, #135, #136, #137, #146 and #147. Build them; do not label them research or defer them.
- **Decisions are derived from the theory, not asked for.** `tasks.md` 14.3a records each one with the text that decides it. Release timing is the founder's (E4); nothing is published.
- **Build on `main` in both repos.** Never create or push a side branch. A local worktree for a parallel lane is fine.
- **Don't patronize, don't downplay the founder's work, don't stop to offer menus.** Close an issue only after its acceptance is re-run on current code, with the evidence in the closing comment.

## 1. Where the code is

| repo | `main` (pushed) | what is NOT on `main` yet |
|---|---|---|
| Detective | `f393268` (lock pins Wesker `2e4865b`) | `patches/detective/1-cleanup` (11 commits) |
| Wesker | `2e4865b` | `patches/wesker/1-cleanup` (4), `2-wave4a` (5), `3-wave4b` (4) |

Every commit in `patches/` was committed in a lane worktree and passed that lane's own gate: the touched files and the guard files, under CPython 3.14 and 3.12 with `PYTHONUNBUFFERED` unset. None has been through a cross-repo batch gate. Landing them is step 1 below.

### What each patch series carries

**Wesker `1-cleanup`**, applied on `2e4865b`:
- **#45/#39:** a resident-memory watchdog bounds a mutant where the OS refuses `RLIMIT_AS` (macOS). `memory_bound` reads `rlimit` / `watchdog` / `none`, and the page names it. On Linux with the rlimit refused (simulated), the worker peak went from 4074 MB to 237 MB. Polling costs 6.2 µs per read, 0.03 % of a core.
- **#28:** a cycle through a thread the code under test starts is refused by name instead of waited into (`record_thread_starts` in `interrupt.py`). The suspected `_baseline_failures` false-kill window was checked: none exists, and a test proves it.
- **#20:** `trace_cache.test_fingerprint` canonicalises the test identity and leaves installed-package fixture files out, matching Detective `644c3ac`.

**Wesker `2-wave4a`**, applied after `1-cleanup`: the μ⁻ families.
- **#44, #120–#123:** every Def. 11.8 operator is built or realized: 36 built, 2 realized, none unsupported.
- **The premise of each operator is OBSERVED.** `Wesker/codomain.py::observe_codomain` records returned values per return line, exceptions, and argument state before and after. An operator is generated at a site only where it applied to every observed value, did not raise, and changed at least one.
- `run_function_profiling(..., two_sign=True)` is a real parameter, and typing is by return site.
- `MutationPolicy.unbuilt` is a field, and profile results carry `mu_minus_withheld` per function.
- The raise-inject kill class reads as `reach_class` (`kill_class_of_dimension`).
- **Policy:** the two-sign id moves (`9+neg.6035bc2f613d` → `9+neg.7a3fc088c5ec`); the one-sign id is unchanged. The Wesker suite gave 2385 passed (3.14).

**Wesker `3-wave4b`**, applied after `1-cleanup`, on the same base as 4a:
- **#48:** a canonical, interpreter-independent serializer for mutant ids, with an exported old-id → new-id mapping.
- **#53:** SWAP never transposes identical operands.
- **#37:** the EXCEPTION operator narrows a handler to an observed subtype, or drops one member of a tuple handler.
- **#22:** a per-site census, each mutant joined to its site, and a detection/contract kill ledger.
- **#30 (annotation sites counted `withheld(annotation)`) was NOT reached.**
- **Expect conflicts with 4a** in `CHANGELOG.md` and the `tests/test_policy.py` golden ids: both lanes move the policy id. Resolve by regenerating the golden from the merged tree; never hand-pick one side's id.
- **This lane stopped before writing its report, so check the following yourself:**
  - whether each commit message's "NOT closed" paragraph covers what remains;
  - #22's acceptance item by item;
  - the Detective consumer change #48's flag migration needs. Detective's `.detective/equivalents.json` records flags by mutant id; after #48 they must be mapped through the exported old → new function. A record that cannot be mapped is named, never dropped.

**Detective `1-cleanup`**, applied on `f393268`:
- **#95 is done:** `FAULT_OPEN` is empty. Every fault flag is read directly where its type declares it, or three-valued with `ABSENT` handled. Typing `Protocol`s are added for the duck-typed results.
- **#94: one field remains,** `TargetBinding.receiver_params`. About fifteen sites re-derive the self/cls skip by parameter name: route each through the computed field, delete `binding.strip_receiver_args`, and regenerate the `classify_target` golden by rm + converge.
- **Already done in the series:** `RemovalReport` views computed from `outcomes`; `FileIdentity`, `RevisionId`, `PlanResolution.file` and the unwired adequacy benchmark retired; `ExecutableProperty.confidence` / `.source_lenses` deleted, with old `pins.json` files still loading.

**`wip/`: two unfinished diffs, NOT tested, for reference only.**
- `detective-sole-detector-UNFINISHED.diff`: a removal must never delete a test that is the only detector of a survivor the certificate leans on. Seen on #143's fixture: `audit` offers `--remove` for `test_atomic_write_text_writes`, the only detector of the refused floor survivors.
- `detective-146-emitters-UNFINISHED.diff`: the first edits toward #146's template emitters.

## 2. How to land and gate (the procedure that worked)

1. **Apply the series.** In Wesker, `git am` the series in order (1, 2, 3), resolving the policy golden as above. In Detective, `git am patches/detective/1-cleanup/*`.
2. **Before a lane commits, run the guard files** (see `LANE_BRIEF.md`, Addendum 4). Detective's are `test_consumer_distinction_intent`, `test_field_consumption_intent`, `test_absorbed_rename_intent` and `test_pinned_decision_consumption_intent`. Every new field on a result type goes to every test double of that type across `tests/`; this cost the most rework when skipped.
   - Known: Detective's `test_absorbed_rename_intent.py::test_no_registry_entry_names_something_the_pair_now_declares` will fail once Wave 4a's Wesker lands, because `bound` is now declared by Wesker. Update the registry entry it names.
3. **The batch gate.** Wesker's suite under 3.14 and 3.12; then Detective's full suite against the local Wesker under 3.14 and 3.12. Always run with `env -u PYTHONUNBUFFERED`: CI's stdout is a block-buffered pipe, and an exported `PYTHONUNBUFFERED` hid an ordering defect that failed all six Wesker CI cells. The 3.12 environment must not live under `/tmp`, because `tests/conftest.py` evicts modules from the temp dir.
4. **Push in pair order.** Push Wesker `main`, then `uv lock --upgrade-package wesker`, then `uv sync --locked` in both environments, commit `build: uv.lock pins Wesker <sha>` with what that Wesker carries, and push Detective. Read CI on both: six cells each, plus SonarCloud for Wesker.
5. **Update every issue the batch touches.** Close the ones whose acceptance re-runs green on the pushed `main`, and say what remains on the others.

## 3. What remains, in dependency order

1. **Land the patches** (section 2), then finish **Wave 4 on the Detective side:**
   - Replace Detective's codomain harvest with `Wesker.codomain.observe_codomain` (`Detective/engine.py`, the `capture_return_types(original, pool, …)` call, and the re-observation in `_consulted_codomain`). Until then, `--two-sign` generates none of the premised operators.
   - Read `MutationPolicy.unbuilt` / `mu_minus_withheld`, and name them on a two-sign COMPLETE (#140 item 3, #120–#123 page side).
   - Assert the extended universe in Detective's two-sign tests (#44 AC3).
   - The #48 flag migration consumer.
   - Read #22's detection/contract ledger.
   - Wesker #30 (annotation census).
2. **Beside Wave 4,** on disjoint files:
   - **#136:** sweep and parametrized-row editing over the single-edit removal transaction.
   - **#72:** a per-type constructor registry and captured-object fixture emission.
   - **Wave 5:** #82 (`.detective/` on SQLite), #81, #73, Wesker #20's remainder, #21.
   - **#146:** the five template emitters. Each refuses by name when its precondition fails, has a discharge test, lands only through `receipt` + `verify-rewrite`, and has a `--json` record.
3. **The cleanup remainder:**
   - #94 `receiver_params` (above);
   - the sole-detector removal rule (above);
   - #97 `detective explain <target> <MUTANT_ID>`;
   - #89's remaining items: U4 (a written test that kills nothing), U3 (the unsound-float ending), `match=` for message-only exceptions, the samples-store `repr` round trip, a routing failure on diagnose/audit/doctor, the harvest's `testpaths`, plan's ledger ignoring certificates;
   - #110's reach half;
   - #98's converge/audit disclosure line;
   - #100's last cause (a `pyproject.toml` marker edit changes the regime digest, so the next run misses the cache);
   - `verify-rewrite` listing refused-floor members as abstentions;
   - audit calling a test of unobserved reach redundant;
   - `audit --plan` printing the bare function name.
4. **One re-pin sweep, after Wave 4,** under the final policy id: every certificate and generated suite in both repos. Pins taken before Wave 4 go stale. Owed since then, at minimum:
   - **Wesker:** `install_standing`, `memory_cut_run_standing`, `harness_slowdown`, `form_b_output_modes`, `canonical_test_identity`.
   - **Detective:** `engine_ownership`, `memory_cut_text`, `memory_cut_remedy`, `ungateable_standing`, `unresolved_gate_standing`, `environment_route`, `audit_writes_text`, `real_gaps_text`, `audit_headline_verdict`.

   Pins cut under machine load are not defects; re-run them on an idle machine.
5. **Capabilities,** two lanes at a time on disjoint files:
   - **#135:** certified negative residuals over explicit domain bases.
   - **#74:** drop-to-synthesis for undischargeable obligations.
   - **#137:** construction contracts and the Wesker operator-catalog export; the proposal and design are in `openspec/changes/declare-construction-contracts/`.
   - **#90:** effect contracts. The world is an explicit input, and five archetypes are run against the commits before each historical fix.
   - **#147:** measured composition costs. Interface mutants at a candidate seam give γ (NEG_SPEC Thm 15.2: γ ≤ |InterfaceMutants|); σ per component comes from a materialized trial copy (`tasks.md` 8.3); proxy, measured, bound and unavailable are kept distinct.
6. **Wave 6, performance.** Benchmarks first (Wesker #43, Detective #132), then the changes they justify: Wesker #40–#42, #33, #25; Detective #83, #84, #87, #130, #131. Also #75 and #85.
7. **#79,** the worked example, as a doc beside the README. The README stays the founder's.
8. **The macOS legs**, now runnable on the founder's machine:
   - the watchdog on real macOS (#45/#39);
   - `taskpolicy -b` and the Mac Pro run of the SAME check (Wesker #27, Detective #80);
   - Detective #138.
9. **Close-out:** release readiness (#88, #35) and the index issues (#99, #102, #133, #36).

## 4. Facts that cost time to learn

- **Never name a mutant by a literal content id in a test.** Ids differed between 3.12 and 3.13+ until #48. Find a mutant by what it changes.
- **The self-measurement badge run (`spec-full.yml`) is sharded:** a plan job, four shards and an aggregation. Its last run on `8fcadfe` fitted in time; every shard then failed for reasons since fixed: an observation crash, an out-of-memory kill, and the execution-mode fallback. Its next run is the evidence for Wesker #29.
- **A function the measuring engine itself runs (Detective or Wesker code) is now measured isolated** (Detective `0346890`). Converge on the pair's own functions is correct but slower.
- **Lanes worked best one issue family per commit,** with the guard files run before each commit, the test doubles updated in the same commit, and one batch gate per landing rather than per lane.
- **Integration rework came from parallel lanes editing the same files** (`cli.py`, the result types, the guard registries). Run lanes in parallel only on disjoint files.
