# Parsimony — the SICP advisory read (design spec)

**Status:** design, pre-build. **Home:** Detective (native). **Powered by:** Wesker.
**Scope:** a small, well-scoped set of *advisory* code-quality signals that make Detective a
SICP-style clean-coding tool for the human or large model at its CLI. Nothing here proves
anything, and nothing here writes source.

---

## 0. Why this exists, and the one line that keeps it honest

Detective already implements the **provable** half of "SICP-style refactoring": a function is
pinned by a mutation-complete suite, and `decompose --apply` splits it only at a seam a suite
proves behaviour-preserving. That is real, and it gates.

It does **not** implement the **stylistic / epistemic** half — cohesion, the right abstraction,
the God-function that is behaviourally overloaded — because those are **not provable**. Mutation
testing has no opinion on them.

The invariant that makes adding them safe, stated once and never violated:

> **Behavioural equivalence is PROVABLE and gates source rewrites. SICP parsimony is NOT
> provable and may only ever SIGNAL.** The signal points *where*; the proof decides *whether*.

An advisory metric can never cause an unproven rewrite, because the only thing that writes source
is still `decompose --apply` behind mutation-completeness. The parsimony read is a strictly
additive *informational channel* that cannot contaminate the proof. That is why it is not scope
creep.

---

## 1. Where it lives — the trilogy roles (load-bearing)

The Resident Evil naming is the architecture:

- **Wesker** — the background intelligence that drives everything: the mutation engine. Never
  driven directly.
- **Detective** — the playable character: the operational layer a **strong intelligence (human or
  large model) drives through the CLI** to actually change code. **The parsimony read is
  Detective-native**, because a stylistic/epistemic call *requires* judgement, and the judgement is
  here.
- **Uroboros** — the "final solution", powered by Wesker: the mindless virus thrown at whole repos
  that churns **without a strong intelligence** toward *provable* purity. **SICP signals are out of
  Uroboros's action loop** — a dumb relentless process cannot adjudicate a stylistic call. Uroboros
  purifies what is provable and *routes* judgement-needing residue to its existing review buckets;
  it does not advise, and it does not rank on style.

Consequence for this spec: everything below is a **per-function** read computed **in Detective**,
surfaced to whoever drives Detective. Uroboros consumes the same `ScopeMap` it always has and
ignores the advisory fields for its churn. There is **no automated cross-function stylistic
ranking** — the intelligence at Detective's wheel does the prioritising across functions; that is
its job, not the engine's.

This whole feature follows a pattern the codebase already established: `scope.py` is a *"clean-room
port of LintGate's reshaper, consuming Wesker's real `ProfilingResult`"* (its own docstring). We
take the **idea** from the LintGate prototype (a multi-lens advisory read), and rebuild it clean,
native, and minimal against real Detective/Wesker types. We port concepts, never the sprawl.

---

## 2. The laws it obeys (inherited, not restated per-feature)

1. **The model never drives.** The subjective axes (§6) surface *evidence*; any model opinion is a
   bounded, typed *selection*, never control flow.
2. **One function is the unit.** Every signal is a property of ONE function's AST or ONE function's
   mutant set. Nothing scales with the repo. (Repo-scale axes are §7 — deferred, and Uroboros's, not
   Detective's.)
3. **Proven or nothing.** Advisory output never triggers a write. Only the proof gate writes.
4. **Deterministic, CPU-only, no inference in the engine.** Every lens is a pure AST or mutation
   computation. SICP-on-a-chip holds.
5. **Ground before threshold.** Prefer a *structural* rule to a fitted number. Where a numeric
   cutoff is unavoidable, it is a **loose backstop to calibrate on real Detective/Wesker functions
   at build** — measured first, never fitted to a handful of examples.

---

## 3. The lenses — and how little is new

Sign convention throughout: a lens votes **+1 = parsimonious/clean · 0 = no opinion · −1 = smell
(look here)**. The informational zero is explicit (Yami's lesson): 0 means "this lens has nothing
to say", never "disagreement".

| Lens | Unit | Source in Detective/Wesker | New? |
|---|---|---|---|
| **complexity** | fn | `cognitive_complexity.compute_cognitive_complexity` | have |
| **impurity/state** | fn | `purity.is_pure` / `analyze_function` | have |
| **behavioural overload** | fn | Wesker mutation-DOF (`ScopeMap.behavioral_dof`, `specification.behavioral_variants`) | have |
| **interface width** | fn | `decompose.find_extraction_candidates` (`max_params=4`), `decompose_apply.block_interface` | have |
| **structural seam** | fn | `ScopeMap.decompose_seams` (`find_extraction_candidates`) | have |
| **regime** (behavioural entanglement) | fn | `ScopeMap.regime` (A/B) | have |
| **cohesion** | fn | statement-level def-use over `_names`/`structural_bindings`/`_aug_targets` | **NEW (small)** |

Six of seven lenses are already computed. The build is a fusion + a surface + **one** genuinely new
pure metric.

---

## 4. The one new metric — cohesion (precise definition)

**Question it answers:** does this function compute *one* thing, or several unrelated things that
merely share a scope? (SICP: a procedure should embody one abstraction.)

**Construction (pure AST, reuses existing primitives):**

1. Over the function's top-level statements `body[0..n]`, build a **def-use graph**: an undirected
   edge between statement *i* and statement *j* iff they share a data dependency — *i* writes a name
   that *j* reads (or vice-versa), using `_names(stmt, ast.Store)` / `_names(stmt, ast.Load)` /
   `_aug_targets`, **excluding** names in `structural_bindings(stmt)` (the loop-variable-leak that a
   naïve reads∩writes test gets wrong — `block_interface` already handles this exact case).
2. Ignore statements with no data footprint (bare `return`, pure side-effect-free no-ops) for the
   component count; they neither support nor break cohesion.
3. **Cohesion = the number of weakly-connected components** among the data-touching statements.

**Ternary projection (structural — no fitted threshold):**
- exactly **1** component → **+1** (cohesive: one computation).
- **≥ 2** components → **−1** (incohesive: independent responsibilities sharing only a scope).
- **< 2** data-touching statements → **0** (trivial — no opinion).

This is an LCOM-analogue at statement granularity. It is the **data-flow** answer to "is this two
things?"; `decompose_seams` is the **structural-cut** answer; `regime B` is the **behavioural**
answer. Their agreement is the signal (§5) — and cohesion costs almost nothing because
`block_interface` already computes the read/write sets it needs.

---

## 5. Fusion — consensus, not a weighted sum

Both recommendation-engine prototypes (Yami, ModelAtlas) are written post-mortems of the same
failure: **a hand-tuned weighted sum of non-commensurable axes is broken.** We do not build one.

**The read is a consensus over ternary votes:**

- `flagged = (count of −1 lenses) ≥ 2` — a smell is reported only when **≥ 2 independent lenses
  agree**. One lens is necessary, never sufficient (LintGate's `decomposition_evidence` learned this
  the same way). This is scale-robust by construction: thresholding to {−1,0,+1} erases the
  incommensurable magnitudes before they are compared.
- `agreement = count of −1 lenses` — the strength of the "look here" (Yami's interference count).
- `dominant = the −1 lens with the strongest raw signal` — the **attribution channel**: the read
  says *"flagged for cohesion (3 components) + behavioural overload"*, never a bare scalar.

**The existing `★ LOOK HERE FIRST` is a special case.** Today it fires on `regime B ∧
decompose_seams` — i.e. two lenses at −1. Adding cohesion / overload / interface-width simply
extends the agreement count: a function flagged by regime-B **and** an un-taken seam **and**
incohesion **and** behavioural overload is a 4-lens consensus — the highest-value decompose target,
and one no pure linter can name because one of the four lenses is *behavioural* (Wesker's mutant
density), which linters cannot see. That fusion is the contribution unique to this trilogy.

**Cry-wolf suppression (provenance).** A lens whose input was not measured votes **0**, never −1 —
the same discipline `ScopeMap` already carries (`tests_discovered = -1` / `trace_truncated` /
`served_from_cache`). "We did not measure this" and "we measured it and it is clean" must never
render identically.

**The two numeric backstops** (to calibrate at build, per Law 5, not fitted here): the **cognitive
complexity** −1 cutoff and the **behavioural-overload density** −1 cutoff. Everything else —
cohesion (component count), interface width (Detective's own `max_params=4`), seam presence, regime
B, purity (boolean) — is a structural rule with no free parameter.

---

## 6. Data structure & attach point

New module `Detective/parsimony.py` (clean-room sibling of `scope.py`):

```python
@dataclass(frozen=True)
class ParsimonyLens:
    name: str            # "cohesion" | "complexity" | "overload" | ...
    vote: int            # -1 smell | 0 no-opinion | +1 clean
    raw: float | int     # the measured value (for attribution / --full)
    detail: str          # human phrase: "3 disjoint data-flow components"
    measured: bool       # False -> vote forced to 0 (provenance)

@dataclass(frozen=True)
class ParsimonySignals:
    lenses: tuple[ParsimonyLens, ...]
    flagged: bool        # >= 2 lenses at -1
    agreement: int       # count of -1 lenses
    dominant: str | None # attribution: strongest -1 lens, else None

def parsimony_from_function(func_node, scope: ScopeMap) -> ParsimonySignals: ...
```

- `ScopeMap` gains one additive, backward-compatible field: `parsimony: ParsimonySignals | None =
  None` (defaulted, in the same spirit as the other getattr-defaulted fields — an older path simply
  has None).
- `engine.diagnose` already composes a `ProfilingResult`-derived `ScopeMap` **with** an AST-derived
  structural read (`_count_decompose_seams`). `parsimony_from_function` slots into that exact seam:
  diagnose passes the function AST + the just-built `ScopeMap` (for the behavioural/regime/seam
  lenses it already holds) and attaches the result. No new profiling pass; the behavioural lens
  reuses the mutant set diagnose already has.

---

## 7. Surface (`cli._format_scope`)

An **advisory block**, clearly labelled, below the existing regime/seam guidance:

```
  parsimony (advisory — stylistic, not proof):
    ⚠ flagged — 3 lenses agree: cohesion (3 disjoint components) ·
      behavioural overload (41 DOF in 12 lines) · un-taken seam
    → a human/model call: split candidates are advisory; any split still
      goes through `decompose --apply` (the proof gate).
```

- When not flagged: a single clean line (or nothing under `--terse`), never noise.
- `--full` / `--json` expose every lens's `raw`/`vote`/`measured` for a caller that wants the detail
  — the same tiering `converge` already uses.
- The imperative is always "a human/model call" — the surface never tells the caller a rewrite is
  safe; only the proof gate does.

---

## 8. Beyond the function-unit read

- **Repo / module / class STATIC map — BUILT** (`detective parsimony <path>`, `parsimony_map.py`):
  rolls up the AST-only lenses (complexity · cohesion · interface width · structural seam) over a
  tree, worst-first, with a clean-percent score per module and class. ADVISORY — no mutant, no
  proof, writes nothing — the one repo-scale surface, and it says so. Home = Detective (its lenses
  live there); the "no `detective src/`" law is scoped to PROOF (there is no repo-scale mutation
  profile), which this does not claim. Its `_clean_pct` is Detective-pinned; the fusion reuses the
  pinned per-function combiners.
- **Still deferred:** duplication (copy-paste), import-layering / abstraction-barrier contracts
  (import-linter-style). Naming quality (subjective — evidence-only + an optional bounded model
  opinion later). Any automated ranking inside Uroboros's churn (the driver prioritises).
- **Naming quality / "is this the *right* abstraction"** — genuinely subjective. MVP surfaces
  *structural evidence* only (e.g. "this name is one char", "these two components could be two
  procedures"); an optional **bounded, typed model opinion** (select a suggestion into a schema —
  never drives) is a later add that preserves Law 1.
- **Any automated stylistic ranking** — the driver (human/large model) prioritises across functions;
  the engine does not. (This is the ModelAtlas percentile/MMR machinery — validated as *not needed*
  once the automation stays provable-only.)

---

## 9. Build order (each step: Serena-probe the wiring, Detective-pin the behaviour)

1. `parsimony.py` scaffold: `ParsimonyLens` / `ParsimonySignals` + the pure lens readers that only
   *wrap* existing computers (complexity, purity, interface width, seam, regime, overload). Pin each
   pure reader with `detective converge`.
2. **cohesion**: the def-use component count. The one new metric — pin it hardest (it has the most
   branches: structural bindings, aug-targets, trivial-function zero). Validate on real
   Detective/Wesker functions (a known God-function vs a known clean one) before trusting the cutoff-
   free structural rule.
3. **fusion**: `parsimony_from_function` — ternary projection + ≥2-agreement + dominant attribution +
   the measured→0 provenance rule. Pin it.
4. **calibrate** the two numeric backstops (complexity, overload density) on the real corpus — measure
   the distribution, pick a loose backstop, record why. Do not fit to examples.
5. **attach**: `ScopeMap.parsimony` field + `diagnose` composition. Pin diagnose's assembly.
6. **surface**: `cli._format_scope` advisory block + `--full`/`--json`. Snapshot-test the render.
7. **Uroboros boundary check**: confirm the crawl ignores `parsimony` for its churn and (optionally)
   routes a flagged-residue note to an existing review bucket — no new Uroboros action loop.

Green pytest at each step is the proof; a kill count with a red suite is nothing.

---

## 10. Honesty invariants (the things a reviewer checks)

- Advisory output **never** triggers a write. Grep the call graph: no path from `ParsimonySignals`
  to `apply_decomposition`.
- Every lens carries `measured`; an unmeasured lens votes 0. No `getattr(..., default)` that could
  absorb a wrong field name into a silent clean verdict (the MCP bug Detective already caught once).
- No hand-tuned weighted sum anywhere. Fusion is agreement-count over ternary votes.
- Every flagged read names its `dominant` lens — attribution, not a bare number.
- The two numeric cutoffs carry a comment recording the corpus they were calibrated on and the date.
