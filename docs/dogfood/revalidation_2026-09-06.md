# Detective greenfield RE-VALIDATION ledger — arc-dsl / GofL / conorheins (2026-09-06)

Companion run to `pabkit_2026-09-06.md` (the discovery ledger). Purpose: run Detective's ENTIRE
CLI as a greenfield repo owner would — fresh clones, follow the printed instructions literally,
read the FULL STATIC output after each command — to (a) confirm the gaps we already FIXED took at
the surface, (b) re-confirm the status of the findings recorded-but-OPEN, and (c) check full
functionality + UX cleanliness end to end.

## Stance (non-negotiable, from the session discipline)
- **Be the user the tool is for.** Drive through the CLI only; do exactly what the `DO THIS` says,
  in sequence; never route around it with tribal fluency. The tool is meant to be run by a person
  or agent literally reading its output — so following the printed next action IS the test.
- **Read full static output**, not streaming, not grep-filtered (progress `\r` frames collapsed to
  the final frame). Exercise EVERY component, not just converge — sibling-path divergence (Finding
  E) only shows if you run the siblings.
- **A finding is a broken/misleading BEHAVIOUR** — a spiral, a wrong next action, a sibling-path
  divergence, a couldn't-measure state rendered as a result. NEVER "jargon is dense" or "it used an
  absolute path" (both struck for calibration in the discovery ledger).
- **Observe / validate only.** Diagnose causes with the two-step (shared-PRODUCER trace, not the
  edited symbol); record status here. NO code changes without founder go-ahead — surface first.

## Harness (proven this session)
- Engine = LOCAL Detective+Wesker via `PYTHONPATH=$PP` (proven: resolves to `/Users/rohanvinaik/tools/...`).
- `PP=/Users/rohanvinaik/tools/Detective:/Users/rohanvinaik/tools/Wesker`
- venv = `scratchpad/dogfood/.venv-det` (pytest 9.1.1 + numpy 2.5.3 + detective console script);
  two-knob proof passed (venv python + PP → local engine).
- Fresh pristine clones in `scratchpad/dogfood_reval/{arc-dsl,GofL,conorheins}` — verified no
  `.detective`/`.wesker` cache dirs present at clone time.
- conorheins deliberately has NO jax/funcy in the venv — that is what makes the `fix_load`
  message meaningful (the load MUST fail and name the dep).

## What we're validating (from the discovery ledger)
FIXED (expect clean at the surface):
- de-spiral next-action routing: `fix_load` / `provide_sample` / naming the missing dep (not the
  catch-all `regime --migrate`).
- `_load_original` names the real import error.
- `detective survey` (the pure-in-impure detector) + usage-based type inference.

RECORDED-BUT-OPEN (expect still live; confirm status, don't be surprised):
- **A** — loud pin→style handoff absent at ✓ COMPLETE.
- **B [HIGH]** — converge ✓ COMPLETE vs audit "N killable": non-reconciling split + loop
  (reproducibility of the candidate-equivalent witness search).
- **C** — verify-rewrite STALE_RECEIPT render (verdict correct; proof-replay row misleading).
- **D** — survey and decompose disagree on the pure-in-impure extraction.
- **E [HIGH]** — de-spiral routing is converge-only; audit's sibling ladder + verify_rewrite keep
  the old bug (the shared-producer addendum).

---

# OBSERVATIONS

_(populated as the walkthrough runs — one section per repo, one entry per command, full static output read)_

## arc-dsl (pinnable scripts repo) — fresh clone `dogfood_reval/arc-dsl`

**Correctness path — de-spiral + BUG C VALIDATED, no spiral.** Full sequence run as a greenfield
owner, reading each static frame:
- `--help` → leads to `regime`. Clean, pedagogical.
- `regime` → `scripts` layout, marker not declared → `DO THIS: regime --migrate`. Exit 0.
- `regime --migrate` → created pyproject.toml (pythonpath=["."], marker registered); re-read regime
  → "resolves cleanly." The BUG C migrate loop is gone at the regime layer.
- `diagnose dsl.py::add` → 48 behaviours, 0 pinned → `DO THIS: converge`. Clean.
- `converge dsl.py::add` (bare, from-scratch): wrote a runnable 4-test suite, 2-line gap remains →
  **`AUTHOR INPUTS`** with the exact uncovered-line conditions + `THEN RUN: converge`. **NOT** the
  old `regime --migrate` loop. **The de-spiral fix took.** (`9/48 killed`.)
- `converge … --input "((1,2),(3,4))" --input "(1,(2,3))"` → **✓ COMPLETE · 35/48 killed** (modulo
  13 unproven-equiv · 14 crash-only). Terminates. Matches the discovery ledger.
- `survey dsl.py` → 0 trapped (the false-positive fix held on a fresh clone — `Numerical`/`Any` not
  flagged). `plan .` → 730 regions, clean static map, constructive regions gated `converge first`.

### FINDING A — CONFIRMED live (loud style handoff absent at ✓ COMPLETE)
converge's ✓ COMPLETE `DONE` block points ONLY to `flag` (to prove an equivalent). No signpost to
the style half (plan / decompose / survey). The correctness half is DONE right here — the exact
moment the style handoff should fire — and it doesn't. Status: unchanged, as filed.

### FINDING B — CONFIRMED live [HIGH], with sharper reproducibility data
On the EXACT 6-test suite converge called ✓ COMPLETE:
- `audit dsl.py::add` #1 → **incomplete · 3 killable mutant(s) no test kills** · 18/42 value-pinned ·
  71.4% · `DO THIS: converge`.
- Followed audit's advice literally → `converge` re-pins **✓ COMPLETE, writes nothing** (no-op loop).
- `audit` #2 → **1 killable** · 19/44 · 72.7%.  `audit` #3 → **1 killable** · 19/44 · 72.7%.

The killable count **wobbles (3 → 1 → 1) and never reaches 0**; even the value-survivor denominator
moves (42 → 44). So it is neither "converge stably misses N real killables" nor "audit is pure
noise" — the candidate-equivalent witness search is non-deterministic run-to-run, so converge's
✓ COMPLETE is NOT reproducible against audit's fresh classify, and `audit → converge` is a genuine
no-op loop that cannot close (audit is read-only; it never persists the witness it found). This is
the discovery ledger's suspected "unstable boundary" cause, now confirmed empirically. The
load-bearing fix remains: make the search reproducible given a fixed suite.

### FINDING C — CONFIRMED live (verify-rewrite STALE_RECEIPT render)
`receipt dsl.py::add` (emits receipt JSON to stdout; progress to stderr — no file written, user
redirects) → captured `arc_receipt.json`. `verify-rewrite arc_receipt.json dsl.py::add` on the
UNCHANGED source → `STALE_RECEIPT`, exit 2. Verdict correct. Two render defects, both as filed:
1. `· proof replay   the original suite ran skipped on the rewritten source` — misleading: no replay
   ran and there is no rewritten source. Should be suppressed on this path.
2. The `DONE` line is DUPLICATED (verbatim two ways):
   `nothing was rewritten — the current source is identical to the receipt's original.`
   `the current source is identical to the receipt's original — nothing was rewritten`

## GofL (inexpressible ndarray param) — fresh clone `dogfood_reval/GofL`

Package `gameoflife/`; regime → flat, migrate (added marker to pyproject) → resolves. Target
`gameoflife/game.py::Game.update_cell` — `update_cell(step, xy)` unannotated, `step[xy[0], xy[1]]`.

**`provide_sample` de-spiral fix — VALIDATED.** `converge` bare → 0/31, and the next action is
`AUTHOR INPUT: … provide a real sample (pass call_site_inputs … or add a literal call site)`, with
an explicit `Why not migrate: the module loaded and the search RAN in-process … regime --migrate
cannot change [that]. A real sample can.` The right escape is named; no migrate loop.

**survey usage-inference (step 2b) — VALIDATED.** `survey gameoflife/game.py` → **2 extractable_core**:
`Game.update_cell` (90) and `Game.count_neighbors` (115) — the `step[xy[0], xy[1]]` tuple-subscript
usage-inference types `step` as ndarray on a fresh clone. Correctly flags for extraction.

### FINDING D — CONFIRMED live (survey ↔ decompose contradiction)
- `survey` → extract the pure decision from `Game.update_cell` / `count_neighbors` (for pinnability).
- `decompose 'gameoflife/game.py::Game.update_cell'` → "skipping low-value extraction `_compute_status`:
  leaves a pure delegating wrapper — not a seam" → **"no separable block. There is no seam here to split."**
The two style tools answer different questions (survey: pinnability seam; decompose: complexity seam)
and silently contradict. A greenfield user told by survey to extract finds decompose won't. As filed.

### FINDING E — CONFIRMED live on the INEXPRESSIBLE axis (audit's ladder)
`audit 'gameoflife/game.py::Game.update_cell'` → `unclassified 31 — the search could not run` →
`DO THIS: converge` · `Why: 11 uncovered line(s) — real gaps, not equivalents` · `Writes the missing
tests`. But converge on this target CANNOT write them (needs a real sample — it says so). So audit:
(a) does NOT surface the `provide a real sample` guidance converge gives, and (b) wrongly promises
"converge writes the missing tests." `_audit_action` never consumes `inputs_expressible`/`needs_sample`
— the sibling-ladder bug, exactly as filed. (Primary unloadable case → conorheins below.)

## conorheins (unloadable module — jax/funcy/matplotlib absent) — fresh clone `dogfood_reval/conorheins`

Target `jax_backend/src/utils.py::str2bool`. Module top-level imports jax + matplotlib + funcy
(NOT in the venv). Repo ships `jax_backend/tests/test_demo_*_smoke.py` that also import jax.

**survey — VALIDATED (fix took).** `survey jax_backend/src/utils.py` → **6 trapped_by_imports**
(`make_single_timestep_fn_nolearning`, `.single_timestep`, `initialize_meta_params`,
`get_default_inits`, `str2bool`, `compute_group_VFE_velocities` — each "module imports jax,
matplotlib"). Static, unaffected by the missing deps. Matches the discovery ledger.

### FINDING F — NEW [HIGH · a SPIRAL]: a COLLECTION-FAILURE cut gets the TIMEOUT-cut remedy → infinite loop
`converge 'jax_backend/src/utils.py::str2bool'` (bare) → **exit 3**, `unclassified 27 — the search
could not run`, and `DO THIS: detective converge '…::str2bool' --trace-budget 0 --trace-session-budget 0`,
`Why first: the profile was cut before the mutant universe was measured`. **Following that DO THIS
literally returns BYTE-IDENTICAL output with the SAME DO THIS** — an infinite spiral, exit 3 both times.

**Cause (observed, needs a symbolic trace of the CUT routing to pin):** 2 test files fail to collect
on the missing `jax` import — `jax_backend/tests/test_demo_nolearning_smoke.py`,
`…_withlearning_save_smoke.py` (the WARNING names them). That collection failure cuts the profile.
But `--trace-budget 0` is the remedy for a *timeout* cut; for a *collection-failure* cut it changes
nothing, so the command re-emits the same advice forever. The real cause (a missing dep → tests can't
import) is present in the WARNING but the CUT next-action does not consume it — the same narrow-proxy
root as the whole ledger ("cut ⇒ must be a timeout ⇒ trace-budget") instead of the real signal
("cut BECAUSE these 2 tests failed to import jax → install it / run under the venv that has it").

**This PREEMPTS the `fix_load` fix.** On a truly fresh greenfield clone the collection-failure cut
fires FIRST and outranks `load_failed`, so converge never reaches the `fix_load` path that names the
missing dep — the discovery-ledger `fix_load` validation was done in a state where those failing test
files were not collected. The un-spiral-able fix is the same shape as `fix_load`: name the failed-to-
collect files + their import error and route to "fix the import / right venv", never a trace-budget re-run.

### FINDING E — CONFIRMED primary [HIGH]: audit's sibling ladder, and it diverges from converge
`audit 'jax_backend/src/utils.py::str2bool'` → exit 0, `unclassified 27 — the search could not run` →
`DO THIS: detective converge` · `Why: 7 uncovered line(s) — real gaps … Writes the missing tests`.
It does NOT name the dep, does NOT mention the collection failure, and promises converge "writes the
missing tests" — but converge on this target SPIRALS (Finding F) and writes nothing. So `audit` (exit
0, generic converge) and `converge` (exit 3, trace-budget spiral) DIVERGE on the same target, and
neither names the real cause. `_audit_action` consumes none of `load_failed`/`inputs_expressible`/`note`
— exactly as filed. verify_rewrite as the third consumer stays a trace-level fact (discovery addendum);
not separately re-run here — the collection-cut preempts the load-failure path it would need.

### Minor UX (not a defect — calibration): third-party SyntaxWarning spam
converge/audit output is prefaced by ~15 lines of the target repo's OWN `SyntaxWarning: invalid escape
sequence` (matplotlib titles in its demo files) before the verdict. Honest passthrough of the repo's
warnings, not a Detective bug — but it buries the actual next-action. Possible smoothing: suppress/mute
third-party SyntaxWarnings during a run. Logged as UX, explicitly NOT a correctness finding.

---

# SUMMARY — re-validation status (all three repos, full surface, pristine clones)

## Fixes that VALIDATED clean at the surface
- **de-spiral routing** — arc-dsl run-1 → `AUTHOR INPUTS` (not migrate); GofL → `provide_sample`
  with explicit "Why not migrate". No migrate loop on either. ✓
- **BUG C** (flat-sibling load / migrate loop) — arc-dsl regime→migrate→converge TERMINATES → ✓ COMPLETE. ✓
- **survey** — usage-inference (GofL `update_cell`/`count_neighbors` extractable_core);
  trapped_by_imports (conorheins 6 flagged); false-positive fix (arc-dsl dsl.py 0 trapped). ✓
- Full 15-command surface exercised on arc-dsl; all clean except A/B/C.

## Fix that exists in code but is NOT REACHED on a real greenfield clone
- **`fix_load`** (name the missing dep) — PREEMPTED on conorheins by the collection-failure CUT
  (Finding F). The routing hits the CUT path first; the user never sees `fix_load`. The
  discovery-ledger validation was done without the failing test files collected.

## OPEN findings — re-confirmed live
| # | sev | where re-confirmed | status |
|---|---|---|---|
| A | design | arc-dsl ✓ COMPLETE | live — DONE points only to `flag`, no style handoff |
| B | HIGH | arc-dsl (converge vs audit) | live — killable wobbles 3→1→1, never 0; no-op loop; NOT reproducible |
| C | minor | arc-dsl verify-rewrite | live — misleading proof-replay row + duplicated DONE line |
| D | design | GofL (survey vs decompose) | live — survey "extract" vs decompose "no seam" |
| E | HIGH | GofL (inexpressible) + conorheins (unloadable) | live — audit ladder consumes no signal; diverges from converge |

## NEW finding
| # | sev | where | status |
|---|---|---|---|
| F | HIGH · spiral | conorheins converge/audit | a COLLECTION-FAILURE cut gets the TIMEOUT-cut remedy (`--trace-budget 0`) → byte-identical infinite loop; the real cause (2 tests fail to import jax) is named in the WARNING but not consumed by the next action; PREEMPTS `fix_load` |

## Headline
The behaviour-half fixes (de-spiral, BUG C, survey) took cleanly. The correctness-half findings
(B) and the sibling-ladder findings (E) are all still live, and a NEW spiral (F) — the highest-
severity kind, an infinite loop — surfaced on conorheins that the discovery pass did NOT hit,
BECAUSE the discovery pass wasn't a truly pristine greenfield clone with the repo's own (failing)
tests collected. All findings recorded; none fixed (observe/validate pass, per direction).

---

# SYMBOLIC TRACES (2026-09-06) — the CAUSES, grounded with Serena (correcting the inferred claims)

Founder ruling: an observed behaviour is not a traced cause. Each finding's cause below is now
established by reading the actual implementation via Serena (find_symbol / find_referencing_symbols),
not inferred from CLI output. Where the trace corrected the inferred claim, that is called out.

## FINDING F — TRACED (and the inferred cause was materially wrong about the FIX)
Full chain, all bodies read:
- `Detective/validity.py::normalize_validity` (188-189): Wesker's `collection_errors` (the test files
  that failed to collect) → `collection_incomplete=True`.
- `validity.py::measurement_cut_reasons` (89-90): appends the TYPED reason `"collection_incomplete"`
  to `cut_reasons`.
- `MeasurementValidity.admits_certificate` (147-149): `gateable and not cut_reasons` → **False**.
- `converge.py::certificate_standing` (162): `not admits_certificate` → `"ungateable"`.
- `cli.py::converge_next_action` (2342): `standing == "ungateable"` → `"repair_measurement"` — checked
  FIRST, so it OUTRANKS `load_failed`→`fix_load`. (This confirms the preemption claim.)
- `cli.py::_converge_action` (repair_measurement branch, ~2557): checks only `result.collection_conflicts`
  and `result.budget_exhausted`; everything else (incl. `collection_incomplete`) falls to the `else`
  → `--trace-budget 0 --trace-session-budget 0` / "the profile was cut before the mutant universe was
  measured." `--trace-budget 0` cannot fix a collection ImportError → same cut next run → SPIRAL.

**The decisive trace fact (could NOT be inferred from output):** the correct remedy ALREADY EXISTS —
`validity.py::cut_reason_sentence("collection_incomplete")` returns *"one or more test files failed to
collect (an import error), so the routed suite is missing tests the layout implies — fix the collection
errors and re-run."* The `repair_measurement` render NEVER calls `cut_reason_sentence`; it re-derives two
ad-hoc booleans and a catch-all. So F is the SAME root as the whole ledger — a computed, typed signal
(`cut_reasons`) with a ready remedy, dropped at the render layer — NOT "add logic to distinguish a
collection cut from a timeout cut" (my inferred framing). **The correct fix: `_converge_action`'s
repair_measurement branch must consume `result.validity.cut_reasons` and emit `cut_reason_sentence(r)`
per reason** (collection_incomplete → fix-the-imports/right-venv; uncontained_worker, coverage_truncated,
sampled_universe, ambiguous_module_identity, engine_refused_unspecified each already have a sentence),
instead of the `budget_exhausted`/`collection_conflicts`-only ladder with a trace-budget else. Filed;
not fixed (observe/validate).

## FINDING E — TRACED (the drop is EARLIER than I claimed — at audit_suite, not the renderer)
- `cli.py::_audit_action` (3601-3677): branches read only `a.failing_tests`, `a.killable_gaps`,
  `a.missing_lines`, `a.redundant_tests`, `a.candidate_equivalent(_ids)`, `a.unclassified`. No
  `load_failed`/`inputs_expressible`/`note`. Both dogfood cases hit branch 2 (`killable_gaps or
  missing_lines`, via the AST `missing_lines`) → "DO THIS: converge · Writes the missing tests."
- `audit.py::SuiteAudit` (52-145): the result dataclass has **no `load_failed`, `inputs_expressible`,
  or `note` field**. The renderer cannot consume a field the type does not define.
- `audit.py::audit_suite` (248-465): calls the SAME `classify_survivors` (line ~363) and gets a report
  that DOES carry `load_failed`/`note`/`inputs_expressible` — but reads only `bool(report.inputs_expressible)`
  (for `_gap_desc` alone, collapsing None→False) and the survivor buckets; **`report.load_failed` and
  `report.note` are never read**, and none of the three reach `SuiteAudit`.

**Corrected cause:** the divergence is not "the renderer ignores the signal" — converge carries the
whole `rep` to `_converge_action` (routing `fix_load`/`provide_sample`), while audit collapses the same
report into a `SuiteAudit` that has already DISCARDED `load_failed`/`note` (and lossily flattened
`inputs_expressible`). The two commands render from different objects. **Fix is 3-point:** SuiteAudit
must carry the signals → `audit_suite` must propagate them from `report` → `_audit_action` must consume
them (share converge's routing). verify_rewrite as the third consumer was traced in the discovery
addendum (rewrite.py:403-571; `classification_ran = report is not None` proxy) — sound, drops the note.

## FINDING A — TRACED (from `_converge_action` tail, cli.py 2484-2668)
Two DONE branches at ✓ COMPLETE:
- `rep.equivalent` present (arc-dsl: 13 unproven-equiv) → DONE points ONLY to `detective flag` — no
  style handoff at all.
- else → DONE points ONLY to `detective decompose '{fn}' --apply` marked "Next (optional)" — undersells
  it and omits `plan` / `survey` / `verify-rewrite --budget`.
Cause confirmed as filed: neither DONE branch signposts the style half loudly at the moment correctness
is done. Fix: append the loud pin→style handoff (plan + decompose + survey + verify-rewrite --budget) to
BOTH DONE branches. Design-forward.

## FINDING C — TRACED (`cli.py::_format_rewrite` 5324-5378; `rewrite.py::verify_rewrite` 447-456)
- Defect 1 (cli.py ~5335): the `· proof replay` row is UNCONDITIONAL —
  `_row("· proof replay", f"the original suite ran {r.proof_replayed} on the rewritten source")`.
  STALE_RECEIPT's early return sets `proof_replayed="skipped"`, so it prints "ran skipped on the
  rewritten source" though no replay ran and there is no rewritten source. Suppress the row when
  `proof_replayed == "skipped"` (STALE_RECEIPT / INVALID_RECEIPT).
- Defect 2 (cli.py ~5368-5377): `verdict_msg["STALE_RECEIPT"]` ("nothing was rewritten — the current
  source is identical…") AND `r.note` (rewrite.py:455, "the current source is identical… — nothing was
  rewritten") both print → the duplicated line. Drop one (either the verdict_msg or the note on this path).
Cause confirmed as filed; verdict itself correct.

## FINDING D — TRACED (survey and decompose use ORTHOGONAL criteria — the contradiction is real)
- `decompose.py::find_extraction_candidates` (998) + `_evaluate_block` (923) + module docstring (1-21):
  decompose keeps a block as a seam ONLY when it is a contiguous ≥2-statement, single-exit run with a
  small interface (≤4 in / ≤2 out) AND `block_cc >= _MIN_BLOCK_CC` (=3), in a function Detective also
  requires to be behaviorally ENTANGLED (2+ surviving mutation categories). Criterion = a COMPLEXITY seam.
- `survey.py::survey_source` (read earlier): flags a function for an EXPRESSIBILITY/pinnability boundary
  — `extractable_core` (inexpressible param) / `impure_body` / `trapped_by_imports`. Criterion = a
  PINNABILITY boundary.
These are orthogonal. GofL `update_cell` satisfies survey's (unannotated ndarray wraps a SMALL pure
rule) but fails decompose's (that pure rule is not a CC≥3 contiguous seam → "leaves a pure delegating
wrapper — not a seam"; also decompose needs a proof it cannot get on an inexpressible fn). So the two
STYLE tools legitimately answer different questions and SILENTLY contradict. Fix (founder call): make
decompose name the criterion gap, OR have survey say "extract by hand — decompose uses complexity
criteria and won't", OR a dedicated "extract pure decision" action. As filed.

## FINDING B — TRACED (corrects my inferred cause AND refutes a standing memory)
Full chain, bodies read:
- `engine.py::classify_survivors` (2663): classifies `result.value_survivor_records` — the value-survivor
  SET from the profile.
- `engine.py::classify_survivors._classify_pool` (2857): per survivor →
  `contract_disposition(buildable=True, killable=verdict.killable, blocked=verdict.blocked, flag)`:
  killable→killable; not-killable & not-blocked→candidate-equivalent; **blocked→unclassified**.
- `equivalence.py::classify_survivor` (1646) → `_search_witness` (1346): `killable = witness is not None`;
  the search is DEADLINE-sensitive (per-input `time.monotonic() >= deadline → blocked; break`, and per-call
  `_outcome` timeouts), so a deadline-cut survivor is `blocked → unclassified` (NOT a false equivalent).
- `validity.py::normalize_validity` (212-223): **in-process mutant EVALUATION shares the target module's
  mutable state, so a borderline mutant's scored disposition (crash-kill vs value-survivor) is NOT
  reproducible run-to-run** — flagged `approximate:mutant_universe`.

**Corrected cause (primary driver is UPSTREAM, not the witness search):** because the value-survivor SET
itself is an in-process estimate (validity.py), converge's final classify (converge.py:2105) and audit's
fresh profile (audit.py:363) classify DIFFERENT survivor sets — observed 42 vs 44 value-survivors — so
they get different killable counts (3→1→1). converge's ✓ COMPLETE requires its own profile's set to have
0 killable AND 0 unclassified; audit's fresh set has 1-3 killable. Neither is wrong; both honestly read a
NON-DETERMINISTIC measurement. audit is read-only (never persists a witness), so its "N killable → converge"
is a no-op — converge re-profiles, gets its own set, says ✓ COMPLETE again → the loop cannot close.

**Refutes memory `project_converge_determinism_bug.md`** ("the value-kill proof is deterministic; killset +
survivors STABLE; only the scored COUNT is noisy"). The trace + observation show the survivor SET is NOT
stable under live in-process (42 vs 44), so the derived killable/candidate-equivalent classification wobbles
— not merely the headline count. The "proof deterministic" claim holds only for a FIXED survivor set; the
set itself is non-deterministic. My earlier inferred cause ("the candidate-equivalent witness search is
non-deterministic") was directionally right but mislocated: the witness-search deadline-sensitivity is a
SECONDARY source; the primary is the non-deterministic survivor SET. Fix direction unchanged (make the
measurement reproducible given a fixed suite — isolate the profile, or seed/stabilize the in-process scoring,
so converge and audit classify the SAME set); founder call on soundness-vs-UX. NOTE: the memory should be
corrected — flagged to founder, not edited unilaterally.


## 2026-09-07 audit closure follow-through

The finding-by-finding disposition, symbolic traces, conditional pin receipts, and formal
artifact checks are recorded in [the closure report](audit_closure_2026-09-07.md).
The [operational handoff](CLOSURE_HANDOFF.md) records the latest full-suite status and
reproduction commands. These later results supplement this historical ledger; they do not
retroactively turn its observations into formal correctness or equivalence proofs.
