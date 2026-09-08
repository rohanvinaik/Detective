# Correctness repairs — 2026-09-08

Status: DESIGN, for founder mark-up. Nothing built.

Companion: [`DOCTOR.md`](DOCTOR.md). Doctor's `emission_disposition` is the shared derivation
repair **R3** must consume — see §R3.

---

## 0. Provenance

Two independent passes, kept separate on purpose:

- **Behavioural.** A/B of the uncommitted closure wave against HEAD (`fccee9c` / Wesker
  `be935ac`), run as a greenfield user over fresh clones of `michaelhodel/arc-dsl`,
  `takmakov/GofL`, `conorheins/collective_motion_actinf`, `parama/pabkit`. All 15 verbs, one
  command at a time, full static output read. Ledger and logs:
  `scratchpad/ab/AB_LEDGER_2026-09-08.md`, `scratchpad/ab/logs/{with,without}/`.
- **Symbolic.** Serena traces of current source, run afterwards. The 2026-09-06 dogfood ledger's
  trace of this same chain was authored to *guide* the E/F fixes and five commits plus the closure
  wave have landed since, so it is anti-correlated with current truth and was not used as a
  premise.

Every claim below is marked **observed** (behaviour) or **traced** (`file:line`). Where only one
exists, it says so.

---

## R0 — RESOLVED 2026-09-08: Finding B is fixed, not suppressed

**Answer: the wave attributes kills that HEAD fails to attribute. It suppresses nothing.**
Proceed with R1–R4. A separate finding surfaced en route — see **R5**.

### The probe

Independent of both classifiers. Hand-built the SWAP mutations of `add` that are **not**
semantically equivalent — each swaps the two elements of a returned tuple, exhaustive over that
form — and ran the real generated 6-test suite against each
(`scratchpad/ab/r0_probe.py`):

| Mutant | without-arm suite | with-arm suite |
|---|---|---|
| swap in the `(tuple, tuple)` branch | **KILLED** (1 failed) | **KILLED** (1 failed) |
| swap in the `(int, tuple)` branch | **KILLED** (2 failed) | **KILLED** (2 failed) |
| swap in the `(tuple, int)` branch | SURVIVED | SURVIVED |

**The two arms' suites are behaviourally identical.** The difference between the arms is entirely
in classification, not in what the tests do.

HEAD reports `3 killable mutant(s) no test kills` — while the suite demonstrably **kills two** of
the three non-equivalent SWAPs. That is a **kill-attribution defect**, not a missing test, and it
explains the no-op loop exactly: audit reports gaps → `DO THIS: converge` → converge correctly
finds nothing to write (the tests already kill them) → `✓ COMPLETE` → audit reports the gaps
again. The wave's `value_killed` 18 → 21 and empty `killable_gaps` are that attribution being
fixed. Consistent with the closure report's Wesker claim that *"value-kill attribution follows the
actual asserting test."*

**Established:** items 1–4 above. **Not established:** that HEAD's three specific IDs
(`SWAP_4d186208`, `SWAP_e54f5438`, `SWAP_839d5869`) map exactly onto these three mutations — the
probe is exhaustive over tuple-element swaps, not over every SWAP form — nor that the 40 → 48
universe difference is fully accounted for.

### Original framing, retained

**Was blocking. This would have reordered everything had it come back the other way.**

**Observed.** At HEAD, on the exact suite converge certified `✓ COMPLETE` (arc-dsl `dsl.py::add`),
`audit` reports `incomplete · 3 killable mutant(s) no test kills` → `DO THIS: converge` → converge
re-pins `✓ COMPLETE` and writes nothing. Non-reconciling split, no-op loop. Under the closure wave
audit instead reports `complete, modulo 24 unproven-equivalent and 3 crash-only` → `DONE`, and
re-profiles on every run (48/48 mutants, 2.6s, three consecutive runs, identical output — not a
cache hit; HEAD served runs 2 and 3 from cache).

**The gap in that result.** The arms now *agree*. Agreement is not correctness. The 2026-09-06
ledger's Finding B diagnosis states that audit's killables were **real** — the witness search
verifies its matches, a spurious one raises and is dropped — and concluded *"converge therefore
OVERCLAIMS ✓ COMPLETE."* If that holds, the wave may have made the search reproducible (the
intended fix) **or** stopped finding true killables (a suppression). Nothing measured so far
separates those two, and the A/B ledger's first draft reported it as a clean win. That was the
same unknown-versus-established error this document exists to repair, committed in its own
headline.

**The check.** Take the 3 killable mutant IDs the `without` arm reports for `dsl.py::add` (in
`scratchpad/ab/logs/without/arc-dsl.09-audit-*.log` and the converge report) and determine whether
a distinguishing input exists for each. If one does, Finding B is **not** fixed and the wave has
suppressed a true signal.

**Do this before treating B as closed.**

---

## R1 — Validity has no representation for "the target did not load"

**Traced.** `Detective/validity.py:55` — `measurement_cut_reasons(reported_gateable, gateable,
budget_exhausted, coverage_depth, containment, identity_ambiguous, collection_incomplete=False,
evaluation_failed=False)`. **There is no load-failure parameter.**

**Consequence.** A target that never imported produces no cut reason → `admits_certificate` stays
True → `certificate_standing` reads clean → `converge_next_action` (`cli.py:2402-2407`) passes all
three standing guards. **Observed** on conorheins `jax_backend/src/utils.py::str2bool` with
funcy/jax/matplotlib absent: `0/27 killed`, `0 pinned`, `⚠ unclassified 27 — the search could not
run on them`, and **exit 0**.

**Latent, worse case.** Reaching `settled` requires only `not (has_killable or has_line_gap)`
(`cli.py:2408`). A load-failed target with no static line gap returns `settled` — DONE on a run
that measured nothing. Not observed; reachable by inspection.

**Repair.** Load failure becomes a named cut reason in `measurement_cut_reasons`, with its own
`cut_reason_sentence`. This is the principled fix: it makes a load-failed measurement non-gateable
independent of any routing, so both the vacuous `settled` and any certificate become impossible.

**This is also the general form of the pabkit U1 / BUG-B founder call**, still open: *"should a
crash while measuring be a REFUSAL rather than folding into a 0-kill Incomplete… add a 'N mutants
un-evaluable' floor + non-zero disposition when the whole universe is un-evaluable."* Same shape,
different cause. R1 should be designed so U1 is a sibling reason, not a second mechanism.

Pure, sits beside the existing pinned decisions, **converged in isolation before wiring**.

---

## R2 — Two false proxies, retired together

### R2a — a hardcoded claim

**Traced.** `cli.py:3323`, inside `_derived_input` (`cli.py:3159-3390`), the `kind == "lines"`
branch:

```python
out.append(_row("· Why", "Every killable mutant is already dead. What is left is"))
```

A string literal. Not derived from anything. True on arc-dsl, where every killable really was
dead; **false** on conorheins, where classification never ran — and the renderer cannot tell the
difference because it never asks. `⚠ unclassified 27 — the search could not run` prints two rows
above it, from the same data.

`_derived_input` already receives `r`, `proof` and `rep`, so the count is in scope: **local
change, no plumbing.** Extract the choice as a named-code decision rather than an inline ternary.

### R2b — a structural proxy

**Traced (2026-09-06 ledger addendum, re-confirmed by structure below).**
`rewrite.py` uses `classification_ran = (report is not None)` — which asks *did a report come
back*, not *did the classifier actually look*. On a load failure `classify_survivors` returns a
non-None report with every survivor unclassified, so the proxy reads True.

Both are the same defect: a claim asserted where a measurement exists to derive it. Retire
together.

---

## R3 — One shared route, three renderers, and only one of them wired

**Traced.** `measurement_block_route` (`cli.py:2479-2509`) is the shared decision, returning
`fix_load` / `close_the_gap` / `provide_sample` / `""`. Its own docstring says it is *"Shared by
converge AND audit so the two commands can never diverge on the same survivor report."*

`find_referencing_symbols` gives two production call sites:

| Consumer | Site | State |
|---|---|---|
| `_audit_action` | `cli.py:3797` | **unconditional**, ahead of every count — correct |
| `converge_next_action` | `cli.py:2419` | **nested inside `if session_reason:`** |
| `verify_rewrite` | — | **no call site at all** |

**So the docstring's claim is false as wired.**

### The converge gate

```python
if session_reason == "pytest_missing": return "install_pytest"
if session_reason:                       # ← the gate
    _block = measurement_block_route(load_failed, inputs_expressible, needs_sample)
    if _block: return _block
    if wrote_runnable_suite: return "close_the_gap"
    return "fix_collection"
return "close_the_gap"
```

`session_reason` describes **baseline collection at run start**. Suite collects cleanly → gate
false → falls through to `close_the_gap` → AUTHOR INPUTS. **`fix_load` is structurally unreachable
whenever the suite collects**, which is the trigger condition observed empirically.

Note the symmetry with the 2026-09-06 ledger's own finding: it repaired `session_reason` being
stale in the *truthy* direction (fired when it should not, → the migrate loop; fixed by
`wrote_runnable_suite`). This is the same signal wrong in the *falsy* direction. One overloaded
signal, two opposite failures.

### verify-rewrite

**Traced.** `RewriteVerification` (`rewrite.py:181-194`) has `verdict`, `function`,
`proof_replayed`, `new_dimensions`, `differences`, `abstentions`, `note` — **no load-failure
field.** Identical in shape to the old `SuiteAudit` defect: the renderer cannot consume a field
the type does not define. Per the ledger this is **sound but mute** — it never false-PRESERVEs,
because unclassified survivors force it off the strong claim; but it drops the one actionable fact
it holds.

### Observed consequence — a spiral, live in BOTH arms

conorheins `str2bool`, collection cut removed so only the module-load failure remains:

- `audit` → `STOP: the live original could not be loaded: ModuleNotFoundError: No module named 'funcy'` — **correct**
- `converge` → `AUTHOR INPUTS`, `Why: Every killable mutant is already dead`, **exit 0**, funcy never named
- `diagnose` → `DO THIS: converge` — routes the operator into it

Following `AUTHOR INPUTS` literally with four inputs covering all seven named uncovered lines
returns **byte-identical output carrying the same instruction**. This is Finding E **inverted**:
the repair landed on audit, converge became the broken sibling, and the collection cut normally
masks it.

### Repair

Hoist converge's consultation out of `if session_reason:` **and above the `settled` check at
`cli.py:2408`** (R1's latent case). Add the field to `RewriteVerification`, propagate, surface the
note. And per [`DOCTOR.md`](DOCTOR.md) §4: the three renderers should consume
**`emission_disposition`** — the cross-axis precedence decision — rather than each getting
`measurement_block_route` bolted on and rewired when doctor lands. One derivation, three
renderers.

---

## R4 — `survey` / `extract` usage inference: a true positive traded for a false positive

**Observed.** GofL `gameoflife/game.py`:

| | HEAD | closure wave |
|---|---|---|
| `survey` | **2 trapped**: `Game.update_cell` (90), `Game.count_neighbors` (115), `extractable_core` | **0 trapped** |
| `extract …::Game.update_cell` | concrete proposal `update_cell_decision(neighbor_sum)` | `nothing trapped` |

**The underlying fact was verified, not assumed.** `step` genuinely is an ndarray:
`get_next_step` builds `np.zeros((x, y))` at `game.py:83` and passes it at `:85`; the subscripts
at `:95` and `:121` are 2-D ndarray reads. `update_cell` genuinely wraps a pure decision over
`neighbor_sum`. So the wave's "0 trapped" is a **false negative on the canonical demo case.**

**Traced.** The plumbing is intact — `survey._param_inexpressible` (`survey.py:164`) still calls
`usage_inferred_type`. The change is inside `usage_inferred_type` (`call_sites.py:180-198`), which
returns a **flat string where `""` means unknown**. That `""` carries two different meanings — *no
signal* and *ambiguous, possibly ndarray* — and the wave correctly stopped inferring ndarray from a
tuple subscript (a dict accepts tuple keys), which moved GofL from "trapped" into the same bucket
as "clean". **That collapse is the defect.** Three consumers: `survey._param_inexpressible`,
`extract._inexpressible_params` (`extract.py:54`), `extract._extraction_inputs` (`extract.py:208`).

**Cause is the wave's own reported repair**, closure item 6/D — *"Tuple indexing alone no longer
implies ndarray; dictionaries supply a counterexample."* Sound in isolation. The closure report
records item 6 as a clean repair with no downstream cost, and the handoff's "Qualifications still
open" does not mention it.

**Scope is narrow, and that matters.** `trapped_by_imports` is fully intact — pabkit
`pab/metrics.py` reports the same 6 torch-trapped functions on both arms, byte-identical. Only the
usage-inference / `extractable_core` path is affected.

**Knock-on.** Finding D (survey says "extract", decompose says "no seam") reads as resolved on the
wave arm **only because survey no longer emits the signal.** Resolved by signal loss.

### Two stale claims left pointing the wrong way

- `survey.py:149-153` — `_param_inexpressible`'s docstring still asserts *"the usage half is what
  closes the recall gap on GofL `Game.update_cell` … `step[xy[0], xy[1]]` types it."* False now.
- `tests/test_usage_inference_intent.py:92` — the test is named
  **`test_gofl_update_cell_step_infers_ndarray`** and its body asserts `== ""`. The name claims
  the capability works; the assertion pins that it does not.

The second is the more serious. The ledger records that the original silence was pinned
deliberately — *"an intent test pins the silence, so a future change that starts flagging it is a
deliberate decision, not a drift"* — and that step 2b (`d73a578`) deliberately flipped it. The
wave flipped it back and left the name lying. **The guard was built to force deliberation in both
directions and held in only one.**

**Repair.** `usage_inferred_type` becomes three-valued in house form — a supported type name / an
unresolved-but-suggestive boundary / nothing — and `survey_disposition` (`survey.py:63-89`, already
a four-code named decision) gains the unresolved state so an ambiguous param stays a **visible
candidate** rather than silence. Fix both stale claims.

---

## R5 — NEW: a trivially-killable mutant carried as "no input distinguishes them"

Surfaced by R0's probe. **Present in both arms** — not a wave regression.

The third mutant — swapping the returned tuple's elements in the `(tuple, int)` branch —
survives both suites, and is distinguished by the most obvious input in the type's domain:

```
add((1,2), 3)  original=(4, 5)   mutant=(5, 4)   DISTINGUISHES
add((5,9), 1)  original=(6, 10)  mutant=(10, 6)  DISTINGUISHES
```

The witness search does not find it. Under the wave it is carried in the 24
`unproven-equivalent`, and `mutant_complete` reads **True** with `killable_gaps: []`. So HEAD's
"incomplete" verdict was right about *this* mutant for the wrong reason (it bundled it with two
attribution errors), and the wave's `✓ COMPLETE` is an overclaim for it.

Two things to separate here:

1. **The search gap.** `line_complete` is True — the branch IS executed by some test — but
   execution without a distinguishing assertion does not kill. The witness search never tries a
   `(tuple, int)` pair, because no supplied `--input` reached that branch. Detective's own
   structural caveat names this case exactly — *"a survivor above may be KILLABLE, not equivalent —
   confirm over a nested/cross-referential `--input` (or **a branch no input reached**)"* — so the
   behaviour is disclosed. What is missing is that the caveat's force does not reach
   `mutant_complete: True`.

2. **A wording defect, precisely on thesis.** converge's DONE block is scoped correctly:
   *"cannot be distinguished by any input **Detective found**."* Audit's row drops the scope:

   > `· unproven-equiv     24 survivor(s) — no input distinguishes them`

   That is a claim about all inputs, asserted from a bounded search. It is the
   unknown-versus-established collapse in a row label, on the exact axis this project exists to
   police. Cheap to fix and it should be fixed with R2, which is the same class of defect.

Whether the search should *try* the un-exercised branch is a founder call (it costs a synthesis
pass against a branch no operator asked about). The wording is not a founder call.

---

## Constraints inherited from the 2026-09-06 ledger

Three, all load-bearing, all of which would otherwise have been walked into:

1. **R4 must stay advisory-only.** The ledger records step "2a" as a **traced regression that was
   dropped**: making GofL read `inputs_expressible=False` routes converge to
   `close_the_gap → "lines"` and offers an untypeable `--input "(<step>, <xy>)"` — strictly worse
   than the existing `provide_sample`. The three-state change must **not** propagate into
   converge's routing.
2. **The `"lines"` renderer is multi-consumer and was deliberately deferred.** Traced as reaching
   `_derived_input`, the `_derive_inputs` MCP adapter, and the journey-contract test — *"belongs in
   the audit, designed holistically with `converge_next_action` / `provide_sample` / the
   `test`-vs-`lines` kinds — not patched piecemeal."* R2a and R3 therefore land **together**.
3. **Trace the shared producer, not the edited symbol.** The ledger's own recorded discipline
   failure. `find_referencing_symbols(classify_survivors)` is what finds siblings;
   `find_referencing_symbols(converge_next_action)` finds only callers and structurally cannot.

---

## Order

| # | Repair | Why here |
|---|---|---|
| ~~R0~~ | ~~Settle agreement-vs-suppression on Finding B~~ | **RESOLVED 2026-09-08 — fixed, not suppressed** |
| **L** | The invocation ledger (`DOCTOR.md` §7.1) | red cannot be built without it; a new persisted artifact, not a wiring job |
| **D** | [`DOCTOR.md`](DOCTOR.md) precedence lattice + `emission_disposition` | R3 should consume it, not be rewired later |
| **R1** | Load failure as a validity cut reason | principled root; makes the vacuous `settled` impossible |
| **R2** | Retire both false proxies + audit's unscoped `unproven-equiv` row (R5.2) | claim-level, general across states |
| **R3** | Wire all three renderers | lands with R2 per constraint 2 |
| **R4** | Three-valued usage inference, advisory only | independent of R1–R3 |
| **R5.1** | Whether the witness search should try un-exercised branches | founder call; costs a synthesis pass |

Every pure decision **converged in isolation before wiring** (`feedback_converge_before_wiring`),
paired with a hand-written intent test authored from intent, citing the defect.

---

## Regression cases

The essential combinations, several of which nothing currently covers:

1. Collection succeeds **and** target import fails → named refusal, non-zero exit, **no input
   prescription**.
2. Supplying inputs under that failure → the same honest refusal, not a byte-identical re-emission.
3. **Repairing the import allows progress.** Untested — needs a second venv with jax+funcy.
   `.venv-det` must stay deps-absent; it *is* the load-failure repro.
4. **`audit` non-regression.** It is currently the correct sibling and the most at risk from a
   shared-route edit.
5. `verify-rewrite` under target-load failure — untested; the note must surface.
6. A tuple-key dictionary is never asserted to be an ndarray (retain the wave's true fix).
7. GofL's two candidates discoverable via `survey`, actionable via `extract`.
8. An ambiguous param stays **visibly unresolved**, not silent.
9. An identical rewrite keeps scoped treatment; a genuinely changed rewrite still reports
   `CHANGED` (both arms currently correct — do not lose this).

**Open contract question:** which exit code a load-failure refusal carries. The documented table
has `1 = a real gap or typed REFUSAL` and `3 = INVALID MEASUREMENT, re-run`. "Nothing was
measured" argues 3. CI branches on this, so it should be chosen, not emergent. Note the wave
already moved verify-rewrite's ABSTAIN from 1 → 3 (**observed**).

---

## Not in scope here — queued from the pabkit ledger

Recorded so they are not silently dropped: no `detective doctor` (→ `DOCTOR.md`); the count-noise
label (*"≈ in-process estimate; the killset/proof is stable"* — never seen in any output during
the A/B); the unverified trace-cache body-digest hypothesis; U3 (unsound-float dead end); U4
(a written test that kills 0); U5 ("proposed removals: your own test"); the exception-message-only
CLI copy.

**Also both arms, minor:** the converge/audit header reads `uncovered 11 line(s): [93, 95, 97, 98,
100, 101, 104, 107]` — count says 11, list shows 8 (GofL `Game.update_cell`).

**Harness note worth keeping:** `python -c` puts cwd at `sys.path[0]`, so a two-knob resolution
proof run from inside `/Users/rohanvinaik/tools/Detective` reports the working tree for *both*
arms and silently makes any A/B vacuous. Prove resolution from the target repo's cwd. `--version`
prints `0.13.0` for both engine states and does not distinguish them.
