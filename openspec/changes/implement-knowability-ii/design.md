# Design

Section references: `KII §n` = `docs/theory/knowability_ii/KNOWABILITY_II.md`; `NS` =
`NEGATIVE_SPECIFICATION.md`; `CD` = `COMMUNICATING_DETERMINISM.md`; `ARCH` = `ARCHITECTURE.md`.
Code locations are as read at Wesker 2fbd029 / Detective ce2a500; re-locate with `find_symbol` before
editing (AGENTS.md: `find_referencing_symbols` before every edit).

## 1. Division of labour (unchanged in kind)

Wesker **measures**: it generates the operator universe, runs mutants in process, and records what was
observed. Detective **decides and speaks**: it types each survivor, resolves what structure and the corpus
can, orders what the teacher must, and prints signs whose map from state is injective over remedies.

Everything new in Wesker is **annotation on records that already exist**, defaulting absent. Everything
new in Detective is **a consumer of that annotation plus a ledger**, defaulting off. The one-function law
(ARCH §11) is untouched: a premise is an entry with an origin, never a wider run.

## 2. Data shapes

### 2.1 Wesker — survivor/killed record extension (W2–W5)

Each entry of `ProfilingResult.survivor_records` / `killed_records` (plain dicts; cached results round-trip
unchanged) MAY carry three new optional keys. Absent means "not measured", never "zero".

```json
{
  "mutant_id": "…", "mutant": "…", "category": "BOUNDARY", "mutated_line": 12, "dimension": "BOUNDARY:Lt~far",
  "site": {                                   // W2 — present only when site_trace=True
    "site_id": "L12:Compare:0",               // line : node type : ordinal within the line
    "reached": ["tests/test_x.py::test_a", "…"],   // covering tests whose admissible trace executed the site
    "infected": ["tests/test_x.py::test_a"],      // subset of reached: the local value differed
    "propagated": [],                              // subset of infected: that test killed (value or crash)
    "n_reached": 2, "n_infected": 1, "n_propagated": 0
  },
  "constraint": {                             // W3 — present for every mutant whose site is located
    "reach": {"text": "net > threshold", "kind": "linear", "vars": ["subtotal","discount","threshold"], "opaque_guards": 0},
    "infect": {"text": "net == threshold", "kind": "linear", "vars": ["subtotal","discount","threshold"]},
    "bindings": {"net": "subtotal - discount"}  // single-assignment lets, inlined so formulas are over parameters
  },
  "surprise": {                               // W4 — present only when site_trace=True and n_infected>0 and n_propagated==0
    "n": 1, "q_floor": 0.83, "q_ceiling": null, "bits_floor": 2.56, "bits_ceiling": null, "base": "measured"
  }                                           // base ∈ {"measured","unmeasured"}; unmeasured ⇒ no bits, never 0
}
```

`SCORED_DISPOSITIONS` and `mutant_disposition` are untouched (CONSTRAINT 9). A `site` block never
changes `killed`, `killed_by` or the disposition; it is evidence about *why* a survivor survived.

### 2.2 Wesker — formulas (W3)

`Wesker/constraints.py` (new, standard library only):

```python
@dataclass(frozen=True)
class Formula:
    text: str                # ast.unparse of the expression over parameter names
    kind: str                # "boolean" | "linear" | "polynomial" | "opaque"
    vars: tuple[str, ...]    # free parameter names (after inlining single-assignment bindings)
    opaque_guards: int = 0   # guards on the path that could not be rendered in L (calls, attributes, …)

def reach_formula(func_node, mutated_line, site_id) -> Formula
def infect_formula(mutant) -> Formula          # per-category table, KII §4 Def 4.1; "opaque" for STATE/STMT/EXCEPTION
def formula_kind(expr: ast.expr, params: frozenset[str]) -> str   # (pure — pinned): the kind classifier
def inline_bindings(func_node, mutated_line) -> dict[str, str]   # single-assignment names on the path to the site
```

`formula_kind` rules: `boolean` iff every leaf is a bool/comparison of params to constants with no
arithmetic; `linear` iff arithmetic is `+ - ` and `*`/`//`/`%` only against an int constant; `polynomial`
iff only `+ - * **` with int exponents; otherwise `opaque` (calls, attributes, subscripts, floats under
`/`, strings under arithmetic).

The infect table is a module-level dict keyed by `(category, original-op, replacement-op)` with a
rendering function; every row is a truth-table intent test (W3.3). Rows not in the table render `opaque`.

### 2.3 Detective — the solver (D1)

`Detective/entail.py` (new). Modelled on TrialLedger `layer2/entail.py`; standard library only.

```python
# Terms: int/float(Fraction)/bool/str literals, parameter names, + - * // % ** (int exp), comparisons,
# and/or/not. Parsed from Formula.text with ast; anything outside the grammar ⇒ Opaque(name).
@dataclass(frozen=True)
class Verdict:
    status: str                     # "ENTAILED" | "REFUTED" | "UNDETERMINED" | "INCONSISTENT"
    deciding: tuple[str, ...]       # minimal premise ids that decided it (empty when none did)
    witness: dict[str, object] | None   # a satisfying assignment for the QUERY when status is UNDETERMINED/REFUTED-of-negation, else None
    blockers: tuple[str, ...]       # opaque content that stopped the decision
    bound_hit: bool                 # True ⇒ UNDETERMINED is a bound, not a finding

def components(formulas: list[Formula]) -> list[frozenset[str]]        # by shared variable
def domain_for(var, formulas, premises, bound) -> list[object]         # constants ±1, boundary_probe_values, declared bound
def decide(query: Formula, premises: list[Premise], bound: int = 10_000) -> Verdict
def decide_pair(reach: Formula, infect: Formula, premises, bound) -> tuple[Verdict, Verdict]   # reach alone; reach∧infect
```

Semantics (KII Def 4.4): enumerate the query's component exactly; `ENTAILED` iff premises satisfiable
and premises ∧ ¬query unsatisfiable; `REFUTED` iff premises satisfiable and premises ∧ query
unsatisfiable; `INCONSISTENT` iff premises unsatisfiable; else `UNDETERMINED` (with `bound_hit` when the
enumeration was cut). `deciding` is computed by dropping premises one at a time and keeping those whose
removal flips the status (minimal set, greedy; recorded as "a minimal set", never "the minimum").

### 2.4 Detective — premises (D2)

`Detective/premises.py` (new). Store `.detective/premises.json` through `atomic_store.write_json_store`.

```python
@dataclass(frozen=True)
class Premise:
    id: str                 # content digest of (formula_text, scope, origin)
    formula_text: str       # in L; parsed by entail
    scope: str              # "function:<file>::<qualname>" | "module:<path>" | "repo"
    origin: str             # "author" | "caller" | "default" | "corpus"
    status: str             # "confirmed" | "proposed" | "rejected"
    source: str             # flag id / fence id / call site "file:line" / near-miss id / convention name
    created: str            # ISO date
    note: str = ""

def premise_admission(origin, spine_confirmed, retains_plurality, user_confirmed) -> str   # (pure — pinned)
#   "confirmed"    author|default with user_confirmed; corpus with spine_confirmed ∧ retains_plurality ∧ user_confirmed
#   "proposed"     corpus (or caller) without user_confirmed
#   "inadmissible" corpus without spine_confirmed or without retains_plurality (NS Def 9.3)
def s_version(confirmed: list[Premise]) -> str   # sha256 of sorted ids, first 12 hex
def in_scope(p: Premise, func_key: str) -> bool
```

`flag` (equivalence) writes `Premise(formula_text="equivalent(<mutant_id>)", origin="author", status="confirmed",
source="flag:<id>")`. `flag --fence` writes `formula_text="forbidden(<x>,<y>)"`. A censor
(`censor.Censor`) writes `origin="corpus", status="proposed"`, `source` = its spine. `--input` writes
nothing here (it is a witness; `samples.py`).

### 2.5 Detective — the survivor state (D3)

`Detective/equivalence.py` gains, beside `residual_disposition` (kept; old callers unchanged):

```python
def survivor_state(
    is_killable: bool, is_crash_only: bool, structural_difficulty: str, reached: bool, inputs_expressible: bool,
    reach_status: str,        # Verdict.status of reach alone, or "UNMEASURED"
    pair_status: str,         # Verdict.status of reach ∧ infect, or "UNMEASURED"
    violated_confirmed: bool, # a satisfying assignment exists only by violating a confirmed premise
    n_infected: int, n_propagated: int, surprise_above_knee: bool,
    oracle_blind: bool,       # D8: propagated at the codomain but every covering oracle is in one ω-class there
    bound_hit: bool, premises_inconsistent: bool,
) -> str:
    """(pure — pinned) KII §5 Prop 5.2 — the table is this function's intent test."""
```
Return codes, in precedence order: `inconsistent_premises` · `killer_ready` · `dead_site` ·
`local_equivalent` · `masked` · `reachable_if` · `pseudo_tested_oracle` · `open_at_bound` · then the
existing `value_residual` / `fixture_residual` / `structural_residual` / `genuine_equivalent` exactly as
`residual_disposition` orders them. `dof_zero` is NOT a return code (CONSTRAINT 1): the D4 pipeline turns
it into `killer_ready` by executing the solver's witness before `survivor_state` is called.

```python
def survivor_region(state: str, bears_on_intent: bool, deciding_origin: str) -> str   # (pure — pinned)
#   "structure" | "corpus" | "teacher" | "code" | "none"
def survivor_remedy(state: str) -> str                                            # (pure — pinned), the printed remedy
```

Injectivity test (D3.3): over all states, `survivor_remedy` values that differ ⇒ printed sign prefixes
differ; the test enumerates the table in KII §5 literally.

### 2.6 Detective — κ (D5)

`Detective/kappa.py` gains:

```python
def premise_kappa(candidate: Premise, open_survivors: list[SurvivorFormulas], confirmed: list[Premise], bound) -> tuple[int, int]
#   floor: survivors in candidate's component whose decide() status changes with candidate adopted
#   ceiling: floor + survivors whose status changes when ALL proposed premises sharing a variable with candidate are also adopted
def rank_teacher_queue(items, kappas) -> list        # by floor desc, ceiling desc, surprise desc
def measure_d(adopted: list[Premise], call_graph) -> int   # count of adoptions that were bridges at the quotient (kappa.is_bridge)
```

Every emitted κ is a dict `{"floor": int, "ceiling": int, "s_version": str}`.

### 2.7 Detective — the five-number report (D9)

`ConvergeResult` and the audit result gain an optional `information: dict | None`:

```json
{"H0": 17, "L": 17, "L_ind": 0, "H_star": 0, "I_ext": 0, "s_version": "a1b2c3d4e5f6", "basis": "coverage analog, not bits"}
```
Printed as one line after the verdict line: `info  H₀ 17 · L 17 · L_ind 0 · H* 0 · I_ext 0 (coverage analog; S a1b2c3)`.

## 3. Decisions

1. **Site probe by expression wrapping, opt-in.** W2 compiles an instrumented original and mutant where
   the fire-site expression is wrapped `__wesker_site__(<expr>, site_id)`; the probe appends a stable
   observation (`repr` capped at 200 chars, else `type(v).__name__`) to a per-test list. Infection = the
   two lists differ. Off by default (`site_trace=False`), so V5 holds trivially. The alternative — a
   `sys.settrace` value reader — cannot see sub-expression values; rejected.
2. **Formulas over parameters, with single-assignment inlining.** The shipping example's guard is over
   `net`, a let-bound name; `inline_bindings` rewrites it over parameters so the solver's variables are
   the function's inputs. Multi-assignment or loop-carried names ⇒ `opaque`.
3. **One solver, exact enumeration, no SMT.** CONSTRAINT 10. Domains are the constants in the component
   ±1, the existing `boundary_probe_values`, and the declared bound; linear single-variable components are
   therefore exhaustive (KII Prop 4.3 (i)); polynomial ones are bounded and say so.
4. **The solver's witness is a candidate input, nothing more.** D4 routes it through the existing witness
   path (`classify_survivor` → `Witness`); a kill is still an observed difference (CONSTRAINT 3).
5. **DOF⁰ test = no intent bears on the variables.** `bears_on_intent(vars, premises_in_scope, fences,
   intent_tests_referencing_params)` is a pure decision: True iff any confirmed premise, fence, or
   hand-written intent test (origin census, ARCH §0.1 "intent") mentions one of the variables. False ⇒
   synthesize and characterize, no question.
6. **κ is recomputed, never stored.** CONSTRAINT 6. Cost is bounded by component size; components are
   small by construction (one function's survivors). The call graph is read only for bridges and `d`.
7. **Surprise base is this function's own q.** CONSTRAINT 7. The repo-wide q (ceiling) is read from
   `.wesker/mutation_report.json`'s prior run if present, else `null`.
8. **Old codes stay.** `residual_disposition` keeps its signature and codes; `survivor_state` is a new
   decision that *consumes* it for the tail of its precedence, so every existing consumer and test is
   unchanged, and `consumption.py` / `distinction.py` must find the new decision consumed and its codes
   distinguished (D3.4).
9. **The teacher queue is a verb, not the default output.** `detective ask file::fn` prints it; `DO THIS`
   names only the max-κ item (CD §6: one imperative, never a menu).
10. **Policy id moves once, at W1.** W2–W5 add annotation only and do not change the universe or the
    observation rule, so they do not move the id; the CHANGELOG says so explicitly, as it did for policy 8→9.

## 4. Non-decisions (left open, named)

- The null model for surprise beyond per-execution independence (KII §13 item 3).
- The premise regime key (KII §13 item 4): premises are scoped to the function by default; module/repo
  scope is opt-in with `--scope`.
- The entropy-bit report (KII §13 item 6): coverage analogs only, labelled.
- STATE/STMT infection formulas beyond the single-assignment case (KII §13 item 2): `opaque`.
