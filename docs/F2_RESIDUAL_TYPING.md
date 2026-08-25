# F2 — Residual typing

**Status:** design + first slice building. Phase F's "own document" (TEST_BASIS §17 F2).
**Home:** Detective (the residual classifier and its surfaces).
**Question:** *when converge leaves a survivor un-killed, what KIND of residual is it, and what is
the one next action for that kind?*

Provenance tags as in TEST_BASIS: **[V]** verified by reading current source · **[C]** commit ·
**[P]** proposal · **[?]** open decision.

---

## 1. What already exists — the residual is NOT one bucket [V]

TEST_BASIS §17 calls the residual "one undifferentiated `I_solve` bucket." Grounding the current code
falsifies that: converge already classifies every survivor.

- **Value dispositions** (`equivalence.SurvivorReport` properties): `killable` (a witness exists) ·
  `candidate_equivalent` (no distinguishing input FOUND) · `crash_only` (a crash input distinguishes
  it, no value pin) · `unclassified` (search could not run) · `manual_equivalent` (human-flagged) ·
  `inputs_expressible` (can a human even type the input as `--input`?).
- **Residual sub-types on `ConvergeResult`**: `needs_receiver` · `environment_coupled` (golden
  refused — env-dependent) · `environment_gated` (a line behind state no `--input` can set →
  fixture/manual) · `capability_identity` (clock/env) · `structural_difficulty` (`deep_structural` /
  `flat`) · `signature` / `param_names` (the `--input` template).
- **The #67 structural detector is built and pinned**: `equivalence.structural_input_difficulty(
  has_worklist_loop, indexes_into_element, nested_container_param) -> "deep_structural" | "flat"`
  (pure, pinned), fed by `equivalence.structural_shape(node)` (an AST read). It fires only on a
  worklist/fixpoint loop combined with element-indexing or a nested-container parameter —
  conservative by design.
- **Per-type hand-backs already render**: the `--input` template, `flag <mutant_id>`, fixture /
  receiver prompts, and (shipped, `73dbf3b`) the **deep-structure caveat** on both the terse default
  and the verbose report.

## 2. The one real gap [V]

`candidate_equivalent` **conflates two residuals that need opposite next actions**:

- **genuine-equivalent** — `flat` shape, no killer exists → `flag` is correct.
- **killable-unsynthesized** — `deep_structural`, a killer *exists* but the deterministic witness
  search did not reach it → `flag` would be a FALSE equivalence claim; it needs a structural input or
  a differential check.

`structural_difficulty` (the #67 gate) is the discriminator. The shipped caveat WARNS about this; it
is not yet a first-class residual TYPE with its own routing. Promoting it is the whole of F2 — much
narrower than "type the residual," which is largely done.

## 3. The design [P]

### 3.1 A pinned typing decision

The canonical per-survivor residual type, beside the #67 detector in `equivalence.py`:

```python
def residual_disposition(is_killable: bool, is_crash_only: bool, structural_difficulty: str) -> str:
    "killer_ready"         a witness exists — synthesize the test (not really a residual)
    "value_residual"       crash-only: a crash input distinguishes it, no value pins it
    "structural_residual"  no input found AND deep_structural — likely KILLABLE with a nested /
                           cross-referential input; route to the structural hand-back, NEVER flag
    "genuine_equivalent"   no input found AND flat — flag is appropriate
```

Named codes, not bools (two look-alike states must not collapse): `structural_residual` and
`genuine_equivalent` both come from a "no distinguishing input found" survivor and are told apart
ONLY by the #67 gate. Pure over `bool/bool/str`, so it is **pinnable** (unlike the AST `structural_shape`).

### 3.2 One decision, every surface

`deep_structure_caveat` (cli, shipped) is re-expressed as a consumer of `residual_disposition`, so the
caveat and the typed residual can never disagree on what "deep-structural" means. The terse default,
the verbose report, and `--json` all read the one typing, never re-derive it (the measurement/decision
discipline, one level down from the F2 defect already fixed).

### 3.3 The escalation dispatch (hand-back branch)

Per residual type, the ONE hand-back:

| type | hand-back |
|---|---|
| `killer_ready` | synthesize the test (the normal converge path) |
| `structural_residual` | "supply a nested/cross-referential `--input` (template below) or run a differential check; **do not** `flag`" |
| `value_residual` | "value-unspecified — a crash input distinguishes it, no value pins it" |
| `genuine_equivalent` | `flag <mutant_id>` |

The dispatch is a pure decision (type → hand-back kind), routed through the existing
`--input` template / `flag` / fixture surfaces — no new synthesis machinery.

## 4. Deferred, and why [?]

- **Active structural search** — `structural_residual` could instead TRIGGER a harder / structural
  witness search (real new synthesis machinery), not just a typed hand-back. That is genuinely "its
  own document" — the hand-back branch (§3.3) is the bounded slice built now. **[?]**
- **The `inputs_expressible` second discriminator** — the discrimination is LIVE, but through
  `residual_disposition`, not this helper. `residual_disposition` consumes `inputs_expressible` and
  peels an inexpressible residual to `fixture_residual` UPSTREAM, and `candidate_equivalent_caveat`
  (cli.py) maps that to the `fixture` / `structural` / `none` caveat both surfaces render — so the
  fixture-vs-input ask reaches the terse default AND the verbose report via the caveat.
  `structural_residual_handback(inputs_expressible) -> "structural_input" | "structural_fixture"`
  (pure, pinned) is **built but NOT yet wired** — the reference graph shows only its test consumes it,
  and it is currently REDUNDANT (once the caveat reports `structural`, the inputs are already
  expressible, so its fixture branch is unreachable). Kept as a pure helper reserved for a finer
  hand-back TEXT (a distinct "supply a nested `--input`" vs "hand-build a fixture" message) if that is
  ever surfaced separately from the caveat. [Grounded 2026-08-25; corrects the earlier "both surfaces
  consume it" claim, which the reference graph falsifies.]
- **Where the type is stored** — a per-verdict field on `SurvivorReport` (more reusable) vs a
  converge-level decision consuming the report (smaller change). The slice takes the decision-consuming
  form; a stored field can follow if a second consumer appears. **[?]**

## 5. Scope

The typing decision + the caveat consolidation are a bounded pure-decision extraction (pinnable) plus
rewiring the caveat onto it — comparable to an X-slice. The active structural search (§4) is the only
genuinely large, separate piece.
