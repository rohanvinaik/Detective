# Detective + Wesker — Build-to-Completion Plan (2026-07-13)

## North Star
Detective is **SymbolicSpellCheck for code**: point it at a function → discover the complete
behavioral map via Wesker mutation → **Zone 1** (provable & unique) auto-emit code/decomposition +
the free minimal-complete pytest suite; **Zone 2** (partial) surface what it knows + the exact
residual the user/agent must decide; **Zone 3** (can't exercise) hand the tiny residual off.
CPU-only, deterministic, offline. **Guarantee: never silently change working behavior** — all
failure confined to *non-recovery*, never *destruction*. Detective DISCOVERS what exists; it never
decides intent. Serena is a dev-time audit oracle only — NEVER a Detective dependency.

Full thesis + isomorphism: `~/.claude/.../memory/project_detective_vision_crystallized_2026_07_13.md`.

## Cross-cutting protocol (every phase)
- **Dogfood** before AND after every function change (profile with `detective`; engine-core that
  can't self-profile is guarded by the Wesker suite + a sample-target profile that exercises the change).
- **Never hand-write** Detective/Wesker tests — run `converge`; if it can't, fix input synthesis.
- **Serena** = dev-oracle cross-check only, never imported, never in `pyproject`.
- Auto-apply only where deterministically correct; else propose; never delete without confirm.
- The **clean-room fresh-user sim** (`pip install` → toy repo → CLI) is the acceptance gate.
- **push / PyPI are USER-ONLY.**

## Phases (agreed order — operators first)

### Phase 0 — Protocol & baseline (no product edits)
- Dogfooding harness + Serena dev-oracle wired; `.serena/` gitignored in Detective.
- Clean-room frozen as the acceptance harness. Wesker + Detective suites green as BEFORE baseline.

### Phase 1 — Missing operators (Wesker; cheap, additive, first) — ✓ DONE 2026-07-13
Added: identity/membership (`is`/`in`), aug-assign (`+=`), direction-flip (`<`↔`>`, as
orthogonal DOF — closes a false-SC=1 hole), and STMT category (`ast.Expr` deletion, new
MutationCategory threaded through 7 Wesker sites + Detective oracle_light). Wesker 83 green,
Detective 252 green. Uncommitted. LintGate-Detective audit of the new AST functions was
crash-dominated (input-reach wall) — value-correctness verified by real-AST dogfood + the
`len(keys)==_count_targets` alignment invariant.

- Add: identity/membership comparisons (`is`/`is not`/`in`/`not in`), comparison direction-flip
  (`Lt↔Gt`), general statement deletion, augmented-assignment (`+=` …) mutation (confirm coverage first).
- Per operator: sample target that uses it → profile BEFORE (blind spot) → add → profile AFTER
  (mutant appears) → Wesker suite still green → converge any new Wesker tests.
- **Accept**: new operators generate mutants; no regression in Wesker's own kill rate.

### Phase 2 — Input-reach by discovery (THE main gap; leverage) — ✓ DONE 2026-07-13
New `Detective/call_sites.py::discover_call_site_inputs` (stdlib-only, no execution, no Serena
dep) harvests real literal call-sites from the repo. Wired into the two live `_input_grids`
consumers: `classify_survivors` (witness) + converge's `_golden_properties` (golden). Result:
`process_orders` went 0 tests → `✓ COMPLETE mutant+line-complete`, 18/25 killed, minimal 1-test
suite pinning the real output. Detective 252 / Wesker 83 green. `preserves_behavior` found DEAD
(zero refs) — flag for Phase-3 removal-with-confirm.
HONEST EDGE (→ Phase 3): with thin real-call coverage, boundary/branch DOF the calls don't
exercise (e.g. `qty>0` with only qty=2 seen) are labelled "provably equivalent" — an OVERCLAIM
(really "no distinguishing input tried"). The completeness gate must distinguish provably-equivalent
from not-exercised, and surface the latter as Zone-2. MVP bounds: positional+literal args only,
no cross-call cache, no structural boundary-neighbor synthesis.

- `discover_inputs(target, project_root)`: stdlib-`ast` walk of the repo, resolve `Call` nodes to the
  target, extract argument expressions → concrete values / `SourceExpr`. The honest spec of real use.
- Rank/merge: discovered call-site inputs FIRST, annotation-synth SECOND, scalar grid LAST; add ±1
  boundary neighbors to numeric discovered values (keeps BOUNDARY kills).
- Wire into `_input_grids`, `candidate_inputs` (witness), `representative_site` (golden site).
- Zone-3 honesty when nothing exercises the fn (surface the specific residual).
- **Accept**: clean-room `process_orders` converges to a non-empty, exercising suite (today: 0 tests).

### Phase 3 — Completeness-gated proof (trust spine) — ✓ DONE 2026-07-13
Honest equivalent classification: "provably equivalent"/"no test can kill" → "candidate-equivalent
(UNPROVEN)" + Zone-2 action; "✓ COMPLETE" only when nothing candidate-equivalent remains. Vacuous-proof
FIXED: `_suite_green` now runs the TARGET's own covering suite (gated on `line_complete`), not project-wide
`count>0` — demonstrated decisively (proj2 proves with a real call-site; proj3 REFUSES to prove in Zone-3
despite an unrelated passing test). Dead `preserves_behavior`+`_build` removed. Decompose reworded to the
INFORMATION-CONSERVATION frame (the "gap" is a feature: surfaces hidden bugs, never introduces them). Detective
253 / Wesker 83 green. LintGate-Detective audit flagged the new `call_sites.py` as 0-tests (→ Phase 5).

- `decompose_apply._suite_green()` → gate on the suite actually COVERING THE TARGET (Wesker
  line-coverage), not project-wide `count > 0`.
- `preserves_behavior` `exercised` guard → require the EXTRACTED BLOCK's lines exercised.
- Make the three zones explicit in CLI; replace unqualified "behavior-preserved" with warrant-scoped
  verdicts ("PROVEN: N inputs exercised the block" vs "UNPROVEN — residual: …").
- **Accept**: the vacuous-proof clean-room case (decompose with only an unrelated test) now ABSTAINS.

### Phase 4 — Packaging / fresh-user (audit criteria 1 & 2)
- Bump Wesker `0.1.0 → 0.2.0`; pin Detective's dep to a tag/version (kill floating `.git`).
- Make pytest a runtime dep (or refuse to claim a wired suite when absent + clear message); fix the
  wiring misdiagnosis ("check import path" when pytest is just missing).
- Fix contradictory `✗ INCOMPLETE / 0% killed` vs `✓ functionally complete` headline.
- USER pushes local Wesker (`23c37a0`) to GitHub; I prep everything.
- **Accept**: clean-room `pip install` → `detective --help` works → converge runs e2e (today: ImportError).

### Phase 5 — Self-referential proof (dogfooding closure)
- Regenerate Detective's own suite via `converge`; retire hand-written `*_native.py` where covered.
- **Accept**: Detective's suite is converge-generated — the tool has proven itself on itself.

## Critical path
`0 → 1 → 2 → 3`, packaging (4) staged for the USER push, self-suite (5) last (needs 2 done).
User intent enters at Phase 2 Zone-3 residuals and Phase 3 Zone-2 surfacing — structural, by design.
